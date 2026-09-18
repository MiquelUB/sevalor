from app.models.models import Empresa, Usuari, Client
import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from app.main import app

@pytest.mark.asyncio
async def test_alta_planol(admin_session, headers, boss_token):
    token, empresa_id = boss_token
    boss_nif = "B" + str(uuid.uuid4())[:8].upper()
    
    # 1. Crear empresa
    admin_session.add(Empresa(
        id=uuid.UUID(empresa_id), nom='Test Planols', nif=boss_nif, subdomini='testplan-' + str(uuid.uuid4())[:5], pla_subscripcio='STARTER', estat_pagament='ACTIU'
    ))
    
    # 2. Crear carpeta per al planol
    carpeta_id = str(uuid.uuid4())
    from app.models.models import CarpetaPlanols
    admin_session.add(CarpetaPlanols(
        id=uuid.UUID(carpeta_id), empresa_id=uuid.UUID(empresa_id), nom='Carpeta Principal', categoria='CLIENTS'
    ))
    await admin_session.flush()
    
    payload = {
        "titol": "Plànol Planta Baixa",
        "codi_referencia": "PB-001",
        "carpeta_id": carpeta_id,
        "tipus_fitxer": "PDF",
        "fitxer_path": "/docs/planols/pb-001.pdf",
        "mida_bytes": 1048576,
        "es_georeferenciat": False
    }
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/api/v1/gestio/planols", json=payload, headers=headers)
        assert res.status_code == 201, f"Expected 201, got {res.status_code}: {res.text}"
        data = res.json()
        assert data["codi_referencia"] == "PB-001"
        assert data["titol"] == "Plànol Planta Baixa"
        
        # Llistat (RF-01)
        res_list = await ac.get(f"/api/v1/gestio/planols?carpeta_id={carpeta_id}", headers=headers)
        assert res_list.status_code == 200
        llista = res_list.json()
        assert len(llista) == 1
        assert llista[0]["codi_referencia"] == "PB-001"

        # Duplicat codi
        res_dup = await ac.post("/api/v1/gestio/planols", json=payload, headers=headers)
        assert res_dup.status_code == 400
        assert "registrat" in res_dup.json()["detail"]
