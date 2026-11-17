"""Tests exhaustius del Copilot v2 i Subagents Especialitzats (T060 - T068, Disc Sobirà Bloc 2).

Cobreix:
- Routing ponderat Top-2 i selecció de subagents per domini operatiu.
- Subagent de Planificació i Equip (ordres de treball, agenda, fitxatges, incidències) sobre disc de l'empresa.
- Privacitat i aïllament d'operaris (FR-021: operari només veu les seves dades).
- Noves eines de Magatzem (moviments, ruptures, albarans de compra) sobre disc de l'empresa.
- Noves eines de Flota (manteniment, consum de combustible) sobre disc de l'empresa.
- Noves eines de RAG Corporatiu (clients, finques, eines en custòdia, pressupostos pendents).
- Doble barrera de seguretat financera (veto i emmascarament a no-BOSS).
- Porta fail-closed 503 si Copilot desactivat i execució sobirana sobre disc amb persistència a ConsultaXatCopilot.
"""

import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.models import ConsultaXatCopilot, Empresa, Usuari
from app.services.sovereign_storage import SovereignStorageGateway
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

    scored_ot = dispatcher.score_subagents("Quines ordres de treball tenim assignades per a avui?", "ENGINYER")
    assert scored_ot[0][0].id == "subagent_planificacio_equip"

    scored_team = dispatcher.score_subagents("Qui ha fitxat avui de la plantilla i quines hores porten?", "ENGINYER")
    assert scored_team[0][0].id == "subagent_planificacio_equip"

    scored_stock = dispatcher.score_subagents("Tenim alguna alerta de ruptura d'estoc o cables al magatzem?", "CAP_DE_MAGATZEM")
    assert scored_stock[0][0].id == "subagent_logistica_estoc"

    scored_flota = dispatcher.score_subagents("Quins vehicles estan en ruta i quin consum tenen?", "SECRETARIA")
    assert scored_flota[0][0].id == "subagent_flota_despatx"

    scored_marge_eng = dispatcher.score_subagents("Quin marge brut global i diners no facturats tenim?", "ENGINYER")
    assert all(sub.id != "subagent_auditoria_marge" or score < 0 for sub, score in scored_marge_eng)

    scored_marge_boss = dispatcher.score_subagents("Quin marge brut global i diners no facturats tenim?", "BOSS")
    assert scored_marge_boss[0][0].id == "subagent_auditoria_marge"


