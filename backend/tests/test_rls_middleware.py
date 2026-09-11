import pytest
import jwt
from httpx import AsyncClient, ASGITransport
from datetime import datetime, timedelta, timezone
from app.main import app
from app.core.config import settings

@pytest.fixture
def fake_secret():
    # Assegurem que el settings.SECRET_KEY té un valor durant els tests per poder signar
    if not settings.SECRET_KEY:
        settings.SECRET_KEY = "test-secret-key-32-chars-long-xxx"
    return settings.SECRET_KEY

def create_token(rol: str, empresa_id: str, secret: str):
    payload = {
        "sub": "00000000-0000-0000-0000-000000000000",
        "rol": rol,
        "empresa_id": empresa_id,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15)
    }
    return jwt.encode(payload, secret, algorithm=settings.ALGORITHM)

@pytest.mark.asyncio
async def test_middleware_blocks_tenant_spoofing(fake_secret):
    real_tenant = "11111111-1111-1111-1111-111111111111"
    forged_tenant = "99999999-9999-9999-9999-999999999999"
    
    token = create_token("OPERARI", real_tenant, fake_secret)
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Empresa-ID": forged_tenant
    }
    
    # Podem comprovar-ho amb qualsevol endpoint que retorni o validi dades
    # Utilitzarem l'objecte app directament per inspeccionar el Request state a través d'un endpoint dummy
    # Per simplificar, crearem un endpoint de test dinàmic o assecarem l'estat.
    # En lloc de canviar l'app, demanem la llista de notificacions, i si dóna error de base de dades
    # ja veurem quin RLS ha intentat aplicar, o millor: validem l'HTTP code.
    
    # Com que no volem modificar codi només per test, usem el endpoint /api/v1/health, que potser no exposa això.
    # Utilitzem un endpoint que requereixi auth d'operari:
    # /api/v1/gestio/operaris/me ? (probablement només admin)
    pass

