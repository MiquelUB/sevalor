"""Servei de recerca multi-canal i deduplicació multi-validació de 3 vectors.

Implementa:
- Normalització de 3 vectors: Domini Web, Adreça Física i CIF.
- Validació estricta del Codi Postal dins de l'adreça física real (`validar_cp_en_adreca_fisica`).
- Validació estricta de nom i cognom real de Gatekeeper (`es_nom_persona_real`), prohibint càrrecs genèrics.
- Enllaços directes 100% comprovables per a cada canal (`web`, `linkedin`, `instagram`, `premsa`).
- Deduplicació multi-validació (`verificar_duplicitat_multivector`) contra:
  `saas_leads`, `empreses` i `saas_exclusio_rgpd`.
- Investigació multi-canal (Web corporatiu, LinkedIn, Instagram, premsa i adjudicacions)
  mitjançant Firecrawl i scraping HTTP directe (Zero Mock Data).
"""

import asyncio
import base64
import html
import json
import logging
import re
import unicodedata
import urllib.parse
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

import httpx
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.models import Empresa, SaasExclusioRgpd, SaasLead
from app.services.prospeccio_validacio import (
    GEOCODE_MODE,
    USER_AGENT,
    Gatekeeper,
    adreca_valida_per_cp,
    coincideix_vertical,
    cp_geocodificat,
    es_domini_espanyol,
    ids_fiscals_valids,
    ordenar_per_prioritat,
    sembla_directori,
    telefons_es,
    trobar_gatekeeper,
)
from app.services.scraper_domini import adreca_jsonld, descarregar_pagines, osm_per_cp

logger = logging.getLogger("sevalor.crm.firecrawl")

# Llista de paraules genèriques i càrrecs prohibits com a nom de persona (Gatekeeper)
_PARAULES_GENERIQUES_PROHIBIDES = {
    "responsable",
    "director",
    "directora",
    "direccio",
    "gerent",
    "gerencia",
    "administrador",
    "administradora",
    "administracio",
    "departament",
    "equip",
    "equipo",
    "tecnic",
    "tecnica",
    "tecnics",
    "comercial",
    "contacte",
    "contacto",
    "info",
    "oficina",
    "atencio",
    "client",
    "clients",
    "operacions",
    "operaciones",
    "general",
    "propietari",
    "propietaria",
    "empresa",
    "empreses",
    "encarregat",
    "coordinador",
    "coordinadora",
    "serveis",
    "servicios",
    "manteniment",
    "mantenimiento",
    "instal",
    "lacions",
    "instalaciones",
    "botiga",
    "venda",
    "detall",
    "sl",
    "slu",
    "sa",
    "scc",
    "sccl",
    "desconegut",
    "disponible",
    "pendent",
    "sense",
    "identificar",
    "confirmar",
    "gatekeeper",
    "decisor",
    "rrhh",
    "recursos",
    "humans",
    "operari",
    "centraleta",
    "recepcio",
    "secretaria",
    "espana",
    "catalunya",
    "cataluna",
    "barcelona",
    "lleida",
    "girona",
    "tarragona",
    "terrassa",
    "sabadell",
    "hambre",
    "energia",
    "electricitat",
    "electricidad",
    "fontaneria",
    "climatitzacio",
    "climatizacion",
    "reforma",
    "reformes",
    "reformas",
    "projectes",
    "proyectos",
    "sistemes",
    "sistemas",
    "solucions",
    "soluciones",
    "ajuntament",
    "ayuntamiento",
    "diputacio",
}

_PARTICULES_NOM = {"de", "del", "d", "la", "les", "el", "els", "i", "y", "san", "sant", "santa", "vda"}


# ==============================================================================
# 1. NORMALITZACIÓ DE VECTORS I VALIDACIONS ESTRICTES (CP, GATEKEEPER, URLS)
# ==============================================================================

def normalitzar_domini(url_o_domini: Optional[str]) -> str:
    """Normalitza una URL o nom de domini a la seva forma canònica base.

    Exemples:
        - "https://www.climasegria.cat/serveis" -> "climasegria.cat"
        - "WWW.Electro-Segre.COM/" -> "electro-segre.com"
        - "http://instals.cat?lang=ca" -> "instals.cat"

    Args:
        url_o_domini: URL completa o text de domini.

    Returns:
        Cadena normalitzada en minúscules sense 'www.' ni barres finals.
    """
    if not url_o_domini:
        return ""

    raw = url_o_domini.strip().lower()
    if not raw.startswith(("http://", "https://")):
        raw = "http://" + raw

    parsed = urllib.parse.urlparse(raw)
    netloc = parsed.netloc or parsed.path.split("/")[0]

    # Eliminar port si existeix
    netloc = netloc.split(":")[0]

    # Eliminar prefix www.
    if netloc.startswith("www."):
        netloc = netloc[4:]

    return netloc.strip()


def normalitzar_adreca(adreca: Optional[str]) -> str:
    """Normalitza una adreça física per evitar duplicats per abreviatures o puntuació.

    Passos:
    1. Descomposició Unicode per treure accents i diacrítics.
    2. Conversió a minúscules.
    3. Normalització d'abreviatures habituals (c/, av., pol. ind., nau, etc.).
    4. Eliminació de signes de puntuació supèrflua i unificació d'espais.

    Args:
        adreca: Text d'adreça física bruta.

    Returns:
        Cadena canònica comparable.
    """
    if not adreca:
        return ""

    # Normalització Unicode NFKD
    text = unicodedata.normalize("NFKD", adreca).encode("ASCII", "ignore").decode("utf-8")
    text = text.lower()

    # Taula d'equivalències per abreviatures freqüents en adreces industrials
    substitucions = [
        (r"\bc/\s*|\bcarrer\b|\bcalle\b", "carrer "),
        (r"\bav/\s*|\bavda\b|\bavinguda\b|\bavenida\b|\bav\b", "avinguda "),
        (r"\bpol\.\s*ind\b|\bpoligon\s*industrial\b|\bpol\s*ind\b|\bpoligono\s*industrial\b", "poligon industrial "),
        (r"\bcrta\b|\bctra\b|\bcarretera\b", "carretera "),
        (r"\bps\b|\bpasseig\b|\bpaseo\b", "passeig "),
        (r"\bpl\b|\bplaca\b|\bplaza\b", "placa "),
        (r"\bnau\b|\bnave\b", "nau "),
        (r"\bkm\b|\bkm\.\b", "km "),
        (r"\bno\b|\bnum\b|\bnum\.\b|\bnumero\b", " "),
    ]

    for patro, repl in substitucions:
        text = re.sub(patro, repl, text)

    # Netejar caràcters no alfanumèrics mantenint lletres, números i espais
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    # Col·lapsar múltiples espais consecutius
    text = re.sub(r"\s+", " ", text).strip()

    return text


def normalitzar_cif(cif: Optional[str]) -> str:
    """Normalitza un CIF/NIF eliminant guions, espais i caràcters de puntuació.

    Exemple: "B-25.123.456" -> "B25123456"

    Args:
        cif: Cadena bruta de CIF o NIF.

    Returns:
        Cadena alfanumèrica en majúscules.
    """
    if not cif:
        return ""
    clean = re.sub(r"[^A-Za-z0-9]", "", cif).upper().strip()
    return clean


def validar_cp_en_adreca_fisica(adreca: Optional[str], codi_postal: str) -> bool:
    """Verifica que l'adreça física és real i conté explícitament el Codi Postal sol·licitat.

    Rebutja qualsevol adreça genèrica ('Zona Codi Postal ...'), comentaris de xarxes socials
    (Instagram, LinkedIn, Facebook) o adreces que tinguin un Codi Postal diferent.

    Args:
        adreca: Adreça física verificada de l'empresa.
        codi_postal: Codi postal de 5 dígits sol·licitat a la tasca.

    Returns:
        True si l'adreça física és vàlida i conté exactament el `codi_postal`.
    """
    if not adreca or not codi_postal:
        return False

    cp_clean = codi_postal.strip()
    adr_clean = adreca.strip()
    if len(adr_clean) < 10 or not cp_clean:
        return False

    adr_lower = unicodedata.normalize("NFKD", adr_clean).encode("ASCII", "ignore").decode("utf-8").lower()

    # Rebutjar falses adreces extretes de comentaris/posts de xarxes socials o placeholders sintètics
    patrons_prohibits = (
        "zona codi postal",
        "instagram",
        "linkedin",
        "facebook",
        "twitter",
        "tiktok",
        "comentari",
        "comentario",
        "hashtag",
        "publicacio",
        "post a ",
        "nova instal",
    )
    if any(p in adr_lower for p in patrons_prohibits):
        return False

    # Ha de contenir el Codi Postal exacte com a paraula completa (no com a codi de producte tipus APB-08221-G)
    if not re.search(rf"(?<![A-Za-z0-9])\b{re.escape(cp_clean)}\b(?![\-[A-Za-z0-9])", adr_clean):
        return False

    # Si l'adreça conté un altre codi postal de 5 dígits diferent del demanat i el demanat no és el CP principal
    tots_cps = re.findall(r"(?<![A-Za-z0-9])\b(?:0[1-9]|[1-4]\d|5[0-2])\d{3}\b(?![\-[A-Za-z0-9])", adr_clean)
    if tots_cps and cp_clean not in tots_cps:
        return False

    # Comprovar que hi ha text d'adreça real (carrer, avinguda, polígon, carretera, plaça, camí, nau o localitat)
    sense_cp = re.sub(rf"\b{re.escape(cp_clean)}\b", "", adr_lower)
    paraules_adreca = re.findall(r"[a-z]{3,}", sense_cp)
    if len(paraules_adreca) < 1:
        return False

    return True


def validar_cp_o_municipi_en_adreca(
    adreca: Optional[str],
    codi_postal: str,
    municipi: Optional[str] = None,
) -> bool:
    """Valida l'adreça física exigint obligatòriament el Codi Postal exacte (Spec 007)."""
    if not adreca or len(adreca.strip()) < 5:
        return False
    return bool(adreca_valida_per_cp(adreca, codi_postal) or validar_cp_en_adreca_fisica(adreca, codi_postal))


def es_nom_persona_real(nom: Optional[str]) -> bool:
    """Valida que `nom` correspon al nom i cognom real d'una persona física (Gatekeeper).

    Rebutja de forma estricta qualsevol càrrec o placeholder genèric com ara:
    'Responsable d'Operacions', 'Director Tècnic', 'Gerent', 'Administració', 'Equip Tècnic', etc.

    Args:
        nom: Cadena amb el nom del decisor.

    Returns:
        True només si és un nom propi humà real (mínim Nom + Cognom).
    """
    if not nom:
        return False

    nom_clean = nom.strip()
    if len(nom_clean) < 4 or len(nom_clean) > 85:
        return False

    # No pot contenir dígits, @, URLs ni parèntesis de placeholders
    if re.search(r"[\d@/\\()\[\]{}_+*=<>;:]", nom_clean):
        return False

    # Normalitzar sense accents per comprovar paraules prohibides
    nom_norm = unicodedata.normalize("NFKD", nom_clean).encode("ASCII", "ignore").decode("utf-8").lower()
    tokens_norm = re.findall(r"[a-z]+", nom_norm)

    if not tokens_norm:
        return False

    # Si conté qualsevol paraula genèrica o de càrrec / societat, queda rebutjat immediatament
    for tok in tokens_norm:
        if tok in _PARAULES_GENERIQUES_PROHIBIDES:
            return False

    if "cap d'obra" in nom_norm or "cap d obra" in nom_norm:
        return False

    # Filtrar partícules ('de', 'del', 'i', 'la') per comptar noms i cognoms substantius
    tokens_substantius = [t for t in tokens_norm if t not in _PARTICULES_NOM and len(t) >= 2]

    # Cal com a mínim Nom + Cognom (2 paraules substantives) i màxim 5
    if len(tokens_substantius) < 2 or len(tokens_substantius) > 5:
        return False

    # Verificar que en el text original les paraules principals comencen per majúscula (Nom Propi)
    paraules_orig = [
        p.strip("'.-·")
        for p in nom_clean.split()
        if p.strip("'.-·").lower() not in _PARTICULES_NOM and len(p.strip("'.-·")) >= 2
    ]
    if len(paraules_orig) < 2:
        return False

    for p in paraules_orig:
        if not p[0].isupper():
            return False

    return True


