"""
Servei de transcripció d'àudio mitjançant IA local (Whisper CPU INT8).

Implementa Spec 024 RF-14, RF-15:
- Transcripció d'àudios de camp amb faster-whisper (CPU-only INT8 per Hetzner CPX21).
- Zero Mock Data: si no es pot transcriure, es retorna un error i es marca com a REVISIO_MANUAL.
- La implementació real es farà amb faster-whisper quan el servei estigui disponible.

Actualment: stub que retorna un placeholder per a integració futura.
"""

import logging
from typing import Optional

logger = logging.getLogger("whisper_service")


class WhisperTranscriptionError(Exception):
    """Excepció per errors de transcripció d'àudio."""
    pass


async def transcriure_audio(
    audio_path: str,
    language: Optional[str] = None,
    model_size: str = "base",
    device: str = "cpu",
    compute_type: str = "int8",
) -> dict:
    """
    Transcrueix un fitxer d'àudio utilitzant Whisper (CPU INT8).

    Args:
        audio_path: Ruta absoluta al fitxer d'àudio.
        language: Codi d'idioma (ca, es, en). None per detecció automàtica.
        model_size: Mida del model Whisper (tiny, base, small, medium, large).
        device: Dispositiu d'inferència (cpu).
        compute_type: Tipus de càlcul (int8 per CPU).

    Returns:
        dict amb: text, segments, language, duration, status
    """
    if not audio_path or not isinstance(audio_path, str):
        return {
            "status": "ERROR",
            "error": "audio_path no vàlid",
        }

    import os
    if not os.path.isfile(audio_path):
        return {
            "status": "ERROR",
            "error": f"Fitxer no trobat: {audio_path}",
        }

    # >>> IMPLEMENTACIÓ PENDENT <<<
    # Quan el servei faster-whisper estigui desplegat al contenidor,
    # aquí es farà la càrrega del model i la transcripció real.
    #
    # from faster_whisper import WhisperModel
    # model = WhisperModel(model_size, device=device, compute_type=compute_type)
    # segments, info = model.transcribe(audio_path, language=language)
    # text = "".join(seg.text for seg in segments)

    logger.warning(
        "Whisper stub: transcripció no implementada. "
        "Cal desplegar faster-whisper al contenidor celery_worker. "
        "Audio: %s", audio_path
    )

    return {
        "status": "STUB",
        "text": "[Transcripció no disponible: servei Whisper no desplegat]",
        "language": language or "desconegut",
        "duration": 0.0,
        "error": "Stub: faster-whisper no disponible",
    }


# Alias per compatibilitat amb tests existents
transcriure_audio_local = transcriure_audio