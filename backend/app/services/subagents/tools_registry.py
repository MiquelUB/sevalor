"""Font única de veritat (Pydantic v2) per a totes les eines dels subagents de Sevalor Suite (FR-022).

Garanteix:
- Paritat estricta entre esquema JSON del LLM i handlers reals (`test_tool_contract.py`).
- Control RBAC declaratiu (`allowed_roles`) per a cada eina.
- Prohibició d'arguments perillosos (`fitxer_path`, `import_total`, etc.).
- Esquemes JSON aplanats sense `$defs`/`$ref` compatibles amb GBNF de LM Studio (`llama.cpp`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, List, Literal, Optional, Sequence, Type

from pydantic import BaseModel, ConfigDict, Field

from app.services.llm_utils import sanitize_llm_text

# Arguments estrictament prohibits en qualsevol esquema exposat al LLM (OWASP LLM01/LLM05/LLM06)
FORBIDDEN_LLM_ARG_NAMES: FrozenSet[str] = frozenset(
    {
        "fitxer_path",
        "file_path",
        "filepath",
        "path",
        "import_total",
        "preu_cost",
        "preu_unitari",
        "cost_hora",
    }
)

ROLES_GESTIO_I_CAMP: FrozenSet[str] = frozenset(
    {"BOSS", "ADMIN", "ENGINYER", "SECRETARIA", "CAP_DE_MAGATZEM", "OPERARI", "CAP_DE_COLLA"}
)
ROLES_PERITATGE: FrozenSet[str] = frozenset(
    {"OPERARI", "CAP_DE_COLLA", "ENGINYER", "BOSS", "ADMIN"}
)
ROLES_BOSS_ONLY: FrozenSet[str] = frozenset({"BOSS", "ADMIN"})
ROLES_TELEGRAM: FrozenSet[str] = frozenset(
    {"CLIENT_FINAL", "SECRETARIA", "ENGINYER", "BOSS", "ADMIN"}
)


class _StrictToolArgs(BaseModel):
    """Classe base per a tots els models d'arguments d'eines del Copilot."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)


# ── 1. Peritatge Tècnic de Camp ──────────────────────────────────────────────
class GetWarrantyStatusArgs(_StrictToolArgs):
    finca_nom: Optional[str] = Field(
        default=None,
        max_length=160,
        description="Nom de la finca o instal·lació",
    )
    client_nom: Optional[str] = Field(
        default=None,
        max_length=160,
        description="Nom o raó social del client",
    )
    numero_serie: Optional[str] = Field(
        default=None,
        max_length=120,
        description="Número de sèrie de l'equip o maquinària",
    )


class GenerarMemorandumTecnicArgs(_StrictToolArgs):
    descripcio_avaria: str = Field(
        min_length=3,
        max_length=2000,
        description="Descripció tècnica de l'avaria o incidència observada",
    )
    codi_ot: Optional[str] = Field(
        default=None,
        max_length=64,
        description="Codi de l'ordre de treball relacionada (ex: 'OT-2026-001')",
    )


# ── 2. Logística i Magatzem ──────────────────────────────────────────────────
class GetRealStockArgs(_StrictToolArgs):
    article_ref: str = Field(
        default="",
        max_length=160,
        description="Nom, família o referència de l'article (buit per consultar rànquing general del magatzem)",
    )
    ordenar_per: Literal["rellevancia", "menor_estoc", "major_estoc"] = Field(
        default="rellevancia",
        description="Criteri d'ordenació: 'menor_estoc' per trobar materials amb menys unitats",
    )
    limit: int = Field(
        default=15,
        ge=1,
        le=50,
        description="Nombre màxim d'articles a retornar",
    )


class GetEinesStockArgs(_StrictToolArgs):
    terme_cerca: Optional[str] = Field(
        default=None,
        max_length=120,
        description="Nom, model o tipus d'eina o maquinària (buit retorna totes les eines)",
    )


class CheckAllocationSafetyArgs(_StrictToolArgs):
    article_ref: str = Field(min_length=1, max_length=160, description="Referència o nom de l'article")
    quantitat: float = Field(gt=0, description="Quantitat prevista a reservar o consumir")


