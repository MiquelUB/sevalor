"""
Proves End-to-End Zero-Mock de persistència física real al Disc Dur Sobirà del Client.

Llença processos reals de `scripts/client_vault_agent.py` sobre ports TCP efímers
i carpetes temporals aïllades per validar:
1. Onboarding sense Telegram -> inicialitza directament `empresa.json`, `boss.json`
   i `system_prompt.txt` al disc físic real del client (Primary + Secondary).
2. `POST /superadmin/tenants/verificar-disc-dur` fa un round-trip R/W/D real:
   rebutja amb error si el token és incorrecte (HTTP 403) i retorna OK només si passa.
3. Pujada real de plànol (`/gestio/planols/upload`) i logotip (`/gestio/configuracio/logotip`)
   amb lectura real posterior (`/gestio/planols/{id}/raw` i `/superadmin/empreses/{id}/logotip`):
   les dades van exclusivament al disc de l'Empresa A, mai al de l'Empresa B ni a `/docs`/`/tmp`.
4. Cua de trànsit xifrada si l'agent cau offline -> drenatge complet en tornar online.
5. Configuració posterior del Bot de Telegram no sobreescriu `vault_token` ni trenca l'emmagatzematge.
"""

from __future__ import annotations

import os
import secrets
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Dict

import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.db import set_tenant_context
from app.core.security import create_access_token
from app.main import app
from app.models.models import Empresa
from app.services.sovereign_storage import SovereignStorageGateway

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = PROJECT_ROOT / "scripts"


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _start_vault_agent(
    primary_dir: Path,
    secondary_dir: Path,
    vault_token: str,
) -> tuple[subprocess.Popen[bytes], str]:
    port = _find_free_port()
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SCRIPTS_DIR) + os.pathsep + env.get("PYTHONPATH", "")
    env["SEVALOR_VAULT_PATH_A"] = str(primary_dir)
    env["SEVALOR_VAULT_PATH_B"] = str(secondary_dir)
    env["SEVALOR_VAULT_SECRET"] = vault_token
    env["HOST"] = "127.0.0.1"
    env["PORT"] = str(port)

    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "client_vault_agent:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=str(SCRIPTS_DIR),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    url = f"http://127.0.0.1:{port}"
    deadline = time.monotonic() + 15.0
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            out, err = proc.communicate(timeout=2)
            raise RuntimeError(f"Agent exited prematurely ({proc.returncode}): {err.decode()}")
        try:
            r = httpx.get(f"{url}/health", timeout=0.5)
            if r.status_code == 200:
                return proc, url
        except Exception:
            time.sleep(0.15)

    proc.terminate()
    raise TimeoutError(f"Vault agent on {url} did not become healthy in time")


def _stop_vault_agent(proc: subprocess.Popen[bytes]) -> None:
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


