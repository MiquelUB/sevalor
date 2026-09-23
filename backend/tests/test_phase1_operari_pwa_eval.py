import os
import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.main import app
from app.api.v1.gestio.operaris import hash_pin
from app.models.models import Empresa, Usuari, Client, OrdreTreball, FullaPicking, LiniaPicking, Article

@pytest.fixture
async def operari_f1_setup(admin_session: AsyncSession):
    """Configuració dinàmica per avaluar la Fase 1 (sense mocks ni dades hardcoded)."""
    operari_pin = "1234"
    operari_nif = f"NIF{uuid.uuid4().hex[:5].upper()}"

    # 1. Crear Empresa
    emp_id = uuid.uuid4()
    empresa = Empresa(
        id=emp_id,
        nom=f"Empresa Operari F1 {emp_id.hex[:6]}",
        subdomini=f"opf1-{emp_id.hex[:6]}",
        nif=f"A{emp_id.hex[:8].upper()}"
    )
    admin_session.add(empresa)
    await admin_session.flush()

    # 2. Crear Operari
    operari_id = uuid.uuid4()
    operari = Usuari(
        id=operari_id,
        empresa_id=emp_id,
        nom="Jordi Operari",
        email=f"jordi.{emp_id.hex[:6]}@sevalortest.com",
        pin_hash=hash_pin(operari_pin),
        pin_bloquejat=False,
        intents_pin_fallits=0,
        rol="OPERARI",
        nif=operari_nif
    )
    admin_session.add(operari)

    # 3. Crear Client i Ordre de Treball
    client_id = uuid.uuid4()
    client_db = Client(
        id=client_id,
        empresa_id=emp_id,
        rao_social="Finca Agrícola S.L.",
        codi=f"CLI-{emp_id.hex[:4]}",
        nif=f"B{emp_id.hex[:8].upper()}"
    )
    admin_session.add(client_db)
    await admin_session.flush()

    ot_id = uuid.uuid4()
    ordre = OrdreTreball(
        id=ot_id,
        empresa_id=emp_id,
        client_id=client_id,
        codi=f"OT-{emp_id.hex[:4]}",
        titol="Manteniment canonada reg",
        adreca="41.3851, 2.1734",
        estat="PENDENT",
        cap_de_colla_id=operari_id
    )
    admin_session.add(ordre)

    # 4. Crear Article i Fulla de Picking
    art_id = uuid.uuid4()
    article = Article(
        id=art_id,
        empresa_id=emp_id,
        nom="Tub PVC 32mm",
        referencia_inventari=f"TUB-{emp_id.hex[:4]}",
        familia="FONTANERIA"
    )
    admin_session.add(article)
    await admin_session.flush()

    picking_id = uuid.uuid4()
    picking = FullaPicking(
        id=picking_id,
        empresa_id=emp_id,
        ordre_treball_id=ot_id,
        estat_picking="PENDENT"
    )
    admin_session.add(picking)
    await admin_session.flush()

    linia_id = uuid.uuid4()
    linia = LiniaPicking(
        id=linia_id,
        empresa_id=emp_id,
        picking_id=picking_id,
        article_id=art_id,
        quantitat_prevista=10.0,
        quantitat_carregada_pick_in=0.0,
        quantitat_retornada_pick_out=0.0
    )
    admin_session.add(linia)
    await admin_session.commit()

    return {
        "empresa_id": str(emp_id),
        "operari_id": str(operari_id),
        "operari_nif": operari_nif,
        "operari_pin": operari_pin,
        "ot_id": str(ot_id),
        "linia_id": str(linia_id)
    }

@pytest.mark.asyncio
async def test_f1_01_incidencia_multipart_i_buit(operari_f1_setup):
    """TEST-F1-01: Endpoint d'incidències accepta multipart i crea fitxer real."""
    setup = operari_f1_setup
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test/api/v1") as client:
        # Login Operari PWA
        res_login = await client.post(
            "/operari_auth/login",
            json={"nif": setup["operari_nif"], "pin": setup["operari_pin"]},
            headers={"X-Empresa-ID": setup["empresa_id"]}
        )
        assert res_login.status_code == 200, f"Login PWA fallat: {res_login.text}"
        token = res_login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}", "X-Empresa-ID": setup["empresa_id"]}

        # Reportar incidència amb àudio multipart (memòria)
        files = {
            "audio": ("incidencia.webm", b"AUDIO_SAMPLE_DATA_BINARY", "audio/webm")
        }
        data = {
            "ambit": "TASCA",
            "estat": "VERMELL",
            "text_observacions": "Incidència detectada en camp",
            "ordre_treball_id": setup["ot_id"]
        }
        res = await client.post("/operari/incidencies", data=data, files=files, headers=headers)
        assert res.status_code == 201, f"Error creant incidència: {res.text}"
        res_data = res.json()
        assert res_data["audio_path"] is not None
        assert os.path.exists(res_data["audio_path"])
        assert res_data["ambit"] == "TASCA"
        assert res_data["estat"] == "VERMELL"