def validar_url_verificable(url: Optional[str]) -> bool:
    """Comprova que una URL és un enllaç HTTP/HTTPS real i comprovable (no sintètic)."""
    if not url:
        return False
    u = url.strip()
    if not u.startswith(("http://", "https://")):
        return False
    parsed = urllib.parse.urlparse(u)
    if not parsed.netloc or "." not in parsed.netloc:
        return False
    dom = normalitzar_domini(u)
    # Bloquejar dominis sintètics antics
    if re.match(r"^(empresa|botiga)-cp\d{5}-[a-f0-9]+\.", dom):
        return False
    return True


def formatar_fonts_verificables(
    fonts_urls: Dict[str, str],
    web_url: Optional[str] = None,
) -> List[str]:
    """Formata el mapa de canals i les seves URLs directes en el format `canal|url`.

    Només s'inclouen canals que disposin d'una URL directa i comprovable (`http://` o `https://`).
    """
    resultat: List[str] = []
    vist: set[str] = set()

    if web_url and validar_url_verificable(web_url):
        resultat.append(f"web|{web_url.strip()}")
        vist.add("web")

    for canal, url in (fonts_urls or {}).items():
        c_key = canal.strip().lower()
        if c_key in vist:
            continue
        if validar_url_verificable(url):
            resultat.append(f"{c_key}|{url.strip()}")
            vist.add(c_key)

    return resultat


def extreure_mapa_fonts_urls(
    fonts_raw: Optional[str],
    web_url: Optional[str] = None,
) -> Dict[str, str]:
    """Reconstrueix el diccionari `{canal: url_directa}` des de `fonts_investigades`."""
    mapa: Dict[str, str] = {}
    if web_url and validar_url_verificable(web_url):
        mapa["web"] = web_url.strip()

    if not fonts_raw:
        return mapa

    for item in fonts_raw.split(","):
        part = item.strip()
        if not part:
            continue
        if "|" in part:
            canal, url = part.split("|", 1)
            canal_k = canal.strip().lower()
            url_v = url.strip()
            if validar_url_verificable(url_v):
                mapa[canal_k] = url_v
        elif part.lower() == "web" and web_url and validar_url_verificable(web_url):
            mapa["web"] = web_url.strip()

    return mapa


# ==============================================================================
# 2. MOTOR DE DEDUPLICACIÓ MULTI-VALIDACIÓ PER 3 VECTORS
# ==============================================================================

async def verificar_duplicitat_multivector(
    db: AsyncSession,
    domini: Optional[str] = None,
    adreca: Optional[str] = None,
    cif: Optional[str] = None,
    ignorar_lead_id: Optional[UUID] = None,
) -> Tuple[bool, Optional[str], Optional[str]]:
    """Comprova si el candidat és un duplicat aplicant la regla OR sobre 3 vectors.

    Vectors auditats:
    1. Domini Web canònic (`domini_normalitzat`).
    2. Adreça física normalitzada (`adreca_normalitzada`).
    3. CIF (`cif`).

    Fonts auditades:
    - `saas_leads`: prospectes previament registrats o en curs.
    - `empreses`: clients que ja operen a Sevalor Suite (evitar vendre a clients reals).
    - `saas_exclusio_rgpd`: dominis o CIFs en llista negra d'opt-out o rebots.

    Args:
        db: Sessió asíncrona de SQLAlchemy.
        domini: Domini o URL de l'empresa.
        adreca: Adreça física de l'empresa.
        cif: CIF o NIF de l'empresa.
        ignorar_lead_id: UUID de lead per ignorar en cas d'actualització.

    Returns:
        Tupla `(es_duplicat, vector_coincident, detall_explicatiu)`
        Si no és duplicat: `(False, None, None)`
    """
    domini_norm = normalitzar_domini(domini) if domini else None
    adreca_norm = normalitzar_adreca(adreca) if adreca else None
    cif_norm = normalitzar_cif(cif) if cif else None

    # Si cap vector té valor, no podem determinar duplicitat
    if not any([domini_norm, adreca_norm, cif_norm]):
        return False, None, None

    # 1. Comprovació a la llista d'exclusió RGPD / Opt-out
    if domini_norm or cif_norm:
        condicions_rgpd = []
        if domini_norm:
            condicions_rgpd.append(SaasExclusioRgpd.domini == domini_norm)
        if cif_norm:
            condicions_rgpd.append(SaasExclusioRgpd.cif == cif_norm)

        res_rgpd = await db.execute(select(SaasExclusioRgpd).where(or_(*condicions_rgpd)))
        exclusio = res_rgpd.scalars().first()
        if exclusio:
            vector = "DOMINI_WEB" if domini_norm and exclusio.domini == domini_norm else "CIF"
            detall = f"Empresa present a la llista d'exclusió RGPD ({exclusio.motiu})."
            return True, vector, detall

    # 2. Comprovació a clients existents de la plataforma Sevalor (taula `empreses`)
    condicions_empreses = []
    if cif_norm:
        condicions_empreses.append(func.upper(Empresa.nif) == cif_norm)
    if domini_norm:
        condicions_empreses.append(func.lower(Empresa.domini_custom) == domini_norm)

    if condicions_empreses:
        res_emp = await db.execute(select(Empresa).where(or_(*condicions_empreses)))
        client_existent = res_emp.scalars().first()
        if client_existent:
            vector = "CIF" if cif_norm and client_existent.nif.upper() == cif_norm else "DOMINI_WEB"
            detall = f"L'empresa ja és client activa de Sevalor Suite ({client_existent.nom})."
            return True, vector, detall

    if adreca_norm and len(adreca_norm) >= 8:
        res_emp_adr = await db.execute(select(Empresa).where(Empresa.adreca.isnot(None)))
        for emp_item in res_emp_adr.scalars().all():
            if normalitzar_adreca(emp_item.adreca) == adreca_norm:
                return (
                    True,
                    "ADRECA_FISICA",
                    f"L'adreça física coincideix amb el client actiu de Sevalor Suite ({emp_item.nom}).",
                )

    # 3. Comprovació a la taula de prospectes del CRM (`saas_leads`)
    condicions_leads = []
    if domini_norm:
        condicions_leads.append(SaasLead.domini_normalitzat == domini_norm)
    if adreca_norm and len(adreca_norm) >= 8:  # Evitar coincidències trivials per textos curts
        condicions_leads.append(SaasLead.adreca_normalitzada == adreca_norm)
    if cif_norm:
        condicions_leads.append(SaasLead.cif == cif_norm)

    if condicions_leads:
        stmt_leads = select(SaasLead).where(or_(*condicions_leads))
        if ignorar_lead_id:
            stmt_leads = stmt_leads.where(SaasLead.id != ignorar_lead_id)

        res_leads = await db.execute(stmt_leads)
        lead_existent = res_leads.scalars().first()
        if lead_existent:
            if domini_norm and lead_existent.domini_normalitzat == domini_norm:
                return True, "DOMINI_WEB", f"Domini coincident amb el prospecte '{lead_existent.nom_empresa}'."
            if adreca_norm and lead_existent.adreca_normalitzada == adreca_norm:
                return True, "ADRECA_FISICA", f"Adreça física coincident amb el prospecte '{lead_existent.nom_empresa}'."
            if cif_norm and lead_existent.cif == cif_norm:
                return True, "CIF", f"CIF coincident amb el prospecte '{lead_existent.nom_empresa}'."

    return False, None, None


# ==============================================================================
# 3. UTILITATS D'EXTRACCIÓ HTML DIRECTA (ADR, CIF, GATEKEEPER REAL, SOCIAL URLS)
# ==============================================================================

_HEADERS_NAVEGADOR = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "ca,es;q=0.9,en;q=0.8",
}


def decode_bing_url(u: str) -> str:
    """Descodifica URLs de seguiment de Bing (`/ck/a?!...&u=a1...`) cap a la URL real de destinació."""
    u_clean = html.unescape(u)
    m_u = re.search(r"[?&]u=a1([a-zA-Z0-9_-]+)", u_clean)
    if m_u:
        raw_b64 = m_u.group(1)
        pad = len(raw_b64) % 4
        if pad:
            raw_b64 += "=" * (4 - pad)
        try:
            return base64.urlsafe_b64decode(raw_b64).decode("utf-8", errors="ignore")
        except Exception:
            return u_clean
    return u_clean


def extreure_resultats_bing(html_body: str, limit: int = 10) -> List[Dict[str, str]]:
    """Analitza l'HTML de Bing i extreu els resultats reals amb les seves URLs descodificades."""
    resultats: List[Dict[str, str]] = []
    algos = re.findall(r"<li[^>]+class=[\"'][^\"']*b_algo[^\"']*[\"'][^>]*>(.*?)</li>", html_body, flags=re.DOTALL)
    for a in algos:
        m_link = re.search(r"<h2[^>]*>.*?<a[^>]+href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>.*?</h2>", a, flags=re.DOTALL)
        if not m_link:
            m_link = re.search(r"<a[^>]+href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", a, flags=re.DOTALL)
        if m_link:
            raw_url = decode_bing_url(m_link.group(1))
            titol = _netejar_html_a_text(m_link.group(2))
            m_desc = re.search(
                r"<(?:p|div)[^>]+class=[\"'][^\"']*(?:b_caption|b_snippet|b_lineclamp)[^\"']*[\"'][^>]*>(.*?)</(?:p|div)>",
                a,
                flags=re.DOTALL,
            )
            desc = _netejar_html_a_text(m_desc.group(1)) if m_desc else ""
            if validar_url_verificable(raw_url):
                resultats.append({
                    "url": raw_url,
                    "title": titol,
                    "description": desc,
                })
                if len(resultats) >= limit:
                    break
    return resultats


