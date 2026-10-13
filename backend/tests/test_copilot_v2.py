"""Tests exhaustius del Copilot v2 i Subagents Especialitzats (T060 - T068).

Cobreix:
- Routing ponderat Top-2 i selecció de subagents per domini operatiu.
- Subagent de Planificació i Equip (ordres de treball, agenda, fitxatges, incidències).
- Privacitat i aïllament d'operaris (FR-021: operari només veu les seves dades).
- Noves eines de Magatzem (moviments, ruptures, albarans de compra).
- Noves eines de Flota (manteniment, consum de combustible).
- Noves eines de RAG Corporatiu (clients, finques, eines en custòdia, pressupostos pendents).
- Doble barrera de seguretat financera (veto i emmascarament a no-BOSS).
- Execució sobirana determinista (Zero Mock) i persistència a ConsultaXatCopilot.
"""

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.models.models import (
    AlbaraProveidor,
    Article,
    Client,
    ConsultaXatCopilot,
    EinaCustodia,
    Empresa,
    EstocMagatzem,
    Finca,
    Incidencia,
    Magatzem,
    MovimentEstoc,
    OrdreTreball,
    Pressupost,
    Proveidor,
    RegistreJornadaLaboral,
    Usuari,
    Vehicle,
)
from app.services.subagents import (
    CopilotDispatcher,
    SubagentFlotaDespatx,
    SubagentGeneralRag,
    SubagentLogisticaEstoc,
    SubagentPlanificacioEquip,
)


@pytest.mark.asyncio
async def test_scoring_top2_routing():
    """Verifica que el routing ponderat classifica adequadament consultes compostes i específiques."""
    dispatcher = CopilotDispatcher()

    # Planificació i agenda
    scored_ot = dispatcher.score_subagents("Quines ordres de treball tenim assignades per a avui?", "ENGINYER")
    assert scored_ot[0][0].id == "subagent_planificacio_equip"

    # Fitxatges i equip
    scored_team = dispatcher.score_subagents("Qui ha fitxat avui de la plantilla i quines hores porten?", "ENGINYER")
    assert scored_team[0][0].id == "subagent_planificacio_equip"

    # Logística i ruptures d'estoc
    scored_stock = dispatcher.score_subagents("Tenim alguna alerta de ruptura d'estoc o cables al magatzem?", "CAP_DE_MAGATZEM")
    assert scored_stock[0][0].id == "subagent_logistica_estoc"

    # Flota i vehicles en ruta
    scored_flota = dispatcher.score_subagents("Quins vehicles estan en ruta i quin consum tenen?", "SECRETARIA")
    assert scored_flota[0][0].id == "subagent_flota_despatx"

    # Veto financer per a no-BOSS
    scored_marge_eng = dispatcher.score_subagents("Quin marge brut global i diners no facturats tenim?", "ENGINYER")
    assert all(sub.id != "subagent_auditoria_marge" or score < 0 for sub, score in scored_marge_eng)

    # Permès per a BOSS
    scored_marge_boss = dispatcher.score_subagents("Quin marge brut global i diners no facturats tenim?", "BOSS")
    assert scored_marge_boss[0][0].id == "subagent_auditoria_marge"


