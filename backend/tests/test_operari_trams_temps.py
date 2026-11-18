"""Tests d'integració reals (PostgreSQL + RLS) per al temporitzador multi-tram GPS de l'operari."""

import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.main import app
from app.models.models import (
    Client,
    Empresa,
    OrdreTreball,
    OrdreTreballTramTemps,
    Usuari,
)


def _crear_token(usuari_id: uuid.UUID, empresa_id: uuid.UUID, rol: str = "CAP_DE_COLLA") -> str:
    payload = {
        "sub": str(usuari_id),
        "empresa_id": str(empresa_id),
        "rol": rol,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


@pytest.mark.asyncio
async def test_temporitzador_multi_tram_obrir_tancar_pausa_dinar(admin_session: AsyncSession):
    """Verifica el cicle complet Obrir -> Tancar (dinar) -> Obrir -> Tancar i acumulació d'hores facturables."""
    emp_id = uuid.uuid4()
    op_id = uuid.uuid4()
    client_id = uuid.uuid4()
    ot_id = uuid.uuid4()

    empresa = Empresa(
        id=emp_id,
        nom="Empresa Trams Test",
        nif=f"B{emp_id.hex[:8].upper()}",
        subdomini=f"trams-{emp_id.hex[:6]}",
    )
    admin_session.add(empresa)
    await admin_session.flush()

    operari = Usuari(
        id=op_id,
        empresa_id=emp_id,
        nom="Marc",
        cognoms="Soler",
        nif=f"OP{op_id.hex[:6].upper()}",
        rol="CAP_DE_COLLA",
        pin_hash="dummy",
    )
    admin_session.add(operari)

    client_ent = Client(
        id=client_id,
        empresa_id=emp_id,
        codi=f"CLI-{emp_id.hex[:4]}",
        rao_social="Client Multi-Tram SL",
        nif="B11223344",
    )
    admin_session.add(client_ent)
    await admin_session.flush()

    ot = OrdreTreball(
        id=ot_id,
        empresa_id=emp_id,
        codi=f"OT-{ot_id.hex[:5]}",
        client_id=client_id,
        cap_de_colla_id=op_id,
        titol="Instal·lació reg amb pausa de dinar",
        adreca="41.3851, 2.1734",
        estat="PENDENT",
        preu_venda_hora_aplicat=50.0,
    )
    admin_session.add(ot)
    await admin_session.commit()

    token = _crear_token(op_id, emp_id)
    headers = {"Authorization": f"Bearer {token}", "X-Empresa-ID": str(emp_id)}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test/api/v1") as client:
        # 1. OBRIR TEMPS (Tram 1 - Matí) amb GPS dins geovalla
        res_open1 = await client.put(
            f"/operari/feines/{ot_id}/comencar",
            json={"lat": 41.3851, "lng": 2.1734},
            headers=headers,
        )
        assert res_open1.status_code == 200, res_open1.text
        d1 = res_open1.json()
        assert d1["estat"] == "EN_CURS"
        assert d1["te_tram_obert"] is True
        assert d1["temps_acumulat_segons"] == 0
        assert len(d1["trams_temps"]) == 1

        # Simular 2 hores treballades al Tram 1
        tram1_id = uuid.UUID(d1["trams_temps"][0]["id"])
        await admin_session.execute(
            text("UPDATE ordres_treball_trams_temps SET hora_inici = now() - interval '2 hours' WHERE id = :tid"),
            {"tid": tram1_id},
        )
        await admin_session.commit()

        # 2. TANCAR TEMPS (Pausa per dinar) amb GPS
        res_close1 = await client.put(
            f"/operari/feines/{ot_id}/finalitzar-temps",
            json={"lat": 41.3851, "lng": 2.1734},
            headers=headers,
        )
        assert res_close1.status_code == 200, res_close1.text
        c1 = res_close1.json()
        assert c1["estat"] == "PAUSADA"
        assert c1["te_tram_obert"] is False
        assert c1["hores_imputades_facturables"] == pytest.approx(2.0, abs=0.05)
        assert len(c1["trams_temps"]) == 1

        # 3. TORNAR A OBRIR TEMPS (Tram 2 - Tarda) sense GPS disponible (fallback resilient)
        res_open2 = await client.put(
            f"/operari/feines/{ot_id}/comencar",
            json={"lat": None, "lng": None},
            headers=headers,
        )
        assert res_open2.status_code == 200, res_open2.text
        d2 = res_open2.json()
        assert d2["estat"] == "EN_CURS"
        assert d2["te_tram_obert"] is True
        assert d2["temps_acumulat_segons"] >= 7190
        assert len(d2["trams_temps"]) == 2

        # Simular 1.5 hores treballades al Tram 2
        tram2_id = uuid.UUID(d2["trams_temps"][1]["id"])
        await admin_session.execute(
            text("UPDATE ordres_treball_trams_temps SET hora_inici = now() - interval '90 minutes' WHERE id = :tid"),
            {"tid": tram2_id},
        )
        await admin_session.commit()

        # 4. TANCAR TEMPS (Fi de feina)
        res_close2 = await client.put(
            f"/operari/feines/{ot_id}/finalitzar-temps",
            json={"lat": 41.3851, "lng": 2.1734},
            headers=headers,
        )
        assert res_close2.status_code == 200, res_close2.text
        c2 = res_close2.json()
        assert c2["estat"] == "PAUSADA"
        assert c2["te_tram_obert"] is False
        assert c2["hores_imputades_facturables"] == pytest.approx(3.5, abs=0.05)
        assert c2["total_facturable_estimat"] == pytest.approx(175.0, abs=2.5)
        assert len(c2["trams_temps"]) == 2

        # 5. Consultar detall de la feina i verificar acumulació persistent
        res_detail = await client.get(f"/operari/feines/{ot_id}", headers=headers)
        assert res_detail.status_code == 200
        det = res_detail.json()
        assert det["te_tram_obert"] is False
        assert det["hores_imputades_facturables"] == pytest.approx(3.5, abs=0.05)
        assert len(det["trams_temps"]) == 2


@pytest.mark.asyncio
async def test_trams_temps_aillament_rls_multi_tenant(admin_session: AsyncSession):
    """Verifica que l'aïllament RLS impedeix que una segona empresa accedeixi als trams d'una altra."""
    emp_a = uuid.uuid4()
    emp_b = uuid.uuid4()
    op_a = uuid.uuid4()
    op_b = uuid.uuid4()
    cli_a = uuid.uuid4()
    ot_a = uuid.uuid4()

    admin_session.add_all([
        Empresa(id=emp_a, nom="Emp A", nif=f"A{emp_a.hex[:8].upper()}", subdomini=f"a-{emp_a.hex[:6]}"),
        Empresa(id=emp_b, nom="Emp B", nif=f"B{emp_b.hex[:8].upper()}", subdomini=f"b-{emp_b.hex[:6]}"),
    ])
    await admin_session.flush()

    admin_session.add_all([
        Usuari(id=op_a, empresa_id=emp_a, nom="Op A", nif=f"NA{op_a.hex[:5].upper()}", rol="OPERARI", pin_hash="x"),
        Usuari(id=op_b, empresa_id=emp_b, nom="Op B", nif=f"NB{op_b.hex[:5].upper()}", rol="OPERARI", pin_hash="x"),
        Client(id=cli_a, empresa_id=emp_a, codi="CA1", rao_social="Cli A", nif="B99001122"),
    ])
    await admin_session.flush()

    admin_session.add(
        OrdreTreball(
            id=ot_a,
            empresa_id=emp_a,
            codi=f"OT-{ot_a.hex[:5]}",
            client_id=cli_a,
            cap_de_colla_id=op_a,
            titol="OT A",
            adreca="41.3851, 2.1734",
            estat="PENDENT",
        )
    )
    await admin_session.commit()

    tok_a = _crear_token(op_a, emp_a, "OPERARI")
    tok_b = _crear_token(op_b, emp_b, "OPERARI")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test/api/v1") as client:
        res_a = await client.put(
            f"/operari/feines/{ot_a}/comencar",
            json={"lat": 41.3851, "lng": 2.1734},
            headers={"Authorization": f"Bearer {tok_a}", "X-Empresa-ID": str(emp_a)},
        )
        assert res_a.status_code == 200

        # Empresa B intenta obrir/tancar o veure la feina de l'Empresa A -> 404
        res_b = await client.put(
            f"/operari/feines/{ot_a}/comencar",
            json={"lat": 41.3851, "lng": 2.1734},
            headers={"Authorization": f"Bearer {tok_b}", "X-Empresa-ID": str(emp_b)},
        )
        assert res_b.status_code == 404

    # Verificació RLS directa a nivell de sessió PostgreSQL sota rol sevalor_app
    await admin_session.execute(text("SET LOCAL ROLE sevalor_app"))
    await admin_session.execute(
        text("SELECT set_config('app.current_empresa_id', :eid, true)"),
        {"eid": str(emp_b)},
    )
    rows_b = (
        await admin_session.execute(select(OrdreTreballTramTemps))
    ).scalars().all()
    assert len(rows_b) == 0
    await admin_session.execute(text("RESET ROLE"))


@pytest.mark.asyncio
async def test_suma_hores_existents_legacy_i_visibilitat_dashboard_gestio(admin_session: AsyncSession):
    """Verifica que les hores existents prèvies es sumen al nou tram i que /gestio/feines les exposa al dashboard."""
    emp_id = uuid.uuid4()
    op_id = uuid.uuid4()
    boss_id = uuid.uuid4()
    cli_id = uuid.uuid4()
    ot_id = uuid.uuid4()

    admin_session.add(
        Empresa(id=emp_id, nom="Emp Dash", nif=f"D{emp_id.hex[:8].upper()}", subdomini=f"dash-{emp_id.hex[:6]}")
    )
    await admin_session.flush()

    admin_session.add_all([
        Usuari(id=op_id, empresa_id=emp_id, nom="Op Dash", nif=f"OD{op_id.hex[:5].upper()}", rol="OPERARI", pin_hash="x"),
        Usuari(id=boss_id, empresa_id=emp_id, nom="Boss Dash", nif=f"BD{boss_id.hex[:5].upper()}", rol="BOSS", pin_hash="x"),
        Client(id=cli_id, empresa_id=emp_id, codi="CD1", rao_social="Cli Dash", nif="B55443322"),
    ])
    await admin_session.flush()

    # Ordre legacy amb 1.50 hores ja imputades prèviament i estat EN_CURS (sense files a trams_temps)
    admin_session.add(
        OrdreTreball(
            id=ot_id,
            empresa_id=emp_id,
            codi=f"OT-{ot_id.hex[:5]}",
            client_id=cli_id,
            cap_de_colla_id=op_id,
            titol="OT amb hores prèvies",
            adreca="41.3851, 2.1734",
            estat="EN_CURS",
            hora_inici_real=datetime.now(timezone.utc) - timedelta(minutes=30),
            hora_fi_real=None,
            hores_imputades_facturables=1.50,
            preu_venda_hora_aplicat=45.0,
        )
    )
    await admin_session.commit()

    tok_op = _crear_token(op_id, emp_id, "OPERARI")
    tok_boss = _crear_token(boss_id, emp_id, "BOSS")
    h_op = {"Authorization": f"Bearer {tok_op}", "X-Empresa-ID": str(emp_id)}
    h_boss = {"Authorization": f"Bearer {tok_boss}", "X-Empresa-ID": str(emp_id)}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test/api/v1") as client:
        # 1. Parar la feina: 1.50h prèvies + 0.50h actuals = 2.00h totals!
        res_stop = await client.put(
            f"/operari/feines/{ot_id}/finalitzar-temps",
            json={"lat": 41.3851, "lng": 2.1734},
            headers=h_op,
        )
        assert res_stop.status_code == 200, res_stop.text
        stop_data = res_stop.json()
        assert stop_data["estat"] == "PAUSADA"
        assert stop_data["hores_imputades_facturables"] == pytest.approx(2.0, abs=0.05)

        # 2. Verificar que el Dashboard (/gestio/feines) rep les hores, estat i trams!
        res_dash = await client.get("/gestio/feines", headers=h_boss)
        assert res_dash.status_code == 200, res_dash.text
        items = res_dash.json()
        target = next((f for f in items if f["id"] == str(ot_id)), None)
        assert target is not None
        assert target["estat"] == "PAUSADA"
        assert target["hores_imputades_facturables"] == pytest.approx(2.0, abs=0.05)
        assert target["te_tram_obert"] is False
        assert len(target["trams_temps"]) == 2


@pytest.mark.asyncio
async def test_tarifa_real_barema_panell_control_i_cost_operari_sense_hardcode(
    admin_session: AsyncSession, tmp_path
):
    """
    Verifica:
    1) Operari no rep preu_venda_hora_aplicat a GET /operari/feines/{id} (ni 45€ hardcodejat).
    2) cost_ma_obra_real utilitza cost_hora_eur real de l'operari (no 24.00€ hardcodejat).
    3) PUT /gestio/configuracio/barema aplica el preu real del panell de control a /gestio/feines i WIP.
    4) finalitzar-temps sense tram obert retorna HTTP 400.
    """
    emp_id = uuid.uuid4()
    op_id = uuid.uuid4()
    boss_id = uuid.uuid4()
    eng_id = uuid.uuid4()
    cli_id = uuid.uuid4()
    ot_id = uuid.uuid4()
    disc_dir = tmp_path / f"disc_{emp_id.hex[:8]}"
    disc_dir.mkdir(parents=True, exist_ok=True)

    admin_session.add(
        Empresa(
            id=emp_id,
            nom="Emp Tarifa Real",
            nif=f"R{emp_id.hex[:8].upper()}",
            subdomini=f"real-{emp_id.hex[:6]}",
            disc_dur_url=str(disc_dir),
        )
    )
    await admin_session.flush()

    admin_session.add_all([
        Usuari(
            id=op_id,
            empresa_id=emp_id,
            nom="Op Real",
            nif=f"OR{op_id.hex[:5].upper()}",
            rol="OPERARI",
            pin_hash="x",
            cost_hora_eur=30.00,
        ),
        Usuari(
            id=boss_id,
            empresa_id=emp_id,
            nom="Boss Real",
            nif=f"BR{boss_id.hex[:5].upper()}",
            rol="BOSS",
            pin_hash="x",
        ),
        Usuari(
            id=eng_id,
            empresa_id=emp_id,
            nom="Eng Real",
            nif=f"ER{eng_id.hex[:5].upper()}",
            rol="ENGINYER",
            pin_hash="x",
        ),
        Client(
            id=cli_id,
            empresa_id=emp_id,
            codi=f"CR-{cli_id.hex[:4]}",
            rao_social="Client Tarifa Real SL",
            nif="B77889900",
        ),
    ])
    await admin_session.flush()

    # OT amb default antic 45.00 a BD abans de configurar el Barema real
    admin_session.add(
        OrdreTreball(
            id=ot_id,
            empresa_id=emp_id,
            codi=f"OT-{ot_id.hex[:5]}",
            client_id=cli_id,
            cap_de_colla_id=op_id,
            titol="OT amb tarifa real",
            adreca="41.3851, 2.1734",
            estat="PENDENT",
            preu_venda_hora_aplicat=45.0,
        )
    )
    await admin_session.commit()

    tok_op = _crear_token(op_id, emp_id, "OPERARI")
    tok_boss = _crear_token(boss_id, emp_id, "BOSS")
    tok_eng = _crear_token(eng_id, emp_id, "ENGINYER")
    h_op = {"Authorization": f"Bearer {tok_op}", "X-Empresa-ID": str(emp_id)}
    h_boss = {"Authorization": f"Bearer {tok_boss}", "X-Empresa-ID": str(emp_id)}
    h_eng = {"Authorization": f"Bearer {tok_eng}", "X-Empresa-ID": str(emp_id)}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test/api/v1") as client:
        # 1. Intentar finalitzar-temps abans d'iniciar -> HTTP 400
        res_err = await client.put(
            f"/operari/feines/{ot_id}/finalitzar-temps",
            json={"lat": 41.3851, "lng": 2.1734},
            headers=h_op,
        )
        assert res_err.status_code == 400

        # 2. Configuració Barema al Panell de Control a 62.50 €/h
        res_bar = await client.put(
            "/gestio/configuracio/barema",
            json={
                "preu_hora_standard_eur": 62.5,
                "tarifa_urgencia_eur": 85.0,
                "suplement_desplacament_eur": 30.0,
                "marge_materials_defecte_pct": 25.0,
                "partides": [],
            },
            headers=h_boss,
        )
        assert res_bar.status_code == 200, res_bar.text

        # 3. Iniciar i Finalitzar temps real amb GPS diferents
        res_start = await client.put(
            f"/operari/feines/{ot_id}/comencar",
            json={"lat": 41.3851, "lng": 2.1734},
            headers=h_op,
        )
        assert res_start.status_code == 200, res_start.text
        tram_id = uuid.UUID(res_start.json()["trams_temps"][0]["id"])
        await admin_session.execute(
            text("UPDATE ordres_treball_trams_temps SET hora_inici = now() - interval '2 hours' WHERE id = :tid"),
            {"tid": tram_id},
        )
        await admin_session.commit()

        res_stop = await client.put(
            f"/operari/feines/{ot_id}/finalitzar-temps",
            json={"lat": 41.3852, "lng": 2.1735},
            headers=h_op,
        )
        assert res_stop.status_code == 200, res_stop.text
        stop_json = res_stop.json()
        assert "€" not in stop_json["missatge"]
        assert stop_json["total_facturable_estimat"] == pytest.approx(125.0, abs=3.5)
        tram_out = stop_json["trams_temps"][0]
        assert tram_out["gps_inici_lat"] == pytest.approx(41.3851, abs=1e-4)
        assert tram_out["gps_fi_lat"] == pytest.approx(41.3852, abs=1e-4)

        # 4. Detall operari NO exposa preu_venda_hora_aplicat
        res_op_det = await client.get(f"/operari/feines/{ot_id}", headers=h_op)
        assert res_op_det.status_code == 200
        assert res_op_det.json()["preu_venda_hora_aplicat"] is None

        # 5. Cost mà d'obra real a BD = 2h * 30.00 €/h = ~60.00 € (no 24.00 €/h)
        ot_db = (
            await admin_session.execute(select(OrdreTreball).where(OrdreTreball.id == ot_id))
        ).scalar_one()
        assert float(ot_db.cost_ma_obra_real) == pytest.approx(60.0, abs=2.0)

        # 6. Panell de control (/gestio/feines) rep la tarifa real 62.50 €/h (Enginyer -> None)
        res_g_list = await client.get("/gestio/feines", headers=h_boss)
        assert res_g_list.status_code == 200
        g_item = next(f for f in res_g_list.json() if f["id"] == str(ot_id))
        assert g_item["preu_venda_hora_aplicat"] == pytest.approx(62.5, abs=0.01)

        res_g_det = await client.get(f"/gestio/feines/{ot_id}", headers=h_boss)
        assert res_g_det.status_code == 200
        assert res_g_det.json()["preu_venda_hora_aplicat"] == pytest.approx(62.5, abs=0.01)

        res_eng_det = await client.get(f"/gestio/feines/{ot_id}", headers=h_eng)
        assert res_eng_det.status_code == 200
        assert res_eng_det.json()["preu_venda_hora_aplicat"] is None


@pytest.mark.asyncio
async def test_flux_complet_feina_acabada_a_prefactura_editable_i_verifactu(
    admin_session, tmp_path, monkeypatch
):
    """
    Verifica el flux complet:
    1) Feina acabada per l'operari (COMPLERT) i feina tancada per gestió (TANCADA) apareixen a /wip-control.
    2) Materials consumits a picking (PickIn - PickOut) i barema real del panell de control es traslladen a WIP i a la pre-factura.
    3) Convertir a Pre-factura crea ESBORRANY_PREFACTURA (Sèrie PRE), posa OT a PREFACTURADA, i NO compta encara a facturació emesa.
    4) Es pot editar la pre-factura (línies, quantitats, preus, descomptes, retencions) i recalcula totals exactes.
    5) Descartar una pre-factura retorna l'OT a WIP (COMPLERT).
    6) Emetre definitivament (HITL) converteix l'esborrany en Factura Veri*factu (Sèrie F, EMESA, PDF vàlid, OT FACTURADA) i bloqueja edicions posteriors.
    7) Aïllament RLS multi-tenant: Tenant B no pot veure, editar ni emetre pre-factures del Tenant A.
    """
    from app.models.models import Article, FullaPicking, LiniaPicking
    from app.services.sovereign_storage import SovereignStorageGateway

    monkeypatch.setenv("CLIENT_DISKS_MOUNT_ROOT", str(tmp_path / "disks_pref"))
    monkeypatch.setattr(
        SovereignStorageGateway,
        "TRANSIT_QUEUE_DIR",
        tmp_path / "transit_pref",
    )

    suf = uuid.uuid4().hex[:8]
    emp_a_id = uuid.uuid4()
    emp_b_id = uuid.uuid4()
    boss_a_id = uuid.uuid4()
    boss_b_id = uuid.uuid4()
    op_a_id = uuid.uuid4()
    cli_a_id = uuid.uuid4()
    ot_op_id = uuid.uuid4()
    ot_gest_id = uuid.uuid4()
    art_id = uuid.uuid4()
    fulla_id = uuid.uuid4()

    disc_a = tmp_path / "disc_pref_a"
    disc_b = tmp_path / "disc_pref_b"
    disc_a.mkdir(parents=True, exist_ok=True)
    disc_b.mkdir(parents=True, exist_ok=True)

    admin_session.add_all(
        [
            Empresa(
                id=emp_a_id,
                nom="Instal·lacions Prefactura SL",
                nif=f"B{suf[:8]}",
                subdomini=f"prefa-{suf}",
                pla_subscripcio="PRO",
                estat_pagament="ACTIU",
            ),
            Empresa(
                id=emp_b_id,
                nom="Competidor B SL",
                nif=f"B{suf[:7]}9",
                subdomini=f"prefb-{suf}",
                pla_subscripcio="PRO",
                estat_pagament="ACTIU",
            ),
        ]
    )
    await admin_session.flush()

    await admin_session.execute(text(f"SET LOCAL app.current_empresa_id = '{emp_a_id}';"))
    await admin_session.execute(text("SET LOCAL app.current_user_role = 'BOSS';"))

    admin_session.add_all(
        [
            Usuari(
                id=boss_a_id,
                empresa_id=emp_a_id,
                nif=f"BA-{suf}",
                nom="Boss A",
                rol="BOSS",
                telefon=f"+34610{suf[:6]}",
                email=f"ba-{suf}@test.cat",
                password_hash="x",
                estat="ACTIU",
            ),
            Usuari(
                id=op_a_id,
                empresa_id=emp_a_id,
                nif=f"OA-{suf}",
                nom="Operari A",
                rol="OPERARI",
                telefon=f"+34611{suf[:6]}",
                email=f"oa-{suf}@test.cat",
                password_hash="x",
                cost_hora_referencia=25.00,
                estat="ACTIU",
            ),
            Client(
                id=cli_a_id,
                empresa_id=emp_a_id,
                codi=f"CL-{suf[:5]}",
                rao_social="Agrícola Lleida S.A.",
                nif="A25001122",
            ),
            Article(
                id=art_id,
                empresa_id=emp_a_id,
                referencia_inventari=f"MAT-{suf}",
                nom="Electrovàlvula 24V",
                unitat_mesura="UNITAT",
                preu_cost=15.00,
                preu_cost_mitja=15.00,
                preu_venda=40.00,
                actiu=True,
            ),
        ]
    )
    await admin_session.flush()

    admin_session.add_all(
        [
            OrdreTreball(
                id=ot_op_id,
                empresa_id=emp_a_id,
                codi=f"OT-OP-{suf[:5]}",
                client_id=cli_a_id,
                titol="Reparació reg sector B",
                adreca="Camí de Rufea 10, Lleida",
                estat="EN_CURS",
                cap_de_colla_id=op_a_id,
                hores_imputades_facturables=2.0,
            ),
            OrdreTreball(
                id=ot_gest_id,
                empresa_id=emp_a_id,
                codi=f"OT-GS-{suf[:5]}",
                client_id=cli_a_id,
                titol="Revisió bomba pou",
                adreca="Camí de Rufea 11, Lleida",
                estat="ASSIGNADA",
                cap_de_colla_id=op_a_id,
                hores_imputades_facturables=1.0,
            ),
        ]
    )
    await admin_session.flush()

    admin_session.add(
        FullaPicking(
            id=fulla_id,
            empresa_id=emp_a_id,
            ordre_treball_id=ot_op_id,
            estat_picking="CONSOLIDADA",
        )
    )
    await admin_session.flush()
    admin_session.add(
        LiniaPicking(
            empresa_id=emp_a_id,
            picking_id=fulla_id,
            article_id=art_id,
            quantitat_prevista=3.0,
            quantitat_carregada_pick_in=3.0,
            quantitat_retornada_pick_out=1.0,
            quantitat_mermada=0.0,
        )
    )
    await admin_session.commit()

    # Tenant B user
    await admin_session.execute(text(f"SET LOCAL app.current_empresa_id = '{emp_b_id}';"))
    await admin_session.execute(text("SET LOCAL app.current_user_role = 'BOSS';"))
    admin_session.add(
        Usuari(
            id=boss_b_id,
            empresa_id=emp_b_id,
            nif=f"BB-{suf}",
            nom="Boss B",
            rol="BOSS",
            telefon=f"+34612{suf[:6]}",
            email=f"bb-{suf}@test.cat",
            password_hash="x",
            estat="ACTIU",
        )
    )
    await admin_session.commit()

    # Pujar les 3 fotos QA al disc sobirà per poder finalitzar via /operari/feines/{id}/finalitzar
    await admin_session.execute(text(f"SET LOCAL app.current_empresa_id = '{emp_a_id}';"))
    for tipus in ("inicial", "intermedia", "final"):
        await SovereignStorageGateway.pujar_fitxer_binari(
            db=admin_session,
            empresa_id=str(emp_a_id),
            categoria="ots_actives",
            nom_fitxer=f"ot_{ot_op_id}_foto_{tipus}.webp",
            content=b"RIFF....WEBP",
            content_type="image/webp",
        )

    h_boss_a = {"Authorization": f"Bearer {_crear_token(boss_a_id, emp_a_id, 'BOSS')}"}
    h_op_a = {"Authorization": f"Bearer {_crear_token(op_a_id, emp_a_id, 'OPERARI')}"}
    h_boss_b = {"Authorization": f"Bearer {_crear_token(boss_b_id, emp_b_id, 'BOSS')}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1") as client:
        # 1. Configurar barema real a 55.00 €/h
        r_bar = await client.put(
            "/gestio/configuracio/barema",
            json={"preu_hora_standard_eur": 55.0, "preu_hora_urgencia_eur": 80.0},
            headers=h_boss_a,
        )
        assert r_bar.status_code == 200, r_bar.text

        # 2. L'operari finalitza la feina (COMPLERT) i gestió tanca la segona (TANCADA)
        r_fin = await client.put(
            f"/operari/feines/{ot_op_id}/finalitzar",
            json={"observacions": "Feina acabada a camp"},
            headers=h_op_a,
        )
        assert r_fin.status_code == 200, r_fin.text
        assert r_fin.json()["estat"] == "COMPLERT"

        r_tan = await client.put(
            f"/gestio/feines/{ot_gest_id}/tancar-obra",
            json={"signatura_base64": "data:image/png;base64,AA==", "conformitat_client": True},
            headers=h_boss_a,
        )
        assert r_tan.status_code == 200, r_tan.text
        assert r_tan.json()["status"] == "TANCADA"

        # 3. Ambdues feines acabades han d'aparèixer a /wip-control amb tarifes i materials reals
        r_wip = await client.get("/gestio/comptabilitat/wip-control", headers=h_boss_a)
        assert r_wip.status_code == 200, r_wip.text
        wip_data = r_wip.json()
        assert wip_data["nombre_ots_en_wip"] == 2
        wip_op = next(i for i in wip_data["items"] if i["ordre_treball_id"] == str(ot_op_id))
        # 2h * 55.00 + (3-1)*40.00 = 110 + 80 = 190.00
        assert float(wip_op["valor_wip_pvp"]) == pytest.approx(190.0, abs=0.01)
        assert float(wip_op["pvp_materials"]) == pytest.approx(80.0, abs=0.01)
        assert wip_op["client_nom"] == "Agrícola Lleida S.A."

        # 4. Convertir OT a Pre-factura -> crea ESBORRANY_PREFACTURA (Sèrie PRE) i NO factura emesa
        r_pref = await client.post(
            f"/gestio/comptabilitat/wip-control/{ot_op_id}/prefacturar",
            headers=h_boss_a,
        )
        assert r_pref.status_code == 201, r_pref.text
        pref_res = r_pref.json()
        pref_id = pref_res["id"]
        assert pref_res["serie"] == "PRE"
        assert pref_res["estat_document"] == "ESBORRANY_PREFACTURA"
        assert float(pref_res["liquid_exigible"]) == pytest.approx(190.0 * 1.21, abs=0.02)

        # Dashboard P&L encara no computa l'esborrany com a facturació emesa
        r_dash = await client.get("/gestio/comptabilitat/dashboard-economic", headers=h_boss_a)
        assert r_dash.status_code == 200
        assert float(r_dash.json()["facturacio_neta"]) == 0.0

        # Apareix a /prefactures amb les 2 línies (mà d'obra + material consumit)
        r_list_pref = await client.get("/gestio/comptabilitat/prefactures", headers=h_boss_a)
        assert r_list_pref.status_code == 200
        pref_item = next(p for p in r_list_pref.json() if p["id"] == pref_id)
        assert len(pref_item["linies"]) == 2
        assert pref_item["ordres_treball_codis"] == [f"OT-OP-{suf[:5]}"]

        # 5. RLS Tenant B no pot veure, editar ni emetre la pre-factura del Tenant A
        assert (await client.get(f"/gestio/comptabilitat/factures/{pref_id}", headers=h_boss_b)).status_code == 404
        assert (
            await client.post(
                f"/gestio/comptabilitat/prefactures/{pref_id}/emetre",
                json={"serie": "F", "confirmacio_humana_hitl": True},
                headers=h_boss_b,
            )
        ).status_code == 404

        # 6. Editar la pre-factura: ajustar preu, descompte i afegir línia de desplaçament
        r_edit = await client.put(
            f"/gestio/comptabilitat/prefactures/{pref_id}",
            json={
                "metode_pagament": "REBUT_DOMICILIAT",
                "es_inversio_subjecte_passiu": False,
                "retencio_irpf_pct": 0,
                "retencio_garantia_pct": 0,
                "linies": [
                    {
                        "obra_id": str(ot_op_id),
                        "concepte": "Mà d'obra tècnica ajustada",
                        "quantitat": 2.5,
                        "preu_venda_unitari": 60.0,
                        "descompte_aplicat_pct": 10.0,
                        "tipus_iva_pct": 21.0,
                    },
                    {
                        "obra_id": str(ot_op_id),
                        "concepte": "Desplaçament urgència",
                        "quantitat": 1.0,
                        "preu_venda_unitari": 35.0,
                        "descompte_aplicat_pct": 0.0,
                        "tipus_iva_pct": 21.0,
                    },
                ],
            },
            headers=h_boss_a,
        )
        assert r_edit.status_code == 200, r_edit.text
        edited = r_edit.json()
        # 2.5 * 60 * 0.9 = 135.00 + 35.00 = 170.00 base | IVA 35.70 | Total 205.70
        assert float(edited["base_imposable"]) == pytest.approx(170.0, abs=0.01)
        assert float(edited["quota_iva"]) == pytest.approx(35.70, abs=0.01)
        assert float(edited["liquid_exigible"]) == pytest.approx(205.70, abs=0.01)

        # 7. Emetre definitivament a Veri*factu (Sèrie F) -> PDF vàlid, hash SHA-256 i bloqueig d'edició posterior
        r_emit = await client.post(
            f"/gestio/comptabilitat/prefactures/{pref_id}/emetre",
            json={"serie": "F", "confirmacio_humana_hitl": True},
            headers=h_boss_a,
        )
        assert r_emit.status_code == 200, r_emit.text
        emesa = r_emit.json()
        assert emesa["serie"] == "F"
        assert emesa["estat_document"] == "EMESA"
        assert len(emesa["hash_sha256"]) == 64

        r_pdf = await client.get(f"/gestio/comptabilitat/factures/{pref_id}/pdf", headers=h_boss_a)
        assert r_pdf.status_code == 200
        assert r_pdf.content.startswith(b"%PDF")

        # Ja no es pot editar un cop emesa a Veri*factu
        r_edit_blocked = await client.put(
            f"/gestio/comptabilitat/prefactures/{pref_id}",
            json={
                "linies": [
                    {
                        "concepte": "Intent mutació",
                        "quantitat": 1,
                        "preu_venda_unitari": 10.0,
                        "tipus_iva_pct": 21.0,
                    }
                ]
            },
            headers=h_boss_a,
        )
        assert r_edit_blocked.status_code == 400

        # 8. Descartar una pre-factura de la segona OT la retorna a WIP
        r_pref2 = await client.post(
            f"/gestio/comptabilitat/wip-control/{ot_gest_id}/prefacturar",
            headers=h_boss_a,
        )
        assert r_pref2.status_code == 201
        pref2_id = r_pref2.json()["id"]

        r_del2 = await client.delete(
            f"/gestio/comptabilitat/prefactures/{pref2_id}",
            headers=h_boss_a,
        )
        assert r_del2.status_code == 200

        r_wip_after = await client.get("/gestio/comptabilitat/wip-control", headers=h_boss_a)
        assert r_wip_after.status_code == 200
        wip_ids = [i["ordre_treball_id"] for i in r_wip_after.json()["items"]]
        assert str(ot_gest_id) in wip_ids
        assert str(ot_op_id) not in wip_ids


