"""Tests Fase 5 — Fulla 360° Conciliada, Validació, Pre-facturació (3 Rols) i Consulta Comercial Client."""

from __future__ import annotations

import base64
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.api.v1.operari_auth import create_access_token
from app.core.db import set_tenant_context
from app.main import app
from app.models.models import (
    Article,
    CapaVectorial,
    CarpetaPlanol,
    Client,
    Empresa,
    EstocMagatzem,
    FacturaCapcalera,
    FullaPicking,
    LiniaPicking,
    Magatzem,
    OrdreTreball,
    OrdreTreballTramTemps,
    PlanolBase,
    Pressupost,
    TiquetDespesa,
    Usuari,
)
from app.services.sovereign_storage import SovereignStorageGateway, inicialitzar_arbre_carpetes_disc

VALID_WEBP_BYTES = b"RIFF\x24\x00\x00\x00WEBPVP8 " + b"\x00" * 30
VALID_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)
VALID_PNG_BYTES = base64.b64decode(VALID_PNG_B64)


async def _seed_tenant_f5(admin_session, disc_root: Path, label: str) -> Dict[str, Any]:
    inicialitzar_arbre_carpetes_disc(disc_root)
    emp_id = uuid.uuid4()
    boss_id = uuid.uuid4()
    sec_id = uuid.uuid4()
    eng_id = uuid.uuid4()
    op_id = uuid.uuid4()
    cli_id = uuid.uuid4()
    mag_nau_id = uuid.uuid4()
    art_id = uuid.uuid4()

    admin_session.add(
        Empresa(
            id=emp_id,
            nom=f"Sevalor Fase5 {label} SL",
            nif="B" + emp_id.hex[:8].upper(),
            subdomini=f"f5-{label.lower()}-{emp_id.hex[:6]}",
            pla_subscripcio="PRO",
            estat_pagament="ACTIU",
            disc_dur_url=str(disc_root),
            node_ia_actiu=True,
        )
    )
    await admin_session.flush()

    for uid, nom_u, rol_u in [
        (boss_id, "Boss", "BOSS"),
        (sec_id, "Secretaria", "SECRETARIA"),
        (eng_id, "Enginyer", "ENGINYER"),
        (op_id, "Operari", "OPERARI"),
    ]:
        admin_session.add(
            Usuari(
                id=uid,
                empresa_id=emp_id,
                nif=f"{rol_u[0]}{uid.hex[:7].upper()}F",
                nom=nom_u,
                cognoms=label,
                email=f"{rol_u.lower()}-{emp_id.hex[:6]}@sevalor.test",
                telefon="611222333",
                rol=rol_u,
                pin_hash="fake",
                password_hash="fake",
                estat="ACTIU",
            )
        )

    admin_session.add(
        Client(
            id=cli_id,
            empresa_id=emp_id,
            codi=f"CLI-F5-{emp_id.hex[:5].upper()}",
            rao_social=f"Explotacions {label} SA",
            nif="A" + cli_id.hex[:8].upper(),
            adreca_fiscal="Carrer del Reg 25",
            iban_xifrat_simetric="ES7921000813610123456789",
            actiu=True,
        )
    )
    admin_session.add(
        Magatzem(
            id=mag_nau_id,
            empresa_id=emp_id,
            nom=f"Nau Central {label}",
            tipus="NAU",
            actiu=True,
        )
    )
    admin_session.add(
        Article(
            id=art_id,
            empresa_id=emp_id,
            referencia_inventari=f"TUB-F5-{emp_id.hex[:4].upper()}",
            nom="Canonada PE100 DN63",
            unitat_mesura="METRE",
            preu_cost=6.00,
            preu_cost_mitja=6.00,
            pmp_actual=6.00,
            preu_venda=15.00,
            estoc_total_actual=100.0,
        )
    )
    await admin_session.flush()

    admin_session.add(
        EstocMagatzem(
            id=uuid.uuid4(),
            empresa_id=emp_id,
            magatzem_id=mag_nau_id,
            article_id=art_id,
            quantitat_fisica=100.0,
            quantitat_virtual_reservada=10.0,
            quantitat_cuarentena=0.0,
        )
    )
    await admin_session.flush()

    def _hdr(uid: uuid.UUID, rol: str) -> Dict[str, str]:
        tok = create_access_token(str(uid), rol, str(emp_id), timedelta(minutes=30))
        return {"Authorization": f"Bearer {tok}", "X-Empresa-ID": str(emp_id)}

    return {
        "emp_id": emp_id,
        "disc": disc_root,
        "boss_id": boss_id,
        "sec_id": sec_id,
        "eng_id": eng_id,
        "op_id": op_id,
        "cli_id": cli_id,
        "mag_nau_id": mag_nau_id,
        "art_id": art_id,
        "headers_boss": _hdr(boss_id, "BOSS"),
        "headers_sec": _hdr(sec_id, "SECRETARIA"),
        "headers_eng": _hdr(eng_id, "ENGINYER"),
        "headers_op": _hdr(op_id, "OPERARI"),
    }


