"""Suite de tests d'integració per a la Fase 6 (Tasca T017) del CRM de Superadmin.

Cobreix tots els 8 escenaris de prospecció i outreach B2B establerts a tasks.md:
1. test_execucio_atomica_cp_vertical_lliure_i_cerca_multicanal
2. test_deduplicacio_multivalidacio_3_vectors
3. test_corregir_criteri_exigeix_justificacio_humana_obligatoria
4. test_aprenentatge_tancament_exit_guanyat_replicable
5. test_campanya_3_emails_tempo_i_calendari_comercial
6. test_enviament_hitl_i_pausa_automatica_sequencia_en_respondre
7. test_inbound_objeccio_temps_agenda_al_calendari_i_optout_rgpd
8. test_zero_trust_rbac_prospeccio_i_calendari

Normativa estricta (Auditoria_i_Normativa_Tests_Backend.md):
- PostgreSQL 16 real amb Savepoint isolation (create_savepoint)
- Zero mocks de base de dades
- Absència total de db.refresh()
- Zero warnings d'event loop asíncron
- Zero mencions a WhatsApp (només PWA i Bot Oficial de Telegram)
"""

import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.main import app
from app.models.models import (
    Empresa,
    SaasCorreuMissatge,
    SaasCriteriFeedback,
    SaasExclusioRgpd,
    SaasLead,
    SaasOportunitat,
    SaasProspeccioCandidat,
    SaasProspeccioTasca,
)
from app.services.firecrawl_service import (
    normalitzar_adreca,
    verificar_duplicitat_multivector,
)
from app.services.openrouter_prospecting_service import (
    LeadEvaluationSchema,
    carregar_context_doble_bucle,
    qualificar_candidat_amb_openrouter,
)
from app.services.stalwart_mail_service import (
    programar_campanya_3_emails,
)


