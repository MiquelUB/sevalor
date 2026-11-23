import os
import uuid
from datetime import date, datetime
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_with_tenant_context
from app.core.security import require_roles
from app.models.models import Empresa
from app.schemas.comptabilitat import (
    ClientRiscSanititzatDTO,
    FacturaConsultaClientDTO,
    FacturaLiniaComercialDTO,
)
from app.services.economic_suite_service import EconomicSuiteService
from app.services.sovereign_storage import SovereignStorageGateway
from app.services.verifactu import renderitzar_pdf_factura_verifactu

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


async def _obtenir_detall_factura_comercial_db(
    db: AsyncSession,
    empresa_id: uuid.UUID,
    factura_id: uuid.UUID,
) -> Dict[str, Any]:
    """Llegeix el detall comercial de la factura via SECURITY DEFINER (a027), acotat a OTs per a ENGINYER."""
    res = await db.execute(
        text(
            "SELECT public.obtenir_detall_factura_comercial(CAST(:emp_id AS uuid), CAST(:fac_id AS uuid))"
        ),
        {"emp_id": str(empresa_id), "fac_id": str(factura_id)},
    )
    data = res.scalar_one_or_none()
    if not isinstance(data, dict):
        raise HTTPException(status_code=404, detail="Factura no trobada o no vinculada a cap tasca del client")
    return data


def _parse_dt(val: Any) -> datetime:
    if isinstance(val, datetime):
        return val
    raw = str(val or "").replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return datetime.combine(date.today(), datetime.min.time())


def _parse_date_opt(val: Any) -> Optional[date]:
    if val is None or val == "":
        return None
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    try:
        return date.fromisoformat(str(val)[:10])
    except ValueError:
        return None


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


