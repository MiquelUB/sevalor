import uuid
from typing import Dict, Any
from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.core.db import get_db_with_tenant_context
from app.core.security import require_roles
from app.models.models import OrdreTreball, Incidencia, Usuari, Article, Vehicle

router = APIRouter(
    prefix="/gestio/dashboard",
    tags=["Dashboard Torre Control"],
    dependencies=[Depends(require_roles(["BOSS", "SECRETARIA", "ENGINYER"]))],
)

@router.get("/hud", response_model=Dict[str, Any])
async def get_dashboard_hud(
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = getattr(request.state, "empresa_id", None) or request.headers.get("X-Empresa-ID")
    if not empresa_id or empresa_id == 'undefined':
        raise HTTPException(status_code=401, detail="No identificat")
    
    emp_uuid = uuid.UUID(empresa_id)

    # Active jobs
    stmt_active = select(func.count(OrdreTreball.id)).where(OrdreTreball.empresa_id == emp_uuid, OrdreTreball.estat.in_(["EN_CURS", "EN_OBRA", "EN_RUTA"]))
    res_active = await db.execute(stmt_active)
    active_jobs = res_active.scalar() or 0

    # Completed jobs
    stmt_comp = select(func.count(OrdreTreball.id)).where(OrdreTreball.empresa_id == emp_uuid, OrdreTreball.estat == "FINALITZADA")
    res_comp = await db.execute(stmt_comp)
    completed_jobs = res_comp.scalar() or 0

    # Open incidents
    stmt_inc = select(func.count(Incidencia.id)).where(Incidencia.empresa_id == emp_uuid, Incidencia.estat != "TANCADA")
    res_inc = await db.execute(stmt_inc)
    open_incidents = res_inc.scalar() or 0

    # Teams on field (distinct cap_de_colla_id in active jobs)
    stmt_teams = select(func.count(func.distinct(OrdreTreball.cap_de_colla_id))).where(OrdreTreball.empresa_id == emp_uuid, OrdreTreball.estat.in_(["EN_CURS", "EN_OBRA", "EN_RUTA"]))
    res_teams = await db.execute(stmt_teams)
    teams_on_field = res_teams.scalar() or 0

    # Critical stock
    stmt_stock = select(func.count(Article.id)).where(Article.empresa_id == emp_uuid, Article.estoc_actual <= Article.estoc_minim)
    res_stock = await db.execute(stmt_stock)
    critical_stock = res_stock.scalar() or 0

    # Vehicles with alerts
    stmt_veh = select(func.count(Vehicle.id)).where(Vehicle.empresa_id == emp_uuid, Vehicle.estat == "AVERIAT")
    res_veh = await db.execute(stmt_veh)
    vehicles_with_alerts = res_veh.scalar() or 0

    return {
        "active_jobs": active_jobs,
        "completed_jobs": completed_jobs,
        "open_incidents": open_incidents,
        "teams_on_field": teams_on_field,
        "critical_stock": critical_stock,
        "vehicles_with_alerts": vehicles_with_alerts
    }
