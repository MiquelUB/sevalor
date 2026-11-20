import uuid

import pytest

from app.workers.tasks import generar_backup_pgdump, generar_exportacio_aeat


@pytest.mark.asyncio
async def test_generacio_backup_celery():
    """Test directe del worker de backups asíncrons (Spec 024 + ADR-001 Zero-Storage)."""
    import shutil

    from app.services.sovereign_storage import SovereignStorageGateway

    empresa_dummy_id = str(uuid.uuid4())

    # Executem la tasca de forma síncrona (apply) per al test
    result = generar_backup_pgdump.apply(args=[empresa_dummy_id]).get()

    assert result["status"] == "COMPLETED"
    assert "file_path" in result
    assert result["file_path"].startswith(
        f"transit://{empresa_dummy_id}/11_configuracio_i_backups/backups_locals/"
    )
    assert result["file_path"].endswith(".sql.gz")
    assert result["empresa_id"] == empresa_dummy_id

    transit_bin = SovereignStorageGateway._trobar_fitxer_transit(empresa_dummy_id, result["file_path"])
    assert transit_bin is not None and transit_bin.is_file()
    assert transit_bin.read_bytes().startswith(b"SVENC1:")

    # Neteja de la cua efímera de la prova
    shutil.rmtree(transit_bin.parent, ignore_errors=True)

@pytest.mark.asyncio
async def test_generacio_aeat_json():
    """Test directe del worker d'exportació AEAT (Spec 024)."""
    empresa_dummy_id = str(uuid.uuid4())
    trimestre = "2024-Q3"

    result = generar_exportacio_aeat.apply(args=[empresa_dummy_id, trimestre]).get()

    assert result["status"] == "COMPLETED"
    assert "payload_summary" in result
    payload = result["payload_summary"]
    assert payload["trimestre"] == trimestre
    assert payload["empresa_id"] == empresa_dummy_id
    assert payload["facturacion"] > 0
    assert "iva_meritat" in payload
