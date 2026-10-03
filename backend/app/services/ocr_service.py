"""Serveis OCR.

Cap motor OCR està connectat encara. Per complir Zero Mock Data, aquestes
funcions NO inventen valors: retornen tots els camps a ``None`` i l'estat
``PENDENT_REVISIO_MANUAL`` perquè una persona introdueixi les dades.
"""

from typing import Any, Dict

ESTAT_REVISIO_MANUAL = "PENDENT_REVISIO_MANUAL"


async def processar_dni_ocr(file_bytes: bytes) -> Dict[str, Any]:
    """Extracció OCR de DNI (sense motor: revisió manual)."""
    return {
        "status": ESTAT_REVISIO_MANUAL,
        "confidence": 0.0,
        "raw_data": {"nif": None, "nom": None, "cognoms": None},
    }


async def processar_albara_ocr(file_bytes: bytes) -> Dict[str, Any]:
    """Extracció OCR d'Albarà (sense motor: revisió manual)."""
    return {
        "status": ESTAT_REVISIO_MANUAL,
        "proveidor_nif": None,
        "proveidor_nom": None,
        "numero_albara": None,
        "data_albara": None,
        "linies": [],
    }


async def processar_ocr_document_vehicle(file_path: str) -> Dict[str, Any]:
    """Extracció OCR de Permís de Circulació / Assegurança (revisió manual)."""
    return {
        "status": ESTAT_REVISIO_MANUAL,
        "confidence": 0.0,
        "matricula": None,
        "bastidor": None,
        "marca": None,
        "model": None,
        "titular": None,
        "data_matriculacio": None,
    }


async def processar_ocr_proveidor(file_bytes: bytes) -> Dict[str, Any]:
    """Extracció OCR per a altes de proveïdors (revisió manual)."""
    return {
        "status": ESTAT_REVISIO_MANUAL,
        "confidence": 0.0,
        "nif": None,
        "rao_social": None,
        "adreca": None,
        "telefon": None,
        "email": None,
    }


async def processar_tiquet_ocr(file_bytes: bytes) -> Dict[str, Any]:
    """Extracció OCR de tiquets de carburant (revisió manual)."""
    return {
        "status": ESTAT_REVISIO_MANUAL,
        "import_euros": None,
        "litres": None,
        "data_tiquet": None,
        "nif_emissor": None,
    }
