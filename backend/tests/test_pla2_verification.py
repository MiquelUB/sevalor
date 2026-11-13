"""Tests d'integració i auditoria Zero-Mock per al PLA 2 (/gestio OCR + Pont Magatzem -> Comptabilitat)."""

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import jwt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from app.core.config import settings
from app.core.db import set_tenant_context
from app.main import app
from app.models.models import (
    Article,
    Client,
    DespesaComptable,
    Empresa,
    EstocMagatzem,
    Incidencia,
    Magatzem,
    MermaInventari,
    OrdreTreball,
    TiquetDespesa,
    Usuari,
    Vehicle,
)
from app.services.sovereign_storage import SovereignStorageGateway
from app.workers.comptabilitat_tasks import _processar_tiquet_ocr_async


def _make_token(empresa_id: uuid.UUID, usuari_id: uuid.UUID, rol: str) -> str:
    payload = {
        "sub": str(usuari_id),
        "rol": rol,
        "empresa_id": str(empresa_id),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=60),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def _webp_with_metadata(metadata_text: str) -> bytes:
    """Genera un payload binari WEBP vàlid amb metadades de text llegibles per extract_receipt_ocr_data."""
    body = metadata_text.encode("utf-8")
    return b"RIFF\x00\x00\x00\x00WEBP" + b"VP8 " + body


async def _seed_tenant_base(db, tmp_path: Path, nif_emp: str = "B99887766"):
    emp_id = uuid.uuid4()
    op_id = uuid.uuid4()
    boss_id = uuid.uuid4()
    eng_id = uuid.uuid4()
    sec_id = uuid.uuid4()
    veh_id = uuid.uuid4()
    cli_id = uuid.uuid4()
    ot_id = uuid.uuid4()
    mag_id = uuid.uuid4()

    emp = Empresa(
        id=emp_id,
        nom=f"Sevalor Test {str(emp_id)[:6]}",
        nif=nif_emp,
        subdomini=f"pla2-{str(emp_id)[:8]}",
        disc_dur_url=str(tmp_path / f"disc_{emp_id}"),
        pla_subscripcio="PRO",
        estat_pagament="ACTIU",
    )
    db.add(emp)
    await db.flush()

    db.add_all(
        [
            Usuari(
                id=boss_id,
                empresa_id=emp_id,
                nif=f"B{str(boss_id)[:8]}",
                nom="Cap",
                cognoms="Empresa",
                email=f"boss_{str(emp_id)[:6]}@test.local",
                rol="BOSS",
                estat="ACTIU",
            ),
            Usuari(
                id=sec_id,
                empresa_id=emp_id,
                nif=f"S{str(sec_id)[:8]}",
                nom="Secre",
                cognoms="Comptable",
                email=f"sec_{str(emp_id)[:6]}@test.local",
                rol="SECRETARIA",
                estat="ACTIU",
            ),
            Usuari(
                id=eng_id,
                empresa_id=emp_id,
                nif=f"E{str(eng_id)[:8]}",
                nom="Enginyer",
                cognoms="Cap",
                email=f"eng_{str(emp_id)[:6]}@test.local",
                rol="ENGINYER",
                estat="ACTIU",
            ),
            Usuari(
                id=op_id,
                empresa_id=emp_id,
                nif=f"O{str(op_id)[:8]}",
                nom="Operari",
                cognoms="Camp",
                rol="OPERARI",
                estat="ACTIU",
                telefon=f"+346{str(op_id.int)[:8]}",
            ),
        ]
    )
    await db.flush()

    veh = Vehicle(
        id=veh_id,
        empresa_id=emp_id,
        matricula=f"{str(veh_id.int)[:4]}XYZ",
        marca="Ford",
        model="Transit",
        estat="OPERATIU",
        conductor_habitual_id=op_id,
        targeta_combustible_bloquejada=False,
    )
    cli = Client(
        id=cli_id,
        empresa_id=emp_id,
        codi=f"CLI-{str(cli_id)[:6]}",
        rao_social="Agrícola Nord SL",
        nif="B11223344",
    )
    mag = Magatzem(
        id=mag_id,
        empresa_id=emp_id,
        nom="Nau Central PLA2",
        tipus="NAU_CENTRAL",
    )
    db.add_all([veh, cli, mag])
    await db.flush()

    ot = OrdreTreball(
        id=ot_id,
        empresa_id=emp_id,
        codi=f"OT-{str(ot_id)[:6]}",
        client_id=cli_id,
        titol="Instal·lació reg sector 4",
        adreca="Camí del Canal 12",
        import_pressupostat=320.00,
        import_pressupostat_net=320.00,
        cost_materials_picking_pmp=100.00,
        cost_ma_obra_real=80.00,
        cost_flota_real=20.00,
    )
    db.add(ot)
    await db.flush()

    return {
        "empresa_id": emp_id,
        "boss_id": boss_id,
        "sec_id": sec_id,
        "eng_id": eng_id,
        "op_id": op_id,
        "veh_id": veh_id,
        "cli_id": cli_id,
        "ot_id": ot_id,
        "mag_id": mag_id,
        "nif_emp": nif_emp,
    }