@pytest.mark.asyncio
async def test_subagent_planificacio_equip_full_tools(admin_session, tmp_path: Path):
    """Verifica el funcionament de les 5 eines del SubagentPlanificacioEquip llegint del disc de l'empresa."""
    empresa_id = uuid.uuid4()
    boss_id = uuid.uuid4()
    operari_id = uuid.uuid4()
    client_id = uuid.uuid4()
    ot_id = uuid.uuid4()

    admin_session.add(
        Empresa(
            id=empresa_id,
            nom="Planificacio Agro SL",
            nif="B" + uuid.uuid4().hex[:8].upper(),
            subdomini="plan-" + uuid.uuid4().hex[:5],
            pla_subscripcio="ENTERPRISE",
            estat_pagament="ACTIU",
            vertical="CampoPro",
            disc_dur_url=str(tmp_path),
            node_ia_url=str(tmp_path),
            node_ia_actiu=True,
            feature_copilot_ia=True,
        )
    )
    await admin_session.flush()

    await SovereignStorageGateway.desar_entitat_json(
        admin_session,
        empresa_id,
        "operaris",
        boss_id,
        {"id": str(boss_id), "nom": "Director", "cognoms": "Operacions", "rol": "BOSS", "estat": "ACTIU"},
    )
    await SovereignStorageGateway.desar_entitat_json(
        admin_session,
        empresa_id,
        "operaris",
        operari_id,
        {"id": str(operari_id), "nom": "Joan", "cognoms": "Pérez", "rol": "OPERARI", "estat": "ACTIU"},
    )
    await SovereignStorageGateway.desar_entitat_json(
        admin_session,
        empresa_id,
        "clients",
        client_id,
        {"id": str(client_id), "codi": "CLI-PL1", "rao_social": "Client Reg", "nif": "A12312312", "actiu": True},
    )

    codi_ot = "OT-PL-" + uuid.uuid4().hex[:4].upper()
    await SovereignStorageGateway.desar_entitat_json(
        admin_session,
        empresa_id,
        "ots_actives",
        ot_id,
        {
            "id": str(ot_id),
            "client_id": str(client_id),
            "codi": codi_ot,
            "titol": "Revisió bomba de reg sector 4",
            "estat": "ASSIGNADA",
            "cap_de_colla_id": str(operari_id),
            "data_planificacio": date.today().isoformat(),
            "adreca": "Finca Les Oliveres, Sector Nord",
        },
    )
    h_ini = (datetime.now(timezone.utc) - timedelta(hours=4)).strftime("%H:%M")
    await SovereignStorageGateway.desar_entitat_json(
        admin_session,
        empresa_id,
        "jornades",
        "j_1",
        {
            "id": "j_1",
            "usuari_id": str(operari_id),
            "data_jornada": date.today().isoformat(),
            "hora_inici": h_ini,
            "hora_fi": None,
            "estat": "EN_CURS",
            "hores_ordinaries": 4.0,
        },
    )
    await SovereignStorageGateway.desar_entitat_json(
        admin_session,
        empresa_id,
        "incidencies_registres",
        "inc_1",
        {
            "id": "inc_1",
            "ordre_treball_id": str(ot_id),
            "operari_id": str(operari_id),
            "ambit": "CAMP",
            "estat": "OBERTA",
            "text_observacions": "Pressió d'aigua insuficient: el manòmetre marca 0.8 bar en lloc de 2.5 bar",
        },
    )
    await admin_session.commit()

    subagent = SubagentPlanificacioEquip()

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
async def test_subagent_planificacio_operari_privacy(admin_session, tmp_path: Path):
    """Verifica que un operari NOMÉS pot veure les seves pròpies ordres i horaris (FR-021)."""
    empresa_id = uuid.uuid4()
    operari_1 = uuid.uuid4()
    operari_2 = uuid.uuid4()
    client_id = uuid.uuid4()

    admin_session.add(
        Empresa(
            id=empresa_id,
            nom="Seguretat Operari SL",
            nif="B" + uuid.uuid4().hex[:8].upper(),
            subdomini="priv-" + uuid.uuid4().hex[:5],
            pla_subscripcio="ENTERPRISE",
            estat_pagament="ACTIU",
            disc_dur_url=str(tmp_path),
            node_ia_url=str(tmp_path),
            node_ia_actiu=True,
            feature_copilot_ia=True,
        )
    )
    await admin_session.flush()

    await SovereignStorageGateway.desar_entitat_json(
        admin_session, empresa_id, "operaris", operari_1, {"id": str(operari_1), "nom": "Miquel", "rol": "OPERARI", "estat": "ACTIU"}
    )
    await SovereignStorageGateway.desar_entitat_json(
        admin_session, empresa_id, "operaris", operari_2, {"id": str(operari_2), "nom": "Jordi", "rol": "OPERARI", "estat": "ACTIU"}
    )
    await SovereignStorageGateway.desar_entitat_json(
        admin_session, empresa_id, "clients", client_id, {"id": str(client_id), "codi": "CLI-PRIV1", "rao_social": "Client Privat", "nif": "A99887766", "actiu": True}
    )

    codi_ot1 = "OT-OP1-" + uuid.uuid4().hex[:3].upper()
    codi_ot2 = "OT-OP2-" + uuid.uuid4().hex[:3].upper()
    await SovereignStorageGateway.desar_entitat_json(
        admin_session,
        empresa_id,
        "ots_actives",
        "ot1",
        {"id": "ot1", "client_id": str(client_id), "codi": codi_ot1, "titol": "Feina Miquel", "estat": "ASSIGNADA", "adreca": "Carrer Camp 1", "cap_de_colla_id": str(operari_1)},
    )
    await SovereignStorageGateway.desar_entitat_json(
        admin_session,
        empresa_id,
        "ots_actives",
        "ot2",
        {"id": "ot2", "client_id": str(client_id), "codi": codi_ot2, "titol": "Feina Jordi", "estat": "ASSIGNADA", "adreca": "Carrer Camp 2", "cap_de_colla_id": str(operari_2)},
    )
    await SovereignStorageGateway.desar_entitat_json(
        admin_session,
        empresa_id,
        "jornades",
        "j1",
        {"id": "j1", "usuari_id": str(operari_1), "data_jornada": date.today().isoformat(), "hores_ordinaries": 8.0, "estat": "TANCAT"},
    )
    await SovereignStorageGateway.desar_entitat_json(
        admin_session,
        empresa_id,
        "jornades",
        "j2",
        {"id": "j2", "usuari_id": str(operari_2), "data_jornada": date.today().isoformat(), "hores_ordinaries": 6.5, "estat": "TANCAT"},
    )
    await admin_session.commit()

    subagent = SubagentPlanificacioEquip()

    res_ots_op1 = await subagent.execute_tool(
        "get_work_orders",
        {},
        admin_session,
        empresa_id,
        caller_role="OPERARI",
        caller_user_id=operari_1,
    )
    assert res_ots_op1["trobat"] is True
    codis = [o["codi"] for o in res_ots_op1["ordres"]]
    assert codi_ot1 in codis
    assert codi_ot2 not in codis

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
async def test_subagent_logistica_noves_eines(admin_session, tmp_path: Path):
    """Verifica get_stock_movements, get_low_stock_alerts i get_supplier_docs a SubagentLogisticaEstoc."""
    empresa_id = uuid.uuid4()
    prov_id = uuid.uuid4()
    art_id = uuid.uuid4()

    admin_session.add(
        Empresa(
            id=empresa_id,
            nom="Magatzem Test SL",
            nif="B" + uuid.uuid4().hex[:8].upper(),
            subdomini="mag-" + uuid.uuid4().hex[:5],
            pla_subscripcio="ENTERPRISE",
            estat_pagament="ACTIU",
            disc_dur_url=str(tmp_path),
            node_ia_url=str(tmp_path),
            node_ia_actiu=True,
            feature_copilot_ia=True,
        )
    )
    await admin_session.flush()

    await SovereignStorageGateway.desar_entitat_json(
        admin_session,
        empresa_id,
        "proveidors",
        prov_id,
        {"id": str(prov_id), "codi": "PRV-01", "nif": "B11223344", "rao_social": "Subministraments Elèctrics SA", "actiu": True},
    )
    await SovereignStorageGateway.desar_entitat_json(
        admin_session,
        empresa_id,
        "magatzem_articles",
        art_id,
        {
            "id": str(art_id),
            "referencia_inventari": "TUB-PVC-90",
            "nom": "Tub PVC Pressió 90mm",
            "unitat_mesura": "METRES",
            "familia": "Fontaneria",
            "estoc_optim": 100.0,
            "estoc_minim": 20.0,
            "quantitat_fisica": 5.0,
            "quantitat_virtual_reservada": 0.0,
            "actiu": True,
            "moviments": [
                {
                    "id": "mov_1",
                    "tipus_moviment": "ENTRADA_ALBARA",
                    "quantitat": 50.0,
                    "referencia_document": "ALB-9876",
                    "notes": "Descàrrega camió matí",
                }
            ],
        },
    )
    await SovereignStorageGateway.desar_entitat_json(
        admin_session,
        empresa_id,
        "albarans",
        "alb_9876",
        {
            "id": "alb_9876",
            "proveidor_id": str(prov_id),
            "numero_albara": "ALB-9876",
            "data_albara": date.today().isoformat(),
            "estat": "REBUT",
        },
    )
    await admin_session.commit()

    subagent = SubagentLogisticaEstoc()

    res_alert = await subagent.execute_tool("get_low_stock_alerts", {}, admin_session, empresa_id)
    assert res_alert["trobat"] is True
    assert res_alert["total_alertes"] >= 1
    assert any(a["referencia"] == "TUB-PVC-90" and a["deficit"] == 15.0 for a in res_alert["alertes"])

    res_mov = await subagent.execute_tool(
        "get_stock_movements", {"material_id": "TUB-PVC-90"}, admin_session, empresa_id
    )
    assert res_mov["trobat"] is True
    assert res_mov["total"] >= 1
    assert res_mov["moviments"][0]["referencia_document"] == "ALB-9876"

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
async def test_subagent_flota_noves_eines(admin_session, tmp_path: Path):
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
            disc_dur_url=str(tmp_path),
            node_ia_url=str(tmp_path),
            node_ia_actiu=True,
            feature_copilot_ia=True,
        )
    )
    await admin_session.flush()

    await SovereignStorageGateway.desar_entitat_json(
        admin_session,
        empresa_id,
        "vehicles",
        v_id,
        {
            "id": str(v_id),
            "matricula": "9876-XYZ",
            "marca": "Renault",
            "model": "Master",
            "tipus": "FURGONETA",
            "estat": "OPERATIU",
            "odometre_acumulat": 125000,
            "consum_l_100km": 9.4,
            "consum_mitjana_historica": 9.6,
            "consum_adblue_litres": 12.0,
            "data_proxima_itv": (date.today() + timedelta(days=20)).isoformat(),
            "estat_itv": "PROPERA_CADUCITAT",
            "regim_adquisicio": "RENTING",
            "renting_limit_km": 150000,
            "historial_reparacions": "Revisió 120k feta a concessionari oficial",
        },
    )
    await admin_session.commit()

    subagent = SubagentFlotaDespatx()

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

    res_maint_op = await subagent.execute_tool(
        "get_vehicle_maintenance",
        {"matricula": "9876-XYZ"},
        admin_session,
        empresa_id,
        caller_role="OPERARI",
    )
    veh_op = res_maint_op["manteniments"][0]
    assert "regim_adquisicio" not in veh_op

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
async def test_subagent_general_rag_noves_eines(admin_session, tmp_path: Path):
    """Verifica search_clients, get_finca_detail, get_pending_budgets i get_tools_custody."""
    empresa_id = uuid.uuid4()
    client_id = uuid.uuid4()
    operari_id = uuid.uuid4()

    admin_session.add(
        Empresa(
            id=empresa_id,
            nom="General Agro SL",
            nif="B" + uuid.uuid4().hex[:8].upper(),
            subdomini="gen-" + uuid.uuid4().hex[:5],
            pla_subscripcio="ENTERPRISE",
            estat_pagament="ACTIU",
            disc_dur_url=str(tmp_path),
            node_ia_url=str(tmp_path),
            node_ia_actiu=True,
            feature_copilot_ia=True,
        )
    )
    await admin_session.flush()

    await SovereignStorageGateway.desar_entitat_json(
        admin_session,
        empresa_id,
        "operaris",
        operari_id,
        {"id": str(operari_id), "nif": "0113C", "nom": "Carles", "cognoms": "Tècnic", "rol": "OPERARI", "estat": "ACTIU"},
    )
    await SovereignStorageGateway.desar_entitat_json(
        admin_session,
        empresa_id,
        "clients",
        client_id,
        {
            "id": str(client_id),
            "codi": "CLI-001",
            "rao_social": "Finca Can Puig SA",
            "nif": "A55566677",
            "telefon": "938123456",
            "email": "info@canpuig.cat",
            "iban_xifrat_simetric": "AES_ENCRYPTED_IBAN_SECRET",
            "actiu": True,
        },
    )
    await SovereignStorageGateway.desar_entitat_json(
        admin_session,
        empresa_id,
        "finques",
        "finca_1",
        {
            "id": "finca_1",
            "client_id": str(client_id),
            "nom": "Parcel·la Les Vinyes",
            "adreca": "Camí Ral s/n",
            "superficie_ha": 14.5,
            "poligon_sigpac": "12",
            "parcel_sigpac": "104",
            "actiu": True,
        },
    )
    await SovereignStorageGateway.desar_entitat_json(
        admin_session,
        empresa_id,
        "pressupostos",
        "pres_1",
        {"id": "pres_1", "client_id": str(client_id), "numero": "PRES-2026-045", "total": 4850.0, "estat": "PENDENT"},
    )
    await SovereignStorageGateway.desar_entitat_json(
        admin_session,
        empresa_id,
        "magatzem_eines",
        "eina_1",
        {
            "id": "eina_1",
            "nom": "Fusora de Polietilè",
            "model": "Rothenberger Roweld P160",
            "numero_serie": "SN-ROTH-9921",
            "estat": "OPERATIU",
            "custodiat_per_operari_id": str(operari_id),
            "data_propera_calibracio": (date.today() + timedelta(days=90)).isoformat(),
        },
    )
    await admin_session.commit()

    subagent = SubagentGeneralRag()

    res_c = await subagent.execute_tool("search_clients", {"terme": "Can Puig"}, admin_session, empresa_id)
    assert res_c["trobat"] is True
    cl = res_c["clients"][0]
    assert cl["rao_social"] == "Finca Can Puig SA"
    assert "iban_xifrat_simetric" not in cl

    res_f = await subagent.execute_tool("get_finca_detail", {"finca_nom_o_id": "Les Vinyes"}, admin_session, empresa_id)
    assert res_f["trobat"] is True
    assert res_f["superficie_ha"] == 14.5
    assert res_f["client_propietari"] == "Finca Can Puig SA"

    res_b_boss = await subagent.execute_tool(
        "get_pending_budgets", {}, admin_session, empresa_id, caller_role="BOSS"
    )
    assert res_b_boss["trobat"] is True
    assert res_b_boss["pressupostos"][0]["total"] == 4850.0

    res_b_eng = await subagent.execute_tool(
        "get_pending_budgets", {}, admin_session, empresa_id, caller_role="ENGINYER"
    )
    assert "total" not in res_b_eng["pressupostos"][0]

    res_e = await subagent.execute_tool("get_tools_custody", {}, admin_session, empresa_id)
    assert res_e["trobat"] is True
    assert res_e["eines"][0]["nom"] == "Fusora de Polietilè"
    assert "Carles" in res_e["eines"][0]["custodiat_per"]


