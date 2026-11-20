# backend/tests/test_fase4_vault_agent_dual_disk.py
import sys
import uuid
from pathlib import Path

import pytest

# Assegura que l'arrel del projecte és a sys.path per importar scripts
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import scripts.client_vault_agent as vault_agent  # noqa: E402


@pytest.mark.asyncio
async def test_vault_agent_31_carpetes_i_rotacio_disc_a_disc_b(tmp_path: Path) -> None:
    """Verifica la creació de les 38 carpetes oficials i el backup amb SHA-256 als 2 discos (WSS Agent)."""
    disc_a = tmp_path / "disc_a_primari"
    disc_b = tmp_path / "disc_b_mirall"
    cfg = vault_agent.AgentConfig(
        server_url="https://sevalor-sevalor-backend.80opze.easypanel.host",
        role="EMPRESA",
        empresa_id=str(uuid.uuid4()),
        vault_token="svlt_token_produccio_test",
        disk_a=disc_a,
        disk_b=disc_b,
    )
    agent = vault_agent.SovereignWssAgent(cfg)

    # 1. Health check i inicialització de les 38 carpetes
    h_data = await agent.execute_action("health", {})
    assert h_data["status"] == "OK"
    assert h_data["carpetes_count"] == len(vault_agent.CARPETES_OFICIALS)
    assert (disc_a / "08_flota_i_operaris/operaris/documents_rrhh").is_dir()

    # 2. Escriure una entitat i executar el backup de tancament de jornada
    put_res = await agent.execute_action(
        "json_put",
        {
            "subcarpeta": "01_clients/fitxes",
            "item_id": "cli_001",
            "content": {"id": "cli_001", "nom": "Client Sobirà SL"},
        },
    )
    assert put_res["status"] == "SAVED"

    bak_data = await agent.execute_action(
        "backup_daily",
        {"empresa_id": "emp_1", "taules": {"clients": 1}},
    )
    assert bak_data["status"] == "OK"
    assert len(bak_data["sha256"]) == 64
    assert Path(bak_data["zip_path"]).is_file()
    assert bak_data["fitxers_empaquetats"] >= 2
