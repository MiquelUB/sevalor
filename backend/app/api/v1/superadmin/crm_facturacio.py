"""Router CRM SaaS, Facturació B2B Veri*factu amb Human-in-the-Loop i Tiquets d'Incidència."""

import logging
import os
import uuid
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_with_tenant_context
from app.core.security import require_roles
from app.models.models import (
    Empresa,
    SaasFacturaB2B,
    SaasHistorialLlicencia,
    SaasTiquetSuport,
)
from app.services.verifactu import generar_qr_verifactu, generar_sha256_encadenat

logger = logging.getLogger("superadmin.crm_facturacio")

router = APIRouter(
    prefix="/superadmin/crm",
    tags=["Superadmin CRM & Facturació B2B Veri*factu"],
    dependencies=[Depends(require_roles(["SUPERADMIN"]))],
)

SEVALOR_EMISSOR_NOM = "SEVALOR SUITE S.L."
SEVALOR_EMISSOR_NIF = "B99887766"


class EquipIADetallItem(BaseModel):
    concepte: Optional[str] = Field(None, max_length=200)
    nom: Optional[str] = Field(None, max_length=200)
    unitats: int = Field(1, ge=1, le=500)
    preu_unitari: float = Field(0.0, ge=0.0)
    modalitat: str = Field("VENDA")

    @field_validator("modalitat")
    @classmethod
    def validar_nomes_venda(cls, v: str) -> str:
        val = v.strip().upper()
        if val != "VENDA":
            raise ValueError(
                "Els equips d'IA mai són de rènting; només s'admet la modalitat 'VENDA'."
            )
        return val

    def normalized_dict(self) -> Dict[str, Any]:
        label = (self.concepte or self.nom or "Equip IA").strip()
        return {
            "concepte": label,
            "nom": label,
            "unitats": self.unitats,
            "preu_unitari": self.preu_unitari,
            "modalitat": self.modalitat,
        }


class PrefacturaCreateRequest(BaseModel):
    empresa_id: str
    periode: Optional[str] = Field(None, max_length=30, description="Ex: 2026-10")
    periode_facturacio: Optional[str] = Field(None, max_length=30, description="Ex: 2026-10")
    serie: str = Field("SAAS", min_length=2, max_length=20)
    concepte_onboarding_desc: Optional[str] = Field(None, max_length=255)
    concepte_onboarding: Optional[str] = Field(None, max_length=255)
    import_onboarding: float = Field(0.0, ge=0.0)
    concepte_config_ia_desc: Optional[str] = Field(None, max_length=255)
    concepte_config_ia: Optional[str] = Field(None, max_length=255)
    import_config_ia: float = Field(0.0, ge=0.0)
    equips_ia_detall: Optional[List[EquipIADetallItem]] = None
    import_equips_ia: Optional[float] = Field(None, ge=0.0)
    num_operaris_facturats: Optional[int] = Field(None, ge=0, le=500)
    num_operaris: Optional[int] = Field(None, ge=0, le=500)
    preu_unitari_operari: Optional[float] = Field(None, ge=0.0)
    preu_per_operari: Optional[float] = Field(None, ge=0.0)
    tipus_iva_percent: Optional[float] = Field(None, ge=0.0, le=100.0)
    iva_percent: Optional[float] = Field(None, ge=0.0, le=100.0)
    notes: Optional[str] = None


class PrefacturaUpdateRequest(BaseModel):
    empresa_id: Optional[str] = None
    periode: Optional[str] = Field(None, max_length=30)
    periode_facturacio: Optional[str] = Field(None, max_length=30)
    concepte_onboarding_desc: Optional[str] = Field(None, max_length=255)
    concepte_onboarding: Optional[str] = Field(None, max_length=255)
    import_onboarding: Optional[float] = Field(None, ge=0.0)
    concepte_config_ia_desc: Optional[str] = Field(None, max_length=255)
    concepte_config_ia: Optional[str] = Field(None, max_length=255)
    import_config_ia: Optional[float] = Field(None, ge=0.0)
    equips_ia_detall: Optional[List[EquipIADetallItem]] = None
    import_equips_ia: Optional[float] = Field(None, ge=0.0)
    num_operaris_facturats: Optional[int] = Field(None, ge=0, le=500)
    num_operaris: Optional[int] = Field(None, ge=0, le=500)
    preu_unitari_operari: Optional[float] = Field(None, ge=0.0)
    preu_per_operari: Optional[float] = Field(None, ge=0.0)
    tipus_iva_percent: Optional[float] = Field(None, ge=0.0, le=100.0)
    iva_percent: Optional[float] = Field(None, ge=0.0, le=100.0)
    notes: Optional[str] = None


