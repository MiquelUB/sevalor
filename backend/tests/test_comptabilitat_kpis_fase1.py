import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import jwt
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.core.config import settings
from app.main import app
from app.models.contractes import RevisionsContracte
from app.models.models import Client, Empresa, OrdreTreball, Usuari


def _make_headers(empresa_id: uuid.UUID, user_id: uuid.UUID, rol: str) -> dict[str, str]:
    token = jwt.encode(
        {
            "sub": str(user_id),
            "rol": rol,
            "empresa_id": str(empresa_id),
            "exp": datetime.now(timezone.utc) + timedelta(minutes=60),
        },
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def setup_fase1_tenants(admin_session):
    emp_a_id = uuid.uuid4()
    emp_b_id = uuid.uuid4()
    cli_a_id = uuid.uuid4()
    cli_b_id = uuid.uuid4()
    boss_a_id = uuid.uuid4()
    eng_a_id = uuid.uuid4()
    boss_b_id = uuid.uuid4()
    op_a_id = uuid.uuid4()

    tag = str(uuid.uuid4())[:6]

    admin_session.add_all(
        [
            Empresa(
                id=emp_a_id,
                nom=f"Fase1 Tenant A {tag}",
                nif=f"B1A{tag}",
                subdomini=f"f1a-{tag}",
                pla_subscripcio="PRO",
                estat_pagament="ACTIU",
            ),
            Empresa(
                id=emp_b_id,
                nom=f"Fase1 Tenant B {tag}",
                nif=f"B1B{tag}",
                subdomini=f"f1b-{tag}",
                pla_subscripcio="PRO",
                estat_pagament="ACTIU",
            ),
        ]
    )
    await admin_session.flush()

    admin_session.add_all(
        [
            Usuari(
                id=boss_a_id,
                empresa_id=emp_a_id,
                nif=f"BA-{tag}",
                nom="Boss A",
                rol="BOSS",
                email=f"ba-{tag}@test.local",
                telefon=f"+34600{tag[:6]}",
                password_hash="x",
                es_alta_direccio=True,
            ),
            Usuari(
                id=eng_a_id,
                empresa_id=emp_a_id,
                nif=f"EA-{tag}",
                nom="Eng A",
                rol="ENGINYER",
                email=f"ea-{tag}@test.local",
                telefon=f"+34601{tag[:6]}",
                password_hash="x",
            ),
            Usuari(
                id=op_a_id,
                empresa_id=emp_a_id,
                nif=f"OA-{tag}",
                nom="Operari A",
                rol="OPERARI",
                cost_hora_eur=Decimal("25.00"),
                telefon=f"+34602{tag[:6]}",
            ),
            Usuari(
                id=boss_b_id,
                empresa_id=emp_b_id,
                nif=f"BB-{tag}",
                nom="Boss B",
                rol="BOSS",
                email=f"bb-{tag}@test.local",
                telefon=f"+34603{tag[:6]}",
                password_hash="x",
                es_alta_direccio=True,
            ),
            Client(
                id=cli_a_id,
                empresa_id=emp_a_id,
                codi=f"CLIA-{tag}",
                rao_social="Client Fase1 A SL",
                nif="B11111111",
            ),
            Client(
                id=cli_b_id,
                empresa_id=emp_b_id,
                codi=f"CLIB-{tag}",
                rao_social="Client Fase1 B SL",
                nif="B22222222",
            ),
        ]
    )
    await admin_session.flush()

    return {
        "emp_a": emp_a_id,
        "emp_b": emp_b_id,
        "cli_a": cli_a_id,
        "cli_b": cli_b_id,
        "boss_a": boss_a_id,
        "eng_a": eng_a_id,
        "op_a": op_a_id,
        "boss_b": boss_b_id,
        "h_boss_a": _make_headers(emp_a_id, boss_a_id, "BOSS"),
        "h_eng_a": _make_headers(emp_a_id, eng_a_id, "ENGINYER"),
        "h_boss_b": _make_headers(emp_b_id, boss_b_id, "BOSS"),
    }


@pytest.mark.asyncio
async def test_t1_1_cobrament_parcial_i_total_manual_impacte_kpis(setup_fase1_tenants):
    d = setup_fase1_tenants
    data_em = date.today() - timedelta(days=10)
    data_cob = date.today()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res_em = await ac.post(
            "/api/v1/gestio/comptabilitat/factures/emetre",
            json={
                "client_id": str(d["cli_a"]),
                "serie": "F",
                "data_emissio": data_em.isoformat(),
                "data_venciment": (data_em + timedelta(days=30)).isoformat(),
                "linies": [
                    {
                        "concepte": "Instal·lació reg goteig",
                        "quantitat": 1,
                        "preu_venda_unitari": 1000.00,
                        "tipus_iva_pct": 21.00,
                    }
                ],
            },
            headers=d["h_boss_a"],
        )
        assert res_em.status_code == 201, res_em.text
        fac_id = res_em.json()["id"]
        assert Decimal(str(res_em.json()["liquid_exigible"])) == Decimal("1210.00")

        # 1) Cobrament PARCIAL (605.00 EUR = 50%)
        res_parc = await ac.patch(
            f"/api/v1/gestio/comptabilitat/factures/{fac_id}/cobrament",
            json={
                "estat_cobrament": "PARCIAL",
                "import_cobrat": "605.00",
                "data_cobrament_real": data_cob.isoformat(),
                "notes": "Primer pagament transferència",
            },
            headers=d["h_boss_a"],
        )
        assert res_parc.status_code == 200, res_parc.text
        body_parc = res_parc.json()
        assert body_parc["estat_cobrament"] == "PARCIAL"
        assert Decimal(str(body_parc["import_cobrat"])) == Decimal("605.00")
        assert body_parc["data_cobrament_real"] == data_cob.isoformat()

        res_dash_parc = await ac.get(
            "/api/v1/gestio/comptabilitat/dashboard-economic?criteri_caixa=true",
            headers=d["h_boss_a"],
        )
        assert res_dash_parc.status_code == 200
        dash_parc = res_dash_parc.json()
        assert Decimal(str(dash_parc["cash_flow_operatiu_real"])) == Decimal("605.00")
        assert Decimal(str(dash_parc["facturacio_neta"])) == Decimal("500.00")

        # 2) Cobrament TOTAL (sense import_cobrat -> autocompleta liquid_exigible 1210.00)
        res_tot = await ac.patch(
            f"/api/v1/gestio/comptabilitat/factures/{fac_id}/cobrament",
            json={
                "estat_cobrament": "COBRADA",
                "data_cobrament_real": data_cob.isoformat(),
            },
            headers=d["h_boss_a"],
        )
        assert res_tot.status_code == 200, res_tot.text
        body_tot = res_tot.json()
        assert body_tot["estat_cobrament"] == "COBRADA"
        assert Decimal(str(body_tot["import_cobrat"])) == Decimal("1210.00")

        res_dash_tot = await ac.get(
            "/api/v1/gestio/comptabilitat/dashboard-economic?criteri_caixa=true",
            headers=d["h_boss_a"],
        )
        assert res_dash_tot.status_code == 200
        dash_tot = res_dash_tot.json()
        assert Decimal(str(dash_tot["cash_flow_operatiu_real"])) == Decimal("1210.00")
        assert Decimal(str(dash_tot["facturacio_neta"])) == Decimal("1000.00")
        assert Decimal(str(dash_tot["dso_dies_mitjana_cobrament"])) == Decimal("10.00")


@pytest.mark.asyncio
async def test_t1_2_validacions_i_seguretat_cobrament_rls(setup_fase1_tenants):
    d = setup_fase1_tenants
    avui = date.today()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1) Pre-factura en esborrany -> NO es pot cobrar (400)
        res_pre = await ac.post(
            "/api/v1/gestio/comptabilitat/prefactures",
            json={
                "client_id": str(d["cli_a"]),
                "serie": "PRE",
                "data_emissio": avui.isoformat(),
                "data_venciment": avui.isoformat(),
                "linies": [
                    {
                        "concepte": "Esborrany",
                        "quantitat": 1,
                        "preu_venda_unitari": 200.00,
                        "tipus_iva_pct": 21.00,
                    }
                ],
            },
            headers=d["h_boss_a"],
        )
        assert res_pre.status_code == 201, res_pre.text
        pre_id = res_pre.json()["id"]

        res_cob_pre = await ac.patch(
            f"/api/v1/gestio/comptabilitat/factures/{pre_id}/cobrament",
            json={"estat_cobrament": "COBRADA"},
            headers=d["h_boss_a"],
        )
        assert res_cob_pre.status_code == 400

        # 2) Factura emesa -> Veto ENGINYER (403) i Aïllament RLS Tenant B (404)
        res_em = await ac.post(
            "/api/v1/gestio/comptabilitat/factures/emetre",
            json={
                "client_id": str(d["cli_a"]),
                "serie": "F",
                "data_emissio": avui.isoformat(),
                "data_venciment": avui.isoformat(),
                "linies": [
                    {
                        "concepte": "Servei tècnic",
                        "quantitat": 1,
                        "preu_venda_unitari": 500.00,
                        "tipus_iva_pct": 21.00,
                    }
                ],
            },
            headers=d["h_boss_a"],
        )
        assert res_em.status_code == 201
        fac_id = res_em.json()["id"]

        res_eng = await ac.patch(
            f"/api/v1/gestio/comptabilitat/factures/{fac_id}/cobrament",
            json={"estat_cobrament": "COBRADA"},
            headers=d["h_eng_a"],
        )
        assert res_eng.status_code == 403

        res_rls = await ac.patch(
            f"/api/v1/gestio/comptabilitat/factures/{fac_id}/cobrament",
            json={"estat_cobrament": "COBRADA"},
            headers=d["h_boss_b"],
        )
        assert res_rls.status_code == 404

        # 3) Import superior al líquid exigible -> 422
        res_exc = await ac.patch(
            f"/api/v1/gestio/comptabilitat/factures/{fac_id}/cobrament",
            json={"estat_cobrament": "PARCIAL", "import_cobrat": "9999.00"},
            headers=d["h_boss_a"],
        )
        assert res_exc.status_code == 422

        # 4) Factura anul·lada -> NO es pot cobrar (400)
        res_an = await ac.post(
            f"/api/v1/gestio/comptabilitat/factures/{fac_id}/anular",
            json={"motiu": "Error d'emissió test", "confirmacio_humana_hitl": True},
            headers=d["h_boss_a"],
        )
        assert res_an.status_code == 200, res_an.text

        res_cob_an = await ac.patch(
            f"/api/v1/gestio/comptabilitat/factures/{fac_id}/cobrament",
            json={"estat_cobrament": "COBRADA"},
            headers=d["h_boss_a"],
        )
        assert res_cob_an.status_code == 400


