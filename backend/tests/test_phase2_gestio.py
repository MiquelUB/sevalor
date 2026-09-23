import uuid

import bcrypt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.models.models import Empresa, Usuari


@pytest.fixture
async def gestio_tenant_setup(admin_session: AsyncSession):
    empresa_id = uuid.uuid4()
    empresa = Empresa(
        id=empresa_id,
        nom="Empresa Gestio Real",
        nif="B12344321",
        subdomini="gestioreal",
    )
    admin_session.add(empresa)
    await admin_session.flush()

    boss_id = uuid.uuid4()
    boss = Usuari(
        id=boss_id,
        empresa_id=empresa_id,
        nif="88888888H",
        nom="Laia Directora",
        email="laia@gestioreal.com",
        password_hash=bcrypt.hashpw("Password123!".encode(), bcrypt.gensalt()).decode(),
        rol="BOSS",
    )
    admin_session.add(boss)

    enginyer_id = uuid.uuid4()
    enginyer = Usuari(
        id=enginyer_id,
        empresa_id=empresa_id,
        nif="99999999I",
        nom="Pol Enginyer",
        email="pol@gestioreal.com",
        password_hash=bcrypt.hashpw("Password123!".encode(), bcrypt.gensalt()).decode(),
        rol="ENGINYER",
    )
    admin_session.add(enginyer)
    await admin_session.commit()

    return {
        "empresa_id": str(empresa_id),
        "boss_email": "laia@gestioreal.com",
        "enginyer_email": "pol@gestioreal.com",
        "password": "Password123!",
    }


@pytest.mark.asyncio
async def test_clients_crud_dia0_i_alta(gestio_tenant_setup):
    """T2.1 & T2.2: Clients Dia-0 retorna [] i POST /gestio/clients crea el client real."""
    setup = gestio_tenant_setup
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test/api/v1") as client:
        login = await client.post("/auth/login", json={"email": setup["boss_email"], "password": setup["password"]})
        assert login.status_code == 200
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}", "X-Empresa-ID": setup["empresa_id"]}

        # 1. Dia-0: llista buida
        res0 = await client.get("/gestio/clients", headers=headers)
        assert res0.status_code == 200
        assert res0.json() == []

        # 2. Alta de nou client real
        payload = {
            "codi": "CLI-REAL-01",
            "rao_social": "Client Hidràulic del Bages S.L.",
            "nif": "B87654321",
            "telefon": "+34 938 000 111",
            "email": "contacte@clientbages.cat",
            "adreca_fiscal": "Polígon Els Dolors, Nau 4",
            "iban": "ES9121000418450200051332"
        }
        create_res = await client.post("/gestio/clients", json=payload, headers=headers)
        assert create_res.status_code == 201
        created = create_res.json()
        assert created["codi"] == "CLI-REAL-01"
        assert created["rao_social"] == "Client Hidràulic del Bages S.L."

        # 3. Llista ara conté 1 client
        res1 = await client.get("/gestio/clients", headers=headers)
        assert res1.status_code == 200
        assert len(res1.json()) == 1
        assert res1.json()[0]["codi"] == "CLI-REAL-01"


@pytest.mark.asyncio
async def test_magatzem_crud_dia0_i_alta(gestio_tenant_setup):
    """T2.3: Magatzem Dia-0 retorna [] i POST /gestio/magatzem/articles crea article real."""
    setup = gestio_tenant_setup
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test/api/v1") as client:
        login = await client.post("/auth/login", json={"email": setup["boss_email"], "password": setup["password"]})
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}", "X-Empresa-ID": setup["empresa_id"]}

        # 1. Dia-0: catàleg buit
        res0 = await client.get("/gestio/magatzem/articles", headers=headers)
        assert res0.status_code == 200
        assert res0.json() == []

        # 2. Alta d'article
        payload = {
            "referencia_inventari": "TUB-PE100-90",
            "nom": "Tub Polietilè PE-100 Ø90 PN16",
            "unitat_mesura": "METRES_LINEALS",
            "familia": "TUBERIA",
            "estoc_optim": 200.0,
            "estoc_minim": 50.0,
            "preu_cost": 4.50,
            "preu_venda": 8.20
        }
        create_res = await client.post("/gestio/magatzem/articles", json=payload, headers=headers)
        assert create_res.status_code == 201
        assert create_res.json()["referencia_inventari"] == "TUB-PE100-90"

        # 3. Llista ara conté 1 article
        res1 = await client.get("/gestio/magatzem/articles", headers=headers)
        assert res1.status_code == 200
        assert len(res1.json()) == 1


