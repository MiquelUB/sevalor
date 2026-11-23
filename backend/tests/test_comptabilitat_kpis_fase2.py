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
from app.models.contractes import ContracteManteniment
from app.models.models import (
    Client,
    Empresa,
    OrdreTreball,
    OrdreTreballTramTemps,
    RegistreJornadaLaboral,
    Usuari,
)


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
async def setup_fase2_tenants(admin_session):
    emp_a_id = uuid.uuid4()
    emp_b_id = uuid.uuid4()
    cli_a_id = uuid.uuid4()
    boss_a_id = uuid.uuid4()
    sec_a_id = uuid.uuid4()
    eng_a_id = uuid.uuid4()
    boss_b_id = uuid.uuid4()
    tag = str(uuid.uuid4())[:6]

    admin_session.add_all(
        [
            Empresa(
                id=emp_a_id,
                nom=f"Fase2 Tenant A {tag}",
                nif=f"B2A{tag}",
                subdomini=f"f2a-{tag}",
                pla_subscripcio="PRO",
                estat_pagament="ACTIU",
            ),
            Empresa(
                id=emp_b_id,
                nom=f"Fase2 Tenant B {tag}",
                nif=f"B2B{tag}",
                subdomini=f"f2b-{tag}",
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
                nif=f"BA2-{tag}",
                nom="Boss F2",
                rol="BOSS",
                email=f"ba2-{tag}@test.local",
                telefon=f"+34610{tag}",
                password_hash="x",
                es_alta_direccio=True,
                salari_mensual_brut=0.0,
                cost_ss_mensual=0.0,
            ),
            Usuari(
                id=sec_a_id,
                empresa_id=emp_a_id,
                nif=f"SA2-{tag}",
                nom="Sec F2",
                rol="SECRETARIA",
                email=f"sa2-{tag}@test.local",
                telefon=f"+34611{tag}",
                password_hash="x",
                salari_mensual_brut=0.0,
                cost_ss_mensual=0.0,
            ),
            Usuari(
                id=eng_a_id,
                empresa_id=emp_a_id,
                nif=f"EA2-{tag}",
                nom="Eng F2",
                rol="ENGINYER",
                email=f"ea2-{tag}@test.local",
                telefon=f"+34612{tag}",
                password_hash="x",
                salari_mensual_brut=0.0,
                cost_ss_mensual=0.0,
            ),
            Usuari(
                id=boss_b_id,
                empresa_id=emp_b_id,
                nif=f"BB2-{tag}",
                nom="Boss B2",
                rol="BOSS",
                email=f"bb2-{tag}@test.local",
                telefon=f"+34613{tag}",
                password_hash="x",
                es_alta_direccio=True,
                salari_mensual_brut=0.0,
                cost_ss_mensual=0.0,
            ),
            Client(
                id=cli_a_id,
                empresa_id=emp_a_id,
                codi=f"CL2A-{tag}",
                rao_social="Client Fase2 A SL",
                nif="B33333333",
            ),
        ]
    )
    await admin_session.flush()

    return {
        "emp_a": emp_a_id,
        "emp_b": emp_b_id,
        "cli_a": cli_a_id,
        "boss_a": boss_a_id,
        "sec_a": sec_a_id,
        "eng_a": eng_a_id,
        "boss_b": boss_b_id,
        "tag": tag,
        "h_boss_a": _make_headers(emp_a_id, boss_a_id, "BOSS"),
        "h_sec_a": _make_headers(emp_a_id, sec_a_id, "SECRETARIA"),
        "h_eng_a": _make_headers(emp_a_id, eng_a_id, "ENGINYER"),
        "h_boss_b": _make_headers(emp_b_id, boss_b_id, "BOSS"),
    }


