"""Endpoints públics verificats per token HMAC per consultar, descarregar i acceptar/rebutjar pressupostos."""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.models.models import Client, Empresa, Pressupost
from app.services.pressupost_service import (
    DEFAULT_VALIDESA_DIES,
    carregar_detalls_pressupostos_map,
    desar_detalls_pressupost_disc,
    generar_pdf_pressupost_bytes,
    verificar_token_acceptacio_pressupost,
)

router = APIRouter(prefix="/public/pressupostos", tags=["Portal Públic Pressupostos"])


class RespondrePressupostPublicRequest(BaseModel):
    accio: str = Field(..., pattern="^(APROVAR|REBUTJAR)$")
    comentari: Optional[str] = Field(None, max_length=500)


async def _resolver_pressupost_per_token(
    db: AsyncSession, token: str
) -> tuple[uuid.UUID, Pressupost, Optional[Client], Optional[Empresa], Dict[str, Any]]:
    verified = verificar_token_acceptacio_pressupost(token)
    if not verified:
        raise HTTPException(
            status_code=404,
            detail="L'enllaç del pressupost no és vàlid o ha caducat.",
        )
    empresa_id, pressupost_id = verified

    # Injectar context RLS estricte del tenant verificat pel token HMAC
    await db.execute(
        text("SELECT set_config('app.current_empresa_id', :emp, true);"),
        {"emp": str(empresa_id)},
    )
    await db.execute(text("SELECT set_config('app.current_user_role', 'BOSS', true);"))

    pressupost = (
        await db.execute(
            select(Pressupost).where(
                Pressupost.id == pressupost_id,
                Pressupost.empresa_id == empresa_id,
            )
        )
    ).scalar_one_or_none()
    if not pressupost:
        raise HTTPException(status_code=404, detail="Pressupost no trobat.")

    empresa = (await db.execute(select(Empresa).where(Empresa.id == empresa_id))).scalar_one_or_none()
    client = (
        await db.execute(
            select(Client).where(Client.id == pressupost.client_id, Client.empresa_id == empresa_id)
        )
    ).scalar_one_or_none()
    detalls_map = await carregar_detalls_pressupostos_map(db, empresa_id)
    detalls = dict(detalls_map.get(str(pressupost.id), {}))
    return empresa_id, pressupost, client, empresa, detalls


@router.get("/{token}")
async def obtenir_pressupost_public(
    token: str,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Retorna la vista pública del pressupost per al client final."""
    _, pressupost, client, empresa, detalls = await _resolver_pressupost_per_token(db, token)
    linies: List[Dict[str, Any]] = detalls.get("linies") or []
    total_val = float(pressupost.total) if pressupost.total is not None else 0.0
    raw_base = detalls.get("base_imposable")
    base_val = float(raw_base) if raw_base is not None else total_val
    raw_sub = detalls.get("subtotal_brut")
    subtotal_brut_val = float(raw_sub) if raw_sub is not None else base_val
    return {
        "id": str(pressupost.id),
        "numero": pressupost.numero,
        "titol": detalls.get("titol") or f"Pressupost {pressupost.numero}",
        "descripcio": detalls.get("descripcio"),
        "adreca_obra": detalls.get("adreca_obra"),
        "data_pressupost": detalls.get("data_pressupost")
        or (pressupost.created_at.date().isoformat() if pressupost.created_at else None),
        "referencia_client": detalls.get("referencia_client"),
        "elaborat_per": detalls.get("elaborat_per"),
        "vehicle_nom": detalls.get("vehicle_nom"),
        "eines_resum": detalls.get("eines_resum") or [],
        "desplacament_km": detalls.get("desplacament_km"),
        "desplacament_preu_km": detalls.get("desplacament_preu_km"),
        "desplacament_import_fix": detalls.get("desplacament_import_fix"),
        "estat": pressupost.estat,
        "subtotal_brut": subtotal_brut_val,
        "descompte_global_pct": float(detalls.get("descompte_global_pct") or 0.0),
        "descompte_global_import": float(detalls.get("descompte_global_import") or 0.0),
        "base_imposable": base_val,
        "quota_iva": float(detalls.get("quota_iva") or 0.0),
        "total": total_val,
        "validesa_dies": int(detalls.get("validesa_dies") or DEFAULT_VALIDESA_DIES),
        "forma_pagament": detalls.get("forma_pagament"),
        "percentatge_acompte": float(detalls.get("percentatge_acompte") or 0.0),
        "termini_execucio": detalls.get("termini_execucio"),
        "notes_exclusions": detalls.get("notes_exclusions"),
        "mencio_legal": detalls.get("mencio_legal"),
        "linies": linies,
        "created_at": pressupost.created_at.isoformat() if pressupost.created_at else None,
        "motiu_canvis_client": detalls.get("motiu_canvis_client"),
        "client_nom": detalls.get("client_rao_social") or (client.rao_social if client else None),
        "client_nif": detalls.get("client_nif") or (client.nif if client else None),
        "client_adreca": detalls.get("client_adreca") or (client.adreca_fiscal if client else None),
        "client_persona_contacte": detalls.get("client_persona_contacte")
        or (getattr(client, "persona_contacte", None) if client else None),
        "empresa": {
            "nom": empresa.nom if empresa else "Sevalor Suite",
            "nif": empresa.nif if empresa else None,
            "adreca": empresa.adreca if empresa else None,
            "primari_hsl": empresa.primari_hsl if empresa else "150 40 20",
            "secundari_hsl": empresa.secundari_hsl if empresa else "38 92% 50%",
        },
    }


@router.get("/{token}/pdf")
async def descarregar_pressupost_public_pdf(
    token: str,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Descarrega el PDF oficial del pressupost des de l'enllaç públic."""
    _, pressupost, client, empresa, detalls = await _resolver_pressupost_per_token(db, token)
    pdf_bytes = generar_pdf_pressupost_bytes(
        empresa=empresa,
        client=client,
        pressupost=pressupost,
        detalls=detalls,
        acceptacio_url=None,
    )
    safe_num = pressupost.numero.replace("/", "_").replace(" ", "_")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="PRESSUPOST_{safe_num}.pdf"'},
    )


@router.post("/{token}/respondre")
async def respondre_pressupost_public(
    token: str,
    payload: RespondrePressupostPublicRequest,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Permet al client final acceptar o demanar canvis en un pressupost pendent."""
    empresa_id, pressupost, _, _, detalls = await _resolver_pressupost_per_token(db, token)
    if pressupost.estat != "PENDENT":
        raise HTTPException(
            status_code=400,
            detail=f"Aquest pressupost ja es troba en estat '{pressupost.estat}'.",
        )

    now = datetime.now(timezone.utc)
    if payload.accio == "APROVAR":
        pressupost.estat = "APROVAT"
        pressupost.token_signatura = f"PORTAL-APROV-{pressupost.id}"
    else:
        pressupost.estat = "REBUTJAT"
        if payload.comentari:
            detalls["motiu_canvis_client"] = payload.comentari.strip()

    detalls["data_resposta_client"] = now.isoformat()
    pressupost.updated_at = now
    await db.commit()
    await desar_detalls_pressupost_disc(db, empresa_id, pressupost, detalls)

    return {
        "status": "ok",
        "estat": pressupost.estat,
        "numero": pressupost.numero,
        "token_signatura": pressupost.token_signatura,
    }
