import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_with_tenant_context
from app.core.security import require_roles
from app.models.models import Incidencia

router = APIRouter(
    prefix="/operari",
    tags=["Operari Incidències"],
    dependencies=[Depends(require_roles(["OPERARI", "CAPATAZ", "CAP_DE_COLLA"]))],
)

class IncidenciaCreate(BaseModel):
    ordre_treball_id: Optional[uuid.UUID] = None
    vehicle_id: Optional[uuid.UUID] = None
    ambit: str = Field("TASCA", max_length=30)
    estat: str = Field("VERMELL", max_length=20)
    audio_path: Optional[str] = None
    foto_path: Optional[str] = None
    text_observacions: Optional[str] = None

class IncidenciaResponse(IncidenciaCreate):
    id: uuid.UUID
    operari_id: Optional[uuid.UUID]

@router.get("/incidencies", response_model=List[IncidenciaResponse])
async def llistar_incidencies_operari(
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = request.state.empresa_id
    if not empresa_id:
        raise HTTPException(status_code=401)

    auth_header = request.headers.get("Authorization")
    token = auth_header.split(" ")[1]
    import jwt

    from app.core.config import settings
    decoded = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM], options={"verify_aud": False})
    usuari_id = decoded.get("sub")


    stmt = select(Incidencia).where(
        Incidencia.empresa_id == uuid.UUID(empresa_id),
        Incidencia.operari_id == uuid.UUID(usuari_id)
    ).order_by(Incidencia.created_at.desc())

    result = await db.execute(stmt)
    return result.scalars().all()

from fastapi import UploadFile, File, Form
import os

@router.post("/incidencies", response_model=IncidenciaResponse, status_code=status.HTTP_201_CREATED)
async def reportar_incidencia(
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = request.state.empresa_id
    if not empresa_id:
        raise HTTPException(status_code=401)

    auth_header = request.headers.get("Authorization")
    token = auth_header.split(" ")[1]
    import jwt

    from app.core.config import settings
    decoded = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM], options={"verify_aud": False})
    usuari_id = decoded.get("sub")

    content_type = request.headers.get("content-type", "")

    ordre_treball_id = None
    vehicle_id = None
    ambit = "TASCA"
    estat = "VERMELL"
    text_observacions = None
    audio_path = None
    foto_path = None

    if "application/json" in content_type:
        body = await request.json()
        payload = IncidenciaCreate(**body)
        ordre_treball_id = payload.ordre_treball_id
        vehicle_id = payload.vehicle_id
        ambit = payload.ambit
        estat = payload.estat
        text_observacions = payload.text_observacions
        audio_path = payload.audio_path
        foto_path = payload.foto_path
    else:
        form = await request.form()
        ot_id_str = form.get("ordre_treball_id")
        if ot_id_str:
            try:
                ordre_treball_id = uuid.UUID(str(ot_id_str))
            except ValueError:
                ordre_treball_id = None
        veh_id_str = form.get("vehicle_id")
        if veh_id_str:
            try:
                vehicle_id = uuid.UUID(str(veh_id_str))
            except ValueError:
                vehicle_id = None
        ambit = str(form.get("ambit", "TASCA"))
        estat = str(form.get("estat", "VERMELL"))
        obs = form.get("text_observacions")
        if obs:
            text_observacions = str(obs)

        base_dir = f"/tmp/data/{empresa_id}/incidencies"
        os.makedirs(base_dir, exist_ok=True)

        audio_file = form.get("audio")
        if audio_file and hasattr(audio_file, "read"):
            filename = getattr(audio_file, "filename", "audio.webm")
            audio_path = f"{base_dir}/{uuid.uuid4()}_{filename}"
            content = await audio_file.read()
            with open(audio_path, "wb") as f:
                f.write(content)

        foto_file = form.get("foto")
        if foto_file and hasattr(foto_file, "read"):
            filename = getattr(foto_file, "filename", "foto.webp")
            foto_path = f"{base_dir}/{uuid.uuid4()}_{filename}"
            content = await foto_file.read()
            with open(foto_path, "wb") as f:
                f.write(content)

    nova_inci = Incidencia(
        empresa_id=uuid.UUID(empresa_id),
        ordre_treball_id=ordre_treball_id,
        vehicle_id=vehicle_id,
        operari_id=uuid.UUID(usuari_id),
        ambit=ambit,
        estat=estat,
        audio_path=audio_path,
        foto_path=foto_path,
        text_observacions=text_observacions
    )

    db.add(nova_inci)
    await db.commit()

    # Disparar transcripció i avaluació (Fase 3 Copilot)
    if audio_path:
        from app.workers.celery_app import celery_app
        celery_app.send_task(
            "app.workers.tasks.transcriure_audio_task",
            args=[audio_path, empresa_id],
            queue="queue_media"
        )

    return nova_inci