@pytest.mark.asyncio
async def test_pla2_ocr_worker_pipeline_all_rules(db_session, tmp_path):
    """Verifica totes les regles OCR de /gestio en PostgreSQL + disc sobirà reals (zero mocks)."""
    ctx = await _seed_tenant_base(db_session, tmp_path)
    emp_id = ctx["empresa_id"]
    await set_tenant_context(db_session, emp_id, is_superadmin=False)

    async def _create_tiquet_with_bytes(categoria: str, content: bytes, fname: str) -> TiquetDespesa:
        path = await SovereignStorageGateway.pujar_fitxer_binari(
            db=db_session,
            empresa_id=emp_id,
            categoria="tiquets_despesa",
            nom_fitxer=fname,
            content=content,
            content_type="image/webp",
        )
        t = TiquetDespesa(
            id=uuid.uuid4(),
            empresa_id=emp_id,
            categoria=categoria,
            usuari_id=ctx["op_id"],
            vehicle_id=ctx["veh_id"],
            ordre_treball_id=ctx["ot_id"],
            data_tiquet=date.today(),
            estat_aprovacio="PENDENT_PROCESSAMENT",
            estat_fiscal="PENDENT_OCR",
            foto_tiquet_path=path,
        )
        db_session.add(t)
        await db_session.flush()
        return t

    # 1. Confiança < 70% (tiquet tacat / il·legible)
    t_low = await _create_tiquet_with_bytes(
        "FERRETERIA",
        _webp_with_metadata("Confidence: 0.42\nText parcial tacat oli"),
        "low_conf.webp",
    )
    res_low = await _processar_tiquet_ocr_async(db_session, emp_id, t_low.id)
    assert res_low["status"] == "LOW_CONFIDENCE_MANUAL_REVIEW"
    assert t_low.estat_aprovacio == "INCIDENCIA_COMPROVACIO_MANUAL"
    inc_low = (
        await db_session.execute(
            select(Incidencia).where(
                Incidencia.empresa_id == emp_id,
                Incidencia.tipus == "TIQUET_COMPROVACIO_MANUAL",
            )
        )
    ).scalar_one()
    assert inc_low.gravetat == "MITJANA"

    # 2. Carburant mixt Dièsel + AdBlue -> PENDENT_DESGLOSE_MANUAL + reanomenament
    t_mix = await _create_tiquet_with_bytes(
        "CARBURANT",
        _webp_with_metadata(
            "Proveidor: REPSOL ESTACIO\nNIF Emissor: A28047223\n"
            "NIF Comprador: B99887766\nDiesel Optimo 45L + AdBlue 10L\n"
            "Data: 2026-11-13\nTotal: 78.50 EUR"
        ),
        "mix_fuel.webp",
    )
    res_mix = await _processar_tiquet_ocr_async(db_session, emp_id, t_mix.id)
    assert res_mix["status"] == "PENDENT_DESGLOSE_MANUAL"
    assert t_mix.estat_aprovacio == "PENDENT_DESGLOSE_MANUAL"
    assert t_mix.nom_fitxer_visible == "REPSOL_ESTACIO_78.50EUR_1113.webp"
    assert Path(t_mix.foto_tiquet_path).name == f"{emp_id}_{t_mix.id}_REPSOL_ESTACIO_78.50EUR_20261113.webp"
    assert Path(t_mix.foto_tiquet_path).is_file()

    # 3. Excedència > 100 EUR -> bloqueja vehicle + incidència ALTA + requereix BOSS
    t_over = await _create_tiquet_with_bytes(
        "CARBURANT",
        _webp_with_metadata(
            "Proveidor: CEPSA FLOTA\nNIF Emissor: A28003119\n"
            "NIF Comprador: B99887766\nData: 2026-11-13\nTotal: 145.50 EUR"
        ),
        "over_100.webp",
    )
    res_over = await _processar_tiquet_ocr_async(db_session, emp_id, t_over.id)
    assert res_over["status"] == "BLOQUEJAT_EXCEDENCIA_100EUR"
    assert t_over.estat_aprovacio == "BLOQUEJAT_EXCEDENCIA_100EUR"
    assert t_over.requereix_aprovacio_boss is True
    veh_db = (await db_session.execute(select(Vehicle).where(Vehicle.id == ctx["veh_id"]))).scalar_one()
    assert veh_db.targeta_combustible_bloquejada is True
    inc_over = (
        await db_session.execute(
            select(Incidencia).where(
                Incidencia.empresa_id == emp_id,
                Incidencia.tipus == "TIQUET_EXCEDENCIA_LIMIT_100EUR",
            )
        )
    ).scalar_one()
    assert inc_over.gravetat == "ALTA"

    # Secretària NO pot aprovar tiquet > 100 EUR; només BOSS pot i desbloqueja vehicle
    sec_headers = {"Authorization": f"Bearer {_make_token(emp_id, ctx['sec_id'], 'SECRETARIA')}", "X-Empresa-ID": str(emp_id)}
    boss_headers = {"Authorization": f"Bearer {_make_token(emp_id, ctx['boss_id'], 'BOSS')}", "X-Empresa-ID": str(emp_id)}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r_sec = await ac.post(
            f"/api/v1/gestio/comptabilitat/tiquets/{t_over.id}/auditar",
            json={"accio": "APROVAT", "custodia_paper_confirmada": True},
            headers=sec_headers,
        )
        assert r_sec.status_code == 403

        r_boss = await ac.post(
            f"/api/v1/gestio/comptabilitat/tiquets/{t_over.id}/auditar",
            json={"accio": "APROVAT", "custodia_paper_confirmada": True, "desblocatge_targeta_vehicle": True},
            headers=boss_headers,
        )
        assert r_boss.status_code == 200
        assert r_boss.json()["estat_aprovacio"] == "APROVAT"
    veh_unblocked = (await db_session.execute(select(Vehicle).where(Vehicle.id == ctx["veh_id"]))).scalar_one()
    assert veh_unblocked.targeta_combustible_bloquejada is False

    # 4. EDGE-08: Sense NIF corporatiu comprador -> IVA 0%, 62X, PENDENT_DE_CANJE
    t_nonif = await _create_tiquet_with_bytes(
        "DIETES",
        _webp_with_metadata(
            "Proveidor: RESTAURANT CAN JOAN\nNIF Emissor: B65432198\n"
            "Data: 2026-11-13\nTotal: 48.40 EUR"
        ),
        "no_buyer_nif.webp",
    )
    res_nonif = await _processar_tiquet_ocr_async(db_session, emp_id, t_nonif.id)
    assert res_nonif["status"] == "PENDENT_DE_CANJE"
    assert float(t_nonif.quota_iva) == 0.0
    assert float(t_nonif.base_imposable) == pytest.approx(48.40)
    assert t_nonif.subcompte_pgc == "62X"
    desp_nonif = (
        await db_session.execute(select(DespesaComptable).where(DespesaComptable.tiquet_id == t_nonif.id))
    ).scalar_one()
    assert desp_nonif.subcompte == "62X"
    assert float(desp_nonif.quota_iva) == 0.0
    assert desp_nonif.estat == "PENDENT_DE_CANJE"

    # 5. Tiquet vàlid de Ferreteria amb NIF comprador -> ARXIVAT_GESTIO + DespesaComptable vinculada a OT
    t_ok = await _create_tiquet_with_bytes(
        "FERRETERIA",
        _webp_with_metadata(
            "Proveidor: FERRETERIA LLEIDA\nNIF Emissor: B25001122\n"
            "NIF Comprador: B99887766\nBase Imposable: 50.00\nQuota IVA: 10.50\n"
            "Data: 2026-11-13\nTotal: 60.50 EUR"
        ),
        "valid_ferreteria.webp",
    )
    res_ok = await _processar_tiquet_ocr_async(db_session, emp_id, t_ok.id)
    assert res_ok["status"] == "ARXIVAT_GESTIO"
    assert float(t_ok.base_imposable) == pytest.approx(50.00)
    assert float(t_ok.quota_iva) == pytest.approx(10.50)
    assert t_ok.subcompte_pgc == "602.FERRETERIA_OBRA"


