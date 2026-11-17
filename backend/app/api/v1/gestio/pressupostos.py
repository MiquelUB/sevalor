"""Endpoints per a la gestió de Pressupostos i integració transaccional amb Telegram (Spec 009 / Phase 4)."""

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_with_tenant_context
from app.core.security import get_current_user_claims, require_roles
from app.models.models import Client, Empresa, Pressupost
from app.services.sovereign_storage import SovereignStorageGateway
from app.services.telegram_service import telegram_service

logger = logging.getLogger("sevalor.pressupostos")

router = APIRouter(
    prefix="/gestio/pressupostos",
    tags=["Gestió Pressupostos i Telegram"],
    dependencies=[Depends(require_roles(["BOSS", "SECRETARIA", "ENGINYER"]))],
)


# ---------------------------------------------------------------------------
# DTOs / Esquemes Pydantic
# ---------------------------------------------------------------------------


class PressupostCreate(BaseModel):
    client_id: uuid.UUID
    numero: str = Field(..., max_length=30)
    total: float = Field(default=0.00, ge=0.0)


class PressupostResponse(BaseModel):
    id: uuid.UUID
    empresa_id: uuid.UUID
    client_id: uuid.UUID
    numero: str
    total: float
    estat: str
    token_signatura: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=List[PressupostResponse])
async def llistar_pressupostos(
    client_id: Optional[uuid.UUID] = Query(None),
    estat: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(get_current_user_claims),
):
    """Llista els pressupostos de l'empresa (filtrats per RLS)."""
    empresa_id_str = claims.get("empresa_id")
    if not empresa_id_str:
        raise HTTPException(status_code=400, detail="Falta el tenant al token.")
    empresa_id = uuid.UUID(empresa_id_str)

    stmt = select(Pressupost).where(Pressupost.empresa_id == empresa_id)
    if client_id:
        stmt = stmt.where(Pressupost.client_id == client_id)
    if estat:
        stmt = stmt.where(Pressupost.estat == estat.upper())

    stmt = stmt.order_by(Pressupost.created_at.desc())
    res = await db.execute(stmt)
    return res.scalars().all()


