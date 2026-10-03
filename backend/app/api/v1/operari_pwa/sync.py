import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_with_tenant_context
from app.core.security import get_current_user_claims
from app.models.models import Incidencia, OrdreTreball

router = APIRouter(prefix="/sync", tags=["PWA Sync"])
logger = logging.getLogger(__name__)

class SyncAction(BaseModel):
    id: str = Field(..., description="ID únic de l'acció al client")
    accio: str = Field(..., description="Tipus d'acció (FITXAR_JORNADA, CREAR_TIQUET, etc.)")
    payload: Dict[str, Any] = Field(..., description="Càrrega útil de l'acció")
    timestamp: Optional[int] = Field(None, description="Timestamp de l'acció en client (ms)")

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
    Resol conflictes basant-se en el timestamp de l'acció vs DB (Spec 02 - T007).
    """
    processades = 0
    errors = []

    for accio in request.accions:
        try:
            if accio.accio == "FITXAR_JORNADA":
                logger.info(f"Processant FITXAR_JORNADA per {accio.id}")

            elif accio.accio == "CREAR_TIQUET":
                logger.info(f"Processant CREAR_TIQUET per {accio.id}")

            elif accio.accio == "REPORTAR_INCIDENCIA":
                logger.info(f"Processant REPORTAR_INCIDENCIA per {accio.id}")
                ambit = accio.payload.get("ambit", "GENERAL")
                estat = accio.payload.get("estat", "VERMELL")
                text_obs = accio.payload.get("text_observacions", accio.payload.get("descripcio", ""))
                audio_path = accio.payload.get("audio_path")
                foto_path = accio.payload.get("foto_path")

                nova_incidencia = Incidencia(
                    empresa_id=uuid.UUID(claims["empresa_id"]),
                    operari_id=uuid.UUID(claims["sub"]),
                    ambit=ambit,
                    estat=estat,
                    text_observacions=text_obs,
                    audio_path=audio_path,
                    foto_path=foto_path
                )
                db.add(nova_incidencia)

            elif accio.accio == "FINALITZAR_ORDRE":
                logger.info(f"Processant FINALITZAR_ORDRE per {accio.id}")
                # Exemple de validació de timestamp (CRDT/Conflict Resolution)
                ordre_id = accio.payload.get("ordre_id")
                if ordre_id and accio.timestamp:
                    result = await db.execute(select(OrdreTreball).where(OrdreTreball.id == ordre_id))
                    ordre = result.scalars().first()

                    if ordre:
                        # Convertim el datetime a timestamp (ms)
                        db_ts = int(ordre.updated_at.timestamp() * 1000) if ordre.updated_at else 0
                        if accio.timestamp < db_ts:
                            logger.warning(f"Conflicte detectat per a ordre {ordre_id}. Client ts: {accio.timestamp}, DB ts: {db_ts}")
                            raise HTTPException(status_code=409, detail=f"Conflicte detectat a l'ordre {ordre_id}. DB és més recent.")

            else:
                logger.warning(f"Acció desconeguda: {accio.accio}")

            processades += 1

        except HTTPException as e:
            if e.status_code == 409:
                errors.append({"id": accio.id, "error": e.detail, "status": 409})
            else:
                errors.append({"id": accio.id, "error": str(e), "status": e.status_code})
        except Exception as e:
            logger.error(f"Error processant acció {accio.id}: {str(e)}")
            errors.append({"id": accio.id, "error": str(e), "status": 500})

    await db.commit()

    # Si hi ha conflictes, responem 207 (Multi-Status) o un 200 amb detall
    return {
        "status": "ok",
        "processades": processades,
        "errors": errors
    }

@router.get("/hud")
async def get_hud_stats(
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(get_current_user_claims)
):
    """
    Retorna les estadístiques diàries per al HUD de l'operari.
    (S'executa quan hi ha connectivitat).
    """
    import datetime

    from sqlalchemy import func

    avui = datetime.date.today()
    operari_id_uuid = uuid.UUID(claims["sub"])

    # Ordres de treball per avui assignades a l'operari
    query_ordres = select(OrdreTreball.estat, func.count(OrdreTreball.id)).where(
        OrdreTreball.cap_de_colla_id == operari_id_uuid,
        OrdreTreball.data_planificacio == avui
    ).group_by(OrdreTreball.estat)

    result_ordres = await db.execute(query_ordres)
    ordres = result_ordres.all()

    ordres_pendents = sum(count for estat, count in ordres if estat == "PENDENT")
    ordres_completades = sum(count for estat, count in ordres if estat == "COMPLETADA")

    # Incidències creades avui per l'operari
    query_inc = select(func.count(Incidencia.id)).where(
        Incidencia.operari_id == operari_id_uuid,
        func.date(Incidencia.created_at) == avui
    )

    result_inc = await db.execute(query_inc)
    incidencies_avui = result_inc.scalar() or 0

    return {
        "ordres_pendents": ordres_pendents,
        "ordres_completades": ordres_completades,
        "incidencies_avui": incidencies_avui,
        "data": avui.isoformat()
    }
