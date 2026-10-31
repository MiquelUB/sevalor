"""Middleware de seguretat per a l'extracció de context multi-tenant (Spec 012)."""

import uuid
from typing import Optional

import jwt
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.core.config import settings
from app.core.redis import get_redis_client, is_tenant_blacklisted


async def resoldre_empresa_id_per_host(clean_host: str) -> Optional[str]:
    """Cerca l'empresa_id associat a un domini o subdomini, amb suport de memòria cau."""
    if not clean_host or clean_host in ("localhost", "127.0.0.1", "testserver", "test"):
        return None

    parts = clean_host.split(".")
    subdomini = parts[0] if len(parts) >= 3 else None

    # 1. Comprovar Redis si està disponible
    redis_client = await get_redis_client()
    cache_key = f"host_to_tenant:{clean_host}"
    if redis_client:
        try:
            cached = await redis_client.get(cache_key)
            if cached == "NONE":
                return None
            if cached:
                return cached.decode("utf-8") if isinstance(cached, bytes) else str(cached)
        except Exception:
            pass

    # 2. Consulta a la base de dades
    empresa_id = None
    try:
        from sqlalchemy import func, or_, select

        from app.core.db import AsyncSessionLocal, get_db
        from app.main import app
        from app.models.models import Empresa

        conds = [func.lower(Empresa.domini_custom) == clean_host]
        if subdomini and subdomini not in ("www", "api", "app", "localhost", "sevalor", "superadmin"):
            conds.append(func.lower(Empresa.subdomini) == subdomini)

        if get_db in app.dependency_overrides:
            gen = app.dependency_overrides[get_db]()
            test_session = await anext(gen)
            stmt = select(Empresa.id).where(or_(*conds))
            res = await test_session.execute(stmt)
            row = res.scalar()
            if row:
                empresa_id = str(row)
        else:
            async with AsyncSessionLocal() as session:
                stmt = select(Empresa.id).where(or_(*conds))
                res = await session.execute(stmt)
                row = res.scalar()
                if row:
                    empresa_id = str(row)
    except Exception:
        pass

    # 3. Desar a Redis amb TTL de 120 segons
    if redis_client:
        try:
            val = empresa_id or "NONE"
            await redis_client.set(cache_key, val, ex=120)
        except Exception:
            pass

    return empresa_id


class TenantMiddleware(BaseHTTPMiddleware):
    """Intercepta peticions HTTP per extreure l'empresa_id del tenant i associar-lo al request.state."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method == "OPTIONS":
            return await call_next(request)

        raw_host = request.headers.get("x-forwarded-host") or request.headers.get("host") or ""
        clean_host = (
            raw_host.strip()
            .lower()
            .replace("https://", "")
            .replace("http://", "")
            .split("/")[0]
            .split(":")[0]
        )
        request.state.tenant_host = clean_host
        is_local = clean_host in ("localhost", "127.0.0.1", "testserver", "test", "")

        path = request.url.path

        # 1. Blindatge Host de Superadmin:
        # Només el domini oficial de la plataforma pot accedir a /api/v1/superadmin
        if path.startswith("/api/v1/superadmin"):
            admin_host = (settings.PLATFORM_ADMIN_HOST or "").strip().lower()
            if not is_local and admin_host and clean_host != admin_host:
                return JSONResponse(
                    status_code=404,
                    content={"detail": "Not Found"},
                )

        empresa_id: str | None = None
        is_superadmin: bool = False
        is_impersonation: bool = False
        jwt_empresa_id: str | None = None
        user_role: str | None = None

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

                raw_role = payload.get("rol")
                if raw_role:
                    user_role = str(raw_role).upper()

                if user_role == "SUPERADMIN":
                    is_impersonation = bool(payload.get("is_impersonation", False))
                    if not is_impersonation or path.startswith("/api/v1/superadmin"):
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
            empresa_id = jwt_empresa_id or request.headers.get("X-Empresa-ID")

        elif not auth_header:
            # Per a usuaris anònims (ex. pantalla de login PWA), acceptem X-Empresa-ID
            header_tenant = request.headers.get("X-Empresa-ID")
            if header_tenant:
                empresa_id = header_tenant.strip()

        # 2. Resolució automàtica per Host si no ve informat
        host_empresa_id = None
        if not is_local:
            host_empresa_id = await resoldre_empresa_id_per_host(clean_host)

        if not empresa_id and host_empresa_id:
            empresa_id = host_empresa_id

        # 3. Protecció Cross-Tenant (Zero-Trust):
        # Si un usuari autenticat d'un tenant intenta consumir l'API des del subdomini d'un altre tenant:
        # Les sessions d'impersonació autoritzada de Superadmin estan expressament exemptes del bloqueig cross-tenant
        if jwt_empresa_id and not is_superadmin and not is_impersonation and host_empresa_id:
            if str(jwt_empresa_id) != str(host_empresa_id):
                return JSONResponse(
                    status_code=403,
                    content={
                        "detail": "Cross-tenant domain mismatch: el token no pertany al domini d'aquesta empresa."
                    },
                )

        if empresa_id:
            try:
                empresa_id = str(uuid.UUID(str(empresa_id)))
            except Exception:
                empresa_id = None

        request.state.empresa_id = empresa_id
        request.state.is_superadmin = is_superadmin
        request.state.is_impersonation = is_impersonation
        request.state.user_role = user_role

        if is_superadmin:
            if path.startswith("/api/v1/") and not (
                path.startswith("/api/v1/superadmin")
                or path.startswith("/api/v1/auth")
                or path.startswith("/api/v1/health")
            ):
                return JSONResponse(
                    status_code=403,
                    content={
                        "detail": "Zero-Trust Segregation: SUPERADMIN no pot accedir a rutes operatives de negoci."
                    },
                )
        elif empresa_id:
            if path.startswith("/api/v1/") and not (
                path.startswith("/api/v1/auth")
                or path.startswith("/api/v1/health")
                or path.startswith("/api/v1/public/")
            ):
                blocked_state = await is_tenant_blacklisted(empresa_id)
                if blocked_state:
                    return JSONResponse(
                        status_code=403,
                        content={
                            "detail": f"El compte de l'empresa està en estat '{blocked_state}'. Contacteu amb l'administració de Sevalor per regularitzar el servei."
                        },
                    )

        from app.core.context import role_context, superadmin_context, tenant_context

        token_tenant = tenant_context.set(empresa_id)
        token_superadmin = superadmin_context.set(is_superadmin)
        token_role = role_context.set(user_role)

        try:
            response = await call_next(request)
            return response
        finally:
            tenant_context.reset(token_tenant)
            superadmin_context.reset(token_superadmin)
            role_context.reset(token_role)
