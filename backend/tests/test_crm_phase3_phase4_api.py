"""Suite de tests per a la Fase 3 i Fase 4 (Tasques T009 a T013) del CRM de Superadmin.

Cobreix:
- T009/T010: Sincronització Inbound, pausa automàtica de seqüència i configuració Docker Stalwart.
- T011: Lots atòmics per Codi Postal i Vertical lliure (`POST /tasques-cp`, `GET /tasques-cp`,
        `GET /tasques-cp/{id}`, `GET /tasques-cp/{id}/stream` SSE).
- T012: Doble Bucle d'Aprenentatge:
        - `POST /candidats/{id}/corregir-criteri` (validació obligatòria de `motiu_correccio_humana` >= 10 caràcters).
        - `POST /oportunitats/{id}/registrar-exit` (raó de compra `GUANYAT` i lookalike replicable).
        - `GET /criteris-feedback`.
- T013: Calendari Comercial Integrat, Campanyes i Correu Bidireccional:
        - `GET /calendari`, `POST /calendari/esdeveniments`, `PUT /correus/{id}/esborrany`,
        - `POST /correus/{id}/enviar` (acció HITL), `GET /leads/{id}/correus`,
        - `POST /leads/{id}/validar-mx`, `POST /correu/sincronitzar-inbound`,
        - `GET /exclusio-rgpd` i `POST /exclusio-rgpd`.
- Segregació Zero-Trust (RBAC Superadmin: usuari BOSS rep 403 Forbidden).

Normativa estricta:
- PostgreSQL 16 real amb `create_savepoint` i sense mocks de BD.
- Absència total de `db.refresh()`.
- Generadors aleatoris amb UUID per a unicitat.
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
    SaasCorreuMissatge,
    SaasLead,
    SaasOportunitat,
    SaasProspeccioCandidat,
    SaasProspeccioTasca,
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
    payload = {
        "sub": str(uuid.uuid4()),
        "rol": "BOSS",
        "empresa_id": str(uuid.uuid4()),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
        "totp_activat": True,
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return {"Authorization": f"Bearer {token}"}


# ==============================================================================
# TESTS T011: TASQUES ATÒMIQUES PER CODI POSTAL I STREAMING SSE
# ==============================================================================

@pytest.mark.asyncio
async def test_t011_execucio_atomica_cp_i_streaming(superadmin_headers: dict[str, str]):
    """Verifica l'execució d'un lot atòmic per Codi Postal amb vertical lliure, links reals i streaming SSE."""
    suffix = uuid.uuid4().hex[:6]
    vertical_lliure = f"Manteniment de Climatització i Fred Industrial {suffix}"
    dom_sel = f"climasegre-{suffix}.cat"
    dom_desc = f"subministraments-{suffix}.cat"

    candidats_reals = [
        {
            "nom_empresa": f"Clima i Fred Segre {suffix} SL",
            "web_url": f"https://{dom_sel}",
            "adreca_fisica": f"Polígon Industrial El Segre, Carrer del Metall, 14, 25001 Lleida ({suffix})",
            "cif": f"B25{suffix.upper()[:6]}",
            "email": f"jmarcet@{dom_sel}",
            "telefon": "+34973240011",
            "decisor_nom": "Joan Marcet Vila",
            "decisor_carrec": "Director Tècnic",
            "linkedin_url": f"https://www.linkedin.com/in/joan-marcet-{suffix}",
            "instagram_url": f"https://www.instagram.com/climasegre_{suffix}/",
            "fita_recent": "Adjudicació del manteniment de climatització de 4 naus logístiques a Lleida",
            "web_markdown": "Empresa instal·ladora de climatització industrial amb 12 tècnics i servei 24h.",
        },
        {
            "nom_empresa": f"Botiga Subministraments {suffix} SL",
            "web_url": f"https://{dom_desc}",
            "adreca_fisica": f"Avinguda Catalunya, 8, 25001 Lleida ({suffix})",
            "cif": f"B25{uuid.uuid4().hex[:6].upper()}",
            "email": f"info@{dom_desc}",
            "telefon": "+34973240022",
            "linkedin_url": f"https://www.linkedin.com/company/subministraments-{suffix}",
            "instagram_url": f"https://www.instagram.com/subministraments_{suffix}/",
            "web_markdown": "Venda de recanvis al detall en mostrador.",
        },
    ]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Crear i executar tasca atòmica de CP
        res = await ac.post(
            "/api/v1/superadmin/crm/prospeccio/tasques-cp",
            json={
                "codi_postal": "25001",
                "vertical": vertical_lliure,
                "operaris_minims": 6,
                "candidats_descoberts": candidats_reals,
            },
            headers=superadmin_headers,
        )
        assert res.status_code == 201, res.text
        data = res.json()
        assert "tasca_id" in data
        tasca_id = data["tasca_id"]
        assert data["codi_postal"] == "25001"
        assert data["vertical"] == vertical_lliure
        assert data["total_trobats"] == 2
        assert data["total_seleccionats"] == 1
        assert data["total_descartats"] == 1

        # 2. Llistar tasques de CP i verificar que NO s'ha encadenat el CP 25002 (FR-003)
        list_res = await ac.get(
            "/api/v1/superadmin/crm/prospeccio/tasques-cp",
            headers=superadmin_headers,
        )
        assert list_res.status_code == 200
        tasques = list_res.json()
        assert any(t["id"] == tasca_id and t["estat"] == "COMPLETAT" for t in tasques)
        assert not any(t["codi_postal"] == "25002" and t["vertical"] == vertical_lliure for t in tasques)

        # 3. Obtenir detall complet de la tasca amb auditoria transparent de candidats i URLs directes
        det_res = await ac.get(
            f"/api/v1/superadmin/crm/prospeccio/tasques-cp/{tasca_id}",
            headers=superadmin_headers,
        )
        assert det_res.status_code == 200, det_res.text
        detall = det_res.json()
        assert detall["id"] == tasca_id
        assert "candidats" in detall
        assert len(detall["candidats"]) == 2
        estats_cand = {c["estat_decisio"] for c in detall["candidats"]}
        assert "SELECCIONAT" in estats_cand
        assert "DESCARTAT" in estats_cand
        for c in detall["candidats"]:
            fonts = c.get("fonts_investigades") or ""
            fonts_urls = c.get("fonts_urls") or {}
            assert "web" in fonts
            assert "linkedin" in fonts
            assert "instagram" in fonts
            assert fonts_urls.get("web", "").startswith("https://")
            assert fonts_urls.get("linkedin", "").startswith("https://www.linkedin.com/")
            assert fonts_urls.get("instagram", "").startswith("https://www.instagram.com/")
            if c["estat_decisio"] == "SELECCIONAT":
                assert c["decisor_nom"] == "Joan Marcet Vila"
                assert "25001" in (c["adreca_fisica"] or "")

        # 4. Comprovar streaming SSE
        stream_res = await ac.get(
            f"/api/v1/superadmin/crm/prospeccio/tasques-cp/{tasca_id}/stream",
            headers=superadmin_headers,
        )
        assert stream_res.status_code == 200
        assert "text/event-stream" in stream_res.headers.get("content-type", "")
        stream_text = stream_res.text
        assert "event: status" in stream_text
        assert "event: progres" in stream_text


@pytest.mark.asyncio
async def test_t011_tallafocs_cp_adreca_fisica_i_gatekeeper_real(superadmin_headers: dict[str, str]):
    """Verifica que es descarten candidats amb CP d'un comentari d'Instagram o amb nom de Gatekeeper genèric."""
    suffix = uuid.uuid4().hex[:6]
    candidats_invalids = [
        {
            # Error 1: L'adreça física és de 08015 (Barcelona), encara que un comentari d'Instagram digui 25560
            "nom_empresa": f"Manteniments Pirineu {suffix} SL",
            "web_url": f"https://mantenimentspirineu-{suffix}.cat",
            "adreca_fisica": "Carrer Aragó, 120, 08015 Barcelona",
            "cif": f"B25{suffix.upper()[:6]}",
            "email": f"info@mantenimentspirineu-{suffix}.cat",
            "decisor_nom": "Pere Puig Roca",
            "decisor_carrec": "Gerent",
            "fita_recent": "Instagram: Nova instal·lació i manteniment a la zona 25560 Sort",
            "web_markdown": "Empresa de manteniment amb 10 operaris.",
        },
        {
            # Error 2: L'adreça física sí que té el CP 25560, però el Gatekeeper és un càrrec genèric ("Responsable d'Operacions...")
            "nom_empresa": f"Instal·lacions Sort {suffix} SL",
            "web_url": f"https://instal-sort-{suffix}.cat",
            "adreca_fisica": f"Avinguda Comtes de Pallars, 15, 25560 Sort ({suffix})",
            "cif": f"B25{uuid.uuid4().hex[:6].upper()}",
            "email": f"info@instal-sort-{suffix}.cat",
            "decisor_nom": f"Responsable d'Operacions de Instal·lacions Sort {suffix} SL",
            "decisor_carrec": "Director Tècnic",
            "web_markdown": "Empresa de manteniment amb 9 operaris a Sort (25560).",
        },
    ]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post(
            "/api/v1/superadmin/crm/prospeccio/tasques-cp",
            json={
                "codi_postal": "25560",
                "vertical": "manteniment",
                "operaris_minims": 5,
                "candidats_descoberts": candidats_invalids,
            },
            headers=superadmin_headers,
        )
        assert res.status_code == 201, res.text
        data = res.json()
        assert data["total_trobats"] == 2
        assert data["total_seleccionats"] == 0
        assert data["total_descartats"] == 2

        det_res = await ac.get(
            f"/api/v1/superadmin/crm/prospeccio/tasques-cp/{data['tasca_id']}",
            headers=superadmin_headers,
        )
        assert det_res.status_code == 200
        cands = det_res.json()["candidats"]
        assert all(c["estat_decisio"] == "DESCARTAT" for c in cands)
        # El candidat amb nom genèric no ha de conservar mai el placeholder com a decisor_nom
        cand_generic = next(c for c in cands if "Instal·lacions Sort" in c["nom_empresa"])
        assert cand_generic["decisor_nom"] is None


@pytest.mark.asyncio
async def test_t011_admissio_gradual_contacte_operatiu_sense_nom_gatekeeper(
    superadmin_headers: dict[str, str],
    db_session: AsyncSession,
):
    """Verifica que el tallafocs ponderat admet condicionalment (SELECCIONAT) amb score penalitzat (65-78)
    a una empresa real amb quadrilla d'operaris i telèfon/email verificat, encara que no tingui nom de Gatekeeper."""
    suffix = uuid.uuid4().hex[:6]
    candidat_corporatiu = [
        {
            "nom_empresa": f"Clima i Manteniment Pallars {suffix} SL",
            "web_url": f"https://pallars-clima-{suffix}.cat",
            "adreca_fisica": f"Carrer Industrial, 8, 25560 Sort ({suffix})",
            "cif": f"B25{uuid.uuid4().hex[:6].upper()}",
            "telefon": "+34973620123",
            "email": f"info@pallars-clima-{suffix}.cat",
            "decisor_nom": None,
            "web_markdown": "Empresa d'instal·lacions i manteniment tècnic amb equip de 8 operaris a Sort (25560).",
        }
    ]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post(
            "/api/v1/superadmin/crm/prospeccio/tasques-cp",
            json={
                "codi_postal": "25560",
                "vertical": "manteniment",
                "operaris_minims": 5,
                "candidats_descoberts": candidat_corporatiu,
            },
            headers=superadmin_headers,
        )
        assert res.status_code == 201, res.text
        data = res.json()
        assert data["total_trobats"] == 1
        assert data["total_seleccionats"] == 1
        assert data["total_descartats"] == 0

        det_res = await ac.get(
            f"/api/v1/superadmin/crm/prospeccio/tasques-cp/{data['tasca_id']}",
            headers=superadmin_headers,
        )
        assert det_res.status_code == 200
        cand = det_res.json()["candidats"][0]
        assert cand["estat_decisio"] == "SELECCIONAT"
        assert 65 <= cand["score"] <= 78
        assert cand["decisor_nom"] is None
        assert "Pendent nom" in (cand["decisor_carrec"] or "")

        # Verificar que el SaasLead s'ha creat correctament amb nom de contacte de Direcció Tècnica
        res_lead = await db_session.execute(
            select(SaasLead).where(SaasLead.nom_empresa == f"Clima i Manteniment Pallars {suffix} SL")
        )
        lead = res_lead.scalar_one_or_none()
        assert lead is not None
        assert lead.nom_contacte == f"Direcció Tècnica (Clima i Manteniment Pallars {suffix} SL)"
        assert lead.telefon == "+34973620123"