@pytest.mark.asyncio
async def test_t1_3_mrr_des_de_contractes_manteniment_reals(setup_fase1_tenants, admin_session):
    d = setup_fase1_tenants
    avui = date.today()
    tag = str(uuid.uuid4())[:6]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res_c = await ac.post(
            "/api/v1/gestio/contractes/",
            json={
                "client_id": str(d["cli_a"]),
                "numero_contracte": f"CTR-REAL-{tag}",
                "data_inici": avui.isoformat(),
                "import_anual": 12000.00,
                "periodicitat": "MENSUAL",
                "estat": "ACTIU",
            },
            headers=d["h_boss_a"],
        )
        assert res_c.status_code == 201, res_c.text
        contracte_id = uuid.UUID(res_c.json()["id"])

        # Vincular una OT real a través de revisions_contracte
        await admin_session.execute(
            text(f"SET LOCAL app.current_empresa_id = '{d['emp_a']}';")
        )
        await admin_session.execute(text("SET LOCAL app.current_user_role = 'BOSS';"))
        ot_id = uuid.uuid4()
        admin_session.add(
            OrdreTreball(
                id=ot_id,
                empresa_id=d["emp_a"],
                codi=f"OT-CTR-{tag}",
                client_id=d["cli_a"],
                cap_de_colla_id=d["op_a"],
                titol="Revisió contracte real",
                adreca="Finca Sud",
                estat="COMPLETADA",
                hores_imputades_facturables=10.0,
                cost_materials_pmp=150.00,
                km_imputats=100,
            )
        )
        await admin_session.flush()
        admin_session.add(
            RevisionsContracte(
                empresa_id=d["emp_a"],
                contracte_id=contracte_id,
                ordre_treball_id=ot_id,
                data_prevista=avui,
                estat="COMPLETADA",
            )
        )
        await admin_session.flush()

        res_mrr = await ac.get(
            "/api/v1/gestio/comptabilitat/contractes-mrr-auditoria",
            headers=d["h_boss_a"],
        )
        assert res_mrr.status_code == 200
        rows = res_mrr.json()
        assert len(rows) == 1
        row = rows[0]
        assert row["codi_contracte"] == f"CTR-REAL-{tag}"
        assert Decimal(str(row["quota_mensual_mrr"])) == Decimal("1000.00")
        # 10h * 25 EUR = 250 + 150 materials + 100km * 0.32 (32) = 432.00 EUR
        assert Decimal(str(row["cost_real_ots_periode"])) == Decimal("432.00")
        assert Decimal(str(row["marge_net_contracte"])) == Decimal("568.00")
        assert row["semafor"] == "RENDIBLE"

        res_dash = await ac.get(
            "/api/v1/gestio/comptabilitat/dashboard-economic",
            headers=d["h_boss_a"],
        )
        assert res_dash.status_code == 200
        assert Decimal(str(res_dash.json()["mrr_mensual_actiu"])) == Decimal("1000.00")

        # Tenant B no veu el contracte de Tenant A
        res_mrr_b = await ac.get(
            "/api/v1/gestio/comptabilitat/contractes-mrr-auditoria",
            headers=d["h_boss_b"],
        )
        assert res_mrr_b.status_code == 200
        assert res_mrr_b.json() == []


