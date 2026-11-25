"""Servei de configuració sobirana del Copilot IA al Disc Dur Dedicat de l'Empresa (FR-024).

Norma Constitucional (Zero-Storage Hetzner):
- Tota la configuració del Copilot (`system_prompt`, `rag_prompt`, `subagent_prompts`,
  `llm_chat_model`, `llm_vision_model`, `hardware_profile`, `timeout_budget_s`, `version`)
  viu EXCLUSIVAMENT al fitxer únic `09_copilot_ia/prompt_sistema/copilot_profile.json`
  al disc dur dedicat de cada empresa, llegit i escrit pel Túnel Invers Natiu WSS
  (amb cua efímera xifrada `SVENC1:` si el PC està en trànsit d'onboarding).
- `system_prompt.txt` es conserva únicament com a migració read-only d'una sola vegada
  si existeix al disc i manca `copilot_profile.json` (mai s'hi escriu de nou).
- Cap text de prompt ni configuració del Copilot s'emmagatzema a PostgreSQL.
- Caché efímera en memòria (TTL 60 s) amb invalidació multi-worker via Redis (`copilot_cfg_ver:{empresa_id}`).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional, Sequence, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import bump_cache_version, get_cache_version
from app.services.sovereign_storage import SovereignStorageGateway

logger = logging.getLogger("copilot_config_service")

CONFIG_CACHE_TTL_SECONDS: float = 60.0
PROFILE_ITEM_ID: str = "copilot_profile"
PROFILE_SCHEMA_VERSION: int = 2
SYSTEM_PROMPT_FILENAME: str = "system_prompt.txt"
_REDIS_CACHE_NS: str = "copilot_cfg_ver"
DEFAULT_SYNTHESIS_MAX_TOKENS: int = 700

HardwareProfile = Literal["32GB", "16GB"]

_VERTICAL_DEFAULT_PROMPTS: Dict[str, str] = {
    "CAMPOPRO": (
        "Ets el Copilot Tècnic corporatiu d'una empresa d'instal·lacions agrícoles i regadiu (CampoPro). "
        "Domines canonades PE-100, electrovàlvules, bombes submergibles, filtració, parcel·les SIGPAC i manteniment de finques. "
        "Prioritza alertes de reg crític, cabals i trencaments de camp, fent respostes curtes aptes per a mòbil. "
        "Davant guies o manuals interns consulta la base documental; davant accions amb impacte econòmic exigeix confirmació humana; "
        "davant peticions econòmiques sense permisos respecta les restriccions de rol."
    ),
    "ELECTRICPRO": (
        "Ets el Copilot Tècnic corporatiu d'una empresa d'instal·lacions elèctriques de baixa tensió i fotovoltaica (ElectricPro). "
        "Domines normativa REBT, quadres elèctrics, proteccions, seccions de cablejat, inversors i certificacions. "
        "Prioritza seguretat elèctrica, diferencials i lliuraments a temps, fent respostes directes aptes per a mòbil. "
        "Davant normativa consulta protocols interns; exigeix confirmació humana per a comandes i respecta les restriccions per rol."
    ),
    "HYDROPRO": (
        "Ets el Copilot Tècnic corporatiu d'una empresa de fontaneria, aigua i instal·lacions hidràuliques (HydroPro). "
        "Domines xarxes d'abastament, grups de pressió, vàlvules, detecció de fuites i manteniment preventiu. "
        "Prioritza urgències de fuga o manca de subministrament, fent respostes breus aptes per a mòbil. "
        "Distingeix entre procediments de manual i dades operatives; respecta la confirmació humana i les restriccions de rol."
    ),
    "BUILDINGPRO": (
        "Ets el Copilot Tècnic corporatiu d'una empresa d'edificació, reformes i obra civil (BuildingPro). "
        "Domines CTE, coordinació d'oficis, control d'obra, certificacions i seguretat i salut PRL. "
        "Prioritza seguiment d'obra, recursos pesants i prevenció de riscos en format clar apte per a mòbil. "
        "Distingeix consultes documentals de dades de camp; respecta confirmació humana i restriccions de rol."
    ),
    "CLIMAPRO": (
        "Ets el Copilot Tècnic corporatiu d'una empresa de climatització, aerotèrmia i fred industrial (ClimaPro). "
        "Domines RITE, gasos fluorats, calderes, bombes de calor i manteniment preventiu. "
        "Prioritza incidències de fred/calor crítiques i compliment RITE amb estil concís apte per a mòbil. "
        "Distingeix guies de dades operatives; exigeix confirmació humana en comandes i respecta restriccions per rol."
    ),
}

_VERTICAL_ROUTER_HINTS: Dict[str, str] = {
    "CAMPOPRO": (
        "Vocabulari CampoPro: finques/parcel·les SIGPAC, degoteig, electrovàlvules, PE-100, filtració, bombes. "
        "Consultes de 'com' o 'on' es fa un procés van a manuals/guies; cerques de registres o estoc van a dades operatives. "
        "Si es demana si hi ha material o vehicle per a una OT, crida els subagents implicats en paral·lel."
    ),
    "ELECTRICPRO": (
        "Vocabulari ElectricPro: REBT, quadre BT, diferencial, magnetotèrmic, inversor solar, secció cable. "
        "Consultes de normativa o passos ('com/on') van a guies RAG; estat d'OTs, flota o estoc van a dades operatives. "
        "Si es pregunta material+OT o flota+equip, encamina crides en paral·lel."
    ),
    "HYDROPRO": (
        "Vocabulari HydroPro: grup pressió, canonada, vàlvula, fuga, comptador, depuradora. "
        "Distingeix manuals ('com purgar/reparar') de consultes d'inventari o ordres; combina fonts en preguntes transversals."
    ),
    "BUILDINGPRO": (
        "Vocabulari BuildingPro: CTE, PRL, grua/pesant, ofici, certificat obra, albarà proveïdor. "
        "Distingeix protocols PRL ('com/on') de registres d'obra i combina equip+flota o estoc+OT en paral·lel."
    ),
    "CLIMAPRO": (
        "Vocabulari ClimaPro: RITE, gasos fluorats, R32, aerotèrmia, caldera, manteniment preventiu. "
        "Distingeix procediments ('com/on') de dades d'estoc/OTs i encamina fonts en paral·lel en consultes creuades."
    ),
}

IDIOSINCRASIA_LABELS: Dict[str, str] = {
    "horari_magatzem": "Horari de magatzem i lliuraments",
    "prioritat_sla": "Prioritat contractual i SLA",
    "zones_cobertura": "Zones i rutes de cobertura",
    "glossari_intern": "Glossari intern de l'empresa",
}


def strip_omplir_placeholders(text: str) -> str:
    """Elimina automàticament qualsevol línia amb marcadors `[OMPLIR` abans d'enviar-la a l'LLM."""
    if not text:
        return ""
    kept = [line for line in str(text).splitlines() if "[OMPLIR" not in line.upper()]
    return "\n".join(kept).strip()


def build_default_router_hints(vertical: str) -> str:
    """Retorna pistes recomanades d'encaminament multi-subagent segons la vertical."""
    v_key = (vertical or "SEVALOR").strip().upper()
    return _VERTICAL_ROUTER_HINTS.get(
        v_key,
        (
            "Distingeix preguntes de procediment ('com es fa', 'on es troba') encaminant a guies RAG "
            "de consultes de registres operatius. Si la pregunta creua estoc, OTs i flota, crida els subagents en paral·lel."
        ),
    )


