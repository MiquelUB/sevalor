import os
import uuid
import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Sequence

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_with_tenant_context, set_tenant_context
from app.core.security import get_current_user_claims, require_financial_access, require_roles
from app.models.models import (
    Client,
    DespesaComptable,
    Empresa,
    FacturaCapcalera,
    FacturaLinia,
    OrdreTreball,
)
from app.schemas.comptabilitat import (
    Art80ItemDTO,
    Art80ReclamacioRequestDTO,
    ClientRiscSanititzatDTO,
    ContracteMRRAuditoriaDTO,
    DashboardEconomicResponseDTO,
    DespesaComptableDTO,
    FacturaEmissioCreateDTO,
    FacturaLiniaCreateDTO,
    FacturaLiniaDetailDTO,
    Norma43ConciliarRequestDTO,
    Norma43MovimentDTO,
    OperariCostEfectiuDTO,
    OTCostMargeDTO,
    OverrideRiscRequestDTO,
    PrefacturaEmetreDTO,
    PrefacturaUpdateDTO,
    RetencioGarantiaDTO,
    TiquetAuditoriaRequestDTO,
    TiquetDespesaResponseDTO,
    WIPControlResponseDTO,
)
from app.services.barema_service import resoldre_preu_hora_control_panel
from app.services.economic_suite_service import (
    ESTATS_OT_PENDENTS_PREFACTURACIO,
    EconomicSuiteService,
)
from app.services.magatzem_comptabilitat_service import calcular_cost_i_marge_analitic_ot
from app.services.outbox_aeat import registrar_enviament_outbox
from app.services.sovereign_storage import SovereignStorageGateway
from app.services.verifactu import generar_factura_pdf, renderitzar_pdf_factura_verifactu

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
    client_nom: Optional[str] = None
    estat_document: str = "EMESA"
    data_emissio: Optional[datetime] = None
    data_venciment: Optional[date] = None
    metode_pagament: str = "TRANSFERENCIA"
    es_inversio_subjecte_passiu: bool = False
    base_imposable: float = 0.0
    quota_iva: float = 0.0
    import_retencio: float = 0.0
    import_retencio_garantia_4308: float = 0.0
    import_suplits: float = 0.0
    liquid_exigible: float = 0.0
    hash_sha256: str
    hash_anterior: Optional[str] = None
    pdf_path: Optional[str] = None
    estat_cobrament: str
    estat_enviament: str
    linies: List[FacturaLiniaDetailDTO] = []
    ordres_treball_codis: List[str] = []


async def _serialitzar_factures(
    db: AsyncSession,
    emp_uuid: uuid.UUID,
    factures: Sequence[FacturaCapcalera],
) -> List[FacturaResponse]:
    if not factures:
        return []
    fact_ids = [f.id for f in factures]
    client_ids = list({f.client_id for f in factures})

    cli_rows = (
        await db.execute(
            select(Client.id, Client.rao_social).where(
                Client.empresa_id == emp_uuid,
                Client.id.in_(client_ids),
            )
        )
    ).all()
    cli_map = {cid: rao for cid, rao in cli_rows}

    lin_rows = (
        await db.execute(
            select(FacturaLinia)
            .where(
                FacturaLinia.empresa_id == emp_uuid,
                FacturaLinia.factura_id.in_(fact_ids),
            )
            .order_by(FacturaLinia.created_at.asc())
        )
    ).scalars().all()
    lin_map: Dict[uuid.UUID, List[FacturaLiniaDetailDTO]] = {}
    obra_ids_set: set[uuid.UUID] = set()
    for lin in lin_rows:
        if lin.obra_id:
            obra_ids_set.add(lin.obra_id)
        lin_map.setdefault(lin.factura_id, []).append(
            FacturaLiniaDetailDTO(
                id=lin.id,
                obra_id=lin.obra_id,
                centre_de_cost_id=lin.centre_de_cost_id or "CC-GENERAL",
                article_id=lin.article_id,
                concepte=lin.concepte,
                compte_pgc=lin.compte_pgc or "700000",
                quantitat=float(lin.quantitat or 0),
                quantitat_merma=float(lin.quantitat_merma or 0),
                preu_venda_unitari=float(lin.preu_venda_unitari or 0),
                descompte_aplicat_pct=float(lin.descompte_aplicat_pct or 0),
                tipus_iva=float(lin.tipus_iva or 0),
                subtotal=float(lin.subtotal or 0),
            )
        )

    ot_rows = (
        await db.execute(
            select(OrdreTreball.id, OrdreTreball.codi, OrdreTreball.factura_id).where(
                OrdreTreball.empresa_id == emp_uuid,
                (OrdreTreball.factura_id.in_(fact_ids))
                | (OrdreTreball.id.in_(list(obra_ids_set)) if obra_ids_set else False),
            )
        )
    ).all()
    ot_codis_by_fact: Dict[uuid.UUID, List[str]] = {}
    ot_codi_by_id = {oid: codi for oid, codi, _ in ot_rows}
    for _, codi, fid in ot_rows:
        if fid and codi not in ot_codis_by_fact.setdefault(fid, []):
            ot_codis_by_fact[fid].append(codi)
    for fid, lins in lin_map.items():
        for lin_dto in lins:
            if lin_dto.obra_id and lin_dto.obra_id in ot_codi_by_id:
                codi = ot_codi_by_id[lin_dto.obra_id]
                if codi not in ot_codis_by_fact.setdefault(fid, []):
                    ot_codis_by_fact[fid].append(codi)

    return [
        FacturaResponse(
            id=f.id,
            numero_factura=f.numero_factura,
            serie=f.serie,
            client_id=f.client_id,
            client_nom=cli_map.get(f.client_id),
            estat_document=f.estat_document,
            data_emissio=f.data_emissio,
            data_venciment=f.data_venciment,
            metode_pagament=f.metode_pagament,
            es_inversio_subjecte_passiu=bool(f.es_inversio_subjecte_passiu),
            base_imposable=float(f.base_imposable or 0),
            quota_iva=float(f.quota_iva or 0),
            import_retencio=float(f.import_retencio or 0),
            import_retencio_garantia_4308=float(f.import_retencio_garantia_4308 or 0),
            import_suplits=float(f.import_suplits or 0),
            liquid_exigible=float(f.liquid_exigible or 0),
            hash_sha256=f.hash_sha256,
            hash_anterior=f.hash_anterior,
            pdf_path=f.pdf_path,
            estat_cobrament=f.estat_cobrament,
            estat_enviament=f.estat_enviament,
            linies=lin_map.get(f.id, []),
            ordres_treball_codis=ot_codis_by_fact.get(f.id, []),
        )
        for f in factures
    ]


