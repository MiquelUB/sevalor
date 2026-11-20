"""Tests del BLOC 2 — Orquestrador, Disc d'Empresa, HMAC Anti-Barreja i 8 Subagents Sobirans."""

import json
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

import httpx
import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.main import app
from app.models.models import Empresa, Usuari
from app.services.sovereign_storage import SovereignStorageGateway
from app.services.subagents.subagent_auditoria_marge import SubagentAuditoriaMarge
from app.services.subagents.subagent_client_telegram import SubagentClientTelegram
from app.services.subagents.subagent_flota_despatx import SubagentFlotaDespatx
from app.services.subagents.subagent_general_rag import SubagentGeneralRag
from app.services.subagents.subagent_logistica_estoc import SubagentLogisticaEstoc
from app.services.subagents.subagent_ocr_vision import SubagentOcrVision
from app.services.subagents.subagent_peritatge_camp import SubagentPeritatgeCamp
from app.services.subagents.subagent_planificacio_equip import SubagentPlanificacioEquip


def _token(usuari_id: uuid.UUID, empresa_id: uuid.UUID, rol: str, **extra: Any) -> str:
    payload = {
        "sub": str(usuari_id),
        "rol": rol,
        "empresa_id": str(empresa_id),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=20),
        **extra,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


@pytest.mark.asyncio
async def test_bloc2_hmac_anti_barreja_local_fs_i_http_vault(admin_session, tmp_path: Path, monkeypatch):
    """
    Escut Anti-Barreges HMAC-SHA256 tant en LOCAL_FS com en HTTP_VAULT:
    - Fitxer d'Empresa B copiat físicament al disc d'Empresa A -> REBUTJAT.
    - Fitxer amb empresa_id canviat però HMAC invàlid / zero / absent -> REBUTJAT.
    - Resposta HTTP_VAULT manipulada amb fitxer cross-tenant -> REBUTJADA.
    """
    emp_a, emp_b = uuid.uuid4(), uuid.uuid4()
    disc_a, disc_b = tmp_path / "Disc_A", tmp_path / "Disc_B"
    disc_a.mkdir()
    disc_b.mkdir()

    for eid, nom, sub, disc in [
        (emp_a, "Empresa A Sobirana", "ampa-" + uuid.uuid4().hex[:5], str(disc_a)),
        (emp_b, "Empresa B Rival", "ampb-" + uuid.uuid4().hex[:5], str(disc_b)),
    ]:
        admin_session.add(
            Empresa(
                id=eid,
                nom=nom,
                nif="B" + uuid.uuid4().hex[:8].upper(),
                subdomini=sub,
                pla_subscripcio="ENTERPRISE",
                estat_pagament="ACTIU",
                disc_dur_url=disc,
                node_ia_url=disc,
                node_ia_actiu=True,
                feature_copilot_ia=True,
            )
        )
    await admin_session.flush()

    await SovereignStorageGateway.desar_entitat_json(
        admin_session,
        emp_a,
        "protocols_interns",
        "proto_a",
        {"id": "proto_a", "titol": "Protocol Valid A", "contingut": "Contingut autentic empresa A"},
    )
    await SovereignStorageGateway.desar_entitat_json(
        admin_session,
        emp_b,
        "protocols_interns",
        "proto_b",
        {"id": "proto_b", "titol": "Secret Exclusiu B", "contingut": "Codi secret exclusiu B"},
    )

    dir_a = disc_a / "10_protocols_i_manuals/procediments_interns"
    raw_b = json.loads((disc_b / "10_protocols_i_manuals/procediments_interns/proto_b.json").read_text(encoding="utf-8"))

    # Injecció 1: fitxer de B dins carpeta d'A
    (dir_a / "intrus_b.json").write_text(json.dumps(raw_b), encoding="utf-8")

    # Injecció 2: fitxer amb empresa_id=A falsificat i HMAC zero
    forged_zero = {
        **raw_b,
        "titol": "Manipulat HMAC Zero",
        "contingut": "Manipulat HMAC Zero",
        "_sovereign_meta": {**raw_b["_sovereign_meta"], "empresa_id": str(emp_a), "hmac_tenant": "0" * 64},
    }
    (dir_a / "forged_zero.json").write_text(json.dumps(forged_zero), encoding="utf-8")

    # Injecció 3: fitxer sense hmac_tenant tot i posar empresa_id=A
    unsigned = {
        "id": "unsigned_x",
        "titol": "Sense Signatura HMAC",
        "contingut": "Dada injectada sense firma",
        "_sovereign_meta": {"empresa_id": str(emp_a), "subcarpeta": "10_protocols_i_manuals/procediments_interns"},
    }
    (dir_a / "unsigned.json").write_text(json.dumps(unsigned), encoding="utf-8")

    # Verificació LOCAL_FS: només ha d'aparèixer proto_a
    llegits_fs = await SovereignStorageGateway.llegir_entitats_json(admin_session, emp_a, "protocols_interns")
    assert len(llegits_fs) == 1
    assert llegits_fs[0]["id"] == "proto_a"

    sub_rag = SubagentGeneralRag()
    assert (await sub_rag.tool_get_rag_knowledge(admin_session, emp_a, "Secret Exclusiu B"))["trobat"] is False
    assert (await sub_rag.tool_get_rag_knowledge(admin_session, emp_a, "Manipulat HMAC Zero"))["trobat"] is False
    assert (await sub_rag.tool_get_rag_knowledge(admin_session, emp_a, "Sense Signatura"))["trobat"] is False
    ok_a = await sub_rag.tool_get_rag_knowledge(admin_session, emp_a, "Protocol Valid A")
    assert ok_a["trobat"] is True
    assert len(ok_a["documents"]) == 1

    # Verificació WSS_TUNNEL: injectem fitxers barrejats físicament al disc de l'agent WSS
    from tests.wss_test_helpers import live_empresa_wss_context

    emp_wss = uuid.uuid4()
    tok_wss = f"svlt_hmac_wss_{uuid.uuid4().hex[:12]}"
    disc_wss = tmp_path / "Disc_WSS_HMAC"
    admin_session.add(
        Empresa(
            id=emp_wss,
            nom="Empresa WSS HMAC",
            nif="B" + uuid.uuid4().hex[:8].upper(),
            subdomini="wsshmac-" + uuid.uuid4().hex[:5],
            pla_subscripcio="ENTERPRISE",
            estat_pagament="ACTIU",
            disc_dur_url=f"wss-tunnel://{emp_wss}",
            node_ia_url=f"wss-tunnel://{emp_wss}",
            vault_token=tok_wss,
            node_ia_actiu=True,
            feature_copilot_ia=True,
        )
    )
    await admin_session.flush()

    async with live_empresa_wss_context(emp_wss, tok_wss, disc_wss, start_llm=False):
        await SovereignStorageGateway.desar_entitat_json(
            admin_session,
            emp_wss,
            "magatzem_articles",
            "art_wss_ok",
            {"id": "art_wss_ok", "nom": "Bombeta Valid WSS"},
        )
        # Injectem fitxers intrusos directament al disc físic de l'agent WSS
        art_dir = disc_wss / "03_magatzem/articles_i_estoc"
        (art_dir / "intrus_b.json").write_text(json.dumps(raw_b), encoding="utf-8")
        (art_dir / "forged_zero.json").write_text(json.dumps(forged_zero), encoding="utf-8")
        (art_dir / "unsigned.json").write_text(json.dumps(unsigned), encoding="utf-8")

        llegits_wss = await SovereignStorageGateway.llegir_entitats_json(
            admin_session, emp_wss, "magatzem_articles"
        )
        assert len(llegits_wss) == 1
        assert llegits_wss[0]["id"] == "art_wss_ok"


