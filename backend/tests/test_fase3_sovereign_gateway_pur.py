# backend/tests/test_fase3_sovereign_gateway_pur.py
import uuid
from pathlib import Path

import httpx
import pytest

from app.models.models import Empresa
from app.services.sovereign_storage import SovereignStorageGateway


@pytest.mark.asyncio
async def test_cua_transit_auto_purga_quan_agent_torna_online(db_session, tmp_path: Path, monkeypatch):
    """Verifica que si l'Agent HTTP està caigut s'encua el paquet i, en tornar online (200 OK), es buida de Hetzner."""
    SovereignStorageGateway.TRANSIT_QUEUE_DIR = tmp_path / "transit_queue"
    emp_id = uuid.uuid4()
    emp = Empresa(
        id=emp_id,
        nom="Sevalormante Transit Test",
        nif=f"B{uuid.uuid4().int % 10000000:07d}C",
        subdomini=f"transit-{emp_id.hex[:6]}",
        disc_dur_url="http://127.0.0.1:19999",  # Port tancat inicialment
        telegram_webhook_secret="svlt_test_secret_123",
    )
    db_session.add(emp)
    await db_session.commit()

    # 1. Amb l'agent apagat, s'encua en trànsit
    uri = SovereignStorageGateway._encuar_paquet_transit(
        empresa_id=emp_id,
        tipus="JSON",
        subcarpeta="01_clients/fitxes",
        identificador="client_1",
        payload_bytes=b'{"id": "client_1", "nom": "Client Camp"}',
    )
    assert uri.startswith("transit://")
    emp_queue_dir = SovereignStorageGateway.TRANSIT_QUEUE_DIR / str(emp_id)
    assert len(list(emp_queue_dir.glob("*.bin"))) == 1

    # 2. Simular resposta 200 OK de l'Agent HTTP del client i drenar
    async def _mock_put(self, url, **kwargs):
        return httpx.Response(200, json={"status": "SAVED"})

    monkeypatch.setattr(httpx.AsyncClient, "put", _mock_put)
    res = await SovereignStorageGateway.drenar_cua_transit_empresa(db_session, emp_id)
    assert res["enviats"] == 1
    assert res["pendents"] == 0
    assert not emp_queue_dir.exists()
