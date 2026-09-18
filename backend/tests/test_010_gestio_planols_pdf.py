import pytest
import uuid
import os
from unittest.mock import patch
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.models.models import Empresa, PlanolBase, CarpetaPlanol
from sqlalchemy import text

@pytest.mark.asyncio
async def test_generar_pdf_planol(admin_session, headers, boss_token):
    token, empresa_id = boss_token
    boss_nif = "B" + str(uuid.uuid4())[:8].upper()
    
    admin_session.add(Empresa(
        id=uuid.UUID(empresa_id), nom='Test Planols', nif=boss_nif, subdomini='planols-' + str(uuid.uuid4())[:5], pla_subscripcio='STARTER', estat_pagament='ACTIU'
    ))
    await admin_session.flush()
    
    carpeta = CarpetaPlanol(
        id=uuid.uuid4(),
        empresa_id=uuid.UUID(empresa_id),
        nom="Carpeta Test", categoria="CLIENTS"
    )
    admin_session.add(carpeta)
    await admin_session.flush()

    planol_id = uuid.uuid4()
    planol = PlanolBase(
        id=planol_id,
        empresa_id=uuid.UUID(empresa_id),
        carpeta_id=carpeta.id,
        titol="Plànol Finca Test",
        codi_referencia="PLAN-001",
        tipus_fitxer="DXF",
        fitxer_path="/test.dxf",
        mida_bytes=1000
    )
    admin_session.add(planol)
    await admin_session.flush()

    from app.workers.tasks import generar_informe_planol_pdf
    res_worker = generar_informe_planol_pdf(str(planol_id), empresa_id)
    assert res_worker["status"] == "SUCCESS"
    assert os.path.exists(res_worker["path"])

    with patch('app.api.v1.gestio.planols.generar_informe_planol_pdf.delay') as mock_delay:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            res = await ac.post(f"/api/v1/gestio/planols/{planol_id}/exportar-pdf", headers=headers)
            assert res.status_code == 202
            assert res.json()["estat"] == "EN_PROCES"
            mock_delay.assert_called_once_with(str(planol_id), empresa_id)
