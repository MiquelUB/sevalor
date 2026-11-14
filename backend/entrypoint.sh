#!/bin/bash
# Entrypoint del backend SEVALOR.
# Aplica Alembic migrations i seed només en el contenidor principal (uvicorn),
# amb timeouts estrictes i alliberament de bloquejos per evitar 502 Bad Gateway en desplegaments.

if [ "$1" = "uvicorn" ] || [ -z "$1" ]; then
    echo "[entrypoint] Alliberant possibles transaccions bloquejades (idle in transaction) a PostgreSQL..."
    python3 -c "
import asyncio
from sqlalchemy import text
from app.core.db import engine

async def _unlock():
    try:
        async with engine.begin() as conn:
            await conn.execute(text('''
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = current_database()
                  AND pid <> pg_backend_pid()
                  AND (
                    state = 'idle in transaction'
                    OR (wait_event_type = 'Lock' AND state = 'active')
                  );
            '''))
    except Exception as e:
        print(f'[entrypoint] Avís unlock PG: {e}')
    finally:
        await engine.dispose()

asyncio.run(_unlock())
" || true

    echo "[entrypoint] Aplicant Alembic migrations (timeout 25s)..."
    timeout 25s python3 -m alembic upgrade head || echo "[entrypoint] Advertència: Error o timeout durant Alembic migrations (ignorat per no bloquejar uvicorn)"

    echo "[entrypoint] Sincronitzant usuaris i dades base (seed, timeout 20s)..."
    timeout 20s python3 scripts/seed.py || echo "[entrypoint] Advertència: Error o timeout durant el seed (ignorat)"

    echo "[entrypoint] Migrations i seed completats. Arrencant uvicorn..."
else
    echo "[entrypoint] Iniciant procés worker ($1)..."
fi

# Executem el CMD passat per Docker (uvicorn o celery)
exec "$@"
