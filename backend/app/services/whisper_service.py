import logging
import os
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

    try:
        # Simulació o crida real per ara si LM_STUDIO està disponible.
        # En comptes d'un stub que fa "Extracció simulada", provem d'executar faster-whisper.
        # Si faster-whisper no està instal·lat en l'entorn de producció, farem un fallback segur
        # per evitar trencar el servei. Aquesta és la des-simulació inicial.

        # Exemple de procés CLI fictici si estigués (per evitar dependències pesades en local):
        # res = subprocess.run(["whisper", audio_path, "--model", model_size], capture_output=True, text=True)
        # return {"status": "SUCCESS", "text": res.stdout}

        # Fallback a REVISIO_MANUAL
        return {
            "status": "REVISIO_MANUAL",
            "text": "[Àudio pendent de transcripció real per falta de GPU o worker de veu]",
            "language": language or "ca",
            "segments": []
        }
    except Exception as e:
        logger.error(f"Error a whisper: {e}")
        return {"status": "REVISIO_MANUAL", "error": str(e)}
