"""
Tests d'Integració Pas 1: Validació de la Persistència Integral de la PWA
cap a PostgreSQL 16 (amb RLS) i al Disc Dur Sobirà del Client (SovereignStorageGateway).
Complint estrictament la normativa Zero Mock i l'Auditoria de Tests Backend.
"""

import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.main import app
from app.models.models import (
    Article,
    CarpetaPlanol,
    Client,
    Empresa,
    FullaPicking,
    LiniaPicking,
    OrdreTreball,
    PlanolBase,
    RegistreJornadaLaboral,
    TiquetCarburant,
    Usuari,
    Vehicle,
)


@pytest.fixture
async def setup_pas1_operari(admin_session: AsyncSession, tmp_path: Path):
    """Configuració aïllada amb Empresa, Disc Dur dedicat i Operari."""
    empresa_id = uuid.uuid4()
    operari_id = uuid.uuid4()
    disc_client = tmp_path / f"disc_client_{empresa_id.hex[:6]}"
    disc_client.mkdir(parents=True, exist_ok=True)

    empresa = Empresa(
        id=empresa_id,
        nom=f"Empresa Test Pas 1 {empresa_id.hex[:4]}",
        nif=f"B{empresa_id.hex[:8].upper()}",
        subdomini=f"pas1-{empresa_id.hex[:6]}",
        disc_dur_url=str(disc_client),
        node_ia_actiu=True,
    )
    admin_session.add(empresa)

    operari = Usuari(
        id=operari_id,
        empresa_id=empresa_id,
        nom="Joan Operari",
        cognoms="Garcia",
        nif=f"NIF{operari_id.hex[:5].upper()}",
        email=f"joan.{operari_id.hex[:4]}@sevalor.cat",
        rol="OPERARI",
        estat="ACTIU",
    )
    admin_session.add(operari)
    await admin_session.commit()

    payload = {
        "sub": str(operari_id),
        "rol": "OPERARI",
        "empresa_id": str(empresa_id),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=60),
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Empresa-ID": str(empresa_id),
    }

    return {
        "empresa_id": empresa_id,
        "operari_id": operari_id,
        "disc_client": disc_client,
        "headers": headers,
    }


@pytest.mark.asyncio
async def test_pas1_01_jornada_i_vehicle_al_disc_client(setup_pas1_operari, admin_session: AsyncSession):
    """TEST-PAS1-01: Fitxatge de jornada i assignació de vehicle persisteixen a PostgreSQL i al disc dur."""
    setup = setup_pas1_operari
    headers = setup["headers"]
    disc: Path = setup["disc_client"]
    empresa_id: uuid.UUID = setup["empresa_id"]
    operari_id: uuid.UUID = setup["operari_id"]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test/api/v1") as client:
        # 1. Iniciar Jornada
        res_inici = await client.post(
            "/operari/jornada/inici",
            json={"latitud": 41.3851, "longitud": 2.1734},
            headers=headers,
        )
        assert res_inici.status_code == 201, res_inici.text
        jornada_id = res_inici.json()["id"]

        # Comprovar disc dur: 08_flota_i_operaris/registres_jornada/<id>.json
        fitxa_jornada = disc / "08_flota_i_operaris" / "registres_jornada" / f"{jornada_id}.json"
        assert fitxa_jornada.exists(), f"Fitxa de jornada no trobada a {fitxa_jornada}"
        contingut_jornada = fitxa_jornada.read_text(encoding="utf-8")
        assert "EN_CURS" in contingut_jornada
        assert "41.3851,2.1734" in contingut_jornada

        # 2. Assignar Vehicle
        v_id = uuid.uuid4()
        vehicle = Vehicle(
            id=v_id,
            empresa_id=empresa_id,
            matricula=f"{uuid.uuid4().hex[:4].upper()}-BBB",
            marca="Nissan",
            model="NV400",
            odometre_acumulat=50000,
        )
        admin_session.add(vehicle)
        await admin_session.commit()

        res_veh = await client.post(
            f"/operari/jornada/{jornada_id}/vehicle",
            json={"vehicle_id": str(v_id), "km_actuals": 50120},
            headers=headers,
        )
        assert res_veh.status_code == 200, res_veh.text

        # Comprovar disc dur: 08_flota_i_operaris/vehicles/<v_id>.json
        fitxa_vehicle = disc / "08_flota_i_operaris" / "vehicles" / f"{v_id}.json"
        assert fitxa_vehicle.exists(), f"Fitxa de vehicle no trobada a {fitxa_vehicle}"
        contingut_vehicle = fitxa_vehicle.read_text(encoding="utf-8")
        assert "50120" in contingut_vehicle
        assert str(operari_id) in contingut_vehicle

        # 3. Finalitzar Jornada
        res_fi = await client.post(
            f"/operari/jornada/{jornada_id}/fi",
            json={"latitud": 41.3890, "longitud": 2.1750},
            headers=headers,
        )
        assert res_fi.status_code == 200, res_fi.text

        contingut_fi = fitxa_jornada.read_text(encoding="utf-8")
        assert "COMPLERT" in contingut_fi
        assert "41.389,2.175" in contingut_fi or "41.3890,2.1750" in contingut_fi


