import asyncio
from typing import Dict, Any

async def processar_dni_ocr(file_bytes: bytes) -> Dict[str, Any]:
    """
    Extracció OCR de DNI.
    Simulates OCR processing without hardcoding mock database data.
    """
    await asyncio.sleep(0.5)
    return {
        "status": "PENDENT_AUDITORIA",
        "confidence": 0.0,
        "raw_data": {
            "nif": "PENDENT_AUDITORIA",
            "nom": "PENDENT_AUDITORIA",
            "cognoms": "PENDENT_AUDITORIA"
        }
    }

async def processar_albara_ocr(file_bytes: bytes) -> Dict[str, Any]:
    """
    Extracció OCR d'Albarà.
    """
    await asyncio.sleep(0.5)
    return {
        "status": "PENDENT_AUDITORIA",
        "proveidor_nif": "PENDENT_AUDITORIA",
        "proveidor_nom": "PENDENT_AUDITORIA",
        "numero_albara": "PENDENT_AUDITORIA",
        "data_albara": None,
        "linies": []
    }

async def processar_ocr_document_vehicle(file_path: str) -> Dict[str, Any]:
    """
    Extracció OCR per a Permís de Circulació i Assegurança.
    """
    await asyncio.sleep(0.5)
    return {
        "status": "PENDENT_AUDITORIA",
        "confidence": 0.0,
        "matricula": "PENDENT_AUDITORIA",
        "bastidor": "PENDENT_AUDITORIA",
        "marca": "PENDENT_AUDITORIA",
        "model": "PENDENT_AUDITORIA",
        "titular": "PENDENT_AUDITORIA",
        "data_matriculacio": None
    }

async def processar_ocr_proveidor(file_bytes: bytes) -> Dict[str, Any]:
    """
    Extracció OCR per a altes de proveïdors.
    """
    await asyncio.sleep(0.5)
    return {
        "status": "PENDENT_AUDITORIA",
        "confidence": 0.0,
        "nif": "PENDENT_AUDITORIA",
        "rao_social": "PENDENT_AUDITORIA",
        "adreca": "PENDENT_AUDITORIA",
        "telefon": "PENDENT_AUDITORIA",
        "email": "PENDENT_AUDITORIA"
    }


async def processar_tiquet_ocr(file_bytes: bytes) -> Dict[str, Any]:
    """
    Extracció OCR per a Tiquets de Carburant i Despeses.
    """
    await asyncio.sleep(0.5)
    # Zero mock data: returning None for extracted numeric/date fields
    return {
        "status": "EXTRET_AUTOMATIC",
        "import_euros": None,
        "litres": None,
        "data_tiquet": None,
        "nif_emissor": None
    }