def build_default_contrast_rules(vertical: str) -> List[str]:
    """Retorna regles de contrast recomanades per a la síntesi multi-font."""
    _ = vertical
    return [
        "Compara l'estoc disponible real amb les quantitats previstes de les ordres de treball i indica la diferència exacta.",
        "Quan falti material o el vehicle tingui alertes d'ITV/disponibilitat, assenyala el bloqueig abans de recomanar sortida.",
    ]


def build_default_vertical_prompt(vertical: str, empresa_nom: str = "") -> str:
    """Genera una plantilla inicial neta (sense noms d'eines ni duplicar regles del coordinador)."""
    v_key = (vertical or "SEVALOR").strip().upper()
    base = _VERTICAL_DEFAULT_PROMPTS.get(
        v_key,
        (
            "Ets el Copilot Tècnic corporatiu de l'empresa dins Sevalor Suite. "
            "Ajudes l'oficina tècnica i les quadrilles de camp a consultar ordres de treball, estoc, "
            "flota, clients i protocols interns en format clar apte per a mòbil. "
            "Distingeix guies de dades operatives, exigeix confirmació humana en comandes i respecta restriccions de rol."
        ),
    )
    if empresa_nom and empresa_nom.strip() and not empresa_nom.strip().startswith("Tenant "):
        return f"Empresa: {empresa_nom.strip()}.\n{base}"
    return base