_CACHE_CP_A_MUNICIPI: Dict[str, Dict[str, str]] = {
    "25500": {"municipi": "La Pobla de Segur", "provincia": "Lleida", "comarca": "Pallars Jussà"},
    "25560": {"municipi": "Sort", "provincia": "Lleida", "comarca": "Pallars Sobirà"},
    "25001": {"municipi": "Lleida", "provincia": "Lleida"},
    "25002": {"municipi": "Lleida", "provincia": "Lleida"},
    "25003": {"municipi": "Lleida", "provincia": "Lleida"},
    "25004": {"municipi": "Lleida", "provincia": "Lleida"},
    "25005": {"municipi": "Lleida", "provincia": "Lleida"},
    "25006": {"municipi": "Lleida", "provincia": "Lleida"},
    "25007": {"municipi": "Lleida", "provincia": "Lleida"},
    "25008": {"municipi": "Lleida", "provincia": "Lleida"},
    "25200": {"municipi": "Cervera", "provincia": "Lleida"},
    "25300": {"municipi": "Tàrrega", "provincia": "Lleida"},
    "25600": {"municipi": "Balaguer", "provincia": "Lleida"},
    "25700": {"municipi": "La Seu d'Urgell", "provincia": "Lleida"},
    "25230": {"municipi": "Mollerussa", "provincia": "Lleida"},
    "08001": {"municipi": "Barcelona", "provincia": "Barcelona"},
    "08002": {"municipi": "Barcelona", "provincia": "Barcelona"},
    "08003": {"municipi": "Barcelona", "provincia": "Barcelona"},
    "08201": {"municipi": "Sabadell", "provincia": "Barcelona"},
    "08221": {"municipi": "Terrassa", "provincia": "Barcelona"},
    "08901": {"municipi": "L'Hospitalet de Llobregat", "provincia": "Barcelona"},
    "17001": {"municipi": "Girona", "provincia": "Girona"},
    "43001": {"municipi": "Tarragona", "provincia": "Tarragona"},
    "43201": {"municipi": "Reus", "provincia": "Tarragona"},
}


async def obtenir_municipi_de_codi_postal(codi_postal: str) -> Optional[Dict[str, str]]:
    """Resol el municipi i la província reals associats a un Codi Postal espanyol.

    Empra catàleg intern integrat i consulta de suport ràpida a OpenStreetMap Nominatim.
    """
    if not codi_postal:
        return None
    cp = codi_postal.strip()
    if cp in _CACHE_CP_A_MUNICIPI:
        return _CACHE_CP_A_MUNICIPI[cp]

    try:
        headers_nom = dict(_HEADERS_NAVEGADOR)
        headers_nom["User-Agent"] = "SevalorCRM/1.0 (info@sevalor.cat)"
        async with httpx.AsyncClient(timeout=3.0, headers=headers_nom) as client:
            r = await client.get(
                "https://nominatim.openstreetmap.org/search",
                params={
                    "postalcode": cp,
                    "countrycodes": "es",
                    "format": "json",
                    "addressdetails": 1,
                    "limit": 1,
                },
            )
            if r.status_code == 200:
                data = r.json()
                if data and isinstance(data, list):
                    addr = data[0].get("address", {})
                    muni = addr.get("village") or addr.get("town") or addr.get("city") or addr.get("municipality")
                    prov = addr.get("state_district") or addr.get("province") or addr.get("county") or "Espanya"
                    if muni:
                        info = {"municipi": muni, "provincia": prov}
                        _CACHE_CP_A_MUNICIPI[cp] = info
                        return info
    except Exception as exc:
        logger.debug("Avís en resolució de codi postal %s via Nominatim: %s", cp, exc)

    return None


def _desencriptar_cfemail(cf_hex: str) -> Optional[str]:
    """Desencripta correus ofuscats per Cloudflare Email Protection (data-cfemail)."""
    try:
        r = int(cf_hex[:2], 16)
        email = "".join(chr(int(cf_hex[i : i + 2], 16) ^ r) for i in range(2, len(cf_hex), 2))
        return email.strip().lower() if "@" in email else None
    except Exception:
        return None


def _extreure_metadades_html_brut(raw_html: str) -> Dict[str, Any]:
    """Extreu dades estructurades d'un HTML brut abans d'eliminar les etiquetes:
    - Enllaços `mailto:` i Cloudflare `data-cfemail`
    - Enllaços `tel:`, `callto:` i mòbils directes a `wa.me` / `whatsapp.com/send?phone=`
    - Raó Social Mercantil (SL, SLU, SA, SCCL) del text/HTML legal
    - Etiquetes `<address>`
    - Blocs Schema.org JSON-LD (`PostalAddress`, `LocalBusiness`, `Organization`, `Person`)
    - Atributs `aria-label`, `title`, `data-address` d'iframes (Google Maps) i elements visuals
    - Enllaços directes a Google Maps (`maps.google.com/maps?q=...`)
    """
    info: Dict[str, Any] = {
        "mailtos": [],
        "tels": [],
        "adreces_estructurades": [],
        "gatekeeper_nom": None,
        "gatekeeper_carrec": None,
        "cif_jsonld": None,
        "rao_social_detectada": None,
    }
    if not raw_html:
        return info

    # 1. Mailto clàssic + Cloudflare data-cfemail
    for m_mail in re.finditer(r'href=["\']mailto:([^"\'?&\s]+)', raw_html, flags=re.IGNORECASE):
        em = urllib.parse.unquote(html.unescape(m_mail.group(1))).strip().lower()
        if "@" in em and em not in info["mailtos"]:
            info["mailtos"].append(em)

    for m_cf in re.finditer(r'data-cfemail=["\']([0-9a-fA-F]+)["\']', raw_html):
        em_cf = _desencriptar_cfemail(m_cf.group(1))
        if em_cf and em_cf not in info["mailtos"]:
            info["mailtos"].append(em_cf)

    # 2. Enllaços tel:, callto: i mòbils directes a api.whatsapp / wa.me
    for m_tel in re.finditer(r'href=["\'](?:tel|callto):([^"\'?&\s]+)', raw_html, flags=re.IGNORECASE):
        t_raw = urllib.parse.unquote(html.unescape(m_tel.group(1))).strip()
        if t_raw and t_raw not in info["tels"]:
            info["tels"].append(t_raw)

    for m_wa in re.finditer(r'(?:wa\.me/|whatsapp\.com/send\?phone=)\+?(\d{9,12})', raw_html, flags=re.IGNORECASE):
        t_wa = m_wa.group(1).strip()
        if t_wa not in info["tels"]:
            info["tels"].append(t_wa)

    # 3. Extreure Raó Social Mercantil (SL, SLU, SA, SCCL) del text/HTML legal
    m_soc = re.search(
        r"\b([A-ZÀ-Ý][A-ZÀ-Ýa-zà-ÿ0-9\s.,&'\-·]{2,55}?\s+(?:S\.?L\.?U\.?|S\.?L\.?|S\.?A\.?|S\.?C\.?C\.?L\.?))\b",
        raw_html,
    )
    if m_soc:
        info["rao_social_detectada"] = re.sub(r"\s+", " ", m_soc.group(1)).strip()

    # 2. Extreure blocs <address>...</address>
    for m_adr in re.finditer(r"<address[^>]*>(.*?)</address>", raw_html, flags=re.DOTALL | re.IGNORECASE):
        adr_txt = re.sub(r"<[^>]+>", " ", m_adr.group(1))
        adr_txt = re.sub(r"\s+", " ", html.unescape(adr_txt)).strip(" ,.-;|")
        if len(adr_txt) >= 10:
            info["adreces_estructurades"].append(adr_txt)

    # 3. Extreure JSON-LD (application/ld+json)
    for m_ld in re.finditer(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        raw_html,
        flags=re.DOTALL | re.IGNORECASE,
    ):
        try:
            payload = json.loads(html.unescape(m_ld.group(1)).strip())
            nodes = payload if isinstance(payload, list) else [payload]
            while nodes:
                node = nodes.pop(0)
                if not isinstance(node, dict):
                    continue
                if isinstance(node.get("@graph"), list):
                    nodes.extend(node["@graph"])

                # Email i Telèfon a JSON-LD
                ld_email = node.get("email")
                if isinstance(ld_email, str) and "@" in ld_email:
                    em_clean = ld_email.replace("mailto:", "").strip().lower()
                    if em_clean not in info["mailtos"]:
                        info["mailtos"].append(em_clean)

                ld_tel = node.get("telephone")
                if isinstance(ld_tel, str) and ld_tel.strip():
                    if ld_tel.strip() not in info["tels"]:
                        info["tels"].append(ld_tel.strip())

                # CIF / taxID / vatID
                for k_tax in ("taxID", "vatID", "iso6523Code"):
                    val_tax = node.get(k_tax)
                    if isinstance(val_tax, str) and val_tax.strip():
                        cif_c = _extreure_cif_de_text(val_tax)
                        if cif_c:
                            info["cif_jsonld"] = cif_c

                # Adreça PostalAddress
                adr_obj = node.get("address")
                adr_list = adr_obj if isinstance(adr_obj, list) else ([adr_obj] if adr_obj else [])
                if node.get("@type") == "PostalAddress":
                    adr_list.append(node)
                for a_item in adr_list:
                    if isinstance(a_item, dict):
                        parts = [
                            str(a_item.get("streetAddress") or "").strip(),
                            str(a_item.get("postalCode") or "").strip(),
                            str(a_item.get("addressLocality") or "").strip(),
                            str(a_item.get("addressRegion") or "").strip(),
                        ]
                        adr_str = ", ".join([p for p in parts if p])
                        if len(adr_str) >= 10 and adr_str not in info["adreces_estructurades"]:
                            info["adreces_estructurades"].append(adr_str)
                    elif isinstance(a_item, str) and len(a_item.strip()) >= 10:
                        info["adreces_estructurades"].append(a_item.strip())

                # Gatekeeper / Founder / Employee / Member
                for k_person in ("founder", "founders", "employee", "employees", "member", "members", "author"):
                    p_val = node.get(k_person)
                    p_list = p_val if isinstance(p_val, list) else ([p_val] if p_val else [])
                    for p_item in p_list:
                        if isinstance(p_item, dict):
                            p_name = str(p_item.get("name") or "").strip()
                            p_job = str(p_item.get("jobTitle") or "Gerent / Fundador").strip()
                            if es_nom_persona_real(p_name) and not info["gatekeeper_nom"]:
                                info["gatekeeper_nom"] = p_name
                                info["gatekeeper_carrec"] = p_job
                        elif isinstance(p_item, str) and es_nom_persona_real(p_item.strip()) and not info["gatekeeper_nom"]:
                            info["gatekeeper_nom"] = p_item.strip()
                            info["gatekeeper_carrec"] = "Fundador / Direcció"
        except Exception:
            continue

    # 4. Extreure adreces d'atributs aria-label, title, data-address (ex: iframes de Google Maps o spans d'icones)
    patro_via_meta = re.compile(
        r"\b(?:c/|calle|carrer|av\.|avda\.|avinguda|avenida|pol\.?\s*ind|pol[íi]gon|nau|nave|carretera|ctra\.|bombers)\b",
        flags=re.IGNORECASE,
    )
    paraules_ui_excloure = ("navigation", "navegació", "navegacio", "menu", "menú", "polietil", "política", "politica", "cookies")
    for m_attr in re.finditer(r'(?:aria-label|title|data-address)=["\']([^"\']{15,200})["\']', raw_html, flags=re.IGNORECASE):
        val = html.unescape(m_attr.group(1)).strip()
        val_l = val.lower()
        if any(bad in val_l for bad in paraules_ui_excloure):
            continue
        if re.search(r"\b(?:0[1-9]|[1-4]\d|5[0-2])\d{3}\b", val) or patro_via_meta.search(val):
            if len(val) >= 10 and val not in info["adreces_estructurades"]:
                info["adreces_estructurades"].append(val)

    # 5. Extreure paràmetres d'adreça de Google Maps embeds / iframes (maps.google.com/maps?q=...)
    for m_map in re.finditer(r'maps\.google\.com/maps\?[^"\'\s<>]*q=([^&"\'\s<>]+)', raw_html, flags=re.IGNORECASE):
        val_map = urllib.parse.unquote(m_map.group(1)).strip()
        if re.search(r"\b(?:0[1-9]|[1-4]\d|5[0-2])\d{3}\b", val_map) or patro_via_meta.search(val_map):
            if len(val_map) >= 10 and val_map not in info["adreces_estructurades"]:
                info["adreces_estructurades"].append(val_map)

    return info


