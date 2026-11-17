import socket
import sys
import threading
import time
from pathlib import Path

import pytest
import uvicorn
from fastapi import HTTPException
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import scripts.bridge_lm_studio as bridge_lm_studio  # noqa: E402
import scripts.client_vault_agent as vault_agent  # noqa: E402

from app.services.sovereign_storage import (  # noqa: E402
    CARPETES_SUPERADMIN,
    MAPA_CARPETES_SUPERADMIN,
    SuperadminStorageGateway,
)


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def test_bloc0_disc_empresa_i_disc_superadmin_carpetes(tmp_path: Path, monkeypatch):
    """Verifica creació de les 38 carpetes d'Empresa i les 20 carpetes del Disc Dur de Superadmin."""
    # 1. Mode EMPRESA (/media/akaun/Project_1/Sevalormante_docs)
    emp_a = tmp_path / "Sevalormante_docs"
    emp_b = tmp_path / "Sevalormante_docs_backup_B"
    monkeypatch.setattr(vault_agent, "VAULT_ROLE", "EMPRESA")
    monkeypatch.setattr(vault_agent, "VAULT_PRIMARY_A", emp_a)
    monkeypatch.setattr(vault_agent, "VAULT_SECONDARY_B", emp_b)
    monkeypatch.setattr(vault_agent, "VAULT_SECRET", "svlt_emp_token_bloc0")

    with TestClient(vault_agent.app) as client:
        assert client.get("/v1/models").status_code == 403
        assert client.post("/admin/inicialitzar-ruta").status_code == 403
        assert (
            client.post("/admin/inicialitzar-ruta", headers={"X-Vault-Token": "wrong"}).status_code
            == 403
        )

        r_init = client.post(
            "/admin/inicialitzar-ruta",
            headers={"X-Vault-Token": "svlt_emp_token_bloc0"},
        )
        assert r_init.status_code == 200
        data_emp = r_init.json()
        assert data_emp["role"] == "EMPRESA"
        assert data_emp["carpetes_count"] == 38
        assert (emp_a / "09_copilot_ia/index_vectorial_rag").is_dir()
        assert (emp_a / "06_ordres_treball/actives_buffer").is_dir()

        r_health_emp = client.get("/health")
        assert r_health_emp.status_code == 200
        assert r_health_emp.json()["role"] == "EMPRESA"
        assert r_health_emp.json()["carpetes_count"] == 38

    # 2. Mode SUPERADMIN (/media/akaun/Project_1/Sevalor_Superadmin_docs)
    sup_a = tmp_path / "Sevalor_Superadmin_docs"
    sup_b = tmp_path / "Sevalor_Superadmin_docs_backup_B"
    monkeypatch.setattr(vault_agent, "VAULT_ROLE", "SUPERADMIN")
    monkeypatch.setattr(vault_agent, "VAULT_PRIMARY_A", sup_a)
    monkeypatch.setattr(vault_agent, "VAULT_SECONDARY_B", sup_b)
    monkeypatch.setattr(vault_agent, "VAULT_SECRET", "svlt_superadmin_token_bloc0")

    with TestClient(vault_agent.app) as client:
        r_sup = client.post(
            "/admin/inicialitzar-ruta",
            headers={"X-Vault-Token": "svlt_superadmin_token_bloc0"},
        )
        assert r_sup.status_code == 200
        data_sup = r_sup.json()
        assert data_sup["role"] == "SUPERADMIN"
        assert data_sup["carpetes_count"] == 20
        assert len(CARPETES_SUPERADMIN) == 20
        assert len(MAPA_CARPETES_SUPERADMIN) == 20
        assert (sup_a / "02_facturacio_saas/factures_b2b_json").is_dir()
        assert (sup_a / "04_rascador_prospeccio/candidats").is_dir()
        assert (sup_a / "03_crm_comercial/leads").is_dir()
        assert not (sup_a / "06_ordres_treball/actives_buffer").exists()

        r_health_sup = client.get("/health")
        assert r_health_sup.status_code == 200
        assert r_health_sup.json()["role"] == "SUPERADMIN"
        assert r_health_sup.json()["carpetes_count"] == 20

        r_bak = client.post(
            "/backups/tancament-jornada",
            json={"origen": "superadmin", "factures_b2b": 3},
            headers={"X-Vault-Token": "svlt_superadmin_token_bloc0"},
        )
        assert r_bak.status_code == 200
        assert r_bak.json()["role"] == "SUPERADMIN"
        assert Path(r_bak.json()["zip_path"]).is_file()
        assert not (sup_a / "11_configuracio_i_backups").exists()