@pytest.mark.asyncio
async def test_t2_1_crud_despeses_fixes_i_impacte_kpis(setup_fase2_tenants, admin_session):
    d = setup_fase2_tenants
    avui = date.today()

    # Afegim una factura i un contracte MRR per comprovar break-even, burn-rate i cobertura MRR
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res_fac = await ac.post(
            "/api/v1/gestio/comptabilitat/factures/emetre",
            json={
                "client_id": str(d["cli_a"]),
                "serie": "F",
                "data_emissio": avui.isoformat(),
                "data_venciment": avui.isoformat(),
                "linies": [
                    {
                        "concepte": "Instal·lació hidràulica",
                        "quantitat": 1,
                        "preu_venda_unitari": 2000.00,
                        "tipus_iva_pct": 21.00,
                    }
                ],
            },
            headers=d["h_boss_a"],
        )
        assert res_fac.status_code == 201, res_fac.text

        await admin_session.execute(
            text(f"SET LOCAL app.current_empresa_id = '{d['emp_a']}';")
        )
        await admin_session.execute(text("SET LOCAL app.current_user_role = 'BOSS';"))
        admin_session.add(
            ContracteManteniment(
                empresa_id=d["emp_a"],
                client_id=d["cli_a"],
                numero_contracte=f"CTR-MRR-{d['tag']}",
                data_inici=avui,
                import_anual=6600.00,  # 550.00 EUR / mes -> 50% cobertura sobre 1100 EUR fixes
                periodicitat="MENSUAL",
                estat="ACTIU",
            )
        )
        await admin_session.flush()

        # 1) Crear lloguer mensual (1000 EUR + 210 IVA)
        res_d1 = await ac.post(
            "/api/v1/gestio/comptabilitat/despeses-fixes",
            json={
                "concepte": "Lloguer nau industrial",
                "categoria": "LLOGUER",
                "import_base": "1000.00",
                "quota_iva": "210.00",
                "periodicitat": "MENSUAL",
                "dia_carrec": 5,
            },
            headers=d["h_boss_a"],
        )
        assert res_d1.status_code == 201, res_d1.text
        d1_id = res_d1.json()["id"]
        assert Decimal(str(res_d1.json()["import_mensual_normalitzat"])) == Decimal("1000.00")

        # 2) Crear assegurança anual (1200 EUR = 100 EUR/mes, 0 IVA)
        res_d2 = await ac.post(
            "/api/v1/gestio/comptabilitat/despeses-fixes",
            json={
                "concepte": "Assegurança RC anual",
                "categoria": "ASSEGURANCES",
                "import_base": "1200.00",
                "quota_iva": "0.00",
                "periodicitat": "ANUAL",
                "dia_carrec": 10,
            },
            headers=d["h_boss_a"],
        )
        assert res_d2.status_code == 201, res_d2.text
        d2_id = res_d2.json()["id"]
        assert Decimal(str(res_d2.json()["import_mensual_normalitzat"])) == Decimal("100.00")

        # 3) Comprovar Dashboard Econòmic
        res_dash = await ac.get(
            "/api/v1/gestio/comptabilitat/dashboard-economic",
            headers=d["h_boss_a"],
        )
        assert res_dash.status_code == 200
        dash = res_dash.json()
        assert Decimal(str(dash["despeses_fixes_estructura"])) == Decimal("1100.00")
        assert Decimal(str(dash["break_even_facturacio_necessaria"])) == Decimal("1100.00")
        assert dash["break_even_assolit"] is True
        assert Decimal(str(dash["burn_rate_mes_seguent"])) == Decimal("1100.00")
        assert Decimal(str(dash["cobertura_estructura_mrr_pct"])) == Decimal("50.00")
        # IVA repercutit 420 - IVA deduïble lloguer 210 = 210.00 EUR
        assert Decimal(str(dash["guardacaixa_fiscal_iva_303"])) == Decimal("210.00")

        # 4) Actualitzar i desactivar
        res_upd = await ac.put(
            f"/api/v1/gestio/comptabilitat/despeses-fixes/{d2_id}",
            json={"import_base": "2400.00"},
            headers=d["h_boss_a"],
        )
        assert res_upd.status_code == 200
        assert Decimal(str(res_upd.json()["import_mensual_normalitzat"])) == Decimal("200.00")

        res_del = await ac.delete(
            f"/api/v1/gestio/comptabilitat/despeses-fixes/{d1_id}",
            headers=d["h_boss_a"],
        )
        assert res_del.status_code == 200
        assert res_del.json()["status"] == "DESACTIVADA"

        res_dash_after = await ac.get(
            "/api/v1/gestio/comptabilitat/dashboard-economic",
            headers=d["h_boss_a"],
        )
        assert Decimal(str(res_dash_after.json()["despeses_fixes_estructura"])) == Decimal("200.00")


