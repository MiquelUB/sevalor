"""Connexió asíncrona a la base de dades PostgreSQL amb SQLAlchemy 2.0 i asyncpg."""

from collections.abc import AsyncGenerator
from fastapi import Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

import os
from sqlalchemy.pool import NullPool

# Configuració del motor segons entorn
engine_kwargs: dict = {"echo": False, "pool_pre_ping": True}
if os.getenv("TESTING") == "1":
    engine_kwargs["poolclass"] = NullPool
else:
    engine_kwargs["pool_size"] = 10
    engine_kwargs["max_overflow"] = 20

engine = create_async_engine(
    settings.get_database_url(),
    **engine_kwargs,
)

# Fàbrica de sessions asíncrones
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Classe base per a tots els models SQLAlchemy."""
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Generador de sessions de base de dades asíncrones per a injecció de dependències."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_db_with_tenant_context(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """Generador de sessions amb RLS automàtic des del tenant extret pel middleware."""
    async with AsyncSessionLocal() as session:
        try:
            empresa_id = getattr(request.state, "empresa_id", None)
            is_superadmin = getattr(request.state, "is_superadmin", False)
            await set_tenant_context(session, empresa_id, is_superadmin)
            yield session
        finally:
            await session.close()


async def set_tenant_context(session: AsyncSession, empresa_id: str | None, is_superadmin: bool = False) -> None:
    """Injecta la variable de sessió app.current_empresa_id per activar les polítiques RLS de PostgreSQL."""
    if is_superadmin:
        await session.execute(text("RESET ROLE;"))
        await session.execute(
            text("SELECT set_config('app.is_superadmin', 'true', true);")
        )
    else:
        # Assignar el rol d'aplicació per fer complir RLS a PostgreSQL (els superusuaris ignorarien RLS)
        await session.execute(text("SET ROLE sevalor_app;"))
        await session.execute(
            text("SELECT set_config('app.is_superadmin', 'false', true);")
        )

    if empresa_id:
        await session.execute(
            text("SELECT set_config('app.current_empresa_id', :val, true);"),
            {"val": str(empresa_id)},
        )
    else:
        await session.execute(
            text("SELECT set_config('app.current_empresa_id', '', true);")
        )
