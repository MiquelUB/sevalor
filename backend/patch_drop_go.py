import re

with open('/media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/feines.py', 'r') as f:
    content = f.read()

drop_go = """
class DropAndGoRequest(BaseModel):
    versio: int
    cap_de_colla_id: Optional[uuid.UUID] = None
    data_programada: Optional[date] = None

@router.patch("/{id}/drop-and-go")
async def drop_and_go(
    id: uuid.UUID,
    payload: DropAndGoRequest,
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = getattr(request.state, "empresa_id", None) or request.headers.get("X-Empresa-ID")
    if not empresa_id or empresa_id == 'undefined':
        raise HTTPException(status_code=401, detail="No identificat")

    stmt = select(OrdreTreball).where(
        OrdreTreball.id == id,
        OrdreTreball.empresa_id == uuid.UUID(empresa_id)
    )
    result = await db.execute(stmt)
    ordre = result.scalars().first()
    if not ordre:
        raise HTTPException(status_code=404, detail="Ordre de treball no trobada")

    if ordre.versio != payload.versio:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Conflicte de concurrència: la feina ha estat modificada per un altre usuari (versió actual: {ordre.versio}, versió enviada: {payload.versio})"
        )

    if payload.cap_de_colla_id is not None:
        ordre.cap_de_colla_id = payload.cap_de_colla_id
    if payload.data_programada is not None:
        ordre.data_planificacio = payload.data_programada

    ordre.versio = ordre.versio + 1

    await db.commit()
    await db.refresh(ordre)
    return {"status": "ok", "versio": ordre.versio, "cap_de_colla_id": ordre.cap_de_colla_id, "data_planificacio": ordre.data_planificacio}
"""

if "DropAndGoRequest" not in content:
    content += drop_go
    with open('/media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/feines.py', 'w') as f:
        f.write(content)
