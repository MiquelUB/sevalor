"""Tests del BLOC 5 — Spotlight RLS, Veto Enginyer en Flota/Operaris/Clients/Contractes, Proveïdors BEC+CAE, Comptabilitat, Configuració, Notificacions Redis+Telegram i Plànols."""

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import jwt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.api.v1.gestio import notificacions as notis_mod
from app.core.config import settings
from app.main import app
from app.models.contractes import ContracteManteniment
from app.models.models import (
    Article,
    CapaVectorial,
    CarpetaPlanol,
    Client,
    Empresa,
    ExportacioPdfPlanol,
    FacturaCapcalera,
    MantenimentVehicle,
    OrdreTreball,
    PinIncidenciaPlanol,
    PlanolBase,
    Proveidor,
    Usuari,
    Vehicle,
)
from app.services.sovereign_storage import inicialitzar_arbre_carpetes_disc


def _make_token(usuari_id: uuid.UUID, empresa_id: uuid.UUID, rol: str) -> str:
    payload: dict[str, Any] = {
        "sub": str(usuari_id),
        "rol": rol,
        "empresa_id": str(empresa_id),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=20),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


async def _seed_empresa_bloc5(
    admin_session,
    disc_root: Path,
    nom: str = "Empresa Bloc5 S.L.",
):
    inicialitzar_arbre_carpetes_disc(disc_root)
    emp_id = uuid.uuid4()
    boss_id = uuid.uuid4()
    sec_id = uuid.uuid4()
    eng_id = uuid.uuid4()
    op_id = uuid.uuid4()

    admin_session.add(
        Empresa(
            id=emp_id,
            nom=nom,
            nif="B" + uuid.uuid4().hex[:8].upper(),
            subdomini="b5-" + uuid.uuid4().hex[:6],
            pla_subscripcio="PRO",
            estat_pagament="ACTIU",
            disc_dur_url=str(disc_root),
            telegram_bot_actiu=True,
        )
    )
    await admin_session.flush()

    for uid, nom_u, cognoms_u, rol_u, tel_u, extra in [
        (boss_id, "Marc", "Direcció", "BOSS", "610111222", {}),
        (sec_id, "Anna", "Secretaria", "SECRETARIA", "610111333", {}),
        (eng_id, "Pau", "Enginyeria", "ENGINYER", "610111444", {}),
        (op_id, "Joan", "Operari", "OPERARI", "610111555", {"cost_hora_eur": 24.5}),
    ]:
        admin_session.add(
            Usuari(
                id=uid,
                empresa_id=emp_id,
                nif=f"{rol_u[0]}{uid.hex[:7].upper()}Z",
                nom=nom_u,
                cognoms=cognoms_u,
                email=f"{rol_u.lower()}-{emp_id.hex[:6]}-{uid.hex[:4]}@sevalor.test",
                telefon=tel_u,
                rol=rol_u,
                pin_hash="fake",
                password_hash="fake",
                estat="ACTIU",
                **extra,
            )
        )
    await admin_session.flush()

    return {
        "empresa_id": emp_id,
        "boss_id": boss_id,
        "sec_id": sec_id,
        "eng_id": eng_id,
        "op_id": op_id,
        "headers_boss": {"Authorization": f"Bearer {_make_token(boss_id, emp_id, 'BOSS')}"},
        "headers_sec": {"Authorization": f"Bearer {_make_token(sec_id, emp_id, 'SECRETARIA')}"},
        "headers_eng": {"Authorization": f"Bearer {_make_token(eng_id, emp_id, 'ENGINYER')}"},
        "headers_op": {"Authorization": f"Bearer {_make_token(op_id, emp_id, 'OPERARI')}"},
    }


