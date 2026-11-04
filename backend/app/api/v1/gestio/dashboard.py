import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, or_, select, union
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_with_tenant_context
from app.core.security import require_roles
from app.models.models import (
    Article,
    Client,
    EstocMagatzem,
    Incidencia,
    OrdreTreball,
    RegistreJornadaLaboral,
    Usuari,
    Vehicle,
)

router = APIRouter(
    prefix="/gestio/dashboard",
    tags=["Dashboard Torre Control"],
    dependencies=[Depends(require_roles(["BOSS", "SECRETARIA", "ENGINYER"]))],
)


@router.get("/hud", response_model=Dict[str, Any])
async def get_dashboard_hud(
    request: Request, db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = getattr(request.state, "empresa_id", None) or request.headers.get("X-Empresa-ID")
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="No identificat")

    emp_uuid = uuid.UUID(empresa_id)

    # Active jobs (totes les feines actives o planificades pendents/en curs)
    stmt_active = select(func.count(OrdreTreball.id)).where(
        OrdreTreball.empresa_id == emp_uuid,
        OrdreTreball.estat.in_(["PENDENT", "ASSIGNADA", "PROGRAMADA", "EN_CURS", "EN_OBRA", "EN_RUTA"]),
    )
    res_active = await db.execute(stmt_active)
    active_jobs = res_active.scalar() or 0

    # Completed jobs
    stmt_comp = select(func.count(OrdreTreball.id)).where(
        OrdreTreball.empresa_id == emp_uuid, OrdreTreball.estat.in_(["FINALITZADA", "COMPLETADA", "TANCADA"])
    )
    res_comp = await db.execute(stmt_comp)
    completed_jobs = res_comp.scalar() or 0

    # Open incidents (incidències no resoltes / no tancades)
    stmt_inc = select(func.count(Incidencia.id)).where(
        Incidencia.empresa_id == emp_uuid,
        ~Incidencia.estat.in_(["TANCADA", "RESOLTA", "VERD"]),
    )
    res_inc = await db.execute(stmt_inc)
    open_incidents = res_inc.scalar() or 0

    # Teams on field:
    # 1. Caps de colla o operaris assignats a feines actives (PENDENT, ASSIGNADA, PROGRAMADA, EN_CURS, EN_OBRA, EN_RUTA)
    # 2. Operaris amb fitxatge / registre de jornada obert avui
    # 3. Operaris en servei operatiu al camp (EN_SERVEI, EN_RUTA, EN_OBRA)
    q_ots = (
        select(OrdreTreball.cap_de_colla_id.label("usuari_id"))
        .where(
            OrdreTreball.empresa_id == emp_uuid,
            OrdreTreball.estat.in_(["ASSIGNADA", "PROGRAMADA", "EN_CURS", "EN_OBRA", "EN_RUTA"]),
            OrdreTreball.cap_de_colla_id.is_not(None),
        )
    )
    q_jornada = (
        select(RegistreJornadaLaboral.usuari_id.label("usuari_id"))
        .where(
            RegistreJornadaLaboral.empresa_id == emp_uuid,
            RegistreJornadaLaboral.data_jornada == func.current_date(),
            RegistreJornadaLaboral.hora_fi.is_(None),
            RegistreJornadaLaboral.estat == "EN_CURS",
        )
    )
    q_servei = (
        select(Usuari.id.label("usuari_id"))
        .where(
            Usuari.empresa_id == emp_uuid,
            Usuari.rol.in_(["OPERARI", "CAP_DE_COLLA"]),
            Usuari.estat == "ACTIU",
            Usuari.estat_operatiu.in_(["EN_SERVEI", "EN_RUTA", "EN_OBRA"]),
        )
    )

    stmt_teams_union = union(q_ots, q_jornada, q_servei).subquery()
    stmt_teams = select(func.count(stmt_teams_union.c.usuari_id))
    res_teams = await db.execute(stmt_teams)
    teams_on_field = res_teams.scalar() or 0

    # Critical stock
    stmt_stock = (
        select(Article.id)
        .outerjoin(EstocMagatzem, Article.id == EstocMagatzem.article_id)
        .where(
            Article.empresa_id == emp_uuid,
            Article.actiu.is_(True),
            Article.estoc_minim > 0,
        )
        .group_by(Article.id, Article.estoc_minim)
        .having(func.coalesce(func.sum(EstocMagatzem.quantitat_fisica), 0) <= Article.estoc_minim)
    )
    res_stock = await db.execute(stmt_stock)
    critical_stock = len(res_stock.all())

    # Vehicles with alerts
    stmt_veh = select(func.count(Vehicle.id)).where(
        Vehicle.empresa_id == emp_uuid,
        or_(
            Vehicle.estat.in_(["AVERIAT", "TALLER", "ACCIDENTAT", "MANTENIMENT"]),
            Vehicle.estat_itv.in_(["DESFAVORABLE", "CADUCADA", "NEGATIVA"]),
        ),
    )
    res_veh = await db.execute(stmt_veh)
    vehicles_with_alerts = res_veh.scalar() or 0

    return {
        "active_jobs": active_jobs,
        "completed_jobs": completed_jobs,
        "open_incidents": open_incidents,
        "teams_on_field": teams_on_field,
        "critical_stock": critical_stock,
        "vehicles_with_alerts": vehicles_with_alerts,
    }


