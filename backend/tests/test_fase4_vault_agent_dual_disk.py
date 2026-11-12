# backend/tests/test_fase4_vault_agent_dual_disk.py
import sys
from pathlib import Path

# Assegura que l'arrel del projecte és a sys.path per importar scripts
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastapi.testclient import TestClient

import scripts.client_vault_agent as vault_agent


def test_vault_agent_31_carpetes_i_rotacio_disc_a_disc_b(tmp_path: Path, monkeypatch):
    """Verifica la creació de les carpetes oficials i el backup amb SHA-256 als 2 discos."""
    disc_a = tmp_path / "disc_a_primari"
    disc_b = tmp_path / "disc_b_mirall"
    monkeypatch.setattr(vault_agent, "VAULT_PRIMARY_A", disc_a)
    monkeypatch.setattr(vault_agent, "VAULT_SECONDARY_B", disc_b)
    monkeypatch.setattr(vault_agent, "VAULT_SECRET", "svlt_token_produccio_test")

    client = TestClient(vault_agent.app)
    headers = {"X-Vault-Token": "svlt_token_produccio_test"}

    # 1. Health check i inicialització de les carpetes
    r_health = client.get("/health")
    assert r_health.status_code == 200
    assert r_health.json()["carpetes_count"] == len(vault_agent.CARPETES_OFICIALS)
    assert (disc_a / "08_flota_i_operaris/operaris/documents_rrhh").is_dir()

    # 2. Escriure una entitat i executar el backup de tancament de jornada
    r_put = client.put(
        "/entitats/01_clients/fitxes/cli_001",
        json={"id": "cli_001", "nom": "Client Sobirà SL"},
        headers=headers,
    )
    assert r_put.status_code == 200

    r_bak = client.post(
        "/backups/tancament-jornada",
        json={"empresa_id": "emp_1", "taules": {"clients": 1}},
        headers=headers,
    )
    assert r_bak.status_code == 200
    bak_data = r_bak.json()
    assert bak_data["status"] == "OK"
    assert len(bak_data["sha256"]) == 64
    assert Path(bak_data["zip_path"]).is_file()
    assert bak_data["fitxers_empaquetats"] >= 2
