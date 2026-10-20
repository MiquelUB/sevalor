import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.models import Empresa
import uuid
import jwt
from datetime import datetime, timezone, timedelta
from app.core.config import settings

@pytest.fixture
def superadmin_token():
    payload = {
        "sub": str(uuid.uuid4()),
        "rol": "SUPERADMIN",
        "totp_activat": True,
        "ip_allowlist": ["*"],
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

@pytest.fixture
async def my_empresa(db_session: AsyncSession):
    emp = Empresa(nom="Test", nif=f"123456{uuid.uuid4().hex[:3]}")
    db_session.add(emp)
    await db_session.commit()
    await db_session.refresh(emp)
    return emp

@pytest.fixture
def boss_token_for_empresa(my_empresa):
    payload = {
        "sub": str(uuid.uuid4()),
        "rol": "BOSS",
        "empresa_id": str(my_empresa.id),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

@pytest.mark.asyncio
async def test_update_camaleo_config_superadmin(
    async_client: AsyncClient,
    db_session: AsyncSession,
    superadmin_token: str,
    my_empresa: Empresa
):
    payload = {
        "primari_hsl": "100 50% 50%",
        "domini_custom": "custom.sevalor.com"
    }
    headers = {"Authorization": f"Bearer {superadmin_token}"}

    response = await async_client.put(
        f"/superadmin/empreses/{my_empresa.id}/camaleo",
        json=payload,
        headers=headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "OK"
    assert data["configuracio_actualitzada"]["primari_hsl"] == "100 50% 50%"
    assert data["configuracio_actualitzada"]["domini_custom"] == "custom.sevalor.com"

    # Verifiquem a la BD
    result = await db_session.execute(select(Empresa).where(Empresa.id == my_empresa.id))
    emp = result.scalars().first()
    assert emp.primari_hsl == "100 50% 50%"
    assert emp.domini_custom == "custom.sevalor.com"

@pytest.mark.asyncio
async def test_update_camaleo_config_boss(
    async_client: AsyncClient,
    boss_token_for_empresa: str,
    my_empresa: Empresa
):
    payload = {
        "logotip_path": "/path/to/logo.png",
        "favicon_path": "/path/to/favicon.ico"
    }
    headers = {"Authorization": f"Bearer {boss_token_for_empresa}"}

    response = await async_client.put(
        f"/superadmin/empreses/{my_empresa.id}/camaleo",
        json=payload,
        headers=headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "OK"
    assert data["configuracio_actualitzada"]["logotip_path"] == "/path/to/logo.png"
    
@pytest.mark.asyncio
async def test_update_camaleo_config_boss_forbidden(
    async_client: AsyncClient,
    boss_token_for_empresa: str
):
    other_empresa_id = str(uuid.uuid4())
    payload = {
        "logotip_path": "/path/to/logo.png"
    }
    headers = {"Authorization": f"Bearer {boss_token_for_empresa}"}

    response = await async_client.put(
        f"/superadmin/empreses/{other_empresa_id}/camaleo",
        json=payload,
        headers=headers
    )
    
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_update_company_details_camaleo(
    async_client: AsyncClient,
    db_session: AsyncSession,
    superadmin_token: str,
    my_empresa: Empresa,
):
    payload = {
        "nom": "Empresa Renovada SL",
        "adreca": "Carrer Major 42, Lleida",
        "vertical": "CAMPOPRO",
        "primari_hsl": "142 71% 28%",
        "secundari_hsl": "38 92% 50%",
        "accent_hsl": "160 84% 39%",
    }
    headers = {"Authorization": f"Bearer {superadmin_token}"}

    response = await async_client.put(
        f"/superadmin/empreses/{my_empresa.id}/camaleo",
        json=payload,
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "OK"
    assert data["configuracio_actualitzada"]["nom"] == "Empresa Renovada SL"
    assert data["configuracio_actualitzada"]["adreca"] == "Carrer Major 42, Lleida"
    assert data["configuracio_actualitzada"]["vertical"] == "CAMPOPRO"

    await db_session.refresh(my_empresa)
    assert my_empresa.nom == "Empresa Renovada SL"
    assert my_empresa.adreca == "Carrer Major 42, Lleida"
    assert my_empresa.vertical == "CAMPOPRO"


@pytest.mark.asyncio
async def test_pujar_logotip_magic_bytes_valid_png(
    async_client: AsyncClient,
    superadmin_token: str,
    my_empresa: Empresa,
):
    # PNG Magic bytes: \x89PNG\r\n\x1a\n + payload fictici
    valid_png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
    files = {"fitxer": ("logo.png", valid_png_bytes, "image/png")}
    headers = {"Authorization": f"Bearer {superadmin_token}"}

    response = await async_client.post(
        f"/superadmin/empreses/{my_empresa.id}/logotip",
        files=files,
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "OK"
    assert data["format"] == "png"
    assert "logo_oficial.png" in data["logotip_path"]


@pytest.mark.asyncio
async def test_pujar_logotip_magic_bytes_invalid_415(
    async_client: AsyncClient,
    superadmin_token: str,
    my_empresa: Empresa,
):
    # Fitxer de text simulant ser PNG
    invalid_bytes = b"TEXT_NOT_AN_IMAGE_12345"
    files = {"fitxer": ("fake_logo.png", invalid_bytes, "image/png")}
    headers = {"Authorization": f"Bearer {superadmin_token}"}

    response = await async_client.post(
        f"/superadmin/empreses/{my_empresa.id}/logotip",
        files=files,
        headers=headers,
    )

    assert response.status_code == 415


@pytest.mark.asyncio
async def test_obtenir_logotip_endpoint(
    async_client: AsyncClient,
    my_empresa: Empresa,
):
    # L'endpoint públic/intern de logotip ha de retornar 200 OK (imatge o SVG monograma)
    response = await async_client.get(f"/superadmin/empreses/{my_empresa.id}/logotip")
    assert response.status_code == 200
    assert "image" in response.headers.get("content-type", "")

