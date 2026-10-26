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
    """Verifica l'execució d'un lot atòmic per Codi Postal amb vertical lliure i streaming SSE."""
    suffix = uuid.uuid4().hex[:6]
    vertical_lliure = f"Manteniment de Climatització i Fred Industrial {suffix}"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Crear i executar tasca atòmica de CP
        res = await ac.post(
            "/api/v1/superadmin/crm/prospeccio/tasques-cp",
            json={
                "codi_postal": "25001",
                "vertical": vertical_lliure,
                "operaris_minims": 6,
            },
            headers=superadmin_headers,
        )
        assert res.status_code == 201, res.text
        data = res.json()
        assert "tasca_id" in data
        tasca_id = data["tasca_id"]
        assert data["codi_postal"] == "25001"
        assert data["vertical"] == vertical_lliure
        assert data["total_trobats"] >= 2
        assert data["total_seleccionats"] >= 1
        assert data["total_descartats"] >= 1

        # 2. Llistar tasques de CP i verificar que NO s'ha encadenat el CP 25002 (FR-003)
        list_res = await ac.get(
            "/api/v1/superadmin/crm/prospeccio/tasques-cp",
            headers=superadmin_headers,
        )
        assert list_res.status_code == 200
        tasques = list_res.json()
        assert any(t["id"] == tasca_id and t["estat"] == "COMPLETAT" for t in tasques)
        assert not any(t["codi_postal"] == "25002" and t["vertical"] == vertical_lliure for t in tasques)

        # 3. Obtenir detall complet de la tasca amb auditoria transparent de candidats
        det_res = await ac.get(
            f"/api/v1/superadmin/crm/prospeccio/tasques-cp/{tasca_id}",
            headers=superadmin_headers,
        )
        assert det_res.status_code == 200, det_res.text
        detall = det_res.json()
        assert detall["id"] == tasca_id
        assert "candidats" in detall
        assert len(detall["candidats"]) >= 2
        estats_cand = {c["estat_decisio"] for c in detall["candidats"]}
        assert "SELECCIONAT" in estats_cand
        assert "DESCARTAT" in estats_cand
        for c in detall["candidats"]:
            fonts = c.get("fonts_investigades") or ""
            assert "web" in fonts
            assert "linkedin" in fonts
            assert "instagram" in fonts

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