class VerificarPrefacturaRequest(BaseModel):
    confirmacio_humana: bool = Field(
        True,
        description="Ha de ser True. El sistema mai pot emetre una factura Veri*factu sense verificació humana.",
    )


class EstatCobramentRequest(BaseModel):
    estat: Optional[str] = Field(None, pattern="^(COBRADA|IMPAGADA|EMESA_VERIFACTU)$")
    estat_cobrament: Optional[str] = Field(None, pattern="^(COBRADA|IMPAGADA|EMESA_VERIFACTU)$")
    activar_hibernacio: Optional[bool] = Field(
        None,
        description="Si és True i la factura està IMPAGADA, passa l'empresa a estat HIBERNANT.",
    )
    passar_a_hibernant: Optional[bool] = Field(None)


class TiquetSuportCreateRequest(BaseModel):
    empresa_id: str
    assumpte: str = Field(..., min_length=3, max_length=200)
    descripcio: str = Field(..., min_length=3)
    severitat: Optional[str] = Field(None, pattern="^(BAIXA|NORMAL|ALTA|CRITICA)$")
    prioritat: Optional[str] = Field(None, pattern="^(BAIXA|NORMAL|ALTA|CRITICA)$")


class TiquetSuportUpdateRequest(BaseModel):
    estat: Optional[str] = Field(None, pattern="^(OBERT|EN_CURS|RESOLT|TANCAT)$")
    resolucio_notes: Optional[str] = None
    resolucio: Optional[str] = None
    severitat: Optional[str] = Field(None, pattern="^(BAIXA|NORMAL|ALTA|CRITICA)$")
    prioritat: Optional[str] = Field(None, pattern="^(BAIXA|NORMAL|ALTA|CRITICA)$")


def _serialitzar_factura_b2b(f: SaasFacturaB2B) -> Dict[str, Any]:
    codi_oficial = (
        f"SEVALOR-{f.serie}-{f.numero_factura:05d}"
        if f.numero_factura is not None
        else None
    )
    estat_cobrament = (
        f.estat if f.estat in ("COBRADA", "IMPAGADA") else "PENDENT"
    )
    return {
        "id": str(f.id),
        "empresa_id": str(f.empresa_id) if f.empresa_id else None,
        "client_nom_snapshot": f.client_nom_snapshot,
        "client_nif_snapshot": f.client_nif_snapshot,
        "serie": f.serie,
        "numero_factura": codi_oficial,
        "numero_correlatiu": f.numero_factura,
        "codi_factura": (
            codi_oficial
            if codi_oficial is not None
            else f"PREFACTURA-{str(f.id)[:8].upper()}"
        ),
        "estat": "EMESA_VERIFACTU" if f.numero_factura is not None and f.estat != "ESBORRANY_PREFACTURA" else f.estat,
        "estat_cobrament": estat_cobrament,
        "periode": f.periode,
        "periode_facturacio": f.periode,
        "concepte_onboarding_desc": f.concepte_onboarding_desc,
        "concepte_onboarding": f.concepte_onboarding_desc,
        "import_onboarding": float(f.import_onboarding or 0.0),
        "concepte_config_ia_desc": f.concepte_config_ia_desc,
        "concepte_config_ia": f.concepte_config_ia_desc,
        "import_config_ia": float(f.import_config_ia or 0.0),
        "equips_ia_detall": f.equips_ia_detall or [],
        "import_equips_ia": float(f.import_equips_ia or 0.0),
        "num_operaris_facturats": int(f.num_operaris_facturats or 0),
        "num_operaris": int(f.num_operaris_facturats or 0),
        "preu_unitari_operari": float(f.preu_unitari_operari or 0.0),
        "preu_per_operari": float(f.preu_unitari_operari or 0.0),
        "import_operaris": float(f.import_operaris or 0.0),
        "base_imposable": float(f.base_imposable or 0.0),
        "tipus_iva_percent": float(f.tipus_iva_percent or 21.0),
        "iva_percent": float(f.tipus_iva_percent or 21.0),
        "quota_iva": float(f.quota_iva or 0.0),
        "import_total": float(f.import_total or 0.0),
        "total_factura": float(f.import_total or 0.0),
        "verificada_per_huma": bool(f.data_verificacio_humana is not None),
        "verificada_per_id": str(f.verificada_per_id) if f.verificada_per_id else None,
        "data_verificacio_humana": (
            f.data_verificacio_humana.isoformat() if f.data_verificacio_humana else None
        ),
        "hash_sha256": f.hash_sha256,
        "hash_actual": f.hash_sha256,
        "hash_anterior": f.hash_anterior,
        "qr_verifactu": f.qr_verifactu,
        "pdf_path": f.pdf_path,
        "data_emissio": f.data_emissio.isoformat() if f.data_emissio else None,
        "created_at": f.created_at.isoformat() if f.created_at else None,
    }


