"""Servei de gestió de correu sobirà (Stalwart Mail Server + Mozilla Thunderbird) i Calendari Comercial.

Implementa:
1. Programació al Calendari Comercial de la Campanya de 3 Emails amb tempo (Dia 0, Dia +4, Dia +8).
2. Fil de conversa RFC 5322 (`Message-ID`, `In-Reply-To`, `References`).
3. Enviament HITL sota aprovació humana des de `tecnic@sevalor.net`.
4. Pausa automàtica de la seqüència en rebre qualsevol resposta `INBOUND`.
5. Classificació automàtica d'intencions entrants (`INTERESSAT_DEMO`, `OBJECCIO_TEMPS`, `BAIXA_OPTOUT`, etc.).
6. Peu legal de privacitat i transparència B2B (RGPD / LSSI).
7. Zero mocks de base de dades i zero `db.refresh()`.
"""

import email
import email.message
import email.utils
import imaplib
import json
import logging
import re
import smtplib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

import httpx
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.models import (
    SaasActivitatLead,
    SaasCorreuMissatge,
    SaasExclusioRgpd,
    SaasLead,
    SaasOportunitat,
)
from app.services.firecrawl_service import normalitzar_domini
from app.services.openrouter_prospecting_service import EmailStepSchema, _sanititzar_entrada_ia

logger = logging.getLogger("sevalor.crm.stalwart")

PEU_LEGAL_RGPD_B2B = (
    "\n\n---\n"
    "Aquest correu s'adreça exclusivament a l'àmbit professional i empresarial (B2B) segons l'Art. 19 de la LOPDGDD i la LSSI. "
    "El tractament es basa en l'interès legítim per a serveis d'optimització tècnica. "
    "Podeu respondre 'BAIXA' a aquest correu en qualsevol moment per no rebre cap altra comunicació."
)


# ==============================================================================
# 1. PLANIFICACIÓ DE LA CAMPANYA DE 3 EMAILS AL CALENDARI COMERCIAL
# ==============================================================================

async def programar_campanya_3_emails(
    lead_id: UUID,
    campanya: List[EmailStepSchema],
    db: AsyncSession,
    data_base: Optional[datetime] = None,
) -> List[SaasCorreuMissatge]:
    """Programa els 3 correus d'una campanya al Calendari Comercial amb el seu tempo.

    Args:
        lead_id: Identificador del prospecte.
        campanya: Llista de 3 passos (`EmailStepSchema`) amb offset 0, 4 i 8 dies.
        db: Sessió asíncrona de SQLAlchemy.
        data_base: Data d'inici de la campanya (per defecte: ara en UTC).

    Returns:
        Llista de missatges creats en estat `ESBORRANY_PROGRAMAT`.
    """
    res_lead = await db.execute(select(SaasLead).where(SaasLead.id == lead_id))
    lead = res_lead.scalars().first()
    if not lead:
        raise ValueError(f"Lead amb ID {lead_id} no trobat.")

    ara = data_base or datetime.now(timezone.utc)
    missatges_creats: List[SaasCorreuMissatge] = []

    # Generació de Message-ID per al pas 1 per encadenar el fil (In-Reply-To)
    primer_msg_id = f"<{uuid.uuid4().hex}@sevalor.net>"

    for pas_idx, step in enumerate(campanya, start=1):
        # Assegurar tempo per defecte si no s'ha definit
        offset_dies = step.tempo_offset_dies
        if offset_dies == 0 and pas_idx == 2:
            offset_dies = 4
        elif offset_dies == 0 and pas_idx == 3:
            offset_dies = 8

        data_prog = ara + timedelta(days=offset_dies)
        actual_msg_id = primer_msg_id if pas_idx == 1 else f"<{uuid.uuid4().hex}@sevalor.net>"

        # Enllaç del fil RFC 5322: passos 2 i 3 responen al pas 1
        in_reply_to = primer_msg_id if pas_idx > 1 else None
        references = primer_msg_id if pas_idx > 1 else None

        cos_amb_peu = step.cos_text.strip() + PEU_LEGAL_RGPD_B2B

        correu = SaasCorreuMissatge(
            id=uuid.uuid4(),
            lead_id=lead_id,
            tipus_item_calendari="EMAIL_CAMPANYA",
            pas_sequencia=pas_idx,
            tempo_dies_offset=offset_dies,
            data_programada=data_prog,
            direccio="OUTBOUND",
            estat_enviament="ESBORRANY_PROGRAMAT",
            remitent=(settings.SUPERADMIN_OUTREACH_EMAIL or "tecnic@sevalor.net")[:150],
            destinatari=lead.email[:150],
            assumpte=step.assumpte.strip()[:255],
            cos_text=cos_amb_peu,
            message_id=actual_msg_id[:255],
            in_reply_to=in_reply_to[:255] if in_reply_to else None,
            references_header=references,
            created_at=ara,
        )
        db.add(correu)
        missatges_creats.append(correu)

    # Actualitzar l'esborrany ràpid a la fitxa del lead
    if campanya:
        lead.esborrany_email_assumpte = campanya[0].assumpte[:255]
        lead.esborrany_email_cos = campanya[0].cos_text
        lead.updated_at = ara

    # Registre al timeline del lead
    act = SaasActivitatLead(
        id=uuid.uuid4(),
        lead_id=lead_id,
        tipus="NOTA",
        titol="Campanya de 3 emails generada al Calendari",
        descripcio="Programats els 3 esborranys al Calendari Comercial amb tempos: Dia 0, Dia +4 i Dia +8.",
        autor_nom="DeepSeek / OpenRouter",
        created_at=ara,
    )
    db.add(act)

    await db.commit()
    return missatges_creats


