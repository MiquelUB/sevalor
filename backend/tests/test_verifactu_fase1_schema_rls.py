"""Tests de Fase 1 Veri*factu (HAC/1177/2024): Esquema a028, Unicitat per Exercici, Triggers d'Immutabilitat i RLS."""

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from app.core.db import set_tenant_context
from app.models.models import (
    Client,
    Empresa,
    FacturaCapcalera,
    SaasFacturaB2B,
    VerifactuCadenaTenant,
)


@pytest.mark.asyncio
async def test_fase1_unicitat_exercici_any_nou_i_trigger_immutabilitat(admin_session) -> None:
    """
    Verifica:
    1. Mateixa sèrie i número ('F', 1) en exercicis diferents (2026 vs 2027) pel mateix tenant -> OK.
    2. Esborrany ('PRE', ESBORRANY_PREFACTURA) es pot editar i eliminar.
    3. Factura definitiva ('F', EMESA) bloqueja UPDATE de camps fiscals i DELETE amb VERIFACTU_IMMUTABLE_VIOLATION.
    4. Factura definitiva permet UPDATE de cobrament, CSV AEAT i anul·lació, però impedeix revertir l'anul·lació.
    """
    emp_id = uuid.uuid4()
    cli_id = uuid.uuid4()
    suf = str(emp_id)[:8]

    admin_session.add(
        Empresa(
            id=emp_id,
            nom=f"Verifactu F1 {suf} S.L.",
            rao_social_fiscal=f"Verifactu F1 {suf} S.L.U.",
            nif=f"B{suf.upper()}",
            subdomini=f"vf1-{suf}",
            codi_postal="08001",
            poblacio="Barcelona",
            provincia="Barcelona",
            dades_registre_mercantil="RM Barcelona Tom 12345 Foli 67 Full B-99999",
        )
    )
    await admin_session.flush()

    admin_session.add(
        Client(
            id=cli_id,
            empresa_id=emp_id,
            codi=f"C-{suf}",
            rao_social="Client Fiscal S.L.",
            nif="B11223344",
            codi_postal="17001",
            poblacio="Girona",
            provincia="Girona",
        )
    )
    await admin_session.flush()

    await set_tenant_context(admin_session, str(emp_id), False, role="BOSS")

    # 1. Pre-factura en esborrany: es pot modificar i esborrar
    pref = FacturaCapcalera(
        empresa_id=emp_id,
        client_id=cli_id,
        exercici=2026,
        serie="PRE",
        numero_factura=1,
        num_serie_verifactu="PRE-2026-0001",
        estat_document="ESBORRANY_PREFACTURA",
        base_imposable=100.00,
        quota_iva=21.00,
        import_total_verifactu=121.00,
        liquid_exigible=121.00,
        hash_sha256="ESBORRANY_PREFACTURA",
    )
    admin_session.add(pref)
    await admin_session.flush()

    pref.base_imposable = 150.00
    await admin_session.flush()
    await admin_session.delete(pref)
    await admin_session.flush()

    # 2. Emissió F-2026-0001 i F-2027-0001 (mateixa sèrie i número, diferent exercici -> OK)
    f_2026 = FacturaCapcalera(
        empresa_id=emp_id,
        client_id=cli_id,
        exercici=2026,
        serie="F",
        numero_factura=1,
        num_serie_verifactu="F-2026-0001",
        tipus_factura="F1",
        estat_document="EMESA",
        base_imposable=1000.00,
        quota_iva=210.00,
        import_total_verifactu=1210.00,
        liquid_exigible=1210.00,
        hash_sha256="A" * 64,
        fecha_hora_huso_gen_registro="2026-11-23T12:00:00+01:00",
        qr_verifactu_payload="https://prewww2.aeat.es/wlpl/TIKE-CONT/ValidarQR?nif=B123&numserie=F-2026-0001&fecha=23-11-2026&importe=1210.00",
    )
    f_2027 = FacturaCapcalera(
        empresa_id=emp_id,
        client_id=cli_id,
        exercici=2027,
        serie="F",
        numero_factura=1,
        num_serie_verifactu="F-2027-0001",
        tipus_factura="F1",
        estat_document="EMESA",
        base_imposable=2000.00,
        quota_iva=420.00,
        import_total_verifactu=2420.00,
        liquid_exigible=2420.00,
        hash_anterior="A" * 64,
        hash_sha256="B" * 64,
        fecha_hora_huso_gen_registro="2027-01-02T09:00:00+01:00",
    )
    admin_session.add_all([f_2026, f_2027])
    await admin_session.flush()

    # 3. Intent d'alterar base_imposable d'una factura EMESA -> Bloquejat pel trigger PostgreSQL
    with pytest.raises(DBAPIError) as exc_info:
        async with admin_session.begin_nested():
            await admin_session.execute(
                text("UPDATE factures_capcalera SET base_imposable = 9999.99 WHERE id = :fid"),
                {"fid": f_2026.id},
            )
    assert "VERIFACTU_IMMUTABLE_VIOLATION" in str(exc_info.value)

    # 4. Intent d'esborrar una factura EMESA -> Bloquejat pel trigger PostgreSQL
    with pytest.raises(DBAPIError) as exc_del:
        async with admin_session.begin_nested():
            await admin_session.execute(
                text("DELETE FROM factures_capcalera WHERE id = :fid"),
                {"fid": f_2026.id},
            )
    assert "VERIFACTU_IMMUTABLE_VIOLATION" in str(exc_del.value)

    # 5. Actualitzar cobrament, CSV AEAT i anul·lar és permès, però revertir l'anul·lació està prohibit
    await admin_session.execute(
        text(
            """
            UPDATE factures_capcalera
            SET estat_cobrament = 'COBRADA',
                csv_aeat = 'CSV-AEAT-2026-OK',
                estat_anulacio = 'ANULADA_VERIFACTU',
                hash_anulacio_sha256 = :h_anul,
                data_anulacio = :d_anul
            WHERE id = :fid
            """
        ),
        {
            "h_anul": "C" * 64,
            "d_anul": datetime.now(timezone.utc),
            "fid": f_2026.id,
        },
    )

    with pytest.raises(DBAPIError) as exc_rev:
        async with admin_session.begin_nested():
            await admin_session.execute(
                text("UPDATE factures_capcalera SET estat_anulacio = 'ACTIVA' WHERE id = :fid"),
                {"fid": f_2026.id},
            )
    assert "VERIFACTU_IMMUTABLE_VIOLATION" in str(exc_rev.value)


