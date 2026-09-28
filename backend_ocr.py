import re

path = "backend/app/api/v1/gestio/flota.py"
with open(path, "r") as f:
    text = f.read()

new_endpoint = """
@router.post("/ocr-draft")
async def ocr_vehicle_draft(
    request: Request,
    file: UploadFile = File(...),
    tenant: dict = Depends(valida_uuid)
):
    \"\"\"
    (RF-00 Alta Màgica OCR) Simula el processament de la Fitxa Tècnica / Permís de Circulació / Pòlissa
    per extreure estructuradament les dades i fer un "Zero Data Entry".
    \"\"\"
    empresa_id = request.state.empresa_id
    if not empresa_id: raise HTTPException(status_code=401)
    
    # Simulem que la IA llegeix el fitxer (podria ser un PDF, JPG...)
    # Retornem un esborrany JSON compatible amb el frontend de Flota
    # Normalment cridaríem de forma asíncrona a GPT-4V o a la llibreria local LLaVA/Tesseract
    
    nom_arxiu = file.filename.lower()
    
    # Mock bàsic segons el nom del fitxer (o genèric)
    matricula = "0000XXX"
    marca = "Marca Detectada"
    model = "Model OCR"
    
    if "renault" in nom_arxiu or "kangoo" in nom_arxiu:
        matricula = "2468KNG"
        marca = "Renault"
        model = "Kangoo Z.E."
    elif "toyota" in nom_arxiu:
        matricula = "1357TYT"
        marca = "Toyota"
        model = "Proace"
        
    return {
        "matricula": matricula,
        "marca": marca,
        "model": model,
        "tipus": "EV",
        "distintiu_ambiental": "ZERO",
        "places": 2,
        "pes_maxim_autoritzat": 2000,
        "regim_adquisicio": "RENTING",
        "renting_limit_km": 80000,
        "companyia_asseguradora": "Mapfre",
        "polissa_asseguranca": f"POL-OCR-{matricula}",
        "carnet_necessari": "B"
    }
"""

with open(path, "a") as f:
    f.write(new_endpoint)

print("OCR endpoint added to flota")
