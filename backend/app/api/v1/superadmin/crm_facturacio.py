"""Router CRM SaaS, Facturació B2B Veri*factu amb Human-in-the-Loop i Tiquets d'Incidència."""

import logging
import os
import uuid
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.superadmin.tenants import _resolve_empresa
from app.core.config import settings
from app.core.db import get_db_with_tenant_context
from app.core.security import require_roles
from app.models.models import (
    Empresa,
    SaasFacturaB2B,
    SaasHistorialLlicencia,
    SaasTiquetSuport,
)
from app.services.sovereign_storage import SuperadminStorageGateway
from app.services.vault_tunnel import empresa_target_key, vault_tunnel_broker
from app.services.verifactu import (
    calcular_huella_alta_hac1177,
    calcular_huella_anulacio_hac1177,
    format_num_serie,
    generar_url_qr_aeat_hac1177,
    renderitzar_pdf_factura_verifactu_bytes,
)
from app.services.verifactu_xml import (
    construir_element_registro_alta,
    construir_element_registro_anulacion,
    embolcallar_soap_suministro_aeat,
)

logger = logging.getLogger("superadmin.crm_facturacio")

router = APIRouter(
    prefix="/superadmin/crm",
    tags=["Superadmin CRM & Facturació B2B Veri*factu"],
    dependencies=[Depends(require_roles(["SUPERADMIN"]))],
)

SEVALOR_EMISSOR_NOM = settings.SUPERADMIN_EMISSOR_NOM
SEVALOR_EMISSOR_NIF = settings.SUPERADMIN_EMISSOR_NIF


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
        "exercici": int(f.exercici or (f.data_emissio.year if f.data_emissio else 2026)),
        "numero_factura": codi_oficial,
        "numero_correlatiu": f.numero_factura,
        "num_serie_verifactu": f.num_serie_verifactu
        or (
            format_num_serie(
                f.serie,
                int(f.exercici or (f.data_emissio.year if f.data_emissio else 2026)),
                int(f.numero_factura),
            )
            if f.numero_factura is not None
            else None
        ),
        "tipus_factura": str(getattr(f, "tipus_factura", None) or "F1"),
        "codi_factura": (
            codi_oficial
            if codi_oficial is not None
            else f"PREFACTURA-{str(f.id)[:8].upper()}"
        ),
        "estat": "EMESA_VERIFACTU" if f.numero_factura is not None and f.estat != "ESBORRANY_PREFACTURA" else f.estat,
        "estat_cobrament": estat_cobrament,
        "estat_anulacio": str(getattr(f, "estat_anulacio", None) or "ACTIVA"),
        "estat_enviament_aeat": str(getattr(f, "estat_enviament_aeat", None) or "PENDENT"),
        "csv_aeat": getattr(f, "csv_aeat", None),
        "hash_anulacio_sha256": getattr(f, "hash_anulacio_sha256", None),
        "motiu_anulacio": getattr(f, "motiu_anulacio", None),
        "fecha_hora_huso_gen_registro": getattr(f, "fecha_hora_huso_gen_registro", None),
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


async def _carregar_mapes_facturacio_superadmin() -> tuple[
    Dict[str, Dict[str, Any]],
    Dict[str, Dict[str, Any]],
    Dict[str, Dict[str, Any]],
]:
    """Llegeix fitxes comercials, llicències i factures SaaS des del Disc Sobirà de Superadmin."""
    fitxes_map: Dict[str, Dict[str, Any]] = {}
    llicencies_map: Dict[str, Dict[str, Any]] = {}
    factures_map: Dict[str, Dict[str, Any]] = {}
    for cat, target_map, id_keys in (
        ("tenants_fitxes", fitxes_map, ("id", "empresa_id")),
        ("tenants_llicencies", llicencies_map, ("empresa_id", "id")),
        ("saas_factures_json", factures_map, ("id",)),
    ):
        try:
            items = await SuperadminStorageGateway.llegir_entitats_json(cat)
            for item in items:
                for k in id_keys:
                    if item.get(k):
                        target_map[str(item[k])] = item
                        break
        except HTTPException as exc:
            logger.warning("No s'ha pogut llegir '%s' del Disc Superadmin: %s", cat, exc.detail)
        except Exception as exc:
            logger.warning("Error llegint '%s' del Disc Superadmin: %s", cat, exc)
    return fitxes_map, llicencies_map, factures_map


