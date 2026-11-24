"""Esquemes de crida d'eines generats automàticament des de la font única Pydantic (`tools_registry.py`)."""

from typing import Any, Dict, List

from app.services.subagents.tools_registry import (
    TOOL_REGISTRY,
    get_openai_tools_for_subagent,
    to_openai_tool,
)

# ── 1. Peritatge Tècnic de Camp ──────────────────────────────────────────────
SCHEMA_GET_WARRANTY_STATUS: Dict[str, Any] = to_openai_tool(TOOL_REGISTRY["get_warranty_status"])
SCHEMA_GENERAR_MEMORANDUM_TECNIC: Dict[str, Any] = to_openai_tool(
    TOOL_REGISTRY["generar_memorandum_tecnic"]
)
SCHEMAS_PERITATGE_CAMP: List[Dict[str, Any]] = get_openai_tools_for_subagent(
    "subagent_peritatge_camp"
)

# ── 2. Logística i Magatzem ──────────────────────────────────────────────────
SCHEMA_GET_REAL_STOCK: Dict[str, Any] = to_openai_tool(TOOL_REGISTRY["get_real_stock"])
SCHEMA_GET_EINES_STOCK: Dict[str, Any] = to_openai_tool(TOOL_REGISTRY["get_eines_stock"])
SCHEMA_CHECK_ALLOCATION_SAFETY: Dict[str, Any] = to_openai_tool(
    TOOL_REGISTRY["check_allocation_safety"]
)
SCHEMA_PROPOSE_PURCHASE_ORDER: Dict[str, Any] = to_openai_tool(
    TOOL_REGISTRY["propose_purchase_order"]
)
SCHEMA_REPLANIFICAR_OT: Dict[str, Any] = to_openai_tool(TOOL_REGISTRY["replanificar_ot"])
SCHEMA_GET_STOCK_MOVEMENTS: Dict[str, Any] = to_openai_tool(TOOL_REGISTRY["get_stock_movements"])
SCHEMA_GET_LOW_STOCK_ALERTS: Dict[str, Any] = to_openai_tool(TOOL_REGISTRY["get_low_stock_alerts"])
SCHEMA_GET_SUPPLIER_DOCS: Dict[str, Any] = to_openai_tool(TOOL_REGISTRY["get_supplier_docs"])
SCHEMAS_LOGISTICA_ESTOC: List[Dict[str, Any]] = get_openai_tools_for_subagent(
    "subagent_logistica_estoc"
)

# ── 3. Flota i Desplaçaments ─────────────────────────────────────────────────
SCHEMA_GET_CLOSEST_VEHICLE: Dict[str, Any] = to_openai_tool(TOOL_REGISTRY["get_closest_vehicle"])
SCHEMA_GET_VEHICLE_INFO: Dict[str, Any] = to_openai_tool(TOOL_REGISTRY["get_vehicle_info"])
SCHEMA_AUDIT_ITV_INSURANCE_FLEET: Dict[str, Any] = to_openai_tool(
    TOOL_REGISTRY["audit_itv_insurance_fleet"]
)
SCHEMA_GET_HEAVY_VEHICLES_FOR_OT: Dict[str, Any] = to_openai_tool(
    TOOL_REGISTRY["get_heavy_vehicles_for_ot"]
)
SCHEMA_GET_FLEET_STATUS: Dict[str, Any] = to_openai_tool(TOOL_REGISTRY["get_fleet_status"])
SCHEMA_GET_VEHICLE_MAINTENANCE: Dict[str, Any] = to_openai_tool(
    TOOL_REGISTRY["get_vehicle_maintenance"]
)
SCHEMA_GET_FUEL_CONSUMPTION: Dict[str, Any] = to_openai_tool(TOOL_REGISTRY["get_fuel_consumption"])
SCHEMAS_FLOTA_DESPATX: List[Dict[str, Any]] = get_openai_tools_for_subagent(
    "subagent_flota_despatx"
)