@pytest.mark.asyncio
async def test_subagent_planificacio_equip_full_tools(admin_session):
    """Verifica el funcionament de les 5 eines del SubagentPlanificacioEquip."""
    empresa_id = uuid.uuid4()
    boss_id = uuid.uuid4()
    operari_id = uuid.uuid4()

    empresa = Empresa(
        id=empresa_id,
        nom="Planificacio Agro SL",
        nif="B" + uuid.uuid4().hex[:8].upper(),
        subdomini="plan-" + uuid.uuid4().hex[:5],
        pla_subscripcio="ENTERPRISE",
        estat_pagament="ACTIU",
        vertical="CampoPro",
    )
    admin_session.add(empresa)
    await admin_session.flush()

    admin_session.add(
        Usuari(
            id=boss_id,
            empresa_id=empresa_id,
            nom="Director",
            cognoms="Operacions",
            nif="0101B",
            rol="BOSS",
            estat="ACTIU",
        )
    )
    admin_session.add(
        Usuari(
            id=operari_id,
            empresa_id=empresa_id,
            nom="Joan",
            cognoms="Pérez",
            nif="0102O",
            rol="OPERARI",
            estat="ACTIU",
        )
    )
    await admin_session.flush()

    client_id = uuid.uuid4()
    admin_session.add(
        Client(
            id=client_id,
            empresa_id=empresa_id,
            codi="CLI-PL1",
            rao_social="Client Reg",
            nif="A12312312",
            actiu=True,
        )
    )
    await admin_session.flush()

    # Crear Ordre de Treball
    ot_id = uuid.uuid4()
    codi_ot = "OT-PL-" + uuid.uuid4().hex[:4].upper()
    admin_session.add(
        OrdreTreball(
            id=ot_id,
            empresa_id=empresa_id,
            client_id=client_id,
            codi=codi_ot,
            titol="Revisió bomba de reg sector 4",
            estat="ASSIGNADA",
            cap_de_colla_id=operari_id,
            data_planificacio=date.today(),
            adreca="Finca Les Oliveres, Sector Nord",
        )
    )
    await admin_session.flush()

    # Crear Registre de Jornada

    admin_session.add(
        RegistreJornadaLaboral(
            id=uuid.uuid4(),
            empresa_id=empresa_id,
            usuari_id=operari_id,
            data_jornada=date.today(),
            hora_inici=datetime.now(timezone.utc) - timedelta(hours=4),
            hora_fi=None,
            estat="EN_CURS",
            hores_ordinaries=4.0,
        )
    )

    # Crear Incidència
    admin_session.add(
        Incidencia(
            id=uuid.uuid4(),
            empresa_id=empresa_id,
            ordre_treball_id=ot_id,
            operari_id=operari_id,
            ambit="CAMP",
            estat="OBERTA",
            text_observacions="Pressió d'aigua insuficient: el manòmetre marca 0.8 bar en lloc de 2.5 bar",
        )
    )

    await admin_session.commit()

    subagent = SubagentPlanificacioEquip()

    # 1. get_work_orders
    res_ots = await subagent.execute_tool(
        "get_work_orders",
        {"limit": 5},
        admin_session,
        empresa_id,
        caller_role="BOSS",
        caller_user_id=boss_id,
    )
    assert res_ots["trobat"] is True
    assert res_ots["total"] >= 1
    assert any(o["codi"] == codi_ot for o in res_ots["ordres"])

    # 2. get_work_order_detail
    res_detail = await subagent.execute_tool(
        "get_work_order_detail",
        {"codi_ot": codi_ot},
        admin_session,
        empresa_id,
        caller_role="BOSS",
        caller_user_id=boss_id,
    )
    assert res_detail["trobat"] is True
    assert res_detail["codi"] == codi_ot
    assert res_detail["operari_assignat"] == "Joan Pérez"

    # 3. get_team_today
    res_team = await subagent.execute_tool(
        "get_team_today",
        {},
        admin_session,
        empresa_id,
        caller_role="BOSS",
        caller_user_id=boss_id,
    )
    assert res_team["trobat"] is True
    assert res_team["total_plantilla"] >= 1
    assert any(op["nom"] == "Joan Pérez" and op["jornada_activa"] for op in res_team["equip"])

    # 4. get_timesheet
    res_time = await subagent.execute_tool(
        "get_timesheet",
        {"dies": 7},
        admin_session,
        empresa_id,
        caller_role="BOSS",
        caller_user_id=boss_id,
    )
    assert res_time["trobat"] is True
    assert res_time["total_hores"] >= 4.0

    # 5. get_open_incidents
    res_inc = await subagent.execute_tool(
        "get_open_incidents",
        {"limit": 5},
        admin_session,
        empresa_id,
        caller_role="BOSS",
        caller_user_id=boss_id,
    )
    assert res_inc["trobat"] is True
    assert any("Pressió d'aigua" in i.get("observacions", "") for i in res_inc["incidencies"])



