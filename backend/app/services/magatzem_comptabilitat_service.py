"""Servei d'integració analítica Magatzem -> Comptabilitat (Pla 2 / Specs 003, 004, 007, 018)."""

from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import (
    Article,
    DespesaComptable,
    EstocMagatzem,
    FacturaLinia,
    FullaPicking,
    Incidencia,
    LiniaPicking,
    Magatzem,
    MermaInventari,
    MovimentEstoc,
    OrdreTreball,
    TiquetDespesa,
)

TWO_DEC = Decimal("0.01")
THREE_DEC = Decimal("0.001")
FOUR_DEC = Decimal("0.0001")

MOTIUS_MERMA_OBRA = {
    "OBRA_TALL_INUTIL",
    "ENVAS_DESPRECINTAT_CAMP",
    "FIANCA_PALET_TRENCAT",
}
MOTIUS_MERMA_MAGATZEM = {
    "CADUCITAT_FEFO",
    "TRENCAMENT_NAU",
}
MOTIUS_MERMA_VALIDS = MOTIUS_MERMA_OBRA | MOTIUS_MERMA_MAGATZEM


def _q2(val: Decimal | float | int) -> Decimal:
    return Decimal(str(val)).quantize(TWO_DEC, rounding=ROUND_HALF_UP)


def _q3(val: Decimal | float | int) -> Decimal:
    return Decimal(str(val)).quantize(THREE_DEC, rounding=ROUND_HALF_UP)


def _q4(val: Decimal | float | int) -> Decimal:
    return Decimal(str(val)).quantize(FOUR_DEC, rounding=ROUND_HALF_UP)


