"""Tests per al servei de documents, logotips sobirans (/docs/ i /data/) i resolució de marca pública.

Verifica (Zero Mock sobre PostgreSQL real):
- Protecció contra Path Traversal
- Resolució de logotip corporatiu (fitxer real i fallback dinàmic SVG)
- Fallback 404 net per a fitxers inexistents
- Resolució amb i sense trailing slash a /public/tenant-config/ i /gestio/configuracio/marca/
"""

import os
import tempfile
import uuid
from pathlib import Path

import pytest
from httpx import AsyncClient

from app.api.v1.docs_serve import _validar_seguretat_path
from app.core.branding import generar_svg_monograma, resoldre_fitxer_logotip_local
from app.models.models import Empresa


class patch_env:
    def __init__(self, key: str, val: str):
        self.key = key
        self.val = val
        self.old: str | None = None

    def __enter__(self) -> None:
        self.old = os.environ.get(self.key)
        os.environ[self.key] = self.val

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        if self.old is not None:
            os.environ[self.key] = self.old
        else:
            os.environ.pop(self.key, None)


def test_path_traversal_detection() -> None:
    """Valida que qualsevol intent de Path Traversal sigui interceptat amb HTTP 400."""
    with pytest.raises(Exception):
        _validar_seguretat_path("../etc/passwd")

    with pytest.raises(Exception):
        _validar_seguretat_path("empresa/../../config.json")

    with pytest.raises(Exception):
        _validar_seguretat_path("empresa/test\0file.txt")


def test_generar_svg_monograma() -> None:
    """Valida que el monograma SVG contingui les inicials i el color primari."""
    svg = generar_svg_monograma("Acme Construccions", "210 100% 40%")
    assert "<svg" in svg
    assert "AC" in svg
    assert "hsl(210 100% 40%)" in svg

    svg_default = generar_svg_monograma(None, None)
    assert "<svg" in svg_default
    assert "SV" in svg_default


def test_resoldre_fitxer_logotip_local_existent() -> None:
    """Valida la resolució quan el fitxer existeix físicament."""
    empresa_id = str(uuid.uuid4())
    with tempfile.TemporaryDirectory() as tmpdir:
        logo_dir = (
            Path(tmpdir)
            / f"disc_{empresa_id}"
            / "11_configuracio_i_backups"
            / "identitat_camaleo"
        )
        logo_dir.mkdir(parents=True, exist_ok=True)
        logo_file = logo_dir / "logo_oficial.png"
        logo_file.write_bytes(b"\x89PNG\r\n\x1a\n")

        with patch_env("CLIENT_DISKS_MOUNT_ROOT", tmpdir):
            resolved = resoldre_fitxer_logotip_local(None, empresa_id)
            assert resolved == str(logo_file)


@pytest.mark.asyncio
async def test_docs_serve_logo_fallback_svg(async_client: AsyncClient) -> None:
    """Valida que una sol·licitud a /docs/<empresa_id>/configuracio/logo_oficial.jpg retorni SVG dinàmic si no és a disc."""
    empresa_id = str(uuid.uuid4())
    response = await async_client.get(f"/docs/{empresa_id}/configuracio/logo_oficial.jpg")
    assert response.status_code == 200
    assert "image/svg+xml" in response.headers.get("content-type", "")
    assert "<svg" in response.text


@pytest.mark.asyncio
async def test_docs_serve_inexistent_non_logo_404(async_client: AsyncClient) -> None:
    """Valida que fitxers no-logo inexistents retornin 404 net."""
    response = await async_client.get("/docs/random_empresa/planols/inexistent_planol.pdf")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_public_tenant_config_and_marca_trailing_slash(
    async_client: AsyncClient, headers: dict[str, str], admin_session: object
) -> None:
    """Valida que /public/tenant-config/?domain=... i /gestio/configuracio/marca/ responguin 200 OK."""
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession

    session: AsyncSession = admin_session  # type: ignore[assignment]
    empresa_id = uuid.UUID(headers["X-Empresa-ID"])
    domini_test = f"sevalormante-{empresa_id.hex[:6]}.projectexinoxano.cat"

    res = await session.execute(select(Empresa).where(Empresa.id == empresa_id))
    empresa = res.scalar_one_or_none()
    if not empresa:
        empresa = Empresa(
            id=empresa_id,
            nom="Sevalor Manteniment SL",
            nif=f"B{empresa_id.hex[:8].upper()}",
            subdomini=f"sevalormante-{empresa_id.hex[:6]}",
            domini_custom=domini_test,
            primari_hsl="142 71% 25%",
            secundari_hsl="142 45% 15%",
            accent_hsl="38 92% 50%",
        )
        session.add(empresa)
    else:
        empresa.domini_custom = domini_test
    await session.commit()

    # Amb trailing slash (com fa Next.js trailingSlash: true)
    r_pub = await async_client.get(f"/public/tenant-config/?domain={domini_test}")
    assert r_pub.status_code == 200
    data_pub = r_pub.json()
    assert data_pub["id"] == str(empresa_id)

    # Endpoint de marca amb trailing slash
    r_marca = await async_client.get("/gestio/configuracio/marca/", headers=headers)
    assert r_marca.status_code == 200
    data_marca = r_marca.json()
    assert "primari_hsl" in data_marca
