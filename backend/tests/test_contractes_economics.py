import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import date

from app.models.models import Empresa, Client, Usuari, FacturaCapcalera
from app.models.contractes import ContracteManteniment

@pytest.fixture
async def empresa(db_session: AsyncSession):
    nova_empresa = Empresa(nom="Empresa Test Economics", nif="B12345670")
    db_session.add(nova_empresa)
    await db_session.commit()
    await db_session.refresh(nova_empresa)
    return nova_empresa

@pytest.fixture
async def boss(db_session: AsyncSession, empresa: Empresa):
    nou_boss = Usuari(
        empresa_id=empresa.id,
        nom="Boss Economics", nif="87654321X",
        email="boss_economics@example.com",
        rol="BOSS",
        pin_hash="hashed_pin"
    )
    db_session.add(nou_boss)
    await db_session.commit()
    await db_session.refresh(nou_boss)
    return nou_boss

@pytest.fixture
async def client_db(db_session: AsyncSession, empresa: Empresa):
    nou_client = Client(
        empresa_id=empresa.id,
        codi="CLI-002",
        rao_social="Client Contracte Econ",
        nif="B22222222"
    )
    db_session.add(nou_client)
    await db_session.commit()
    await db_session.refresh(nou_client)
    return nou_client

@pytest.fixture
async def auth_headers(boss: Usuari):
    import jwt
    from app.core.config import settings

    payload = {
        "sub": str(boss.id),
        "empresa_id": str(boss.empresa_id),
        "rol": "BOSS",
        "exp": 9999999999,
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return {"Authorization": f"Bearer {token}", "X-Empresa-ID": str(boss.empresa_id)}

@pytest.fixture
async def contractes(db_session: AsyncSession, empresa: Empresa, client_db: Client):
    c1 = ContracteManteniment(
        empresa_id=empresa.id,
        client_id=client_db.id,
        numero_contracte="C-100",
        data_inici=date(2025, 1, 1),
        import_anual=1200.0,
        estat="ACTIU"
    )
    c2 = ContracteManteniment(
        empresa_id=empresa.id,
        client_id=client_db.id,
        numero_contracte="C-101",
        data_inici=date(2025, 1, 1),
        import_anual=600.0,
        estat="ACTIU"
    )
    c3 = ContracteManteniment(
        empresa_id=empresa.id,
        client_id=client_db.id,
        numero_contracte="C-102",
        data_inici=date(2025, 1, 1),
        import_anual=2400.0,
        estat="BAIXA" # Should not be in MRR
    )
    db_session.add_all([c1, c2, c3])
    await db_session.commit()
    return c1, c2, c3

@pytest.mark.asyncio
async def test_mrr_calcul(async_client: AsyncClient, contractes: tuple, auth_headers: dict):
    # Active contracts: 1200 + 600 = 1800. MRR = 1800 / 12 = 150.0
    resp = await async_client.get("/gestio/contractes/kpis/mrr", headers=auth_headers)
    assert resp.status_code == 200
    dades = resp.json()
    assert dades["mrr"] == 150.0

@pytest.mark.asyncio
async def test_prefacturar_contracte(async_client: AsyncClient, db_session: AsyncSession, contractes: tuple, auth_headers: dict):
    c1 = contractes[0] # import 1200
    
    resp = await async_client.post(f"/gestio/contractes/{c1.id}/prefacturar", headers=auth_headers)
    assert resp.status_code == 200
    dades = resp.json()
    factura_id = dades["factura_id"]
    
    # Verify factura in DB
    stmt = select(FacturaCapcalera).where(FacturaCapcalera.id == factura_id)
    res = await db_session.execute(stmt)
    factura = res.scalar_one_or_none()
    
    assert factura is not None
    assert float(factura.base_imposable) == 1200.0
    assert float(factura.quota_iva) == 252.0 # 1200 * 0.21
    assert factura.estat_enviament == "PENDENT"
