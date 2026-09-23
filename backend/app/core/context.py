"""Variables de context per emmagatzemar l'estat del tenant globalment per a cada tasca asíncrona."""

from contextvars import ContextVar

tenant_context: ContextVar[str | None] = ContextVar("tenant_context", default=None)
superadmin_context: ContextVar[bool] = ContextVar("superadmin_context", default=False)