@router.get("/incidencies-drawer", response_model=List[Dict[str, Any]])
async def get_incidencies_drawer(
    request: Request,
    estat: Optional[str] = None,
    totes: bool = False,
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    """Llistat reactiu d'incidències de camp obertes per al calaix lateral de la Torre de Control (Spec 01 T046)."""
    empresa_id = getattr(request.state, "empresa_id", None) or request.headers.get("X-Empresa-ID")
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="No identificat")

    emp_uuid = uuid.UUID(empresa_id)

    stmt = (
        select(
            Incidencia,
            Usuari.nom.label("operari_nom"),
            Usuari.cognoms.label("operari_cognoms"),
            OrdreTreball.codi.label("ot_codi"),
            OrdreTreball.titol.label("ot_titol"),
            Client.rao_social.label("ot_client_nom"),
        )
        .outerjoin(Usuari, Incidencia.operari_id == Usuari.id)
        .outerjoin(OrdreTreball, Incidencia.ordre_treball_id == OrdreTreball.id)
        .outerjoin(Client, OrdreTreball.client_id == Client.id)
        .where(Incidencia.empresa_id == emp_uuid)
    )

    if estat:
        stmt = stmt.where(Incidencia.estat == estat)
    elif not totes:
        stmt = stmt.where(~Incidencia.estat.in_(["TANCADA", "RESOLTA", "VERD"]))

    stmt = stmt.order_by(Incidencia.created_at.desc())

    result = await db.execute(stmt)
    rows = result.all()

    items = []
    for inc, op_nom, op_cognoms, ot_codi, ot_titol, ot_client in rows:
        nom_complet = f"{op_nom or ''} {op_cognoms or ''}".strip() or "Operari de camp"
        items.append({
            "id": str(inc.id),
            "ordre_treball_id": str(inc.ordre_treball_id) if inc.ordre_treball_id else None,
            "vehicle_id": str(inc.vehicle_id) if inc.vehicle_id else None,
            "operari_id": str(inc.operari_id) if inc.operari_id else None,
            "operari_nom": nom_complet,
            "ordre_treball_codi": ot_codi,
            "ordre_treball_titol": ot_titol,
            "client_nom": ot_client,
            "ambit": inc.ambit,
            "estat": inc.estat,
            "grau": "URGENT_BLOQUEJANT" if inc.estat == "VERMELL" else "MODERADA",
            "audio_path": inc.audio_path,
            "foto_path": inc.foto_path,
            "text_observacions": inc.text_observacions,
            "created_at": inc.created_at.isoformat() if inc.created_at else None,
            "updated_at": inc.updated_at.isoformat() if inc.updated_at else None,
        })
    return items


@router.patch("/incidencies/{incidencia_id}/resoldre")
async def resoldre_incidencia_dashboard(
    request: Request,
    incidencia_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    """Commuta una incidència a VERD des de la Torre de Control i reactiva la feina si cal."""
    empresa_id = getattr(request.state, "empresa_id", None) or request.headers.get("X-Empresa-ID")
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="No identificat")

    emp_uuid = uuid.UUID(empresa_id)

    stmt = select(Incidencia).where(
        Incidencia.id == incidencia_id,
        Incidencia.empresa_id == emp_uuid,
    )
    res = await db.execute(stmt)
    inc = res.scalars().first()
    if not inc:
        raise HTTPException(status_code=404, detail="Incidència no trobada")

    inc.estat = "VERD"
    if inc.ordre_treball_id:
        ot_stmt = select(OrdreTreball).where(
            OrdreTreball.id == inc.ordre_treball_id,
            OrdreTreball.empresa_id == emp_uuid,
        )
        ot_res = await db.execute(ot_stmt)
        ot = ot_res.scalars().first()
        if ot and ot.estat == "BLOQUEJADA":
            ot.estat = "EN_CURS"

    await db.commit()
    return {"status": "OK", "id": str(inc.id), "estat": inc.estat}


@router.patch("/incidencies/{incidencia_id}/aprova-hitl")
async def aprova_hitl_incidencia(
    request: Request,
    incidencia_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    """Validació humana (HITL) del pressupost d'imprevistos (Spec 01 T048)."""
    empresa_id = getattr(request.state, "empresa_id", None) or request.headers.get("X-Empresa-ID")
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="No identificat")

    emp_uuid = uuid.UUID(empresa_id)

    stmt = select(Incidencia).where(
        Incidencia.id == incidencia_id,
        Incidencia.empresa_id == emp_uuid,
    )
    res = await db.execute(stmt)
    inc = res.scalars().first()
    if not inc:
        raise HTTPException(status_code=404, detail="Incidència no trobada")

    inc.estat = "VERD"
    await db.commit()
    return {"status": "OK", "id": str(inc.id), "aprovacio_hitl_supervisor": True, "estat": inc.estat}