class ProposePurchaseOrderArgs(_StrictToolArgs):
    article_ref: str = Field(min_length=1, max_length=160, description="Referència o nom de l'article a comprar")
    quantitat: float = Field(gt=0, description="Quantitat suggerida a comprar")


class ReplanificarOtArgs(_StrictToolArgs):
    codi_ot: str = Field(min_length=2, max_length=64, description="Codi de l'Ordre de Treball (ex: 'OT-2026-001')")
    nova_data: str = Field(min_length=8, max_length=32, description="Nova data en format YYYY-MM-DD")


class GetStockMovementsArgs(_StrictToolArgs):
    article_ref: Optional[str] = Field(
        default=None,
        max_length=160,
        description="Nom o referència de l'article (opcional)",
    )
    limit: int = Field(default=10, ge=1, le=50, description="Nombre màxim de moviments")


class GetLowStockAlertsArgs(_StrictToolArgs):
    familia: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Filtre opcional per família de material",
    )


class GetSupplierDocsArgs(_StrictToolArgs):
    proveidor_nom: Optional[str] = Field(
        default=None,
        max_length=160,
        description="Nom o raó social del proveïdor (opcional)",
    )
    tipus: Optional[str] = Field(
        default=None,
        max_length=40,
        description="Tipus de document opcional ('albara' o 'factura')",
    )
    limit: int = Field(default=5, ge=1, le=20, description="Nombre màxim de documents")


# ── 3. Flota i Desplaçaments ─────────────────────────────────────────────────
class GetClosestVehicleArgs(_StrictToolArgs):
    lat: float = Field(ge=-90.0, le=90.0, description="Latitud geogràfica")
    lng: float = Field(ge=-180.0, le=180.0, description="Longitud geogràfica")


class GetVehicleInfoArgs(_StrictToolArgs):
    matricula: str = Field(min_length=3, max_length=32, description="Matrícula del vehicle (ex: '1234-XYZ')")


class AuditItvInsuranceFleetArgs(_StrictToolArgs):
    dies_marge: int = Field(default=30, ge=1, le=365, description="Marge de dies cap al futur")


class GetHeavyVehiclesForOtArgs(_StrictToolArgs):
    carrega_minima_kg: Optional[int] = Field(default=None, ge=0, le=100000, description="Càrrega útil mínima en kg")
    equipament: Optional[str] = Field(
        default=None,
        max_length=80,
        description="Equipament homologat (ex: 'GRUA_AUTOCARGANT', 'ENGANXALL_REMOLC')",
    )
    categoria_ue: Optional[str] = Field(default=None, max_length=16, description="Categoria UE (ex: 'N1', 'N2', 'N3')")


class GetFleetStatusArgs(_StrictToolArgs):
    filtres_estat: Optional[str] = Field(
        default=None,
        max_length=40,
        description="Filtre opcional d'estat ('EN_RUTA', 'ASSIGNAT', 'DISPONIBLE')",
    )


class GetVehicleMaintenanceArgs(_StrictToolArgs):
    matricula: Optional[str] = Field(default=None, max_length=32, description="Matrícula del vehicle")
    limit: int = Field(default=5, ge=1, le=20, description="Nombre màxim de registres")


class GetFuelConsumptionArgs(_StrictToolArgs):
    matricula: Optional[str] = Field(default=None, max_length=32, description="Matrícula opcional del vehicle")


# ── 4. Auditoria Financer i Rendibilitat (BOSS Only) ─────────────────────────
class GetUnbilledMoneyArgs(_StrictToolArgs):
    mes: Optional[int] = Field(default=None, ge=1, le=12, description="Mes a auditar (1-12)")
    any: Optional[int] = Field(default=None, ge=2020, le=2100, description="Any a auditar (ex: 2026)")


class ReconcilePostObraArgs(_StrictToolArgs):
    codi_ot: str = Field(min_length=2, max_length=64, description="Codi de l'ordre de treball (ex: 'OT-2026-001')")


class DetectMarginLeakArgs(_StrictToolArgs):
    codi_ot: Optional[str] = Field(
        default=None,
        max_length=64,
        description="Codi opcional d'una OT concreta (buit audita totes les obres amb auditoria)",
    )


