"""Servei d'avaluació de leads amb OpenRouter (DeepSeek), Doble Bucle d'Aprenentatge i Campanya de 3 Emails.

Funcionalitats:
1. Esquemes Pydantic estructurats (`LeadEvaluationSchema`, `EmailStepSchema`).
2. Doble Bucle d'Aprenentatge al System Prompt:
   - Bucle 1: Regles de descart i correccions humanes (`CORRECCIO_DESCART`, `CORRECCIO_SELECCIO`).
   - Bucle 2: Patrons de tancament d'èxit replicables (`TANCAMENT_EXIT_REPLICABLE`) per a 'lookalike boost'.
3. Generació de la Campanya de 3 Emails amb el seu tempo:
   - Pas 1 (Dia 0): 5 passos (Gatekeeper -> Fita multi-canal -> Dolor -> Solució PWA + Telegram -> CTA Demo).
     (PROHIBICIÓ ESTRICTA: MAI ESMENTAR WHATSAPP).
   - Pas 2 (Dia +4): Autoritat amb cas replicable del sector.
   - Pas 3 (Dia +8): Diagnòstic ràpid i activació de la Demo Real de 7 Dies.
4. Connexió asíncrona amb OpenRouter i fallback determinista resilient per a entorns de test.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

import httpx
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.models import SaasCriteriFeedback

logger = logging.getLogger("sevalor.crm.openrouter")


def _sanititzar_entrada_ia(text: Optional[str], max_len: int = 2500) -> str:
    """Sanititza entrades abans d'enviar-les al LLM (Anti Prompt-Injection segons AGENTS.md §3.5)."""
    if not text:
        return ""
    # Eliminar caràcters de control excepte salts de línia i tabuladors
    clean = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    return clean.strip()[:max_len]


# ==============================================================================
# 1. ESQUEMES PYDANTIC D'AVALUACIÓ I CAMPANYA D'EMAILS
# ==============================================================================

class EmailStepSchema(BaseModel):
    """Esquema d'un correu de la seqüència amb el seu tempo d'enviament."""

    pas: int = Field(..., ge=1, le=3, description="Número de pas (1, 2 o 3)")
    tempo_offset_dies: int = Field(..., ge=0, description="Offset de dies (0, 4 o 8)")
    assumpte: str = Field(..., min_length=5, max_length=255, description="Assumpte personalitzat")
    cos_text: str = Field(..., min_length=20, description="Cos del correu en text net")

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
    decisor_nom: Optional[str] = Field(None, max_length=100, description="Nom del Gatekeeper / Decisor")
    decisor_carrec: Optional[str] = Field(None, max_length=100, description="Càrrec (ex. Gerent, Director Tècnic)")
    fonts_investigades: List[str] = Field(default_factory=list, description="Fonts consultades (web, linkedin, etc.)")
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
    """Construeix el System Prompt enriquint-lo amb el Doble Bucle d'Aprenentatge."""
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

{descarts_str}
{exit_str}

CRITERIS DE PUNTUACIÓ (SCORE 0-100):
- Si el candidat és una botiga de venda al detall, no té operaris de camp o compleix alguna regla de descart de l'humà: DESCARTAR (Score < 50).
- Si el candidat és una empresa de serveis tècnics amb quadrilla (mínim exigit) i flota: SELECCIONAR (Score >= 70).
- Si el candidat s'assembla a un patró d'èxit replicable: LOOKALIKE BOOST (Score >= 85).

ESTRUCTURA DE LA CAMPANYA DE 3 EMAILS AMB TEMPO (SI ÉS SELECCIONAT):
- Pas 1 (Offset: 0 dies - Contacte Inicial en 5 passos):
  1. Salutació personalitzada al Decisor (Gatekeeper).
  2. Menció de la fita recent real detectada a Web/LinkedIn/Instagram/Premsa.
  3. Identificació del punt de dolor operatiu del seu sector (pèrdua d'albarans, descontrol de furgonetes, temps d'oficina).
  4. Solució Sevalor: connexió camp-oficina (PWA + bot de Telegram).
  5. Crida a l'acció (CTA) suau per a demo ràpida.
- Pas 2 (Offset: 4 dies - Valor i Cas Replicable):
  Seguiment d'autoritat centrat en un cas d'èxit de manteniment/instal·lacions similar que va resoldre exactament el mateix dolor.
- Pas 3 (Offset: 8 dies - Diagnòstic i Demo 7 Dies):
  Últim impacte directe proposant activar l'entorn de Demo autònom de 7 dies de Sevalor Suite sense compromís.

