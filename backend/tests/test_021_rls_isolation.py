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

@pytest.mark.asyncio
async def test_celery_worker_session_rls():
    from app.workers.tasks import get_worker_session
    empresa_id = str(uuid.uuid4())
    async with get_worker_session(empresa_id) as session:
        # Check that the config is correctly set
        res = await session.execute(text("SHOW app.current_empresa_id;"))
        current_empresa_id = res.scalar()
        assert current_empresa_id == empresa_id


@pytest.mark.asyncio
async def test_rls_hard_economics_boss_only(admin_session: AsyncSession, db_session: AsyncSession):
    """Verifica la Barrera Econòmica Hard Layer a nivell de PostgreSQL RLS (Constitució §2.VI).
    
    1. Si el rol no és BOSS (ex. ENGINYER o OPERARI), qualsevol SELECT sobre taules
       econòmiques (factures_capcalera, auditories_post_obra) retorna EXACTAMENT 0 files.
    2. Si el rol és BOSS o SUPERADMIN, retorna les files del tenant.
    3. Si un altre tenant intenta accedir com a BOSS, retorna 0 files (aïllament multi-tenant).
    4. Si no es passa cap rol (fail-closed), retorna 0 files.
    """
    from app.models.models import AuditoriaPostObra, FacturaCapcalera

    tenant_a_id = uuid.uuid4()
    tenant_b_id = uuid.uuid4()

    tenant_a = Empresa(id=tenant_a_id, nom="Tenant Econ A", subdomini=f"ea-{tenant_a_id.hex[:6]}", nif=f"EA{tenant_a_id.hex[:6].upper()}")
    tenant_b = Empresa(id=tenant_b_id, nom="Tenant Econ B", subdomini=f"eb-{tenant_b_id.hex[:6]}", nif=f"EB{tenant_b_id.hex[:6].upper()}")
    admin_session.add_all([tenant_a, tenant_b])
    await admin_session.flush()

    client_a = Client(id=uuid.uuid4(), empresa_id=tenant_a_id, codi="CEA", rao_social="Client Econ A", nif="C99999999")
    admin_session.add(client_a)
    await admin_session.flush()

    ordre_a = OrdreTreball(id=uuid.uuid4(), empresa_id=tenant_a_id, client_id=client_a.id, codi=f"OT-{tenant_a_id.hex[:4]}", titol="OT Econ", adreca="Ad", estat="FINALITZADA")
    admin_session.add(ordre_a)
    await admin_session.flush()

    factura_a = FacturaCapcalera(
        id=uuid.uuid4(),
        empresa_id=tenant_a_id,
        client_id=client_a.id,
        numero_factura=101,
        serie="2026",
        base_imposable=5000.00,
        quota_iva=1050.00,
        liquid_exigible=6050.00,
        hash_sha256="e" * 64,
        estat_cobrament="PENDENT",
        estat_enviament="PENDENT",
    )
    auditoria_a = AuditoriaPostObra(
        id=uuid.uuid4(),
        empresa_id=tenant_a_id,
        ordre_treball_id=ordre_a.id,
        marge_previst_percentatge=35.00,
        marge_real_liquidat_percentatge=28.50,
        desviacio_hores=2.5,
    )
    admin_session.add_all([factura_a, auditoria_a])
    await admin_session.commit()

    # A. Com a ENGINYER (Veto Hard Layer a nivell de PostgreSQL RLS)
    await db_session.execute(text("SET ROLE sevalor_app;"))
    await db_session.execute(text("SELECT set_config('app.is_superadmin', 'false', true);"))
    await db_session.execute(text(f"SELECT set_config('app.current_empresa_id', '{str(tenant_a_id)}', true);"))
    await db_session.execute(text("SELECT set_config('app.current_user_role', 'ENGINYER', true);"))

    res_fac_eng = await db_session.execute(text("SELECT id FROM factures_capcalera"))
    assert len(res_fac_eng.fetchall()) == 0, "VIOLACIÓ CONSTITUCIONAL: L'enginyer ha pogut llegir factures_capcalera a PostgreSQL!"

    res_aud_eng = await db_session.execute(text("SELECT id FROM auditories_post_obra"))
    assert len(res_aud_eng.fetchall()) == 0, "VIOLACIÓ CONSTITUCIONAL: L'enginyer ha pogut llegir auditories_post_obra a PostgreSQL!"

    # B. Com a OPERARI
    await db_session.execute(text("SELECT set_config('app.current_user_role', 'OPERARI', true);"))
    res_fac_op = await db_session.execute(text("SELECT id FROM factures_capcalera"))
    assert len(res_fac_op.fetchall()) == 0, "VIOLACIÓ CONSTITUCIONAL: L'operari ha pogut llegir factures_capcalera a PostgreSQL!"

    # C. Sense rol definit (fail-closed)
    await db_session.execute(text("SELECT set_config('app.current_user_role', '', true);"))
    res_fac_none = await db_session.execute(text("SELECT id FROM factures_capcalera"))
    assert len(res_fac_none.fetchall()) == 0, "VIOLACIÓ CONSTITUCIONAL: Sessió anònima ha pogut llegir factures_capcalera!"

    # D. Com a BOSS del Tenant A (autoritzat)
    await db_session.execute(text("SELECT set_config('app.current_user_role', 'BOSS', true);"))
    res_fac_boss = await db_session.execute(text("SELECT id, base_imposable FROM factures_capcalera"))
    rows_fac = res_fac_boss.fetchall()
    assert len(rows_fac) == 1
    assert str(rows_fac[0].id) == str(factura_a.id)

    res_aud_boss = await db_session.execute(text("SELECT id, marge_real_liquidat_percentatge FROM auditories_post_obra"))
    rows_aud = res_aud_boss.fetchall()
    assert len(rows_aud) == 1
    assert str(rows_aud[0].id) == str(auditoria_a.id)

    # E. Com a BOSS del Tenant B (aïllament multi-tenant)
    await db_session.execute(text(f"SELECT set_config('app.current_empresa_id', '{str(tenant_b_id)}', true);"))
    res_fac_boss_b = await db_session.execute(text("SELECT id FROM factures_capcalera"))
    assert len(res_fac_boss_b.fetchall()) == 0, "VIOLACIÓ CONSTITUCIONAL: El BOSS del Tenant B ha pogut veure factures del Tenant A!"