# ── 4. Auditoria Financer i Rendibilitat (BOSS Only) ─────────────────────────
SCHEMA_GET_UNBILLED_MONEY: Dict[str, Any] = to_openai_tool(TOOL_REGISTRY["get_unbilled_money"])
SCHEMA_RECONCILE_POST_OBRA: Dict[str, Any] = to_openai_tool(TOOL_REGISTRY["reconcile_post_obra"])
SCHEMA_DETECT_MARGIN_LEAK: Dict[str, Any] = to_openai_tool(TOOL_REGISTRY["detect_margin_leak"])
SCHEMAS_AUDITORIA_MARGE: List[Dict[str, Any]] = get_openai_tools_for_subagent(
    "subagent_auditoria_marge"
)

# ── 5. OCR i Digitalització de Documents (Zero fitxer_path) ──────────────────
SCHEMA_EXTRACT_ALBARA_LINES: Dict[str, Any] = to_openai_tool(TOOL_REGISTRY["extract_albara_lines"])
SCHEMA_EXTRACT_VEHICLE_TECH_CARD: Dict[str, Any] = to_openai_tool(
    TOOL_REGISTRY["extract_vehicle_tech_card"]
)
SCHEMA_EXTRACT_FUEL_RECEIPT: Dict[str, Any] = to_openai_tool(TOOL_REGISTRY["extract_fuel_receipt"])
SCHEMA_EXTRACT_CLIENTS_CSV: Dict[str, Any] = to_openai_tool(TOOL_REGISTRY["extract_clients_csv"])
SCHEMAS_OCR_VISION: List[Dict[str, Any]] = get_openai_tools_for_subagent("subagent_ocr_vision")

# ── 6. Client Final & Canal Telegram (Zero import_total al LLM) ──────────────
SCHEMA_NOTIFY_TECHNICIAN_ARRIVAL: Dict[str, Any] = to_openai_tool(
    TOOL_REGISTRY["notify_technician_arrival"]
)
SCHEMA_SEND_INTERACTIVE_BUDGET: Dict[str, Any] = to_openai_tool(
    TOOL_REGISTRY["send_interactive_budget"]
)
SCHEMA_RECEIVE_CLIENT_MEDIA: Dict[str, Any] = to_openai_tool(TOOL_REGISTRY["receive_client_media"])
SCHEMAS_CLIENT_TELEGRAM: List[Dict[str, Any]] = get_openai_tools_for_subagent(
    "subagent_client_telegram"
)

# ── 7. RAG Corporatiu, Clients i Finques ─────────────────────────────────────
SCHEMA_GET_RAG_KNOWLEDGE: Dict[str, Any] = to_openai_tool(TOOL_REGISTRY["get_rag_knowledge"])
SCHEMA_GET_CLIENT_HISTORY: Dict[str, Any] = to_openai_tool(TOOL_REGISTRY["get_client_history"])
SCHEMA_SEARCH_CLIENTS: Dict[str, Any] = to_openai_tool(TOOL_REGISTRY["search_clients"])
SCHEMA_GET_FINCA_DETAIL: Dict[str, Any] = to_openai_tool(TOOL_REGISTRY["get_finca_detail"])
SCHEMA_GET_PENDING_BUDGETS: Dict[str, Any] = to_openai_tool(TOOL_REGISTRY["get_pending_budgets"])
SCHEMA_GET_TOOLS_CUSTODY: Dict[str, Any] = to_openai_tool(TOOL_REGISTRY["get_tools_custody"])
SCHEMAS_GENERAL_RAG: List[Dict[str, Any]] = get_openai_tools_for_subagent("subagent_general_rag")

# ── 8. Planificació, Agenda i Equip de Treball ───────────────────────────────
SCHEMA_GET_WORK_ORDERS: Dict[str, Any] = to_openai_tool(TOOL_REGISTRY["get_work_orders"])
SCHEMA_GET_WORK_ORDER_DETAIL: Dict[str, Any] = to_openai_tool(
    TOOL_REGISTRY["get_work_order_detail"]
)
SCHEMA_GET_TEAM_TODAY: Dict[str, Any] = to_openai_tool(TOOL_REGISTRY["get_team_today"])
SCHEMA_GET_TIMESHEET: Dict[str, Any] = to_openai_tool(TOOL_REGISTRY["get_timesheet"])
SCHEMA_GET_OPEN_INCIDENTS: Dict[str, Any] = to_openai_tool(TOOL_REGISTRY["get_open_incidents"])
SCHEMAS_PLANIFICACIO_EQUIP: List[Dict[str, Any]] = get_openai_tools_for_subagent(
    "subagent_planificacio_equip"
)