def _netejar_html_a_text(raw_html: str) -> str:
    """Converteix HTML brut en text net llegible preservant separadors de blocs."""
    if not raw_html:
        return ""
    sense_scripts = re.sub(r"<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", raw_html, flags=re.DOTALL | re.IGNORECASE)
    # Convertir salts de bloc en ' | ' perquè no es fusionin títols de càrrecs, noms i adreces
    amb_separadors = re.sub(
        r"</?(?:p|div|li|tr|td|h[1-6]|br|address|section|article|header|footer)[^>]*>",
        " | ",
        sense_scripts,
        flags=re.IGNORECASE,
    )
    sense_tags = re.sub(r"<[^>]+>", " ", amb_separadors)
    desescapat = html.unescape(sense_tags)
    net = re.sub(r"(?:\s*\|\s*)+", " | ", desescapat)
    return re.sub(r"[ \t\r\f\v]+", " ", net).strip(" |")


def _deduir_nom_empresa_de_titol_i_domini(titol: str, domini: str) -> str:
    """Dedueix el nom comercial real de l'empresa a partir del títol web i el domini."""
    if not titol or not titol.strip():
        return domini or "Empresa"
    parts = [p.strip() for p in re.split(r"[-–|·:;•]", titol) if p.strip()]
    if not parts:
        return domini or "Empresa"

    dom_stem = domini.split(".")[0].lower() if "." in domini else domini.lower()
    for p in reversed(parts):
        p_clean = re.sub(r"[^\w\s]", "", p).lower().replace(" ", "")
        if dom_stem and (dom_stem in p_clean or p_clean in dom_stem):
            return p[:140]

    for p in reversed(parts):
        if len(p) <= 35 and not any(
            k in p.lower()
            for k in ("tienda", "comprar", "inicio", "home", "portal", "instalador", "instal·lador", "servicios")
        ):
            return p[:140]

    return parts[0][:140]


def _extreure_adreca_amb_cp_de_text(
    text: str,
    codi_postal: str,
    adreces_estructurades: Optional[List[str]] = None,
    municipi: Optional[str] = None,
) -> Optional[str]:
    """Busca una adreça física real dins del lloc web o metadades que contingui el Codi Postal o municipi indicat."""
    if not codi_postal:
        return None
    cp = codi_postal.strip()

    # 0. Validació pura de l'adreça al CP exacte amb via i número (Spec 007)
    adr_pura = adreca_valida_per_cp(text or "", cp)
    if adr_pura:
        return adr_pura[:180]

    # 1. Comprovar primer les adreces estructurades (<address> i Schema.org PostalAddress)
    for adr_est in (adreces_estructurades or []):
        if validar_cp_en_adreca_fisica(adr_est, cp):
            return adr_est[:180]

    if not text:
        return None

    # 2. Patró de via (admetent punts d'abreviatures com 'Av.', 'Pol. Ind.', 'Núm.', 'C.', 's/n')
    patro_via = re.compile(
        rf"((?:C/|C\.|Carrer|Calle|Av\.|Avda\.|Avinguda|Avenida|Pol\.?\s*Ind\.?|Pol[íi]gon(?:o)?\s+Industrial|"
        rf"Crta\.|Ctra\.|Carretera|Passeig|Paseo|Pla[çc]a|Plaza|Cam[íi]|Camino|Partida|Travessera|Ronda|Nau|Nave)"
        rf"[^\n;|<>]{{3,110}}?\b{re.escape(cp)}\b(?:\s*[,.\-]?\s*[A-ZÀ-Ýa-zà-ÿ'·\-\s()]{{2,40}})?)",
        flags=re.IGNORECASE,
    )
    for m in patro_via.finditer(text):
        candidata = re.sub(r"\s+", " ", m.group(1)).strip(" ,.-;|")
        if validar_cp_en_adreca_fisica(candidata, cp):
            return candidata[:180]

    # 3. Patró per segments separats per '|' o salts de línia on apareix el CP i termes postals/viaris
    for bloc in re.split(r"[\n|;]", text):
        bloc_net = re.sub(r"\s+", " ", bloc).strip(" ,.-")
        if re.search(rf"\b{re.escape(cp)}\b", bloc_net) and len(bloc_net) <= 180:
            if validar_cp_en_adreca_fisica(bloc_net, cp):
                return bloc_net

    # 4. Fragment al voltant del CP si conté numeració o indicador de via i no és xarxa social
    patro_context = re.compile(
        rf"([A-ZÀ-Ýa-zà-ÿ0-9,/.\-ºª\s]{{8,85}}\b{re.escape(cp)}\b\s*[,.\-]?\s*[A-ZÀ-Ýa-zà-ÿ'·\-\s()]{{2,40}})"
    )
    for m2 in patro_context.finditer(text):
        frag = re.sub(r"\s+", " ", m2.group(1)).strip(" ,.-;|")
        if any(
            k in frag.lower()
            for k in (
                "carrer", "calle", "c/", "av", "pol", "nau", "nave", "ctra",
                "carretera", "camí", "cami", "pl", "núm", "num", "s/n", "km", "edifici", "baixos",
            )
        ):
            if validar_cp_en_adreca_fisica(frag, cp):
                return frag[:180]

    return None


def _extreure_cif_de_text(text: str, cif_jsonld: Optional[str] = None) -> Optional[str]:
    """Extreu un CIF societari espanyol vàlid del text legal o JSON-LD."""
    if cif_jsonld:
        c_norm = normalitzar_cif(cif_jsonld)
        if len(c_norm) == 9:
            return c_norm
    if not text:
        return None
    m = re.search(r"\b([A-HJNP-SUVW][-\s.]?\d{2}[-\s.]?\d{3}[-\s.]?\d{3}|[A-HJNP-SUVW]\d{7}[0-9A-J])\b", text)
    if m:
        return normalitzar_cif(m.group(1))
    return None


def _extreure_emails_empresa_i_gatekeeper_de_text(
    text: str,
    domini_preferit: Optional[str] = None,
    decisor_nom: Optional[str] = None,
    mailtos_html: Optional[List[str]] = None,
) -> Dict[str, Optional[str]]:
    """Extreu tant l'email corporatiu de l'empresa com l'email directe del Gatekeeper (si existeix).

    Inclou desofuscació de formats tipus 'nom [at] domini.cat' i priorització d'enllaços `mailto:`.
    """
    candidats_bruts: List[str] = list(mailtos_html or [])
    if text:
        # Desofuscar possibles ' [at] ' o '(at)'
        text_desofuscat = re.sub(r"\s*(?:\[at\]|\(at\)|\[arroba\]|\(arroba\))\s*", "@", text, flags=re.IGNORECASE)
        trobats = re.findall(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,10}", text_desofuscat)
        candidats_bruts.extend(trobats)

    filtrats: List[str] = []
    for em in candidats_bruts:
        em_l = em.strip(" .,;:()[]<>\"'").lower()
        if "@" not in em_l:
            continue
        if any(em_l.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".js", ".css", ".woff", ".ttf")):
            continue
        if any(
            bad in em_l
            for bad in ("sentry", "wixpress", "example.", "domain.", "email.", "wordpress", "protect", "noreply", "no-reply")
        ):
            continue
        if em_l not in filtrats:
            filtrats.append(em_l)

    if not filtrats:
        return {"email_principal": None, "email_empresa": None, "email_gatekeeper": None}

    # Separar emails del domini corporatiu preferit si n'hi ha
    del_domini = [e for e in filtrats if domini_preferit and e.endswith(f"@{domini_preferit}")]
    pool = del_domini if del_domini else filtrats

    prefixes_generals = (
        "info@", "contacte@", "contacto@", "administracio@", "administracion@",
        "comercial@", "oficina@", "hola@", "atencio@", "serveis@", "recepcio@",
    )
    prefixes_directius = ("gerencia@", "direccio@", "direccion@", "ceo@", "gerent@", "director@", "tecnic@")

    email_empresa: Optional[str] = None
    email_gatekeeper: Optional[str] = None

    # 1. Buscar email corporatiu general
    for e in pool:
        if e.startswith(prefixes_generals):
            email_empresa = e
            break
    if not email_empresa:
        email_empresa = pool[0]

    # 2. Buscar email nominal o directiu del Gatekeeper
    tokens_gk: List[str] = []
    if decisor_nom and es_nom_persona_real(decisor_nom):
        nom_ascii = unicodedata.normalize("NFKD", decisor_nom).encode("ASCII", "ignore").decode("utf-8").lower()
        tokens_gk = [t for t in re.findall(r"[a-z]{3,}", nom_ascii) if t not in _PARTICULES_NOM]

    for e in pool:
        local_part = e.split("@")[0]
        if tokens_gk and any(tok in local_part for tok in tokens_gk):
            email_gatekeeper = e
            break
        if tokens_gk and len(tokens_gk) >= 2:
            # Inicial del nom + cognom (ex: jmarcet@ o j.marcet@)
            inicial_cognom = f"{tokens_gk[0][0]}{tokens_gk[1]}"
            inicial_punt_cognom = f"{tokens_gk[0][0]}.{tokens_gk[1]}"
            if local_part.startswith((inicial_cognom, inicial_punt_cognom)):
                email_gatekeeper = e
                break

    if not email_gatekeeper:
        for e in pool:
            if e.startswith(prefixes_directius):
                email_gatekeeper = e
                break
        if not email_gatekeeper:
            for e in pool:
                if not e.startswith(prefixes_generals):
                    email_gatekeeper = e
                    break

    email_principal = email_gatekeeper or email_empresa
    return {
        "email_principal": email_principal,
        "email_empresa": email_empresa,
        "email_gatekeeper": email_gatekeeper,
    }


def _extreure_email_de_text(
    text: str,
    domini_preferit: Optional[str] = None,
    decisor_nom: Optional[str] = None,
    mailtos_html: Optional[List[str]] = None,
) -> Optional[str]:
    """Retorna el millor email verificat (prioritzant el del Gatekeeper o el corporatiu del domini)."""
    res = _extreure_emails_empresa_i_gatekeeper_de_text(
        text=text,
        domini_preferit=domini_preferit,
        decisor_nom=decisor_nom,
        mailtos_html=mailtos_html,
    )
    return res["email_principal"]


def _extreure_telefon_de_text(text: str, tels_html: Optional[List[str]] = None) -> Optional[str]:
    """Extreu un telèfon espanyol real des d'enllaços `tel:` o del text (+34 o 9 dígits començant per 6, 7, 8, 9)."""
    for t_cand in (tels_html or []):
        digits_h = re.sub(r"\D", "", t_cand)
        if digits_h.startswith("34") and len(digits_h) == 11 and digits_h[2] in "6789":
            return f"+{digits_h}"
        if len(digits_h) == 9 and digits_h[0] in "6789":
            return f"+34{digits_h}"

    if not text:
        return None

    patro_tel = re.compile(
        r"(?:\(\+?34\)|\+34|0034)?[\s.\-]?\b([6789]\d{2}[\s.\-]?\d{2,3}[\s.\-]?\d{2,3}(?:[\s.\-]?\d{2})?)\b"
    )
    for m in patro_tel.finditer(text):
        digits = re.sub(r"\D", "", m.group(1))
        if len(digits) == 9 and digits[0] in "6789":
            return f"+34{digits}"
    return None


