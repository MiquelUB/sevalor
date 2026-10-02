import pytest
import uuid
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.models import Empresa, Client
from app.models.contractes import ContracteManteniment, ContractesMantenimentFinques, RevisionsContracte
from datetime import date

pytestmark = pytest.mark.asyncio

async def test_contractes_rls_isolation(admin_session: AsyncSession, db_session: AsyncSession):
    # Crear dues empreses
    tenant_a_id = uuid.uuid4()
    tenant_b_id = uuid.uuid4()
    
    tenant_a = Empresa(id=tenant_a_id, nom="Tenant A", subdomini=f"a-{tenant_a_id.hex[:6]}", nif="A11111111")
    tenant_b = Empresa(id=tenant_b_id, nom="Tenant B", subdomini=f"b-{tenant_b_id.hex[:6]}", nif="B22222222")
    admin_session.add_all([tenant_a, tenant_b])
    await admin_session.commit()
    
    # Crear clients
    client_a = Client(id=uuid.uuid4(), empresa_id=tenant_a_id, codi="CA", rao_social="Client A", nif="C11111111")
    client_b = Client(id=uuid.uuid4(), empresa_id=tenant_b_id, codi="CB", rao_social="Client B", nif="C22222222")
    admin_session.add_all([client_a, client_b])
    await admin_session.commit()

    # Crear contractes
    contracte_a = ContracteManteniment(id=uuid.uuid4(), empresa_id=tenant_a_id, client_id=client_a.id, numero_contracte="CA-001", data_inici=date.today(), import_anual=1000.0, periodicitat="ANUAL")
    contracte_b = ContracteManteniment(id=uuid.uuid4(), empresa_id=tenant_b_id, client_id=client_b.id, numero_contracte="CB-001", data_inici=date.today(), import_anual=2000.0, periodicitat="MENSUAL")
    
    admin_session.add_all([contracte_a, contracte_b])
    await admin_session.commit()
    
    # Simular sessió normal com a Tenant A
    await db_session.execute(text("SET ROLE sevalor_app;"))
    await db_session.execute(text("SELECT set_config('app.is_superadmin', 'false', true);"))
    await db_session.execute(text(f"SELECT set_config('app.current_empresa_id', '{str(tenant_a_id)}', true);"))
    
    # Comprovar que només veu el seu contracte
    result = await db_session.execute(text("SELECT id, empresa_id FROM contractes_manteniment"))
    rows = result.fetchall()
    
    assert len(rows) == 1
    assert str(rows[0].empresa_id) == str(tenant_a_id)
    assert str(rows[0].id) == str(contracte_a.id)