@pytest_asyncio.fixture
async def setup_fase5(admin_session, tmp_path: Path):
    ta = await _seed_tenant_f5(admin_session, tmp_path / "disc_f5_a", "A")
    tb = await _seed_tenant_f5(admin_session, tmp_path / "disc_f5_b", "B")
    await admin_session.commit()
    return {"a": ta, "b": tb}


@pytest.mark.asyncio
async def test_f5_01_bloqueig_400_ot_no_conclosa_tram_obert_i_sense_validar(
    setup_fase5: Dict[str, Any],
    admin_session,
):
    """Bloqueja 400 si OT no conclosa, té tram de temps obert o intenta pre-facturar abans de validar."""
    ta = setup_fase5["a"]
    emp_id = ta["emp_id"]

    ot_en_curs = OrdreTreball(
        id=uuid.uuid4(),
        empresa_id=emp_id,
        client_id=ta["cli_id"],
        cap_de_colla_id=ta["op_id"],
        codi=f"OT-F5-CURS-{emp_id.hex[:4].upper()}",
        titol="Feina en curs",
        adreca="Finca 1",
        estat="EN_CURS",
        data_planificacio=date.today(),
    )
    ot_tram_obert = OrdreTreball(
        id=uuid.uuid4(),
        empresa_id=emp_id,
        client_id=ta["cli_id"],
        cap_de_colla_id=ta["op_id"],
        codi=f"OT-F5-TRAM-{emp_id.hex[:4].upper()}",
        titol="Feina amb tram obert",
        adreca="Finca 2",
        estat="COMPLERT",
        data_planificacio=date.today(),
        hores_imputades_facturables=2.0,
    )
    ot_complerta = OrdreTreball(
        id=uuid.uuid4(),
        empresa_id=emp_id,
        client_id=ta["cli_id"],
        cap_de_colla_id=ta["op_id"],
        codi=f"OT-F5-COMP-{emp_id.hex[:4].upper()}",
        titol="Feina conclosa pendent validar",
        adreca="Finca 3",
        estat="COMPLERT",
        data_planificacio=date.today(),
        hores_imputades_facturables=2.0,
    )
    admin_session.add_all([ot_en_curs, ot_tram_obert, ot_complerta])
    await admin_session.flush()
    admin_session.add(
        OrdreTreballTramTemps(
            id=uuid.uuid4(),
            empresa_id=emp_id,
            ordre_treball_id=ot_tram_obert.id,
            operari_id=ta["op_id"],
            hora_inici=datetime.now(timezone.utc) - timedelta(hours=1),
            hora_fi=None,
            durada_segons=0,
        )
    )
    await admin_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1") as ac:
        # 1. OT no conclosa -> 400 tant a validar com a pre-facturar
        r_v1 = await ac.put(
            f"/gestio/feines/{ot_en_curs.id}/validar-conciliacio",
            json={"checklist_conciliacio": {"hores_revisades": True}},
            headers=ta["headers_eng"],
        )
        assert r_v1.status_code == 400
        assert "no ha finalitzat" in r_v1.json()["detail"].lower()

        r_p1 = await ac.post(
            f"/gestio/feines/{ot_en_curs.id}/passar-a-prefacturacio",
            headers=ta["headers_eng"],
        )
        assert r_p1.status_code == 400

        # 2. OT conclosa però amb tram de temps obert -> 400
        r_v2 = await ac.put(
            f"/gestio/feines/{ot_tram_obert.id}/validar-conciliacio",
            json={"checklist_conciliacio": {"hores_revisades": True}},
            headers=ta["headers_eng"],
        )
        assert r_v2.status_code == 400
        assert "tram de temps obert" in r_v2.json()["detail"].lower()

        # 3. OT conclosa sense validar encara -> 400 en passar a pre-facturació
        r_p3 = await ac.post(
            f"/gestio/feines/{ot_complerta.id}/passar-a-prefacturacio",
            headers=ta["headers_eng"],
        )
        assert r_p3.status_code == 400
        assert "validar" in r_p3.json()["detail"].lower()


