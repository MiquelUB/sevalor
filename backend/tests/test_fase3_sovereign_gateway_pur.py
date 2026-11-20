# backend/tests/test_fase3_sovereign_gateway_pur.py
import json
import uuid
from pathlib import Path

import pytest

from app.models.models import Empresa
from app.services.sovereign_storage import SovereignStorageGateway
from tests.wss_test_helpers import live_empresa_wss_context, wait_for


@pytest.mark.asyncio
async def test_cua_transit_auto_purga_quan_agent_torna_online(db_session, tmp_path: Path, monkeypatch):
    """Zero Mock (WSS): si l'agent WSS està offline s'encua SVENC1: i en connectar es drena i es purga de Hetzner."""
    monkeypatch.setattr(SovereignStorageGateway, "TRANSIT_QUEUE_DIR", tmp_path / "transit_queue")
    emp_id = uuid.uuid4()
    vault_token = f"svlt_pur_{uuid.uuid4().hex[:16]}"
    emp = Empresa(
        id=emp_id,
        nom="Sevalormante Transit Test",
        nif=f"B{uuid.uuid4().int % 10000000:07d}C",
        subdomini=f"transit-{emp_id.hex[:6]}",
        disc_dur_url=f"wss-tunnel://{emp_id}",
        node_ia_url=f"wss-tunnel://{emp_id}",
        vault_token=vault_token,
    )
    db_session.add(emp)
    await db_session.flush()

    # 1. Amb l'agent WSS apagat, s'encua en trànsit xifrat SVENC1:
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

    # 2. L'agent WSS real torna online -> drenatge i auto-purga immediata
    disk_a = tmp_path / "disk_a"
    async with live_empresa_wss_context(emp_id, vault_token, disk_a, start_llm=False):
        target_file = disk_a / "01_clients" / "fitxes" / "client_1.json"
        await wait_for(lambda: target_file.exists(), timeout=8.0)
        res = await SovereignStorageGateway.drenar_cua_transit_empresa(db_session, emp_id)
        assert res["pendents"] == 0
        assert not emp_queue_dir.exists()
        assert json.loads(target_file.read_text(encoding="utf-8"))["nom"] == "Client Camp"
