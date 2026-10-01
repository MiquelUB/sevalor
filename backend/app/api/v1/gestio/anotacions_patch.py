from datetime import datetime

class CapaAnotacioCreate(BaseModel):
    ordre_treball_id: uuid.UUID
    nom_capa: str = Field(..., max_length=100)
    fitxer_vectorial_path: str = Field(..., max_length=500)
    operari_id: Optional[uuid.UUID] = None
    estat_capa: str = Field("ACTIVA", max_length=30)

class CapaAnotacioResponse(BaseModel):
    id: uuid.UUID
    ordre_treball_id: uuid.UUID
    nom_capa: str
    fitxer_vectorial_path: str
    operari_id: Optional[uuid.UUID]
    estat_capa: str

@router.get("/anotacions", response_model=List[CapaAnotacioResponse])
async def llistar_anotacions(
    request: Request,
    ordre_treball_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    """Llista les capes d'anotacions."""
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == 'undefined':
        raise HTTPException(status_code=401, detail="No identificat")

    stmt = select(CapaAnotacio).where(CapaAnotacio.empresa_id == uuid.UUID(empresa_id))
    if ordre_treball_id:
        stmt = stmt.where(CapaAnotacio.ordre_treball_id == ordre_treball_id)

    result = await db.execute(stmt)
    return result.scalars().all()

@router.post("/anotacions", response_model=CapaAnotacioResponse, status_code=status.HTTP_201_CREATED)
async def crear_anotacio(
    request: Request,
    payload: CapaAnotacioCreate,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    """Crea una nova capa d'anotació."""
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == 'undefined':
        raise HTTPException(status_code=401, detail="No identificat")

    # TODO Check if ordre_treball exists for this empresa

    nova_anotacio = CapaAnotacio(
        empresa_id=uuid.UUID(empresa_id),
        ordre_treball_id=payload.ordre_treball_id,
        nom_capa=payload.nom_capa,
        fitxer_vectorial_path=payload.fitxer_vectorial_path,
        operari_id=payload.operari_id,
        estat_capa=payload.estat_capa
    )
    db.add(nova_anotacio)
    await db.commit()
    await db.refresh(nova_anotacio)
    return nova_anotacio

