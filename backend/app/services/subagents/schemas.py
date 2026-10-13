"""Esquemes de crida d'eines (Tool Calling Schemas) per als Subagents especialitzats."""

from typing import Any, Dict, List

# ── 1. Peritatge Tècnic de Camp ─────────────────────────────────────────────
SCHEMA_GET_WARRANTY_STATUS = {
    "type": "function",
    "function": {
        "name": "get_warranty_status",
        "description": "Audita si una finca, client o equip disposa de garantia oficial o garantia de mà d'obra vigent (<90 dies).",
        "parameters": {
            "type": "object",
            "properties": {
                "finca_id": {
                    "type": "string",
                    "description": "UUID de la finca o instal·lació",
                },
                "client_id": {
                    "type": "string",
                    "description": "UUID del client",
                },
                "numero_serie": {
                    "type": "string",
                    "description": "Número de sèrie de l'equip o maquinària",
                },
            },
        },
    },
}

SCHEMA_GENERAR_MEMORANDUM_TECNIC = {
    "type": "function",
    "function": {
        "name": "generar_memorandum_tecnic",
        "description": "Genera una proposta de memoràndum tècnic d'avaria classificant l'avaria com a EXTRA_FACTURABLE o COST_NO_IMPUTABLE per a revisió de l'enginyer (HITL).",
        "parameters": {
            "type": "object",
            "properties": {
                "descripcio_avaria": {
                    "type": "string",
                    "description": "Descripció tècnica de l'avaria o incidència observada",
                },
                "ordre_treball_id": {
                    "type": "string",
                    "description": "UUID de l'ordre de treball relacionada (opcional)",
                },
            },
            "required": ["descripcio_avaria"],
        },
    },
}

SCHEMAS_PERITATGE_CAMP: List[Dict[str, Any]] = [
    SCHEMA_GET_WARRANTY_STATUS,
    SCHEMA_GENERAR_MEMORANDUM_TECNIC,
]

# ── 2. Logística i Magatzem ─────────────────────────────────────────────────
SCHEMA_GET_REAL_STOCK = {
    "type": "function",
    "function": {
        "name": "get_real_stock",
        "description": "Consulta l'estoc físic, estoc virtual reservat i saldo real disponible d'un article o família als magatzems de l'empresa.",
        "parameters": {
            "type": "object",
            "properties": {
                "article_ref": {
                    "type": "string",
                    "description": "Nom, família o referència de l'article a cercar (ex: 'Cable 6mm²', 'PE-100', 'TUB')",
                }
            },
            "required": ["article_ref"],
        },
    },
}

SCHEMA_CHECK_ALLOCATION_SAFETY = {
    "type": "function",
    "function": {
        "name": "check_allocation_safety",
        "description": "Avalua si consumir una quantitat d'un material en una nova obra reduirà l'estoc per sota del mínim de seguretat.",
        "parameters": {
            "type": "object",
            "properties": {
                "article_ref": {
                    "type": "string",
                    "description": "Referència o nom de l'article",
                },
                "quantitat": {
                    "type": "number",
                    "description": "Quantitat prevista a reservar o consumir",
                },
            },
            "required": ["article_ref", "quantitat"],
        },
    },
}

SCHEMA_PROPOSE_PURCHASE_ORDER = {
    "type": "function",
    "function": {
        "name": "propose_purchase_order",
        "description": "Genera una proposta d'esborrany de comanda de compra de reposició per a un article que ha entrat en ruptura d'estoc.",
        "parameters": {
            "type": "object",
            "properties": {
                "article_ref": {
                    "type": "string",
                    "description": "Referència de l'article a comprar",
                },
                "quantitat": {
                    "type": "number",
                    "description": "Quantitat suggerida a comprar",
                },
            },
            "required": ["article_ref", "quantitat"],
        },
    },
}

SCHEMA_REPLANIFICAR_OT = {
    "type": "function",
    "function": {
        "name": "replanificar_ot",
        "description": "Proposa re-planificar una Ordre de Treball (canvi de data o tècnic assignat). L'acció no s'executa immediatament, es demana confirmació a l'usuari (HITL).",
        "parameters": {
            "type": "object",
            "properties": {
                "codi_ot": {
                    "type": "string",
                    "description": "Codi de l'Ordre de Treball (ex: 'OT-2026-001')",
                },
                "nova_data": {
                    "type": "string",
                    "description": "Nova data de planificació en format YYYY-MM-DD",
                },
            },
            "required": ["codi_ot", "nova_data"],
        },
    },
}

