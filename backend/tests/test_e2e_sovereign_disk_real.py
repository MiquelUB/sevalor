"""
Proves End-to-End Zero-Mock de persistència física real al Disc Dur Sobirà del Client via Túnel WSS.

Executa `SovereignWssAgent` reals (Empresa A i Empresa B) contra Uvicorn real i carpetes aïllades:
1. Onboarding sense URL externa -> assigna `wss-tunnel://<id>`, retorna `comanda_install_wss`,
   i en connectar l'agent A s'auto-inicialitzen les 38 carpetes + `empresa.json`, `boss.json` i `system_prompt.txt`.
2. `POST /superadmin/tenants/verificar-disc-dur` fa un round-trip R/W/D real per WSS:
   retorna `TUNEL_OFFLINE` si desconnectat i `DISC_OPERATIU` amb `roundtrip_escriptura=True` quan connectat.
3. Pujada real de plànol (`/gestio/planols/upload`) i logotip via Superadmin (`/superadmin/empreses/{id}/logotip`)
   amb lectura real posterior: les dades van exclusivament al disc de l'Empresa A, mai al de l'Empresa B.
4. Cua de trànsit xifrada `SVENC1:` si l'agent cau offline -> drenatge complet i auto-purga en reconnectar.
5. Configuració posterior del Bot de Telegram no sobreescriu `vault_token` ni trenca l'emmagatzematge.
"""

from __future__ import annotations

import secrets
import uuid
from pathlib import Path
from typing import Dict

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.db import set_tenant_context
from app.core.security import create_access_token
from app.main import app
from app.models.models import Empresa
from app.services.sovereign_storage import SovereignStorageGateway
from app.services.vault_tunnel import empresa_target_key, vault_tunnel_broker
from tests.wss_test_helpers import (
    LiveUvicornServer,
    RunningWssAgent,
    start_local_llm_server,
    wait_for,
)