# ── 5. OCR i Digitalització (Zero fitxer_path al LLM!) ───────────────────────
class ExtractOcrTextArgs(_StrictToolArgs):
    text_ocr: str = Field(
        default="",
        max_length=8000,
        description="Text del document adjuntat o enganxat per l'usuari (mai rutes de disc)",
    )


# ── 6. Client Final & Canal Telegram (Zero import_total al LLM!) ─────────────
class NotifyTechnicianArrivalArgs(_StrictToolArgs):
    codi_ot: str = Field(min_length=2, max_length=64, description="Codi de l'ordre de treball (ex: 'OT-2026-001')")
    minuts_estimats: int = Field(default=15, ge=1, le=240, description="Temps estimat d'arribada en minuts")


class SendInteractiveBudgetArgs(_StrictToolArgs):
    numero_pressupost: Optional[str] = Field(
        default=None,
        max_length=64,
        description="Número de pressupost existent al disc (ex: 'PRES-2026-045')",
    )
    client_nom: Optional[str] = Field(
        default=None,
        max_length=160,
        description="Nom o raó social del client receptor",
    )


class ReceiveClientMediaArgs(_StrictToolArgs):
    client_nom: str = Field(min_length=2, max_length=160, description="Nom o raó social del client")
    descripcio: str = Field(default="", max_length=500, description="Comentari sobre la fotografia o arxiu")


# ── 7. RAG Corporatiu, Clients i Finques ─────────────────────────────────────
class GetRagKnowledgeArgs(_StrictToolArgs):
    query: str = Field(min_length=2, max_length=300, description="Paraules clau del protocol o normativa")


class GetClientHistoryArgs(_StrictToolArgs):
    client_nom: str = Field(min_length=2, max_length=160, description="Nom o raó social del client")


class SearchClientsArgs(_StrictToolArgs):
    terme: str = Field(min_length=1, max_length=160, description="Nom, raó social, NIF o codi del client")
    limit: int = Field(default=5, ge=1, le=20, description="Nombre màxim de resultats")


class GetFincaDetailArgs(_StrictToolArgs):
    finca_nom_o_id: str = Field(min_length=1, max_length=160, description="Nom o adreça de la finca o parcel·la")


class GetPendingBudgetsArgs(_StrictToolArgs):
    client_nom: Optional[str] = Field(default=None, max_length=160, description="Nom opcional del client")
    limit: int = Field(default=5, ge=1, le=20, description="Nombre màxim de pressupostos")


class GetToolsCustodyArgs(_StrictToolArgs):
    operari_nom: Optional[str] = Field(default=None, max_length=160, description="Nom opcional de l'operari")
    limit: int = Field(default=10, ge=1, le=30, description="Nombre màxim d'eines")


# ── 8. Planificació, Agenda i Equip de Treball ───────────────────────────────
class GetWorkOrdersArgs(_StrictToolArgs):
    data: Optional[str] = Field(default=None, max_length=32, description="Data YYYY-MM-DD o 'avui'")
    estat: Optional[str] = Field(
        default=None,
        max_length=32,
        description="Estat ('PENDENT', 'ASSIGNADA', 'EN_CURS', 'COMPLETADA')",
    )
    operari_nom: Optional[str] = Field(default=None, max_length=120, description="Nom de l'operari assignat")
    limit: int = Field(default=10, ge=1, le=50, description="Nombre màxim d'ordres")


class GetWorkOrderDetailArgs(_StrictToolArgs):
    codi_ot: str = Field(min_length=2, max_length=64, description="Codi de l'ordre de treball (ex: 'OT-2026-001')")


class GetTeamTodayArgs(_StrictToolArgs):
    pass


class GetTimesheetArgs(_StrictToolArgs):
    data: Optional[str] = Field(default=None, max_length=32, description="Data YYYY-MM-DD o 'avui'")
    operari_nom: Optional[str] = Field(default=None, max_length=120, description="Nom de l'operari")


class GetOpenIncidentsArgs(_StrictToolArgs):
    codi_ot: Optional[str] = Field(default=None, max_length=64, description="Codi opcional de l'OT")


@dataclass(frozen=True)
class ToolSpec:
    """Definició canònica única d'una eina d'un subagent."""

    name: str
    subagent_id: str
    description: str
    args_model: Type[BaseModel]
    handler_method: str
    allowed_roles: FrozenSet[str]
    is_hitl_action: bool = False