@pytest.mark.asyncio
async def test_comptabilitat_dia0_i_veto_enginyer(gestio_tenant_setup):
    """T2.4 & T2.5: Factures Dia-0 retorna [] i Enginyer rep HTTP 403 (Veto d'Enginyer)."""
    setup = gestio_tenant_setup
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test/api/v1") as client:
        # 1. Boss accedeix a comptabilitat Dia-0 -> 200 []
        boss_login = await client.post("/auth/login", json={"email": setup["boss_email"], "password": setup["password"]})
        boss_token = boss_login.json()["access_token"]
        boss_headers = {"Authorization": f"Bearer {boss_token}", "X-Empresa-ID": setup["empresa_id"]}

        res_boss = await client.get("/gestio/comptabilitat/factures", headers=boss_headers)
        assert res_boss.status_code == 200
        assert res_boss.json() == []

        # 2. Enginyer intenta accedir a comptabilitat -> 403 Forbidden (Veto d'Enginyer Spec 001/007)
        eng_login = await client.post("/auth/login", json={"email": setup["enginyer_email"], "password": setup["password"]})
        eng_token = eng_login.json()["access_token"]
        eng_headers = {"Authorization": f"Bearer {eng_token}", "X-Empresa-ID": setup["empresa_id"]}

        res_eng = await client.get("/gestio/comptabilitat/factures", headers=eng_headers)
        assert res_eng.status_code == 403, "L'Enginyer hauria de rebre 403 Forbidden per Veto d'Enginyer!"


@pytest.mark.asyncio
async def test_notificacions_converses_dia0_i_creacio(gestio_tenant_setup):
    """T2.6: Notificacions Dia-0 retorna [] i permet crear conversa un cop creat un client."""
    setup = gestio_tenant_setup
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test/api/v1") as client:
        boss_login = await client.post("/auth/login", json={"email": setup["boss_email"], "password": setup["password"]})
        boss_token = boss_login.json()["access_token"]
        headers = {"Authorization": f"Bearer {boss_token}", "X-Empresa-ID": setup["empresa_id"]}

        # 1. Dia-0 converses
        res0 = await client.get("/gestio/notificacions/converses", headers=headers)
        assert res0.status_code == 200
        assert res0.json() == []

        # 2. Crear client necessari per a la conversa
        cl_res = await client.post("/gestio/clients", json={
            "codi": "CLI-CONV-01",
            "rao_social": "Client Notificacions SL",
            "nif": "B99881122"
        }, headers=headers)
        client_id = cl_res.json()["id"]

        # 3. Crear conversa
        conv_res = await client.post("/gestio/notificacions/converses", json={
            "client_id": client_id,
            "titol": "Incidència Avaria Sector 2"
        }, headers=headers)
        assert conv_res.status_code == 201
        conversa_id = conv_res.json()["id"]

        # 4. Enviar missatge a la conversa
        msg_res = await client.post(f"/gestio/notificacions/converses/{conversa_id}/missatges", json={
            "remitent": "OFICINA",
            "canal": "WEB_PWA",
            "contingut_text": "Hem enviat la brigada de guàrdia."
        }, headers=headers)
        assert msg_res.status_code == 201

        # 5. Obtenir missatges de la conversa
        msgs = await client.get(f"/gestio/notificacions/converses/{conversa_id}/missatges", headers=headers)
        assert msgs.status_code == 200
        assert len(msgs.json()) == 1
        assert msgs.json()[0]["contingut_text"] == "Hem enviat la brigada de guàrdia."


@pytest.mark.asyncio
async def test_planols_carpetes_dia0_i_alta(gestio_tenant_setup):
    """T2.7: Plànols Dia-0 retorna [] i permet crear carpetes i plànols."""
    setup = gestio_tenant_setup
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test/api/v1") as client:
        boss_login = await client.post("/auth/login", json={"email": setup["boss_email"], "password": setup["password"]})
        boss_token = boss_login.json()["access_token"]
        headers = {"Authorization": f"Bearer {boss_token}", "X-Empresa-ID": setup["empresa_id"]}

        # 1. Dia-0 carpetes i plànols
        res_c0 = await client.get("/gestio/planols/carpetes", headers=headers)
        assert res_c0.status_code == 200
        assert res_c0.json() == []

        res_p0 = await client.get("/gestio/planols", headers=headers)
        assert res_p0.status_code == 200
        assert res_p0.json() == []

        # 2. Crear carpeta
        carp_res = await client.post("/gestio/planols/carpetes", json={
            "nom": "Sector Xarxa Nord",
            "categoria": "INFRAESTRUCTURA_COMUNITARIA",
            "municipi": "Manresa"
        }, headers=headers)
        assert carp_res.status_code == 201
        carpeta_id = carp_res.json()["id"]

        # 3. Crear plànol dins la carpeta
        plan_res = await client.post("/gestio/planols", json={
            "carpeta_id": carpeta_id,
            "titol": "Traçat Arterial PE-100 Ø160",
            "codi_referencia": "PLN-2026-001",
            "tipus_fitxer": "DXF",
            "es_georeferenciat": True,
            "projeccio": "ETRS89 / UTM 31N"
        }, headers=headers)
        assert plan_res.status_code == 201
        assert plan_res.json()["codi_referencia"] == "PLN-2026-001"
