import pytest
import os
import uuid
from app.workers.tasks import generar_backup_pgdump, generar_exportacio_aeat

@pytest.mark.asyncio
async def test_generacio_backup_celery():
    """Test directe del worker de backups asíncrons (Spec 024)."""
    empresa_dummy_id = str(uuid.uuid4())
    
    # Executem la tasca de forma síncrona (apply) per al test
    result = generar_backup_pgdump.apply(args=[empresa_dummy_id]).get()
    
    assert result["status"] == "COMPLETED"
    assert "file_path" in result
    assert os.path.exists(result["file_path"])
    assert result["file_path"].endswith(".sql.gz")
    assert result["empresa_id"] == empresa_dummy_id
    
    # Neteja de la prova
    os.remove(result["file_path"])

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
