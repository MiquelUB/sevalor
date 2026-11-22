#!/usr/bin/env python3
"""Benchmark i Avaluació Real del Copilot v3.2 sobre Models Locals (LM Studio / Ollama).

Avalua 36 casos reals en català repartits entre les 4 verticals (CampoPro, ElectricPro,
HydroPro, BuildingPro) i els 8 subagents del coordinador en 2 etapes:
  - Precisió de selecció d'eina (Stage 1 Router amb `json_schema` / `json_object`)
  - Precisió d'arguments humans (`codi_ot`, `matricula`, `client_nom`, `ordenar_per`, etc.)
  - 0% fuita de narració d'eines (`conte_narracio_eina`)
  - 0% al·lucinació numèrica (`xifres_inventades`)
  - 0% fuita d'etiquetes `<think>`
  - Precisió multi-subagent i RBAC (`OPERARI` vs `BOSS`)
  - Latència `p50`, `p95` i mitjana (Router, Síntesi i Total) comparada contra perfil `32GB` o `16GB`.

Exemples d'ús (des de l'arrel del repositori):
  # Validar els 36 casos i contractes d'encaminament sense LM Studio:
  backend/.venv/bin/python scripts/eval_copilot_models.py --dry-run

  # Benchmark en viu contra LM Studio local al PC dedicat (Ryzen 7 5700U 32 GB):
  backend/.venv/bin/python scripts/eval_copilot_models.py \
      --url http://127.0.0.1:1234/v1 \
      --model qwen2.5-vl-7b-instruct \
      --hardware-profile 32GB \
      --output-json /tmp/eval_qwen25_7b.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.copilot_config_service import build_default_vertical_prompt  # noqa: E402
from app.services.llm_utils import (  # noqa: E402
    conte_narracio_eina,
    escape_data_block,
    strip_think,
    xifres_inventades,
)
from app.services.subagents.dispatcher import (  # noqa: E402
    ROUTER_SYSTEM_PROMPT,
    SYNTH_CONTRACT_RULES,
    CopilotDispatcher,
)
from app.services.subagents.tools_registry import (  # noqa: E402
    ToolSpec,
    build_router_json_schema,
    validate_tool_args,
)


@dataclass(frozen=True)
class EvalCase:
    """Cas d'avaluació real per al Copilot v3.2."""

    id: str
    vertical: str
    rol: str
    query: str
    expected_tools: List[str]
    expected_args_subset: Dict[str, Any] = field(default_factory=dict)
    multi_subagent: bool = False
    is_greeting: bool = False
    fixture_result: Dict[str, Any] = field(default_factory=dict)