TOOL_REGISTRY: Dict[str, ToolSpec] = {
    # 1. Peritatge de Camp
    "get_warranty_status": ToolSpec(
        name="get_warranty_status",
        subagent_id="subagent_peritatge_camp",
        description="Audita si una finca, client o equip té garantia oficial o de mà d'obra vigent (<90 dies).",
        args_model=GetWarrantyStatusArgs,
        handler_method="tool_get_warranty_status",
        allowed_roles=ROLES_PERITATGE,
    ),
    "generar_memorandum_tecnic": ToolSpec(
        name="generar_memorandum_tecnic",
        subagent_id="subagent_peritatge_camp",
        description="Genera proposta de memoràndum tècnic d'avaria (EXTRA_FACTURABLE o COST_NO_IMPUTABLE) per a revisió humana.",
        args_model=GenerarMemorandumTecnicArgs,
        handler_method="tool_generar_memorandum_tecnic",
        allowed_roles=ROLES_PERITATGE,
        is_hitl_action=True,
    ),
    # 2. Logística i Magatzem
    "get_real_stock": ToolSpec(
        name="get_real_stock",
        subagent_id="subagent_logistica_estoc",
        description="Consulta l'estoc disponible d'articles consumibles al magatzem o el rànquing de materials amb menor/major estoc.",
        args_model=GetRealStockArgs,
        handler_method="tool_get_real_stock",
        allowed_roles=ROLES_GESTIO_I_CAMP,
    ),
    "get_eines_stock": ToolSpec(
        name="get_eines_stock",
        subagent_id="subagent_logistica_estoc",
        description="Consulta l'estat, custodi i ubicació d'eines, maquinària i equips de treball.",
        args_model=GetEinesStockArgs,
        handler_method="tool_get_eines_stock",
        allowed_roles=ROLES_GESTIO_I_CAMP,
    ),
    "check_allocation_safety": ToolSpec(
        name="check_allocation_safety",
        subagent_id="subagent_logistica_estoc",
        description="Avalua si consumir una quantitat d'un material deixarà l'estoc sota el mínim de seguretat.",
        args_model=CheckAllocationSafetyArgs,
        handler_method="tool_check_allocation_safety",
        allowed_roles=ROLES_GESTIO_I_CAMP,
    ),
    "propose_purchase_order": ToolSpec(
        name="propose_purchase_order",
        subagent_id="subagent_logistica_estoc",
        description="Genera proposta d'esborrany de comanda de compra de reposició (HITL).",
        args_model=ProposePurchaseOrderArgs,
        handler_method="tool_propose_purchase_order",
        allowed_roles=ROLES_GESTIO_I_CAMP,
        is_hitl_action=True,
    ),
    "replanificar_ot": ToolSpec(
        name="replanificar_ot",
        subagent_id="subagent_logistica_estoc",
        description="Proposa re-planificar una ordre de treball a una nova data (requereix confirmació HITL).",
        args_model=ReplanificarOtArgs,
        handler_method="tool_replanificar_ot",
        allowed_roles=ROLES_GESTIO_I_CAMP,
        is_hitl_action=True,
    ),
    "get_stock_movements": ToolSpec(
        name="get_stock_movements",
        subagent_id="subagent_logistica_estoc",
        description="Consulta l'historial recent d'entrades, sortides i pickings d'estoc d'un article o del magatzem.",
        args_model=GetStockMovementsArgs,
        handler_method="tool_get_stock_movements",
        allowed_roles=ROLES_GESTIO_I_CAMP,
    ),
    "get_low_stock_alerts": ToolSpec(
        name="get_low_stock_alerts",
        subagent_id="subagent_logistica_estoc",
        description="Obté els articles per sota de l'estoc mínim de seguretat o en ruptura d'inventari.",
        args_model=GetLowStockAlertsArgs,
        handler_method="tool_get_low_stock_alerts",
        allowed_roles=ROLES_GESTIO_I_CAMP,
    ),
    "get_supplier_docs": ToolSpec(
        name="get_supplier_docs",
        subagent_id="subagent_logistica_estoc",
        description="Consulta albarans o factures de proveïdors registrats al disc de l'empresa.",
        args_model=GetSupplierDocsArgs,
        handler_method="tool_get_supplier_docs",
        allowed_roles=ROLES_GESTIO_I_CAMP,
    ),
    # 3. Flota i Desplaçaments
    "get_closest_vehicle": ToolSpec(
        name="get_closest_vehicle",
        subagent_id="subagent_flota_despatx",
        description="Localitza el vehicle més proper a unes coordenades GPS mitjançant Haversine.",
        args_model=GetClosestVehicleArgs,
        handler_method="tool_get_closest_vehicle",
        allowed_roles=ROLES_GESTIO_I_CAMP,
    ),
    "get_vehicle_info": ToolSpec(
        name="get_vehicle_info",
        subagent_id="subagent_flota_despatx",
        description="Consulta dades tècniques, odòmetre, ITV i assegurança d'un vehicle per matrícula.",
        args_model=GetVehicleInfoArgs,
        handler_method="tool_get_vehicle_info",
        allowed_roles=ROLES_GESTIO_I_CAMP,
    ),
    "audit_itv_insurance_fleet": ToolSpec(
        name="audit_itv_insurance_fleet",
        subagent_id="subagent_flota_despatx",
        description="Audita venciments imminents d'ITV, assegurança, rènting i tacògraf de la flota.",
        args_model=AuditItvInsuranceFleetArgs,
        handler_method="tool_audit_itv_insurance_fleet",
        allowed_roles=ROLES_GESTIO_I_CAMP,
    ),
    "get_heavy_vehicles_for_ot": ToolSpec(
        name="get_heavy_vehicles_for_ot",
        subagent_id="subagent_flota_despatx",
        description="Filtra vehicles pesants o especials per equipament homologat, càrrega útil o categoria UE.",
        args_model=GetHeavyVehiclesForOtArgs,
        handler_method="tool_get_heavy_vehicles_for_ot",
        allowed_roles=ROLES_GESTIO_I_CAMP,
    ),
    "get_fleet_status": ToolSpec(
        name="get_fleet_status",
        subagent_id="subagent_flota_despatx",
        description="Consulta l'estat de tots els vehicles de la flota: en ruta, assignats a operaris o disponibles.",
        args_model=GetFleetStatusArgs,
        handler_method="tool_get_fleet_status",
        allowed_roles=ROLES_GESTIO_I_CAMP,
    ),
    "get_vehicle_maintenance": ToolSpec(
        name="get_vehicle_maintenance",
        subagent_id="subagent_flota_despatx",
        description="Consulta l'historial de manteniments i reparacions d'un vehicle o de la flota.",
        args_model=GetVehicleMaintenanceArgs,
        handler_method="tool_get_vehicle_maintenance",
        allowed_roles=ROLES_GESTIO_I_CAMP,
    ),
    "get_fuel_consumption": ToolSpec(
        name="get_fuel_consumption",
        subagent_id="subagent_flota_despatx",
        description="Consulta registres de carburant, litres i recàrregues de la flota o d'un vehicle.",
        args_model=GetFuelConsumptionArgs,
        handler_method="tool_get_fuel_consumption",
        allowed_roles=ROLES_GESTIO_I_CAMP,
    ),
    # 4. Auditoria Financer i Marge (BOSS Only)
    "get_unbilled_money": ToolSpec(
        name="get_unbilled_money",
        subagent_id="subagent_auditoria_marge",
        description="Calcula imports de treballs tancats pendents de facturar (exclusiu Direcció).",
        args_model=GetUnbilledMoneyArgs,
        handler_method="tool_get_unbilled_money",
        allowed_roles=ROLES_BOSS_ONLY,
    ),
    "reconcile_post_obra": ToolSpec(
        name="reconcile_post_obra",
        subagent_id="subagent_auditoria_marge",
        description="Consulta la conciliació financera post-obra i desviació de marge d'una OT (exclusiu Direcció).",
        args_model=ReconcilePostObraArgs,
        handler_method="tool_reconcile_post_obra",
        allowed_roles=ROLES_BOSS_ONLY,
    ),
    "detect_margin_leak": ToolSpec(
        name="detect_margin_leak",
        subagent_id="subagent_auditoria_marge",
        description="Detecta fuites de marge o mermes operatives en una OT o al conjunt d'obres (exclusiu Direcció).",
        args_model=DetectMarginLeakArgs,
        handler_method="tool_detect_margin_leak",
        allowed_roles=ROLES_BOSS_ONLY,
    ),
    # 5. OCR i Digitalització (Zero fitxer_path)
    "extract_albara_lines": ToolSpec(
        name="extract_albara_lines",
        subagent_id="subagent_ocr_vision",
        description="Extreu dades estructurades del text d'un albarà de proveïdor i prepara esborrany HITL.",
        args_model=ExtractOcrTextArgs,
        handler_method="tool_extract_albara_lines",
        allowed_roles=ROLES_GESTIO_I_CAMP,
        is_hitl_action=True,
    ),
    "extract_vehicle_tech_card": ToolSpec(
        name="extract_vehicle_tech_card",
        subagent_id="subagent_ocr_vision",
        description="Extreu matrícula i bastidor VIN del text d'una fitxa tècnica de vehicle.",
        args_model=ExtractOcrTextArgs,
        handler_method="tool_extract_vehicle_tech_card",
        allowed_roles=ROLES_GESTIO_I_CAMP,
    ),
    "extract_fuel_receipt": ToolSpec(
        name="extract_fuel_receipt",
        subagent_id="subagent_ocr_vision",
        description="Extreu litres i import del text d'un tiquet de carburant i prepara esborrany HITL.",
        args_model=ExtractOcrTextArgs,
        handler_method="tool_extract_fuel_receipt",
        allowed_roles=ROLES_GESTIO_I_CAMP,
        is_hitl_action=True,
    ),
    # 6. Client Final & Canal Telegram (Zero import_total al LLM)
    "notify_technician_arrival": ToolSpec(
        name="notify_technician_arrival",
        subagent_id="subagent_client_telegram",
        description="Prepara una notificació d'arribada d'operaris per Telegram vinculada a una OT (HITL).",
        args_model=NotifyTechnicianArrivalArgs,
        handler_method="tool_notify_technician_arrival",
        allowed_roles=ROLES_TELEGRAM,
        is_hitl_action=True,
    ),
    "send_interactive_budget": ToolSpec(
        name="send_interactive_budget",
        subagent_id="subagent_client_telegram",
        description="Prepara l'enviament per Telegram d'un pressupost verificat existent al disc (HITL).",
        args_model=SendInteractiveBudgetArgs,
        handler_method="tool_send_interactive_budget",
        allowed_roles=ROLES_TELEGRAM,
        is_hitl_action=True,
    ),
    "receive_client_media": ToolSpec(
        name="receive_client_media",
        subagent_id="subagent_client_telegram",
        description="Registra una fotografia o incidència multimèdia d'un client identificat pel nom.",
        args_model=ReceiveClientMediaArgs,
        handler_method="tool_receive_client_media",
        allowed_roles=ROLES_TELEGRAM,
    ),
    # 7. RAG Corporatiu, Clients i Finques
    "get_rag_knowledge": ToolSpec(
        name="get_rag_knowledge",
        subagent_id="subagent_general_rag",
        description=(
            "Cerca procediments interns, manuals tècnics, normatives i guies d'ús del panell de gestió "
            "(com donar d'alta clients, vehicles, operaris, articles, crear OTs, pressupostos, facturar, etc.). "
            "Usa-la SEMPRE per preguntes de «com es fa», «com donar d'alta» o «on es configura»."
        ),
        args_model=GetRagKnowledgeArgs,
        handler_method="tool_get_rag_knowledge",
        allowed_roles=ROLES_GESTIO_I_CAMP,
    ),
    "get_client_history": ToolSpec(
        name="get_client_history",
        subagent_id="subagent_general_rag",
        description="Recopila l'historial d'intervencions dels darrers 365 dies d'un client pel seu nom.",
        args_model=GetClientHistoryArgs,
        handler_method="tool_get_client_history",
        allowed_roles=ROLES_GESTIO_I_CAMP,
    ),
    "search_clients": ToolSpec(
        name="search_clients",
        subagent_id="subagent_general_rag",
        description=(
            "Cerca fitxes de clients reals existents per nom, NIF o població al directori corporatiu. "
            "NO usar per preguntes de procediment o ajuda com «com donar d'alta un client»."
        ),
        args_model=SearchClientsArgs,
        handler_method="tool_search_clients",
        allowed_roles=ROLES_GESTIO_I_CAMP,
    ),
    "get_finca_detail": ToolSpec(
        name="get_finca_detail",
        subagent_id="subagent_general_rag",
        description="Obté adreça, SIGPAC, referència cadastral i dades tècniques d'una finca o parcel·la.",
        args_model=GetFincaDetailArgs,
        handler_method="tool_get_finca_detail",
        allowed_roles=ROLES_GESTIO_I_CAMP,
    ),
    "get_pending_budgets": ToolSpec(
        name="get_pending_budgets",
        subagent_id="subagent_general_rag",
        description="Consulta pressupostos pendents d'aprovació (filtrable per nom de client).",
        args_model=GetPendingBudgetsArgs,
        handler_method="tool_get_pending_budgets",
        allowed_roles=ROLES_GESTIO_I_CAMP,
    ),
    "get_tools_custody": ToolSpec(
        name="get_tools_custody",
        subagent_id="subagent_general_rag",
        description="Consulta eines i equips en custòdia assignats a operaris o al magatzem.",
        args_model=GetToolsCustodyArgs,
        handler_method="tool_get_tools_custody",
        allowed_roles=ROLES_GESTIO_I_CAMP,
    ),
    # 8. Planificació, Agenda i Equip de Treball
    "get_work_orders": ToolSpec(
        name="get_work_orders",
        subagent_id="subagent_planificacio_equip",
        description="Consulta la llista d'ordres de treball per data, estat o operari assignat.",
        args_model=GetWorkOrdersArgs,
        handler_method="tool_get_work_orders",
        allowed_roles=ROLES_GESTIO_I_CAMP,
    ),
    "get_work_order_detail": ToolSpec(
        name="get_work_order_detail",
        subagent_id="subagent_planificacio_equip",
        description="Obté el detall complet d'una ordre de treball (client, finca, estat, vehicle i picking).",
        args_model=GetWorkOrderDetailArgs,
        handler_method="tool_get_work_order_detail",
        allowed_roles=ROLES_GESTIO_I_CAMP,
    ),
    "get_team_today": ToolSpec(
        name="get_team_today",
        subagent_id="subagent_planificacio_equip",
        description="Consulta la plantilla total de treballadors i l'estat de jornada/fitxatge d'avui.",
        args_model=GetTeamTodayArgs,
        handler_method="tool_get_team_today",
        allowed_roles=ROLES_GESTIO_I_CAMP,
    ),
    "get_timesheet": ToolSpec(
        name="get_timesheet",
        subagent_id="subagent_planificacio_equip",
        description="Consulta els registres de jornada laboral i hores fitxades per data o operari.",
        args_model=GetTimesheetArgs,
        handler_method="tool_get_timesheet",
        allowed_roles=ROLES_GESTIO_I_CAMP,
    ),
    "get_open_incidents": ToolSpec(
        name="get_open_incidents",
        subagent_id="subagent_planificacio_equip",
        description="Consulta les incidències tècniques obertes a les feines o vehicles.",
        args_model=GetOpenIncidentsArgs,
        handler_method="tool_get_open_incidents",
        allowed_roles=ROLES_GESTIO_I_CAMP,
    ),
}