@pytest.mark.asyncio
async def test_pas1_02_feina_3_fotos_qa_i_tancament_al_disc_client(setup_pas1_operari, admin_session: AsyncSession):
    """TEST-PAS1-02: Les 3 fotos QA es desen a 06_ordres_treball/actives_buffer i l'OT tancada a historic_tancades."""
    setup = setup_pas1_operari
    headers = setup["headers"]
    disc: Path = setup["disc_client"]
    empresa_id: uuid.UUID = setup["empresa_id"]
    operari_id: uuid.UUID = setup["operari_id"]

    # Crear Client i OT
    client_id = uuid.uuid4()
    cli = Client(
        id=client_id,
        empresa_id=empresa_id,
        rao_social="Comunitat Test Pas 1",
        codi=f"CLI-{empresa_id.hex[:4]}",
        nif=f"H{empresa_id.hex[:8].upper()}",
    )
    admin_session.add(cli)

    ot_id = uuid.uuid4()
    ot = OrdreTreball(
        id=ot_id,
        empresa_id=empresa_id,
        client_id=client_id,
        codi=f"OT-{empresa_id.hex[:4]}",
        titol="Reparació bomba de calor",
        adreca="Carrer Major 1, Barcelona",
        estat="PENDENT",
        cap_de_colla_id=operari_id,
    )
    admin_session.add(ot)
    await admin_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test/api/v1") as client:
        # 1. Intentar finalitzar sense les 3 fotos -> HTTP 400
        res_fail = await client.put(f"/operari/feines/{ot_id}/finalitzar", headers=headers)
        assert res_fail.status_code == 400
        assert "Falten fotografies requerides" in res_fail.json()["detail"]

        # 2. Pujar Foto 1: INICIAL
        f_inicial = b"FOTO_INICIAL_SAMPLE_BYTES"
        res_f1 = await client.post(
            f"/operari/feines/{ot_id}/fotos",
            data={"tipus": "INICIAL"},
            files={"foto": ("foto_inicial.webp", f_inicial, "image/webp")},
            headers=headers,
        )
        assert res_f1.status_code == 200, res_f1.text

        # 3. Pujar Foto 2: INTERMEDIA
        f_intermedia = b"FOTO_INTERMEDIA_SAMPLE_BYTES"
        res_f2 = await client.post(
            f"/operari/feines/{ot_id}/fotos",
            data={"tipus": "INTERMEDIA"},
            files={"foto": ("foto_intermedia.webp", f_intermedia, "image/webp")},
            headers=headers,
        )
        assert res_f2.status_code == 200, res_f2.text

        # 4. Pujar Foto 3: FINAL
        f_final = b"FOTO_FINAL_SAMPLE_BYTES"
        res_f3 = await client.post(
            f"/operari/feines/{ot_id}/fotos",
            data={"tipus": "FINAL"},
            files={"foto": ("foto_final.webp", f_final, "image/webp")},
            headers=headers,
        )
        assert res_f3.status_code == 200, res_f3.text

        # Verificar físicament que les 3 fotos són a 06_ordres_treball/actives_buffer
        carpeta_buffer = disc / "06_ordres_treball" / "actives_buffer"
        p_inicial = carpeta_buffer / f"ot_{ot_id}_foto_inicial.webp"
        p_intermedia = carpeta_buffer / f"ot_{ot_id}_foto_intermedia.webp"
        p_final = carpeta_buffer / f"ot_{ot_id}_foto_final.webp"

        assert p_inicial.exists(), f"Foto inicial no trobada a {p_inicial}"
        assert p_intermedia.exists(), f"Foto intermèdia no trobada a {p_intermedia}"
        assert p_final.exists(), f"Foto final no trobada a {p_final}"

        assert p_inicial.read_bytes() == f_inicial
        assert p_intermedia.read_bytes() == f_intermedia
        assert p_final.read_bytes() == f_final

        # 5. Consultar fotos -> protocol_complet == True
        res_status = await client.get(f"/operari/feines/{ot_id}/fotos", headers=headers)
        assert res_status.status_code == 200
        assert res_status.json()["protocol_complet"] is True

        # 6. Finalitzar feina -> HTTP 200
        res_fin = await client.put(f"/operari/feines/{ot_id}/finalitzar", headers=headers)
        assert res_fin.status_code == 200
        assert res_fin.json()["estat"] == "COMPLERT"

        # Comprovar que s'ha creat la fitxa històrica a 06_ordres_treball/historic_tancades/<id>.json
        fitxa_historic = disc / "06_ordres_treball" / "historic_tancades" / f"{ot_id}.json"
        assert fitxa_historic.exists(), f"Fitxa històrica no trobada a {fitxa_historic}"
        contingut_ot = fitxa_historic.read_text(encoding="utf-8")
        assert "COMPLERT" in contingut_ot
        assert f"ot_{ot_id}_foto_inicial.webp" in contingut_ot