SCHEMA_GET_STOCK_MOVEMENTS = {
    "type": "function",
    "function": {
        "name": "get_stock_movements",
        "description": "Consulta l'historial de moviments d'estoc (entrades, sortides, mermes) d'un article o referència.",
        "parameters": {
            "type": "object",
            "properties": {
                "article_ref": {
                    "type": "string",
                    "description": "Nom o referència de l'article (ex: 'TUB-PE-100' o 'Cable')",
                },
                "limit": {
                    "type": "integer",
                    "description": "Nombre màxim de moviments a consultar (per defecte 10)",
                },
            },
            "required": ["article_ref"],
        },
    },
}

SCHEMA_GET_LOW_STOCK_ALERTS = {
    "type": "function",
    "function": {
        "name": "get_low_stock_alerts",
        "description": "Obté tots els articles que estan per sota de l'estoc mínim de seguretat o en ruptura d'inventari als magatzems.",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
}

SCHEMA_GET_SUPPLIER_DOCS = {
    "type": "function",
    "function": {
        "name": "get_supplier_docs",
        "description": "Consulta els albarans o factures d'un proveïdor registrats al sistema de l'empresa.",
        "parameters": {
            "type": "object",
            "properties": {
                "proveidor_nom": {
                    "type": "string",
                    "description": "Nom o raó social del proveïdor",
                },
                "limit": {
                    "type": "integer",
                    "description": "Nombre màxim de documents a consultar (per defecte 10)",
                },
            },
            "required": ["proveidor_nom"],
        },
    },
}

SCHEMAS_LOGISTICA_ESTOC: List[Dict[str, Any]] = [
    SCHEMA_GET_REAL_STOCK,
    SCHEMA_CHECK_ALLOCATION_SAFETY,
    SCHEMA_PROPOSE_PURCHASE_ORDER,
    SCHEMA_REPLANIFICAR_OT,
    SCHEMA_GET_STOCK_MOVEMENTS,
    SCHEMA_GET_LOW_STOCK_ALERTS,
    SCHEMA_GET_SUPPLIER_DOCS,
]

# ── 3. Flota i Desplaçaments ────────────────────────────────────────────────
SCHEMA_GET_CLOSEST_VEHICLE = {
    "type": "function",
    "function": {
        "name": "get_closest_vehicle",
        "description": "Determina quin vehicle de la flota és el més proper a unes coordenades GPS donades usant la fórmula Haversine en temps real.",
        "parameters": {
            "type": "object",
            "properties": {
                "lat": {
                    "type": "number",
                    "description": "Latitud geogràfica de la ubicació o obra",
                },
                "lng": {
                    "type": "number",
                    "description": "Longitud geogràfica de la ubicació o obra",
                },
            },
            "required": ["lat", "lng"],
        },
    },
}

SCHEMA_GET_VEHICLE_INFO = {
    "type": "function",
    "function": {
        "name": "get_vehicle_info",
        "description": "Consulta les dades tècniques, odòmetre, consum, estat i data d'ITV o assegurança d'un vehicle de la flota per matrícula.",
        "parameters": {
            "type": "object",
            "properties": {
                "matricula": {
                    "type": "string",
                    "description": "Matrícula del vehicle (ex: '1234-XYZ')",
                }
            },
            "required": ["matricula"],
        },
    },
}

SCHEMA_AUDIT_ITV_INSURANCE_FLEET = {
    "type": "function",
    "function": {
        "name": "audit_itv_insurance_fleet",
        "description": "Audita tota la flota cercant vehicles amb ITV o assegurança caducada o que caduca en els propers 30 dies.",
        "parameters": {
            "type": "object",
            "properties": {
                "dies_marge": {
                    "type": "integer",
                    "description": "Marge de dies cap al futur (per defecte 30 dies)",
                }
            },
        },
    },
}

SCHEMA_GET_FLEET_STATUS = {
    "type": "function",
    "function": {
        "name": "get_fleet_status",
        "description": "Consulta l'estat general de la flota de vehicles: quins vehicles estan en ruta, en servei o assignats a operaris, i quins estan disponibles al parc.",
        "parameters": {
            "type": "object",
            "properties": {
                "filtres_estat": {
                    "type": "string",
                    "description": "Filtre opcional d'estat (ex: 'EN_RUTA', 'ASSIGNAT', 'DISPONIBLE')",
                }
            },
        },
    },
}

SCHEMA_GET_VEHICLE_MAINTENANCE = {
    "type": "function",
    "function": {
        "name": "get_vehicle_maintenance",
        "description": "Consulta l'historial de manteniments, reparacions i revisions d'un vehicle de la flota per matrícula.",
        "parameters": {
            "type": "object",
            "properties": {
                "matricula": {
                    "type": "string",
                    "description": "Matrícula del vehicle (ex: '1234-XYZ')",
                },
            },
            "required": ["matricula"],
        },
    },
}

SCHEMA_GET_FUEL_CONSUMPTION = {
    "type": "function",
    "function": {
        "name": "get_fuel_consumption",
        "description": "Consulta el registre de tiquets de carburant, quilometratge i recàrregues de la flota o d'un vehicle concret.",
        "parameters": {
            "type": "object",
            "properties": {
                "matricula": {
                    "type": "string",
                    "description": "Matrícula opcional d'un vehicle concret",
                },
            },
        },
    },
}

SCHEMAS_FLOTA_DESPATX: List[Dict[str, Any]] = [
    SCHEMA_GET_CLOSEST_VEHICLE,
    SCHEMA_GET_VEHICLE_INFO,
    SCHEMA_AUDIT_ITV_INSURANCE_FLEET,
    SCHEMA_GET_FLEET_STATUS,
    SCHEMA_GET_VEHICLE_MAINTENANCE,
    SCHEMA_GET_FUEL_CONSUMPTION,
]

# ── 4. Auditoria Financer i Rendibilitat (BOSS Only) ─────────────────────────
SCHEMA_GET_UNBILLED_MONEY = {
    "type": "function",
    "function": {
        "name": "get_unbilled_money",
        "description": "Calcula quants diners no han estat facturats comparant els treballs tancats i el material instal·lat amb les factures emeses.",
        "parameters": {
            "type": "object",
            "properties": {
                "mes": {
                    "type": "integer",
                    "description": "Mes de l'any a auditar (1-12)",
                },
                "any": {
                    "type": "integer",
                    "description": "Any a auditar (ex: 2026)",
                },
            },
        },
    },
}

SCHEMA_RECONCILE_POST_OBRA = {
    "type": "function",
    "function": {
        "name": "reconcile_post_obra",
        "description": "Executa una conciliació financera post-obra comparant hores reals de fitxatge, materials retirats i despeses addicionals contra el pressupost original.",
        "parameters": {
            "type": "object",
            "properties": {
                "ordre_treball_id": {
                    "type": "string",
                    "description": "UUID de l'ordre de treball a conciliar",
                }
            },
            "required": ["ordre_treball_id"],
        },
    },
}

SCHEMA_DETECT_MARGIN_LEAK = {
    "type": "function",
    "function": {
        "name": "detect_margin_leak",
        "description": "Detecta desviacions de marge brut i pèrdues de rendibilitat en obres en curs (alerta si marge < 25%).",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
}

SCHEMAS_AUDITORIA_MARGE: List[Dict[str, Any]] = [
    SCHEMA_GET_UNBILLED_MONEY,
    SCHEMA_RECONCILE_POST_OBRA,
    SCHEMA_DETECT_MARGIN_LEAK,
]

# ── 5. OCR i Digitalització de Documents ─────────────────────────────────────
SCHEMA_EXTRACT_ALBARA_LINES = {
    "type": "function",
    "function": {
        "name": "extract_albara_lines",
        "description": "Extreu les línies d'articles, quantitats, descomptes i preus d'un albarà o factura de proveïdor.",
        "parameters": {
            "type": "object",
            "properties": {
                "fitxer_path": {
                    "type": "string",
                    "description": "Ruta local del document PDF o imatge de l'albarà",
                }
            },
            "required": ["fitxer_path"],
        },
    },
}

SCHEMA_EXTRACT_VEHICLE_TECH_CARD = {
    "type": "function",
    "function": {
        "name": "extract_vehicle_tech_card",
        "description": "Extreu les dades oficials de la fitxa tècnica verda del vehicle (bastidor, MMA, places, cilindrada, ITV).",
        "parameters": {
            "type": "object",
            "properties": {
                "fitxer_path": {
                    "type": "string",
                    "description": "Ruta local del document del vehicle",
                }
            },
            "required": ["fitxer_path"],
        },
    },
}

SCHEMA_EXTRACT_FUEL_RECEIPT = {
    "type": "function",
    "function": {
        "name": "extract_fuel_receipt",
        "description": "Extreu l'import en euros, litres de carburant, quilometratge i benzinera d'una fotografia de tiquet de gasolina.",
        "parameters": {
            "type": "object",
            "properties": {
                "fitxer_path": {
                    "type": "string",
                    "description": "Ruta local de la fotografia del tiquet",
                }
            },
            "required": ["fitxer_path"],
        },
    },
}

SCHEMAS_OCR_VISION: List[Dict[str, Any]] = [
    SCHEMA_EXTRACT_ALBARA_LINES,
    SCHEMA_EXTRACT_VEHICLE_TECH_CARD,
    SCHEMA_EXTRACT_FUEL_RECEIPT,
]

# ── 6. Client Final & Canal Telegram ────────────────────────────────────────
SCHEMA_NOTIFY_TECHNICIAN_ARRIVAL = {
    "type": "function",
    "function": {
        "name": "notify_technician_arrival",
        "description": "Envia una notificació de cortesia al client per Telegram indicant que la quadrilla de tècnics està en camí o ha arribat.",
        "parameters": {
            "type": "object",
            "properties": {
                "client_id": {
                    "type": "string",
                    "description": "UUID del client",
                },
                "minuts_estimats": {
                    "type": "integer",
                    "description": "Temps estimat d'arribada en minuts",
                },
            },
            "required": ["client_id"],
        },
    },
}

SCHEMA_SEND_INTERACTIVE_BUDGET = {
    "type": "function",
    "function": {
        "name": "send_interactive_budget",
        "description": "Envia al canal de Telegram del client el pressupost amb botons interactius per Aprovar amb 1 Clic o Rebutjar.",
        "parameters": {
            "type": "object",
            "properties": {
                "pressupost_id": {
                    "type": "string",
                    "description": "UUID del pressupost aprovable",
                },
                "client_id": {
                    "type": "string",
                    "description": "UUID del client receptor",
                },
            },
            "required": ["pressupost_id", "client_id"],
        },
    },
}

SCHEMA_RECEIVE_CLIENT_MEDIA = {
    "type": "function",
    "function": {
        "name": "receive_client_media",
        "description": "Registra una fotografia o arxiu d'avaria enviat pel client final i l'associa a l'ordre de treball activa.",
        "parameters": {
            "type": "object",
            "properties": {
                "client_id": {
                    "type": "string",
                    "description": "UUID del client",
                },
                "descripcio": {
                    "type": "string",
                    "description": "Comentari del client sobre la foto",
                },
            },
            "required": ["client_id"],
        },
    },
}

SCHEMAS_CLIENT_TELEGRAM: List[Dict[str, Any]] = [
    SCHEMA_NOTIFY_TECHNICIAN_ARRIVAL,
    SCHEMA_SEND_INTERACTIVE_BUDGET,
    SCHEMA_RECEIVE_CLIENT_MEDIA,
]

# ── 7. RAG Corporatiu, Clients i Finques ────────────────────────────────────
SCHEMA_GET_RAG_KNOWLEDGE = {
    "type": "function",
    "function": {
        "name": "get_rag_knowledge",
        "description": "Cerca procediments tècnics, manuals d'obra i normatives a la base de coneixement corporativa RAG.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Paraules clau o descripció del procediment a cercar",
                }
            },
            "required": ["query"],
        },
    },
}

