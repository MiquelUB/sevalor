import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from app.main import app

@pytest.mark.asyncio
async def test_alta_ordre_treball(admin_session, headers, boss_token):
    token, empresa_id = boss_token
    boss_nif = "B" + str(uuid.uuid4())[:8].upper()
    
    # 1. Crear empresa
    await admin_session.execute(
        text("INSERT INTO empreses (id, nom, nif, subdomini, pla_subscripcio, estat_pagament) VALUES (:id, 'Test Feines', :nif, :sub, 'STARTER', 'ACTIU')"),
        {"id": empresa_id, "nif": boss_nif, "sub": "testfeina-" + str(uuid.uuid4())[:5]}
    )
    
    # 2. Crear client per tenir client_id
    client_id = str(uuid.uuid4())
    await admin_session.execute(
        text("INSERT INTO clients (id, empresa_id, codi, rao_social, nif) VALUES (:id, :emp, 'CLI-1', 'Client FEINA', '12345678A')"),
        {"id": client_id, "emp": empresa_id}
    )
    
    # 3. Crear operari per tenir cap_de_colla_id
    operari_id = str(uuid.uuid4())
    await admin_session.execute(
        text("INSERT INTO usuaris (id, empresa_id, nif, nom, cognoms, rol, estat) VALUES (:id, :emp, 'OP-999', 'Paco', 'Garcia', 'OPERARI', 'ACTIU')"),
        {"id": operari_id, "emp": empresa_id}
    )
    await admin_session.commit()
    
    payload = {
        "codi": "OT-001",
        "client_id": client_id,
        "titol": "Revisió Instal·lació",
        "adreca": "Carrer de la Indústria 42, BCN",
        "descripcio": "Revisió general",
        "estat": "PENDENT",
        "data_planificacio": "2027-01-01",
        "cap_de_colla_id": operari_id
    }
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/api/v1/gestio/feines", json=payload, headers=headers)
        assert res.status_code == 201, f"Expected 201, got {res.status_code}: {res.text}"
        data = res.json()
        assert data["codi"] == "OT-001"
        assert data["titol"] == "Revisió Instal·lació"
        
        # Llistat (RF-01)
        res_list = await ac.get("/api/v1/gestio/feines", headers=headers)
        assert res_list.status_code == 200
        llista = res_list.json()
        assert len(llista) == 1
        assert llista[0]["codi"] == "OT-001"

        # Duplicat codi
        res_dup = await ac.post("/api/v1/gestio/feines", json=payload, headers=headers)
        assert res_dup.status_code == 400
        assert "registrat" in res_dup.json()["detail"]
