import uuid
from datetime import date, datetime, timedelta, timezone

import jwt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.main import app
from app.models.models import Empresa, MantenimentVehicle, TiquetCombustible, Usuari, Vehicle


@pytest.mark.asyncio
async def test_renting_odometre_inici_contracte(
    admin_session: AsyncSession, headers: dict, boss_token: tuple
):
    """Verifica el càlcul d'odòmetre net quan un vehicle s'incorpora al contracte amb km previs

    (odometre_inici_contracte = 40000, odometre_acumulat = 49000, renting_limit_km = 10000 => 9000 km = 90.0%).
    """
    token, empresa_id = boss_token
    boss_nif = "B" + str(uuid.uuid4())[:8].upper()

    admin_session.add(
        Empresa(
            id=uuid.UUID(empresa_id),
            nom="Test Renting Odo Inici",
            nif=boss_nif,
            subdomini="testodo-" + str(uuid.uuid4())[:5],
            pla_subscripcio="ENTERPRISE",
            estat_pagament="ACTIU",
        )
    )
    await admin_session.flush()

    avui = date.today()
    payload = {
        "matricula": "1090AVS",
        "marca": "Peugeot",
        "model": "Partner",
        "tipus": "DIESEL",
        "distintiu_ambiental": "C",
        "estat": "OPERATIU",
        "regim_adquisicio": "RENTING",
        "renting_limit_km": 10000,
        "odometre_inici_contracte": 40000,
        "odometre_acumulat": 49000,
        "data_inici_contracte": (avui - timedelta(days=300)).isoformat(),
        "data_fi_contracte": (avui + timedelta(days=65)).isoformat(),
        "quota_mensual_eur": 450.00,
        "preu_km_exces_eur": 0.08,
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/api/v1/gestio/flota", json=payload, headers=headers)
        assert res.status_code == 201, f"Expected 201, got {res.status_code}: {res.text}"
        data = res.json()

        assert data["km_recorreguts_contracte"] == 9000
        assert data["renting_ocupacio_percent"] == 90.0
        assert data["renting_alerta"] is True
        assert data["renting_nivell_alerta"] == "90%"
        assert data["alerta_renting_km"] == "AVIS_90"
        assert data["cost_penalitzacio_km_eur"] == 0.0


@pytest.mark.asyncio
async def test_diferencia_renting_leasing_lloguer_tco(
    admin_session: AsyncSession, headers: dict, boss_token: tuple
):
    """Comprova la diferenciació financera real del TCO entre RENTING, LEASING i LLOGUER

    amb registres reals de MantenimentVehicle (500 €) i TiquetCombustible (200 €):
    - En LEASING: el manteniment (500 €) s'imputa al TCO i retorna valor_residual_eur.
    - En RENTING: el manteniment ordinari (500 €) NO penalitza el TCO (cobert per quota) i es calcula l'excés de km.
    - En LLOGUER: es multiplica tarifa_diaria_eur pels dies transcorreguts, manteniment cobert i alerta si dies_restants <= 3.
    """
    token, empresa_id = boss_token
    emp_uuid = uuid.UUID(empresa_id)
    boss_nif = "B" + str(uuid.uuid4())[:8].upper()

    admin_session.add(
        Empresa(
            id=emp_uuid,
            nom="Test TCO Regims",
            nif=boss_nif,
            subdomini="testtco-" + str(uuid.uuid4())[:5],
            pla_subscripcio="PRO",
            estat_pagament="ACTIU",
        )
    )
    conductor_id = uuid.uuid4()
    admin_session.add(
        Usuari(
            id=conductor_id,
            empresa_id=emp_uuid,
            nif=f"48{conductor_id.hex[:6].upper()}Z",
            nom="Marc",
            cognoms="Tècnic",
            rol="OPERARI",
            email=f"marc-{conductor_id.hex[:6]}@sevalor.cat",
            telefon="600112233",
        )
    )
    await admin_session.flush()

    avui = date.today()
    ara = datetime.now(timezone.utc)
    data_inici_30d = avui - timedelta(days=30)

    # 1. RENTING (amb excés de 2.000 km a 0.10 €/km = 200 € penalització)
    payload_renting = {
        "matricula": "3001RNT",
        "marca": "Renault",
        "model": "Kangoo",
        "tipus": "DIESEL",
        "regim_adquisicio": "RENTING",
        "renting_limit_km": 10000,
        "odometre_inici_contracte": 10000,
        "odometre_acumulat": 22000,  # 12.000 km nets -> 2.000 km d'excés
        "data_inici_contracte": data_inici_30d.isoformat(),
        "data_fi_contracte": (avui + timedelta(days=335)).isoformat(),
        "quota_mensual_eur": 500.00,
        "preu_km_exces_eur": 0.10,
    }

    # 2. LEASING (quota 400 €/mes, valor residual 4.500 €)
    payload_leasing = {
        "matricula": "3002LSG",
        "marca": "Ford",
        "model": "Transit Custom",
        "tipus": "DIESEL",
        "regim_adquisicio": "LEASING",
        "renting_limit_km": 30000,
        "odometre_inici_contracte": 0,
        "odometre_acumulat": 10000,
        "data_inici_contracte": data_inici_30d.isoformat(),
        "data_fi_contracte": (avui + timedelta(days=335)).isoformat(),
        "quota_mensual_eur": 400.00,
        "valor_residual_eur": 4500.00,
    }

    # 3. LLOGUER (tarifa 40 €/dia, fiança 300 €, resten 2 dies <= 3 -> alerta venciment)
    payload_lloguer = {
        "matricula": "3003LLG",
        "marca": "Toyota",
        "model": "Proace",
        "tipus": "DIESEL",
        "regim_adquisicio": "LLOGUER",
        "odometre_inici_contracte": 50000,
        "odometre_acumulat": 53000,  # 3.000 km nets
        "data_inici_contracte": data_inici_30d.isoformat(),
        "data_fi_contracte": (avui + timedelta(days=2)).isoformat(),
        "tarifa_diaria_eur": 40.00,
        "fianca_eur": 300.00,
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r_rnt = await ac.post("/api/v1/gestio/flota", json=payload_renting, headers=headers)
        r_lsg = await ac.post("/api/v1/gestio/flota", json=payload_leasing, headers=headers)
        r_llg = await ac.post("/api/v1/gestio/flota", json=payload_lloguer, headers=headers)
        assert r_rnt.status_code == 201
        assert r_lsg.status_code == 201
        assert r_llg.status_code == 201

        id_rnt = uuid.UUID(r_rnt.json()["id"])
        id_lsg = uuid.UUID(r_lsg.json()["id"])
        id_llg = uuid.UUID(r_llg.json()["id"])

        # Inserim per a CADA vehicle: 500 € de Manteniment i 200 € de Combustible
        for vid in (id_rnt, id_lsg, id_llg):
            admin_session.add(
                MantenimentVehicle(
                    empresa_id=emp_uuid,
                    vehicle_id=vid,
                    data_manteniment=ara,
                    tipus="PREVENTIU",
                    descripcio="Revisió i frens",
                    taller="Taller Oficial",
                    cost_euros=500.00,
                )
            )
            admin_session.add(
                TiquetCombustible(
                    empresa_id=emp_uuid,
                    vehicle_id=vid,
                    conductor_id=conductor_id,
                    data_tiquet=ara,
                    import_euros=200.00,
                    litres=130.0,
                    odometre_registrat=25000,
                )
            )
        await admin_session.flush()

        # Obtenir detall actualitzat de cada vehicle
        det_rnt = (await ac.get(f"/api/v1/gestio/flota/{id_rnt}", headers=headers)).json()
        det_lsg = (await ac.get(f"/api/v1/gestio/flota/{id_lsg}", headers=headers)).json()
        det_llg = (await ac.get(f"/api/v1/gestio/flota/{id_llg}", headers=headers)).json()

        # A. Verificació RENTING: manteniment (500 €) NO penalitza el TCO (manteniment_computable_tco_eur == 0.0)
        assert det_rnt["despesa_combustible_acumulada_eur"] == 200.00
        assert det_rnt["despesa_manteniment_acumulada_eur"] == 500.00
        assert det_rnt["manteniment_computable_tco_eur"] == 0.00
        assert det_rnt["cost_penalitzacio_km_eur"] == 200.00  # 2000 km * 0.10 €
        assert det_rnt["cost_total_acumulat_eur"] == round(
            det_rnt["cost_fix_meritat_eur"] + 200.00 + 200.00, 2
        )
        assert det_rnt["alerta_renting_km"] == "SUPERAT_100"

        # B. Verificació LEASING: manteniment (500 €) SÍ que s'imputa al TCO + retorna valor_residual_eur
        assert det_lsg["valor_residual_eur"] == 4500.00
        assert det_lsg["despesa_combustible_acumulada_eur"] == 200.00
        assert det_lsg["despesa_manteniment_acumulada_eur"] == 500.00
        assert det_lsg["manteniment_computable_tco_eur"] == 500.00
        assert det_lsg["cost_total_acumulat_eur"] == round(
            det_lsg["cost_fix_meritat_eur"] + 200.00 + 500.00, 2
        )

        # C. Verificació LLOGUER: 30 dies * 40 €/dia = 1200 €, manteniment cobert (0 €), alerta venciment <= 3 dies
        assert det_llg["cost_fix_meritat_eur"] == 1200.00
        assert det_llg["manteniment_computable_tco_eur"] == 0.00
        assert det_llg["cost_total_acumulat_eur"] == 1400.00  # 1200 fix + 200 combustible
        assert det_llg["dies_restants_contracte"] == 2
        assert det_llg["alerta_contracte_venciment"] is True


@pytest.mark.asyncio
async def test_alerta_ritme_desviacio_temporal(
    admin_session: AsyncSession, headers: dict, boss_token: tuple
):
    """Verifica l'alerta primerenca de ritme quan el percentatge de km consumits

    supera en més del 10% el progrés temporal del contracte.
    """
    token, empresa_id = boss_token
    boss_nif = "B" + str(uuid.uuid4())[:8].upper()

    admin_session.add(
        Empresa(
            id=uuid.UUID(empresa_id),
            nom="Test Ritme Empresa",
            nif=boss_nif,
            subdomini="testritme-" + str(uuid.uuid4())[:5],
            pla_subscripcio="ENTERPRISE",
            estat_pagament="ACTIU",
        )
    )
    await admin_session.flush()

    avui = date.today()
    data_inici = avui - timedelta(days=10)
    data_fi = avui + timedelta(days=90)

    payload = {
        "matricula": "4004RIT",
        "marca": "Volkswagen",
        "model": "Caddy",
        "tipus": "DIESEL",
        "distintiu_ambiental": "C",
        "estat": "OPERATIU",
        "regim_adquisicio": "RENTING",
        "renting_limit_km": 50000,
        "odometre_acumulat": 15000,
        "odometre_inici_contracte": 0,
        "data_inici_contracte": data_inici.isoformat(),
        "data_fi_contracte": data_fi.isoformat(),
        "quota_mensual_eur": 520.00,
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/api/v1/gestio/flota", json=payload, headers=headers)
        assert res.status_code == 201
        data = res.json()

        assert data["renting_ocupacio_percent"] == 30.0
        assert data["ocupacio_temps_percent"] == 10.0
        assert data["desviacio_ritme_percent"] == 20.0
        assert data["renting_alerta"] is True
        assert data["renting_nivell_alerta"] == "RITME_EXCES_KM"
        assert data["alerta_renting_km"] == "RITME_EXCES_KM"


@pytest.mark.asyncio
async def test_rls_isolation_regims(admin_session: AsyncSession, db_session: AsyncSession):
    """Verifica l'aïllament multi-tenant (RLS) tant a nivell de PostgreSQL com a nivell d'API HTTP:

    El Tenant B rep 404 en intentar consultar un vehicle del Tenant A i llista buida a GET /gestio/flota.
    """
    tenant_a_id = uuid.uuid4()
    tenant_b_id = uuid.uuid4()

    tenant_a = Empresa(
        id=tenant_a_id,
        nom="Tenant Flota A",
        subdomini=f"fa-{tenant_a_id.hex[:6]}",
        nif="A" + str(uuid.uuid4())[:8].upper(),
    )
    tenant_b = Empresa(
        id=tenant_b_id,
        nom="Tenant Flota B",
        subdomini=f"fb-{tenant_b_id.hex[:6]}",
        nif="B" + str(uuid.uuid4())[:8].upper(),
    )
    admin_session.add_all([tenant_a, tenant_b])
    await admin_session.flush()

    vehicle_a_id = uuid.uuid4()
    vehicle_a = Vehicle(
        id=vehicle_a_id,
        empresa_id=tenant_a_id,
        matricula="5555AAA",
        marca="Mercedes",
        model="Vito",
        regim_adquisicio="LEASING",
        quota_mensual_eur=650.00,
        valor_residual_eur=5000.00,
    )
    admin_session.add(vehicle_a)
    await admin_session.commit()

    # 1. Verificació RLS a nivell de base de dades per a Tenant B
    await db_session.execute(text("SET ROLE sevalor_app;"))
    await db_session.execute(text("SELECT set_config('app.is_superadmin', 'false', true);"))
    await db_session.execute(
        text(f"SELECT set_config('app.current_empresa_id', '{str(tenant_b_id)}', true);")
    )

    res_db = await db_session.execute(text("SELECT id FROM vehicles"))
    assert res_db.fetchall() == []
    await db_session.execute(text("RESET ROLE;"))

    # 2. Verificació RLS a nivell d'endpoint HTTP amb token de Tenant B
    token_b = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "empresa_id": str(tenant_b_id),
            "rol": "BOSS",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
        },
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    headers_b = {"Authorization": f"Bearer {token_b}", "X-Empresa-ID": str(tenant_b_id)}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res_list = await ac.get("/api/v1/gestio/flota", headers=headers_b)
        assert res_list.status_code == 200
        assert res_list.json() == []

        res_detail = await ac.get(f"/api/v1/gestio/flota/{vehicle_a_id}", headers=headers_b)
        assert res_detail.status_code == 404
