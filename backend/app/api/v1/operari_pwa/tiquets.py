import secrets
import uuid
from datetime import date, datetime, timezone
from typing import List, Optional

import filetype
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_with_tenant_context
from app.core.security import get_current_user_claims, require_roles
from app.models.models import OrdreTreball, TiquetCarburant, TiquetDespesa, Usuari, Vehicle

router = APIRouter(
    prefix="/operari",
    tags=["Operari Tiquets i Despeses"],
    dependencies=[
        Depends(require_roles(["OPERARI", "CAPATAZ", "CAP_DE_COLLA", "BOSS", "SUPERADMIN"]))
    ],
)


class TiquetCarburantCreate(BaseModel):
    vehicle_id: Optional[uuid.UUID] = None
    tiquet_foto_path: str = Field(..., max_length=500)
    odometre_foto_path: Optional[str] = Field(None, max_length=500)
    litres: Optional[float] = None
    import_euros: Optional[float] = None
    odometre_valor: Optional[int] = None


class TiquetCarburantResponse(BaseModel):
    id: uuid.UUID
    vehicle_id: Optional[uuid.UUID]
    operari_id: uuid.UUID
    tiquet_foto_path: str
    odometre_foto_path: Optional[str]
    litres: Optional[float]
    import_euros: Optional[float]
    odometre_valor: Optional[int]
    estat_ocr: str
    created_at: Optional[datetime] = None


@router.get("/tiquets", response_model=List[TiquetCarburantResponse])
async def llistar_tiquets_operari(
    request: Request, db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="Tenant context missing")

    claims = get_current_user_claims(request)
    usuari_id = claims.get("sub")

    stmt = (
        select(TiquetCarburant)
        .where(
            TiquetCarburant.empresa_id == uuid.UUID(empresa_id),
            TiquetCarburant.operari_id == uuid.UUID(usuari_id),
        )
        .order_by(TiquetCarburant.created_at.desc())
    )

    result = await db.execute(stmt)
    items = result.scalars().all()

    return [
        TiquetCarburantResponse(
            id=t.id,
            vehicle_id=t.vehicle_id,
            operari_id=t.operari_id,
            tiquet_foto_path=t.tiquet_foto_path,
            odometre_foto_path=t.odometre_foto_path,
            litres=float(t.litres) if t.litres is not None else None,
            import_euros=float(t.import_) if t.import_ is not None else None,
            odometre_valor=t.odometre_valor,
            estat_ocr=t.estat_ocr,
            created_at=t.created_at,
        )
        for t in items
    ]