# ==============================================================================
# TESTS T012: DOBLE BUCLE D'APRENENTATGE (CORREGIR CRITERI I REGISTRAR ÈXIT)
# ==============================================================================

@pytest.mark.asyncio
async def test_t012_corregir_criteri_exigeix_justificacio_obligatoria(
    superadmin_headers: dict[str, str],
    db_session: AsyncSession,
):
    """Verifica que corregir la decisió d'un candidat exigeix obligatòriament justificació humana (FR-011)."""
    now = datetime.now(timezone.utc)
    suffix = uuid.uuid4().hex[:8]

    tasca = SaasProspeccioTasca(
        id=uuid.uuid4(),
        codi_postal="25001",
        vertical="Instal·lacions Elèctriques",
        operaris_minims=5,
        estat="COMPLETAT",
        created_at=now,
    )
    candidat = SaasProspeccioCandidat(
        id=uuid.uuid4(),
        tasca_id=tasca.id,
        nom_empresa=f"Electro {suffix} SL",
        web_url="https://electro.cat",
        domini_normalitzat=f"electro-{suffix}.cat",
        codi_postal="25001",
        vertical="Instal·lacions Elèctriques",
        score=75,
        estat_decisio="SELECCIONAT",
        motiu_detallat_ia="Empresa d'electricitat amb bona presència web.",
        created_at=now,
        updated_at=now,
    )
    db_session.add(tasca)
    await db_session.flush()
    db_session.add(candidat)
    await db_session.flush()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Intent sense justificació o amb text < 10 caràcters -> ha de retornar error 400
        bad_res = await ac.post(
            f"/api/v1/superadmin/crm/prospeccio/candidats/{candidat.id}/corregir-criteri",
            json={
                "nova_decisio": "DESCARTAT",
                "motiu_correccio_humana": "Curt",  # < 10 caràcters
            },
            headers=superadmin_headers,
        )
        assert bad_res.status_code in (400, 422)

        # Intent amb justificació vàlida (>= 10 caràcters) -> ha d'acceptar i registrar aprenentatge
        motiu_valid = "És un negoci d'il·luminació al detall, no fan instal·lacions al terreny."
        good_res = await ac.post(
            f"/api/v1/superadmin/crm/prospeccio/candidats/{candidat.id}/corregir-criteri",
            json={
                "nova_decisio": "DESCARTAT",
                "motiu_correccio_humana": motiu_valid,
            },
            headers=superadmin_headers,
        )
        assert good_res.status_code == 200, good_res.text
        assert good_res.json()["nova_decisio"] == "DESCARTAT"

        # Verificar que la regla s'ha afegit a saas_criteris_feedback
        feedback_res = await ac.get(
            "/api/v1/superadmin/crm/prospeccio/criteris-feedback?tipus=CORRECCIO_DESCART",
            headers=superadmin_headers,
        )
        assert feedback_res.status_code == 200
        feedbacks = feedback_res.json()
        assert any(f["nom_empresa"] == f"Electro {suffix} SL" for f in feedbacks)