@pytest.mark.asyncio
async def test_f5_02_flux_complet_enginyer_conciliacio_evidencies_validacio_prefactura_i_client360(
    setup_fase5: Dict[str, Any],
    admin_session,
):
    """Flux complet ENGINYER: conciliació + evidències + validació + pre-facturació + Fitxa Client 360 + PDF + barrera 403."""
    ta = setup_fase5["a"]
    emp_id = ta["emp_id"]
    cli_id = ta["cli_id"]

    # Crear pressupost, plànol, OT conclosa, picking, tiquet i evidències físiques
    pres = Pressupost(
        id=uuid.uuid4(),
        empresa_id=emp_id,
        client_id=cli_id,
        numero=f"PRES-F5-{emp_id.hex[:4].upper()}",
        total=950.00,
        estat="APROVAT",
    )
    carpeta = CarpetaPlanol(
        id=uuid.uuid4(), empresa_id=emp_id, nom="Finques F5", categoria="FINQUES"
    )
    admin_session.add_all([pres, carpeta])
    await admin_session.flush()

    planol = PlanolBase(
        id=uuid.uuid4(),
        empresa_id=emp_id,
        carpeta_id=carpeta.id,
        client_id=cli_id,
        titol="Plànol Reg F5",
        codi_referencia="PLN-F5",
        tipus_fitxer="PNG",
        fitxer_path="04_planols_tecnics/planol_f5.png",
        mida_bytes=100,
    )
    admin_session.add(planol)
    await admin_session.flush()

    ot = OrdreTreball(
        id=uuid.uuid4(),
        empresa_id=emp_id,
        client_id=cli_id,
        cap_de_colla_id=ta["op_id"],
        planol_id=planol.id,
        codi=f"OT-F5-ENG-{emp_id.hex[:4].upper()}",
        titol="Substitució col·lector principal",
        adreca="Finca Nord, Km 4",
        estat="COMPLERT",
        data_planificacio=date.today(),
        data_finalitzacio_camp=date.today(),
        hores_imputades_facturables=3.0,
        preu_venda_hora_aplicat=60.00,
        import_pressupostat=950.00,
        nom_receptor="Joan Client",
        dni_receptor="12345678A",
        observacions_tancament="Instal·lació provada a pressió nominal.",
    )
    admin_session.add(ot)
    await admin_session.flush()

    fp = FullaPicking(
        id=uuid.uuid4(),
        empresa_id=emp_id,
        ordre_treball_id=ot.id,
        estat_picking="CARREGAT",
    )
    admin_session.add(fp)
    await admin_session.flush()

    lp = LiniaPicking(
        id=uuid.uuid4(),
        empresa_id=emp_id,
        picking_id=fp.id,
        article_id=ta["art_id"],
        magatzem_id=ta["mag_nau_id"],
        quantitat_prevista=10.0,
        quantitat_carregada_pick_in=10.0,
        quantitat_retornada_pick_out=0.0,
        quantitat_mermada=0.0,
        origen_estoc="NAU",
    )
    capa = CapaVectorial(
        id=uuid.uuid4(),
        empresa_id=emp_id,
        planol_base_id=planol.id,
        ordre_treball_id=ot.id,
        nom="Traçat As-Built Col·lector",
        disciplina="REG",
        geometries_geojson={"type": "FeatureCollection", "features": []},
        version_id=1,
    )
    tiq = TiquetDespesa(
        id=uuid.uuid4(),
        empresa_id=emp_id,
        categoria="FERRETERIA",
        usuari_id=ta["op_id"],
        ordre_treball_id=ot.id,
        data_tiquet=date.today(),
        base_imposable=25.00,
        import_total=30.25,
        estat_aprovacio="APROVAT",
        estat_fiscal="PROCESSAT",
        nom_fitxer_visible="tiquet_brides.webp",
        foto_tiquet_path="08_tiquets/tiquet_brides.webp",
    )
    # Factura general NO vinculada a cap OT (l'ENGINYER NO hi ha de poder accedir!)
    fac_no_ot = FacturaCapcalera(
        id=uuid.uuid4(),
        empresa_id=emp_id,
        numero_factura=9001,
        serie="F",
        client_id=cli_id,
        estat_document="EMESA",
        estat_cobrament="PENDENT",
        base_imposable=500.00,
        quota_iva=105.00,
        liquid_exigible=605.00,
        hash_sha256="A" * 64,
    )
    admin_session.add_all([lp, capa, tiq, fac_no_ot])
    await admin_session.flush()

    # Desar fotos QA i signatura reals al disc sobirà
    for nom_f in ("inicial", "intermedia", "final"):
        await SovereignStorageGateway.pujar_fitxer_binari(
            db=admin_session,
            empresa_id=emp_id,
            categoria="ots_actives",
            nom_fitxer=f"ot_{ot.id}_foto_{nom_f}.webp",
            content=VALID_WEBP_BYTES,
            content_type="image/webp",
        )
    sig_path = await SovereignStorageGateway.pujar_fitxer_binari(
        db=admin_session,
        empresa_id=emp_id,
        categoria="ots_historic",
        nom_fitxer=f"ot_{ot.id}_signatura_client.png",
        content=VALID_PNG_BYTES,
        content_type="image/png",
    )
    ot.signatura_client_path = sig_path
    ot.data_signatura = datetime.now(timezone.utc)
    await admin_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1") as ac:
        # 1. ENGINYER consulta GET /conciliacio -> veu evidències i imports comercials, però 0 costos interns
        r_conc = await ac.get(f"/gestio/feines/{ot.id}/conciliacio", headers=ta["headers_eng"])
        assert r_conc.status_code == 200, r_conc.text
        c_data = r_conc.json()
        assert c_data["disclaimer"]["codi"] == "CONCLOSA_PENDENT_VALIDACIO"
        assert c_data["fotos_qa"]["protocol_complet"] is True
        assert c_data["signatura"]["present"] is True
        assert c_data["signatura"]["nom_receptor"] == "Joan Client"
        assert c_data["tiquets"]["total"] == 1
        assert len(c_data["capes_gis"]) == 1
        assert c_data["resum_comercial"]["preu_venda_hora_aplicat"] == pytest.approx(60.0)
        assert c_data["resum_intern"]["cost_materials_pmp"] is None
        assert c_data["resum_intern"]["cost_ma_obra_real"] is None
        assert c_data["resum_intern"]["marge_real_eur"] is None

        # 2. ENGINYER carrega evidències binàries autenticades
        r_foto = await ac.get(
            f"/gestio/feines/{ot.id}/evidencies/foto_inicial", headers=ta["headers_eng"]
        )
        assert r_foto.status_code == 200
        assert r_foto.content == VALID_WEBP_BYTES

        r_sig = await ac.get(
            f"/gestio/feines/{ot.id}/evidencies/signatura", headers=ta["headers_eng"]
        )
        assert r_sig.status_code == 200
        assert r_sig.content == VALID_PNG_BYTES

        # 3. ENGINYER valida la conciliació ajustant 2.5h i 2 uts retornades (consum real = 8 uts)
        r_val = await ac.put(
            f"/gestio/feines/{ot.id}/validar-conciliacio",
            json={
                "hores_imputades_facturables": 2.5,
                "ajustos_picking": [
                    {
                        "linia_id": str(lp.id),
                        "quantitat_carregada_pick_in": 10.0,
                        "quantitat_retornada_pick_out": 2.0,
                        "quantitat_mermada": 0.0,
                    }
                ],
                "checklist_conciliacio": {
                    "hores_revisades": True,
                    "materials_conciliats": True,
                    "evidencies_comprovades": True,
                    "incidencies_tiquets": True,
                },
                "notes_validacio_tecnica": "Revisat amb cap de colla. Tot conforme.",
            },
            headers=ta["headers_eng"],
        )
        assert r_val.status_code == 200, r_val.text
        v_data = r_val.json()
        assert v_data["estat"] == "VALIDADA_PER_FACTURAR"
        assert v_data["disclaimer"]["codi"] == "VALIDADA_PENDENT_FACTURAR"
        assert v_data["validacio"]["validada"] is True
        assert v_data["temps_i_gps"]["hores_reals"] == pytest.approx(2.5)
        assert v_data["materials"]["linies"][0]["consum_real"] == pytest.approx(8.0)

        # 4. ENGINYER passa a Pre-facturació des de la Fulla 360° (HTTP 201)
        r_pref = await ac.post(
            f"/gestio/feines/{ot.id}/passar-a-prefacturacio",
            json={"incloure_tiquets_camp": True},
            headers=ta["headers_eng"],
        )
        assert r_pref.status_code == 201, r_pref.text
        pref_data = r_pref.json()
        assert pref_data["serie"] == "PRE"
        assert pref_data["estat_document"] == "ESBORRANY_PREFACTURA"
        # Base = 2.5h*60 (150) + 8u*15 (120) + tiquet 25 = 295.00; IVA 21% = 61.95; Total = 356.95
        assert float(pref_data["base_imposable"]) == pytest.approx(295.00, abs=0.02)
        assert float(pref_data["liquid_exigible"]) == pytest.approx(356.95, abs=0.02)
        assert "cost_unitari_historic" not in str(pref_data)
        pref_id = pref_data["id"]

        # 5. ENGINYER consulta Fitxa 360° del Client -> veu pressupost + pre-factura de tasques, sense IBAN/costos/marges
        r_cli = await ac.get(f"/gestio/clients/{cli_id}/fitxa-360", headers=ta["headers_eng"])
        assert r_cli.status_code == 200, r_cli.text
        cli_360 = r_cli.json()
        assert cli_360["client"]["iban"] is None
        assert cli_360["intervencions"][0]["cost_material"] is None
        assert cli_360["intervencions"][0]["marge_brut"] is None
        assert cli_360["pressupostos"][0]["total"] == pytest.approx(950.00)
        assert len(cli_360["factures"]) == 1
        assert cli_360["factures"][0]["id"] == pref_id
        assert cli_360["factures"][0]["liquid_exigible"] == pytest.approx(356.95, abs=0.02)

        # 6. ENGINYER consulta detall comercial i PDF de la pre-factura vinculada
        r_fac_det = await ac.get(
            f"/gestio/operativa-financera/factures/{pref_id}", headers=ta["headers_eng"]
        )
        assert r_fac_det.status_code == 200, r_fac_det.text
        fac_det = r_fac_det.json()
        assert fac_det["liquid_exigible"] == pytest.approx(356.95, abs=0.02)
        assert len(fac_det["linies"]) == 3
        assert ot.codi in fac_det["ordres_treball_codis"]

        r_fac_pdf = await ac.get(
            f"/gestio/operativa-financera/factures/{pref_id}/pdf", headers=ta["headers_eng"]
        )
        assert r_fac_pdf.status_code == 200
        assert r_fac_pdf.headers["content-type"].startswith("application/pdf")
        assert r_fac_pdf.content.startswith(b"%PDF")

        # 7. BOSS emet la factura final Veri*factu -> ENGINYER veu estat FACTURADA i el PDF final
        r_em = await ac.post(
            f"/gestio/comptabilitat/prefactures/{pref_id}/emetre",
            json={"serie": "F", "confirmacio_humana_hitl": True},
            headers=ta["headers_boss"],
        )
        assert r_em.status_code == 200, r_em.text

        r_conc_final = await ac.get(f"/gestio/feines/{ot.id}/conciliacio", headers=ta["headers_eng"])
        assert r_conc_final.status_code == 200
        assert r_conc_final.json()["disclaimer"]["codi"] == "FACTURADA"
        assert r_conc_final.json()["factura"]["estat_document"] == "EMESA"

        # 8. BARRERA COMPTABILITAT: ENGINYER NO pot consultar comptabilitat global ni factures sense OT
        assert (
            await ac.get("/gestio/comptabilitat/factures", headers=ta["headers_eng"])
        ).status_code == 403
        assert (
            await ac.get("/gestio/comptabilitat/dashboard-economic", headers=ta["headers_eng"])
        ).status_code == 403
        assert (
            await ac.get(
                f"/gestio/operativa-financera/factures/{fac_no_ot.id}",
                headers=ta["headers_eng"],
            )
        ).status_code == 404


