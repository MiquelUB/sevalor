import json
import uuid
from pathlib import Path

import pytest

from app.models.models import Empresa
from app.services.sovereign_storage import SovereignStorageGateway
from app.workers.tasks import crear_directoris_sobirans
from tests.wss_test_helpers import live_empresa_wss_context, wait_for


@pytest.mark.asyncio
async def test_resoldre_desti_disc_elimina_fallback_hardcoded(db_session, tmp_path: Path, monkeypatch):
    """ADR-001 (Fase 0): Sense disc_dur_url NO hi ha fallback silenciós a /tmp/sevalor_client_disks ni /data/disc_*; encua a OFFLINE_TRANSIT xifrat SVENC1:."""
    transit_dir = tmp_path / "sevalor_transit_fase0"
    monkeypatch.setenv("SOVEREIGN_TRANSIT_QUEUE_DIR", str(transit_dir))
    monkeypatch.setattr(SovereignStorageGateway, "TRANSIT_QUEUE_DIR", transit_dir)

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

    mode, base_target, _ = await SovereignStorageGateway.resoldre_desti_disc_empresa(db_session, emp_id)
    assert mode == "OFFLINE_TRANSIT"
    assert base_target == f"wss-tunnel://{emp_id}"
    assert "/media/akaun" not in base_target
    assert "/tmp/sevalor_client_disks" not in base_target
    assert not Path(f"/tmp/sevalor_client_disks/disc_{emp.subdomini}").exists()

    # Escriure entitat sense disc configurat NO escriu text pla a Hetzner; xifra SVENC1: a la cua de trànsit
    ref = await SovereignStorageGateway.desar_entitat_json(
        db=db_session,
        empresa_id=emp_id,
        categoria="clients",
        item_id="cli_fase0",
        dades={"nom": "Client Zero Storage"},
    )
    assert ref == f"transit://{emp_id}/01_clients/fitxes/cli_fase0"
    bin_files = list((transit_dir / str(emp_id)).glob("*.bin"))
    assert len(bin_files) == 1
    raw_bin = bin_files[0].read_bytes()
    assert raw_bin.startswith(b"SVENC1:")
    assert b"Client Zero Storage" not in raw_bin


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
    Zero Mock (WSS):
    1. Si l'agent WSS del client està offline, es genera paquet xifrat SVENC1: a la cua de trànsit.
    2. Retorna ruta transit://...
    3. Quan l'agent WSS real connecta, els fitxers es drenen al disc físic del client i es purguen de Hetzner.
    """
    transit_dir = tmp_path / "sevalor_transit_queue"
    monkeypatch.setenv("SOVEREIGN_TRANSIT_QUEUE_DIR", str(transit_dir))
    monkeypatch.setattr(SovereignStorageGateway, "TRANSIT_QUEUE_DIR", transit_dir)

    emp_id = uuid.uuid4()
    vault_token = f"svlt_{uuid.uuid4().hex}"
    emp = Empresa(
        id=emp_id,
        nom="Empresa Transit Test SL",
        nif=f"B{uuid.uuid4().int % 10000000:07d}A",
        subdomini=f"transittest-{emp_id.hex[:6]}",
        disc_dur_url=f"wss-tunnel://{emp_id}",
        node_ia_url=f"wss-tunnel://{emp_id}",
        vault_token=vault_token,
    )
    db_session.add(emp)
    await db_session.flush()

    # 1. Intent de desar entitat amb node WSS desconnectat -> Ha d'encuar xifrat SVENC1:
    entitat_id = f"cli_{uuid.uuid4().hex[:6]}"
    dades = {"nom": "Client de Camp", "nif": "12345678Z"}

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

    # 2. Agent WSS real torna a estar en línia -> auto-drenatge i auto-purga immediata
    disk_a = tmp_path / "disk_transit_a"
    async with live_empresa_wss_context(emp_id, vault_token, disk_a, start_llm=False):
        target_file = disk_a / "01_clients" / "fitxes" / f"{entitat_id}.json"
        await wait_for(lambda: target_file.exists(), timeout=8.0)
        stats = await SovereignStorageGateway.drenar_cua_transit_empresa(db_session, emp_id)
        assert stats["pendents"] == 0
        assert not emp_transit_folder.exists()
        saved = json.loads(target_file.read_text(encoding="utf-8"))
        assert saved["nom"] == "Client de Camp"
        assert saved["nif"] == "12345678Z"