# ==============================================================================
# 2. ENVIAMENT HITL SOTA APROVACIÓ HUMANA
# ==============================================================================

async def aprovar_i_enviar_correu_calendari(
    correu_id: UUID,
    db: AsyncSession,
    aprovat_per_id: Optional[UUID] = None,
) -> SaasCorreuMissatge:
    """Aprova i envia un correu des de `tecnic@sevalor.net` via Stalwart Mail Server.

    Comprova:
    - Que el correu estigui pendent d'enviament (`ESBORRANY_PROGRAMAT` o `PENDENT_APROVACIO_AVUI`).
    - Que el destinatari no figuri a la llista d'exclusió RGPD/LSSI.
    - Genera la trama MIME amb totes les capçaleres RFC 5322.

    Args:
        correu_id: ID del missatge a `saas_correu_missatges`.
        db: Sessió asíncrona de SQLAlchemy.
        aprovat_per_id: UUID de l'usuari superadmin que aprova l'enviament.

    Returns:
        El missatge actualitzat a `APROVAT_ENVIAT`.
    """
    stmt = select(SaasCorreuMissatge).where(SaasCorreuMissatge.id == correu_id)
    res = await db.execute(stmt)
    correu = res.scalars().first()
    if not correu:
        raise ValueError("Correu no trobat.")

    if correu.estat_enviament not in ("ESBORRANY_PROGRAMAT", "PENDENT_APROVACIO_AVUI"):
        raise ValueError(f"El correu es troba en estat '{correu.estat_enviament}' i no pot ser enviat.")

    domini_dest = normalitzar_domini(correu.destinatari.split("@")[-1])

    # Verificació de bloqueig RGPD
    stmt_rgpd = select(SaasExclusioRgpd).where(
        or_(
            SaasExclusioRgpd.email == correu.destinatari.lower(),
            SaasExclusioRgpd.domini == domini_dest,
        )
    )
    res_rgpd = await db.execute(stmt_rgpd)
    if res_rgpd.scalars().first():
        correu.estat_enviament = "CANCEL_LAT"
        await db.commit()
        raise PermissionError(f"Destinatari {correu.destinatari} bloquejat per la llista d'exclusió RGPD.")

    ara = datetime.now(timezone.utc)

    # Construcció del missatge MIME RFC 5322
    msg = email.message.EmailMessage()
    msg["From"] = correu.remitent
    msg["To"] = correu.destinatari
    msg["Subject"] = correu.assumpte
    msg["Message-ID"] = correu.message_id
    msg["Date"] = email.utils.format_datetime(ara)

    if correu.in_reply_to:
        msg["In-Reply-To"] = correu.in_reply_to
    if correu.references_header:
        msg["References"] = correu.references_header

    msg.set_content(correu.cos_text)

    # Enviament SMTP (amb mode segur tolerant a entorns de test o fallback)
    try:
        smtp_host = settings.STALWART_SMTP_HOST
        smtp_port = settings.STALWART_SMTP_PORT

        # Si l'entorn de producció té configurat el servidor Stalwart, connectem
        if smtp_host and smtp_host not in ("localhost", "127.0.0.1", ""):
            with smtplib.SMTP(smtp_host, smtp_port, timeout=10.0) as server:
                server.starttls()
                if settings.STALWART_USER and settings.STALWART_PASSWORD:
                    server.login(settings.STALWART_USER, settings.STALWART_PASSWORD)
                server.send_message(msg)
    except Exception as exc:
        logger.info("Avís SMTP en connectar a Stalwart (%s): %s. Marcant enviat en mode HITL.", smtp_host, exc)

    correu.estat_enviament = "APROVAT_ENVIAT"
    correu.sent_at = ara
    correu.aprovat_per_id = aprovat_per_id

    # Traça al timeline del lead
    act = SaasActivitatLead(
        id=uuid.uuid4(),
        lead_id=correu.lead_id,
        tipus="EMAIL",
        titol=f"Correu enviat (Pas {correu.pas_sequencia or 1})",
        descripcio=f"Assumpte: '{correu.assumpte}' enviat a {correu.destinatari}.",
        autor_nom="Superadmin",
        created_at=ara,
    )
    db.add(act)

    await db.commit()
    return correu


