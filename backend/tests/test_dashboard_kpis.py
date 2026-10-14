import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.models import Empresa, OrdreTreball, Usuari, Client

@pytest.mark.asyncio
async def test_get_dashboard_hud_kpis(async_client: AsyncClient, db_session: AsyncSession, headers: dict):
    """Verifica que el HUD del dashboard calcula correctament els KPIs per al tenant."""
    empresa_id = headers["X-Empresa-ID"]
    emp_uuid = uuid.UUID(empresa_id)

    # 1. Crear empresa de test
    empresa = Empresa(
        id=emp_uuid,
        nom="Empresa Test HUD",
        nif=f"B{uuid.uuid4().hex[:8]}",
        subdomini=f"hud-{uuid.uuid4().hex[:6]}",
        pla_subscripcio="ENTERPRISE",
        estat_pagament="ACTIU",
    )
    db_session.add(empresa)
    await db_session.flush()

    # 2. Crear client
    client = Client(
        id=uuid.uuid4(),
        empresa_id=emp_uuid,
        codi="CLI-001",
        nif="B11223344",
        rao_social="Client Test HUD",
        adreca_fiscal="Carrer Major 1, Barcelona",
    )
    db_session.add(client)

    # 3. Crear operari
    operari = Usuari(
        id=uuid.uuid4(),
        empresa_id=emp_uuid,
        nif="11111111A",
        nom="Operari",
        cognoms="Test",
        rol="OPERARI",
        estat="ACTIU",
        estat_operatiu="DISPONIBLE",
    )
    db_session.add(operari)
    await db_session.flush()

    # 4. Crear OT assignada i en curs amb cap_de_colla_id
    ot = OrdreTreball(
        id=uuid.uuid4(),
        empresa_id=emp_uuid,
        codi=f"OT-{uuid.uuid4().hex[:5]}",
        client_id=client.id,
        titol="Manteniment actiu",
        adreca="Barcelona",
        estat="EN_CURS",
        cap_de_colla_id=operari.id,
    )
    db_session.add(ot)
    await db_session.flush()

    # Cridar endpoint HUD
    response = await async_client.get("/gestio/dashboard/hud", headers=headers)
    assert response.status_code == 200
    data = response.json()

    # Comprovar KPIs
    assert data["active_jobs"] >= 1
    assert data["teams_on_field"] == 1
    assert data["open_incidents"] == 0
