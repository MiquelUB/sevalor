"""
Servei de Transcripció d'Àudio Local (Whisper INT8 / HTTP Whisper Node).
Inclou inferència local faster-whisper CPU INT8 amb monitorització de CPU >90%
i persistència d'alertes a superadmin_telemetry.alertes_seguretat (Spec 022 / 024).
"""

import logging
import os
import time
from typing import Any, Optional
from uuid import uuid4

import httpx
import psutil
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.models import AlertaSeguretat

logger = logging.getLogger("whisper_service")

_WHISPER_MODEL: Any = None


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
    """Transcriu un arxiu d'àudio delegant-lo al servidor Whisper local si existeix."""
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"L'arxiu d'àudio no existeix a {audio_path}")

    whisper_url = f"{settings.WHISPER_URL.rstrip('/')}/transcribe"
    start_ts = time.time()

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            with open(audio_path, "rb") as f:
                files = {"file": (os.path.basename(audio_path), f, "audio/webm")}
                data = {"language": language or "auto", "model": model_size}
                response = await client.post(whisper_url, files=files, data=data)

            if response.status_code == 200:
                res_json = response.json()
                text_clean = res_json.get("text", "").strip()
                idioma = res_json.get("language", language or "ca")
                confianca = float(res_json.get("confianca", 0.90))
                durada = float(res_json.get("duration", 0.0))

                logger.info(
                    f"Àudio transcrit via API Whisper local ({idioma}) en {time.time() - start_ts:.2f}s"
                )
                return {
                    "text": text_clean,
                    "idioma_detectat": idioma,
                    "confianca_estimada": round(confianca, 2),
                    "durada_segons": round(durada, 1),
                    "temps_proces_segons": round(time.time() - start_ts, 2),
                    "estat": "TRANSCRIT",
                }
            else:
                logger.warning(f"API Whisper retornà HTTP {response.status_code}")

    except Exception as e:
        logger.warning(f"Node Whisper local ({whisper_url}) inaccesible ({e}). Retornant buit.")

    # Si no hi ha node Whisper actiu, retornem estat sense transcripció (Zero Mock)
    return {
        "text": "",
        "idioma_detectat": language or "ca",
        "confianca_estimada": 0.0,
        "durada_segons": 0.0,
        "temps_proces_segons": round(time.time() - start_ts, 2),
        "estat": "SENSE_NODE_WHISPER",
    }


def _confianca_des_de_segments(segments: list[Any]) -> float:
    """Calcula una confiança aproximada a partir d'avg_logprob."""
    if not segments:
        return 0.0
    avg_logprobs = [getattr(s, "avg_logprob", -0.5) for s in segments]
    mean_lp = sum(avg_logprobs) / len(avg_logprobs)
    confianca = max(0.0, min(1.0, 1.0 + (mean_lp / 2.0)))
    return float(confianca)
