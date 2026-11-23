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
async def test_generacio_aeat_json(admin_session):
    """Test directe del worker d'exportació AEAT amb dades reals a PostgreSQL (Spec 024 / Zero-Mock)."""
    from datetime import datetime, timezone

    from app.core.db import set_tenant_context
    from app.models.models import Client, Empresa, FacturaCapcalera

    trimestre = "2024-Q3"

    # 1. Sense factures al trimestre -> Zero-Mock retorna 0.0
    empresa_buida_id = str(uuid.uuid4())
    res_buit = generar_exportacio_aeat.apply(args=[empresa_buida_id, trimestre]).get()
    assert res_buit["status"] == "COMPLETED"
    assert res_buit["payload_summary"]["facturacion"] == 0.0
    assert res_buit["payload_summary"]["num_factures"] == 0

    # 2. Amb factura real emesa al Q3 2024 -> calcula el sumatori real des de PostgreSQL
    emp_id = uuid.uuid4()
    cli_id = uuid.uuid4()
    suf = emp_id.hex[:8]
    admin_session.add(
        Empresa(
            id=emp_id,
            nom=f"Test AEAT Worker {suf}",
            nif=f"B{suf.upper()}",
            subdomini=f"aeatw-{suf}",
            pla_subscripcio="PRO",
            estat_pagament="ACTIU",
        )
    )
    await admin_session.flush()
    await set_tenant_context(admin_session, str(emp_id), is_superadmin=False, role="BOSS")
    admin_session.add(
        Client(
            id=cli_id,
            empresa_id=emp_id,
            codi=f"C-{suf}",
            rao_social="Client Exportacio AEAT S.L.",
            nif="B12345678",
        )
    )
    await admin_session.flush()
    admin_session.add(
        FacturaCapcalera(
            empresa_id=emp_id,
            exercici=2024,
            serie="F",
            numero_factura=1,
            num_serie_verifactu="F-2024-0001",
            tipus_factura="F1",
            client_id=cli_id,
            estat_document="EMESA",
            estat_anulacio="ACTIVA",
            data_emissio=datetime(2024, 8, 15, tzinfo=timezone.utc),
            base_imposable=1500.50,
            quota_iva=315.10,
            import_total_verifactu=1815.60,
            liquid_exigible=1815.60,
            hash_sha256="A" * 64,
        )
    )
    await admin_session.flush()

    result = await generar_exportacio_aeat.apply(
        args=[str(emp_id), trimestre],
        kwargs={"db_session": admin_session},
    ).get()

    assert result["status"] == "COMPLETED"
    assert "payload_summary" in result
    payload = result["payload_summary"]
    assert payload["trimestre"] == trimestre
    assert payload["empresa_id"] == str(emp_id)
    assert payload["facturacion"] == 1500.50
    assert payload["iva_meritat"] == 315.10
    assert payload["num_factures"] == 1
