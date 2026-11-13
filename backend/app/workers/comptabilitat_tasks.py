"""Tasques Celery periòdiques de la Suite Econòmica i Comptabilitat (Spec 007 v5.0)."""

import asyncio
import logging
import os
import re
import uuid
from datetime import date
from decimal import Decimal
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import (
    Client,
    DespesaComptable,
    Empresa,
    FacturaCapcalera,
    Incidencia,
    RetencioGarantia,
    TiquetDespesa,
    Vehicle,
)
from app.services.economic_suite_service import EconomicSuiteService
from app.workers.celery_app import celery_app
from app.workers.tasks import _run_async_in_worker, get_worker_session

logger = logging.getLogger(__name__)


async def executar_auditoria_diaria_financera_tenant_async(
    db: AsyncSession,
    empresa_id: uuid.UUID,
) -> dict[str, Any]:
    """Executa l'auditoria diària d'un tenant amb sessió RLS activa:
    1. Avalua el risc creditici dels clients (bloqueig per factures >90d excloent retencions 4308).
    2. Marca retencions de garantia client vençudes com a PENDENT_RECLAMACIO.
    3. Obre la finestra d'Art. 80 LIVA (180-270 dies) i marca les expirades (>270 dies).
    """
    avui = date.today()

    clients_res = await db.execute(select(Client).where(Client.empresa_id == empresa_id))
    clients = clients_res.scalars().all()
    clients_bloquejats = 0
    for client in clients:
        updated_client = await EconomicSuiteService.evaluar_risc_client(db, empresa_id, client.id)
        if updated_client.estat_risc_operatiu == "BLOQUEJAT_RISC":
            clients_bloquejats += 1

    ret_res = await db.execute(
        select(RetencioGarantia).where(
            RetencioGarantia.empresa_id == empresa_id,
            RetencioGarantia.estat == "RETINGUDA",
            RetencioGarantia.data_venciment_garantia <= avui,
        )
    )
    retencions_pendents = 0
    for retencio in ret_res.scalars().all():
        retencio.estat = "PENDENT_RECLAMACIO"
        retencions_pendents += 1

    fact_res = await db.execute(
        select(FacturaCapcalera).where(
            FacturaCapcalera.empresa_id == empresa_id,
            FacturaCapcalera.estat_cobrament.in_(["PENDENT", "PARCIAL", "IMPAGADA"]),
            FacturaCapcalera.data_venciment.isnot(None),
        )
    )
    art80_obertes = 0
    art80_expirades = 0
    for factura in fact_res.scalars().all():
        if factura.data_venciment is None:
            continue
        dies_morositat = (avui - factura.data_venciment).days
        if dies_morositat > 270 and factura.estat_art80 != "RECLAMADA_AEAT":
            factura.estat_art80 = "FINESTRA_ART80_EXPIRADA"
            art80_expirades += 1
        elif 180 <= dies_morositat <= 270 and factura.estat_art80 == "NO_APLICA":
            factura.estat_art80 = "FINESTRA_ART80_OBERTA"
            art80_obertes += 1

    await db.commit()
    return {
        "empresa_id": str(empresa_id),
        "clients_bloquejats": clients_bloquejats,
        "retencions_pendents_reclamacio": retencions_pendents,
        "art80_finestres_obertes": art80_obertes,
        "art80_finestres_expirades": art80_expirades,
    }


@celery_app.task(
    name="app.workers.comptabilitat_tasks.executar_auditoria_diaria_financera_tenant",
    queue="queue_periodic",
)
def executar_auditoria_diaria_financera_tenant(empresa_id: str) -> dict[str, Any]:
    """Task Celery per auditar un tenant específic amb sessió RLS aïllada."""

    async def _run() -> dict[str, Any]:
        emp_uuid = uuid.UUID(empresa_id)
        async with get_worker_session(str(emp_uuid)) as session:
            return await executar_auditoria_diaria_financera_tenant_async(session, emp_uuid)

    return asyncio.run(_run())