@pytest.mark.asyncio
async def test_pla2_pmp_firm_price_tolerance_and_consignment(db_session, tmp_path):
    """Verifica PMP dinàmic, bloqueig HTTP 409 per Preu Ferm, tolerància granel +-2% i exclusió dipòsit/RMA."""
    ctx = await _seed_tenant_base(db_session, tmp_path)
    emp_id = ctx["empresa_id"]
    mag_id = ctx["mag_id"]
    await set_tenant_context(db_session, emp_id, is_superadmin=False)

    art = Article(
        id=uuid.uuid4(),
        empresa_id=emp_id,
        referencia_inventari="TUB-PE100",
        nom="Tub Polietilè 63mm",
        unitat_mesura="METRES",
        es_material_continu=True,
        preu_cost=10.00,
        preu_cost_mitja=10.00,
        pmp_actual=10.0000,
        ultim_preu_compra=10.0000,
        estoc_total_actual=10.000,
    )
    art_diposit = Article(
        id=uuid.uuid4(),
        empresa_id=emp_id,
        referencia_inventari="BOMBA-DIP",
        nom="Bomba submergible en dipòsit",
        es_diposit_proveidor=True,
        pmp_actual=0.0000,
        estoc_total_actual=5.000,
    )
    art_rma = Article(
        id=uuid.uuid4(),
        empresa_id=emp_id,
        referencia_inventari="RMA-VALV",
        nom="Vàlvula client en custòdia RMA",
        es_custodia_rma_client=True,
        pmp_actual=0.0000,
        estoc_total_actual=1.000,
    )
    db_session.add_all([art, art_diposit, art_rma])
    await db_session.flush()

    db_session.add(
        EstocMagatzem(
            empresa_id=emp_id,
            article_id=art.id,
            magatzem_id=mag_id,
            quantitat_fisica=10.0,
        )
    )
    await db_session.flush()

    headers = {"Authorization": f"Bearer {_make_token(emp_id, ctx['boss_id'], 'BOSS')}", "X-Empresa-ID": str(emp_id)}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Entrada PMP atòmica: (10*10 + 10*20) / 20 = 15.00 EUR, tolerància granel <= 2%
        r1 = await ac.post(
            "/api/v1/gestio/magatzem/entrades-pmp",
            json={
                "article_id": str(art.id),
                "magatzem_id": str(mag_id),
                "quantitat_rebuda": 10.0,
                "preu_compra_unitari": 20.0,
                "preu_ferm_comanda": 20.0,
                "es_granel_continu": True,
                "quantitat_demanada_comanda": 9.85,
                "referencia_document": "ALB-2026-001",
            },
            headers=headers,
        )
        assert r1.status_code == 200, r1.text
        d1 = r1.json()
        assert d1["pmp_anterior"] == pytest.approx(10.0)
        assert d1["pmp_nou"] == pytest.approx(15.0)
        assert d1["estoc_total_actual"] == pytest.approx(20.0)
        assert d1["conciliacio_estat"] == "CONCILIADA_TOLERANCIA_GRANEL_2PCT"

        # 2. Violació de Clàusula de Preu Ferm -> HTTP 409 + Incidència ALTA + PMP intacte
        r2 = await ac.post(
            "/api/v1/gestio/magatzem/entrades-pmp",
            json={
                "article_id": str(art.id),
                "magatzem_id": str(mag_id),
                "quantitat_rebuda": 5.0,
                "preu_compra_unitari": 25.0,
                "preu_ferm_comanda": 20.0,
            },
            headers=headers,
        )
        assert r2.status_code == 409
        art_check = (await db_session.execute(select(Article).where(Article.id == art.id))).scalar_one()
        assert float(art_check.pmp_actual) == pytest.approx(15.0)
        inc = (
            await db_session.execute(
                select(Incidencia).where(
                    Incidencia.empresa_id == emp_id,
                    Incidencia.tipus == "NO_CONFORMITAT_PREU_ALBARA",
                )
            )
        ).scalar_one()
        assert inc.gravetat == "ALTA"

        # 3. Dipòsit de proveïdor i custòdia RMA -> PMP exclòs (roman 0.0)
        r3 = await ac.post(
            "/api/v1/gestio/magatzem/entrades-pmp",
            json={
                "article_id": str(art_diposit.id),
                "magatzem_id": str(mag_id),
                "quantitat_rebuda": 3.0,
                "preu_compra_unitari": 500.0,
            },
            headers=headers,
        )
        assert r3.status_code == 200
        assert r3.json()["exclos_pmp_diposit_o_rma"] is True
        assert r3.json()["pmp_nou"] == 0.0

        r4 = await ac.post(
            "/api/v1/gestio/magatzem/entrades-pmp",
            json={
                "article_id": str(art_rma.id),
                "magatzem_id": str(mag_id),
                "quantitat_rebuda": 1.0,
                "preu_compra_unitari": 120.0,
            },
            headers=headers,
        )
        assert r4.status_code == 200
        assert r4.json()["exclos_pmp_diposit_o_rma"] is True
        assert r4.json()["pmp_nou"] == 0.0