@router.get("/factures/{factura_id}", response_model=FacturaConsultaClientDTO)
async def consultar_factura_tecnica(
    factura_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    """Consulta el detall comercial complet d'una pre-factura o factura vinculada a tasques d'un client.

    Accessible a ENGINYER, SECRETARIA i BOSS per atendre reclamacions de clients sense obrir
    l'accés global a `/gestio/comptabilitat` ni exposar costos PMP, marges ni comptes PGC.
    """
    empresa_id = _get_empresa_id(request)
    data = await _obtenir_detall_factura_comercial_db(db, empresa_id, factura_id)

    raw_linies_val = data.get("linies")
    raw_linies: List[Dict[str, Any]] = raw_linies_val if isinstance(raw_linies_val, list) else []
    linies_dto: List[FacturaLiniaComercialDTO] = [
        FacturaLiniaComercialDTO(
            id=uuid.UUID(str(lin["id"])),
            concepte=str(lin.get("concepte") or ""),
            quantitat=float(lin.get("quantitat") or 0.0),
            preu_venda_unitari=float(lin.get("preu_venda_unitari") or 0.0),
            tipus_iva=float(lin.get("tipus_iva") or 0.0),
            descompte_aplicat_pct=float(lin.get("descompte_aplicat_pct") or 0.0),
            subtotal=float(lin.get("subtotal") or 0.0),
            obra_id=uuid.UUID(str(lin["obra_id"])) if lin.get("obra_id") else None,
        )
        for lin in raw_linies
    ]

    return FacturaConsultaClientDTO(
        id=uuid.UUID(str(data["id"])),
        client_id=uuid.UUID(str(data["client_id"])) if data.get("client_id") else None,
        client_nom=data.get("client_nom"),
        client_nif=data.get("client_nif"),
        numero_factura=int(data.get("numero_factura") or 0),
        serie=str(data.get("serie") or ""),
        data_emissio=_parse_dt(data.get("data_emissio")),
        data_venciment=_parse_date_opt(data.get("data_venciment")),
        estat_document=str(data.get("estat_document") or ""),
        estat_cobrament=str(data.get("estat_cobrament") or "PENDENT"),
        base_imposable=float(data.get("base_imposable") or 0.0),
        quota_iva=float(data.get("quota_iva") or 0.0),
        import_suplits=float(data.get("import_suplits") or 0.0),
        import_retencio=float(data.get("import_retencio") or 0.0),
        import_retencio_garantia_4308=float(data.get("import_retencio_garantia_4308") or 0.0),
        liquid_exigible=float(data.get("liquid_exigible") or 0.0),
        es_inversio_subjecte_passiu=bool(data.get("es_inversio_subjecte_passiu", False)),
        ordres_treball_codis=[str(c) for c in (data.get("ordres_treball_codis") or [])],
        descripcions_linies=[lin.concepte for lin in linies_dto],
        linies=linies_dto,
    )


@router.get("/factures/{factura_id}/pdf")
async def descarregar_pdf_factura_comercial(
    factura_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> Response:
    """Serveix el PDF de la pre-factura o factura del client vinculada a tasques (per a ENGINYER/SECRETARIA/BOSS)."""
    empresa_id = _get_empresa_id(request)
    data = await _obtenir_detall_factura_comercial_db(db, empresa_id, factura_id)

    estat_doc = str(data.get("estat_document") or "")
    pdf_path = data.get("pdf_path")
    if pdf_path and estat_doc != "ESBORRANY_PREFACTURA":
        try:
            return await SovereignStorageGateway.servir_fitxer(
                db=db,
                empresa_id=str(empresa_id),
                fitxer_path=str(pdf_path),
                media_type="application/pdf",
                disposition="inline",
            )
        except HTTPException:
            # Si el fitxer històric no es troba físicament, regenerem el PDF comercial al vol
            pass

    emp = (
        await db.execute(select(Empresa).where(Empresa.id == empresa_id))
    ).scalar_one_or_none()

    raw_linies_pdf = data.get("linies")
    raw_linies_list: List[Dict[str, Any]] = (
        raw_linies_pdf if isinstance(raw_linies_pdf, list) else []
    )
    linies_objs = [
        SimpleNamespace(
            concepte=str(lin.get("concepte") or ""),
            quantitat=float(lin.get("quantitat") or 0.0),
            preu_venda_unitari=float(lin.get("preu_venda_unitari") or 0.0),
            tipus_iva=float(lin.get("tipus_iva") or 0.0),
            descompte_aplicat_pct=float(lin.get("descompte_aplicat_pct") or 0.0),
            subtotal=float(lin.get("subtotal") or 0.0),
        )
        for lin in raw_linies_list
    ]

    serie = str(data.get("serie") or "PRE")
    numero = int(data.get("numero_factura") or 0)
    data_em_dt = _parse_dt(data.get("data_emissio"))
    data_venc = _parse_date_opt(data.get("data_venciment"))

    temp_dir = "/tmp/sevalor_factures_temp"
    os.makedirs(temp_dir, exist_ok=True)
    ruta_tmp = os.path.join(temp_dir, f"{uuid.uuid4()}_{serie}_{numero}.pdf")
    try:
        renderitzar_pdf_factura_verifactu(
            empresa_nom=emp.nom if emp else "Sevalor Suite",
            empresa_nif=emp.nif if emp else "B00000000",
            primari_hsl=emp.primari_hsl if emp else "150 40 20",
            client_nom=str(data.get("client_nom") or "Client"),
            client_nif=str(data.get("client_nif") or "00000000X"),
            serie=serie,
            numero_factura=numero,
            data_emissio=data_em_dt.strftime("%Y-%m-%d"),
            data_venciment=data_venc.isoformat() if data_venc else None,
            estat_document=estat_doc,
            linies=linies_objs,
            base_imposable=float(data.get("base_imposable") or 0.0),
            quota_iva=float(data.get("quota_iva") or 0.0),
            import_suplits=float(data.get("import_suplits") or 0.0),
            import_retencio=float(data.get("import_retencio") or 0.0),
            import_retencio_garantia=float(data.get("import_retencio_garantia_4308") or 0.0),
            import_total=float(data.get("liquid_exigible") or 0.0),
            es_isp=bool(data.get("es_inversio_subjecte_passiu", False)),
            hash_actual=str(data.get("hash_sha256") or ""),
            hash_anterior=data.get("hash_anterior"),
            qr_content=data.get("qr_verifactu_payload"),
            ruta_desti=ruta_tmp,
        )
        with open(ruta_tmp, "rb") as f_bin:
            pdf_bytes = f_bin.read()
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'inline; filename="FACTURA_{serie}_{numero:04d}.pdf"'
            },
        )
    finally:
        try:
            if os.path.exists(ruta_tmp):
                os.remove(ruta_tmp)
        except OSError:
            pass
