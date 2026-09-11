#!/bin/bash
# Entrypoint del backend SEVALOR.
# Aplica Alembic migrations automàticament abans d'arrencar uvicorn.

set -e

echo "[entrypoint] Aplicant Alembic migrations..."
python3 -m alembic upgrade head

echo "[entrypoint] Migrations aplicades. Arrencant uvicorn..."

# Executem el CMD passat per Docker (uvicorn per defecte)
exec "$@"