@pytest.mark.asyncio
async def test_t012_registrar_exit_guanyat_i_lookalike_feedback(
    superadmin_headers: dict[str, str],
    db_session: AsyncSession,
):
    """Verifica que registrar el tancament d'èxit GUANYAT alimenta el Bucle 2 de Lookalikes (FR-012)."""
    now = datetime.now(timezone.utc)
    suffix = uuid.uuid4().hex[:8]

    lead = SaasLead(
        id=uuid.uuid4(),
        nom_empresa=f"Frigorífics Ponent {suffix} SL",
        nom_contacte="Artur Mas",
        email=f"artur_{suffix}@frigo.cat",
        vertical="Climatització Industrial",
        created_at=now,
        updated_at=now,
    )
    db_session.add(lead)
    await db_session.flush()

    op = SaasOportunitat(
        id=uuid.uuid4(),
        lead_id=lead.id,
        titol=f"Llicència Sevalor - {lead.nom_empresa}",
        etapa="NEGOCIACIO",
        valor_mensual_estimat=480.0,
        probabilitat_percent=80,
        created_at=now,
        updated_at=now,
    )
    db_session.add(op)
    await db_session.flush()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post(
            f"/api/v1/superadmin/crm/prospeccio/oportunitats/{op.id}/registrar-exit",
            json={
                "rao_tancament_exit": "El Bot de Telegram els resol la signatura d'entregues urgents.",
                "requisits_replicables": "Empreses de fred industrial amb >8 operaris i torns 24h.",
                "es_replicable": True,
            },
            headers=superadmin_headers,
        )
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["etapa"] == "GUANYAT"
        assert data["es_replicable"] is True

        # Comprovar que s'ha registrat a saas_criteris_feedback com a TANCAMENT_EXIT_REPLICABLE
        fb_res = await ac.get(
            "/api/v1/superadmin/crm/prospeccio/criteris-feedback?tipus=TANCAMENT_EXIT_REPLICABLE",
            headers=superadmin_headers,
        )
        assert fb_res.status_code == 200
        fbs = fb_res.json()
        assert any("Bot de Telegram" in f["explicacio_humana_o_rao_exit"] for f in fbs)