EVAL_CASES: List[EvalCase] = [
    # --- 1. LOGÍSTICA I ESTOC (CampoPro / ElectricPro / HydroPro / BuildingPro) ---
    EvalCase(
        id="LOG-01",
        vertical="CAMPOPRO",
        rol="BOSS",
        query="Quin material té menys estoc al magatzem central ara mateix?",
        expected_tools=["get_real_stock"],
        expected_args_subset={"ordenar_per": "menor_estoc"},
        fixture_result={
            "trobat": True,
            "ordenar_per": "menor_estoc",
            "articles": [
                {"referencia": "VALV-110", "nom": "Electrovàlvula 24V 2 polzades", "estoc_total": 2, "estoc_minim": 10},
                {"referencia": "TUB-PE63", "nom": "Tub PE100 63mm 10atm", "estoc_total": 14, "estoc_minim": 20},
            ],
        },
    ),
    EvalCase(
        id="LOG-02",
        vertical="CAMPOPRO",
        rol="ENGINYER",
        query="Quantes unitats tenim de tub PE63 al magatzem?",
        expected_tools=["get_real_stock"],
        fixture_result={
            "trobat": True,
            "articles": [{"referencia": "TUB-PE63", "nom": "Tub PE100 63mm", "estoc_total": 14}],
        },
    ),
    EvalCase(
        id="LOG-03",
        vertical="ELECTRICPRO",
        rol="ENGINYER",
        query="Comprova si tenim diferencials superimmunitzats 40A en estoc.",
        expected_tools=["get_real_stock"],
        fixture_result={
            "trobat": True,
            "articles": [{"referencia": "DIF-40A-SI", "nom": "Diferencial 40A 30mA Superimmunitzat", "estoc_total": 6}],
        },
    ),
    EvalCase(
        id="LOG-04",
        vertical="BUILDINGPRO",
        rol="BOSS",
        query="Qui té en custòdia el trepant percutor Hilti TE-70?",
        expected_tools=["get_eines_stock", "get_tools_custody"],
        fixture_result={
            "trobat": True,
            "eines": [{"nom": "Hilti TE-70", "operari": "Marc Soler", "estat": "ASSIGNADA"}],
        },
    ),
    EvalCase(
        id="LOG-05",
        vertical="HYDROPRO",
        rol="BOSS",
        query="Mostra els moviments recents d'estoc de la bomba Grundfos CR5.",
        expected_tools=["get_stock_movements"],
        fixture_result={
            "trobat": True,
            "moviments": [{"article": "Grundfos CR5", "tipus": "SORTIDA", "quantitat": 1, "data": "2026-11-18"}],
        },
    ),
    EvalCase(
        id="LOG-06",
        vertical="CAMPOPRO",
        rol="ENGINYER",
        query="Quins articles tenen alerta d'estoc baix o ruptura al magatzem?",
        expected_tools=["get_low_stock_alerts", "get_real_stock"],
        fixture_result={
            "trobat": True,
            "articles": [
                {"referencia": "ASPER-34", "nom": "Aspersor sectorial 3/4", "estoc_total": 3, "estoc_minim": 15}
            ],
        },
    ),
    # --- 2. FLOTA I DESPATX ---
    EvalCase(
        id="FLO-01",
        vertical="CAMPOPRO",
        rol="ENGINYER",
        query="Dona'm la fitxa del vehicle amb matrícula 4521-KLM.",
        expected_tools=["get_vehicle_info"],
        expected_args_subset={"matricula": "4521-KLM"},
        fixture_result={
            "trobat": True,
            "matricula": "4521-KLM",
            "marca": "Iveco",
            "model": "Daily 35S",
            "data_proxima_itv": "2026-12-15",
            "odometre_acumulat": 112400,
        },
    ),
    EvalCase(
        id="FLO-02",
        vertical="BUILDINGPRO",
        rol="BOSS",
        query="Quins vehicles tenen la ITV o l'assegurança a punt de caducar els propers 30 dies?",
        expected_tools=["audit_itv_insurance_fleet"],
        fixture_result={
            "trobat": True,
            "total_alertes": 1,
            "alertes": [{"matricula": "8890-JTR", "tipus": "ITV", "dies_restants": 8, "severitat": "WARNING"}],
        },
    ),
    EvalCase(
        id="FLO-03",
        vertical="ELECTRICPRO",
        rol="ENGINYER",
        query="Quins vehicles pesants amb grua autocargant tenim disponibles per carregar 2500 kg?",
        expected_tools=["get_heavy_vehicles_for_ot"],
        fixture_result={
            "trobat": True,
            "total_vehicles": 1,
            "vehicles": [{"matricula": "2002-BBB", "marca": "Iveco", "carrega_util_kg": 3200}],
        },
    ),
    EvalCase(
        id="FLO-04",
        vertical="HYDROPRO",
        rol="ENGINYER",
        query="Quines ordres de treball tenim obertes o pendents aquesta setmana?",
        expected_tools=["get_work_orders"],
        fixture_result={
            "trobat": True,
            "ordres": [{"codi_ot": "OT-2026-084", "client": "Comunitat C/ Major 12", "estat": "EN_CURS"}],
        },
    ),
    EvalCase(
        id="FLO-05",
        vertical="CAMPOPRO",
        rol="OPERARI",
        query="On és la furgoneta més propera a les coordenades 41.6175, 0.6200?",
        expected_tools=["get_closest_vehicle"],
        fixture_result={
            "trobat": True,
            "vehicle_mes_proper": {"matricula": "4521-KLM", "distancia_km": 4.2},
        },
    ),
    EvalCase(
        id="FLO-06",
        vertical="BUILDINGPRO",
        rol="BOSS",
        query="Resumeix el consum de combustible i gasoil de la flota aquest mes.",
        expected_tools=["get_fuel_consumption", "get_fleet_status"],
        fixture_result={
            "trobat": True,
            "total_litres": 640.5,
            "despesa_total_eur": 985.40,
        },
    ),
    # --- 3. FINANCES I MARGES (NOMÉS BOSS / ADMIN) ---
    EvalCase(
        id="FIN-01",
        vertical="CAMPOPRO",
        rol="BOSS",
        query="Quants diners tenim pendents de facturar aquest mes?",
        expected_tools=["get_unbilled_money"],
        fixture_result={
            "trobat": True,
            "total_pendent_facturar_eur": 14850.50,
            "ordres_pendents": 4,
        },
    ),
    EvalCase(
        id="FIN-02",
        vertical="ELECTRICPRO",
        rol="BOSS",
        query="Quina desviació i rendibilitat real hem tingut a les obres tancades aquest mes?",
        expected_tools=["reconcile_post_obra", "detect_margin_leak"],
        fixture_result={
            "trobat": True,
            "obres_analitzades": 5,
            "marge_mitja_pct": 21.4,
        },
    ),
    EvalCase(
        id="FIN-03",
        vertical="BUILDINGPRO",
        rol="BOSS",
        query="Fes la reconciliació post-obra de l'ordre OT-2026-041 per veure si hem perdut marge.",
        expected_tools=["reconcile_post_obra", "detect_margin_leak"],
        fixture_result={
            "trobat": True,
            "codi_ot": "OT-2026-041",
            "marge_previst_pct": 28.0,
            "marge_real_pct": 16.5,
            "desviacio_eur": -920.00,
        },
    ),
    EvalCase(
        id="FIN-04",
        vertical="HYDROPRO",
        rol="BOSS",
        query="Quins pressupostos tenim pendents d'acceptació per part dels clients?",
        expected_tools=["get_pending_budgets"],
        fixture_result={
            "trobat": True,
            "pressupostos": [{"numero": "PR-2026-102", "client": "Hotel Pirineu", "import_total": 4890.00}],
        },
    ),
    EvalCase(
        id="FIN-05",
        vertical="CAMPOPRO",
        rol="BOSS",
        query="Detecta si hi ha alguna fuga de marge o merma en les obres tancades d'aquest trimestre.",
        expected_tools=["detect_margin_leak"],
        fixture_result={
            "trobat": True,
            "alertes_marge": [{"codi_ot": "OT-2026-033", "merma_pct": 14.2}],
        },
    ),
    # --- 4. CLIENTS, GARANTIES I HISTÒRIC 360° ---
    EvalCase(
        id="CLI-01",
        vertical="CAMPOPRO",
        rol="ENGINYER",
        query="Mostra l'historial 360 del client Finca Mas Roig.",
        expected_tools=["get_client_history", "get_finca_detail"],
        fixture_result={
            "trobat": True,
            "client": "Finca Mas Roig",
            "intervencions_ultim_any": 3,
            "ultima_ot": "OT-2026-055",
        },
    ),
    EvalCase(
        id="CLI-02",
        vertical="HYDROPRO",
        rol="ENGINYER",
        query="La bomba de pressió de Finca Can Serra encara està en garantia?",
        expected_tools=["get_warranty_status"],
        fixture_result={
            "trobat": True,
            "garantia_activa": True,
            "data_instal_lacio": "2025-09-10",
            "tipus": "FABRICANT_2_ANYS",
        },
    ),
    EvalCase(
        id="CLI-03",
        vertical="ELECTRICPRO",
        rol="SECRETARIA",
        query="Cerca les dades de contacte del client Indústries Ponent.",
        expected_tools=["search_clients", "get_client_history"],
        fixture_result={
            "trobat": True,
            "clients": [{"nom": "Indústries Ponent SL", "telefon": "973112233"}],
        },
    ),
    EvalCase(
        id="CLI-04",
        vertical="BUILDINGPRO",
        rol="ENGINYER",
        query="Quines incidències obertes tenim reportades a les ordres d'obra?",
        expected_tools=["get_open_incidents"],
        fixture_result={
            "trobat": True,
            "incidencies": [{"id": "INC-14", "client": "Edifici Rambla 8", "descripcio": "Filtració coberta nord"}],
        },
    ),
    # --- 5. PLANIFICACIÓ, EQUIP I JORNADES ---
    EvalCase(
        id="RRH-01",
        vertical="BUILDINGPRO",
        rol="BOSS",
        query="Quants operaris tenim actius a la plantilla avui i quines tasques tenen assignades?",
        expected_tools=["get_team_today", "get_work_orders"],
        fixture_result={
            "trobat": True,
            "operaris_actius": 6,
            "assignacions": [{"operari": "Jordi Puig", "ot": "OT-2026-091"}],
        },
    ),
    EvalCase(
        id="RRH-02",
        vertical="ELECTRICPRO",
        rol="ENGINYER",
        query="Mostra el detall complet de l'ordre de treball OT-2026-084.",
        expected_tools=["get_work_order_detail", "get_work_orders"],
        fixture_result={
            "trobat": True,
            "codi_ot": "OT-2026-084",
            "estat": "EN_CURS",
            "operari": "Manel Font",
        },
    ),
    EvalCase(
        id="RRH-03",
        vertical="CAMPOPRO",
        rol="BOSS",
        query="Resumeix les hores fitxades i jornades de l'equip aquesta setmana.",
        expected_tools=["get_timesheet"],
        fixture_result={
            "trobat": True,
            "total_hores": 162.5,
            "operaris_actius": 4,
        },
    ),
    # --- 6. BASE DE CONEIXEMENT, RAG I PERITATGE ---
    EvalCase(
        id="RAG-01",
        vertical="ELECTRICPRO",
        rol="OPERARI",
        query="Quin és el protocol de seguretat REBT per treballar sense tensió amb les 5 regles d'or?",
        expected_tools=["get_rag_knowledge"],
        fixture_result={
            "trobat": True,
            "documents": [{"titol": "Protocol 5 Regles d'Or REBT", "resum": "1. Desconnectar 2. Bloquejar 3. Verificar absència tensió 4. Posar a terra 5. Senyalitzar"}],
        },
    ),
    EvalCase(
        id="RAG-02",
        vertical="CAMPOPRO",
        rol="OPERARI",
        query="Busca al manual de procediments com purgar els filtres de malla automàtics.",
        expected_tools=["get_rag_knowledge"],
        fixture_result={
            "trobat": True,
            "documents": [{"titol": "Manteniment Filtres de Malla", "resum": "Tancar vàlvula entrada, obrir purga 45 segons i revisar pressió diferencial <0.5 bar."}],
        },
    ),
    EvalCase(
        id="RAG-03",
        vertical="HYDROPRO",
        rol="ENGINYER",
        query="Genera un memoràndum tècnic de peritatge per a l'avaria de bomba de l'ordre OT-2026-084.",
        expected_tools=["generar_memorandum_tecnic"],
        fixture_result={
            "trobat": True,
            "memorandum_id": "MEM-2026-09",
            "resum": "Cavitació a bomba de pou profund per nivell freàtic baix.",
        },
    ),
    # --- 7. FINQUES, PROVEÏDORS I OCR ---
    EvalCase(
        id="DOC-01",
        vertical="CAMPOPRO",
        rol="ENGINYER",
        query="Mostra el detall tècnic i parcel·les SIGPAC de la finca Els Olivers.",
        expected_tools=["get_finca_detail"],
        fixture_result={
            "trobat": True,
            "finca": "Finca Els Olivers",
            "hectarees": 18.5,
        },
    ),
    EvalCase(
        id="DOC-02",
        vertical="BUILDINGPRO",
        rol="SECRETARIA",
        query="Cerca els albarans de compra del proveïdor Materials del Segrià.",
        expected_tools=["get_supplier_docs"],
        fixture_result={
            "trobat": True,
            "documents": [{"nom": "ALB-2026-411_MaterialsSegria.pdf", "import_eur": 1245.80}],
        },
    ),
    EvalCase(
        id="OCR-01",
        vertical="HYDROPRO",
        rol="SECRETARIA",
        query="Extreu per OCR les línies de l'albarà escanejat d'avui.",
        expected_tools=["extract_albara_lines"],
        fixture_result={
            "trobat": True,
            "linies": [{"article": "Vàlvula esfera 1\"", "quantitat": 10}],
        },
    ),
    # --- 8. TELEGRAM / COMUNICACIONS CLIENT ---
    EvalCase(
        id="TEL-01",
        vertical="CAMPOPRO",
        rol="SECRETARIA",
        query="Notifica per Telegram l'arribada del tècnic al client Mas Roig en 20 minuts.",
        expected_tools=["notify_technician_arrival"],
        fixture_result={
            "trobat": True,
            "estat": "PENDENT_CONFIRMACIO_HITL",
            "eta_minuts": 20,
        },
    ),
    # --- 9. MULTI-SUBAGENT (2 DOMINIS EN UNA SOLA CONSULTA) ---
    EvalCase(
        id="MULTI-01",
        vertical="CAMPOPRO",
        rol="ENGINYER",
        query="Tenim estoc de tub PE63 i quina furgoneta està disponible sense alertes d'ITV per portar-lo?",
        expected_tools=["get_real_stock", "audit_itv_insurance_fleet"],
        multi_subagent=True,
        fixture_result={
            "trobat": True,
            "articles": [{"referencia": "TUB-PE63", "estoc_total": 14}],
            "vehicles_aptes": [{"matricula": "4521-KLM", "estat": "OPERATIU"}],
        },
    ),
    EvalCase(
        id="MULTI-02",
        vertical="ELECTRICPRO",
        rol="BOSS",
        query="Comprova la garantia de la instal·lació del client Indústries Nord i el seu historial de finques.",
        expected_tools=["get_warranty_status", "get_client_history"],
        multi_subagent=True,
        fixture_result={
            "trobat": True,
            "garantia_activa": False,
            "intervencions": 2,
        },
    ),
    EvalCase(
        id="MULTI-03",
        vertical="BUILDINGPRO",
        rol="BOSS",
        query="Quins operaris tenim disponibles avui a l'equip i quin vehicle pesant amb grua podem assignar?",
        expected_tools=["get_team_today", "get_heavy_vehicles_for_ot"],
        multi_subagent=True,
        fixture_result={
            "trobat": True,
            "operaris_aptes": ["Manel Font"],
            "vehicles": [{"matricula": "2002-BBB", "carrega_util_kg": 3200}],
        },
    ),
    # --- 10. RBAC SEGURETAT (OPERARI NO POT ACCEDIR A EINES FINANCERES BOSS-ONLY) ---
    EvalCase(
        id="RBAC-01",
        vertical="CAMPOPRO",
        rol="OPERARI",
        query="Quin marge brut i quants diners sense facturar té l'empresa aquest mes?",
        expected_tools=[],
        fixture_result={"trobat": False, "missatge": "Accés restringit a dades econòmiques."},
    ),
    EvalCase(
        id="RBAC-02",
        vertical="ELECTRICPRO",
        rol="OPERARI",
        query="Fes la reconciliació post-obra i detecta fuites de marge de l'ordre OT-2026-041.",
        expected_tools=[],
        fixture_result={"trobat": False, "missatge": "Accés restringit a dades econòmiques."},
    ),
    # --- 11. FAST-PATH SALUTACIONS (0 CRIDES DE ROUTER) ---
    EvalCase(
        id="FAST-01",
        vertical="CAMPOPRO",
        rol="BOSS",
        query="Hola, bon dia!",
        expected_tools=[],
        is_greeting=True,
    ),
    EvalCase(
        id="FAST-02",
        vertical="HYDROPRO",
        rol="OPERARI",
        query="Gràcies!",
        expected_tools=[],
        is_greeting=True,
    ),
]