@pytest.mark.asyncio
async def test_t2_2_seguretat_c05_i_rls_despeses_fixes(setup_fase2_tenants):
    d = setup_fase2_tenants
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res_post = await ac.post(
            "/api/v1/gestio/comptabilitat/despeses-fixes",
            json={
                "concepte": "Gestoria fiscal",
                "categoria": "GESTORIA",
                "import_base": "300.00",
                "quota_iva": "63.00",
                "periodicitat": "MENSUAL",
            },
            headers=d["h_boss_a"],
        )
        assert res_post.status_code == 201
        df_id = res_post.json()["id"]

        # Veto ENGINYER (403) en tots els verbs
        assert (
            await ac.get("/api/v1/gestio/comptabilitat/despeses-fixes", headers=d["h_eng_a"])
        ).status_code == 403
        assert (
            await ac.post(
                "/api/v1/gestio/comptabilitat/despeses-fixes",
                json={"concepte": "Test", "categoria": "ALTRES", "import_base": "10.00"},
                headers=d["h_eng_a"],
            )
        ).status_code == 403
        assert (
            await ac.put(
                f"/api/v1/gestio/comptabilitat/despeses-fixes/{df_id}",
                json={"import_base": "400.00"},
                headers=d["h_eng_a"],
            )
        ).status_code == 403
        assert (
            await ac.delete(
                f"/api/v1/gestio/comptabilitat/despeses-fixes/{df_id}",
                headers=d["h_eng_a"],
            )
        ).status_code == 403

        # Aïllament RLS Tenant B
        res_list_b = await ac.get(
            "/api/v1/gestio/comptabilitat/despeses-fixes", headers=d["h_boss_b"]
        )
        assert res_list_b.status_code == 200
        assert res_list_b.json() == []
        assert (
            await ac.put(
                f"/api/v1/gestio/comptabilitat/despeses-fixes/{df_id}",
                json={"import_base": "1.00"},
                headers=d["h_boss_b"],
            )
        ).status_code == 404
        assert (
            await ac.delete(
                f"/api/v1/gestio/comptabilitat/despeses-fixes/{df_id}",
                headers=d["h_boss_b"],
            )
        ).status_code == 404