@dataclass
class SovereignCopilotProfile:
    """Configuració sobirana del Copilot llegida exclusivament del disc dedicat de l'empresa."""

    empresa_id: UUID
    system_prompt: str
    rag_prompt: str = ""
    subagent_prompts: Dict[str, str] = field(default_factory=dict)
    contrast_rules: List[str] = field(default_factory=list)
    router_hints: str = ""
    subagents: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    idiosincrasia: Dict[str, str] = field(default_factory=dict)
    synthesis_max_tokens: int = DEFAULT_SYNTHESIS_MAX_TOKENS
    llm_model: str = ""
    llm_chat_model: str = ""
    llm_vision_model: str = ""
    hardware_profile: HardwareProfile = "32GB"
    timeout_budget_s: float = 24.0
    router_timeout_s: float = 8.0
    version: int = PROFILE_SCHEMA_VERSION
    updated_at: Optional[str] = None

    @property
    def effective_chat_model(self) -> str:
        """Model prioritari per a xat/router (`llm_chat_model` o fallback a `llm_model`)."""
        return (self.llm_chat_model or self.llm_model or "").strip()

    @property
    def effective_vision_model(self) -> str:
        """Model prioritari per a OCR/visió (`llm_vision_model`, o model de xat només si suporta visió)."""
        if (self.llm_vision_model or "").strip():
            return self.llm_vision_model.strip()
        fallback = (self.llm_chat_model or self.llm_model or "").strip()
        low = fallback.lower()
        if "-vl-" in low or "vision" in low:
            return fallback
        return ""

    def is_subagent_enabled(self, subagent_id: str) -> bool:
        """Indica si el subagent està habilitat al perfil de l'empresa (per defecte True)."""
        cfg = (self.subagents or {}).get(subagent_id)
        if isinstance(cfg, dict) and "enabled" in cfg:
            return bool(cfg["enabled"])
        return True

    @property
    def subagent_enabled_map(self) -> Dict[str, bool]:
        """Retorna el mapa `{subagent_id: bool}` d'activació configurada."""
        return {
            sid: bool(cfg.get("enabled", True))
            for sid, cfg in (self.subagents or {}).items()
            if isinstance(cfg, dict)
        }


# Caché efímera en memòria per empresa_id -> (expires_monotonic, redis_version, SovereignCopilotProfile)
_PROFILE_CACHE: Dict[str, Tuple[float, Optional[str], SovereignCopilotProfile]] = {}


def invalidate_copilot_config_cache(empresa_id: Optional[UUID | str] = None) -> None:
    """Invalida la caché local de configuració del Copilot per a una empresa (o totes si `None`)."""
    if empresa_id is None:
        _PROFILE_CACHE.clear()
        return
    _PROFILE_CACHE.pop(str(empresa_id), None)


def get_cached_copilot_profile_sync(empresa_id: UUID | str) -> Optional[SovereignCopilotProfile]:
    """Retorna el perfil en caché local si no ha expirat (només per lectures síncrones ràpides)."""
    entry = _PROFILE_CACHE.get(str(empresa_id))
    if entry is not None and entry[0] > time.monotonic():
        return entry[2]
    return None


def _normalize_hardware_profile(raw: Any) -> HardwareProfile:
    val = str(raw or "32GB").strip().upper()
    return "16GB" if val == "16GB" else "32GB"


def _normalize_timeout_budget(raw: Any, hw_profile: HardwareProfile) -> float:
    default_s = 30.0 if hw_profile == "16GB" else 24.0
    if raw is None or raw == "":
        return default_s
    try:
        parsed = float(raw)
    except (TypeError, ValueError):
        return default_s
    return max(8.0, min(parsed, 90.0))


def _normalize_router_timeout(raw: Any, hw_profile: HardwareProfile) -> float:
    default_s = 12.0 if hw_profile == "16GB" else 8.0
    if raw is None or raw == "":
        return default_s
    try:
        parsed = float(raw)
    except (TypeError, ValueError):
        return default_s
    return max(3.0, min(parsed, 25.0))


def _normalize_idiosincrasia(raw: Any) -> Dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    out: Dict[str, str] = {}
    for k in ("horari_magatzem", "prioritat_sla", "zones_cobertura", "glossari_intern"):
        val = strip_omplir_placeholders(str(raw.get(k) or "").strip())
        if val:
            out[k] = val[:400]
    return out


