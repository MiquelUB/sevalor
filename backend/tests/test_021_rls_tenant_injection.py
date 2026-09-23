import uuid

import pytest
from sqlalchemy import text

from app.core.db import get_db_with_tenant_context
from app.core.context import tenant_context, superadmin_context

class MockRequest:
    class State:
        pass
    def __init__(self, empresa_id, is_superadmin=False):
        self.state = self.State()
        self.state.empresa_id = empresa_id
        self.state.is_superadmin = is_superadmin

@pytest.mark.asyncio
async def test_tenant_injection_dependency():
    """Test para verificar la inyección del contexto RLS (Tarea 1.1)."""
    fake_tenant_id = str(uuid.uuid4())
    req = MockRequest(empresa_id=fake_tenant_id)
    token_tenant = tenant_context.set(fake_tenant_id)
    token_superadmin = superadmin_context.set(False)

    try:
        db_gen = get_db_with_tenant_context(req)
        session = await anext(db_gen)

        try:
            result = await session.execute(text("SELECT current_setting('app.current_empresa_id', true)"))
            tenant_in_db = result.scalar()
            assert tenant_in_db == fake_tenant_id, f"El tenant en DB es {tenant_in_db}, se esperaba {fake_tenant_id}"

            result_role = await session.execute(text("SELECT current_setting('app.is_superadmin', true)"))
            is_super = result_role.scalar()
            assert is_super == 'false'

        finally:
            await session.close()
            try:
                await anext(db_gen)
            except StopAsyncIteration:
                pass
    finally:
        tenant_context.reset(token_tenant)
        superadmin_context.reset(token_superadmin)

@pytest.mark.asyncio
async def test_tenant_injection_superadmin():
    req = MockRequest(empresa_id=None, is_superadmin=True)
    token_tenant = tenant_context.set(None)
    token_superadmin = superadmin_context.set(True)

    try:
        db_gen = get_db_with_tenant_context(req)
        session = await anext(db_gen)
        try:
            result_role = await session.execute(text("SELECT current_setting('app.is_superadmin', true)"))
            is_super = result_role.scalar()
            assert is_super == 'true'
        finally:
            await session.close()
            try:
                await anext(db_gen)
            except StopAsyncIteration:
                pass
    finally:
        tenant_context.reset(token_tenant)
        superadmin_context.reset(token_superadmin)