@pytest.mark.asyncio
async def test_t1_4_exclusio_factures_anulades_dashboard_i_risc(setup_fase1_tenants):
    d = setup_fase1_tenants
    avui = date.today()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res_em = await ac.post(
            "/api/v1/gestio/comptabilitat/factures/emetre",
            json={
                "client_id": str(d["cli_a"]),
                "serie": "F",
                "data_emissio": avui.isoformat(),
                "data_venciment": avui.isoformat(),
                "linies": [
                    {
                        "concepte": "Equip bombament",
                        "quantitat": 1,
                        "preu_venda_unitari": 1000.00,
                        "tipus_iva_pct": 21.00,
                    }
                ],
            },
            headers=d["h_boss_a"],
        )
        assert res_em.status_code == 201
        fac_id = res_em.json()["id"]

        res_before = await ac.get(
            "/api/v1/gestio/comptabilitat/dashboard-economic",
            headers=d["h_boss_a"],
        )
        assert Decimal(str(res_before.json()["facturacio_neta"])) == Decimal("1000.00")
        assert Decimal(str(res_before.json()["guardacaixa_fiscal_iva_303"])) == Decimal("210.00")

        res_an = await ac.post(
            f"/api/v1/gestio/comptabilitat/factures/{fac_id}/anular",
            json={"motiu": "Duplicat abans d'enviar al client", "confirmacio_humana_hitl": True},
            headers=d["h_boss_a"],
        )
        assert res_an.status_code == 200

        res_after = await ac.get(
            "/api/v1/gestio/comptabilitat/dashboard-economic",
            headers=d["h_boss_a"],
        )
        assert res_after.status_code == 200
        dash = res_after.json()
        assert Decimal(str(dash["facturacio_neta"])) == Decimal("0.00")
        assert Decimal(str(dash["guardacaixa_fiscal_iva_303"])) == Decimal("0.00")
        for k, val in dash["aging_impagats"].items():
            assert Decimal(str(val)) == Decimal("0.00"), f"Aging {k} ha de ser 0.00"
