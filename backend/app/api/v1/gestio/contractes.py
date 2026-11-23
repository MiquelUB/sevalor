import hashlib
import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_with_tenant_context
from app.core.security import require_financial_access
from app.models.contractes import (
    ContracteManteniment,
    ContractesMantenimentFinques,
    RevisionsContracte,
)
from app.models.models import Client, FacturaCapcalera, FacturaLinia, Finca
from app.services.economics_service import calculate_mrr
from app.services.sovereign_storage import SovereignStorageGateway

logger = logging.getLogger("sevalor.contractes")

# Spec 01 Principi VI (economics_boss_only): ENGINYER i OPERARI no poden accedir a Contractes ni MRR
router = APIRouter(
    prefix="/gestio/contractes",
    tags=["Contractes Manteniment"],
    dependencies=[Depends(require_financial_access)],
)

PERIODICITAT_DIVISORS = {
    "MENSUAL": 12.0,
    "TRIMESTRAL": 4.0,
    "SEMESTRAL": 2.0,
    "ANUAL": 1.0,
}


def _resolve_emp_uuid(request: Request, claims: dict[str, Any]) -> uuid.UUID:
    empresa_id = (
        getattr(request.state, "empresa_id", None)
        or claims.get("empresa_id")
        or request.headers.get("X-Empresa-ID")
    )
    if not empresa_id or str(empresa_id) in ("undefined", "null", "None"):
        raise HTTPException(status_code=401, detail="No identificat")
    try:
        return uuid.UUID(str(empresa_id))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Identificador d'empresa invàlid") from exc


