"""Servei atòmic i idempotent de Picking (Pick-In / Pick-Out) i Magatzem de Vehicle (Furgoneta)."""

from __future__ import annotations

import logging
import uuid
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import (
    Article,
    EstocMagatzem,
    FullaPicking,
    LiniaPicking,
    Magatzem,
    MermaInventari,
    MovimentEstoc,
    OrdreTreball,
    Usuari,
    Vehicle,
)
from app.services.recompra_service import avaluar_i_sincronitzar_alertes_recompra
from app.services.sovereign_storage import SovereignStorageGateway

logger = logging.getLogger("sevalor.picking_stock")


def _q2(val: Decimal | float | int | None) -> Decimal:
    return Decimal(str(val if val is not None else 0)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


def _q3(val: Decimal | float | int | None) -> Decimal:
    return Decimal(str(val if val is not None else 0)).quantize(
        Decimal("0.001"), rounding=ROUND_HALF_UP
    )


def _q4(val: Decimal | float | int | None) -> Decimal:
    return Decimal(str(val if val is not None else 0)).quantize(
        Decimal("0.0001"), rounding=ROUND_HALF_UP
    )


def _resoldre_pmp_article(article: Article) -> Decimal:
    """Retorna el PMP vigent d'un article sense valors inventats."""
    for candidate in (
        getattr(article, "pmp_actual", None),
        getattr(article, "preu_cost_mitja", None),
        getattr(article, "ultim_preu_compra", None),
        getattr(article, "preu_cost", None),
    ):
        if candidate is not None and Decimal(str(candidate)) > 0:
            return _q4(candidate)
    return Decimal("0.0000")


async def recalcular_totals_materials_ot(
    db: AsyncSession,
    empresa_id: uuid.UUID,
    ordre_treball_id: uuid.UUID,
) -> Tuple[Decimal, Decimal]:
    """Recalcula i persisteix cost_materials_picking_pmp, cost_materials_pmp i pvp_materials_aplicat a l'OT."""
    ot = (
        await db.execute(
            select(OrdreTreball).where(
                OrdreTreball.id == ordre_treball_id,
                OrdreTreball.empresa_id == empresa_id,
            )
        )
    ).scalars().first()
    if not ot:
        return Decimal("0.00"), Decimal("0.00")

    rows = (
        await db.execute(
            select(LiniaPicking, Article)
            .join(FullaPicking, LiniaPicking.picking_id == FullaPicking.id)
            .join(Article, LiniaPicking.article_id == Article.id)
            .where(
                FullaPicking.empresa_id == empresa_id,
                FullaPicking.ordre_treball_id == ordre_treball_id,
                LiniaPicking.empresa_id == empresa_id,
            )
        )
    ).all()

    total_cost_pmp = Decimal("0.00")
    total_pvp = Decimal("0.00")

    for lp, art in rows:
        q_in = _q3(lp.quantitat_carregada_pick_in or 0)
        q_out = _q3(lp.quantitat_retornada_pick_out or 0)
        q_merma = _q3(lp.quantitat_mermada or 0)
        q_prev = _q3(lp.quantitat_prevista or 0)

        if q_in > 0:
            q_consum_total = max(Decimal("0.000"), _q3(q_in - q_out))
            q_facturable = max(Decimal("0.000"), _q3(q_consum_total - q_merma))
        else:
            q_consum_total = Decimal("0.000")
            q_facturable = q_prev

        pmp_u = _resoldre_pmp_article(art)
        pvp_u = _q2(art.preu_venda or 0)

        total_cost_pmp += _q2(q_consum_total * pmp_u)
        total_pvp += _q2(q_facturable * pvp_u)

    ot.cost_materials_picking_pmp = float(_q2(total_cost_pmp))
    ot.cost_materials_pmp = float(_q2(total_cost_pmp))
    ot.pvp_materials_aplicat = float(_q2(total_pvp))
    return _q2(total_cost_pmp), _q2(total_pvp)


async def _resincronitzar_estoc_total_article(
    db: AsyncSession,
    empresa_id: uuid.UUID,
    article: Article,
) -> None:
    """Actualitza Article.estoc_total_actual com a suma real de tots els EstocMagatzem de l'empresa."""
    total_fisic = (
        await db.execute(
            select(func.coalesce(func.sum(EstocMagatzem.quantitat_fisica), 0)).where(
                EstocMagatzem.empresa_id == empresa_id,
                EstocMagatzem.article_id == article.id,
            )
        )
    ).scalar_one()
    article.estoc_total_actual = float(_q3(total_fisic))


async def resoldre_magatzem_furgoneta(
    db: AsyncSession,
    empresa_id: uuid.UUID,
    *,
    ordre_treball_id: Optional[uuid.UUID] = None,
    usuari_id: Optional[uuid.UUID] = None,
    magatzem_id: Optional[uuid.UUID] = None,
) -> Tuple[Optional[Magatzem], Optional[Vehicle]]:
    """Resol el magatzem mòbil (tipus='FURGONETA') associat a una OT o a l'operari."""
    if magatzem_id is not None:
        mag = (
            await db.execute(
                select(Magatzem).where(
                    Magatzem.id == magatzem_id,
                    Magatzem.empresa_id == empresa_id,
                    Magatzem.tipus == "FURGONETA",
                )
            )
        ).scalars().first()
        if mag:
            veh = (
                (
                    await db.execute(
                        select(Vehicle).where(
                            Vehicle.id == mag.vehicle_id,
                            Vehicle.empresa_id == empresa_id,
                        )
                    )
                )
                .scalars()
                .first()
                if mag.vehicle_id
                else None
            )
            return mag, veh

    vehicle_id: Optional[uuid.UUID] = None
    if ordre_treball_id is not None:
        ot = (
            await db.execute(
                select(OrdreTreball).where(
                    OrdreTreball.id == ordre_treball_id,
                    OrdreTreball.empresa_id == empresa_id,
                )
            )
        ).scalars().first()
        if ot and ot.vehicle_id:
            vehicle_id = ot.vehicle_id

    if vehicle_id is None and usuari_id is not None:
        u = (
            await db.execute(
                select(Usuari).where(
                    Usuari.id == usuari_id,
                    Usuari.empresa_id == empresa_id,
                )
            )
        ).scalars().first()
        if u and getattr(u, "vehicle_assignat_id", None):
            vehicle_id = u.vehicle_assignat_id
        if vehicle_id is None:
            veh_hab = (
                await db.execute(
                    select(Vehicle).where(
                        Vehicle.empresa_id == empresa_id,
                        Vehicle.conductor_habitual_id == usuari_id,
                    )
                )
            ).scalars().first()
            if veh_hab:
                vehicle_id = veh_hab.id

    if vehicle_id is not None:
        veh = (
            await db.execute(
                select(Vehicle).where(
                    Vehicle.id == vehicle_id,
                    Vehicle.empresa_id == empresa_id,
                )
            )
        ).scalars().first()
        mag = (
            await db.execute(
                select(Magatzem).where(
                    Magatzem.empresa_id == empresa_id,
                    Magatzem.vehicle_id == vehicle_id,
                    Magatzem.tipus == "FURGONETA",
                )
            )
        ).scalars().first()
        if mag is None and veh and veh.magatzem_id:
            mag = (
                await db.execute(
                    select(Magatzem).where(
                        Magatzem.id == veh.magatzem_id,
                        Magatzem.empresa_id == empresa_id,
                    )
                )
            ).scalars().first()
        return mag, veh

    return None, None


async def obtenir_estoc_furgoneta_operari(
    db: AsyncSession,
    empresa_id: uuid.UUID,
    *,
    ordre_treball_id: Optional[uuid.UUID] = None,
    usuari_id: Optional[uuid.UUID] = None,
) -> Dict[str, Any]:
    """Retorna l'estoc disponible real del magatzem mòbil (FURGONETA) assignat a l'OT o operari."""
    mag, veh = await resoldre_magatzem_furgoneta(
        db,
        empresa_id,
        ordre_treball_id=ordre_treball_id,
        usuari_id=usuari_id,
    )
    if mag is None:
        return {
            "magatzem_id": None,
            "magatzem_nom": None,
            "vehicle_id": str(veh.id) if veh else None,
            "vehicle_matricula": veh.matricula if veh else None,
            "vehicle_model": f"{veh.marca} {veh.model}".strip() if veh else None,
            "items": [],
        }

    rows = (
        await db.execute(
            select(EstocMagatzem, Article)
            .join(Article, EstocMagatzem.article_id == Article.id)
            .where(
                EstocMagatzem.empresa_id == empresa_id,
                EstocMagatzem.magatzem_id == mag.id,
            )
            .order_by(Article.nom.asc())
        )
    ).all()

    items: List[Dict[str, Any]] = []
    for estoc, art in rows:
        fisica = _q3(estoc.quantitat_fisica or 0)
        reservada = _q3(estoc.quantitat_virtual_reservada or 0)
        disponible = max(Decimal("0.000"), _q3(fisica - reservada))
        if disponible <= 0:
            continue
        items.append(
            {
                "estoc_id": str(estoc.id),
                "article_id": str(art.id),
                "nom": art.nom,
                "referencia": art.referencia_inventari,
                "codi_barres": getattr(art, "codi_barres", None),
                "unitat": art.unitat_mesura or "UNITAT",
                "format_continu": bool(getattr(art, "es_material_continu", False)),
                "quantitat_fisica": float(fisica),
                "quantitat_disponible": float(disponible),
            }
        )

    return {
        "magatzem_id": str(mag.id),
        "magatzem_nom": mag.nom,
        "vehicle_id": str(veh.id) if veh else (str(mag.vehicle_id) if mag.vehicle_id else None),
        "vehicle_matricula": veh.matricula if veh else None,
        "vehicle_model": f"{veh.marca} {veh.model}".strip() if veh else None,
        "items": items,
    }


async def actualitzar_linia_picking_amb_estoc(
    db: AsyncSession,
    empresa_id: uuid.UUID,
    linia_id: uuid.UUID,
    *,
    usuari_id: Optional[uuid.UUID] = None,
    quantitat_carregada_pick_in: Optional[float] = None,
    quantitat_retornada_pick_out: Optional[float] = None,
    quantitat_mermada: Optional[float] = None,
    auto_commit: bool = True,
) -> Dict[str, Any]:
    """Actualitza Pick-In / Pick-Out / Merma d'una línia de picking amb ajust atòmic i idempotent de magatzem."""
    if quantitat_carregada_pick_in is not None and quantitat_carregada_pick_in < 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="La quantitat carregada (Pick-In) no pot ser negativa.",
        )
    if quantitat_retornada_pick_out is not None and quantitat_retornada_pick_out < 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="La quantitat retornada (Pick-Out) no pot ser negativa.",
        )
    if quantitat_mermada is not None and quantitat_mermada < 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="La quantitat mermada no pot ser negativa.",
        )

    linia = (
        await db.execute(
            select(LiniaPicking)
            .where(
                LiniaPicking.id == linia_id,
                LiniaPicking.empresa_id == empresa_id,
            )
            .with_for_update()
        )
    ).scalars().first()
    if not linia:
        raise HTTPException(status_code=404, detail="Línia de picking no trobada")

    fulla = (
        await db.execute(
            select(FullaPicking).where(
                FullaPicking.id == linia.picking_id,
                FullaPicking.empresa_id == empresa_id,
            )
        )
    ).scalars().first()
    ot = (
        (
            await db.execute(
                select(OrdreTreball).where(
                    OrdreTreball.id == fulla.ordre_treball_id,
                    OrdreTreball.empresa_id == empresa_id,
                )
            )
        )
        .scalars()
        .first()
        if fulla
        else None
    )
    article = (
        await db.execute(
            select(Article).where(
                Article.id == linia.article_id,
                Article.empresa_id == empresa_id,
            )
        )
    ).scalars().first()

    old_aplicat = _q3(getattr(linia, "consum_aplicat_magatzem", 0) or 0)
    old_merma = _q3(linia.quantitat_mermada or 0)
    old_pick_out = _q3(linia.quantitat_retornada_pick_out or 0)
    ja_reconciliat = bool(old_aplicat > 0 or old_pick_out > 0 or old_merma > 0)

    es_pick_out = (
        quantitat_retornada_pick_out is not None or quantitat_mermada is not None
    )

    # Calcular i validar coherència física ABANS de mutar cap atribut ORM
    q_prev = _q3(linia.quantitat_prevista or 0)
    q_in = (
        _q3(quantitat_carregada_pick_in)
        if quantitat_carregada_pick_in is not None
        else _q3(linia.quantitat_carregada_pick_in or 0)
    )
    q_out = (
        _q3(quantitat_retornada_pick_out)
        if quantitat_retornada_pick_out is not None
        else old_pick_out
    )
    q_merma = (
        _q3(quantitat_mermada)
        if quantitat_mermada is not None
        else old_merma
    )

    base_carregada = q_in if q_in > 0 else q_prev
    if es_pick_out and base_carregada > 0 and (q_out + q_merma) > base_carregada:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"La suma de retorn ({float(q_out)}) i merma ({float(q_merma)}) "
                f"no pot superar la quantitat carregada ({float(base_carregada)})."
            ),
        )

    if quantitat_carregada_pick_in is not None:
        linia.quantitat_carregada_pick_in = float(q_in)
        if fulla and fulla.estat_picking == "PENDENT" and q_in > 0:
            fulla.estat_picking = "EN_CURS"
    if quantitat_retornada_pick_out is not None:
        linia.quantitat_retornada_pick_out = float(q_out)
    if quantitat_mermada is not None:
        linia.quantitat_mermada = float(q_merma)

    estoc_actualitzat = False
    if es_pick_out:
        baixa_fisica_total = max(Decimal("0.000"), _q3(base_carregada - q_out))
        delta_fisic = _q3(baixa_fisica_total - old_aplicat)
        delta_merma = _q3(q_merma - old_merma)

        stmt_estoc = select(EstocMagatzem).where(
            EstocMagatzem.empresa_id == empresa_id,
            EstocMagatzem.article_id == linia.article_id,
        )
        if linia.magatzem_id is not None:
            stmt_estoc = stmt_estoc.where(EstocMagatzem.magatzem_id == linia.magatzem_id)
        else:
            stmt_estoc = stmt_estoc.order_by(EstocMagatzem.quantitat_fisica.desc())

        estoc = (await db.execute(stmt_estoc.with_for_update())).scalars().first()
        if estoc is not None:
            if linia.magatzem_id is None:
                linia.magatzem_id = estoc.magatzem_id

            # Alliberar reserva virtual una única vegada al primer Pick-Out (idempotent)
            if not ja_reconciliat and q_prev > 0:
                estoc.quantitat_virtual_reservada = float(
                    max(
                        Decimal("0.000"),
                        _q3(Decimal(str(estoc.quantitat_virtual_reservada or 0)) - q_prev),
                    )
                )

            if delta_fisic != 0:
                estoc.quantitat_fisica = float(
                    max(
                        Decimal("0.000"),
                        _q3(Decimal(str(estoc.quantitat_fisica or 0)) - delta_fisic),
                    )
                )
                ref_doc = ot.codi if ot else str(linia.picking_id)
                if delta_fisic > 0:
                    db.add(
                        MovimentEstoc(
                            empresa_id=empresa_id,
                            magatzem_id=estoc.magatzem_id,
                            article_id=linia.article_id,
                            tipus_moviment="SORTIDA",
                            quantitat=float(delta_fisic),
                            usuari_id=usuari_id,
                            referencia_document=ref_doc,
                            notes=(
                                f"Pick-Out PWA OT {ref_doc}: carregat={float(base_carregada)}, "
                                f"retorn={float(q_out)}, merma={float(q_merma)}"
                            ),
                        )
                    )
                else:
                    db.add(
                        MovimentEstoc(
                            empresa_id=empresa_id,
                            magatzem_id=estoc.magatzem_id,
                            article_id=linia.article_id,
                            tipus_moviment="ENTRADA",
                            quantitat=float(abs(delta_fisic)),
                            usuari_id=usuari_id,
                            referencia_document=ref_doc,
                            notes=(
                                f"Ajust devolució Pick-Out PWA OT {ref_doc}: "
                                f"retorn={float(q_out)}, merma={float(q_merma)}"
                            ),
                        )
                    )

            if delta_merma != 0:
                estoc.quantitat_cuarentena = float(
                    max(
                        Decimal("0.000"),
                        _q3(Decimal(str(estoc.quantitat_cuarentena or 0)) + delta_merma),
                    )
                )
                if article is not None:
                    article.estoc_slot_residus = float(
                        max(
                            Decimal("0.000"),
                            _q3(Decimal(str(article.estoc_slot_residus or 0)) + delta_merma),
                        )
                    )
                if delta_merma > 0 and article is not None:
                    pmp_u = _resoldre_pmp_article(article)
                    cost_merma = _q2(delta_merma * pmp_u)
                    db.add(
                        MermaInventari(
                            empresa_id=empresa_id,
                            article_id=article.id,
                            magatzem_id=estoc.magatzem_id,
                            ordre_treball_id=ot.id if ot else None,
                            usuari_id=usuari_id,
                            quantitat=float(delta_merma),
                            pmp_aplicat=float(pmp_u),
                            cost_total=float(cost_merma),
                            motiu="MERMA_OBRA_PICK_OUT",
                            subcompte_comptable="600.MERMA_OBRA",
                            transferit_slot_residus=True,
                            notes=f"Merma declarada a Pick-Out PWA (OT {ot.codi if ot else linia.picking_id})",
                        )
                    )
                    db.add(
                        MovimentEstoc(
                            empresa_id=empresa_id,
                            magatzem_id=estoc.magatzem_id,
                            article_id=article.id,
                            tipus_moviment="MERMA",
                            quantitat=float(delta_merma),
                            usuari_id=usuari_id,
                            referencia_document=ot.codi if ot else str(linia.picking_id),
                            notes="Merma d'obra declarada a Pick-Out PWA",
                        )
                    )

            if article is not None:
                await _resincronitzar_estoc_total_article(db, empresa_id, article)
            estoc_actualitzat = True

        linia.consum_aplicat_magatzem = float(baixa_fisica_total)
        if fulla and fulla.estat_picking != "TANCAT":
            fulla.estat_picking = "RECONCILIAT"

    if ot is not None:
        await recalcular_totals_materials_ot(db, empresa_id, ot.id)

    await avaluar_i_sincronitzar_alertes_recompra(db, empresa_id, [linia.article_id])
    if auto_commit:
        await db.commit()
    else:
        await db.flush()

    pick_in_f = float(linia.quantitat_carregada_pick_in or 0.0)
    pick_out_f = float(linia.quantitat_retornada_pick_out or 0.0)
    merma_f = float(linia.quantitat_mermada or 0.0)
    consum_real = max(0.0, round(pick_in_f - pick_out_f, 3))

    try:
        await SovereignStorageGateway.desar_entitat_json(
            db=db,
            empresa_id=empresa_id,
            categoria="picking",
            item_id=f"linia_{linia.id}",
            dades={
                "id": str(linia.id),
                "picking_id": str(linia.picking_id),
                "article_id": str(linia.article_id),
                "magatzem_id": str(linia.magatzem_id) if linia.magatzem_id else None,
                "origen_estoc": getattr(linia, "origen_estoc", "NAU") or "NAU",
                "quantitat_prevista": float(linia.quantitat_prevista),
                "quantitat_carregada_pick_in": pick_in_f,
                "quantitat_retornada_pick_out": pick_out_f,
                "quantitat_mermada": merma_f,
                "consum_real": consum_real,
                "consum_aplicat_magatzem": float(linia.consum_aplicat_magatzem or 0.0),
            },
        )
    except Exception as exc:
        logger.warning("No s'ha pogut sincronitzar la línia de picking %s al disc: %s", linia.id, exc)

    return {
        "id": linia.id,
        "article_id": linia.article_id,
        "quantitat_prevista": float(linia.quantitat_prevista),
        "quantitat_carregada_pick_in": pick_in_f,
        "quantitat_retornada_pick_out": pick_out_f,
        "quantitat_mermada": merma_f,
        "consum_real": consum_real,
        "consum_aplicat_magatzem": float(linia.consum_aplicat_magatzem or 0.0),
        "origen_estoc": getattr(linia, "origen_estoc", "NAU") or "NAU",
        "estoc_actualitzat": estoc_actualitzat,
    }