SCHEMA_GET_CLIENT_HISTORY = {
    "type": "function",
    "function": {
        "name": "get_client_history",
        "description": "Recopila la Fitxa 360° i l'historial complet dels darrers 365 dies d'un client (intervencions, peces instal·lades i incidències).",
        "parameters": {
            "type": "object",
            "properties": {
                "client_id": {
                    "type": "string",
                    "description": "UUID del client",
                },
                "client_nom": {
                    "type": "string",
                    "description": "Nom o raó social del client",
                },
            },
        },
    },
}

SCHEMA_SEARCH_CLIENTS = {
    "type": "function",
    "function": {
        "name": "search_clients",
        "description": "Cerca clients i les seves finques, contactes o adreces a la base de dades corporativa.",
        "parameters": {
            "type": "object",
            "properties": {
                "terme": {
                    "type": "string",
                    "description": "Nom, raó social, NIF o adreça del client a cercar",
                },
            },
            "required": ["terme"],
        },
    },
}

SCHEMA_GET_FINCA_DETAIL = {
    "type": "function",
    "function": {
        "name": "get_finca_detail",
        "description": "Obté la informació tècnica, adreça, SIGPAC, referència cadastral i codi de cadenat d'una finca o instal·lació.",
        "parameters": {
            "type": "object",
            "properties": {
                "finca_nom_o_id": {
                    "type": "string",
                    "description": "Nom de la finca o identificador",
                },
            },
            "required": ["finca_nom_o_id"],
        },
    },
}