@pytest.mark.asyncio
async def test_pla2_mermes_ot_margin_rbac_veto_and_rls_isolation(db_session, tmp_path):
    """Verifica mermes (600 vs 659), càlcul determinista cost/marge OT, veto ENGINYER (403) i aïllament RLS."""
    ctx_a = await _seed_tenant_base(db_session, tmp_path, nif_emp="B11111111")
    ctx_b = await _seed_tenant_base(db_session, tmp_path, nif_emp="B22222222")
    emp_a = ctx_a["empresa_id"]
    emp_b = ctx_b["empresa_id"]

    await set_tenant_context(db_session, emp_a, is_superadmin=False)

    art = Article(
        id=uuid.uuid4(),
        empresa_id=emp_a,
        referencia_inventari="GOTER-16",
        nom="Goter autocompensant 16mm",
        unitat_mesura="METRES",
        pmp_actual=15.0000,
        preu_cost_mitja=15.0000,
        preu_cost=15.00,
        estoc_total_actual=20.000,
    )
    db_session.add(art)
    await db_session.flush()
    db_session.add(
        EstocMagatzem(
            empresa_id=emp_a,
            article_id=art.id,
            magatzem_id=ctx_a["mag_id"],
            quantitat_fisica=20.0,
        )
    )
    # Tiquet OCR vàlid vinculat a la mateixa OT (60.50 EUR)
    db_session.add(
        TiquetDespesa(
            id=uuid.uuid4(),
            empresa_id=emp_a,
            categoria="FERRETERIA",
            usuari_id=ctx_a["op_id"],
            ordre_treball_id=ctx_a["ot_id"],
            data_tiquet=date.today(),
            base_imposable=50.00,
            iva_pct=21.00,
            quota_iva=10.50,
            import_total=60.50,
            estat_aprovacio="ARXIVAT_GESTIO",
            estat_fiscal="DEDUIBLE",
        )
    )
    await db_session.flush()

    boss_a = {"Authorization": f"Bearer {_make_token(emp_a, ctx_a['boss_id'], 'BOSS')}", "X-Empresa-ID": str(emp_a)}
    eng_a = {"Authorization": f"Bearer {_make_token(emp_a, ctx_a['eng_id'], 'ENGINYER')}", "X-Empresa-ID": str(emp_a)}
    boss_b = {"Authorization": f"Bearer {_make_token(emp_b, ctx_b['boss_id'], 'BOSS')}", "X-Empresa-ID": str(emp_b)}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Merma imputable a obra sense OT -> 422
        r_no_ot = await ac.post(
            "/api/v1/gestio/magatzem/mermes",
            json={
                "article_id": str(art.id),
                "magatzem_id": str(ctx_a["mag_id"]),
                "quantitat_mermada": 2.0,
                "motiu": "OBRA_TALL_INUTIL",
            },
            headers=boss_a,
        )
        assert r_no_ot.status_code == 422

        # 2. Merma d'obra (2 x 15.00 = 30.00 EUR -> 600.MERMA_OBRA)
        r_obra = await ac.post(
            "/api/v1/gestio/magatzem/mermes",
            json={
                "article_id": str(art.id),
                "magatzem_id": str(ctx_a["mag_id"]),
                "quantitat_mermada": 2.0,
                "motiu": "OBRA_TALL_INUTIL",
                "ordre_treball_id": str(ctx_a["ot_id"]),
            },
            headers=boss_a,
        )
        assert r_obra.status_code == 201, r_obra.text
        d_obra = r_obra.json()
        assert d_obra["subcompte"] == "600.MERMA_OBRA"
        assert d_obra["cost_total_imputat"] == pytest.approx(30.0)
        assert d_obra["estoc_restant"] == pytest.approx(18.0)
        assert d_obra["estoc_slot_residus"] == pytest.approx(2.0)

        # 3. Merma de nau (CADUCITAT_FEFO, 1 x 15.00 = 15.00 EUR -> 659.MERMA_MAGATZEM)
        r_nau = await ac.post(
            "/api/v1/gestio/magatzem/mermes",
            json={
                "article_id": str(art.id),
                "magatzem_id": str(ctx_a["mag_id"]),
                "quantitat_mermada": 1.0,
                "motiu": "CADUCITAT_FEFO",
            },
            headers=boss_a,
        )
        assert r_nau.status_code == 201, r_nau.text
        d_nau = r_nau.json()
        assert d_nau["subcompte"] == "659.MERMA_MAGATZEM"
        assert d_nau["cost_total_imputat"] == pytest.approx(15.0)
        assert d_nau["estoc_restant"] == pytest.approx(17.0)
        assert d_nau["estoc_slot_residus"] == pytest.approx(3.0)

        # 4. Càlcul exacte del cost real i marge brut OT:
        #    Materials picking PMP = 100.00
        #    Mermes imputades OT   =  30.00 (només OBRA_TALL_INUTIL, no la de nau)
        #    Tiquets OCR OT        =  60.50
        #    Mà d'obra             =  80.00
        #    Flota                 =  20.00
        #    Total cost            = 290.50 | Ingressos = 320.00 | Marge = 29.50 (9.22% < 15%)
        r_marge = await ac.get(
            f"/api/v1/gestio/comptabilitat/ordres-treball/{ctx_a['ot_id']}/cost-marge",
            headers=boss_a,
        )
        assert r_marge.status_code == 200, r_marge.text
        m = r_marge.json()
        assert m["desglossament_costos"]["materials_picking_pmp_eur"] == pytest.approx(100.0)
        assert m["desglossament_costos"]["mermes_imputades_eur"] == pytest.approx(30.0)
        assert m["desglossament_costos"]["tiquets_camp_ocr_eur"] == pytest.approx(60.5)
        assert m["cost_total_real_eur"] == pytest.approx(290.5)
        assert m["marge_brut_eur"] == pytest.approx(29.5)
        assert m["marge_brut_pct"] == pytest.approx(9.22)
        assert m["alerta_desviacio_marge"] is True

        # 5. Veto Enginyer a Comptabilitat (403 Forbidden)
        r_veto_marge = await ac.get(
            f"/api/v1/gestio/comptabilitat/ordres-treball/{ctx_a['ot_id']}/cost-marge",
            headers=eng_a,
        )
        assert r_veto_marge.status_code == 403
        r_veto_desp = await ac.get(
            "/api/v1/gestio/comptabilitat/despeses-analitiques",
            headers=eng_a,
        )
        assert r_veto_desp.status_code == 403

        # 6. Aïllament cross-tenant via API (Tenant B no pot veure OT de Tenant A)
        r_cross = await ac.get(
            f"/api/v1/gestio/comptabilitat/ordres-treball/{ctx_a['ot_id']}/cost-marge",
            headers=boss_b,
        )
        assert r_cross.status_code == 404

    # 7. Aïllament RLS directe a nivell PostgreSQL per les noves taules mermes_inventari i despeses_comptables
    await set_tenant_context(db_session, emp_b, is_superadmin=False)
    res_rls_mermes = (await db_session.execute(text("SELECT count(*) FROM mermes_inventari"))).scalar_one()
    res_rls_desp = (await db_session.execute(text("SELECT count(*) FROM despeses_comptables"))).scalar_one()
    assert res_rls_mermes == 0
    assert res_rls_desp == 0

    await set_tenant_context(db_session, emp_a, is_superadmin=False)
    res_rls_mermes_a = (await db_session.execute(text("SELECT count(*) FROM mermes_inventari"))).scalar_one()
    res_rls_desp_a = (await db_session.execute(text("SELECT count(*) FROM despeses_comptables"))).scalar_one()
    assert res_rls_mermes_a == 2
    assert res_rls_desp_a == 2