@celery_app.task(
    name="app.workers.comptabilitat_tasks.executar_auditoria_diaria_financera_tots_tenants",
    queue="queue_periodic",
)
def executar_auditoria_diaria_financera_tots_tenants() -> list[dict[str, Any]]:
    """Itera totes les empreses actives i executa l'auditoria financera amb RLS."""

    async def _run() -> list[dict[str, Any]]:
        async with get_worker_session() as session:
            res = await session.execute(select(Empresa.id))
            empreses_ids = res.scalars().all()

        resultats: list[dict[str, Any]] = []
        for emp_id in empreses_ids:
            try:
                async with get_worker_session(str(emp_id)) as tenant_session:
                    out = await executar_auditoria_diaria_financera_tenant_async(
                        tenant_session, emp_id
                    )
                    resultats.append(out)
            except Exception as exc:
                logger.error("Error en auditoria financera per empresa %s: %s", emp_id, exc)
        return resultats

    return asyncio.run(_run())


def _sanitize_slug(val: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9]+", "_", val or "PROVEIDOR").strip("_")
    return clean[:24] or "PROVEIDOR"


async def _processar_tiquet_ocr_async(
    db: AsyncSession,
    empresa_id: uuid.UUID,
    tiquet_id: uuid.UUID,
) -> dict[str, Any]:
    """
    Spec 018 (RF-08, RF-08.1, RF-13, RF-17, EDGE-01, EDGE-02, EDGE-08) + Spec 007:
    L'OCR NO corre a la PWA. S'executa aquí quan el fitxer arriba a /gestio:
    1. Analitza la imatge amb el motor OCR de /gestio.
    2. Si confiança < 70%, obre Incidència TIQUET_COMPROVACIO_MANUAL.
    3. Si és Carburant + AdBlue mixt, el marca PENDENT_DESGLOSE_MANUAL.
    4. Si supera 100 EUR, bloqueja targeta combustible del vehicle i crea incidència ALTA.
    5. Si manca NIF corporatiu del comprador (EDGE-08), aplica IVA 0% no deduïble a subcompte 62X i PENDENT_DE_CANJE.
    6. Reanomena l'arxiu a [empresa_id]_[UUID]_[proveidor]_[import]_[data].webp i el consolida a DespesaComptable.
    """
    from app.services.ocr_service import ReceiptOCRData, extract_receipt_ocr_data
    from app.services.sovereign_storage import SovereignStorageGateway

    res = await db.execute(
        select(TiquetDespesa).where(
            TiquetDespesa.id == tiquet_id,
            TiquetDespesa.empresa_id == empresa_id,
        )
    )
    tiquet = res.scalars().first()
    if not tiquet:
        return {"status": "NOT_FOUND", "tiquet_id": str(tiquet_id)}

    empresa = (
        await db.execute(select(Empresa).where(Empresa.id == empresa_id))
    ).scalars().first()

    ocr_result: ReceiptOCRData
    if not tiquet.foto_tiquet_path:
        ocr_result = ReceiptOCRData(
            confidence=0.0,
            total_eur=0.0,
            tax_base_eur=0.0,
            quota_iva_eur=0.0,
            iva_pct=21.0,
            vendor_name="PROVEIDOR",
            vendor_nif=None,
            buyer_nif=None,
            date_str=date.today().isoformat(),
            has_mixed_fuel_and_adblue=False,
        )
    else:
        raw_bytes, filename = await SovereignStorageGateway.obtenir_bytes_fitxer(
            db, empresa_id, tiquet.foto_tiquet_path
        )
        ocr_result = await extract_receipt_ocr_data(
            raw_bytes,
            filename=filename or os.path.basename(tiquet.foto_tiquet_path),
            node_ia_url=getattr(empresa, "node_ia_url", None) if empresa else None,
            vault_token=getattr(empresa, "vault_token", None) if empresa else None,
            empresa_nif=getattr(empresa, "nif", None) if empresa else None,
        )

    # RF-17 / EDGE-01: Paper deteriorat o il·legible (<70% confiança)
    if ocr_result.confidence < 0.70:
        tiquet.estat_aprovacio = "INCIDENCIA_COMPROVACIO_MANUAL"
        tiquet.estat_fiscal = "REVISIO_MANUAL"
        db.add(
            Incidencia(
                id=uuid.uuid4(),
                empresa_id=empresa_id,
                operari_id=tiquet.usuari_id,
                vehicle_id=tiquet.vehicle_id,
                ordre_treball_id=tiquet.ordre_treball_id,
                ambit="DESPESA_CAMP",
                tipus="TIQUET_COMPROVACIO_MANUAL",
                gravetat="MITJANA",
                estat="OBERTA",
                foto_path=tiquet.foto_tiquet_path,
                text_observacions=(
                    "El motor d'OCR no ha pogut llegir el tiquet per mal estat del paper. "
                    "Comprovació manual requerida sobre el comprovant físic dipositat al Check-out."
                ),
            )
        )
        await db.commit()
        return {"status": "LOW_CONFIDENCE_MANUAL_REVIEW", "tiquet_id": str(tiquet.id)}

    import_total = Decimal(str(ocr_result.total_eur)).quantize(Decimal("0.01"))
    proveidor_slug = _sanitize_slug(ocr_result.vendor_name)
    data_compacta = ocr_result.date_str.replace("-", "")

    # RF-08: Reanomenament sense col·lisions al disc sobirà
    nom_auditoria = f"{empresa_id}_{tiquet.id}_{proveidor_slug}_{import_total:.2f}EUR_{data_compacta}.webp"
    nom_amigable_pwa = f"{proveidor_slug}_{import_total:.2f}EUR_{data_compacta[-4:]}.webp"

    if tiquet.foto_tiquet_path:
        nova_ruta = await SovereignStorageGateway.reanomenar_fitxer_binari(
            db=db,
            empresa_id=empresa_id,
            old_path=tiquet.foto_tiquet_path,
            new_filename=nom_auditoria,
            categoria="tiquets_despesa",
        )
        tiquet.foto_tiquet_path = nova_ruta

    tiquet.nom_fitxer_visible = nom_amigable_pwa
    tiquet.import_total = float(import_total)
    tiquet.nif_emissor = ocr_result.vendor_nif
    tiquet.nif_comprador = ocr_result.buyer_nif
    tiquet.rao_social = ocr_result.vendor_name
    try:
        tiquet.data_tiquet = date.fromisoformat(ocr_result.date_str)
    except ValueError:
        pass

    # RF-08.1: Repostatge mixt Dièsel + AdBlue
    if tiquet.categoria == "CARBURANT" and ocr_result.has_mixed_fuel_and_adblue:
        tiquet.estat_aprovacio = "PENDENT_DESGLOSE_MANUAL"
        tiquet.estat_fiscal = "PENDENT_DESGLOSE"
        tiquet.base_imposable = float(ocr_result.tax_base_eur or import_total)
        tiquet.quota_iva = float(ocr_result.quota_iva_eur or 0.0)
        await db.commit()
        return {
            "status": "PENDENT_DESGLOSE_MANUAL",
            "tiquet_id": str(tiquet.id),
            "nom_fitxer": nom_amigable_pwa,
        }

    # RF-13 / EDGE-02: Superació del límit diari de 100 EUR
    if import_total > Decimal("100.00"):
        tiquet.estat_aprovacio = "BLOQUEJAT_EXCEDENCIA_100EUR"
        tiquet.estat_fiscal = "BLOQUEJAT"
        tiquet.requereix_aprovacio_boss = True
        if tiquet.vehicle_id:
            veh = (
                await db.execute(
                    select(Vehicle).where(
                        Vehicle.id == tiquet.vehicle_id,
                        Vehicle.empresa_id == empresa_id,
                    )
                )
            ).scalar_one_or_none()
            if veh:
                veh.targeta_combustible_bloquejada = True
        db.add(
            Incidencia(
                id=uuid.uuid4(),
                empresa_id=empresa_id,
                operari_id=tiquet.usuari_id,
                vehicle_id=tiquet.vehicle_id,
                ordre_treball_id=tiquet.ordre_treball_id,
                ambit="DESPESA_CAMP",
                tipus="TIQUET_EXCEDENCIA_LIMIT_100EUR",
                gravetat="ALTA",
                estat="OBERTA",
                foto_path=tiquet.foto_tiquet_path,
                text_observacions=(
                    f"Incidència de Tiquet per Excedència de Límit: {import_total:.2f} € (>100 €). "
                    "Targeta de furgó bloquejada."
                ),
            )
        )
        await db.commit()
        return {
            "status": "BLOQUEJAT_EXCEDENCIA_100EUR",
            "tiquet_id": str(tiquet.id),
            "import": float(import_total),
        }

    # EDGE-08: Tiquet simplificat sense NIF corporatiu comprador -> IVA 0% no deduïble a subcompte 62X
    te_nif_comprador = bool(ocr_result.buyer_nif)
    if not te_nif_comprador:
        tiquet.estat_aprovacio = "PENDENT_DE_CANJE"
        tiquet.estat_fiscal = "PENDENT_BESCANVI"
        base_imp = import_total
        quota_iva = Decimal("0.00")
        tiquet.iva_pct = 0.00
        tiquet.base_imposable = float(base_imp)
        tiquet.quota_iva = 0.00
        subcompte = "62X"
        tiquet.subcompte_pgc = subcompte
        estat_despesa = "PENDENT_DE_CANJE"
    else:
        tiquet.estat_aprovacio = "ARXIVAT_GESTIO"
        tiquet.estat_fiscal = "DEDUIBLE"
        base_imp = Decimal(
            str(ocr_result.tax_base_eur or round(float(import_total) / 1.21, 2))
        ).quantize(Decimal("0.01"))
        quota_iva = (import_total - base_imp).quantize(Decimal("0.01"))
        tiquet.iva_pct = float(ocr_result.iva_pct or 21.0)
        tiquet.base_imposable = float(base_imp)
        tiquet.quota_iva = float(quota_iva)
        subcompte = "602.FERRETERIA_OBRA" if tiquet.categoria == "FERRETERIA" else "629.DESPESA_CAMP"
        tiquet.subcompte_pgc = subcompte
        estat_despesa = "PENDENT_VALIDACIO"

    despesa = DespesaComptable(
        id=uuid.uuid4(),
        empresa_id=empresa_id,
        ordre_treball_id=tiquet.ordre_treball_id,
        tiquet_id=tiquet.id,
        concepte=f"Tiquet {tiquet.categoria} - {ocr_result.vendor_name}",
        subcompte=subcompte,
        base_imposable=float(base_imp),
        quota_iva=float(quota_iva),
        import_total=float(import_total),
        estat=estat_despesa,
        origen="OCR_TIQUET_CAMP",
    )
    db.add(despesa)
    await db.commit()

    return {
        "status": tiquet.estat_aprovacio,
        "tiquet_id": str(tiquet.id),
        "nom_fitxer": nom_amigable_pwa,
        "import_total": float(import_total),
        "despesa_id": str(despesa.id),
    }


@celery_app.task(
    name="app.workers.comptabilitat_tasks.processar_tiquet_ocr_a_gestio_task",
    queue="queue_documents",
)
def processar_tiquet_ocr_a_gestio_task(empresa_id: str, tiquet_id: str) -> dict[str, Any]:
    """Processa en segon pla un tiquet capturat des de PWA (queue_documents)."""
    emp_uuid = uuid.UUID(empresa_id)
    tiq_uuid = uuid.UUID(tiquet_id)

    async def _run(session: AsyncSession) -> dict[str, Any]:
        return await _processar_tiquet_ocr_async(session, emp_uuid, tiq_uuid)

    return cast(dict[str, Any], _run_async_in_worker(_run, empresa_id=empresa_id, is_superadmin=False))


@celery_app.task(
    name="comptabilitat.processar_tiquet_ocr_a_gestio",
    queue="queue_documents",
)
def processar_tiquet_ocr_a_gestio_canonical_task(
    empresa_id: str, tiquet_id: str
) -> dict[str, Any]:
    """Àlies canònic Spec 024 per al processament OCR de tiquets a queue_documents."""
    return cast(dict[str, Any], processar_tiquet_ocr_a_gestio_task(empresa_id, tiquet_id))