async def _sync_pressupost_disc(
    db: AsyncSession, empresa_id: uuid.UUID, pressupost: Pressupost
) -> None:
    """Sincronitza el pressupost a 04_factures/prefactures_i_pressupostos al disc de l'empresa."""
    try:
        ruta = await SovereignStorageGateway.desar_entitat_json(
            db=db,
            empresa_id=empresa_id,
            categoria="pressupostos",
            item_id=str(pressupost.id),
            dades={
                "id": str(pressupost.id),
                "client_id": str(pressupost.client_id),
                "numero": pressupost.numero,
                "total": float(pressupost.total or 0.0),
                "estat": pressupost.estat,
                "created_at": pressupost.created_at.isoformat() if pressupost.created_at else None,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        if not str(ruta).startswith("transit://"):
            await SovereignStorageGateway.drenar_cua_transit_empresa(db, empresa_id)
    except Exception as exc:
        logger.warning("No s'ha pogut sincronitzar el pressupost %s al disc: %s", pressupost.id, exc)


@router.post("", response_model=PressupostResponse, status_code=status.HTTP_201_CREATED)
async def crear_pressupost(
    dades: PressupostCreate,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(get_current_user_claims),
):
    """Crea un nou pressupost en estat PENDENT i el sincronitza al disc dur de l'empresa."""
    empresa_id_str = claims.get("empresa_id")
    if not empresa_id_str:
        raise HTTPException(status_code=400, detail="Falta el tenant al token.")
    empresa_id = uuid.UUID(empresa_id_str)

    # Verificar que el client pertany a l'empresa
    stmt_c = select(Client).where(Client.id == dades.client_id, Client.empresa_id == empresa_id)
    client = (await db.execute(stmt_c)).scalars().first()
    if not client:
        raise HTTPException(
            status_code=404,
            detail="El client especificat no existeix o no pertany a la teva empresa.",
        )

    nou_pressupost = Pressupost(
        id=uuid.uuid4(),
        empresa_id=empresa_id,
        client_id=dades.client_id,
        numero=dades.numero,
        total=dades.total,
        estat="PENDENT",
    )
    db.add(nou_pressupost)
    await db.commit()
    await _sync_pressupost_disc(db, empresa_id, nou_pressupost)
    return nou_pressupost


@router.get("/{pressupost_id}", response_model=PressupostResponse)
async def obtenir_pressupost(
    pressupost_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(get_current_user_claims),
):
    """Obté el detall d'un pressupost per ID (Spec 009 / TEST-F4-01)."""
    empresa_id_str = claims.get("empresa_id")
    if not empresa_id_str:
        raise HTTPException(status_code=400, detail="Falta el tenant al token.")
    empresa_id = uuid.UUID(empresa_id_str)

    stmt = select(Pressupost).where(
        Pressupost.id == pressupost_id, Pressupost.empresa_id == empresa_id
    )
    res = await db.execute(stmt)
    pressupost = res.scalars().first()
    if not pressupost:
        raise HTTPException(status_code=404, detail="Pressupost no trobat.")
    return pressupost


@router.post("/{pressupost_id}/enviar-telegram")
async def enviar_pressupost_via_telegram(
    pressupost_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(get_current_user_claims),
):
    """Envia el pressupost amb Inline Keyboard al client via Telegram (Spec 009 RF-09)."""
    empresa_id_str = claims.get("empresa_id")
    if not empresa_id_str:
        raise HTTPException(status_code=400, detail="Falta el tenant al token.")
    empresa_id = uuid.UUID(empresa_id_str)

    stmt = select(Pressupost).where(
        Pressupost.id == pressupost_id, Pressupost.empresa_id == empresa_id
    )
    res = await db.execute(stmt)
    pressupost = res.scalars().first()
    if not pressupost:
        raise HTTPException(status_code=404, detail="Pressupost no trobat.")

    resultat = await telegram_service.enviar_pressupost_telegram(db, pressupost.id)
    if not resultat.get("ok"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=resultat.get("detail", "No s'ha pogut enviar el missatge per Telegram."),
        )

    return {
        "status": "enviat",
        "pressupost_id": str(pressupost.id),
        "numero": pressupost.numero,
        "chat_id": resultat.get("chat_id"),
    }


@router.post("/{pressupost_id}/aprovar", response_model=PressupostResponse)
async def aprovar_pressupost(
    pressupost_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(get_current_user_claims),
):
    """Aprova un pressupost, canviant el seu estat a APROVAT."""
    empresa_id_str = claims.get("empresa_id")
    if not empresa_id_str:
        raise HTTPException(status_code=400, detail="Falta el tenant al token.")
    empresa_id = uuid.UUID(empresa_id_str)

    stmt = select(Pressupost).where(
        Pressupost.id == pressupost_id, Pressupost.empresa_id == empresa_id
    )
    res = await db.execute(stmt)
    pressupost = res.scalars().first()
    if not pressupost:
        raise HTTPException(status_code=404, detail="Pressupost no trobat.")

    if pressupost.estat != "PENDENT":
        raise HTTPException(
            status_code=400, detail="Només es poden aprovar pressupostos en estat PENDENT."
        )

    pressupost.estat = "APROVAT"
    await db.commit()
    await _sync_pressupost_disc(db, empresa_id, pressupost)
    return pressupost


@router.post("/{pressupost_id}/rebutjar", response_model=PressupostResponse)
async def rebutjar_pressupost(
    pressupost_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(get_current_user_claims),
):
    """Rebutja un pressupost, canviant el seu estat a REBUTJAT."""
    empresa_id_str = claims.get("empresa_id")
    if not empresa_id_str:
        raise HTTPException(status_code=400, detail="Falta el tenant al token.")
    empresa_id = uuid.UUID(empresa_id_str)

    stmt = select(Pressupost).where(
        Pressupost.id == pressupost_id, Pressupost.empresa_id == empresa_id
    )
    res = await db.execute(stmt)
    pressupost = res.scalars().first()
    if not pressupost:
        raise HTTPException(status_code=404, detail="Pressupost no trobat.")

    if pressupost.estat != "PENDENT":
        raise HTTPException(
            status_code=400, detail="Només es poden rebutjar pressupostos en estat PENDENT."
        )

    pressupost.estat = "REBUTJAT"
    await db.commit()
    await _sync_pressupost_disc(db, empresa_id, pressupost)
    return pressupost


@router.post("/generar-ia")
async def generar_pressupost_ia(
    prompt: str = Query(..., description="Descripció del pressupost per a la IA"),
    client_id: Optional[uuid.UUID] = Query(None, description="Client opcional"),
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(get_current_user_claims),
):
    """Genera un esborrany de pressupost via Node IA Local + Catàleg al Disc de l'Empresa (Zero Fallback / Zero Mock)."""
    empresa_id_str = claims.get("empresa_id")
    if not empresa_id_str:
        raise HTTPException(status_code=400, detail="Falta el tenant al token.")
    empresa_id = uuid.UUID(empresa_id_str)
    rol = str(claims.get("rol") or "").upper()

    res_emp = await db.execute(select(Empresa).where(Empresa.id == empresa_id))
    empresa = res_emp.scalar_one_or_none()
    node_url = (empresa.node_ia_url or "").strip() if empresa and empresa.node_ia_url else ""
    disc_url = (
        getattr(empresa, "disc_dur_url", None) or ""
    ).strip() if empresa else ""

    if (
        not empresa
        or not getattr(empresa, "feature_copilot_ia", False)
        or not getattr(empresa, "node_ia_actiu", False)
        or not (node_url or disc_url)
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "COPILOT_DESACTIVAT",
                "message": "El Copilot IA local està desactivat per a aquesta empresa. Zero fallback a Hetzner.",
            },
        )

    articles_disc = await SovereignStorageGateway.llegir_entitats_json(
        db, empresa_id, "magatzem_articles"
    )
    ots_hist = await SovereignStorageGateway.llegir_entitats_json(
        db, empresa_id, "ots_historic"
    )

    tokens = [t for t in re.split(r"[\s,;:.!?]+", prompt.lower()) if len(t) >= 3]
    linies: List[Dict[str, Any]] = []
    total_calculat = 0.0
    te_preus_reals = True
    pot_veure_preus = rol in ("BOSS", "ADMIN", "SECRETARIA")

    for art in articles_disc:
        nom_art = str(art.get("nom") or "")
        ref_art = str(art.get("referencia_inventari") or "")
        blob = f"{nom_art} {ref_art}".lower()
        if any(tok in blob for tok in tokens):
            pvp_raw = art.get("preu_venda")
            pvp = float(pvp_raw) if (pot_veure_preus and pvp_raw is not None and float(pvp_raw) > 0) else None
            if pvp is None:
                te_preus_reals = False
            else:
                total_calculat += pvp
            linies.append(
                {
                    "concepte": nom_art or ref_art,
                    "quantitat": 1,
                    "preu_unitari": pvp,
                    "total": pvp,
                }
            )
            if len(linies) >= 5:
                break

    hist_match = [
        o
        for o in ots_hist
        if any(tok in f"{o.get('titol', '')} {o.get('descripcio', '')}".lower() for tok in tokens)
    ]

    llm_summary: Optional[str] = None
    if node_url.startswith(("http://", "https://")):
        from app.api.v1.gestio.copilot import cridar_lm_studio

        context_str = (
            f"Articles coincidents al catàleg del disc: {len(linies)}. "
            f"Feines històriques similars: {len(hist_match)}."
        )
        llm_summary = await cridar_lm_studio(
            pregunta=f"Redacta una breu justificació tècnica de pressupost per a: {prompt}",
            vertical=empresa.vertical or "SEVALOR",
            context_addicional=context_str,
            empresa=empresa,
        )
        if llm_summary is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "code": "NODE_IA_OFFLINE",
                    "message": "El túnel Copilot / Node IA local no respon. Zero fallback a Hetzner.",
                },
            )
    elif disc_url.startswith(("http://", "https://")) and not node_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "NODE_IA_OFFLINE",
                "message": "Falta configurar node_ia_url per al node IA local de l'empresa.",
            },
        )

    if not linies:
        te_preus_reals = False
        linies.append(
            {
                "concepte": prompt.strip()[:120],
                "quantitat": 1,
                "preu_unitari": None,
                "total": None,
            }
        )

    draft_id = str(uuid.uuid4())
    total_estimat = round(total_calculat, 2) if (pot_veure_preus and te_preus_reals and total_calculat > 0) else None
    draft_payload: Dict[str, Any] = {
        "titol": f"Esborrany Pressupost Copilot — {prompt.strip()[:60]}",
        "resum_tecnic": llm_summary,
        "feines_historiques_similars": len(hist_match),
        "linies": linies,
        "total_estimat": total_estimat,
    }

    await SovereignStorageGateway.desar_entitat_json(
        db=db,
        empresa_id=empresa_id,
        categoria="pressupostos",
        item_id=f"draft_{draft_id}",
        dades={
            "id": draft_id,
            "client_id": str(client_id) if client_id else None,
            "estat": "PENDENT_AUDITORIA",
            "origen": "COPILOT_IA",
            "prompt": prompt,
            "draft": draft_payload,
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    )

    return {
        "id": draft_id,
        "status": "PENDENT_AUDITORIA",
        "draft": draft_payload,
        "missatge": "Proposta PENDENT_AUDITORIA desada al disc de l'empresa per a validació humana (HITL).",
    }