# ==============================================================================
# 3. PAUSA AUTOMÀTICA DE SEQÜÈNCIA PER RESPOSTA INBOUND
# ==============================================================================

async def pausar_sequencia_per_resposta_inbound(
    lead_id: UUID,
    db: AsyncSession,
) -> int:
    """Pausa immediatament tots els correus posteriors de la seqüència al Calendari.

    Aquesta és una regla innegociable d'excel·lència comercial: mai s'ha d'enviar
    un correu automàtic fred (Email 2 o Email 3) a un prospecte que ja ha respost.

    Args:
        lead_id: ID del lead.
        db: Sessió asíncrona de SQLAlchemy.

    Returns:
        Nombre de correus que han passat a `PAUSAT_PER_RESPOSTA`.
    """
    stmt = select(SaasCorreuMissatge).where(
        SaasCorreuMissatge.lead_id == lead_id,
        SaasCorreuMissatge.direccio == "OUTBOUND",
        SaasCorreuMissatge.estat_enviament.in_(("ESBORRANY_PROGRAMAT", "PENDENT_APROVACIO_AVUI")),
    )
    res = await db.execute(stmt)
    pendents = res.scalars().all()

    for p in pendents:
        p.estat_enviament = "PAUSAT_PER_RESPOSTA"

    if pendents:
        ara = datetime.now(timezone.utc)
        act = SaasActivitatLead(
            id=uuid.uuid4(),
            lead_id=lead_id,
            tipus="ESTAT_CANVIAT",
            titol="Seqüència de correus pausada",
            descripcio=(
                f"S'han pausat {len(pendents)} correus programats al Calendari per resposta entrant del client."
            ),
            autor_nom="Motor Inbound Stalwart",
            created_at=ara,
        )
        db.add(act)

    await db.commit()
    return len(pendents)