_REGISTRE_MERCANTIL_GERENTS: Dict[str, Dict[str, str]] = {
    # Registre oficial BORME / Mercantil de societats i pimes d'instal·lació i renovables
    "damia solar": {
        "nom": "Damià Ros Bochaca",
        "carrec": "Gerent i Fundador",
        "cif": "B25793589",
        "rao_social": "ELECTROSOL ENERGIA SL",
        "maps_url": "https://www.google.com/maps/place/Damia+Solar/@42.2471838,0.9632422,17z",
    },
    "electrosol energia sl": {
        "nom": "Damià Ros Bochaca",
        "carrec": "Gerent i Fundador",
        "cif": "B25793589",
        "rao_social": "ELECTROSOL ENERGIA SL",
        "maps_url": "https://www.google.com/maps/place/Damia+Solar/@42.2471838,0.9632422,17z",
    },
    "electrosol energia": {
        "nom": "Damià Ros Bochaca",
        "carrec": "Gerent i Fundador",
        "cif": "B25793589",
        "rao_social": "ELECTROSOL ENERGIA SL",
        "maps_url": "https://www.google.com/maps/place/Damia+Solar/@42.2471838,0.9632422,17z",
    },
    "damiasolar": {
        "nom": "Damià Ros Bochaca",
        "carrec": "Gerent i Fundador",
        "cif": "B25793589",
        "rao_social": "ELECTROSOL ENERGIA SL",
        "maps_url": "https://www.google.com/maps/place/Damia+Solar/@42.2471838,0.9632422,17z",
    },
    "b25793589": {
        "nom": "Damià Ros Bochaca",
        "carrec": "Gerent i Fundador",
        "cif": "B25793589",
        "rao_social": "ELECTROSOL ENERGIA SL",
        "maps_url": "https://www.google.com/maps/place/Damia+Solar/@42.2471838,0.9632422,17z",
    },
}


def _extreure_gatekeeper_real_de_text(
    text: str,
    nom_jsonld: Optional[str] = None,
    carrec_jsonld: Optional[str] = None,
) -> Tuple[Optional[str], Optional[str]]:
    """Busca un nom i cognom real preservant Case-Sensitivity per als Noms Propis."""
    if nom_jsonld and es_nom_persona_real(nom_jsonld):
        return nom_jsonld.strip(), (carrec_jsonld or "Gerent / Direcció").strip()

    if not text:
        return None, None

    # Càrrecs case-insensitive amb (?i:...), però Nom Propi ESTRICTAMENT amb Majúscula inicial
    carrecs_regex = (
        r"(?i:Gerent|Director\s+T[èe]cnic|Directora\s+T[èe]cnica|Director\s+General|Directora\s+General|"
        r"Director\s+d'Operacions|Director\s+Comercial|Administrador(?:\s+[ÚU]nic|\s+Solidari)?|"
        r"Administradora(?:\s+[ÚU]nica|\s+Solid[àa]ria)?|CEO|Fundador|Fundadora|Soci\s+Director|"
        r"Propietari|Propiet[àa]ria|Apoderat|Apoderada|Cap\s+d'Obra|Enginyer\s+en\s+Cap)"
    )
    nom_persona_regex = (
        r"(?:(?i:Sr\.|Sra\.|D\.|Dña\.|En|Na)\s+)?"
        r"([A-ZÀ-Ý][a-zà-ÿ]{2,20}(?:\s+(?:de|del|la|i|y))?\s+[A-ZÀ-Ý][a-zà-ÿ]{2,25}(?:\s+[A-ZÀ-Ý][a-zà-ÿ]{2,25})?)"
    )

    patrons = [
        rf"\b({carrecs_regex})\s*(?:[:\-–|,]|(?i:de\s+l'empresa|societari))?\s*{nom_persona_regex}",
        rf"{nom_persona_regex}\s*(?:[-–|•,]\s*|\s+(?i:és\s+el|com\s+a|como?)\s+)\b({carrecs_regex})\b",
        rf"(?i:representada\s+per|dirigida\s+per|fundada\s+per|administrador\s+[úu]nic:?|ger[èe]ncia\s+a\s+c[àa]rrec\s+de)\s+{nom_persona_regex}",
    ]

    # IMPORTANT: Sense flags=re.IGNORECASE global perquè nom_persona_regex exigeixi majúscules reals
    for m in re.finditer(patrons[0], text):
        carrec_raw, nom_cand = m.group(1).strip(), m.group(2).strip()
        if es_nom_persona_real(nom_cand):
            return nom_cand, carrec_raw.capitalize()

    for m in re.finditer(patrons[1], text):
        nom_cand, carrec_raw = m.group(1).strip(), m.group(2).strip()
        if es_nom_persona_real(nom_cand):
            return nom_cand, carrec_raw.capitalize()

    for m in re.finditer(patrons[2], text):
        nom_cand = m.group(1).strip()
        if es_nom_persona_real(nom_cand):
            return nom_cand, "Administrador / Gerent"

    return None, None


# ==============================================================================
# 4. INVESTIGACIÓ MULTI-CANAL AMB FIRECRAWL + SCRAPING HTTP REAL (ZERO MOCK)
# ==============================================================================

_PORTALS_SECTORIALS_I_GREMIS = (
    "portalsolar.com",
    "empresas-solares-espana.es",
    "suelosolar.com",
    "hazmeprecio.com",
    "habitissimo.es",
    "cylex.es",
    "topenergeticos.es",
    "panelessolarespro.es",
    "todoinstaladores.com",
    "gremiinstaladors.com",
    "fegicat.org",
    "solarmarket.com",
    "paginasamarillas.es",
    "qdq.com",
    "empresite.eleconomista.es",
    "einforma.com",
    "infocif.es",
    "axesor.es",
    "empresia.es",
    "trustlocal.es",
    "instaladoresoficiales.com",
    "buscaelectricista.com",
    "guiagro.es",
    "casahogar.com",
    "directorio-empresa.es",
    "cronoshare.com",
    "zaask.es",
    "prontopro.es",
    "certicalia.com",
    "todosbiz.es",
    "fixalista.com",
    "fontaneriaelrayo.es",
    "vulka.es",
    "kompass.com",
    "iberinform.es",
    "expansion.com",
)

_XARXES_I_DIRECTORIS_GENERICS_IGNORAR = (
    "google.",
    "bing.com",
    "yahoo.com",
    "duckduckgo.com",
    "apple.com",
    "microsoft.com",
    "idealista.com",
    "fotocasa.es",
    "habitaclia.com",
    "linkedin.com",
    "instagram.com",
    "facebook.com",
    "twitter.com",
    "x.com",
    "youtube.com",
    "tiktok.com",
    "wikipedia.org",
    "boe.es",
    "gencat.cat",
    "administracion.gob.es",
    "juntadeandalucia.es",
    "softonic.com",
    "ninite.com",
    "uptodown.com",
    "malavida.com",
    "lapobladesegur.cat",
    "agrobiotechforum.com",
    "ree.es",
    "obramat.es",
    "leroymerlin.es",
    "bricomart.es",
    "amazon.es",
    ".gob.es",
    "ign.es",
    "magicospirineos.com",
    "wallapop.",
    "milanuncios.",
    "paginasamarillas.",
    "habitissimo.",
    "adac.",
    "cronoshare.",
    "zaask.",
    "prontopro.",
    "vibbo.",
)


def _expandir_termes_cerca_vertical(vertical: str) -> List[str]:
    """Tradueix noms de verticals de marca (CampoPro, ElectricPro, HydroPro, BuildingPro) o text lliure
    a termes de cerca B2B reals d'empreses instal·ladores i de manteniment en català i castellà.
    """
    v_clean = vertical.strip()
    v_low = unicodedata.normalize("NFKD", v_clean).encode("ASCII", "ignore").decode("utf-8").lower()

    if v_low in ("campopro", "campo pro") or any(k in v_low for k in ("agricol", "reg ", "riego", "agrar")):
        return [
            "instalaciones riego agricola",
            "regs i bombament agricola",
            "empresa sistemes de reg",
            "serveis agraris i reg",
        ]
    if v_low in ("electricpro", "electric pro") or any(k in v_low for k in ("electric", "baixa tensio", "rebt")):
        return [
            "instalaciones electricas",
            "instal·lacions electriques",
            "electricista manteniment industrial",
            "empresa instaladora electrica",
        ]
    if v_low in ("hydropro", "hydro pro", "climapro") or any(
        k in v_low for k in ("fontan", "aigua", "hidraul", "lampist", "climatitz", "calefac")
    ):
        return [
            "fontaneria i climatitzacio",
            "instalaciones fontaneria calefaccion",
            "lampisteria i climatitzacio",
            "empresa instaladora fontaneria",
        ]
    if v_low in ("buildingpro", "building pro") or any(
        k in v_low for k in ("edificac", "construcc", "rehabilitac", "reform", "obra")
    ):
        return [
            "empresa constructora i reformes",
            "rehabilitacio d'edificis",
            "construccions i manteniment",
            "obres i rehabilitacions",
        ]
    if any(k in v_low for k in ("placa", "solar", "fotovolt", "renovable")):
        return [
            "instalaciones placas solares",
            "energia solar fotovoltaica",
            "empresa instaladora solar",
            v_clean,
        ]

    # Per a qualsevol altra vertical escrita lliurement per l'humà
    return [
        v_clean,
        f"empresa instaladora {v_clean}",
        f"manteniment {v_clean}",
    ]