def _simplify_schema_node(node: Any, defs: Dict[str, Any]) -> Any:
    """Resol `$ref`, elimina `title` i aplana `anyOf: [T, null]` per compatibilitat estricta amb GBNF."""
    if isinstance(node, list):
        return [_simplify_schema_node(item, defs) for item in node]
    if not isinstance(node, dict):
        return node

    if "$ref" in node:
        ref_name = str(node["$ref"]).rsplit("/", 1)[-1]
        resolved = defs.get(ref_name, {})
        merged = {**resolved, **{k: v for k, v in node.items() if k != "$ref"}}
        return _simplify_schema_node(merged, defs)

    out: Dict[str, Any] = {}
    if "anyOf" in node and isinstance(node["anyOf"], list):
        non_null = [
            opt for opt in node["anyOf"] if not (isinstance(opt, dict) and opt.get("type") == "null")
        ]
        if len(non_null) == 1:
            base = _simplify_schema_node(non_null[0], defs)
            if isinstance(base, dict):
                out.update(base)
        else:
            out["anyOf"] = [_simplify_schema_node(opt, defs) for opt in non_null]

    for k, v in node.items():
        if k in ("$defs", "title", "anyOf", "default"):
            continue
        if k == "properties" and isinstance(v, dict):
            out["properties"] = {pk: _simplify_schema_node(pv, defs) for pk, pv in v.items()}
        elif k == "items":
            out["items"] = _simplify_schema_node(v, defs)
        else:
            out[k] = v

    if out.get("type") == "object":
        out.setdefault("properties", {})
        out["additionalProperties"] = False
    return out


