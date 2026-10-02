import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_with_tenant_context
from app.models.contractes import (
    ContracteManteniment,
    ContractesMantenimentFinques,
    RevisionsContracte,
)
from app.models.models import Client, FacturaCapcalera, FacturaLinia, Finca
from app.services.economics_service import calculate_mrr

router = APIRouter(prefix="/gestio/contractes", tags=["Contractes Manteniment"])

class RenovarRequest(BaseModel):
    increment_percent: float = Field(default=0.0)

class BaixaRequest(BaseModel):
    motiu: str

class ContracteAlerta(BaseModel):
    revisio_id: uuid.UUID
    contracte_id: uuid.UUID
    numero_contracte: str
    data_prevista: date
    dies_restants: int
    estat: str

class MrrResponse(BaseModel):
    mrr: float


class ContracteMantenimentCreate(BaseModel):
    client_id: uuid.UUID
    numero_contracte: str = Field(..., max_length=50)
    data_inici: date
    data_fi: Optional[date] = None
    import_anual: float = Field(0.0)
    periodicitat: str = Field(..., description="MENSUAL, TRIMESTRAL, SEMESTRAL, ANUAL")
    estat: str = Field("ACTIU")
    observacions: Optional[str] = None
    finques_ids: List[uuid.UUID] = []

class ContracteMantenimentResponse(ContracteMantenimentCreate):
    id: uuid.UUID
    empresa_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}

class ContracteAmbFinquesResponse(ContracteMantenimentResponse):
    finques: List[uuid.UUID]

@router.post("/", response_model=ContracteAmbFinquesResponse, status_code=status.HTTP_201_CREATED)
async def crear_contracte(
    request: Request,
    contracte: ContracteMantenimentCreate,
    db: AsyncSession = Depends(get_db_with_tenant_context)
) -> Any:
    empresa_id = getattr(request.state, "empresa_id", None) or request.headers.get("X-Empresa-ID")
    if not empresa_id or empresa_id == 'undefined':
        raise HTTPException(status_code=401, detail="No identificat")
    empresa_uuid = uuid.UUID(empresa_id)

    # Validar que client pertany a l'empresa
    client_res = await db.execute(select(Client).where(Client.id == contracte.client_id, Client.empresa_id == empresa_uuid))
    if not client_res.scalars().first():
        raise HTTPException(status_code=404, detail="Client no trobat")

    # Validar que totes les finques pertanyen a l'empresa i al client
    if contracte.finques_ids:
        finques_res = await db.execute(select(Finca).where(Finca.id.in_(contracte.finques_ids), Finca.empresa_id == empresa_uuid, Finca.client_id == contracte.client_id))
        finques_db = finques_res.scalars().all()
        if len(finques_db) != len(contracte.finques_ids):
            raise HTTPException(status_code=400, detail="Alguna finca no és vàlida o no pertany al client")

    # Crear contracte
    nou_contracte = ContracteManteniment(
        empresa_id=empresa_uuid,
        client_id=contracte.client_id,
        numero_contracte=contracte.numero_contracte,
        data_inici=contracte.data_inici,
        data_fi=contracte.data_fi,
        import_anual=contracte.import_anual,
        periodicitat=contracte.periodicitat,
        estat=contracte.estat,
        observacions=contracte.observacions
    )
    db.add(nou_contracte)
    await db.flush() # Per obtenir l'ID

    # Crear relacions amb finques
    for finca_id in contracte.finques_ids:
        rel = ContractesMantenimentFinques(
            empresa_id=empresa_uuid,
            contracte_id=nou_contracte.id,
            finca_id=finca_id
        )
        db.add(rel)

    await db.commit()
    await db.refresh(nou_contracte)

    # Utilitzem dict per satisfer el model ContracteAmbFinquesResponse
    base_resp = ContracteMantenimentResponse.model_validate(nou_contracte)
    resp_dict = base_resp.model_dump()
    resp_dict["finques"] = contracte.finques_ids
    return ContracteAmbFinquesResponse(**resp_dict)