@router.get("/factures", response_model=List[FacturaResponse])
async def llistar_factures(
    request: Request, db: AsyncSession = Depends(get_db_with_tenant_context)
) -> List[FacturaResponse]:
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401)

    emp_uuid = uuid.UUID(empresa_id)
    stmt = (
        select(FacturaCapcalera)
        .where(FacturaCapcalera.empresa_id == emp_uuid)
        .order_by(FacturaCapcalera.created_at.desc())
    )
    factures = (await db.execute(stmt)).scalars().all()
    return await _serialitzar_factures(db, emp_uuid, factures)


@router.get("/prefactures", response_model=List[FacturaResponse])
async def llistar_prefactures(
    request: Request, db: AsyncSession = Depends(get_db_with_tenant_context)
) -> List[FacturaResponse]:
    """Llista totes les pre-factures editables pendents de validació humana (ESBORRANY_PREFACTURA)."""
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401)

    emp_uuid = uuid.UUID(empresa_id)
    stmt = (
        select(FacturaCapcalera)
        .where(
            FacturaCapcalera.empresa_id == emp_uuid,
            FacturaCapcalera.estat_document == "ESBORRANY_PREFACTURA",
        )
        .order_by(FacturaCapcalera.created_at.desc())
    )
    factures = (await db.execute(stmt)).scalars().all()
    return await _serialitzar_factures(db, emp_uuid, factures)


@router.get("/factures/{factura_id}", response_model=FacturaResponse)
async def obtenir_detall_factura(
    factura_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> FacturaResponse:
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401)
    emp_uuid = uuid.UUID(empresa_id)
    factura = (
        await db.execute(
            select(FacturaCapcalera).where(
                FacturaCapcalera.id == factura_id,
                FacturaCapcalera.empresa_id == emp_uuid,
            )
        )
    ).scalar_one_or_none()
    if not factura:
        raise HTTPException(status_code=404, detail="Factura no trobada.")
    return (await _serialitzar_factures(db, emp_uuid, [factura]))[0]


