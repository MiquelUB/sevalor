import uuid
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_with_tenant_context
from app.core.security import require_roles

import io
from fastapi import UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.exc import IntegrityError
from app.services.csv_service import parse_and_validate_csv, generate_csv_content, CsvImportResult

from app.models.models import Client

router = APIRouter(
    prefix="/gestio/clients",
    tags=["Gestió Clients"],
    dependencies=[Depends(require_roles(["BOSS", "SECRETARIA", "ENGINYER"]))],
)

class ClientCreate(BaseModel):
    codi: str = Field(..., max_length=20)
    rao_social: str = Field(..., max_length=200)
    nif: str = Field(..., max_length=20)
    telefon: Optional[str] = Field(None, max_length=30)
    email: Optional[str] = Field(None, max_length=200)
    adreca_fiscal: Optional[str] = Field(None)
    iban: Optional[str] = Field(None, max_length=34)


class ClientResponse(ClientCreate):
    id: uuid.UUID
    estat_canal_telegram: str
    actiu: bool
    model_config = {"from_attributes": True}


class ClientAmbIBANResponse(BaseModel):
    id: uuid.UUID
    rao_social: str
    iban_xifrat_simetric: Optional[str]


class CanviIBANRequest(BaseModel):
    nou_iban: str = Field(..., min_length=15, max_length=34)