async def _sincronitzar_contracte_disc(
    db: AsyncSession,
    empresa_id: uuid.UUID,
    contracte: ContracteManteniment,
    finques_ids: Optional[List[uuid.UUID]] = None,
) -> None:
    """Sincronitza el contracte amb 01_clients/contractes_manteniment al disc sobirà."""
    try:
        ruta = await SovereignStorageGateway.desar_entitat_json(
            db=db,
            empresa_id=empresa_id,
            categoria="contractes",
            item_id=str(contracte.id),
            dades={
                "id": str(contracte.id),
                "client_id": str(contracte.client_id),
                "numero_contracte": contracte.numero_contracte,
                "data_inici": contracte.data_inici.isoformat(),
                "data_fi": contracte.data_fi.isoformat() if contracte.data_fi else None,
                "import_anual": float(contracte.import_anual or 0.0),
                "periodicitat": contracte.periodicitat,
                "estat": contracte.estat,
                "observacions": contracte.observacions,
                "motiu_baixa": contracte.motiu_baixa,
                "finques_ids": [str(f) for f in (finques_ids or [])],
                "synced_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        if not str(ruta).startswith("transit://"):
            await SovereignStorageGateway.drenar_cua_transit_empresa(db, empresa_id)
    except Exception as exc:
        logger.warning("No s'ha pogut sincronitzar el contracte %s al disc sobirà: %s", contracte.id, exc)


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
    client_nom: Optional[str] = None
    motiu_baixa: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class ContracteAmbFinquesResponse(ContracteMantenimentResponse):
    finques: List[uuid.UUID]


@router.post("/", response_model=ContracteAmbFinquesResponse, status_code=status.HTTP_201_CREATED)
async def crear_contracte(
    request: Request,
    contracte: ContracteMantenimentCreate,
    claims: dict[str, Any] = Depends(require_financial_access),
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> Any:
    empresa_uuid = _resolve_emp_uuid(request, claims)

    # Validar que client pertany a l'empresa
    client_res = await db.execute(
        select(Client).where(Client.id == contracte.client_id, Client.empresa_id == empresa_uuid)
    )
    client_obj = client_res.scalars().first()
    if not client_obj:
        raise HTTPException(status_code=404, detail="Client no trobat")

    # Validar que totes les finques pertanyen a l'empresa i al client
    if contracte.finques_ids:
        finques_res = await db.execute(
            select(Finca).where(
                Finca.id.in_(contracte.finques_ids),
                Finca.empresa_id == empresa_uuid,
                Finca.client_id == contracte.client_id,
            )
        )
        finques_db = finques_res.scalars().all()
        if len(finques_db) != len(contracte.finques_ids):
            raise HTTPException(
                status_code=400, detail="Alguna finca no és vàlida o no pertany al client"
            )

    nou_contracte = ContracteManteniment(
        empresa_id=empresa_uuid,
        client_id=contracte.client_id,
        numero_contracte=contracte.numero_contracte,
        data_inici=contracte.data_inici,
        data_fi=contracte.data_fi,
        import_anual=contracte.import_anual,
        periodicitat=contracte.periodicitat,
        estat=contracte.estat,
        observacions=contracte.observacions,
    )
    db.add(nou_contracte)
    await db.flush()

    for finca_id in contracte.finques_ids:
        rel = ContractesMantenimentFinques(
            empresa_id=empresa_uuid, contracte_id=nou_contracte.id, finca_id=finca_id
        )
        db.add(rel)

    await db.commit()
    await _sincronitzar_contracte_disc(db, empresa_uuid, nou_contracte, contracte.finques_ids)

    base_resp = ContracteMantenimentResponse.model_validate(nou_contracte)
    resp_dict = base_resp.model_dump()
    resp_dict["client_nom"] = client_obj.rao_social
    resp_dict["finques"] = contracte.finques_ids
    return ContracteAmbFinquesResponse(**resp_dict)


@router.get("/", response_model=List[ContracteMantenimentResponse])
async def llistar_contractes(
    request: Request,
    claims: dict[str, Any] = Depends(require_financial_access),
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> Any:
    empresa_uuid = _resolve_emp_uuid(request, claims)

    stmt = (
        select(ContracteManteniment, Client.rao_social)
        .outerjoin(Client, ContracteManteniment.client_id == Client.id)
        .where(ContracteManteniment.empresa_id == empresa_uuid)
        .order_by(ContracteManteniment.created_at.desc())
    )
    result = await db.execute(stmt)
    out = []
    for ctr, cli_nom in result.all():
        d = ContracteMantenimentResponse.model_validate(ctr).model_dump()
        d["client_nom"] = cli_nom
        out.append(ContracteMantenimentResponse(**d))
    return out


@router.get("/mrr", response_model=MrrResponse)
@router.get("/kpis/mrr", response_model=MrrResponse)
async def obtenir_mrr(
    request: Request,
    claims: dict[str, Any] = Depends(require_financial_access),
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> Any:
    empresa_uuid = _resolve_emp_uuid(request, claims)
    mrr = await calculate_mrr(db, empresa_uuid)
    return MrrResponse(mrr=mrr)


@router.get("/alertes/venciments", response_model=List[ContracteAlerta])
async def llistar_alertes(
    request: Request,
    claims: dict[str, Any] = Depends(require_financial_access),
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> Any:
    empresa_uuid = _resolve_emp_uuid(request, claims)

    stmt = (
        select(RevisionsContracte, ContracteManteniment)
        .join(ContracteManteniment, RevisionsContracte.contracte_id == ContracteManteniment.id)
        .where(
            RevisionsContracte.empresa_id == empresa_uuid,
            RevisionsContracte.estat.in_(["PENDENT", "VENCUDA", "PROGRAMADA"]),
        )
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
                    estat=estat_actual,
                )
            )

    await db.commit()
    return alertes


@router.post("/{contracte_id}/renovar")
async def renovar_contracte(
    contracte_id: uuid.UUID,
    req: RenovarRequest,
    request: Request,
    claims: dict[str, Any] = Depends(require_financial_access),
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> Any:
    empresa_uuid = _resolve_emp_uuid(request, claims)

    stmt = select(ContracteManteniment).where(
        ContracteManteniment.id == contracte_id, ContracteManteniment.empresa_id == empresa_uuid
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
    await _sincronitzar_contracte_disc(db, empresa_uuid, contracte)

    return {"status": "ok", "missatge": "Contracte renovat amb èxit"}


@router.post("/{contracte_id}/baixa")
async def baixa_contracte(
    contracte_id: uuid.UUID,
    req: BaixaRequest,
    request: Request,
    claims: dict[str, Any] = Depends(require_financial_access),
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> Any:
    empresa_uuid = _resolve_emp_uuid(request, claims)

    stmt = select(ContracteManteniment).where(
        ContracteManteniment.id == contracte_id, ContracteManteniment.empresa_id == empresa_uuid
    )
    result = await db.execute(stmt)
    contracte = result.scalar_one_or_none()

    if not contracte:
        raise HTTPException(status_code=404, detail="Contracte no trobat")

    contracte.estat = "BAIXA"
    contracte.motiu_baixa = req.motiu

    stmt_rev = select(RevisionsContracte).where(
        RevisionsContracte.contracte_id == contracte.id,
        RevisionsContracte.empresa_id == empresa_uuid,
        RevisionsContracte.estat.in_(["PENDENT", "PROGRAMADA"]),
    )
    res_rev = await db.execute(stmt_rev)
    for rev in res_rev.scalars():
        rev.estat = "CANCELADA"
        db.add(rev)

    db.add(contracte)
    await db.commit()
    await _sincronitzar_contracte_disc(db, empresa_uuid, contracte)

    return {"status": "ok", "missatge": "Contracte donat de baixa"}


@router.post("/{contracte_id}/prefacturar")
async def generar_prefactura(
    contracte_id: uuid.UUID,
    request: Request,
    claims: dict[str, Any] = Depends(require_financial_access),
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> Any:
    empresa_uuid = _resolve_emp_uuid(request, claims)

    stmt = select(ContracteManteniment).where(
        ContracteManteniment.id == contracte_id, ContracteManteniment.empresa_id == empresa_uuid
    )
    result = await db.execute(stmt)
    contracte = result.scalar_one_or_none()

    if not contracte:
        raise HTTPException(status_code=404, detail="Contracte no trobat")

    if contracte.estat != "ACTIU":
        raise HTTPException(status_code=400, detail="Només es poden facturar contractes actius")

    divisor = PERIODICITAT_DIVISORS.get(str(contracte.periodicitat or "ANUAL").upper(), 1.0)
    quota_base = round(float(contracte.import_anual or 0.0) / divisor, 2)
    quota_iva = round(quota_base * 0.21, 2)
    liquid_exigible = round(quota_base + quota_iva, 2)
    avui = datetime.now(timezone.utc).date()

    from decimal import Decimal
    from app.schemas.comptabilitat import FacturaEmissioCreateDTO, FacturaLiniaCreateDTO
    from app.services.economic_suite_service import EconomicSuiteService

    uid_str = claims.get("sub") or getattr(request.state, "user_id", None)
    usuari_uuid = uuid.UUID(str(uid_str)) if uid_str else uuid.uuid4()

    factura = await EconomicSuiteService.crear_prefactura_esborrany(
        db=db,
        empresa_id=empresa_uuid,
        usuari_id=usuari_uuid,
        payload=FacturaEmissioCreateDTO(
            client_id=contracte.client_id,
            serie="PRE",
            data_emissio=avui,
            data_venciment=avui,
            referencia_client=contracte.numero_contracte,
            linies=[
                FacturaLiniaCreateDTO(
                    concepte=f"Quota {contracte.periodicitat} Manteniment Contracte {contracte.numero_contracte}",
                    quantitat=Decimal("1.00"),
                    preu_venda_unitari=Decimal(str(quota_base)),
                    tipus_iva_pct=Decimal("21.00"),
                )
            ],
        ),
    )
    seq_num = int(factura.numero_factura)
    fingerprint = factura.hash_sha256

    try:
        ruta = await SovereignStorageGateway.desar_entitat_json(
            db=db,
            empresa_id=empresa_uuid,
            categoria="pressupostos",
            item_id=f"prefactura_{factura.id}",
            dades={
                "factura_id": str(factura.id),
                "contracte_id": str(contracte.id),
                "numero_contracte": contracte.numero_contracte,
                "serie": "PRE",
                "numero_factura": seq_num,
                "periodicitat": contracte.periodicitat,
                "base_imposable": quota_base,
                "quota_iva": quota_iva,
                "liquid_exigible": liquid_exigible,
                "hash_sha256": fingerprint,
                "data_emissio": avui.isoformat(),
            },
        )
        if not str(ruta).startswith("transit://"):
            await SovereignStorageGateway.drenar_cua_transit_empresa(db, empresa_uuid)
    except Exception as exc:
        logger.warning("No s'ha pogut sincronitzar pre-factura %s al disc sobirà: %s", factura.id, exc)

    return {
        "status": "ok",
        "factura_id": str(factura.id),
        "serie": "PRE",
        "numero_factura": seq_num,
        "base_imposable": quota_base,
        "missatge": "Pre-factura generada",
    }


@router.get("/{contracte_id}", response_model=ContracteAmbFinquesResponse)
async def detall_contracte(
    request: Request,
    contracte_id: uuid.UUID,
    claims: dict[str, Any] = Depends(require_financial_access),
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> Any:
    empresa_uuid = _resolve_emp_uuid(request, claims)

    stmt = (
        select(ContracteManteniment, Client.rao_social)
        .outerjoin(Client, ContracteManteniment.client_id == Client.id)
        .where(ContracteManteniment.id == contracte_id, ContracteManteniment.empresa_id == empresa_uuid)
    )
    row = (await db.execute(stmt)).first()
    if not row:
        raise HTTPException(status_code=404, detail="Contracte no trobat")
    contracte, cli_nom = row

    finques_stmt = select(ContractesMantenimentFinques).where(
        ContractesMantenimentFinques.empresa_id == empresa_uuid,
        ContractesMantenimentFinques.contracte_id == contracte_id,
    )
    finques_res = await db.execute(finques_stmt)
    finques_db = finques_res.scalars().all()
    finques_ids = [f.finca_id for f in finques_db]

    base_resp = ContracteMantenimentResponse.model_validate(contracte)
    resp_dict = base_resp.model_dump()
    resp_dict["client_nom"] = cli_nom
    resp_dict["finques"] = finques_ids
    return ContracteAmbFinquesResponse(**resp_dict)
