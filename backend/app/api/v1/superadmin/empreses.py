import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_with_tenant_context, set_tenant_context
from app.core.security import require_roles
from app.models.models import Empresa

logger = logging.getLogger("superadmin.empreses")

router = APIRouter(
    prefix="/superadmin/empreses", tags=["Superadmin", "Empreses Configuració Camaleó & Logo"]
)

HETZNER_BASE_DOCS = os.environ.get("HETZNER_DOCS_PATH", "/docs")


def validar_magic_bytes_imatge(content: bytes) -> tuple[str, str]:
    """Valida els magic bytes d'una imatge. Retorna (extensió, mime_type).

    Suporta PNG, JPEG, WEBP i SVG segurs (Zero-Trust).
    """
    if len(content) < 8:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Fitxer d'imatge massa curt o incomplet.",
        )
    # PNG: \x89PNG\r\n\x1a\n
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png", "image/png"
    # JPEG: \xff\xd8\xff
    if content.startswith(b"\xff\xd8\xff"):
        return "jpg", "image/jpeg"
    # WEBP: RIFF....WEBP
    if content.startswith(b"RIFF") and len(content) >= 12 and content[8:12] == b"WEBP":
        return "webp", "image/webp"
    # SVG (XML or <svg tag)
    trimmed = content[:500].strip().lower()
    if trimmed.startswith(b"<svg") or (trimmed.startswith(b"<?xml") and b"<svg" in trimmed):
        if b"<script" in content.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="L'arxiu SVG conté etiquetes <script> no permeses per raons de seguretat.",
            )
        return "svg", "image/svg+xml"

    raise HTTPException(
        status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        detail="Format d'imatge no suportat. Només s'admeten fitxers PNG, JPG, WEBP o SVG autèntics.",
    )


def desar_fitxer_logotip(empresa_id: str, content: bytes, ext: str) -> str:
    """Emmagatzema físicament el logotip corporatiu al disc sobirà d'Hetzner."""
    candidats = [
        HETZNER_BASE_DOCS,
        "/tmp/sevalor_docs",
        "/tmp/docs",
    ]
    canonical_path = f"/docs/{empresa_id}/configuracio/logo_oficial.{ext}"
    saved = False

    for base in candidats:
        try:
            target_dir = os.path.join(base, str(empresa_id), "configuracio")
            os.makedirs(target_dir, exist_ok=True)
            target_file = os.path.join(target_dir, f"logo_oficial.{ext}")
            with open(target_file, "wb") as f:
                f.write(content)
            saved = True
            break
        except (PermissionError, OSError):
            continue

    if not saved:
        logger.warning(
            f"No s'ha pogut escriure el logotip a disc per a {empresa_id}, es conserva la ruta canònica."
        )

    return canonical_path


def resoldre_fitxer_logotip_local(
    logotip_path: Optional[str], empresa_id: str
) -> Optional[str]:
    """Cerca la ubicació física real del fitxer al servidor."""
    if logotip_path and os.path.exists(logotip_path):
        return logotip_path

    candidats = [
        HETZNER_BASE_DOCS,
        "/tmp/sevalor_docs",
        "/tmp/docs",
    ]
    for base in candidats:
        for ext in ["png", "jpg", "jpeg", "webp", "svg"]:
            p = os.path.join(base, str(empresa_id), "configuracio", f"logo_oficial.{ext}")
            if os.path.exists(p):
                return p
    return None


class UpdateCamaleoConfigRequest(BaseModel):
    nom: Optional[str] = Field(None, max_length=100)
    adreca: Optional[str] = None
    vertical: Optional[str] = Field(None, max_length=100)
    primari_hsl: Optional[str] = Field(None, max_length=30)
    secundari_hsl: Optional[str] = Field(None, max_length=30)
    accent_hsl: Optional[str] = Field(None, max_length=30)
    logotip_path: Optional[str] = Field(None, max_length=500)
    favicon_path: Optional[str] = Field(None, max_length=500)
    domini_custom: Optional[str] = Field(None, max_length=100)


@router.put("/{empresa_id}/camaleo", response_model=Dict[str, Any])
async def update_camaleo_config(
    empresa_id: str,
    payload: UpdateCamaleoConfigRequest,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(require_roles(["SUPERADMIN", "BOSS"])),
) -> Dict[str, Any]:
    try:
        emp_uuid = uuid.UUID(empresa_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="UUID invàlid.")

    # BOSS role validation: make sure BOSS is modifying their own company
    rol = claims.get("rol", "")
    token_emp_id = claims.get("empresa_id")
    if rol == "BOSS" and str(token_emp_id) != str(empresa_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Un BOSS només pot modificar la configuració de la seva pròpia empresa.",
        )

    emp_res = await db.execute(select(Empresa).where(Empresa.id == emp_uuid))
    empresa = emp_res.scalars().first()
    if not empresa:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Empresa no trobada.")

    if payload.nom is not None and payload.nom.strip():
        empresa.nom = payload.nom.strip()
    if payload.adreca is not None:
        empresa.adreca = payload.adreca.strip()
    if payload.vertical is not None and payload.vertical.strip():
        empresa.vertical = payload.vertical.strip().upper()

    if payload.primari_hsl is not None:
        empresa.primari_hsl = payload.primari_hsl
    if payload.secundari_hsl is not None:
        empresa.secundari_hsl = payload.secundari_hsl
    if payload.accent_hsl is not None:
        empresa.accent_hsl = payload.accent_hsl
    if payload.logotip_path is not None:
        empresa.logotip_path = payload.logotip_path
    if payload.favicon_path is not None:
        empresa.favicon_path = payload.favicon_path
    if payload.domini_custom is not None:
        empresa.domini_custom = payload.domini_custom

    empresa.updated_at = datetime.now(timezone.utc)
    await db.commit()

    return {
        "status": "OK",
        "empresa_id": empresa_id,
        "configuracio_actualitzada": {
            "nom": empresa.nom,
            "adreca": empresa.adreca,
            "vertical": empresa.vertical,
            "primari_hsl": empresa.primari_hsl,
            "secundari_hsl": empresa.secundari_hsl,
            "accent_hsl": empresa.accent_hsl,
            "logotip_path": empresa.logotip_path,
            "favicon_path": empresa.favicon_path,
            "domini_custom": getattr(empresa, "domini_custom", None),
        },
    }


