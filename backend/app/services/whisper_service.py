import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger("whisper_service")

class WhisperTranscriptionError(Exception):
    pass

async def transcriure_audio(
    audio_path: str,
    language: Optional[str] = None,
    model_size: str = "base",
    device: str = "cpu",
    compute_type: str = "int8",
) -> dict:
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
                    "http://127.0.0.1:8000/v1/audio/transcriptions",
                    files=files,
                    data=data
                )

                response.raise_for_status()
                result = response.json()
                segments = result.get("segments", [])

                return {
                    "status": "SUCCESS",
                    "text": result.get("text", ""),
                    "language": language or "ca",
                    "confianca_acustica": _confianca_des_de_segments(segments),
                    "segments": segments
                }
    except (httpx.RequestError, httpx.HTTPStatusError) as e:
        logger.warning(f"Error connectant al node d'IA Whisper, s'activa fallback: {e}")
        return {
            "status": "REVISIO_MANUAL",
            "text": "Copilot provisionalment no disponible",
            "language": language or "ca",
            "confianca_acustica": 0.0,
            "segments": []
        }
    except Exception as e:
        logger.error(f"Error a whisper: {e}")
        return {
            "status": "REVISIO_MANUAL",
            "text": "Copilot provisionalment no disponible",
            "language": language or "ca",
            "confianca_acustica": 0.0,
            "segments": []
        }


def _confianca_des_de_segments(segments: list) -> float:
    """Confiança acústica real: mitjana de exp(avg_logprob) dels segments (0.0 si no n'hi ha)."""
    import math

    valors = [
        math.exp(s["avg_logprob"])
        for s in segments
        if isinstance(s, dict) and isinstance(s.get("avg_logprob"), (int, float))
    ]
    if not valors:
        return 0.0
    return round(min(1.0, max(0.0, sum(valors) / len(valors))), 4)