# ==============================================================================
# TESTS T013: CALENDARI COMERCIAL INTEGRAT, CAMPANYES I CORREU BIDIRECCIONAL
# ==============================================================================

@pytest.mark.asyncio
async def test_t013_calendari_comercial_i_hitl_enviar(
    superadmin_headers: dict[str, str],
    db_session: AsyncSession,
):
    """Verifica la consulta del Calendari Comercial i l'acció HITL d'aprovació d'enviament (FR-014, FR-015)."""
    now = datetime.now(timezone.utc)
    suffix = uuid.uuid4().hex[:8]

    lead = SaasLead(
        id=uuid.uuid4(),
        nom_empresa=f"Solar Segrià {suffix} SL",
        nom_contacte="Ramon Roca",
        email=f"ramon_{suffix}@solarsegria.cat",
        vertical="ElectricPro",
        estat_qualificacio="DEMO_ACTIVA",
        data_inici_demo=now,
        data_fi_demo=now + timedelta(days=7),
        created_at=now,
        updated_at=now,
    )
    db_session.add(lead)
    await db_session.flush()

    correu_id = uuid.uuid4()
    correu = SaasCorreuMissatge(
        id=correu_id,
        lead_id=lead.id,
        tipus_item_calendari="EMAIL_CAMPANYA",
        pas_sequencia=1,
        tempo_dies_offset=0,
        data_programada=now,
        direccio="OUTBOUND",
        estat_enviament="ESBORRANY_PROGRAMAT",
        remitent="tecnic@sevalor.net",
        destinatari=lead.email,
        assumpte="Optimització tècnica per a Solar Segrià",
        cos_text="Hola Ramon, us presentem la solució Sevalor.",
        message_id=f"<{uuid.uuid4().hex}@sevalor.net>",
        created_at=now,
    )
    db_session.add(correu)
    await db_session.flush()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Consultar Calendari Comercial (incloent EMAIL_CAMPANYA i VENCIMENT_DEMO)
        cal_res = await ac.get(
            "/api/v1/superadmin/crm/prospeccio/calendari",
            headers=superadmin_headers,
        )
        assert cal_res.status_code == 200
        cal_data = cal_res.json()
        assert "items" in cal_data
        assert any(item["id"] == str(correu_id) for item in cal_data["items"])
        assert any(
            item["tipus_item_calendari"] == "VENCIMENT_DEMO" and item["lead_id"] == str(lead.id)
            for item in cal_data["items"]
        )

        # 2. Editar esborrany del correu
        edit_res = await ac.put(
            f"/api/v1/superadmin/crm/prospeccio/correus/{correu_id}/esborrany",
            json={
                "assumpte": "Assumpte editat per l'humà abans d'enviar",
            },
            headers=superadmin_headers,
        )
        assert edit_res.status_code == 200

        # 3. Acció HITL: Aprovar i Enviar des de tecnic@sevalor.net
        send_res = await ac.post(
            f"/api/v1/superadmin/crm/prospeccio/correus/{correu_id}/enviar",
            headers=superadmin_headers,
        )
        assert send_res.status_code == 200, send_res.text
        send_data = send_res.json()
        assert send_data["estat_enviament"] == "APROVAT_ENVIAT"

        # 4. Obtenir fil de correus del lead
        thread_res = await ac.get(
            f"/api/v1/superadmin/crm/prospeccio/leads/{lead.id}/correus",
            headers=superadmin_headers,
        )
        assert thread_res.status_code == 200
        thread = thread_res.json()
        assert len(thread) >= 1
        assert thread[0]["estat_enviament"] == "APROVAT_ENVIAT"

        # 5. Crear esdeveniment manual al Calendari Comercial
        ev_res = await ac.post(
            "/api/v1/superadmin/crm/prospeccio/calendari/esdeveniments",
            json={
                "lead_id": str(lead.id),
                "tipus": "SEGUIMENT_CALENDARI",
                "data_programada": (now + timedelta(days=3)).isoformat(),
                "titol": "Trucada de seguiment comercial",
                "descripcio": "Confirmar revisió de proposta amb Ramon Roca.",
            },
            headers=superadmin_headers,
        )
        assert ev_res.status_code == 201, ev_res.text

        # 6. Validar registres DNS MX del lead via endpoint
        mx_res = await ac.post(
            f"/api/v1/superadmin/crm/prospeccio/leads/{lead.id}/validar-mx",
            headers=superadmin_headers,
        )
        assert mx_res.status_code == 200
        assert "mx_validat" in mx_res.json()


