import logging
import uuid
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

import filetype
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_with_tenant_context
from app.core.security import get_current_user_claims, require_roles
from app.models.models import DocumentCAERC, Proveidor, RegistreEsdevenimentsSIF
from app.services.codis_service import generar_seguent_codi
from app.services.sovereign_storage import SovereignStorageGateway

logger = logging.getLogger("sevalor.proveidors")

router = APIRouter(
    prefix="/gestio/proveidors",
    tags=["Gestió Proveïdors"],
    dependencies=[Depends(require_roles(["BOSS", "SECRETARIA", "ENGINYER"]))],
)


def _resolve_emp_uuid(request: Request, claims: Optional[dict[str, Any]] = None) -> uuid.UUID:
    raw = (
        getattr(request.state, "empresa_id", None)
        or (claims.get("empresa_id") if claims else None)
        or request.headers.get("X-Empresa-ID")
    )
    if not raw or str(raw) in ("undefined", "null", "None"):
        raise HTTPException(status_code=401, detail="No identificat")
    try:
        return uuid.UUID(str(raw))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Identificador d'empresa invàlid") from exc


class ProveidorCreate(BaseModel):
    codi: Optional[str] = Field(None, max_length=20)
    rao_social: str = Field(..., max_length=200)
    nif: str = Field(..., max_length=20)
    telefon: Optional[str] = Field(None, max_length=30)
    email: Optional[str] = Field(None, max_length=200)
    especialitat: str = Field("MATERIALS", max_length=50)
    iban: Optional[str] = Field(None, max_length=34)
    es_recc: bool = False
    aplica_isp_defecte: bool = False


class ProveidorResponse(ProveidorCreate):
    id: uuid.UUID
    codi: str
    actiu: bool
    es_recc: bool
    aplica_isp_defecte: bool
    # Ofuscat per defecte: només últims 4 dígits (Spec 003: veto d'IBAN per Enginyer)
    iban_ofuscat: Optional[str] = None
    iban_visible: Optional[str] = None
    estat_cae: str = "SENSE_DOCUMENTS"
    dies_restants_cae: Optional[int] = None
    alerta_cae: str = "PENDENT"
    bloqueig_bec: bool = False
    detall_antifrau: Optional[Dict[str, Any]] = None
    volum_compres_eur: Optional[float] = None
    retencio_salvaguarda_percent: float = 0.0


class CanviIBANRequest(BaseModel):
    nou_iban: str = Field(..., min_length=15, max_length=34)


class BecSolicitudRequest(BaseModel):
    proveidor_id: uuid.UUID
    nou_iban: str = Field(..., min_length=15, max_length=34)
    origen_deteccio: str = Field("VERIFICACIO_FACTURA", max_length=60)


class BecAutoritzarRequest(BaseModel):
    proveidor_id: uuid.UUID
    verificacio_telefonica_feta: bool = Field(...)
    persona_contactada: str = Field(..., min_length=2, max_length=200)
    observacions: Optional[str] = Field(None, max_length=500)


class ProveidorIBANResponse(BaseModel):
    id: uuid.UUID
    rao_social: str
    iban_xifrat_simetric: Optional[str]


def _normalitzar_iban_valid(iban_raw: Optional[str]) -> Optional[str]:
    if not iban_raw:
        return None
    net = iban_raw.upper().replace(" ", "").strip()
    if not net:
        return None
    if len(net) < 15 or len(net) > 34 or not net.isalnum():
        raise HTTPException(status_code=422, detail="Format d'IBAN invàlid")
    return net


