import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.main import app
from app.models.models import Empresa, Usuari

pytestmark = pytest.mark.asyncio


async def test_flux_complet_activacio_gerent(db_session: AsyncSession):
    # 1. Crear empresa i usuari BOSS pendent d'activar
    emp_uuid = uuid.uuid4()
    boss_uuid = uuid.uuid4()
    subdomini = f"activatest-{uuid.uuid4().hex[:6]}"
    email = f"boss-{uuid.uuid4().hex[:6]}@empresa.cat"

    emp = Empresa(
        id=emp_uuid,
        nom="Instal·lacions del Nord S.L.",
        nif=f"B{uuid.uuid4().hex[:8].upper()}",
        subdomini=subdomini,
        domini_custom=f"sevalor.{subdomini}.cat",
        primari_hsl="142 76% 36%",
        estat_pagament="TRIAL",
    )
    db_session.add(emp)

    boss = Usuari(
        id=boss_uuid,
        empresa_id=emp_uuid,
        nif=f"DNI{uuid.uuid4().hex[:5].upper()}",
        nom="Laura",
        cognoms="Soler",
        email=email,
        telefon="+34611223344",
        rol="BOSS",
        estat="ACTIU",
        password_hash=None,
    )
    db_session.add(boss)
    await db_session.commit()

    # 2. Generar token d'activació de 24 hores
    token = jwt.encode(
        {
            "sub": str(boss_uuid),
            "action": "activate",
            "exp": datetime.now(timezone.utc) + timedelta(hours=24),
        },
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 3. Verificar token
        res_verif = await client.get(f"/api/v1/auth/activacio/verificar?token={token}")
        assert res_verif.status_code == 200
        data_verif = res_verif.json()
        assert data_verif["valid"] is True
        assert data_verif["nom"] == "Laura"
        assert data_verif["empresa_nom"] == "Instal·lacions del Nord S.L."

        # 4. Provar contrasenyes que no coincideixen -> 422
        res_fail = await client.post(
            "/api/v1/auth/activacio",
            json={
                "token": token,
                "password": "Password123!",
                "password_confirm": "Diferent123!",
            },
        )
        assert res_fail.status_code == 422

        # 5. Completar activació amb contrasenya correcta
        res_ok = await client.post(
            "/api/v1/auth/activacio",
            json={
                "token": token,
                "password": "NovaPasswordSegura123!",
                "password_confirm": "NovaPasswordSegura123!",
            },
        )
        assert res_ok.status_code == 200
        assert res_ok.json()["status"] == "ACTIVATED"

        # 6. Provar login amb la nova contrasenya
        res_login = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "NovaPasswordSegura123!"},
        )
        assert res_login.status_code == 200
        assert "access_token" in res_login.json()
        assert res_login.json()["rol"] == "BOSS"
