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
from app.models.models import (
    Article,
    Client,
    DespesaComptable,
    DespesaFixaRecurrent,
    Empresa,
    EstocMagatzem,
    Magatzem,
    MantenimentVehicle,
    OrdreTreball,
    OrdreTreballTramTemps,
    TiquetDespesa,
    Usuari,
    Vehicle,
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
async def setup_fase3_tenant(admin_session):
    emp_id = uuid.uuid4()
    cli_id = uuid.uuid4()
    boss_id = uuid.uuid4()
    op_id = uuid.uuid4()
    mag_id = uuid.uuid4()
    tag = str(uuid.uuid4())[:6]

    admin_session.add(
        Empresa(
            id=emp_id,
            nom=f"Fase3 Tenant {tag}",
            nif=f"B3A{tag}",
            subdomini=f"f3-{tag}",
            pla_subscripcio="PRO",
            estat_pagament="ACTIU",
        )
    )
    await admin_session.flush()

    admin_session.add_all(
        [
            Usuari(
                id=boss_id,
                empresa_id=emp_id,
                nif=f"B3-{tag}",
                nom="Boss F3",
                rol="BOSS",
                email=f"b3-{tag}@test.local",
                telefon=f"+34630{tag}",
                password_hash="x",
                es_alta_direccio=True,
                salari_mensual_brut=0.0,
                cost_ss_mensual=0.0,
            ),
            Usuari(
                id=op_id,
                empresa_id=emp_id,
                nif=f"O3-{tag}",
                nom="Operari F3",
                rol="OPERARI",
                cost_hora_eur=Decimal("30.00"),
                salari_mensual_brut=0.0,
                cost_ss_mensual=0.0,
                telefon=f"+34631{tag}",
            ),
            Client(
                id=cli_id,
                empresa_id=emp_id,
                codi=f"CL3-{tag}",
                rao_social="Client Fase3 SL",
                nif="B44444444",
            ),
            Magatzem(
                id=mag_id,
                empresa_id=emp_id,
                nom="Nau Principal F3",
                tipus="NAU_CENTRAL",
            ),
        ]
    )
    await admin_session.flush()

    return {
        "emp": emp_id,
        "cli": cli_id,
        "boss": boss_id,
        "op": op_id,
        "mag": mag_id,
        "tag": tag,
        "h_boss": _make_headers(emp_id, boss_id, "BOSS"),
    }


@pytest.mark.asyncio
async def test_t3_1_invariant_waterfall_flota_i_mermes(setup_fase3_tenant, admin_session):
    d = setup_fase3_tenant
    avui = date.today()
    ara = datetime.now(timezone.utc)

    await admin_session.execute(text(f"SET LOCAL app.current_empresa_id = '{d['emp']}';"))
    await admin_session.execute(text("SET LOCAL app.current_user_role = 'BOSS';"))

    # Vehicle amb quota mensual 300€ + manteniment taller real 200€ (total flota 500€) + 1000 km a OT
    veh_id = uuid.uuid4()
    admin_session.add(
        Vehicle(
            id=veh_id,
            empresa_id=d["emp"],
            matricula=f"99{d['tag'][:4].upper()}",
            marca="Ford",
            model="Transit",
            quota_mensual_eur=300.00,
            odometre_acumulat=50000,
            km_inicials_mes=0,
        )
    )
    await admin_session.flush()
    admin_session.add(
        MantenimentVehicle(
            empresa_id=d["emp"],
            vehicle_id=veh_id,
            data_manteniment=ara,
            tipus="CORRECTIU",
            descripcio="Canvi frens",
            cost_euros=200.00,
        )
    )
    # OT amb 1000 km i 5h (5 * 30 = 150€ mà d'obra)
    admin_session.add(
        OrdreTreball(
            empresa_id=d["emp"],
            codi=f"OT-F31-{d['tag']}",
            client_id=d["cli"],
            cap_de_colla_id=d["op"],
            titol="Obra Flota",
            adreca="Finca Est",
            estat="COMPLETADA",
            data_planificacio=avui,
            hores_imputades_facturables=5.0,
            km_imputats=1000,
        )
    )
    # Tiquet 100€
    admin_session.add(
        TiquetDespesa(
            empresa_id=d["emp"],
            categoria="COMBUSTIBLE",
            usuari_id=d["op"],
            vehicle_id=veh_id,
            data_tiquet=avui,
            base_imposable=82.64,
            iva_pct=21.0,
            quota_iva=17.36,
            import_total=100.00,
            estat_aprovacio="APROVAT",
            estat_fiscal="DEDUIBLE",
        )
    )
    # Merma consolidada a DespesaComptable 80€
    admin_session.add(
        DespesaComptable(
            empresa_id=d["emp"],
            concepte="Merma tub PE",
            subcompte="600.MERMA_OBRA",
            base_imposable=80.00,
            quota_iva=0.00,
            import_total=80.00,
            estat="CONSOLIDADA",
            origen="MAGATZEM_MERMA",
        )
    )
    # Despesa fixa 400€
    admin_session.add(
        DespesaFixaRecurrent(
            empresa_id=d["emp"],
            concepte="Lloguer nau",
            categoria="LLOGUER",
            import_base=400.00,
            quota_iva=84.00,
            periodicitat="MENSUAL",
            actiu=True,
        )
    )
    await admin_session.flush()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res_f = await ac.post(
            "/api/v1/gestio/comptabilitat/factures/emetre",
            json={
                "client_id": str(d["cli"]),
                "serie": "F",
                "data_emissio": avui.isoformat(),
                "data_venciment": avui.isoformat(),
                "linies": [
                    {
                        "concepte": "Instal·lació completa",
                        "quantitat": 1,
                        "preu_venda_unitari": 2000.00,
                        "tipus_iva_pct": 21.00,
                    }
                ],
            },
            headers=d["h_boss"],
        )
        assert res_f.status_code == 201, res_f.text

        res_dash = await ac.get(
            "/api/v1/gestio/comptabilitat/dashboard-economic",
            headers=d["h_boss"],
        )
        assert res_dash.status_code == 200
        dash = res_dash.json()

        # Cost flota: 300 quota + 200 taller = 500 EUR / 1000 km = 0.50 EUR/km
        assert Decimal(str(dash["cost_flota_eur_km_mitja"])) == Decimal("0.50")
        # Despeses fixes NO dupliquen flota: exactament 400.00 EUR
        assert Decimal(str(dash["despeses_fixes_estructura"])) == Decimal("400.00")

        wf = {k: Decimal(str(v)) for k, v in dash["waterfall_mensual"].items()}
        assert wf["facturacio_bruta"] == Decimal("2000.00")
        assert wf["cost_materials_i_merma"] == Decimal("-80.00")
        assert wf["cost_ma_obra_directa"] == Decimal("-150.00")
        assert wf["cost_tiquets_i_flota"] == Decimal("-600.00")  # 100 tiquet + 500 flota
        assert wf["despeses_fixes"] == Decimal("-400.00")

        suma_wf = (
            wf["facturacio_bruta"]
            + wf["cost_materials_i_merma"]
            + wf["cost_ma_obra_directa"]
            + wf["cost_tiquets_i_flota"]
            + wf["despeses_fixes"]
        )
        assert suma_wf == wf["benefici_net_ebitda"]
        assert suma_wf == Decimal(str(dash["ebitda_operatiu_eur"]))
        assert suma_wf == Decimal("770.00")


@pytest.mark.asyncio
async def test_t3_2_evolucio_12m_mesos_calendari_exactes_i_despeses_reals(
    setup_fase3_tenant, admin_session
):
    d = setup_fase3_tenant
    avui = date.today()
    # Mes fa 2 mesos exactes
    total_m = avui.year * 12 + (avui.month - 1) - 2
    y_old, m_old = total_m // 12, (total_m % 12) + 1
    data_old = date(y_old, m_old, 15)
    label_old = f"{y_old:04d}-{m_old:02d}"
    label_now = avui.strftime("%Y-%m")

    await admin_session.execute(text(f"SET LOCAL app.current_empresa_id = '{d['emp']}';"))
    await admin_session.execute(text("SET LOCAL app.current_user_role = 'BOSS';"))
    admin_session.add(
        TiquetDespesa(
            empresa_id=d["emp"],
            categoria="DIETES",
            usuari_id=d["op"],
            data_tiquet=data_old,
            base_imposable=200.00,
            iva_pct=0.0,
            quota_iva=0.0,
            import_total=200.00,
            estat_aprovacio="APROVAT",
            estat_fiscal="DEDUIBLE",
        )
    )
    await admin_session.flush()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Factura fa 2 mesos (1000 EUR)
        res_f1 = await ac.post(
            "/api/v1/gestio/comptabilitat/factures/emetre",
            json={
                "client_id": str(d["cli"]),
                "serie": "F",
                "data_emissio": data_old.isoformat(),
                "data_venciment": data_old.isoformat(),
                "linies": [
                    {
                        "concepte": "Feina històrica",
                        "quantitat": 1,
                        "preu_venda_unitari": 1000.00,
                        "tipus_iva_pct": 21.00,
                    }
                ],
            },
            headers=d["h_boss"],
        )
        assert res_f1.status_code == 201, res_f1.text

        res_dash = await ac.get(
            "/api/v1/gestio/comptabilitat/dashboard-economic",
            headers=d["h_boss"],
        )
        assert res_dash.status_code == 200
        serie = res_dash.json()["evolucio_12m"]
        assert len(serie) == 12
        mesos = [item["mes"] for item in serie]
        assert len(set(mesos)) == 12  # Sense duplicats
        assert mesos[-1] == label_now

        # Comprovar consecutivitat exacta mes a mes
        for idx in range(1, len(mesos)):
            y1, m1 = map(int, mesos[idx - 1].split("-"))
            y2, m2 = map(int, mesos[idx].split("-"))
            assert (y2 * 12 + m2) - (y1 * 12 + m1) == 1

        row_old = next(r for r in serie if r["mes"] == label_old)
        assert row_old["ingressos"] == 1000.0
        assert row_old["despeses"] == 200.0
        assert row_old["ebitda_pct"] == 80.0

        # Mes sense activitat ha de tenir 0.0 i 0.0 (Zero Mock)
        row_empty = serie[0]
        assert row_empty["mes"] != label_old
        assert row_empty["ingressos"] == 0.0
        assert row_empty["despeses"] == 0.0


@pytest.mark.asyncio
async def test_t3_3_capital_immobilitzat_real_estoc_fisic_i_sortida(
    setup_fase3_tenant, admin_session
):
    d = setup_fase3_tenant
    fa_120_dies = datetime.now(timezone.utc) - timedelta(days=120)

    await admin_session.execute(text(f"SET LOCAL app.current_empresa_id = '{d['emp']}';"))
    await admin_session.execute(text("SET LOCAL app.current_user_role = 'BOSS';"))

    # Article 1: creat fa 120d amb estoc_optim=100 però estoc físic=0 -> ha de computar 0.00 EUR
    art_buit_id = uuid.uuid4()
    admin_session.add(
        Article(
            id=art_buit_id,
            empresa_id=d["emp"],
            referencia_inventari=f"ART-BUIT-{d['tag']}",
            nom="Article sense estoc real",
            preu_cost=50.00,
            preu_cost_mitja=50.00,
            pmp_actual=50.00,
            preu_venda=90.00,
            estoc_optim=100.0,
            estoc_total_actual=0.0,
            created_at=fa_120_dies,
        )
    )
    # Article 2: creat fa 120d amb estoc físic=10 i PMP=15€ -> ha de computar 150.00 EUR
    art_real_id = uuid.uuid4()
    admin_session.add(
        Article(
            id=art_real_id,
            empresa_id=d["emp"],
            referencia_inventari=f"ART-IMMOB-{d['tag']}",
            nom="Vàlvula immobilitzada",
            preu_cost=15.00,
            preu_cost_mitja=15.00,
            pmp_actual=15.00,
            preu_venda=35.00,
            estoc_optim=50.0,
            estoc_total_actual=10.0,
            created_at=fa_120_dies,
        )
    )
    await admin_session.flush()
    admin_session.add(
        EstocMagatzem(
            empresa_id=d["emp"],
            article_id=art_real_id,
            magatzem_id=d["mag"],
            quantitat_fisica=10.0,
            quantitat_virtual_reservada=0.0,
        )
    )
    await admin_session.flush()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res_before = await ac.get(
            "/api/v1/gestio/comptabilitat/dashboard-economic",
            headers=d["h_boss"],
        )
        assert res_before.status_code == 200
        assert Decimal(str(res_before.json()["capital_immobilitzat_90d_eur"])) == Decimal("150.00")

        # Registrem una SORTIDA real de 1 unitat -> actualitza darrer_moviment_sortida = avui
        res_sort = await ac.post(
            f"/api/v1/gestio/magatzem/magatzems/{d['mag']}/moviment",
            json={
                "article_id": str(art_real_id),
                "tipus": "SORTIDA",
                "quantitat": 1.0,
                "notes": "Consum obra test T3.3",
            },
            headers=d["h_boss"],
        )
        assert res_sort.status_code in (200, 201), res_sort.text

        res_after = await ac.get(
            "/api/v1/gestio/comptabilitat/dashboard-economic",
            headers=d["h_boss"],
        )
        assert res_after.status_code == 200
        assert Decimal(str(res_after.json()["capital_immobilitzat_90d_eur"])) == Decimal("0.00")


@pytest.mark.asyncio
async def test_t3_4_marges_vertical_i_economia_rendibilitat(setup_fase3_tenant, admin_session):
    d = setup_fase3_tenant
    avui = date.today()
    ara = datetime.now(timezone.utc)

    await admin_session.execute(text(f"SET LOCAL app.current_empresa_id = '{d['emp']}';"))
    await admin_session.execute(text("SET LOCAL app.current_user_role = 'BOSS';"))

    ot_id = uuid.uuid4()
    admin_session.add(
        OrdreTreball(
            id=ot_id,
            empresa_id=d["emp"],
            codi=f"OT-T34-{d['tag']}",
            client_id=d["cli"],
            cap_de_colla_id=d["op"],
            titol="Muntatge reg electrònic",
            adreca="Finca Nord",
            vertical="CAMPOPRO",
            estat="COMPLETADA",
            data_planificacio=avui,
            cost_materials_pmp=100.00,
            cost_materials_picking_pmp=100.00,
        )
    )
    await admin_session.flush()
    # 4h de treball real a 30€/h = 120€ de mà d'obra
    admin_session.add(
        OrdreTreballTramTemps(
            empresa_id=d["emp"],
            ordre_treball_id=ot_id,
            operari_id=d["op"],
            hora_inici=ara - timedelta(hours=4),
            hora_fi=ara,
            durada_segons=4 * 3600,
        )
    )
    await admin_session.flush()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Facturem 500€ vinculats a aquesta obra
        res_f = await ac.post(
            "/api/v1/gestio/comptabilitat/factures/emetre",
            json={
                "client_id": str(d["cli"]),
                "serie": "F",
                "data_emissio": avui.isoformat(),
                "data_venciment": avui.isoformat(),
                "linies": [
                    {
                        "obra_id": str(ot_id),
                        "concepte": "Servei reg",
                        "quantitat": 1,
                        "preu_venda_unitari": 500.00,
                        "tipus_iva_pct": 21.00,
                    }
                ],
            },
            headers=d["h_boss"],
        )
        assert res_f.status_code == 201, res_f.text

        # 1) Marges per vertical al Dashboard Econòmic: 500 - (100 mat + 120 mà d'obra) = 280.00 EUR
        res_dash = await ac.get(
            "/api/v1/gestio/comptabilitat/dashboard-economic",
            headers=d["h_boss"],
        )
        assert res_dash.status_code == 200
        verticals = res_dash.json()["marges_per_vertical"]
        v_campo = next(v for v in verticals if v["vertical"] == "CAMPOPRO")
        assert Decimal(str(v_campo["marge_eur"])) == Decimal("280.00")

        # 2) Router legacy /gestio/economia/rendibilitat alineat sense zeros hardcodejats
        res_eco = await ac.get("/api/v1/gestio/economia/rendibilitat", headers=d["h_boss"])
        assert res_eco.status_code == 200
        eco_row = next(r for r in res_eco.json() if r["ordre_treball_id"] == str(ot_id))
        assert eco_row["hores_treballades"] == 4.0
        assert eco_row["cost_operari"] == 120.0
        assert eco_row["cost_materials"] == 100.0
        assert eco_row["import_facturat"] == 500.0
        assert eco_row["marge_brut"] == 280.0
