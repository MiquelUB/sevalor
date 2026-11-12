import json
import uuid
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
from httpx import Response

from app.models.models import Empresa
from app.services.sovereign_storage import SovereignStorageGateway
from app.workers.tasks import crear_directoris_sobirans


@pytest.mark.asyncio
async def test_resoldre_desti_disc_elimina_fallback_hardcoded(db_session, tmp_path: Path):
    """Verifica que una empresa anomenada Sevalormante NO utilitza el fallback de /media/akaun."""
    emp_id = uuid.uuid4()
    emp = Empresa(
        id=emp_id,
        nom="Sevalormante Manteniment SL",
        nif=f"B{uuid.uuid4().int % 10000000:07d}A",
        subdomini=f"sevalormante-{emp_id.hex[:6]}",
        disc_dur_url=None,
    )
    db_session.add(emp)
    await db_session.flush()

    mode, base_target, secret = await SovereignStorageGateway.resoldre_desti_disc_empresa(db_session, emp_id)
    assert mode == "LOCAL_FS"
    assert "/media/akaun" not in base_target
    assert f"disc_{emp.subdomini}" in base_target


@pytest.mark.asyncio
async def test_crear_directoris_sobirans_zero_fugides_hetzner(tmp_path: Path, monkeypatch):
    """Verifica que crear_directoris_sobirans no escriu a /data ni /docs d'Hetzner."""
    vaults_dir = tmp_path / "client_vaults"
    monkeypatch.setenv("CLIENT_DISKS_MOUNT_ROOT", str(vaults_dir))

    emp_id = str(uuid.uuid4())
    creades = crear_directoris_sobirans(emp_id)

    assert len(creades) > 0
    # Totes les rutes han de ser filles de CLIENT_DISKS_MOUNT_ROOT
    for ruta in creades:
        assert str(vaults_dir) in ruta
        assert not ruta.startswith("/data/")
        assert not ruta.startswith("/docs/")


@pytest.mark.asyncio
async def test_cua_transit_temporal_i_auto_purga_immediata(db_session, tmp_path: Path, monkeypatch):
    """
    Verifica que:
    1. Si l'Agent HTTP del client està apagat (RequestError), es genera paquet a la cua de trànsit.
    2. Retorna ruta transit://...
    3. Quan l'agent torna a respondre 200 OK, drenar_cua_transit_empresa purga immediatament els fitxers temporals.
    """
    transit_dir = tmp_path / "sevalor_transit_queue"
    monkeypatch.setenv("SOVEREIGN_TRANSIT_QUEUE_DIR", str(transit_dir))
    SovereignStorageGateway.TRANSIT_QUEUE_DIR = transit_dir

    emp_id = uuid.uuid4()
    vault_token = f"svlt_{uuid.uuid4().hex}"
    emp = Empresa(
        id=emp_id,
        nom="Empresa Transit Test SL",
        nif=f"B{uuid.uuid4().int % 10000000:07d}A",
        subdomini=f"transittest-{emp_id.hex[:6]}",
        disc_dur_url="http://node-offline.local:9001",
        telegram_webhook_secret=vault_token,
    )
    db_session.add(emp)
    await db_session.flush()

    # 1. Intent de desar entitat amb node desconnectat -> Ha d'encuar a trànsit
    entitat_id = f"cli_{uuid.uuid4().hex[:6]}"
    dades = {"nom": "Client de Camp", "nif": "12345678Z"}

    def offline_put(*args, **kwargs):
        raise httpx.ConnectError("Connection refused: node apagat")

    with patch.object(httpx.AsyncClient, "put", side_effect=offline_put):
        transit_ref = await SovereignStorageGateway.desar_entitat_json(
            db=db_session,
            empresa_id=emp_id,
            categoria="clients",
            item_id=entitat_id,
            dades=dades,
        )

    assert transit_ref.startswith(f"transit://{emp_id}/01_clients/fitxes/{entitat_id}")

    emp_transit_folder = transit_dir / str(emp_id)
    assert emp_transit_folder.exists()
    meta_files = list(emp_transit_folder.glob("*.meta.json"))
    bin_files = list(emp_transit_folder.glob("*.bin"))
    assert len(meta_files) == 1
    assert len(bin_files) == 1

    meta_content = json.loads(meta_files[0].read_text(encoding="utf-8"))
    assert meta_content["empresa_id"] == str(emp_id)
    assert meta_content["subcarpeta"] == "01_clients/fitxes"
    assert meta_content["identificador"] == entitat_id

    # 2. Node torna a estar en línia -> Drenar cua amb auto-purga immediata
    recorded_drains = []

    async def online_put(self, url, *args, **kwargs):
        recorded_drains.append((str(url), kwargs.get("headers", {}), kwargs.get("content", b"")))
        return Response(status_code=200, json={"status": "SAVED"})

    with patch.object(httpx.AsyncClient, "put", new=online_put):
        stats = await SovereignStorageGateway.drenar_cua_transit_empresa(db_session, emp_id)

    assert stats["enviats"] == 1
    assert stats["pendents"] == 0
    assert len(recorded_drains) == 1
    assert recorded_drains[0][1].get("X-Vault-Token") == vault_token
    assert f"01_clients/fitxes/{entitat_id}" in recorded_drains[0][0]

    # Auto-purga: els fitxers temporals i la carpeta d'empresa han d'haver desaparegut completament
    assert not emp_transit_folder.exists()
