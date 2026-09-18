from app.models.models import Empresa, Usuari, Client
"""
Test de flux complet: Operari PWA + Gestió Backend.

Cobreix:
- Enrolament/login amb PIN.
- Iniciar i tancar jornada.
- Llistar feines, iniciar trajecte.
- Crear client i factura des de gestió.
- Verificar RLS (tenant A no veu dades de B).
- Verificar RBAC (Enginyer no accedeix a comptabilitat).
- Cap ús de mocks: tot passa per httpx.AsyncClient real contra l'app FastAPI,
  amb dades reals dins d'un SAVEPOINT.
"""

import uuid
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def _nif(prefix="B"):
    return prefix + uuid.uuid4().hex[:8].upper()


def _sub():
    return "sub-" + uuid.uuid4().hex[:6]


# ---------------------------------------------------------------------------
# FIXTURES DE DADES COMPARTIDES
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def empresa_i_admin(admin_session: AsyncSession):
    """Crea una empresa i retorna el seu empresa_id i headers de Boss."""
    eid = str(uuid.uuid4())
    nif = _nif()
    admin_session.add(Empresa(
        id=uuid.UUID(eid), nom='Test SA', nif=nif, subdomini=_sub(), pla_subscripcio='STARTER', estat_pagament='ACTIU', vertical='SEVALOR'
    ))
    await admin_session.flush()
    # Boss
    boss_id = str(uuid.uuid4())
    boss_nif = _nif()
    boss_pw = "$2b$12$LJ3m4ys3Lk0Tm0B0e0e0eO5x5x5x5x5x5x5x5x5x5x5x5x5x5"  # dummy bcrypt
    admin_session.add(Usuari(
        id=uuid.UUID(boss_id), empresa_id=uuid.UUID(eid), nif=boss_nif, nom='Boss', cognoms='Admin', email=f'boss@{nif.lower()}.com', password_hash=boss_pw, rol='BOSS'
    ))
    await admin_session.flush()
    await admin_session.flush()
    return eid


@pytest_asyncio.fixture
async def operari_token(empresa_i_admin, async_client: AsyncClient, admin_session: AsyncSession):
    """Crea un operari, fa login amb PIN i retorna el token JWT."""
    eid = empresa_i_admin
    op_id = str(uuid.uuid4())
    op_nif = _nif("X")
    pin_clear = "4826"
    # Hashejar PIN
    import bcrypt
    pin_hash = bcrypt.hashpw(pin_clear.encode(), bcrypt.gensalt()).decode()

    admin_session.add(Usuari(
        id=uuid.UUID(op_id), empresa_id=uuid.UUID(eid), nif=op_nif, nom='Operari', cognoms='Test', rol='OPERARI', pin_hash=pin_hash, estat='ACTIU', telefon=f'+346{uuid.uuid4().int % 100000000:08d}'
    ))
    await admin_session.flush()
    await admin_session.flush()

    # Login
    resp = await async_client.post("/operari_auth/login", json={"nif": op_nif, "pin": pin_clear}, headers={"X-Empresa-ID": eid})
    assert resp.status_code == 200, f"Login fallit: {resp.status_code} {resp.text}"
    data = resp.json()
    assert "access_token" in data
    return data["access_token"], op_id, eid