@pytest.mark.asyncio
async def test_copilot_dispatcher_dispatch_sovereign(admin_session, tmp_path: Path):
    """Verifica 503 quan Copilot apagat i execució sobirana sobre disc quan actiu amb log BD + disc."""
    empresa_id = uuid.uuid4()
    boss_id = uuid.uuid4()

    emp = Empresa(
        id=empresa_id,
        nom="Sovereign Agro SL",
        nif="B" + uuid.uuid4().hex[:8].upper(),
        subdomini="sov-" + uuid.uuid4().hex[:5],
        pla_subscripcio="ENTERPRISE",
        estat_pagament="ACTIU",
        disc_dur_url=str(tmp_path),
        node_ia_url=str(tmp_path),
        node_ia_actiu=False,
        feature_copilot_ia=True,
    )
    admin_session.add(emp)
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

    # 1. Amb node_ia_actiu=False -> HTTP 503 obligatori (Zero Fallback a Hetzner)
    with pytest.raises(HTTPException) as exc_info:
        await dispatcher.dispatch(
            pregunta="Hola, qui ets?",
            db=admin_session,
            empresa_id=empresa_id,
            usuari_id=boss_id,
            rol_usuari="BOSS",
        )
    assert exc_info.value.status_code == 503

    # 2. Activem node local sobirà -> execució vàlida amb auditoria
    emp.node_ia_actiu = True
    await admin_session.commit()

    res_salutacio = await dispatcher.dispatch(
        pregunta="Hola, qui ets?",
        db=admin_session,
        empresa_id=empresa_id,
        usuari_id=boss_id,
        rol_usuari="BOSS",
    )
    assert "Copilot Tècnic de SEVALOR Suite" in res_salutacio["resposta"]

    stmt = select(ConsultaXatCopilot).where(
        ConsultaXatCopilot.empresa_id == empresa_id,
        ConsultaXatCopilot.usuari_id == boss_id,
    )
    log_db = (await admin_session.execute(stmt)).scalars().first()
    assert log_db is not None
    assert log_db.pregunta == "Hola, qui ets?"
    assert log_db.temps_inferencia_ms >= 0

    feedbacks = await SovereignStorageGateway.llegir_entitats_json(
        admin_session, empresa_id, "copilot_feedback"
    )
    assert any(fb.get("pregunta") == "Hola, qui ets?" for fb in feedbacks)