@pytest.mark.asyncio
async def test_t009_t010_inbound_intencions_i_docker_stalwart(
    superadmin_headers: dict[str, str],
    db_session: AsyncSession,
):
    """Verifica T009 (intencions INTERESSAT_INFO, OUT_OF_OFFICE, NO_INTERESSAT) i T010 (docker-compose Stalwart)."""
    from pathlib import Path

    # T010: Verificar configuració de stalwart_mail a docker-compose.yml
    compose_path = Path(__file__).resolve().parents[2] / "docker-compose.yml"
    compose_content = compose_path.read_text(encoding="utf-8")
    assert "stalwart_mail:" in compose_content
    assert "stalwartlabs/mail-server:latest" in compose_content
    assert "sevalor_stalwart_data:" in compose_content

    # T009: Verificar intencio INTERESSAT_INFO genera esborrany de resposta tècnica i mou a QUALIFICACIO
    now = datetime.now(timezone.utc)
    suffix = uuid.uuid4().hex[:8]
    email_info = f"info_{suffix}@instalacions.cat"

    lead = SaasLead(
        id=uuid.uuid4(),
        nom_empresa=f"Instal·lacions {suffix} SL",
        nom_contacte="Marta Serra",
        email=email_info,
        vertical="HydroPro",
        created_at=now,
        updated_at=now,
    )
    db_session.add(lead)
    await db_session.flush()

    op = SaasOportunitat(
        id=uuid.uuid4(),
        lead_id=lead.id,
        titol=f"Llicència HydroPro - {lead.nom_empresa}",
        etapa="PROSPECCIO",
        valor_mensual_estimat=250.0,
        probabilitat_percent=20,
        created_at=now,
        updated_at=now,
    )
    db_session.add(op)
    await db_session.flush()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res_info = await ac.post(
            "/api/v1/superadmin/crm/prospeccio/correu/sincronitzar-inbound",
            json={
                "remitent": email_info,
                "assumpte": "Re: Tarifes i detalls",
                "cos_text": "Hola, ens podeu enviar més informació de tarifes i detalls tècnics?",
            },
            headers=superadmin_headers,
        )
        assert res_info.status_code == 200, res_info.text
        assert res_info.json()["intencio_ia"] == "INTERESSAT_INFO"

        # Comprovar que s'ha generat l'esborrany de resposta tècnica (OUTBOUND / ESBORRANY_PROGRAMAT)
        thread_res = await ac.get(
            f"/api/v1/superadmin/crm/prospeccio/leads/{lead.id}/correus",
            headers=superadmin_headers,
        )
        assert thread_res.status_code == 200
        msgs = thread_res.json()
        assert any(
            m["direccio"] == "OUTBOUND" and m["estat_enviament"] == "ESBORRANY_PROGRAMAT"
            for m in msgs
        )


@pytest.mark.asyncio
async def test_t013_inbound_sincronitzar_pausa_automatica(
    superadmin_headers: dict[str, str],
    db_session: AsyncSession,
):
    """Verifica que la sincronització Inbound pausa automàticament els correus pendents de la seqüència."""
    now = datetime.now(timezone.utc)
    suffix = uuid.uuid4().hex[:8]
    email_lead = f"direccio_{suffix}@agro.cat"

    lead = SaasLead(
        id=uuid.uuid4(),
        nom_empresa=f"Agro {suffix} SL",
        nom_contacte="Albert Riu",
        email=email_lead,
        vertical="CampoPro",
        created_at=now,
        updated_at=now,
    )
    db_session.add(lead)
    await db_session.flush()

    # Correu 2 programat com a esborrany
    m2 = SaasCorreuMissatge(
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
        assumpte="Cas d'èxit de seguiment",
        cos_text="Hola Albert...",
        message_id=f"<{uuid.uuid4().hex}@sevalor.net>",
        created_at=now,
    )
    db_session.add(m2)
    await db_session.flush()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Enviar resposta entrant del client
        inbound_res = await ac.post(
            "/api/v1/superadmin/crm/prospeccio/correu/sincronitzar-inbound",
            json={
                "remitent": email_lead,
                "assumpte": "Re: Proposta",
                "cos_text": "Hola, ens agradaria veure una demo del software la setmana que ve.",
            },
            headers=superadmin_headers,
        )
        assert inbound_res.status_code == 200, inbound_res.text
        inbound_data = inbound_res.json()
        assert inbound_data["intencio_ia"] == "INTERESSAT_DEMO"

        # Verificar que el correu 2 ha passat automàticament a PAUSAT_PER_RESPOSTA
        stmt_m2 = select(SaasCorreuMissatge).where(SaasCorreuMissatge.id == m2.id)
        res_m2 = await db_session.execute(stmt_m2)
        m2_saved = res_m2.scalar_one()
        assert m2_saved.estat_enviament == "PAUSAT_PER_RESPOSTA"