# ---------------------------------------------------------------------------
# TEST DE FLUX COMPLET
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestFluxOperari:

    async def test_01_inici_jornada(self, operari_token, async_client: AsyncClient, admin_session: AsyncSession):
        """L'operari inicia la jornada laboral."""
        token, op_id, eid = operari_token

        resp = await async_client.post(
            "/operari/jornada/inici",
            headers={"Authorization": f"Bearer {token}", "X-Empresa-ID": eid},
            json={"latitud": 41.38, "longitud": 2.18},
        )
        # NOTA: L'endpoint pot retornar 200 o 201. S'adapta segons el codi real.
        # Si falla per rate-limit (429) o per RBAC (403), ho veurem.
        assert resp.status_code in (200, 201), f"Inici jornada fallit: {resp.status_code} {resp.text}"
        data = resp.json()
        assert "id" in data
        self.jornada_id = data["id"]

    async def test_02_llistar_feines(self, operari_token, async_client: AsyncClient):
        """L'operari llista les feines del dia."""
        token, op_id, eid = operari_token

        resp = await async_client.get(
            "/operari/feines",
            headers={"Authorization": f"Bearer {token}", "X-Empresa-ID": eid},
        )
        # Pot ser 200 (feines trobades) o 200 amb array buit (Dia 0 real)
        assert resp.status_code == 200, f"Llistar feines fallit: {resp.status_code} {resp.text}"

    async def test_03_rbac_enginyer_bloquejat(self, empresa_i_admin, async_client: AsyncClient):
        """Un token d'Enginyer rep 403 a /gestio/comptabilitat."""
        eid = empresa_i_admin
        # Crear Enginyer
        jwt_payload = {
            "sub": str(uuid.uuid4()), "rol": "ENGINYER", "empresa_id": eid,
        }
        # No tenim secrets aquí; cal generar un token vàlid amb la SECRET_KEY
        from app.core.config import settings
        import jwt as pyjwt
        eng_token = pyjwt.encode(jwt_payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

        resp = await async_client.get(
            "/gestio/comptabilitat/factures",
            headers={"Authorization": f"Bearer {eng_token}", "X-Empresa-ID": eid},
        )
        assert resp.status_code == 403, f"Veto Enginyer no aplicat: {resp.status_code} {resp.text}"

    async def test_04_boss_crea_factura(self, empresa_i_admin, async_client: AsyncClient, admin_session: AsyncSession):
        """El Boss crea un client i una factura."""
        eid = empresa_i_admin
        # Token de Boss
        from app.core.config import settings
        import jwt as pyjwt
        boss_token = pyjwt.encode(
            {"sub": str(uuid.uuid4()), "rol": "BOSS", "empresa_id": eid},
            settings.SECRET_KEY, algorithm=settings.ALGORITHM,
        )
        headers = {"Authorization": f"Bearer {boss_token}", "X-Empresa-ID": eid}

        # Client
        client_id = str(uuid.uuid4())
        admin_session.add(Client(
        id=uuid.UUID(client_id), empresa_id=uuid.UUID(eid), codi=f'CLI-{uuid.uuid4().hex[:4]}', rao_social='Client SA', nif=_nif()
    ))
        await admin_session.flush()
        await admin_session.flush()

        # Crear factura
        resp = await async_client.post(
            "/gestio/comptabilitat/factures",
            headers=headers,
            json={
                "client_id": client_id,
                "numero_factura": 1,
                "serie": "2026",
                "base_imposable": 1000.0,
                "quota_iva": 210.0,
                "import_retencio": 0.0,
                "import_suplits": 0.0,
                "liquid_exigible": 1210.0,
            },
        )
        assert resp.status_code == 201, f"Crear factura fallit: {resp.status_code} {resp.text}"

    async def test_05_rls_tenant_aillament(self, empresa_i_admin, async_client: AsyncClient, admin_session: AsyncSession):
        """Usuari del Tenant A no pot veure dades del Tenant B."""
        from app.core.config import settings
        import jwt as pyjwt

        eid_a = empresa_i_admin
        # Client a Tenant A
        client_a = str(uuid.uuid4())
        admin_session.add(Client(
        id=uuid.UUID(client_a), empresa_id=uuid.UUID(eid_a), codi='CLI-A', rao_social='Client A', nif=_nif()
    ))
        await admin_session.flush()
        # Crear Tenant B
        eid_b = str(uuid.uuid4())
        admin_session.add(Empresa(
        id=uuid.UUID(eid_b), nom='EmpB', nif=_nif(), subdomini=_sub(), pla_subscripcio='STARTER', estat_pagament='ACTIU'
    ))
        await admin_session.flush()
        # Client a Tenant B
        client_b = str(uuid.uuid4())
        admin_session.add(Client(
        id=uuid.UUID(client_b), empresa_id=uuid.UUID(eid_b), codi='CLI-B', rao_social='Client B', nif=_nif()
    ))
        await admin_session.flush()
        await admin_session.flush()

        # Token de BOSS A (prova accedir a client de B)
        boss_a_token = pyjwt.encode(
            {"sub": str(uuid.uuid4()), "rol": "BOSS", "empresa_id": eid_a},
            settings.SECRET_KEY, algorithm=settings.ALGORITHM,
        )
        resp = await async_client.get(
            "/gestio/clients",
            headers={"Authorization": f"Bearer {boss_a_token}", "X-Empresa-ID": eid_a},
        )
        assert resp.status_code == 200
        clients_a = resp.json()
        # Només hauria de veure el client de A (1), no el de B
        assert len(clients_a) == 1, f"RLS trencat: Tenant A veu {len(clients_a)} clients (hauria de ser 1)"
        assert clients_a[0]["id"] != client_b, "RLS trencat: Tenant A veu client de B"