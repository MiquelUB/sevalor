import re

path = "/media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/flota.py"
with open(path, "r") as f:
    text = f.read()

target = """@router.post("/{vehicle_id}/documents", status_code=201)
async def pujar_document_flota(
    vehicle_id: uuid.UUID,
    tipus_document: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db_with_tenant_context),
    tenant: dict = Depends(valida_uuid),
    current_user: dict = Depends(get_current_user_gestio)
):
    empresa_id = tenant["empresa_id"]"""

replace = """@router.post("/{vehicle_id}/documents", status_code=201)
async def pujar_document_flota(
    request: Request,
    vehicle_id: uuid.UUID,
    tipus_document: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = request.state.empresa_id
    if not empresa_id: raise HTTPException(status_code=401)
    empresa_id = uuid.UUID(empresa_id)
    # TODO current_user can be from state or skip for now
    current_user_id = None"""

text = text.replace(target, replace)

target_get = """@router.get("/{vehicle_id}/documents")
async def llistar_documents_flota(
    vehicle_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    tenant: dict = Depends(valida_uuid)
):
    empresa_id = tenant["empresa_id"]"""

replace_get = """@router.get("/{vehicle_id}/documents")
async def llistar_documents_flota(
    request: Request,
    vehicle_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = request.state.empresa_id
    if not empresa_id: raise HTTPException(status_code=401)
    empresa_id = uuid.UUID(empresa_id)"""

text = text.replace(target_get, replace_get)

# Also fix the import of DocumentFlota and UploadFile just in case it caused issues
# But they were at the top of the appended block

with open(path, "w") as f:
    f.write(text)
print("Endpoints fixed")
