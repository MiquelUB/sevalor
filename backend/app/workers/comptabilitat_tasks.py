"""Tasques Celery periòdiques de la Suite Econòmica i Comptabilitat (Spec 007 v5.0)."""

import asyncio
import logging
import uuid
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import (
    Client,
    Empresa,
    FacturaCapcalera,
    RetencioGarantia,
)
from app.services.economic_suite_service import EconomicSuiteService
from app.workers.celery_app import celery_app
from app.workers.tasks import get_worker_session

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