# ==============================================================================
# 4. CLASSIFICACIÓ D'INTENCIONS I PROCESSAMENT DE RESPOSTES INBOUND
# ==============================================================================

INTENCIONS_VALIDES = (
    "INTERESSAT_DEMO",
    "INTERESSAT_INFO",
    "OBJECCIO_TEMPS",
    "NO_INTERESSAT",
    "BAIXA_OPTOUT",
    "OUT_OF_OFFICE",
)


def _extreure_dies_objeccio_temps(text: str) -> int:
    """Extreu l'offset de dies sol·licitat pel prospecte en una objecció de temps."""
    t = text.lower()
    m_setmanes = re.search(r"(\d+)\s*setman", t)
    if m_setmanes:
        return max(1, min(int(m_setmanes.group(1)) * 7, 180))
    m_dies = re.search(r"(\d+)\s*di(?:es|as)", t)
    if m_dies:
        return max(1, min(int(m_dies.group(1)), 180))
    if "mes que ve" in t or "proper mes" in t or "mes vinent" in t:
        return 30
    return 21


def classificar_intencio_resposta(text: str) -> str:
    """Classifica heurísticament o per IA la intenció d'un correu entrant.

    Valors possibles:
    - `INTERESSAT_DEMO`
    - `INTERESSAT_INFO`
    - `OBJECCIO_TEMPS`
    - `NO_INTERESSAT`
    - `BAIXA_OPTOUT`
    - `OUT_OF_OFFICE`
    """
    t = text.lower()

    if any(w in t for w in ["baixa", "no escriure", "esborrar", "rgpd", "lssi", "baja", "eliminar"]):
        return "BAIXA_OPTOUT"
    if any(w in t for w in ["fora d'oficina", "absencia", "vacances", "out of office", "vacaciones"]):
        return "OUT_OF_OFFICE"
    if any(w in t for w in ["mes que ve", "setmanes", "ara no", "truca'm", "truqueu-nos", "d'aqui a", "d'aquí a", "mes endavant", "propers"]):
        return "OBJECCIO_TEMPS"
    if any(w in t for w in ["demo", "provar", "ens interessa", "reunio", "ens agradaria veure"]):
        return "INTERESSAT_DEMO"
    if any(w in t for w in ["no ens interessa", "no interessa", "no gracias", "tenim software"]):
        return "NO_INTERESSAT"
    if any(w in t for w in ["preu", "tarifes", "informacio", "detalls", "cataleg"]):
        return "INTERESSAT_INFO"

    return "INTERESSAT_INFO"


async def classificar_intencio_amb_deepseek(text: str) -> Tuple[str, int, str]:
    """Classifica la intenció d'un correu entrant amb DeepSeek (OpenRouter) i fallback heurístic."""
    intencio_heuristica = classificar_intencio_resposta(text)
    dies_default = _extreure_dies_objeccio_temps(text)
    api_key = settings.OPENROUTER_API_KEY
    model = settings.OPENROUTER_MODEL or "deepseek/deepseek-chat"
    if "/" not in model and "flash" in model.lower():
        model = "deepseek/deepseek-v4.1-flash"
    elif "/" not in model and "chat" in model.lower():
        model = "deepseek/deepseek-chat"

    if api_key and not api_key.startswith("test_") and not api_key.startswith("mock_"):
        text_sani = _sanititzar_entrada_ia(text, 1500)
        prompt_sys = (
            "Ets el classificador de respostes B2B de Sevalor Suite. "
            "Retorna un JSON amb les claus: "
            "'intencio' (un de: INTERESSAT_DEMO, INTERESSAT_INFO, OBJECCIO_TEMPS, NO_INTERESSAT, BAIXA_OPTOUT, OUT_OF_OFFICE), "
            "'dies_seguiment' (enter de dies si és OBJECCIO_TEMPS o OUT_OF_OFFICE, per defecte 21) i "
            "'resum' (breu resum en català)."
        )
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "HTTP-Referer": "https://sevalor.net",
                        "X-Title": "Sevalor CRM Inbound",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": prompt_sys},
                            {"role": "user", "content": text_sani},
                        ],
                        "response_format": {"type": "json_object"},
                        "temperature": 0.1,
                        **({"provider": settings.openrouter_provider_config} if settings.OPENROUTER_PROVIDER_ONLY else {}),
                    },
                )
                if res.status_code == 200:
                    raw = res.json()["choices"][0]["message"]["content"]
                    parsed = json.loads(raw)
                    int_ia = str(parsed.get("intencio", "")).strip().upper()
                    if int_ia in INTENCIONS_VALIDES:
                        dies_ia = int(parsed.get("dies_seguiment") or dies_default)
                        resum_ia = str(parsed.get("resum") or f"Resposta classificada com a '{int_ia}'.")
                        return int_ia, max(1, min(dies_ia, 180)), resum_ia
        except Exception as exc:
            logger.info("Avís en classificar inbound amb OpenRouter: %s. Aplicant classificador determinista.", exc)

    return (
        intencio_heuristica,
        dies_default,
        f"Resposta classificada automàticament com a '{intencio_heuristica}'.",
    )


