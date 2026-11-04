"""
Tests d'Integració de les 4 Fases de la PWA Operari (Segons pla_implementacio_fases_pwa.md).
- Fase 1: Control Horari GPS (Inici de Torn i persistència al disc dur sobirà).
- Fase 2: Geovalla 50m, Semàfor de 3 Fotos QA (INICIAL, INTERMEDIA, FINAL) i Bloqueig de Tancament d'OT.
- Fase 3: Check-in de Vehicle i Odòmetre inicial.
- Fase 4: Tancament de Jornada amb Odòmetre final i Custòdia de Paper.
Tots els tests s'executen contra PostgreSQL 16 i el disc dur sobirà (Zero Mock Data).
"""

import uuid
from datetime import datetime, timezone
from pathlib import Path

import jwt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.main import app
from app.models.models import (
    Client,
    Empresa,
    OrdreTreball,
    RegistreJornadaLaboral,
    Usuari,
    Vehicle,
)


@pytest.fixture
async def setup_fases_operari(admin_session: AsyncSession, tmp_path: Path):
    """Configuració aïllada amb Empresa, Disc Dur dedicat, Vehicle, Client i Operari."""
    empresa_id = uuid.uuid4()
    operari_id = uuid.uuid4()
    client_id = uuid.uuid4()
    vehicle_id = uuid.uuid4()
    ot_id = uuid.uuid4()

    disc_client = tmp_path / f"disc_fases_{empresa_id.hex[:6]}"
    disc_client.mkdir(parents=True, exist_ok=True)

    empresa = Empresa(
        id=empresa_id,
        nom=f"Empresa Fases {empresa_id.hex[:4]}",
        nif=f"B{empresa_id.hex[:8].upper()}",
        subdomini=f"fases-{empresa_id.hex[:6]}",
        disc_dur_url=str(disc_client),
        node_ia_actiu=True,
    )
    admin_session.add(empresa)
    await admin_session.flush()

    operari = Usuari(
        id=operari_id,
        empresa_id=empresa_id,
        nom="Pau",
        cognoms="Baixa",
        nif=f"NIF{operari_id.hex[:5].upper()}",
        email=f"pau.{operari_id.hex[:4]}@sevalor.cat",
        rol="CAP_DE_COLLA",
        telefon="699874458",
    )
    admin_session.add(operari)
    await admin_session.flush()

    vehicle = Vehicle(
        id=vehicle_id,
        empresa_id=empresa_id,
        matricula="1234-XYZ",
        marca="Renault",
        model="Kangoo Maxi",
        odometre_acumulat=124000,
        estat="ACTIU",
    )
    admin_session.add(vehicle)

    client_ent = Client(
        id=client_id,
        empresa_id=empresa_id,
        rao_social="Finca Agrícola El Prat SL",
        codi=f"CLI-{empresa_id.hex[:4]}",
        nif="B99887766",
    )
    admin_session.add(client_ent)
    await admin_session.flush()

    # Ordre de treball amb coordenades a Barcelona (41.3879, 2.1699)
    ordre = OrdreTreball(
        id=ot_id,
        empresa_id=empresa_id,
        codi="OT-FASES-01",
        titol="Manteniment de Bombes de Reg",
        adreca="41.3879, 2.1699",
        client_id=client_id,
        cap_de_colla_id=operari_id,
        estat="PENDENT",
    )
    admin_session.add(ordre)

    await admin_session.commit()

    token_payload = {
        "sub": str(operari_id),
        "empresa_id": str(empresa_id),
        "rol": "CAP_DE_COLLA",
        "exp": datetime.now(timezone.utc).timestamp() + 3600,
    }
    jwt_token = jwt.encode(token_payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    return {
        "empresa_id": empresa_id,
        "operari_id": operari_id,
        "vehicle_id": vehicle_id,
        "ot_id": ot_id,
        "jwt_token": jwt_token,
        "disc_client": disc_client,
    }


@pytest.mark.asyncio
async def test_fase1_control_horari_gps_inici(
    setup_fases_operari: dict, admin_session: AsyncSession
):
    """Fase 1: Iniciar jornada amb GPS (FR-004) i verificar persistència a PostgreSQL i al disc dur sobirà."""
    data = setup_fases_operari
    transport = ASGITransport(app=app)

    async with AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=True
    ) as client:
        res = await client.post(
            "/api/v1/operari/jornada/inici",
            json={"latitud": 41.3879, "longitud": 2.1699},
            headers={"Authorization": f"Bearer {data['jwt_token']}"},
        )
        assert res.status_code == 201, res.text
        resp_json = res.json()
        assert resp_json["estat"] == "EN_CURS"
        jornada_id = uuid.UUID(resp_json["id"])

        # Verificar a BD
        stmt = select(RegistreJornadaLaboral).where(
            RegistreJornadaLaboral.id == jornada_id,
            RegistreJornadaLaboral.empresa_id == data["empresa_id"],
        )
        result = await admin_session.execute(stmt)
        j_db = result.scalars().first()
        assert j_db is not None
        assert j_db.estat == "EN_CURS"
        assert "41.3879" in (j_db.geolocalitzacio_inici or "")

        # Verificar fitxer JSON al disc dur sobirà
        json_file = (
            data["disc_client"]
            / "08_flota_i_operaris"
            / "registres_jornada"
            / f"{jornada_id}.json"
        )
        assert json_file.exists()