@dataclass
class CaseEvalResult:
    case_id: str
    vertical: str
    rol: str
    query: str
    selected_subagents: List[str]
    allowed_tools_count: int
    predicted_tools: List[str]
    tool_hit: bool
    args_valid: bool
    args_subset_hit: bool
    narration_leaked: bool
    numeric_hallucination: bool
    think_leaked: bool
    router_ms: float
    synth_ms: float
    total_ms: float
    error: Optional[str] = None


def _percentile(values: Sequence[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = (len(ordered) - 1) * (pct / 100.0)
    lo = math.floor(idx)
    hi = math.ceil(idx)
    if lo == hi:
        return ordered[lo]
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (idx - lo)


async def _detect_first_model(client: httpx.AsyncClient, base_url: str) -> str:
    resp = await client.get(f"{base_url.rstrip('/')}/models", timeout=5.0)
    resp.raise_for_status()
    data = resp.json()
    items = data.get("data") if isinstance(data, dict) else []
    if isinstance(items, list):
        for item in items:
            if isinstance(item, dict) and item.get("id"):
                return str(item["id"])
    raise RuntimeError(f"No s'ha trobat cap model carregat a {base_url}/models.")


async def _call_router_live(
    client: httpx.AsyncClient,
    base_url: str,
    model: str,
    query: str,
    active_specs: Sequence[ToolSpec],
    timeout_s: float,
) -> tuple[List[Dict[str, Any]], float, Optional[str]]:
    """Executa l'Etapa 1 (Router JSON estructurat) idèntica a `dispatcher.py`."""
    schema = build_router_json_schema(active_specs)
    tools_desc = "\n".join(f"- {s.name}: {s.description}" for s in active_specs)
    sys_msg = f"{ROUTER_SYSTEM_PROMPT}\n\nEines disponibles:\n{tools_desc}"
    payload: Dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": sys_msg},
            {"role": "user", "content": f"Pregunta actual: {query}"},
        ],
        "temperature": 0.0,
        "max_tokens": 220,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "sevalor_tool_plan",
                "strict": True,
                "schema": schema,
            },
        },
    }

    t0 = time.perf_counter()
    try:
        resp = await client.post(
            f"{base_url.rstrip('/')}/chat/completions",
            json=payload,
            timeout=timeout_s,
        )
        if resp.status_code == 400:
            # Fallback a json_object si el backend no admet json_schema estricte
            payload["response_format"] = {"type": "json_object"}
            resp = await client.post(
                f"{base_url.rstrip('/')}/chat/completions",
                json=payload,
                timeout=timeout_s,
            )
        resp.raise_for_status()
        data = resp.json()
        raw = str(data["choices"][0]["message"].get("content", "")).strip()
        clean = strip_think(raw)
        start = clean.find("{")
        end = clean.rfind("}")
        if start == -1 or end == -1:
            return [], (time.perf_counter() - t0) * 1000.0, "JSON no trobat a la sortida del router"
        parsed = json.loads(clean[start : end + 1])
        calls = parsed.get("calls") if isinstance(parsed, dict) else []
        if not isinstance(calls, list):
            calls = []
        return [c for c in calls if isinstance(c, dict)], (time.perf_counter() - t0) * 1000.0, None
    except Exception as exc:
        return [], (time.perf_counter() - t0) * 1000.0, str(exc)


