"""Classe base abstracta per als Subagents especialitzats de Sevalor Suite."""

import uuid
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession


class BaseSubagent(ABC):
    """Classe base per a tots els subagents especialitzats."""

    id: str
    nom: str
    descripcio: str
    allowed_roles: List[str]
    system_prompt: str
    tools_schema: List[Dict[str, Any]]

    @abstractmethod
    def can_handle(self, query: str, rol: str) -> bool:
        """Determina si aquest subagent té la competència per atendre la consulta."""
        pass

    @abstractmethod
    async def execute_tool(
        self, tool_name: str, args: dict, db: AsyncSession, empresa_id: uuid.UUID
    ) -> dict:
        """Executa l'eina indicada contra la base de dades sota context RLS."""
        pass

    @abstractmethod
    async def run_sovereign(
        self, pregunta: str, db: AsyncSession, empresa_id: uuid.UUID
    ) -> Tuple[str, Optional[str], Optional[dict], Optional[dict], List[dict]]:
        """
        Execució sobirana local determinista (Zero Mock Data) quan LM Studio
        està offline o no retorna una crida de tool estructurada.
        Retorna (resposta, tool_name, tool_args, tool_resultat, enllacos).
        """
        pass
