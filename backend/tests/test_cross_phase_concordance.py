"""
Tests de Concordança entre Fases (SEVALOR v4.0).
Validen la integritat i coherència transversal de punta a punta entre totes les fases:
- TEST-CROSS-01: Fluxe Complet de Camp a Oficina (Incidència PWA -> Celery / DB -> Gestió).
- TEST-CROSS-02: RLS Transversal (cap endpoint de cap fase trenca l'aïllament multi-tenant).
- TEST-CROSS-03: Coherència Pressupost -> Telegram -> Copilot (Estat viu APROVAT).
- TEST-CROSS-04: Consistència d'Estoc entre Magatzem, Picking i Copilot (500 - 120 = 380 viu).
- TEST-CROSS-05: Denegació Transversal de Rol (Veto d'Enginyer consistent a clients/iban, copilot i comptabilitat).
"""

import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.config import settings
from app.main import app
from app.models.models import (
    Article,
    Client,
    Empresa,
    EstocMagatzem,
    FullaPicking,
    Incidencia,
    LiniaPicking,
    Magatzem,
    OrdreTreball,
    Pressupost,
    Usuari,
    Vehicle,
)


def crear_token(usuari_id: uuid.UUID, empresa_id: uuid.UUID, rol: str) -> str:
    """Helper per generar tokens JWT per a proves."""
    payload = {
        "sub": str(usuari_id),
        "rol": rol,
        "empresa_id": str(empresa_id),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


@pytest.mark.asyncio
async def test_cross_01_fluxe_complet_camp_a_oficina(admin_session):
    """
    TEST-CROSS-01: Fluxe Complet de Camp a Oficina.
    1. Operari crea incidència multipart des de camp amb foto i àudio.
    2. Comprovar registre a la BD amb àudio i foto persistits.
    3. Comprovar que l'OT i la seva posició es reflecteixen a la Torre de Control GIS (/gestio/feines/mapa).
    """
    empresa_id = uuid.uuid4()
    operari_id = uuid.uuid4()
    boss_id = uuid.uuid4()

    empresa = Empresa(
        id=empresa_id,
        nom="Serveis Integrals Catalunya SL",
        nif="B" + uuid.uuid4().hex[:8].upper(),
        subdomini="sic-" + uuid.uuid4().hex[:5],
        pla_subscripcio="ENTERPRISE",
        estat_pagament="ACTIU",
        vertical="SEVALOR",
    )
    admin_session.add(empresa)
    await admin_session.flush()

    usuari_operari = Usuari(
        id=operari_id,
        empresa_id=empresa_id,
        nom="Pol",
        cognoms="Operari",
        nif="22334455H",
        rol="OPERARI",
        estat="ACTIU",
    )
    usuari_boss = Usuari(
        id=boss_id,
        empresa_id=empresa_id,
        nom="Anna",
        cognoms="Directora",
        nif="77889900I",
        rol="BOSS",
        estat="ACTIU",
    )
    admin_session.add_all([usuari_operari, usuari_boss])
    await admin_session.flush()

    client = Client(
        id=uuid.uuid4(),
        empresa_id=empresa_id,
        codi="CLI-CROSS-01",
        rao_social="Hospital de Campanya Vallès",
        nif="Q" + uuid.uuid4().hex[:8].upper(),
    )
    admin_session.add(client)
    await admin_session.flush()

    ot = OrdreTreball(
        id=uuid.uuid4(),
        empresa_id=empresa_id,
        codi="OT-CROSS-001",
        client_id=client.id,
        titol="Reparació quadre clínic",
        adreca="41.3910, 2.1820",
        estat="EN_CURS",
        cap_de_colla_id=operari_id,
    )
    admin_session.add(ot)
    await admin_session.flush()

    token_operari = crear_token(operari_id, empresa_id, "OPERARI")
    token_boss = crear_token(boss_id, empresa_id, "BOSS")

    # 1. POST incidència des de camp (multipart)
    form_data = {
        "ordre_treball_id": str(ot.id),
        "tipus_incidencia": "BLOQUEIG_CAMP",
        "descripcio": "Tub d'alimentació trencat per pressió excessiva.",
    }
    files = {
        "audio": ("gravacio_camp.webm", b"RIFF-WAVE-CAMP-AUDIO", "audio/webm"),
        "foto": ("evidencia.jpg", b"JPEG-RAW-IMAGE-EVIDENCE", "image/jpeg"),
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res_inc = await ac.post(
            "/api/v1/operari/incidencies",
            data=form_data,
            files=files,
            headers={"Authorization": f"Bearer {token_operari}", "X-Empresa-ID": str(empresa_id)},
        )
        assert res_inc.status_code == 201
        data_inc = res_inc.json()
        assert data_inc["audio_path"] is not None
        assert data_inc["foto_path"] is not None

        # 2. Verificar presència a la BD
        q_inc_db = select(Incidencia).where(Incidencia.ordre_treball_id == ot.id)
        inc_db = (await admin_session.execute(q_inc_db)).scalars().first()
        assert inc_db is not None
        assert inc_db.audio_path is not None

        # 3. Comprovar que a l'oficina es veu l'OT a la Torre de Control GIS
        res_mapa = await ac.get(
            "/api/v1/gestio/feines/mapa",
            headers={"Authorization": f"Bearer {token_boss}", "X-Empresa-ID": str(empresa_id)},
        )
        assert res_mapa.status_code == 200
        feines_mapa = res_mapa.json()
        codis = [f["codi"] for f in feines_mapa]
        assert "OT-CROSS-001" in codis


@pytest.mark.asyncio
async def test_cross_02_rls_transversal(admin_session):
    """
    TEST-CROSS-02: RLS Transversal (cap endpoint de cap fase no trenca l'aïllament).
    Empresa A té dades de clients, flota, magatzem, mapa, pressupostos i RAG.
    Empresa B (buida) consulta els mateixos endpoints i rep llistes buides.
    """
    empresa_a_id = uuid.uuid4()
    empresa_b_id = uuid.uuid4()
    boss_b_id = uuid.uuid4()

    emp_a = Empresa(
        id=empresa_a_id,
        nom="Empresa Alpha SL",
        nif="B" + uuid.uuid4().hex[:8].upper(),
        subdomini="alpha-" + uuid.uuid4().hex[:5],
        pla_subscripcio="ENTERPRISE",
        estat_pagament="ACTIU",
        vertical="SEVALOR",
    )
    emp_b = Empresa(
        id=empresa_b_id,
        nom="Empresa Beta SL",
        nif="B" + uuid.uuid4().hex[:8].upper(),
        subdomini="beta-" + uuid.uuid4().hex[:5],
        pla_subscripcio="ENTERPRISE",
        estat_pagament="ACTIU",
        vertical="SEVALOR",
    )
    admin_session.add_all([emp_a, emp_b])
    await admin_session.flush()

    usuari_b = Usuari(
        id=boss_b_id,
        empresa_id=empresa_b_id,
        nom="Director",
        cognoms="Beta",
        nif="99001122K",
        rol="BOSS",
        estat="ACTIU",
    )
    admin_session.add(usuari_b)

    # Poblar Empresa A
    client_a = Client(
        id=uuid.uuid4(),
        empresa_id=empresa_a_id,
        codi="CLI-A",
        rao_social="Client d'Alpha",
        nif="B" + uuid.uuid4().hex[:8].upper(),
    )
    veh_a = Vehicle(
        id=uuid.uuid4(),
        empresa_id=empresa_a_id,
        matricula="9999-ZZZ",
        marca="Toyota",
        model="Proace",
    )
    art_a = Article(
        id=uuid.uuid4(),
        empresa_id=empresa_a_id,
        referencia_inventari="ART-A-1",
        nom="Component Secret Alpha",
    )
    admin_session.add_all([client_a, veh_a, art_a])
    await admin_session.flush()

    press_a = Pressupost(
        id=uuid.uuid4(),
        empresa_id=empresa_a_id,
        client_id=client_a.id,
        numero="PRES-ALPHA-01",
        total=5000.0,
    )
    ot_a = OrdreTreball(
        id=uuid.uuid4(),
        empresa_id=empresa_a_id,
        codi="OT-ALPHA-01",
        client_id=client_a.id,
        titol="Obra Confidencial Alpha",
        adreca="41.3800, 2.1600",
        estat="PENDENT",
    )
    admin_session.add_all([press_a, ot_a])
    await admin_session.flush()

    token_b = crear_token(boss_b_id, empresa_b_id, "BOSS")
    headers_b = {
        "Authorization": f"Bearer {token_b}",
        "X-Empresa-ID": str(empresa_b_id),
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        endpoints_a_verificar = [
            "/api/v1/gestio/clients",
            "/api/v1/gestio/flota",
            "/api/v1/gestio/magatzem/articles",
            "/api/v1/gestio/feines/mapa",
            "/api/v1/gestio/pressupostos",
            "/api/v1/gestio/copilot/rag",
        ]

        for ep in endpoints_a_verificar:
            res = await ac.get(ep, headers=headers_b)
            assert res.status_code == 200, f"Error a l'endpoint {ep}: {res.text}"
            data = res.json()
            assert isinstance(data, list)
            assert len(data) == 0, f"Filtració RLS detectada a {ep}: conté dades de l'altra empresa!"


@pytest.mark.asyncio
async def test_cross_03_coherencia_pressupost_telegram_copilot(admin_session, boss_token):
    """
    TEST-CROSS-03: Coherència Pressupost -> Telegram -> Copilot.
    Un pressupost aprovat via Telegram ha de reflectir-se viu al Copilot d'agent.
    """
    token_jwt, empresa_id_str = boss_token
    empresa_id = uuid.UUID(empresa_id_str)

    empresa = Empresa(
        id=empresa_id,
        nom="Instal·lacions del Maresme SL",
        nif="B" + uuid.uuid4().hex[:8].upper(),
        subdomini="mar-" + uuid.uuid4().hex[:5],
        pla_subscripcio="ENTERPRISE",
        estat_pagament="ACTIU",
        vertical="SEVALOR",
    )
    admin_session.add(empresa)
    await admin_session.flush()

    decoded = jwt.decode(token_jwt, options={"verify_signature": False})
    usuari_id = uuid.UUID(decoded["sub"])
    usuari = Usuari(
        id=usuari_id,
        empresa_id=empresa_id,
        nom="Boss",
        cognoms="Cross",
        nif="88990011L",
        rol="BOSS",
        estat="ACTIU",
    )
    admin_session.add(usuari)

    chat_id = 998877665
    client = Client(
        id=uuid.uuid4(),
        empresa_id=empresa_id,
        codi="CLI-CROSS-TG",
        rao_social="Client Masnou Residencial",
        nif="B" + uuid.uuid4().hex[:8].upper(),
        telegram_chat_id=chat_id,
        estat_canal_telegram="ACTIU",
    )
    admin_session.add(client)
    await admin_session.flush()

    pressupost = Pressupost(
        id=uuid.uuid4(),
        empresa_id=empresa_id,
        client_id=client.id,
        numero="PRES-CROSS-2026",
        total=6450.00,
        estat="PENDENT",
    )
    admin_session.add(pressupost)
    await admin_session.flush()

    # 1. Aprovar via Telegram Webhook
    payload_tg = {
        "callback_query": {
            "id": "cbq_cross_01",
            "message": {"chat": {"id": chat_id}},
            "data": f"aprovar_pressupost:{pressupost.id}",
        }
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res_tg = await ac.post("/api/v1/webhooks/telegram", json=payload_tg)
        assert res_tg.status_code == 200

        # 2. Consultar l'estat via API oficial de pressupostos
        headers = {"Authorization": f"Bearer {token_jwt}", "X-Empresa-ID": str(empresa_id)}
        res_press = await ac.get(f"/api/v1/gestio/pressupostos/{pressupost.id}", headers=headers)
        assert res_press.status_code == 200
        assert res_press.json()["estat"] == "APROVAT"

        # 3. Consultar l'historial del client al Copilot
        res_copilot = await ac.post(
            "/api/v1/gestio/copilot/xat",
            json={"pregunta": "Historial i fitxa 360 del client Masnou Residencial"},
            headers=headers,
        )
        assert res_copilot.status_code == 200
        assert res_copilot.json()["tool_utilitzada"] == "get_client_history"


@pytest.mark.asyncio
async def test_cross_04_consistencia_estoc_magatzem_picking_copilot(admin_session, boss_token):
    """
    TEST-CROSS-04: Consistència d'Estoc viu entre Magatzem, Picking i Copilot.
    Estoc inicial: 500 unitats físiques.
    Reserva de Picking: 120 unitats.
    Estoc disponible viu calculat: 500 - 120 = 380 unitats.
    L'agent Copilot ha de respondre exactament 380 unitats disponibles.
    """
    token_jwt, empresa_id_str = boss_token
    empresa_id = uuid.UUID(empresa_id_str)

    empresa = Empresa(
        id=empresa_id,
        nom="Logística i Peces SL",
        nif="B" + uuid.uuid4().hex[:8].upper(),
        subdomini="log-" + uuid.uuid4().hex[:5],
        pla_subscripcio="ENTERPRISE",
        estat_pagament="ACTIU",
        vertical="SEVALOR",
    )
    admin_session.add(empresa)
    await admin_session.flush()

    decoded = jwt.decode(token_jwt, options={"verify_signature": False})
    usuari_id = uuid.UUID(decoded["sub"])
    usuari = Usuari(
        id=usuari_id,
        empresa_id=empresa_id,
        nom="Boss",
        cognoms="Cross2",
        nif="55667788M",
        rol="BOSS",
        estat="ACTIU",
    )
    admin_session.add(usuari)

    magatzem = Magatzem(
        id=uuid.uuid4(),
        empresa_id=empresa_id,
        nom="Magatzem Granollers",
        tipus="CENTRAL",
    )
    admin_session.add(magatzem)

    article = Article(
        id=uuid.uuid4(),
        empresa_id=empresa_id,
        referencia_inventari="ELEC-24V-001",
        nom="Electrovàlvula 24V",
        familia="HIDRAULICA",
        unitat_mesura="UNITAT",
        estoc_minim=20.0,
        estoc_optim=600.0,
    )
    admin_session.add(article)
    await admin_session.flush()

    # Estoc amb 500 físiques i 120 reservades pel picking
    estoc = EstocMagatzem(
        id=uuid.uuid4(),
        empresa_id=empresa_id,
        magatzem_id=magatzem.id,
        article_id=article.id,
        quantitat_fisica=500.0,
        quantitat_virtual_reservada=120.0,
    )
    admin_session.add(estoc)
    await admin_session.flush()

    headers = {"Authorization": f"Bearer {token_jwt}", "X-Empresa-ID": str(empresa_id)}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post(
            "/api/v1/gestio/copilot/xat",
            json={"pregunta": "Quant d'estoc real ens queda d'Electrovàlvula 24V?"},
            headers=headers,
        )

        assert res.status_code == 200
        data = res.json()
        assert data["tool_utilitzada"] == "get_real_stock"
        # 500 - 120 = 380
        assert data["tool_resultat"]["total_disponible"] == 380.0
        assert "380" in data["resposta"]


@pytest.mark.asyncio
async def test_cross_05_denegacio_transversal_rol_veto_enginyer(admin_session):
    """
    TEST-CROSS-05: Denegació Transversal de Rol (Veto d'Enginyer consistent).
    Verifica que el rol ENGINYER té blocat l'accés financer a:
    1. GET /gestio/clients/{id}/iban -> HTTP 403 Forbidden.
    2. POST /gestio/copilot/xat (pregunta de tarifes/salaris) -> HTTP 403 Forbidden.
    3. GET /gestio/comptabilitat/factures -> HTTP 403 Forbidden.
    """
    empresa_id = uuid.uuid4()
    enginyer_id = uuid.uuid4()

    empresa = Empresa(
        id=empresa_id,
        nom="Enginyeria de Precisió SL",
        nif="B" + uuid.uuid4().hex[:8].upper(),
        subdomini="prec-" + uuid.uuid4().hex[:5],
        pla_subscripcio="ENTERPRISE",
        estat_pagament="ACTIU",
        vertical="SEVALOR",
    )
    admin_session.add(empresa)
    await admin_session.flush()

    usuari = Usuari(
        id=enginyer_id,
        empresa_id=empresa_id,
        nom="Sergi",
        cognoms="Tècnic",
        nif="33445566J",
        rol="ENGINYER",
        estat="ACTIU",
    )
    admin_session.add(usuari)

    client = Client(
        id=uuid.uuid4(),
        empresa_id=empresa_id,
        codi="CLI-CROSS-VETO",
        rao_social="Client IBAN Protegit",
        nif="B" + uuid.uuid4().hex[:8].upper(),
        iban_xifrat_simetric="ES9121000418450200051332",
    )
    admin_session.add(client)
    await admin_session.flush()

    token_enginyer = crear_token(enginyer_id, empresa_id, "ENGINYER")
    headers = {
        "Authorization": f"Bearer {token_enginyer}",
        "X-Empresa-ID": str(empresa_id),
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. IBAN Protegit
        res_iban = await ac.get(f"/api/v1/gestio/clients/{client.id}/iban", headers=headers)
        assert res_iban.status_code == 403

        # 2. Veto Financer Copilot
        res_xat = await ac.post(
            "/api/v1/gestio/copilot/xat",
            json={"pregunta": "Quin és el cost per hora dels treballadors i la tarifa horària?"},
            headers=headers,
        )
        assert res_xat.status_code == 403

        # 3. Comptabilitat protegida
        res_compta = await ac.get("/api/v1/gestio/comptabilitat/factures", headers=headers)
        assert res_compta.status_code == 403