def _normalize_synthesis_max_tokens(raw: Any) -> int:
    if raw is None or raw == "":
        return DEFAULT_SYNTHESIS_MAX_TOKENS
    try:
        parsed = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_SYNTHESIS_MAX_TOKENS
    return max(250, min(parsed, 1500))


def _normalize_contrast_rules(raw: Any) -> List[str]:
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        return []
    out: List[str] = []
    for item in raw:
        txt = str(item or "").strip()
        if txt:
            out.append(txt[:400])
    return out[:20]


def _merge_subagents_config(
    raw_subagents: Any,
    raw_prompts: Any,
    raw_enabled: Any = None,
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, str]]:
    """Unifica l'estructura v2 `subagents: {id: {enabled, prompt}}` amb el camp v1 `subagent_prompts`."""
    merged: Dict[str, Dict[str, Any]] = {}

    if isinstance(raw_subagents, dict):
        for k, v in raw_subagents.items():
            sid = str(k or "").strip()
            if not sid:
                continue
            if isinstance(v, dict):
                merged[sid] = {
                    "enabled": bool(v.get("enabled", True)),
                    "prompt": str(v.get("prompt") or "").strip(),
                }
            elif isinstance(v, str):
                merged[sid] = {"enabled": True, "prompt": v.strip()}

    if isinstance(raw_prompts, dict):
        for k, v in raw_prompts.items():
            sid = str(k or "").strip()
            if not sid:
                continue
            p_txt = str(v or "").strip()
            if sid not in merged:
                merged[sid] = {"enabled": True, "prompt": p_txt}
            elif p_txt:
                merged[sid]["prompt"] = p_txt

    if isinstance(raw_enabled, dict):
        for k, v in raw_enabled.items():
            sid = str(k or "").strip()
            if not sid:
                continue
            if sid not in merged:
                merged[sid] = {"enabled": bool(v), "prompt": ""}
            else:
                merged[sid]["enabled"] = bool(v)

    # Netejar entrades totalment per defecte (enabled=True i prompt buit)
    clean_subagents: Dict[str, Dict[str, Any]] = {
        sid: cfg
        for sid, cfg in merged.items()
        if cfg["prompt"] or cfg["enabled"] is False
    }
    clean_prompts: Dict[str, str] = {
        sid: cfg["prompt"]
        for sid, cfg in clean_subagents.items()
        if cfg["prompt"]
    }
    return clean_subagents, clean_prompts


def _profile_from_dict(empresa_id: UUID, doc: Dict[str, Any], prompt_txt_fallback: str = "") -> SovereignCopilotProfile:
    clean_subagents, clean_sub = _merge_subagents_config(
        doc.get("subagents"),
        doc.get("subagent_prompts"),
        doc.get("subagent_enabled"),
    )

    hw = _normalize_hardware_profile(doc.get("hardware_profile"))
    timeout_s = _normalize_timeout_budget(doc.get("timeout_budget_s"), hw)
    router_timeout_s = _normalize_router_timeout(doc.get("router_timeout_s"), hw)
    synth_tokens = _normalize_synthesis_max_tokens(doc.get("synthesis_max_tokens"))
    contrast_rules = _normalize_contrast_rules(doc.get("contrast_rules"))
    router_hints = strip_omplir_placeholders(str(doc.get("router_hints") or "").strip())[:1200]
    idiosincrasia = _normalize_idiosincrasia(doc.get("idiosincrasia"))
    chat_model = str(doc.get("llm_chat_model") or doc.get("llm_model") or "").strip()
    vision_model = str(doc.get("llm_vision_model") or "").strip()
    sys_prompt = str(doc.get("system_prompt") or prompt_txt_fallback or "").strip()
    try:
        version = int(doc.get("version") or PROFILE_SCHEMA_VERSION)
    except (TypeError, ValueError):
        version = PROFILE_SCHEMA_VERSION

    return SovereignCopilotProfile(
        empresa_id=empresa_id,
        system_prompt=sys_prompt,
        rag_prompt=str(doc.get("rag_prompt") or "").strip(),
        subagent_prompts=clean_sub,
        contrast_rules=contrast_rules,
        router_hints=router_hints,
        subagents=clean_subagents,
        idiosincrasia=idiosincrasia,
        synthesis_max_tokens=synth_tokens,
        llm_model=chat_model,
        llm_chat_model=chat_model,
        llm_vision_model=vision_model,
        hardware_profile=hw,
        timeout_budget_s=timeout_s,
        router_timeout_s=router_timeout_s,
        version=version,
        updated_at=str(doc.get("updated_at") or "") or None,
    )


