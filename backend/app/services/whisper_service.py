"""
Servei de Transcripció d'Àudio Local (Whisper INT8 / HTTP Whisper Node).
Inclou inferència local faster-whisper CPU INT8 amb monitorització de CPU >90%
i persistència d'alertes a superadmin_telemetry.alertes_seguretat (Spec 022 / 024).
"""

import logging
import math
import os
import time
from typing import Any, Optional
from uuid import uuid4

import httpx
import psutil
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import AlertaSeguretat

logger = logging.getLogger("whisper_service")

_WHISPER_MODEL: Any = None


class WhisperTranscriptionError(Exception):
    pass


def get_local_int8_whisper_model() -> Any:
    """Retorna la instància singleton del model faster-whisper INT8 (CPU-only)."""
    global _WHISPER_MODEL
    if _WHISPER_MODEL is None:
        from faster_whisper import WhisperModel  # type: ignore[import-not-found]

        # Spec 022 RF-10 / Spec 024 Tasca 5.1: CPU-only amb quantificació INT8
        _WHISPER_MODEL = WhisperModel("small", device="cpu", compute_type="int8", cpu_threads=4)
    return _WHISPER_MODEL


async def transcribe_field_audio_local_int8(
    audio_path: str,
    db: AsyncSession | None = None,
    *,
    cpu_percent_override: float | None = None,
) -> dict[str, Any]:
    """Transcriu àudio en local amb faster-whisper INT8 i registra alerta si CPU > 90%."""
    start_ts = time.perf_counter()
    cpu_pct = (
        float(cpu_percent_override)
        if cpu_percent_override is not None
        else float(psutil.cpu_percent(interval=0.1))
    )

    if cpu_pct > 90.0 and db is not None:
        db.add(
            AlertaSeguretat(
                id=uuid4(),
                tipus="SATURACIO_CPU_WHISPER_INT8",
                gravetat="GROGA",
                origen="whisper_service",
                detall=(
                    f"Ús de CPU al {cpu_pct:.1f}% (>90%) durant la inferència local "
                    "faster-whisper INT8."
                ),
            )
        )
        await db.commit()

    model = get_local_int8_whisper_model()
    segments, info = model.transcribe(audio_path, beam_size=3, language="ca", vad_filter=True)
    text = " ".join(seg.text.strip() for seg in segments).strip()
    latency_ms = int((time.perf_counter() - start_ts) * 1000)

    return {
        "text": text,
        "language": getattr(info, "language", "ca"),
        "latency_ms": latency_ms,
        "quantization": "INT8_LOCAL_CPU",
        "cpu_percent": cpu_pct,
    }


async def transcriure_audio(
    audio_path: str,
    language: Optional[str] = None,
    model_size: str = "base",
    device: str = "cpu",
    compute_type: str = "int8",
) -> dict[str, Any]:
    if not audio_path or not isinstance(audio_path, str):
        return {"status": "ERROR", "error": "audio_path no vàlid"}

    if not os.path.isfile(audio_path):
        return {"status": "ERROR", "error": "L'arxiu no existeix físicament a disc"}

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            with open(audio_path, "rb") as f:
                files = {"file": (os.path.basename(audio_path), f, "audio/webm")}
                data = {"model": "whisper-1", "response_format": "verbose_json"}
                if language:
                    data["language"] = language

                response = await client.post(
                    "http://127.0.0.1:8000/v1/audio/transcriptions", files=files, data=data
                )

                response.raise_for_status()
                result = response.json()
                segments = result.get("segments", [])

                return {
                    "status": "SUCCESS",
                    "text": result.get("text", ""),
                    "language": language or "ca",
                    "confianca_acustica": _confianca_des_de_segments(segments),
                    "segments": segments,
                }
    except (httpx.RequestError, httpx.HTTPStatusError) as e:
        logger.warning(f"Error connectant al node d'IA Whisper, s'activa fallback: {e}")
        return {
            "status": "REVISIO_MANUAL",
            "text": "Copilot provisionalment no disponible",
            "language": language or "ca",
            "confianca_acustica": 0.0,
            "segments": [],
        }
    except Exception as e:
        logger.error(f"Error a whisper: {e}")
        return {
            "status": "REVISIO_MANUAL",
            "text": "Copilot provisionalment no disponible",
            "language": language or "ca",
            "confianca_acustica": 0.0,
            "segments": [],
        }


def _confianca_des_de_segments(segments: list[Any]) -> float:
    """Confiança acústica real: mitjana de exp(avg_logprob) dels segments (0.0 si no n'hi ha)."""
    valors = [
        math.exp(s["avg_logprob"])
        for s in segments
        if isinstance(s, dict) and isinstance(s.get("avg_logprob"), (int, float))
    ]
    if not valors:
        return 0.0
    return round(min(1.0, max(0.0, sum(valors) / len(valors))), 4)