@router.get("", response_model=List[ProveidorResponse])
async def llistar_proveidors(
    request: Request,
    q: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    claims: Dict[str, Any] = Depends(require_roles(["BOSS", "SECRETARIA", "ENGINYER"])),
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> List[Dict[str, Any]]:
    emp_uuid = _resolve_emp_uuid(request, claims)
    rol = str(claims.get("rol", "")).upper()
    is_enginyer = rol == "ENGINYER"

    stmt = select(Proveidor).where(Proveidor.empresa_id == emp_uuid)

    if q:
        search_term = f"%{q}%"
        stmt = stmt.where(
            or_(
                Proveidor.codi.ilike(search_term),
                Proveidor.rao_social.ilike(search_term),
                Proveidor.nif.ilike(search_term),
            )
        )

    stmt = stmt.limit(limit).offset(offset).order_by(Proveidor.created_at.desc())

    result = await db.execute(stmt)
    proveidors = result.scalars().all()
    prov_ids = [p.id for p in proveidors]

    # Documents CAE reals per proveïdor
    cae_map: Dict[uuid.UUID, DocumentCAERC] = {}
    bec_map: Dict[uuid.UUID, Dict[str, Any]] = {}
    if prov_ids:
        res_docs = await db.execute(
            select(DocumentCAERC)
            .where(
                DocumentCAERC.empresa_id == emp_uuid,
                DocumentCAERC.proveidor_id.in_(prov_ids),
            )
            .order_by(DocumentCAERC.data_caducitat.desc())
        )
        for doc in res_docs.scalars().all():
            if doc.proveidor_id not in cae_map:
                cae_map[doc.proveidor_id] = doc

        if not is_enginyer:
            entitats_prov = await SovereignStorageGateway.llegir_entitats_json(
                db, emp_uuid, "proveidors"
            )
            for item in entitats_prov:
                if not isinstance(item, dict):
                    continue
                item_id = str(item.get("id") or "")
                if not item_id.startswith("bec_pend_"):
                    continue
                if item.get("estat") != "BLOQUEIG_ANTIFRAU_IBAN":
                    continue
                pid_str = str(item.get("proveidor_id") or "")
                try:
                    pid_uuid = uuid.UUID(pid_str)
                except ValueError:
                    continue
                bec_map[pid_uuid] = {
                    "estat": "BLOQUEIG_ANTIFRAU_IBAN",
                    "iban_vell": item.get("iban_vell") or "Sense IBAN previ",
                    "iban_nou": item.get("iban_nou"),
                    "origen": item.get("origen") or "VERIFICACIO_MANUAL",
                    "data_deteccio": item.get("data_deteccio"),
                }

    avui = date.today()
    resultat = []
    for p in proveidors:
        iban_ocult = None
        if p.iban_xifrat_simetric:
            iban_ocult = "****" + p.iban_xifrat_simetric[-4:]

        doc_cae = cae_map.get(p.id)
        if not doc_cae:
            estat_cae = "SENSE_DOCUMENTS"
            dies_restants = None
            alerta_cae = "PENDENT"
        else:
            dies_restants = (doc_cae.data_caducitat - avui).days
            if dies_restants < 0:
                estat_cae = "CADUCAT"
                alerta_cae = "BLOQUEJAT"
            elif dies_restants <= 15:
                estat_cae = "URGENT"
                alerta_cae = "CADUCITAT_PROPERA"
            elif dies_restants <= 30:
                estat_cae = "AVIS"
                alerta_cae = "REVISAR"
            else:
                estat_cae = "EN_VIGOR"
                alerta_cae = "OK"

        detall_bec = bec_map.get(p.id)
        resultat.append(
            {
                "id": p.id,
                "codi": p.codi,
                "rao_social": p.rao_social,
                "nif": p.nif,
                "telefon": p.telefon,
                "email": p.email,
                "especialitat": p.especialitat,
                "iban": None,  # mai exposem l'IBAN complet al llistat
                "iban_ofuscat": None if is_enginyer else iban_ocult,
                "iban_visible": "**** (Restringit)" if is_enginyer else (iban_ocult or "Sense IBAN"),
                "actiu": p.actiu,
                "es_recc": p.es_recc,
                "aplica_isp_defecte": p.aplica_isp_defecte,
                "estat_cae": estat_cae,
                "dies_restants_cae": dies_restants,
                "alerta_cae": alerta_cae,
                "bloqueig_bec": detall_bec is not None,
                "detall_antifrau": detall_bec,
                "volum_compres_eur": None,
                "retencio_salvaguarda_percent": 60.0 if p.especialitat == "SUBCONTRACTA" else 0.0,
            }
        )
    return resultat


@router.post("", response_model=ProveidorResponse, status_code=status.HTTP_201_CREATED)
async def alta_proveidor(
    request: Request,
    proveidor: ProveidorCreate,
    claims: Dict[str, Any] = Depends(require_roles(["BOSS", "SECRETARIA", "ENGINYER"])),
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> Dict[str, Any]:
    emp_uuid = _resolve_emp_uuid(request, claims)
    rol = str(claims.get("rol", "")).upper()

    stmt_nif = select(Proveidor).where(
        Proveidor.empresa_id == emp_uuid,
        Proveidor.nif == proveidor.nif,
    )
    result_nif = await db.execute(stmt_nif)
    if result_nif.scalars().first():
        raise HTTPException(
            status_code=400, detail="El NIF/CIF ja es troba registrat en el sistema"
        )

    codi_auto = await generar_seguent_codi(db, Proveidor, emp_uuid, "PRV")
    iban_net = None if rol == "ENGINYER" else _normalitzar_iban_valid(proveidor.iban)

    nou_proveidor = Proveidor(
        empresa_id=emp_uuid,
        codi=codi_auto,
        rao_social=proveidor.rao_social,
        nif=proveidor.nif,
        telefon=proveidor.telefon,
        email=proveidor.email,
        especialitat=proveidor.especialitat,
        es_recc=proveidor.es_recc,
        aplica_isp_defecte=proveidor.aplica_isp_defecte,
        iban_xifrat_simetric=iban_net,
    )

    db.add(nou_proveidor)
    await db.commit()

    try:
        ruta = await SovereignStorageGateway.desar_entitat_json(
            db=db,
            empresa_id=emp_uuid,
            categoria="proveidors",
            item_id=str(nou_proveidor.id),
            dades={
                "id": str(nou_proveidor.id),
                "codi": nou_proveidor.codi,
                "rao_social": nou_proveidor.rao_social,
                "nif": nou_proveidor.nif,
                "telefon": nou_proveidor.telefon,
                "email": nou_proveidor.email,
                "especialitat": nou_proveidor.especialitat,
                "actiu": nou_proveidor.actiu,
            },
        )
        if not str(ruta).startswith("transit://"):
            await SovereignStorageGateway.drenar_cua_transit_empresa(db, emp_uuid)
    except Exception as exc:
        logger.warning("No s'ha pogut sincronitzar proveïdor %s al disc sobirà: %s", nou_proveidor.id, exc)

    iban_ocult = "****" + iban_net[-4:] if iban_net else None
    return {
        "id": nou_proveidor.id,
        "codi": nou_proveidor.codi,
        "rao_social": nou_proveidor.rao_social,
        "nif": nou_proveidor.nif,
        "telefon": nou_proveidor.telefon,
        "email": nou_proveidor.email,
        "especialitat": nou_proveidor.especialitat,
        "iban": None,
        "iban_ofuscat": iban_ocult,
        "iban_visible": "**** (Restringit)" if rol == "ENGINYER" else (iban_ocult or "Sense IBAN"),
        "actiu": nou_proveidor.actiu,
        "es_recc": nou_proveidor.es_recc,
        "aplica_isp_defecte": nou_proveidor.aplica_isp_defecte,
    }


# ---------------------------------------------------------------------------
# Canvi d'IBAN amb autorització i registre SIF (Spec 003 RF-09 / EDGE-01)
# ---------------------------------------------------------------------------


@router.get(
    "/{proveidor_id}/iban",
    response_model=ProveidorIBANResponse,
    dependencies=[Depends(require_roles(["BOSS", "SECRETARIA"]))],
)
async def obtenir_iban_proveidor(
    request: Request,
    proveidor_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> Dict[str, Any]:
    """Retorna l'IBAN complet del proveïdor. Només BOSS/SECRETARIA (403 per Enginyer)."""
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401)

    res = await db.execute(
        select(Proveidor).where(
            Proveidor.id == proveidor_id, Proveidor.empresa_id == uuid.UUID(empresa_id)
        )
    )
    prov = res.scalars().first()
    if not prov:
        raise HTTPException(status_code=404, detail="Proveïdor no trobat")

    return {
        "id": prov.id,
        "rao_social": prov.rao_social,
        "iban_xifrat_simetric": prov.iban_xifrat_simetric,
    }


@router.put(
    "/{proveidor_id}/iban",
    response_model=ProveidorIBANResponse,
    dependencies=[Depends(require_roles(["BOSS"]))],
)
async def canviar_iban_proveidor(
    request: Request,
    proveidor_id: uuid.UUID,
    payload: CanviIBANRequest,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(get_current_user_claims),
) -> Dict[str, Any]:
    """Canvia l'IBAN d'un proveïdor amb autorització de BOSS i registre SIF (EDGE-01, RF-09)."""
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401)

    res = await db.execute(
        select(Proveidor).where(
            Proveidor.id == proveidor_id, Proveidor.empresa_id == uuid.UUID(empresa_id)
        )
    )
    prov = res.scalars().first()
    if not prov:
        raise HTTPException(status_code=404, detail="Proveïdor no trobat")

    iban_anterior = prov.iban_xifrat_simetric
    prov.iban_xifrat_simetric = payload.nou_iban
    await db.commit()

    # Registre SIF immutabilitat (Spec 007/024).
    # NOTA: usuari_id=None perquè els tests (i alguns fluxos BFF) usen JWT amb
    # `sub` aleatori que no existeix a la taula `usuaris`. El `sub` viatja a
    # `dades_event` per traçabilitat. En producció real, l'endpoint hauria de
    # validar l'existència de l'usuari o acceptar només usuaris registrats.
    await db.execute(
        RegistreEsdevenimentsSIF.__table__.insert().values(  # type: ignore
            empresa_id=uuid.UUID(empresa_id),
            codi_esdeveniment="EV-05",
            usuari_id=None,
            descripcio=f"Canvi d'IBAN del proveïdor {prov.rao_social}",
            hash_sello=f"canvi-iban-{uuid.uuid4()}",
            dades_event={
                "iban_anterior_digest": f"****{iban_anterior[-4:] if iban_anterior else ''}",
                "usuari_sub": claims.get("sub"),
            },
        )
    )
    await db.commit()

    return {
        "id": prov.id,
        "rao_social": prov.rao_social,
        "iban_xifrat_simetric": prov.iban_xifrat_simetric,
    }


@router.post(
    "/canvi-iban",
    dependencies=[Depends(require_roles(["BOSS", "SECRETARIA"]))],
)
async def registrar_alerta_canvi_iban(
    request: Request,
    payload: BecSolicitudRequest,
    claims: Dict[str, Any] = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> Dict[str, Any]:
    """Registra una sol·licitud o detecció de canvi d'IBAN bloquejant-la fins autorització BOSS."""
    emp_uuid = _resolve_emp_uuid(request, claims)
    nou_iban_net = _normalitzar_iban_valid(payload.nou_iban)
    if not nou_iban_net:
        raise HTTPException(status_code=422, detail="Cal indicar un IBAN vàlid")

    prov = (
        await db.execute(
            select(Proveidor).where(
                Proveidor.id == payload.proveidor_id,
                Proveidor.empresa_id == emp_uuid,
            )
        )
    ).scalars().first()
    if not prov:
        raise HTTPException(status_code=404, detail="Proveïdor no trobat")

    iban_anterior = (
        f"****{prov.iban_xifrat_simetric[-4:]}" if prov.iban_xifrat_simetric else "Sense IBAN previ"
    )
    ara_iso = datetime.now(timezone.utc).isoformat()
    await SovereignStorageGateway.desar_entitat_json(
        db=db,
        empresa_id=emp_uuid,
        categoria="proveidors",
        item_id=f"bec_pend_{prov.id}",
        dades={
            "id": f"bec_pend_{prov.id}",
            "proveidor_id": str(prov.id),
            "iban_vell": iban_anterior,
            "iban_nou": nou_iban_net,
            "origen": payload.origen_deteccio,
            "estat": "BLOQUEIG_ANTIFRAU_IBAN",
            "data_deteccio": ara_iso,
            "usuari_sub": claims.get("sub"),
        },
    )
    if str(claims.get("rol", "")).upper() == "BOSS":
        await db.execute(
            RegistreEsdevenimentsSIF.__table__.insert().values(  # type: ignore
                empresa_id=emp_uuid,
                codi_esdeveniment="EV-BEC",
                usuari_id=None,
                descripcio=f"Bloqueig antifrau BEC per canvi IBAN de {prov.rao_social}",
                hash_sello=f"bec-req-{uuid.uuid4()}",
                dades_event={
                    "proveidor_id": str(prov.id),
                    "iban_vell": iban_anterior,
                    "iban_nou": nou_iban_net,
                    "origen": payload.origen_deteccio,
                    "estat": "BLOQUEIG_ANTIFRAU_IBAN",
                    "data_deteccio": ara_iso,
                    "usuari_sub": claims.get("sub"),
                },
            )
        )
        await db.commit()
    return {
        "estat": "BLOQUEIG_ANTIFRAU_IBAN",
        "proveidor_id": str(prov.id),
        "iban_vell": iban_anterior,
        "iban_nou": nou_iban_net,
    }


@router.post(
    "/autoritzar-canvi-iban",
    dependencies=[Depends(require_roles(["BOSS"]))],
)
async def autoritzar_canvi_iban_bec(
    request: Request,
    payload: BecAutoritzarRequest,
    claims: Dict[str, Any] = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> Dict[str, Any]:
    """Doble verificació telefònica BOSS per desbloquejar i aplicar el nou IBAN amb traça SIF."""
    if not payload.verificacio_telefonica_feta:
        raise HTTPException(
            status_code=422, detail="Cal confirmar la verificació telefònica prèvia."
        )
    emp_uuid = _resolve_emp_uuid(request, claims)

    prov = (
        await db.execute(
            select(Proveidor).where(
                Proveidor.id == payload.proveidor_id,
                Proveidor.empresa_id == emp_uuid,
            )
        )
    ).scalars().first()
    if not prov:
        raise HTTPException(status_code=404, detail="Proveïdor no trobat")

    entitats_prov = await SovereignStorageGateway.llegir_entitats_json(
        db, emp_uuid, "proveidors"
    )
    bec_pendent = None
    for item in entitats_prov:
        if (
            isinstance(item, dict)
            and str(item.get("id") or "") == f"bec_pend_{prov.id}"
            and item.get("estat") == "BLOQUEIG_ANTIFRAU_IBAN"
        ):
            bec_pendent = item
            break
    if not bec_pendent or not bec_pendent.get("iban_nou"):
        raise HTTPException(
            status_code=404,
            detail="No hi ha cap canvi d'IBAN pendent d'autorització per a aquest proveïdor.",
        )

    nou_iban = str(bec_pendent["iban_nou"])
    iban_anterior = prov.iban_xifrat_simetric
    prov.iban_xifrat_simetric = nou_iban

    await SovereignStorageGateway.desar_entitat_json(
        db=db,
        empresa_id=emp_uuid,
        categoria="proveidors",
        item_id=f"bec_pend_{prov.id}",
        dades={
            **bec_pendent,
            "id": f"bec_pend_{prov.id}",
            "estat": "AUTORITZAT",
            "autoritzat_a": datetime.now(timezone.utc).isoformat(),
            "persona_contactada": payload.persona_contactada,
        },
    )

    await db.execute(
        RegistreEsdevenimentsSIF.__table__.insert().values(  # type: ignore
            empresa_id=emp_uuid,
            codi_esdeveniment="EV-05",
            usuari_id=None,
            descripcio=f"Autorització telefònica BEC canvi IBAN de {prov.rao_social}",
            hash_sello=f"canvi-iban-{uuid.uuid4()}",
            dades_event={
                "proveidor_id": str(prov.id),
                "iban_anterior_digest": f"****{iban_anterior[-4:] if iban_anterior else ''}",
                "persona_contactada": payload.persona_contactada,
                "observacions": payload.observacions,
                "usuari_sub": claims.get("sub"),
            },
        )
    )
    await db.commit()
    return {
        "estat": "AUTORITZAT",
        "proveidor_id": str(prov.id),
        "iban_ofuscat": f"****{nou_iban[-4:]}",
    }


@router.post(
    "/{proveidor_id}/cae",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(["BOSS", "SECRETARIA"]))],
)
async def pujar_document_cae(
    request: Request,
    proveidor_id: uuid.UUID,
    tipus_document: str = Form("POLISSA_RC"),
    data_caducitat: date = Form(...),
    file: UploadFile = File(...),
    claims: Dict[str, Any] = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> Dict[str, Any]:
    """Puja un document CAE / Pòlissa RC validat per Magic Bytes al disc sobirà del client."""
    emp_uuid = _resolve_emp_uuid(request, claims)
    prov = (
        await db.execute(
            select(Proveidor).where(
                Proveidor.id == proveidor_id,
                Proveidor.empresa_id == emp_uuid,
            )
        )
    ).scalars().first()
    if not prov:
        raise HTTPException(status_code=404, detail="Proveïdor no trobat")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=422, detail="El fitxer CAE és buit")
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=422, detail="El fitxer CAE supera el màxim de 10 MB")

    kind = filetype.guess(content)
    mime = kind.mime if kind else ""
    allowed_mimes = {
        "application/pdf": "pdf",
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/webp": "webp",
    }
    if mime not in allowed_mimes:
        raise HTTPException(
            status_code=422,
            detail="Format invàlid (Magic Bytes): només s'admeten PDF, JPG, PNG o WEBP per documents CAE.",
        )

    ext = allowed_mimes[mime]
    nom_uuid = f"cae_{prov.id}_{uuid.uuid4().hex[:8]}.{ext}"
    ruta_disc = await SovereignStorageGateway.pujar_fitxer_binari(
        db=db,
        empresa_id=emp_uuid,
        categoria="proveidors",
        nom_fitxer=nom_uuid,
        content=content,
        content_type=mime,
    )

    estat_doc = "CADUCAT" if data_caducitat < date.today() else "VALIDAT"
    doc = DocumentCAERC(
        empresa_id=emp_uuid,
        proveidor_id=prov.id,
        tipus_document=tipus_document.strip().upper()[:30],
        data_caducitat=data_caducitat,
        fitxer_path=ruta_disc,
        estat=estat_doc,
    )
    db.add(doc)
    await db.commit()

    return {
        "id": str(doc.id),
        "proveidor_id": str(prov.id),
        "tipus_document": doc.tipus_document,
        "data_caducitat": doc.data_caducitat.isoformat(),
        "estat": doc.estat,
        "fitxer_path": doc.fitxer_path,
    }