@pytest.mark.asyncio
async def test_pas1_03_tiquets_i_ocr_al_disc_client(setup_pas1_operari, admin_session: AsyncSession):
    """TEST-PAS1-03: Tiquets de carburant i imatges OCR es guarden a 08_flota_i_operaris/tiquets_despesa."""
    setup = setup_pas1_operari
    headers = setup["headers"]
    disc: Path = setup["disc_client"]
    empresa_id: uuid.UUID = setup["empresa_id"]

    # Crear vehicle per associar al tiquet
    v_id = uuid.uuid4()
    vehicle = Vehicle(
        id=v_id,
        empresa_id=empresa_id,
        matricula=f"{uuid.uuid4().hex[:4].upper()}-CCC",
        marca="Renault",
        model="Master",
    )
    admin_session.add(vehicle)
    await admin_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test/api/v1") as client:
        # 1. Pujar tiquet amb OCR
        img_bytes = b"\xff\xd8\xff\xe0...IMATGE_TIQUET_REAL..."
        files = {"file": ("rebut_gasoil.jpg", img_bytes, "image/jpeg")}
        data = {"vehicle_id": str(v_id)}

        res_ocr = await client.post("/operari/tiquets/ocr", files=files, data=data, headers=headers)
        assert res_ocr.status_code == 200, res_ocr.text
        tiquet_ocr_id = res_ocr.json()["id"]

        # Verificar al disc dur del client: carpeta 08_flota_i_operaris/tiquets_despesa
        carpeta_tiquets = disc / "08_flota_i_operaris" / "tiquets_despesa"
        fitxes_ocr = list(carpeta_tiquets.glob(f"{tiquet_ocr_id}.json"))
        assert len(fitxes_ocr) == 1, f"Fitxa JSON de tiquet OCR no trobada a {carpeta_tiquets}"

        fitxers_jpg = list(carpeta_tiquets.glob("ocr_*.jpg"))
        assert len(fitxers_jpg) >= 1, "Imatge binària de tiquet no trobada al disc del client"

        # 2. Registrar tiquet directe
        tiquet_payload = {
            "vehicle_id": str(v_id),
            "tiquet_foto_path": "manual_foto_tiquet.jpg",
            "litres": 45.5,
            "import_euros": 72.80,
            "odometre_valor": 51200,
        }
        res_tiq = await client.post("/operari/tiquets", json=tiquet_payload, headers=headers)
        assert res_tiq.status_code == 201, res_tiq.text
        tiquet_id = res_tiq.json()["id"]

        fitxa_manual = carpeta_tiquets / f"{tiquet_id}.json"
        assert fitxa_manual.exists()
        contingut_tiquet = fitxa_manual.read_text(encoding="utf-8")
        assert "72.8" in contingut_tiquet