async def _call_synthesis_live(
    client: httpx.AsyncClient,
    base_url: str,
    model: str,
    vertical: str,
    query: str,
    fixture_result: Dict[str, Any],
    timeout_s: float,
) -> tuple[str, float, Optional[str]]:
    """Executa l'Etapa 2 (Síntesi sense tools) amb prefix estàtic cachejable."""
    static_prompt = f"{build_default_vertical_prompt(vertical)}\n\n{SYNTH_CONTRACT_RULES}"
    dades_json = json.dumps(fixture_result, ensure_ascii=False)
    user_msg = (
        f"Pregunta de l'usuari: {query}\n\n"
        f"{escape_data_block(dades_json)}\n\n"
        "Respon directament en català usant EXCLUSIVAMENT les dades dins <dades_empresa>. "
        "No inventis cap xifra i no mencionis eines ni processos interns."
    )
    payload: Dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": static_prompt},
            {"role": "user", "content": user_msg},
        ],
        "temperature": 0.1,
        "max_tokens": 350,
    }
    t0 = time.perf_counter()
    try:
        resp = await client.post(
            f"{base_url.rstrip('/')}/chat/completions",
            json=payload,
            timeout=timeout_s,
        )
        resp.raise_for_status()
        data = resp.json()
        raw = str(data["choices"][0]["message"].get("content", "")).strip()
        return raw, (time.perf_counter() - t0) * 1000.0, None
    except Exception as exc:
        return "", (time.perf_counter() - t0) * 1000.0, str(exc)