@pytest.mark.asyncio
async def test_bloc2_tots_8_subagents_llegeixen_nomes_del_disc_sense_sql(admin_session, tmp_path: Path):
    """
    Amb totes les taules de domini d'Hetzner completament buides, tots els 8 subagents
    consulten exclusivament el disc dur dedicat de l'empresa i respecten les barreres de rol.
    """
    emp_id = uuid.uuid4()
    boss_id = uuid.uuid4()
    op1_id = uuid.uuid4()
    op2_id = uuid.uuid4()
    cli_id = uuid.uuid4()
    finca_id = uuid.uuid4()
    prov_id = uuid.uuid4()
    art_id = uuid.uuid4()
    veh1_id = uuid.uuid4()
    veh2_id = uuid.uuid4()
    ot1_id = uuid.uuid4()
    ot2_id = uuid.uuid4()

    disc = tmp_path / "Disc_Complet"
    disc.mkdir()

    admin_session.add(
        Empresa(
            id=emp_id,
            nom="Instal·lacions Zero-Storage SL",
            nif="B" + uuid.uuid4().hex[:8].upper(),
            subdomini="zs-" + uuid.uuid4().hex[:5],
            pla_subscripcio="ENTERPRISE",
            estat_pagament="ACTIU",
            disc_dur_url=str(disc),
            node_ia_url=str(disc),
            node_ia_actiu=True,
            feature_copilot_ia=True,
        )
    )
    await admin_session.flush()

    # Seed EXCLUSIU al disc dur de l'empresa (zero insercions SQL a taules de domini)
    await SovereignStorageGateway.desar_entitat_json(
        admin_session,
        emp_id,
        "clients",
        cli_id,
        {
            "id": str(cli_id),
            "codi": "CLI-DISC-1",
            "rao_social": "Agrícola Valls del Camp SL",
            "nif": "B77665544",
            "telefon": "977112233",
            "telegram_chat_id": "tg_999111",
            "actiu": True,
        },
    )
    await SovereignStorageGateway.desar_entitat_json(
        admin_session,
        emp_id,
        "finques",
        finca_id,
        {
            "id": str(finca_id),
            "client_id": str(cli_id),
            "nom": "Parcel·la Oliveres Nord",
            "adreca": "Camí de Montblanc km 4",
            "superficie_ha": 18.2,
            "poligon_sigpac": "09",
            "parcel_sigpac": "214",
        },
    )
    await SovereignStorageGateway.desar_entitat_json(
        admin_session,
        emp_id,
        "pressupostos",
        "pres_1",
        {"id": "pres_1", "client_id": str(cli_id), "numero": "PR-DISC-01", "estat": "PENDENT", "total": 9200.0},
    )
    await SovereignStorageGateway.desar_entitat_json(
        admin_session,
        emp_id,
        "proveidors",
        prov_id,
        {"id": str(prov_id), "rao_social": "Subministraments Camp SA", "nif": "A12345678", "actiu": True},
    )
    await SovereignStorageGateway.desar_entitat_json(
        admin_session,
        emp_id,
        "magatzem_articles",
        art_id,
        {
            "id": str(art_id),
            "referencia_inventari": "SOL-CABLE-6",
            "nom": "Cable Solar 6mm²",
            "unitat_mesura": "METRES",
            "familia": "SOLAR",
            "quantitat_fisica": 500.0,
            "quantitat_virtual_reservada": 120.0,
            "estoc_minim": 50.0,
            "preu_venda": 4.0,
        },
    )
    await SovereignStorageGateway.desar_entitat_json(
        admin_session,
        emp_id,
        "magatzem_eines",
        "eina_1",
        {
            "id": "eina_1",
            "nom": "Trepant Percutor Hilti",
            "model": "TE-60",
            "numero_serie": "SN-HILTI-99",
            "estat": "ASSIGNADA",
            "custodiat_per_operari_id": str(op1_id),
            "data_compra": (date.today() - timedelta(days=100)).isoformat(),
        },
    )
    await SovereignStorageGateway.desar_entitat_json(
        admin_session,
        emp_id,
        "operaris",
        op1_id,
        {"id": str(op1_id), "nom": "Marc", "cognoms": "Soler", "rol": "OPERARI", "estat": "ACTIU"},
    )
    await SovereignStorageGateway.desar_entitat_json(
        admin_session,
        emp_id,
        "operaris",
        op2_id,
        {"id": str(op2_id), "nom": "Anna", "cognoms": "Puig", "rol": "OPERARI", "estat": "ACTIU"},
    )
    await SovereignStorageGateway.desar_entitat_json(
        admin_session,
        emp_id,
        "jornades",
        "j_1",
        {
            "id": "j_1",
            "usuari_id": str(op1_id),
            "data_jornada": date.today().isoformat(),
            "hora_inici": "08:00",
            "hores_ordinaries": 5.5,
            "estat": "OBERT",
        },
    )
    await SovereignStorageGateway.desar_entitat_json(
        admin_session,
        emp_id,
        "vehicles",
        veh1_id,
        {
            "id": str(veh1_id),
            "matricula": "1234-BBB",
            "marca": "Renault",
            "model": "Master",
            "estat": "EN_RUTA",
            "conductor_habitual_id": str(op1_id),
            "regim_adquisicio": "RENTING",
            "consum_l_100km": 8.7,
        },
    )
    await SovereignStorageGateway.desar_entitat_json(
        admin_session,
        emp_id,
        "vehicles",
        veh2_id,
        {"id": str(veh2_id), "matricula": "9999-ZZZ", "marca": "Ford", "model": "Transit", "estat": "OPERATIU"},
    )
    await SovereignStorageGateway.desar_entitat_json(
        admin_session,
        emp_id,
        "ots_actives",
        ot1_id,
        {
            "id": str(ot1_id),
            "codi": "OT-DISC-01",
            "client_id": str(cli_id),
            "finca_id": str(finca_id),
            "cap_de_colla_id": str(op1_id),
            "vehicle_id": str(veh1_id),
            "titol": "Muntatge plaques sector nord",
            "estat": "EN_CURS",
            "adreca": "41.3860, 2.1740",
            "data_planificacio": (date.today() - timedelta(days=10)).isoformat(),
        },
    )
    await SovereignStorageGateway.desar_entitat_json(
        admin_session,
        emp_id,
        "ots_actives",
        ot2_id,
        {
            "id": str(ot2_id),
            "codi": "OT-DISC-02",
            "client_id": str(cli_id),
            "cap_de_colla_id": str(op2_id),
            "titol": "Revisió Anna",
            "estat": "PENDENT",
        },
    )
    await SovereignStorageGateway.desar_entitat_json(
        admin_session,
        emp_id,
        "ots_historic",
        "ot_tancada_1",
        {
            "id": "ot_tancada_1",
            "codi": "OT-HIST-99",
            "estat": "TANCADA",
            "data_planificacio": date.today().isoformat(),
        },
    )
    await SovereignStorageGateway.desar_entitat_json(
        admin_session,
        emp_id,
        "picking",
        "pick_1",
        {
            "id": "pick_1",
            "ordre_treball_id": "ot_tancada_1",
            "article_id": str(art_id),
            "quantitat_carregada_pick_in": 100.0,
        },
    )
    await SovereignStorageGateway.desar_entitat_json(
        admin_session,
        emp_id,
        "ots_informes",
        "inf_1",
        {
            "id": "inf_1",
            "ordre_treball_id": "ot_tancada_1",
            "codi_ot": "OT-HIST-99",
            "desviacio_hores": 1.5,
            "desviacio_km": 12.0,
            "marge_previst_percentatge": 25.0,
            "marge_real_liquidat_percentatge": 21.0,
            "alerta_merma_operativa": False,
        },
    )

    # 1. GeneralRag
    sub_rag = SubagentGeneralRag()
    cli_res = await sub_rag.tool_search_clients(admin_session, emp_id, "Valls")
    assert cli_res["trobat"] is True and cli_res["clients"][0]["codi"] == "CLI-DISC-1"
    pres_eng = await sub_rag.tool_get_pending_budgets(admin_session, emp_id, caller_role="ENGINYER")
    assert pres_eng["trobat"] is True and "total" not in pres_eng["pressupostos"][0]
    pres_boss = await sub_rag.tool_get_pending_budgets(admin_session, emp_id, caller_role="BOSS")
    assert pres_boss["pressupostos"][0]["total"] == pytest.approx(9200.0)

    # 2. LogisticaEstoc (500 - 120 = 380)
    sub_log = SubagentLogisticaEstoc()
    est_res = await sub_log.tool_get_real_stock(admin_session, emp_id, "Cable Solar")
    assert est_res["trobat"] is True and est_res["total_disponible"] == pytest.approx(380.0)

    # 3. PlanificacioEquip + FR-021 operari isolation
    sub_plan = SubagentPlanificacioEquip()
    ots_op1 = await sub_plan.tool_get_work_orders(
        admin_session, emp_id, caller_role="OPERARI", caller_user_id=op1_id
    )
    codis_op1 = [o["codi"] for o in ots_op1["ordres"]]
    assert "OT-DISC-01" in codis_op1 and "OT-DISC-02" not in codis_op1

    # 4. FlotaDespatx (només veh1 té coordenades reals via OT-DISC-01; sense fallback 41.3851, 2.1734)
    sub_flota = SubagentFlotaDespatx()
    prox = await sub_flota.tool_get_closest_vehicle(admin_session, emp_id, 41.3850, 2.1730)
    assert prox["trobat"] is True
    assert prox["vehicle_mes_proper"]["matricula"] == "1234-BBB"
    assert len(prox["tots_els_vehicles"]) == 1  # veh2 sense GPS no té coordenades inventades
    resp_sense_coords, _, _, res_sense_coords, _ = await sub_flota.run_sovereign(
        "Quin vehicle està més a prop?", admin_session, emp_id
    )
    assert res_sense_coords is not None and res_sense_coords["trobat"] is False

    # 5. PeritatgeCamp (garantia real + memòria al disc sense costos hardcodejats 85.50/45.00)
    sub_perit = SubagentPeritatgeCamp()
    gar = await sub_perit.tool_get_warranty_status(
        admin_session, emp_id, finca_id=str(finca_id), numero_serie="SN-HILTI-99"
    )
    assert gar["trobat"] is True and len(gar["garanties"]) == 2
    memo = await sub_perit.tool_generar_memorandum_tecnic(
        admin_session, emp_id, "Arrel externa ha trencat element soterrat", ot_id_str=str(ot1_id)
    )
    assert memo["trobat"] is True
    assert memo["cost_estimat"] not in (85.50, 45.00)
    memos_disc = await SovereignStorageGateway.llegir_entitats_json(
        admin_session, emp_id, "copilot_memorandums"
    )
    assert len(memos_disc) == 1 and memos_disc[0]["id"] == memo["memo_id"]

    # 6. AuditoriaMarge (BOSS only)
    sub_marge = SubagentAuditoriaMarge()
    veto_eng = await sub_marge.execute_tool(
        "get_unbilled_money", {}, admin_session, emp_id, caller_role="ENGINYER"
    )
    assert veto_eng.get("denegat_per_rol") is True
    unbilled_boss = await sub_marge.execute_tool(
        "get_unbilled_money", {}, admin_session, emp_id, caller_role="BOSS"
    )
    assert unbilled_boss["cost_materials_consumit_pvp"] == pytest.approx(400.0)
    rec = await sub_marge.tool_reconcile_post_obra(admin_session, emp_id, "OT-HIST-99")
    assert rec["reconciliat"] is True and rec["marge_real"] == pytest.approx(21.0)

    # 7. OcrVision (resol proveïdor al disc i desa esborrany OCR)
    sub_ocr = SubagentOcrVision()
    ocr_res = await sub_ocr.tool_extract_albara_lines(
        admin_session, emp_id, "Albarà NIF A12345678 Data 12/10/2026 TOTAL 120.50 €"
    )
    assert ocr_res["proveidor_nom"] == "Subministraments Camp SA"
    albarans_disc = await SovereignStorageGateway.llegir_entitats_json(admin_session, emp_id, "albarans")
    assert any(a.get("estat") == "ESBORRANY_OCR" for a in albarans_disc)

    # 8. ClientTelegram (sense inventar UUIDs falsos)
    sub_tg = SubagentClientTelegram()
    tg_res = await sub_tg.tool_notify_technician_arrival(admin_session, emp_id, "OT-DISC-01", 10)
    assert tg_res["notificat"] is True
    _, t_name_none, _, tg_sovereign, _ = await sub_tg.run_sovereign(
        "Estat canal telegram", admin_session, emp_id, caller_role="BOSS", caller_user_id=boss_id
    )
    assert t_name_none is None
    assert tg_sovereign is not None and tg_sovereign["clients_telegram_vinculats"] == 1


