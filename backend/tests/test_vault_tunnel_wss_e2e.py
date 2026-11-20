"""Suite End-to-End de Fase 5: Certificació Integral del Túnel Invers Natiu WSS (`ADR-001`).

Normativa estricta (AGENTS.md §5-§7 & Auditoria_i_Normativa_Tests_Backend.md):
- ZERO MOCKS: Servidor Uvicorn real + PostgreSQL 16 amb RLS + Redis 7 + agents WSS reals (`SovereignWssAgent`).
- ZERO DUALITAT: Cap servidor HTTP entrant al client, cap Cloudflare Tunnel, cap fallback LOCAL_FS a Hetzner.
- Cobreix els 5 escenaris mandatoris del pla de Fase 5:
  1. Aïllament total 2 Empreses + Superadmin amb 3 agents WSS reals simultanis (Disc + Copilot IA local).
  2. Seguretat Zero-Trust al handshake WSS (token erroni, spoofing cross-tenant, rol falsificat -> 4401/4403 + AlertaSeguretat).
  3. Offline + Cua Xifrada `SVENC1:` + Auto-drenatge + `unlink` immediat en reconnectar.
  4. Transferència Binària (PDF/PNG) + Magic Bytes + Anti-Path-Traversal (`../`).
  5. Pont Redis Cross-Process RPC (`celery_worker` / `bot` -> `uvicorn` propietari del WebSocket).
"""

from __future__ import annotations

import asyncio
import json
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict

import httpx
import jwt
import pytest
import websockets
from sqlalchemy import select

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import scripts.client_vault_agent as cva  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.core.db import set_tenant_context  # noqa: E402
from app.models.models import AlertaSeguretat, Empresa, Usuari  # noqa: E402
from app.services.sovereign_storage import (  # noqa: E402
    CARPETES_SUPERADMIN,
    MAPA_CARPETES_CLIENT,
    SovereignStorageGateway,
    SuperadminStorageGateway,
)
from app.services.vault_tunnel import (  # noqa: E402
    SUPERADMIN_TARGET_KEY,
    VaultTunnelBroker,
    VaultTunnelRemoteError,
    empresa_target_key,
    vault_tunnel_broker,
)
from tests.wss_test_helpers import (  # noqa: E402
    LiveUvicornServer,
    RunningWssAgent,
    start_local_llm_server,
    wait_for,
)