SCHEMA_GET_PENDING_BUDGETS = {
    "type": "function",
    "function": {
        "name": "get_pending_budgets",
        "description": "Consulta els pressupostos pendents d'aprovació o signatura per part del client.",
        "parameters": {
            "type": "object",
            "properties": {
                "client_nom": {
                    "type": "string",
                    "description": "Nom opcional del client per filtrar pressupostos",
                },
            },
        },
    },
}

SCHEMA_GET_TOOLS_CUSTODY = {
    "type": "function",
    "function": {
        "name": "get_tools_custody",
        "description": "Consulta les eines, instruments i maquinària en custòdia assignades a operaris o magatzems.",
        "parameters": {
            "type": "object",
            "properties": {
                "operari_nom": {
                    "type": "string",
                    "description": "Nom opcional de l'operari",
                },
            },
        },
    },
}

SCHEMAS_GENERAL_RAG: List[Dict[str, Any]] = [
    SCHEMA_GET_RAG_KNOWLEDGE,
    SCHEMA_GET_CLIENT_HISTORY,
    SCHEMA_SEARCH_CLIENTS,
    SCHEMA_GET_FINCA_DETAIL,
    SCHEMA_GET_PENDING_BUDGETS,
    SCHEMA_GET_TOOLS_CUSTODY,
]