async def processar_entrada_albara_i_recalcular_pmp(
    db: AsyncSession,
    empresa_id: UUID,
    article_id: UUID,
    magatzem_id: UUID,
    quantitat_rebuda: Decimal,
    preu_compra_unitari: Decimal,
    preu_ferm_comanda: Decimal | None = None,
    es_granel_continu: bool = False,
    quantitat_demanada_comanda: Decimal | None = None,
    referencia_document: str | None = None,
    usuari_id: UUID | None = None,
) -> dict[str, Any]:
    """
    Spec 003 (RF-23, RF-24, RF-24.1) + Spec 004 (RF-41, RF-46):
    1. Valida la Clàusula de Preu Ferm (bloqueja amb HTTP 409 si preu_compra_unitari > preu_ferm_comanda).
    2. Aplica tolerància del +-2% si és material a granel/format continu.
    3. Recalcula el Preu Mitjà Ponderat (PMP) de forma atòmica amb SELECT ... FOR UPDATE,
       excloent materials en dipòsit de proveïdor o custòdia RMA de client.
    """
    if quantitat_rebuda <= 0:
        raise HTTPException(
            status_code=422,
            detail="La quantitat rebuda ha de ser positiva.",
        )

    stmt_art = (
        select(Article)
        .where(Article.id == article_id, Article.empresa_id == empresa_id)
        .with_for_update()
    )
    article = (await db.execute(stmt_art)).scalar_one_or_none()
    if not article:
        raise HTTPException(status_code=404, detail="Article no trobat al magatzem del tenant")

    stmt_mag = select(Magatzem).where(
        Magatzem.id == magatzem_id,
        Magatzem.empresa_id == empresa_id,
    )
    magatzem = (await db.execute(stmt_mag)).scalar_one_or_none()
    if not magatzem:
        raise HTTPException(status_code=404, detail="Magatzem no trobat al tenant")

    # 1. Control de Clàusula de Preu Ferm (Spec 003 RF-23 / Spec 004 RF-41.1)
    if preu_ferm_comanda is not None and _q4(preu_compra_unitari) > _q4(preu_ferm_comanda):
        incidencia = Incidencia(
            id=uuid4(),
            empresa_id=empresa_id,
            ambit="MAGATZEM",
            tipus="NO_CONFORMITAT_PREU_ALBARA",
            gravetat="ALTA",
            estat="OBERTA",
            text_observacions=(
                f"Incompliment de Clàusula de Preu Ferm a l'article {article.referencia_inventari}: "
                f"Pactat {preu_ferm_comanda} € vs Albarà/Factura {preu_compra_unitari} €. PMP bloquejat."
            ),
        )
        db.add(incidencia)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Alerta de No Conformitat: Preu superior al Preu Ferm pactat. Actualització de PMP bloquejada.",
        )

    # 2. Tolerància del +-2% en materials a granel/continu (Spec 003 RF-24.1)
    conciliacio_estat = "CONCILIADA"
    es_continu = bool(es_granel_continu or getattr(article, "es_material_continu", False))
    if quantitat_demanada_comanda is not None and quantitat_demanada_comanda > 0:
        desviacio_pct = (
            abs(quantitat_rebuda - quantitat_demanada_comanda) / quantitat_demanada_comanda
        )
        if es_continu and desviacio_pct <= Decimal("0.02"):
            conciliacio_estat = "CONCILIADA_TOLERANCIA_GRANEL_2PCT"
        elif quantitat_rebuda < quantitat_demanada_comanda:
            conciliacio_estat = "ENTREGA_PARCIAL_BACKORDER"
        elif quantitat_rebuda > quantitat_demanada_comanda:
            conciliacio_estat = "EXCES_QUANTITAT_PER_REVISAR"

    # 3. Bloqueig pessimista d'estoc i recàlcul de PMP (Spec 004 RF-41.2 i RF-46)
    stmt_estoc = (
        select(EstocMagatzem)
        .where(
            EstocMagatzem.article_id == article_id,
            EstocMagatzem.magatzem_id == magatzem_id,
            EstocMagatzem.empresa_id == empresa_id,
        )
        .with_for_update()
    )
    estoc = (await db.execute(stmt_estoc)).scalar_one_or_none()
    if estoc is None:
        estoc = EstocMagatzem(
            empresa_id=empresa_id,
            article_id=article_id,
            magatzem_id=magatzem_id,
            quantitat_fisica=0.0,
            quantitat_virtual_reservada=0.0,
            quantitat_cuarentena=0.0,
        )
        db.add(estoc)
        await db.flush()

    estoc_actual_total = _q3(article.estoc_total_actual or estoc.quantitat_fisica or 0)
    pmp_anterior = _q4(
        article.pmp_actual or article.preu_cost_mitja or article.preu_cost or 0
    )

    exclos_pmp = bool(
        getattr(article, "es_diposit_proveidor", False)
        or getattr(article, "es_custodia_rma_client", False)
    )
    if not exclos_pmp:
        denominador = estoc_actual_total + _q3(quantitat_rebuda)
        if denominador > 0:
            nou_pmp = _q4(
                ((estoc_actual_total * pmp_anterior) + (quantitat_rebuda * preu_compra_unitari))
                / denominador
            )
            article.pmp_actual = float(nou_pmp)
            article.preu_cost_mitja = float(nou_pmp)
            article.ultim_preu_compra = float(_q4(preu_compra_unitari))
            article.preu_cost_ultim = float(_q4(preu_compra_unitari))
            article.preu_cost = float(_q2(nou_pmp))

    nou_estoc_total = _q3(estoc_actual_total + _q3(quantitat_rebuda))
    article.estoc_total_actual = float(nou_estoc_total)
    estoc.quantitat_fisica = float(_q3(Decimal(str(estoc.quantitat_fisica or 0)) + quantitat_rebuda))

    db.add(
        MovimentEstoc(
            id=uuid4(),
            empresa_id=empresa_id,
            magatzem_id=magatzem_id,
            article_id=article_id,
            tipus_moviment="ENTRADA",
            quantitat=float(_q3(quantitat_rebuda)),
            referencia_document=referencia_document,
            notes=f"Entrada PMP ({conciliacio_estat}) a {preu_compra_unitari} EUR/u",
            usuari_id=usuari_id,
        )
    )

    await db.commit()
    return {
        "article_id": str(article.id),
        "magatzem_id": str(magatzem_id),
        "pmp_anterior": float(_q4(pmp_anterior)),
        "pmp_nou": float(_q4(article.pmp_actual or 0)),
        "estoc_total_actual": float(_q3(article.estoc_total_actual)),
        "conciliacio_estat": conciliacio_estat,
        "exclos_pmp_diposit_o_rma": exclos_pmp,
    }


