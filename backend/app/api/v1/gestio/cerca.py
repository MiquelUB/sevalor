"""Endpoint de cerca universal ràpida (Spotlight Meta-Search).

Compleix Spec 001 (RF-02) i Tasca 4.1:
- Cerca reactiva per a Clients, Vehicles, Ordres de Treball, Articles i Operaris
- Filtrat estricte per inquilí mitjançant app.current_empresa_id
- Temps de resposta inferior a 200 ms
- Respecta el Veto d'Enginyer (oculta dades financeres a perfils no autoritzats)
"""

import uuid
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_with_tenant_context
from app.core.security import require_roles
from app.models.models import Article, Client, OrdreTreball, Usuari, Vehicle

router = APIRouter(
    prefix="/gestio/cerca",
    tags=["Cerca Universal Spotlight"],
    dependencies=[Depends(require_roles(["BOSS", "SECRETARIA", "ENGINYER"]))],
)


class SpotlightResultItem(BaseModel):
    id: str
    entitat: str  # CLIENT, VEHICLE, ORDRE, ARTICLE, USUARI
    tipus: str
    titol: str
    subtitol: Optional[str] = None
    desc: str = ""
    enllac: str
    ref: str
    esFinancera: bool = False


def _resolve_emp_uuid(request: Request, claims: dict[str, Any]) -> uuid.UUID:
    raw = (
        getattr(request.state, "empresa_id", None)
        or claims.get("empresa_id")
        or request.headers.get("X-Empresa-ID")
    )
    if not raw or str(raw) in ("undefined", "null", "None"):
        raise HTTPException(status_code=401, detail="No identificat")
    try:
        return uuid.UUID(str(raw))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Identificador d'empresa invàlid.") from exc