def _make_boss_headers(empresa_id: uuid.UUID, user_id: uuid.UUID) -> Dict[str, str]:
    tok = jwt.encode(
        {
            "sub": str(user_id),
            "empresa_id": str(empresa_id),
            "rol": "BOSS",
            "totp_verified": True,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
        },
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    return {
        "Authorization": f"Bearer {tok}",
        "X-Empresa-ID": str(empresa_id),
    }


def _make_superadmin_headers() -> Dict[str, str]:
    tok = jwt.encode(
        {
            "sub": "00000000-0000-0000-0000-000000000000",
            "empresa_id": None,
            "rol": "SUPERADMIN",
            "totp_activat": True,
            "ip_allowlist": ["127.0.0.1", "localhost", "testclient", "*"],
            "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
        },
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    return {"Authorization": f"Bearer {tok}"}


@pytest.mark.asyncio
async def test_fase5_1_aillament_total_2_empreses_i_superadmin_wss_reals(
    admin_session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test 1: 3 agents WSS reals (Empresa A, Empresa B, Superadmin) operant en paral·lel amb aïllament total."""
    sa_secret = f"svlt_sa_f5_{uuid.uuid4().hex[:16]}"
    monkeypatch.setenv("SUPERADMIN_VAULT_SECRET", sa_secret)
    monkeypatch.delenv("SUPERADMIN_VAULT_URL", raising=False)

    llm_a_srv, llm_a_url, llm_a_calls = start_local_llm_server(
        model_name="qwen2.5-empresa-A-reg",
        default_reply="Resposta exclusiva del Copilot d'Empresa A (CampoPro Reg).",
    )
    llm_b_srv, llm_b_url, llm_b_calls = start_local_llm_server(
        model_name="deepseek-empresa-B-rebt",
        default_reply="Resposta exclusiva del Copilot d'Empresa B (ElectricPro REBT).",
    )

    disk_a_main = tmp_path / "empresa_a_disc_a"
    disk_a_mirr = tmp_path / "empresa_a_disc_b"
    disk_b_main = tmp_path / "empresa_b_disc_a"
    disk_b_mirr = tmp_path / "empresa_b_disc_b"
    disk_sa_main = tmp_path / "superadmin_disc_a"
    disk_sa_mirr = tmp_path / "superadmin_disc_b"

    agent_sa: RunningWssAgent | None = None
    agent_a: RunningWssAgent | None = None
    agent_b: RunningWssAgent | None = None
    emp_a_id: uuid.UUID | None = None
    emp_b_id: uuid.UUID | None = None

    try:
        async with LiveUvicornServer() as server:
            # 1. Connectar Agent WSS de Superadmin
            agent_sa = RunningWssAgent(
                server.http_url,
                role="SUPERADMIN",
                token=sa_secret,
                disk_a=disk_sa_main,
                disk_b=disk_sa_mirr,
            ).start()
            await wait_for(lambda: vault_tunnel_broker.is_online(SUPERADMIN_TARGET_KEY))
            for sub in CARPETES_SUPERADMIN:
                await wait_for(lambda s=sub: (disk_sa_main / s).is_dir() and (disk_sa_mirr / s).is_dir())

            sa_headers = _make_superadmin_headers()
            async with httpx.AsyncClient(base_url=server.http_url, timeout=15.0) as client:
                # 2. Onboarding d'Empresa A i Empresa B via API real (mentre els seus PCs estan apagats)
                slug_a = f"f5empa-{uuid.uuid4().hex[:6]}"
                r_onb_a = await client.post(
                    "/api/v1/superadmin/tenants/onboarding",
                    headers=sa_headers,
                    json={
                        "rao_social": "Regadius Sobirans A S.L.",
                        "nif": f"B{uuid.uuid4().int % 89999999 + 10000000}",
                        "adreca": "Camí de l'Horta 12, Lleida",
                        "slug": slug_a,
                        "subdomini": slug_a,
                        "vertical": "CAMPOPRO",
                        "pla_subscripcio": "PRO",
                        "estat_inicial": "ACTIU",
                        "quota_operaris": 10,
                        "agent_prompt_system": "Copilot exclusiu d'Empresa A (Regadius).",
                        "boss_nif": f"{uuid.uuid4().int % 89999999 + 10000000}A",
                        "boss_nom": "Arnau",
                        "boss_cognoms": "Vila",
                        "boss_email": f"arnau@{slug_a}.cat",
                        "feature_flags": {"copilot_ia": True, "flota_avancada": True},
                    },
                )
                assert r_onb_a.status_code == 201, r_onb_a.text
                data_a = r_onb_a.json()
                emp_a_id = uuid.UUID(data_a["tenant"]["id"])
                boss_a_id = uuid.UUID(data_a["tenant"]["boss_usuari_id"])
                token_a = data_a["tenant"]["vault_token"]

                slug_b = f"f5empb-{uuid.uuid4().hex[:6]}"
                r_onb_b = await client.post(
                    "/api/v1/superadmin/tenants/onboarding",
                    headers=sa_headers,
                    json={
                        "rao_social": "Electra Sobirana B S.L.",
                        "nif": f"B{uuid.uuid4().int % 89999999 + 10000000}",
                        "adreca": "Polígon Nord Nau 8, Reus",
                        "slug": slug_b,
                        "subdomini": slug_b,
                        "vertical": "ELECTRICPRO",
                        "pla_subscripcio": "ENTERPRISE",
                        "estat_inicial": "ACTIU",
                        "quota_operaris": 20,
                        "agent_prompt_system": "Copilot exclusiu d'Empresa B (Baixa Tensió REBT).",
                        "boss_nif": f"{uuid.uuid4().int % 89999999 + 10000000}B",
                        "boss_nom": "Berta",
                        "boss_cognoms": "Serra",
                        "boss_email": f"berta@{slug_b}.cat",
                        "feature_flags": {"copilot_ia": True, "flota_avancada": True},
                    },
                )
                assert r_onb_b.status_code == 201, r_onb_b.text
                data_b = r_onb_b.json()
                emp_b_id = uuid.UUID(data_b["tenant"]["id"])
                boss_b_id = uuid.UUID(data_b["tenant"]["boss_usuari_id"])
                token_b = data_b["tenant"]["vault_token"]

                assert token_a != token_b

                # 3. Connectar simultàniament els agents WSS d'Empresa A i Empresa B
                agent_a = RunningWssAgent(
                    server.http_url,
                    role="EMPRESA",
                    token=token_a,
                    empresa_id=str(emp_a_id),
                    disk_a=disk_a_main,
                    disk_b=disk_a_mirr,
                    llm_url=llm_a_url,
                ).start()
                agent_b = RunningWssAgent(
                    server.http_url,
                    role="EMPRESA",
                    token=token_b,
                    empresa_id=str(emp_b_id),
                    disk_a=disk_b_main,
                    disk_b=disk_b_mirr,
                    llm_url=llm_b_url,
                ).start()

                await wait_for(lambda: vault_tunnel_broker.is_online(empresa_target_key(emp_a_id)))
                await wait_for(lambda: vault_tunnel_broker.is_online(empresa_target_key(emp_b_id)))

                # Verificar auto-bootstrap de les 38 carpetes + mirall Disc B i drenatge de fitxes inicials
                await wait_for(
                    lambda: (disk_a_main / "11_configuracio_i_backups/identitat_camaleo/empresa.json").is_file()
                    and (disk_b_main / "11_configuracio_i_backups/identitat_camaleo/empresa.json").is_file(),
                    timeout=8.0,
                )
                for rel_dir in MAPA_CARPETES_CLIENT.values():
                    assert (disk_a_main / rel_dir).is_dir()
                    assert (disk_a_mirr / rel_dir).is_dir()
                    assert (disk_b_main / rel_dir).is_dir()
                    assert (disk_b_mirr / rel_dir).is_dir()

                # Fitxes B2B al Disc de Superadmin i mai als discos de les empreses
                assert (disk_sa_main / f"01_tenants_b2b/fitxes_empreses/{emp_a_id}.json").is_file()
                assert (disk_sa_main / f"01_tenants_b2b/fitxes_empreses/{emp_b_id}.json").is_file()
                assert not (disk_a_main / "01_tenants_b2b").exists()
                assert not (disk_b_main / "01_tenants_b2b").exists()

                # 4. Escriptura d'entitats JSON a Empresa A i Empresa B -> aïllament físic absolut
                await SovereignStorageGateway.desar_entitat_json(
                    admin_session,
                    emp_a_id,
                    "clients",
                    "cli_exclusiu_a",
                    {"id": "cli_exclusiu_a", "rao_social": "Cooperativa Agrícola A"},
                )
                await SovereignStorageGateway.desar_entitat_json(
                    admin_session,
                    emp_b_id,
                    "clients",
                    "cli_exclusiu_b",
                    {"id": "cli_exclusiu_b", "rao_social": "Indústries Elèctriques B"},
                )

                assert (disk_a_main / "01_clients/fitxes/cli_exclusiu_a.json").is_file()
                assert not (disk_b_main / "01_clients/fitxes/cli_exclusiu_a.json").exists()
                assert not (disk_sa_main / "01_clients/fitxes/cli_exclusiu_a.json").exists()

                assert (disk_b_main / "01_clients/fitxes/cli_exclusiu_b.json").is_file()
                assert not (disk_a_main / "01_clients/fitxes/cli_exclusiu_b.json").exists()

                # 5. Copilot IA d'Empresa A parla NOMÉS amb el motor LLM d'Empresa A, i el de B amb el de B
                headers_a = _make_boss_headers(emp_a_id, boss_a_id)
                headers_b = _make_boss_headers(emp_b_id, boss_b_id)

                r_st_a = await client.get("/api/v1/gestio/copilot/ia-status", headers=headers_a)
                assert r_st_a.status_code == 200
                assert r_st_a.json()["estat"] == "ONLINE"
                assert r_st_a.json()["model_actiu"] == "qwen2.5-empresa-A-reg"

                r_st_b = await client.get("/api/v1/gestio/copilot/ia-status", headers=headers_b)
                assert r_st_b.status_code == 200
                assert r_st_b.json()["estat"] == "ONLINE"
                assert r_st_b.json()["model_actiu"] == "deepseek-empresa-B-rebt"

                r_chat_a = await client.post(
                    "/api/v1/gestio/copilot/xat",
                    headers=headers_a,
                    json={"pregunta": "Revisa els hidrants del sector nord."},
                )
                assert r_chat_a.status_code == 200, r_chat_a.text
                assert "Empresa A (CampoPro Reg)" in r_chat_a.json()["resposta"]

                r_chat_b = await client.post(
                    "/api/v1/gestio/copilot/xat",
                    headers=headers_b,
                    json={"pregunta": "Revisa el diferencial del quadre general."},
                )
                assert r_chat_b.status_code == 200, r_chat_b.text
                assert "Empresa B (ElectricPro REBT)" in r_chat_b.json()["resposta"]

                assert any(c["path"] == "/v1/chat/completions" for c in llm_a_calls)
                assert any(c["path"] == "/v1/chat/completions" for c in llm_b_calls)
    finally:
        for ag in (agent_a, agent_b, agent_sa):
            if ag is not None:
                await ag.stop()
        if emp_a_id:
            await vault_tunnel_broker.disconnect(empresa_target_key(emp_a_id))
        if emp_b_id:
            await vault_tunnel_broker.disconnect(empresa_target_key(emp_b_id))
        await vault_tunnel_broker.disconnect(SUPERADMIN_TARGET_KEY)
        llm_a_srv.shutdown()
        llm_a_srv.server_close()
        llm_b_srv.shutdown()
        llm_b_srv.server_close()


@pytest.mark.asyncio
async def test_fase5_2_seguretat_zero_trust_handshake_wss(
    admin_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test 2: Rebuig immediat 4401/4403 davant tokens erronis, spoofing cross-tenant o rols falsificats + AlertaSeguretat."""
    sa_secret = f"svlt_sa_f5_sec_{uuid.uuid4().hex[:16]}"
    monkeypatch.setenv("SUPERADMIN_VAULT_SECRET", sa_secret)

    emp_a_id = uuid.uuid4()
    emp_b_id = uuid.uuid4()
    tok_a = f"svlt_a_{uuid.uuid4().hex[:16]}"
    tok_b = f"svlt_b_{uuid.uuid4().hex[:16]}"

    admin_session.add_all(
        [
            Empresa(
                id=emp_a_id,
                nom="Sec A SL",
                nif=f"B{uuid.uuid4().int % 89999999 + 10000000}",
                subdomini=f"seca-{uuid.uuid4().hex[:6]}",
                vertical="CAMPOPRO",
                estat_pagament="ACTIU",
                pla_subscripcio="PRO",
                vault_token=tok_a,
            ),
            Empresa(
                id=emp_b_id,
                nom="Sec B SL",
                nif=f"B{uuid.uuid4().int % 89999999 + 10000000}",
                subdomini=f"secb-{uuid.uuid4().hex[:6]}",
                vertical="ELECTRICPRO",
                estat_pagament="SUSPES_PAGAMENT",
                pla_subscripcio="PRO",
                vault_token=tok_b,
            ),
        ]
    )
    await admin_session.commit()

    async with LiveUvicornServer() as server:
        ws_url = f"ws://127.0.0.1:{server.port}/api/v1/vault-tunnel/connect"

        # 1. Token d'Empresa A intentant suplantar Empresa B -> 4401 / 4403
        async with websockets.connect(
            ws_url,
            additional_headers={
                "X-Vault-Role": "EMPRESA",
                "X-Empresa-ID": str(emp_a_id),
                "X-Vault-Token": tok_b,
            },
        ) as ws_spoof:
            with pytest.raises(websockets.ConnectionClosed) as exc_spoof:
                await ws_spoof.recv()
            assert exc_spoof.value.rcvd is not None and exc_spoof.value.rcvd.code == 4401

        # 2. Rol falsificat (INVALID_ROLE) -> 4401
        async with websockets.connect(
            ws_url,
            additional_headers={
                "X-Vault-Role": "HACKER_ADMIN",
                "X-Vault-Token": sa_secret,
            },
        ) as ws_role:
            with pytest.raises(websockets.ConnectionClosed) as exc_role:
                await ws_role.recv()
            assert exc_role.value.rcvd is not None and exc_role.value.rcvd.code == 4401

        # 3. SUPERADMIN enviant X-Empresa-ID (intent de barreja) -> 4403
        async with websockets.connect(
            ws_url,
            additional_headers={
                "X-Vault-Role": "SUPERADMIN",
                "X-Empresa-ID": str(emp_a_id),
                "X-Vault-Token": sa_secret,
            },
        ) as ws_sa_mix:
            with pytest.raises(websockets.ConnectionClosed) as exc_sa_mix:
                await ws_sa_mix.recv()
            assert exc_sa_mix.value.rcvd is not None and exc_sa_mix.value.rcvd.code == 4403

        # 4. Empresa suspesa (SUSPES_PAGAMENT) -> 4403
        async with websockets.connect(
            ws_url,
            additional_headers={
                "X-Vault-Role": "EMPRESA",
                "X-Empresa-ID": str(emp_b_id),
                "X-Vault-Token": tok_b,
            },
        ) as ws_susp:
            with pytest.raises(websockets.ConnectionClosed) as exc_susp:
                await ws_susp.recv()
            assert exc_susp.value.rcvd is not None and exc_susp.value.rcvd.code == 4403

        # Verificar que s'han registrat les alertes de seguretat a PostgreSQL
        await set_tenant_context(admin_session, None, is_superadmin=True)
        alertes = (
            await admin_session.execute(
                select(AlertaSeguretat).where(
                    AlertaSeguretat.tipus.in_(
                        ["WSS_TUNNEL_AUTH_FAILED", "WSS_TUNNEL_FORBIDDEN"]
                    )
                )
            )
        ).scalars().all()
        assert len(alertes) >= 4


@pytest.mark.asyncio
async def test_fase5_3_offline_cua_svenc1_503_copilot_i_autodrenatge_unlink(
    admin_session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test 3: Agent apagat -> Copilot retorna 503 NODE_IA_OFFLINE, escriptures van a cua SVENC1:, i en reconnectar es drena i fa unlink."""
    transit_root = tmp_path / "transit_queue_f5"
    monkeypatch.setenv("SOVEREIGN_TRANSIT_QUEUE_DIR", str(transit_root))

    emp_id = uuid.uuid4()
    boss_id = uuid.uuid4()
    tok = f"svlt_f5_off_{uuid.uuid4().hex[:16]}"
    disk_a = tmp_path / "off_disk_a"
    disk_b = tmp_path / "off_disk_b"

    admin_session.add(
        Empresa(
            id=emp_id,
            nom="Offline Drain SL",
            nif=f"B{uuid.uuid4().int % 89999999 + 10000000}",
            subdomini=f"offf5-{uuid.uuid4().hex[:6]}",
            vertical="HYDROPRO",
            estat_pagament="ACTIU",
            pla_subscripcio="PRO",
            feature_copilot_ia=True,
            node_ia_actiu=True,
            node_ia_url=f"wss-tunnel://{emp_id}",
            disc_dur_url=f"wss-tunnel://{emp_id}",
            vault_token=tok,
        )
    )
    admin_session.add(
        Usuari(
            id=boss_id,
            empresa_id=emp_id,
            nif=f"{uuid.uuid4().int % 89999999 + 10000000}H",
            nom="Helena",
            cognoms="Bosch",
            email=f"helena-{emp_id.hex[:6]}@sevalor.cat",
            rol="BOSS",
            estat="ACTIU",
            totp_activat=True,
        )
    )
    await admin_session.commit()

    agent: RunningWssAgent | None = None
    try:
        async with LiveUvicornServer() as server:
            boss_headers = _make_boss_headers(emp_id, boss_id)
            async with httpx.AsyncClient(base_url=server.http_url, timeout=15.0) as client:
                # 1. Amb el túnel WSS desconnectat -> Copilot retorna 503 TUNEL_OFFLINE (Zero Fallback)
                r_chat_off = await client.post(
                    "/api/v1/gestio/copilot/xat",
                    headers=boss_headers,
                    json={"pregunta": "Quin cabal tenim a la canonada principal?"},
                )
                assert r_chat_off.status_code == 503
                assert r_chat_off.json()["detail"]["motiu"] == "TUNEL_OFFLINE"

                # 2. Escriptura JSON i fitxer binari mentre el PC és apagat -> cua xifrada SVENC1:
                ref_json = await SovereignStorageGateway.desar_entitat_json(
                    admin_session,
                    emp_id,
                    "clients",
                    "cli_offline_1",
                    {"id": "cli_offline_1", "nom": "Client Desat de Nit SL"},
                )
                assert ref_json.startswith(f"transit://{emp_id}/")

                pdf_secret = b"%PDF-1.4\nAlbara nocturn secret\n%%EOF\n"
                ref_bin = await SovereignStorageGateway.pujar_fitxer_binari(
                    admin_session,
                    emp_id,
                    "albarans",
                    "albara_nit.pdf",
                    pdf_secret,
                    "application/pdf",
                )
                assert ref_bin.startswith(f"transit://{emp_id}/")

                emp_transit_dir = transit_root / str(emp_id)
                raw_files = list(emp_transit_dir.glob("*.json")) + list(emp_transit_dir.glob("*.bin"))
                assert len(raw_files) >= 2
                for rf in [f for f in raw_files if not f.name.endswith(".meta.json")]:
                    blob = rf.read_bytes()
                    assert blob.startswith(b"SVENC1:")
                    assert b"Client Desat de Nit" not in blob
                    assert b"Albara nocturn secret" not in blob

                # 3. Engeguem el PC del client (SovereignWssAgent) -> auto-drenatge i unlink immediat a Hetzner
                agent = RunningWssAgent(
                    server.http_url,
                    role="EMPRESA",
                    token=tok,
                    empresa_id=str(emp_id),
                    disk_a=disk_a,
                    disk_b=disk_b,
                ).start()

                target_cli_file = disk_a / "01_clients/fitxes/cli_offline_1.json"
                target_bin_file = disk_a / "03_magatzem/albarans_compra/albara_nit.pdf"
                await wait_for(
                    lambda: target_cli_file.is_file() and target_bin_file.is_file(),
                    timeout=8.0,
                )
                assert target_bin_file.read_bytes() == pdf_secret
                saved_cli = json.loads(target_cli_file.read_text("utf-8"))
                assert saved_cli["nom"] == "Client Desat de Nit SL"

                # Cua de trànsit a Hetzner completament buida (unlink verificat)
                await wait_for(
                    lambda: SovereignStorageGateway.comptar_cua_transit_empresa(emp_id) == 0,
                    timeout=5.0,
                )
                assert list(emp_transit_dir.glob("*.bin")) == []
                assert list(emp_transit_dir.glob("*.meta.json")) == []
    finally:
        if agent is not None:
            await agent.stop()
        await vault_tunnel_broker.disconnect(empresa_target_key(emp_id))


@pytest.mark.asyncio
async def test_fase5_4_binaris_magic_bytes_i_anti_path_traversal_wss(
    admin_session, tmp_path: Path
) -> None:
    """Test 4: Pujada, lectura, reanomenat i esborrat de PDF/PNG reals sobre WSS + bloqueig estricte de Path Traversal (`../`)."""
    emp_id = uuid.uuid4()
    tok = f"svlt_f5_bin_{uuid.uuid4().hex[:16]}"
    disk_a = tmp_path / "bin_disk_a"
    disk_b = tmp_path / "bin_disk_b"

    admin_session.add(
        Empresa(
            id=emp_id,
            nom="Binary Guard SL",
            nif=f"B{uuid.uuid4().int % 89999999 + 10000000}",
            subdomini=f"binf5-{uuid.uuid4().hex[:6]}",
            vertical="BUILDINGPRO",
            estat_pagament="ACTIU",
            pla_subscripcio="PRO",
            node_ia_url=f"wss-tunnel://{emp_id}",
            disc_dur_url=f"wss-tunnel://{emp_id}",
            vault_token=tok,
        )
    )
    await admin_session.commit()

    agent: RunningWssAgent | None = None
    try:
        async with LiveUvicornServer() as server:
            agent = RunningWssAgent(
                server.http_url,
                role="EMPRESA",
                token=tok,
                empresa_id=str(emp_id),
                disk_a=disk_a,
                disk_b=disk_b,
            ).start()
            target_key = empresa_target_key(emp_id)
            await wait_for(lambda: vault_tunnel_broker.is_online(target_key))

            # 1. PNG real amb Magic Bytes vàlids
            png_bytes = (
                b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
                b"\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc`\x00\x00"
                b"\x00\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82"
            )
            uri_png = await SovereignStorageGateway.pujar_fitxer_binari(
                admin_session,
                emp_id,
                "incidencies_fotos",
                "evidencia_1.png",
                png_bytes,
                "image/png",
            )
            assert uri_png == "vault://07_incidencies/fotos_camp/evidencia_1.png"
            read_bytes, read_name = await SovereignStorageGateway.obtenir_bytes_fitxer(
                admin_session, emp_id, uri_png
            )
            assert read_bytes == png_bytes
            assert read_name == "evidencia_1.png"

            # Reanomenar i esborrar
            uri_renamed = await SovereignStorageGateway.reanomenar_fitxer_binari(
                db=admin_session,
                empresa_id=emp_id,
                old_path=uri_png,
                new_filename="evidencia_validada.png",
                categoria="incidencies_fotos",
                content_type="image/png",
            )
            assert uri_renamed.endswith("/evidencia_validada.png")
            assert await SovereignStorageGateway.esborrar_fitxer_binari(
                admin_session, emp_id, uri_renamed
            ) is True

            # 2. Intents d'atac Path Traversal (`../`) directes pel broker -> bloquejats per l'agent amb PATH_TRAVERSAL (400)
            with pytest.raises(VaultTunnelRemoteError) as exc_trav1:
                await vault_tunnel_broker.call(
                    target_key,
                    "json_put",
                    {
                        "subcarpeta": "../../etc",
                        "item_id": "passwd",
                        "content": {"hacked": True},
                    },
                )
            assert exc_trav1.value.code == "PATH_TRAVERSAL"

            with pytest.raises(VaultTunnelRemoteError) as exc_trav2:
                await vault_tunnel_broker.call(
                    target_key,
                    "file_get",
                    {"rel_path": "../../../etc/shadow"},
                )
            assert exc_trav2.value.code == "PATH_TRAVERSAL"
    finally:
        if agent is not None:
            await agent.stop()
        await vault_tunnel_broker.disconnect(empresa_target_key(emp_id))


@pytest.mark.asyncio
async def test_fase5_5_redis_cross_process_rpc_celery_bot_bridge(
    admin_session, tmp_path: Path
) -> None:
    """Test 5: Un segon broker extern (simulant `celery_worker` o `bot` en un altre procés) executa accions RPC via Redis 7 cap al WebSocket sostingut per `uvicorn`."""
    emp_id = uuid.uuid4()
    tok = f"svlt_f5_rpc_{uuid.uuid4().hex[:16]}"
    disk_a = tmp_path / "rpc_disk_a"
    disk_b = tmp_path / "rpc_disk_b"

    llm_srv, llm_url, _ = start_local_llm_server(
        model_name="qwen2.5-celery-worker-test",
        default_reply="Resposta generada des del worker via pont Redis 7 -> WSS.",
    )

    admin_session.add(
        Empresa(
            id=emp_id,
            nom="Redis RPC Bridge SL",
            nif=f"B{uuid.uuid4().int % 89999999 + 10000000}",
            subdomini=f"rpcf5-{uuid.uuid4().hex[:6]}",
            vertical="CAMPOPRO",
            estat_pagament="ACTIU",
            pla_subscripcio="PRO",
            node_ia_url=f"wss-tunnel://{emp_id}",
            disc_dur_url=f"wss-tunnel://{emp_id}",
            vault_token=tok,
        )
    )
    await admin_session.commit()

    agent: RunningWssAgent | None = None
    try:
        async with LiveUvicornServer() as server:
            agent = RunningWssAgent(
                server.http_url,
                role="EMPRESA",
                token=tok,
                empresa_id=str(emp_id),
                disk_a=disk_a,
                disk_b=disk_b,
                llm_url=llm_url,
            ).start()
            target_key = empresa_target_key(emp_id)
            await wait_for(lambda: vault_tunnel_broker.is_online(target_key))

            # Instància independent de VaultTunnelBroker sense connexions en memòria local (simula procés celery_worker / bot)
            external_worker_broker = VaultTunnelBroker()
            assert target_key not in external_worker_broker._connections
            assert await external_worker_broker.is_online(target_key) is True

            # 1. Escriptura i lectura JSON des del procés worker a través del pont Redis 7 -> WebSocket Uvicorn -> PC Client
            await external_worker_broker.json_put(
                target_key,
                subcarpeta="04_factures/verifactu_emeses",
                item_id="fac_celery_001",
                content={"id": "fac_celery_001", "import_total": 1250.50, "origen": "celery_worker"},
            )
            assert (disk_a / "04_factures/verifactu_emeses/fac_celery_001.json").is_file()

            items = await external_worker_broker.json_get_list(
                target_key, "04_factures/verifactu_emeses"
            )
            assert any(i.get("id") == "fac_celery_001" for i in items)

            # 2. Crida d'inferència LLM des del procés bot/celery a través del pont Redis 7
            chat_res = await external_worker_broker.call_llm_chat(
                target_key,
                {
                    "model": "qwen2.5-celery-worker-test",
                    "messages": [{"role": "user", "content": " Ping des de Telegram Bot "}],
                },
            )
            reply_content = chat_res["choices"][0]["message"]["content"]
            assert "pont Redis 7 -> WSS" in reply_content
    finally:
        if agent is not None:
            await agent.stop()
        await vault_tunnel_broker.disconnect(empresa_target_key(emp_id))
        llm_srv.shutdown()
        llm_srv.server_close()
