import os
import shutil
import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_with_tenant_context
from app.core.security import get_current_user_claims, require_roles
from app.services.memorandum_service import generar_memorandum_tecnic
from app.services.whisper_service import transcriure_audio

router = APIRouter(
    prefix="/gestio/copilot",
    tags=["Copilot IA RAG"],
    dependencies=[Depends(require_roles(["BOSS", "SECRETARIA", "ENGINYER"]))],
)


class RagQueryIn(BaseModel):
    prompt: str = Field(..., description="La consulta per al model")


class RagQueryOut(BaseModel):
    resposta: str
    fonts: list[str] = []


MAX_PROMPT_CHARS = 2000


def sanititzar_prompt(text: str) -> str:
    """Elimina caràcters de control i limita la longitud (anti prompt-injection, AGENTS §3.5)."""
    net = "".join(ch for ch in text if ch in ("\n", "\t") or ord(ch) >= 32)
    return net.strip()[:MAX_PROMPT_CHARS]


@router.post("/rag", response_model=RagQueryOut, status_code=status.HTTP_200_OK)
async def consultar_ia_rag(
    dades: RagQueryIn,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(get_current_user_claims),
) -> RagQueryOut:
    """Consulta el LLM local (LM Studio). Si el node d'IA no respon, retorna 503 (mai text inventat)."""
    from app.api.v1.gestio.copilot import cridar_lm_studio

    pregunta = sanititzar_prompt(dades.prompt)
    if not pregunta:
        raise HTTPException(status_code=422, detail="Consulta buida")

    resposta = await cridar_lm_studio(pregunta=pregunta)
    if not resposta:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Node d'IA local no disponible",
        )
    return RagQueryOut(resposta=resposta, fonts=[])


class PeritatgeOut(BaseModel):
    id: uuid.UUID
    estat: str
    dictamen_pericial: str
    transcripcio_audio: str
    confianca_acustica: float


def verificar_magic_bytes(file_path: str, tipus: str) -> bool:
    with open(file_path, "rb") as f:
        capcalera = f.read(8)
    if tipus == "audio":
        return (
            capcalera.startswith(b"\x1a\x45\xdf\xa3")
            or capcalera.startswith(b"OggS")
            or capcalera.startswith(b"RIFF")
            or capcalera.startswith(b"ID3")
            or capcalera.startswith(b"\xff\xfb")
        )
    elif tipus == "imatge":
        return capcalera.startswith(b"\xff\xd8\xff") or capcalera.startswith(b"\x89PNG\r\n\x1a\n")
    return False


@router.post(
    "/incidencies/peritatge", response_model=PeritatgeOut, status_code=status.HTTP_201_CREATED
)
async def peritatge_incidencies(
    request: Request,
    audio: UploadFile = File(...),
    foto: Optional[UploadFile] = File(None),
    incidencia_id: Optional[str] = Form(None),
    ordre_treball_id: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    claims = get_current_user_claims(request)
    empresa_id = uuid.UUID(claims["empresa_id"])

    if not audio.filename:
        raise HTTPException(status_code=400, detail="Audio file required")

    audio_filename = f"{uuid.uuid4()}.webm"
    audio_path = f"/tmp/{audio_filename}"

    try:
        with open(audio_path, "wb") as f:
            shutil.copyfileobj(audio.file, f)

        if not verificar_magic_bytes(audio_path, "audio"):
            raise HTTPException(status_code=400, detail="Format d'àudio no vàlid")

        foto_path = None
        if foto and foto.filename:
            foto_filename = f"{uuid.uuid4()}.jpg"
            foto_path = f"/tmp/{foto_filename}"
            with open(foto_path, "wb") as f:
                shutil.copyfileobj(foto.file, f)
            if not verificar_magic_bytes(foto_path, "imatge"):
                raise HTTPException(status_code=400, detail="Format d'imatge no vàlid")

        # Transcriure àudio
        transcripcio_result = await transcriure_audio(audio_path=audio_path)
        transcripcio_text = transcripcio_result.get("text", "")
        confianca = float(transcripcio_result.get("confianca_acustica", 0.0))

        # Generar memorandum
        memo = await generar_memorandum_tecnic(
            db=db,
            empresa_id=empresa_id,
            incidencia_id=uuid.UUID(incidencia_id) if incidencia_id else None,
            ordre_treball_id=uuid.UUID(ordre_treball_id) if ordre_treball_id else None,
            transcripcio=transcripcio_text,
            confianca_acustica=confianca,
            foto_path=foto_path,
        )

        return PeritatgeOut(
            id=memo.id,
            estat=memo.estat,
            dictamen_pericial=memo.dictamen_pericial,
            transcripcio_audio=memo.transcripcio_audio or "",
            confianca_acustica=float(memo.confianca_acustica),
        )
    finally:
        if os.path.exists(audio_path):
            os.remove(audio_path)
        if foto_path and os.path.exists(foto_path):
            os.remove(foto_path)