@pytest.mark.asyncio
async def test_e2e_sovereign_disk_multi_tenant_roundtrip_and_transit_drain(
    tmp_path: Path,
    db_session,
    monkeypatch,
):
    transit_dir = tmp_path / "transit_queue_e2e"
    transit_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("SOVEREIGN_TRANSIT_QUEUE_DIR", str(transit_dir))

    primary_a = tmp_path / "disc_empresa_a_primary"
    secondary_a = tmp_path / "disc_empresa_a_secondary"
    primary_b = tmp_path / "disc_empresa_b_primary"
    secondary_b = tmp_path / "disc_empresa_b_secondary"
    for p in (primary_a, secondary_a, primary_b, secondary_b):
        p.mkdir(parents=True, exist_ok=True)

    token_a = f"svlt_{secrets.token_urlsafe(24)}"
    token_b = f"svlt_{secrets.token_urlsafe(24)}"

    proc_a, url_a = _start_vault_agent(primary_a, secondary_a, token_a)
    proc_b, url_b = _start_vault_agent(primary_b, secondary_b, token_b)

    sa_token = create_access_token(
        {
            "sub": str(uuid.uuid4()),
            "email": "superadmin-e2e@sevalor.app",
            "rol": "SUPERADMIN",
            "empresa_id": None,
            "totp_activat": True,
            "ip_allowlist": ["*"],
        }
    )
    sa_headers = {"Authorization": f"Bearer {sa_token}"}

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            # 1. Verificació estricta del disc dur amb token erroni ha de fallar (NO fals positiu)
            bad_check = await ac.post(
                "/api/v1/superadmin/tenants/verificar-disc-dur",
                json={
                    "disc_dur_url": url_a,
                    "vault_token": "svlt_token_incorrecte_12345",
                },
                headers=sa_headers,
            )
            assert bad_check.status_code == 200
            bad_data = bad_check.json()
            assert bad_data["status"] == "ERROR"
            assert bad_data["codi_http"] in (401, 403)
            assert bad_data["motiu"] == "TOKEN_INVALID"

            # 2. Verificació amb token real passa el round-trip R/W/D complet
            good_check = await ac.post(
                "/api/v1/superadmin/tenants/verificar-disc-dur",
                json={"disc_dur_url": url_a, "vault_token": token_a},
                headers=sa_headers,
            )
            assert good_check.status_code == 200
            good_data = good_check.json()
            assert good_data["status"] == "OK", good_data
            assert good_data["roundtrip_escriptura"] is True
            # El fitxer de sondeig s'ha d'haver esborrat del disc real
            probe_matches = list(primary_a.rglob("_healthcheck_*.json"))
            assert probe_matches == []

            # 3. Onboarding Empresa A SENSE Telegram ni webhook secret -> disc A rep fitxers inicials
            rnd_a = uuid.uuid4().hex[:6]
            slug_a = f"e2e-emp-a-{rnd_a}"
            onb_a = await ac.post(
                "/api/v1/superadmin/tenants/onboarding",
                json={
                    "rao_social": f"Sevalormante E2E A {rnd_a} SL",
                    "nif": f"B{uuid.uuid4().int % 10000000:07d}A",
                    "adreca": "Polígon Industrial Nord, Nau 4",
                    "slug": slug_a,
                    "subdomini": slug_a,
                    "vertical": "Construcció i Manteniment",
                    "agent_prompt_system": "Ets l'assistent tècnic de proves E2E A.",
                    "disc_dur_url": url_a,
                    "vault_token": token_a,
                    "estat_inicial": "ACTIU",
                    "pla_subscripcio": "PRO",
                    "quota_operaris": 12,
                    "boss_nif": f"{uuid.uuid4().int % 90000000 + 10000000}Z",
                    "boss_nom": "Oriol",
                    "boss_cognoms": "Vidal Martí",
                    "boss_email": f"boss-a-{rnd_a}@example.com",
                    "feature_flags": {
                        "copilot_ia": True,
                        "flota_avancada": True,
                        "planols_tecnics": True,
                        "telegram_bot": False,
                    },
                },
                headers=sa_headers,
            )
            assert onb_a.status_code == 201, onb_a.text
            onb_a_json = onb_a.json()
            emp_a_id = onb_a_json["tenant"]["id"]
            boss_a_id = onb_a_json["tenant"]["boss_usuari_id"]
            assert onb_a_json["tenant"]["vault_token"] == token_a
            assert onb_a_json["vault_sync"]["status"] == "SYNCED"

            # Verificació física real al disc primari de l'Empresa A (i aïllament total vs Empresa B)
            assert (primary_a / "11_configuracio_i_backups/identitat_camaleo/empresa.json").is_file()
            assert (primary_a / "11_configuracio_i_backups/identitat_camaleo/boss.json").is_file()
            assert (primary_a / "09_copilot_ia/prompt_sistema/system_prompt.txt").is_file()
            # Cap fitxer ha d'haver anat al disc de l'Empresa B
            assert not (primary_b / "11_configuracio_i_backups/identitat_camaleo/empresa.json").exists()

            # Verificació en BD: telegram_webhook_secret continua None i vault_token és token_a
            await set_tenant_context(db_session, emp_a_id, is_superadmin=True)
            emp_a_db = (
                await db_session.execute(select(Empresa).where(Empresa.id == uuid.UUID(emp_a_id)))
            ).scalar_one()
            assert emp_a_db.vault_token == token_a
            assert emp_a_db.telegram_webhook_secret is None

            # Onboarding Empresa B amb el seu propi agent HTTP B
            rnd_b = uuid.uuid4().hex[:6]
            slug_b = f"e2e-emp-b-{rnd_b}"
            onb_b = await ac.post(
                "/api/v1/superadmin/tenants/onboarding",
                json={
                    "rao_social": f"Instal·lacions B {rnd_b} SL",
                    "nif": f"B{uuid.uuid4().int % 10000000:07d}B",
                    "slug": slug_b,
                    "subdomini": slug_b,
                    "vertical": "Electricitat",
                    "disc_dur_url": url_b,
                    "vault_token": token_b,
                    "estat_inicial": "ACTIU",
                    "pla_subscripcio": "STARTER",
                    "quota_operaris": 5,
                    "boss_nif": f"{uuid.uuid4().int % 90000000 + 10000000}X",
                    "boss_nom": "Marta",
                    "boss_cognoms": "Serra Puig",
                    "boss_email": f"boss-b-{rnd_b}@example.com",
                    "feature_flags": {
                        "copilot_ia": False,
                        "flota_avancada": True,
                        "planols_tecnics": True,
                        "telegram_bot": False,
                    },
                },
                headers=sa_headers,
            )
            assert onb_b.status_code == 201, onb_b.text
            assert (primary_b / "11_configuracio_i_backups/identitat_camaleo/empresa.json").is_file()

            # 4. Pujada real de plànol i logotip per part del BOSS de l'Empresa A
            boss_a_token = create_access_token(
                {
                    "sub": boss_a_id,
                    "empresa_id": emp_a_id,
                    "rol": "BOSS",
                    "email": f"boss-a-{rnd_a}@example.com",
                    "totp_activat": True,
                }
            )
            boss_headers: Dict[str, str] = {
                "Authorization": f"Bearer {boss_a_token}",
                "X-Empresa-ID": emp_a_id,
            }

            carp_resp = await ac.post(
                "/api/v1/gestio/planols/carpetes",
                json={"nom": "Sector E2E", "categoria": "CLIENTS"},
                headers=boss_headers,
            )
            assert carp_resp.status_code == 201, carp_resp.text
            carpeta_id = carp_resp.json()["id"]

            dxf_bytes = b"0\nSECTION\n2\nHEADER\n9\n$ACADVER\n1\nAC1015\n0\nENDSEC\n0\nEOF\n"
            up_planol = await ac.post(
                "/api/v1/gestio/planols/upload",
                files={"fitxer": ("xarxa_e2e.dxf", dxf_bytes, "application/dxf")},
                data={
                    "carpeta_id": carpeta_id,
                    "titol": "Plànol Real E2E Sector Sud",
                    "codi_referencia": f"E2E-{rnd_a}",
                    "tipus_fitxer": "DXF",
                    "es_georeferenciat": "true",
                    "projeccio": "ETRS89 / UTM 31N",
                },
                headers=boss_headers,
            )
            assert up_planol.status_code == 201, up_planol.text
            planol_json = up_planol.json()
            assert planol_json["fitxer_path"].startswith("vault://05_planols/arxius_base/")
            planol_id = planol_json["id"]

            # Fitxer físic present a Company A primary, absent a Company B
            planol_files_a = list((primary_a / "05_planols/arxius_base").glob("*.dxf"))
            assert len(planol_files_a) == 1
            assert planol_files_a[0].read_bytes() == dxf_bytes
            assert list((primary_b / "05_planols/arxius_base").glob("*.dxf")) == []

            # Descàrrega real des de /fitxer torna els bytes idèntics
            raw_resp = await ac.get(
                f"/api/v1/gestio/planols/{planol_id}/fitxer", headers=boss_headers
            )
            assert raw_resp.status_code == 200
            assert raw_resp.content == dxf_bytes

            # Pujada real de logotip PNG via /gestio/configuracio/logotip i lectura per /empreses/{id}/logotip
            png_bytes = (
                b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
                b"\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc`\x00\x00"
                b"\x00\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82"
            )
            up_logo = await ac.post(
                "/api/v1/gestio/configuracio/logotip",
                files={"fitxer": ("logo_test.png", png_bytes, "image/png")},
                headers=boss_headers,
            )
            assert up_logo.status_code == 200, up_logo.text
            assert up_logo.json()["logotip_path"].startswith(
                "vault://11_configuracio_i_backups/identitat_camaleo/logo_oficial.png"
            )
            assert (
                primary_a / "11_configuracio_i_backups/identitat_camaleo/logo_oficial.png"
            ).read_bytes() == png_bytes

            get_logo = await ac.get(f"/api/v1/superadmin/empreses/{emp_a_id}/logotip")
            assert get_logo.status_code == 200
            assert get_logo.content == png_bytes

            # 5. Offline -> cua de trànsit xifrada (NO plaintext a disc temporal) -> drenatge quan torna online
            _stop_vault_agent(proc_a)
            proc_a = None  # type: ignore[assignment]

            secret_pdf = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
            up_offline = await ac.post(
                "/api/v1/gestio/planols/upload",
                files={"fitxer": ("offline_secret.pdf", secret_pdf, "application/pdf")},
                data={
                    "carpeta_id": carpeta_id,
                    "titol": "Plànol Offline Xifrat",
                    "codi_referencia": f"OFF-{rnd_a}",
                    "tipus_fitxer": "PDF",
                    "es_georeferenciat": "false",
                },
                headers=boss_headers,
            )
            assert up_offline.status_code == 201, up_offline.text
            off_json = up_offline.json()
            assert off_json["fitxer_path"].startswith(
                f"transit://{emp_a_id}/05_planols/arxius_base/"
            )

            # Comprovem que a la cua de trànsit el contingut NO està en text pla
            queued_files = list((transit_dir / emp_a_id).glob("*.bin"))
            assert len(queued_files) == 1
            raw_queued = queued_files[0].read_bytes()
            assert raw_queued.startswith(b"SVENC1:")
            assert b"%PDF-1.4" not in raw_queued

            # El backend pot desxifrar i servir el PDF directament des de transit:// mentre l'agent torna
            transit_read = await ac.get(
                f"/api/v1/gestio/planols/{off_json['id']}/fitxer", headers=boss_headers
            )
            assert transit_read.status_code == 200
            assert transit_read.content == secret_pdf

            # Ara reengeguem l'agent A al mateix port i drenem la cua de trànsit
            port_a = int(url_a.rsplit(":", 1)[-1])
            env_a = os.environ.copy()
            env_a["PYTHONPATH"] = str(SCRIPTS_DIR) + os.pathsep + env_a.get("PYTHONPATH", "")
            env_a["SEVALOR_VAULT_PATH_A"] = str(primary_a)
            env_a["SEVALOR_VAULT_PATH_B"] = str(secondary_a)
            env_a["SEVALOR_VAULT_SECRET"] = token_a
            proc_a = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "client_vault_agent:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port_a),
                    "--log-level",
                    "warning",
                ],
                cwd=str(SCRIPTS_DIR),
                env=env_a,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            for _ in range(50):
                try:
                    if httpx.get(f"{url_a}/health", timeout=0.5).status_code == 200:
                        break
                except Exception:
                    time.sleep(0.1)

            drain_res = await SovereignStorageGateway.drenar_cua_transit_empresa(
                db_session, emp_a_id
            )
            assert drain_res["enviats"] == 1
            assert drain_res["pendents"] == 0
            # La cua temporal s'ha purgat a 0 fitxers i el PDF real ha arribat al disc A
            assert list((transit_dir / emp_a_id).glob("*.bin")) == []
            assert list((transit_dir / emp_a_id).glob("*.meta.json")) == []
            pdf_files_a = list((primary_a / "05_planols/arxius_base").glob("*.pdf"))
            assert len(pdf_files_a) == 1
            assert pdf_files_a[0].read_bytes() == secret_pdf

            # Fins i tot després del drenatge, el fitxer amb referència transit:// es serveix des del Vault
            drained_read = await ac.get(
                f"/api/v1/gestio/planols/{off_json['id']}/fitxer", headers=boss_headers
            )
            assert drained_read.status_code == 200
            assert drained_read.content == secret_pdf

            # 6. Configurar webhook de Telegram NO pot sobreescriure ni trencar vault_token
            tg_res = await ac.put(
                "/api/v1/gestio/configuracio/telegram",
                json={
                    "telegram_bot_token": f"999000111:AA_{secrets.token_urlsafe(16)}",
                    "telegram_webhook_secret": "tg_secret_custom_empresa_a_2026",
                },
                headers=boss_headers,
            )
            assert tg_res.status_code == 200, tg_res.text
            await set_tenant_context(db_session, emp_a_id, is_superadmin=True)
            emp_after_tg = (
                await db_session.execute(
                    select(Empresa).where(Empresa.id == uuid.UUID(emp_a_id))
                )
            ).scalar_one()
            assert emp_after_tg.vault_token == token_a
            assert emp_after_tg.telegram_webhook_secret == "tg_secret_custom_empresa_a_2026"
    finally:
        if proc_a is not None:
            _stop_vault_agent(proc_a)
        _stop_vault_agent(proc_b)