async def registrar_merma_i_imputar_a_comptabilitat(
    db: AsyncSession,
    empresa_id: UUID,
    article_id: UUID,
    magatzem_id: UUID,
    quantitat_mermada: Decimal,
    motiu: str,
    ordre_treball_id: UUID | None = None,
    usuari_id: UUID | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    """
    Spec 004 (RF-19, RF-37, RF-40, RF-51) + Spec 007:
    - Descompta de forma atòmica les unitats de l'estoc actiu i les mou al Slot de Residus/Ferralla.
    - Calcula el cost comptable exacte segons el PMP vigent.
    - Si és imputable a obra (OBRA_TALL_INUTIL, ENVAS_DESPRECINTAT_CAMP, FIANCA_PALET_TRENCAT),
      exigeix ordre_treball_id i crea apunt a DespesaComptable sota 600.MERMA_OBRA.
    - Si és de nau (CADUCITAT_FEFO, TRENCAMENT_NAU), l'imputa a 659.MERMA_MAGATZEM.
    """
    if motiu not in MOTIUS_MERMA_VALIDS:
        raise HTTPException(
            status_code=422,
            detail=f"Motiu de merma invàlid: {motiu}. Vàlids: {sorted(MOTIUS_MERMA_VALIDS)}",
        )

    if quantitat_mermada <= 0:
        raise HTTPException(
            status_code=422,
            detail="La quantitat mermada ha de ser superior a 0.",
        )

    imputable_a_obra = motiu in MOTIUS_MERMA_OBRA
    if imputable_a_obra and ordre_treball_id is None:
        raise HTTPException(
            status_code=422,
            detail=f"El motiu de merma '{motiu}' exigeix indicar l'ordre_treball_id per imputar el cost a l'obra.",
        )

    if ordre_treball_id is not None:
        ot_check = (
            await db.execute(
                select(OrdreTreball.id).where(
                    OrdreTreball.id == ordre_treball_id,
                    OrdreTreball.empresa_id == empresa_id,
                )
            )
        ).scalar_one_or_none()
        if not ot_check:
            raise HTTPException(status_code=404, detail="Ordre de treball no trobada al tenant")

    stmt_art = (
        select(Article)
        .where(Article.id == article_id, Article.empresa_id == empresa_id)
        .with_for_update()
    )
    article = (await db.execute(stmt_art)).scalar_one_or_none()
    if not article:
        raise HTTPException(status_code=404, detail="Article no trobat")

    stmt_estoc = (
        select(EstocMagatzem)
        .where(
            EstocMagatzem.article_id == article_id,
            EstocMagatzem.magatzem_id == magatzem_id,
            EstocMagatzem.empresa_id == empresa_id,
        )
        .with_for_update()
    )
    estoc = (await db.execute(stmt_estoc)).scalar_one_or_none()

    estoc_act = _q3(article.estoc_total_actual or 0)
    if estoc_act <= 0 and estoc and _q3(estoc.quantitat_fisica or 0) > 0:
        estoc_act = _q3(estoc.quantitat_fisica)

    qty_merma = _q3(quantitat_mermada)
    if estoc_act < qty_merma:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No es pot mermar més quantitat de la disponible en estoc físic",
        )

    cost_unitari = _q4(
        article.pmp_actual
        or article.preu_cost_mitja
        or article.ultim_preu_compra
        or article.preu_cost
        or 0
    )
    cost_total_merma = _q2(qty_merma * cost_unitari)

    nou_estoc = _q3(estoc_act - qty_merma)
    nou_residus = _q3(Decimal(str(article.estoc_slot_residus or 0)) + qty_merma)
    article.estoc_total_actual = float(nou_estoc)
    article.estoc_slot_residus = float(nou_residus)

    if estoc:
        estoc.quantitat_fisica = float(
            max(Decimal("0.000"), _q3(Decimal(str(estoc.quantitat_fisica or 0)) - qty_merma))
        )
        estoc.quantitat_cuarentena = float(
            _q3(Decimal(str(estoc.quantitat_cuarentena or 0)) + qty_merma)
        )

    subcompte = "600.MERMA_OBRA" if imputable_a_obra else "659.MERMA_MAGATZEM"

    merma = MermaInventari(
        id=uuid4(),
        empresa_id=empresa_id,
        article_id=article.id,
        magatzem_id=magatzem_id,
        ordre_treball_id=ordre_treball_id,
        usuari_id=usuari_id,
        quantitat=float(qty_merma),
        pmp_aplicat=float(cost_unitari),
        cost_total=float(cost_total_merma),
        motiu=motiu,
        subcompte_comptable=subcompte,
        transferit_slot_residus=True,
        notes=notes,
    )
    db.add(merma)
    await db.flush()

    despesa = DespesaComptable(
        id=uuid4(),
        empresa_id=empresa_id,
        ordre_treball_id=ordre_treball_id,
        merma_id=merma.id,
        concepte=(
            f"Merma d'inventari ({motiu}) - {article.nom} "
            f"({qty_merma} {article.unitat_mesura})"
        )[:500],
        subcompte=subcompte,
        base_imposable=float(cost_total_merma),
        quota_iva=0.00,
        import_total=float(cost_total_merma),
        estat="CONSOLIDADA",
        origen="MAGATZEM_MERMA",
    )
    db.add(despesa)

    db.add(
        MovimentEstoc(
            id=uuid4(),
            empresa_id=empresa_id,
            magatzem_id=magatzem_id,
            article_id=article.id,
            tipus_moviment="MERMA",
            quantitat=float(qty_merma),
            referencia_document=str(merma.id),
            notes=f"Merma {motiu} -> {subcompte}",
            usuari_id=usuari_id,
        )
    )

    await db.commit()
    return {
        "merma_id": str(merma.id),
        "despesa_comptable_id": str(despesa.id),
        "cost_total_imputat": float(cost_total_merma),
        "subcompte": subcompte,
        "ordre_treball_id": str(ordre_treball_id) if ordre_treball_id else None,
        "estoc_restant": float(nou_estoc),
        "estoc_slot_residus": float(nou_residus),
    }


