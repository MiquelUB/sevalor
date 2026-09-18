import pytest
from httpx import AsyncClient, ASGITransport
import uuid
from app.main import app
from app.models.models import Empresa, Usuari, Vehicle
import jwt
from app.core.config import settings

@pytest.fixture
def test_empresa(admin_session):
    return uuid.uuid4()

@pytest.mark.asyncio
async def test_operari_puja_tiquet_ocr(admin_session):
    emp_id = uuid.uuid4()
    op_id = uuid.uuid4()
    veh_id = uuid.uuid4()
    
    admin_session.add(Empresa(id=emp_id, nom='Test', nif='1234', subdomini='t' + str(uuid.uuid4())[:5]))
    await admin_session.flush()
    
    admin_session.add(Usuari(id=op_id, empresa_id=emp_id, nif='OP123', nom='Operari', cognoms='Test', rol='OPERARI', estat='ACTIU', pin_hash='xx', telefon='123'))
    admin_session.add(Vehicle(id=veh_id, empresa_id=emp_id, matricula='1234ABC', marca='Ford', model='Transit', estat='OPERATIU'))
    await admin_session.flush()
    
    token = jwt.encode({"sub": str(op_id), "rol": "OPERARI", "empresa_id": str(emp_id), "exp": 9999999999}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    headers = {"Authorization": f"Bearer {token}", "X-Empresa-ID": str(emp_id)}
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        fitxer_simulat = {"file": ("tiquet_benzina.jpg", b"fake_image_data", "image/jpeg")}
        
        res = await ac.post(
            "/api/v1/operari/tiquets/ocr", 
            files=fitxer_simulat,
            data={"vehicle_id": str(veh_id)},
            headers=headers
        )
        
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["status"] == "OK"
        assert "import_extret" in data
        assert data["import_extret"] > 0.0
        
        tiquet_id = data.get("id")
        assert tiquet_id is not None
        
        res_llista = await ac.get("/api/v1/operari/tiquets", headers=headers)
        assert res_llista.status_code == 200
        tiquets = res_llista.json()
        assert any(t["id"] == tiquet_id for t in tiquets)

