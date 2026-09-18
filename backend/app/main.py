"""Punt d'entrada principal de l'API de Sevalor Suite."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from app.api.v1.health import router as health_router
from app.api.v1.superadmin.tenants import router as tenants_router
from app.api.v1.gestio.operaris import router as operaris_router
from app.api.v1.gestio.clients import router as clients_router
from app.api.v1.gestio.proveidors import router as proveidors_router
from app.api.v1.gestio.flota import router as flota_router
from app.api.v1.gestio.magatzem import router as magatzem_router
from app.api.v1.gestio.feines import router as feines_router
from app.api.v1.gestio.planols import router as planols_router
from app.api.v1.gestio.comptabilitat import router as comptabilitat_router
from app.api.v1.gestio.notificacions import router as notificacions_router
from app.api.v1.operari_auth import router as operari_auth_router
from app.api.v1.auth import router as auth_router
from app.api.v1.operari_pwa.jornada import router as jornada_router
from app.api.v1.operari_pwa.picking import router as picking_router
from app.api.v1.operari_pwa.incidencies import router as incidencies_router
from app.api.v1.gestio.configuracio import router as configuracio_router
from app.api.v1.gestio.copilot import router as copilot_router
from app.api.v1.telemetria import router as telemetria_router
from app.api.v1.operari_pwa.feines import router as feines_pwa_router
from app.api.v1.operari_pwa.tiquets import router as tiquets_router
from app.api.v1.operari_pwa.vehicles import router as vehicles_pwa_router
from app.api.v1.gestio.feines import intervencions_router
from app.api.v1.gestio.cerca import router as cerca_router, spotlight_router
from app.core.config import settings
from app.middleware.tenant import TenantMiddleware

limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])

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
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(TenantMiddleware)
app.add_middleware(SlowAPIMiddleware)

app.include_router(health_router, prefix=settings.API_V1_STR)
app.include_router(tenants_router, prefix=settings.API_V1_STR)
app.include_router(operaris_router, prefix=settings.API_V1_STR)
app.include_router(clients_router, prefix=settings.API_V1_STR)
app.include_router(proveidors_router, prefix=settings.API_V1_STR)
app.include_router(flota_router, prefix=settings.API_V1_STR)
app.include_router(magatzem_router, prefix=settings.API_V1_STR)
app.include_router(feines_router, prefix=settings.API_V1_STR)
app.include_router(planols_router, prefix=settings.API_V1_STR)
app.include_router(comptabilitat_router, prefix=settings.API_V1_STR)
app.include_router(notificacions_router, prefix=settings.API_V1_STR)
app.include_router(operari_auth_router, prefix=settings.API_V1_STR)
app.include_router(auth_router, prefix=settings.API_V1_STR + "/auth", tags=["Autenticació Oficina"])
app.include_router(jornada_router, prefix=settings.API_V1_STR)
app.include_router(feines_pwa_router, prefix=settings.API_V1_STR)
app.include_router(picking_router, prefix=settings.API_V1_STR)
app.include_router(incidencies_router, prefix=settings.API_V1_STR)
app.include_router(tiquets_router, prefix=settings.API_V1_STR)
app.include_router(vehicles_pwa_router, prefix=settings.API_V1_STR)
app.include_router(intervencions_router, prefix=settings.API_V1_STR)
app.include_router(cerca_router, prefix=settings.API_V1_STR)
app.include_router(spotlight_router, prefix=settings.API_V1_STR)
app.include_router(configuracio_router, prefix=settings.API_V1_STR)

# Compatibilitat de rutes per a crides directes a /configuracio/empresa
from fastapi import APIRouter
from app.api.v1.gestio.configuracio import obtenir_dades_empresa, obtenir_marca_camaleonica
compat_config_router = APIRouter(prefix="/configuracio", tags=["Configuració Compat"])
compat_config_router.add_api_route("/empresa", obtenir_dades_empresa, methods=["GET"])
compat_config_router.add_api_route("/empresa/marca", obtenir_marca_camaleonica, methods=["GET"])
app.include_router(compat_config_router, prefix=settings.API_V1_STR)
app.include_router(copilot_router, prefix=settings.API_V1_STR)
app.include_router(telemetria_router, prefix=settings.API_V1_STR)

@app.get("/")
async def root():
    return {
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "operational",
    }