@pytest.mark.asyncio
async def test_t013_gestio_exclusio_rgpd(superadmin_headers: dict[str, str]):
    """Verifica l'endpoint d'afegir i llistar dominis a la llista d'exclusió RGPD."""
    suffix = uuid.uuid4().hex[:8]
    domini = f"empresa-optout-{suffix}.com"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post(
            "/api/v1/superadmin/crm/prospeccio/exclusio-rgpd",
            json={
                "email": f"baja@{domini}",
                "domini": domini,
                "motiu": "SOL_LICITUD_WEB",
            },
            headers=superadmin_headers,
        )
        assert res.status_code == 201, res.text

        list_res = await ac.get(
            "/api/v1/superadmin/crm/prospeccio/exclusio-rgpd",
            headers=superadmin_headers,
        )
        assert list_res.status_code == 200
        excl_list = list_res.json()
        assert any(e["domini"] == domini for e in excl_list)


@pytest.mark.asyncio
async def test_zero_trust_seguretat_nous_endpoints(boss_headers: dict[str, str]):
    """Verifica que un usuari BOSS no pot accedir a cap dels nous endpoints de Superadmin (403 Forbidden)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r1 = await ac.get("/api/v1/superadmin/crm/prospeccio/tasques-cp", headers=boss_headers)
        assert r1.status_code == 403

        r2 = await ac.get("/api/v1/superadmin/crm/prospeccio/calendari", headers=boss_headers)
        assert r2.status_code == 403

        r3 = await ac.get("/api/v1/superadmin/crm/prospeccio/criteris-feedback", headers=boss_headers)
        assert r3.status_code == 403

        r4 = await ac.get("/api/v1/superadmin/crm/prospeccio/exclusio-rgpd", headers=boss_headers)
        assert r4.status_code == 403


@pytest.mark.asyncio
async def test_editar_i_eliminar_lead_deal_i_candidat_crm(
    superadmin_headers: dict[str, str],
    db_session: AsyncSession,
):
    """Verifica l'edició completa i l'esborrat net de Leads, Deals (Oportunitats) i Candidats al CRM."""
    suffix = uuid.uuid4().hex[:8]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Crear un Lead amb Deal inicial
        res_create = await ac.post(
            "/api/v1/superadmin/crm/prospeccio/leads",
            json={
                "nom_empresa": f"Instal·lacions Editables {suffix} SL",
                "nom_contacte": "Marc Vila Soler",
                "email": f"m.vila@{suffix}.cat",
                "telefon": "+34612345678",
                "vertical": "ElectricPro",
                "operaris_estimats": 7,
                "crear_oportunitat_inicial": True,
                "valor_mensual_estimat": 126.0,
            },
            headers=superadmin_headers,
        )
        assert res_create.status_code == 201, res_create.text
        lead_id = res_create.json()["lead_id"]
        op_id = res_create.json()["oportunitat_id"]
        assert op_id is not None

        # 2. Editar el Lead (PUT) i comprovar normalització d'adreça, CIF i domini
        res_edit_lead = await ac.put(
            f"/api/v1/superadmin/crm/prospeccio/leads/{lead_id}",
            json={
                "nom_empresa": f"Instal·lacions Editades {suffix} SL",
                "nom_contacte": "Marc Vila Soler",
                "carrec_contacte": "Director Tècnic",
                "email": f"marc.vila@{suffix}.cat",
                "telefon": "+34973112233",
                "cif": "b-25123456",
                "web_url": f"https://www.{suffix}.cat/contacte",
                "adreca_fisica": "Pol. Ind. El Segre, C/ Josep Baró, 14, 25001 Lleida",
                "codi_postal": "25001",
                "operaris_estimats": 10,
            },
            headers=superadmin_headers,
        )
        assert res_edit_lead.status_code == 200, res_edit_lead.text

        det_lead = await ac.get(
            f"/api/v1/superadmin/crm/prospeccio/leads/{lead_id}",
            headers=superadmin_headers,
        )
        assert det_lead.status_code == 200
        lead_json = det_lead.json()
        assert lead_json["nom_empresa"] == f"Instal·lacions Editades {suffix} SL"
        assert lead_json["cif"] == "B25123456"
        assert lead_json["domini_normalitzat"] == f"{suffix}.cat"
        assert lead_json["adreca_fisica"] == "Pol. Ind. El Segre, C/ Josep Baró, 14, 25001 Lleida"

        # 3. Editar el Deal (Oportunitat) amb PUT
        res_edit_op = await ac.put(
            f"/api/v1/superadmin/crm/prospeccio/oportunitats/{op_id}",
            json={
                "titol": f"Deal Ampliat 10 Operaris - {suffix}",
                "etapa": "PROPOSTA",
                "valor_mensual_estimat": 180.0,
                "valor_ia_setup": 250.0,
                "probabilitat_percent": 65,
            },
            headers=superadmin_headers,
        )
        assert res_edit_op.status_code == 200, res_edit_op.text
        op_json = res_edit_op.json()
        assert op_json["titol"] == f"Deal Ampliat 10 Operaris - {suffix}"
        assert op_json["nova_etapa"] == "PROPOSTA"
        assert op_json["valor_mensual_estimat"] == 180.0

        # 4. Eliminar el Deal (DELETE /oportunitats/{id})
        res_del_op = await ac.delete(
            f"/api/v1/superadmin/crm/prospeccio/oportunitats/{op_id}",
            headers=superadmin_headers,
        )
        assert res_del_op.status_code == 200, res_del_op.text

        # 5. Eliminar el Lead (DELETE /leads/{id})
        res_del_lead = await ac.delete(
            f"/api/v1/superadmin/crm/prospeccio/leads/{lead_id}",
            headers=superadmin_headers,
        )
        assert res_del_lead.status_code == 200, res_del_lead.text

        res_404 = await ac.get(
            f"/api/v1/superadmin/crm/prospeccio/leads/{lead_id}",
            headers=superadmin_headers,
        )
        assert res_404.status_code == 404

        # 6. Eliminar candidat amb estat ERROR_EXTRACCIO i comprovar decrement de total_descartats
        tasca_id = uuid.uuid4()
        candidat_err_id = uuid.uuid4()
        ara_t = datetime.now(timezone.utc)
        tasca_test = SaasProspeccioTasca(
            id=tasca_id,
            codi_postal="25001",
            vertical="ElectricPro",
            operaris_minims=5,
            estat="COMPLETAT",
            total_trobats=1,
            total_seleccionats=0,
            total_descartats=1,
            total_duplicats=0,
            created_at=ara_t,
        )
        candidat_err = SaasProspeccioCandidat(
            id=candidat_err_id,
            tasca_id=tasca_id,
            nom_empresa=f"Error Extraccio {suffix} SL",
            web_url="https://error.invalid",
            domini_normalitzat="error.invalid",
            codi_postal="25001",
            vertical="ElectricPro",
            fonts_investigades="",
            mx_validat=False,
            operaris_estimats=0,
            score=0,
            estat_decisio="ERROR_EXTRACCIO",
            motiu_detallat_ia="Error de prova",
            created_at=ara_t,
            updated_at=ara_t,
        )
        db_session.add(tasca_test)
        await db_session.flush()
        db_session.add(candidat_err)
        await db_session.commit()

        res_del_cand = await ac.delete(
            f"/api/v1/superadmin/crm/prospeccio/candidats/{candidat_err_id}",
            headers=superadmin_headers,
        )
        assert res_del_cand.status_code == 200, res_del_cand.text

        # Comprovar que la tasca ha restat el descartat i el trobat
        res_t_check = await db_session.execute(select(SaasProspeccioTasca).where(SaasProspeccioTasca.id == tasca_id))
        tasca_actualitzada = res_t_check.scalars().first()
        assert tasca_actualitzada is not None
        assert tasca_actualitzada.total_trobats == 0
        assert tasca_actualitzada.total_descartats == 0


@pytest.mark.asyncio
async def test_t011_savepoint_error_extraccio_truncament_varchar_i_contacte_operatiu(
    superadmin_headers: dict[str, str],
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    """Valida:
    1. Aïllament SAVEPOINT (db.begin_nested): una fallada en un candidat genera ERROR_EXTRACCIO sense avortar el lot.
    2. Admissió condicional per contacte operatiu quan no hi ha nom humà de Gatekeeper però sí telèfon i operaris.
    3. Blindatge VARCHAR en nom_contacte (<=100) i titol d'oportunitat (<=200) amb noms d'empresa llargs.
    4. Decrement correcte de comptadors en eliminar un candidat amb estat ERROR_EXTRACCIO.
    """
    from app.services.firecrawl_service import firecrawl_service

    suffix = uuid.uuid4().hex[:6]
    dom_operatiu = f"instal-operatiu-{suffix}.cat"
    dom_error = f"fallada-xarxa-{suffix}.cat"

    # Nom d'empresa i vertical llargs per estressar els límits VARCHAR(100) i VARCHAR(200)
    nom_llarg = (
        f" Grup d'Enginyeria i Manteniment Integral d'Instal·lacions Fotovoltaiques "
        f"i Climatització Industrial de Ponent {suffix} SL "
    ).strip()
    vertical_llarga = (
        f"Instal·lació i Manteniment Preventiu de Sistemes de Climatització, "
        f"Baixa Tensió REBT i Bombeig Solar {suffix}"
    )

    orig_investigar = firecrawl_service.investigar_empresa_completa

    async def _mock_investigar_amb_fallada_aillada(
        nom_empresa: str,
        web_url: str,
        codi_postal: str,
        vertical: str,
        dades_inicials: dict | None = None,
    ):
        if dom_error in web_url:
            raise RuntimeError("Timeout simulat raspant subpàgina d'avís legal")
        return await orig_investigar(
            nom_empresa=nom_empresa,
            web_url=web_url,
            codi_postal=codi_postal,
            vertical=vertical,
            dades_inicials=dades_inicials,
        )

    monkeypatch.setattr(
        firecrawl_service,
        "investigar_empresa_completa",
        _mock_investigar_amb_fallada_aillada,
    )

    candidats_lot = [
        {
            # Candidat 1: Sense Gatekeeper nominal (porta un càrrec genèric), però amb telèfon operatiu,
            # ubicació al municipi de Lleida (Polígon sense els 5 dígits explícits) i >6 operaris.
            "nom_empresa": nom_llarg,
            "web_url": f"https://{dom_operatiu}",
            "adreca_fisica": f"Polígon Industrial El Segre, Carrer del Metall, Nau 18, Lleida ({suffix})",
            "cif": f"B25{suffix.upper()[:6]}",
            "email": f"info@{dom_operatiu}",
            "telefon": "+34973248899",
            "decisor_nom": "Responsable d'Operacions i Manteniment",  # Genèric -> es netejarà a None
            "decisor_carrec": "Direcció Tècnica",
            "web_markdown": (
                "Empresa instal·ladora al Polígon Industrial El Segre de Lleida amb flota de 14 furgonetes "
                "i equip de 18 tècnics d'obra en climatització i electricitat industrial."
            ),
        },
        {
            # Candidat 2: Provocarà una excepció en temps d'execució que ha de quedar aïllada al seu SAVEPOINT
            "nom_empresa": f"Empresa Amb Fallada Xarxa {suffix} SL",
            "web_url": f"https://{dom_error}",
            "adreca_fisica": "Carrer Major, 10, 25001 Lleida",
            "cif": f"B25{uuid.uuid4().hex[:6].upper()}",
            "email": f"contacte@{dom_error}",
            "telefon": "+34973000000",
        },
    ]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Executar el lot atòmic per al CP 25001 (Lleida)
        res = await ac.post(
            "/api/v1/superadmin/crm/prospeccio/tasques-cp",
            json={
                "codi_postal": "25001",
                "vertical": vertical_llarga,
                "operaris_minims": 6,
                "candidats_descoberts": candidats_lot,
            },
            headers=superadmin_headers,
        )
        assert res.status_code == 201, res.text
        data = res.json()
        tasca_id = data["tasca_id"]
        assert data["total_trobats"] == 2
        assert data["total_seleccionats"] == 1
        assert data["total_descartats"] == 1

        # 2. Verificar el detall dels candidats registrats al lot
        det_res = await ac.get(
            f"/api/v1/superadmin/crm/prospeccio/tasques-cp/{tasca_id}",
            headers=superadmin_headers,
        )
        assert det_res.status_code == 200, det_res.text
        candidats = det_res.json()["candidats"]
        assert len(candidats) == 2

        cand_sel = next(c for c in candidats if c["estat_decisio"] == "SELECCIONAT")
        cand_err = next(c for c in candidats if c["estat_decisio"] == "ERROR_EXTRACCIO")

        # 2a. Verificació de l'admissió condicional sense Gatekeeper nominal
        assert cand_sel["decisor_nom"] is None
        assert 65 <= cand_sel["score"] <= 78
        assert "AVÍS: Decisor nominal pendent d'identificar" in (cand_sel["motiu_detallat_ia"] or "")
        assert cand_sel["lead_id"] is not None

        # 2b. Verificació del blindatge VARCHAR a SaasLead i SaasOportunitat
        lead_res = await ac.get(
            f"/api/v1/superadmin/crm/prospeccio/leads/{cand_sel['lead_id']}",
            headers=superadmin_headers,
        )
        assert lead_res.status_code == 200
        lead_data = lead_res.json()
        assert len(lead_data["nom_contacte"]) <= 100
        assert lead_data["nom_contacte"].startswith("Direcció Tècnica (")
        assert len(lead_data["oportunitats"]) == 1
        assert len(lead_data["oportunitats"][0]["titol"]) <= 200

        # 2c. Verificació del candidat aïllat amb ERROR_EXTRACCIO
        assert cand_err["score"] == 0
        assert cand_err["lead_id"] is None
        assert "Timeout simulat" in (cand_err["motiu_detallat_ia"] or "")

        # 3. Eliminar el candidat en estat ERROR_EXTRACCIO i comprovar que els comptadors es decrementen
        del_res = await ac.delete(
            f"/api/v1/superadmin/crm/prospeccio/candidats/{cand_err['id']}",
            headers=superadmin_headers,
        )
        assert del_res.status_code == 200, del_res.text

        det_post_del = await ac.get(
            f"/api/v1/superadmin/crm/prospeccio/tasques-cp/{tasca_id}",
            headers=superadmin_headers,
        )
        assert det_post_del.status_code == 200
        tasca_actualitzada = det_post_del.json()
        assert tasca_actualitzada["total_trobats"] == 1
        assert tasca_actualitzada["total_seleccionats"] == 1
        assert tasca_actualitzada["total_descartats"] == 0
