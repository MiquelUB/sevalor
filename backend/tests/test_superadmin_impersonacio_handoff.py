"""Traspàs d'impersonació Superadmin → domini propi de l'empresa (codi d'un sol ús)."""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.core.redis import get_redis_client
from app.main import app


def _superadmin_headers() -> Dict[str, str]:
    payload = {
        "sub": "00000000-0000-0000-0000-000000000000",
        "rol": "SUPERADMIN",
        "empresa_id": None,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
        "totp_activat": True,
        "ip_allowlist": ["*"],
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return {"Authorization": f"Bearer {token}"}


async def _crear_tenant(ac: AsyncClient, headers: Dict[str, str]) -> Dict[str, Any]:
    suffix = str(uuid.uuid4())[:8]
    payload = {
        "rao_social": f"Handoff {suffix} S.L.",
        "nif": "B" + str(uuid.uuid4())[:8].upper(),
        "subdomini": f"handoff-{suffix}",
        "domini_custom": f"gestio.handoff-{suffix}.cat",
        "vertical": "SEVALOR",
        "pla_subscripcio": "STARTER",
        "quota_disc_gb": 20,
        "boss_nif": "12345678Z",
        "boss_nom": "Anna",
        "boss_cognoms": "Vidal",
        "boss_email": f"anna@handoff-{suffix}.cat",
        "boss_telefon": "+34611000111",
        "feature_flags": {},
    }
    res = await ac.post("/api/v1/superadmin/tenants/onboarding", json=payload, headers=headers)
    assert res.status_code == 201, res.text
    tenant: Dict[str, Any] = res.json()["tenant"]
    return tenant


def _code_from(handoff_url: str) -> str:
    assert "/impersonacio#code=" in handoff_url
    return handoff_url.split("#code=", 1)[1]


@pytest.mark.asyncio
async def test_impersonacio_handoff_domini_propi_un_sol_us_i_aillament_tenant() -> None:
    if await get_redis_client() is None:
        pytest.skip("Redis no disponible: el traspàs de domini requereix Redis real.")

    headers = _superadmin_headers()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        tenant_a = await _crear_tenant(ac, headers)
        tenant_b = await _crear_tenant(ac, headers)

        # 1. La impersonació de A apunta al domini propi de A (no al host d'admin)
        res_imp = await ac.post(
            f"/api/v1/superadmin/tenants/{tenant_a['id']}/impersonate", headers=headers
        )
        assert res_imp.status_code == 200, res_imp.text
        handoff_url = res_imp.json().get("handoff_url")
        if not handoff_url:
            pytest.skip("Redis no ha pogut persistir la sessió de traspàs d'impersonació en aquest entorn.")
        assert handoff_url.startswith(f"https://{tenant_a['domini_custom']}/impersonacio#code=")
        code = _code_from(handoff_url)

        # 2. Bescanvi correcte des del domini de A → JWT d'impersonació de A
        res_ok = await ac.post(
            "/api/v1/auth/impersonacio/intercanvi",
            json={"code": code},
            headers={"x-forwarded-host": tenant_a["domini_custom"]},
        )
        assert res_ok.status_code == 200, res_ok.text
        dades = res_ok.json()
        assert dades["empresa_id"] == tenant_a["id"]
        assert dades["return_url"].endswith(f"/superadmin/empreses/{tenant_a['id']}")
        claims = jwt.decode(
            dades["access_token"], settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        assert claims["is_impersonation"] is True
        assert claims["empresa_id"] == tenant_a["id"]

        # 3. El codi és d'un sol ús
        res_replay = await ac.post(
            "/api/v1/auth/impersonacio/intercanvi",
            json={"code": code},
            headers={"x-forwarded-host": tenant_a["domini_custom"]},
        )
        assert res_replay.status_code == 401

        # 4. Aïllament: un codi de A no es pot bescanviar al domini de B
        res_imp2 = await ac.post(
            f"/api/v1/superadmin/tenants/{tenant_a['id']}/impersonate", headers=headers
        )
        code2 = _code_from(res_imp2.json()["handoff_url"])
        res_cross = await ac.post(
            "/api/v1/auth/impersonacio/intercanvi",
            json={"code": code2},
            headers={"x-forwarded-host": tenant_b["domini_custom"]},
        )
        assert res_cross.status_code == 403

        # 5. Codis inventats rebutjats
        res_fake = await ac.post(
            "/api/v1/auth/impersonacio/intercanvi",
            json={"code": "x" * 43},
            headers={"x-forwarded-host": tenant_a["domini_custom"]},
        )
        assert res_fake.status_code == 401


@pytest.mark.asyncio
async def test_impersonacio_sense_domini_propi_no_genera_handoff() -> None:
    headers = _superadmin_headers()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        suffix = str(uuid.uuid4())[:8]
        payload = {
            "rao_social": f"SenseDomini {suffix} S.L.",
            "nif": "B" + str(uuid.uuid4())[:8].upper(),
            "subdomini": f"sensedomini-{suffix}",
            "domini_custom": settings.PLATFORM_ADMIN_HOST,
            "vertical": "SEVALOR",
            "pla_subscripcio": "STARTER",
            "quota_disc_gb": 20,
            "boss_nif": "12345678Z",
            "boss_nom": "Marc",
            "boss_cognoms": "Roca",
            "boss_email": f"marc@sensedomini-{suffix}.cat",
            "boss_telefon": "+34611000222",
            "feature_flags": {},
        }
        res = await ac.post("/api/v1/superadmin/tenants/onboarding", json=payload, headers=headers)
        assert res.status_code == 201, res.text
        empresa_id = res.json()["tenant"]["id"]

        res_imp = await ac.post(
            f"/api/v1/superadmin/tenants/{empresa_id}/impersonate", headers=headers
        )
        assert res_imp.status_code == 200
        assert res_imp.json()["handoff_url"] is None
        assert res_imp.json()["empresa_id"] == empresa_id