async def registrar_consum_material_furgoneta(
    db: AsyncSession,
    empresa_id: uuid.UUID,
    ordre_treball_id: uuid.UUID,
    article_id: uuid.UUID,
    quantitat: float,
    *,
    quantitat_mermada: float = 0.0,
    magatzem_id: Optional[uuid.UUID] = None,
    usuari_id: Optional[uuid.UUID] = None,
    notes: Optional[str] = None,
    auto_commit: bool = True,
) -> Dict[str, Any]:
    """Descompta material del magatzem mòbil (FURGONETA) i el vincula atòmicament a la Fulla de Picking de l'OT."""
    q_sol = _q3(quantitat)
    q_merma = _q3(quantitat_mermada)
    if q_sol <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="La quantitat a agafar de la furgoneta ha de ser superior a 0.",
        )
    if q_merma < 0 or q_merma > q_sol:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="La merma no pot ser negativa ni superior a la quantitat consumida.",
        )

    ot = (
        await db.execute(
            select(OrdreTreball).where(
                OrdreTreball.id == ordre_treball_id,
                OrdreTreball.empresa_id == empresa_id,
            )
        )
    ).scalars().first()
    if not ot:
        raise HTTPException(status_code=404, detail="Ordre de treball no trobada")

    article = (
        await db.execute(
            select(Article).where(
                Article.id == article_id,
                Article.empresa_id == empresa_id,
            )
        )
    ).scalars().first()
    if not article:
        raise HTTPException(status_code=404, detail="Article no trobat")

    mag, veh = await resoldre_magatzem_furgoneta(
        db,
        empresa_id,
        ordre_treball_id=ordre_treball_id,
        usuari_id=usuari_id,
        magatzem_id=magatzem_id,
    )
    if mag is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="No s'ha trobat cap magatzem de vehicle (FURGONETA) assignat a aquesta ordre o operari.",
        )

    estoc = (
        await db.execute(
            select(EstocMagatzem)
            .where(
                EstocMagatzem.empresa_id == empresa_id,
                EstocMagatzem.magatzem_id == mag.id,
                EstocMagatzem.article_id == article.id,
            )
            .with_for_update()
        )
    ).scalars().first()

    if estoc is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"L'article '{article.nom}' no té estoc a la furgoneta '{mag.nom}'.",
        )

    fisica_actual = _q3(estoc.quantitat_fisica or 0)
    reservada_actual = _q3(estoc.quantitat_virtual_reservada or 0)
    disponible = max(Decimal("0.000"), _q3(fisica_actual - reservada_actual))
    if q_sol > disponible:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"Estoc insuficient a la furgoneta '{mag.nom}' per a '{article.nom}'. "
                f"Disponible: {float(disponible)}, sol·licitat: {float(q_sol)}."
            ),
        )

    # 1. Descomptar del magatzem de la furgoneta
    estoc.quantitat_fisica = float(_q3(fisica_actual - q_sol))
    if q_merma > 0:
        estoc.quantitat_cuarentena = float(
            _q3(Decimal(str(estoc.quantitat_cuarentena or 0)) + q_merma)
        )
        article.estoc_slot_residus = float(
            _q3(Decimal(str(article.estoc_slot_residus or 0)) + q_merma)
        )

    await _resincronitzar_estoc_total_article(db, empresa_id, article)

    # 2. Localitzar o crear FullaPicking de l'OT
    fulla = (
        await db.execute(
            select(FullaPicking)
            .where(
                FullaPicking.empresa_id == empresa_id,
                FullaPicking.ordre_treball_id == ot.id,
            )
            .order_by(FullaPicking.created_at.asc())
        )
    ).scalars().first()
    if fulla is None:
        fulla = FullaPicking(
            empresa_id=empresa_id,
            ordre_treball_id=ot.id,
            vehicle_id=veh.id if veh else mag.vehicle_id,
            estat_picking="EN_CURS",
        )
        db.add(fulla)
        await db.flush()
    elif fulla.estat_picking == "PENDENT":
        fulla.estat_picking = "EN_CURS"

    # 3. Localitzar o crear LiniaPicking amb origen_estoc='FURGONETA'
    linia = (
        await db.execute(
            select(LiniaPicking)
            .where(
                LiniaPicking.empresa_id == empresa_id,
                LiniaPicking.picking_id == fulla.id,
                LiniaPicking.article_id == article.id,
                LiniaPicking.magatzem_id == mag.id,
                LiniaPicking.origen_estoc == "FURGONETA",
            )
            .with_for_update()
        )
    ).scalars().first()

    if linia is None:
        linia = LiniaPicking(
            empresa_id=empresa_id,
            picking_id=fulla.id,
            article_id=article.id,
            magatzem_id=mag.id,
            quantitat_prevista=0.0,
            quantitat_carregada_pick_in=float(q_sol),
            quantitat_retornada_pick_out=0.0,
            quantitat_mermada=float(q_merma),
            origen_estoc="FURGONETA",
            consum_aplicat_magatzem=float(q_sol),
        )
        db.add(linia)
        await db.flush()
    else:
        linia.quantitat_carregada_pick_in = float(
            _q3(Decimal(str(linia.quantitat_carregada_pick_in or 0)) + q_sol)
        )
        linia.quantitat_mermada = float(
            _q3(Decimal(str(linia.quantitat_mermada or 0)) + q_merma)
        )
        linia.consum_aplicat_magatzem = float(
            _q3(Decimal(str(linia.consum_aplicat_magatzem or 0)) + q_sol)
        )

    # 4. Registrar moviment d'estoc i merma (si escau)
    db.add(
        MovimentEstoc(
            empresa_id=empresa_id,
            magatzem_id=mag.id,
            article_id=article.id,
            tipus_moviment="SORTIDA",
            quantitat=float(q_sol),
            usuari_id=usuari_id,
            referencia_document=ot.codi,
            notes=(
                f"Consum directe de furgoneta ({mag.nom}) a OT {ot.codi}"
                + (f" — {notes.strip()}" if notes and notes.strip() else "")
            ),
        )
    )

    if q_merma > 0:
        pmp_u = _resoldre_pmp_article(article)
        cost_merma = _q2(q_merma * pmp_u)
        db.add(
            MermaInventari(
                empresa_id=empresa_id,
                article_id=article.id,
                magatzem_id=mag.id,
                ordre_treball_id=ot.id,
                usuari_id=usuari_id,
                quantitat=float(q_merma),
                pmp_aplicat=float(pmp_u),
                cost_total=float(cost_merma),
                motiu="MERMA_OBRA_FURGONETA",
                subcompte_comptable="600.MERMA_OBRA",
                transferit_slot_residus=True,
                notes=f"Merma en consum de furgoneta ({mag.nom}) per OT {ot.codi}",
            )
        )
        db.add(
            MovimentEstoc(
                empresa_id=empresa_id,
                magatzem_id=mag.id,
                article_id=article.id,
                tipus_moviment="MERMA",
                quantitat=float(q_merma),
                usuari_id=usuari_id,
                referencia_document=ot.codi,
                notes=f"Merma en consum de furgoneta ({mag.nom}) per OT {ot.codi}",
            )
        )

    # 5. Recalcular totals reals de l'OT i alertes de reposició
    cost_pmp_ot, pvp_mat_ot = await recalcular_totals_materials_ot(db, empresa_id, ot.id)
    await avaluar_i_sincronitzar_alertes_recompra(db, empresa_id, [article.id])

    if auto_commit:
        await db.commit()

    try:
        await SovereignStorageGateway.desar_entitat_json(
            db=db,
            empresa_id=empresa_id,
            categoria="picking",
            item_id=f"linia_{linia.id}",
            dades={
                "id": str(linia.id),
                "picking_id": str(fulla.id),
                "ordre_treball_id": str(ot.id),
                "article_id": str(article.id),
                "magatzem_id": str(mag.id),
                "origen_estoc": "FURGONETA",
                "quantitat_carregada_pick_in": float(linia.quantitat_carregada_pick_in),
                "quantitat_mermada": float(linia.quantitat_mermada),
                "consum_aplicat_magatzem": float(linia.consum_aplicat_magatzem),
            },
        )
    except Exception as exc:
        logger.warning("No s'ha pogut sincronitzar el consum de furgoneta al disc: %s", exc)

    return {
        "linia_id": str(linia.id),
        "picking_id": str(fulla.id),
        "ordre_treball_id": str(ot.id),
        "article_id": str(article.id),
        "article_nom": article.nom,
        "magatzem_id": str(mag.id),
        "magatzem_nom": mag.nom,
        "origen_estoc": "FURGONETA",
        "quantitat_consumida": float(q_sol),
        "quantitat_mermada": float(q_merma),
        "estoc_restant_furgoneta": float(estoc.quantitat_fisica),
        "pvp_materials_ot": float(pvp_mat_ot),
        "cost_materials_pmp_ot": float(cost_pmp_ot),
    }
