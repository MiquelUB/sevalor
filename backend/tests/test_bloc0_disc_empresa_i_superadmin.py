import socket
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List

import pytest
import uvicorn
from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import scripts.client_vault_agent as vault_agent  # noqa: E402

from app.services.sovereign_storage import (  # noqa: E402
    CARPETES_SUPERADMIN,
    MAPA_CARPETES_SUPERADMIN,
    SuperadminStorageGateway,
    inicialitzar_arbre_carpetes_superadmin,
)


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _build_legacy_http_superadmin_test_app(sup_a: Path, secret: str) -> FastAPI:
    """Servidor HTTP transitori només per a test de SuperadminStorageGateway fins a la Fase 3 WSS-only."""
    import json

    vapp = FastAPI()

    def _auth(tok: str | None) -> None:
        if tok != secret:
            raise HTTPException(status_code=403, detail="Token invàlid")

    @vapp.post("/admin/inicialitzar-ruta")
    async def init_ruta(x_vault_token: str | None = Header(default=None, alias="X-Vault-Token")) -> Dict[str, Any]:
        _auth(x_vault_token)
        creades = inicialitzar_arbre_carpetes_superadmin(sup_a)
        return {"status": "OK", "role": "SUPERADMIN", "carpetes_count": len(creades)}

    @vapp.put("/entitats/{categoria:path}/{item_id}")
    async def put_entitat(
        categoria: str,
        item_id: str,
        payload: Dict[str, Any],
        x_vault_token: str | None = Header(default=None, alias="X-Vault-Token"),
    ) -> Dict[str, Any]:
        _auth(x_vault_token)
        folder = (sup_a / categoria).resolve()
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{item_id}.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return {"status": "SAVED"}

    @vapp.get("/entitats/{categoria:path}")
    async def list_entitats(
        categoria: str,
        x_vault_token: str | None = Header(default=None, alias="X-Vault-Token"),
    ) -> List[Dict[str, Any]]:
        _auth(x_vault_token)
        folder = (sup_a / categoria).resolve()
        if not folder.is_dir():
            return []
        return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(folder.glob("*.json"))]

    @vapp.delete("/entitats/{categoria:path}/{item_id}")
    async def del_entitat(
        categoria: str,
        item_id: str,
        x_vault_token: str | None = Header(default=None, alias="X-Vault-Token"),
    ) -> Dict[str, Any]:
        _auth(x_vault_token)
        fp = (sup_a / categoria / f"{item_id}.json").resolve()
        if fp.is_file():
            fp.unlink()
        return {"status": "DELETED"}

    @vapp.post("/fitxers/{categoria:path}")
    async def put_fitxer(
        categoria: str,
        fitxer: UploadFile = File(...),
        nom_desti: str = Form(...),
        x_vault_token: str | None = Header(default=None, alias="X-Vault-Token"),
    ) -> Dict[str, Any]:
        _auth(x_vault_token)
        folder = (sup_a / categoria).resolve()
        folder.mkdir(parents=True, exist_ok=True)
        (folder / nom_desti).write_bytes(await fitxer.read())
        return {"status": "OK"}

    @vapp.get("/fitxers/{rel_path:path}")
    async def get_fitxer(
        rel_path: str,
        x_vault_token: str | None = Header(default=None, alias="X-Vault-Token"),
    ) -> FileResponse:
        _auth(x_vault_token)
        fp = (sup_a / rel_path).resolve()
        if not fp.is_file():
            raise HTTPException(status_code=404, detail="No trobat")
        return FileResponse(fp, filename=fp.name)

    return vapp


@pytest.mark.asyncio
async def test_bloc0_disc_empresa_i_disc_superadmin_carpetes(tmp_path: Path) -> None:
    """Verifica creació de les 38 carpetes d'Empresa i les 20 carpetes del Disc Dur de Superadmin via Agent WSS."""
    # ADR-001 (Fase 2): client_vault_agent ja NO exposa cap app FastAPI/HTTP entrant
    assert not hasattr(vault_agent, "app")

    # 1. Mode EMPRESA
    emp_a = tmp_path / "Sevalormante_docs"
    emp_b = tmp_path / "Sevalormante_docs_backup_B"
    agent_emp = vault_agent.SovereignWssAgent(
        vault_agent.AgentConfig(
            server_url="https://sevalor-sevalor-backend.80opze.easypanel.host",
            role="EMPRESA",
            empresa_id=str(uuid.uuid4()),
            vault_token="svlt_emp_token_bloc0",
            disk_a=emp_a,
            disk_b=emp_b,
        )
    )

    data_emp = await agent_emp.execute_action("init_folders", {})
    assert data_emp["role"] == "EMPRESA"
    assert data_emp["carpetes_count"] == 38
    assert (emp_a / "09_copilot_ia/index_vectorial_rag").is_dir()
    assert (emp_a / "06_ordres_treball/actives_buffer").is_dir()

    h_emp = await agent_emp.execute_action("health", {})
    assert h_emp["role"] == "EMPRESA"
    assert h_emp["carpetes_count"] == 38

    # 2. Mode SUPERADMIN
    sup_a = tmp_path / "Sevalor_Superadmin_docs"
    sup_b = tmp_path / "Sevalor_Superadmin_docs_backup_B"
    agent_sup = vault_agent.SovereignWssAgent(
        vault_agent.AgentConfig(
            server_url="https://sevalor-sevalor-backend.80opze.easypanel.host",
            role="SUPERADMIN",
            vault_token="svlt_superadmin_token_bloc0",
            disk_a=sup_a,
            disk_b=sup_b,
        )
    )

    data_sup = await agent_sup.execute_action("init_folders", {})
    assert data_sup["role"] == "SUPERADMIN"
    assert data_sup["carpetes_count"] == 20
    assert len(CARPETES_SUPERADMIN) == 20
    assert len(MAPA_CARPETES_SUPERADMIN) == 20
    assert (sup_a / "02_facturacio_saas/factures_b2b_json").is_dir()
    assert (sup_a / "04_rascador_prospeccio/candidats").is_dir()
    assert (sup_a / "03_crm_comercial/leads").is_dir()
    assert not (sup_a / "06_ordres_treball/actives_buffer").exists()

    h_sup = await agent_sup.execute_action("health", {})
    assert h_sup["role"] == "SUPERADMIN"
    assert h_sup["carpetes_count"] == 20

    bak_sup = await agent_sup.execute_action("backup_daily", {"origen": "superadmin", "factures_b2b": 3})
    assert bak_sup["role"] == "SUPERADMIN"
    assert Path(bak_sup["zip_path"]).is_file()
    assert not (sup_a / "11_configuracio_i_backups").exists()