def _recalcular_imports(f: SaasFacturaB2B) -> None:
    equips = f.equips_ia_detall or []
    if equips:
        total_equips = sum(
            float(item.get("unitats", 1)) * float(item.get("preu_unitari", 0.0))
            for item in equips
        )
        f.import_equips_ia = round(total_equips, 2)
    else:
        f.import_equips_ia = round(float(f.import_equips_ia or 0.0), 2)

    f.import_operaris = round(
        int(f.num_operaris_facturats or 0) * float(f.preu_unitari_operari or 0.0), 2
    )
    base = (
        float(f.import_onboarding or 0.0)
        + float(f.import_config_ia or 0.0)
        + float(f.import_equips_ia or 0.0)
        + float(f.import_operaris or 0.0)
    )
    f.base_imposable = round(base, 2)
    iva_pct = float(f.tipus_iva_percent if f.tipus_iva_percent is not None else 21.0)
    f.quota_iva = round(f.base_imposable * (iva_pct / 100.0), 2)
    f.import_total = round(f.base_imposable + f.quota_iva, 2)


def _obtenir_ruta_factura_b2b_pdf(factura_id: str) -> str:
    base_docs = os.getenv("SOVEREIGN_DOCS_PATH", "/docs")
    target_dir = os.path.join(base_docs, "superadmin", "factures_b2b")
    try:
        os.makedirs(target_dir, exist_ok=True)
        return os.path.join(target_dir, f"factura_saas_{factura_id}.pdf")
    except OSError:
        fallback_dir = "/tmp/sevalor_docs/superadmin/factures_b2b"
        os.makedirs(fallback_dir, exist_ok=True)
        return os.path.join(fallback_dir, f"factura_saas_{factura_id}.pdf")


