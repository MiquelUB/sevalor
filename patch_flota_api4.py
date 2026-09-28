import re

path = "/media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/flota.py"
with open(path, "r") as f:
    text = f.read()

new_endpoints = """
from fastapi import UploadFile, File, Form
from app.models.models import DocumentFlota
import shutil
import os

@router.post("/{vehicle_id}/documents", status_code=201)
async def pujar_document_flota(
    vehicle_id: uuid.UUID,
    tipus_document: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    tenant: dict = Depends(valida_uuid),
    current_user: dict = Depends(get_current_user_gestio)
):
    empresa_id = tenant["empresa_id"]
    
    # Comprovar vehicle
    stmt = select(Vehicle).where(Vehicle.id == vehicle_id, Vehicle.empresa_id == empresa_id)
    res = await db.execute(stmt)
    v_db = res.scalars().first()
    if not v_db:
        raise HTTPException(status_code=404, detail="Vehicle no trobat")

    # Guardar disc local
    docs_dir = f"/docs/{empresa_id}/flota/{vehicle_id}"
    os.makedirs(docs_dir, exist_ok=True)
    file_path = os.path.join(docs_dir, file.filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    doc = DocumentFlota(
        empresa_id=empresa_id,
        vehicle_id=vehicle_id,
        tipus_document=tipus_document,
        nom_arxiu=file.filename,
        ruta_arxiu=file_path,
        creat_per_id=uuid.UUID(current_user["sub"])
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    
    # Executar OCR asíncron
    try:
        from app.workers.tasks import processar_ocr_document_task
        processar_ocr_document_task.delay(file_path, str(empresa_id))
    except:
        pass
        
    return {"missatge": "Document pujat i en procés d'OCR", "id": str(doc.id)}

@router.get("/{vehicle_id}/documents")
async def llistar_documents_flota(
    vehicle_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    tenant: dict = Depends(valida_uuid)
):
    empresa_id = tenant["empresa_id"]
    stmt = select(DocumentFlota).where(DocumentFlota.vehicle_id == vehicle_id, DocumentFlota.empresa_id == empresa_id)
    res = await db.execute(stmt)
    docs = res.scalars().all()
    
    return [
        {
            "id": str(d.id),
            "tipus": d.tipus_document,
            "nom_arxiu": d.nom_arxiu,
            "data": d.data_document.isoformat() if d.data_document else None
        } for d in docs
    ]
"""

# Appending to the end of the file
with open(path, "a") as f:
    f.write(new_endpoints)

print("Added document endpoints")
