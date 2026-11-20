"""Model SQLAlchemy per a la configuració estrictament aïllada del Copilot IA per empresa."""

from sqlalchemy import Column, DateTime, ForeignKey, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.core.db import Base


class CopilotConfig(Base):
    """Configuració sobirana i aïllada del Copilot IA per empresa (PK = empresa_id, FORCE RLS)."""

    __tablename__ = "copilot_configs"

    empresa_id = Column(
        UUID(as_uuid=True),
        ForeignKey("empreses.id", ondelete="CASCADE"),
        primary_key=True,
    )
    system_prompt = Column(Text, nullable=False, default="", server_default="")
    rag_prompt = Column(Text, nullable=False, default="", server_default="")
    subagent_prompts = Column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    llm_model = Column(String(120), nullable=False, default="", server_default="")
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
