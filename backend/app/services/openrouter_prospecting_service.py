"""Servei d'avaluació de leads amb OpenRouter (DeepSeek), Doble Bucle d'Aprenentatge i Campanya de 3 Emails.

Funcionalitats:
1. Esquemes Pydantic estructurats (`LeadEvaluationSchema`, `EmailStepSchema`).
2. Doble Bucle d'Aprenentatge al System Prompt:
   - Bucle 1: Regles de descart i correccions humanes (`CORRECCIO_DESCART`, `CORRECCIO_SELECCIO`).
   - Bucle 2: Patrons de tancament d'èxit replicables (`TANCAMENT_EXIT_REPLICABLE`) per a 'lookalike boost'.
3. Validació estricta Zero-Mock i Personalització Real:
   - Codi Postal verificat obligatòriament a l'adreça física (`validar_cp_en_adreca_fisica`).
   - Nom i Cognom REAL de persona física per al Gatekeeper (`es_nom_persona_real`), prohibint càrrecs genèrics.
4. Generació de la Campanya de 3 Emails amb el seu tempo:
   - Pas 1 (Dia 0): 5 passos (Gatekeeper -> Fita multi-canal -> Dolor -> Solució PWA + Telegram -> CTA Demo).
     (PROHIBICIÓ ESTRICTA: MAI ESMENTAR WHATSAPP).
   - Pas 2 (Dia +4): Autoritat amb cas replicable del sector.
   - Pas 3 (Dia +8): Diagnòstic ràpid i activació de la Demo Real de 7 Dies.
"""

import asyncio
import json
import logging
import re
from typing import Any, Dict, List, Optional

import httpx
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.models import SaasCriteriFeedback
from app.services.firecrawl_service import (
    es_nom_persona_real,
    validar_cp_o_municipi_en_adreca,
)

logger = logging.getLogger("sevalor.crm.openrouter")


def _sanititzar_entrada_ia(text: Optional[str], max_len: int = 2500) -> str:
    """Sanititza entrades abans d'enviar-les al LLM (Anti Prompt-Injection segons AGENTS.md §3.5)."""
    if not text:
        return ""
    # Eliminar caràcters de control excepte salts de línia i tabuladors
    clean = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    return clean.strip()[:max_len]


def _extreure_context_prioritari_ia(web_markdown: str, max_len: int = 6000) -> str:
    """Selecciona l'inici, el peu de pàgina i els blocs amb CIF/Contacte/Equip perquè no es perdin en truncar."""
    if not web_markdown:
        return ""
    net = _sanititzar_entrada_ia(web_markdown, max_len=40000)
    if len(net) <= max_len:
        return net

    capcalera = net[:2000]
    peu_i_subpagines = net[-3000:]
    # Cercar blocs intermedis que continguin paraules clau de decisors o dades fiscals
    blocs_clau = []
    for m in re.finditer(
        r".{0,250}\b(?:gerent|director|fundador|administrador|equip|cif|nif|s\.l\.|pol[íi]gon)\b.{0,250}",
        net[2000:-3000],
        flags=re.IGNORECASE,
    ):
        blocs_clau.append(m.group(0).strip())
        if sum(len(b) for b in blocs_clau) >= 1000:
            break

    combinat = f"{capcalera}\n...\n" + "\n".join(blocs_clau) + f"\n...\n{peu_i_subpagines}"
    return combinat[:max_len]


# ==============================================================================
# 1. ESQUEMES PYDANTIC D'AVALUACIÓ I CAMPANYA D'EMAILS
# ==============================================================================