@router.get("/factures", response_model=List[Dict[str, Any]])
async def llistar_factures_b2b(
    empresa_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> List[Dict[str, Any]]:
    """Llista totes les pre-factures i factures B2B Veri*factu (fins i tot d'empreses donades de baixa)."""
    stmt = select(SaasFacturaB2B).order_by(SaasFacturaB2B.created_at.desc())
    if empresa_id:
        try:
            emp_uuid = uuid.UUID(empresa_id)
            stmt = stmt.where(SaasFacturaB2B.empresa_id == emp_uuid)
        except ValueError:
            raise HTTPException(status_code=400, detail="UUID d'empresa invàlid.")

    res = await db.execute(stmt)
    factures = res.scalars().all()
    return [_serialitzar_factura_b2b(f) for f in factures]


@router.post("/prefactures", status_code=status.HTTP_201_CREATED, response_model=Dict[str, Any])
async def crear_prefactura_b2b(
    payload: PrefacturaCreateRequest,
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> Dict[str, Any]:
    """Crea una pre-factura NO final en estat ESBORRANY_PREFACTURA editable abans de Veri*factu."""
    try:
        emp_uuid = uuid.UUID(payload.empresa_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="UUID d'empresa invàlid.")

    emp_res = await db.execute(select(Empresa).where(Empresa.id == emp_uuid))
    emp = emp_res.scalars().first()
    if not emp:
        raise HTTPException(status_code=404, detail="Empresa no trobada.")

    if payload.num_operaris_facturats is not None:
        num_ops = payload.num_operaris_facturats
    elif payload.num_operaris is not None:
        num_ops = payload.num_operaris
    else:
        num_ops = int(getattr(emp, "quota_operaris", None) or 5)

    if payload.preu_unitari_operari is not None:
        preu_op = payload.preu_unitari_operari
    elif payload.preu_per_operari is not None:
        preu_op = payload.preu_per_operari
    else:
        preu_op = float(getattr(emp, "tarifa_per_operari", 0.0) or 0.0)

    equips_dump = (
        [item.normalized_dict() for item in payload.equips_ia_detall]
        if payload.equips_ia_detall is not None
        else []
    )

    periode_val = (payload.periode or payload.periode_facturacio or date.today().strftime("%Y-%m")).strip()
    conc_onb = payload.concepte_onboarding if payload.concepte_onboarding is not None else payload.concepte_onboarding_desc
    conc_ia = payload.concepte_config_ia if payload.concepte_config_ia is not None else payload.concepte_config_ia_desc
    iva_val = (
        payload.iva_percent
        if payload.iva_percent is not None
        else (payload.tipus_iva_percent if payload.tipus_iva_percent is not None else 21.0)
    )

    nova_prefactura = SaasFacturaB2B(
        empresa_id=emp.id,
        client_nom_snapshot=emp.nom,
        client_nif_snapshot=emp.nif,
        serie=payload.serie.strip().upper(),
        numero_factura=None,
        estat="ESBORRANY_PREFACTURA",
        periode=periode_val,
        concepte_onboarding_desc=conc_onb,
        import_onboarding=payload.import_onboarding,
        concepte_config_ia_desc=conc_ia,
        import_config_ia=payload.import_config_ia,
        equips_ia_detall=equips_dump,
        import_equips_ia=payload.import_equips_ia or 0.0,
        num_operaris_facturats=num_ops,
        preu_unitari_operari=preu_op,
        tipus_iva_percent=iva_val,
    )
    _recalcular_imports(nova_prefactura)

    db.add(nova_prefactura)
    await db.commit()

    return _serialitzar_factura_b2b(nova_prefactura)


@router.put("/prefactures/{prefactura_id}", response_model=Dict[str, Any])
async def editar_prefactura_b2b(
    prefactura_id: str,
    payload: PrefacturaUpdateRequest,
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> Dict[str, Any]:
    """Edita qualsevol dels 4 conceptes opcionals d'una pre-factura abans de la seva verificació humana."""
    try:
        pref_uuid = uuid.UUID(prefactura_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="UUID de pre-factura invàlid.")

    res = await db.execute(select(SaasFacturaB2B).where(SaasFacturaB2B.id == pref_uuid))
    pref = res.scalars().first()
    if not pref:
        raise HTTPException(status_code=404, detail="Pre-factura no trobada.")

    if pref.estat != "ESBORRANY_PREFACTURA":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Aquesta factura ja ha estat verificada i emesa amb Veri*factu; és immutable i no es pot modificar.",
        )

    if payload.periode is not None or payload.periode_facturacio is not None:
        pref.periode = (payload.periode or payload.periode_facturacio or pref.periode).strip()
    if payload.concepte_onboarding_desc is not None or "concepte_onboarding" in payload.model_fields_set:
        pref.concepte_onboarding_desc = (
            payload.concepte_onboarding
            if "concepte_onboarding" in payload.model_fields_set
            else payload.concepte_onboarding_desc
        )
    if payload.import_onboarding is not None:
        pref.import_onboarding = payload.import_onboarding
    if payload.concepte_config_ia_desc is not None or "concepte_config_ia" in payload.model_fields_set:
        pref.concepte_config_ia_desc = (
            payload.concepte_config_ia
            if "concepte_config_ia" in payload.model_fields_set
            else payload.concepte_config_ia_desc
        )
    if payload.import_config_ia is not None:
        pref.import_config_ia = payload.import_config_ia
    if payload.equips_ia_detall is not None:
        pref.equips_ia_detall = [item.normalized_dict() for item in payload.equips_ia_detall]
    if payload.import_equips_ia is not None:
        pref.import_equips_ia = payload.import_equips_ia
    if payload.num_operaris_facturats is not None or payload.num_operaris is not None:
        pref.num_operaris_facturats = (
            payload.num_operaris_facturats
            if payload.num_operaris_facturats is not None
            else int(payload.num_operaris or 0)
        )
    if payload.preu_unitari_operari is not None or payload.preu_per_operari is not None:
        pref.preu_unitari_operari = (
            payload.preu_unitari_operari
            if payload.preu_unitari_operari is not None
            else float(payload.preu_per_operari or 0.0)
        )
    if payload.tipus_iva_percent is not None or payload.iva_percent is not None:
        pref.tipus_iva_percent = (
            payload.tipus_iva_percent
            if payload.tipus_iva_percent is not None
            else float(payload.iva_percent or 21.0)
        )

    _recalcular_imports(pref)
    await db.commit()

    serialized = _serialitzar_factura_b2b(pref)
    return {**serialized, "factura": serialized}


@router.post("/prefactures/{prefactura_id}/verificar-i-emetre", response_model=Dict[str, Any])
async def verificar_i_emetre_verifactu_b2b(
    prefactura_id: str,
    payload: Optional[VerificarPrefacturaRequest] = None,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(require_roles(["SUPERADMIN"])),
) -> Dict[str, Any]:
    """Human-in-the-Loop obligatori: Verifica una pre-factura i emet la factura definitiva Veri*factu."""
    if payload is not None and not payload.confirmacio_humana:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Verificació humana obligatòria (Human-in-the-Loop): cal confirmar explícitament la pre-factura abans d'emetre-la a Veri*factu.",
        )

    try:
        pref_uuid = uuid.UUID(prefactura_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="UUID de pre-factura invàlid.")

    res = await db.execute(select(SaasFacturaB2B).where(SaasFacturaB2B.id == pref_uuid))
    pref = res.scalars().first()
    if not pref:
        raise HTTPException(status_code=404, detail="Pre-factura no trobada.")

    if pref.estat != "ESBORRANY_PREFACTURA":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La factura ja ha estat emesa anteriorment.",
        )

    _recalcular_imports(pref)

    # Bloqueig i obtenció de l'última factura emesa de la sèrie SAAS
    base_sql = (
        "SELECT numero_factura, hash_sha256 FROM saas_factures_b2b "
        "WHERE serie = :serie AND estat != 'ESBORRANY_PREFACTURA' "
        "AND numero_factura IS NOT NULL "
        "ORDER BY numero_factura DESC LIMIT 1"
    )
    if os.getenv("TESTING") != "1":
        base_sql += " FOR UPDATE"

    last_res = await db.execute(text(base_sql), {"serie": pref.serie})
    last_row = last_res.fetchone()
    if last_row:
        ultim_num = int(last_row[0])
        hash_anterior: Optional[str] = str(last_row[1]) if last_row[1] else None
    else:
        ultim_num = 0
        hash_anterior = None

    nou_num = ultim_num + 1
    data_avui = date.today()
    data_emissio_str = data_avui.isoformat()

    hash_actual = generar_sha256_encadenat(
        empresa_nif=SEVALOR_EMISSOR_NIF,
        client_nif=pref.client_nif_snapshot,
        serie=pref.serie,
        numero_factura=nou_num,
        base_imposable=float(pref.base_imposable),
        quota_iva=float(pref.quota_iva),
        import_total=float(pref.import_total),
        data_emissio=data_emissio_str,
        hash_anterior=hash_anterior,
    )

    qr_content = generar_qr_verifactu(
        nif_emissor=SEVALOR_EMISSOR_NIF,
        nif_destinatari=pref.client_nif_snapshot,
        serie=pref.serie,
        numero=nou_num,
        hash_sha256=hash_actual,
        import_total=float(pref.import_total),
        data_emissio=data_emissio_str,
    )

    pdf_path = _obtenir_ruta_factura_b2b_pdf(str(pref.id))
    _generar_pdf_b2b_reportlab(
        pref=pref,
        numero_factura=nou_num,
        data_emissio_str=data_emissio_str,
        hash_actual=hash_actual,
        hash_anterior=hash_anterior,
        qr_content=qr_content,
        ruta_desti=pdf_path,
    )

    sub = claims.get("sub")
    verificador_uuid: Optional[uuid.UUID] = None
    if sub:
        try:
            verificador_uuid = uuid.UUID(str(sub))
        except ValueError:
            verificador_uuid = None

    pref.numero_factura = nou_num
    pref.estat = "EMESA_VERIFACTU"
    pref.verificada_per_id = verificador_uuid
    pref.data_verificacio_humana = datetime.now(timezone.utc)
    pref.data_emissio = data_avui
    pref.hash_sha256 = hash_actual
    pref.hash_anterior = hash_anterior
    pref.qr_verifactu = qr_content
    pref.pdf_path = pdf_path

    await db.commit()

    serialized = _serialitzar_factura_b2b(pref)
    return {**serialized, "factura": serialized}