def inline_strict_schema(model: Type[BaseModel]) -> Dict[str, Any]:
    """Genera un JSON Schema pla sense `$defs`/`$ref`, apte per a OpenAI tools i llama.cpp GBNF."""
    raw = model.model_json_schema()
    raw_defs = raw.get("$defs")
    defs: Dict[str, Any] = raw_defs if isinstance(raw_defs, dict) else {}
    simplified = _simplify_schema_node(raw, defs)
    if not isinstance(simplified, dict):
        return {"type": "object", "properties": {}, "additionalProperties": False}
    simplified.setdefault("type", "object")
    simplified.setdefault("properties", {})
    simplified["additionalProperties"] = False
    return simplified


def to_openai_tool(spec: ToolSpec) -> Dict[str, Any]:
    """Exporta un `ToolSpec` a format OpenAI Function Calling."""
    return {
        "type": "function",
        "function": {
            "name": spec.name,
            "description": spec.description,
            "parameters": inline_strict_schema(spec.args_model),
        },
    }


def get_specs_for_subagent(
    subagent_id: str,
    *,
    caller_role: Optional[str] = None,
) -> List[ToolSpec]:
    """Retorna els `ToolSpec` d'un subagent filtrats opcionalment per rol RBAC."""
    role_up = caller_role.upper().strip() if caller_role else None
    specs: List[ToolSpec] = []
    for spec in TOOL_REGISTRY.values():
        if spec.subagent_id != subagent_id:
            continue
        if role_up and role_up not in spec.allowed_roles:
            continue
        specs.append(spec)
    return specs


