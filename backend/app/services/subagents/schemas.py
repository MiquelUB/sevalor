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
        "description": "Consulta l'estoc real en temps real (físic disponible vs reservat) d'un article o material als magatzems.",
        "parameters": {
            "type": "object",
            "properties": {
                "article_ref": {
                    "type": "string",
                    "description": "Referència d'inventari o nom de l'article (ex: 'Cable 6mm²', 'Tub PE-100', 'Electrovalvula')",
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
        "description": "Comprova si l'assignació de materials a una ordre de treball deixaria l'estoc per sota del mínim de seguretat.",
        "parameters": {
            "type": "object",
            "properties": {
                "article_ref": {
                    "type": "string",
                    "description": "Referència o nom del material",
                },
                "quantitat": {
                    "type": "number",
                    "description": "Quantitat prevista per consumir",
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
        "description": "Prepara una proposta d'ordre de compra al proveïdor habitual a preu pactat si l'estoc és insuficient.",
        "parameters": {
            "type": "object",
            "properties": {
                "article_ref": {
                    "type": "string",
                    "description": "Referència o nom de l'article a reposar",
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

SCHEMAS_LOGISTICA_ESTOC: List[Dict[str, Any]] = [
    SCHEMA_GET_REAL_STOCK,
    SCHEMA_CHECK_ALLOCATION_SAFETY,
    SCHEMA_PROPOSE_PURCHASE_ORDER,
    SCHEMA_REPLANIFICAR_OT,
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

SCHEMAS_FLOTA_DESPATX: List[Dict[str, Any]] = [
    SCHEMA_GET_CLOSEST_VEHICLE,
    SCHEMA_GET_VEHICLE_INFO,
    SCHEMA_AUDIT_ITV_INSURANCE_FLEET,
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
                    "description": "Mes de l'any a analitzar (1-12), opcional. Si no s'especifica es calcula l'històric acumulat.",
                }
            },
        },
    },
}

SCHEMA_RECONCILE_POST_OBRA = {
    "type": "function",
    "function": {
        "name": "reconcile_post_obra",
        "description": "Audita la desviació entre costos previstos i costos reals (materials, mà d'obra, km) per a una ordre de treball tancada.",
        "parameters": {
            "type": "object",
            "properties": {
                "codi_ot": {
                    "type": "string",
                    "description": "Codi de l'Ordre de Treball (ex: 'OT-2026-001')",
                }
            },
            "required": ["codi_ot"],
        },
    },
}

SCHEMA_DETECT_MARGIN_LEAK = {
    "type": "function",
    "function": {
        "name": "detect_margin_leak",
        "description": "Identifica si hi ha hagut consum continu anormal de material (>250% del previst) sense incidència justificada que erosionin el marge.",
        "parameters": {
            "type": "object",
            "properties": {
                "codi_ot": {
                    "type": "string",
                    "description": "Codi de l'Ordre de Treball",
                }
            },
            "required": ["codi_ot"],
        },
    },
}

SCHEMAS_AUDITORIA_MARGE: List[Dict[str, Any]] = [
    SCHEMA_GET_UNBILLED_MONEY,
    SCHEMA_RECONCILE_POST_OBRA,
    SCHEMA_DETECT_MARGIN_LEAK,
]

# ── 5. Digitalització OCR "Zero Data Entry" ─────────────────────────────────
SCHEMA_EXTRACT_ALBARA_LINES = {
    "type": "function",
    "function": {
        "name": "extract_albara_lines",
        "description": "Extreu les dades estructurades d'un albarà o factura de proveïdor (capçalera, data, NIF, partides i imports).",
        "parameters": {
            "type": "object",
            "properties": {
                "text_ocr": {
                    "type": "string",
                    "description": "Text extret de la imatge de l'albarà",
                }
            },
            "required": ["text_ocr"],
        },
    },
}

SCHEMA_EXTRACT_VEHICLE_TECH_CARD = {
    "type": "function",
    "function": {
        "name": "extract_vehicle_tech_card",
        "description": "Extreu matrícula, número de bastidor (VIN), marca i data de matriculació de la fitxa d'inspecció tècnica d'un vehicle.",
        "parameters": {
            "type": "object",
            "properties": {
                "text_ocr": {
                    "type": "string",
                    "description": "Text OCR de la fitxa del vehicle",
                }
            },
            "required": ["text_ocr"],
        },
    },
}

SCHEMA_EXTRACT_FUEL_RECEIPT = {
    "type": "function",
    "function": {
        "name": "extract_fuel_receipt",
        "description": "Extreu litres, import total, estació de servei i data d'un tiquet de combustible.",
        "parameters": {
            "type": "object",
            "properties": {
                "text_ocr": {
                    "type": "string",
                    "description": "Text OCR del tiquet de benzina",
                }
            },
            "required": ["text_ocr"],
        },
    },
}

SCHEMAS_OCR_VISION: List[Dict[str, Any]] = [
    SCHEMA_EXTRACT_ALBARA_LINES,
    SCHEMA_EXTRACT_VEHICLE_TECH_CARD,
    SCHEMA_EXTRACT_FUEL_RECEIPT,
]

# ── 6. Concierge Telegram i Notificacions ────────────────────────────────────
SCHEMA_NOTIFY_TECHNICIAN_ARRIVAL = {
    "type": "function",
    "function": {
        "name": "notify_technician_arrival",
        "description": "Envia un avís al client final per Telegram informant de l'arribada prevista de la quadrilla tècnica a la finca o obra.",
        "parameters": {
            "type": "object",
            "properties": {
                "ordre_treball_id": {
                    "type": "string",
                    "description": "UUID de l'ordre de treball",
                },
                "minuts_estimats": {
                    "type": "integer",
                    "description": "Minuts estimats per a l'arribada",
                },
            },
            "required": ["ordre_treball_id"],
        },
    },
}

SCHEMA_SEND_INTERACTIVE_BUDGET = {
    "type": "function",
    "function": {
        "name": "send_interactive_budget",
        "description": "Envia un pressupost interactiu amb botonera d'acceptació/rebuig immediat al Telegram del client.",
        "parameters": {
            "type": "object",
            "properties": {
                "client_id": {
                    "type": "string",
                    "description": "UUID del client destinatari",
                },
                "concepte": {
                    "type": "string",
                    "description": "Descripció de l'extra o servei",
                },
                "import_total": {
                    "type": "number",
                    "description": "Import total en euros (IVA inclòs)",
                },
            },
            "required": ["client_id", "concepte", "import_total"],
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

# ── 7. RAG Corporatiu i Fitxa 360 Client (Transversal) ──────────────────────
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

SCHEMAS_GENERAL_RAG: List[Dict[str, Any]] = [
    SCHEMA_GET_RAG_KNOWLEDGE,
    SCHEMA_GET_CLIENT_HISTORY,
]
