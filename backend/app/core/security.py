"""Seguretat, control d'accés basat en rols (RBAC) i dependències d'autorització."""

from typing import Any, Callable, Dict, List

import jwt
from fastapi import Depends, HTTPException, Request, status

from app.core.config import settings


def get_current_user_claims(request: Request) -> Dict[str, Any]:
    """Extreu i valida el token JWT Bearer de la petició."""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autenticació requerida. Capçalera Bearer no trobada.",
        )

    token = auth_header.split(" ")[1]
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            options={"verify_aud": False},
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El token d'accés ha expirat.",
        )
    except (jwt.PyJWTError, Exception) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token d'accés invàlid o manipulat.",
        ) from exc


def require_roles(allowed_roles: List[str]) -> Callable:
    """Dependència FastAPI per restringir endpoints a rols específics (Tasca 4.4: Veto d'Enginyer)."""
    def role_checker(claims: Dict[str, Any] = Depends(get_current_user_claims)) -> Dict[str, Any]:
        user_role = claims.get("rol", "").upper()

        # El rol SUPERADMIN té accés de bypass en entorns autoritzats
        if user_role == "SUPERADMIN":
            return claims

        if user_role not in [r.upper() for r in allowed_roles]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Accés denegat: el rol '{user_role}' no té privilegis suficients per accedir a aquest recurs.",
            )
        return claims

    return role_checker


# Veto d'Enginyer: Només BOSS, SECRETARIA o COMPTABILITAT poden accedir a dades financeres
require_financial_access = require_roles(["BOSS", "SECRETARIA", "COMPTABILITAT"])