@router.get("", response_model=List[SpotlightResultItem])
async def cerca_spotlight(
    request: Request,
    q: str = Query(..., min_length=2, description="Criteri de cerca (mínim 2 caràcters)"),
    entitat: Optional[str] = Query(
        None, description="Filtre per entitat (CLIENTS, VEHICLES, ORDRES, ARTICLES, OPERARIS, TOTS)"
    ),
    claims: dict[str, Any] = Depends(require_roles(["BOSS", "SECRETARIA", "ENGINYER"])),
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> List[SpotlightResultItem]:
    """Executa la cerca ràpida Spotlight multi-entitat sota aïllament estricte de tenant."""
    emp_uuid = _resolve_emp_uuid(request, claims)
    criteri = f"%{q.strip().lower()}%"
    resultats: List[SpotlightResultItem] = []
    entitat_filtre = entitat.upper() if entitat else "TOTS"

    # 1. Clients
    if entitat_filtre in ("TOTS", "CLIENTS", "CLIENT"):
        stmt_cli = (
            select(Client)
            .where(
                Client.empresa_id == emp_uuid,
                or_(
                    func.lower(Client.rao_social).like(criteri),
                    func.lower(Client.nif).like(criteri),
                    func.lower(Client.codi).like(criteri),
                ),
            )
            .limit(10)
        )
        res_cli = await db.execute(stmt_cli)
        for c in res_cli.scalars().all():
            sub = f"NIF: {c.nif} | {c.telefon or ''}"
            href = f"/gestio/clients?id={c.id}"
            resultats.append(
                SpotlightResultItem(
                    id=str(c.id),
                    entitat="CLIENT",
                    tipus="CLIENT",
                    titol=f"{c.codi}: {c.rao_social}",
                    subtitol=sub,
                    desc=sub,
                    enllac=href,
                    ref=href,
                    esFinancera=False,
                )
            )

    # 2. Vehicles
    if entitat_filtre in ("TOTS", "VEHICLES", "VEHICLE"):
        stmt_veh = (
            select(Vehicle)
            .where(
                Vehicle.empresa_id == emp_uuid,
                or_(
                    func.lower(Vehicle.matricula).like(criteri),
                    func.lower(Vehicle.marca).like(criteri),
                    func.lower(Vehicle.model).like(criteri),
                ),
            )
            .limit(10)
        )
        res_veh = await db.execute(stmt_veh)
        for v in res_veh.scalars().all():
            sub = f"Estat: {v.estat} | Tipus: {v.tipus}"
            href = f"/gestio/flota?id={v.id}"
            resultats.append(
                SpotlightResultItem(
                    id=str(v.id),
                    entitat="VEHICLE",
                    tipus="VEHICLE",
                    titol=f"{v.matricula} — {v.marca} {v.model}",
                    subtitol=sub,
                    desc=sub,
                    enllac=href,
                    ref=href,
                    esFinancera=False,
                )
            )

    # 3. Ordres de Treball
    if entitat_filtre in ("TOTS", "ORDRES", "ORDRE"):
        stmt_ord = (
            select(OrdreTreball)
            .where(
                OrdreTreball.empresa_id == emp_uuid,
                or_(
                    func.lower(OrdreTreball.codi).like(criteri),
                    func.lower(OrdreTreball.titol).like(criteri),
                ),
            )
            .limit(10)
        )
        res_ord = await db.execute(stmt_ord)
        for o in res_ord.scalars().all():
            sub = f"Estat: {o.estat}"
            href = f"/gestio/feines?id={o.id}"
            resultats.append(
                SpotlightResultItem(
                    id=str(o.id),
                    entitat="ORDRE",
                    tipus="ORDRE",
                    titol=f"{o.codi}: {o.titol}",
                    subtitol=sub,
                    desc=sub,
                    enllac=href,
                    ref=href,
                    esFinancera=False,
                )
            )

    # 4. Articles de Magatzem (incloent cerca per codi de barres)
    if entitat_filtre in ("TOTS", "ARTICLES", "MAGATZEM"):
        stmt_art = (
            select(Article)
            .where(
                Article.empresa_id == emp_uuid,
                or_(
                    func.lower(Article.referencia_inventari).like(criteri),
                    func.lower(Article.nom).like(criteri),
                    func.lower(func.coalesce(Article.codi_barres, "")).like(criteri),
                ),
            )
            .limit(10)
        )
        res_art = await db.execute(stmt_art)
        for a in res_art.scalars().all():
            sub = f"Unitat: {a.unitat_mesura} | Família: {a.familia}"
            href = f"/gestio/magatzem?id={a.id}"
            resultats.append(
                SpotlightResultItem(
                    id=str(a.id),
                    entitat="ARTICLE",
                    tipus="ARTICLE",
                    titol=f"{a.referencia_inventari} — {a.nom}",
                    subtitol=sub,
                    desc=sub,
                    enllac=href,
                    ref=href,
                    esFinancera=False,
                )
            )

    # 5. Usuaris / Operaris
    if entitat_filtre in ("TOTS", "OPERARIS", "USUARIS"):
        stmt_usr = (
            select(Usuari)
            .where(
                Usuari.empresa_id == emp_uuid,
                or_(
                    func.lower(Usuari.nom).like(criteri),
                    func.lower(Usuari.cognoms).like(criteri),
                    func.lower(Usuari.nif).like(criteri),
                    func.lower(func.coalesce(Usuari.telefon, "")).like(criteri),
                ),
            )
            .limit(10)
        )
        res_usr = await db.execute(stmt_usr)
        for u in res_usr.scalars().all():
            sub = f"Rol: {u.rol} | Tel: {u.telefon or '—'}"
            href = f"/gestio/operaris?id={u.id}"
            resultats.append(
                SpotlightResultItem(
                    id=str(u.id),
                    entitat="USUARI",
                    tipus="OPERARI",
                    titol=f"{u.nom} {u.cognoms}".strip(),
                    subtitol=sub,
                    desc=sub,
                    enllac=href,
                    ref=href,
                    esFinancera=False,
                )
            )

    return resultats


# ---------------------------------------------------------------------------
# Shortcut per a Spotlight Items inicials (pwa/layout.tsx)
# ---------------------------------------------------------------------------

spotlight_router = APIRouter(
    prefix="/spotlight",
    tags=["Spotlight"],
    dependencies=[Depends(require_roles(["BOSS", "SECRETARIA", "ENGINYER"]))],
)


@spotlight_router.get("/items")
async def llistar_spotlight_items_inicials(
    request: Request,
    claims: dict[str, Any] = Depends(require_roles(["BOSS", "SECRETARIA", "ENGINYER"])),
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> List[dict[str, Any]]:
    """Retorna els elements principals reals per a navegació ràpida Spotlight."""
    raw = (
        getattr(request.state, "empresa_id", None)
        or claims.get("empresa_id")
        or request.headers.get("X-Empresa-ID")
    )
    if not raw or str(raw) in ("undefined", "null", "None"):
        return []
    try:
        emp_uuid = uuid.UUID(str(raw))
    except ValueError:
        return []

    items: List[dict[str, Any]] = []

    res_cli = await db.execute(
        select(Client).where(Client.empresa_id == emp_uuid).limit(6)
    )
    for c in res_cli.scalars().all():
        items.append(
            {
                "id": str(c.id),
                "tipus": "CLIENT",
                "titol": f"{c.codi}: {c.rao_social}",
                "desc": f"NIF: {c.nif}",
                "ref": f"/gestio/clients?id={c.id}",
                "esFinancera": False,
            }
        )

    res_ord = await db.execute(
        select(OrdreTreball).where(OrdreTreball.empresa_id == emp_uuid).limit(6)
    )
    for o in res_ord.scalars().all():
        items.append(
            {
                "id": str(o.id),
                "tipus": "ORDRE",
                "titol": f"{o.codi}: {o.titol}",
                "desc": f"Estat: {o.estat}",
                "ref": f"/gestio/feines?id={o.id}",
                "esFinancera": False,
            }
        )

    res_veh = await db.execute(
        select(Vehicle).where(Vehicle.empresa_id == emp_uuid).limit(4)
    )
    for v in res_veh.scalars().all():
        items.append(
            {
                "id": str(v.id),
                "tipus": "VEHICLE",
                "titol": f"{v.matricula} — {v.marca} {v.model}",
                "desc": f"Estat: {v.estat}",
                "ref": f"/gestio/flota?id={v.id}",
                "esFinancera": False,
            }
        )

    return items