@pytest.mark.asyncio
async def test_01_spotlight_cerca_rls_i_enllacos_reals(admin_session, tmp_path):
    tenant_a = await _seed_empresa_bloc5(admin_session, tmp_path / "disc_a", "Empresa A")
    tenant_b = await _seed_empresa_bloc5(admin_session, tmp_path / "disc_b", "Empresa B")

    tag = f"ALFA-{uuid.uuid4().hex[:5].upper()}"
    cli_a = Client(
        id=uuid.uuid4(),
        empresa_id=tenant_a["empresa_id"],
        codi="CL-A",
        rao_social=f"Client {tag} Propi",
        nif=f"A{uuid.uuid4().hex[:8].upper()}",
    )
    cli_b = Client(
        id=uuid.uuid4(),
        empresa_id=tenant_b["empresa_id"],
        codi="CL-B",
        rao_social=f"Client {tag} Alien",
        nif=f"B{uuid.uuid4().hex[:8].upper()}",
    )
    veh_a = Vehicle(
        id=uuid.uuid4(),
        empresa_id=tenant_a["empresa_id"],
        matricula=f"99{tag[:4]}",
        marca="Toyota",
        model=f"Hilux {tag}",
        estat="OPERATIU",
    )
    art_a = Article(
        id=uuid.uuid4(),
        empresa_id=tenant_a["empresa_id"],
        referencia_inventari=f"REF-{tag}",
        nom=f"Bomba {tag}",
        codi_barres=f"CB{tag}",
        preu_cost=100.0,
        preu_venda=150.0,
    )
    ot_a = OrdreTreball(
        id=uuid.uuid4(),
        empresa_id=tenant_a["empresa_id"],
        codi=f"OT-{tag}",
        client_id=cli_a.id,
        titol=f"Revisió {tag}",
        adreca="Finca Nord, Lleida",
        vertical="CAMPOPRO",
        estat="PLANIFICADA",
    )
    admin_session.add_all([cli_a, cli_b, veh_a, art_a, ot_a])
    await admin_session.flush()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res_a = await ac.get(
            f"/api/v1/gestio/cerca?q={tag}", headers=tenant_a["headers_boss"]
        )
        assert res_a.status_code == 200, res_a.text
        items_a = res_a.json()
        titols_a = [x["titol"] for x in items_a]
        assert any("Propi" in t for t in titols_a)
        assert not any("Alien" in t for t in titols_a)
        assert all(x["esFinancera"] is False for x in items_a)

        urls = {x["tipus"]: x["ref"] for x in items_a}
        assert urls["CLIENT"].startswith("/gestio/clients?id=")
        assert urls["VEHICLE"].startswith("/gestio/flota?id=")
        assert urls["ORDRE"].startswith("/gestio/feines?id=")
        assert urls["ARTICLE"].startswith("/gestio/magatzem?id=")

        res_spot_b = await ac.get("/api/v1/spotlight/items", headers=tenant_b["headers_boss"])
        assert res_spot_b.status_code == 200
        spot_titols_b = [x["titol"] for x in res_spot_b.json()]
        assert not any("Propi" in t for t in spot_titols_b)

        res_eng = await ac.get(f"/api/v1/gestio/cerca?q={tag}", headers=tenant_a["headers_eng"])
        assert res_eng.status_code == 200


@pytest.mark.asyncio
async def test_02_contractes_rbac_enginyer_403_i_prefactura_real(admin_session, tmp_path):
    tenant = await _seed_empresa_bloc5(admin_session, tmp_path / "disc_c")
    cli = Client(
        id=uuid.uuid4(),
        empresa_id=tenant["empresa_id"],
        codi="CL-CON",
        rao_social="Agrícola Segrià S.L.",
        nif="B99887766",
    )
    admin_session.add(cli)
    await admin_session.flush()

    contracte = ContracteManteniment(
        id=uuid.uuid4(),
        empresa_id=tenant["empresa_id"],
        client_id=cli.id,
        numero_contracte="CON-2026-B5",
        observacions="Manteniment Reg Trimestral",
        estat="ACTIU",
        import_anual=Decimal("1200.00"),
        periodicitat="TRIMESTRAL",
        data_inici=date(2026, 1, 1),
        data_fi=date(2026, 12, 31),
    )
    admin_session.add(contracte)
    await admin_session.flush()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        for role_hdr in (tenant["headers_eng"], tenant["headers_op"]):
            r_mrr = await ac.get("/api/v1/gestio/contractes/mrr", headers=role_hdr)
            assert r_mrr.status_code == 403
            r_lst = await ac.get("/api/v1/gestio/contractes/", headers=role_hdr)
            assert r_lst.status_code == 403
            r_pre = await ac.post(
                f"/api/v1/gestio/contractes/{contracte.id}/prefacturar", headers=role_hdr
            )
            assert r_pre.status_code == 403

        r_boss_mrr = await ac.get("/api/v1/gestio/contractes/mrr", headers=tenant["headers_boss"])
        assert r_boss_mrr.status_code == 200
        assert r_boss_mrr.json()["mrr"] == 100.0

        r_boss_list = await ac.get("/api/v1/gestio/contractes/", headers=tenant["headers_boss"])
        assert r_boss_list.status_code == 200
        assert r_boss_list.json()[0]["client_nom"] == "Agrícola Segrià S.L."

        r_pre1 = await ac.post(
            f"/api/v1/gestio/contractes/{contracte.id}/prefacturar",
            headers=tenant["headers_boss"],
        )
        assert r_pre1.status_code == 200, r_pre1.text
        d1 = r_pre1.json()
        assert d1["serie"] == "PRE"
        assert d1["numero_factura"] == 1
        assert d1["base_imposable"] == 300.0

        f_db = (
            await admin_session.execute(
                select(FacturaCapcalera).where(FacturaCapcalera.id == uuid.UUID(d1["factura_id"]))
            )
        ).scalars().first()
        assert f_db is not None
        assert f_db.estat_document == "ESBORRANY_PREFACTURA"
        assert f_db.estat_enviament == "ESBORRANY"
        assert f_db.hash_sha256 == "ESBORRANY_PREFACTURA"
        assert f_db.num_serie_verifactu.startswith("PRE-")


