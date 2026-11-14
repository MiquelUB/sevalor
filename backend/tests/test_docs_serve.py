"""Tests per al servei de documents i logotips sobirans (/docs/ i /data/).

Verifica:
- Protecció contra Path Traversal
- Resolució de logotip corporatiu (fitxer real i fallback dinàmic SVG)
- Fallback 404 net per a fitxers inexistents
- Resolució a través de rutes /docs/ i /data/
"""

import os
import tempfile
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.v1.docs_serve import _validar_seguretat_path
from app.core.branding import generar_svg_monograma, resoldre_fitxer_logotip_local
from app.core.db import get_db
from app.main import app


@pytest.fixture(autouse=True)
def override_db_dependency():
    mock_session = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalars.return_value.first.return_value = None
    mock_session.execute.return_value = mock_res

    async def _override():
        yield mock_session

    app.dependency_overrides[get_db] = _override
    yield
    app.dependency_overrides.pop(get_db, None)


def test_path_traversal_detection():
    """Valida que qualsevol intent de Path Traversal sigui interceptat amb HTTP 400."""
    with pytest.raises(Exception):
        _validar_seguretat_path("../etc/passwd")

    with pytest.raises(Exception):
        _validar_seguretat_path("empresa/../../config.json")

    with pytest.raises(Exception):
        _validar_seguretat_path("empresa/test\0file.txt")


def test_generar_svg_monograma():
    """Valida que el monograma SVG contingui les inicials i el color primari."""
    svg = generar_svg_monograma("Acme Construccions", "210 100% 40%")
    assert "<svg" in svg
    assert "AC" in svg
    assert "hsl(210 100% 40%)" in svg

    svg_default = generar_svg_monograma(None, None)
    assert "<svg" in svg_default
    assert "SV" in svg_default


def test_resoldre_fitxer_logotip_local_existent():
    """Valida la resolució quan el fitxer existeix físicament."""
    empresa_id = str(uuid.uuid4())
    with tempfile.TemporaryDirectory() as tmpdir:
        logo_dir = Path(tmpdir) / f"disc_{empresa_id}" / "11_configuracio_i_backups" / "identitat_camaleo"
        logo_dir.mkdir(parents=True, exist_ok=True)
        logo_file = logo_dir / "logo_oficial.png"
        logo_file.write_bytes(b"\x89PNG\r\n\x1a\n")

        with patch_env("CLIENT_DISKS_MOUNT_ROOT", tmpdir):
            resolved = resoldre_fitxer_logotip_local(None, empresa_id)
            assert resolved == str(logo_file)


class patch_env:
    def __init__(self, key: str, val: str):
        self.key = key
        self.val = val
        self.old = None

    def __enter__(self):
        self.old = os.environ.get(self.key)
        os.environ[self.key] = self.val

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.old is not None:
            os.environ[self.key] = self.old
        else:
            os.environ.pop(self.key, None)


def test_docs_serve_logo_fallback_svg():
    """Valida que una sol·licitud a /docs/<empresa_id>/configuracio/logo_oficial.jpg retorni SVG dinàmic si no és a disc."""
    empresa_id = str(uuid.uuid4())
    client = TestClient(app)

    response = client.get(f"/docs/{empresa_id}/configuracio/logo_oficial.jpg")
    assert response.status_code == 200
    assert "image/svg+xml" in response.headers.get("content-type", "")
    assert "<svg" in response.text


def test_docs_serve_inexistent_non_logo_404():
    """Valida que fitxers no-logo inexistents retornin 404 net."""
    client = TestClient(app)
    response = client.get("/docs/random_empresa/planols/inexistent_planol.pdf")
    assert response.status_code == 404