@pytest.mark.asyncio
async def test_f5_03_secretaria_i_boss_validacio_prefacturacio_des_de_fulla_360(
    setup_fase5: Dict[str, Any],
    admin_session,
):
    """SECRETARIA i BOSS poden validar i pre-facturar des de la Fulla 360° i veure-ho a /comptabilitat/prefactures."""
    ta = setup_fase5["a"]
    emp_id = ta["emp_id"]

    ot_sec = OrdreTreball(
        id=uuid.uuid4(),
        empresa_id=emp_id,
        client_id=ta["cli_id"],
        cap_de_colla_id=ta["op_id"],
        codi=f"OT-F5-SEC-{emp_id.hex[:4].upper()}",
        titol="Revisió quadre elèctric",
        adreca="Finca Sud",
        estat="COMPLERT",
        data_planificacio=date.today(),
        hores_imputades_facturables=2.0,
        preu_venda_hora_aplicat=55.00,
    )
    ot_boss = OrdreTreball(
        id=uuid.uuid4(),
        empresa_id=emp_id,
        client_id=ta["cli_id"],
        cap_de_colla_id=ta["op_id"],
        codi=f"OT-F5-BOSS-{emp_id.hex[:4].upper()}",
        titol="Manteniment grup pressió",
        adreca="Finca Est",
        estat="COMPLERT",
        data_planificacio=date.today(),
        hores_imputades_facturables=1.5,
        preu_venda_hora_aplicat=70.00,
    )
    admin_session.add_all([ot_sec, ot_boss])
    await admin_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1") as ac:
        # SECRETARIA valida i pre-factura
        assert (
            await ac.put(
                f"/gestio/feines/{ot_sec.id}/validar-conciliacio",
                json={"checklist_conciliacio": {"hores_revisades": True}},
                headers=ta["headers_sec"],
            )
        ).status_code == 200
        r_p_sec = await ac.post(
            f"/gestio/feines/{ot_sec.id}/passar-a-prefacturacio", headers=ta["headers_sec"]
        )
        assert r_p_sec.status_code == 201, r_p_sec.text

        # BOSS valida i pre-factura
        assert (
            await ac.put(
                f"/gestio/feines/{ot_boss.id}/validar-conciliacio",
                json={"checklist_conciliacio": {"hores_revisades": True}},
                headers=ta["headers_boss"],
            )
        ).status_code == 200
        r_p_boss = await ac.post(
            f"/gestio/feines/{ot_boss.id}/passar-a-prefacturacio", headers=ta["headers_boss"]
        )
        assert r_p_boss.status_code == 201, r_p_boss.text

        # Les 2 pre-factures apareixen immediatament a /gestio/comptabilitat/prefactures
        r_list = await ac.get("/gestio/comptabilitat/prefactures", headers=ta["headers_sec"])
        assert r_list.status_code == 200, r_list.text
        ids_pref = {p["id"] for p in r_list.json()}
        assert r_p_sec.json()["id"] in ids_pref
        assert r_p_boss.json()["id"] in ids_pref


