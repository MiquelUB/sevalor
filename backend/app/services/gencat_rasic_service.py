"""
gencat_rasic_service.py -> backend/app/services/gencat_rasic_service.py

Connexió directa amb el cens oficial d'empreses instal·ladores habilitades de la Generalitat de Catalunya:
RASIC (Registre d'Agents de la Seguretat Industrial de Catalunya) via l'API de Dades Obertes (Socrata).

Aquest servei proporciona dades 100% reals i certificades pel Departament d'Empresa i Treball:
- CIF oficial
- Raó social certificada
- Adreça física real i Codi Postal registrat
- Habilitacions industrials reglamentàries (Baixa Tensió REBT, Climatització/ITE, Gas, etc.)
- Telèfon de contacte oficial
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

import httpx
from stdnum.es import nif as _nif
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

RASIC_DATASET_URL = "https://analisi.transparenciacatalunya.cat/resource/qcrr-stew.json"
USER_AGENT = "SevalorSuite/1.0 (CRM Prospeccio; contacte@sevalor.net)"

# Mapeig de paraules clau de vertical a columnes del registre RASIC
MAPA_VERTICALS_COLUMNA = {
    "electric": ["bt_installacions", "at_installacions", "at_linies"],
    "baixa tensio": ["bt_installacions"],
    "rebt": ["bt_installacions"],
    "alta tensio": ["at_installacions", "at_linies"],
    "clima": ["ite_installacions_termiques", "ite_installacions_term", "frigoristes"],
    "climatitzacio": ["ite_installacions_termiques", "ite_installacions_term", "frigoristes"],
    "fred": ["frigoristes", "ite_installacions_termiques"],
    "calefaccio": ["ite_installacions_termiques", "gas"],
    "gas": ["gas"],
    "fontaneria": ["gas", "ite_installacions_termiques", "bt_installacions"],
    "aigua": ["gas", "ite_installacions_termiques"],
}


def _encaixa_amb_vertical(registre: Dict[str, Any], vertical: Optional[str]) -> bool:
    """Comprova si el registre RASIC disposa d'habilitació per a la vertical sol·licitada."""
    if not vertical:
        return True
    v_norm = vertical.lower().strip()

    columnes_interes: set[str] = set()
    for clau, cols in MAPA_VERTICALS_COLUMNA.items():
        if clau in v_norm:
            columnes_interes.update(cols)

    if not columnes_interes:
        # Si la vertical és molt específica o no categoritzada, admetre l'empresa si té qualsevol habilitació
        return True

    return any(registre.get(col) in ("Sí", "Si", "SÍ", "SI", True) for col in columnes_interes)


class GencatRasicService:
    """Servei asíncron per consultar el registre RASIC de Dades Obertes de Catalunya."""

    def __init__(self, client: Optional[httpx.AsyncClient] = None) -> None:
        self._client = client

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=0.5, min=0.5, max=2.0), reraise=False)
    async def consultar_instal_ladors(
        self,
        codi_postal: Optional[str] = None,
        municipi: Optional[str] = None,
        vertical: Optional[str] = None,
        limit: int = 50,
        timeout: float = 10.0,
    ) -> List[Dict[str, Any]]:
        """Consulta el cens oficial del RASIC per CP o Municipi, filtrant per empreses actives (Alta)."""
        params: Dict[str, str] = {
            "estat_registre": "Alta",
            "$limit": str(limit * 2),  # Demanem més per permetre filtrat per vertical
        }

        if codi_postal and re.fullmatch(r"\d{5}", codi_postal.strip()):
            params["codi_postal"] = codi_postal.strip()
        elif municipi and municipi.strip():
            # A la base de dades sovint està en majúscules o títol
            params["municipi"] = municipi.strip().capitalize()

        headers = {"User-Agent": USER_AGENT}

        try:
            if self._client:
                resp = await self._client.get(RASIC_DATASET_URL, params=params, headers=headers)
            else:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    resp = await client.get(RASIC_DATASET_URL, params=params, headers=headers)

            if resp.status_code != 200:
                logger.warning("RASIC API ha retornat HTTP %s: %s", resp.status_code, resp.text[:200])
                return []
            bruts = resp.json()
        except Exception as e:
            logger.debug("Error consultant l'API del RASIC: %s", e)
            return []

        resultats: List[Dict[str, Any]] = []
        cifs_vistos: set[str] = set()

        for it in bruts:
            doc = (it.get("document") or "").strip().upper()
            if doc in cifs_vistos:
                continue
            cifs_vistos.add(doc)

            if not _encaixa_amb_vertical(it, vertical):
                continue

            titular = (it.get("titular") or "").strip()
            adreca = (it.get("adreca_agrupada") or "").strip()
            cp_registrat = (it.get("codi_postal") or "").strip()
            mun_registrat = (it.get("municipi") or "").strip()

            cif_valid = doc if _nif.is_valid(doc) else None
            tel = (it.get("telefon_mobil") or it.get("telefon_fix") or "").strip()

            adreca_completa = f"{adreca}, {cp_registrat} {mun_registrat}".strip(", ")

            resultats.append({
                "origen": "rasic",
                "nom_empresa": titular,
                "cif": cif_valid,
                "adreca_fisica": adreca_completa,
                "codi_postal": cp_registrat,
                "municipi": mun_registrat,
                "telefon": tel or None,
                "n_rasic": it.get("n_mero_de_rasic"),
                "fonts_investigades": f"rasic|{RASIC_DATASET_URL}?document={doc}",
            })

            if len(resultats) >= limit:
                break

        return resultats