# ── 8. Planificació, Agenda i Equip de Treball ───────────────────────────────
SCHEMA_GET_WORK_ORDERS = {
    "type": "function",
    "function": {
        "name": "get_work_orders",
        "description": "Consulta la llista d'ordres de treball (feines) de l'empresa segons data, estat o operari assignat.",
        "parameters": {
            "type": "object",
            "properties": {
                "data": {
                    "type": "string",
                    "description": "Data específica en format YYYY-MM-DD o 'avui'",
                },
                "estat": {
                    "type": "string",
                    "description": "Estat de l'OT (ex: 'PENDENT', 'ASSIGNADA', 'EN_CURS', 'COMPLETADA')",
                },
                "operari_nom": {
                    "type": "string",
                    "description": "Nom de l'operari per filtrar feines assignades",
                },
            },
        },
    },
}

SCHEMA_GET_WORK_ORDER_DETAIL = {
    "type": "function",
    "function": {
        "name": "get_work_order_detail",
        "description": "Obté el detall complet d'una ordre de treball específica (codi, títol, client, finca, estat, vehicle i materials de picking).",
        "parameters": {
            "type": "object",
            "properties": {
                "codi_ot": {
                    "type": "string",
                    "description": "Codi de l'ordre de treball (ex: 'OT-2026-001' o UUID)",
                },
            },
            "required": ["codi_ot"],
        },
    },
}

SCHEMA_GET_TEAM_TODAY = {
    "type": "function",
    "function": {
        "name": "get_team_today",
        "description": "Consulta la plantilla total de l'empresa (cens complet de treballadors i operaris actius desglossats per rols) i l'estat de jornada d'avui: qui està en jornada activa (fitxat), qui ha finalitzat i quin vehicle tenen assignat.",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
}

SCHEMA_GET_TIMESHEET = {
    "type": "function",
    "function": {
        "name": "get_timesheet",
        "description": "Consulta els registres de jornada laboral i fitxatges (hores ordinàries i extraordinàries) per a un operari o data.",
        "parameters": {
            "type": "object",
            "properties": {
                "data": {
                    "type": "string",
                    "description": "Data en format YYYY-MM-DD o 'avui'",
                },
                "operari_nom": {
                    "type": "string",
                    "description": "Nom de l'operari",
                },
            },
        },
    },
}

SCHEMA_GET_OPEN_INCIDENTS = {
    "type": "function",
    "function": {
        "name": "get_open_incidents",
        "description": "Consulta les incidències tècniques registrades a les feines o vehicles que encara estan pendents de resolució.",
        "parameters": {
            "type": "object",
            "properties": {
                "codi_ot": {
                    "type": "string",
                    "description": "Codi opcional de l'OT per filtrar incidències",
                },
            },
        },
    },
}

SCHEMAS_PLANIFICACIO_EQUIP: List[Dict[str, Any]] = [
    SCHEMA_GET_WORK_ORDERS,
    SCHEMA_GET_WORK_ORDER_DETAIL,
    SCHEMA_GET_TEAM_TODAY,
    SCHEMA_GET_TIMESHEET,
    SCHEMA_GET_OPEN_INCIDENTS,
]