async def run_evaluation(
    *,
    dry_run: bool,
    base_url: str,
    model: Optional[str],
    hardware_profile: str,
    vertical_filter: Optional[str],
    limit: Optional[int],
) -> Dict[str, Any]:
    dispatcher = CopilotDispatcher()
    cases = list(EVAL_CASES)
    if vertical_filter:
        vf = vertical_filter.strip().upper()
        cases = [c for c in cases if c.vertical == vf]
    if limit is not None and limit > 0:
        cases = cases[:limit]

    resolved_model = model or "dry-run"
    router_timeout = 8.0 if hardware_profile == "16GB" else 6.0
    synth_timeout = 18.0 if hardware_profile == "16GB" else 14.0

    results: List[CaseEvalResult] = []
    async with httpx.AsyncClient(follow_redirects=False) as client:
        if not dry_run and not model:
            resolved_model = await _detect_first_model(client, base_url)

        for case in cases:
            # 1. Selecció de subagents i RBAC reals del dispatcher
            selected, es_domini_operatiu = dispatcher.select_active_subagents(case.query, case.rol)
            selected_ids = [s.id for s in selected]
            active_specs, _tool_map = dispatcher._get_active_specs(selected, case.rol)
            allowed_tools = [s.name for s in active_specs]

            if case.is_greeting:
                is_greet_ok = not es_domini_operatiu
                results.append(
                    CaseEvalResult(
                        case_id=case.id,
                        vertical=case.vertical,
                        rol=case.rol,
                        query=case.query,
                        selected_subagents=selected_ids,
                        allowed_tools_count=len(allowed_tools),
                        predicted_tools=[],
                        tool_hit=is_greet_ok,
                        args_valid=True,
                        args_subset_hit=True,
                        narration_leaked=False,
                        numeric_hallucination=False,
                        think_leaked=False,
                        router_ms=0.0,
                        synth_ms=0.0,
                        total_ms=0.0,
                    )
                )
                continue

            if dry_run:
                # Verifica que les eines esperades estan dins l'allowlist del rol i que RBAC bloca finances a OPERARI
                if not case.expected_tools:
                    # RBAC case: cap eina financera BOSS-only pot estar a allowed_tools
                    fin_tools = {"get_unbilled_money", "reconcile_post_obra", "detect_margin_leak"}
                    hit = not any(t in fin_tools for t in allowed_tools)
                else:
                    hit = any(t in allowed_tools for t in case.expected_tools)
                    if case.multi_subagent:
                        hit = all(t in allowed_tools for t in case.expected_tools)
                results.append(
                    CaseEvalResult(
                        case_id=case.id,
                        vertical=case.vertical,
                        rol=case.rol,
                        query=case.query,
                        selected_subagents=selected_ids,
                        allowed_tools_count=len(allowed_tools),
                        predicted_tools=allowed_tools[:3],
                        tool_hit=hit,
                        args_valid=True,
                        args_subset_hit=True,
                        narration_leaked=False,
                        numeric_hallucination=False,
                        think_leaked=False,
                        router_ms=0.0,
                        synth_ms=0.0,
                        total_ms=0.0,
                    )
                )
                continue

            # Mode LIVE contra LM Studio / Ollama
            calls: List[Dict[str, Any]] = []
            router_ms = 0.0
            err: Optional[str] = None
            if active_specs and es_domini_operatiu:
                calls, router_ms, err = await _call_router_live(
                    client, base_url, resolved_model, case.query, active_specs, router_timeout
                )

            predicted_tools: List[str] = []
            all_args_valid = True
            subset_hit = not bool(case.expected_args_subset)

            for call in calls:
                tname = str(call.get("tool") or "").strip()
                raw_args = call.get("args") if isinstance(call.get("args"), dict) else {}
                if not tname:
                    continue
                predicted_tools.append(tname)
                try:
                    if tname not in allowed_tools:
                        raise ValueError(f"Eina '{tname}' fora de l'allowlist del rol {case.rol}")
                    validated = validate_tool_args(tname, raw_args)
                    if case.expected_args_subset and tname in case.expected_tools:
                        if all(
                            str(validated.get(k, "")).lower() == str(v).lower()
                            for k, v in case.expected_args_subset.items()
                        ):
                            subset_hit = True
                except Exception:
                    all_args_valid = False

            if not case.expected_tools:
                fin_tools = {"get_unbilled_money", "reconcile_post_obra", "detect_margin_leak"}
                tool_hit = not any(t in fin_tools for t in predicted_tools)
            elif case.multi_subagent:
                tool_hit = all(t in predicted_tools for t in case.expected_tools)
            else:
                tool_hit = any(t in predicted_tools for t in case.expected_tools)

            synth_raw = ""
            synth_ms = 0.0
            if case.fixture_result and err is None:
                synth_raw, synth_ms, synth_err = await _call_synthesis_live(
                    client,
                    base_url,
                    resolved_model,
                    case.vertical,
                    case.query,
                    case.fixture_result,
                    synth_timeout,
                )
                if synth_err:
                    err = synth_err

            clean_synth = strip_think(synth_raw)
            think_leaked = "<think>" in clean_synth.lower() or "</think>" in clean_synth.lower()
            narration_leaked = conte_narracio_eina(clean_synth) if clean_synth else False
            numeric_hall = (
                xifres_inventades(clean_synth, case.fixture_result)
                if clean_synth and case.fixture_result
                else False
            )

            results.append(
                CaseEvalResult(
                    case_id=case.id,
                    vertical=case.vertical,
                    rol=case.rol,
                    query=case.query,
                    selected_subagents=selected_ids,
                    allowed_tools_count=len(allowed_tools),
                    predicted_tools=predicted_tools,
                    tool_hit=tool_hit,
                    args_valid=all_args_valid,
                    args_subset_hit=subset_hit,
                    narration_leaked=narration_leaked,
                    numeric_hallucination=numeric_hall,
                    think_leaked=think_leaked,
                    router_ms=round(router_ms, 1),
                    synth_ms=round(synth_ms, 1),
                    total_ms=round(router_ms + synth_ms, 1),
                    error=err,
                )
            )

    total = len(results)
    non_greet = [r for r in results if not any(c.id == r.case_id and c.is_greeting for c in cases)]
    multi_res = [r for r in results if any(c.id == r.case_id and c.multi_subagent for c in cases)]
    totals_ms = [r.total_ms for r in non_greet if r.total_ms > 0]
    router_lat = [r.router_ms for r in non_greet if r.router_ms > 0]
    synth_lat = [r.synth_ms for r in non_greet if r.synth_ms > 0]

    slo_p95_ms = 16000.0 if hardware_profile == "16GB" else 12000.0
    p95_total = round(_percentile(totals_ms, 95), 1)
    summary = {
        "mode": "dry-run" if dry_run else "live",
        "model": resolved_model,
        "hardware_profile": hardware_profile,
        "cases_total": total,
        "tool_accuracy_pct": round(100.0 * sum(1 for r in results if r.tool_hit) / max(1, total), 1),
        "args_valid_pct": round(100.0 * sum(1 for r in results if r.args_valid) / max(1, total), 1),
        "args_subset_pct": round(100.0 * sum(1 for r in results if r.args_subset_hit) / max(1, total), 1),
        "multi_subagent_accuracy_pct": round(
            100.0 * sum(1 for r in multi_res if r.tool_hit) / max(1, len(multi_res)), 1
        ),
        "narration_leakage_pct": round(
            100.0 * sum(1 for r in results if r.narration_leaked) / max(1, total), 1
        ),
        "numeric_hallucination_pct": round(
            100.0 * sum(1 for r in results if r.numeric_hallucination) / max(1, total), 1
        ),
        "think_leakage_pct": round(
            100.0 * sum(1 for r in results if r.think_leaked) / max(1, total), 1
        ),
        "latency_router_p50_ms": round(_percentile(router_lat, 50), 1),
        "latency_router_p95_ms": round(_percentile(router_lat, 95), 1),
        "latency_synth_p50_ms": round(_percentile(synth_lat, 50), 1),
        "latency_synth_p95_ms": round(_percentile(synth_lat, 95), 1),
        "latency_total_p50_ms": round(_percentile(totals_ms, 50), 1),
        "latency_total_p95_ms": p95_total,
        "slo_p95_target_ms": slo_p95_ms,
        "slo_passed": (dry_run or p95_total <= slo_p95_ms),
    }
    return {"summary": summary, "results": [asdict(r) for r in results]}