@pytest.mark.asyncio
async def test_fase1_rls_verifactu_cadena_tenant_i_saas_trigger(admin_session) -> None:
    """
    Verifica:
    1. Aïllament RLS estricte a `verifactu_cadena_tenant` entre Tenant A i Tenant B, i veto a `ENGINYER`.
    2. Trigger d'immutabilitat sobre `saas_factures_b2b` quan `estat = 'EMESA_VERIFACTU'`.
    """
    emp_a = uuid.uuid4()
    emp_b = uuid.uuid4()
    suf_a = str(emp_a)[:8]
    suf_b = str(emp_b)[:8]

    admin_session.add_all(
        [
            Empresa(
                id=emp_a,
                nom=f"Tenant A {suf_a}",
                nif=f"B{suf_a.upper()}",
                subdomini=f"ta-{suf_a}",
            ),
            Empresa(
                id=emp_b,
                nom=f"Tenant B {suf_b}",
                nif=f"B{suf_b.upper()}",
                subdomini=f"tb-{suf_b}",
            ),
        ]
    )
    await admin_session.flush()

    await set_tenant_context(admin_session, str(emp_a), False, role="BOSS")
    admin_session.add(
        VerifactuCadenaTenant(
            empresa_id=emp_a,
            ultim_hash_sha256="D" * 64,
            ultim_num_serie="F-2026-0001",
            ultima_data_expedicio="23-11-2026",
            ultim_tipus_registre="ALTA",
        )
    )
    await admin_session.flush()

    # Forçar RLS fins i tot si la connexió de test és superuser
    await admin_session.execute(text("SET LOCAL ROLE sevalor_app;"))

    # Tenant A BOSS veu la seva cadena (1 fila)
    rows_a = (await admin_session.execute(select(VerifactuCadenaTenant))).scalars().all()
    assert len(rows_a) == 1
    assert rows_a[0].empresa_id == emp_a

    # Tenant B BOSS veu 0 files de Tenant A
    await set_tenant_context(admin_session, str(emp_b), False, role="BOSS")
    rows_b = (await admin_session.execute(select(VerifactuCadenaTenant))).scalars().all()
    assert len(rows_b) == 0

    # Tenant A ENGINYER veu 0 files (bloqueig economics_boss_only_verifactu_cadena_tenant)
    await set_tenant_context(admin_session, str(emp_a), False, role="ENGINYER")
    rows_eng = (await admin_session.execute(select(VerifactuCadenaTenant))).scalars().all()
    assert len(rows_eng) == 0

    await admin_session.execute(text("RESET ROLE;"))

    # Trigger immutabilitat sobre SaasFacturaB2B
    saas_f = SaasFacturaB2B(
        empresa_id=emp_a,
        client_nom_snapshot="Tenant A S.L.",
        client_nif_snapshot=f"B{suf_a.upper()}",
        exercici=2026,
        serie="SAAS",
        numero_factura=1,
        num_serie_verifactu="SAAS-2026-0001",
        estat="EMESA_VERIFACTU",
        periode="2026-11",
        base_imposable=500.00,
        quota_iva=105.00,
        import_total=605.00,
        import_total_verifactu=605.00,
        hash_sha256="E" * 64,
        fecha_hora_huso_gen_registro="2026-11-23T12:00:00+01:00",
    )
    admin_session.add(saas_f)
    await admin_session.flush()

    with pytest.raises(DBAPIError) as exc_saas:
        async with admin_session.begin_nested():
            await admin_session.execute(
                text("UPDATE saas_factures_b2b SET import_total = 10.00 WHERE id = :sid"),
                {"sid": saas_f.id},
            )
    assert "VERIFACTU_IMMUTABLE_VIOLATION" in str(exc_saas.value)