async def calcular_cost_i_marge_analitic_ot(
    db: AsyncSession,
    empresa_id: UUID,
    ordre_treball_id: UUID,
) -> dict[str, Any]:
    """
    Calcula en temps real per a /gestio/comptabilitat el Cost Real i el Marge Brut d'una OT:
    - Consum net de materials per balanç (Pick In - Pick Out intacte) valorat a PMP.
    - Mermes imputades a l'obra i envasos desprecintats a camp (100% cost).
    - Tiquets de despesa de camp validats/pendents de canje vinculats a l'OT.
    - Cost de mà d'obra i cost de flota.
    """
    stmt_ot = select(OrdreTreball).where(
        OrdreTreball.id == ordre_treball_id,
        OrdreTreball.empresa_id == empresa_id,
    )
    ot = (await db.execute(stmt_ot)).scalar_one_or_none()
    if not ot:
        raise HTTPException(status_code=404, detail="Ordre de treball no trobada")

    # 1. Cost de materials consumits (Pick In - Pick Out) * PMP
    cost_picking_explicit = _q2(ot.cost_materials_picking_pmp or ot.cost_materials_pmp or 0)
    if cost_picking_explicit > 0:
        cost_picking_net = cost_picking_explicit
    else:
        stmt_pick = (
            select(
                func.coalesce(
                    func.sum(
                        func.greatest(
                            LiniaPicking.quantitat_carregada_pick_in
                            - LiniaPicking.quantitat_retornada_pick_out
                            - LiniaPicking.quantitat_mermada,
                            0,
                        )
                        * func.coalesce(
                            func.nullif(Article.pmp_actual, 0),
                            func.nullif(Article.preu_cost_mitja, 0),
                            Article.preu_cost,
                        )
                    ),
                    0,
                )
            )
            .join(FullaPicking, LiniaPicking.picking_id == FullaPicking.id)
            .join(Article, LiniaPicking.article_id == Article.id)
            .where(
                FullaPicking.ordre_treball_id == ordre_treball_id,
                FullaPicking.empresa_id == empresa_id,
                LiniaPicking.empresa_id == empresa_id,
            )
        )
        cost_picking_net = _q2((await db.execute(stmt_pick)).scalar_one() or 0)

    # 2. Cost de mermes imputades a l'OT
    stmt_mermes = select(func.coalesce(func.sum(MermaInventari.cost_total), 0)).where(
        MermaInventari.empresa_id == empresa_id,
        MermaInventari.ordre_treball_id == ordre_treball_id,
    )
    cost_mermes_ot = _q2((await db.execute(stmt_mermes)).scalar_one() or 0)

    # 3. Tiquets de camp imputats a l'OT i processats per OCR o aprovats a /gestio
    stmt_tiquets = select(func.coalesce(func.sum(TiquetDespesa.import_total), 0)).where(
        TiquetDespesa.empresa_id == empresa_id,
        TiquetDespesa.ordre_treball_id == ordre_treball_id,
        TiquetDespesa.estat_aprovacio.in_(["ARXIVAT_GESTIO", "PENDENT_DE_CANJE", "APROVAT"]),
    )
    cost_tiquets_ot = _q2((await db.execute(stmt_tiquets)).scalar_one() or 0)

    # 4. Cost mà d'obra i flota
    cost_ma_obra = _q2(ot.cost_ma_obra_real or 0)
    cost_flota = _q2(ot.cost_flota_real or 0)

    cost_total_ot = _q2(cost_picking_net + cost_mermes_ot + cost_tiquets_ot + cost_ma_obra + cost_flota)

    # 5. Ingressos nets (explicit o factures/pressupost)
    ingressos_nets = _q2(ot.import_pressupostat_net or 0)
    if ingressos_nets <= 0:
        facturat_ot = (
            await db.execute(
                select(func.coalesce(func.sum(FacturaLinia.subtotal), 0)).where(
                    FacturaLinia.empresa_id == empresa_id,
                    FacturaLinia.obra_id == ordre_treball_id,
                )
            )
        ).scalar_one()
        ingressos_nets = _q2(facturat_ot or ot.import_pressupostat or 0)

    marge_brut_eur = _q2(ingressos_nets - cost_total_ot)
    marge_brut_pct = (
        _q2((marge_brut_eur / ingressos_nets) * Decimal("100"))
        if ingressos_nets > 0
        else Decimal("0.00")
    )

    return {
        "ordre_treball_id": str(ot.id),
        "codi": ot.codi,
        "titol": ot.titol,
        "ingressos_nets_eur": float(ingressos_nets),
        "desglossament_costos": {
            "materials_picking_pmp_eur": float(cost_picking_net),
            "mermes_imputades_eur": float(cost_mermes_ot),
            "tiquets_camp_ocr_eur": float(cost_tiquets_ot),
            "ma_obra_real_eur": float(cost_ma_obra),
            "flota_real_eur": float(cost_flota),
        },
        "cost_total_real_eur": float(cost_total_ot),
        "marge_brut_eur": float(marge_brut_eur),
        "marge_brut_pct": float(marge_brut_pct),
        "alerta_desviacio_marge": bool(ingressos_nets > 0 and marge_brut_pct < Decimal("15.00")),
    }