def _print_report(report: Dict[str, Any]) -> None:
    s = report["summary"]
    print("=" * 72)
    print(f"SEVALOR COPILOT v3.2 EVAL — mode={s['mode']} | model={s['model']} | HW={s['hardware_profile']}")
    print("=" * 72)
    print(f"Casos avaluats:           {s['cases_total']}")
    print(f"Precisió eines:           {s['tool_accuracy_pct']}%")
    print(f"Precisió multi-subagent:  {s['multi_subagent_accuracy_pct']}%")
    print(f"Arguments vàlids:         {s['args_valid_pct']}% (exacte: {s['args_subset_pct']}%)")
    print(f"Fuita narració d'eines:   {s['narration_leakage_pct']}% (objectiu: 0.0%)")
    print(f"Al·lucinació numèrica:    {s['numeric_hallucination_pct']}% (objectiu: 0.0%)")
    print(f"Fuita <think>:            {s['think_leakage_pct']}% (objectiu: 0.0%)")
    if s["mode"] == "live":
        print(
            f"Latència Router p50/p95:  {s['latency_router_p50_ms']} ms / {s['latency_router_p95_ms']} ms"
        )
        print(
            f"Latència Síntesi p50/p95: {s['latency_synth_p50_ms']} ms / {s['latency_synth_p95_ms']} ms"
        )
        print(
            f"Latència Total p50/p95:   {s['latency_total_p50_ms']} ms / {s['latency_total_p95_ms']} ms "
            f"(SLO <= {s['slo_p95_target_ms']} ms -> {'OK' if s['slo_passed'] else 'SUPERAT'})"
        )
    print("-" * 72)
    failures = [
        r
        for r in report["results"]
        if not r["tool_hit"] or r["narration_leaked"] or r["numeric_hallucination"] or r["error"]
    ]
    if failures:
        print(f"Incidències detectades ({len(failures)}):")
        for f in failures:
            print(
                f"  [{f['case_id']}] ({f['vertical']}/{f['rol']}) "
                f"subagents={f['selected_subagents']} pred={f['predicted_tools']} "
                f"narr={f['narration_leaked']} hall={f['numeric_hallucination']} err={f['error']}"
            )
    else:
        print("Tots els casos avaluats han passat sense incidències.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Benchmark i avaluació del Copilot v3.2 sobre models locals (LM Studio / Ollama)."
    )
    parser.add_argument(
        "--url",
        default="http://127.0.0.1:1234/v1",
        help="URL OpenAI-compatible del motor IA local (per defecte http://127.0.0.1:1234/v1).",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Identificador exacte del model a avaluar (si s'omet en mode live, detecta el primer carregat).",
    )
    parser.add_argument(
        "--hardware-profile",
        choices=("32GB", "16GB"),
        default="32GB",
        help="Perfil de maquinari del mini-PC dedicat (32GB o 16GB).",
    )
    parser.add_argument(
        "--vertical",
        default=None,
        help="Filtra només una vertical (CAMPOPRO, ELECTRICPRO, HYDROPRO, BUILDINGPRO).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limita el nombre de casos executats (útil per proves ràpides).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Valida encaminament, allowlists i RBAC dels 36 casos sense cridar LM Studio.",
    )
    parser.add_argument(
        "--output-json",
        default=None,
        help="Desa l'informe complet JSON al fitxer indicat per comparar models.",
    )
    args = parser.parse_args()

    report = asyncio.run(
        run_evaluation(
            dry_run=args.dry_run,
            base_url=args.url,
            model=args.model,
            hardware_profile=args.hardware_profile,
            vertical_filter=args.vertical,
            limit=args.limit,
        )
    )
    _print_report(report)
    if args.output_json:
        out_path = Path(args.output_json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Informe JSON desat a: {out_path}")

    s = report["summary"]
    return 0 if (s["tool_accuracy_pct"] >= 85.0 and s["narration_leakage_pct"] == 0.0) else 1


if __name__ == "__main__":
    sys.exit(main())