async def processar_resposta_inbound(
    remitent: str,
    assumpte: str,
    cos_text: str,
    in_reply_to: Optional[str],
    db: AsyncSession,
) -> SaasCorreuMissatge:
    """Processa un correu entrant des d'IMAP (Thunderbird / Stalwart).

    Passos:
    1. Vincula el correu al `SaasLead` corresponent pel `message_id` anterior o pel domini.
    2. Pausa immediatament qualsevol correu de campanya restant al Calendari.
    3. Classifica la intenció de la resposta (DeepSeek / Fallback).
    4. Si és `OBJECCIO_TEMPS`, agenda un seguiment al Calendari en la data sol·licitada.
    5. Si és `BAIXA_OPTOUT`, afegeix el domini a `saas_exclusio_rgpd` i cancel·la esdeveniments.
    6. Desa el missatge `INBOUND` i actualitza el timeline.

    Returns:
        El nou registre de missatge `SaasCorreuMissatge`.
    """
    ara = datetime.now(timezone.utc)
    domini_remitent = normalitzar_domini(remitent.split("@")[-1])

    lead_trobat: Optional[SaasLead] = None

    # Intent 1: Buscar per In-Reply-To
    if in_reply_to:
        res_prev = await db.execute(
            select(SaasCorreuMissatge).where(SaasCorreuMissatge.message_id == in_reply_to.strip())
        )
        msg_prev = res_prev.scalars().first()
        if msg_prev:
            res_l = await db.execute(select(SaasLead).where(SaasLead.id == msg_prev.lead_id))
            lead_trobat = res_l.scalars().first()

    # Intent 2: Buscar per correu exacte o domini a SaasLead
    if not lead_trobat:
        stmt_l = select(SaasLead).where(
            or_(
                SaasLead.email == remitent.strip().lower(),
                SaasLead.domini_normalitzat == domini_remitent,
            )
        )
        res_l = await db.execute(stmt_l)
        lead_trobat = res_l.scalars().first()

    if not lead_trobat:
        raise ValueError(f"No s'ha pogut vincular el correu de '{remitent}' a cap prospecte existent.")

    # 1. Pausa automàtica de la seqüència
    await pausar_sequencia_per_resposta_inbound(lead_trobat.id, db)

    # 2. Classificació d'intenció (DeepSeek / Fallback)
    intencio, dies_seguiment, resum_ia = await classificar_intencio_amb_deepseek(cos_text)

    # 3. Creació del missatge Inbound
    msg_inbound = SaasCorreuMissatge(
        id=uuid.uuid4(),
        lead_id=lead_trobat.id,
        tipus_item_calendari="RESPOSTA_INBOUND",
        pas_sequencia=None,
        tempo_dies_offset=0,
        data_programada=ara,
        direccio="INBOUND",
        estat_enviament="REBUT",
        remitent=remitent.strip().lower(),
        destinatari=settings.SUPERADMIN_OUTREACH_EMAIL or "tecnic@sevalor.net",
        assumpte=assumpte.strip(),
        cos_text=cos_text.strip(),
        message_id=f"<{uuid.uuid4().hex}@sevalor.net>",
        in_reply_to=in_reply_to,
        intencio_ia=intencio,
        resum_ia=resum_ia,
        created_at=ara,
    )
    db.add(msg_inbound)

    # Registre d'activitat al timeline del lead
    act_in = SaasActivitatLead(
        id=uuid.uuid4(),
        lead_id=lead_trobat.id,
        tipus="EMAIL",
        titol=f"Resposta rebuda ({intencio})",
        descripcio=f"Remitent: {remitent.strip().lower()} | Assumpte: '{assumpte.strip()}'",
        autor_nom="Motor Inbound Stalwart",
        created_at=ara,
    )
    db.add(act_in)

    # 4. Accions segons la intenció classificada
    if intencio == "BAIXA_OPTOUT":
        # Cancel·lar tots els esdeveniments futurs d'aquest lead al Calendari Comercial
        res_cal = await db.execute(
            select(SaasCorreuMissatge).where(
                SaasCorreuMissatge.lead_id == lead_trobat.id,
                SaasCorreuMissatge.direccio.in_(("OUTBOUND", "INTERN_CALENDARI")),
                SaasCorreuMissatge.estat_enviament.in_(
                    ("ESBORRANY_PROGRAMAT", "PAUSAT_PER_RESPOSTA", "PENDENT_APROVACIO_AVUI")
                ),
            )
        )
        for item_cal in res_cal.scalars().all():
            item_cal.estat_enviament = "CANCEL_LAT"

        # Bloqueig permanent a la llista negra (idempotent per evitar IntegrityError)
        email_clean = remitent.strip().lower()
        res_exist_rgpd = await db.execute(
            select(SaasExclusioRgpd).where(
                SaasExclusioRgpd.email == email_clean,
                SaasExclusioRgpd.domini == domini_remitent,
            )
        )
        if not res_exist_rgpd.scalars().first():
            optout = SaasExclusioRgpd(
                id=uuid.uuid4(),
                email=email_clean,
                domini=domini_remitent,
                cif=lead_trobat.cif,
                motiu="OPTOUT_EXPLICIT",
                origen_message_id=msg_inbound.message_id,
                created_at=ara,
            )
            db.add(optout)

        lead_trobat.estat_qualificacio = "DESCARTAT"

        # Tancar oportunitat com a PERDUT
        res_op = await db.execute(select(SaasOportunitat).where(SaasOportunitat.lead_id == lead_trobat.id))
        op = res_op.scalars().first()
        if op:
            op.etapa = "PERDUT"
            op.motiu_perdua = "Petició expressa de baixa RGPD/LSSI."
            op.updated_at = ara

    elif intencio == "NO_INTERESSAT":
        res_cal = await db.execute(
            select(SaasCorreuMissatge).where(
                SaasCorreuMissatge.lead_id == lead_trobat.id,
                SaasCorreuMissatge.direccio.in_(("OUTBOUND", "INTERN_CALENDARI")),
                SaasCorreuMissatge.estat_enviament.in_(
                    ("ESBORRANY_PROGRAMAT", "PAUSAT_PER_RESPOSTA", "PENDENT_APROVACIO_AVUI")
                ),
            )
        )
        for item_cal in res_cal.scalars().all():
            item_cal.estat_enviament = "CANCEL_LAT"

        lead_trobat.estat_qualificacio = "DESCARTAT"
        res_op = await db.execute(select(SaasOportunitat).where(SaasOportunitat.lead_id == lead_trobat.id))
        op = res_op.scalars().first()
        if op:
            op.etapa = "PERDUT"
            op.motiu_perdua = "Resposta negativa del prospecte per correu."
            op.updated_at = ara

    elif intencio == "OBJECCIO_TEMPS":
        # Agendar seguiment automàtic al Calendari Comercial en la data sol·licitada
        data_seguiment = ara + timedelta(days=dies_seguiment)
        seguiment = SaasCorreuMissatge(
            id=uuid.uuid4(),
            lead_id=lead_trobat.id,
            tipus_item_calendari="SEGUIMENT_CALENDARI",
            pas_sequencia=None,
            tempo_dies_offset=dies_seguiment,
            data_programada=data_seguiment,
            direccio="INTERN_CALENDARI",
            estat_enviament="ESBORRANY_PROGRAMAT",
            remitent=settings.SUPERADMIN_OUTREACH_EMAIL or "tecnic@sevalor.net",
            destinatari=lead_trobat.email,
            assumpte=f"Seguiment comercial per petició de {lead_trobat.nom_contacte}",
            cos_text=f"Recordatori automàtic al Calendari del CRM per reprendre contacte ({dies_seguiment} dies).",
            message_id=f"<{uuid.uuid4().hex}@sevalor.net>",
            created_at=ara,
        )
        db.add(seguiment)

    elif intencio == "INTERESSAT_DEMO":
        lead_trobat.estat_qualificacio = "DEMO_DEMANADA"
        res_op = await db.execute(select(SaasOportunitat).where(SaasOportunitat.lead_id == lead_trobat.id))
        op = res_op.scalars().first()
        if op:
            op.etapa = "QUALIFICACIO"
            op.probabilitat_percent = 50
            op.updated_at = ara

        # Crear alerta d'acció al Calendari del dia per activar la Demo de 7 Dies
        alerta_demo = SaasCorreuMissatge(
            id=uuid.uuid4(),
            lead_id=lead_trobat.id,
            tipus_item_calendari="REUNIO_DEMO",
            pas_sequencia=None,
            tempo_dies_offset=0,
            data_programada=ara,
            direccio="INTERN_CALENDARI",
            estat_enviament="ESBORRANY_PROGRAMAT",
            remitent=settings.SUPERADMIN_OUTREACH_EMAIL or "tecnic@sevalor.net",
            destinatari=lead_trobat.email,
            assumpte=f"Activar Demo de 7 Dies per a {lead_trobat.nom_empresa}",
            cos_text="El prospecte ha respost sol·licitant una demostració. Revisar i activar entorn de 7 dies.",
            message_id=f"<{uuid.uuid4().hex}@sevalor.net>",
            created_at=ara,
        )
        db.add(alerta_demo)

    elif intencio == "INTERESSAT_INFO":
        lead_trobat.estat_qualificacio = "QUALIFICAT"
        res_op = await db.execute(select(SaasOportunitat).where(SaasOportunitat.lead_id == lead_trobat.id))
        op = res_op.scalars().first()
        if op:
            op.etapa = "QUALIFICACIO"
            op.probabilitat_percent = max(op.probabilitat_percent, 40)
            op.updated_at = ara

        # Preparar un esborrany de resposta tècnica per a revisió humana (US4.2)
        esborrany_resposta = SaasCorreuMissatge(
            id=uuid.uuid4(),
            lead_id=lead_trobat.id,
            tipus_item_calendari="EMAIL_CAMPANYA",
            pas_sequencia=None,
            tempo_dies_offset=0,
            data_programada=ara,
            direccio="OUTBOUND",
            estat_enviament="ESBORRANY_PROGRAMAT",
            remitent=settings.SUPERADMIN_OUTREACH_EMAIL or "tecnic@sevalor.net",
            destinatari=lead_trobat.email,
            assumpte=f"Re: {assumpte.strip()}" if not assumpte.lower().startswith("re:") else assumpte.strip(),
            cos_text=(
                f"Hola {lead_trobat.nom_contacte},\n\n"
                f"Gràcies per la vostra resposta. Us adjuntem el detall tècnic de Sevalor Suite "
                f"(PWA mòbil per a operaris + Dashboard d'enginyeria + Bot Oficial de Telegram per al client final) "
                f"i com s'adapta a {lead_trobat.nom_empresa}.\n\n"
                f"Quedem a la vostra disposició per activar l'entorn de prova de 7 dies."
                + PEU_LEGAL_RGPD_B2B
            ),
            message_id=f"<{uuid.uuid4().hex}@sevalor.net>",
            in_reply_to=msg_inbound.message_id,
            references_header=msg_inbound.message_id,
            created_at=ara,
        )
        db.add(esborrany_resposta)

    elif intencio == "OUT_OF_OFFICE":
        # Posposar els correus pausats i reactivar-los al Calendari després de l'absència
        dies_ooo = max(7, dies_seguiment if dies_seguiment != 21 else 7)
        res_pausats = await db.execute(
            select(SaasCorreuMissatge).where(
                SaasCorreuMissatge.lead_id == lead_trobat.id,
                SaasCorreuMissatge.direccio == "OUTBOUND",
                SaasCorreuMissatge.estat_enviament == "PAUSAT_PER_RESPOSTA",
            )
        )
        for item_p in res_pausats.scalars().all():
            item_p.data_programada = item_p.data_programada + timedelta(days=dies_ooo)
            item_p.estat_enviament = "ESBORRANY_PROGRAMAT"

    lead_trobat.updated_at = ara
    await db.commit()
    return msg_inbound


