"""Classe base abstracta per als Subagents especialitzats de Sevalor Suite (Zero-Storage Sobirà)."""

import re
import uuid
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.sovereign_storage import SovereignStorageGateway


class BaseSubagent(ABC):
    """Classe base per a tots els subagents especialitzats (lectura exclusiva al disc de l'empresa)."""

    id: str
    nom: str
    descripcio: str
    allowed_roles: List[str]
    system_prompt: str
    tools_schema: List[Dict[str, Any]]

    async def read_sovereign_category(
        self,
        db: AsyncSession,
        empresa_id: uuid.UUID,
        categoria: str,
    ) -> List[Dict[str, Any]]:
        """Llegeix totes les fitxes verificades (HMAC + tenant) d'una categoria al disc de l'empresa."""
        return await SovereignStorageGateway.llegir_entitats_json(db, empresa_id, categoria)

    async def save_sovereign_entity(
        self,
        db: AsyncSession,
        empresa_id: uuid.UUID,
        categoria: str,
        item_id: str | uuid.UUID,
        dades: Dict[str, Any],
    ) -> str:
        """Desa una fitxa JSON signada amb HMAC al disc dur dedicat de l'empresa."""
        return await SovereignStorageGateway.desar_entitat_json(
            db, empresa_id, categoria, item_id, dades
        )

    async def read_sovereign_text(
        self,
        db: AsyncSession,
        empresa_id: uuid.UUID,
        categoria: str,
        nom_fitxer: str,
    ) -> Optional[str]:
        """Llegeix un fitxer de text (p.ex. system_prompt.txt) directament del disc de l'empresa."""
        return await SovereignStorageGateway.llegir_text_fitxer(
            db, empresa_id, categoria, nom_fitxer
        )

    async def search_sovereign_categories(
        self,
        db: AsyncSession,
        empresa_id: uuid.UUID,
        categories: Sequence[str],
        query_text: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Cerca textual multi-carpeta sobre fitxes verificades del disc dur del tenant."""
        q_norm = (query_text or "").strip().lower()
        tokens = [t for t in re.split(r"[\s,;:\-_]+", q_norm) if len(t) >= 2]
        resultats: List[Dict[str, Any]] = []
        for cat in categories:
            registres = await self.read_sovereign_category(db, empresa_id, cat)
            for item in registres:
                haystack = " ".join(
                    str(v)
                    for k, v in item.items()
                    if k != "_sovereign_meta" and v is not None
                ).lower()
                if not q_norm or q_norm in haystack or any(tok in haystack for tok in tokens):
                    resultats.append({**item, "_categoria": cat})
                    if len(resultats) >= limit:
                        return resultats
        return resultats

    @staticmethod
    def match_query_record(
        record: Dict[str, Any],
        query_text: str,
        fields: Optional[Sequence[str]] = None,
    ) -> bool:
        """Comprova coincidència segura (exacta o per tokens significatius) en una fitxa JSON."""
        q_norm = (query_text or "").strip().lower()
        if not q_norm:
            return True
        keys = fields if fields is not None else [k for k in record.keys() if k != "_sovereign_meta"]
        haystack = " ".join(str(record.get(k, "")) for k in keys if record.get(k) is not None).lower()
        if q_norm in haystack:
            return True
        tokens = [t for t in re.split(r"[\s,;:/\-_]+", q_norm) if len(t) >= 3]
        return bool(tokens and any(tok in haystack for tok in tokens))

    @abstractmethod
    def can_handle(self, query: str, rol: str) -> bool:
        """Determina si aquest subagent té la competència per atendre la consulta."""
        pass

    @abstractmethod
    async def execute_tool(
        self,
        tool_name: str,
        args: dict,
        db: AsyncSession,
        empresa_id: uuid.UUID,
        caller_role: Optional[str] = None,
        caller_user_id: Optional[uuid.UUID] = None,
        **kwargs: Any,
    ) -> dict:
        """Executa l'eina indicada contra el disc dur dedicat de l'empresa."""
        pass

    @abstractmethod
    async def run_sovereign(
        self,
        pregunta: str,
        db: AsyncSession,
        empresa_id: uuid.UUID,
        caller_role: Optional[str] = None,
        caller_user_id: Optional[uuid.UUID] = None,
        **kwargs: Any,
    ) -> Tuple[str, Optional[str], Optional[dict], Optional[dict], List[dict]]:
        """
        Execució sobirana sobre el disc dur dedicat de l'empresa (Zero Mock Data, Zero Hetzner SQL).
        Retorna (resposta, tool_name, tool_args, tool_resultat, enllacos).
        """
        pass

