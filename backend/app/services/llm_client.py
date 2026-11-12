import logging
from typing import Any, Dict, List, Optional

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.network_utils import build_node_ia_headers, resolve_effective_node_url

logger = logging.getLogger("llm_client")


class LLMClientError(Exception):
    pass


class LLMClient:
    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: int = 30,
        vault_token: Optional[str] = None,
    ):
        resolved = resolve_effective_node_url(base_url)
        url: Optional[str] = str(resolved).rstrip("/") if (resolved and str(resolved).strip()) else None
        self.base_url = url
        self.timeout = timeout
        self.vault_token = vault_token.strip() if (vault_token and vault_token.strip()) else None

        # Max input length to prevent injection or context limit issues
        self.MAX_PROMPT_LENGTH = 8000

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.RequestError, httpx.TimeoutException)),
        reraise=True,
    )
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = "local-model",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Call a local LLM via an OpenAI-compatible API endpoint (like LM Studio).
        """
        if not self.base_url:
            raise LLMClientError(
                "No s'ha configurat cap ordinador dedicat d'IA (node_ia_url) per a aquest client."
            )

        # Validate inputs to prevent context limit exhaustion
        for msg in messages:
            content = msg.get("content", "")
            if len(content) > self.MAX_PROMPT_LENGTH:
                raise LLMClientError(
                    f"Message content exceeds maximum length of {self.MAX_PROMPT_LENGTH} characters."
                )

        url = f"{self.base_url}/chat/completions"

        payload = {"model": model, "messages": messages, "temperature": temperature}
        if max_tokens:
            payload["max_tokens"] = max_tokens

        try:
            headers = build_node_ia_headers(vault_token=self.vault_token)
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                return response.json()  # type: ignore
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTPStatusError calling LLM: {e.response.text}")
            raise LLMClientError(f"API returned status {e.response.status_code}") from e
        except Exception as e:
            logger.error(f"Error calling LLM: {e}")
            raise LLMClientError(f"Failed to communicate with LLM node: {str(e)}") from e
