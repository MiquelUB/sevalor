"""Tests d'integració reals (Zero Mock + RLS) per a:
1. Posició GPS real d'operaris al mapa (eliminació de coordenades mockejades + 0.002).
2. Endpoint live GPS `/api/v1/operari/posicio` i prioritat per timestamp real.
3. Creació completa d'Ordre de Treball (`POST /api/v1/gestio/feines`) amb preservació de context RLS post-commit.
4. Aïllament estricte multi-tenant (RLS) entre Empresa A i Empresa B.
"""

import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.main import app
from app.models.models import (
    Client,
    EinaCustodia,
    Empresa,
    OrdreTreball,
    RegistreJornadaLaboral,
    Usuari,
)


def _make_token(empresa_id: str, user_id: str, rol: str) -> str:
    payload = {
        "sub": user_id,
        "rol": rol,
        "empresa_id": empresa_id,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


@pytest.mark.asyncio
async def test_operari_sense_gps_real_no_retorna_posicio_mockejada(
    admin_session, headers, boss_token
):
    """Un operari assignat a una OT però sense senyal GPS real ha de retornar latitud/longitud=None."""
    _, empresa_id = boss_token
    emp_uuid = uuid.UUID(empresa_id)

    admin_session.add(
        Empresa(
            id=emp_uuid,
            nom="Empresa Zero Mock GPS",
            nif="B" + uuid.uuid4().hex[:8].upper(),
            subdomini="gps-nomock-" + uuid.uuid4().hex[:6],
            pla_subscripcio="PRO",
            estat_pagament="ACTIU",
        )
    )
    await admin_session.flush()

    client_id = uuid.uuid4()
    admin_session.add(
        Client(
            id=client_id,
            empresa_id=emp_uuid,
            codi="CLI-GPS-1",
            rao_social="Client Finca Nord",
            nif="B11223344",
        )
    )

    op_id = uuid.uuid4()
    admin_session.add(
        Usuari(
            id=op_id,
            empresa_id=emp_uuid,
            nif="44556677A",
            nom="Pere",
            cognoms="SenseGPS",
            rol="OPERARI",
            estat="ACTIU",
        )
    )
    await admin_session.flush()

    # Assignem l'operari a una OT activa amb coordenades — abans això mockejava lat+0.002!
    admin_session.add(
        OrdreTreball(
            id=uuid.uuid4(),
            empresa_id=emp_uuid,
            codi=f"OT-{uuid.uuid4().hex[:6].upper()}",
            client_id=client_id,
            titol="Revisió canal principal",
            adreca="Lleida",
            estat="EN_CURS",
            cap_de_colla_id=op_id,
            latitud=41.6176,
            longitud=0.6200,
        )
    )
    await admin_session.flush()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/api/v1/gestio/operaris", headers=headers)
        assert res.status_code == 200, res.text
        ops = res.json()
        op_data = next((o for o in ops if o["id"] == str(op_id)), None)
        assert op_data is not None
        assert op_data["latitud"] is None
        assert op_data["longitud"] is None
        assert op_data["posicio_origen"] is None


@pytest.mark.asyncio
async def test_operari_posicio_gps_real_temps_real_i_jornada_i_rls(
    admin_session, headers, boss_token
):
    """Verifica /operari/posicio (temps real), fallback a fitxatge real, rebuig de 0,0 i RLS."""
    _, emp_a_id = boss_token
    emp_a_uuid = uuid.UUID(emp_a_id)
    emp_b_uuid = uuid.uuid4()

    admin_session.add(
        Empresa(
            id=emp_a_uuid,
            nom="Empresa GPS A",
            nif="B" + uuid.uuid4().hex[:8].upper(),
            subdomini="gps-a-" + uuid.uuid4().hex[:6],
            pla_subscripcio="PRO",
            estat_pagament="ACTIU",
        )
    )
    admin_session.add(
        Empresa(
            id=emp_b_uuid,
            nom="Empresa GPS B",
            nif="B" + uuid.uuid4().hex[:8].upper(),
            subdomini="gps-b-" + uuid.uuid4().hex[:6],
            pla_subscripcio="PRO",
            estat_pagament="ACTIU",
        )
    )
    await admin_session.flush()

    op_live_id = uuid.uuid4()
    op_fitxatge_id = uuid.uuid4()
    admin_session.add(
        Usuari(
            id=op_live_id,
            empresa_id=emp_a_uuid,
            nif="11223344L",
            nom="Marc",
            cognoms="LiveGPS",
            rol="OPERARI",
            estat="ACTIU",
        )
    )
    admin_session.add(
        Usuari(
            id=op_fitxatge_id,
            empresa_id=emp_a_uuid,
            nif="22334455F",
            nom="Anna",
            cognoms="FitxatgeGPS",
            rol="OPERARI",
            estat="ACTIU",
        )
    )
    await admin_session.flush()

    # Registre de jornada amb coordenades reals a Girona per a Anna
    admin_session.add(
        RegistreJornadaLaboral(
            empresa_id=emp_a_uuid,
            usuari_id=op_fitxatge_id,
            geolocalitzacio_inici="41.979400,2.821400",
            estat="EN_CURS",
        )
    )
    await admin_session.flush()

    op_live_headers = {
        "Authorization": f"Bearer {_make_token(emp_a_id, str(op_live_id), 'OPERARI')}",
        "X-Empresa-ID": emp_a_id,
    }
    boss_b_headers = {
        "Authorization": f"Bearer {_make_token(str(emp_b_uuid), str(uuid.uuid4()), 'BOSS')}",
        "X-Empresa-ID": str(emp_b_uuid),
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Rebutjar coordenades nul·les (0,0)
        res_bad = await ac.post(
            "/api/v1/operari/posicio",
            json={"latitud": 0.0, "longitud": 0.0},
            headers=op_live_headers,
        )
        assert res_bad.status_code == 422

        # 2. Enviar posició GPS real de Marc (Tarragona)
        res_pos = await ac.post(
            "/api/v1/operari/posicio",
            json={"latitud": 41.118912, "longitud": 1.244521},
            headers=op_live_headers,
        )
        assert res_pos.status_code == 200, res_pos.text
        assert res_pos.json()["latitud"] == pytest.approx(41.118912, abs=1e-5)

        # 3. Verificar que GET /gestio/operaris retorna posicions reals i diferents per cada operari
        res_ops = await ac.get("/api/v1/gestio/operaris", headers=headers)
        assert res_ops.status_code == 200, res_ops.text
        ops_map = {o["id"]: o for o in res_ops.json()}

        marc = ops_map[str(op_live_id)]
        assert marc["latitud"] == pytest.approx(41.118912, abs=1e-5)
        assert marc["longitud"] == pytest.approx(1.244521, abs=1e-5)
        assert marc["posicio_origen"] == "GPS_TEMPS_REAL"
        assert marc["posicio_actualitzada_at"] is not None

        anna = ops_map[str(op_fitxatge_id)]
        assert anna["latitud"] == pytest.approx(41.9794, abs=1e-4)
        assert anna["longitud"] == pytest.approx(2.8214, abs=1e-4)
        assert anna["posicio_origen"] == "FITXATGE_JORNADA"

        # 4. Aïllament RLS: Empresa B no pot veure els operaris ni el GPS d'Empresa A
        res_b = await ac.get("/api/v1/gestio/operaris", headers=boss_b_headers)
        assert res_b.status_code == 200
        assert all(o["id"] not in (str(op_live_id), str(op_fitxatge_id)) for o in res_b.json())


@pytest.mark.asyncio
async def test_creacio_ot_completa_preserva_rls_post_commit(
    admin_session, headers, boss_token
):
    """Verifica que POST /gestio/feines retorna totes les dades relacionades post-commit i respecta RLS."""
    _, emp_a_id = boss_token
    emp_a_uuid = uuid.UUID(emp_a_id)
    emp_b_uuid = uuid.uuid4()

    admin_session.add(
        Empresa(
            id=emp_a_uuid,
            nom="Empresa OT Completa A",
            nif="B" + uuid.uuid4().hex[:8].upper(),
            subdomini="ot-comp-a-" + uuid.uuid4().hex[:6],
            pla_subscripcio="PRO",
            estat_pagament="ACTIU",
        )
    )
    admin_session.add(
        Empresa(
            id=emp_b_uuid,
            nom="Empresa OT Completa B",
            nif="B" + uuid.uuid4().hex[:8].upper(),
            subdomini="ot-comp-b-" + uuid.uuid4().hex[:6],
            pla_subscripcio="PRO",
            estat_pagament="ACTIU",
        )
    )
    await admin_session.flush()

    client_id = uuid.uuid4()
    op_cap_id = uuid.uuid4()
    eina_id = uuid.uuid4()

    admin_session.add(
        Client(
            id=client_id,
            empresa_id=emp_a_uuid,
            codi="CLI-OT-COMP",
            rao_social="Agrícola del Segrià S.L.",
            nif="B55443322",
            adreca_fiscal="Carrer Major 10, Lleida",
        )
    )
    admin_session.add(
        Usuari(
            id=op_cap_id,
            empresa_id=emp_a_uuid,
            nif="33445566K",
            nom="Joan",
            cognoms="CapColla",
            rol="CAP_DE_COLLA",
            estat="ACTIU",
        )
    )
    admin_session.add(
        EinaCustodia(
            id=eina_id,
            empresa_id=emp_a_uuid,
            nom="Soldadora PEHD",
            model="Ritmo 160",
            numero_serie="SN-RITMO-01",
            estat="DISPONIBLE",
        )
    )
    await admin_session.flush()

    codi_ot = f"OT-{uuid.uuid4().hex[:6].upper()}"
    payload = {
        "codi": codi_ot,
        "client_id": str(client_id),
        "titol": "Instal·lació sector reg automatitzat",
        "adreca": "Carrer Major 10, Lleida",
        "descripcio": "Muntatge complet amb prova de pressió",
        "estat": "ASSIGNADA",
        "data_planificacio": "2027-04-12",
        "hores_previstes": 4.5,
        "preu_venda_hora_aplicat": 48.0,
        "cap_de_colla_id": str(op_cap_id),
        "operaris_ids": [str(op_cap_id)],
        "eina_ids": [str(eina_id)],
    }

    boss_b_headers = {
        "Authorization": f"Bearer {_make_token(str(emp_b_uuid), str(uuid.uuid4()), 'BOSS')}",
        "X-Empresa-ID": str(emp_b_uuid),
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/api/v1/gestio/feines", json=payload, headers=headers)
        assert res.status_code == 201, res.text
        created = res.json()
        assert created["codi"] == codi_ot
        assert created["client_nom"] == "Agrícola del Segrià S.L."
        assert created["cap_de_colla_nom"] == "Joan CapColla"
        assert float(created["hores_previstes"]) == pytest.approx(4.5, abs=0.01)
        assert float(created["preu_venda_hora_aplicat"]) == pytest.approx(48.0, abs=0.01)
        assert len(created["eines"]) == 1
        assert created["eines"][0]["id"] == str(eina_id)
        assert len(created["operaris_assignats"]) == 1

        # Verificar aïllament RLS: Empresa B no pot llegir aquesta OT
        res_b = await ac.get(f"/api/v1/gestio/feines/{created['id']}", headers=boss_b_headers)
        assert res_b.status_code == 404