@pytest.mark.asyncio
async def test_f5_04_aillament_rls_cross_tenant_fase5(
    setup_fase5: Dict[str, Any],
    admin_session,
):
    """RLS: Tenant B rep 404 en tots els endpoints nous sobre dades del Tenant A."""
    ta = setup_fase5["a"]
    tb = setup_fase5["b"]

    ot_a = OrdreTreball(
        id=uuid.uuid4(),
        empresa_id=ta["emp_id"],
        client_id=ta["cli_id"],
        cap_de_colla_id=ta["op_id"],
        codi=f"OT-F5-RLS-{ta['emp_id'].hex[:4].upper()}",
        titol="OT Privada Tenant A",
        adreca="Finca Privada",
        estat="COMPLERT",
        data_planificacio=date.today(),
        hores_imputades_facturables=2.0,
        preu_venda_hora_aplicat=50.00,
    )
    admin_session.add(ot_a)
    await admin_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1") as ac:
        # Tenant A valida i crea pre-factura
        assert (
            await ac.put(
                f"/gestio/feines/{ot_a.id}/validar-conciliacio",
                json={"checklist_conciliacio": {"hores_revisades": True}},
                headers=ta["headers_eng"],
            )
        ).status_code == 200
        r_pre = await ac.post(
            f"/gestio/feines/{ot_a.id}/passar-a-prefacturacio", headers=ta["headers_eng"]
        )
        assert r_pre.status_code == 201
        fac_a_id = r_pre.json()["id"]

        # Tenant B (BOSS i ENGINYER) rep 404 en tots els endpoints sobre recursos d'A
        for hdr_b in (tb["headers_boss"], tb["headers_eng"]):
            assert (await ac.get(f"/gestio/feines/{ot_a.id}/conciliacio", headers=hdr_b)).status_code == 404
            assert (
                await ac.get(f"/gestio/feines/{ot_a.id}/evidencies/foto_inicial", headers=hdr_b)
            ).status_code == 404
            assert (
                await ac.put(
                    f"/gestio/feines/{ot_a.id}/validar-conciliacio",
                    json={"checklist_conciliacio": {}},
                    headers=hdr_b,
                )
            ).status_code == 404
            assert (
                await ac.post(f"/gestio/feines/{ot_a.id}/passar-a-prefacturacio", headers=hdr_b)
            ).status_code == 404
            assert (
                await ac.get(f"/gestio/clients/{ta['cli_id']}/fitxa-360", headers=hdr_b)
            ).status_code == 404
            assert (
                await ac.get(f"/gestio/operativa-financera/factures/{fac_a_id}", headers=hdr_b)
            ).status_code == 404
            assert (
                await ac.get(f"/gestio/operativa-financera/factures/{fac_a_id}/pdf", headers=hdr_b)
            ).status_code == 404

    # Verificar que la factura real de Tenant A no s'ha vist alterada
    await set_tenant_context(admin_session, str(ta["emp_id"]), role="BOSS")
    fac_row = (
        await admin_session.execute(
            select(FacturaCapcalera).where(FacturaCapcalera.id == uuid.UUID(fac_a_id))
        )
    ).scalar_one()
    assert fac_row.estat_document == "ESBORRANY_PREFACTURA"
