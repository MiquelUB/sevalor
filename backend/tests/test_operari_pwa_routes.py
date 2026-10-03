import uuid
from datetime import date, datetime, timedelta, timezone

import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.main import app
from app.models.models import (
    Article,
    CapaAnotacio,
    Client,
    Empresa,
    EstocMagatzem,
    FullaPicking,
    LiniaPicking,
    Magatzem,
    OrdreTreball,
    Usuari,
    Vehicle,
)


def _crear_token_operari(usuari_id: str, empresa_id: str, rol: str = "OPERARI") -> str:
    payload = {
        "sub": usuari_id,
        "rol": rol,
        "empresa_id": empresa_id,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


@pytest.mark.asyncio
async def test_feines_and_alias_route(admin_session):
    """Verifica que tant /operari/feines com /operari_pwa/feines retornin les feines assignades."""
    emp_id = uuid.uuid4()
    operari_id = uuid.uuid4()
    nif = "B" + str(uuid.uuid4())[:8].upper()

    empresa = Empresa(
        id=emp_id,
        nom="Empresa Feines Test",
        nif=nif,
        subdomini="feines-" + str(uuid.uuid4())[:6],
        pla_subscripcio="PRO",
        estat_pagament="ACTIU",
    )
    admin_session.add(empresa)
    await admin_session.flush()

    usuari = Usuari(
        id=operari_id,
        empresa_id=emp_id,
        nif=nif + "O",
        nom="Operari Joan",
        rol="OPERARI",
        pin_hash="dummy_hash",
    )
    admin_session.add(usuari)
    await admin_session.flush()

    client = Client(
        id=uuid.uuid4(),
        empresa_id=emp_id,
        codi="CLI-01",
        rao_social="Client Feines",
        nif="B87654321",
    )
    admin_session.add(client)
    await admin_session.flush()

    ot = OrdreTreball(
        id=uuid.uuid4(),
        empresa_id=emp_id,
        codi="OT-FEINES-1",
        client_id=client.id,
        titol="Instal·lació de reg sector 4",
        estat="PENDENT",
        adreca="Camí Ral 10",
        data_planificacio=date.today(),
        cap_de_colla_id=operari_id,
    )
    admin_session.add(ot)
    await admin_session.flush()

    token = _crear_token_operari(str(operari_id), str(emp_id), rol="OPERARI")
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Empresa-ID": str(emp_id),
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Ruta estàndard
        res1 = await ac.get("/api/v1/operari/feines", headers=headers)
        assert res1.status_code == 200
        data1 = res1.json()
        assert len(data1) == 1
        assert data1[0]["codi"] == "OT-FEINES-1"

        # Ruta àlies per a compatibilitat PWA
        res2 = await ac.get("/api/v1/operari_pwa/feines", headers=headers)
        assert res2.status_code == 200
        data2 = res2.json()
        assert len(data2) == 1
        assert data2[0]["codi"] == "OT-FEINES-1"


@pytest.mark.asyncio
async def test_materials_and_alias_route(admin_session):
    """Verifica que tant /operari/materials com /materials/operari retornin els materials de picking."""
    emp_id = uuid.uuid4()
    operari_id = uuid.uuid4()
    nif = "B" + str(uuid.uuid4())[:8].upper()

    empresa = Empresa(
        id=emp_id,
        nom="Empresa Materials Test",
        nif=nif,
        subdomini="mat-" + str(uuid.uuid4())[:6],
        pla_subscripcio="PRO",
        estat_pagament="ACTIU",
    )
    admin_session.add(empresa)
    await admin_session.flush()

    usuari = Usuari(
        id=operari_id,
        empresa_id=emp_id,
        nif=nif + "O",
        nom="Operari Materials",
        rol="OPERARI",
        pin_hash="dummy_hash",
    )
    admin_session.add(usuari)
    await admin_session.flush()

    client = Client(
        id=uuid.uuid4(),
        empresa_id=emp_id,
        codi="CLI-02",
        rao_social="Client Materials",
        nif="B87654322",
    )
    admin_session.add(client)
    await admin_session.flush()

    ot = OrdreTreball(
        id=uuid.uuid4(),
        empresa_id=emp_id,
        codi="OT-MAT-1",
        client_id=client.id,
        titol="Manteniment canonada",
        estat="PENDENT",
        adreca="Polígon Sud",
    )
    admin_session.add(ot)
    await admin_session.flush()

    art = Article(
        id=uuid.uuid4(),
        empresa_id=emp_id,
        referencia_inventari="TUB-PE-32",
        nom="Tub Polietilè 32mm",
        unitat_mesura="METRES_LINEALS",
        es_material_continu=True,
        familia="CANONADES",
    )
    admin_session.add(art)
    await admin_session.flush()

    picking = FullaPicking(
        id=uuid.uuid4(),
        empresa_id=emp_id,
        ordre_treball_id=ot.id,
        estat_picking="PENDENT",
    )
    admin_session.add(picking)
    await admin_session.flush()

    linia = LiniaPicking(
        id=uuid.uuid4(),
        empresa_id=emp_id,
        picking_id=picking.id,
        article_id=art.id,
        quantitat_prevista=50.0,
        quantitat_carregada_pick_in=0.0,
        quantitat_retornada_pick_out=0.0,
    )
    admin_session.add(linia)
    await admin_session.flush()

    token = _crear_token_operari(str(operari_id), str(emp_id), rol="OPERARI")
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Empresa-ID": str(emp_id),
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # /api/v1/operari/materials
        res1 = await ac.get("/api/v1/operari/materials", headers=headers)
        assert res1.status_code == 200
        data1 = res1.json()
        assert len(data1) == 1
        assert data1[0]["nom"] == "Tub Polietilè 32mm"
        assert data1[0]["quantitat_programada"] == 50.0
        assert data1[0]["format_continu"] is True

        # /api/v1/materials/operari
        res2 = await ac.get("/api/v1/materials/operari", headers=headers)
        assert res2.status_code == 200
        data2 = res2.json()
        assert len(data2) == 1
        assert data2[0]["referencia"] == "TUB-PE-32"


@pytest.mark.asyncio
async def test_vehicles_stock_and_alias_route(admin_session):
    """Verifica que tant /operari/vehicles/stock com /operari_pwa/vehicles/stock retornin l'estoc."""
    emp_id = uuid.uuid4()
    operari_id = uuid.uuid4()
    nif = "B" + str(uuid.uuid4())[:8].upper()

    empresa = Empresa(
        id=emp_id,
        nom="Empresa Vehicles Stock Test",
        nif=nif,
        subdomini="vstock-" + str(uuid.uuid4())[:6],
        pla_subscripcio="PRO",
        estat_pagament="ACTIU",
    )
    admin_session.add(empresa)
    await admin_session.flush()

    usuari = Usuari(
        id=operari_id,
        empresa_id=emp_id,
        nif=nif + "O",
        nom="Operari Furgoneta",
        rol="OPERARI",
        pin_hash="dummy_hash",
    )
    admin_session.add(usuari)
    await admin_session.flush()

    veh = Vehicle(
        id=uuid.uuid4(),
        empresa_id=emp_id,
        matricula="5678BCD",
        marca="Renault",
        model="Master",
        estat="OPERATIU",
    )
    admin_session.add(veh)
    await admin_session.flush()

    mag = Magatzem(
        id=uuid.uuid4(),
        empresa_id=emp_id,
        nom="Furgoneta 5678BCD",
        tipus="FURGONETA",
        vehicle_id=veh.id,
    )
    admin_session.add(mag)
    await admin_session.flush()

    art = Article(
        id=uuid.uuid4(),
        empresa_id=emp_id,
        referencia_inventari="BRIDA-100",
        nom="Brida niló 100mm",
        unitat_mesura="UNITAT",
        estoc_optim=100.0,
        familia="FIXACIO",
    )
    admin_session.add(art)
    await admin_session.flush()

    estoc = EstocMagatzem(
        id=uuid.uuid4(),
        empresa_id=emp_id,
        article_id=art.id,
        magatzem_id=mag.id,
        quantitat_fisica=45.0,
    )
    admin_session.add(estoc)
    await admin_session.flush()

    token = _crear_token_operari(str(operari_id), str(emp_id), rol="OPERARI")
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Empresa-ID": str(emp_id),
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # /api/v1/operari/vehicles/stock
        res1 = await ac.get("/api/v1/operari/vehicles/stock", headers=headers)
        assert res1.status_code == 200
        data1 = res1.json()
        assert len(data1) == 1
        assert data1[0]["nom"] == "Brida niló 100mm"
        assert data1[0]["quantitat_actual"] == 45.0
        assert data1[0]["quantitat_optima"] == 100.0

        # /api/v1/operari_pwa/vehicles/stock
        res2 = await ac.get("/api/v1/operari_pwa/vehicles/stock", headers=headers)
        assert res2.status_code == 200
        data2 = res2.json()
        assert len(data2) == 1
        assert data2[0]["referencia"] == "BRIDA-100"


@pytest.mark.asyncio
async def test_planols_and_alias_route(admin_session):
    """Verifica que tant /operari/planols com /planols/operari retornin les capes d'anotació."""
    emp_id = uuid.uuid4()
    operari_id = uuid.uuid4()
    nif = "B" + str(uuid.uuid4())[:8].upper()

    empresa = Empresa(
        id=emp_id,
        nom="Empresa Planols Test",
        nif=nif,
        subdomini="planols-" + str(uuid.uuid4())[:6],
        pla_subscripcio="PRO",
        estat_pagament="ACTIU",
    )
    admin_session.add(empresa)
    await admin_session.flush()

    usuari = Usuari(
        id=operari_id,
        empresa_id=emp_id,
        nif=nif + "O",
        nom="Operari Dibuix",
        rol="OPERARI",
        pin_hash="dummy_hash",
    )
    admin_session.add(usuari)
    await admin_session.flush()

    client = Client(
        id=uuid.uuid4(),
        empresa_id=emp_id,
        codi="CLI-03",
        rao_social="Client Plànols",
        nif="B87654323",
    )
    admin_session.add(client)
    await admin_session.flush()

    ot = OrdreTreball(
        id=uuid.uuid4(),
        empresa_id=emp_id,
        codi="OT-PLANOL-1",
        client_id=client.id,
        titol="Plànol topogràfic obra",
        estat="PENDENT",
        adreca="Av. Catalunya 4",
    )
    admin_session.add(ot)
    await admin_session.flush()

    capa = CapaAnotacio(
        id=uuid.uuid4(),
        empresa_id=emp_id,
        ordre_treball_id=ot.id,
        nom_capa="Capa Acometida Elèctrica",
        fitxer_vectorial_path="/docs/capes/capa_1.geojson",
        operari_id=operari_id,
        estat_capa="ACTIVA",
    )
    admin_session.add(capa)
    await admin_session.flush()

    token = _crear_token_operari(str(operari_id), str(emp_id), rol="OPERARI")
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Empresa-ID": str(emp_id),
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # /api/v1/operari/planols
        res1 = await ac.get("/api/v1/operari/planols", headers=headers)
        assert res1.status_code == 200
        data1 = res1.json()
        assert len(data1) == 1
        assert data1[0]["nom"] == "Capa Acometida Elèctrica"
        assert data1[0]["es_tancada"] is False

        # /api/v1/planols/operari
        res2 = await ac.get("/api/v1/planols/operari", headers=headers)
        assert res2.status_code == 200
        data2 = res2.json()
        assert len(data2) == 1
        assert data2[0]["id"] == str(capa.id)


@pytest.mark.asyncio
async def test_superadmin_segregation_on_marca(admin_session):
    """Verifica que un Superadmin no pugui cridar /gestio/configuracio/marca (Zero-Trust Segregation 403)."""
    superadmin_payload = {
        "sub": str(uuid.uuid4()),
        "email": "superadmin@sevalor.com",
        "is_superadmin": True,
        "rol": "SUPERADMIN",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
    }
    sa_token = jwt.encode(superadmin_payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    sa_headers = {"Authorization": f"Bearer {sa_token}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/api/v1/gestio/configuracio/marca", headers=sa_headers)
        # Haurà de retornar 403 Forbidden per mandat Zero-Trust
        assert res.status_code == 403
        assert "Zero-Trust Segregation" in res.json().get("detail", "")