@pytest.mark.asyncio
async def test_bloc0_superadmin_storage_gateway_tunel_real_tcp_i_offline(tmp_path: Path, monkeypatch):
    """
    Sense mocks HTTP:
    1. Si el túnel Superadmin està desconnectat, inicialitzar_rutes_superadmin falla amb 503 i NO crea carpetes.
    2. Si el secret no està configurat, rebutja abans de connectar (503).
    3. Amb un agent Uvicorn real escoltant per TCP a 127.0.0.1:<port>, crea les 20 carpetes i fa CRUD real.
    """
    sup_a = tmp_path / "Superadmin_Vault_A"
    sup_b = tmp_path / "Superadmin_Vault_B"
    closed_port = _find_free_port()

    # A. Túnel sense secret -> bloqueig 503
    monkeypatch.setenv("SUPERADMIN_VAULT_URL", f"http://127.0.0.1:{closed_port}")
    monkeypatch.setenv("SUPERADMIN_VAULT_SECRET", "")
    with pytest.raises(HTTPException) as exc_nosecret:
        await SuperadminStorageGateway.inicialitzar_rutes_superadmin()
    assert exc_nosecret.value.status_code == 503
    assert not sup_a.exists()

    # B. Túnel tancat (ningú escoltant al port) -> HTTP 503 obligatori, zero carpetes creades
    monkeypatch.setenv("SUPERADMIN_VAULT_SECRET", "svlt_sup_real_tcp_secret")
    with pytest.raises(HTTPException) as exc_offline:
        await SuperadminStorageGateway.inicialitzar_rutes_superadmin()
    assert exc_offline.value.status_code == 503
    assert not sup_a.exists()

    # C. Arrencada REAL del servidor client_vault_agent amb Uvicorn per TCP
    monkeypatch.setattr(vault_agent, "VAULT_ROLE", "SUPERADMIN")
    monkeypatch.setattr(vault_agent, "VAULT_PRIMARY_A", sup_a)
    monkeypatch.setattr(vault_agent, "VAULT_SECONDARY_B", sup_b)
    monkeypatch.setattr(vault_agent, "VAULT_SECRET", "svlt_sup_real_tcp_secret")

    live_port = _find_free_port()
    config = uvicorn.Config(vault_agent.app, host="127.0.0.1", port=live_port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 5.0
        while not server.started and time.monotonic() < deadline:
            time.sleep(0.05)
        assert server.started, "El servidor Uvicorn real del Bloc 0 no ha arrencat a temps"

        monkeypatch.setenv("SUPERADMIN_VAULT_URL", f"http://127.0.0.1:{live_port}")
        monkeypatch.setenv("SUPERADMIN_VAULT_SECRET", "svlt_sup_real_tcp_secret")

        res_http = await SuperadminStorageGateway.inicialitzar_rutes_superadmin()
        assert res_http["role"] == "SUPERADMIN"
        assert res_http["carpetes_count"] == 20
        assert (sup_a / "01_tenants_b2b/fitxes_empreses").is_dir()

        ruta_lead = await SuperadminStorageGateway.desar_entitat_json(
            "crm_leads",
            "lead_001",
            {"empresa": "Regadius Lleida SL", "estat": "NOUS"},
        )
        assert ruta_lead == "superadmin-vault://03_crm_comercial/leads/lead_001.json"
        assert (sup_a / "03_crm_comercial/leads/lead_001.json").is_file()

        leads = await SuperadminStorageGateway.llegir_entitats_json("crm_leads")
        assert len(leads) == 1
        assert leads[0]["empresa"] == "Regadius Lleida SL"
        assert leads[0]["_superadmin_meta"]["scope"] == "SUPERADMIN"

        pdf_ref = await SuperadminStorageGateway.pujar_fitxer_binari(
            "saas_factures_pdf",
            "factura_saas_001.pdf",
            b"%PDF-1.4\nSEVALOR-SAAS-TEST\n",
            "application/pdf",
        )
        assert (
            pdf_ref
            == "superadmin-vault://02_facturacio_saas/factures_b2b_pdf/factura_saas_001.pdf"
        )

        pdf_bytes, pdf_name = await SuperadminStorageGateway.obtenir_bytes_fitxer(pdf_ref)
        assert pdf_bytes == b"%PDF-1.4\nSEVALOR-SAAS-TEST\n"
        assert pdf_name == "factura_saas_001.pdf"

        deleted = await SuperadminStorageGateway.eliminar_entitat_json("crm_leads", "lead_001")
        assert deleted is True
        assert await SuperadminStorageGateway.llegir_entitats_json("crm_leads") == []

        # Token erroni rebutjat amb 403 real per TCP
        monkeypatch.setenv("SUPERADMIN_VAULT_SECRET", "token_incorrecte")
        with pytest.raises(HTTPException) as exc_auth:
            await SuperadminStorageGateway.llegir_entitats_json("crm_leads")
        assert exc_auth.value.status_code == 403
    finally:
        server.should_exit = True
        thread.join(timeout=5.0)

    # D. Un cop aturat el servidor/túnel, la crida torna a fallar amb 503
    monkeypatch.setenv("SUPERADMIN_VAULT_SECRET", "svlt_sup_real_tcp_secret")
    with pytest.raises(HTTPException) as exc_after_stop:
        await SuperadminStorageGateway.llegir_entitats_json("crm_leads")
    assert exc_after_stop.value.status_code == 503


def test_bloc0_seguretat_path_traversal_i_ports_bridge(tmp_path: Path, monkeypatch):
    """Verifica bloqueig de Path Traversal, límit proxy i ports del bridge (1234, 9001, 9002)."""
    disc_a = tmp_path / "Disc_Sec"
    disc_b = tmp_path / "Disc_Sec_B"
    monkeypatch.setattr(vault_agent, "VAULT_ROLE", "EMPRESA")
    monkeypatch.setattr(vault_agent, "VAULT_PRIMARY_A", disc_a)
    monkeypatch.setattr(vault_agent, "VAULT_SECONDARY_B", disc_b)
    monkeypatch.setattr(vault_agent, "VAULT_SECRET", "svlt_sec_token")

    headers = {"X-Vault-Token": "svlt_sec_token"}
    with TestClient(vault_agent.app) as client:
        r_trav_1 = client.put(
            "/entitats/..%2f..%2fetc/passwd",
            json={"hack": True},
            headers=headers,
        )
        assert r_trav_1.status_code in (400, 404)

        r_trav_2 = client.get("/fitxers/..%2fsecrets", headers=headers)
        assert r_trav_2.status_code in (400, 404)

        r_v1_trav = client.get("/v1/models%2f..%2f..%2fadmin", headers=headers)
        assert r_v1_trav.status_code in (400, 404)

    monkeypatch.delenv("SEVALOR_BRIDGE_PORTS", raising=False)
    assert bridge_lm_studio.get_target_ports() == (1234, 9001, 9002)
    monkeypatch.setenv("SEVALOR_BRIDGE_PORTS", "1234, 9001, 9002")
    assert bridge_lm_studio.get_target_ports() == (1234, 9001, 9002)
    monkeypatch.setenv("SEVALOR_BRIDGE_PORTS", "99999")
    with pytest.raises(ValueError):
        bridge_lm_studio.get_target_ports()