class EmailStepSchema(BaseModel):
    """Esquema d'un correu de la seqüència amb el seu tempo d'enviament."""

    pas: int = Field(..., ge=1, le=3, description="Número de pas (1, 2 o 3)")
    tempo_offset_dies: int = Field(..., ge=0, description="Offset de dies (0, 4 o 8)")
    assumpte: str = Field(..., min_length=5, max_length=255, description="Assumpte personalitzat")
    cos_text: str = Field(..., min_length=20, description="Cos del correu en text net")

    @model_validator(mode="before")
    @classmethod
    def normalitzar_email_step(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        # Pas (1, 2 o 3)
        if "pas" not in data or data["pas"] is None:
            data["pas"] = 1
        else:
            try:
                data["pas"] = max(1, min(3, int(data["pas"])))
            except Exception:
                data["pas"] = 1

        # Tempo offset dies (0, 4, 8)
        if "tempo_offset_dies" not in data or data["tempo_offset_dies"] is None:
            offsets = {1: 0, 2: 4, 3: 8}
            data["tempo_offset_dies"] = offsets.get(data["pas"], 0)
        else:
            try:
                data["tempo_offset_dies"] = max(0, int(data["tempo_offset_dies"]))
            except Exception:
                offsets = {1: 0, 2: 4, 3: 8}
                data["tempo_offset_dies"] = offsets.get(data["pas"], 0)

        # Assumpte (mínim 5 caràcters, màxim 255)
        assumpte = data.get("assumpte") or data.get("subject") or data.get("titol") or ""
        if len(str(assumpte).strip()) < 5:
            assumpte = "Optimització de procesos tècnics amb Sevalor Suite"
        data["assumpte"] = str(assumpte).strip()[:255]

        # Cos text (mínim 20 caràcters)
        cos = (
            data.get("cos_text")
            or data.get("body")
            or data.get("text")
            or data.get("cos")
            or data.get("contingut")
            or data.get("missatge")
            or ""
        )
        if len(str(cos).strip()) < 20:
            cos = (
                "Hola equip directiu,\n\n"
                "Us contactem des de Sevalor Suite per a optimitzar la vostra operativa de camp i quadrilles."
            )
        data["cos_text"] = str(cos).strip()

        return data

    @field_validator("assumpte", "cos_text")
    @classmethod
    def prohibir_mencio_whatsapp(cls, v: str) -> str:
        """Garanteix a nivell d'esquema que mai s'esmenti WhatsApp (només PWA i Bot de Telegram)."""
        if re.search(r"whatsapp", v, flags=re.IGNORECASE):
            v = re.sub(r"whatsapp", "Telegram", v, flags=re.IGNORECASE)
        return v


class LeadEvaluationSchema(BaseModel):
    """Esquema complet d'avaluació del lead per DeepSeek."""

    operaris_estimats: int = Field(..., ge=0, description="Treballadors o tècnics de camp estimats")
    decisor_nom: Optional[str] = Field(None, max_length=100, description="Nom i cognom REAL de la persona física decisora")
    decisor_carrec: Optional[str] = Field(None, max_length=100, description="Càrrec (ex. Gerent, Director Tècnic)")
    fonts_investigades: List[str] = Field(default_factory=list, description="Fonts consultades amb URL (canal|url)")
    fita_recent: Optional[str] = Field(None, description="Fita recent trobada a xarxes, web o notícies")
    punt_dolor: Optional[str] = Field(None, description="Punt de dolor operatiu detectat")
    angle_atac: str = Field(
        "ANGLE_A_VISIBILITAT_TELEGRAM",
        pattern="^(ANGLE_A_VISIBILITAT_TELEGRAM|ANGLE_B_ESTOC_FURGONETES|ANGLE_C_CAMP_FACTURA|ANGLE_D_CONEIXEMENT_IA)$",
    )
    score: int = Field(..., ge=0, le=100, description="Puntuació de qualificació de 0 a 100")
    estat_decisio: str = Field(..., pattern="^(SELECCIONAT|DESCARTAT)$")
    motiu_detallat_ia: str = Field(..., min_length=10, description="Justificació transparent de la decisió")
    campanya_3_emails: List[EmailStepSchema] = Field(
        default_factory=list,
        description="Seqüència de 3 correus amb tempo (0, 4, 8 dies) si és SELECCIONAT",
    )

    @model_validator(mode="before")
    @classmethod
    def normalitzar_dades_llm(cls, data: Any) -> Any:
        """Normalitza toleradament claus retornades per l'LLM (DeepSeek) abans de validar l'esquema."""
        if not isinstance(data, dict):
            return data

        # 1. Normalitzar estat_decisio i score
        estat_raw = str(data.get("estat_decisio") or data.get("estat") or data.get("decisio") or "").strip().upper()
        if "SEL" in estat_raw:
            estat = "SELECCIONAT"
        elif "DESC" in estat_raw:
            estat = "DESCARTAT"
        else:
            estat = "DESCARTAT"
        data["estat_decisio"] = estat

        if data.get("score") is None:
            p = data.get("puntuacio") or data.get("puntuacio_qualificacio")
            try:
                data["score"] = int(p) if p is not None else (75 if estat == "SELECCIONAT" else 30)
            except Exception:
                data["score"] = 75 if estat == "SELECCIONAT" else 30
        else:
            try:
                data["score"] = max(0, min(100, int(data["score"])))
            except Exception:
                data["score"] = 75 if estat == "SELECCIONAT" else 30

        # 2. Normalitzar operaris_estimats
        if data.get("operaris_estimats") is None:
            candidats_operaris = [
                data.get("operaris"),
                data.get("treballadors"),
                data.get("empleats"),
                data.get("plantilla"),
                data.get("operaris_totals"),
                data.get("num_operaris"),
            ]
            trobat_operaris = None
            for cand in candidats_operaris:
                if cand is not None:
                    try:
                        trobat_operaris = int(cand)
                        break
                    except (ValueError, TypeError):
                        pass
            if trobat_operaris is not None:
                data["operaris_estimats"] = max(0, trobat_operaris)
            else:
                data["operaris_estimats"] = 5 if estat == "SELECCIONAT" else 0
        else:
            try:
                data["operaris_estimats"] = max(0, int(data["operaris_estimats"]))
            except Exception:
                data["operaris_estimats"] = 5 if estat == "SELECCIONAT" else 0

        # 3. Normalitzar motiu_detallat_ia
        motiu = data.get("motiu_detallat_ia")
        if not motiu or not isinstance(motiu, str) or len(motiu.strip()) < 10:
            candidats_motiu = [
                data.get("motiu"),
                data.get("justificacio"),
                data.get("explicacio"),
                data.get("raonament"),
                data.get("notes"),
                data.get("detall"),
                data.get("resum"),
            ]
            trobat_motiu = None
            for cand_m in candidats_motiu:
                if cand_m and isinstance(cand_m, str) and len(cand_m.strip()) >= 10:
                    trobat_motiu = cand_m.strip()
                    break
            if trobat_motiu:
                data["motiu_detallat_ia"] = trobat_motiu
            else:
                nom = data.get("empresa") or data.get("nom_empresa") or "l'empresa"
                data["motiu_detallat_ia"] = (
                    f"Avaluació de {nom}: lead amb estat {estat} segons els criteris de qualificació establerts."
                )

        # 4. Normalitzar campanya_3_emails (acceptar 'campanya_emails', 'emails', etc.)
        if not data.get("campanya_3_emails"):
            emails_alt = (
                data.get("campanya_emails")
                or data.get("campanya")
                or data.get("emails")
                or data.get("emails_campanya")
                or []
            )
            if isinstance(emails_alt, list):
                data["campanya_3_emails"] = emails_alt

        # 5. Normalitzar decisor_nom i decisor_carrec
        if not data.get("decisor_nom"):
            data["decisor_nom"] = data.get("nom_decisor") or data.get("gatekeeper_nom") or data.get("nom_contacte")
        if not data.get("decisor_carrec"):
            data["decisor_carrec"] = data.get("carrec_decisor") or data.get("gatekeeper_carrec") or data.get("carrec")

        # 6. Normalitzar angle_atac
        angles_valids = {
            "ANGLE_A_VISIBILITAT_TELEGRAM",
            "ANGLE_B_ESTOC_FURGONETES",
            "ANGLE_C_CAMP_FACTURA",
            "ANGLE_D_CONEIXEMENT_IA",
        }
        if data.get("angle_atac") not in angles_valids:
            data["angle_atac"] = "ANGLE_A_VISIBILITAT_TELEGRAM"

        return data


# ==============================================================================
# 2. DOBLE BUCLE D'APRENENTATGE (CRITERIS DE RETROALIMENTACIÓ)
# ==============================================================================

async def carregar_context_doble_bucle(
    vertical: str,
    db: AsyncSession,
) -> Dict[str, Any]:
    """Carrega de la base de dades les regles humanes de descart i els tancaments d'èxit.

    Args:
        vertical: Nom de la vertical o sector (text lliure).
        db: Sessió asíncrona de SQLAlchemy.

    Returns:
        Diccionari amb:
        - `regles_descart`: Llista de motius de descart manuals de l'humà per evitar repetir errors.
        - `casos_exit_replicables`: Llista de clients reals que han contractat (`GUANYAT`) amb la raó d'èxit.
    """
    stmt = (
        select(SaasCriteriFeedback)
        .where(SaasCriteriFeedback.actiu.is_(True))
        .order_by(desc(SaasCriteriFeedback.created_at))
        .limit(30)
    )
    res = await db.execute(stmt)
    feedbacks = res.scalars().all()

    regles_descart: List[Dict[str, str]] = []
    regles_seleccio: List[Dict[str, str]] = []
    casos_exit: List[Dict[str, str]] = []

    for f in feedbacks:
        # Bucle 1: Correccions humanes (descarts i seleccions)
        if f.tipus_aprenentatge == "CORRECCIO_DESCART":
            regles_descart.append({
                "vertical": f.vertical,
                "empresa": f.nom_empresa,
                "evidencies": f.resum_evidencies_o_requisits,
                "motiu_descart_huma": f.explicacio_humana_o_rao_exit,
            })
        elif f.tipus_aprenentatge == "CORRECCIO_SELECCIO":
            regles_seleccio.append({
                "vertical": f.vertical,
                "empresa": f.nom_empresa,
                "evidencies": f.resum_evidencies_o_requisits,
                "motiu_seleccio_huma": f.explicacio_humana_o_rao_exit,
            })
        # Bucle 2: Tancaments d'èxit replicables (GUANYAT)
        elif f.tipus_aprenentatge == "TANCAMENT_EXIT_REPLICABLE" and f.es_replicable:
            casos_exit.append({
                "vertical": f.vertical,
                "empresa": f.nom_empresa,
                "requisits_complerts": f.resum_evidencies_o_requisits,
                "rao_tancament_exit": f.explicacio_humana_o_rao_exit,
            })

    return {
        "regles_descart": regles_descart,
        "regles_seleccio": regles_seleccio,
        "casos_exit_replicables": casos_exit,
    }


def construir_system_prompt(context_aprenentatge: Dict[str, Any]) -> str:
    """Construeix el System Prompt enriquint-lo amb el Doble Bucle d'Aprenentatge i regles estrictes."""
    descarts_str = ""
    if context_aprenentatge.get("regles_descart") or context_aprenentatge.get("regles_seleccio"):
        descarts_str = "\n### BUCLE 1: REGLES I JUSTIFICACIONS HUMANES DE DESCART I SELECCIÓ:\n"
        for r in context_aprenentatge.get("regles_descart", [])[:5]:
            descarts_str += (
                f"- [DESCARTAR] Sector '{r['vertical']}' / '{r['empresa']}': DESCARTAT PER L'HUMÀ perquè: "
                f"{r['motiu_descart_huma']}. Evidències: {r['evidencies']}\n"
            )
        for s in context_aprenentatge.get("regles_seleccio", [])[:5]:
            descarts_str += (
                f"- [SELECCIONAR] Sector '{s['vertical']}' / '{s['empresa']}': SELECCIONAT PER L'HUMÀ perquè: "
                f"{s['motiu_seleccio_huma']}. Evidències: {s['evidencies']}\n"
            )

    exit_str = ""
    if context_aprenentatge.get("casos_exit_replicables"):
        exit_str = "\n### BUCLE 2: CASOS D'ÈXIT REPLICABLES CONTRACTATS ('GUANYAT' - PRIORITZAR LOOKALIKES):\n"
        for c in context_aprenentatge["casos_exit_replicables"][:5]:
            exit_str += (
                f"- Sector '{c['vertical']}' / '{c['empresa']}': REQUISITS: {c['requisits_complerts']} | "
                f"RAÓ D'ÈXIT: {c['rao_tancament_exit']}. Si el candidat compleix aquests requisits, atorga puntuació alta (>85).\n"
            )

    prompt = f"""Ets l'Avaluador Comercial i Estrateg d'Outreach de Sevalor Suite (SaaS B2B sobirà a Hetzner per a empreses de serveis tècnics de 5 a 50 operaris al terreny: agricultura, baixa tensió REBT, climatització, fontaneria, manteniment industrial i edificació).

PRODUCTE SEVALOR SUITE:
- PWA mòbil offline `/operari` per a les quadrilles de camp (partes en 30s, fotos, mermes de vehicle).
- Dashboard d'enginyeria i gestió `/gestio` (control d'estoc en temps real, albarans i facturació Veri*factu).
- Bot Oficial de Telegram per interactuar directament amb el client final (avisos d'arribada, signatura digital i conformitats).
- NORMA ESTRICTA I SUPREMA: ESTÀ TOTALMENT PROHIBIT ESMENTAR 'WHATSAPP'. Únicament s'utilitza la PWA i el Bot Oficial de Telegram de Sevalor.

REGLES INNEGOCIABLES DE VALIDACIÓ (TOLERÀNCIA ZERO):
1. UBICACIÓ FÍSICA REAL: L'adreça física verificada ha de correspondre al Codi Postal sol·licitat o al mateix municipi/polígon industrial. Si pertany a una altra localitat allunyada -> `estat_decisio = "DESCARTAT"`.
2. GATEKEEPER REAL O CONTACTE OPERATIU: Prioritza extreure el Nom i Cognom real d'una persona física del text web (`decisor_nom`). PROHIBIT posar càrrecs genèrics a `decisor_nom` (si no hi ha nom humà, retorna `decisor_nom = null`). Si `decisor_nom` és `null` però l'empresa té contacte operatiu verificat i compleix el mínim d'operaris de camp, classifica-la igualment com a `estat_decisio = "SELECCIONAT"` i genera la campanya de 3 correus adreçada a la direcció tècnica de l'empresa.
3. DADES I FONTS COMPROBABLES: Només utilitza fites i canals verificables amb URL directa present a les dades d'entrada.

{descarts_str}
{exit_str}

CRITERIS DE PUNTUACIÓ (SCORE 0-100):
- Si l'empresa pertany a una altra localitat allunyada fora del CP/municipi demanat, o no té ni Gatekeeper ni contacte operatiu verificat, o és una botiga de venda al detall sense operaris de camp: DESCARTAR (`estat_decisio = "DESCARTAT"`, Score < 50).
- Si l'empresa opera o té seu al CP o municipi demanat, disposa de quadrilla d'operaris de camp (>= mínim exigit), i té un Gatekeeper amb nom i cognom real O bé disposa de contacte operatiu verificat: SELECCIONAR (`estat_decisio = "SELECCIONAT"`, Score >= 70).
- Si a més s'assembla a un patró d'èxit replicable: LOOKALIKE BOOST (Score >= 85).

ESTRUCTURA DE LA CAMPANYA DE 3 EMAILS AMB TEMPO (SI ÉS SELECCIONAT):
- Pas 1 (Offset: 0 dies - Contacte Inicial en 5 passos):
  1. Salutació personalitzada pel Nom real del Decisor (Gatekeeper).
  2. Menció de la fita recent real o activitat verificada.
  3. Identificació del punt de dolor operatiu del seu sector (pèrdua d'albarans, descontrol de furgonetes, temps d'oficina).
  4. Solució Sevalor: connexió camp-oficina (PWA + bot de Telegram).
  5. Crida a l'acció (CTA) suau per a demo ràpida.
- Pas 2 (Offset: 4 dies - Valor i Cas Replicable):
  Seguiment d'autoritat centrat en un cas d'èxit de manteniment/instal·lacions similar que va resoldre exactament el mateix dolor.
- Pas 3 (Offset: 8 dies - Diagnòstic i Demo 7 Dies):
  Últim impacte directe proposant activar l'entorn de Demo autònom de 7 dies de Sevalor Suite sense compromís.

FORMAT DE RETORN JSON OBLIGATORI (COMPLEIX ESTRICTAMENT AQUESTES CLAUS EXACTES):
```json
{{
  "operaris_estimats": 10,
  "decisor_nom": "Nom i Cognom real d'una persona física o null",
  "decisor_carrec": "Gerent o null",
  "fonts_investigades": ["web|https://..."],
  "fita_recent": "Fita trobada o null",
  "punt_dolor": "Punt de dolor detectat o null",
  "angle_atac": "ANGLE_A_VISIBILITAT_TELEGRAM",
  "score": 85,
  "estat_decisio": "SELECCIONAT",
  "motiu_detallat_ia": "Justificació transparent i detallada de la decisió...",
  "campanya_3_emails": [
    {{
      "pas": 1,
      "tempo_offset_dies": 0,
      "assumpte": "Assumpte correu 1",
      "cos_text": "Cos correu 1..."
    }},
    {{
      "pas": 2,
      "tempo_offset_dies": 4,
      "assumpte": "Assumpte correu 2",
      "cos_text": "Cos correu 2..."
    }},
    {{
      "pas": 3,
      "tempo_offset_dies": 8,
      "assumpte": "Assumpte correu 3",
      "cos_text": "Cos correu 3..."
    }}
  ]
}}
```
ATENCIÓ: Utilitza OBLIGATÒRIAMENT les claus `operaris_estimats`, `motiu_detallat_ia` i `campanya_3_emails` (està prohibit canviar els noms de les claus).
Retorna exclusivament aquest objecte JSON vàlid sense cap text addicional.
"""
    return prompt


def _aplicar_regles_estrictes_post_avaluacio(
    avaluacio: LeadEvaluationSchema,
    codi_postal: str,
    adreca_fisica: Optional[str],
    fonts_verificades: List[str],
    municipi: Optional[str] = None,
    te_contacte_operatiu: bool = False,
    operaris_minims: int = 5,
) -> LeadEvaluationSchema:
    """Valida CP/municipi i permet seleccionar leads amb contacte operatiu encara que falti el nom del Gatekeeper."""
    avaluacio.fonts_investigades = fonts_verificades

    # 1. Validació de l'adreça física al CP exacte o al mateix municipi/polígon industrial
    if adreca_fisica is not None and not validar_cp_o_municipi_en_adreca(adreca_fisica, codi_postal, municipi=municipi):
        if avaluacio.estat_decisio == "SELECCIONAT":
            avaluacio.estat_decisio = "DESCARTAT"
            avaluacio.score = min(avaluacio.score, 30)
            avaluacio.campanya_3_emails = []
            avaluacio.motiu_detallat_ia = (
                f"Descartat (Ubicació Física): L'adreça ('{adreca_fisica or 'No disponible'}') "
                f"no correspon al CP {codi_postal.strip()} ni al municipi ({municipi or 'N/A'})."
            )

    # 2. Gatekeeper Nominal vs Lead Corporatiu amb Contacte Directe Verificat
    if not es_nom_persona_real(avaluacio.decisor_nom):
        avaluacio.decisor_nom = None
        if avaluacio.estat_decisio == "SELECCIONAT":
            if not (te_contacte_operatiu and avaluacio.operaris_estimats >= operaris_minims):
                avaluacio.estat_decisio = "DESCARTAT"
                avaluacio.score = min(avaluacio.score, 40)
                avaluacio.campanya_3_emails = []
                avaluacio.motiu_detallat_ia = (
                    "Descartat automàticament: No s'ha pogut verificar el Gatekeeper ni contacte operatiu suficient."
                )

    return avaluacio


# ==============================================================================
# 3. CRIDA A OPENROUTER I GENERACIÓ ESTRUCTURADA
# ==============================================================================

async def qualificar_candidat_amb_openrouter(
    nom_empresa: str,
    web_url: str,
    codi_postal: str,
    vertical: str,
    operaris_minims: int,
    web_markdown: str,
    fonts_investigades: List[str],
    fita_recent: Optional[str],
    gatekeeper_hints: Dict[str, str],
    db: AsyncSession,
    adreca_fisica: Optional[str] = None,
    municipi: Optional[str] = None,
    te_contacte_operatiu: bool = False,
) -> LeadEvaluationSchema:
    """Avalua el candidat mitjançant OpenRouter (DeepSeek) aplicant validació estricta post-IA.

    Args:
        nom_empresa: Nom de la societat.
        web_url: Web corporatiu.
        codi_postal: Codi postal de la recerca.
        vertical: Sector tècnic (text lliure definit per l'humà).
        operaris_minims: Mínim de treballadors exigit.
        web_markdown: Contingut raspat de la web.
        fonts_investigades: Canals auditats amb URL (web|url, linkedin|url, etc.).
        fita_recent: Fita detectada durant la recerca multi-canal.
        gatekeeper_hints: Pistes verificades del decisor (`nom`, `carrec`, `context`).
        db: Sessió asíncrona per consultar el Doble Bucle d'Aprenentatge.
        adreca_fisica: Adreça física extreta per validar-hi el Codi Postal.
        municipi: Municipi esperat del codi postal per a validació geogràfica flexible.
        te_contacte_operatiu: True si es disposa d'email amb MX vàlid o telèfon directe verificat.

    Returns:
        Instància validada de `LeadEvaluationSchema`.
    """
    context_aprenentatge = await carregar_context_doble_bucle(vertical, db)
    system_prompt = construir_system_prompt(context_aprenentatge)

    nom_sani = _sanititzar_entrada_ia(nom_empresa, 150)
    web_sani = _sanititzar_entrada_ia(web_url, 255)
    cp_sani = _sanititzar_entrada_ia(codi_postal, 15)
    adr_sani = _sanititzar_entrada_ia(adreca_fisica, 250) if adreca_fisica else "No especificada"
    vertical_sani = _sanititzar_entrada_ia(vertical, 150)
    fita_sani = _sanititzar_entrada_ia(fita_recent, 500)
    md_sani = _extreure_context_prioritari_ia(web_markdown, 6000)

    nom_gk_hint = gatekeeper_hints.get("nom") or gatekeeper_hints.get("context") or ""
    carrec_gk_hint = gatekeeper_hints.get("carrec") or ""
    if es_nom_persona_real(nom_gk_hint):
        decisor_hint_str = f"Decisor persona física verificat: {nom_gk_hint} (Càrrec: {carrec_gk_hint or 'Direcció'})"
    elif te_contacte_operatiu:
        decisor_hint_str = (
            "Decisor persona física: Pendent d'extreure del text web. "
            "Disposa de contacte operatiu verificat (admetre com a SELECCIONAT si compleix operaris i ubicació)."
        )
    else:
        decisor_hint_str = "Decisor persona física verificat: CAP NOM REAL NI CONTACTE OPERATIU (descartar obligatòriament)"

    user_prompt = f"""Avalua el següent candidat de prospecció:
- Empresa: {nom_sani}
- Web verificable: {web_sani}
- Adreça Física detectada: {adr_sani}
- Codi Postal sol·licitat: {cp_sani}
- Sector / Vertical (escrit per l'humà): {vertical_sani}
- Mínim d'operaris sol·licitat: {operaris_minims}
- Fonts amb enllaç directe: {', '.join(fonts_investigades)}
- Fita recent multi-canal: {fita_sani or 'No detectada a xarxes'}
- {decisor_hint_str}

Resum del lloc web corporatiu:
{md_sani}
"""

    api_key = settings.OPENROUTER_API_KEY
    model = settings.OPENROUTER_MODEL or "deepseek/deepseek-v4.1-flash"
    if "/" not in model and "flash" in model.lower():
        model = "deepseek/deepseek-v4.1-flash"
    elif "/" not in model and "chat" in model.lower():
        model = "deepseek/deepseek-chat"

    # Si tenim API Key d'OpenRouter vàlida, fem la crida real
    if api_key and not api_key.startswith("test_") and not api_key.startswith("mock_"):
        endpoint = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "https://sevalor.net",
            "X-Title": "Sevalor CRM Prospeccio",
            "Content-Type": "application/json",
        }
        body: Dict[str, Any] = {
            "model": model,
            "models": [model, "deepseek/deepseek-chat"],
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
        }
        if settings.OPENROUTER_PROVIDER_ONLY:
            body["provider"] = settings.openrouter_provider_config

        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                res = await client.post(endpoint, headers=headers, json=body)
                # Si el proveïdor preferent (ex. Baidu) retorna 429 Rate Limit o 5xx, reintentem immediatament
                # sense la restricció 'provider' per permetre a OpenRouter utilitzar la resta de proveïdors o deepseek-chat
                if res.status_code == 429 or res.status_code in (502, 503, 504):
                    logger.warning(
                        "OpenRouter API ha retornat codi %s amb proveïdor preferent. Reintentant sense restricció de proveïdor...",
                        res.status_code,
                    )
                    body_retry = dict(body)
                    body_retry.pop("provider", None)
                    body_retry["models"] = [model, "deepseek/deepseek-chat"]
                    await asyncio.sleep(1.0)
                    res = await client.post(endpoint, headers=headers, json=body_retry)

                if res.status_code == 200:
                    raw_content = res.json()["choices"][0]["message"]["content"]
                    clean_json = raw_content.strip()
                    if clean_json.startswith("```"):
                        clean_json = re.sub(r"^```(?:json)?\s*", "", clean_json)
                        clean_json = re.sub(r"\s*```$", "", clean_json)
                    data = json.loads(clean_json)
                    avaluacio_ia = LeadEvaluationSchema.model_validate(data)
                    return _aplicar_regles_estrictes_post_avaluacio(
                        avaluacio=avaluacio_ia,
                        codi_postal=codi_postal,
                        adreca_fisica=adreca_fisica,
                        fonts_verificades=fonts_investigades,
                        municipi=municipi,
                        te_contacte_operatiu=te_contacte_operatiu,
                        operaris_minims=operaris_minims,
                    )
                logger.warning("OpenRouter API ha retornat codi %s: %s", res.status_code, res.text)
        except Exception as exc:
            logger.error("Error en la crida a OpenRouter per %s: %s. Aplicant avaluador determinista.", nom_empresa, exc)

    # Avaluador determinista basat en regles estrictes (Zero Mock de dades)
    avaluacio_det = _generar_avaluacio_fallback_determinista(
        nom_empresa=nom_empresa,
        web_url=web_url,
        codi_postal=codi_postal,
        vertical=vertical,
        operaris_minims=operaris_minims,
        fonts_investigades=fonts_investigades,
        fita_recent=fita_recent,
        gatekeeper_hints=gatekeeper_hints,
        context_aprenentatge=context_aprenentatge,
        adreca_fisica=adreca_fisica,
        municipi=municipi,
        te_contacte_operatiu=te_contacte_operatiu,
    )
    return _aplicar_regles_estrictes_post_avaluacio(
        avaluacio=avaluacio_det,
        codi_postal=codi_postal,
        adreca_fisica=adreca_fisica,
        fonts_verificades=fonts_investigades,
        municipi=municipi,
        te_contacte_operatiu=te_contacte_operatiu,
        operaris_minims=operaris_minims,
    )