@pytest.mark.asyncio
async def test_bloc2_503_zero_fallback_i_xat_amb_prompt_i_feedback_disc(
    admin_session, tmp_path: Path, monkeypatch
):
    """
    Zero Mock (WSS):
    1) node_ia_actiu=False -> HTTP 503 COPILOT_DESACTIVAT (zero fallback a Hetzner).
    2) node_ia_actiu=True + túnel WSS offline -> HTTP 503 NODE_IA_OFFLINE.
    3) node_ia_actiu=True + túnel WSS actiu -> injecta 09_copilot_ia/prompt_sistema/system_prompt.txt,
       executa tool contra disc dur de l'empresa i desa aprenentatge a copilot_feedback amb HMAC.
    """
    from tests.wss_test_helpers import live_empresa_wss_context

    emp_off = uuid.uuid4()
    boss_off = uuid.uuid4()
    admin_session.add(
        Empresa(
            id=emp_off,
            nom="Empresa Apagada",
            nif="B" + uuid.uuid4().hex[:8].upper(),
            subdomini="off-" + uuid.uuid4().hex[:5],
            pla_subscripcio="PRO",
            estat_pagament="ACTIU",
            disc_dur_url=f"wss-tunnel://{emp_off}",
            node_ia_url=f"wss-tunnel://{emp_off}",
            node_ia_actiu=False,
            feature_copilot_ia=True,
        )
    )
    admin_session.add(
        Usuari(
            id=boss_off,
            empresa_id=emp_off,
            nom="Off",
            cognoms="Boss",
            nif="OFF-" + uuid.uuid4().hex[:4],
            rol="BOSS",
            estat="ACTIU",
        )
    )

    emp_dead_tunnel = uuid.uuid4()
    boss_dead = uuid.uuid4()
    admin_session.add(
        Empresa(
            id=emp_dead_tunnel,
            nom="Empresa Tunel Caigut",
            nif="B" + uuid.uuid4().hex[:8].upper(),
            subdomini="dead-" + uuid.uuid4().hex[:5],
            pla_subscripcio="PRO",
            estat_pagament="ACTIU",
            disc_dur_url=f"wss-tunnel://{emp_dead_tunnel}",
            node_ia_url=f"wss-tunnel://{emp_dead_tunnel}",
            node_ia_actiu=True,
            feature_copilot_ia=True,
        )
    )
    admin_session.add(
        Usuari(
            id=boss_dead,
            empresa_id=emp_dead_tunnel,
            nom="Dead",
            cognoms="Boss",
            nif="DED-" + uuid.uuid4().hex[:4],
            rol="BOSS",
            estat="ACTIU",
        )
    )

    emp_on = uuid.uuid4()
    boss_on = uuid.uuid4()
    disc_on = tmp_path / "Disc_On"
    tok_wss_on = f"svlt_bloc2_on_{uuid.uuid4().hex[:12]}"
    admin_session.add(
        Empresa(
            id=emp_on,
            nom="Empresa Tunel Viu",
            nif="B" + uuid.uuid4().hex[:8].upper(),
            subdomini="live-" + uuid.uuid4().hex[:5],
            pla_subscripcio="ENTERPRISE",
            estat_pagament="ACTIU",
            disc_dur_url=f"wss-tunnel://{emp_on}",
            node_ia_url=f"wss-tunnel://{emp_on}",
            vault_token=tok_wss_on,
            node_ia_actiu=True,
            feature_copilot_ia=True,
        )
    )
    admin_session.add(
        Usuari(
            id=boss_on,
            empresa_id=emp_on,
            nom="Usuari",
            cognoms="",
            email=f"{boss_on.hex}@sovereign.local",
            nif="LIV-" + uuid.uuid4().hex[:4],
            rol="BOSS",
            estat="ACTIU",
        )
    )
    await admin_session.flush()

    tok_off = _token(boss_off, emp_off, "BOSS")
    tok_dead = _token(boss_dead, emp_dead_tunnel, "BOSS")
    tok_on = _token(boss_on, emp_on, "BOSS")

    captured_payloads: List[Dict[str, Any]] = []
    round_counter = {"n": 0}

    def _reply_builder(payload: Dict[str, Any]) -> Dict[str, Any]:
        captured_payloads.append(payload)
        round_counter["n"] += 1
        if round_counter["n"] == 1:
            return {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "tool_calls": [
                                {
                                    "id": "call_1",
                                    "type": "function",
                                    "function": {
                                        "name": "get_real_stock",
                                        "arguments": json.dumps({"article_ref": "Vàlvula Motor"}),
                                    },
                                }
                            ],
                        }
                    }
                ]
            }
        if round_counter["n"] == 2:
            return {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "Maria, al magatzem hi consten 42 unitats de Vàlvula Motor 2 polzades.",
                        }
                    }
                ]
            }
        # Ronda 3: resposta amb content=None per validar fallback determinista segur
        return {"choices": [{"message": {"role": "assistant", "content": None, "tool_calls": None}}]}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res_off = await ac.post(
            "/api/v1/gestio/copilot/xat",
            json={"pregunta": "Quin estoc tenim?"},
            headers={"Authorization": f"Bearer {tok_off}", "X-Empresa-ID": str(emp_off)},
        )
        assert res_off.status_code == 503
        assert res_off.json()["detail"]["code"] == "COPILOT_DESACTIVAT"

        res_dead = await ac.post(
            "/api/v1/gestio/copilot/xat",
            json={"pregunta": "Quin estoc tenim?"},
            headers={"Authorization": f"Bearer {tok_dead}", "X-Empresa-ID": str(emp_dead_tunnel)},
        )
        assert res_dead.status_code == 503
        assert res_dead.json()["detail"]["code"] == "NODE_IA_OFFLINE"

        async with live_empresa_wss_context(
            emp_on,
            tok_wss_on,
            disc_on,
            model_name="custom-loaded-model",
            reply_builder=_reply_builder,
        ):
            await SovereignStorageGateway.desar_entitat_json(
                admin_session,
                emp_on,
                "operaris",
                boss_on,
                {"id": str(boss_on), "nom": "Maria", "cognoms": "Sobirana", "rol": "BOSS"},
            )
            await SovereignStorageGateway.desar_entitat_json(
                admin_session,
                emp_on,
                "magatzem_articles",
                "art_live",
                {"id": "art_live", "nom": "Vàlvula Motor 2 polzades", "referencia_inventari": "VLV-2P", "estoc_disponible": 42.0},
            )
            await SovereignStorageGateway.pujar_fitxer_binari(
                admin_session,
                emp_on,
                "copilot_prompt",
                "system_prompt.txt",
                b"INSTRUCCIO SECRETA DEL CLIENT: Prioritza sempre les valvules de llauto.",
                "text/plain; charset=utf-8",
            )

            res_ok = await ac.post(
                "/api/v1/gestio/copilot/xat",
                json={"pregunta": "Quant d'estoc ens queda de Vàlvula Motor?"},
                headers={"Authorization": f"Bearer {tok_on}", "X-Empresa-ID": str(emp_on)},
            )
            assert res_ok.status_code == 200, res_ok.text
            data_ok = res_ok.json()
            assert data_ok["tool_utilitzada"] == "get_real_stock"
            assert data_ok["tool_resultat"]["total_disponible"] == pytest.approx(42.0)
            assert "42" in data_ok["resposta"]

            assert len(captured_payloads) >= 2
            sys_msg = captured_payloads[0]["messages"][0]["content"]
            assert "INSTRUCCIO SECRETA DEL CLIENT" in sys_msg
            assert "Maria Sobirana" in sys_msg

            feedbacks = await SovereignStorageGateway.llegir_entitats_json(
                admin_session, emp_on, "copilot_feedback"
            )
            assert len(feedbacks) >= 1
            assert any("Vàlvula Motor" in (fb.get("pregunta") or "") for fb in feedbacks)
            assert feedbacks[0]["_sovereign_meta"]["hmac_tenant"]

            res_null_content = await ac.post(
                "/api/v1/gestio/copilot/xat",
                json={"pregunta": "Quin estoc tenim de Vàlvula Motor?"},
                headers={"Authorization": f"Bearer {tok_on}", "X-Empresa-ID": str(emp_on)},
            )
            assert res_null_content.status_code == 200, res_null_content.text
            assert "42" in res_null_content.json()["resposta"]