@pytest.mark.asyncio
async def test_subagent_planificacio_operari_privacy(admin_session):
    """Verifica que un operari NOMÉS pot veure les seves pròpies ordres i horaris (FR-021)."""
    empresa_id = uuid.uuid4()
    operari_1 = uuid.uuid4()
    operari_2 = uuid.uuid4()

    empresa = Empresa(
        id=empresa_id,
        nom="Seguretat Operari SL",
        nif="B" + uuid.uuid4().hex[:8].upper(),
        subdomini="priv-" + uuid.uuid4().hex[:5],
        pla_subscripcio="ENTERPRISE",
        estat_pagament="ACTIU",
    )
    admin_session.add(empresa)
    await admin_session.flush()

    admin_session.add(Usuari(id=operari_1, empresa_id=empresa_id, nif="0111M", nom="Miquel", rol="OPERARI", estat="ACTIU"))
    admin_session.add(Usuari(id=operari_2, empresa_id=empresa_id, nif="0112J", nom="Jordi", rol="OPERARI", estat="ACTIU"))

    client_id = uuid.uuid4()
    admin_session.add(
        Client(
            id=client_id,
            empresa_id=empresa_id,
            codi="CLI-PRIV1",
            rao_social="Client Privat",
            nif="A99887766",
            actiu=True,
        )
    )
    await admin_session.flush()

    # OT per operari 1 i OT per operari 2
    codi_ot1 = "OT-OP1-" + uuid.uuid4().hex[:3].upper()
    codi_ot2 = "OT-OP2-" + uuid.uuid4().hex[:3].upper()
    admin_session.add(
        OrdreTreball(
            id=uuid.uuid4(),
            empresa_id=empresa_id,
            client_id=client_id,
            codi=codi_ot1,
            titol="Feina Miquel",
            estat="ASSIGNADA",
            adreca="Carrer Camp 1",
            cap_de_colla_id=operari_1,
        )
    )
    admin_session.add(
        OrdreTreball(
            id=uuid.uuid4(),
            empresa_id=empresa_id,
            client_id=client_id,
            codi=codi_ot2,
            titol="Feina Jordi",
            estat="ASSIGNADA",
            adreca="Carrer Camp 2",
            cap_de_colla_id=operari_2,
        )
    )
    await admin_session.flush()



    # Jornades
    admin_session.add(
        RegistreJornadaLaboral(
            id=uuid.uuid4(),
            empresa_id=empresa_id,
            usuari_id=operari_1,
            data_jornada=date.today(),
            hores_ordinaries=8.0,
            estat="TANCAT",
        )
    )
    admin_session.add(
        RegistreJornadaLaboral(
            id=uuid.uuid4(),
            empresa_id=empresa_id,
            usuari_id=operari_2,
            data_jornada=date.today(),
            hores_ordinaries=6.5,
            estat="TANCAT",
        )
    )
    await admin_session.commit()


    subagent = SubagentPlanificacioEquip()

    # Operari 1 consulta ordres
    res_ots_op1 = await subagent.execute_tool(
        "get_work_orders",
        {},
        admin_session,
        empresa_id,
        caller_role="OPERARI",
        caller_user_id=operari_1,
    )
    assert res_ots_op1["trobat"] is True
    # Només ha de veure la seva feina
    codis = [o["codi"] for o in res_ots_op1["ordres"]]
    assert codi_ot1 in codis
    assert codi_ot2 not in codis

    # Operari 1 consulta timesheet
    res_time_op1 = await subagent.execute_tool(
        "get_timesheet",
        {},
        admin_session,
        empresa_id,
        caller_role="OPERARI",
        caller_user_id=operari_1,
    )
    assert res_time_op1["total_hores"] == 8.0
    for r in res_time_op1["registres"]:
        assert r["usuari"] == "Miquel"


