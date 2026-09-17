"""Configuració de fixtures per a Pytest amb aïllament SAVEPOINT per test.

Compleix Audotoria_i_Normativa_Tests_Backend.md:
- Prohibició total de mocks al backend (crides reals a PostgreSQL)
- Aïllament SAVEPOINT (join_transaction_mode="create_savepoint")
- Zero warnings de loops asíncrons
- Sobreescriu TOTES les dependències de base de dades (get_db i get_db_with_tenant_context)"""

import asyncio
import os
import uuid
import jwt
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text, pool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.main import app
from app.core.db import get_db, get_db_with_tenant_context

# Desactivar rate‑limiting si estem en mode testing
if os.getenv("TESTING") == "1":
    if hasattr(app.state, "limiter"):
        app.state.limiter.enabled = False

TEST_DB_URL = os.getenv(
    "TEST_DATABASE_URL",
    f"postgresql+asyncpg://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_SERVER}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}",
)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_database():
    """Initializes the database schema and RLS policies for testing before any tests run."""
    engine = create_async_engine(TEST_DB_URL, echo=False)
    
    from app.core.db import Base
    from app.models import models
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
        await conn.execute(text("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'sevalor_app') THEN
                CREATE ROLE sevalor_app;
            END IF;
        END
        $$;
        """))
        await conn.execute(text("GRANT USAGE ON SCHEMA public TO sevalor_app;"))
        await conn.execute(text("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO sevalor_app;"))
        await conn.execute(text("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO sevalor_app;"))
        await conn.execute(text("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO sevalor_app;"))
        await conn.execute(text("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO sevalor_app;"))
    
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Fixture de sessió de BD amb SAVEPOINT: cada test veu un entorn aïllat i fa rollback al final."""
    engine = create_async_engine(
        TEST_DB_URL,
        echo=False,
        poolclass=pool.NullPool,
    )
    async with engine.connect() as conn:
        trans = await conn.begin()
        async_session = AsyncSession(
            bind=conn,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        yield async_session
        await trans.rollback()
    await engine.dispose()


@pytest.fixture(scope="function", autouse=True)
def override_get_db(db_session: AsyncSession):
    """Sobrescriu TOTES les dependències de BD perquè apuntin a la sessió de test.

    Sobrescriu tant get_db com get_db_with_tenant_context perquè els endpoints
    que usin qualsevol de les dues vegin la mateixa transacció aïllada.
    """

    async def _get_test_db():
        yield db_session

    async def _get_test_db_tenant_context():
        yield db_session

    app.dependency_overrides[get_db] = _get_test_db
    app.dependency_overrides[get_db_with_tenant_context] = _get_test_db_tenant_context
    yield
    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def admin_session(db_session: AsyncSession) -> AsyncGenerator[AsyncSession, None]:
    """Sessió de BD amb permisos de SUPERADMIN per a fixtures d'administració."""
    await db_session.execute(text("SET LOCAL app.is_superadmin = 'true';"))
    yield db_session


@pytest.fixture(scope="function")
def boss_token():
    """Token JWT vàlid per a un usuari BOSS."""
    empresa_id = str(uuid.uuid4())
    payload = {
        "sub": str(uuid.uuid4()),
        "rol": "BOSS",
        "empresa_id": empresa_id,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return token, empresa_id


@pytest.fixture(scope="function")
def headers(boss_token):
    """Headers HTTP amb token d'autenticació BOSS i tenant ID."""
    token, empresa_id = boss_token
    return {
        "Authorization": f"Bearer {token}",
        "X-Empresa-ID": empresa_id,
    }


@pytest_asyncio.fixture(scope="function")
async def async_client(headers):
    """Client HTTP asíncron per a tests d'integració.

    Nota: httpx.AsyncClient amb ASGITransport NO passa pel TenantMiddleware
    de Starlette. Per això afegim X-Empresa-ID als headers per defecte.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test/api/v1", headers=headers
    ) as client:
        yield client