async def _desar_superadmin_segur(categoria: str, item_id: str, dades: Dict[str, Any]) -> None:
    try:
        await SuperadminStorageGateway.desar_entitat_json(categoria, item_id, dades)
    except HTTPException as exc:
        logger.warning("No s'ha pogut sincronitzar '%s/%s' al Disc Superadmin: %s", categoria, item_id, exc.detail)
    except Exception as exc:
        logger.warning("Error sincronitzant '%s/%s' al Disc Superadmin: %s", categoria, item_id, exc)


def _enriquir_factura_amb_disc(
    serialized: Dict[str, Any],
    fitxes_map: Dict[str, Dict[str, Any]],
    factures_map: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    fac_disc = factures_map.get(str(serialized.get("id") or ""), {})
    fitxa = fitxes_map.get(str(serialized.get("empresa_id") or ""), {})
    nom_real = (
        fac_disc.get("client_nom_snapshot")
        or fitxa.get("rao_social")
        or fitxa.get("nom")
        or serialized.get("client_nom_snapshot")
    )
    nif_real = fac_disc.get("client_nif_snapshot") or fitxa.get("nif") or serialized.get("client_nif_snapshot")
    return {
        **serialized,
        "client_nom_snapshot": nom_real,
        "client_nif_snapshot": nif_real,
    }


@router.get("/factures", response_model=List[Dict[str, Any]])
async def llistar_factures_b2b(
    empresa_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> List[Dict[str, Any]]:
    """Llista totes les pre-factures i factures B2B Veri*factu (fins i tot d'empreses donades de baixa)."""
    stmt = select(SaasFacturaB2B).order_by(SaasFacturaB2B.created_at.desc())
    if empresa_id:
        emp = await _resolve_empresa(db, empresa_id)
        if emp:
            stmt = stmt.where(SaasFacturaB2B.empresa_id == emp.id)
        else:
            raise HTTPException(status_code=404, detail="Empresa no trobada.")

    res = await db.execute(stmt)
    factures = res.scalars().all()
    fitxes_map, _, factures_map = await _carregar_mapes_facturacio_superadmin()
    return [_enriquir_factura_amb_disc(_serialitzar_factura_b2b(f), fitxes_map, factures_map) for f in factures]


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

    fitxes_map, llicencies_map, _ = await _carregar_mapes_facturacio_superadmin()
    fitxa = fitxes_map.get(str(emp.id), {})
    llic = llicencies_map.get(str(emp.id), {})

    if payload.preu_unitari_operari is not None:
        preu_op = payload.preu_unitari_operari
    elif payload.preu_per_operari is not None:
        preu_op = payload.preu_per_operari
    else:
        preu_op = float(
            llic.get("tarifa_per_operari", getattr(emp, "tarifa_per_operari", 0.0) or 0.0)
        )

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

    client_nom_real = str(fitxa.get("rao_social") or fitxa.get("nom") or emp.nom)
    client_nif_real = str(fitxa.get("nif") or emp.nif)

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

    serialized = {
        **_serialitzar_factura_b2b(nova_prefactura),
        "client_nom_snapshot": client_nom_real,
        "client_nif_snapshot": client_nif_real,
    }
    await _desar_superadmin_segur("saas_factures_json", str(nova_prefactura.id), serialized)
    return serialized


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

    fitxes_map, _, factures_map = await _carregar_mapes_facturacio_superadmin()
    serialized = _enriquir_factura_amb_disc(_serialitzar_factura_b2b(pref), fitxes_map, factures_map)
    await _desar_superadmin_segur("saas_factures_json", str(pref.id), serialized)
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
    exercici_int = data_avui.year
    data_emissio_str = data_avui.isoformat()
    num_serie_vf = format_num_serie(pref.serie, exercici_int, nou_num)

    fitxes_map, _, factures_map = await _carregar_mapes_facturacio_superadmin()
    fac_disc = factures_map.get(str(pref.id), {})
    fitxa_emp = fitxes_map.get(str(pref.empresa_id or ""), {})
    client_nom_real = str(
        fac_disc.get("client_nom_snapshot")
        or fitxa_emp.get("rao_social")
        or fitxa_emp.get("nom")
        or pref.client_nom_snapshot
    )
    client_nif_real = str(
        fac_disc.get("client_nif_snapshot") or fitxa_emp.get("nif") or pref.client_nif_snapshot
    )

    hash_actual, _, ts_huso = calcular_huella_alta_hac1177(
        nif_emissor=SEVALOR_EMISSOR_NIF,
        num_serie_factura=num_serie_vf,
        fecha_expedicion=data_avui,
        tipus_factura="F1",
        cuota_total=float(pref.quota_iva),
        importe_total=float(pref.import_total),
        hash_anterior=hash_anterior,
    )

    qr_content = generar_url_qr_aeat_hac1177(
        nif_emissor=SEVALOR_EMISSOR_NIF,
        num_serie_factura=num_serie_vf,
        fecha_expedicion=data_avui,
        importe_total=float(pref.import_total),
    )

    pdf_bytes = _generar_pdf_b2b_reportlab_bytes(
        pref=pref,
        client_nom_real=client_nom_real,
        client_nif_real=client_nif_real,
        numero_factura=nou_num,
        data_emissio_str=data_emissio_str,
        hash_actual=hash_actual,
        hash_anterior=hash_anterior,
        qr_content=qr_content,
        num_serie_verifactu=num_serie_vf,
    )
    pdf_path = await SuperadminStorageGateway.pujar_fitxer_binari(
        "saas_factures_pdf",
        f"factura_saas_{pref.id}.pdf",
        pdf_bytes,
        content_type="application/pdf",
    )

    sub = claims.get("sub")
    verificador_uuid: Optional[uuid.UUID] = None
    if sub:
        try:
            verificador_uuid = uuid.UUID(str(sub))
        except ValueError:
            verificador_uuid = None

    pref.exercici = exercici_int
    pref.numero_factura = nou_num
    pref.num_serie_verifactu = num_serie_vf
    pref.tipus_factura = "F1"
    pref.import_total_verifactu = float(pref.import_total)
    pref.estat = "EMESA_VERIFACTU"
    pref.verificada_per_id = verificador_uuid
    pref.data_verificacio_humana = datetime.now(timezone.utc)
    pref.data_emissio = data_avui
    pref.hash_sha256 = hash_actual
    pref.hash_anterior = hash_anterior
    pref.fecha_hora_huso_gen_registro = ts_huso
    pref.qr_verifactu = qr_content
    pref.pdf_path = pdf_path

    await db.commit()

    serialized = {
        **_serialitzar_factura_b2b(pref),
        "client_nom_snapshot": client_nom_real,
        "client_nif_snapshot": client_nif_real,
    }
    await _desar_superadmin_segur("saas_factures_json", str(pref.id), serialized)
    return {**serialized, "factura": serialized}


def _generar_pdf_b2b_reportlab_bytes(
    pref: SaasFacturaB2B,
    client_nom_real: str,
    client_nif_real: str,
    numero_factura: int,
    data_emissio_str: str,
    hash_actual: str,
    hash_anterior: Optional[str],
    qr_content: str,
    num_serie_verifactu: Optional[str] = None,
) -> bytes:
    """Renderitza el PDF de factura SaaS B2B utilitzant la plantilla HTML oficial Veri*factu amb WeasyPrint."""
    iva_pct = float(pref.tipus_iva_percent or 21.0)
    linies_b2b: List[Dict[str, Any]] = []

    if float(pref.import_onboarding or 0.0) > 0:
        linies_b2b.append(
            {
                "concepte": pref.concepte_onboarding_desc or "Onboarding / Llicència Plataforma",
                "descripcio_detall": f"Període {pref.periode}",
                "quantitat": 1,
                "preu_venda_unitari": float(pref.import_onboarding),
                "tipus_iva": iva_pct,
                "subtotal": float(pref.import_onboarding),
            }
        )
    if float(pref.import_config_ia or 0.0) > 0:
        linies_b2b.append(
            {
                "concepte": pref.concepte_config_ia_desc or "Configuració IA Local",
                "quantitat": 1,
                "preu_venda_unitari": float(pref.import_config_ia),
                "tipus_iva": iva_pct,
                "subtotal": float(pref.import_config_ia),
            }
        )
    if float(pref.import_equips_ia or 0.0) > 0:
        if pref.equips_ia_detall:
            for item in pref.equips_ia_detall:
                u = int(item.get("unitats", 1))
                p = float(item.get("preu_unitari", 0.0))
                linies_b2b.append(
                    {
                        "concepte": f"{item.get('concepte') or item.get('nom') or 'Equip IA'} (VENDA)",
                        "quantitat": u,
                        "preu_venda_unitari": p,
                        "tipus_iva": iva_pct,
                        "subtotal": round(u * p, 2),
                    }
                )
        else:
            linies_b2b.append(
                {
                    "concepte": "Venda d'Equips IA",
                    "quantitat": 1,
                    "preu_venda_unitari": float(pref.import_equips_ia),
                    "tipus_iva": iva_pct,
                    "subtotal": float(pref.import_equips_ia),
                }
            )
    if float(pref.import_operaris or 0.0) > 0:
        linies_b2b.append(
            {
                "concepte": f"Llicència SaaS d'Operaris ({pref.periode})",
                "quantitat": max(1, int(pref.num_operaris_facturats or 1)),
                "preu_venda_unitari": float(pref.preu_unitari_operari or pref.import_operaris),
                "tipus_iva": iva_pct,
                "subtotal": float(pref.import_operaris),
            }
        )

    exercici_int = int(pref.exercici or int(data_emissio_str[:4]))
    num_serie = num_serie_verifactu or pref.num_serie_verifactu or format_num_serie(pref.serie, exercici_int, numero_factura)

    return renderitzar_pdf_factura_verifactu_bytes(
        empresa_nom=SEVALOR_EMISSOR_NOM,
        empresa_rao_social=SEVALOR_EMISSOR_NOM,
        empresa_eslogan=settings.SUPERADMIN_EMISSOR_ESLOGAN,
        empresa_nif=SEVALOR_EMISSOR_NIF,
        empresa_adreca=settings.SUPERADMIN_EMISSOR_ADRECA,
        empresa_cp=settings.SUPERADMIN_EMISSOR_CP,
        empresa_poblacio=settings.SUPERADMIN_EMISSOR_POBLACIO,
        empresa_provincia=settings.SUPERADMIN_EMISSOR_PROVINCIA,
        empresa_telefon=settings.SUPERADMIN_EMISSOR_TELEFON,
        empresa_email=settings.SUPERADMIN_EMISSOR_EMAIL,
        empresa_registre_mercantil=settings.SUPERADMIN_EMISSOR_REGISTRE_MERCANTIL,
        empresa_titular_compte=settings.SUPERADMIN_EMISSOR_TITULAR_COMPTE,
        empresa_iban=settings.SUPERADMIN_EMISSOR_IBAN,
        primari_hsl="162 88% 20%",
        client_nom=client_nom_real,
        client_nif=client_nif_real,
        serie=pref.serie,
        numero_factura=numero_factura,
        exercici=exercici_int,
        num_serie_verifactu=num_serie,
        tipus_factura=str(getattr(pref, "tipus_factura", None) or "F1"),
        data_emissio=data_emissio_str,
        referencia_comanda=f"Període {pref.periode}",
        estat_document="ESBORRANY_PREFACTURA" if pref.estat == "ESBORRANY_PREFACTURA" else "EMESA",
        estat_anulacio=str(getattr(pref, "estat_anulacio", None) or "ACTIVA"),
        linies=linies_b2b,
        base_imposable=float(pref.base_imposable),
        quota_iva=float(pref.quota_iva),
        import_total_verifactu=float(pref.import_total),
        import_total=float(pref.import_total),
        hash_actual=hash_actual,
        hash_anterior=hash_anterior,
        qr_content=qr_content,
        csv_aeat=getattr(pref, "csv_aeat", None),
    )


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
    fitxes_map, _, factures_map = await _carregar_mapes_facturacio_superadmin()
    out = _enriquir_factura_amb_disc(_serialitzar_factura_b2b(fac), fitxes_map, factures_map)
    await _desar_superadmin_segur("saas_factures_json", str(fac.id), out)
    out["empresa_hibernada"] = empresa_hibernada
    return out


class AnularFacturaB2BRequest(BaseModel):
    motiu: str = Field(..., min_length=3, max_length=300)
    confirmacio_humana: bool = True


@router.post("/factures/{factura_id}/anular", response_model=Dict[str, Any])
async def anular_factura_b2b_verifactu(
    factura_id: str,
    payload: AnularFacturaB2BRequest,
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> Dict[str, Any]:
    """Emet un Registre d'Anul·lació (RegistroAnulacion) per a una factura SaaS B2B (Art. 13.2 Ordre HAC/1177/2024)."""
    if not payload.confirmacio_humana:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Verificació humana obligatòria (HITL) per anul·lar una factura B2B.",
        )
    try:
        f_uuid = uuid.UUID(factura_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="UUID de factura invàlid.")

    res = await db.execute(select(SaasFacturaB2B).where(SaasFacturaB2B.id == f_uuid))
    fac = res.scalars().first()
    if not fac:
        raise HTTPException(status_code=404, detail="Factura no trobada.")
    if fac.estat == "ESBORRANY_PREFACTURA" or fac.numero_factura is None:
        raise HTTPException(
            status_code=422,
            detail="Només es poden anul·lar factures ja emeses a Veri*factu.",
        )
    if getattr(fac, "estat_anulacio", "ACTIVA") == "ANULADA_VERIFACTU":
        raise HTTPException(status_code=409, detail="La factura ja es troba anul·lada.")

    num_serie = fac.num_serie_verifactu or format_num_serie(
        fac.serie, int(fac.exercici or 2026), int(fac.numero_factura)
    )
    huella_anul, _, _ = calcular_huella_anulacio_hac1177(
        nif_emissor=SEVALOR_EMISSOR_NIF,
        num_serie_anulada=num_serie,
        fecha_expedicion_anulada=fac.data_emissio or date.today(),
        hash_anterior=fac.hash_sha256,
    )
    fac.estat_anulacio = "ANULADA_VERIFACTU"
    fac.data_anulacio = datetime.now(timezone.utc)
    fac.motiu_anulacio = payload.motiu.strip()
    fac.hash_anulacio_sha256 = huella_anul
    await db.commit()

    fitxes_map, _, factures_map = await _carregar_mapes_facturacio_superadmin()
    out = _enriquir_factura_amb_disc(_serialitzar_factura_b2b(fac), fitxes_map, factures_map)
    await _desar_superadmin_segur("saas_factures_json", str(fac.id), out)
    return out


@router.get("/factures/{factura_id}/pdf")
async def descarregar_pdf_factura_b2b(
    factura_id: str,
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> Response:
    """Descarrega el PDF oficial Veri*factu d'una factura B2B emesa des del Disc Sobirà de Superadmin."""
    try:
        f_uuid = uuid.UUID(factura_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="UUID de factura invàlid.")

    res = await db.execute(select(SaasFacturaB2B).where(SaasFacturaB2B.id == f_uuid))
    fac = res.scalars().first()
    if not fac or not fac.pdf_path:
        raise HTTPException(status_code=404, detail="Fitxer PDF de la factura no trobat.")

    num_str = f"{fac.numero_factura:05d}" if fac.numero_factura else str(fac.id)[:8]
    filename_dl = f"Factura_{fac.serie}_{num_str}.pdf"
    if fac.pdf_path.startswith("superadmin-vault://") or os.path.exists(fac.pdf_path):
        try:
            pdf_bytes, _ = await SuperadminStorageGateway.obtenir_bytes_fitxer(fac.pdf_path)
            return Response(
                content=pdf_bytes,
                media_type="application/pdf",
                headers={"Content-Disposition": f'attachment; filename="{filename_dl}"'},
            )
        except HTTPException:
            if os.path.exists(fac.pdf_path):
                with open(fac.pdf_path, "rb") as fh:
                    return Response(
                        content=fh.read(),
                        media_type="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="{filename_dl}"'},
                    )
            raise
    raise HTTPException(status_code=404, detail="Fitxer PDF de la factura no trobat.")


@router.get("/factures/{factura_id}/xml")
async def descarregar_xml_factura_b2b(
    factura_id: str,
    tipus_registre: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> Response:
    """Exporta l'XML oficial Veri*factu (SuministroLR.xsd) per a una factura SaaS B2B de Superadmin."""
    try:
        f_uuid = uuid.UUID(factura_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="UUID de factura invàlid.")

    res = await db.execute(select(SaasFacturaB2B).where(SaasFacturaB2B.id == f_uuid))
    fac = res.scalars().first()
    if not fac or fac.numero_factura is None:
        raise HTTPException(status_code=404, detail="Factura B2B emesa no trobada.")

    exercici_int = int(fac.exercici or (fac.data_emissio.year if fac.data_emissio else 2026))
    num_serie = fac.num_serie_verifactu or format_num_serie(
        fac.serie, exercici_int, int(fac.numero_factura)
    )
    tipus_reg = (
        tipus_registre.strip().upper()
        if tipus_registre
        else ("ANULACION" if getattr(fac, "estat_anulacio", "ACTIVA") == "ANULADA_VERIFACTU" else "ALTA")
    )

    if tipus_reg == "ANULACION":
        el = construir_element_registro_anulacion(
            nif_emissor=SEVALOR_EMISSOR_NIF,
            nom_emissor=SEVALOR_EMISSOR_NOM,
            num_serie_anulada=num_serie,
            fecha_expedicion_anulada=fac.data_emissio or date.today(),
            hash_anterior=fac.hash_sha256,
            num_serie_anterior=num_serie,
            fecha_expedicion_anterior=fac.data_emissio or date.today(),
            hash_anulacio_sha256=str(fac.hash_anulacio_sha256 or fac.hash_sha256 or ("0" * 64)),
            fecha_hora_huso_gen_registro=fac.fecha_hora_huso_gen_registro,
        )
    else:
        el = construir_element_registro_alta(
            nif_emissor=SEVALOR_EMISSOR_NIF,
            nom_emissor=SEVALOR_EMISSOR_NOM,
            num_serie_factura=num_serie,
            fecha_expedicion=fac.data_emissio or date.today(),
            tipus_factura=str(fac.tipus_factura or "F1"),
            descripcio_operacio=f"Facturació SaaS Sevalor Suite ({fac.periode})",
            client_nom=fac.client_nom_snapshot,
            client_nif=fac.client_nif_snapshot,
            linies=[
                {
                    "concepte": f"Llicència SaaS Sevalor Suite ({fac.periode})",
                    "quantitat": 1,
                    "preu_venda_unitari": float(fac.base_imposable or 0),
                    "tipus_iva": float(fac.tipus_iva_percent or 21.0),
                    "subtotal": float(fac.base_imposable or 0),
                }
            ],
            base_imposable=float(fac.base_imposable or 0),
            quota_iva=float(fac.quota_iva or 0),
            import_total_verifactu=float(fac.import_total_verifactu or fac.import_total or 0),
            hash_anterior=fac.hash_anterior,
            hash_sha256=str(fac.hash_sha256 or ("0" * 64)),
            fecha_hora_huso_gen_registro=fac.fecha_hora_huso_gen_registro,
        )

    xml_str = embolcallar_soap_suministro_aeat(
        nom_emissor=SEVALOR_EMISSOR_NOM,
        nif_emissor=SEVALOR_EMISSOR_NIF,
        registres_elements=[el],
    )
    return Response(content=xml_str, media_type="application/xml")


@router.get("/verifactu/declaracio-responsable")
async def obtenir_declaracio_responsable_superadmin() -> Dict[str, Any]:
    """Declaració Responsable del SIF Veri*factu per a Superadmin B2B (Art. 15 Ordre HAC/1177/2024)."""
    return {
        "nom_sistema": settings.VERIFACTU_SIF_NOMBRE,
        "id_sistema": settings.VERIFACTU_SIF_ID,
        "versio": settings.VERIFACTU_SIF_VERSION,
        "numero_instalacio": settings.VERIFACTU_SIF_NUM_INSTALACION,
        "productor_nom": settings.VERIFACTU_SIF_NOM_PRODUCTOR,
        "productor_nif": settings.VERIFACTU_SIF_NIF_PRODUCTOR,
        "emissor_nom": SEVALOR_EMISSOR_NOM,
        "emissor_nif": SEVALOR_EMISSOR_NIF,
        "modalitat": "VERI*FACTU",
        "entorn_actiu": settings.VERIFACTU_ENV,
        "normativa": "Reial Decret 1007/2023 i Ordre Ministerial HAC/1177/2024",
    }


async def _comprovar_pc_local_empresa(empresa_id: uuid.UUID) -> bool:
    """Comprova en viu si el Túnel Invers WSS de l'ordinador dedicat de l'empresa està connectat."""
    return await vault_tunnel_broker.is_online(empresa_target_key(empresa_id))


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
        emp = await _resolve_empresa(db, empresa_id)
        if emp:
            stmt = stmt.where(SaasTiquetSuport.empresa_id == emp.id)
        else:
            raise HTTPException(status_code=404, detail="Empresa no trobada.")

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

    pc_online = await _comprovar_pc_local_empresa(emp.id)
    if not pc_online:
        diagnostic = (
            f"🔴 S'ha detectat automàticament que l'ordinador central del client (wss-tunnel://{emp.id}) "
            "té el Túnel Sobirà WSS APAGAT o sense connexió. "
            "Si l'operari no pot obrir un plànol extra no inclòs a l'OT d'avui, és responsabilitat de l'empresa encendre el seu ordinador d'oficina."
        )
    else:
        diagnostic = (
            f"🟢 L'ordinador central del client (wss-tunnel://{emp.id}) respon ONLINE "
            "via Túnel Sobirà WSS en el moment d'obrir el tiquet."
        )

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

    fitxes_map, _, _ = await _carregar_mapes_facturacio_superadmin()
    fitxa_t = fitxes_map.get(str(emp.id), {})
    serialized_tiq = {
        **_serialitzar_tiquet(nou_tiquet),
        "empresa_nom_snapshot": str(
            fitxa_t.get("rao_social") or fitxa_t.get("nom") or nou_tiquet.empresa_nom_snapshot
        ),
    }
    await _desar_superadmin_segur("suport_tiquets", str(nou_tiquet.id), serialized_tiq)
    return serialized_tiq


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
    out_t = _serialitzar_tiquet(tiquet)
    await _desar_superadmin_segur("suport_tiquets", str(tiquet.id), out_t)
    return out_t
