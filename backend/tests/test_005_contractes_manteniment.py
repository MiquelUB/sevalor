import uuid
from datetime import date
import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.models import Empresa, Client
from app.models.contractes import ContracteManteniment, RevisionsContracte
from app.services.contractes_service import generar_ordres_preventives_per_contracte

pytestmark = pytest.mark.asyncio

async def test_crear_contracte(async_client: AsyncClient, admin_session: AsyncSession, db_session: AsyncSession, boss_token):
    token, empresa_id = boss_token
    
    # Creem empresa i client
    boss_nif = "B" + str(uuid.uuid4())[:8].upper()
    admin_session.add(Empresa(
        id=uuid.UUID(empresa_id), nom='Test Contractes', nif=boss_nif, subdomini='testct-' + str(uuid.uuid4())[:5], pla_subscripcio='STARTER', estat_pagament='ACTIU'
    ))
    await admin_session.flush()
    
    client_id = uuid.uuid4()
    admin_session.add(Client(
        id=client_id, empresa_id=uuid.UUID(empresa_id), codi='CLI-CT', rao_social='Client Contracte', nif='CT123456'
    ))
    await admin_session.commit()
    
    headers = {"Authorization": f"Bearer {token}", "X-Empresa-ID": str(empresa_id)}
    
    payload = {
        "client_id": str(client_id),
        "numero_contracte": "CT-2026-001",
        "data_inici": date.today().isoformat(),
        "import_anual": 1500.50,
        "periodicitat": "MENSUAL",
        "estat": "ACTIU",
        "finques_ids": []
    }
    
    resp = await async_client.post("/gestio/contractes/", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["numero_contracte"] == "CT-2026-001"
    
    contracte_id = data["id"]
    
    # Llistar contractes
    resp_list = await async_client.get("/gestio/contractes/")
    assert resp_list.status_code == 200
    assert len(resp_list.json()) > 0
    
    # Detall contracte
    resp_detail = await async_client.get(f"/gestio/contractes/{contracte_id}")
    assert resp_detail.status_code == 200
    assert resp_detail.json()["numero_contracte"] == "CT-2026-001"

async def test_servei_generacio_ot(db_session: AsyncSession):
    # Setup de dades saltant RLS localment
    empresa_id = uuid.uuid4()
    await db_session.execute(
        text("INSERT INTO empreses (id, nom, nif) VALUES (:id, :nom, :nif) ON CONFLICT DO NOTHING"),
        {"id": empresa_id, "nom": "Empresa OT", "nif": "EOT123"}
    )
    
    client_id = uuid.uuid4()
    await db_session.execute(
        text("INSERT INTO clients (id, empresa_id, codi, rao_social, nif) VALUES (:id, :e_id, :codi, :rao, :nif) ON CONFLICT DO NOTHING"),
        {"id": client_id, "e_id": empresa_id, "codi": "C-OT", "rao": "Client OT", "nif": "COT123"}
    )
    
    contracte_id = uuid.uuid4()
    await db_session.execute(
        text("""
        INSERT INTO contractes_manteniment 
        (id, empresa_id, client_id, numero_contracte, data_inici, import_anual, periodicitat) 
        VALUES (:id, :e_id, :c_id, :num, :data, :imp, :per)
        """),
        {"id": contracte_id, "e_id": empresa_id, "c_id": client_id, "num": "CT-OT-1", "data": date.today(), "imp": 1000.0, "per": "MENSUAL"}
    )
    
    await db_session.commit()
    
    # Obtenir el contracte
    # Com estem al service no estem en context tenant segurament, o sí si utilitzem get_worker_session
    # Simularem com fa el worker
    await db_session.execute(text("SET ROLE sevalor_app;"))
    await db_session.execute(text("SELECT set_config('app.is_superadmin', 'false', true);"))
    await db_session.execute(text(f"SELECT set_config('app.current_empresa_id', '{str(empresa_id)}', true);"))
    
    from sqlalchemy import select
    res = await db_session.execute(select(ContracteManteniment).where(ContracteManteniment.id == contracte_id))
    contracte = res.scalars().first()
    
    # Generar ordres
    noves_ots = await generar_ordres_preventives_per_contracte(contracte, db_session)
    
    # Comprovem que s'han generat
    assert len(noves_ots) > 0
    
    # Verifiquem a la bd
    res_ots = await db_session.execute(text(f"SELECT id FROM ordres_treball WHERE empresa_id = '{str(empresa_id)}' AND codi LIKE 'PREV-%'"))
    ots = res_ots.fetchall()
    assert len(ots) > 0
    
    res_revisions = await db_session.execute(text(f"SELECT id FROM revisions_contracte WHERE contracte_id = '{str(contracte_id)}'"))
    revisions = res_revisions.fetchall()
    assert len(revisions) > 0
    assert len(revisions) == len(ots)