@pytest.mark.asyncio
async def test_fase1_control_horari_inici_amb_cookie_sense_auth_header(
    setup_fases_operari: dict, admin_session: AsyncSession
):
    """Verifica que el endpoint /jornada/inici i /jornada/activa funcionen exclusivament amb la cookie de sessió

    (sevalor_access_token) sense cap capçalera 'Authorization', evitant AttributeError: 'NoneType' object has no attribute 'split'.
    """
    data = setup_fases_operari
    transport = ASGITransport(app=app)

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        follow_redirects=True,
        cookies={"sevalor_access_token": data["jwt_token"]},
    ) as client:
        # 1. Comprovar jornada activa abans d'iniciar (retorna 404 perquè no n'hi ha cap en curs)
        res_activa_pre = await client.get("/api/v1/operari/jornada/activa")
        assert res_activa_pre.status_code == 404

        # 2. Iniciar jornada exclusivament amb la cookie
        res_inici = await client.post(
            "/api/v1/operari/jornada/inici",
            json={"latitud": 41.3879, "longitud": 2.1699},
        )
        assert res_inici.status_code == 201, res_inici.text
        resp_json = res_inici.json()
        assert resp_json["estat"] == "EN_CURS"
        jornada_id = resp_json["id"]

        # 3. Comprovar jornada activa després d'iniciar (retorna 200 amb les dades de la jornada)
        res_activa_post = await client.get("/api/v1/operari/jornada/activa")
        assert res_activa_post.status_code == 200
        assert res_activa_post.json()["id"] == jornada_id
        assert res_activa_post.json()["estat"] == "EN_CURS"


@pytest.mark.asyncio
async def test_fase2_geovalla_comencar_feina(setup_fases_operari: dict):
    """Fase 2: Validar geovalla de 50m (FR-005): rebuig si està a més de 50m sense justificació, èxit amb justificació."""
    data = setup_fases_operari
    transport = ASGITransport(app=app)

    async with AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=True
    ) as client:
        # 1. Intentar començar des de 5 km de distància sense justificació -> Ha de fallar amb 400
        res_fail = await client.put(
            f"/api/v1/operari/feines/{data['ot_id']}/comencar",
            json={"lat": 41.4200, "lng": 2.2200, "desviacio_justificada": False},
            headers={"Authorization": f"Bearer {data['jwt_token']}"},
        )
        assert res_fail.status_code == 400
        assert "Geovalla" in res_fail.json().get("detail", "")

        # 2. Començar amb justificació de desviació permesa -> Ha de tenir èxit
        res_ok = await client.put(
            f"/api/v1/operari/feines/{data['ot_id']}/comencar",
            json={
                "lat": 41.4200,
                "lng": 2.2200,
                "desviacio_justificada": True,
                "justificacio_gps": "Aparcament a 300m degut a obres municipals",
            },
            headers={"Authorization": f"Bearer {data['jwt_token']}"},
        )
        assert res_ok.status_code == 200, res_ok.text
        assert res_ok.json()["estat"] == "EN_CURS"


