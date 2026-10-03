import asyncio
import logging

from sqlalchemy import select

from app.core.celery_app import celery_app
from app.core.database import get_worker_session
from app.models.contractes import ContracteManteniment
from app.models.models import Empresa
from app.services.contractes_service import generar_ordres_preventives_per_contracte

logger = logging.getLogger(__name__)


@celery_app.task(name="app.workers.tasks.revisar_contractes_manteniment", queue="queue_periodic")
def revisar_contractes_manteniment():
    """T006: Revisa els contractes de manteniment i genera les ordres de treball preventives."""

    async def process():
        async with get_worker_session() as session:
            result = await session.execute(select(Empresa.id))
            empreses_ids = result.scalars().all()

        for emp_id in empreses_ids:
            try:
                empresa_id_str = str(emp_id)
                async with get_worker_session(empresa_id_str) as session:
                    stmt = select(ContracteManteniment).where(ContracteManteniment.estat == "ACTIU")
                    res = await session.execute(stmt)
                    contractes = res.scalars().all()

                    for contracte in contractes:
                        noves_ots = await generar_ordres_preventives_per_contracte(
                            contracte, session
                        )
                        if noves_ots:
                            logger.info(
                                f"Generades {len(noves_ots)} OTs preventives pel contracte {contracte.numero_contracte} de l'empresa {empresa_id_str}"
                            )
            except Exception as e:
                logger.error(f"Error generant OTs preventives per l'empresa {emp_id}: {e}")

    asyncio.run(process())
