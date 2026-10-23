"""Tests d'integració reals (Zero Mock) per a la seguretat i aïllament de dominis multi-tenant."""

import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.main import app
from app.models.models import Empresa, Usuari


@pytest.fixture
def superadmin_token():
    payload = {
        "sub": "00000000-0000-0000-0000-000000000000",
        "rol": "SUPERADMIN",
        "empresa_id": None,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
        "totp_activat": True,
        "ip_allowlist": ["*"],
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


@pytest.mark.asyncio
async def test_public_tenant_resolve_success(db_session: AsyncSession):
    """Verifica que /public/tenant/resolve retorna únicament la marca cosmètica i dades públiques."""
    empresa_id = uuid.uuid4()
    domini_test = f"tenant-{uuid.uuid4().hex[:6]}.projectexinoxano.cat"

    emp = Empresa(
        id=empresa_id,
        nom="Instal·lacions Soler",
        nif=f"B{uuid.uuid4().hex[:8].upper()}",
        subdomini=f"soler-{uuid.uuid4().hex[:4]}",
        domini_custom=domini_test,
        primari_hsl="152 60% 25%",
        secundari_hsl="152 45% 15%",
        accent_hsl="38 92% 50%",
        logotip_path="https://example.com/logo.png",
        estat_pagament="ACTIU",
    )
    db_session.add(emp)
    await db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Resolució per capçalera Host
        res = await ac.get("/api/v1/public/tenant/resolve", headers={"Host": domini_test})
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["id"] == str(empresa_id)
        assert data["nom"] == "Instal·lacions Soler"
        assert data["domini_custom"] == domini_test
        assert data["primari_hsl"] == "152 60% 25%"
        assert data["logotip_path"] == "https://example.com/logo.png"

        # Zero Data Leak: NIF, dades bancàries i privades NO hi són
        assert "nif" not in data
        assert "iban" not in data
        assert "password" not in data

        # 2. Resolució per query param host
        res_query = await ac.get(f"/api/v1/public/tenant/resolve?host={domini_test}")
        assert res_query.status_code == 200
        assert res_query.json()["id"] == str(empresa_id)


@pytest.mark.asyncio
async def test_public_tenant_resolve_not_found(db_session: AsyncSession):
    """Verifica que un domini inexistent o donat de baixa retorna 404."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/api/v1/public/tenant/resolve", headers={"Host": "no-existeix.cat"})
        assert res.status_code == 404


@pytest.mark.asyncio
async def test_public_tenant_resolve_hibernant_or_suspes(db_session: AsyncSession):
    """Verifica que empreses en HIBERNANT o SUSPES retornen 403."""
    dom_hib = f"hibernant-{uuid.uuid4().hex[:6]}.cat"
    emp = Empresa(
        id=uuid.uuid4(),
        nom="Empresa Hibernant",
        nif=f"B{uuid.uuid4().hex[:8].upper()}",
        subdomini=f"hib-{uuid.uuid4().hex[:4]}",
        domini_custom=dom_hib,
        estat_pagament="HIBERNANT",
    )
    db_session.add(emp)
    await db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/api/v1/public/tenant/resolve", headers={"Host": dom_hib})
        assert res.status_code == 403
        assert "hibernació" in res.json()["detail"]


@pytest.mark.asyncio
async def test_superadmin_host_gate(superadmin_token):
    """Verifica que els endpoints de /superadmin retornen 404 si es criden des del domini d'un client."""
    headers_client_host = {
        "Authorization": f"Bearer {superadmin_token}",
        "Host": "sevalormante.projectexinoxano.cat",
    }
    headers_admin_host = {
        "Authorization": f"Bearer {superadmin_token}",
        "Host": settings.PLATFORM_ADMIN_HOST,
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Crida des del subdomini de client -> 404 Not Found
        res_blocked = await ac.get("/api/v1/superadmin/tenants", headers=headers_client_host)
        assert res_blocked.status_code == 404

        # Crida des del domini oficial d'administració -> 200 OK
        res_allowed = await ac.get("/api/v1/superadmin/tenants", headers=headers_admin_host)
        assert res_allowed.status_code == 200


@pytest.mark.asyncio
async def test_cross_tenant_domain_mismatch_blocked(db_session: AsyncSession):
    """Verifica que un token de l'Empresa A utilitzat des del subdomini de l'Empresa B és rebutjat amb 403."""
    emp_a_id = uuid.uuid4()
    emp_b_id = uuid.uuid4()
    dom_b = f"empresa-b-{uuid.uuid4().hex[:6]}.projectexinoxano.cat"

    emp_b = Empresa(
        id=emp_b_id,
        nom="Empresa B",
        nif=f"B{uuid.uuid4().hex[:8].upper()}",
        subdomini=f"b-{uuid.uuid4().hex[:4]}",
        domini_custom=dom_b,
        estat_pagament="ACTIU",
    )
    db_session.add(emp_b)
    await db_session.commit()

    # Token pertanyent a Empresa A
    token_empresa_a = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "empresa_id": str(emp_a_id),
            "rol": "BOSS",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
        },
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )

    headers = {
        "Authorization": f"Bearer {token_empresa_a}",
        "Host": dom_b,
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/api/v1/gestio/clients", headers=headers)
        assert res.status_code == 403
        assert "Cross-tenant domain mismatch" in res.json()["detail"]


@pytest.mark.asyncio
async def test_login_oficina_domain_gate(db_session: AsyncSession):
    """Verifica que un usuari no pot fer login des del subdomini d'una altra empresa."""
    import bcrypt

    emp_a_id = uuid.uuid4()
    emp_b_id = uuid.uuid4()
    dom_b = f"empresa-b-{uuid.uuid4().hex[:6]}.projectexinoxano.cat"

    emp_a = Empresa(
        id=emp_a_id,
        nom="Empresa A",
        nif=f"B{uuid.uuid4().hex[:8].upper()}",
        subdomini=f"a-{uuid.uuid4().hex[:4]}",
        domini_custom=f"empresa-a-{uuid.uuid4().hex[:6]}.projectexinoxano.cat",
        estat_pagament="ACTIU",
    )
    db_session.add(emp_a)

    emp_b = Empresa(
        id=emp_b_id,
        nom="Empresa B",
        nif=f"B{uuid.uuid4().hex[:8].upper()}",
        subdomini=f"b-{uuid.uuid4().hex[:4]}",
        domini_custom=dom_b,
        estat_pagament="ACTIU",
    )
    db_session.add(emp_b)

    # Usuari pertanyent a Empresa A
    user_a = Usuari(
        id=uuid.uuid4(),
        empresa_id=emp_a_id,
        email=f"boss-{uuid.uuid4().hex[:4]}@empresa-a.cat",
        password_hash=bcrypt.hashpw("Password123!".encode(), bcrypt.gensalt()).decode(),
        rol="BOSS",
        nom="Boss A",
        cognoms="Test",
        nif="44444444A",
    )
    db_session.add(user_a)
    await db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post(
            "/api/v1/auth/login",
            json={"email": user_a.email, "password": "Password123!"},
            headers={"Host": dom_b},
        )
        assert res.status_code == 403
        assert "Aquest usuari no pertany a l'empresa" in res.json()["detail"]