@pytest.mark.asyncio
async def test_03_clients_iban_veto_fitxa360_i_edicio(admin_session, tmp_path):
    tenant = await _seed_empresa_bloc5(admin_session, tmp_path / "disc_cli")
    iban_valid = "ES9121000418450200051332"
    cli_payload = {
        "codi": "CLI-360",
        "rao_social": "Regadius Lleida S.L.",
        "nif": "B12345678",
        "telefon": "973112233",
        "email": "reg@lleida.test",
        "adreca_fiscal": "Carrer Major 1, Lleida",
        "iban": iban_valid,
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r_create = await ac.post(
            "/api/v1/gestio/clients", json=cli_payload, headers=tenant["headers_boss"]
        )
        assert r_create.status_code == 201, r_create.text
        cli_id = r_create.json()["id"]
        assert r_create.json()["iban"] == iban_valid

        admin_session.add(
            OrdreTreball(
                id=uuid.uuid4(),
                empresa_id=tenant["empresa_id"],
                codi="OT-360-01",
                client_id=uuid.UUID(cli_id),
                titol="Intervenció 360",
                adreca="Carrer Major 1, Lleida",
                vertical="CAMPOPRO",
                estat="EN_CURS",
            )
        )
        await admin_session.flush()

        # Edició per ENGINYER preserva IBAN a BD però retorna masked/None
        r_put_eng = await ac.put(
            f"/api/v1/gestio/clients/{cli_id}",
            json={**cli_payload, "rao_social": "Regadius Modificat", "iban": None},
            headers=tenant["headers_eng"],
        )
        assert r_put_eng.status_code == 200, r_put_eng.text
        assert r_put_eng.json()["rao_social"] == "Regadius Modificat"
        assert r_put_eng.json()["iban"] is None

        # Fitxa 360: ENGINYER no rep xifres econòmiques ni IBAN; BOSS sí
        r_360_eng = await ac.get(
            f"/api/v1/gestio/clients/{cli_id}/fitxa-360", headers=tenant["headers_eng"]
        )
        assert r_360_eng.status_code == 200
        d_eng = r_360_eng.json()
        assert d_eng["client"]["iban"] is None
        assert len(d_eng["intervencions"]) == 1
        assert d_eng["intervencions"][0]["cost_material"] is None
        assert d_eng["intervencions"][0]["ingres_facturat"] is None
        assert d_eng["intervencions"][0]["marge_brut"] is None

        r_360_boss = await ac.get(
            f"/api/v1/gestio/clients/{cli_id}/fitxa-360", headers=tenant["headers_boss"]
        )
        assert r_360_boss.status_code == 200
        d_boss = r_360_boss.json()
        assert d_boss["client"]["iban"] == iban_valid
        assert d_boss["intervencions"][0]["cost_material"] == 0.0
        assert d_boss["intervencions"][0]["ingres_facturat"] == 0.0
        assert d_boss["intervencions"][0]["marge_brut"] == 0.0


@pytest.mark.asyncio
async def test_04_proveidors_rls_bec_i_cae_magic_bytes(admin_session, tmp_path):
    tenant_a = await _seed_empresa_bloc5(admin_session, tmp_path / "disc_pa")
    tenant_b = await _seed_empresa_bloc5(admin_session, tmp_path / "disc_pb")

    prov_b = Proveidor(
        id=uuid.uuid4(),
        empresa_id=tenant_b["empresa_id"],
        codi="PRV-B",
        rao_social="Proveidor Alien B S.L.",
        nif="B87654321",
        iban_xifrat_simetric="ES9121000418450200051332",
    )
    admin_session.add(prov_b)
    await admin_session.flush()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r_new = await ac.post(
            "/api/v1/gestio/proveidors",
            json={
                "codi": "PRV-A",
                "rao_social": "Subministraments Hidràulics S.L.",
                "nif": "B55443322",
                "iban": "ES9121000418450200051332",
            },
            headers=tenant_a["headers_boss"],
        )
        assert r_new.status_code == 201, r_new.text
        prov_a_id = r_new.json()["id"]

        # RLS: Tenant A no veu B
        r_list_a = await ac.get("/api/v1/gestio/proveidors", headers=tenant_a["headers_boss"])
        assert r_list_a.status_code == 200
        assert all(p["id"] != str(prov_b.id) for p in r_list_a.json())

        r_iban_cross = await ac.get(
            f"/api/v1/gestio/proveidors/{prov_b.id}/iban", headers=tenant_a["headers_boss"]
        )
        assert r_iban_cross.status_code == 404

        # ENGINYER no veu IBAN
        r_list_eng = await ac.get("/api/v1/gestio/proveidors", headers=tenant_a["headers_eng"])
        assert r_list_eng.status_code == 200
        assert r_list_eng.json()[0]["iban"] is None
        assert r_list_eng.json()[0]["iban_ofuscat"] is None
        assert r_list_eng.json()[0]["iban_visible"] == "**** (Restringit)"

        # Flux BEC: SECRETARIA registra canvi -> bloqueig_bec=True -> BOSS autoritza -> bloqueig_bec=False
        r_bec_req = await ac.post(
            "/api/v1/gestio/proveidors/canvi-iban",
            json={
                "proveidor_id": prov_a_id,
                "nou_iban": "ES7921000813610123456789",
                "origen_deteccio": "VERIFICACIO_FACTURA",
            },
            headers=tenant_a["headers_sec"],
        )
        assert r_bec_req.status_code == 200, r_bec_req.text
        assert r_bec_req.json()["estat"] == "BLOQUEIG_ANTIFRAU_IBAN"

        r_chk_bec = await ac.get("/api/v1/gestio/proveidors", headers=tenant_a["headers_boss"])
        assert r_chk_bec.json()[0]["bloqueig_bec"] is True

        r_auth_eng = await ac.post(
            "/api/v1/gestio/proveidors/autoritzar-canvi-iban",
            json={
                "proveidor_id": prov_a_id,
                "verificacio_telefonica_feta": True,
                "persona_contactada": "Joan Responsable",
            },
            headers=tenant_a["headers_sec"],
        )
        assert r_auth_eng.status_code == 403

        r_auth_boss = await ac.post(
            "/api/v1/gestio/proveidors/autoritzar-canvi-iban",
            json={
                "proveidor_id": prov_a_id,
                "verificacio_telefonica_feta": True,
                "persona_contactada": "Joan Responsable",
            },
            headers=tenant_a["headers_boss"],
        )
        assert r_auth_boss.status_code == 200
        assert r_auth_boss.json()["iban_ofuscat"] == "****6789"

        # CAE Magic Bytes: falsificat 422, PNG real 201
        r_cae_bad = await ac.post(
            f"/api/v1/gestio/proveidors/{prov_a_id}/cae",
            data={"tipus_document": "POLISSA_RC", "data_caducitat": "2028-01-01"},
            files={"file": ("fals.pdf", b"NOT_A_REAL_PDF_OR_PNG", "application/pdf")},
            headers=tenant_a["headers_boss"],
        )
        assert r_cae_bad.status_code == 422

        png_min = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
        r_cae_ok = await ac.post(
            f"/api/v1/gestio/proveidors/{prov_a_id}/cae",
            data={"tipus_document": "POLISSA_RC", "data_caducitat": "2028-01-01"},
            files={"file": ("polissa.png", png_min, "image/png")},
            headers=tenant_a["headers_boss"],
        )
        assert r_cae_ok.status_code == 201, r_cae_ok.text
        r_list_after = await ac.get("/api/v1/gestio/proveidors", headers=tenant_a["headers_boss"])
        assert r_list_after.json()[0]["estat_cae"] == "EN_VIGOR"
        assert r_list_after.json()[0]["bloqueig_bec"] is False
        assert r_list_after.json()[0]["iban_ofuscat"] == "****6789"


@pytest.mark.asyncio
async def test_05_flota_propers_anomalia_persistent_i_veto_tco(admin_session, tmp_path):
    tenant = await _seed_empresa_bloc5(admin_session, tmp_path / "disc_flo")
    veh = Vehicle(
        id=uuid.uuid4(),
        empresa_id=tenant["empresa_id"],
        matricula="4444-FLT",
        marca="Ford",
        model="Transit Custom",
        tipus="DIESEL",
        estat="OPERATIU",
        regim_adquisicio="RENTING",
        quota_mensual_eur=520.0,
        tarifa_diaria_eur=35.0,
        preu_km_exces_eur=0.12,
        valor_residual_eur=4500.0,
        fianca_eur=600.0,
        consum_l_100km=11.5,
        consum_mitjana_historica=7.0,
        data_inici_contracte=date.today() - timedelta(days=30),
        data_fi_contracte=date.today() + timedelta(days=335),
    )
    admin_session.add(veh)
    await admin_session.flush()
    mant = MantenimentVehicle(
        id=uuid.uuid4(),
        empresa_id=tenant["empresa_id"],
        vehicle_id=veh.id,
        data_manteniment=datetime.now(timezone.utc),
        tipus="PREVENTIU",
        descripcio="Canvi filtres",
        cost_euros=210.0,
    )
    admin_session.add(mant)
    await admin_session.flush()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # /propers sense coords d'OT activa no falla amb ValidationError
        r_prop = await ac.get(
            "/api/v1/gestio/flota/propers?lat=41.61&lng=0.62",
            headers=tenant["headers_eng"],
        )
        assert r_prop.status_code == 200, r_prop.text
        assert r_prop.json()[0]["lat"] is None
        assert r_prop.json()[0]["distancia_km"] is None

        # Descartar anomalia persisteix anomalia_consum_descartada = True
        r_desc = await ac.post(
            "/api/v1/gestio/flota/descartar-anomalia-consum",
            json={
                "vehicle_id": str(veh.id),
                "motiu_tipificat": "CARREGA_PESADA",
                "observacions": "Transport generador",
            },
            headers=tenant["headers_eng"],
        )
        assert r_desc.status_code == 200
        assert r_desc.json()["anomalia_consum_descartada"] is True

        # Veto TCO per ENGINYER vs BOSS
        r_flo_eng = await ac.get("/api/v1/gestio/flota", headers=tenant["headers_eng"])
        assert r_flo_eng.status_code == 200
        v_eng = r_flo_eng.json()[0]
        assert v_eng["anomalia_descartada"] is True
        assert v_eng["anomalia_consum"] is False
        assert v_eng["quota_mensual_eur"] is None
        assert v_eng["cost_total_acumulat_eur"] is None
        assert v_eng["cost_per_km_eur"] is None

        r_mant_eng = await ac.get(
            f"/api/v1/gestio/flota/{veh.id}/manteniments", headers=tenant["headers_eng"]
        )
        assert r_mant_eng.status_code == 200
        assert r_mant_eng.json()[0]["cost_euros"] is None

        r_flo_boss = await ac.get("/api/v1/gestio/flota", headers=tenant["headers_boss"])
        assert r_flo_boss.status_code == 200
        v_boss = r_flo_boss.json()[0]
        assert v_boss["quota_mensual_eur"] == 520.0
        assert v_boss["cost_total_acumulat_eur"] > 0


@pytest.mark.asyncio
async def test_06_operaris_sense_lleida_km_mes_i_veto_cost(admin_session, tmp_path):
    tenant = await _seed_empresa_bloc5(admin_session, tmp_path / "disc_op")
    # Vehicle amb 95000 km històrics: NO s'ha d'exposar com km del mes!
    veh_old = Vehicle(
        id=uuid.uuid4(),
        empresa_id=tenant["empresa_id"],
        matricula="7777-KMS",
        marca="Iveco",
        model="Daily",
        estat="OPERATIU",
        odometre_acumulat=95000,
    )
    cli = Client(
        id=uuid.uuid4(),
        empresa_id=tenant["empresa_id"],
        codi="CL-KM",
        rao_social="Client KM S.L.",
        nif="B44332211",
    )
    admin_session.add_all([veh_old, cli])
    await admin_session.flush()

    ot_mes = OrdreTreball(
        id=uuid.uuid4(),
        empresa_id=tenant["empresa_id"],
        codi="OT-KM-01",
        client_id=cli.id,
        titol="Desplaçament sector",
        adreca="Camí de Vallfogona, Lleida",
        vertical="CAMPOPRO",
        estat="EN_CURS",
        km_imputats=42,
    )
    admin_session.add(ot_mes)
    await admin_session.flush()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r_ops_eng = await ac.get("/api/v1/gestio/operaris", headers=tenant["headers_eng"])
        assert r_ops_eng.status_code == 200, r_ops_eng.text
        ops_eng = r_ops_eng.json()
        assert len(ops_eng) == 1
        assert ops_eng[0]["latitud"] is None
        assert ops_eng[0]["longitud"] is None
        assert ops_eng[0]["cost_hora_eur"] is None

        r_ops_boss = await ac.get("/api/v1/gestio/operaris", headers=tenant["headers_boss"])
        assert r_ops_boss.status_code == 200
        assert r_ops_boss.json()[0]["cost_hora_eur"] == 24.5

        r_met = await ac.get("/api/v1/gestio/operaris/metrics", headers=tenant["headers_boss"])
        assert r_met.status_code == 200
        assert r_met.json()["km_conduits_mes"] == 42


@pytest.mark.asyncio
async def test_07_comptabilitat_periode_wip_rectificativa_i_planols_cascade(admin_session, tmp_path):
    tenant = await _seed_empresa_bloc5(admin_session, tmp_path / "disc_cmp")
    cli = Client(
        id=uuid.uuid4(),
        empresa_id=tenant["empresa_id"],
        codi="CL-CMP",
        rao_social="Finques Urgell S.L.",
        nif="B66778899",
    )
    admin_session.add(cli)
    await admin_session.flush()

    # Factura d'un any anterior vs factura del mes actual -> filtre periode ha de discriminar
    f_old = FacturaCapcalera(
        id=uuid.uuid4(),
        empresa_id=tenant["empresa_id"],
        client_id=cli.id,
        serie="F",
        numero_factura=1,
        hash_sha256="a" * 64,
        hash_anterior="GENESIS",
        data_emissio=datetime(2024, 6, 15, tzinfo=timezone.utc),
        estat_document="EMESA",
        base_imposable=1000.0,
        quota_iva=210.0,
        liquid_exigible=1210.0,
    )
    f_now = FacturaCapcalera(
        id=uuid.uuid4(),
        empresa_id=tenant["empresa_id"],
        client_id=cli.id,
        serie="F",
        numero_factura=2,
        hash_sha256="b" * 64,
        hash_anterior="a" * 64,
        data_emissio=datetime.now(timezone.utc),
        estat_document="EMESA",
        base_imposable=250.0,
        quota_iva=52.5,
        liquid_exigible=302.5,
    )
    ot_wip = OrdreTreball(
        id=uuid.uuid4(),
        empresa_id=tenant["empresa_id"],
        codi="OT-WIP-01",
        client_id=cli.id,
        titol="Instal·lació sector A",
        adreca="Partida Rufea 12, Lleida",
        vertical="CAMPOPRO",
        estat="ALBARA_SIGNAT",
        hores_imputades_facturables=2.0,
        preu_venda_hora_aplicat=50.0,
        pvp_materials_aplicat=100.0,
    )
    admin_session.add_all([f_old, f_now, ot_wip])
    await admin_session.flush()

    # Plànols amb fills i capes vectorials per validar esborrat en cascada sense HTTP 500
    carpeta_root = CarpetaPlanol(
        id=uuid.uuid4(),
        empresa_id=tenant["empresa_id"],
        nom="Sector Nord",
        categoria="CLIENTS",
    )
    admin_session.add(carpeta_root)
    await admin_session.flush()
    carpeta_fill = CarpetaPlanol(
        id=uuid.uuid4(),
        empresa_id=tenant["empresa_id"],
        nom="Subcarpeta Finca",
        categoria="FINQUES",
        parent_id=carpeta_root.id,
    )
    admin_session.add(carpeta_fill)
    await admin_session.flush()
    planol = PlanolBase(
        id=uuid.uuid4(),
        empresa_id=tenant["empresa_id"],
        carpeta_id=carpeta_fill.id,
        titol="Plànol Hidràulic",
        codi_referencia="PL-001",
        tipus_fitxer="PDF",
        fitxer_path="planols/pl001.pdf",
        mida_bytes=1234,
    )
    admin_session.add(planol)
    await admin_session.flush()
    capa = CapaVectorial(
        id=uuid.uuid4(),
        empresa_id=tenant["empresa_id"],
        planol_base_id=planol.id,
        nom="Canonades PE100",
        disciplina="REG",
    )
    admin_session.add(capa)
    await admin_session.flush()
    pin = PinIncidenciaPlanol(
        id=uuid.uuid4(),
        empresa_id=tenant["empresa_id"],
        capa_id=capa.id,
        latitud=41.61,
        longitud=0.62,
        titol="Fuit d'aigua",
    )
    exp = ExportacioPdfPlanol(
        id=uuid.uuid4(),
        empresa_id=tenant["empresa_id"],
        planol_base_id=planol.id,
        titol_report="Informe",
        capes_incloses_ids=[capa.id],
    )
    admin_session.add_all([pin, exp])
    await admin_session.flush()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r_dash_mes = await ac.get(
            "/api/v1/gestio/comptabilitat/dashboard-economic?periode=MES_ACTUAL",
            headers=tenant["headers_boss"],
        )
        assert r_dash_mes.status_code == 200
        assert float(r_dash_mes.json()["facturacio_neta"]) == 250.0

        r_dash_all = await ac.get(
            "/api/v1/gestio/comptabilitat/dashboard-economic",
            headers=tenant["headers_boss"],
        )
        assert r_dash_all.status_code == 200
        assert float(r_dash_all.json()["facturacio_neta"]) == 1250.0

        # WIP -> Pre-factura 1 clic
        r_wip_pre = await ac.post(
            f"/api/v1/gestio/comptabilitat/wip-control/{ot_wip.id}/prefacturar",
            headers=tenant["headers_boss"],
        )
        assert r_wip_pre.status_code == 201, r_wip_pre.text
        assert r_wip_pre.json()["serie"] == "PRE"

        # Rectificativa Sèrie R
        r_rect = await ac.post(
            f"/api/v1/gestio/comptabilitat/factures/{f_now.id}/rectificar",
            json={"motiu": "Error en base imposable"},
            headers=tenant["headers_boss"],
        )
        assert r_rect.status_code == 201, r_rect.text
        assert r_rect.json()["serie"] == "R"

        # Esborrat de carpeta Plànols amb fills -> 204
        r_del_carp = await ac.delete(
            f"/api/v1/gestio/planols/carpetes/{carpeta_root.id}",
            headers=tenant["headers_eng"],
        )
        assert r_del_carp.status_code == 204, r_del_carp.text


@pytest.mark.asyncio
async def test_08_configuracio_telegram_barema_i_notificacions_redis_dispatch(
    admin_session, tmp_path, monkeypatch
):
    tenant_a = await _seed_empresa_bloc5(admin_session, tmp_path / "disc_na")
    tenant_b = await _seed_empresa_bloc5(admin_session, tmp_path / "disc_nb")

    cli_tg = Client(
        id=uuid.uuid4(),
        empresa_id=tenant_a["empresa_id"],
        codi="CL-TG",
        rao_social="Client Canal Telegram S.L.",
        nif="B33221100",
        telegram_chat_id=987654321,
    )
    admin_session.add(cli_tg)
    await admin_session.flush()

    dispatched: list[tuple[uuid.UUID, int, str]] = []

    async def _capture_tg(empresa_id: uuid.UUID, chat_id: int, text_msg: str, **kwargs):
        dispatched.append((empresa_id, chat_id, text_msg))
        return True

    monkeypatch.setattr(notis_mod, "send_telegram_direct_message", _capture_tg)
    assert not hasattr(notis_mod, "TOKENS_FACTURA")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Configuració GET /telegram i Barema RBAC
        r_tg = await ac.get(
            "/api/v1/gestio/configuracio/telegram", headers=tenant_a["headers_boss"]
        )
        assert r_tg.status_code == 200
        assert "estat" in r_tg.json()

        r_bar_eng = await ac.get(
            "/api/v1/gestio/configuracio/barema", headers=tenant_a["headers_eng"]
        )
        assert r_bar_eng.status_code == 403

        r_bar_put = await ac.put(
            "/api/v1/gestio/configuracio/barema",
            json={
                "preu_hora_standard_eur": 52.0,
                "tarifa_urgencia_eur": 80.0,
                "suplement_desplacament_eur": 30.0,
                "marge_materials_defecte_pct": 28.0,
                "partides": [
                    {
                        "codi": "REG-01",
                        "descripcio": "Electrovàlvula 2 polzades",
                        "unitat": "u",
                        "preu_eur": 95.0,
                    }
                ],
            },
            headers=tenant_a["headers_boss"],
        )
        assert r_bar_put.status_code == 200
        r_bar_get = await ac.get(
            "/api/v1/gestio/configuracio/barema", headers=tenant_a["headers_boss"]
        )
        assert r_bar_get.status_code == 200
        assert r_bar_get.json()["preu_hora_standard_eur"] == 52.0
        assert len(r_bar_get.json()["partides"]) == 1

        # Notificacions: client_nom, invitació sense campopro_bot, missatge dispara Telegram, token Redis
        r_conv = await ac.post(
            "/api/v1/gestio/notificacions/converses",
            json={"client_id": str(cli_tg.id), "titol": "Avís muntatge"},
            headers=tenant_a["headers_boss"],
        )
        assert r_conv.status_code == 201, r_conv.text
        conv = r_conv.json()
        assert conv["client_nom"] == "Client Canal Telegram S.L."
        assert conv["client_te_telegram"] is True

        r_inv = await ac.post(
            f"/api/v1/gestio/notificacions/converses/{conv['id']}/invitar-telegram",
            headers=tenant_a["headers_boss"],
        )
        assert r_inv.status_code == 200
        assert "campopro_bot" not in r_inv.json()["enllac_profund"]

        r_msg = await ac.post(
            f"/api/v1/gestio/notificacions/converses/{conv['id']}/missatges",
            json={"contingut_text": "Demà passem a les 09:00h", "tipus_esdeveniment": "MISSATGE_MANUAL"},
            headers=tenant_a["headers_boss"],
        )
        assert r_msg.status_code == 201
        msg_json = r_msg.json()
        assert msg_json["remitent_tipus"] == "OFICINA"
        assert msg_json["tipus_esdeveniment"] == "MISSATGE_MANUAL"
        assert len(dispatched) == 1
        assert dispatched[0][1] == 987654321

        # Token factura a Redis (A pot validar, B bloquejat 403)
        fact_dummy_id = str(uuid.uuid4())
        r_tok = await ac.get(
            f"/api/v1/gestio/notificacions/converses/{conv['id']}/enllac-factura?factura_id={fact_dummy_id}",
            headers=tenant_a["headers_boss"],
        )
        assert r_tok.status_code == 200, r_tok.text
        tok = r_tok.json()["token"]

        r_val_a = await ac.get(
            f"/api/v1/gestio/notificacions/descarregar-factura?token={tok}",
            headers=tenant_a["headers_boss"],
        )
        assert r_val_a.status_code == 200
        assert r_val_a.json()["factura_id"] == fact_dummy_id

        r_val_b = await ac.get(
            f"/api/v1/gestio/notificacions/descarregar-factura?token={tok}",
            headers=tenant_b["headers_boss"],
        )
        assert r_val_b.status_code == 403
