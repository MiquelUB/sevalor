"""Middleware de seguretat per a l'extracció de context multi-tenant (Spec 012)."""

import jwt
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.core.config import settings

class TenantMiddleware(BaseHTTPMiddleware):
    """Intercepta peticions HTTP per extreure l'empresa_id del tenant i associar-lo al request.state."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        empresa_id: str | None = None
        is_superadmin: bool = False
        jwt_empresa_id: str | None = None

        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            try:
                payload = jwt.decode(
                    token,
                    settings.SECRET_KEY,
                    algorithms=[settings.ALGORITHM],
                    options={"verify_aud": False},
                )
                
                if payload.get("rol") == "SUPERADMIN":
                    is_superadmin = True
                
                extret_id = payload.get("empresa_id")
                if extret_id:
                    jwt_empresa_id = str(extret_id)
                    empresa_id = jwt_empresa_id

            except (jwt.PyJWTError, Exception):
                pass

        if is_superadmin:
            header_tenant = request.headers.get("X-Empresa-ID")
            if header_tenant:
                empresa_id = header_tenant.strip()
                    
        elif auth_header:
            empresa_id = jwt_empresa_id
            
        elif not auth_header:
            # Per a usuaris anònims (ex. pantalla de login PWA), acceptem X-Empresa-ID
            header_tenant = request.headers.get("X-Empresa-ID")
            if header_tenant:
                empresa_id = header_tenant.strip()
            else:
                host = request.headers.get("host", "").split(":")[0]
                parts = host.split(".")
                if len(parts) >= 3 and parts[0] not in ("www", "api", "app", "localhost"):
                    request.state.subdomain = parts[0]

        request.state.empresa_id = empresa_id
        request.state.is_superadmin = is_superadmin

        response = await call_next(request)
        return response