@router.get("/", response_model=List[ContracteMantenimentResponse])
async def llistar_contractes(
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context)
) -> Any:
    empresa_id = getattr(request.state, "empresa_id", None) or request.headers.get("X-Empresa-ID")
    if not empresa_id or empresa_id == 'undefined':
        raise HTTPException(status_code=401, detail="No identificat")
    empresa_uuid = uuid.UUID(empresa_id)

    stmt = select(ContracteManteniment).where(ContracteManteniment.empresa_id == empresa_uuid).order_by(ContracteManteniment.created_at.desc())
    result = await db.execute(stmt)
    contractes = result.scalars().all()
    return contractes

@router.get("/kpis/mrr", response_model=MrrResponse)
async def obtenir_mrr(
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context)
) -> Any:
    empresa_id = getattr(request.state, "empresa_id", None) or request.headers.get("X-Empresa-ID")
    if not empresa_id or empresa_id == 'undefined':
        raise HTTPException(status_code=401, detail="No identificat")

    empresa_uuid = uuid.UUID(empresa_id)
    mrr = await calculate_mrr(db, empresa_uuid)
    return MrrResponse(mrr=mrr)

@router.get("/alertes/venciments", response_model=List[ContracteAlerta])
async def llistar_alertes(
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context)
) -> Any:
    empresa_id = getattr(request.state, "empresa_id", None) or request.headers.get("X-Empresa-ID")
    if not empresa_id or empresa_id == 'undefined':
        raise HTTPException(status_code=401, detail="No identificat")

    empresa_uuid = uuid.UUID(empresa_id)

    stmt = select(RevisionsContracte, ContracteManteniment).join(
        ContracteManteniment, RevisionsContracte.contracte_id == ContracteManteniment.id
    ).where(
        RevisionsContracte.empresa_id == empresa_uuid,
        RevisionsContracte.estat.in_(["PENDENT", "VENCUDA", "PROGRAMADA"])
    )
    result = await db.execute(stmt)
    rows = result.all()

    avui = datetime.now(timezone.utc).date()
    alertes = []

    for revisio, contracte in rows:
        dies_restants = (revisio.data_prevista - avui).days
        if dies_restants <= 15:
            estat_actual = revisio.estat
            if dies_restants < 0 and estat_actual != "VENCUDA":
                revisio.estat = "VENCUDA"
                db.add(revisio)
                estat_actual = "VENCUDA"

            alertes.append(
                ContracteAlerta(
                    revisio_id=revisio.id,
                    contracte_id=contracte.id,
                    numero_contracte=contracte.numero_contracte,
                    data_prevista=revisio.data_prevista,
                    dies_restants=dies_restants,
                    estat=estat_actual
                )
            )

    await db.commit()
    return alertes

@router.post("/{contracte_id}/renovar")
async def renovar_contracte(
    contracte_id: uuid.UUID,
    req: RenovarRequest,
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context)
) -> Any:
    empresa_id = getattr(request.state, "empresa_id", None) or request.headers.get("X-Empresa-ID")
    if not empresa_id or empresa_id == 'undefined':
        raise HTTPException(status_code=401, detail="No identificat")

    empresa_uuid = uuid.UUID(empresa_id)

    stmt = select(ContracteManteniment).where(
        ContracteManteniment.id == contracte_id,
        ContracteManteniment.empresa_id == empresa_uuid
    )
    result = await db.execute(stmt)
    contracte = result.scalar_one_or_none()

    if not contracte:
        raise HTTPException(status_code=404, detail="Contracte no trobat")

    if contracte.estat != "ACTIU":
        raise HTTPException(status_code=400, detail="Només es poden renovar contractes actius")

    if contracte.data_fi:
        nova_data_inici = contracte.data_fi + timedelta(days=1)
        nova_data_fi = date(nova_data_inici.year + 1, nova_data_inici.month, nova_data_inici.day)
    else:
        nova_data_inici = datetime.now(timezone.utc).date()
        nova_data_fi = date(nova_data_inici.year + 1, nova_data_inici.month, nova_data_inici.day)

    contracte.data_inici = nova_data_inici
    contracte.data_fi = nova_data_fi

    if req.increment_percent > 0:
        contracte.import_anual = float(contracte.import_anual) * (1 + (req.increment_percent / 100))

    db.add(contracte)
    await db.commit()

    return {"status": "ok", "missatge": "Contracte renovat amb èxit"}

