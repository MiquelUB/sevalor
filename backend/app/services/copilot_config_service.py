"""Servei de configuració estrictament aïllada del Copilot IA per empresa (RLS + PK)."""

from typing import Dict, Optional
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.copilot_config import CopilotConfig


async def _bind_rls_tenant(db: AsyncSession, empresa_id: UUID) -> None:
    """Vincula la sessió actual de PostgreSQL a l'empresa_id via set_config (equivalent a SET LOCAL)."""
    await db.execute(
        text("SELECT set_config('app.current_empresa_id', :eid, true)"),
        {"eid": str(empresa_id)},
    )


async def get_strict_copilot_config(
    db: AsyncSession, empresa_id: UUID
) -> Optional[CopilotConfig]:
    """Llegeix la configuració del Copilot exclusivament per a empresa_id amb RLS actiu."""
    await _bind_rls_tenant(db, empresa_id)
    res = await db.execute(
        select(CopilotConfig).where(CopilotConfig.empresa_id == empresa_id)
    )
    return res.scalar_one_or_none()


async def save_strict_copilot_config(
    db: AsyncSession,
    empresa_id: UUID,
    system_prompt: str,
    rag_prompt: str,
    subagent_prompts: Dict[str, str],
    llm_model: str = "",
) -> CopilotConfig:
    """Crea o actualitza la configuració del Copilot exclusivament per a empresa_id amb RLS actiu."""
    await _bind_rls_tenant(db, empresa_id)
    cfg = await get_strict_copilot_config(db, empresa_id)
    clean_subagents = {
        str(k).strip(): str(v).strip()
        for k, v in (subagent_prompts or {}).items()
        if str(k).strip()
    }
    if not cfg:
        cfg = CopilotConfig(
            empresa_id=empresa_id,
            system_prompt=system_prompt.strip(),
            rag_prompt=rag_prompt.strip(),
            subagent_prompts=clean_subagents,
            llm_model=llm_model.strip(),
        )
        db.add(cfg)
    else:
        cfg.system_prompt = system_prompt.strip()
        cfg.rag_prompt = rag_prompt.strip()
        cfg.subagent_prompts = clean_subagents
        cfg.llm_model = llm_model.strip()

    await db.commit()
    await db.refresh(cfg)
    return cfg
