import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import date, datetime, timedelta, timezone

from app.models.models import Empresa, Client, Usuari
from app.models.contractes import ContracteManteniment, RevisionsContracte

@pytest.fixture
async def empresa(db_session: AsyncSession):
    nova_empresa = Empresa(nom="Empresa Test Contractes", nif="B12345679")
    db_session.add(nova_empresa)
    await db_session.commit()
    await db_session.refresh(nova_empresa)
    return nova_empresa

@pytest.fixture
async def boss(db_session: AsyncSession, empresa: Empresa):
    nou_boss = Usuari(
        empresa_id=empresa.id,
        nom="Boss Contractes", nif="12345678X",
        email="boss_contractes@example.com",
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
        codi="CLI-001",
        rao_social="Client Contracte Cicle",
        nif="B11111111"
    )
    db_session.add(nou_client)
    await db_session.commit()
    await db_session.refresh(nou_client)
    return nou_client

@pytest.fixture
async def auth_headers(boss: Usuari):
    return {"Authorization": f"Bearer {boss.id}", "X-Empresa-ID": str(boss.empresa_id)}

@pytest.fixture
async def contracte(db_session: AsyncSession, empresa: Empresa, client_db: Client):
    c = ContracteManteniment(
        empresa_id=empresa.id,
        client_id=client_db.id,
        numero_contracte="C-001",
        data_inici=date(2025, 1, 1),
        data_fi=date(2025, 12, 31),
        import_anual=1200.0,
        estat="ACTIU"
    )
    db_session.add(c)
    await db_session.commit()
    await db_session.refresh(c)
    return c

@pytest.mark.asyncio
async def test_alertes_venciment(async_client: AsyncClient, db_session: AsyncSession, contracte: ContracteManteniment, auth_headers: dict):
    # Creem revisions: una vençuda, una a 5 dies, una llunyana
    avui = datetime.now(timezone.utc).date()
    
    r1 = RevisionsContracte(
        empresa_id=contracte.empresa_id,
        contracte_id=contracte.id,
        data_prevista=avui - timedelta(days=2),
        estat="PENDENT"
    )
    r2 = RevisionsContracte(
        empresa_id=contracte.empresa_id,
        contracte_id=contracte.id,
        data_prevista=avui + timedelta(days=5),
        estat="PROGRAMADA"
    )
    r3 = RevisionsContracte(
        empresa_id=contracte.empresa_id,
        contracte_id=contracte.id,
        data_prevista=avui + timedelta(days=30),
        estat="PROGRAMADA"
    )
    db_session.add_all([r1, r2, r3])
    await db_session.commit()

    resp = await async_client.get("/gestio/contractes/alertes/venciments", headers=auth_headers)
    print(resp.text); assert resp.status_code == 200
    alertes = resp.json()
    
    assert len(alertes) == 2 # 1 vençuda (r1), 1 aprop (r2)
    
    # Comprovar si r1 va canviar estat a VENCUDA
    await db_session.refresh(r1)
    assert r1.estat == "VENCUDA"

@pytest.mark.asyncio
async def test_renovar_contracte(async_client: AsyncClient, db_session: AsyncSession, contracte: ContracteManteniment, auth_headers: dict):
    resp = await async_client.post(f"/gestio/contractes/{contracte.id}/renovar", json={"increment_percent": 10.0}, headers=auth_headers)
    print(resp.text); assert resp.status_code == 200
    
    await db_session.refresh(contracte)
    assert float(contracte.import_anual) == 1320.0
    assert contracte.data_inici == date(2026, 1, 1)
    assert contracte.data_fi == date(2027, 1, 1)

@pytest.mark.asyncio
async def test_baixa_contracte(async_client: AsyncClient, db_session: AsyncSession, contracte: ContracteManteniment, auth_headers: dict):
    # Crear revisio pendent que hauria de ser cancel·lada
    avui = datetime.now(timezone.utc).date()
    r = RevisionsContracte(
        empresa_id=contracte.empresa_id,
        contracte_id=contracte.id,
        data_prevista=avui + timedelta(days=10),
        estat="PROGRAMADA"
    )
    db_session.add(r)
    await db_session.commit()

    resp = await async_client.post(f"/gestio/contractes/{contracte.id}/baixa", json={"motiu": "El client no vol continuar"}, headers=auth_headers)
    print(resp.text); assert resp.status_code == 200
    
    await db_session.refresh(contracte)
    assert contracte.estat == "BAIXA"
    assert contracte.motiu_baixa == "El client no vol continuar"
    
    await db_session.refresh(r)
    assert r.estat == "CANCELADA"