@router.post("/factures", response_model=FacturaResponse, status_code=status.HTTP_201_CREATED)
async def crear_factura(
    request: Request, payload: FacturaCreate, db: AsyncSession = Depends(get_db_with_tenant_context)
) -> FacturaCapcalera:
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401)

    # Validar client
    stmt_c = select(Client).where(
        Client.id == payload.client_id, Client.empresa_id == uuid.UUID(empresa_id)
    )
    if not (await db.execute(stmt_c)).scalars().first():
        raise HTTPException(status_code=404, detail="Client no trobat")

    # Validar duplicat num + serie
    stmt_dup = select(FacturaCapcalera).where(
        FacturaCapcalera.empresa_id == uuid.UUID(empresa_id),
        FacturaCapcalera.numero_factura == payload.numero_factura,
        FacturaCapcalera.serie == payload.serie,
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
    import_total = (
        payload.base_imposable
        + payload.quota_iva
        + payload.import_suplits
        - payload.import_retencio
    )

    # Ruta temporal per al PDF de generació
    temp_dir = "/tmp/sevalor_factures_temp"
    os.makedirs(temp_dir, exist_ok=True)
    nom_pdf = f"FACTURA_{payload.serie}_{payload.numero_factura:05d}_{data_emissio}.pdf"
    ruta_pdf_temp = os.path.join(temp_dir, f"{uuid.uuid4()}_{nom_pdf}")

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
        ruta_desti=ruta_pdf_temp,
    )

    hash_actual = resultat_pdf["hash_sha256"]
    hash_ant = resultat_pdf["hash_anterior"]

    # Enviar PDF directament al disc dur del client (Passarel·la Sobirana)
    with open(ruta_pdf_temp, "rb") as f:
        pdf_bytes = f.read()

    ruta_pdf_sobirana = await SovereignStorageGateway.pujar_fitxer_binari(
        db=db,
        empresa_id=empresa_id,
        categoria="factures_pdf",
        nom_fitxer=nom_pdf,
        content=pdf_bytes,
        content_type="application/pdf",
    )

    # Netejar de la memòria d'Hetzner (Zero-Storage Retention)
    try:
        os.remove(ruta_pdf_temp)
    except OSError:
        pass

    # Sincronitzar la fitxa JSON de la factura al disc dur del client
    await SovereignStorageGateway.desar_entitat_json(
        db=db,
        empresa_id=empresa_id,
        categoria="factures_pdf",
        item_id=f"FACTURA_{payload.serie}_{payload.numero_factura:05d}",
        dades={
            "serie": payload.serie,
            "numero_factura": payload.numero_factura,
            "client_nom": client_nom,
            "client_nif": client_nif,
            "base_imposable": payload.base_imposable,
            "quota_iva": payload.quota_iva,
            "liquid_exigible": import_total,
            "data_emissio": data_emissio,
            "hash_sha256": hash_actual,
            "hash_anterior": hash_ant,
            "pdf_path": ruta_pdf_sobirana,
        },
    )

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
        pdf_path=ruta_pdf_sobirana,
        estat_cobrament="PENDENT",
        estat_enviament="PENDENT",
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
        ruta_pdf=ruta_pdf_sobirana,
        db_session=db,
    )

    return nova_factura


@router.get("/factures/{factura_id}/pdf")
async def descarregar_factura_pdf(
    factura_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> Response:
    """Serveix el PDF de la factura (o pre-factura en esborrany) des del disc dur del client o el genera en temps real."""
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401)

    emp_uuid = uuid.UUID(empresa_id)
    stmt = select(FacturaCapcalera).where(
        FacturaCapcalera.id == factura_id, FacturaCapcalera.empresa_id == emp_uuid
    )
    factura = (await db.execute(stmt)).scalars().first()
    if not factura:
        raise HTTPException(status_code=404, detail="Factura no trobada")

    if factura.pdf_path and factura.estat_document != "ESBORRANY_PREFACTURA":
        return await SovereignStorageGateway.servir_fitxer(
            db=db,
            empresa_id=empresa_id,
            fitxer_path=factura.pdf_path,
            media_type="application/pdf",
            disposition="inline",
        )

    emp = (await db.execute(select(Empresa).where(Empresa.id == emp_uuid))).scalar_one_or_none()
    cli = (
        await db.execute(
            select(Client).where(Client.id == factura.client_id, Client.empresa_id == emp_uuid)
        )
    ).scalar_one_or_none()
    linies = (
        await db.execute(
            select(FacturaLinia)
            .where(FacturaLinia.factura_id == factura.id, FacturaLinia.empresa_id == emp_uuid)
            .order_by(FacturaLinia.created_at.asc())
        )
    ).scalars().all()

    temp_dir = "/tmp/sevalor_factures_temp"
    os.makedirs(temp_dir, exist_ok=True)
    data_em_str = (
        factura.data_emissio.strftime("%Y-%m-%d")
        if isinstance(factura.data_emissio, datetime)
        else str(factura.data_emissio)
    )
    ruta_tmp = os.path.join(temp_dir, f"{uuid.uuid4()}_{factura.serie}_{factura.numero_factura}.pdf")
    try:
        renderitzar_pdf_factura_verifactu(
            empresa_nom=emp.nom if emp else "Sevalor Suite",
            empresa_nif=emp.nif if emp else "B00000000",
            primari_hsl=emp.primari_hsl if emp else "150 40 20",
            client_nom=cli.rao_social if cli else "Client",
            client_nif=cli.nif if cli else "00000000X",
            serie=str(factura.serie),
            numero_factura=int(factura.numero_factura),
            data_emissio=data_em_str,
            data_venciment=factura.data_venciment.isoformat() if factura.data_venciment else None,
            estat_document=str(factura.estat_document),
            linies=list(linies),
            base_imposable=float(factura.base_imposable or 0),
            quota_iva=float(factura.quota_iva or 0),
            import_suplits=float(factura.import_suplits or 0),
            import_retencio=float(factura.import_retencio or 0),
            import_retencio_garantia=float(factura.import_retencio_garantia_4308 or 0),
            import_total=float(factura.liquid_exigible or 0),
            es_isp=bool(factura.es_inversio_subjecte_passiu),
            hash_actual=str(factura.hash_sha256 or ""),
            hash_anterior=factura.hash_anterior,
            qr_content=factura.qr_verifactu_payload,
            ruta_desti=ruta_tmp,
        )
        with open(ruta_tmp, "rb") as f_bin:
            pdf_bytes = f_bin.read()
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'inline; filename="FACTURA_{factura.serie}_{factura.numero_factura:04d}.pdf"'
            },
        )
    finally:
        try:
            if os.path.exists(ruta_tmp):
                os.remove(ruta_tmp)
        except OSError:
            pass