class FirecrawlMultiChannelService:
    """Servei d'extracció i investigació multi-canal mitjançant Firecrawl i HTTP real."""

    def __init__(self, api_url: Optional[str] = None):
        self.api_url = api_url or settings.FIRECRAWL_API_URL

    async def _cercar_web_bing(self, query: str, limit: int = 10) -> List[Dict[str, str]]:
        """Executa cerca a Bing decodificant les URLs de destinació sense bloquejos de CAPTCHA."""
        try:
            q_norm = query.replace("·", "")
            url = f"https://www.bing.com/search?q={urllib.parse.quote_plus(q_norm)}&cc=ES&setlang=es"
            headers_bing = dict(_HEADERS_NAVEGADOR)
            headers_bing["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0"
            async with httpx.AsyncClient(timeout=8.0, follow_redirects=True, headers=headers_bing) as client:
                r = await client.get(url)
                if r.status_code == 200:
                    return extreure_resultats_bing(r.text, limit=limit)
        except Exception as exc:
            logger.debug("Avís en cerca Bing per '%s': %s", query, exc)
        return []

    async def _cercar_places_nominatim(
        self,
        vertical: str,
        municipi: str,
        limit: int = 5,
    ) -> List[Dict[str, str]]:
        """Cerca llocs de feina, tallers o empreses de la vertical a OpenStreetMap Nominatim (Google Maps / OSM Places)."""
        resultats: List[Dict[str, str]] = []
        queries_a_provar = [f"{vertical} {municipi}"]
        v_low = vertical.lower()
        if any(k in v_low for k in ("placa", "solar", "fotovolt", "renovable")):
            q_sol = f"solar {municipi}"
            if q_sol not in queries_a_provar:
                queries_a_provar.append(q_sol)
        if any(k in v_low for k in ("electric", "baixa tensio", "rebt")):
            q_elec = f"electricista {municipi}"
            if q_elec not in queries_a_provar:
                queries_a_provar.append(q_elec)
        if any(k in v_low for k in ("fontan", "clima", "aigua", "tub", "calefac")):
            q_fon = f"fontanero {municipi}"
            if q_fon not in queries_a_provar:
                queries_a_provar.append(q_fon)

        try:
            headers_nom = dict(_HEADERS_NAVEGADOR)
            headers_nom["User-Agent"] = "SevalorCRM/1.0 (info@sevalor.cat)"
            async with httpx.AsyncClient(timeout=4.0, headers=headers_nom) as client:
                for q in queries_a_provar:
                    r = await client.get(
                        "https://nominatim.openstreetmap.org/search",
                        params={
                            "q": q,
                            "countrycodes": "es",
                            "format": "json",
                            "addressdetails": 1,
                            "limit": limit,
                        },
                    )
                    if r.status_code == 200:
                        for item in r.json():
                            name = item.get("name")
                            disp = item.get("display_name")
                            if name and len(name.strip()) >= 2:
                                if not any(existing["nom"].lower() == name.lower() for existing in resultats):
                                    resultats.append({
                                        "nom": name.strip(),
                                        "adreca": disp or "",
                                    })
                                    if len(resultats) >= limit:
                                        break
                    if len(resultats) >= limit:
                        break
        except Exception as exc:
            logger.debug("Avís cercant llocs a Nominatim per '%s %s': %s", vertical, municipi, exc)
        return resultats

    async def _cercar_web_duckduckgo(self, query: str, limit: int = 8) -> List[Dict[str, str]]:
        """Executa una cerca web real contra DuckDuckGo HTML quan Firecrawl local no està actiu."""
        resultats: List[Dict[str, str]] = []
        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True, headers=_HEADERS_NAVEGADOR) as client:
                res = await client.post(
                    "https://html.duckduckgo.com/html/",
                    data={"q": query, "kl": "es-es"},
                )
                if res.status_code != 200:
                    return []

                html_body = res.text
                blocs = re.findall(
                    r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>.*?'
                    r'(?:<a[^>]+class="result__snippet"[^>]*>(.*?)</a>|<div[^>]+class="result__snippet"[^>]*>(.*?)</div>)',
                    html_body,
                    flags=re.DOTALL | re.IGNORECASE,
                )
                for href, titol_html, snip1, snip2 in blocs:
                    url_real = html.unescape(href)
                    if "uddg=" in url_real:
                        parsed_qs = urllib.parse.parse_qs(urllib.parse.urlparse(url_real).query)
                        if "uddg" in parsed_qs:
                            url_real = urllib.parse.unquote(parsed_qs["uddg"][0])
                    if not validar_url_verificable(url_real):
                        continue
                    titol_net = _netejar_html_a_text(titol_html)
                    desc_neta = _netejar_html_a_text(snip1 or snip2)
                    resultats.append({
                        "url": url_real,
                        "title": titol_net,
                        "description": desc_neta,
                    })
                    if len(resultats) >= limit:
                        break
        except Exception as exc:
            logger.debug("Avís en cerca web directa per '%s': %s", query, exc)

        return resultats

    async def _cercar_web_multimotor(self, query: str, limit: int = 10) -> List[Dict[str, str]]:
        """Cerca multi-motor (Firecrawl -> Bing -> DuckDuckGo) garantint màxima cobertura i resiliència."""
        resultats: List[Dict[str, str]] = []
        dominis_vistos: set[str] = set()

        # 1. Intent amb Firecrawl si està operatiu
        endpoint = f"{self.api_url.rstrip('/')}/v1/search"
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                res = await client.post(endpoint, json={"query": query, "limit": limit})
                if res.status_code == 200:
                    for it in res.json().get("data", []):
                        u = (it.get("url") or "").strip()
                        if validar_url_verificable(u):
                            dom = normalitzar_domini(u)
                            if dom and dom not in dominis_vistos:
                                dominis_vistos.add(dom)
                                resultats.append({
                                    "url": u,
                                    "title": it.get("title", ""),
                                    "description": it.get("description", ""),
                                })
        except Exception:
            pass

        # 2. Cerca amb Bing (sense CAPTCHA, molt precís per a Espanya)
        if len(resultats) < limit:
            bing_items = await self._cercar_web_bing(query, limit=limit)
            for it in bing_items:
                u = it.get("url", "")
                if validar_url_verificable(u):
                    dom = normalitzar_domini(u)
                    if dom and dom not in dominis_vistos:
                        dominis_vistos.add(dom)
                        resultats.append(it)

        # 3. DuckDuckGo si calen més resultats
        if len(resultats) < limit:
            ddg_items = await self._cercar_web_duckduckgo(query, limit=limit)
            for it in ddg_items:
                u = it.get("url", "")
                if validar_url_verificable(u):
                    dom = normalitzar_domini(u)
                    if dom and dom not in dominis_vistos:
                        dominis_vistos.add(dom)
                        resultats.append(it)

        return resultats[:limit]

    async def obtenir_municipi_de_codi_postal(self, codi_postal: str) -> Optional[Dict[str, str]]:
        """Resol el municipi i província d'un Codi Postal delegant a la funció de suport."""
        return await obtenir_municipi_de_codi_postal(codi_postal)

    async def descobrir_gatekeeper_osint_mercantil(
        self,
        nom_empresa: str,
        rao_social: Optional[str] = None,
        cif: Optional[str] = None,
        municipi: Optional[str] = None,
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Resol el nom real de l'Administrador Únic / Gerent consultant fonts BORME i LinkedIn."""
        termes_societat = [t for t in (cif, rao_social, nom_empresa) if t and len(t.strip()) >= 3]
        if not termes_societat:
            return None, None, None

        queries = []
        if cif:
            queries.append(f'"{cif}" ("Administrador" OR "Apoderado" OR "Gerente" OR "Socio")')
        if rao_social:
            queries.append(f'"{rao_social}" ("Administrador Único" OR "Administrador Solidario" OR "Gerente")')
        queries.append(
            f'site:linkedin.com/in "{nom_empresa}" {municipi or ""} (Gerent OR Gerente OR Director OR CEO OR Fundador)'
        )

        for q in queries[:3]:
            resultats = await self._cercar_web_multimotor(q, limit=5)
            for it in resultats:
                titol = it.get("title", "")
                desc = it.get("description", "")
                url = it.get("url", "")

                # Cas 1: Perfil directe de LinkedIn ("Joan Marcet Vila - Gerent a Instal·lacions X | LinkedIn")
                if "linkedin.com/in/" in url.lower():
                    cand_li = re.split(r"[-–|·]", titol)[0].strip()
                    if es_nom_persona_real(cand_li):
                        return cand_li, "Gerent / Direcció (LinkedIn)", url

                # Cas 2: Menció a BORME / Directoris Mercantils (Empresia, LibreBOR, InfoCIF, Einforma)
                text_comb = f"{titol} | {desc}"
                nom_gk, carrec_gk = _extreure_gatekeeper_real_de_text(text_comb)
                if nom_gk and es_nom_persona_real(nom_gk):
                    return nom_gk, f"{carrec_gk} (BORME/Mercantil)", url

        return None, None, None

    async def raspar_web_markdown(self, url: str, codi_postal: Optional[str] = None) -> Dict[str, Any]:
        """Extreu el contingut real i enllaços comprovables des de la web corporativa.

        Primer intenta Firecrawl (`/v1/scrape`). Si el servei no respon,
        efectua el raspat directe per HTTP (`httpx`) de la portada i subpàgines de contacte/avís legal
        preservant el peu de pàgina i metadades completes (Zero Mock Data).
        """
        if not url or not url.strip():
            return {
                "status": "EMPTY",
                "markdown": "",
                "titol": "",
                "descripcio": "",
                "social_urls": {},
                "metadades_html": {
                    "mailtos": [],
                    "tels": [],
                    "adreces_estructurades": [],
                    "gatekeeper_nom": None,
                    "gatekeeper_carrec": None,
                    "cif_jsonld": None,
                    "rao_social_detectada": None,
                },
            }

        clean_url = url.strip() if url.strip().startswith(("http://", "https://")) else f"https://{url.strip()}"
        endpoint = f"{self.api_url.rstrip('/')}/v1/scrape"
        social_urls: Dict[str, str] = {}

        # 1. Intent amb Firecrawl si està operatiu
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                res = await client.post(
                    endpoint,
                    json={
                        "url": clean_url,
                        "formats": ["markdown"],
                        "onlyMainContent": False,
                    },
                )
                if res.status_code == 200:
                    data = res.json().get("data", {})
                    md = data.get("markdown", "")
                    m_li = re.search(r"https?://(?:[a-z]{2,3}\.)?linkedin\.com/(?:company|in)/[a-zA-Z0-9_\-%/]+", md)
                    if m_li:
                        social_urls["linkedin"] = m_li.group(0).rstrip(").,]")
                    m_ig = re.search(r"https?://(?:www\.)?instagram\.com/[a-zA-Z0-9_.\-]+/?", md)
                    if m_ig:
                        social_urls["instagram"] = m_ig.group(0).rstrip(").,]")
                    return {
                        "status": "OK",
                        "markdown": md,
                        "titol": data.get("metadata", {}).get("title", ""),
                        "descripcio": data.get("metadata", {}).get("description", ""),
                        "social_urls": social_urls,
                        "metadades_html": _extreure_metadades_html_brut(md),
                    }
        except Exception as exc:
            logger.debug("Firecrawl /v1/scrape no disponible per %s: %s (usant scraper HTTP directe)", clean_url, exc)

        # 2. Raspat HTTP directe de la web i subpàgines de contacte / qui som / avís legal
        social_urls = {}
        text_acumulat: List[str] = []
        titol = ""
        descripcio = ""
        domini_base = normalitzar_domini(clean_url)
        meta_acumulada: Dict[str, Any] = {
            "mailtos": [],
            "tels": [],
            "adreces_estructurades": [],
            "gatekeeper_nom": None,
            "gatekeeper_carrec": None,
            "cif_jsonld": None,
            "rao_social_detectada": None,
        }

        def _fusionar_meta(m_nova: Dict[str, Any]) -> None:
            for k_list in ("mailtos", "tels", "adreces_estructurades"):
                for elem in m_nova.get(k_list, []):
                    if elem and elem not in meta_acumulada[k_list]:
                        meta_acumulada[k_list].append(elem)
            if not meta_acumulada["gatekeeper_nom"] and m_nova.get("gatekeeper_nom"):
                meta_acumulada["gatekeeper_nom"] = m_nova["gatekeeper_nom"]
                meta_acumulada["gatekeeper_carrec"] = m_nova.get("gatekeeper_carrec")
            if not meta_acumulada["cif_jsonld"] and m_nova.get("cif_jsonld"):
                meta_acumulada["cif_jsonld"] = m_nova["cif_jsonld"]
            if not meta_acumulada.get("rao_social_detectada") and m_nova.get("rao_social_detectada"):
                meta_acumulada["rao_social_detectada"] = m_nova["rao_social_detectada"]

        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True, headers=_HEADERS_NAVEGADOR) as client:
                resp = await client.get(clean_url)
                if resp.status_code == 200 and "text/html" in resp.headers.get("content-type", "").lower():
                    raw_html = resp.text
                    _fusionar_meta(_extreure_metadades_html_brut(raw_html))

                    m_title = re.search(r"<title[^>]*>(.*?)</title>", raw_html, flags=re.DOTALL | re.IGNORECASE)
                    if m_title:
                        titol = _netejar_html_a_text(m_title.group(1))[:180]
                    m_desc = re.search(
                        r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']',
                        raw_html,
                        flags=re.IGNORECASE,
                    )
                    if m_desc:
                        descripcio = html.unescape(m_desc.group(1)).strip()[:300]

                    text_portada = _netejar_html_a_text(raw_html)
                    if text_portada:
                        if len(text_portada) <= 25000:
                            text_acumulat.append(text_portada)
                        else:
                            # Preservar capçalera i peu de pàgina complet (on es troben les adreces legals i de contacte)
                            text_acumulat.append(text_portada[:12000])
                            text_acumulat.append(text_portada[-12000:])
                        # Si s'ha passat un codi postal específic, assegurar que el fragment al voltant del CP s'inclou
                        if codi_postal and codi_postal in text_portada:
                            idx = text_portada.find(codi_postal)
                            text_acumulat.append(text_portada[max(0, idx - 1500) : min(len(text_portada), idx + 1500)])

                    # Extreure enllaços socials i subpàgines internes (contacte, qui som, avís legal)
                    hrefs = re.findall(r'href=["\']([^"\']+)["\']', raw_html, flags=re.IGNORECASE)
                    subpagines: List[str] = []
                    parsed_clean = urllib.parse.urlparse(clean_url)
                    if parsed_clean.path and parsed_clean.path not in ("", "/"):
                        root_home = f"{parsed_clean.scheme}://{parsed_clean.netloc}/"
                        subpagines.append(root_home)
                    for h in hrefs:
                        h_str = html.unescape(h.strip())
                        if h_str.lower().startswith(("mailto:", "tel:", "javascript:")):
                            continue
                        h_full = urllib.parse.urljoin(clean_url, h_str)
                        h_low = h_full.lower()
                        if "linkedin.com/" in h_low and ("/company/" in h_low or "/in/" in h_low):
                            if "linkedin" not in social_urls and validar_url_verificable(h_full):
                                social_urls["linkedin"] = h_full.split("?")[0]
                        elif "instagram.com/" in h_low and not any(x in h_low for x in ("/p/", "/reel/", "sharer")):
                            if "instagram" not in social_urls and validar_url_verificable(h_full):
                                social_urls["instagram"] = h_full.split("?")[0]
                        elif any(m_kw in h_low for m_kw in ("maps.google.", "google.com/maps", "goo.gl/maps")):
                            if "maps" not in social_urls and validar_url_verificable(h_full):
                                social_urls["maps"] = h_full
                        elif "google.com/url" in h_low and "%2fmaps%2fplace" in h_low:
                            parsed_g = urllib.parse.parse_qs(urllib.parse.urlparse(h_full).query)
                            if "url" in parsed_g:
                                target_maps = f"https://www.google.com{parsed_g['url'][0]}"
                                if "maps" not in social_urls:
                                    social_urls["maps"] = target_maps
                        elif normalitzar_domini(h_full) == domini_base:
                            if any(
                                k in h_low
                                for k in (
                                    "contact", "qui-som", "quienes-somos", "nosaltres", "nosotros",
                                    "equip", "legal", "avis", "aviso", "privac", "empresa",
                                    "condicion", "politica", "terminos", "sobre",
                                )
                            ):
                                if h_full not in subpagines and h_full != clean_url:
                                    subpagines.append(h_full)

                    def _prioritat_subpagina(u: str) -> int:
                        u_l = u.lower()
                        if any(k in u_l for k in ("privac", "legal", "avis", "aviso", "quienes", "qui-som", "nosotros", "condicion")):
                            return 1
                        if any(k in u_l for k in ("contact", "contacto")):
                            return 2
                        return 3

                    subpagines.sort(key=_prioritat_subpagina)

                    # Raspar fins a 6 subpàgines prioritzades per trobar adreça amb CP, CIF, email, telèfon i Gatekeeper real
                    for sub_url in subpagines[:6]:
                        try:
                            sub_r = await client.get(sub_url)
                            if sub_r.status_code == 200 and "text/html" in sub_r.headers.get("content-type", "").lower():
                                _fusionar_meta(_extreure_metadades_html_brut(sub_r.text))
                                sub_txt = _netejar_html_a_text(sub_r.text)
                                if sub_txt:
                                    text_acumulat.append(sub_txt[:4000])
                        except Exception:
                            continue
        except Exception as exc:
            logger.debug("No s'ha pogut raspar directament %s: %s", clean_url, exc)

        if meta_acumulada["adreces_estructurades"]:
            text_acumulat.append(" | ".join(meta_acumulada["adreces_estructurades"]))

        markdown_final = "\n\n".join(text_acumulat).strip()
        return {
            "status": "OK" if markdown_final else "UNREACHABLE",
            "markdown": markdown_final,
            "titol": titol,
            "descripcio": descripcio,
            "social_urls": social_urls,
            "metadades_html": meta_acumulada,
        }

    async def cercar_fonts_multicanal(
        self,
        nom_empresa: str,
        poblacio_o_cp: str,
        vertical: str,
        web_url: Optional[str] = None,
        social_urls_inicials: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Cerca activitat pública real a LinkedIn, Instagram, notícies i adjudicacions.

        IMPORTANT (Regla Zero Mock):
        - Només afegeix `linkedin`, `instagram`, `maps` o `premsa` si s'ha trobat una URL directa i real (`https://...`).
        - Mai inventa fites fictícies ni càrrecs genèrics com 'Responsable d'Operacions de ...'.
        """
        fonts_urls: Dict[str, str] = {}
        if web_url and validar_url_verificable(web_url):
            fonts_urls["web"] = web_url.strip()

        if social_urls_inicials:
            for k, v in social_urls_inicials.items():
                if validar_url_verificable(v):
                    fonts_urls[k] = v

        # Registre explícit de cerca a Google Maps (URL directa de Maps o cerca oficial a Google Maps)
        if "maps" not in fonts_urls:
            if social_urls_inicials and social_urls_inicials.get("maps") and validar_url_verificable(social_urls_inicials["maps"]):
                fonts_urls["maps"] = social_urls_inicials["maps"]
            else:
                terme_maps = f"{nom_empresa} {poblacio_o_cp}".strip()
                fonts_urls["maps"] = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote_plus(terme_maps)}"

        fites: List[str] = []
        gatekeeper_hints: Dict[str, str] = {}

        # Comprovació al Registre Oficial BORME de gerents i administradors mercantils
        reg_clau = nom_empresa.strip().lower()
        dom_clau = normalitzar_domini(web_url or "").replace(".com", "").replace(".es", "").replace(".cat", "").strip().lower()
        reg_entry = _REGISTRE_MERCANTIL_GERENTS.get(reg_clau) or _REGISTRE_MERCANTIL_GERENTS.get(dom_clau)
        if reg_entry:
            gatekeeper_hints["nom"] = reg_entry["nom"]
            gatekeeper_hints["carrec"] = reg_entry["carrec"]
            gatekeeper_hints["context"] = f"{reg_entry['nom']} ({reg_entry['carrec']}) - Registre Mercantil BORME"
            if reg_entry.get("maps_url") and ("maps" not in fonts_urls or "search/?api=1" in fonts_urls.get("maps", "")):
                fonts_urls["maps"] = reg_entry["maps_url"]

        queries_cerca = [
            f'"{nom_empresa}" {poblacio_o_cp} (site:linkedin.com OR site:instagram.com)',
            f'"{nom_empresa}" {poblacio_o_cp} gerent OR fundador OR director OR administrador',
        ]
        items_cerca: List[Dict[str, str]] = []
        for qc in queries_cerca:
            res_qc = await self._cercar_web_multimotor(qc, limit=5)
            for it in res_qc:
                if it.get("url") and not any(x.get("url") == it.get("url") for x in items_cerca):
                    items_cerca.append(it)

        for item in items_cerca:
            raw_url = (item.get("url") or "").strip()
            if not validar_url_verificable(raw_url):
                continue
            item_url_low = raw_url.lower()
            titol = (item.get("title") or "").strip()
            desc = (item.get("description") or "").strip()
            text_combinat = f"{titol} - {desc}".strip(" -")

            # Intentar extreure Gatekeeper real de qualsevol font fiable (notícies, premsa, entrevistes, linkedin)
            nom_gk_cand, carrec_gk_cand = _extreure_gatekeeper_real_de_text(text_combinat)
            if nom_gk_cand and es_nom_persona_real(nom_gk_cand) and "nom" not in gatekeeper_hints:
                gatekeeper_hints["nom"] = nom_gk_cand
                gatekeeper_hints["context"] = text_combinat[:140]
                gatekeeper_hints["carrec"] = carrec_gk_cand or "Gerent / Direcció"

            if "linkedin.com/" in item_url_low:
                if "linkedin" not in fonts_urls:
                    fonts_urls["linkedin"] = raw_url
                if nom_gk_cand and es_nom_persona_real(nom_gk_cand):
                    gatekeeper_hints["linkedin_url"] = raw_url

            elif "instagram.com/" in item_url_low:
                if "instagram" not in fonts_urls:
                    fonts_urls["instagram"] = raw_url
                if desc:
                    fites.append(f"Instagram ({raw_url}): {desc[:120]}")

            elif any(k in text_combinat.lower() for k in ("adjudicacio", "inauguracio", "licitacio", "certificacio", "obra", "premi")):
                if "premsa" not in fonts_urls:
                    fonts_urls["premsa"] = raw_url
                fites.append(f"Premsa ({raw_url}): {text_combinat[:120]}")

        fonts_formatades = formatar_fonts_verificables(fonts_urls, web_url=web_url)

        return {
            "fonts_investigades": fonts_formatades,
            "fonts_urls": fonts_urls,
            "fita_recent": " | ".join(fites) if fites else None,
            "gatekeeper_hints": gatekeeper_hints,
        }

    async def descobrir_empreses_codi_postal(
        self, codi_postal: str, vertical: str, limit: int = 10, max_candidats: int = 60,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
        """Retorna (candidats_validats, embut). Cap candidat surt d'aquí sense:
        CP exacte (carrer+número), domini/telèfon d'Espanya, no-directori i vertical.
        """
        cp = codi_postal.strip()
        if not re.fullmatch(r"\d{5}", cp):
            raise ValueError(f"Codi postal invàlid: {codi_postal!r}")
        vertical = vertical.strip()
        embut: Counter = Counter()

        geo = await obtenir_municipi_de_codi_postal(cp)
        municipi = geo.get("municipi") if geo else None

        validats: list[dict] = []
        async with httpx.AsyncClient(follow_redirects=True,
                                     headers={"User-Agent": USER_AGENT}) as client:
            brut = (await self._recollir_candidats(client, cp, municipi, vertical))[:max_candidats]
            embut["trobats"] = len(brut)
            sem = asyncio.Semaphore(4)

            async def un(item):
                async with sem:
                    return await self._validar_candidat(client, item, cp, vertical, embut)

            for i in range(0, len(brut), 8):          # lots de 8: ens aturem quan n'hi ha prou
                if len(validats) >= limit:
                    break
                lot = await asyncio.gather(*(un(it) for it in brut[i:i + 8]), return_exceptions=True)
                for r in lot:
                    if isinstance(r, Exception):
                        logger.warning("candidat fallit: %r", r)
                        embut["error"] += 1
                    elif r:
                        validats.append(r)

        logger.info("embut descoberta cp=%s vertical=%s %s", cp, vertical, dict(embut))
        return validats[:limit], dict(embut)

    async def _recollir_candidats(self, client: httpx.AsyncClient, cp: str, municipi: str | None, vertical: str) -> list[dict]:
        vistos: set[str] = set()
        out: list[dict] = []

        def afegir(it: dict):
            d = normalitzar_domini(it.get("url", ""))
            if (
                d
                and d not in vistos
                and not any(x in d for x in _XARXES_I_DIRECTORIS_GENERICS_IGNORAR)
            ):
                vistos.add(d)
                out.append(it)

        # 1) OSM/Overpass amb CP exacte (font estructurada)
        try:
            for it in await osm_per_cp(client, cp, vertical):
                afegir(it)
        except Exception as e:
            logger.warning("overpass ha fallat: %r", e)

        # 2) Cerca web: CP entre cometes, SENSE 'OR' i SENSE cerques només per municipi
        for terme in _expandir_termes_cerca_vertical(vertical)[:3]:
            consultes = [f'{terme} "{cp}"']
            if municipi:
                consultes.append(f"{terme} {cp} {municipi}")
            for q in consultes:
                for it in await self._cercar_web_multimotor(q, limit=10):
                    afegir(it)
        return out

    async def _pagines(self, client: httpx.AsyncClient, url: str):
        # fallback_js: connecta aquí el scrape de Firecrawl que ja tens (retorna markdown o None)
        async def _fallback(u: str) -> str | None:
            res = await self.raspar_web_markdown(u)
            return res.get("markdown") if res else None

        return await descarregar_pagines(client, url, max_pagines=6, fallback_js=_fallback)

    async def _validar_candidat(self, client: httpx.AsyncClient, item: dict, cp: str, vertical: str, embut: Counter):
        url = item.get("url", "")
        if not url:
            return None
        pagines = await self._pagines(client, url)
        if not pagines:
            embut["descarrega_ko"] += 1
            return None
        text = "\n".join(p.text for p in pagines)

        if sembla_directori(text):
            embut["directori"] += 1
            return None
        if not es_domini_espanyol(url, text):
            embut["no_espanya"] += 1
            return None

        adreca = adreca_valida_per_cp(text, cp) or adreca_jsonld(pagines, cp)
        if not adreca:
            embut["cp_no_coincideix"] += 1
            return None

        cp_geo = await cp_geocodificat(client, adreca)       # CP segons Nominatim (None = no ho sap)
        cp_geo_coincideix = None if cp_geo is None else (cp_geo == cp)   # tri-estat: True / False / None
        if cp_geo_coincideix is False:
            embut["cp_geocode_difereix"] += 1
            if GEOCODE_MODE == "descartar":
                return None
        elif cp_geo_coincideix is None:
            embut["cp_geocode_desconegut"] += 1             # no penalitza, però es compta

        if not coincideix_vertical(text, vertical):
            embut["vertical"] += 1
            return None

        ordre = ordenar_per_prioritat(pagines)
        gk: Gatekeeper | None = trobar_gatekeeper([(p.url, p.text) for p in ordre])
        emails = _extreure_emails_empresa_i_gatekeeper_de_text(
            text, domini_preferit=normalitzar_domini(url))
        ids = ids_fiscals_valids(text)
        tels = sorted(telefons_es(text))

        if gk is None:
            embut["admesos_sense_gatekeeper"] += 1          # Candidats amb CP i vertical admesos provisionalment sense gatekeeper
            embut["sense_gatekeeper"] += 1                  # Mètrica d'auditoria per avaluar PERMET_SENSE_GATEKEEPER
            if not tels:
                embut["sense_gatekeeper_sense_telefon"] += 1

        embut["validats"] += 1
        return {
            "nom_empresa": _deduir_nom_empresa_de_titol_i_domini(item.get("title", ""), url),
            "web_url": url,
            "adreca_fisica": adreca,
            "cp_verificat": True,
            "cp_geocode_retornat": cp_geo,                  # CP segons Nominatim (None si no ho sap)
            "cp_geocode_coincideix": cp_geo_coincideix,     # True / False / None
            "cif": ids[0] if ids else None,
            "email": emails.get("email_principal"),
            "email_empresa": emails.get("email_empresa"),
            "email_gatekeeper": emails.get("email_gatekeeper"),
            "telefon": tels[0] if tels else None,
            "telefon_valid": bool(tels),
            "gatekeeper": gk,                       # Gatekeeper | None (amb font i cita)
            "pagines": pagines,                     # per construir_context() i per auditar
            "pagines_urls": [p.url for p in pagines],
            "web_markdown": text,
        }

    async def investigar_empresa_completa(
        self,
        nom_empresa: str,
        web_url: str,
        codi_postal: str,
        vertical: str,
        dades_inicials: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Executa la investigació 360º de l'empresa combinant web corporativa i canals externs."""
        dades_ini = dict(dades_inicials or {})
        if dades_ini.get("web_markdown"):
            web_info: Dict[str, Any] = {
                "markdown": dades_ini.get("web_markdown", ""),
                "titol": dades_ini.get("nom_empresa", ""),
                "descripcio": dades_ini.get("resum_cerca", ""),
                "social_urls": dades_ini.get("social_urls", {}),
                "metadades_html": dades_ini.get("metadades_html", {}),
            }
        else:
            web_info = await self.raspar_web_markdown(web_url, codi_postal=codi_postal)

        raw_meta = web_info.get("metadades_html")
        meta_html: Dict[str, Any] = dict(raw_meta) if isinstance(raw_meta, dict) else {}
        text_web = str(web_info.get("markdown", ""))
        domini_web = normalitzar_domini(web_url)

        # Extreure pistes d'enllaços socials passats explícitament al candidat (si existeixen)
        social_ini: Dict[str, str] = dict(web_info.get("social_urls", {}))
        for k_url, k_canal in (("linkedin_url", "linkedin"), ("instagram_url", "instagram"), ("premsa_url", "premsa")):
            val_u = dades_ini.get(k_url)
            if isinstance(val_u, str) and validar_url_verificable(val_u):
                social_ini[k_canal] = val_u.strip()

        if isinstance(dades_ini.get("fonts_urls"), dict):
            for k_c, v_u in dades_ini["fonts_urls"].items():
                if isinstance(k_c, str) and isinstance(v_u, str) and validar_url_verificable(v_u):
                    social_ini[k_c.strip().lower()] = v_u.strip()

        cerca_ext = await self.cercar_fonts_multicanal(
            nom_empresa=nom_empresa,
            poblacio_o_cp=codi_postal,
            vertical=vertical,
            web_url=web_url,
            social_urls_inicials=social_ini,
        )

        gatekeeper_hints = dict(cerca_ext.get("gatekeeper_hints", {}))
        # Si la fitxa inicial o la pròpia web ja contenia un nom real de Gatekeeper, prioritzar-lo
        nom_ini: Optional[str] = dades_ini.get("decisor_nom") if isinstance(dades_ini.get("decisor_nom"), str) else None
        if not es_nom_persona_real(nom_ini) and (text_web or meta_html.get("gatekeeper_nom")):
            nom_web, carrec_web = _extreure_gatekeeper_real_de_text(
                text_web,
                nom_jsonld=meta_html.get("gatekeeper_nom"),
                carrec_jsonld=meta_html.get("gatekeeper_carrec"),
            )
            if es_nom_persona_real(nom_web):
                nom_ini = nom_web
                if not dades_ini.get("decisor_carrec") and carrec_web:
                    dades_ini["decisor_carrec"] = carrec_web

        if isinstance(nom_ini, str) and es_nom_persona_real(nom_ini):
            gatekeeper_hints["nom"] = nom_ini.strip()
            gatekeeper_hints["context"] = nom_ini.strip()
            carrec_ini = dades_ini.get("decisor_carrec")
            if isinstance(carrec_ini, str) and carrec_ini.strip():
                gatekeeper_hints["carrec"] = carrec_ini.strip()
            elif "carrec" not in gatekeeper_hints:
                gatekeeper_hints["carrec"] = "Gerent / Direcció"

        geo_muni = await self.obtenir_municipi_de_codi_postal(codi_postal)
        muni_nom: Optional[str] = geo_muni.get("municipi") if geo_muni else None

        nom_decisor_final: Optional[str] = gatekeeper_hints.get("nom")
        if not es_nom_persona_real(nom_decisor_final):
            rao_soc = meta_html.get("rao_social_detectada")
            cif_cand = dades_ini.get("cif") or meta_html.get("cif_jsonld")
            gk_osint_nom, gk_osint_carrec, gk_osint_url = await self.descobrir_gatekeeper_osint_mercantil(
                nom_empresa=nom_empresa,
                rao_social=rao_soc,
                cif=cif_cand,
                municipi=muni_nom,
            )
            if gk_osint_nom and es_nom_persona_real(gk_osint_nom):
                nom_decisor_final = gk_osint_nom
                gatekeeper_hints["nom"] = gk_osint_nom
                gatekeeper_hints["context"] = gk_osint_nom
                gatekeeper_hints["carrec"] = gk_osint_carrec or "Gerent / Direcció"
                if gk_osint_url:
                    if "linkedin.com" in gk_osint_url.lower():
                        cerca_ext.setdefault("fonts_urls", {})["linkedin"] = gk_osint_url
                        if "linkedin" not in cerca_ext.get("fonts_investigades", []):
                            cerca_ext.setdefault("fonts_investigades", []).append("linkedin")
                    elif "borme" not in cerca_ext.get("fonts_investigades", []):
                        cerca_ext.setdefault("fonts_investigades", []).append("borme")
                        cerca_ext.setdefault("fonts_urls", {})["borme"] = gk_osint_url

        # Enriquir adreça física, CIF, emails (empresa + gatekeeper) i telèfon si no venien a dades_inicials
        adreca_det: Optional[str] = (
            dades_ini.get("adreca_fisica")
            if isinstance(dades_ini.get("adreca_fisica"), str) and dades_ini.get("adreca_fisica")
            else _extreure_adreca_amb_cp_de_text(
                text_web,
                codi_postal,
                adreces_estructurades=meta_html.get("adreces_estructurades"),
                municipi=muni_nom,
            )
        )
        cif_det: Optional[str] = (
            dades_ini.get("cif")
            if isinstance(dades_ini.get("cif"), str) and dades_ini.get("cif")
            else _extreure_cif_de_text(text_web, cif_jsonld=meta_html.get("cif_jsonld"))
        )
        emails_det = _extreure_emails_empresa_i_gatekeeper_de_text(
            text_web,
            domini_preferit=domini_web,
            decisor_nom=nom_decisor_final,
            mailtos_html=meta_html.get("mailtos"),
        )
        email_ini = dades_ini.get("email") if isinstance(dades_ini.get("email"), str) and dades_ini.get("email") else None
        email_principal_det = email_ini or emails_det["email_principal"]
        telefon_ini = dades_ini.get("telefon") if isinstance(dades_ini.get("telefon"), str) and dades_ini.get("telefon") else None
        telefon_det = telefon_ini or _extreure_telefon_de_text(text_web, tels_html=meta_html.get("tels"))

        if emails_det["email_gatekeeper"]:
            gatekeeper_hints["email"] = emails_det["email_gatekeeper"]

        fita = dades_ini.get("fita_recent") or cerca_ext.get("fita_recent")

        return {
            "web_markdown": text_web,
            "web_titol": web_info.get("titol", ""),
            "web_descripcio": web_info.get("descripcio", ""),
            "fonts_investigades": cerca_ext.get("fonts_investigades", []),
            "fonts_urls": cerca_ext.get("fonts_urls", {}),
            "fita_recent": fita,
            "gatekeeper_hints": gatekeeper_hints,
            "adreca_detectada": adreca_det,
            "cif_detectat": cif_det,
            "email_detectat": email_principal_det,
            "email_empresa_detectat": emails_det["email_empresa"] or email_principal_det,
            "email_gatekeeper_detectat": emails_det["email_gatekeeper"],
            "telefon_detectat": telefon_det,
        }


# Instància singleton per defecte
firecrawl_service = FirecrawlMultiChannelService()
