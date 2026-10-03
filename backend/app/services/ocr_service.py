from typing import Any, Dict

from fastapi import HTTPException


async def processar_dni_ocr(file_bytes: bytes) -> Dict[str, Any]:
    """
    Extracció OCR de DNI.
    """
    raise HTTPException(status_code=501, detail="Servei OCR per a DNI no implementat encara.")

async def processar_albara_ocr(file_bytes: bytes) -> Dict[str, Any]:
    """
    Extracció OCR d'Albarà.
    """
    raise HTTPException(status_code=501, detail="Servei OCR per a albarans no implementat encara.")

async def processar_ocr_document_vehicle(file_path: str) -> Dict[str, Any]:
    """
    Extracció OCR per a Permís de Circulació i Assegurança.
    """
    raise HTTPException(status_code=501, detail="Servei OCR de vehicles no implementat encara.")

async def processar_ocr_proveidor(file_bytes: bytes) -> Dict[str, Any]:
    """
    Extracció OCR per a altes de proveïdors.
    """
    raise HTTPException(status_code=501, detail="Servei OCR de proveïdors no implementat encara.")

async def processar_tiquet_ocr(file_bytes: bytes) -> Dict[str, Any]:
    """
    Extracció OCR per a Tiquets de Carburant i Despeses.
    """
    raise HTTPException(status_code=501, detail="Servei OCR per a tiquets no implementat encara.")
