"""Servei de configuració sobirana del Copilot IA al Disc Dur Dedicat de l'Empresa (FR-024).

Norma Constitucional (Zero-Storage Hetzner):
- Els textos del `system_prompt`, `rag_prompt`, `subagent_prompts` i el perfil de models
  (`llm_chat_model`, `llm_vision_model`, `hardware_profile`, `timeout_budget_s`) viuen
  EXCLUSIVAMENT al disc dur dedicat de cada empresa (`09_copilot_ia/prompt_sistema/`),
  llegits i escrits pel Túnel Invers Natiu WSS (amb cua efímera xifrada `SVENC1:` si el
  PC està en trànsit d'onboarding).
- Cap text de prompt ni dada d'empresa s'emmagatzema a PostgreSQL (`copilot_configs`).
- Caché efímera en memòria (TTL 60 s) invalidada instantàniament en cada `PUT /config`.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Literal, Optional, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.sovereign_storage import SovereignStorageGateway

logger = logging.getLogger("copilot_config_service")

CONFIG_CACHE_TTL_SECONDS: float = 60.0
PROFILE_ITEM_ID: str = "copilot_profile"
SYSTEM_PROMPT_FILENAME: str = "system_prompt.txt"

HardwareProfile = Literal["32GB", "16GB"]

_VERTICAL_DEFAULT_PROMPTS: Dict[str, str] = {
    "CAMPOPRO": (
        "Ets el Copilot Tècnic corporatiu d'una empresa d'instal·lacions agrícoles i regadiu (CampoPro). "
        "Domines canonades PE-100, electrovàlvules, bombes submergibles, filtració, parcel·les SIGPAC i manteniment de finques. "
        "Respon sempre en català clar, directe i operatiu per a enginyers i quadrilles de camp."
    ),
    "ELECTRICPRO": (
        "Ets el Copilot Tècnic corporatiu d'una empresa d'instal·lacions elèctriques de baixa tensió i fotovoltaica (ElectricPro). "
        "Domines normativa REBT, quadres elèctrics, proteccions, seccions de cablejat, inversors i certificacions. "
        "Respon sempre en català clar, precís i orientat a seguretat i normativa."
    ),
    "HYDROPRO": (
        "Ets el Copilot Tècnic corporatiu d'una empresa de fontaneria, aigua i instal·lacions hidràuliques (HydroPro). "
        "Domines xarxes d'abastament, grups de pressió, vàlvules, detecció de fuites i manteniment preventiu. "
        "Respon sempre en català clar, directe i tècnic."
    ),
    "BUILDINGPRO": (
        "Ets el Copilot Tècnic corporatiu d'una empresa d'edificació, reformes i obra civil (BuildingPro). "
        "Domines CTE, coordinació d'oficis, control d'obra, certificacions i seguretat i salut PRL. "
        "Respon sempre en català clar, concís i professional."
    ),
    "CLIMAPRO": (
        "Ets el Copilot Tècnic corporatiu d'una empresa de climatització, aerotèrmia i fred industrial (ClimaPro). "
        "Domines RITE, gasos fluorats, calderes, bombes de calor i manteniment preventiu. "
        "Respon sempre en català clar, directe i precís."
    ),
}


def build_default_vertical_prompt(vertical: str, empresa_nom: str = "") -> str:
    """Genera una plantilla inicial neta (sense noms d'eines) segons la vertical de l'empresa."""
    v_key = (vertical or "SEVALOR").strip().upper()
    base = _VERTICAL_DEFAULT_PROMPTS.get(
        v_key,
        (
            "Ets el Copilot Tècnic corporatiu de l'empresa dins Sevalor Suite. "
            "Ajudes l'oficina tècnica i les quadrilles de camp a consultar ordres de treball, estoc, "
            "flota, clients i protocols interns. Respon sempre en català de forma clara, concisa i rigorosa."
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
    llm_model: str = ""
    llm_chat_model: str = ""
    llm_vision_model: str = ""
    hardware_profile: HardwareProfile = "32GB"
    timeout_budget_s: float = 18.0
    updated_at: Optional[str] = None

    @property
    def effective_chat_model(self) -> str:
        """Model prioritari per a xat/router (`llm_chat_model` o fallback a `llm_model`)."""
        return (self.llm_chat_model or self.llm_model or "").strip()

    @property
    def effective_vision_model(self) -> str:
        """Model prioritari per a OCR/visió (`llm_vision_model`, o `llm_chat_model`, o `llm_model`)."""
        return (self.llm_vision_model or self.llm_chat_model or self.llm_model or "").strip()


# Caché efímera en memòria per empresa_id -> (expires_monotonic, SovereignCopilotProfile)
_PROFILE_CACHE: Dict[str, Tuple[float, SovereignCopilotProfile]] = {}


def invalidate_copilot_config_cache(empresa_id: Optional[UUID | str] = None) -> None:
    """Invalida la caché de configuració del Copilot per a una empresa (o totes si `None`)."""
    if empresa_id is None:
        _PROFILE_CACHE.clear()
        return
    _PROFILE_CACHE.pop(str(empresa_id), None)


def _normalize_hardware_profile(raw: Any) -> HardwareProfile:
    val = str(raw or "32GB").strip().upper()
    return "16GB" if val == "16GB" else "32GB"


def _normalize_timeout_budget(raw: Any, hw_profile: HardwareProfile) -> float:
    default_s = 22.0 if hw_profile == "16GB" else 18.0
    if raw is None or raw == "":
        return default_s
    try:
        parsed = float(raw)
    except (TypeError, ValueError):
        return default_s
    return max(8.0, min(parsed, 30.0))


def _profile_from_dict(empresa_id: UUID, doc: Dict[str, Any], prompt_txt_fallback: str = "") -> SovereignCopilotProfile:
    raw_sub = doc.get("subagent_prompts")
    clean_sub: Dict[str, str] = {}
    if isinstance(raw_sub, dict):
        clean_sub = {
            str(k).strip(): str(v).strip()
            for k, v in raw_sub.items()
            if str(k).strip() and str(v or "").strip()
        }

    hw = _normalize_hardware_profile(doc.get("hardware_profile"))
    timeout_s = _normalize_timeout_budget(doc.get("timeout_budget_s"), hw)
    chat_model = str(doc.get("llm_chat_model") or doc.get("llm_model") or "").strip()
    vision_model = str(doc.get("llm_vision_model") or "").strip()
    sys_prompt = str(doc.get("system_prompt") or prompt_txt_fallback or "").strip()

    return SovereignCopilotProfile(
        empresa_id=empresa_id,
        system_prompt=sys_prompt,
        rag_prompt=str(doc.get("rag_prompt") or "").strip(),
        subagent_prompts=clean_sub,
        llm_model=chat_model,
        llm_chat_model=chat_model,
        llm_vision_model=vision_model,
        hardware_profile=hw,
        timeout_budget_s=timeout_s,
        updated_at=str(doc.get("updated_at") or "") or None,
    )


async def get_strict_copilot_config(
    db: AsyncSession,
    empresa_id: UUID,
    *,
    use_cache: bool = True,
) -> Optional[SovereignCopilotProfile]:
    """Llegeix la configuració del Copilot exclusivament del disc sobirà de l'empresa (`09_copilot_ia/prompt_sistema/`)."""
    cache_key = str(empresa_id)
    now = time.monotonic()
    if use_cache:
        cached = _PROFILE_CACHE.get(cache_key)
        if cached is not None and cached[0] > now:
            return cached[1]

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
            if drain.get("drenats", 0) > 0:
                docs = await SovereignStorageGateway.llegir_entitats_json(
                    db, empresa_id, "copilot_prompt"
                )
                profile_doc = next(
                    (d for d in docs if str(d.get("id") or "") == PROFILE_ITEM_ID),
                    docs[0] if docs else None,
                )
        except Exception as exc:
            logger.debug("Drenatge oportú de configuració copilot omès per %s: %s", empresa_id, exc)

    # 2. Lectura complementària o fallback de `system_prompt.txt` sobirà
    prompt_txt = ""
    if profile_doc is None or not str(profile_doc.get("system_prompt") or "").strip():
        raw_txt = await SovereignStorageGateway.llegir_text_fitxer(
            db, empresa_id, "copilot_prompt", SYSTEM_PROMPT_FILENAME
        )
        prompt_txt = (raw_txt or "").strip()

    if profile_doc is None and not prompt_txt:
        return None

    profile = _profile_from_dict(empresa_id, profile_doc or {}, prompt_txt_fallback=prompt_txt)
    if not profile.system_prompt:
        return None

    _PROFILE_CACHE[cache_key] = (now + CONFIG_CACHE_TTL_SECONDS, profile)
    return profile


async def save_strict_copilot_config(
    db: AsyncSession,
    empresa_id: UUID,
    system_prompt: str,
    rag_prompt: str = "",
    subagent_prompts: Optional[Dict[str, str]] = None,
    llm_model: str = "",
    *,
    llm_chat_model: Optional[str] = None,
    llm_vision_model: Optional[str] = None,
    hardware_profile: str = "32GB",
    timeout_budget_s: Optional[float] = None,
) -> SovereignCopilotProfile:
    """Desa la configuració del Copilot EXCLUSIVAMENT al disc dur dedicat de l'empresa (Zero-Storage Hetzner)."""
    clean_prompt = (system_prompt or "").strip()
    clean_rag = (rag_prompt or "").strip()
    clean_subagents = {
        str(k).strip(): str(v).strip()
        for k, v in (subagent_prompts or {}).items()
        if str(k).strip() and str(v or "").strip()
    }
    hw = _normalize_hardware_profile(hardware_profile)
    timeout_eff = _normalize_timeout_budget(timeout_budget_s, hw)
    chat_model_eff = str(
        llm_chat_model if (llm_chat_model is not None and llm_chat_model.strip()) else (llm_model or "")
    ).strip()
    vision_model_eff = str(llm_vision_model or "").strip()
    updated_at = datetime.now(timezone.utc).isoformat()

    payload_json: Dict[str, Any] = {
        "id": PROFILE_ITEM_ID,
        "empresa_id": str(empresa_id),
        "system_prompt": clean_prompt,
        "rag_prompt": clean_rag,
        "subagent_prompts": clean_subagents,
        "llm_model": chat_model_eff,
        "llm_chat_model": chat_model_eff,
        "llm_vision_model": vision_model_eff,
        "hardware_profile": hw,
        "timeout_budget_s": timeout_eff,
        "updated_at": updated_at,
    }

    # 1. Desa el perfil estructurat signat amb HMAC a `09_copilot_ia/prompt_sistema/copilot_profile.json`
    await SovereignStorageGateway.desar_entitat_json(
        db=db,
        empresa_id=empresa_id,
        categoria="copilot_prompt",
        item_id=PROFILE_ITEM_ID,
        dades=payload_json,
    )

    # 2. Desa també `09_copilot_ia/prompt_sistema/system_prompt.txt` en text pla llegible al PC dedicat
    if clean_prompt:
        await SovereignStorageGateway.pujar_fitxer_binari(
            db=db,
            empresa_id=empresa_id,
            categoria="copilot_prompt",
            nom_fitxer=SYSTEM_PROMPT_FILENAME,
            content=clean_prompt.encode("utf-8"),
            content_type="text/plain; charset=utf-8",
        )

    profile = SovereignCopilotProfile(
        empresa_id=empresa_id,
        system_prompt=clean_prompt,
        rag_prompt=clean_rag,
        subagent_prompts=clean_subagents,
        llm_model=chat_model_eff,
        llm_chat_model=chat_model_eff,
        llm_vision_model=vision_model_eff,
        hardware_profile=hw,
        timeout_budget_s=timeout_eff,
        updated_at=updated_at,
    )
    invalidate_copilot_config_cache(empresa_id)
    if clean_prompt:
        _PROFILE_CACHE[str(empresa_id)] = (time.monotonic() + CONFIG_CACHE_TTL_SECONDS, profile)
    return profile