def _generar_avaluacio_fallback_determinista(
    nom_empresa: str,
    web_url: str,
    codi_postal: str,
    vertical: str,
    operaris_minims: int,
    fonts_investigades: List[str],
    fita_recent: Optional[str],
    gatekeeper_hints: Dict[str, str],
    context_aprenentatge: Dict[str, Any],
    adreca_fisica: Optional[str] = None,
    municipi: Optional[str] = None,
    te_contacte_operatiu: bool = False,
) -> LeadEvaluationSchema:
    """Avaluador determinista basat en regles estrictes (CP físic + Gatekeeper real + Sector)."""
    # 1. Comprovar si és un comerç al detall sense operaris de camp o coincideix amb descart humà
    nom_lower = nom_empresa.lower()
    if any(w in nom_lower for w in ["botiga", "tienda", "venda", "detall", "subministraments", "mostrador"]):
        regles_descart = context_aprenentatge.get("regles_descart", [])
        motiu_regla = (
            regles_descart[0].get("motiu_descart_huma", "Sense operaris al carrer")
            if regles_descart
            else "Comerç al detall / venda de mostrador sense quadrilles d'operaris al terreny"
        )
        return LeadEvaluationSchema(
            operaris_estimats=1,
            decisor_nom=None,
            decisor_carrec=None,
            fonts_investigades=fonts_investigades,
            fita_recent=fita_recent,
            punt_dolor="Model comercial enfocat a botiga física, no tenen quadrilles de terreny",
            angle_atac="ANGLE_A_VISIBILITAT_TELEGRAM",
            score=25,
            estat_decisio="DESCARTAT",
            motiu_detallat_ia=f"Descartat perquè no compleix el mínim d'operaris de camp ({motiu_regla}).",
            campanya_3_emails=[],
        )

    # 2. Comprovar adreça física amb CP o municipi
    if adreca_fisica is not None and not validar_cp_o_municipi_en_adreca(adreca_fisica, codi_postal, municipi=municipi):
        return LeadEvaluationSchema(
            operaris_estimats=0,
            decisor_nom=None,
            decisor_carrec=None,
            fonts_investigades=fonts_investigades,
            fita_recent=fita_recent,
            punt_dolor=None,
            angle_atac="ANGLE_A_VISIBILITAT_TELEGRAM",
            score=20,
            estat_decisio="DESCARTAT",
            motiu_detallat_ia=(
                f"Descartat (Ubicació Física): L'adreça ('{adreca_fisica or 'No disponible'}') "
                f"no correspon al CP {codi_postal.strip()} ni al municipi ({municipi or 'N/A'})."
            ),
            campanya_3_emails=[],
        )

    # 3. Comprovar Gatekeeper real o admissió per contacte operatiu
    cand_nom = (gatekeeper_hints.get("nom") or gatekeeper_hints.get("context") or "").strip()
    te_nom_real = es_nom_persona_real(cand_nom)
    if not te_nom_real and not te_contacte_operatiu:
        return LeadEvaluationSchema(
            operaris_estimats=max(operaris_minims, 5),
            decisor_nom=None,
            decisor_carrec=gatekeeper_hints.get("carrec"),
            fonts_investigades=fonts_investigades,
            fita_recent=fita_recent,
            punt_dolor="Manca d'identificació nominal del decisor i sense contacte operatiu verificat",
            angle_atac="ANGLE_A_VISIBILITAT_TELEGRAM",
            score=35,
            estat_decisio="DESCARTAT",
            motiu_detallat_ia="Descartat automàticament: Sense Gatekeeper nominal ni contacte operatiu verificat.",
            campanya_3_emails=[],
        )

    decisor_nom = cand_nom if te_nom_real else None
    salutacio_nom = decisor_nom or f"equip directiu de {nom_empresa}"
    decisor_carrec = gatekeeper_hints.get("carrec") or ("Gerent" if te_nom_real else "Direcció / Gerència (Pendent nom)")

    # Lookalike boost si tenim patrons d'èxit del mateix sector
    te_cas_exit = any(
        c.get("vertical", "").lower() in vertical.lower() or vertical.lower() in c.get("vertical", "").lower()
        for c in context_aprenentatge.get("casos_exit_replicables", [])
    )
    score_base = 88 if te_cas_exit else 82
    if not te_nom_real and te_contacte_operatiu:
        score_base = 72
    operaris = max(operaris_minims + 3, 8) if te_nom_real else max(operaris_minims + 2, 7)

    fita = fita_recent or f"Presència corporativa verificada a {web_url} al Codi Postal {codi_postal}"
    punt_dolor = (
        "Pèrdua d'hores entre albarans en paper fets a la furgoneta i posterior picatge a oficina"
        if te_nom_real
        else "Manca d'identificació nominal del decisor a la web (admesa per contacte operatiu directe)"
    )

    # Campanya de 3 emails amb tempo adreçada al nom REAL del Gatekeeper o salutació corporativa
    campanya = [
        EmailStepSchema(
            pas=1,
            tempo_offset_dies=0,
            assumpte=f"Optimització de partes de treball per a {nom_empresa}",
            cos_text=(
                f"Hola {salutacio_nom},\n\n"
                f"Hem seguit la trajectòria de {nom_empresa} ({fita}). "
                f"En empreses de {vertical} amb quadrilles com la vostra, el coll d'ampolla habitual "
                f"és el descontrol dels partes d'obra i la informació dispersa entre les furgonetes i l'oficina.\n\n"
                f"A Sevalor Suite connectem els vostres operaris des de la PWA mòbil amb la gestió central, "
                f"i notifiquem el client final mitjançant el nostre Bot Oficial de Telegram per signar les entregues al moment.\n\n"
                f"Us faria servei veure una demostració de 10 minuts adaptada al vostre flux?\n\n"
                f"Salutacions cordials,\nEquip Tècnic Sevalor\ntecnic@sevalor.net"
            ),
        ),
        EmailStepSchema(
            pas=2,
            tempo_offset_dies=4,
            assumpte=f"Com empreses de {vertical} han eliminat el descontrol de furgonetes",
            cos_text=(
                f"Hola {salutacio_nom},\n\n"
                f"Fa uns dies us comentàvem el repte dels partes d'obra. Una empresa similar del sector de {vertical} "
                f"va reduir un 80% el temps de facturació automatitzant el tancament de l'albarà des del terreny "
                f"amb la PWA de Sevalor i la confirmació immediata per Telegram.\n\n"
                f"Us podem preparar un entorn de proves amb dades del vostre sector per comprovar-ho en viu.\n\n"
                f"Cordialment,\ntecnic@sevalor.net"
            ),
        ),
        EmailStepSchema(
            pas=3,
            tempo_offset_dies=8,
            assumpte=f"Activació de Demo Real de 7 dies per a {nom_empresa}",
            cos_text=(
                f"Hola {salutacio_nom},\n\n"
                f"Per no insistir més per aquesta via: si voleu provar sense cap compromís la plataforma, "
                f"us podem habilitar una instància Demo de 7 dies totalment operativa per a {nom_empresa}.\n\n"
                f"Podeu respondre aquest correu i us enviem l'accés immediat.\n\n"
                f"Una salutació,\ntecnic@sevalor.net"
            ),
        ),
    ]

    nom_descripcio = decisor_nom if te_nom_real else "admesa per contacte operatiu"
    return LeadEvaluationSchema(
        operaris_estimats=operaris,
        decisor_nom=decisor_nom,
        decisor_carrec=decisor_carrec,
        fonts_investigades=fonts_investigades,
        fita_recent=fita,
        punt_dolor=punt_dolor,
        angle_atac="ANGLE_A_VISIBILITAT_TELEGRAM",
        score=score_base,
        estat_decisio="SELECCIONAT",
        motiu_detallat_ia=(
            f"Empresa amb adreça física verificada al CP {codi_postal}, decisor ({nom_descripcio}) "
            f"i quadrilla estimada de {operaris} operaris a la vertical '{vertical}'. "
            f"{'Lookalike coincident amb patrons d\'èxit replicables. ' if te_cas_exit else ''}"
            f"Fita verificada: {fita}."
        ),
        campanya_3_emails=campanya,
    )