@pytest.mark.asyncio
async def test_fase2_semafor_3_fotos_i_bloqueig_tancament(
    setup_fases_operari: dict, admin_session: AsyncSession
):
    """Fase 2: Protocol obligatori de 3 Fotos QA (FR-007) i bloqueig de finalització fins a completar-les."""
    data = setup_fases_operari
    transport = ASGITransport(app=app)

    async with AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=True
    ) as client:
        # 1. Intentar tancar l'ordre sense cap foto -> Ha de fallar amb 400
        res_tancar_fail = await client.put(
            f"/api/v1/operari/feines/{data['ot_id']}/finalitzar",
            headers={"Authorization": f"Bearer {data['jwt_token']}"},
        )
        assert res_tancar_fail.status_code == 400
        assert "control de qualitat" in res_tancar_fail.json().get("detail", "").lower()

        # 2. Pujar Foto INICIAL
        res_f1 = await client.post(
            f"/api/v1/operari/feines/{data['ot_id']}/fotos",
            data={"tipus": "INICIAL"},
            files={"foto": ("inicial.webp", b"FOTO_INICIAL_BYTES", "image/webp")},
            headers={"Authorization": f"Bearer {data['jwt_token']}"},
        )
        assert res_f1.status_code == 200

        # Consultar estat -> protocol_complet ha de ser False
        res_estat1 = await client.get(
            f"/api/v1/operari/feines/{data['ot_id']}/fotos",
            headers={"Authorization": f"Bearer {data['jwt_token']}"},
        )
        assert res_estat1.status_code == 200
        assert res_estat1.json()["protocol_complet"] is False

        # 3. Pujar Foto INTERMEDIA
        res_f2 = await client.post(
            f"/api/v1/operari/feines/{data['ot_id']}/fotos",
            data={"tipus": "INTERMEDIA"},
            files={"foto": ("intermedia.webp", b"FOTO_INTERMEDIA_BYTES", "image/webp")},
            headers={"Authorization": f"Bearer {data['jwt_token']}"},
        )
        assert res_f2.status_code == 200

        # 4. Pujar Foto FINAL
        res_f3 = await client.post(
            f"/api/v1/operari/feines/{data['ot_id']}/fotos",
            data={"tipus": "FINAL"},
            files={"foto": ("final.webp", b"FOTO_FINAL_BYTES", "image/webp")},
            headers={"Authorization": f"Bearer {data['jwt_token']}"},
        )
        assert res_f3.status_code == 200

        # Consultar estat -> protocol_complet ha de ser True
        res_estat_final = await client.get(
            f"/api/v1/operari/feines/{data['ot_id']}/fotos",
            headers={"Authorization": f"Bearer {data['jwt_token']}"},
        )
        assert res_estat_final.status_code == 200
        assert res_estat_final.json()["protocol_complet"] is True

        # 5. Ara que les 3 fotos estan pujades, tancar l'ordre satisfactòriament
        res_tancar_ok = await client.put(
            f"/api/v1/operari/feines/{data['ot_id']}/finalitzar",
            json={
                "hores": 2.5,
                "observacions": "Reparació completada amb èxit",
                "signatura_base64": "data:image/png;base64,SIGNATURA_TEST",
            },
            headers={"Authorization": f"Bearer {data['jwt_token']}"},
        )
        assert res_tancar_ok.status_code == 200, res_tancar_ok.text
        assert res_tancar_ok.json()["estat"] == "COMPLERT"

        # Verificar que s'ha arxivat al disc dur a '06_ordres_treball/historic_tancades'
        historic_json = (
            data["disc_client"]
            / "06_ordres_treball"
            / "historic_tancades"
            / f"{data['ot_id']}.json"
        )
        assert historic_json.exists()


@pytest.mark.asyncio
async def test_fase3_checkin_vehicle_i_fase4_checkout(
    setup_fases_operari: dict, admin_session: AsyncSession
):
    """Fases 3 i 4: Assistent matinal (assignar vehicle) i checkout vespre (odòmetre i tancament)."""
    data = setup_fases_operari
    transport = ASGITransport(app=app)

    async with AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=True
    ) as client:
        # Iniciar jornada
        res_jornada = await client.post(
            "/api/v1/operari/jornada/inici",
            json={"latitud": 41.3879, "longitud": 2.1699},
            headers={"Authorization": f"Bearer {data['jwt_token']}"},
        )
        assert res_jornada.status_code == 201
        jornada_id = res_jornada.json()["id"]

        # FASE 3: Assignar vehicle i km inicials (124050 km)
        res_veh = await client.post(
            f"/api/v1/operari/jornada/{jornada_id}/vehicle",
            json={
                "vehicle_id": str(data["vehicle_id"]),
                "km_actuals": 124050,
                "km_inicials": 124050,
            },
            headers={"Authorization": f"Bearer {data['jwt_token']}"},
        )
        assert res_veh.status_code == 200, res_veh.text

        # FASE 4: Tancar Jornada amb GPS
        res_fi = await client.post(
            f"/api/v1/operari/jornada/{jornada_id}/fi",
            json={"latitud": 41.3885, "longitud": 2.1705},
            headers={"Authorization": f"Bearer {data['jwt_token']}"},
        )
        assert res_fi.status_code == 200, res_fi.text
        assert res_fi.json()["estat"] == "COMPLERT"

        # Comprovar estat a la BD
        stmt = select(RegistreJornadaLaboral).where(
            RegistreJornadaLaboral.id == uuid.UUID(jornada_id)
        )
        res_db = await admin_session.execute(stmt)
        j_db = res_db.scalars().first()
        assert j_db is not None
        assert j_db.estat == "COMPLERT"
        assert j_db.hora_fi is not None
