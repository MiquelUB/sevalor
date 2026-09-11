"""Alembic env.py amb suport per a SQLAlchemy async (asyncpg)."""
import asyncio
import os
import sys
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Afegim el directori pare (backend/) al sys.path per poder fer 'from app...'
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Importem la Base declarativa i tots els models perquè l'autogenerate els vegi
from app.core.db import Base  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.models import models  # noqa: F401, E402  -- registre de models

# Alembic Config
config = context.config

# Logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Permet que la URL provingui de l'entorn si està definida
if os.getenv("TEST_DATABASE_URL"):
    config.set_main_option("sqlalchemy.url", os.getenv("TEST_DATABASE_URL"))

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in 'online' mode amb async engine."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
