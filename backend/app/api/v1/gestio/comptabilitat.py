import uuid
import hashlib
import os
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field

from app.core.db import get_db_with_tenant_context
from app.core.security import get_current_user_claims, require_financial_access
from app.models.models import FacturaCapcalera, Client, Empresa
from app.services.verifactu import generar_factura_pdf
from app.services.outbox_aeat import registrar_enviament_outbox

router = APIRouter(
    prefix="/gestio/comptabilitat",
    tags=["Gestió Comptabilitat"],
    dependencies=[Depends(require_financial_access)],
)

class FacturaCreate(BaseModel):
    numero_factura: int
    serie: str = Field("2026", max_length=20)
    client_id: uuid.UUID
    base_imposable: float = Field(0.0)
    quota_iva: float = Field(0.0)
    import_retencio: float = Field(0.0)
    import_suplits: float = Field(0.0)
    liquid_exigible: float = Field(0.0)
    data_emissio: str = Field("")

class FacturaResponse(BaseModel):
    id: uuid.UUID
    numero_factura: int 
    serie: str
    client_id: uuid.UUID
    base_imposable: float = 0.0
    quota_iva: float = 0.0
    import_retencio: float = 0.0
    import_suplits: float = 0.0
    liquid_exigible: float = 0.0
    hash_sha256: str
    hash_anterior: Optional[str]
    pdf_path: Optional[str] = None
    estat_cobrament: str
    estat_enviament: str

@router.get("/factures", response_model=List[FacturaResponse])
async def llistar_factures(
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = request.state.empresa_id
    if not empresa_id:
        raise HTTPException(status_code=401)

    stmt = select(FacturaCapcalera).where(FacturaCapcalera.empresa_id == uuid.UUID(empresa_id)).order_by(FacturaCapcalera.created_at.desc())
    result = await db.execute(stmt)
    return result.scalars().all()

@router.post("/factures", response_model=FacturaResponse, status_code=status.HTTP_201_CREATED)
async def crear_factura(
    request: Request,
    payload: FacturaCreate,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = request.state.empresa_id
    if not empresa_id:
        raise HTTPException(status_code=401)

    # Validar client
    stmt_c = select(Client).where(Client.id == payload.client_id, Client.empresa_id == uuid.UUID(empresa_id))
    if not (await db.execute(stmt_c)).scalars().first():
        raise HTTPException(status_code=404, detail="Client no trobat")

    # Validar duplicat num + serie
    stmt_dup = select(FacturaCapcalera).where(
        FacturaCapcalera.empresa_id == uuid.UUID(empresa_id),
        FacturaCapcalera.numero_factura == payload.numero_factura,
        FacturaCapcalera.serie == payload.serie
    )
    if (await db.execute(stmt_dup)).scalars().first():
        raise HTTPException(status_code=400, detail="Número i sèrie de factura ja registrats")

    # Carregar empresa i client per a Veri*factu
    stmt_e = select(Empresa).where(Empresa.id == uuid.UUID(empresa_id))
    empresa = (await db.execute(stmt_e)).scalars().first()
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa no trobada")

    stmt_cli = select(Client).where(Client.id == payload.client_id)
    client_db = (await db.execute(stmt_cli)).scalars().first()
    client_nif = client_db.nif if client_db else "00000000X"
    client_nom = client_db.rao_social if client_db else "Client"

    data_emissio = payload.data_emissio or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    # Convertir string a datetime per al model ORM
    try:
        data_emissio_dt = datetime.strptime(data_emissio, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        data_emissio_dt = datetime.now(timezone.utc)
    import_total = payload.base_imposable + payload.quota_iva + payload.import_suplits - payload.import_retencio

    # Ruta per al PDF (en testing, usar /tmp/docs per evitar permisos)
    base_docs = "/tmp/docs" if os.getenv("TESTING") == "1" else "/docs"
    ruta_pdf_dir = f"{base_docs}/{empresa_id}/factures"
    os.makedirs(ruta_pdf_dir, exist_ok=True)
    nom_pdf = f"FACTURA_{payload.serie}_{payload.numero_factura:05d}_{data_emissio}.pdf"
    ruta_pdf = os.path.join(ruta_pdf_dir, nom_pdf)

    # Generar PDF Veri*factu (inclou SELECT FOR UPDATE, hash encadenat, QR)
    resultat_pdf = await generar_factura_pdf(
        db=db,
        empresa_id=uuid.UUID(empresa_id),
        empresa_nom=empresa.nom,
        empresa_nif=empresa.nif,
        logotip_path=empresa.logotip_path,
        primari_hsl=empresa.primari_hsl,
        secundari_hsl=empresa.secundari_hsl,
        client_nom=client_nom,
        client_nif=client_nif,
        serie=payload.serie,
        numero_factura=payload.numero_factura,
        base_imposable=payload.base_imposable,
        quota_iva=payload.quota_iva,
        import_total=import_total,
        data_emissio=data_emissio,
        ruta_desti=ruta_pdf,
    )

    hash_actual = resultat_pdf["hash_sha256"]
    hash_ant = resultat_pdf["hash_anterior"]

    nova_factura = FacturaCapcalera(
        empresa_id=uuid.UUID(empresa_id),
        numero_factura=payload.numero_factura,
        serie=payload.serie,
        client_id=payload.client_id,
        base_imposable=payload.base_imposable,
        quota_iva=payload.quota_iva,
        import_retencio=payload.import_retencio,
        import_suplits=payload.import_suplits,
        liquid_exigible=import_total,
        data_emissio=data_emissio_dt,
        hash_anterior=hash_ant,
        hash_sha256=hash_actual,
        pdf_path=ruta_pdf,
        estat_cobrament="PENDENT",
        estat_enviament="PENDENT"
    )

    db.add(nova_factura)
    await db.commit()

    # Registrar intent d'enviament a AEAT (outbox pattern)
    await registrar_enviament_outbox(
        factura_id=str(nova_factura.id),
        empresa_id=empresa_id,
        serie=payload.serie,
        numero=payload.numero_factura,
        hash_sha256=hash_actual,
        ruta_pdf=ruta_pdf,
        db_session=db,
    )

    return nova_factura
