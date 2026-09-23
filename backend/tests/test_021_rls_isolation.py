import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Article, Client, Empresa, OrdreTreball, Vehicle


@pytest.mark.asyncio
async def test_rls_database_isolation(admin_session: AsyncSession, db_session: AsyncSession):
    tenant_a_id = uuid.uuid4()
    tenant_b_id = uuid.uuid4()

    tenant_a = Empresa(id=tenant_a_id, nom="Tenant A", subdomini=f"a-{tenant_a_id.hex[:6]}", nif="A11111111")
    tenant_b = Empresa(id=tenant_b_id, nom="Tenant B", subdomini=f"b-{tenant_b_id.hex[:6]}", nif="B22222222")
    admin_session.add_all([tenant_a, tenant_b])
    await admin_session.commit()

    client_a = Client(id=uuid.uuid4(), empresa_id=tenant_a_id, codi="CA", rao_social="Cliente A", nif="C11111111")
    client_b = Client(id=uuid.uuid4(), empresa_id=tenant_b_id, codi="CB", rao_social="Cliente B", nif="C22222222")
    admin_session.add_all([client_a, client_b])
    await admin_session.commit()

    article_a = Article(id=uuid.uuid4(), empresa_id=tenant_a_id, nom="Article A", referencia_inventari="A", familia="F")
    article_b = Article(id=uuid.uuid4(), empresa_id=tenant_b_id, nom="Article B", referencia_inventari="B", familia="F")

    ordre_a = OrdreTreball(id=uuid.uuid4(), empresa_id=tenant_a_id, client_id=client_a.id, codi="OA", titol="TOA", adreca="Ad", estat="PENDENT")
    ordre_b = OrdreTreball(id=uuid.uuid4(), empresa_id=tenant_b_id, client_id=client_b.id, codi="OB", titol="TOB", adreca="Ad", estat="PENDENT")

    vehicle_a = Vehicle(id=uuid.uuid4(), empresa_id=tenant_a_id, matricula="1111AAA", marca="M", model="Mod")
    vehicle_b = Vehicle(id=uuid.uuid4(), empresa_id=tenant_b_id, matricula="2222BBB", marca="M", model="Mod")

    admin_session.add_all([article_a, article_b, ordre_a, ordre_b, vehicle_a, vehicle_b])
    await admin_session.commit()

    # 2. PRUEBA DE AISLAMIENTO RLS (Simular sesión normal como Tenant A)
    await db_session.execute(text("SET ROLE sevalor_app;"))
    await db_session.execute(text("SELECT set_config('app.is_superadmin', 'false', true);"))
    await db_session.execute(text(f"SELECT set_config('app.current_empresa_id', '{str(tenant_a_id)}', true);"))

    # Query: Dame todos
    res_clients = await db_session.execute(text("SELECT id, empresa_id FROM clients"))
    rows_c = res_clients.fetchall()
    assert len(rows_c) == 1
    assert str(rows_c[0].empresa_id) == str(tenant_a_id)

    res_articles = await db_session.execute(text("SELECT id, empresa_id FROM articles"))
    rows_a = res_articles.fetchall()
    assert len(rows_a) == 1
    assert str(rows_a[0].empresa_id) == str(tenant_a_id)

    res_ordres = await db_session.execute(text("SELECT id, empresa_id FROM ordres_treball"))
    rows_o = res_ordres.fetchall()
    assert len(rows_o) == 1
    assert str(rows_o[0].empresa_id) == str(tenant_a_id)

    res_vehicles = await db_session.execute(text("SELECT id, empresa_id FROM vehicles"))
    rows_v = res_vehicles.fetchall()
    assert len(rows_v) == 1
    assert str(rows_v[0].empresa_id) == str(tenant_a_id)