@pytest.mark.asyncio
async def test_subagent_logistica_noves_eines(admin_session):
    """Verifica get_stock_movements, get_low_stock_alerts i get_supplier_docs a SubagentLogisticaEstoc."""
    empresa_id = uuid.uuid4()
    prov_id = uuid.uuid4()
    art_id = uuid.uuid4()
    mag_id = uuid.uuid4()

    empresa = Empresa(
        id=empresa_id,
        nom="Magatzem Test SL",
        nif="B" + uuid.uuid4().hex[:8].upper(),
        subdomini="mag-" + uuid.uuid4().hex[:5],
        pla_subscripcio="ENTERPRISE",
        estat_pagament="ACTIU",
    )
    admin_session.add(empresa)
    await admin_session.flush()

    admin_session.add(
        Proveidor(
            id=prov_id,
            empresa_id=empresa_id,
            codi="PRV-01",
            nif="B11223344",
            rao_social="Subministraments Elèctrics SA",
            actiu=True,
        )
    )

    admin_session.add(
        Magatzem(id=mag_id, empresa_id=empresa_id, nom="Magatzem Central", tipus="PRINCIPAL", adreca="Polígon Sud")
    )
    await admin_session.flush()

    admin_session.add(
        Article(
            id=art_id,
            empresa_id=empresa_id,
            referencia_inventari="TUB-PVC-90",
            nom="Tub PVC Pressió 90mm",
            unitat_mesura="METRES",
            familia="Fontaneria",
            estoc_optim=100.0,
            estoc_minim=20.0,
            actiu=True,
        )
    )
    # Estoc físic a 5.0 (per sota del mínim de 20.0 -> Alerta!)
    admin_session.add(
        EstocMagatzem(
            id=uuid.uuid4(),
            empresa_id=empresa_id,
            magatzem_id=mag_id,
            article_id=art_id,
            quantitat_fisica=5.0,
            quantitat_virtual_reservada=0.0,
        )
    )
    # Moviment d'estoc
    admin_session.add(
        MovimentEstoc(
            id=uuid.uuid4(),
            empresa_id=empresa_id,
            magatzem_id=mag_id,
            article_id=art_id,
            tipus_moviment="ENTRADA_ALBARA",
            quantitat=50.0,
            referencia_document="ALB-9876",
            notes="Descàrrega camió matí",
        )
    )
    # Albarà de proveïdor
    admin_session.add(
        AlbaraProveidor(
            id=uuid.uuid4(),
            empresa_id=empresa_id,
            proveidor_id=prov_id,
            numero_albara="ALB-9876",
            data_albara=date.today(),
            estat="REBUT",
        )
    )
    await admin_session.commit()

    subagent = SubagentLogisticaEstoc()

    # 1. get_low_stock_alerts
    res_alert = await subagent.execute_tool("get_low_stock_alerts", {}, admin_session, empresa_id)
    assert res_alert["trobat"] is True
    assert res_alert["total_alertes"] >= 1
    assert any(a["referencia"] == "TUB-PVC-90" and a["deficit"] == 15.0 for a in res_alert["alertes"])

    # 2. get_stock_movements
    res_mov = await subagent.execute_tool(
        "get_stock_movements", {"material_id": "TUB-PVC-90"}, admin_session, empresa_id
    )
    assert res_mov["trobat"] is True
    assert res_mov["total"] >= 1
    assert res_mov["moviments"][0]["referencia_document"] == "ALB-9876"

    # 3. get_supplier_docs
    res_docs = await subagent.execute_tool(
        "get_supplier_docs",
        {"proveidor_nom": "Subministraments"},
        admin_session,
        empresa_id,
        caller_role="BOSS",
    )
    assert res_docs["trobat"] is True
    assert any(d["numero"] == "ALB-9876" for d in res_docs["documents"])


