# SEVALOR Backend

Backend multi-tenant (B2B) per a CampoPro Suite: gestió de clients, proveïdors, magatzem, picking, plànols, notificacions, comptabilitat Veri*factu, operaris PWA i bot de Telegram.

## Tecnologies

- Python 3.12 + FastAPI + SQLAlchemy 2.0 (async)
- PostgreSQL 15+ PostGIS amb **Row-Level Security (RLS)** per a multi-tenancy
- Redis (broker Celery + rate-limit)
- Celery (workers, beat, tasques asíncrones)
- Alembic (migrations)
- bcrypt + JWT per a autenticació
- aiogram per al bot de Telegram
- ReportLab per a PDFs Veri*factu

## Comandes útils

### Tests
```bash
docker exec -e TEST_DATABASE_URL="postgresql+asyncpg://postgres:postgres@db:5432/sevalor" \
    -e TESTING="1" sevalor_backend python3 -m pytest tests/test_flux_integracio.py -v
```

### Alembic (Migrations)
```bash
# Generar una nova migration basada en canvis als models ORM
docker exec -e TEST_DATABASE_URL="postgresql+asyncpg://postgres:postgres@db:5432/sevalor" \
    sevalor_backend python3 -m alembic revision --autogenerate -m "descripció"

# Aplicar totes les migrations pendents
docker exec -e TEST_DATABASE_URL="postgresql+asyncpg://postgres:postgres@db:5432/sevalor" \
    sevalor_backend python3 -m alembic upgrade head

# Marcar una versió com ja aplicada (sense executar canvis)
docker exec -e TEST_DATABASE_URL="postgresql+asyncpg://postgres:postgres@db:5432/sevalor" \
    sevalor_backend python3 -m alembic stamp head
```

## Desplegament a producció

### Variables d'entorn requerides (⚠️ mai versionades al .env real)
- `SECRET_KEY` — Generar amb `python -c "import secrets; print(secrets.token_urlsafe(32))"`
- `DATABASE_URL` — URL completa `postgresql+asyncpg://user:pass@host:port/db`
- `REDIS_URL` — `redis://:pass@host:6379/0`
- `TELEGRAM_BOT_TOKEN` — Token de @BotFather
- `ENVIRONMENT=production`
- `BACKEND_CORS_ORIGINS` — Llista JSON de dominis permesos

### Passos
1. Construir la imatge: `docker compose build backend`
2. Aplicar Alembic: `docker compose run --rm backend alembic upgrade head`
3. Arrencar: `docker compose up -d backend celery_worker celery_beat bot pwa nginx`
4. Verificar `/health` a través de nginx: `curl https://sevalor.app/health`

## Cobertura de tests

| Bloc | Tests | Estat |
|------|-------|-------|
| Gestió (clients, proveïdors, magatzem, picking, planols, notificacions) | 17 | ✅ |
| Copilot IA | 2 | ✅ |
| Operari PWA (login, jornada) | 2 | ✅ |
| Superadmin + RLS + Telemetria | 4 | ✅ + 1 skip |
| **Total** | **25** | **24 ✅ + 1 skip** |

## Estructura

```
backend/
├── alembic/                 # Migrations
│   └── versions/            # Scripts de migració
├── alembic.ini              # Config Alembic
├── app/
│   ├── api/v1/              # Endpoints REST
│   │   ├── gestio/          # CRUD empreses (clients, proveïdors, magatzem...)
│   │   ├── operari_pwa/     # Endpoints per a operaris mòbils
│   │   ├── superadmin/      # Superadministrador
│   │   └── telemetria.py    # KPIs
│   ├── core/                # Config, seguretat, RLS, middleware
│   ├── models/              # Models SQLAlchemy ORM
│   ├── services/            # Lògica de negoci (Veri*factu, Outbox AEAT, etc.)
│   ├── workers/             # Tasques Celery
│   └── main.py              # App FastAPI principal
├── tests/                   # Tests d'integració
├── Dockerfile
├── entrypoint.sh            # Hook que aplica Alembic + arrenca uvicorn
└── requirements.txt
```
