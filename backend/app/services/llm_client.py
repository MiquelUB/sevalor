"""Client LLM sobirà que enruta tota la inferència exclusivament pel Túnel WSS (ADR-001)."""

import logging
import uuid
from typing import Any, Dict, List, Optional

from app.core.network_utils import extract_wss_tunnel_target
from app.services.vault_tunnel import (
    VaultTunnelError,
    empresa_target_key,
    vault_tunnel_broker,
)

logger = logging.getLogger("llm_client")


class LLMClientError(Exception):
    pass


class LLMClient:
    """Enruta crides OpenAI-compatible al motor LLM local de l'empresa via Túnel WSS Únic."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: int = 120,
        vault_token: Optional[str] = None,
        empresa_id: Optional[str | uuid.UUID] = None,
    ) -> None:
        self.base_url = base_url.strip().rstrip("/") if isinstance(base_url, str) and base_url.strip() else None
        self.timeout = timeout
        self.vault_token = vault_token.strip() if (vault_token and vault_token.strip()) else None
        self.empresa_id: Optional[str] = None
        if empresa_id is not None:
            self.empresa_id = str(uuid.UUID(str(empresa_id)))
        elif self.base_url:
            extracted = extract_wss_tunnel_target(self.base_url)
            if extracted:
                try:
                    self.empresa_id = str(uuid.UUID(extracted))
                except ValueError:
                    self.empresa_id = None

        # Límit anti-saturació de context
        self.MAX_PROMPT_LENGTH = 8000

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = "local-model",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Executa `llm_chat` al PC dedicat de l'empresa mitjançant el Túnel Invers Natiu WSS."""
        if not self.empresa_id:
            raise LLMClientError(
                "No s'ha indicat cap empresa amb túnel WSS sobirà (`wss-tunnel://<empresa_id>`)."
            )

        for msg in messages:
            content = msg.get("content", "")
            if len(content) > self.MAX_PROMPT_LENGTH:
                raise LLMClientError(
                    f"Message content exceeds maximum length of {self.MAX_PROMPT_LENGTH} characters."
                )

        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens

        target_key = empresa_target_key(self.empresa_id)
        try:
            return await vault_tunnel_broker.call_llm_chat(
                target_key, payload, timeout=float(self.timeout)
            )
        except VaultTunnelError as exc:
            logger.error("Error comunicant amb LLM local via WSS (%s): %s", exc.code, exc.detail)
            raise LLMClientError(exc.detail) from exc