async def get_strict_copilot_config(
    db: AsyncSession,
    empresa_id: UUID,
    *,
    use_cache: bool = True,
) -> Optional[SovereignCopilotProfile]:
    """Llegeix la configuració del Copilot exclusivament de `copilot_profile.json` al disc sobirà."""
    cache_key = str(empresa_id)
    now = time.monotonic()
    redis_ver: Optional[str] = None
    if use_cache:
        redis_ver = await get_cache_version(_REDIS_CACHE_NS, cache_key)
        cached = _PROFILE_CACHE.get(cache_key)
        if cached is not None and cached[0] > now and cached[1] == redis_ver:
            return cached[2]

    # 1. Intentar llegir `copilot_profile.json` verificat (HMAC + tenant) del disc dedicat via WSS/Transit
    docs = await SovereignStorageGateway.llegir_entitats_json(db, empresa_id, "copilot_prompt")
    profile_doc = next(
        (d for d in docs if str(d.get("id") or "") == PROFILE_ITEM_ID),
        docs[0] if docs else None,
    )

    # Si el túnel acaba de connectar i encara hi havia un paquet pendent a la cua de trànsit, el drenem ara
    if profile_doc is None:
        try:
            drain = await SovereignStorageGateway.drenar_cua_transit_empresa(db, empresa_id)
            if drain.get("enviats", 0) > 0:
                docs = await SovereignStorageGateway.llegir_entitats_json(
                    db, empresa_id, "copilot_prompt"
                )
                profile_doc = next(
                    (d for d in docs if str(d.get("id") or "") == PROFILE_ITEM_ID),
                    docs[0] if docs else None,
                )
        except Exception as exc:
            logger.debug("Drenatge oportú de configuració copilot omès per %s: %s", empresa_id, exc)

    # 2. Migració read-only d'una sola vegada des de `system_prompt.txt` si manca `copilot_profile.json`
    if profile_doc is None or not str(profile_doc.get("system_prompt") or "").strip():
        raw_txt = await SovereignStorageGateway.llegir_text_fitxer(
            db, empresa_id, "copilot_prompt", SYSTEM_PROMPT_FILENAME
        )
        prompt_txt = (raw_txt or "").strip()
        if not prompt_txt:
            return None

        migrated_base = _profile_from_dict(empresa_id, profile_doc or {}, prompt_txt_fallback=prompt_txt)
        try:
            return await save_strict_copilot_config(
                db=db,
                empresa_id=empresa_id,
                system_prompt=migrated_base.system_prompt,
                rag_prompt=migrated_base.rag_prompt,
                subagent_prompts=migrated_base.subagent_prompts,
                contrast_rules=migrated_base.contrast_rules,
                router_hints=migrated_base.router_hints,
                subagents=migrated_base.subagents,
                synthesis_max_tokens=migrated_base.synthesis_max_tokens,
                llm_model=migrated_base.llm_model,
                llm_chat_model=migrated_base.llm_chat_model,
                llm_vision_model=migrated_base.llm_vision_model,
                hardware_profile=migrated_base.hardware_profile,
                timeout_budget_s=migrated_base.timeout_budget_s,
                router_timeout_s=migrated_base.router_timeout_s,
                idiosincrasia=migrated_base.idiosincrasia,
            )
        except Exception as exc:
            logger.warning(
                "Migració read-only de system_prompt.txt a copilot_profile.json diferida per %s: %s",
                empresa_id,
                exc,
            )
            _PROFILE_CACHE[cache_key] = (now + CONFIG_CACHE_TTL_SECONDS, redis_ver, migrated_base)
            return migrated_base

    profile = _profile_from_dict(empresa_id, profile_doc)
    if not profile.system_prompt:
        return None

    if redis_ver is None:
        redis_ver = await get_cache_version(_REDIS_CACHE_NS, cache_key)
    _PROFILE_CACHE[cache_key] = (now + CONFIG_CACHE_TTL_SECONDS, redis_ver, profile)
    return profile