def _generar_pdf_b2b_reportlab(
    pref: SaasFacturaB2B,
    numero_factura: int,
    data_emissio_str: str,
    hash_actual: str,
    hash_anterior: Optional[str],
    qr_content: str,
    ruta_desti: str,
) -> None:
    from reportlab.graphics.barcode import qr  # type: ignore[import-untyped]
    from reportlab.lib.colors import HexColor  # type: ignore[import-untyped]
    from reportlab.lib.pagesizes import A4  # type: ignore[import-untyped]
    from reportlab.pdfgen import canvas  # type: ignore[import-untyped]

    c = canvas.Canvas(ruta_desti, pagesize=A4)
    c.setFont("Helvetica-Bold", 14)
    c.setFillColor(HexColor("#065f46"))
    c.drawString(30, A4[1] - 50, SEVALOR_EMISSOR_NOM)
    c.setFont("Helvetica", 10)
    c.setFillColor(HexColor("#333333"))
    c.drawString(30, A4[1] - 68, f"NIF Emissor: {SEVALOR_EMISSOR_NIF} • Facturació SaaS B2B Veri*factu")
    c.line(30, A4[1] - 78, A4[0] - 30, A4[1] - 78)

    c.setFont("Helvetica-Bold", 11)
    c.drawString(30, A4[1] - 105, "CLIENT EMPRESA (TENANT):")
    c.setFont("Helvetica", 10)
    c.drawString(30, A4[1] - 122, f"{pref.client_nom_snapshot} (NIF: {pref.client_nif_snapshot})")

    c.setFont("Helvetica-Bold", 12)
    c.drawString(
        30, A4[1] - 155, f"FACTURA OFICIAL {pref.serie}-{numero_factura:05d} (Període: {pref.periode})"
    )
    c.setFont("Helvetica", 9)
    c.drawString(30, A4[1] - 172, f"Data d'emissió: {data_emissio_str} • Verificada per humà (HITL)")

    y = A4[1] - 205
    c.setFont("Helvetica-Bold", 10)
    c.drawString(30, y, "CONCEPTES FACTURATS:")
    y -= 18
    c.setFont("Helvetica", 9)

    if float(pref.import_onboarding or 0.0) > 0:
        desc_onb = pref.concepte_onboarding_desc or "Onboarding / Llicència Plataforma"
        c.drawString(40, y, f"1. {desc_onb}: {float(pref.import_onboarding):.2f} €")
        y -= 15

    if float(pref.import_config_ia or 0.0) > 0:
        desc_ia = pref.concepte_config_ia_desc or "Configuració IA"
        c.drawString(40, y, f"2. {desc_ia}: {float(pref.import_config_ia):.2f} €")
        y -= 15

    if float(pref.import_equips_ia or 0.0) > 0:
        c.drawString(40, y, f"3. Venda d'Equips IA ( Total: {float(pref.import_equips_ia):.2f} € ):")
        y -= 14
        for item in pref.equips_ia_detall or []:
            c.drawString(
                55,
                y,
                f"- {item.get('concepte', 'Equip IA')} (VENDA) x {item.get('unitats', 1)} u. a {float(item.get('preu_unitari', 0.0)):.2f} €",
            )
            y -= 13

    if float(pref.import_operaris or 0.0) > 0:
        c.drawString(
            40,
            y,
            f"4. Llicència d'Operaris: {int(pref.num_operaris_facturats or 0)} operaris x {float(pref.preu_unitari_operari or 0.0):.2f} € = {float(pref.import_operaris):.2f} €",
        )
        y -= 18

    y -= 10
    c.line(30, y, A4[0] - 140, y)
    y -= 18
    c.setFont("Helvetica", 10)
    c.drawString(30, y, f"Base Imposable: {float(pref.base_imposable):.2f} €")
    y -= 16
    c.drawString(
        30, y, f"Quota IVA ({float(pref.tipus_iva_percent):.1f}%): {float(pref.quota_iva):.2f} €"
    )
    y -= 20
    c.setFont("Helvetica-Bold", 12)
    c.drawString(30, y, f"IMPORT TOTAL: {float(pref.import_total):.2f} €")

    try:
        qr_code = qr.QrCodeWidget(qr_content, barWidth=65, barHeight=65)
        bounds = qr_code.getBounds()
        qr_w = bounds[2] - bounds[0]
        qr_h = bounds[3] - bounds[1]
        qr_scale = 65 / max(qr_w, qr_h)
        c.saveState()
        c.translate(A4[0] - 105, A4[1] - 235)
        c.scale(qr_scale, qr_scale)
        qr_code.drawOn(c, 0, 0)
        c.restoreState()
        c.setFont("Helvetica", 6)
        c.setFillColor(HexColor("#666666"))
        c.drawString(A4[0] - 105, A4[1] - 242, "Veri*factu AEAT QR")
    except Exception as exc:
        logger.warning("No s'ha pogut incrustar QR al PDF B2B: %s", exc)

    c.setFont("Helvetica", 7)
    c.setFillColor(HexColor("#777777"))
    c.drawString(30, 50, f"Veri*factu Hash SHA-256: {hash_actual}")
    c.drawString(
        30,
        36,
        f"Hash Anterior: {hash_anterior or '(Primera factura de la sèrie SAAS)'}",
    )
    c.showPage()
    c.save()


