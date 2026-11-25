"""Tests d'integració reals (Zero Mock) per a la configuració sobirana del Copilot (`copilot_profile.json`) i Zero-Storage Hetzner."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.core.config import settings
from app.main import app
from app.models.models import Empresa, Usuari
from app.services.copilot_config_service import (
    PROFILE_SCHEMA_VERSION,
    get_strict_copilot_config,
    invalidate_copilot_config_cache,
    save_strict_copilot_config,
)
from app.services.sovereign_storage import SovereignStorageGateway
from tests.wss_test_helpers import live_empresa_wss_context


def _make_headers(user_id: uuid.UUID, empresa_id: uuid.UUID, rol: str) -> dict[str, str]:
    token = jwt.encode(
        {
            "sub": str(user_id),
            "rol": rol,
            "empresa_id": str(empresa_id),
            "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
        },
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    return {
        "Authorization": f"Bearer {token}",
        "X-Empresa-ID": str(empresa_id),
    }


@pytest.mark.asyncio
async def test_copilot_config_force_rls_isolation_and_endpoints(
    admin_session, tmp_path: Path
) -> None:
    """Verifica aïllament multi-tenant, anti-IDOR, RBAC, 422 vs 503, migració read-only i eliminació de copilot_configs."""
    reg_chk = await admin_session.execute(text("SELECT to_regclass('public.copilot_configs')"))
    assert reg_chk.scalar() is None, "La taula residual public.copilot_configs ha d'estar eliminada."

    emp_a_id = uuid.uuid4()
    emp_b_id = uuid.uuid4()
    boss_a_id = uuid.uuid4()
    eng_a_id = uuid.uuid4()
    boss_b_id = uuid.uuid4()
    token_a = f"svlt_cfg_a_{uuid.uuid4().hex[:12]}"

    admin_session.add_all(
        [
            Empresa(
                id=emp_a_id,
                nom="Empresa Alfa SL",
                nif="B" + uuid.uuid4().hex[:8].upper(),
                subdomini="alfa-" + uuid.uuid4().hex[:6],
                vertical="BUILDINGPRO",
                pla_subscripcio="PRO",
                estat_pagament="ACTIU",
                disc_dur_url=f"wss-tunnel://{emp_a_id}",
                node_ia_url=f"wss-tunnel://{emp_a_id}",
                vault_token=token_a,
                feature_copilot_ia=True,
                node_ia_actiu=True,
            ),
            Empresa(
                id=emp_b_id,
                nom="Empresa Beta SL",
                nif="B" + uuid.uuid4().hex[:8].upper(),
                subdomini="beta-" + uuid.uuid4().hex[:6],
                vertical="CAMPOPRO",
                pla_subscripcio="PRO",
                estat_pagament="ACTIU",
                disc_dur_url=f"wss-tunnel://{emp_b_id}",
                node_ia_url=f"wss-tunnel://{emp_b_id}",
                vault_token=f"svlt_cfg_b_{uuid.uuid4().hex[:12]}",
                feature_copilot_ia=True,
                node_ia_actiu=True,
            ),
            Usuari(
                id=boss_a_id,
                empresa_id=emp_a_id,
                nif="11111111A",
                nom="Anna",
                cognoms="Alfa",
                rol="BOSS",
                estat="ACTIU",
            ),
            Usuari(
                id=eng_a_id,
                empresa_id=emp_a_id,
                nif="22222222B",
                nom="Marc",
                cognoms="Enginyer",
                rol="ENGINYER",
                estat="ACTIU",
            ),
            Usuari(
                id=boss_b_id,
                empresa_id=emp_b_id,
                nif="33333333C",
                nom="Joan",
                cognoms="Beta",
                rol="BOSS",
                estat="ACTIU",
            ),
        ]
    )
    await admin_session.commit()

    headers_boss_a = _make_headers(boss_a_id, emp_a_id, "BOSS")
    headers_eng_a = _make_headers(eng_a_id, emp_a_id, "ENGINYER")
    headers_boss_b = _make_headers(boss_b_id, emp_b_id, "BOSS")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Sense configuració -> GET retorna buit, /xat amb túnel offline retorna 503
        #    i /xat amb túnel online però sense configuració retorna 422 COPILOT_NOT_CONFIGURED
        r_empty = await ac.get("/api/v1/gestio/copilot/config", headers=headers_boss_a)
        assert r_empty.status_code == 200, r_empty.text
        assert r_empty.json()["system_prompt"] == ""

        r_xat_off = await ac.post(
            "/api/v1/gestio/copilot/xat",
            headers=headers_boss_a,
            json={"pregunta": "Quines feines tenim avui?"},
        )
        assert r_xat_off.status_code == 503, r_xat_off.text

        async with live_empresa_wss_context(
            emp_a_id,
            token_a,
            tmp_path / "disc_alfa_unconf",
            model_name="qwen2.5-alfa-local",
            default_reply="No s'hauria d'enviar",
        ):
            r_xat_unconf = await ac.post(
                "/api/v1/gestio/copilot/xat",
                headers=headers_boss_a,
                json={"pregunta": "Quines feines tenim avui?"},
            )
            assert r_xat_unconf.status_code == 422, r_xat_unconf.text
            assert "COPILOT_NOT_CONFIGURED" in r_xat_unconf.text

        # 2. ENGINYER no pot fer PUT /config (403)
        r_eng_put = await ac.put(
            "/api/v1/gestio/copilot/config",
            headers=headers_eng_a,
            json={"system_prompt": "Intent no autoritzat", "rag_prompt": ""},
        )
        assert r_eng_put.status_code == 403, r_eng_put.text

        # 3. BOSS d'Empresa A desa la seva configuració estricta
        r_put_a = await ac.put(
            "/api/v1/gestio/copilot/config",
            headers=headers_boss_a,
            json={
                "system_prompt": "PROMPT_EXCLUSIU_ALFA_123",
                "rag_prompt": "RAG_EXCLUSIU_ALFA_456",
                "subagent_prompts": {
                    "subagent_planificacio_equip": "SUBAGENT_PLAN_ALFA_789"
                },
                "llm_model": "qwen2.5-alfa-local",
            },
        )
        assert r_put_a.status_code == 200, r_put_a.text
        assert r_put_a.json()["system_prompt"] == "PROMPT_EXCLUSIU_ALFA_123"
        assert r_put_a.json()["llm_model"] == "qwen2.5-alfa-local"

        # 4. ENGINYER d'Empresa A sí que pot llegir la configuració d'Empresa A
        r_eng_get = await ac.get("/api/v1/gestio/copilot/config", headers=headers_eng_a)
        assert r_eng_get.status_code == 200
        assert r_eng_get.json()["system_prompt"] == "PROMPT_EXCLUSIU_ALFA_123"

        # 5. Aïllament total RLS: Empresa B NO veu la configuració d'Empresa A
        r_get_b = await ac.get("/api/v1/gestio/copilot/config", headers=headers_boss_b)
        assert r_get_b.status_code == 200
        assert r_get_b.json()["system_prompt"] == ""

        # Verificació directa a BD amb servei RLS
        cfg_b_direct = await get_strict_copilot_config(admin_session, emp_b_id)
        assert cfg_b_direct is None
        cfg_a_direct = await save_strict_copilot_config(
            admin_session,
            emp_a_id,
            system_prompt="PROMPT_EXCLUSIU_ALFA_123",
            rag_prompt="RAG_EXCLUSIU_ALFA_456",
            subagent_prompts={"subagent_planificacio_equip": "SUBAGENT_PLAN_ALFA_789"},
            llm_model="qwen2.5-alfa-local",
        )
        assert cfg_a_direct.empresa_id == emp_a_id

        # 6. Inferència real via Túnel WSS d'Empresa A rep exactament el prompt i model d'Alfa
        #    i la configuració resideix EXCLUSIVAMENT al disc dur del PC (Zero-Storage Hetzner)
        async with live_empresa_wss_context(
            emp_a_id,
            token_a,
            tmp_path / "disc_alfa",
            model_name="qwen2.5-alfa-local",
            default_reply="Resposta aïllada d'Alfa.",
        ) as ctx:
            r_xat_a = await ac.post(
                "/api/v1/gestio/copilot/xat",
                headers=headers_boss_a,
                json={"pregunta": "Quines feines tenim avui?"},
            )
            assert r_xat_a.status_code == 200, r_xat_a.text
            chat_calls = [c for c in ctx["llm_calls"] if c["path"] == "/v1/chat/completions"]
            assert len(chat_calls) >= 2  # Etapa 1 (Router JSON) + Etapa 2 (Síntesi KV Prefix Cache)

            router_body = chat_calls[0]["body"]
            assert router_body["model"] == "qwen2.5-alfa-local"
            assert router_body.get("response_format", {}).get("type") == "json_schema"

            synth_body = chat_calls[-1]["body"]
            assert synth_body["model"] == "qwen2.5-alfa-local"
            assert "tools" not in synth_body
            sys_msg = synth_body["messages"][0]["content"]
            user_msg = synth_body["messages"][-1]["content"]
            assert "PROMPT_EXCLUSIU_ALFA_123" in sys_msg
            assert "RAG_EXCLUSIU_ALFA_456" in sys_msg
            # Directrius de subagent han d'anar al torn user (abans de PREGUNTA) i MAI al prefix estàtic system
            assert "SUBAGENT_PLAN_ALFA_789" not in sys_msg
            assert "SUBAGENT_PLAN_ALFA_789" in user_msg
            assert user_msg.index("SUBAGENT_PLAN_ALFA_789") < user_msg.index("PREGUNTA:")
            assert user_msg.index("PREGUNTA:") < user_msg.index("\n<dades_empresa>\n")

            # Segona consulta amb un subagent diferent (estoc/magatzem): el prefix estàtic system ha de ser
            # byte-a-byte idèntic per preservar el KV Prefix Cache, i sense SUBAGENT_PLAN_ALFA_789 al torn user
            r_xat_a_estoc = await ac.post(
                "/api/v1/gestio/copilot/xat",
                headers=headers_boss_a,
                json={"pregunta": "Quin estoc tenim al magatzem?"},
            )
            assert r_xat_a_estoc.status_code == 200, r_xat_a_estoc.text
            chat_calls_after = [c for c in ctx["llm_calls"] if c["path"] == "/v1/chat/completions"]
            assert len(chat_calls_after) >= len(chat_calls) + 2
            synth_body_estoc = chat_calls_after[-1]["body"]
            assert synth_body_estoc["messages"][0]["content"] == sys_msg
            assert "SUBAGENT_PLAN_ALFA_789" not in synth_body_estoc["messages"][-1]["content"]

            # Verificació física Zero-Storage: fitxer únic `copilot_profile.json` al PC dedicat (sense system_prompt.txt ni taula PG)
            prompt_dir = tmp_path / "disc_alfa" / "09_copilot_ia" / "prompt_sistema"
            profile_file = prompt_dir / "copilot_profile.json"
            assert profile_file.is_file()
            assert not (prompt_dir / "system_prompt.txt").exists()
            profile_json = json.loads(profile_file.read_text(encoding="utf-8"))
            assert profile_json["version"] == PROFILE_SCHEMA_VERSION
            assert profile_json["llm_chat_model"] == "qwen2.5-alfa-local"
            assert profile_json["timeout_budget_s"] == 24.0
            assert "PROMPT_EXCLUSIU_ALFA_123" in profile_json["system_prompt"]

            pg_table = await admin_session.execute(text("SELECT to_regclass('public.copilot_configs')"))
            assert pg_table.scalar() is None

            # 7. CRUD complet de protocols RAG (crear, editar i eliminar al disc sobirà via WSS)
            r_rag_create = await ac.post(
                "/api/v1/gestio/copilot/rag/document",
                headers=headers_boss_a,
                json={
                    "titol": "Protocol Bomba Pressió",
                    "contingut": "Revisar pressostat a 3.5 bar abans d'arrencar.",
                    "tags": "bomba, pressio",
                },
            )
            assert r_rag_create.status_code == 201, r_rag_create.text
            rag_doc_id = r_rag_create.json()["id"]

            r_rag_edit = await ac.put(
                f"/api/v1/gestio/copilot/rag/document/{rag_doc_id}",
                headers=headers_boss_a,
                json={
                    "titol": "Protocol Bomba Pressió v2",
                    "contingut": "Revisar pressostat a 4.0 bar i purgar aire.",
                    "tags": "bomba, pressio, purga",
                },
            )
            assert r_rag_edit.status_code == 200, r_rag_edit.text

            r_rag_list = await ac.get("/api/v1/gestio/copilot/rag/document", headers=headers_boss_a)
            assert r_rag_list.status_code == 200
            docs_after_edit = r_rag_list.json()
            assert any(
                d["id"] == rag_doc_id
                and d["titol"] == "Protocol Bomba Pressió v2"
                and "purga" in d["tags"]
                for d in docs_after_edit
            )

            r_rag_del = await ac.delete(
                f"/api/v1/gestio/copilot/rag/document/{rag_doc_id}",
                headers=headers_boss_a,
            )
            assert r_rag_del.status_code == 200, r_rag_del.text

            r_rag_list_after = await ac.get(
                "/api/v1/gestio/copilot/rag/document", headers=headers_boss_a
            )
            assert r_rag_list_after.status_code == 200
            assert not any(d["id"] == rag_doc_id for d in r_rag_list_after.json())


@pytest.mark.asyncio
async def test_copilot_config_legacy_txt_migration_redis_and_503(
    admin_session, tmp_path: Path
) -> None:
    """Verifica migració read-only d'un sol cop de system_prompt.txt -> copilot_profile.json,
    invalidació multi-worker via Redis i propagació de 503 quan el túnel cau (vs 422)."""
    from app.core.redis import bump_cache_version

    emp_id = uuid.uuid4()
    tok = f"svlt_mig_{uuid.uuid4().hex[:12]}"
    admin_session.add(
        Empresa(
            id=emp_id,
            nom="Empresa Migració SL",
            nif="B" + uuid.uuid4().hex[:8].upper(),
            subdomini="mig-" + uuid.uuid4().hex[:6],
            vertical="HYDROPRO",
            pla_subscripcio="PRO",
            estat_pagament="ACTIU",
            disc_dur_url=f"wss-tunnel://{emp_id}",
            node_ia_url=f"wss-tunnel://{emp_id}",
            vault_token=tok,
            feature_copilot_ia=True,
            node_ia_actiu=True,
        )
    )
    await admin_session.commit()
    invalidate_copilot_config_cache(emp_id)

    # 1. Caiguda momentània del túnel WSS durant `file_get` -> ha de propagar HTTP 503 (MAI None / 422)
    from unittest.mock import AsyncMock, patch

    from app.services.vault_tunnel import VaultTunnelOfflineError, vault_tunnel_broker

    with (
        patch.object(vault_tunnel_broker, "is_online", new=AsyncMock(return_value=True)),
        patch.object(
            vault_tunnel_broker,
            "file_get",
            new=AsyncMock(side_effect=VaultTunnelOfflineError("Túnel caigut en trànsit.")),
        ),
    ):
        with pytest.raises(HTTPException) as exc_503:
            await SovereignStorageGateway.llegir_text_fitxer(
                admin_session, emp_id, "copilot_prompt", "system_prompt.txt"
            )
        assert exc_503.value.status_code == 503

    # 2. Amb túnel online i només legacy `system_prompt.txt` -> migra a `copilot_profile.json`
    disc = tmp_path / "disc_mig"
    legacy_dir = disc / "09_copilot_ia" / "prompt_sistema"
    legacy_dir.mkdir(parents=True, exist_ok=True)
    (legacy_dir / "system_prompt.txt").write_text("PROMPT_LEGACY_HYDRO_999", encoding="utf-8")

    async with live_empresa_wss_context(
        emp_id, tok, disc, model_name="qwen2.5-local", default_reply="OK"
    ):
        # Fitxer inexistent retorna None (NO 503)
        missing = await SovereignStorageGateway.llegir_text_fitxer(
            admin_session, emp_id, "copilot_prompt", "fitxer_inexistent.txt"
        )
        assert missing is None

        cfg_mig = await get_strict_copilot_config(admin_session, emp_id, use_cache=True)
        assert cfg_mig is not None
        assert cfg_mig.system_prompt == "PROMPT_LEGACY_HYDRO_999"
        assert cfg_mig.version == PROFILE_SCHEMA_VERSION
        profile_path = legacy_dir / "copilot_profile.json"
        assert profile_path.is_file()

        # 3. Simulació multi-worker: un altre worker actualitza el disc i incrementa la versió Redis
        raw_p = json.loads(profile_path.read_text(encoding="utf-8"))
        raw_p["system_prompt"] = "PROMPT_WORKER_2_ACTUALITZAT"
        profile_path.write_text(json.dumps(raw_p, ensure_ascii=False), encoding="utf-8")
        await bump_cache_version("copilot_cfg_ver", str(emp_id))

        cfg_refreshed = await get_strict_copilot_config(admin_session, emp_id, use_cache=True)
        assert cfg_refreshed is not None
        assert cfg_refreshed.system_prompt == "PROMPT_WORKER_2_ACTUALITZAT"
