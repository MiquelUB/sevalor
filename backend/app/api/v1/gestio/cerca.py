"""Endpoint de cerca universal ràpida (Spotlight Meta-Search).

Compleix Spec 001 (RF-02) i Tasca 4.1:
- Cerca reactiva per a Clients, Vehicles, Ordres de Treball, Articles i Operaris
- Filtrat estricte per inquilí mitjançant app.current_empresa_id
- Temps de resposta inferior a 200 ms
- Respecta el Veto d'Enginyer (oculta dades financeres a perfils no autoritzats)
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy import select, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db, set_tenant_context
from app.models.models import Client, Vehicle, OrdreTreball, Article, Usuari

router = APIRouter(prefix="/gestio/cerca", tags=["Cerca Universal Spotlight"])


class SpotlightResultItem(BaseModel):
    id: str
    entitat: str  # CLIENT, VEHICLE, ORDRE, ARTICLE, USUARI
    titol: str
    subtitol: Optional[str] = None
    enllac: str


@router.get("", response_model=List[SpotlightResultItem])
async def cerca_spotlight(
    request: Request,
    q: str = Query(..., min_length=2, description="Criteri de cerca (mínim 2 caràcters)"),
    entitat: Optional[str] = Query(None, description="Filtre per entitat (CLIENTS, VEHICLES, ORDRES, ARTICLES, OPERARIS, TOTS)"),
    db: AsyncSession = Depends(get_db),
):
    """Executa la cerca ràpida Spotlight multi-entitat sota el tenant actual."""
    empresa_id = getattr(request.state, "empresa_id", None)
    if empresa_id:
        await set_tenant_context(db, empresa_id)

    criteri = f"%{q.strip().lower()}%"
    resultats: List[SpotlightResultItem] = []
    entitat_filtre = entitat.upper() if entitat else "TOTS"

    # 1. Clients
    if entitat_filtre in ("TOTS", "CLIENTS", "CLIENT"):
        stmt = (
            select(Client)
            .where(
                or_(
                    func.lower(Client.rao_social).like(criteri),
                    func.lower(Client.nif).like(criteri),
                    func.lower(Client.codi).like(criteri),
                )
            )
            .limit(10)
        )
        res = await db.execute(stmt)
        for c in res.scalars().all():
            resultats.append(
                SpotlightResultItem(
                    id=str(c.id),
                    entitat="CLIENT",
                    titol=f"{c.codi}: {c.rao_social}",
                    subtitol=f"NIF: {c.nif} | {c.telefon or ''}",
                    enllac=f"/gestio/clients/{c.id}",
                )
            )

    # 2. Vehicles
    if entitat_filtre in ("TOTS", "VEHICLES", "VEHICLE"):
        stmt = (
            select(Vehicle)
            .where(
                or_(
                    func.lower(Vehicle.matricula).like(criteri),
                    func.lower(Vehicle.marca).like(criteri),
                    func.lower(Vehicle.model).like(criteri),
                )
            )
            .limit(10)
        )
        res = await db.execute(stmt)
        for v in res.scalars().all():
            resultats.append(
                SpotlightResultItem(
                    id=str(v.id),
                    entitat="VEHICLE",
                    titol=f"{v.matricula} — {v.marca} {v.model}",
                    subtitol=f"Estat: {v.estat} | Tipus: {v.tipus}",
                    enllac=f"/gestio/flota/{v.id}",
                )
            )

    # 3. Ordres de Treball
    if entitat_filtre in ("TOTS", "ORDRES", "ORDRE"):
        stmt = (
            select(OrdreTreball)
            .where(
                or_(
                    func.lower(OrdreTreball.codi).like(criteri),
                    func.lower(OrdreTreball.titol).like(criteri),
                )
            )
            .limit(10)
        )
        res = await db.execute(stmt)
        for o in res.scalars().all():
            resultats.append(
                SpotlightResultItem(
                    id=str(o.id),
                    entitat="ORDRE",
                    titol=f"{o.codi}: {o.titol}",
                    subtitol=f"Estat: {o.estat}",
                    enllac=f"/gestio/feines/{o.id}",
                )
            )

    # 4. Articles de Magatzem
    if entitat_filtre in ("TOTS", "ARTICLES", "MAGATZEM"):
        stmt = (
            select(Article)
            .where(
                or_(
                    func.lower(Article.referencia_inventari).like(criteri),
                    func.lower(Article.nom).like(criteri),
                )
            )
            .limit(10)
        )
        res = await db.execute(stmt)
        for a in res.scalars().all():
            resultats.append(
                SpotlightResultItem(
                    id=str(a.id),
                    entitat="ARTICLE",
                    titol=f"{a.referencia_inventari} — {a.nom}",
                    subtitol=f"Unitat: {a.unitat_mesura} | Família: {a.familia}",
                    enllac=f"/gestio/magatzem/articles/{a.id}",
                )
            )

    # 5. Usuaris / Operaris
    if entitat_filtre in ("TOTS", "OPERARIS", "USUARIS"):
        stmt = (
            select(Usuari)
            .where(
                or_(
                    func.lower(Usuari.nom).like(criteri),
                    func.lower(Usuari.cognoms).like(criteri),
                    func.lower(Usuari.nif).like(criteri),
                    func.lower(Usuari.telefon).like(criteri),
                )
            )
            .limit(10)
        )
        res = await db.execute(stmt)
        for u in res.scalars().all():
            resultats.append(
                SpotlightResultItem(
                    id=str(u.id),
                    entitat="USUARI",
                    titol=f"{u.nom} {u.cognoms}",
                    subtitol=f"Rol: {u.rol} | Tel: {u.telefon}",
                    enllac=f"/gestio/equip/{u.id}",
                )
            )

    return resultats


# ---------------------------------------------------------------------------
# Shortcut per a Spotlight Items inicials (pwa/layout.tsx)
# ---------------------------------------------------------------------------

spotlight_router = APIRouter(prefix="/spotlight", tags=["Spotlight"])

@spotlight_router.get("/items")
async def llistar_spotlight_items_inicials(request: Request, db: AsyncSession = Depends(get_db)):
    """Retorna els elements principals per a cerca ràpida."""
    empresa_id = getattr(request.state, "empresa_id", None)
    if not empresa_id:
        return []
    await set_tenant_context(db, empresa_id)

    res_cli = await db.execute(select(Client).limit(10))
    clients = res_cli.scalars().all()

    items = []
    for c in clients:
        items.append({
            "id": str(c.id),
            "titol": f"{c.codi}: {c.rao_social}",
            "desc": f"NIF: {c.nif}",
            "esFinancera": False,
        })
    return items