async def save_strict_copilot_config(
    db: AsyncSession,
    empresa_id: UUID,
    system_prompt: str,
    rag_prompt: str = "",
    subagent_prompts: Optional[Dict[str, str]] = None,
    llm_model: str = "",
    *,
    contrast_rules: Optional[List[str]] = None,
    router_hints: str = "",
    subagents: Optional[Dict[str, Dict[str, Any]]] = None,
    subagent_enabled: Optional[Dict[str, bool]] = None,
    synthesis_max_tokens: Optional[int] = None,
    llm_chat_model: Optional[str] = None,
    llm_vision_model: Optional[str] = None,
    hardware_profile: str = "32GB",
    timeout_budget_s: Optional[float] = None,
    router_timeout_s: Optional[float] = None,
    idiosincrasia: Optional[Dict[str, str]] = None,
) -> SovereignCopilotProfile:
    """Desa la configuració del Copilot EXCLUSIVAMENT a `copilot_profile.json` al disc dedicat."""
    clean_prompt = (system_prompt or "").strip()
    clean_rag = (rag_prompt or "").strip()
    clean_subagents_map, clean_subagents = _merge_subagents_config(
        subagents,
        subagent_prompts,
        subagent_enabled,
    )
    clean_contrast_rules = _normalize_contrast_rules(contrast_rules or [])
    clean_router_hints = strip_omplir_placeholders(str(router_hints or "").strip())[:1200]
    clean_idiosincrasia = _normalize_idiosincrasia(idiosincrasia or {})
    synth_tokens_eff = _normalize_synthesis_max_tokens(synthesis_max_tokens)
    hw = _normalize_hardware_profile(hardware_profile)
    timeout_eff = _normalize_timeout_budget(timeout_budget_s, hw)
    router_timeout_eff = _normalize_router_timeout(router_timeout_s, hw)
    chat_model_eff = str(
        llm_chat_model if (llm_chat_model is not None and llm_chat_model.strip()) else (llm_model or "")
    ).strip()
    vision_model_eff = str(llm_vision_model or "").strip()
    updated_at = datetime.now(timezone.utc).isoformat()

    payload_json: Dict[str, Any] = {
        "id": PROFILE_ITEM_ID,
        "version": PROFILE_SCHEMA_VERSION,
        "empresa_id": str(empresa_id),
        "system_prompt": clean_prompt,
        "rag_prompt": clean_rag,
        "subagent_prompts": clean_subagents,
        "subagents": clean_subagents_map,
        "contrast_rules": clean_contrast_rules,
        "router_hints": clean_router_hints,
        "idiosincrasia": clean_idiosincrasia,
        "synthesis_max_tokens": synth_tokens_eff,
        "llm_model": chat_model_eff,
        "llm_chat_model": chat_model_eff,
        "llm_vision_model": vision_model_eff,
        "hardware_profile": hw,
        "timeout_budget_s": timeout_eff,
        "router_timeout_s": router_timeout_eff,
        "updated_at": updated_at,
    }

    # Fitxer únic canònic signat amb HMAC a `09_copilot_ia/prompt_sistema/copilot_profile.json`
    await SovereignStorageGateway.desar_entitat_json(
        db=db,
        empresa_id=empresa_id,
        categoria="copilot_prompt",
        item_id=PROFILE_ITEM_ID,
        dades=payload_json,
    )

    profile = SovereignCopilotProfile(
        empresa_id=empresa_id,
        system_prompt=clean_prompt,
        rag_prompt=clean_rag,
        subagent_prompts=clean_subagents,
        contrast_rules=clean_contrast_rules,
        router_hints=clean_router_hints,
        subagents=clean_subagents_map,
        idiosincrasia=clean_idiosincrasia,
        synthesis_max_tokens=synth_tokens_eff,
        llm_model=chat_model_eff,
        llm_chat_model=chat_model_eff,
        llm_vision_model=vision_model_eff,
        hardware_profile=hw,
        timeout_budget_s=timeout_eff,
        router_timeout_s=router_timeout_eff,
        version=PROFILE_SCHEMA_VERSION,
        updated_at=updated_at,
    )
    invalidate_copilot_config_cache(empresa_id)
    new_ver = await bump_cache_version(_REDIS_CACHE_NS, str(empresa_id))
    if clean_prompt:
        _PROFILE_CACHE[str(empresa_id)] = (
            time.monotonic() + CONFIG_CACHE_TTL_SECONDS,
            new_ver,
            profile,
        )
    return profile
