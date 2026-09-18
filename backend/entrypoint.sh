#!/bin/bash
# Entrypoint del backend SEVALOR.
# Aplica Alembic migrations automàticament abans d'arrencar uvicorn.

set -e

echo "[entrypoint] Aplicant Alembic migrations..."
python3 -m alembic upgrade head

echo "[entrypoint] Sincronitzant usuaris i dades base (seed)..."
python3 scripts/seed.py || echo "[entrypoint] Advertència: Error durant el seed (ignorat)"

echo "[entrypoint] Migrations i seed completats. Arrencant uvicorn..."

# Executem el CMD passat per Docker (uvicorn per defecte)
exec "$@"
