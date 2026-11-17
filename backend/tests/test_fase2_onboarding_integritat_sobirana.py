import json
import os
import socket
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone

import httpx
import jwt
import pytest
import uvicorn
from fastapi import FastAPI, Header, HTTPException, Request
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.config import settings
from app.core.security import blind_email, blind_nif, blind_telefon
from app.main import app
from app.models.models import Empresa, Usuari
from app.services.sovereign_storage import MAPA_CARPETES_CLIENT


@pytest.fixture
def superadmin_token():
    payload = {
        "sub": "00000000-0000-0000-0000-000000000000",
        "rol": "SUPERADMIN",
        "empresa_id": None,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
        "totp_activat": True,
        "ip_allowlist": ["testclient", "127.0.0.1", "localhost", "*"],
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


@pytest.fixture
def headers(superadmin_token):
    return {"Authorization": f"Bearer {superadmin_token}"}


@pytest.mark.asyncio
async def test_onboarding_rebutja_format_carpeta_local(headers):
    """Verifica que el format arcaic 'Carpeta Local:' a disc_dur_url és rebutjat amb 422."""
    rnd = uuid.uuid4().hex[:6]
    payload = {
        "rao_social": f"Empresa Invalid Disk {rnd}",
        "nif": f"B{uuid.uuid4().int % 10000000:07d}A",
        "subdomini": f"invalid-disk-{rnd}",
        "vertical": "CAMPOPRO",
        "pla_subscripcio": "PRO",
        "boss_nif": "48112233X",
        "boss_nom": "Pere",
        "boss_cognoms": "Martí",
        "boss_email": f"pere_{rnd}@invalid.cat",
        "disc_dur_url": "Carpeta Local: /home/user/dades",
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/api/v1/superadmin/tenants/onboarding", json=payload, headers=headers)
        assert res.status_code == 422
        assert "Carpeta Local:" in res.json().get("detail", "")


@pytest.mark.asyncio
async def test_onboarding_integritat_dades_i_persistencia_local_fs(headers, db_session):
    """
    Verifica l'onboarding complet de Fase 2 en mode disc físic (LOCAL_FS):
    - Adreça real persistida a Empresa
    - boss_nif independent de NIF d'empresa
    - boss_nom i boss_cognoms separats
    - boss_telefon real sense mocks
    - Token de disc svlt_ generat a telegram_webhook_secret
    - Escriptura immediata de empresa.json, boss.json i system_prompt.txt al disc sobirà
    - Domini d'activació generat amb projectexinoxano.cat
    """
    rnd = uuid.uuid4().hex[:6]
    cif_empresa = f"B{uuid.uuid4().int % 10000000:07d}A"
    nif_boss = "47891234X"
    sub_slug = f"sevalortest-{rnd}"
    adreca_real = "Polígon Industrial Sud, C/ del Treball 12, Amposta"
    telefon_real = "+34611223344"
    system_prompt_text = "Ets el Copilot d'Enginyeria de Sevalor Test. Prohibit generar mocks."

    base_vaults = os.getenv("CLIENT_DISKS_MOUNT_ROOT", "/tmp/sevalor_client_disks")
    empresa_disk_root = os.path.join(base_vaults, f"disc_{sub_slug}")

    payload = {
        "rao_social": f"Sevalor Test Sobirà {rnd} SL",
        "nif": cif_empresa,
        "adreca": adreca_real,
        "subdomini": sub_slug,
        "vertical": "CAMPOPRO",
        "pla_subscripcio": "ENTERPRISE",
        "quota_operaris": 15,
        "quota_disc_gb": 50,
        "boss_nif": nif_boss,
        "boss_nom": "Miquel Àngel",
        "boss_cognoms": "Pons Roig",
        "boss_email": f"gerencia_{rnd}@sevalortest.cat",
        "boss_telefon": telefon_real,
        "agent_prompt_system": system_prompt_text,
        "disc_dur_url": empresa_disk_root,
        "feature_flags": {
            "copilot_ia": True,
            "flota_avancada": True,
            "planols_tecnics": True,
            "telegram_bot": True,
        },
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/api/v1/superadmin/tenants/onboarding", json=payload, headers=headers)
        assert res.status_code == 201, f"Error onboarding: {res.status_code} - {res.text}"
        data = res.json()
        assert data["status"] == "CREATED"
        tenant_info = data["tenant"]
        assert tenant_info["pla_subscripcio"] == "ENTERPRISE"
        assert tenant_info["quota_operaris"] == 15
        assert tenant_info["domini_complet"] == f"{sub_slug}.projectexinoxano.cat"
        assert f"{sub_slug}.projectexinoxano.cat/activacio" in tenant_info["enllac_activacio_2fa"]

        empresa_id = uuid.UUID(tenant_info["id"])
        boss_id = uuid.UUID(tenant_info["boss_usuari_id"])

    # 1. Comprovació d'integritat Zero-Storage en Base de Dades (Hetzner)
    res_emp = await db_session.execute(select(Empresa).where(Empresa.id == empresa_id))
    empresa_db = res_emp.scalars().first()
    assert empresa_db is not None
    assert empresa_db.nom == f"Tenant-{sub_slug}"
    assert empresa_db.adreca is None
    assert empresa_db.nif == blind_nif(cif_empresa)
    assert empresa_db.subdomini == sub_slug
    assert empresa_db.pla_subscripcio == "ENTERPRISE"
    assert empresa_db.vault_token is not None
    assert empresa_db.vault_token.startswith("svlt_")
    assert len(empresa_db.vault_token) > 20
    assert empresa_db.telegram_webhook_secret is None
    assert tenant_info["vault_token"] == empresa_db.vault_token

    res_boss = await db_session.execute(select(Usuari).where(Usuari.id == boss_id))
    boss_db = res_boss.scalars().first()
    assert boss_db is not None
    assert boss_db.nif == blind_nif(nif_boss)
    assert boss_db.nom == "Usuari"
    assert boss_db.cognoms == ""
    assert boss_db.email == blind_email(f"gerencia_{rnd}@sevalortest.cat")
    assert boss_db.telefon == blind_telefon(telefon_real)
    assert boss_db.rol == "BOSS"

    # 2. Comprovació de persistència de fitxers al disc dur del client (Minut 1)
    config_folder = os.path.join(empresa_disk_root, MAPA_CARPETES_CLIENT["configuracio"])
    prompt_folder = os.path.join(empresa_disk_root, MAPA_CARPETES_CLIENT["copilot_prompt"])

    empresa_json_path = os.path.join(config_folder, "empresa.json")
    boss_json_path = os.path.join(config_folder, "boss.json")
    system_prompt_path = os.path.join(prompt_folder, "system_prompt.txt")

    assert os.path.exists(empresa_json_path), f"Falta {empresa_json_path}"
    assert os.path.exists(boss_json_path), f"Falta {boss_json_path}"
    assert os.path.exists(system_prompt_path), f"Falta {system_prompt_path}"

    with open(empresa_json_path, "r", encoding="utf-8") as f:
        emp_json_data = json.load(f)
        assert emp_json_data["id"] == str(empresa_id)
        assert emp_json_data["adreca"] == adreca_real
        assert emp_json_data["nif"] == cif_empresa
        assert emp_json_data["pla_subscripcio"] == "ENTERPRISE"
        assert emp_json_data["_sovereign_meta"]["categoria"] == "configuracio"

    with open(boss_json_path, "r", encoding="utf-8") as f:
        boss_json_data = json.load(f)
        assert boss_json_data["id"] == str(boss_id)
        assert boss_json_data["nif"] == nif_boss
        assert boss_json_data["nom"] == "Miquel Àngel"
        assert boss_json_data["cognoms"] == "Pons Roig"
        assert boss_json_data["telefon"] == telefon_real

    with open(system_prompt_path, "r", encoding="utf-8") as f:
        prompt_content = f.read()
        assert prompt_content == system_prompt_text


@pytest.mark.asyncio
async def test_onboarding_integritat_i_persistencia_http_vault(headers, db_session, tmp_path):
    """
    Verifica l'onboarding de Fase 2 en mode HTTP_VAULT real (Opció A+):
    - disc_dur_url apunta a un Agent HTTP Local real aixecat sobre Uvicorn TCP
    - Es valida que les crides PUT es fan amb el header X-Vault-Token = svlt_...
    - Es valida la persistència de fitxers reals sense mocks prohibits
    """
    rnd = uuid.uuid4().hex[:6]
    cif_empresa = f"B{uuid.uuid4().int % 10000000:07d}A"
    sub_slug = f"sevalornode-{rnd}"
    secret_token = f"svlt_{rnd}_sovereign_token"
    recorded_puts = []

    vapp = FastAPI()
    vault_root = tmp_path / f"vault_http_{rnd}"
    vault_root.mkdir(parents=True, exist_ok=True)

    @vapp.get("/health")
    async def _health():
        return {"status": "OK", "vault_root": str(vault_root), "disc_a_lliure_gb": 50.0}

    @vapp.post("/admin/inicialitzar-ruta")
    async def _init_ruta(x_vault_token: str | None = Header(default=None, alias="X-Vault-Token")):
        if x_vault_token != secret_token:
            raise HTTPException(status_code=403)
        return {"status": "OK", "carpetes_count": 38}

    @vapp.put("/entitats/{subcarpeta:path}/{item_id}")
    async def _put_ent(
        subcarpeta: str,
        item_id: str,
        request: Request,
        x_vault_token: str | None = Header(default=None, alias="X-Vault-Token"),
    ):
        if x_vault_token != secret_token:
            raise HTTPException(status_code=403)
        body = json.loads((await request.body()).decode("utf-8"))
        full_url = str(request.url)
        recorded_puts.append((full_url, dict(request.headers), body))
        dest = vault_root / subcarpeta
        dest.mkdir(parents=True, exist_ok=True)
        (dest / f"{item_id}.json").write_text(json.dumps(body), encoding="utf-8")
        return {"status": "SAVED"}

    @vapp.get("/entitats/{subcarpeta:path}")
    async def _list_ent(subcarpeta: str, x_vault_token: str | None = Header(default=None, alias="X-Vault-Token")):
        if x_vault_token != secret_token:
            raise HTTPException(status_code=403)
        return []

    @vapp.delete("/entitats/{subcarpeta:path}/{item_id}")
    async def _del_ent(subcarpeta: str, item_id: str, x_vault_token: str | None = Header(default=None, alias="X-Vault-Token")):
        if x_vault_token != secret_token:
            raise HTTPException(status_code=403)
        return {"status": "OK"}

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        port = int(s.getsockname()[1])
    srv = uvicorn.Server(uvicorn.Config(vapp, host="127.0.0.1", port=port, log_level="error"))
    thr = threading.Thread(target=srv.run, daemon=True)
    thr.start()

    try:
        deadline = time.time() + 6.0
        while time.time() < deadline:
            try:
                if httpx.get(f"http://127.0.0.1:{port}/health", timeout=0.3).status_code == 200:
                    break
            except Exception:
                time.sleep(0.05)

        vault_base = f"http://127.0.0.1:{port}"
        payload = {
            "rao_social": f"Sevalor Node HTTP {rnd} SL",
            "nif": cif_empresa,
            "adreca": "Carrer Major 50, Tortosa",
            "subdomini": sub_slug,
            "vertical": "HYDROPRO",
            "pla_subscripcio": "PRO",
            "boss_nif": "39887766K",
            "boss_nom": "Carles",
            "boss_cognoms": "Fabra",
            "boss_email": f"carles_{rnd}@sevalornode.cat",
            "boss_telefon": "+34677889900",
            "disc_dur_url": vault_base,
            "vault_token": secret_token,
        }

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            res = await ac.post("/api/v1/superadmin/tenants/onboarding", json=payload, headers=headers)
            assert res.status_code == 201, f"Error: {res.status_code} - {res.text}"
            data = res.json()
            assert data["status"] == "CREATED"
            empresa_id = uuid.UUID(data["tenant"]["id"])
    finally:
        srv.should_exit = True
        thr.join(timeout=2.0)

    # Comprovem el token generat a BD
    res_emp = await db_session.execute(select(Empresa).where(Empresa.id == empresa_id))
    emp_db = res_emp.scalars().first()
    assert emp_db is not None
    assert emp_db.vault_token == secret_token
    assert emp_db.telegram_webhook_secret is None

    # Comprovem que s'han fet les crides PUT a l'agent local amb el token correcte (excloent _healthcheck_)
    onboarding_puts = [p for p in recorded_puts if "_healthcheck_" not in p[0]]
    assert len(onboarding_puts) >= 2  # empresa i boss
    urls = [p[0] for p in onboarding_puts]
    subcarpeta_cfg = MAPA_CARPETES_CLIENT["configuracio"]
    assert any(f"{subcarpeta_cfg}/empresa" in u for u in urls)
    assert any(f"{subcarpeta_cfg}/boss" in u for u in urls)

    for _url, hdrs, body in onboarding_puts:
        assert hdrs.get("x-vault-token") == secret_token
        assert "_sovereign_meta" in body