@router.post(
    "/tiquets", response_model=TiquetCarburantResponse, status_code=status.HTTP_201_CREATED
)
async def registrar_tiquet_carburant(
    request: Request,
    payload: TiquetCarburantCreate,
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="Tenant context missing")

    claims = get_current_user_claims(request)
    usuari_id = claims.get("sub")

    # Si no es passa vehicle_id, buscar o assignar el primer vehicle del tenant
    v_id = payload.vehicle_id
    if not v_id:
        v_res = await db.execute(select(Vehicle).where(Vehicle.empresa_id == uuid.UUID(empresa_id)))
        v = v_res.scalars().first()
        if v:
            v_id = v.id
        else:
            raise HTTPException(
                status_code=400,
                detail="No hi ha cap vehicle registrat al tenant. Doneu-ne d'alta un primer.",
            )

    nou_tiquet = TiquetCarburant(
        empresa_id=uuid.UUID(empresa_id),
        operari_id=uuid.UUID(usuari_id),
        vehicle_id=v_id,
        tiquet_foto_path=payload.tiquet_foto_path,
        odometre_foto_path=payload.odometre_foto_path,
        litres=payload.litres,
        import_=payload.import_euros,
        odometre_valor=payload.odometre_valor,
        estat_ocr="PENDENT_AUDITORIA",
    )

    db.add(nou_tiquet)
    await db.commit()

    from app.services.sovereign_storage import SovereignStorageGateway

    await SovereignStorageGateway.desar_entitat_json(
        db=db,
        empresa_id=empresa_id,
        categoria="tiquets_despesa",
        item_id=str(nou_tiquet.id),
        dades={
            "id": str(nou_tiquet.id),
            "operari_id": str(nou_tiquet.operari_id),
            "vehicle_id": str(nou_tiquet.vehicle_id) if nou_tiquet.vehicle_id else None,
            "tiquet_foto_path": nou_tiquet.tiquet_foto_path,
            "odometre_foto_path": nou_tiquet.odometre_foto_path,
            "litres": float(nou_tiquet.litres) if nou_tiquet.litres is not None else None,
            "import_euros": float(nou_tiquet.import_) if nou_tiquet.import_ is not None else None,
            "odometre_valor": nou_tiquet.odometre_valor,
            "estat_ocr": nou_tiquet.estat_ocr,
        },
    )

    return TiquetCarburantResponse(
        id=nou_tiquet.id,
        vehicle_id=nou_tiquet.vehicle_id,
        operari_id=nou_tiquet.operari_id,
        tiquet_foto_path=nou_tiquet.tiquet_foto_path,
        odometre_foto_path=nou_tiquet.odometre_foto_path,
        litres=float(nou_tiquet.litres) if nou_tiquet.litres is not None else None,
        import_euros=float(nou_tiquet.import_) if nou_tiquet.import_ is not None else None,
        odometre_valor=nou_tiquet.odometre_valor,
        estat_ocr=nou_tiquet.estat_ocr,
        created_at=nou_tiquet.created_at,
    )


@router.post("/tiquets/ocr", response_model=dict, status_code=status.HTTP_200_OK)
async def pujar_tiquet_ocr(
    request: Request,
    file: UploadFile = File(...),
    vehicle_id: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    """(Spec 018) Rep una imatge de tiquet, simula extracció OCR i ho desa a DB."""
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="Tenant context missing")

    claims = get_current_user_claims(request)
    usuari_id = claims.get("sub")

    v_id = None
    if vehicle_id:
        try:
            v_id = uuid.UUID(vehicle_id)
        except ValueError:
            pass

    if not v_id:
        v_res = await db.execute(select(Vehicle).where(Vehicle.empresa_id == uuid.UUID(empresa_id)))
        v = v_res.scalars().first()
        if v:
            v_id = v.id
        else:
            raise HTTPException(
                status_code=400,
                detail="No hi ha cap vehicle registrat al tenant. Doneu-ne d'alta un primer.",
            )

    from app.services.sovereign_storage import SovereignStorageGateway

    file_ext = file.filename.split(".")[-1] if file.filename else "jpg"
    safe_name = f"ocr_{secrets.token_hex(8)}.{file_ext}"
    file_bytes = await file.read()

    file_path = await SovereignStorageGateway.pujar_fitxer_binari(
        db=db,
        empresa_id=empresa_id,
        categoria="tiquets_despesa",
        nom_fitxer=safe_name,
        content=file_bytes,
        content_type=file.content_type or "image/jpeg",
    )

    from app.services.ocr_service import processar_tiquet_ocr

    ocr_result = await processar_tiquet_ocr(file_bytes)

    nou_tiquet = TiquetCarburant(
        empresa_id=uuid.UUID(empresa_id),
        operari_id=uuid.UUID(usuari_id),
        vehicle_id=v_id,
        tiquet_foto_path=file_path,
        odometre_foto_path=None,
        litres=ocr_result.get("litres"),
        import_=ocr_result.get("import_euros"),
        odometre_valor=None,
        estat_ocr=ocr_result.get("status", "PENDENT_AUDITORIA"),
    )

    db.add(nou_tiquet)
    await db.commit()

    await SovereignStorageGateway.desar_entitat_json(
        db=db,
        empresa_id=empresa_id,
        categoria="tiquets_despesa",
        item_id=str(nou_tiquet.id),
        dades={
            "id": str(nou_tiquet.id),
            "operari_id": str(nou_tiquet.operari_id),
            "vehicle_id": str(nou_tiquet.vehicle_id) if nou_tiquet.vehicle_id else None,
            "tiquet_foto_path": file_path,
            "litres": float(nou_tiquet.litres) if nou_tiquet.litres is not None else None,
            "import_euros": float(nou_tiquet.import_) if nou_tiquet.import_ is not None else None,
            "estat_ocr": nou_tiquet.estat_ocr,
        },
    )

    return {
        "status": "OK",
        "id": str(nou_tiquet.id),
        "litres_extrets": nou_tiquet.litres,
        "import_extret": nou_tiquet.import_,
        "odometre_valor": nou_tiquet.odometre_valor,
        "estat_ocr": nou_tiquet.estat_ocr,
        "missatge": "Tiquet pujat amb processament OCR automàtic.",
    }

