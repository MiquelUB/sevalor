import uuid

import bcrypt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.models.models import Empresa, Usuari


@pytest.mark.asyncio
async def test_auth_login_invalid_credentials(db_session: AsyncSession):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test/api/v1") as client:
        resp = await client.post("/auth/login", json={
            "email": "nonexistent@example.com",
            "password": "wrongpassword"
        })
        assert resp.status_code == 401
        assert "Credencials" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_auth_login_operari_blocked(admin_session: AsyncSession):
    operari = Usuari(
        id=uuid.uuid4(),
        nif="11111111A",
        nom="Operari Test",
        email="operari@example.com",
        password_hash=bcrypt.hashpw("secret123".encode("utf-8"), bcrypt.gensalt()).decode("utf-8"),
        rol="OPERARI",
    )
    admin_session.add(operari)
    await admin_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test/api/v1") as client:
        resp = await client.post("/auth/login", json={
            "email": "operari@example.com",
            "password": "secret123"
        })
        assert resp.status_code == 403
        assert "PIN" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_auth_login_success_and_me(admin_session: AsyncSession):
    empresa = Empresa(
        id=uuid.uuid4(),
        nom="Empresa Test Auth",
        nif="B99999999",
        subdomini="authtest",
    )
    admin_session.add(empresa)
    await admin_session.flush()

    user_id = uuid.uuid4()
    boss = Usuari(
        id=user_id,
        empresa_id=empresa.id,
        nif="22222222B",
        nom="Boss Test",
        email="boss@authtest.com",
        password_hash=bcrypt.hashpw("Password123!".encode("utf-8"), bcrypt.gensalt()).decode("utf-8"),
        rol="BOSS",
    )
    admin_session.add(boss)
    await admin_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test/api/v1") as client:
        # 1. Login
        resp = await client.post("/auth/login", json={
            "email": "boss@authtest.com",
            "password": "Password123!"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["rol"] == "BOSS"
        assert data["nom"] == "Boss Test"

        token = data["access_token"]

        # 2. Call /auth/me without token -> 401
        me_unauth = await client.get("/auth/me")
        assert me_unauth.status_code == 401

        # 3. Call /auth/me with token -> 200
        me_auth = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me_auth.status_code == 200
        me_data = me_auth.json()
        assert me_data["id"] == str(user_id)
        assert me_data["rol"] == "BOSS"
        assert me_data["nom"] == "Boss Test"
        assert me_data["email"] == "boss@authtest.com"
        assert me_data["empresa_id"] == str(empresa.id)