@pytest.fixture
def superadmin_headers() -> dict[str, str]:
    payload = {
        "sub": "00000000-0000-0000-0000-000000000000",
        "rol": "SUPERADMIN",
        "empresa_id": None,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
        "totp_activat": True,
        "ip_allowlist": ["testclient", "127.0.0.1", "localhost", "*"],
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def boss_headers() -> dict[str, str]:
    empresa_id = str(uuid.uuid4())
    payload = {
        "sub": str(uuid.uuid4()),
        "rol": "BOSS",
        "empresa_id": empresa_id,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def gestor_headers() -> dict[str, str]:
    empresa_id = str(uuid.uuid4())
    payload = {
        "sub": str(uuid.uuid4()),
        "rol": "GESTOR",
        "empresa_id": empresa_id,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def operari_headers() -> dict[str, str]:
    empresa_id = str(uuid.uuid4())
    payload = {
        "sub": str(uuid.uuid4()),
        "rol": "OPERARI",
        "empresa_id": empresa_id,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return {"Authorization": f"Bearer {token}"}


# ==============================================================================
# 1. TEST EXECUCIÓ ATÒMICA CP, VERTICAL LLIURE I CERCA MULTI-CANAL
# ==============================================================================

@pytest.mark.asyncio
async def test_execucio_atomica_cp_vertical_lliure_i_cerca_multicanal(
    superadmin_headers: dict[str, str],
    db_session: AsyncSession,
):
    """Verifica que l'operador pot enviar qualsevol nom de vertical escrit lliurement,

    registra candidats seleccionats i descartats amb fonts multi-canal (web, linkedin, instagram)
    i finalitza el CP 25001 sense encadenar el 25002 (FR-001, FR-002, FR-003).
    """
    vertical_lliure = "Manteniment de climatització industrial i fred comercial"
    cp_test = "25001"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Llançar cerca atòmica per CP
        crear_res = await ac.post(
            "/api/v1/superadmin/crm/prospeccio/tasques-cp",
            json={
                "codi_postal": cp_test,
                "vertical": vertical_lliure,
                "operaris_minims": 6,
            },
            headers=superadmin_headers,
        )
        assert crear_res.status_code == 201, crear_res.text
        tasca_data = crear_res.json()
        assert "tasca_id" in tasca_data
        tasca_id = tasca_data["tasca_id"]
        assert tasca_data["codi_postal"] == cp_test
        assert tasca_data["vertical"] == vertical_lliure
        assert tasca_data["total_trobats"] >= 1

        # 2. Consultar el detall de la tasca i els seus candidats
        detall_res = await ac.get(
            f"/api/v1/superadmin/crm/prospeccio/tasques-cp/{tasca_id}",
            headers=superadmin_headers,
        )
        assert detall_res.status_code == 200
        detall = detall_res.json()
        assert detall["id"] == tasca_id
        assert detall["estat"] in ("COMPLETAT", "PENDENT", "EXECUTANT")
        assert "candidats" in detall
        assert len(detall["candidats"]) > 0

        # Verificar presència de fonts multi-canal als candidats
        for cand in detall["candidats"]:
            fonts = cand.get("fonts_investigades") or ""
            assert any(f in fonts for f in ("web", "linkedin", "instagram"))

        # 3. Verificar que NO s'ha encadenat automàticament el CP 25002 (FR-003 Atòmic)
        tasques_res = await ac.get(
            "/api/v1/superadmin/crm/prospeccio/tasques-cp",
            headers=superadmin_headers,
        )
        assert tasques_res.status_code == 200
        tasques = tasques_res.json()
        assert not any(t.get("codi_postal") == "25002" and t.get("vertical") == vertical_lliure for t in tasques)

        # 4. Comprovar streaming SSE
        stream_res = await ac.get(
            f"/api/v1/superadmin/crm/prospeccio/tasques-cp/{tasca_id}/stream",
            headers=superadmin_headers,
        )
        assert stream_res.status_code == 200
        assert "text/event-stream" in stream_res.headers.get("content-type", "")


# ==============================================================================
# 2. TEST DEDUPLICACIÓ MULTI-VALIDACIÓ 3 VECTORS
# ==============================================================================

@pytest.mark.asyncio
async def test_deduplicacio_multivalidacio_3_vectors(db_session: AsyncSession):
    """Verifica la deduplicació per 3 vectors (CIF, Domini Web, Adreça Física) i

    contra clients existents i llista d'exclusió RGPD (FR-004).
    """
    suffix = uuid.uuid4().hex[:8]
    now = datetime.now(timezone.utc)

    # 1. Vector 1: Deduplicació per CIF
    cif_test = f"B{suffix.upper()[:8]}"
    lead1 = SaasLead(
        id=uuid.uuid4(),
        nom_empresa=f"Clima Central {suffix} SL",
        nom_contacte="Marta Gil",
        email=f"marta_{suffix}@climacentral.cat",
        cif=cif_test,
        vertical="ElectricPro",
        created_at=now,
        updated_at=now,
    )
    db_session.add(lead1)
    await db_session.flush()

    dup_cif, vec_cif, _ = await verificar_duplicitat_multivector(
        db=db_session,
        cif=cif_test,
        domini=f"https://diferent-{suffix}.cat",
        adreca=f"Adreça Nova {suffix}",
    )
    assert dup_cif is True
    assert vec_cif == "CIF"

    # 2. Vector 2: Deduplicació per Domini Web (fins i tot sense CIF)
    domini_test = f"instal-fred-{suffix}.cat"
    lead2 = SaasLead(
        id=uuid.uuid4(),
        nom_empresa=f"Instal Fred {suffix} SL",
        nom_contacte="Marc Vila",
        email=f"info@{domini_test}",
        domini_normalitzat=domini_test,
        vertical="HydroPro",
        created_at=now,
        updated_at=now,
    )
    db_session.add(lead2)
    await db_session.flush()

    dup_dom, vec_dom, _ = await verificar_duplicitat_multivector(
        db=db_session,
        cif=None,
        domini=f"http://www.{domini_test}/serveis?lang=ca",
        adreca=f"Polígon {suffix}",
    )
    assert dup_dom is True
    assert vec_dom == "DOMINI_WEB"

    # 3. Vector 3: Deduplicació per Adreça Física Canònica (sense CIF ni Domini)
    adreca_base = f"Polígon Industrial El Segre, Nau 5, {suffix}"
    lead3 = SaasLead(
        id=uuid.uuid4(),
        nom_empresa=f"Construccions {suffix} SL",
        nom_contacte="Pau Soler",
        email=f"pau_{suffix}@obres.cat",
        adreca_fisica=adreca_base,
        adreca_normalitzada=normalitzar_adreca(adreca_base),
        vertical="BuildingPro",
        created_at=now,
        updated_at=now,
    )
    db_session.add(lead3)
    await db_session.flush()

    dup_adr, vec_adr, _ = await verificar_duplicitat_multivector(
        db=db_session,
        cif=None,
        domini=None,
        adreca=f"Pol. Ind. El Segre, Nau 5, {suffix}",
    )
    assert dup_adr is True
    assert vec_adr == "ADRECA_FISICA"

    # 4. Exclusió RGPD (Llista Negra)
    domini_optout = f"optout-{suffix}.com"
    optout = SaasExclusioRgpd(
        id=uuid.uuid4(),
        domini=domini_optout,
        email=f"baja@{domini_optout}",
        motiu="SOL_LICITUD_WEB",
        created_at=now,
    )
    db_session.add(optout)
    await db_session.flush()

    dup_rgpd, vec_rgpd, _ = await verificar_duplicitat_multivector(
        db=db_session,
        domini=f"https://www.{domini_optout}",
    )
    assert dup_rgpd is True
    assert vec_rgpd == "DOMINI_WEB"

    # 5. Client Existent de Sevalor Suite (Taula empreses)
    empresa_client = Empresa(
        id=uuid.uuid4(),
        nom=f"Empresa Client {suffix} SL",
        nif=f"A{suffix.upper()[:8]}",
        subdomini=f"cli{suffix[:6]}",
        domini_custom=f"client-{suffix}.sevalor.com",
        created_at=now,
        updated_at=now,
    )
    db_session.add(empresa_client)
    await db_session.flush()

    dup_cli, vec_cli, _ = await verificar_duplicitat_multivector(
        db=db_session,
        cif=empresa_client.nif,
    )
    assert dup_cli is True
    assert vec_cli == "CIF"


# ==============================================================================
# 3. TEST CORREGIR CRITERI EXIGEIX JUSTIFICACIÓ HUMANA OBLIGATÒRIA
# ==============================================================================

@pytest.mark.asyncio
async def test_corregir_criteri_exigeix_justificacio_humana_obligatoria(
    superadmin_headers: dict[str, str],
    db_session: AsyncSession,
):
    """Verifica que corregir o descartar un candidat exigeix justificació humana obligatòria

    (>= 10 caràcters) i que es registra a saas_criteris_feedback com a Bucle 1 (FR-006, FR-007).
    """
    now = datetime.now(timezone.utc)
    suffix = uuid.uuid4().hex[:8]

    tasca = SaasProspeccioTasca(
        id=uuid.uuid4(),
        codi_postal="08001",
        vertical="ElectricPro",
        estat="COMPLETAT",
        created_at=now,
    )
    db_session.add(tasca)
    await db_session.flush()

    cand = SaasProspeccioCandidat(
        id=uuid.uuid4(),
        tasca_id=tasca.id,
        nom_empresa=f"Electro {suffix} SL",
        web_url="https://electro.cat",
        domini_normalitzat=f"electro-{suffix}.cat",
        codi_postal="08001",
        vertical="ElectricPro",
        score=82,
        estat_decisio="SELECCIONAT",
        motiu_detallat_ia="Empresa d'instal·lacions elèctriques amb quadrilla",
        created_at=now,
        updated_at=now,
    )
    db_session.add(cand)
    await db_session.flush()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Intent sense justificació o massa curta (< 10 caràcters) -> 400 o 422
        bad_res = await ac.post(
            f"/api/v1/superadmin/crm/prospeccio/candidats/{cand.id}/corregir-criteri",
            json={
                "nova_decisio": "DESCARTAT",
                "motiu_correccio_humana": "Curt",
            },
            headers=superadmin_headers,
        )
        assert bad_res.status_code in (400, 422), "Ha de rebutjar justificacions inferiors a 10 caràcters"

        # 2. Correcció correcta amb justificació humana >= 10 caràcters -> 200
        justificacio = "És una botiga de venda de bombetes i petits electrodomèstics, no fan instal·lacions industrials al carrer."
        ok_res = await ac.post(
            f"/api/v1/superadmin/crm/prospeccio/candidats/{cand.id}/corregir-criteri",
            json={
                "nova_decisio": "DESCARTAT",
                "motiu_correccio_humana": justificacio,
            },
            headers=superadmin_headers,
        )
        assert ok_res.status_code == 200, ok_res.text
        cand_data = ok_res.json()
        assert cand_data["nova_decisio"] == "DESCARTAT"

        # 3. Comprovar que s'ha desat a saas_criteris_feedback per al Bucle 1
        fb_stmt = select(SaasCriteriFeedback).where(
            SaasCriteriFeedback.tipus_aprenentatge == "CORRECCIO_DESCART",
            SaasCriteriFeedback.candidat_id == cand.id,
        )
        fb_res = await db_session.execute(fb_stmt)
        fb_entry = fb_res.scalar_one_or_none()
        assert fb_entry is not None
        assert fb_entry.explicacio_humana_o_rao_exit == justificacio


# ==============================================================================
# 4. TEST APRENENTATGE TANCAMENT D'ÈXIT GUANYAT REPLICABLE
# ==============================================================================

@pytest.mark.asyncio
async def test_aprenentatge_tancament_exit_guanyat_replicable(
    superadmin_headers: dict[str, str],
    db_session: AsyncSession,
):
    """Verifica que en tancar una oportunitat com a GUANYAT indicant rao_tancament_exit

    i es_replicable = True, es crea el patró TANCAMENT_EXIT_REPLICABLE i s'inclou al
    context d'aprenentatge per trobar empreses bessones (lookalikes >= 85) (FR-008, FR-009).
    """
    now = datetime.now(timezone.utc)
    suffix = uuid.uuid4().hex[:8]

    lead = SaasLead(
        id=uuid.uuid4(),
        nom_empresa=f"Regs del Sud {suffix} SL",
        nom_contacte="Jordi Pons",
        email=f"jordi_{suffix}@regsdelsud.cat",
        vertical="CampoPro",
        created_at=now,
        updated_at=now,
    )
    db_session.add(lead)
    await db_session.flush()

    op = SaasOportunitat(
        id=uuid.uuid4(),
        lead_id=lead.id,
        titol=f"Implantació CampoPro a {lead.nom_empresa}",
        etapa="PROPOSTA",
        valor_mensual_estimat=350.0,
        probabilitat_percent=80,
        created_at=now,
        updated_at=now,
    )
    db_session.add(op)
    await db_session.flush()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        rao_exit = "El Bot de Telegram permet als operaris reportar avaries d'aspersors sense connexió i signar albarans digitals."
        requisits = "Empreses instal·ladores de reg agrícola amb més de 10 operaris i vehicles de flota."

        res = await ac.post(
            f"/api/v1/superadmin/crm/prospeccio/oportunitats/{op.id}/registrar-exit",
            json={
                "rao_tancament_exit": rao_exit,
                "requisits_replicables": requisits,
                "es_replicable": True,
            },
            headers=superadmin_headers,
        )
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["etapa"] == "GUANYAT"
        assert data["es_replicable"] is True
        assert data["rao_tancament_exit"] == rao_exit

        # Comprovar extracció pel Doble Bucle d'Aprenentatge
        ctx = await carregar_context_doble_bucle("CampoPro", db_session)
        assert len(ctx["casos_exit_replicables"]) >= 1
        assert any("Bot de Telegram" in c["rao_tancament_exit"] for c in ctx["casos_exit_replicables"])


# ==============================================================================
# 5. TEST CAMPANYA DE 3 EMAILS AMB TEMPO I CALENDARI COMERCIAL
# ==============================================================================

@pytest.mark.asyncio
async def test_campanya_3_emails_tempo_i_calendari_comercial(
    superadmin_headers: dict[str, str],
    db_session: AsyncSession,
):
    """Verifica que en qualificar un lead es generen els 3 correus de la campanya

    amb el seu tempo (Dia 0, Dia +4, Dia +8) sense mencions a WhatsApp (utilitzant PWA + Telegram)
    i que apareixen consultables a l'endpoint /calendari (FR-010, FR-011, FR-012, FR-013, FR-014).
    """
    now = datetime.now(timezone.utc)
    suffix = uuid.uuid4().hex[:8]
    email_lead = f"carles_{suffix}@montatges.cat"

    lead = SaasLead(
        id=uuid.uuid4(),
        nom_empresa=f"Muntatges Tècnics {suffix} SL",
        nom_contacte="Carles Vidal",
        email=email_lead,
        vertical="ElectricPro",
        punt_dolor_detectat="Temps excessiu en confeccionar certificats de baixa tensió",
        fita_recent="Nova concessió de parcs solars al Pla d'Urgell",
        created_at=now,
        updated_at=now,
    )
    db_session.add(lead)
    await db_session.flush()

    # 1. Qualificar i generar campanya de 3 correus mitjançant qualificar_candidat_amb_openrouter
    eval_lead = await qualificar_candidat_amb_openrouter(
        nom_empresa=lead.nom_empresa,
        web_url="https://montatgestecnics.cat",
        codi_postal="25001",
        vertical="ElectricPro",
        operaris_minims=5,
        web_markdown="Empresa instal·ladora de baixa tensió amb equip mòbil.",
        fonts_investigades=["web", "linkedin"],
        fita_recent=lead.fita_recent,
        gatekeeper_hints={"carrec": "Gerent", "context": lead.nom_contacte},
        db=db_session,
    )
    assert isinstance(eval_lead, LeadEvaluationSchema)
    emails = eval_lead.campanya_3_emails
    assert len(emails) == 3

    # PROHIBICIÓ ESTRICTA: Absència total de la paraula WhatsApp
    for e in emails:
        assert "whatsapp" not in e.assumpte.lower(), "PROHIBIT esmentar WhatsApp a l'assumpte!"
        assert "whatsapp" not in e.cos_text.lower(), "PROHIBIT esmentar WhatsApp al cos del correu!"
        text_combinat = (e.assumpte + " " + e.cos_text).lower()
        assert "pwa" in text_combinat or "telegram" in text_combinat or "sevalor" in text_combinat

    # 2. Programar els 3 esborranys al Calendari Comercial
    correus_db = await programar_campanya_3_emails(
        lead_id=lead.id,
        campanya=emails,
        db=db_session,
    )
    assert len(correus_db) == 3
    assert correus_db[0].tempo_dies_offset == 0
    assert correus_db[1].tempo_dies_offset == 4
    assert correus_db[2].tempo_dies_offset == 8

    # 3. Consultar via API GET /calendari
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        cal_res = await ac.get(
            "/api/v1/superadmin/crm/prospeccio/calendari",
            headers=superadmin_headers,
        )
        assert cal_res.status_code == 200
        cal_data = cal_res.json()
        ids_programats = {c["id"] for c in cal_data["items"]}
        for c in correus_db:
            assert str(c.id) in ids_programats


# ==============================================================================
# 6. TEST ENVIAMENT HITL I PAUSA AUTOMÀTICA DE SEQÜÈNCIA EN RESPONDRE
# ==============================================================================

@pytest.mark.asyncio
async def test_enviament_hitl_i_pausa_automatica_sequencia_en_respondre(
    superadmin_headers: dict[str, str],
    db_session: AsyncSession,
):
    """Verifica que l'Email 1 s'envia només amb aprovació humana (Message-ID RFC 5322)

    i que quan entra una resposta INBOUND (In-Reply-To), els següents correus (D+4, D+8)
    passen automàticament a PAUSAT_PER_RESPOSTA (FR-015, FR-016).
    """
    now = datetime.now(timezone.utc)
    suffix = uuid.uuid4().hex[:8]
    email_lead = f"gerent_{suffix}@climalleida.cat"

    lead = SaasLead(
        id=uuid.uuid4(),
        nom_empresa=f"Clima Lleida {suffix} SL",
        nom_contacte="Sergi Puig",
        email=email_lead,
        vertical="HydroPro",
        created_at=now,
        updated_at=now,
    )
    db_session.add(lead)
    await db_session.flush()

    c1 = SaasCorreuMissatge(
        id=uuid.uuid4(),
        lead_id=lead.id,
        tipus_item_calendari="EMAIL_CAMPANYA",
        pas_sequencia=1,
        tempo_dies_offset=0,
        data_programada=now,
        direccio="OUTBOUND",
        estat_enviament="ESBORRANY_PROGRAMAT",
        remitent="tecnic@sevalor.net",
        destinatari=email_lead,
        assumpte="Optimització d'ordres de treball per a Clima Lleida",
        cos_text="Hola Sergi, us presentem la solució Sevalor...",
        message_id=f"<{uuid.uuid4().hex}@sevalor.net>",
        created_at=now,
    )
    c2 = SaasCorreuMissatge(
        id=uuid.uuid4(),
        lead_id=lead.id,
        tipus_item_calendari="EMAIL_CAMPANYA",
        pas_sequencia=2,
        tempo_dies_offset=4,
        data_programada=now + timedelta(days=4),
        direccio="OUTBOUND",
        estat_enviament="ESBORRANY_PROGRAMAT",
        remitent="tecnic@sevalor.net",
        destinatari=email_lead,
        assumpte="Cas d'èxit del sector",
        cos_text="Hola Sergi, mira com altres empreses...",
        message_id=f"<{uuid.uuid4().hex}@sevalor.net>",
        created_at=now,
    )
    db_session.add_all([c1, c2])
    await db_session.flush()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Enviament HITL de l'Email 1 per part de Superadmin
        send_res = await ac.post(
            f"/api/v1/superadmin/crm/prospeccio/correus/{c1.id}/enviar",
            headers=superadmin_headers,
        )
        assert send_res.status_code == 200, send_res.text
        data_c1 = send_res.json()
        assert data_c1["estat_enviament"] == "APROVAT_ENVIAT"

        # Comprovar Message-ID al fil del lead
        thread_res = await ac.get(
            f"/api/v1/superadmin/crm/prospeccio/leads/{lead.id}/correus",
            headers=superadmin_headers,
        )
        assert thread_res.status_code == 200
        msgs = thread_res.json()
        assert any("@sevalor.net" in m.get("message_id", "") for m in msgs)

        # 2. Arriba una resposta INBOUND del client
        inbound_res = await ac.post(
            "/api/v1/superadmin/crm/prospeccio/correu/sincronitzar-inbound",
            json={
                "remitent": email_lead,
                "assumpte": "Re: Optimització d'ordres de treball",
                "cos_text": "Hola, ens podria interessar veure una demo del Bot de Telegram.",
            },
            headers=superadmin_headers,
        )
        assert inbound_res.status_code == 200
        assert inbound_res.json()["intencio_ia"] == "INTERESSAT_DEMO"

        # 3. Comprovar que l'Email 2 al Calendari ha passat a PAUSAT_PER_RESPOSTA
        stmt_c2 = select(SaasCorreuMissatge).where(SaasCorreuMissatge.id == c2.id)
        res_c2 = await db_session.execute(stmt_c2)
        c2_saved = res_c2.scalar_one()
        assert c2_saved.estat_enviament == "PAUSAT_PER_RESPOSTA"


# ==============================================================================
# 7. TEST INBOUND OBJECCIÓ DE TEMPS I OPTOUT RGPD
# ==============================================================================

@pytest.mark.asyncio
async def test_inbound_objeccio_temps_agenda_al_calendari_i_optout_rgpd(
    superadmin_headers: dict[str, str],
    db_session: AsyncSession,
):
    """Verifica el tractament Inbound automàtic:

    - OBJECCIO_TEMPS: Agenda esdeveniment de seguiment futur al Calendari Comercial.
    - BAIXA_OPTOUT: Registra a saas_exclusio_rgpd, cancel·la el calendari i mou el lead a DESCARTAT.
    """
    now = datetime.now(timezone.utc)
    suffix = uuid.uuid4().hex[:8]

    # --- Fixtures Cas A: Objecció de Temps ---
    email_temps = f"gerencia_{suffix}@empresa-temps.cat"
    lead_temps = SaasLead(
        id=uuid.uuid4(),
        nom_empresa=f"Empresa Temps {suffix} SL",
        nom_contacte="Laia Solà",
        email=email_temps,
        vertical="ElectricPro",
        created_at=now,
        updated_at=now,
    )

    # --- Fixtures Cas B: Baixa Opt-out RGPD ---
    email_optout = f"contacte_{suffix}@empresa-optout.cat"
    lead_optout = SaasLead(
        id=uuid.uuid4(),
        nom_empresa=f"Empresa Optout {suffix} SL",
        nom_contacte="Joan Font",
        email=email_optout,
        vertical="CampoPro",
        created_at=now,
        updated_at=now,
    )
    db_session.add(lead_temps)
    db_session.add(lead_optout)
    await db_session.flush()

    correu_pendent = SaasCorreuMissatge(
        id=uuid.uuid4(),
        lead_id=lead_optout.id,
        tipus_item_calendari="EMAIL_CAMPANYA",
        pas_sequencia=2,
        tempo_dies_offset=4,
        data_programada=now + timedelta(days=4),
        direccio="OUTBOUND",
        estat_enviament="ESBORRANY_PROGRAMAT",
        remitent="tecnic@sevalor.net",
        destinatari=email_optout,
        assumpte="Seguiment",
        cos_text="Hola Joan...",
        message_id=f"<{uuid.uuid4().hex}@sevalor.net>",
        created_at=now,
    )
    db_session.add(correu_pendent)
    await db_session.flush()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Cas A: Processar Objecció de Temps
        res_temps = await ac.post(
            "/api/v1/superadmin/crm/prospeccio/correu/sincronitzar-inbound",
            json={
                "remitent": email_temps,
                "assumpte": "Re: Proposta",
                "cos_text": "Ara mateix estem saturats, truqueu-nos d'aquí a 3 setmanes si us plau.",
            },
            headers=superadmin_headers,
        )
        assert res_temps.status_code == 200
        assert res_temps.json()["intencio_ia"] == "OBJECCIO_TEMPS"

        # Verificar esdeveniment creat al calendari
        stmt_ev = select(SaasCorreuMissatge).where(
            SaasCorreuMissatge.lead_id == lead_temps.id,
            SaasCorreuMissatge.tipus_item_calendari == "SEGUIMENT_CALENDARI",
        )
        ev_res = await db_session.execute(stmt_ev)
        esdeveniment = ev_res.scalar_one_or_none()
        assert esdeveniment is not None
        assert esdeveniment.data_programada > now

        # 2. Cas B: Processar Baixa Opt-out RGPD
        res_optout = await ac.post(
            "/api/v1/superadmin/crm/prospeccio/correu/sincronitzar-inbound",
            json={
                "remitent": email_optout,
                "assumpte": "Re: Proposta",
                "cos_text": "No ens interessa. Si us plau, doneu-nos de baixa de la base de dades (baixa).",
            },
            headers=superadmin_headers,
        )
        assert res_optout.status_code == 200
        assert res_optout.json()["intencio_ia"] == "BAIXA_OPTOUT"

        # Verificar registre a saas_exclusio_rgpd
        stmt_excl = select(SaasExclusioRgpd).where(SaasExclusioRgpd.email == email_optout)
        excl_res = await db_session.execute(stmt_excl)
        excl_saved = excl_res.scalar_one_or_none()
        assert excl_saved is not None

        # Verificar que el lead ha passat a DESCARTAT
        stmt_lead_op = select(SaasLead).where(SaasLead.id == lead_optout.id)
        lead_saved = (await db_session.execute(stmt_lead_op)).scalar_one()
        assert lead_saved.estat_qualificacio == "DESCARTAT"

        # Verificar cancel·lació dels correus pendents de la campanya
        stmt_m = select(SaasCorreuMissatge).where(SaasCorreuMissatge.id == correu_pendent.id)
        m_saved = (await db_session.execute(stmt_m)).scalar_one()
        assert m_saved.estat_enviament == "CANCEL_LAT"


# ==============================================================================
# 8. TEST ZERO TRUST RBAC: PROSPECCIÓ I CALENDARI PROTEGITS
# ==============================================================================

@pytest.mark.asyncio
async def test_zero_trust_rbac_prospeccio_i_calendari(
    boss_headers: dict[str, str],
    gestor_headers: dict[str, str],
    operari_headers: dict[str, str],
):
    """Verifica que qualsevol usuari amb rol BOSS, GESTOR o OPERARI rep 403 Forbidden

    en tots els endpoints del CRM de Prospecció, Calendari i RGPD.
    """
    roles_non_superadmin = [boss_headers, gestor_headers, operari_headers]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        for headers in roles_non_superadmin:
            r1 = await ac.get("/api/v1/superadmin/crm/prospeccio/tasques-cp", headers=headers)
            assert r1.status_code == 403

            r2 = await ac.post(
                "/api/v1/superadmin/crm/prospeccio/tasques-cp",
                json={"codi_postal": "25001", "vertical": "CampoPro"},
                headers=headers,
            )
            assert r2.status_code == 403

            r3 = await ac.get("/api/v1/superadmin/crm/prospeccio/calendari", headers=headers)
            assert r3.status_code == 403

            r4 = await ac.get("/api/v1/superadmin/crm/prospeccio/criteris-feedback", headers=headers)
            assert r4.status_code == 403

            r5 = await ac.get("/api/v1/superadmin/crm/prospeccio/exclusio-rgpd", headers=headers)
            assert r5.status_code == 403

            r6 = await ac.post(
                "/api/v1/superadmin/crm/prospeccio/exclusio-rgpd",
                json={"email": "test@test.cat", "domini": "test.cat", "motiu": "SOL_LICITUD_WEB"},
                headers=headers,
            )
            assert r6.status_code == 403