@pytest.mark.asyncio
async def test_bloc2_fallback_de_node_ia_local_a_tunel_disc_dur_i_prioritat_docker(
    admin_session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    ADR-001 (WSS-only):
    1) Les funcions antigues de pont Docker HTTP han estat eliminades de network_utils
       i resoldre_url_tunel_ia prioritza sempre wss-tunnel://.
    2) /gestio/copilot/xat i /gestio/copilot/ia-status resolen 200 OK sobre el Túnel Invers WSS únic.
    """
    import app.core.network_utils as net_utils
    from tests.wss_test_helpers import live_empresa_wss_context

    for removed_fn in (
        "get_docker_host_gateways",
        "get_candidate_node_urls",
        "get_candidate_ia_tunnel_urls",
        "resolve_effective_node_url",
        "is_private_or_loopback_url",
    ):
        assert not hasattr(net_utils, removed_fn), f"{removed_fn} hauria d'estar eliminada (ADR-001)"

    wss_uri = net_utils.build_wss_tunnel_uri("empresa-test-1")
    assert net_utils.is_wss_tunnel_uri(wss_uri) is True
    assert net_utils.resoldre_url_tunel_ia("http://127.0.0.1:1234", wss_uri) == wss_uri

    vault_secret = "svlt_fallback_secret_987"
    emp_id = uuid.uuid4()
    boss_id = uuid.uuid4()
    admin_session.add(
        Empresa(
            id=emp_id,
            nom="Empresa Tunel WSS SL",
            nif="B" + uuid.uuid4().hex[:8].upper(),
            subdomini="fbk-" + uuid.uuid4().hex[:5],
            pla_subscripcio="ENTERPRISE",
            estat_pagament="ACTIU",
            node_ia_url=f"wss-tunnel://{emp_id}",
            disc_dur_url=f"wss-tunnel://{emp_id}",
            vault_token=vault_secret,
            node_ia_actiu=True,
            feature_copilot_ia=True,
        )
    )
    admin_session.add(
        Usuari(
            id=boss_id,
            empresa_id=emp_id,
            nom="Boss",
            cognoms="Fallback",
            nif="FBK-" + uuid.uuid4().hex[:4],
            rol="BOSS",
            estat="ACTIU",
        )
    )
    await admin_session.flush()

    tok = _token(boss_id, emp_id, "BOSS")
    async with live_empresa_wss_context(
        emp_id,
        vault_secret,
        tmp_path / "disc_fbk",
        model_name="qwen-vault-proxy",
        default_reply="Resposta via túnel Vault OK",
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            res = await ac.post(
                "/api/v1/gestio/copilot/xat",
                json={"pregunta": "Hola, em confirmes si estàs operatiu?"},
                headers={"Authorization": f"Bearer {tok}", "X-Empresa-ID": str(emp_id)},
            )
            assert res.status_code == 200, res.text
            assert "Resposta via túnel Vault OK" in res.json()["resposta"]

            st = await ac.get(
                "/api/v1/gestio/copilot/ia-status",
                headers={"Authorization": f"Bearer {tok}", "X-Empresa-ID": str(emp_id)},
            )
            assert st.status_code == 200, st.text
            assert st.json()["estat"] == "ONLINE"
