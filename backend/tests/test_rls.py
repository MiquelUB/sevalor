"""Tests d'integració d'aïllament multi-tenant amb Row Level Security (RLS) de PostgreSQL."""

import uuid
import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

from app.models.models import Client, Empresa
from app.core.config import settings
from app.core.db import set_tenant_context

@pytest.mark.asyncio
async def test_tenant_isolation_rls(admin_session):
    """Verifica que l'Inquilí A mai veu les dades de l'Inquilí B sota cap circumstància (RLS natiu)."""
    
    # 1. Creem dades de prova per a 2 tenants usant la sessió admin (bypasseja RLS temporalment per setup)
    empresa_a = Empresa(
        id=uuid.uuid4(),
        nom="Instal·lacions Agràries A, SL",
        nif=f"B{uuid.uuid4().hex[:8].upper()}",
        subdomini=f"empresa-a-{uuid.uuid4().hex[:6]}",
    )
    empresa_b = Empresa(
        id=uuid.uuid4(),
        nom="Sistemes de Reg B, SL",
        nif=f"B{uuid.uuid4().hex[:8].upper()}",
        subdomini=f"empresa-b-{uuid.uuid4().hex[:6]}",
    )
    admin_session.add_all([empresa_a, empresa_b])
    await admin_session.flush()

    client_a = Client(
        id=uuid.uuid4(),
        empresa_id=empresa_a.id,
        codi="CLI-0001",
        rao_social="Finca Oliveres Mas Nou",
        nif="A11111111",
    )
    client_b = Client(
        id=uuid.uuid4(),
        empresa_id=empresa_b.id,
        codi="CLI-0001",
        rao_social="Celler Vall de Roures",
        nif="B22222222",
    )
    admin_session.add_all([client_a, client_b])
    await admin_session.flush()
    
    # Perquè les polítiques RLS funcionin, cal establir el context de tenant.
    # L'admin_session ja és dins un savepoint on es veuen aquestes dades.
    # Simulem un entorn de l'usuari A dins la mateixa connexió configurant RLS localment
    
    await set_tenant_context(admin_session, str(empresa_a.id), is_superadmin=False)
    
    # Executem la consulta general sota el context de l'Empresa A
    result_all_a = await admin_session.execute(select(Client))
    clients_visibles_a = result_all_a.scalars().all()
    
    assert len(clients_visibles_a) >= 1
    # Ha d'haver-hi el seu client
    assert any(c.id == client_a.id for c in clients_visibles_a), "No es veu el propi client"
    # NO pot haver-hi el client B
    assert not any(c.id == client_b.id for c in clients_visibles_a), "BRETXA RLS: L'inquilí A pot veure dades de B"

    # Verificació amb l'Empresa B
    await set_tenant_context(admin_session, str(empresa_b.id), is_superadmin=False)
    
    result_all_b = await admin_session.execute(select(Client))
    clients_visibles_b = result_all_b.scalars().all()
    
    assert len(clients_visibles_b) >= 1
    assert any(c.id == client_b.id for c in clients_visibles_b), "No es veu el propi client"
    assert not any(c.id == client_a.id for c in clients_visibles_b), "BRETXA RLS: L'inquilí B pot veure dades d'A"
    
    # Restablim el superadmin per permetre el rollback automàtic net
    await set_tenant_context(admin_session, None, is_superadmin=True)

