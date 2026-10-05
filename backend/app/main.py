import os
import traceback
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from app.api.v1.auth import router as auth_router
from app.api.v1.gestio.cerca import router as cerca_router
from app.api.v1.gestio.cerca import spotlight_router
from app.api.v1.gestio.clients import router as clients_router
from app.api.v1.gestio.comptabilitat import router as comptabilitat_router
from app.api.v1.gestio.configuracio import obtenir_dades_empresa, obtenir_marca_camaleonica
from app.api.v1.gestio.configuracio import router as configuracio_router
from app.api.v1.gestio.contractes import router as contractes_router
from app.api.v1.gestio.copilot import router as copilot_router
from app.api.v1.gestio.dashboard import router as dashboard_router
from app.api.v1.gestio.economia import router as economia_router
from app.api.v1.gestio.feines import intervencions_router
from app.api.v1.gestio.feines import router as feines_router
from app.api.v1.gestio.flota import router as flota_router
from app.api.v1.gestio.ia import router as ia_router
from app.api.v1.gestio.magatzem import router as magatzem_router
from app.api.v1.gestio.notificacions import router as notificacions_router
from app.api.v1.gestio.operaris import router as operaris_router
from app.api.v1.gestio.planols import router as planols_router
from app.api.v1.gestio.pressupostos import router as pressupostos_router
from app.api.v1.gestio.proveidors import router as proveidors_router
from app.api.v1.gestio.ws import router as ws_router
from app.api.v1.health import router as health_router
from app.api.v1.operari_auth import router as operari_auth_router
from app.api.v1.operari_pwa.feines import llistar_les_meves_feines
from app.api.v1.operari_pwa.feines import router as feines_pwa_router
from app.api.v1.operari_pwa.incidencies import router as incidencies_router
from app.api.v1.operari_pwa.jornada import router as jornada_router
from app.api.v1.operari_pwa.picking import materials_operari_router
from app.api.v1.operari_pwa.picking import router as picking_router
from app.api.v1.operari_pwa.planols import planols_operari_router
from app.api.v1.operari_pwa.planols import router as operari_planols_router
from app.api.v1.operari_pwa.sync import router as sync_router
from app.api.v1.operari_pwa.tiquets import router as tiquets_router
from app.api.v1.operari_pwa.vehicles import llistar_estoc_furgonetes
from app.api.v1.operari_pwa.vehicles import router as vehicles_pwa_router
from app.api.v1.public_docs import router as public_docs_router
from app.api.v1.superadmin.empreses import router as empreses_router
from app.api.v1.superadmin.tenants import router as tenants_router
from app.api.v1.telemetria import router as telemetria_router
from app.api.v1.webhooks.telegram import router as telegram_webhook_router
from app.api.v1.workers import router as workers_router
from app.core.config import settings
from app.middleware.tenant import TenantMiddleware

"""Punt d'entrada principal de l'API de Sevalor Suite."""


redis_url = os.getenv("REDIS_URL", "redis://:sevalor_redis_pass@127.0.0.1:6380/0")
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["100/minute"],
    storage_uri=redis_url if os.getenv("TESTING") != "1" else "memory://",
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="API Core Multi-Tenant per a la plataforma Sevalor Suite",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

app.add_middleware(TenantMiddleware)
app.add_middleware(SlowAPIMiddleware)


@app.middleware("http")
async def metrics_middleware(request, call_next):  # type: ignore[no-untyped-def]
    """Mesura durada i codi d'estat reals de cada petició (només metadades, cap dada de negoci)."""
    import time as _time

    from app.core import metrics as _metrics

    inici = _time.perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        _metrics.record((_time.perf_counter() - inici) * 1000.0, status_code)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_origin_regex=r"^https?://([a-zA-Z0-9-]+\.)*(80opze\.easypanel\.host|sevalor\.app)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(health_router, prefix=settings.API_V1_STR)