class TiquetParseRequest(BaseModel):
    text: str = Field(..., max_length=1000)


@router.post("/tiquets/parse", response_model=dict, status_code=status.HTTP_200_OK)
async def parse_tiquet_text(
    request: Request,
    payload: TiquetParseRequest,
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    """Extracció intel·ligent d'import i categoria de text lliure per a despeses (Spec 03 / Spec 018)."""
    import re

    text = payload.text
    # Extreure import
    match_import = re.search(r"(\d+(?:[.,]\d{1,2})?)\s*(?:€|euros|eur)?", text, re.IGNORECASE)
    import_val = 0.0
    if match_import:
        import_val = float(match_import.group(1).replace(",", "."))

    # Extreure categoria
    text_lower = text.lower()
    if any(k in text_lower for k in ["gasoil", "gasolina", "combustible", "dièsel", "diesel", "carburant"]):
        categoria = "CARBURANT"
    elif any(k in text_lower for k in ["dinar", "esmorzar", "menjar", "dieta", "restaurant"]):
        categoria = "DIETES"
    elif any(k in text_lower for k in ["material", "ferreteria", "tub", "cable", "eina"]):
        categoria = "MATERIAL"
    else:
        categoria = "ALTRES"

    return {
        "import": import_val,
        "categoria": categoria,
        "concepte": text.strip()[:100],
    }


CATEGORIES_TIQUET_CAPTURA = {"CARBURANT", "FERRETERIA", "PEATGES", "DIETES", "ALTRES"}
ALLOWED_IMAGE_MIMES = {"image/webp": "webp", "image/jpeg": "jpg", "image/png": "png"}
MAX_TIQUET_IMAGE_BYTES = 10 * 1024 * 1024


class CheckoutCustodiaRequest(BaseModel):
    tiquet_ids: Optional[List[uuid.UUID]] = None


@router.post("/tiquets/captura-rapida", status_code=status.HTTP_201_CREATED)
async def captura_rapida_tiquet(
    request: Request,
    categoria: str = Form(...),
    foto_tiquet: UploadFile = File(...),
    foto_odometre: Optional[UploadFile] = File(None),
    ordre_treball_id: Optional[str] = Form(None),
    vehicle_id: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    """(Spec 018 Zero-Tecleig) Captura binària pura de tiquets sense OCR local ni inputs manuals."""
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="Tenant context missing")

    emp_uuid = uuid.UUID(str(empresa_id))
    claims = get_current_user_claims(request)
    usuari_id_raw = claims.get("sub")
    if not usuari_id_raw:
        raise HTTPException(status_code=401, detail="Usuari no identificat")
    usuari_uuid = uuid.UUID(str(usuari_id_raw))

    cat_norm = categoria.strip().upper()
    if cat_norm not in CATEGORIES_TIQUET_CAPTURA:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Categoria invàlida '{categoria}'. "
                "Categories permeses: CARBURANT, FERRETERIA, PEATGES, DIETES, ALTRES."
            ),
        )

    raw_tiquet = await foto_tiquet.read()
    if not raw_tiquet:
        raise HTTPException(status_code=422, detail="La fotografia del tiquet és obligatòria.")
    if len(raw_tiquet) > MAX_TIQUET_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="La foto del tiquet supera el límit de 10 MB.")

    kind_tiquet = filetype.guess(raw_tiquet)
    if kind_tiquet is None or kind_tiquet.mime not in ALLOWED_IMAGE_MIMES:
        raise HTTPException(
            status_code=422,
            detail="Format d'imatge de tiquet no vàlid. Només s'admeten WebP, JPEG o PNG.",
        )

    raw_odometre: Optional[bytes] = None
    ext_odometre = "webp"
    mime_odometre = "image/webp"
    if foto_odometre is not None:
        raw_odometre = await foto_odometre.read()
        if raw_odometre:
            if len(raw_odometre) > MAX_TIQUET_IMAGE_BYTES:
                raise HTTPException(
                    status_code=413, detail="La foto de l'odòmetre supera el límit de 10 MB."
                )
            kind_odo = filetype.guess(raw_odometre)
            if kind_odo is None or kind_odo.mime not in ALLOWED_IMAGE_MIMES:
                raise HTTPException(
                    status_code=422,
                    detail="Format d'imatge d'odòmetre no vàlid. Només s'admeten WebP, JPEG o PNG.",
                )
            ext_odometre = ALLOWED_IMAGE_MIMES[kind_odo.mime]
            mime_odometre = kind_odo.mime

    if cat_norm == "CARBURANT" and not raw_odometre:
        raise HTTPException(
            status_code=422,
            detail="Per a CARBURANT és obligatori aportar la segona foto de l'odòmetre.",
        )

    ot_uuid: Optional[uuid.UUID] = None
    if ordre_treball_id and ordre_treball_id.strip():
        try:
            ot_uuid = uuid.UUID(ordre_treball_id.strip())
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="ordre_treball_id invàlid") from exc
        ot_res = await db.execute(
            select(OrdreTreball.id).where(
                OrdreTreball.id == ot_uuid,
                OrdreTreball.empresa_id == emp_uuid,
            )
        )
        if not ot_res.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Ordre de treball no trobada al tenant")

    veh_uuid: Optional[uuid.UUID] = None
    if vehicle_id and vehicle_id.strip():
        try:
            veh_uuid = uuid.UUID(vehicle_id.strip())
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="vehicle_id invàlid") from exc
        v_res = await db.execute(
            select(Vehicle.id).where(Vehicle.id == veh_uuid, Vehicle.empresa_id == emp_uuid)
        )
        if not v_res.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Vehicle no trobat al tenant")
    else:
        u_res = await db.execute(
            select(Usuari.vehicle_assignat_id).where(
                Usuari.id == usuari_uuid,
                Usuari.empresa_id == emp_uuid,
            )
        )
        veh_uuid = u_res.scalar_one_or_none()

    from app.services.sovereign_storage import SovereignStorageGateway
    from app.workers.comptabilitat_tasks import processar_tiquet_ocr_a_gestio_task

    ext_tiquet = ALLOWED_IMAGE_MIMES[kind_tiquet.mime]
    ts = int(datetime.now(timezone.utc).timestamp())
    nom_fitxer_visible = f"tiquet_tmp_{ts}.webp"
    storage_name_tiquet = f"{uuid.uuid4().hex}.{ext_tiquet}"

    path_tiquet = await SovereignStorageGateway.pujar_fitxer_binari(
        db=db,
        empresa_id=str(emp_uuid),
        categoria="tiquets_despesa",
        nom_fitxer=storage_name_tiquet,
        content=raw_tiquet,
        content_type=kind_tiquet.mime,
    )

    path_odometre: Optional[str] = None
    if raw_odometre:
        storage_name_odo = f"{uuid.uuid4().hex}.{ext_odometre}"
        path_odometre = await SovereignStorageGateway.pujar_fitxer_binari(
            db=db,
            empresa_id=str(emp_uuid),
            categoria="tiquets_despesa",
            nom_fitxer=storage_name_odo,
            content=raw_odometre,
            content_type=mime_odometre,
        )

    nou_tiquet = TiquetDespesa(
        id=uuid.uuid4(),
        empresa_id=emp_uuid,
        categoria=cat_norm,
        usuari_id=usuari_uuid,
        vehicle_id=veh_uuid,
        ordre_treball_id=ot_uuid,
        data_tiquet=date.today(),
        base_imposable=None,
        import_total=None,
        estat_aprovacio="PENDENT_PROCESSAMENT",
        estat_fiscal="PENDENT_OCR",
        requereix_aprovacio_boss=False,
        custodia_paper_confirmada=False,
        nom_fitxer_visible=nom_fitxer_visible,
        foto_tiquet_path=path_tiquet,
        foto_odometre_path=path_odometre,
    )
    db.add(nou_tiquet)
    await db.flush()
    tiquet_id_str = str(nou_tiquet.id)
    created_at_iso = nou_tiquet.created_at.isoformat() if nou_tiquet.created_at else None
    await db.commit()

    processar_tiquet_ocr_a_gestio_task.apply_async(
        args=[str(emp_uuid), tiquet_id_str],
        queue="queue_documents",
    )

    return {
        "id": tiquet_id_str,
        "categoria": cat_norm,
        "estat_aprovacio": "PENDENT_PROCESSAMENT",
        "nom_fitxer_visible": nom_fitxer_visible,
        "custodia_paper_confirmada": False,
        "te_foto_odometre": bool(path_odometre),
        "ordre_treball_id": str(ot_uuid) if ot_uuid else None,
        "vehicle_id": str(veh_uuid) if veh_uuid else None,
        "created_at": created_at_iso,
    }


