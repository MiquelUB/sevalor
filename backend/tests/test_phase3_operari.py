import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession
import bcrypt

from app.main import app
from app.models.models import Usuari, Empresa, Vehicle, OrdreTreball, Client
from app.core.config import settings
from app.api.v1.gestio.operaris import hash_pin


@pytest.fixture
async def operari_pwa_setup(admin_session: AsyncSession):
    empresa_id = uuid.uuid4()
    empresa = Empresa(
        id=empresa_id,
        nom="Empresa PWA Camp",
        nif="B33445566",
        subdomini="pwacamp",
    )
    admin_session.add(empresa)
    await admin_session.flush()

    # Operari de camp
    operari_id = uuid.uuid4()
    operari_nif = "OPPWA01"
    operari_pin = "5678"
    operari = Usuari(
        id=operari_id,
        empresa_id=empresa_id,
        nif=operari_nif,
        nom="Joan Capataz",
        rol="CAP_DE_COLLA",
        pin_hash=hash_pin(operari_pin),
        pin_bloquejat=False,
        intents_pin_fallits=0,
    )
    admin_session.add(operari)

    # Boss d'oficina per a la torre de control
    boss_id = uuid.uuid4()
    boss = Usuari(
        id=boss_id,
        empresa_id=empresa_id,
        nif="77777777K",
        nom="Marta Boss",
        email="marta@pwacamp.com",
        password_hash=bcrypt.hashpw("Password123!".encode(), bcrypt.gensalt()).decode(),
        rol="BOSS",
    )
    admin_session.add(boss)
    await admin_session.flush()

    # Vehicle de la flota
    vehicle_id = uuid.uuid4()
    vehicle = Vehicle(
        id=vehicle_id,
        empresa_id=empresa_id,
        matricula="1234-XYZ",
        marca="Toyota",
        model="Hilux",
        estat="OPERATIU"
    )
    admin_session.add(vehicle)

    # Client
    client_id = uuid.uuid4()
    client = Client(
        id=client_id,
        empresa_id=empresa_id,
        codi="CLI-MAPA-01",
        rao_social="Finca Regants Ponent",
        nif="B11223399",
    )
    admin_session.add(client)
    await admin_session.flush()

    # Ordre de treball activa
    ordre_id = uuid.uuid4()
    ordre = OrdreTreball(
        id=ordre_id,
        empresa_id=empresa_id,
        client_id=client_id,
        codi="OT-2026-001",
        titol="Reparació Fuita PE-100",
        adreca="Camí Rural Sector 3",
        estat="EN_OBRA",
        cap_de_colla_id=operari_id,
        vehicle_id=vehicle_id,
    )
    admin_session.add(ordre)
    await admin_session.commit()

    await admin_session.commit()

    return {
        "empresa_id": str(empresa_id),
        "operari_nif": operari_nif,
        "operari_pin": operari_pin,
        "operari_id": str(operari_id),
        "boss_email": "marta@pwacamp.com",
        "password": "Password123!",
        "vehicle_id": str(vehicle_id),
    }


@pytest.mark.asyncio
async def test_operari_incidencies_dia0_i_creacio(operari_pwa_setup):
    """Verifica incidències Dia-0 (llista buida) i creació real via POST."""
    setup = operari_pwa_setup
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test/api/v1") as client:
        # Login de l'operari
        login_res = await client.post("/operari_auth/login", json={
            "nif": setup["operari_nif"],
            "pin": setup["operari_pin"]
        }, headers={"X-Empresa-ID": setup["empresa_id"]})
        assert login_res.status_code == 200
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}", "X-Empresa-ID": setup["empresa_id"]}

        # 1. Dia-0: llista buida
        res0 = await client.get("/operari/incidencies", headers=headers)
        assert res0.status_code == 200
        assert res0.json() == []

        # 2. Reportar incidència
        payload = {
            "ambit": "VEHICLE",
            "estat": "VERMELL",
            "text_observacions": "Punxada pneumàtic davanter dret al camí de grava",
            "foto_path": "/docs/fotos/pneumatic_punxat.webp"
        }
        create_res = await client.post("/operari/incidencies", json=payload, headers=headers)
        assert create_res.status_code == 201
        created = create_res.json()
        assert created["ambit"] == "VEHICLE"
        assert created["operari_id"] == setup["operari_id"]

        # 3. La llista ara retorna la incidència
        res1 = await client.get("/operari/incidencies", headers=headers)
        assert res1.status_code == 200
        assert len(res1.json()) == 1
        assert res1.json()[0]["text_observacions"] == "Punxada pneumàtic davanter dret al camí de grava"


@pytest.mark.asyncio
async def test_operari_tiquets_carburant_dia0_i_creacio(operari_pwa_setup):
    """Verifica tiquets de carburant Dia-0 (llista buida) i registre real amb fotos."""
    setup = operari_pwa_setup
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test/api/v1") as client:
        login_res = await client.post("/operari_auth/login", json={
            "nif": setup["operari_nif"],
            "pin": setup["operari_pin"]
        }, headers={"X-Empresa-ID": setup["empresa_id"]})
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}", "X-Empresa-ID": setup["empresa_id"]}

        # 1. Dia-0: sense tiquets
        res0 = await client.get("/operari/tiquets", headers=headers)
        assert res0.status_code == 200
        assert res0.json() == []

        # 2. Donar d'alta tiquet de carburant
        payload = {
            "vehicle_id": setup["vehicle_id"],
            "litres": 45.5,
            "import_euros": 68.25,
            "odometre_valor": 128950,
            "tiquet_foto_path": "/docs/tiquets/ticket_repostatge.webp",
            "odometre_foto_path": "/docs/tiquets/odometre_128950.webp"
        }
        create_res = await client.post("/operari/tiquets", json=payload, headers=headers)
        assert create_res.status_code == 201
        created = create_res.json()
        assert created["litres"] == 45.5
        assert created["import_euros"] == 68.25
        assert created["estat_ocr"] == "PENDENT_AUDITORIA"

        # 3. Llista ara conté el tiquet
        res1 = await client.get("/operari/tiquets", headers=headers)
        assert res1.status_code == 200
        assert len(res1.json()) == 1


@pytest.mark.asyncio
async def test_intervencions_actives_gis_i_marca(operari_pwa_setup):
    """Verifica l'endpoint /intervencions/actives del mapa GIS i /gestio/configuracio/marca."""
    setup = operari_pwa_setup
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test/api/v1") as client:
        boss_login = await client.post("/auth/login", json={
            "email": setup["boss_email"],
            "password": setup["password"]
        })
        token = boss_login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}", "X-Empresa-ID": setup["empresa_id"]}

        # 1. Intervencions actives pel mapa GIS
        map_res = await client.get("/intervencions/actives", headers=headers)
        assert map_res.status_code == 200
        intervencions = map_res.json()
        assert len(intervencions) == 1
        assert intervencions[0]["codi"] == "OT-2026-001"
        assert intervencions[0]["estat"] == "EN_OBRA"

        # 2. Marca camaleònica (GET /gestio/configuracio/marca)
        marca_res = await client.get("/gestio/configuracio/marca", headers=headers)
        assert marca_res.status_code == 200
        marca_data = marca_res.json()
        assert "primari_hsl" in marca_data
        assert "accent_hsl" in marca_data
