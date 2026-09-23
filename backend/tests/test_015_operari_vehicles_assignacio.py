import uuid

import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.main import app
from app.models.models import Empresa, Usuari, Vehicle


@pytest.mark.asyncio
async def test_operari_assigna_vehicle_i_reporta_danys(admin_session):
    emp_id = uuid.uuid4()
    op_id = uuid.uuid4()
    veh_id = uuid.uuid4()

    admin_session.add(Empresa(id=emp_id, nom='Test', nif='1234', subdomini='t' + str(uuid.uuid4())[:5]))
    await admin_session.flush()

    admin_session.add(Usuari(id=op_id, empresa_id=emp_id, nif='OP123', nom='Operari', cognoms='Test', rol='OPERARI', estat='ACTIU', pin_hash='xx', telefon='123'))
    admin_session.add(Vehicle(id=veh_id, empresa_id=emp_id, matricula='1234ABC', marca='Ford', model='Transit', estat='OPERATIU', odometre_acumulat=100000))
    await admin_session.flush()

    token = jwt.encode({"sub": str(op_id), "rol": "OPERARI", "empresa_id": str(emp_id), "exp": 9999999999}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    headers = {"Authorization": f"Bearer {token}", "X-Empresa-ID": str(emp_id)}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res_inici = await ac.post("/api/v1/operari/jornada/inici", json={"geolocalitzacio": "0,0"}, headers=headers)
        assert res_inici.status_code in [200, 201]
        jornada_id = res_inici.json()["id"]

        res_llista = await ac.get("/api/v1/operari/vehicles", headers=headers)
        assert res_llista.status_code == 200
        vehicles = res_llista.json()
        assert any(v["id"] == str(veh_id) for v in vehicles)

        # 2. Assignació de furgoneta
        res_assign = await ac.post(
            f"/api/v1/operari/jornada/{jornada_id}/vehicle",
            json={"vehicle_id": str(veh_id), "km_actuals": 100500},
            headers=headers
        )
        assert res_assign.status_code == 200
        assert res_assign.json()["vehicle_assignat_id"] == str(veh_id)

        # Falla per KM inferiors
        res_assign_fail = await ac.post(
            f"/api/v1/operari/jornada/{jornada_id}/vehicle",
            json={"vehicle_id": str(veh_id), "km_actuals": 99000},
            headers=headers
        )
        assert res_assign_fail.status_code == 422

        # 3. Report de dany
        res_dany = await ac.post(
            f"/api/v1/operari/vehicles/{veh_id}/danys",
            json={"descripcio": "Retrovisor dret clivellat", "gravetat": "LLEU"},
            headers=headers
        )
        assert res_dany.status_code == 200
        assert res_dany.json()["status"] == "OK"

