import re

with open("backend/app/api/v1/gestio/magatzem.py", "r") as f:
    content = f.read()

old_ocr_func = r'@router\.post\("/albara/ocr", response_model=dict, status_code=status\.HTTP_200_OK\)\nasync def processar_document_ocr\(\n    request: Request,\n    fitxer: UploadFile = File\(\.\.\)\n\):\n    """Processa un document PDF o imatge via OCR d\'IA per extreure dades d\'albarà o factura\."""\n    empresa_id = request\.state\.empresa_id\n    if not empresa_id:\n        raise HTTPException\(status_code=401\)\n    \n    import random\n    from datetime import date\n    \n    return \{\n        "proveidor": \{\n            "nif": "A12345678",\n            "nom": "Jardineria Verda, S\.A\.",\n            "adreca": "C/ de les Flors, 45, 08001 Barcelona",\n            "telefon": "931234567",\n            "email": "info@jardineriaverda\.cat"\n        \},\n        "numero_document": f"ALB-2026-\{random\.randint\(100, 999\)\}",\n        "tipus_document": "ALBARA",\n        "data_document": "2026-08-01",\n        "numero_albarans_vinculats": \[\],\n        "linies": \[\n            \{\n                "referencia": "PROD-01",\n                "nom": "Sac Terra Vegetal \(50L\)",\n                "quantitat": 20\.0,\n                "preu": 5\.50,\n                "descompte_percent": 0\.0,\n                "tipus": "MATERIAL"\n            \},\n            \{\n                "referencia": "PROD-02",\n                "nom": "Tisores Poda",\n                "quantitat": 2\.0,\n                "preu": 25\.00,\n                "descompte_percent": 5\.0,\n                "tipus": "EINA"\n            \}\n        \]\n    \}'

new_ocr_func = """@router.post("/albara/ocr", response_model=dict, status_code=status.HTTP_202_ACCEPTED)
async def processar_document_ocr(
    request: Request,
    fitxer: UploadFile = File(...)
):
    \"\"\"Processa un document PDF o imatge via OCR d'IA per extreure dades d'albarà o factura en BACKGROUND.\"\"\"
    empresa_id = request.state.empresa_id
    if not empresa_id:
        raise HTTPException(status_code=401)
        
    import os
    import uuid
    from app.workers.tasks import processar_ocr_document_task
    
    # 1. Guardem temporalment l'arxiu pujat per poder processar-lo asíncronament
    temp_dir = f"/tmp/docs/{empresa_id}/ocr_inbox"
    os.makedirs(temp_dir, exist_ok=True)
    temp_path = f"{temp_dir}/{uuid.uuid4()}_{fitxer.filename}"
    
    with open(temp_path, "wb") as f:
        f.write(await fitxer.read())
        
    # 2. Despatxa la tasca a Celery (queue_media segons Spec 024 RF-10)
    task = processar_ocr_document_task.delay(temp_path, str(empresa_id))
    
    # 3. Retorna immediatament
    return {"task_id": task.id, "status": "PROCESSING"}"""

content = re.sub(old_ocr_func, new_ocr_func, content)

with open("backend/app/api/v1/gestio/magatzem.py", "w") as f:
    f.write(content)