@pytest.mark.asyncio
async def test_pas1_04_picking_i_capes_planols_al_disc_client(setup_pas1_operari, admin_session: AsyncSession):
    """TEST-PAS1-04: Picking i capes vectorials d'operaris persisteixen a les seves carpetes de disc."""
    setup = setup_pas1_operari
    headers = setup["headers"]
    disc: Path = setup["disc_client"]
    empresa_id: uuid.UUID = setup["empresa_id"]

    # 1. Crear Client, OT, Picking, Article i LiniaPicking
    cli_id = uuid.uuid4()
    admin_session.add(
        Client(
            id=cli_id,
            empresa_id=empresa_id,
            rao_social="Client Test Picking",
            codi=f"CLI-{empresa_id.hex[:4]}",
            nif=f"H{empresa_id.hex[:8].upper()}",
        )
    )
    await admin_session.flush()

    ot_id = uuid.uuid4()
    admin_session.add(
        OrdreTreball(
            id=ot_id,
            empresa_id=empresa_id,
            client_id=cli_id,
            codi=f"OT-{uuid.uuid4().hex[:4]}",
            titol="Revisió general",
            adreca="Polígon Industrial 4",
            estat="PENDENT",
            cap_de_colla_id=setup["operari_id"],
        )
    )
    await admin_session.flush()

    art_id = uuid.uuid4()
    admin_session.add(
        Article(
            id=art_id,
            empresa_id=empresa_id,
            nom="Vàlvula Esfera 1 polzada",
            referencia_inventari=f"VALV-{uuid.uuid4().hex[:4]}",
        )
    )
    await admin_session.flush()

    picking_id = uuid.uuid4()
    admin_session.add(
        FullaPicking(
            id=picking_id,
            empresa_id=empresa_id,
            ordre_treball_id=ot_id,
            estat_picking="PENDENT",
        )
    )
    await admin_session.flush()

    linia_id = uuid.uuid4()
    linia = LiniaPicking(
        id=linia_id,
        empresa_id=empresa_id,
        picking_id=picking_id,
        article_id=art_id,
        quantitat_prevista=10.0,
        quantitat_carregada_pick_in=0.0,
        quantitat_retornada_pick_out=0.0,
    )
    admin_session.add(linia)

    # Crear CarpetaPlanol i PlanolBase
    c_id = uuid.uuid4()
    admin_session.add(
        CarpetaPlanol(
            id=c_id,
            empresa_id=empresa_id,
            nom="General",
            categoria="GENERAL",
        )
    )

    planol_id = uuid.uuid4()
    planol = PlanolBase(
        id=planol_id,
        empresa_id=empresa_id,
        carpeta_id=c_id,
        titol="Plànol Xarxa de Reg Sector 4",
        codi_referencia=f"PLN-{uuid.uuid4().hex[:4]}",
        tipus_fitxer="PDF",
        mida_bytes=1024,
        fitxer_path="esquema_base.pdf",
    )
    admin_session.add(planol)
    await admin_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test/api/v1") as client:
        # A. Actualitzar Picking (Pick-in 10, Pick-out 2 -> Consum real 8)
        payload_pick = {
            "quantitat_carregada_pick_in": 10.0,
            "quantitat_retornada_pick_out": 2.0,
            "quantitat_mermada": 0.0,
        }
        res_pick = await client.put(f"/operari/picking/linies/{linia_id}", json=payload_pick, headers=headers)
        assert res_pick.status_code == 200, res_pick.text
        assert res_pick.json()["consum_real"] == 8.0

        # Comprovar disc dur: 03_magatzem/picking_fulles/linia_<id>.json
        fitxa_linia = disc / "03_magatzem" / "picking_fulles" / f"linia_{linia_id}.json"
        assert fitxa_linia.exists(), f"Fitxa de línia no trobada a {fitxa_linia}"
        assert '"consum_real": 8.0' in fitxa_linia.read_text(encoding="utf-8")

        # B. Crear Capa Vectorial sobre Plànol
        payload_capa = {
            "nom": "Anotació de pas de canonada",
            "disciplina": "FONTANERIA",
            "color_hex": "#10b981",
            "gruix_linia": 4,
            "es_tancada": False,
            "visible": True,
            "dades_geojson": {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": {"type": "LineString", "coordinates": [[10, 10], [20, 20]]},
                        "properties": {"etiqueta": "Tub PEAD 50"},
                    }
                ],
            },
        }
        res_capa = await client.post(f"/operari/planols/{planol_id}/capes", json=payload_capa, headers=headers)
        assert res_capa.status_code == 201, res_capa.text
        capa_id = res_capa.json()["id"]

        # Comprovar disc dur: 05_planols/capes_vectorials/<capa_id>.json
        fitxa_capa = disc / "05_planols" / "capes_vectorials" / f"{capa_id}.json"
        assert fitxa_capa.exists(), f"Fitxa de capa no trobada a {fitxa_capa}"
        assert "Tub PEAD 50" in fitxa_capa.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_pas1_05_bulk_sync_offline_cap_a_postgres_i_disc_client(setup_pas1_operari, admin_session: AsyncSession):
    """TEST-PAS1-05: El bucle de sincronització offline persisteix a PostgreSQL i al disc dur del client."""
    setup = setup_pas1_operari
    headers = setup["headers"]
    disc: Path = setup["disc_client"]
    empresa_id: uuid.UUID = setup["empresa_id"]

    v_id = uuid.uuid4()
    admin_session.add(
        Vehicle(
            id=v_id,
            empresa_id=empresa_id,
            matricula=f"{uuid.uuid4().hex[:4].upper()}-DDD",
            marca="Peugeot",
            model="Partner",
        )
    )
    await admin_session.commit()

    sync_payload = {
        "accions": [
            {
                "id": "act-sync-jornada-1",
                "accio": "FITXAR_JORNADA",
                "payload": {"latitud": 41.5000, "longitud": 2.2500, "tipus": "INICI"},
                "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
            },
            {
                "id": "act-sync-tiquet-2",
                "accio": "CREAR_TIQUET",
                "payload": {
                    "vehicle_id": str(v_id),
                    "import_total": 45.0,
                    "litres": 30.0,
                    "tiquet_foto_path": "sync_offline_foto.webp",
                },
                "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
            },
        ]
    }

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test/api/v1") as client:
        res_sync = await client.post("/sync/push", json=sync_payload, headers=headers)
        assert res_sync.status_code == 200, res_sync.text
        data = res_sync.json()
        assert data["status"] == "ok"
        assert data["processades"] == 2
        assert len(data["errors"]) == 0

    # 1. Comprovar PostgreSQL
    j_res = await admin_session.execute(
        select(RegistreJornadaLaboral).where(RegistreJornadaLaboral.empresa_id == empresa_id)
    )
    jornades = j_res.scalars().all()
    assert len(jornades) >= 1
    assert any(j.geolocalitzacio_inici == "41.5,2.25" for j in jornades)

    t_res = await admin_session.execute(
        select(TiquetCarburant).where(TiquetCarburant.empresa_id == empresa_id)
    )
    tiquets = t_res.scalars().all()
    assert len(tiquets) >= 1
    assert any(float(t.import_ or 0) == 45.0 for t in tiquets)

    # 2. Comprovar Disc Dur del Client
    carpeta_jornades = disc / "08_flota_i_operaris" / "registres_jornada"
    fitxers_jornada = list(carpeta_jornades.glob("*.json"))
    assert len(fitxers_jornada) >= 1

    carpeta_tiquets = disc / "08_flota_i_operaris" / "tiquets_despesa"
    fitxers_tiquets = list(carpeta_tiquets.glob("*.json"))
    assert len(fitxers_tiquets) >= 1