def get_openai_tools_for_subagent(
    subagent_id: str,
    *,
    caller_role: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Retorna la llista d'esquemes OpenAI per a un subagent (amb filtre RBAC opcional)."""
    return [to_openai_tool(s) for s in get_specs_for_subagent(subagent_id, caller_role=caller_role)]


def build_router_json_schema(specs: Sequence[ToolSpec], *, max_calls: int = 3) -> Dict[str, Any]:
    """Construeix l'esquema JSON estricte per al Router de l'Etapa 1 (compatible amb LM Studio GBNF)."""
    variants = [
        {
            "type": "object",
            "properties": {
                "tool": {"type": "string", "enum": [spec.name]},
                "args": inline_strict_schema(spec.args_model),
            },
            "required": ["tool", "args"],
            "additionalProperties": False,
        }
        for spec in specs
    ]
    item_schema: Dict[str, Any] = (
        {"anyOf": variants}
        if len(variants) > 1
        else (variants[0] if len(variants) == 1 else {"type": "object", "additionalProperties": False})
    )
    return {
        "type": "object",
        "properties": {
            "calls": {
                "type": "array",
                "maxItems": max_calls,
                "items": item_schema,
            }
        },
        "required": ["calls"],
        "additionalProperties": False,
    }


def validate_tool_args(tool_name: str, raw_args: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Valida i sanititza els arguments d'una eina contra el seu model Pydantic."""
    spec = TOOL_REGISTRY.get(tool_name)
    if spec is None:
        raise ValueError(f"Eina no registrada: {tool_name}")

    sanitized_in: Dict[str, Any] = {}
    for k, v in (raw_args or {}).items():
        if k in FORBIDDEN_LLM_ARG_NAMES:
            continue
        if isinstance(v, str):
            sanitized_in[k] = sanitize_llm_text(v, max_length=8000)
        else:
            sanitized_in[k] = v

    validated = spec.args_model.model_validate(sanitized_in)
    return validated.model_dump()
