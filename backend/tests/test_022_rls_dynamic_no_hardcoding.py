import uuid
import bcrypt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.main import app
from app.models.models import Empresa, Usuari

@pytest.mark.asyncio
async def test_rls_dynamic_no_hardcoding(admin_session: AsyncSession):
    """
    Test d'avaluació (Fase 0/1):
    Crea dinàmicament dues empreses (A i B) a la base de dades.
    Crea usuaris BOSS per a cadascuna i fa login real per obtenir JWTs.
    Crea un registre (Client) a l'Empresa A a través de l'API REST.
    Verifica que el Token B no pot veure el Client A (retorna []), demostrant aïllament RLS sense mocks.
    """
    pwd_hash = bcrypt.hashpw(b"Secret123!", bcrypt.gensalt()).decode()

    # 1. Crear Empresa A i Empresa B dinàmicament
    emp_a_id = uuid.uuid4()
    emp_b_id = uuid.uuid4()
    empresa_a = Empresa(id=emp_a_id, nom=f"Empresa A {emp_a_id.hex[:6]}", subdomini=f"empa-{emp_a_id.hex[:6]}", nif=f"A{emp_a_id.hex[:8].upper()}")
    empresa_b = Empresa(id=emp_b_id, nom=f"Empresa B {emp_b_id.hex[:6]}", subdomini=f"empb-{emp_b_id.hex[:6]}", nif=f"B{emp_b_id.hex[:8].upper()}")
    admin_session.add_all([empresa_a, empresa_b])
    await admin_session.flush()

    # 2. Crear Usuari BOSS per a cada empresa
    email_a = f"boss.a.{emp_a_id.hex[:6]}@sevalortest.com"
    email_b = f"boss.b.{emp_b_id.hex[:6]}@sevalortest.com"
    user_a = Usuari(id=uuid.uuid4(), empresa_id=emp_a_id, nom="Boss A", email=email_a, password_hash=pwd_hash, rol="BOSS", nif="11111111A")
    user_b = Usuari(id=uuid.uuid4(), empresa_id=emp_b_id, nom="Boss B", email=email_b, password_hash=pwd_hash, rol="BOSS", nif="22222222B")
    admin_session.add_all([user_a, user_b])
    await admin_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test/api/v1") as client:
        # 3. Login real per obtenir tokens
        res_login_a = await client.post("/auth/login", json={"email": email_a, "password": "Secret123!"})
        assert res_login_a.status_code == 200, f"Login A fallat: {res_login_a.text}"
        token_a = res_login_a.json()["access_token"]
        headers_a = {"Authorization": f"Bearer {token_a}", "X-Empresa-ID": str(emp_a_id)}

        res_login_b = await client.post("/auth/login", json={"email": email_b, "password": "Secret123!"})
        assert res_login_b.status_code == 200, f"Login B fallat: {res_login_b.text}"
        token_b = res_login_b.json()["access_token"]
        headers_b = {"Authorization": f"Bearer {token_b}", "X-Empresa-ID": str(emp_b_id)}

        # 4. Crear Client a l'Empresa A a través de l'endpoint POST /gestio/clients
        payload_client = {
            "nom": "Client Dinamic A",
            "rao_social": "Client Dinamic A S.L.",
            "codi": f"CLI-{emp_a_id.hex[:4]}",
            "nif": f"C{emp_a_id.hex[:8].upper()}",
            "email": "client@dinamic.com",
            "telefon": "611223344"
        }
        res_create = await client.post("/gestio/clients", json=payload_client, headers=headers_a)
        assert res_create.status_code == 201, f"Creació client fallada: {res_create.text}"
        created_client_id = res_create.json()["id"]

        # 5. Comprovar que l'Empresa A veu el seu client
        res_list_a = await client.get("/gestio/clients", headers=headers_a)
        assert res_list_a.status_code == 200
        items_a = res_list_a.json()
        assert any(c["id"] == created_client_id for c in items_a)

        # 6. Comprovar que l'Empresa B no veu cap client (retorna [])
        res_list_b = await client.get("/gestio/clients", headers=headers_b)
        assert res_list_b.status_code == 200
        items_b = res_list_b.json()
        assert len(items_b) == 0
        assert not any(c["id"] == created_client_id for c in items_b)
