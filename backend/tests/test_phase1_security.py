import uuid

import bcrypt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.gestio.operaris import hash_pin
from app.main import app
from app.models.models import Empresa, Usuari


@pytest.mark.asyncio
async def test_crear_usuari_equip_uses_real_bcrypt(admin_session: AsyncSession):
    """Verifica que crear un usuari a /gestio/configuracio/equip genera un hash bcrypt real (no simulated)."""
    empresa_id = uuid.uuid4()
    empresa = Empresa(
        id=empresa_id,
        nom="Empresa Hash Test",
        nif="B11223344",
        subdomini="hashtest",
    )
    admin_session.add(empresa)
    await admin_session.flush()

    boss_id = uuid.uuid4()
    boss = Usuari(
        id=boss_id,
        empresa_id=empresa_id,
        nif="33333333C",
        nom="Boss Gestio",
        email="boss@hashtest.com",
        password_hash=bcrypt.hashpw("Password123!".encode(), bcrypt.gensalt()).decode(),
        rol="BOSS",
    )
    admin_session.add(boss)
    await admin_session.commit()

    # Login as BOSS to get token
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test/api/v1") as client:
        login_res = await client.post("/auth/login", json={
            "email": "boss@hashtest.com",
            "password": "Password123!"
        })
        assert login_res.status_code == 200
        token = login_res.json()["access_token"]

        headers = {
            "Authorization": f"Bearer {token}",
            "X-Empresa-ID": str(empresa_id)
        }

        # Crear nou membre d'equip
        payload = {
            "nif": "44444444D",
            "nom": "Maria",
            "cognoms": "Secretaria",
            "email": "maria@hashtest.com",
            "rol": "SECRETARIA"
        }
        res = await client.post("/gestio/configuracio/usuaris", json=payload, headers=headers)
        assert res.status_code == 200, res.text
        data = res.json()
        temp_pwd = data["contrasenya_temporal_12_caracters"]

        # Consultar usuari creat a la BD i verificar el password_hash
        stmt = select(Usuari).where(Usuari.email == "maria@hashtest.com")
        r = await admin_session.execute(stmt)
        nou_usuari = r.scalars().first()
        assert nou_usuari is not None
        assert not nou_usuari.password_hash.startswith("bcrypt_simulated_"), "El password_hash encara és simulat!"
        assert nou_usuari.password_hash.startswith("$2b$") or nou_usuari.password_hash.startswith("$2a$"), "No és un hash bcrypt vàlid"
        assert bcrypt.checkpw(temp_pwd.encode(), nou_usuari.password_hash.encode()), "El password temporal no coincideix amb el hash bcrypt!"