@router.get("/factures/{factura_id}/xml")
async def exportar_factura_xml(
    factura_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db_with_tenant_context)
) -> Response:
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401)

    stmt = select(FacturaCapcalera).where(
        FacturaCapcalera.id == factura_id, FacturaCapcalera.empresa_id == uuid.UUID(empresa_id)
    )
    factura = (await db.execute(stmt)).scalars().first()
    if not factura:
        raise HTTPException(status_code=404, detail="Factura no trobada")

    # Creació de l'estructura XML Veri*factu
    root = ET.Element("RegistroAlta")

    # Dades identificatives
    id_factura = ET.SubElement(root, "IDFactura")
    num_serie = ET.SubElement(id_factura, "NumSerieFactura")
    num_serie.text = f"{factura.serie}-{factura.numero_factura}"
    data_exp = ET.SubElement(id_factura, "FechaExpedicionFactura")
    data_exp.text = factura.data_emissio.strftime("%d-%m-%Y")

    # Desglossament i Inversió de Subjecte Passiu (ISP)
    desglose = ET.SubElement(root, "Desglose")
    if factura.quota_iva == 0.0:
        detalle = ET.SubElement(desglose, "DetalleExenta")
        causa = ET.SubElement(detalle, "CausaExencion")
        causa.text = "I"  # Codi I = Inversión Sujeto Pasivo
        base = ET.SubElement(detalle, "BaseImponible")
        base.text = f"{factura.base_imposable:.2f}"
    else:
        detalle = ET.SubElement(desglose, "DetalleSujeta")
        base = ET.SubElement(detalle, "BaseImponible")
        base.text = f"{factura.base_imposable:.2f}"
        quota = ET.SubElement(detalle, "CuotaRepercutida")
        quota.text = f"{factura.quota_iva:.2f}"

    # Encadenament
    encadenamiento = ET.SubElement(root, "Encadenamiento")
    reg_ant = ET.SubElement(encadenamiento, "RegistroAnterior")
    if factura.hash_anterior:
        reg_ant.text = factura.hash_anterior
    else:
        reg_ant.text = "PRIMER_REGISTRO"

    # Sistema informàtic
    sist_info = ET.SubElement(root, "SistemaInformatico")
    hash_node = ET.SubElement(sist_info, "Hash")
    hash_node.text = factura.hash_sha256

    xml_str = ET.tostring(root, encoding="utf-8", xml_declaration=True).decode("utf-8")

    return Response(content=xml_str, media_type="application/xml")


# ==============================================================================
# SPEC 007 (v5.0): SUITE ECONÒMICA, 6 MILLORES, TIQUETS I NORMA 43
# ==============================================================================


def _get_tenant_and_user(
    request: Request, claims: Optional[Dict[str, Any]] = None
) -> tuple[uuid.UUID, uuid.UUID, str]:
    emp = getattr(request.state, "empresa_id", None)
    uid = (claims or {}).get("sub") or getattr(request.state, "user_id", None)
    rol = (
        (claims or {}).get("rol")
        or getattr(request.state, "user_role", None)
        or getattr(request.state, "rol", "SECRETARIA")
    )
    if not emp or emp == "undefined":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Tenant no autenticat")
    return uuid.UUID(str(emp)), uuid.UUID(str(uid)) if uid else uuid.uuid4(), str(rol).upper()