@router.get("", response_model=List[ClientResponse])
async def llistar_clients(
    request: Request,
    q: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = request.state.empresa_id
    if not empresa_id:
        raise HTTPException(status_code=401, detail="No identificat")

    stmt = select(Client).where(Client.empresa_id == uuid.UUID(empresa_id))

    if q:
        search_term = f"%{q}%"
        stmt = stmt.where(
            or_(
                Client.rao_social.ilike(search_term),
                Client.nif.ilike(search_term)
            )
        )

    stmt = stmt.limit(limit).offset(offset).order_by(Client.created_at.desc())

    result = await db.execute(stmt)
    clients = result.scalars().all()

    return clients

@router.post("", response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
async def alta_client(
    request: Request,
    client: ClientCreate,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = request.state.empresa_id
    if not empresa_id:
        raise HTTPException(status_code=401, detail="No identificat")

    stmt_nif = select(Client).where(Client.empresa_id == uuid.UUID(empresa_id), Client.nif == client.nif)
    result_nif = await db.execute(stmt_nif)
    if result_nif.scalars().first():
        raise HTTPException(status_code=400, detail="El NIF/CIF ja es troba registrat en el sistema")

    stmt_codi = select(Client).where(Client.empresa_id == uuid.UUID(empresa_id), Client.codi == client.codi)
    result_codi = await db.execute(stmt_codi)
    if result_codi.scalars().first():
        raise HTTPException(status_code=400, detail="El codi ja es troba registrat en el sistema")

    nou_client = Client(
        empresa_id=uuid.UUID(empresa_id),
        codi=client.codi,
        rao_social=client.rao_social,
        nif=client.nif,
        telefon=client.telefon,
        email=client.email,
        adreca_fiscal=client.adreca_fiscal,
        iban_xifrat_simetric=client.iban,
    )

    db.add(nou_client)
    await db.commit()

    return nou_client


# ---------------------------------------------------------------------------
# IBAN xifrat — Veto d'Enginyer (Spec 002). BOSS/SECRETARIA poden accedir-hi.
# ---------------------------------------------------------------------------

@router.get("/{client_id}/iban", response_model=ClientAmbIBANResponse,
            dependencies=[Depends(require_roles(["BOSS", "SECRETARIA"]))])
async def obtenir_iban_client(
    request: Request, client_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    """Retorna l'IBAN complet del client. Enginyer rep 403."""
    empresa_id = request.headers.get("X-Empresa-ID") or getattr(request.state, "empresa_id", None)
    if not empresa_id:
        raise HTTPException(status_code=401, detail="No identificat")
    res = await db.execute(select(Client).where(
        Client.id == client_id, Client.empresa_id == uuid.UUID(empresa_id)
    ))
    client = res.scalars().first()
    if not client:
        raise HTTPException(status_code=404, detail="Client no trobat")
    return {"id": client.id, "rao_social": client.rao_social, "iban_xifrat_simetric": client.iban_xifrat_simetric}


@router.put("/{client_id}/iban", response_model=ClientAmbIBANResponse,
            dependencies=[Depends(require_roles(["BOSS", "SECRETARIA"]))])
async def canviar_iban_client(
    request: Request, client_id: uuid.UUID, payload: CanviIBANRequest,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    """Canvia l'IBAN d'un client (Spec 002). Enginyer rep 403."""
    empresa_id = request.headers.get("X-Empresa-ID") or getattr(request.state, "empresa_id", None)
    if not empresa_id:
        raise HTTPException(status_code=401, detail="No identificat")
    res = await db.execute(select(Client).where(
        Client.id == client_id, Client.empresa_id == uuid.UUID(empresa_id)
    ))
    client = res.scalars().first()
    if not client:
        raise HTTPException(status_code=404, detail="Client no trobat")
    client.iban_xifrat_simetric = payload.nou_iban
    await db.commit()
    return {"id": client.id, "rao_social": client.rao_social, "iban_xifrat_simetric": client.iban_xifrat_simetric}


# ---------------------------------------------------------------------------
# Fitxa 360° del Client (Spec 012 RF-04 & Spec 002)
# ---------------------------------------------------------------------------

class FincaFitxa360(BaseModel):
    id: uuid.UUID
    nom: str
    adreca: Optional[str] = None
    superficie_ha: Optional[float] = None
    dades_sigpac: Optional[dict] = None

class PecaInstaladaFitxa360(BaseModel):
    article_id: uuid.UUID
    codi_article: str
    nom_article: str
    quantitat_instalada: float
    unitat_mesura: str
    data_instalacio: datetime
    ordre_treball_id: uuid.UUID
    ordre_treball_codi: str

class IncidenciaFitxa360(BaseModel):
    id: uuid.UUID
    ordre_treball_id: Optional[uuid.UUID] = None
    ordre_treball_codi: Optional[str] = None
    ambit: str
    estat: str
    text_observacions: Optional[str] = None
    foto_path: Optional[str] = None
    audio_path: Optional[str] = None
    created_at: datetime

class IntervencioFitxa360(BaseModel):
    id: uuid.UUID
    codi: str
    titol: str
    adreca: str
    estat: str
    data_planificacio: Optional[date] = None
    hora_inici_prevista: Optional[datetime] = None
    hora_fi_prevista: Optional[datetime] = None
    created_at: datetime
    cost_material: Optional[float] = 0.0
    ingres_facturat: Optional[float] = 0.0
    marge_brut: Optional[float] = 0.0

class Fitxa360Resum(BaseModel):
    total_intervencions: int
    total_incidencies: int
    total_peces_instalades: int
    dies_analitzats: int = 365

class Fitxa360Response(BaseModel):
    client: ClientResponse
    finques: List[FincaFitxa360]
    intervencions: List[IntervencioFitxa360]
    peces_instalades: List[PecaInstaladaFitxa360]
    incidencies: List[IncidenciaFitxa360]
    alertes_garantia: List[dict]
    resum: Fitxa360Resum


@router.get("/{client_id}/fitxa360", response_model=Fitxa360Response)
async def obtenir_fitxa_360_client(
    request: Request,
    client_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    """
    Recopila cronològicament totes les intervencions tècniques, peces instal·lades
    i incidències registrades per al client durant els últims 365 dies (Spec 012 RF-04).
    """
    empresa_id = request.headers.get("X-Empresa-ID") or getattr(request.state, "empresa_id", None)
    if not empresa_id:
        raise HTTPException(status_code=401, detail="No identificat")

    empresa_uuid = uuid.UUID(empresa_id)

    # 1. Verificar client
    res_client = await db.execute(
        select(Client).where(Client.id == client_id, Client.empresa_id == empresa_uuid)
    )
    client = res_client.scalars().first()
    if not client:
        raise HTTPException(status_code=404, detail="Client no trobat")

    fa_un_any = datetime.now(timezone.utc) - timedelta(days=365)

    # 2. Obtenir Finques
    from sqlalchemy import func
    from app.models.models import (
        AlertaGarantiaRecompra,
        Article,
        Finca,
        FullaPicking,
        Incidencia,
        LiniaPicking,
        OrdreTreball,
        FacturaLinia
    )

    res_finques = await db.execute(
        select(Finca).where(Finca.client_id == client_id, Finca.empresa_id == empresa_uuid)
    )
    finques_db = res_finques.scalars().all()
    finques = [
        FincaFitxa360(
            id=f.id,
            nom=f.nom,
            adreca=f.adreca,
            superficie_ha=float(f.superficie_ha) if f.superficie_ha is not None else None,
            dades_sigpac=f.dades_sigpac or {}
        )
        for f in finques_db
    ]

    # 3. Obtenir Ordres de Treball (últims 365 dies)
    res_ots = await db.execute(
        select(OrdreTreball).where(
            OrdreTreball.client_id == client_id,
            OrdreTreball.empresa_id == empresa_uuid,
            OrdreTreball.created_at >= fa_un_any
        ).order_by(OrdreTreball.created_at.desc())
    )
    ots = res_ots.scalars().all()
    ot_map = {ot.id: ot for ot in ots}
    ot_ids = list(ot_map.keys())


    # NEW BLOCK: Calculate Financials for OTs
    # 1. Cost Material
    costos_materials = {}
    if ot_ids:
        stmt_costos = (
            select(FullaPicking.ordre_treball_id, func.sum(LiniaPicking.quantitat_carregada_pick_in * Article.preu_cost))
            .join(FullaPicking, LiniaPicking.picking_id == FullaPicking.id)
            .join(Article, LiniaPicking.article_id == Article.id)
            .where(FullaPicking.ordre_treball_id.in_(ot_ids))
            .group_by(FullaPicking.ordre_treball_id)
        )
        res_costos = await db.execute(stmt_costos)
        for ot_id, cost in res_costos.all():
            costos_materials[ot_id] = float(cost or 0.0)

    # 2. Ingressos
    ingressos = {}
    if ot_ids:
        stmt_ing = (
            select(FacturaLinia.obra_id, func.sum(FacturaLinia.preu_venda_unitari * FacturaLinia.quantitat))
            .where(FacturaLinia.obra_id.in_(ot_ids))
            .group_by(FacturaLinia.obra_id)
        )
        res_ing = await db.execute(stmt_ing)
        for ot_id, ing in res_ing.all():
            ingressos[ot_id] = float(ing or 0.0)

    intervencions = [
        IntervencioFitxa360(
            id=ot.id,
            codi=ot.codi,
            titol=ot.titol,
            adreca=ot.adreca,
            estat=ot.estat,
            data_planificacio=ot.data_planificacio,
            hora_inici_prevista=ot.hora_inici_prevista,
            hora_fi_prevista=ot.hora_fi_prevista,
            created_at=ot.created_at,
            cost_material=costos_materials.get(ot.id, 0.0),
            ingres_facturat=ingressos.get(ot.id, 0.0),
            marge_brut=ingressos.get(ot.id, 0.0) - costos_materials.get(ot.id, 0.0)
        )
        for ot in ots
    ]


    # 4. Obtenir Peces instal·lades a les OTs dels últims 365 dies
    peces_instalades: List[PecaInstaladaFitxa360] = []
    if ot_ids:
        stmt_peces = (
            select(LiniaPicking, Article, FullaPicking)
            .join(FullaPicking, LiniaPicking.picking_id == FullaPicking.id)
            .join(Article, LiniaPicking.article_id == Article.id)
            .where(
                FullaPicking.ordre_treball_id.in_(ot_ids),
                LiniaPicking.empresa_id == empresa_uuid
            )
            .order_by(LiniaPicking.created_at.desc())
        )
        res_peces = await db.execute(stmt_peces)
        for lp, art, fp in res_peces.all():
            ot = ot_map.get(fp.ordre_treball_id)
            # Consum real = carregat - retornat
            quantitat = float(lp.quantitat_carregada_pick_in or 0.0) - float(lp.quantitat_retornada_pick_out or 0.0)
            if quantitat <= 0:
                quantitat = float(lp.quantitat_carregada_pick_in or 0.0)
            peces_instalades.append(PecaInstaladaFitxa360(
                article_id=art.id,
                codi_article=art.referencia_inventari,
                nom_article=art.nom,
                quantitat_instalada=quantitat,
                unitat_mesura=art.unitat_mesura,
                data_instalacio=lp.created_at,
                ordre_treball_id=fp.ordre_treball_id,
                ordre_treball_codi=ot.codi if ot else "S/C"
            ))

    # 5. Obtenir Incidències associades
    incidencies: List[IncidenciaFitxa360] = []
    if ot_ids:
        stmt_inc = select(Incidencia).where(
            Incidencia.ordre_treball_id.in_(ot_ids),
            Incidencia.empresa_id == empresa_uuid,
            Incidencia.created_at >= fa_un_any
        ).order_by(Incidencia.created_at.desc())
        res_inc = await db.execute(stmt_inc)
        for inc in res_inc.scalars().all():
            ot = ot_map.get(inc.ordre_treball_id) if inc.ordre_treball_id else None
            incidencies.append(IncidenciaFitxa360(
                id=inc.id,
                ordre_treball_id=inc.ordre_treball_id,
                ordre_treball_codi=ot.codi if ot else None,
                ambit=inc.ambit,
                estat=inc.estat,
                text_observacions=inc.text_observacions,
                foto_path=inc.foto_path,
                audio_path=inc.audio_path,
                created_at=inc.created_at
            ))

    # 6. Obtenir Alertes de Garantia
    alertes: List[dict] = []
    if ot_ids:
        stmt_alertes = select(AlertaGarantiaRecompra).where(
            AlertaGarantiaRecompra.ordre_treball_id.in_(ot_ids),
            AlertaGarantiaRecompra.empresa_id == empresa_uuid
        )
        res_alertes = await db.execute(stmt_alertes)
        for al in res_alertes.scalars().all():
            alertes.append({
                "id": str(al.id),
                "ordre_treball_id": str(al.ordre_treball_id) if al.ordre_treball_id else None,
                "tipus_alerta": al.tipus_alerta,
                "missatge": al.missatge,
                "data_fi_garantia": str(al.data_fi_garantia) if al.data_fi_garantia else None,
                "estat": al.estat
            })

    resum = Fitxa360Resum(
        total_intervencions=len(intervencions),
        total_incidencies=len(incidencies),
        total_peces_instalades=len(peces_instalades),
        dies_analitzats=365
    )

    client_resp = ClientResponse(
        id=client.id,
        codi=client.codi,
        rao_social=client.rao_social,
        nif=client.nif,
        telefon=client.telefon,
        email=client.email,
        adreca_fiscal=client.adreca_fiscal,
        iban=client.iban_xifrat_simetric,
        estat_canal_telegram=client.estat_canal_telegram,
        actiu=client.actiu
    )

    return Fitxa360Response(
        client=client_resp,
        finques=finques,
        intervencions=intervencions,
        peces_instalades=peces_instalades,
        incidencies=incidencies,
        alertes_garantia=alertes,
        resum=resum
    )



@router.post("/import", response_model=CsvImportResult)
async def importar_clients_csv(
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="El fitxer ha de ser un CSV")
        
    content = await file.read()
    valid_records, errors = parse_and_validate_csv(content, ClientCreate)
    
    inserits = 0
    total_processats = len(valid_records) + len(set(e["fila"] for e in errors))
    
    empresa_id = request.state.empresa_id
    
    # Processar els vàlids un a un per capturar duplicats de BD (ex. NIF repetit)
    for index, record in enumerate(valid_records):
        client_db = Client(
            empresa_id=empresa_id,
            **record.model_dump()
        )
        db.add(client_db)
        try:
            await db.flush()
            inserits += 1
        except IntegrityError as e:
            await db.rollback()
            # Mapejem la fila (afegim +2 pel offset d'index i capçalera, assumint sense errors previs, 
            # però millor no lligar-ho estricte si ja hi ha hagut errors, per ara posem info genèrica)
            errors.append({
                "fila": "Desconeguda",
                "columna": "nif/codi",
                "valor": record.nif,
                "motiu": "Ja existeix un client amb aquest NIF o Codi"
            })
            
    await db.commit()
    
    return CsvImportResult(
        total_processats=total_processats,
        inserits=inserits,
        errors_detectats=errors
    )

@router.get("/export")
async def exportar_clients_csv(
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    result = await db.execute(select(Client).where(Client.empresa_id == request.state.empresa_id))
    clients = result.scalars().all()
    
    fieldnames = ["codi", "rao_social", "nif", "telefon", "email", "adreca_fiscal", "actiu"]
    records = []
    for c in clients:
        records.append({
            "codi": c.codi,
            "rao_social": c.rao_social,
            "nif": c.nif,
            "telefon": c.telefon or "",
            "email": c.email or "",
            "adreca_fiscal": c.adreca_fiscal or "",
            "actiu": str(c.actiu)
        })
        
    csv_io = generate_csv_content(records, fieldnames)
    csv_io.seek(0)
    
    return StreamingResponse(
        iter([csv_io.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=clients_export.csv"}
    )