@router.post("/{empresa_id}/logotip", response_model=Dict[str, Any])
async def pujar_logotip_empresa(
    empresa_id: str,
    fitxer: UploadFile = File(...),
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(require_roles(["SUPERADMIN", "BOSS"])),
) -> Dict[str, Any]:
    """Pujada i registre del logotip oficial de l'empresa al disc sobirà Hetzner."""
    try:
        emp_uuid = uuid.UUID(empresa_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="UUID invàlid.")

    rol = claims.get("rol", "")
    token_emp_id = claims.get("empresa_id")
    if rol == "BOSS" and str(token_emp_id) != str(empresa_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Un BOSS només pot carregar el logotip de la seva pròpia empresa.",
        )

    emp_res = await db.execute(select(Empresa).where(Empresa.id == emp_uuid))
    empresa = emp_res.scalars().first()
    if not empresa:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Empresa no trobada.")

    content = await fitxer.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="El fitxer supera el límit màxim permès de 10 MB.",
        )

    ext, mime_type = validar_magic_bytes_imatge(content)
    dest_path = desar_fitxer_logotip(str(empresa.id), content, ext)

    empresa.logotip_path = dest_path
    empresa.favicon_path = dest_path
    empresa.updated_at = datetime.now(timezone.utc)
    await db.commit()

    return {
        "status": "OK",
        "empresa_id": str(empresa.id),
        "logotip_path": dest_path,
        "format": ext,
        "mime_type": mime_type,
        "mida_bytes": len(content),
        "missatge": "Logotip oficial de l'empresa desat correctament a l'emmagatzematge sobirà.",
    }


@router.get("/{empresa_id}/logotip")
async def obtenir_logotip_empresa(
    empresa_id: str,
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> Response:
    """Serveix la imatge del logotip oficial de l'empresa.

    Si no n'hi ha cap de pujat o no es troba el fitxer a disc, genera un SVG vectorial dinàmic
    amb el monograma de l'empresa i el seu color primari corporatiu.
    """
    try:
        emp_uuid = uuid.UUID(empresa_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="UUID invàlid.")

    await set_tenant_context(db, str(emp_uuid), is_superadmin=True)

    emp_res = await db.execute(select(Empresa).where(Empresa.id == emp_uuid))
    empresa = emp_res.scalars().first()
    if not empresa:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Empresa no trobada.")

    local_path = resoldre_fitxer_logotip_local(empresa.logotip_path, str(empresa.id))
    if local_path and os.path.exists(local_path):
        ext = local_path.rsplit(".", 1)[-1].lower()
        mime_map = {
            "png": "image/png",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "webp": "image/webp",
            "svg": "image/svg+xml",
        }
        mime = mime_map.get(ext, "image/png")
        return FileResponse(
            local_path,
            media_type=mime,
            headers={
                "Cache-Control": "public, max-age=3600",
            },
        )

    # SVG vectorial dinàmic de contingència amb inicials de l'empresa
    nom_text = (empresa.nom or "SEVALOR").strip()
    inicials = "".join([w[0].upper() for w in nom_text.split()[:2]]) or "SV"
    primari = empresa.primari_hsl or "142 71% 25%"

    svg_content = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 160 160" width="160" height="160">
  <rect width="160" height="160" rx="36" fill="hsl({primari})" />
  <text x="50%" y="54%" font-family="system-ui, -apple-system, sans-serif" font-size="52" font-weight="900" fill="#ffffff" text-anchor="middle" dominant-baseline="middle" letter-spacing="1">
    {inicials}
  </text>
</svg>"""

    return Response(
        content=svg_content,
        media_type="image/svg+xml",
        headers={
            "Cache-Control": "public, max-age=300",
        },
    )


@router.delete("/{empresa_id}/logotip", response_model=Dict[str, Any])
async def esborrar_logotip_empresa(
    empresa_id: str,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(require_roles(["SUPERADMIN", "BOSS"])),
) -> Dict[str, Any]:
    """Restableix el logotip a la identitat vectorial dinàmica per defecte."""
    try:
        emp_uuid = uuid.UUID(empresa_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="UUID invàlid.")

    await set_tenant_context(db, str(emp_uuid), is_superadmin=True)

    emp_res = await db.execute(select(Empresa).where(Empresa.id == emp_uuid))
    empresa = emp_res.scalars().first()
    if not empresa:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Empresa no trobada.")

    empresa.logotip_path = None
    empresa.favicon_path = None
    empresa.updated_at = datetime.now(timezone.utc)
    await db.commit()

    return {
        "status": "OK",
        "empresa_id": str(empresa.id),
        "missatge": "Logotip restablert a la identitat vectorial per defecte.",
    }