@router.get("/dashboard-economic", response_model=DashboardEconomicResponseDTO)
async def obtenir_dashboard_economic(
    request: Request,
    criteri_caixa: bool = False,
    periode: Optional[str] = None,
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> DashboardEconomicResponseDTO:
    empresa_id, _, _ = _get_tenant_and_user(request)
    return await EconomicSuiteService.obtenir_dashboard_economic(
        db=db, empresa_id=empresa_id, criteri_caixa=criteri_caixa, periode=periode
    )


@router.get("/wip-control", response_model=WIPControlResponseDTO)
async def obtenir_wip_control(
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> WIPControlResponseDTO:
    empresa_id, _, _ = _get_tenant_and_user(request)
    return await EconomicSuiteService.obtenir_control_wip(db=db, empresa_id=empresa_id)


@router.post("/wip-control/{ordre_treball_id}/prefacturar", status_code=status.HTTP_201_CREATED)
async def convertir_wip_a_prefactura(
    ordre_treball_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> Dict[str, Any]:
    """Converteix en 1 clic una OT finalitzada en WIP a Pre-factura editable (ESBORRANY_PREFACTURA / Sèrie PRE)."""
    empresa_id, usuari_id, _ = _get_tenant_and_user(request)
    ot = (
        await db.execute(
            select(OrdreTreball).where(
                OrdreTreball.id == ordre_treball_id,
                OrdreTreball.empresa_id == empresa_id,
            )
        )
    ).scalar_one_or_none()
    if not ot:
        raise HTTPException(status_code=404, detail="Ordre de treball no trobada.")
    if ot.factura_id is not None:
        raise HTTPException(status_code=400, detail="L'OT ja es troba facturada o prefacturada.")
    if str(ot.estat or "").upper() not in ESTATS_OT_PENDENTS_PREFACTURACIO:
        raise HTTPException(
            status_code=400,
            detail="L'ordre de treball encara no està finalitzada per poder passar a prefacturació.",
        )
    if not ot.client_id:
        raise HTTPException(status_code=400, detail="L'OT no té un client associat.")

    hores = Decimal(str(ot.hores_imputades_facturables or 0))
    preu_hora_real = await resoldre_preu_hora_control_panel(db, empresa_id, ot)
    pvp_h = Decimal(str(preu_hora_real))
    pvp_mat = Decimal(str(ot.pvp_materials_aplicat or 0))
    pressup = Decimal(str(ot.import_pressupostat_net or ot.import_pressupostat or 0))

    linies: List[FacturaLiniaCreateDTO] = []
    if hores > 0:
        linies.append(
            FacturaLiniaCreateDTO(
                concepte=f"Mà d'obra tècnica OT {ot.codi} ({ot.titol})",
                obra_id=ot.id,
                quantitat=hores,
                preu_venda_unitari=pvp_h,
                tipus_iva_pct=Decimal("21.00"),
            )
        )

    if pvp_mat > 0:
        linies.append(
            FacturaLiniaCreateDTO(
                concepte=f"Subministrament i materials OT {ot.codi}",
                obra_id=ot.id,
                quantitat=Decimal("1.00"),
                preu_venda_unitari=pvp_mat,
                tipus_iva_pct=Decimal("21.00"),
            )
        )
    else:
        picking_mats = await EconomicSuiteService.obtenir_materials_consumits_ots(
            db, empresa_id, [ot.id]
        )
        for mat in picking_mats.get(ot.id, []):
            linies.append(
                FacturaLiniaCreateDTO(
                    concepte=f"Material {mat['nom']} (OT {ot.codi})",
                    obra_id=ot.id,
                    article_id=mat["article_id"],
                    quantitat=mat["quantitat"],
                    preu_venda_unitari=mat["preu_venda"],
                    tipus_iva_pct=Decimal("21.00"),
                )
            )

    if not linies:
        linies.append(
            FacturaLiniaCreateDTO(
                concepte=f"Treballs tècnics executats OT {ot.codi} ({ot.titol})",
                obra_id=ot.id,
                quantitat=Decimal("1.00"),
                preu_venda_unitari=pressup if pressup > 0 else Decimal("0.00"),
                tipus_iva_pct=Decimal("21.00"),
            )
        )

    avui = date.today()
    dto_pre = FacturaEmissioCreateDTO(
        client_id=ot.client_id,
        serie="PRE",
        data_emissio=avui,
        data_venciment=avui,
        linies=linies,
    )
    prefactura = await EconomicSuiteService.crear_prefactura_esborrany(
        db=db, empresa_id=empresa_id, usuari_id=usuari_id, payload=dto_pre
    )
    return {
        "id": prefactura.id,
        "numero_factura": prefactura.numero_factura,
        "serie": prefactura.serie,
        "estat_document": prefactura.estat_document,
        "liquid_exigible": prefactura.liquid_exigible,
        "ordre_treball_id": str(ot.id),
    }


@router.post("/prefactures", response_model=FacturaResponse, status_code=status.HTTP_201_CREATED)
async def crear_prefactura_directa(
    payload: FacturaEmissioCreateDTO,
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> FacturaResponse:
    """Crea una nova pre-factura editable (Sèrie PRE / HITL) directament des de Facturació amb materials o conceptes."""
    empresa_id, usuari_id, rol = _get_tenant_and_user(request)
    cli = (
        await db.execute(
            select(Client).where(
                Client.id == payload.client_id,
                Client.empresa_id == empresa_id,
            )
        )
    ).scalar_one_or_none()
    if not cli:
        raise HTTPException(status_code=404, detail="Client no trobat a l'empresa activa.")

    dto_pre = payload.model_copy(update={"serie": "PRE"})
    pref = await EconomicSuiteService.crear_prefactura_esborrany(
        db=db,
        empresa_id=empresa_id,
        usuari_id=usuari_id,
        payload=dto_pre,
    )
    await set_tenant_context(
        db,
        str(empresa_id),
        bool(getattr(request.state, "is_superadmin", False)),
        role=getattr(request.state, "user_role", None) or rol,
    )
    return (await _serialitzar_factures(db, empresa_id, [pref]))[0]


@router.put("/prefactures/{factura_id}", response_model=FacturaResponse)
async def editar_prefactura_esborrany(
    factura_id: uuid.UUID,
    payload: PrefacturaUpdateDTO,
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> FacturaResponse:
    """Edita línies, preus, descomptes, IVA i retencions d'una pre-factura abans d'emetre-la a Veri*factu."""
    empresa_id, usuari_id, rol = _get_tenant_and_user(request)
    pref = await EconomicSuiteService.actualitzar_prefactura_esborrany(
        db=db,
        empresa_id=empresa_id,
        usuari_id=usuari_id,
        factura_id=factura_id,
        payload=payload,
    )
    await set_tenant_context(
        db,
        str(empresa_id),
        bool(getattr(request.state, "is_superadmin", False)),
        role=getattr(request.state, "user_role", None) or rol,
    )
    return (await _serialitzar_factures(db, empresa_id, [pref]))[0]


@router.delete("/prefactures/{factura_id}", status_code=status.HTTP_200_OK)
async def descartar_prefactura_esborrany(
    factura_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> Dict[str, Any]:
    """Descarta una pre-factura en esborrany i retorna les OTs vinculades a la safata de WIP."""
    empresa_id, usuari_id, _ = _get_tenant_and_user(request)
    await EconomicSuiteService.descartar_prefactura_esborrany(
        db=db, empresa_id=empresa_id, usuari_id=usuari_id, factura_id=factura_id
    )
    return {"status": "DESCARTADA", "factura_id": str(factura_id)}


@router.post("/prefactures/{factura_id}/emetre", response_model=FacturaResponse)
async def emetre_prefactura_definitiva(
    factura_id: uuid.UUID,
    request: Request,
    payload: Optional[PrefacturaEmetreDTO] = None,
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> FacturaResponse:
    """Valida humanament (HITL) una pre-factura i l'emet definitivament a Veri*factu (Sèrie F)."""
    empresa_id, usuari_id, rol = _get_tenant_and_user(request)
    body = payload or PrefacturaEmetreDTO()
    factura = await EconomicSuiteService.emetre_prefactura_a_verifactu(
        db=db,
        empresa_id=empresa_id,
        usuari_id=usuari_id,
        factura_id=factura_id,
        payload=body,
    )
    await set_tenant_context(
        db,
        str(empresa_id),
        bool(getattr(request.state, "is_superadmin", False)),
        role=getattr(request.state, "user_role", None) or rol,
    )
    return (await _serialitzar_factures(db, empresa_id, [factura]))[0]


class RectificativaRequestDTO(BaseModel):
    motiu: str = Field(..., min_length=3, max_length=300)


@router.post("/factures/{factura_id}/rectificar", status_code=status.HTTP_201_CREATED)
async def emetre_rectificativa_serie_r(
    factura_id: uuid.UUID,
    payload: RectificativaRequestDTO,
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> Dict[str, Any]:
    """Emet una factura rectificativa Sèrie R (Spec 007 RF-14) vinculada a una factura emesa."""
    empresa_id, usuari_id, _ = _get_tenant_and_user(request)
    orig = (
        await db.execute(
            select(FacturaCapcalera).where(
                FacturaCapcalera.id == factura_id,
                FacturaCapcalera.empresa_id == empresa_id,
            )
        )
    ).scalar_one_or_none()
    if not orig:
        raise HTTPException(status_code=404, detail="Factura original no trobada.")
    if str(orig.serie or "").upper().startswith("R"):
        raise HTTPException(status_code=400, detail="No es pot rectificar una factura rectificativa.")

    avui = date.today()
    base_orig = Decimal(str(orig.base_imposable or 0))
    iva_pct = (
        Decimal("21.00")
        if not orig.es_inversio_subjecte_passiu and Decimal(str(orig.quota_iva or 0)) > 0
        else Decimal("0.00")
    )
    dto_rect = FacturaEmissioCreateDTO(
        client_id=orig.client_id,
        serie="R",
        data_emissio=avui,
        data_venciment=avui,
        es_inversio_subjecte_passiu=bool(orig.es_inversio_subjecte_passiu),
        factura_rectificada_id=orig.id,
        motiu_rectificacio=payload.motiu.strip(),
        linies=[
            FacturaLiniaCreateDTO(
                concepte=f"Rectificativa Sèrie R de {orig.serie}-{orig.numero_factura}: {payload.motiu.strip()}",
                quantitat=Decimal("1.00"),
                preu_venda_unitari=max(Decimal("0.00"), base_orig),
                tipus_iva_pct=iva_pct,
            )
        ],
    )
    rect = await EconomicSuiteService.emetre_factura_verifactu(
        db=db, empresa_id=empresa_id, usuari_id=usuari_id, payload=dto_rect
    )
    return {
        "id": rect.id,
        "serie": rect.serie,
        "numero_factura": rect.numero_factura,
        "liquid_exigible": rect.liquid_exigible,
        "factura_rectificada_id": str(orig.id),
    }


@router.post("/factures/emetre", status_code=status.HTTP_201_CREATED)
async def emetre_factura_suite(
    payload: FacturaEmissioCreateDTO,
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> Dict[str, Any]:
    empresa_id, usuari_id, _ = _get_tenant_and_user(request)
    factura = await EconomicSuiteService.emetre_factura_verifactu(
        db=db, empresa_id=empresa_id, usuari_id=usuari_id, payload=payload
    )
    return {
        "id": factura.id,
        "numero_factura": factura.numero_factura,
        "serie": factura.serie,
        "liquid_exigible": factura.liquid_exigible,
        "hash_sha256": factura.hash_sha256,
        "qr_verifactu_payload": factura.qr_verifactu_payload,
    }


@router.get("/retencions-garantia", response_model=List[RetencioGarantiaDTO])
async def llistar_retencions_garantia(
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> List[RetencioGarantiaDTO]:
    empresa_id, _, _ = _get_tenant_and_user(request)
    return await EconomicSuiteService.llistar_retencions_garantia(db=db, empresa_id=empresa_id)


@router.post("/retencions-garantia/{retencio_id}/reclamar")
async def reclamar_retencio_garantia(
    retencio_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> Dict[str, Any]:
    empresa_id, usuari_id, _ = _get_tenant_and_user(request)
    ret = await EconomicSuiteService.reclamar_retencio_garantia(
        db=db, empresa_id=empresa_id, usuari_id=usuari_id, retencio_id=retencio_id
    )
    return {"id": ret.id, "estat": ret.estat}


@router.post("/clients/{client_id}/evaluar-risc", response_model=ClientRiscSanititzatDTO)
async def evaluar_risc_client(
    client_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> ClientRiscSanititzatDTO:
    empresa_id, _, _ = _get_tenant_and_user(request)
    return await EconomicSuiteService.validar_operacio_camp_client(
        db=db, empresa_id=empresa_id, client_id=client_id, enforce_lock=False, evaluate_risk=True
    )


@router.post(
    "/clients/{client_id}/override-risc",
    dependencies=[Depends(require_roles(["BOSS"]))],
)
async def override_risc_client(
    client_id: uuid.UUID,
    payload: OverrideRiscRequestDTO,
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> Dict[str, Any]:
    empresa_id, boss_id, _ = _get_tenant_and_user(request)
    client = await EconomicSuiteService.override_risc_pel_boss(
        db=db, empresa_id=empresa_id, boss_id=boss_id, client_id=client_id, motiu=payload.motiu
    )
    return {"client_id": client.id, "estat_risc_operatiu": client.estat_risc_operatiu}


@router.get("/art80-incobrables", response_model=List[Art80ItemDTO])
async def llistar_art80_incobrables(
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> List[Art80ItemDTO]:
    empresa_id, _, _ = _get_tenant_and_user(request)
    return await EconomicSuiteService.processar_finestres_art80_liva(db=db, empresa_id=empresa_id)


@router.post("/art80-incobrables/{factura_id}/generar-rectificativa", status_code=status.HTTP_201_CREATED)
@router.post("/art80-incobrables/{factura_id}/rectificar", status_code=status.HTTP_201_CREATED)
async def generar_rectificativa_art80(
    factura_id: uuid.UUID,
    payload: Art80ReclamacioRequestDTO,
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> Dict[str, Any]:
    empresa_id, usuari_id, _ = _get_tenant_and_user(request)
    rect = await EconomicSuiteService.generar_rectificativa_art80(
        db=db,
        empresa_id=empresa_id,
        usuari_id=usuari_id,
        factura_id=factura_id,
        justificant_notarial_path=payload.justificant_notarial_path,
    )
    return {"id": rect.id, "serie": rect.serie, "numero_factura": rect.numero_factura}


@router.get("/operaris-cost-efectiu", response_model=List[OperariCostEfectiuDTO])
async def obtenir_operaris_cost_efectiu(
    request: Request,
    claims: Dict[str, Any] = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> List[OperariCostEfectiuDTO]:
    empresa_id, _, rol = _get_tenant_and_user(request, claims)
    return await EconomicSuiteService.calcular_cost_efectiu_operaris(
        db=db, empresa_id=empresa_id, rol_peticio=rol
    )


@router.get("/contractes-mrr-auditoria", response_model=List[ContracteMRRAuditoriaDTO])
async def obtenir_contractes_mrr_auditoria(
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> List[ContracteMRRAuditoriaDTO]:
    empresa_id, _, _ = _get_tenant_and_user(request)
    return await EconomicSuiteService.auditar_contractes_mrr(db=db, empresa_id=empresa_id)


@router.get("/tiquets", response_model=List[TiquetDespesaResponseDTO])
async def llistar_tiquets_comptabilitat(
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> List[TiquetDespesaResponseDTO]:
    empresa_id, _, _ = _get_tenant_and_user(request)
    return await EconomicSuiteService.llistar_tiquets_despesa(db=db, empresa_id=empresa_id)


@router.post("/tiquets/{tiquet_id}/auditar")
async def auditar_tiquet_comptabilitat(
    tiquet_id: uuid.UUID,
    payload: TiquetAuditoriaRequestDTO,
    request: Request,
    claims: Dict[str, Any] = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> Dict[str, Any]:
    empresa_id, usuari_id, rol = _get_tenant_and_user(request, claims)
    tiquet = await EconomicSuiteService.auditar_tiquet_despesa(
        db=db,
        empresa_id=empresa_id,
        usuari_id=usuari_id,
        rol_peticio=rol,
        tiquet_id=tiquet_id,
        payload=payload,
    )
    return {"id": tiquet.id, "estat_aprovacio": tiquet.estat_aprovacio, "estat_fiscal": tiquet.estat_fiscal}


@router.post("/norma43/conciliar", response_model=List[Norma43MovimentDTO])
async def conciliar_norma43(
    payload: Norma43ConciliarRequestDTO,
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> List[Norma43MovimentDTO]:
    empresa_id, usuari_id, _ = _get_tenant_and_user(request)
    return await EconomicSuiteService.conciliar_norma43(
        db=db,
        empresa_id=empresa_id,
        usuari_id=usuari_id,
        contingut_c43=payload.contingut_c43,
        confirmar_hitl=payload.confirmar_conciliacio_hitl,
    )


@router.get("/ordres-treball/{ordre_treball_id}/cost-marge", response_model=OTCostMargeDTO)
async def obtenir_cost_marge_analitic_ot(
    ordre_treball_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> Dict[str, Any]:
    """Calcula en temps real el cost real (PickIn/Out PMP + Mermes + Tiquets + Mà d'obra + Flota) i marge brut d'una OT."""
    empresa_id, _, _ = _get_tenant_and_user(request)
    return await calcular_cost_i_marge_analitic_ot(
        db=db,
        empresa_id=empresa_id,
        ordre_treball_id=ordre_treball_id,
    )


@router.get("/ordres-treball-marges", response_model=List[OTCostMargeDTO])
async def llistar_marges_analitics_ots(
    request: Request,
    limit: int = 30,
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> List[Dict[str, Any]]:
    """Llista el càlcul determinista de costos i marges bruts per a les OTs del tenant."""
    empresa_id, _, _ = _get_tenant_and_user(request)
    ot_ids = (
        await db.execute(
            select(OrdreTreball.id)
            .where(OrdreTreball.empresa_id == empresa_id)
            .order_by(OrdreTreball.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    resultats = []
    for ot_id in ot_ids:
        resultats.append(
            await calcular_cost_i_marge_analitic_ot(
                db=db,
                empresa_id=empresa_id,
                ordre_treball_id=ot_id,
            )
        )
    return resultats


@router.get("/despeses-analitiques", response_model=List[DespesaComptableDTO])
async def llistar_despeses_analitiques(
    request: Request,
    limit: int = 50,
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> Sequence[DespesaComptable]:
    """Llista els assentaments analítics procedents de Mermes de Magatzem i Tiquets OCR de camp."""
    empresa_id, _, _ = _get_tenant_and_user(request)
    rows = (
        await db.execute(
            select(DespesaComptable)
            .where(DespesaComptable.empresa_id == empresa_id)
            .order_by(DespesaComptable.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    return rows