@router.post("/{contracte_id}/baixa")
async def baixa_contracte(
    contracte_id: uuid.UUID,
    req: BaixaRequest,
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context)
) -> Any:
    empresa_id = getattr(request.state, "empresa_id", None) or request.headers.get("X-Empresa-ID")
    if not empresa_id or empresa_id == 'undefined':
        raise HTTPException(status_code=401, detail="No identificat")

    empresa_uuid = uuid.UUID(empresa_id)

    stmt = select(ContracteManteniment).where(
        ContracteManteniment.id == contracte_id,
        ContracteManteniment.empresa_id == empresa_uuid
    )
    result = await db.execute(stmt)
    contracte = result.scalar_one_or_none()

    if not contracte:
        raise HTTPException(status_code=404, detail="Contracte no trobat")

    contracte.estat = "BAIXA"
    contracte.motiu_baixa = req.motiu

    stmt_rev = select(RevisionsContracte).where(
        RevisionsContracte.contracte_id == contracte.id,
        RevisionsContracte.estat.in_(["PENDENT", "PROGRAMADA"])
    )
    res_rev = await db.execute(stmt_rev)
    for rev in res_rev.scalars():
        rev.estat = "CANCELADA"
        db.add(rev)

    db.add(contracte)
    await db.commit()

    return {"status": "ok", "missatge": "Contracte donat de baixa"}

@router.post("/{contracte_id}/prefacturar")
async def generar_prefactura(
    contracte_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context)
) -> Any:
    empresa_id = getattr(request.state, "empresa_id", None) or request.headers.get("X-Empresa-ID")
    if not empresa_id or empresa_id == 'undefined':
        raise HTTPException(status_code=401, detail="No identificat")

    empresa_uuid = uuid.UUID(empresa_id)

    stmt = select(ContracteManteniment).where(
        ContracteManteniment.id == contracte_id,
        ContracteManteniment.empresa_id == empresa_uuid
    )
    result = await db.execute(stmt)
    contracte = result.scalar_one_or_none()

    if not contracte:
        raise HTTPException(status_code=404, detail="Contracte no trobat")

    if contracte.estat != "ACTIU":
        raise HTTPException(status_code=400, detail="Només es poden facturar contractes actius")

    factura = FacturaCapcalera(
        empresa_id=empresa_uuid,
        client_id=contracte.client_id,
        serie="PRE", numero_factura=9999, hash_sha256="draft_hash",
        data_emissio=datetime.now(timezone.utc).date(),
        base_imposable=contracte.import_anual,
        quota_iva=float(contracte.import_anual) * 0.21,
        liquid_exigible=float(contracte.import_anual) * 1.21,
        estat_enviament="PENDENT",
        estat_cobrament="PENDENT"
    )
    db.add(factura)
    await db.flush()

    linia = FacturaLinia(
        empresa_id=empresa_uuid,
        factura_id=factura.id,
        concepte=f"Quotes Manteniment Contracte {contracte.numero_contracte}",
        quantitat=1,
        preu_venda_unitari=contracte.import_anual,
        subtotal=contracte.import_anual,
        tipus_iva=21.0
    )
    db.add(linia)
    await db.commit()

    return {"status": "ok", "factura_id": str(factura.id), "missatge": "Pre-factura generada"}

@router.get("/{contracte_id}", response_model=ContracteAmbFinquesResponse)
async def detall_contracte(
    request: Request,
    contracte_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_with_tenant_context)
) -> Any:
    empresa_id = getattr(request.state, "empresa_id", None) or request.headers.get("X-Empresa-ID")
    if not empresa_id or empresa_id == 'undefined':
        raise HTTPException(status_code=401, detail="No identificat")
    empresa_uuid = uuid.UUID(empresa_id)

    stmt = select(ContracteManteniment).where(ContracteManteniment.id == contracte_id, ContracteManteniment.empresa_id == empresa_uuid)
    result = await db.execute(stmt)
    contracte = result.scalars().first()

    if not contracte:
        raise HTTPException(status_code=404, detail="Contracte no trobat")

    finques_stmt = select(ContractesMantenimentFinques).where(ContractesMantenimentFinques.contracte_id == contracte_id)
    finques_res = await db.execute(finques_stmt)
    finques_db = finques_res.scalars().all()
    finques_ids = [f.finca_id for f in finques_db]

    base_resp = ContracteMantenimentResponse.model_validate(contracte)
    resp_dict = base_resp.model_dump()
    resp_dict["finques"] = finques_ids
    return ContracteAmbFinquesResponse(**resp_dict)
