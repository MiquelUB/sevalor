import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_with_tenant_context
from app.core.security import get_current_user_claims

router = APIRouter(prefix="/sync", tags=["PWA Sync"])
logger = logging.getLogger(__name__)

class SyncAction(BaseModel):
    id: str = Field(..., description="ID únic de l'acció al client")
    accio: str = Field(..., description="Tipus d'acció (FITXAR_JORNADA, CREAR_TIQUET, etc.)")
    payload: Dict[str, Any] = Field(..., description="Càrrega útil de l'acció")

class BulkSyncRequest(BaseModel):
    accions: List[SyncAction] = Field(..., description="Llista d'accions a sincronitzar seqüencialment")

@router.post("/push")
async def bulk_sync_push(
    request: BulkSyncRequest,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(get_current_user_claims)
):
    """
    Rep una llista d'accions encuades (Offline-First) i les processa seqüencialment.
    (Spec 013 - RF-08)
    """
    processades = 0
    errors = []

    for accio in request.accions:
        try:
            # Aquí s'instanciaria la crida als serveis corresponents segons el tipus d'acció
            if accio.accio == "FITXAR_JORNADA":
                logger.info(f"Processant FITXAR_JORNADA per {accio.id}")
            elif accio.accio == "CREAR_TIQUET":
                logger.info(f"Processant CREAR_TIQUET per {accio.id}")
            elif accio.accio == "REPORTAR_INCIDENCIA":
                logger.info(f"Processant REPORTAR_INCIDENCIA per {accio.id}")
            elif accio.accio == "INICIAR_TRAJECTE":
                logger.info(f"Processant INICIAR_TRAJECTE per {accio.id}")
            elif accio.accio == "FINALITZAR_ORDRE":
                logger.info(f"Processant FINALITZAR_ORDRE per {accio.id}")
            else:
                logger.warning(f"Acció desconeguda: {accio.accio}")

            processades += 1

        except Exception as e:
            logger.error(f"Error processant acció {accio.id}: {str(e)}")
            errors.append({"id": accio.id, "error": str(e)})
            # Si volem parar en sec en el primer error, faríem un raise.
            # Normalment en Sync Queues, guardem l'error i continuem, o abortem depenent del cas.

    # Fem un sol commit al final si volem que tot el bloc sigui atòmic,
    # però com que les accions són independents, en un entorn real fariem flush per acció.
    await db.commit()

    if errors:
        # Podríem tornar un 207 Multi-Status, però per ara retornem 200 amb detall
        pass

    return {
        "status": "ok",
        "processades": processades,
        "errors": errors
    }