@router.get("/tiquets/avui")
async def llistar_tiquets_avui_operari(
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    """Retorna exclusivament la llista Zero-Thumbnail de tiquets capturats avui per l'operari."""
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="Tenant context missing")

    emp_uuid = uuid.UUID(str(empresa_id))
    claims = get_current_user_claims(request)
    usuari_uuid = uuid.UUID(str(claims.get("sub")))

    res = await db.execute(
        select(TiquetDespesa)
        .where(
            TiquetDespesa.empresa_id == emp_uuid,
            TiquetDespesa.usuari_id == usuari_uuid,
            TiquetDespesa.data_tiquet == date.today(),
            TiquetDespesa.custodia_paper_confirmada.is_(False),
        )
        .order_by(TiquetDespesa.created_at.desc())
    )
    files = res.scalars().all()
    return [
        {
            "id": str(f.id),
            "categoria": f.categoria,
            "nom_fitxer_visible": f.nom_fitxer_visible or "tiquet_tmp.webp",
            "estat_aprovacio": f.estat_aprovacio,
            "custodia_paper_confirmada": bool(f.custodia_paper_confirmada),
            "te_foto_odometre": bool(f.foto_odometre_path),
            "ordre_treball_id": str(f.ordre_treball_id) if f.ordre_treball_id else None,
            "created_at": f.created_at.isoformat() if f.created_at else None,
        }
        for f in files
    ]


@router.post("/tiquets/checkout-custodia")
async def confirmar_custodia_tiquets_avui(
    request: Request,
    payload: Optional[CheckoutCustodiaRequest] = None,
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    """Confirma la custòdia física dels tiquets de la safata diària en fer el Checkout de jornada."""
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="Tenant context missing")

    emp_uuid = uuid.UUID(str(empresa_id))
    claims = get_current_user_claims(request)
    usuari_uuid = uuid.UUID(str(claims.get("sub")))

    stmt = select(TiquetDespesa).where(
        TiquetDespesa.empresa_id == emp_uuid,
        TiquetDespesa.usuari_id == usuari_uuid,
        TiquetDespesa.custodia_paper_confirmada.is_(False),
    )
    if payload and payload.tiquet_ids:
        stmt = stmt.where(TiquetDespesa.id.in_(payload.tiquet_ids))

    res = await db.execute(stmt)
    tiquets = res.scalars().all()
    for t in tiquets:
        t.custodia_paper_confirmada = True
    await db.commit()
    return {"status": "OK", "confirmats": len(tiquets)}