@pytest.mark.asyncio
async def test_e2e_sovereign_disk_multi_tenant_roundtrip_and_transit_drain(
    tmp_path: Path,
    db_session,
    monkeypatch,
):
    transit_dir = tmp_path / "transit_queue_e2e"
    transit_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("SOVEREIGN_TRANSIT_QUEUE_DIR", str(transit_dir))
    monkeypatch.setattr(SovereignStorageGateway, "TRANSIT_QUEUE_DIR", transit_dir)

    primary_a = tmp_path / "disc_empresa_a_primary"
    secondary_a = tmp_path / "disc_empresa_a_secondary"
    primary_b = tmp_path / "disc_empresa_b_primary"
    secondary_b = tmp_path / "disc_empresa_b_secondary"
    for p in (primary_a, secondary_a, primary_b, secondary_b):
        p.mkdir(parents=True, exist_ok=True)

    token_a = f"svlt_{secrets.token_urlsafe(24)}"
    token_b = f"svlt_{secrets.token_urlsafe(24)}"

    dummy_llm_srv, dummy_llm_url, _ = start_local_llm_server(model_name="qwen-local")

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

    agent_a: RunningWssAgent | None = None
    agent_b: RunningWssAgent | None = None
    emp_a_id: str | None = None
    emp_b_id: str | None = None

    try:
        async with LiveUvicornServer() as server:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                # 1. Onboarding Empresa A SENSE URL externa ni Telegram -> cua xifrada SVENC1: + comanda 1-clic
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
                assert onb_a_json["tenant"]["disc_dur_url"] == f"wss-tunnel://{emp_a_id}"
                assert onb_a_json["vault_sync"]["status"] == "QUEUED"

                # Verificació abans de connectar l'agent -> TUNEL_OFFLINE
                off_check = await ac.post(
                    "/api/v1/superadmin/tenants/verificar-disc-dur",
                    json={"empresa_id": emp_a_id},
                    headers=sa_headers,
                )
                assert off_check.status_code == 200
                assert off_check.json()["status"] == "ERROR"
                assert off_check.json()["motiu"] == "TUNEL_OFFLINE"

                # 2. Connectem l'agent WSS real de l'Empresa A -> auto-creació 38 carpetes + drenatge
                agent_a = RunningWssAgent(
                    server.http_url,
                    role="EMPRESA",
                    token=token_a,
                    empresa_id=emp_a_id,
                    disk_a=primary_a,
                    disk_b=secondary_a,
                    llm_url=dummy_llm_url,
                ).start()
                await wait_for(lambda: vault_tunnel_broker.is_online(empresa_target_key(emp_a_id)))
                await wait_for(
                    lambda: (primary_a / "11_configuracio_i_backups/identitat_camaleo/empresa.json").is_file()
                    and (primary_a / "11_configuracio_i_backups/identitat_camaleo/boss.json").is_file()
                    and (primary_a / "09_copilot_ia/prompt_sistema/copilot_profile.json").is_file(),
                    timeout=8.0,
                )
                assert not (primary_b / "11_configuracio_i_backups/identitat_camaleo/empresa.json").exists()

                # Verificació roundtrip R/W/D real sobre WSS -> DISC_OPERATIU
                good_check = await ac.post(
                    "/api/v1/superadmin/tenants/verificar-disc-dur",
                    json={"empresa_id": emp_a_id},
                    headers=sa_headers,
                )
                assert good_check.status_code == 200
                good_data = good_check.json()
                assert good_data["status"] == "OK", good_data
                assert good_data["roundtrip_escriptura"] is True
                assert good_data["ia_proxy_ok"] is True
                assert list(primary_a.rglob("_healthcheck_*.json")) == []

                # Verificació en BD: telegram_webhook_secret continua None i vault_token és token_a
                await set_tenant_context(db_session, emp_a_id, is_superadmin=True)
                emp_a_db = (
                    await db_session.execute(select(Empresa).where(Empresa.id == uuid.UUID(emp_a_id)))
                ).scalar_one()
                assert emp_a_db.vault_token == token_a
                assert emp_a_db.telegram_webhook_secret is None

                # 3. Onboarding Empresa B + connexió del seu propi agent WSS B (aïllament estricte)
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
                emp_b_id = onb_b.json()["tenant"]["id"]
                agent_b = RunningWssAgent(
                    server.http_url,
                    role="EMPRESA",
                    token=token_b,
                    empresa_id=emp_b_id,
                    disk_a=primary_b,
                    disk_b=secondary_b,
                    llm_url=dummy_llm_url,
                ).start()
                await wait_for(
                    lambda: (primary_b / "11_configuracio_i_backups/identitat_camaleo/empresa.json").is_file(),
                    timeout=8.0,
                )

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

                planol_files_a = list((primary_a / "05_planols/arxius_base").glob("*.dxf"))
                assert len(planol_files_a) == 1
                assert planol_files_a[0].read_bytes() == dxf_bytes
                assert list((primary_b / "05_planols/arxius_base").glob("*.dxf")) == []

                raw_resp = await ac.get(
                    f"/api/v1/gestio/planols/{planol_id}/fitxer", headers=boss_headers
                )
                assert raw_resp.status_code == 200
                assert raw_resp.content == dxf_bytes

                png_bytes = (
                    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
                    b"\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc`\x00\x00"
                    b"\x00\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82"
                )
                up_logo = await ac.post(
                    f"/api/v1/superadmin/empreses/{emp_a_id}/logotip",
                    files={"fitxer": ("logo_test.png", png_bytes, "image/png")},
                    headers=sa_headers,
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

                # 5. Offline -> cua de trànsit xifrada SVENC1: -> reconnexió -> drenatge automàtic
                await agent_a.stop()
                agent_a = None
                async def _emp_a_offline() -> bool:
                    return not await vault_tunnel_broker.is_online(empresa_target_key(emp_a_id))
                await wait_for(_emp_a_offline)

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

                queued_files = list((transit_dir / emp_a_id).glob("*.bin"))
                assert len(queued_files) == 1
                raw_queued = queued_files[0].read_bytes()
                assert raw_queued.startswith(b"SVENC1:")
                assert b"%PDF-1.4" not in raw_queued

                transit_read = await ac.get(
                    f"/api/v1/gestio/planols/{off_json['id']}/fitxer", headers=boss_headers
                )
                assert transit_read.status_code == 200
                assert transit_read.content == secret_pdf

                # Reengeguem l'agent WSS A -> auto-drenatge automàtic al disc A i auto-purga a Hetzner
                agent_a = RunningWssAgent(
                    server.http_url,
                    role="EMPRESA",
                    token=token_a,
                    empresa_id=emp_a_id,
                    disk_a=primary_a,
                    disk_b=secondary_a,
                    llm_url=dummy_llm_url,
                ).start()
                await wait_for(
                    lambda: len(list((primary_a / "05_planols/arxius_base").glob("*.pdf"))) == 1,
                    timeout=8.0,
                )
                drain_res = await SovereignStorageGateway.drenar_cua_transit_empresa(
                    db_session, emp_a_id
                )
                assert drain_res["pendents"] == 0
                assert list((transit_dir / emp_a_id).glob("*.bin")) == []
                assert list((transit_dir / emp_a_id).glob("*.meta.json")) == []
                pdf_files_a = list((primary_a / "05_planols/arxius_base").glob("*.pdf"))
                assert pdf_files_a[0].read_bytes() == secret_pdf

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
        if agent_a is not None:
            await agent_a.stop()
        if agent_b is not None:
            await agent_b.stop()
        if emp_a_id:
            await vault_tunnel_broker.disconnect(empresa_target_key(emp_a_id))
        if emp_b_id:
            await vault_tunnel_broker.disconnect(empresa_target_key(emp_b_id))
        dummy_llm_srv.shutdown()
        dummy_llm_srv.server_close()