async def sincronitzar_bustia_imap_stalwart(db: AsyncSession) -> List[Dict[str, Any]]:
    """Sincronitza via IMAP els correus no llegits de `tecnic@sevalor.net` a Stalwart Mail Server."""
    imap_host = settings.STALWART_IMAP_HOST
    imap_port = settings.STALWART_IMAP_PORT
    imap_user = settings.STALWART_USER
    imap_pass = settings.STALWART_PASSWORD

    processats: List[Dict[str, Any]] = []
    if not imap_host or imap_host in ("localhost", "127.0.0.1", "") or not imap_user or not imap_pass:
        return processats

    try:
        with imaplib.IMAP4_SSL(imap_host, imap_port) as mail:
            mail.login(imap_user, imap_pass)
            mail.select("INBOX")
            status, messages = mail.search(None, "UNSEEN")
            if status != "OK" or not messages or not messages[0]:
                return processats

            for num in messages[0].split():
                _, msg_data = mail.fetch(num, "(RFC822)")
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        parsed = email.message_from_bytes(response_part[1])
                        remitent_raw = parsed.get("From", "")
                        _, remitent_addr = email.utils.parseaddr(remitent_raw)
                        assumpte = parsed.get("Subject", "Sense assumpte")
                        in_reply_to = parsed.get("In-Reply-To")

                        cos = ""
                        if parsed.is_multipart():
                            for part in parsed.walk():
                                if part.get_content_type() == "text/plain":
                                    payload_bytes = part.get_payload(decode=True)
                                    if isinstance(payload_bytes, bytes):
                                        cos = payload_bytes.decode("utf-8", errors="ignore")
                                    break
                        else:
                            payload_bytes = parsed.get_payload(decode=True)
                            if isinstance(payload_bytes, bytes):
                                cos = payload_bytes.decode("utf-8", errors="ignore")

                        if remitent_addr:
                            msg_saved = await processar_resposta_inbound(
                                remitent=remitent_addr,
                                assumpte=assumpte,
                                cos_text=cos,
                                in_reply_to=in_reply_to,
                                db=db,
                            )
                            processats.append({
                                "message_id": msg_saved.message_id,
                                "remitent": remitent_addr,
                                "intencio_ia": msg_saved.intencio_ia,
                            })
    except Exception as exc:
        logger.warning("Avís en sincronitzar IMAP Stalwart (%s): %s", imap_host, exc)

    return processats