@pytest.mark.asyncio
async def test_subagent_flota_noves_eines(admin_session):
    """Verifica get_vehicle_maintenance i get_fuel_consumption a SubagentFlotaDespatx."""
    empresa_id = uuid.uuid4()
    v_id = uuid.uuid4()

    admin_session.add(
        Empresa(
            id=empresa_id,
            nom="Flota SL",
            nif="B" + uuid.uuid4().hex[:8].upper(),
            subdomini="flt-" + uuid.uuid4().hex[:5],
            pla_subscripcio="ENTERPRISE",
            estat_pagament="ACTIU",
        )
    )
    admin_session.add(
        Vehicle(
            id=v_id,
            empresa_id=empresa_id,
            matricula="9876-XYZ",
            marca="Renault",
            model="Master",
            tipus="FURGONETA",
            estat="OPERATIU",
            odometre_acumulat=125000,
            consum_l_100km=9.4,
            consum_mitjana_historica=9.6,
            consum_adblue_litres=12.0,
            data_proxima_itv=date.today() + timedelta(days=20),
            estat_itv="PROPERA_CADUCITAT",
            regim_adquisicio="RENTING",
            renting_limit_km=150000,
            historial_reparacions="Revisió 120k feta a concessionari oficial",
        )
    )
    await admin_session.commit()

    subagent = SubagentFlotaDespatx()

    # 1. get_vehicle_maintenance (BOSS: veu renting)
    res_maint_boss = await subagent.execute_tool(
        "get_vehicle_maintenance",
        {"matricula": "9876-XYZ"},
        admin_session,
        empresa_id,
        caller_role="BOSS",
    )
    assert res_maint_boss["trobat"] is True
    veh_boss = res_maint_boss["manteniments"][0]
    assert veh_boss["matricula"] == "9876-XYZ"
    assert veh_boss.get("regim_adquisicio") == "RENTING"

    # Manteniment per a no-BOSS (Operari o Enginyer: regim de renting privat ocult)
    res_maint_op = await subagent.execute_tool(
        "get_vehicle_maintenance",
        {"matricula": "9876-XYZ"},
        admin_session,
        empresa_id,
        caller_role="OPERARI",
    )
    veh_op = res_maint_op["manteniments"][0]
    assert "regim_adquisicio" not in veh_op

    # 2. get_fuel_consumption
    res_fuel = await subagent.execute_tool(
        "get_fuel_consumption",
        {"matricula": "9876-XYZ"},
        admin_session,
        empresa_id,
    )
    assert res_fuel["trobat"] is True
    assert res_fuel["consums"][0]["consum_l_100km"] == 9.4
    assert res_fuel["consums"][0]["consum_adblue_litres"] == 12.0


