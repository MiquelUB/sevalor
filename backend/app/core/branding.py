"""Utilitats de Marca i Logotips Sobirans (Chameleon UI Engine).

Proporciona resolució resilient de logotips corporatius sobre disc dur sobirà
o generació vectorial dinàmica SVG per monograma en compliment de Zero Mock Data.
"""

import os
import uuid
from typing import Optional

from fastapi.responses import FileResponse, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Empresa

MIME_MAP = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
    "svg": "image/svg+xml",
}


def generar_svg_monograma(nom: Optional[str] = None, primari_hsl: Optional[str] = None) -> str:
    """Genera un SVG vectorial dinàmic amb les inicials i el color primari de l'empresa."""
    nom_text = (nom or "SEVALOR").strip()
    words = nom_text.split()
    if len(words) >= 2:
        inicials = (words[0][0] + words[1][0]).upper()
    elif len(words) == 1 and len(words[0]) >= 2:
        if words[0].upper().startswith("SEVALOR"):
            inicials = "SV"
        else:
            inicials = words[0][:2].upper()
    else:
        inicials = "SV"

    primari = primari_hsl or "142 71% 25%"

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 160 160" width="160" height="160">
  <rect width="160" height="160" rx="36" fill="hsl({primari})" />
  <text x="50%" y="54%" font-family="system-ui, -apple-system, sans-serif" font-size="56" font-weight="800" fill="#ffffff" text-anchor="middle" dominant-baseline="middle" letter-spacing="2">{inicials}</text>
</svg>"""


def resoldre_fitxer_logotip_local(
    logotip_path: Optional[str], empresa_id: str
) -> Optional[str]:
    """Cerca la ubicació física real del fitxer al disc dur sobirà."""
    if logotip_path and os.path.exists(logotip_path) and os.path.isfile(logotip_path):
        return logotip_path

    base_vaults = os.getenv("CLIENT_DISKS_MOUNT_ROOT", "/tmp/sevalor_client_disks")
    hetzner_docs = os.getenv("HETZNER_DOCS_PATH", "/docs")

    bases = [
        hetzner_docs,
        "/docs",
        "/data",
        base_vaults,
        "/tmp/sevalor_docs",
        "/tmp/docs",
        "/tmp/sevalor_client_disks",
    ]

    # Si tenim un logotip_path que comença per /docs/ o /data/
    if logotip_path:
        clean_rel = logotip_path.lstrip("/")
        if clean_rel.startswith("docs/"):
            clean_rel = clean_rel[len("docs/") :]
        elif clean_rel.startswith("data/"):
            clean_rel = clean_rel[len("data/") :]

        for base in bases:
            candidate = os.path.join(base, clean_rel)
            if os.path.exists(candidate) and os.path.isfile(candidate):
                return candidate

    # Cerca per patrons canònics de configuració
    for base in bases:
        for ext in ["png", "jpg", "jpeg", "webp", "svg"]:
            p = os.path.join(
                base, f"disc_{empresa_id}", "11_configuracio_i_backups", "identitat_camaleo", f"logo_oficial.{ext}"
            )
            if os.path.exists(p) and os.path.isfile(p):
                return p
            p_old = os.path.join(base, str(empresa_id), "configuracio", f"logo_oficial.{ext}")
            if os.path.exists(p_old) and os.path.isfile(p_old):
                return p_old

    return None


async def servir_logotip_empresa(
    db: AsyncSession,
    empresa_id: str | uuid.UUID,
    nom_fallback: Optional[str] = None,
    primari_fallback: Optional[str] = None,
) -> Response:
    """Serveix el logotip d'una empresa amb cascada: fitxer local -> vault sobirà -> SVG dinàmic."""
    emp_uuid = uuid.UUID(str(empresa_id)) if isinstance(empresa_id, str) else empresa_id
    stmt = select(Empresa).where(Empresa.id == emp_uuid)
    res = await db.execute(stmt)
    empresa = res.scalars().first()

    nom = (empresa.nom if empresa else None) or nom_fallback or "SEVALOR"
    primari = (empresa.primari_hsl if empresa else None) or primari_fallback or "142 71% 25%"
    logotip_path = empresa.logotip_path if empresa else None

    # 1. Cerca al sistema de fitxers local
    local_path = resoldre_fitxer_logotip_local(logotip_path, str(emp_uuid))
    if local_path and os.path.exists(local_path):
        ext = local_path.rsplit(".", 1)[-1].lower()
        mime = MIME_MAP.get(ext, "image/png")
        return FileResponse(
            local_path,
            media_type=mime,
            headers={"Cache-Control": "public, max-age=3600"},
        )

    # 2. Emmagatzematge sobirà en trànsit o vault HTTP
    if logotip_path and (logotip_path.startswith("vault://") or logotip_path.startswith("transit://")):
        try:
            from app.services.sovereign_storage import SovereignStorageGateway

            raw_bytes, detected_mime = await SovereignStorageGateway.obtenir_bytes_fitxer(
                db, str(emp_uuid), logotip_path
            )
            return Response(
                content=raw_bytes,
                media_type=detected_mime or "image/png",
                headers={"Cache-Control": "public, max-age=3600"},
            )
        except Exception:
            pass

    # 3. Monograma dinàmic vectorial SVG
    svg_content = generar_svg_monograma(nom, primari)
    return Response(
        content=svg_content,
        media_type="image/svg+xml",
        headers={"Cache-Control": "public, max-age=3600"},
    )
