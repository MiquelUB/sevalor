"""Servei per resoldre tarifes reals del Barema de Preus i costos reals de mà d'obra."""

import logging
import uuid
from decimal import Decimal
from typing import Any, Dict, Optional, Sequence

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import OrdreTreball, OrdreTreballTramTemps, Usuari
from app.services.sovereign_storage import SovereignStorageGateway

logger = logging.getLogger("sevalor.barema_service")

_LEGACY_DEFAULT_PREU_HORA = 45.0


async def obtenir_barema_empresa(
    db: AsyncSession, empresa_id: uuid.UUID
) -> Optional[Dict[str, Any]]:
    """Llegeix el Barema de Preus configurat al Panell de Control (/gestio/configuracio)."""
    try:
        items = await SovereignStorageGateway.llegir_entitats_json(
            db, empresa_id, "configuracio"
        )
    except HTTPException as exc:
        logger.warning(
            "No s'ha pogut llegir el barema del disc sobirà per a %s (%s)",
            empresa_id,
            exc.detail,
        )
        return None
    except Exception as exc:
        logger.warning(
            "Error inesperat llegint barema per a %s: %s", empresa_id, exc
        )
        return None

    for item in items:
        if isinstance(item, dict) and item.get("id") == "barema_preus":
            return item
    return None


async def resoldre_preu_hora_control_panel(
    db: AsyncSession,
    empresa_id: uuid.UUID,
    ordre: OrdreTreball,
    barema_cache: Optional[Dict[str, Any]] = None,
    barema_fetched: bool = False,
) -> float:
    """
    Resol la tarifa horària de venda real de l'OT prioritzant el valor real del
    Panell de Control (Barema de Preus) quan no hi ha una tarifa específica diferent
    del valor per defecte històric (45.00 €).
    """
    barema = (
        barema_cache
        if barema_fetched
        else await obtenir_barema_empresa(db, empresa_id)
    )
    ot_val = (
        float(ordre.preu_venda_hora_aplicat)
        if ordre.preu_venda_hora_aplicat is not None
        else None
    )

    if barema is not None and barema.get("preu_hora_standard_eur") is not None:
        barema_rate = float(barema["preu_hora_standard_eur"])
        if ot_val is None or ot_val == _LEGACY_DEFAULT_PREU_HORA:
            return barema_rate
        return ot_val

    return ot_val if ot_val is not None else 0.0


async def obtenir_cost_hora_operaris_map(
    db: AsyncSession,
    empresa_id: uuid.UUID,
    usuari_ids: Sequence[uuid.UUID],
) -> Dict[uuid.UUID, Decimal]:
    """Retorna un mapa {usuari_id: cost_hora_eur} real de la taula usuaris."""
    unique_ids = list({uid for uid in usuari_ids if uid is not None})
    if not unique_ids:
        return {}

    res = await db.execute(
        select(Usuari).where(
            Usuari.empresa_id == empresa_id,
            Usuari.id.in_(unique_ids),
        )
    )
    out: Dict[uuid.UUID, Decimal] = {}
    for u in res.scalars().all():
        cost_val = u.cost_hora_eur if u.cost_hora_eur is not None else u.cost_hora_referencia
        out[u.id] = Decimal(str(cost_val or 0))
    return out


async def calcular_cost_ma_obra_real(
    db: AsyncSession,
    empresa_id: uuid.UUID,
    ordre: OrdreTreball,
    trams: Sequence[OrdreTreballTramTemps],
    total_hores: float,
) -> float:
    """Calcula el cost real de mà d'obra d'una OT a partir del cost/hora real dels operaris."""
    user_ids = [t.operari_id for t in trams if t.operari_id is not None]
    if ordre.cap_de_colla_id is not None:
        user_ids.append(ordre.cap_de_colla_id)

    costs_map = await obtenir_cost_hora_operaris_map(db, empresa_id, user_ids)

    trams_tancats = [t for t in trams if t.hora_fi is not None and (t.durada_segons or 0) > 0]
    if trams_tancats:
        total_cost = Decimal("0.00")
        for t in trams_tancats:
            uid = t.operari_id or ordre.cap_de_colla_id
            cost_h = costs_map.get(uid, Decimal("0.00")) if uid else Decimal("0.00")
            hores_tram = Decimal(str(t.durada_segons)) / Decimal("3600")
            total_cost += hores_tram * cost_h
        return float(round(total_cost, 2))

    if total_hores > 0 and ordre.cap_de_colla_id is not None:
        cost_h = costs_map.get(ordre.cap_de_colla_id, Decimal("0.00"))
        return float(round(Decimal(str(total_hores)) * cost_h, 2))

    return 0.0