@pytest.mark.asyncio
async def test_f1_02_fitxatge_gps_i_timestamp(operari_f1_setup):
    """TEST-F1-02: Fitxatge registra geolocalització i estat EN_CURS."""
    setup = operari_f1_setup
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test/api/v1") as client:
        res_login = await client.post(
            "/operari_auth/login",
            json={"nif": setup["operari_nif"], "pin": setup["operari_pin"]},
            headers={"X-Empresa-ID": setup["empresa_id"]}
        )
        token = res_login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}", "X-Empresa-ID": setup["empresa_id"]}

        # Iniciar Jornada
        res_inici = await client.post(
            "/operari/jornada/inici",
            json={"geolocalitzacio": "41.3879,2.1699"},
            headers=headers
        )
        assert res_inici.status_code == 201
        jornada_data = res_inici.json()
        assert jornada_data["estat"] == "EN_CURS"
        assert jornada_data["geolocalitzacio_inici"] == "41.3879,2.1699"

        # Finalitzar Jornada
        j_id = jornada_data["id"]
        res_fi = await client.post(
            f"/operari/jornada/{j_id}/fi",
            json={"geolocalitzacio": "41.3880,2.1700"},
            headers=headers
        )
        assert res_fi.status_code == 200
        assert res_fi.json()["estat"] == "COMPLERT"

@pytest.mark.asyncio
async def test_f1_03_empty_state_dia0(admin_session: AsyncSession):
    """TEST-F1-03: Empresa nova sense dades retorna llista buida [] (Zero Mock Data)."""
    emp_id = uuid.uuid4()
    empresa = Empresa(id=emp_id, nom="Nova Empresa Dia0", subdomini=f"dia0-{emp_id.hex[:6]}", nif=f"D{emp_id.hex[:8].upper()}")
    admin_session.add(empresa)
    await admin_session.flush()

    usr_pin = "5555"
    usr_nif = f"NIF{uuid.uuid4().hex[:5].upper()}"
    usr = Usuari(
        id=uuid.uuid4(),
        empresa_id=emp_id,
        nom="Operari Nou",
        pin_hash=hash_pin(usr_pin),
        pin_bloquejat=False,
        intents_pin_fallits=0,
        rol="OPERARI",
        nif=usr_nif
    )
    admin_session.add(usr)
    await admin_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test/api/v1") as client:
        res_login = await client.post(
            "/operari_auth/login",
            json={"nif": usr_nif, "pin": usr_pin},
            headers={"X-Empresa-ID": str(emp_id)}
        )
        assert res_login.status_code == 200
        token = res_login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}", "X-Empresa-ID": str(emp_id)}

        res_feines = await client.get("/operari/feines", headers=headers)
        assert res_feines.status_code == 200
        assert res_feines.json() == []

        res_inci = await client.get("/operari/incidencies", headers=headers)
        assert res_inci.status_code == 200
        assert res_inci.json() == []