@pytest.mark.asyncio
async def test_bloc0_superadmin_storage_gateway_tunel_real_tcp_i_offline(tmp_path: Path, monkeypatch) -> None:
    """
    Zero Mocks (ADR-001 Túnel Invers WSS):
    1. Si el túnel WSS Superadmin està desconnectat, inicialitzar_rutes_superadmin falla amb 503 i NO crea carpetes.
    2. Amb `SovereignWssAgent` real (role=SUPERADMIN), crea les 20 carpetes (Disc A + mirall Disc B) i fa CRUD JSON/binari real.
    3. Un cop desconnectat el túnel WSS, les crides tornen a fallar amb 503 `NODE_SUPERADMIN_OFFLINE`.
    """
    from tests.wss_test_helpers import live_superadmin_wss_context

    sup_a = tmp_path / "Superadmin_Vault_A"
    sup_b = tmp_path / "Superadmin_Vault_B"
    sa_secret = "svlt_sup_real_wss_secret"

    monkeypatch.delenv("SUPERADMIN_VAULT_URL", raising=False)
    monkeypatch.setenv("SUPERADMIN_VAULT_SECRET", sa_secret)

    # A. Túnel WSS offline -> HTTP 503 obligatori, zero carpetes creades
    with pytest.raises(HTTPException) as exc_offline:
        await SuperadminStorageGateway.inicialitzar_rutes_superadmin()
    assert exc_offline.value.status_code == 503
    assert not sup_a.exists()

    # B. Agent Sobirà WSS real connectat (role=SUPERADMIN)
    async with live_superadmin_wss_context(sa_secret, sup_a, disk_b=sup_b):
        res_wss = await SuperadminStorageGateway.inicialitzar_rutes_superadmin()
        assert res_wss["role"] == "SUPERADMIN"
        assert res_wss["mode"] == "WSS_TUNNEL"
        assert res_wss["carpetes_count"] == 20
        assert (sup_a / "01_tenants_b2b/fitxes_empreses").is_dir()
        assert (sup_b / "01_tenants_b2b/fitxes_empreses").is_dir()

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
        assert pdf_ref == "superadmin-vault://02_facturacio_saas/factures_b2b_pdf/factura_saas_001.pdf"

        pdf_bytes, pdf_name = await SuperadminStorageGateway.obtenir_bytes_fitxer(pdf_ref)
        assert pdf_bytes == b"%PDF-1.4\nSEVALOR-SAAS-TEST\n"
        assert pdf_name == "factura_saas_001.pdf"

        deleted = await SuperadminStorageGateway.eliminar_entitat_json("crm_leads", "lead_001")
        assert deleted is True
        assert await SuperadminStorageGateway.llegir_entitats_json("crm_leads") == []

    # C. Un cop aturat el túnel WSS, la crida torna a fallar amb 503
    with pytest.raises(HTTPException) as exc_after_stop:
        await SuperadminStorageGateway.llegir_entitats_json("crm_leads")
    assert exc_after_stop.value.status_code == 503


@pytest.mark.asyncio
async def test_bloc0_seguretat_path_traversal_i_ports_bridge(tmp_path: Path) -> None:
    """Verifica bloqueig de Path Traversal a l'agent WSS i eliminació dels scripts antics (ADR-001)."""
    agent = vault_agent.SovereignWssAgent(
        vault_agent.AgentConfig(
            server_url="https://sevalor-sevalor-backend.80opze.easypanel.host",
            role="EMPRESA",
            empresa_id=str(uuid.uuid4()),
            vault_token="svlt_sec_token",
            disk_a=tmp_path / "Disc_Sec",
            disk_b=tmp_path / "Disc_Sec_B",
        )
    )

    with pytest.raises(vault_agent.AgentActionError) as exc1:
        await agent.execute_action(
            "json_put",
            {"subcarpeta": "../../etc", "item_id": "passwd", "content": {"hack": True}},
        )
    assert exc1.value.code == "PATH_TRAVERSAL"

    with pytest.raises(vault_agent.AgentActionError) as exc2:
        await agent.execute_action("file_get", {"rel_path": "../secrets/key.pem"})
    assert exc2.value.code == "PATH_TRAVERSAL"

    with pytest.raises(vault_agent.AgentActionError) as exc3:
        await agent.execute_action("file_delete", {"rel_path": "..\\etc\\hosts"})
    assert exc3.value.code == "PATH_TRAVERSAL"

    # ADR-001 (Fase 0): Scripts antics de pont Docker HTTP i Cloudflare Tunnel eliminats
    assert not (ROOT_DIR / "scripts" / "bridge_lm_studio.py").exists()
    assert not (ROOT_DIR / "scripts" / "start_tunnel.sh").exists()