@pytest.mark.asyncio
async def test_subagent_general_rag_noves_eines(admin_session):
    """Verifica search_clients, get_finca_detail, get_pending_budgets i get_tools_custody."""
    empresa_id = uuid.uuid4()
    client_id = uuid.uuid4()
    operari_id = uuid.uuid4()

    empresa = Empresa(
        id=empresa_id,
        nom="General Agro SL",
        nif="B" + uuid.uuid4().hex[:8].upper(),
        subdomini="gen-" + uuid.uuid4().hex[:5],
        pla_subscripcio="ENTERPRISE",
        estat_pagament="ACTIU",
    )
    admin_session.add(empresa)
    await admin_session.flush()

    admin_session.add(
        Usuari(
            id=operari_id,
            empresa_id=empresa_id,
            nif="0113C",
            nom="Carles",
            cognoms="Tècnic",
            rol="OPERARI",
            estat="ACTIU",
        )
    )
    await admin_session.flush()


    admin_session.add(
        Client(
            id=client_id,
            empresa_id=empresa_id,
            codi="CLI-001",
            rao_social="Finca Can Puig SA",
            nif="A55566677",
            telefon="938123456",
            email="info@canpuig.cat",
            iban_xifrat_simetric="AES_ENCRYPTED_IBAN_SECRET",
            actiu=True,
        )
    )
    admin_session.add(
        Finca(
            id=uuid.uuid4(),
            empresa_id=empresa_id,
            client_id=client_id,
            nom="Parcel·la Les Vinyes",
            adreca="Camí Ral s/n",
            superficie_ha=14.5,
            poligon_sigpac="12",
            parcel_sigpac="104",
            actiu=True,
        )
    )
    admin_session.add(
        Pressupost(
            id=uuid.uuid4(),
            empresa_id=empresa_id,
            client_id=client_id,
            numero="PRES-2026-045",
            total=4850.0,
            estat="PENDENT",
        )
    )
    admin_session.add(
        EinaCustodia(
            id=uuid.uuid4(),
            empresa_id=empresa_id,
            nom="Fusora de Polietilè",
            model="Rothenberger Roweld P160",
            numero_serie="SN-ROTH-9921",
            estat="OPERATIU",
            custodiat_per_operari_id=operari_id,
            data_propera_calibracio=date.today() + timedelta(days=90),
        )
    )
    await admin_session.commit()

    subagent = SubagentGeneralRag()

    # 1. search_clients (Seguretat: MAI retornar l'IBAN!)
    res_c = await subagent.execute_tool("search_clients", {"terme": "Can Puig"}, admin_session, empresa_id)
    assert res_c["trobat"] is True
    cl = res_c["clients"][0]
    assert cl["rao_social"] == "Finca Can Puig SA"
    assert "iban_xifrat_simetric" not in cl

    # 2. get_finca_detail
    res_f = await subagent.execute_tool("get_finca_detail", {"finca_nom_o_id": "Les Vinyes"}, admin_session, empresa_id)
    assert res_f["trobat"] is True
    assert res_f["superficie_ha"] == 14.5
    assert res_f["client_propietari"] == "Finca Can Puig SA"

    # 3. get_pending_budgets (Double Barrier: total només visible per BOSS)
    res_b_boss = await subagent.execute_tool(
        "get_pending_budgets", {}, admin_session, empresa_id, caller_role="BOSS"
    )
    assert res_b_boss["trobat"] is True
    assert res_b_boss["pressupostos"][0]["total"] == 4850.0

    res_b_eng = await subagent.execute_tool(
        "get_pending_budgets", {}, admin_session, empresa_id, caller_role="ENGINYER"
    )
    assert "total" not in res_b_eng["pressupostos"][0]

    # 4. get_tools_custody
    res_e = await subagent.execute_tool("get_tools_custody", {}, admin_session, empresa_id)
    assert res_e["trobat"] is True
    assert res_e["eines"][0]["nom"] == "Fusora de Polietilè"
    assert "Carles" in res_e["eines"][0]["custodiat_per"]


@pytest.mark.asyncio
async def test_copilot_dispatcher_dispatch_sovereign(admin_session):
    """Verifica el dispatch sobirà determinista de CopilotDispatcher amb persistència a ConsultaXatCopilot."""
    empresa_id = uuid.uuid4()
    boss_id = uuid.uuid4()

    admin_session.add(
        Empresa(
            id=empresa_id,
            nom="Sovereign Agro SL",
            nif="B" + uuid.uuid4().hex[:8].upper(),
            subdomini="sov-" + uuid.uuid4().hex[:5],
            pla_subscripcio="ENTERPRISE",
            estat_pagament="ACTIU",
            node_ia_actiu=False,  # Forçar execució sobirana local
        )
    )
    admin_session.add(
        Usuari(
            id=boss_id,
            empresa_id=empresa_id,
            nom="Gerent",
            cognoms="Test",
            nif="0999G",
            rol="BOSS",
            estat="ACTIU",
        )
    )
    await admin_session.commit()

    dispatcher = CopilotDispatcher()

    # Dispatch d'una salutació
    res_salutacio = await dispatcher.dispatch(
        pregunta="Hola, qui ets?",
        db=admin_session,
        empresa_id=empresa_id,
        usuari_id=boss_id,
        rol_usuari="BOSS",
    )
    assert "Copilot Tècnic de SEVALOR Suite" in res_salutacio["resposta"]

    # Verificar que s'ha persistit el log a la base de dades
    stmt = select(ConsultaXatCopilot).where(
        ConsultaXatCopilot.empresa_id == empresa_id,
        ConsultaXatCopilot.usuari_id == boss_id,
    )
    log_db = (await admin_session.execute(stmt)).scalars().first()
    assert log_db is not None
    assert log_db.pregunta == "Hola, qui ets?"
    assert log_db.temps_inferencia_ms >= 0