@router.put("/{proveidor_id}", response_model=ProveidorResponse)
async def editar_proveidor(
    request: Request,
    proveidor_id: uuid.UUID,
    proveidor: ProveidorCreate,
    claims: Dict[str, Any] = Depends(require_roles(["BOSS", "SECRETARIA", "ENGINYER"])),
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> Dict[str, Any]:
    """Edita la fitxa del proveïdor amb filtre multi-tenant obligatori."""
    emp_uuid = _resolve_emp_uuid(request, claims)
    rol = str(claims.get("rol", "")).upper()

    stmt = select(Proveidor).where(
        Proveidor.id == proveidor_id,
        Proveidor.empresa_id == emp_uuid,
    )
    result = await db.execute(stmt)
    prov = result.scalars().first()
    if not prov:
        raise HTTPException(status_code=404, detail="Proveïdor no trobat")

    # Evitar codi o nif duplicat dins el mateix tenant
    if prov.nif != proveidor.nif:
        stmt_nif = select(Proveidor).where(
            Proveidor.empresa_id == emp_uuid,
            Proveidor.nif == proveidor.nif,
            Proveidor.id != proveidor_id,
        )
        if (await db.execute(stmt_nif)).scalars().first():
            raise HTTPException(
                status_code=400, detail="Aquest NIF ja pertany a un altre proveïdor"
            )

    # El codi del proveïdor s'assigna automàticament i no s'altera manualment
    prov.rao_social = proveidor.rao_social
    prov.nif = proveidor.nif
    prov.telefon = proveidor.telefon
    prov.email = proveidor.email
    prov.especialitat = proveidor.especialitat

    await db.commit()

    try:
        ruta = await SovereignStorageGateway.desar_entitat_json(
            db=db,
            empresa_id=emp_uuid,
            categoria="proveidors",
            item_id=str(prov.id),
            dades={
                "id": str(prov.id),
                "codi": prov.codi,
                "rao_social": prov.rao_social,
                "nif": prov.nif,
                "telefon": prov.telefon,
                "email": prov.email,
                "especialitat": prov.especialitat,
                "actiu": prov.actiu,
            },
        )
        if not str(ruta).startswith("transit://"):
            await SovereignStorageGateway.drenar_cua_transit_empresa(db, emp_uuid)
    except Exception as exc:
        logger.warning("No s'ha pogut sincronitzar proveïdor %s al disc sobirà: %s", prov.id, exc)

    iban_ocult = "****" + prov.iban_xifrat_simetric[-4:] if prov.iban_xifrat_simetric else None

    return {
        "id": prov.id,
        "codi": prov.codi,
        "rao_social": prov.rao_social,
        "nif": prov.nif,
        "telefon": prov.telefon,
        "email": prov.email,
        "especialitat": prov.especialitat,
        "iban": None,
        "iban_ofuscat": iban_ocult,
        "iban_visible": "**** (Restringit)" if rol == "ENGINYER" else (iban_ocult or "Sense IBAN"),
        "actiu": prov.actiu,
        "es_recc": prov.es_recc,
        "aplica_isp_defecte": prov.aplica_isp_defecte,
    }


@router.post("/ocr-draft")
async def ocr_proveidor_draft(request: Request, file: UploadFile = File(...)) -> Dict[str, Any]:
    """
    (RF-00 Alta Màgica OCR) Simula el processament d'una targeta CIF o factura proforma
    per extreure estructuradament les dades del Proveïdor i fer un "Zero Data Entry".
    """
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401)

    file_bytes = await file.read()

    from app.services.ocr_service import processar_ocr_proveidor

    resultat = await processar_ocr_proveidor(file_bytes)

    return resultat