@pytest.mark.asyncio
async def test_f1_04_protocol_3_fotos_i_bloqueig(operari_f1_setup):
    """TEST-F1-04: Bloqueig de finalització mentre falten fotos, i desbloqueig amb 3/3."""
    setup = operari_f1_setup
    ot_id = setup["ot_id"]
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test/api/v1") as client:
        res_login = await client.post(
            "/operari_auth/login",
            json={"nif": setup["operari_nif"], "pin": setup["operari_pin"]},
            headers={"X-Empresa-ID": setup["empresa_id"]}
        )
        token = res_login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}", "X-Empresa-ID": setup["empresa_id"]}

        # 1. Intentar finalitzar sense fotos -> HTTP 400
        res_fail = await client.put(f"/operari/feines/{ot_id}/finalitzar", headers=headers)
        assert res_fail.status_code == 400
        assert "Falten fotografies requerides" in res_fail.json()["detail"]

        # 2. Pujar Foto 1: INICIAL
        res_f1 = await client.post(f"/operari/feines/{ot_id}/fotos", data={"tipus": "INICIAL"}, headers=headers)
        assert res_f1.status_code == 200

        # Comprovar estat intermedi: només 1 de 3
        res_status1 = await client.get(f"/operari/feines/{ot_id}/fotos", headers=headers)
        assert res_status1.json()["protocol_complet"] is False

        # 3. Pujar Foto 2: INTERMEDIA
        res_f2 = await client.post(f"/operari/feines/{ot_id}/fotos", data={"tipus": "INTERMEDIA"}, headers=headers)
        assert res_f2.status_code == 200

        # 4. Pujar Foto 3: FINAL
        res_f3 = await client.post(f"/operari/feines/{ot_id}/fotos", data={"tipus": "FINAL"}, headers=headers)
        assert res_f3.status_code == 200

        # Comprovar estat complet: 3 de 3
        res_status2 = await client.get(f"/operari/feines/{ot_id}/fotos", headers=headers)
        assert res_status2.json()["protocol_complet"] is True

        # 5. Ara finalitzar ha de tenir èxit -> HTTP 200
        res_done = await client.put(f"/operari/feines/{ot_id}/finalitzar", headers=headers)
        assert res_done.status_code == 200
        assert res_done.json()["estat"] == "COMPLERT"

@pytest.mark.asyncio
async def test_f1_05_balanc_materials_picking(operari_f1_setup):
    """TEST-F1-05: Balanç de materials Consum Real = Pick In - Pick Out (Spec 013 RF-18)."""
    setup = operari_f1_setup
    linia_id = setup["linia_id"]
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test/api/v1") as client:
        res_login = await client.post(
            "/operari_auth/login",
            json={"nif": setup["operari_nif"], "pin": setup["operari_pin"]},
            headers={"X-Empresa-ID": setup["empresa_id"]}
        )
        token = res_login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}", "X-Empresa-ID": setup["empresa_id"]}

        # Actualitzar línia de picking: 8 carregats (pick-in), 2 retornats (pick-out)
        payload = {
            "quantitat_carregada_pick_in": 8.0,
            "quantitat_retornada_pick_out": 2.0
        }
        res = await client.put(f"/operari/picking/linies/{linia_id}", json=payload, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["quantitat_carregada_pick_in"] == 8.0
        assert data["quantitat_retornada_pick_out"] == 2.0
        # Consum Real = 8.0 - 2.0 = 6.0
        assert data["consum_real"] == 6.0

@pytest.mark.asyncio
async def test_f1_06_iniciar_trajecte_i_geovalla(operari_f1_setup):
    """TEST-F1-06: Iniciar Trajecte (ETA 25m) i Geovalla d'Obra (>50m)."""
    setup = operari_f1_setup
    ot_id = setup["ot_id"]
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test/api/v1") as client:
        res_login = await client.post(
            "/operari_auth/login",
            json={"nif": setup["operari_nif"], "pin": setup["operari_pin"]},
            headers={"X-Empresa-ID": setup["empresa_id"]}
        )
        token = res_login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}", "X-Empresa-ID": setup["empresa_id"]}

        # 1. Iniciar Trajecte (Spec 013 RF-11)
        res_trajecte = await client.put(f"/operari/feines/{ot_id}/iniciar-trajecte", headers=headers)
        assert res_trajecte.status_code == 200
        assert res_trajecte.json()["eta_minuts"] == 25
        assert res_trajecte.json()["estat_vehicle"] == "EN_TRANSIT"

        # 2. Començar Feina a 5km de distància (adreça és 41.3851, 2.1734) -> HTTP 400 Geovalla (Spec 013 RF-12.1)
        res_geo_fail = await client.put(
            f"/operari/feines/{ot_id}/comencar",
            json={"lat": 41.4200, "lng": 2.2000, "desviacio_justificada": False},
            headers=headers
        )
        assert res_geo_fail.status_code == 400
        assert "Geovalla d'obra superada" in res_geo_fail.json()["detail"]

        # 3. Començar Feina a distància < 50m (ex: a 5 metres) -> HTTP 200 EN_CURS
        res_geo_ok = await client.put(
            f"/operari/feines/{ot_id}/comencar",
            json={"lat": 41.3851, "lng": 2.1734, "desviacio_justificada": False},
            headers=headers
        )
        assert res_geo_ok.status_code == 200
        assert res_geo_ok.json()["estat"] == "EN_CURS"
