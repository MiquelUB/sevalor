import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_with_tenant_context
from app.core.security import require_roles
from app.models.models import FacturaCapcalera, FacturaLinia
from app.schemas.comptabilitat import ClientRiscSanititzatDTO, FacturaConsultaTecnicaDTO
from app.services.economic_suite_service import EconomicSuiteService

router = APIRouter(
    prefix="/gestio/operativa-financera",
    tags=["Operativa Financera Sanititzada (C-05)"],
    dependencies=[Depends(require_roles(["BOSS", "SECRETARIA", "ENGINYER"]))],
)


def _get_empresa_id(request: Request) -> uuid.UUID:
    emp = getattr(request.state, "empresa_id", None)
    if not emp or emp == "undefined":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Tenant no autenticat")
    return uuid.UUID(str(emp))


@router.get("/client/{client_id}/estat-risc", response_model=ClientRiscSanititzatDTO)
async def consultar_estat_risc_client(
    client_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    empresa_id = _get_empresa_id(request)
    return await EconomicSuiteService.validar_operacio_camp_client(
        db=db, empresa_id=empresa_id, client_id=client_id, enforce_lock=False
    )


@router.post("/validar-operacio-client/{client_id}", response_model=ClientRiscSanititzatDTO)
@router.post("/validar-operacio/{client_id}", response_model=ClientRiscSanititzatDTO)
async def validar_operacio_client(
    client_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    empresa_id = _get_empresa_id(request)
    return await EconomicSuiteService.validar_operacio_camp_client(
        db=db, empresa_id=empresa_id, client_id=client_id, enforce_lock=True
    )


@router.get("/factures/{factura_id}", response_model=FacturaConsultaTecnicaDTO)
async def consultar_factura_tecnica(
    factura_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    empresa_id = _get_empresa_id(request)
    factura = (
        await db.execute(
            select(FacturaCapcalera).where(
                FacturaCapcalera.id == factura_id,
                FacturaCapcalera.empresa_id == empresa_id,
            )
        )
    ).scalar_one_or_none()
    if not factura:
        raise HTTPException(status_code=404, detail="Factura no trobada")

    linies = (
        (
            await db.execute(
                select(FacturaLinia.concepte).where(
                    FacturaLinia.factura_id == factura.id,
                    FacturaLinia.empresa_id == empresa_id,
                )
            )
        )
        .scalars()
        .all()
    )
    return FacturaConsultaTecnicaDTO(
        id=factura.id,
        numero_factura=factura.numero_factura,
        serie=factura.serie,
        data_emissio=factura.data_emissio,
        estat_document=factura.estat_document,
        descripcions_linies=list(linies),
    )
