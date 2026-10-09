import pytest
from httpx import AsyncClient
import uuid
import jwt
from datetime import datetime, timezone, timedelta
from app.core.config import settings

@pytest.fixture(scope="function")
def headers_enginyer():
    empresa_id = str(uuid.uuid4())
    payload = {
        "sub": str(uuid.uuid4()),
        "rol": "ENGINYER",
        "empresa_id": empresa_id,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return {
        "Authorization": f"Bearer {token}",
        "X-Empresa-ID": empresa_id,
    }

@pytest.mark.asyncio
async def test_configuracio_empresa_boss_only(async_client: AsyncClient, headers_enginyer):
    payload = {"nom": "Nova Empresa SA"}
    
    response = await async_client.put(
        "/gestio/configuracio/empresa",
        json=payload,
        headers=headers_enginyer
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_configuracio_node_ia_permisos_i_actualitzacio(
    async_client: AsyncClient, headers, headers_enginyer, admin_session
):
    from app.models.models import Empresa
    from sqlalchemy import select

    # 1. Crear l'empresa per al Boss de prova
    empresa_id_boss = uuid.UUID(headers["X-Empresa-ID"])
    res = await admin_session.execute(select(Empresa).where(Empresa.id == empresa_id_boss))
    empresa = res.scalar_one_or_none()
    if not empresa:
        empresa = Empresa(
            id=empresa_id_boss,
            nom="Empresa Sobirana Test",
            nif=f"B{empresa_id_boss.hex[:8].upper()}",
            vertical="ELECTRICPRO",
            node_ia_actiu=False,
            node_ia_url=None,
        )
        admin_session.add(empresa)
        await admin_session.commit()

    # 2. Intent d'actualització per part d'ENGINYER -> 403 Veto
    resp_enginyer = await async_client.put(
        "/gestio/configuracio/node-ia",
        json={"node_ia_url": "http://192.168.1.100:1234/v1", "node_ia_actiu": True},
        headers=headers_enginyer,
    )
    assert resp_enginyer.status_code == 403

    # 3. Estat inicial del node -> SENSE_ORDINADOR_DEDICAT
    resp_estat_inicial = await async_client.get(
        "/gestio/copilot/estat-node",
        headers=headers,
    )
    assert resp_estat_inicial.status_code == 200
    dades_inicials = resp_estat_inicial.json()
    assert dades_inicials["node_actiu"] is False
    assert dades_inicials["estat"] == "SENSE_ORDINADOR_DEDICAT"

    # 4. Actualització autoritzada pel Boss
    resp_boss = await async_client.put(
        "/gestio/configuracio/node-ia",
        json={
            "node_ia_url": "https://ia.empresa-sobirana.cat/v1",
            "node_ia_actiu": True,
            "agent_prompt_system": "Prioritza sempre les normatives REBT ITC-BT-28.",
        },
        headers=headers,
    )
    assert resp_boss.status_code == 200
    assert resp_boss.json()["status"] == "OK"

    # 5. Consulta de paràmetres de node-ia desada
    resp_get = await async_client.get(
        "/gestio/configuracio/node-ia",
        headers=headers,
    )
    assert resp_get.status_code == 200
    dades_node = resp_get.json()
    assert dades_node["node_ia_url"] == "https://ia.empresa-sobirana.cat/v1"
    assert dades_node["node_ia_actiu"] is True
    assert dades_node["te_ordinador_dedicat"] is True
    assert "REBT" in dades_node["agent_prompt_system"]

    # 6. Estat del Copilot reflectint l'ordinador dedicat actiu
    resp_estat_actiu = await async_client.get(
        "/gestio/copilot/estat-node",
        headers=headers,
    )
    assert resp_estat_actiu.status_code == 200
    dades_actiu = resp_estat_actiu.json()
    assert dades_actiu["node_actiu"] is True
    assert dades_actiu["estat"] == "ORDINADOR_DEDICAT_ACTIU"
    assert dades_actiu["proveidor"] == "Ordinador Local Dedicat de l'Empresa"
