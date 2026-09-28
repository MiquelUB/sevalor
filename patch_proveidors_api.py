import re

path = "backend/app/api/v1/gestio/proveidors.py"
with open(path, "r") as f:
    text = f.read()

imports = """
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status, UploadFile, File
"""
text = text.replace("from fastapi import APIRouter, Depends, HTTPException, Query, Request, status", imports)


new_endpoint = """
@router.post("/ocr-draft")
async def ocr_proveidor_draft(
    request: Request,
    file: UploadFile = File(...)
):
    \"\"\"
    (RF-00 Alta Màgica OCR) Simula el processament d'una targeta CIF o factura proforma
    per extreure estructuradament les dades del Proveïdor i fer un "Zero Data Entry".
    \"\"\"
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == 'undefined':
        raise HTTPException(status_code=401)
    
    # Simulem que la IA llegeix el fitxer (podria ser un PDF o JPG)
    # i retorna un JSON compatible amb el frontend de Proveïdors
    
    nom_arxiu = file.filename.lower()
    
    nif = "B00000000"
    rao_social = "Proveïdor OCR S.L."
    email = "contacte@ocr.com"
    telefon = "900000000"
    iban = "ES0000000000000000000000"
    
    if "saltoki" in nom_arxiu:
        nif = "B31688534"
        rao_social = "Saltoki S.A."
        email = "info@saltoki.com"
        telefon = "934000000"
    elif "rexel" in nom_arxiu:
        nif = "B82000000"
        rao_social = "Rexel S.L."
        email = "facturacio@rexel.es"
        telefon = "910000000"
        
    return {
        "nif": nif,
        "rao_social": rao_social,
        "email": email,
        "telefon": telefon,
        "iban": iban,
        "especialitat": "General"
    }
"""

with open(path, "a") as f:
    f.write(new_endpoint)

print("OCR endpoint added to proveidors")