@pytest.mark.asyncio
async def test_operari_pin_bloqueig_i_desbloqueig_via_reset_pin(admin_session: AsyncSession):
    """Verifica el cicle complet: intents fallits -> bloqueig 403 -> reset-pin pel Boss -> desbloqueig."""
    empresa_id = uuid.uuid4()
    empresa = Empresa(
        id=empresa_id,
        nom="Empresa Bloqueig Test",
        nif="B55667788",
        subdomini="bloqueigtest",
    )
    admin_session.add(empresa)
    await admin_session.flush()

    boss_id = uuid.uuid4()
    boss = Usuari(
        id=boss_id,
        empresa_id=empresa_id,
        nif="55555555E",
        nom="Boss Desbloquejador",
        email="boss@bloqueigtest.com",
        password_hash=bcrypt.hashpw("Password123!".encode(), bcrypt.gensalt()).decode(),
        rol="BOSS",
    )
    admin_session.add(boss)

    operari_id = uuid.uuid4()
    operari_nif = "66666666F"
    operari_pin = "4321"
    operari = Usuari(
        id=operari_id,
        empresa_id=empresa_id,
        nif=operari_nif,
        nom="Operari Bloquejable",
        rol="OPERARI",
        telefon="+34600112233",
        pin_hash=hash_pin(operari_pin),
        pin_bloquejat=False,
        intents_pin_fallits=0,
    )
    admin_session.add(operari)
    await admin_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test/api/v1") as client:
        op_headers = {"X-Empresa-ID": str(empresa_id)}

        # 3 intents fallits -> 401
        for _ in range(3):
            r = await client.post("/operari_auth/login", json={"nif": operari_nif, "pin": "9999"}, headers=op_headers)
            assert r.status_code == 401

        # 4t intent fallit -> 403 (compte bloquejat)
        r4 = await client.post("/operari_auth/login", json={"nif": operari_nif, "pin": "9999"}, headers=op_headers)
        assert r4.status_code == 403

        # Fins i tot amb el PIN correcte ha de donar 403
        r_correct_blocked = await client.post("/operari_auth/login", json={"nif": operari_nif, "pin": operari_pin}, headers=op_headers)
        assert r_correct_blocked.status_code == 403

        # Boss fa login i desbloqueja amb reset-pin
        boss_login = await client.post("/auth/login", json={"email": "boss@bloqueigtest.com", "password": "Password123!"})
        boss_token = boss_login.json()["access_token"]
        boss_headers = {"Authorization": f"Bearer {boss_token}", "X-Empresa-ID": str(empresa_id)}

        reset_res = await client.post(f"/gestio/operaris/{operari_id}/reset-pin", headers=boss_headers)
        assert reset_res.status_code == 200
        assert reset_res.json()["pin_bloquejat"] is False
        assert reset_res.json()["intents_pin_fallits"] == 0

        # Ara l'operari ja no està bloquejat a la BD
        r_fresh = await admin_session.execute(select(Usuari).where(Usuari.id == operari_id))
        op_db = r_fresh.scalars().first()
        assert op_db.pin_bloquejat is False
        assert op_db.intents_pin_fallits == 0


@pytest.mark.asyncio
async def test_emergencia_2fa_boss(admin_session: AsyncSession):
    """Verifica l'accés d'emergència 2FA amb consum de codi."""
    empresa_id = uuid.uuid4()
    empresa = Empresa(
        id=empresa_id,
        nom="Empresa Emergencia Test",
        nif="B99887766",
        subdomini="emergenciatest",
        codis_recuperacio_2fa=["EMERGENCY-KEY-001", "EMERGENCY-KEY-002"]
    )
    admin_session.add(empresa)
    await admin_session.flush()

    boss_id = uuid.uuid4()
    boss = Usuari(
        id=boss_id,
        empresa_id=empresa_id,
        nif="77777777G",
        nom="Boss Desesperat",
        email="boss@emergenciatest.com",
        password_hash=bcrypt.hashpw("Password123!".encode(), bcrypt.gensalt()).decode(),
        rol="BOSS",
        totp_activat=True,
        secret_2fa="OLD_SECRET_TOTP",
    )
    admin_session.add(boss)
    await admin_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test/api/v1") as client:
        # Codi incorrecte -> 403
        bad_res = await client.post("/gestio/configuracio/emergencia-2fa-boss", json={
            "nif": "77777777G",
            "codi_recuperacio": "WRONG-KEY"
        })
        assert bad_res.status_code == 403

        # Codi correcte -> 200 i consum del codi
        good_res = await client.post("/gestio/configuracio/emergencia-2fa-boss", json={
            "nif": "77777777G",
            "codi_recuperacio": "EMERGENCY-KEY-001"
        })
        assert good_res.status_code == 200
        assert good_res.json()["status"] == "ACCES_AUTORITZAT"
        assert good_res.json()["codis_restants"] == 1

        # El codi utilitzat no pot tornar a ser usat -> 403
        reuse_res = await client.post("/gestio/configuracio/emergencia-2fa-boss", json={
            "nif": "77777777G",
            "codi_recuperacio": "EMERGENCY-KEY-001"
        })
        assert reuse_res.status_code == 403
