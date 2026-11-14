"""Rutes públiques per servir documents, plànols i logotips sobirans (/docs/ i /data/).

Garanteix resolució directa i resilient de fitxers al disc dur sobirà
amb protecció estricta contra Path Traversal (Zero-Trust) i fallback Camaleó.
"""

import mimetypes
import os
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.branding import MIME_MAP, generar_svg_monograma, servir_logotip_empresa
from app.core.db import get_db
from app.models.models import Empresa

router = APIRouter(tags=["Documents & Logos Sobirans"])

HETZNER_BASE_DOCS = os.environ.get("HETZNER_DOCS_PATH", "/docs")
CLIENT_DISKS_ROOT = os.getenv("CLIENT_DISKS_MOUNT_ROOT", "/tmp/sevalor_client_disks")

ALLOWED_BASES = [
    HETZNER_BASE_DOCS,
    "/docs",
    "/data",
    CLIENT_DISKS_ROOT,
    "/tmp/sevalor_docs",
    "/tmp/docs",
    "/tmp/data",
    "/tmp/sevalor_client_disks",
]


def _validar_seguretat_path(file_path: str) -> str:
    """Valida i neteja el path per evitar qualsevol atac de Path Traversal."""
    clean = file_path.strip().replace("\\", "/")
    if "\0" in clean or ".." in clean.split("/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ruta de fitxer no permesa (Path Traversal detectat).",
        )
    return clean.lstrip("/")


def _obtenir_mime_type(nom_fitxer: str) -> str:
    ext = nom_fitxer.rsplit(".", 1)[-1].lower() if "." in nom_fitxer else ""
    if ext in MIME_MAP:
        return MIME_MAP[ext]
    mime, _ = mimetypes.guess_type(nom_fitxer)
    return mime or "application/octet-stream"


async def _servir_fitxer_generat(
    prefix_dir: str,
    file_path: str,
    db: AsyncSession,
) -> Response:
    clean_path = _validar_seguretat_path(file_path)
    parts = clean_path.split("/")

    # Detectar si és una sol·licitud de logotip / identitat corporativa
    is_logo_request = (
        "logo_oficial" in clean_path
        or "configuracio" in parts
        or "identitat_camaleo" in parts
        or (len(parts) > 1 and parts[-1].startswith("logo"))
    )

    empresa_id_candidate: Optional[str] = None
    if len(parts) >= 1:
        primer = parts[0].replace("disc_", "")
        try:
            uuid.UUID(primer)
            empresa_id_candidate = primer
        except ValueError:
            # Pot ser un subdomini o slug
            empresa_id_candidate = primer

    # 1. Cerca directa al sistema de fitxers sobirà
    for base in ALLOWED_BASES:
        # Provar amb prefix_dir (docs/ o data/)
        candidates = [
            os.path.join(base, clean_path),
            os.path.join(base, prefix_dir, clean_path),
        ]
        # Si tenim disc_<empresa_id>
        if empresa_id_candidate and len(parts) >= 2:
            subpath = "/".join(parts[1:])
            candidates.append(os.path.join(base, f"disc_{empresa_id_candidate}", subpath))
            candidates.append(
                os.path.join(
                    base,
                    f"disc_{empresa_id_candidate}",
                    "11_configuracio_i_backups",
                    "identitat_camaleo",
                    parts[-1],
                )
            )

        for cand in candidates:
            try:
                cand_resolved = Path(cand).resolve()
                # Verificar que no s'escapi de la base per symlink
                if any(str(cand_resolved).startswith(str(Path(b).resolve())) for b in ALLOWED_BASES if os.path.exists(b)):
                    if cand_resolved.is_file():
                        mime = _obtenir_mime_type(cand_resolved.name)
                        return FileResponse(
                            str(cand_resolved),
                            media_type=mime,
                            headers={"Cache-Control": "public, max-age=3600"},
                        )
            except Exception:
                continue

    # 2. Si és un logotip i tenim identificador d'empresa, delegar a la cascada sobirana
    if is_logo_request and empresa_id_candidate:
        try:
            return await servir_logotip_empresa(db, empresa_id_candidate)
        except Exception:
            pass

        # Si l'empresa_id_candidate era un subdomini
        stmt = select(Empresa).where(Empresa.subdomini == empresa_id_candidate)
        res = await db.execute(stmt)
        emp_sub = res.scalars().first()
        if emp_sub:
            return await servir_logotip_empresa(db, str(emp_sub.id))

    # 3. Fallback de monograma si el fitxer demanat era un logotip oficial
    if is_logo_request:
        svg = generar_svg_monograma("SEVALOR", "142 71% 25%")
        return Response(
            content=svg,
            media_type="image/svg+xml",
            headers={"Cache-Control": "public, max-age=3600"},
        )

    # 4. Si no s'ha trobat cap fitxer
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Fitxer '{clean_path}' no trobat al disc sobirà.",
    )


@router.get("/docs/{file_path:path}")
async def servir_document_docs(
    file_path: str,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Serveix fitxers sota la ruta /docs/ (logotips, plànols, documents sobirans)."""
    return await _servir_fitxer_generat("docs", file_path, db)


@router.get("/data/{file_path:path}")
async def servir_document_data(
    file_path: str,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Serveix fitxers sota la ruta /data/ (fotos d'incidències, albarans, etc.)."""
    return await _servir_fitxer_generat("data", file_path, db)
