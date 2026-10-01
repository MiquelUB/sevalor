import logging
import os
import httpx
from typing import Optional

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

    # Simulació de confiança acústica basada en la mida de l'arxiu (dummy per spec)
    mida_arxiu = os.path.getsize(audio_path)
    confianca_acustica = min(0.99, max(0.50, mida_arxiu / 1000000.0))

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            with open(audio_path, "rb") as f:
                files = {"file": (os.path.basename(audio_path), f, "audio/webm")}
                data = {"model": "whisper-1"}
                if language:
                    data["language"] = language
                
                # Mock connection to local Whisper node
                response = await client.post(
                    "http://127.0.0.1:8000/v1/audio/transcriptions",
                    files=files,
                    data=data
                )
                
                response.raise_for_status()
                result = response.json()
                
                return {
                    "status": "SUCCESS",
                    "text": result.get("text", ""),
                    "language": language or "ca",
                    "confianca_acustica": confianca_acustica,
                    "segments": result.get("segments", [])
                }
    except (httpx.RequestError, httpx.HTTPStatusError) as e:
        logger.warning(f"Error connectant al node d'IA Whisper, s'activa fallback: {e}")
        return {
            "status": "REVISIO_MANUAL",
            "text": "Copilot provisionalment no disponible",
            "language": language or "ca",
            "confianca_acustica": confianca_acustica,
            "segments": []
        }
    except Exception as e:
        logger.error(f"Error a whisper: {e}")
        return {
            "status": "REVISIO_MANUAL",
            "text": "Copilot provisionalment no disponible",
            "language": language or "ca",
            "confianca_acustica": confianca_acustica,
            "segments": []
        }