@router.patch("/factures/{factura_id}/estat-cobrament", response_model=Dict[str, Any])
async def canviar_estat_cobrament_factura(
    factura_id: str,
    payload: EstatCobramentRequest,
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> Dict[str, Any]:
    """Actualitza l'estat de cobrament (COBRADA / IMPAGADA) i opcionalment activa l'estat HIBERNANT."""
    try:
        f_uuid = uuid.UUID(factura_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="UUID de factura invàlid.")

    res = await db.execute(select(SaasFacturaB2B).where(SaasFacturaB2B.id == f_uuid))
    fac = res.scalars().first()
    if not fac:
        raise HTTPException(status_code=404, detail="Factura no trobada.")

    if fac.estat == "ESBORRANY_PREFACTURA":
        raise HTTPException(
            status_code=422,
            detail="No es pot marcar com a cobrada o impagada una pre-factura no emesa.",
        )

    nou_estat = payload.estat or payload.estat_cobrament or "COBRADA"
    activar_hib = (
        payload.activar_hibernacio
        if payload.activar_hibernacio is not None
        else bool(payload.passar_a_hibernant)
    )
    fac.estat = nou_estat

    empresa_hibernada = False
    if nou_estat == "IMPAGADA" and activar_hib and fac.empresa_id:
        emp_res = await db.execute(select(Empresa).where(Empresa.id == fac.empresa_id))
        emp = emp_res.scalars().first()
        if emp and emp.estat_pagament not in ("HIBERNANT", "ELIMINAT"):
            estat_ant = emp.estat_pagament
            emp.estat_pagament = "HIBERNANT"
            emp.updated_at = datetime.now(timezone.utc)
            db.add(
                SaasHistorialLlicencia(
                    empresa_id=emp.id,
                    quota_operaris_anterior=int(emp.quota_operaris or 5),
                    quota_operaris_nova=int(emp.quota_operaris or 5),
                    estat_anterior=estat_ant,
                    estat_nou="HIBERNANT",
                    motiu=f"Impagament factura {fac.serie}-{fac.numero_factura:05d} (Període de gràcia HIBERNANT)",
                )
            )
            empresa_hibernada = True

    await db.commit()
    out = _serialitzar_factura_b2b(fac)
    out["empresa_hibernada"] = empresa_hibernada
    return out


@router.get("/factures/{factura_id}/pdf")
async def descarregar_pdf_factura_b2b(
    factura_id: str,
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> FileResponse:
    """Descarrega el PDF oficial Veri*factu d'una factura B2B emesa."""
    try:
        f_uuid = uuid.UUID(factura_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="UUID de factura invàlid.")

    res = await db.execute(select(SaasFacturaB2B).where(SaasFacturaB2B.id == f_uuid))
    fac = res.scalars().first()
    if not fac or not fac.pdf_path or not os.path.exists(fac.pdf_path):
        raise HTTPException(status_code=404, detail="Fitxer PDF de la factura no trobat.")

    num_str = f"{fac.numero_factura:05d}" if fac.numero_factura else str(fac.id)[:8]
    return FileResponse(
        fac.pdf_path,
        media_type="application/pdf",
        filename=f"Factura_{fac.serie}_{num_str}.pdf",
    )


async def _comprovar_pc_local_empresa(node_ia_url: Optional[str]) -> bool:
    """Fa un ping ràpid a l'ordinador local de l'empresa per diagnosticar si està encès."""
    if not node_ia_url or not node_ia_url.strip():
        return False
    url = node_ia_url.strip()
    if not url.startswith("http"):
        url = f"http://{url}"
    try:
        async with httpx.AsyncClient(timeout=1.5) as client:
            resp = await client.get(url)
            return resp.status_code < 500
    except Exception:
        return False


def _serialitzar_tiquet(t: SaasTiquetSuport) -> Dict[str, Any]:
    return {
        "id": str(t.id),
        "empresa_id": str(t.empresa_id) if t.empresa_id else None,
        "empresa_nom_snapshot": t.empresa_nom_snapshot,
        "assumpte": t.assumpte,
        "descripcio": t.descripcio,
        "severitat": t.severitat,
        "prioritat": t.severitat,
        "estat": t.estat,
        "pc_empresa_online_al_crear": t.pc_empresa_online_al_crear,
        "diagnostic_automatic": t.diagnostic_automatic,
        "diagnostic_node": {
            "online": t.pc_empresa_online_al_crear,
            "advertencia": t.diagnostic_automatic if not t.pc_empresa_online_al_crear else None,
        },
        "resolucio_notes": t.resolucio_notes,
        "resolucio": t.resolucio_notes,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "resolved_at": t.resolved_at.isoformat() if t.resolved_at else None,
    }


@router.get("/tiquets", response_model=List[Dict[str, Any]])
async def llistar_tiquets_suport(
    empresa_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> List[Dict[str, Any]]:
    """Llista tots els tiquets d'incidència tècnica conservats al CRM."""
    stmt = select(SaasTiquetSuport).order_by(SaasTiquetSuport.created_at.desc())
    if empresa_id:
        try:
            emp_uuid = uuid.UUID(empresa_id)
            stmt = stmt.where(SaasTiquetSuport.empresa_id == emp_uuid)
        except ValueError:
            raise HTTPException(status_code=400, detail="UUID d'empresa invàlid.")

    res = await db.execute(stmt)
    return [_serialitzar_tiquet(t) for t in res.scalars().all()]


@router.post("/tiquets", status_code=status.HTTP_201_CREATED, response_model=Dict[str, Any])
async def crear_tiquet_suport(
    payload: TiquetSuportCreateRequest,
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> Dict[str, Any]:
    """Crea un tiquet d'incidència al CRM i diagnostica automàticament si l'ordinador del client està apagat."""
    try:
        emp_uuid = uuid.UUID(payload.empresa_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="UUID d'empresa invàlid.")

    emp_res = await db.execute(select(Empresa).where(Empresa.id == emp_uuid))
    emp = emp_res.scalars().first()
    if not emp:
        raise HTTPException(status_code=404, detail="Empresa no trobada.")

    pc_online = await _comprovar_pc_local_empresa(emp.node_ia_url)
    if not emp.node_ia_url:
        diagnostic = (
            "⚠️ L'empresa no té configurada cap adreça d'Ordinador Local (node_ia_url) o el té APAGAT. "
            "Qualsevol consulta a l'arxiu històric de plànols o IA local requerirà que encenguin i connectin el seu equip d'oficina."
        )
    elif not pc_online:
        diagnostic = (
            f"🔴 S'ha detectat automàticament que l'ordinador central del client ({emp.node_ia_url}) està APAGAT o sense connexió. "
            "Si l'operari no pot obrir un plànol extra no inclòs a l'OT d'avui, és responsabilitat de l'empresa encendre el seu ordinador d'oficina."
        )
    else:
        diagnostic = f"🟢 L'ordinador central del client ({emp.node_ia_url}) respon ONLINE en el moment d'obrir el tiquet."

    nou_tiquet = SaasTiquetSuport(
        empresa_id=emp.id,
        empresa_nom_snapshot=emp.nom,
        assumpte=payload.assumpte.strip(),
        descripcio=payload.descripcio.strip(),
        severitat=(payload.severitat or payload.prioritat or "NORMAL"),
        estat="OBERT",
        pc_empresa_online_al_crear=pc_online,
        diagnostic_automatic=diagnostic,
    )
    db.add(nou_tiquet)
    await db.commit()

    return _serialitzar_tiquet(nou_tiquet)


@router.patch("/tiquets/{tiquet_id}", response_model=Dict[str, Any])
async def actualitzar_tiquet_suport(
    tiquet_id: str,
    payload: TiquetSuportUpdateRequest,
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> Dict[str, Any]:
    """Actualitza l'estat o les notes de resolució d'un tiquet de suport."""
    try:
        t_uuid = uuid.UUID(tiquet_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="UUID de tiquet invàlid.")

    res = await db.execute(select(SaasTiquetSuport).where(SaasTiquetSuport.id == t_uuid))
    tiquet = res.scalars().first()
    if not tiquet:
        raise HTTPException(status_code=404, detail="Tiquet no trobat.")

    if payload.estat is not None:
        tiquet.estat = payload.estat
        if payload.estat in ("RESOLT", "TANCAT"):
            tiquet.resolved_at = datetime.now(timezone.utc)
    if payload.resolucio_notes is not None or payload.resolucio is not None:
        tiquet.resolucio_notes = payload.resolucio_notes or payload.resolucio
    if payload.severitat is not None or payload.prioritat is not None:
        tiquet.severitat = payload.severitat or payload.prioritat or tiquet.severitat

    await db.commit()
    return _serialitzar_tiquet(tiquet)