app.include_router(tenants_router, prefix=settings.API_V1_STR)
app.include_router(empreses_router, prefix=settings.API_V1_STR)
app.include_router(operaris_router, prefix=settings.API_V1_STR)
app.include_router(clients_router, prefix=settings.API_V1_STR)
app.include_router(proveidors_router, prefix=settings.API_V1_STR)
app.include_router(flota_router, prefix=settings.API_V1_STR)


app.include_router(public_docs_router, prefix=settings.API_V1_STR)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    err = traceback.format_exc()
    return JSONResponse(
        status_code=400,
        content={"detail": f"GLOBAL 500 CAUGHT: {str(exc)}", "traceback": err},
    )


app.include_router(magatzem_router, prefix=settings.API_V1_STR)
app.include_router(telegram_webhook_router, prefix=settings.API_V1_STR)
app.include_router(dashboard_router, prefix=settings.API_V1_STR)
app.include_router(ws_router, prefix=settings.API_V1_STR)
app.include_router(feines_router, prefix=settings.API_V1_STR)
app.include_router(planols_router, prefix=settings.API_V1_STR)
app.include_router(pressupostos_router, prefix=settings.API_V1_STR)
app.include_router(comptabilitat_router, prefix=settings.API_V1_STR)
app.include_router(economia_router, prefix=settings.API_V1_STR)
app.include_router(contractes_router, prefix=settings.API_V1_STR)
app.include_router(notificacions_router, prefix=settings.API_V1_STR)
app.include_router(operari_auth_router, prefix=settings.API_V1_STR)
app.include_router(auth_router, prefix=settings.API_V1_STR + "/auth", tags=["Autenticació Oficina"])
app.include_router(jornada_router, prefix=settings.API_V1_STR)
app.include_router(feines_pwa_router, prefix=settings.API_V1_STR)
app.include_router(picking_router, prefix=settings.API_V1_STR)
app.include_router(incidencies_router, prefix=settings.API_V1_STR)
app.include_router(tiquets_router, prefix=settings.API_V1_STR)
app.include_router(vehicles_pwa_router, prefix=settings.API_V1_STR)
app.include_router(sync_router, prefix=settings.API_V1_STR + "/operari_pwa")
app.include_router(operari_planols_router, prefix=settings.API_V1_STR)
app.include_router(materials_operari_router, prefix=settings.API_V1_STR)
app.include_router(planols_operari_router, prefix=settings.API_V1_STR)

compat_pwa_router = APIRouter(prefix="/operari_pwa", tags=["Operari PWA Compat"])
compat_pwa_router.add_api_route("/feines", llistar_les_meves_feines, methods=["GET"])
compat_pwa_router.add_api_route("/vehicles/stock", llistar_estoc_furgonetes, methods=["GET"])
app.include_router(compat_pwa_router, prefix=settings.API_V1_STR)

app.include_router(intervencions_router, prefix=settings.API_V1_STR)
app.include_router(cerca_router, prefix=settings.API_V1_STR)
app.include_router(spotlight_router, prefix=settings.API_V1_STR)
app.include_router(configuracio_router, prefix=settings.API_V1_STR)

# Compatibilitat de rutes per a crides directes a /configuracio/empresa


compat_config_router = APIRouter(prefix="/configuracio", tags=["Configuració Compat"])
compat_config_router.add_api_route("/empresa", obtenir_dades_empresa, methods=["GET"])
compat_config_router.add_api_route("/empresa/marca", obtenir_marca_camaleonica, methods=["GET"])
app.include_router(compat_config_router, prefix=settings.API_V1_STR)
app.include_router(copilot_router, prefix=settings.API_V1_STR)
app.include_router(ia_router, prefix=settings.API_V1_STR)
app.include_router(telemetria_router, prefix=settings.API_V1_STR)
app.include_router(workers_router, prefix=settings.API_V1_STR + "/workers", tags=["Workers Celery"])


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "operational",
    }
