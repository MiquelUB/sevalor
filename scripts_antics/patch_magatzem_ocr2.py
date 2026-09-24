import re
with open("backend/app/api/v1/gestio/magatzem.py", "r") as f:
    content = f.read()

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

# Match from @router.post("/albara/ocr" up to the next @router
content = re.sub(r'@router\.post\("/albara/ocr".*?(?=\n@router|\Z)', new_ocr_func, content, flags=re.DOTALL)

with open("backend/app/api/v1/gestio/magatzem.py", "w") as f:
    f.write(content)