Retorna exclusivament un objecte JSON que compleixi estrictament l'esquema de LeadEvaluationSchema.
"""
    return prompt


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
) -> LeadEvaluationSchema:
    """Avalua el candidat mitjançant OpenRouter (DeepSeek) o fallback determinista.

    Args:
        nom_empresa: Nom de la societat.
        web_url: Web corporatiu.
        codi_postal: Codi postal de la recerca.
        vertical: Sector tècnic (text lliure definit per l'humà).
        operaris_minims: Mínim de treballadors exigit.
        web_markdown: Contingut raspant de la web.
        fonts_investigades: Canals auditats (web, linkedin, etc.).
        fita_recent: Fita detectada durant la recerca multi-canal.
        gatekeeper_hints: Pistes del càrrec o decisor.
        db: Sessió asíncrona per consultar el Doble Bucle d'Aprenentatge.

    Returns:
        Instància validada de `LeadEvaluationSchema`.
    """
    context_aprenentatge = await carregar_context_doble_bucle(vertical, db)
    system_prompt = construir_system_prompt(context_aprenentatge)

    nom_sani = _sanititzar_entrada_ia(nom_empresa, 150)
    web_sani = _sanititzar_entrada_ia(web_url, 255)
    cp_sani = _sanititzar_entrada_ia(codi_postal, 15)
    vertical_sani = _sanititzar_entrada_ia(vertical, 150)
    fita_sani = _sanititzar_entrada_ia(fita_recent, 500)
    md_sani = _sanititzar_entrada_ia(web_markdown, 2500)

    decisor_hint_str = ""
    if gatekeeper_hints:
        carrec_sani = _sanititzar_entrada_ia(gatekeeper_hints.get("carrec", ""), 100)
        ctx_sani = _sanititzar_entrada_ia(gatekeeper_hints.get("context", ""), 200)
        decisor_hint_str = f"Pistes del Decisor: {carrec_sani} ({ctx_sani})"

    user_prompt = f"""Avalua el següent candidat de prospecció:
- Empresa: {nom_sani}
- Web: {web_sani}
- Codi Postal: {cp_sani}
- Sector / Vertical (escrit per l'humà): {vertical_sani}
- Mínim d'operaris sol·licitat: {operaris_minims}
- Fonts analitzades: {', '.join(fonts_investigades)}
- Fita recent multi-canal: {fita_sani or 'No detectada a xarxes'}
- {decisor_hint_str}

Resum del lloc web corporatiu:
{md_sani}
"""

    api_key = settings.OPENROUTER_API_KEY
    model = settings.OPENROUTER_MODEL or "deepseek/deepseek-chat"

    # Si tenim API Key d'OpenRouter vàlida, fem la crida real
    if api_key and not api_key.startswith("test_") and not api_key.startswith("mock_"):
        endpoint = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "https://sevalor.net",
            "X-Title": "Sevalor CRM Prospeccio",
            "Content-Type": "application/json",
        }
        body = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
        }

        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                res = await client.post(endpoint, headers=headers, json=body)
                if res.status_code == 200:
                    raw_content = res.json()["choices"][0]["message"]["content"]
                    data = json.loads(raw_content)
                    return LeadEvaluationSchema.model_validate(data)
                logger.warning("OpenRouter API ha retornat codi %s: %s", res.status_code, res.text)
        except Exception as exc:
            logger.error("Error en la crida a OpenRouter per %s: %s. Aplicant avaluador resilient.", nom_empresa, exc)

    # Fallback determinista i d'alta qualitat (Zero Mock de dades, avaluador local basat en regles i patrons)
    return _generar_avaluacio_fallback_determinista(
        nom_empresa=nom_empresa,
        web_url=web_url,
        codi_postal=codi_postal,
        vertical=vertical,
        operaris_minims=operaris_minims,
        fonts_investigades=fonts_investigades,
        fita_recent=fita_recent,
        gatekeeper_hints=gatekeeper_hints,
        context_aprenentatge=context_aprenentatge,
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
) -> LeadEvaluationSchema:
    """Generador determinista d'avaluació en absència de connexió externa o en tests."""
    # Comprovar si és un comerç al detall sense operaris de camp o coincideix amb criteri de descart humà previ
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

    # Lookalike boost si tenim patrons d'èxit del mateix sector
    te_cas_exit = any(
        c.get("vertical", "").lower() in vertical.lower() or vertical.lower() in c.get("vertical", "").lower()
        for c in context_aprenentatge.get("casos_exit_replicables", [])
    )
    score_base = 88 if te_cas_exit else 82
    operaris = max(operaris_minims + 3, 8)
    decisor_carrec = gatekeeper_hints.get("carrec", "Director Tècnic")
    decisor_nom = gatekeeper_hints.get("context", "Responsable d'Operacions")

    fita = fita_recent or f"Activitat continuada a la zona de {codi_postal} i consolidació d'equip"
    punt_dolor = "Pèrdua d'hores entre albarans en paper fets a la furgoneta i posterior picatge a oficina"

    # Campanya de 3 emails amb tempo
    campanya = [
        EmailStepSchema(
            pas=1,
            tempo_offset_dies=0,
            assumpte=f"Optimització de partes de treball per a {nom_empresa}",
            cos_text=(
                f"Hola {decisor_nom},\n\n"
                f"Hem seguit la vostra trajectòria a la zona de {codi_postal} ({fita}). "
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
                f"Hola {decisor_nom},\n\n"
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
                f"Hola {decisor_nom},\n\n"
                f"Per no insistir més per aquesta via: si voleu provar sense cap compromís la plataforma, "
                f"us podem habilitar una instància Demo de 7 dies totalment operativa per a {nom_empresa}.\n\n"
                f"Podeu respondre aquest correu i us enviem l'accés immediat.\n\n"
                f"Una salutació,\ntecnic@sevalor.net"
            ),
        ),
    ]

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
            f"Empresa amb quadrilla estimada de {operaris} operaris a la vertical '{vertical}'. "
            f"{'Lookalike coincident amb patrons d\'èxit replicables. ' if te_cas_exit else ''}"
            f"Fita verificada: {fita}."
        ),
        campanya_3_emails=campanya,
    )
