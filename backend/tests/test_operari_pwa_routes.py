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
async def test_feines_cap_de_colla_role(admin_session):
    """Verifica que un usuari amb rol CAP_DE_COLLA pugui consultar /operari/feines."""
    emp_id = uuid.uuid4()
    cap_id = uuid.uuid4()
    nif = "B" + str(uuid.uuid4())[:8].upper()

    empresa = Empresa(
        id=emp_id,
        nom="Empresa Colla Test",
        nif=nif,
        subdomini="colla-" + str(uuid.uuid4())[:6],
        pla_subscripcio="PRO",
        estat_pagament="ACTIU",
    )
    admin_session.add(empresa)
    await admin_session.flush()

    usuari = Usuari(
        id=cap_id,
        empresa_id=emp_id,
        nif=nif + "C",
        nom="Pau Baixa",
        rol="CAP_DE_COLLA",
        pin_hash="dummy_hash",
    )
    admin_session.add(usuari)
    await admin_session.flush()

    client = Client(
        id=uuid.uuid4(),
        empresa_id=emp_id,
        codi="CLI-COLLA-01",
        rao_social="Client Colla",
        nif="B99887766",
    )
    admin_session.add(client)
    await admin_session.flush()

    ot = OrdreTreball(
        id=uuid.uuid4(),
        empresa_id=emp_id,
        codi="OT-COLLA-1",
        client_id=client.id,
        titol="Instal·lació elèctrica nau industrial",
        estat="ASSIGNADA",
        adreca="Polígon Industrial 5",
        data_planificacio=date.today(),
        cap_de_colla_id=cap_id,
    )
    admin_session.add(ot)
    await admin_session.flush()

    token = _crear_token_operari(str(cap_id), str(emp_id), rol="CAP_DE_COLLA")
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Empresa-ID": str(emp_id),
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/api/v1/operari/feines", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert len(data) == 1
        assert data[0]["codi"] == "OT-COLLA-1"
        assert data[0]["client_nom"] == "Client Colla"



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


@pytest.mark.asyncio
async def test_operari_identificacio_and_public_cae_endpoint(admin_session):
    """Verifica l'endpoint autenticat /operari/identificacio i el públic /public/identificacio/{id}."""
    emp_id = uuid.uuid4()
    operari_id = uuid.uuid4()
    nif_empresa = "B" + str(uuid.uuid4())[:8].upper()
    nif_operari = "47" + str(uuid.uuid4())[:6].upper() + "Z"

    empresa = Empresa(
        id=emp_id,
        nom="Instal·lacions Elèctriques del Nord SL",
        nif=nif_empresa,
        subdomini="nord-" + str(uuid.uuid4())[:6],
        pla_subscripcio="PRO",
        estat_pagament="ACTIU",
        adreca="Carrer Major, 12, Girona",
    )
    admin_session.add(empresa)
    await admin_session.flush()

    usuari = Usuari(
        id=operari_id,
        empresa_id=emp_id,
        nif=nif_operari,
        nom="Marc",
        cognoms="Soler Roca",
        rol="OPERARI",
        pin_hash="pin_hash_1234",
    )
    admin_session.add(usuari)
    await admin_session.flush()

    token = _crear_token_operari(str(operari_id), str(emp_id), rol="OPERARI")
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Empresa-ID": str(emp_id),
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Sense autenticació a /operari/identificacio -> 401
        res_no_auth = await ac.get("/api/v1/operari/identificacio")
        assert res_no_auth.status_code == 401

        # 2. Amb autenticació a /operari/identificacio -> 200
        res_me = await ac.get("/api/v1/operari/identificacio", headers=headers)
        assert res_me.status_code == 200
        data_me = res_me.json()
        assert data_me["operari_id"] == str(operari_id)
        assert data_me["nom_complet"] == "Marc Soler Roca"
        assert data_me["nif"] == nif_operari
        assert data_me["empresa"]["nom"] == "Instal·lacions Elèctriques del Nord SL"
        assert f"/api/v1/public/identificacio/{operari_id}" in data_me["public_url"]
        assert len(data_me["validacions"]) >= 5
        titols = [v["titol"] for v in data_me["validacions"]]
        assert "Alta Seguretat Social" in titols
        assert "Certificat Mèdic d'Aptitud" in titols
        assert "Assegurança RC Empresarial" in titols

        # 3. Endpoint públic JSON per a l'escaneig de QR
        res_pub_json = await ac.get(f"/api/v1/public/identificacio/{operari_id}?format=json")
        assert res_pub_json.status_code == 200
        data_pub = res_pub_json.json()
        assert data_pub["operari_id"] == str(operari_id)
        assert data_pub["nom_complet"] == "Marc Soler Roca"
        assert data_pub["nif"] == nif_operari
        assert data_pub["empresa"]["nom"] == "Instal·lacions Elèctriques del Nord SL"
        assert len(data_pub["validacions"]) >= 5

        # 4. Endpoint públic HTML (visualització oficial per a inspectoria)
        res_pub_html = await ac.get(f"/api/v1/public/identificacio/{operari_id}")
        assert res_pub_html.status_code == 200
        assert "text/html" in res_pub_html.headers.get("content-type", "")
        html = res_pub_html.text
        assert "Marc Soler Roca" in html
        assert nif_operari in html
        assert "Instal·lacions Elèctriques del Nord SL" in html
        assert "Acreditació CAE Verificada" in html

        # 5. Operari inexistent -> 404
        bad_id = uuid.uuid4()
        res_bad = await ac.get(f"/api/v1/public/identificacio/{bad_id}")
        assert res_bad.status_code == 404