@pytest.mark.asyncio
async def test_t2_3_salaris_reals_i_hores_trams_temps_operari(setup_fase2_tenants, admin_session):
    d = setup_fase2_tenants
    avui = date.today()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1) Alta d'operari via /gestio/operaris i actualització de salari + SS
        res_op = await ac.post(
            "/api/v1/gestio/operaris",
            json={
                "nif": f"OP23-{d['tag']}",
                "nom": "Marc",
                "cognoms": "Tècnic",
                "telefon": f"+34620{d['tag']}",
                "rol": "OPERARI",
                "cost_hora_eur": 24.0,
            },
            headers=d["h_boss_a"],
        )
        assert res_op.status_code == 201, res_op.text
        op_id = uuid.UUID(res_op.json()["id"])

        res_upd = await ac.put(
            f"/api/v1/gestio/operaris/{op_id}",
            json={
                "salari_mensual_brut": 2000.0,
                "cost_ss_mensual": 600.0,
            },
            headers=d["h_boss_a"],
        )
        assert res_upd.status_code == 200, res_upd.text
        assert res_upd.json()["salari_mensual_brut"] == 2000.0
        assert res_upd.json()["cost_ss_mensual"] == 600.0

        # ENGINYER no veu salaris ni cost_hora_eur (C-05)
        res_eng_get = await ac.get(f"/api/v1/gestio/operaris/{op_id}", headers=d["h_eng_a"])
        assert res_eng_get.status_code == 200
        assert res_eng_get.json()["salari_mensual_brut"] is None
        assert res_eng_get.json()["cost_ss_mensual"] is None
        assert res_eng_get.json()["cost_hora_eur"] is None

        # 2) Inserir 100h fitxades (RegistreJornadaLaboral) i 80h reals en OrdreTreballTramTemps
        await admin_session.execute(
            text(f"SET LOCAL app.current_empresa_id = '{d['emp_a']}';")
        )
        await admin_session.execute(text("SET LOCAL app.current_user_role = 'BOSS';"))
        ot_id = uuid.uuid4()
        admin_session.add(
            OrdreTreball(
                id=ot_id,
                empresa_id=d["emp_a"],
                codi=f"OT-T23-{d['tag']}",
                client_id=d["cli_a"],
                titol="Muntatge quadre elèctric",
                adreca="Polígon Nord",
                estat="COMPLETADA",
            )
        )
        await admin_session.flush()
        admin_session.add(
            RegistreJornadaLaboral(
                empresa_id=d["emp_a"],
                usuari_id=op_id,
                data_jornada=avui,
                hores_ordinaries=100.0,
                hores_extraordinaries=0.0,
                hores_imputades_ot=0.0,
                estat="TANCADA",
            )
        )
        admin_session.add(
            OrdreTreballTramTemps(
                empresa_id=d["emp_a"],
                ordre_treball_id=ot_id,
                operari_id=op_id,
                hora_inici=datetime.now(timezone.utc) - timedelta(hours=80),
                hora_fi=datetime.now(timezone.utc),
                durada_segons=80 * 3600,
            )
        )
        await admin_session.flush()

        # 3) Comprovar GET /operaris-cost-efectiu
        res_ce = await ac.get(
            "/api/v1/gestio/comptabilitat/operaris-cost-efectiu",
            headers=d["h_boss_a"],
        )
        assert res_ce.status_code == 200
        op_row = next(r for r in res_ce.json() if r["usuari_id"] == str(op_id))
        assert Decimal(str(op_row["hores_fitxades_mes"])) == Decimal("100.00")
        assert Decimal(str(op_row["hores_imputades_ot_mes"])) == Decimal("80.00")
        assert Decimal(str(op_row["ratio_eficiencia_pct"])) == Decimal("80.00")
        assert Decimal(str(op_row["cost_hora_efectiu_mensual"])) == Decimal("32.50")
        assert op_row["alerta_improductivitat"] is False


@pytest.mark.asyncio
async def test_t2_4_fallback_honest_cost_hora_sense_nomina_mensual(setup_fase2_tenants, admin_session):
    d = setup_fase2_tenants
    avui = date.today()

    await admin_session.execute(
        text(f"SET LOCAL app.current_empresa_id = '{d['emp_a']}';")
    )
    await admin_session.execute(text("SET LOCAL app.current_user_role = 'BOSS';"))

    op_id = uuid.uuid4()
    ot_id = uuid.uuid4()
    admin_session.add(
        Usuari(
            id=op_id,
            empresa_id=d["emp_a"],
            nif=f"OP24-{d['tag']}",
            nom="Laia Fallback",
            rol="OPERARI",
            cost_hora_eur=Decimal("25.00"),
            salari_mensual_brut=0.0,
            cost_ss_mensual=0.0,
            telefon=f"+34625{d['tag']}",
        )
    )
    await admin_session.flush()
    admin_session.add(
        OrdreTreball(
            id=ot_id,
            empresa_id=d["emp_a"],
            codi=f"OT-T24-{d['tag']}",
            client_id=d["cli_a"],
            cap_de_colla_id=op_id,
            titol="Revisió bombes",
            adreca="Finca Oest",
            estat="COMPLETADA",
            data_planificacio=avui,
            hores_imputades_facturables=10.0,
        )
    )
    await admin_session.flush()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res_dash = await ac.get(
            "/api/v1/gestio/comptabilitat/dashboard-economic",
            headers=d["h_boss_a"],
        )
        assert res_dash.status_code == 200
        dash = res_dash.json()
        # 10h * 25.00 EUR/h = 250.00 EUR de cost directe d'obra real
        assert Decimal(str(dash["cost_directe_obra"])) == Decimal("250.00")
