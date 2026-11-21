"""Tests d'integració reals (Zero Mock) per a copilot_configs amb FORCE RLS i aïllament total per empresa."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.core.config import settings
from app.main import app
from app.models.models import Empresa, Usuari
from app.services.copilot_config_service import (
    get_strict_copilot_config,
    save_strict_copilot_config,
)
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
    """Verifica FORCE RLS, anti-IDOR, RBAC, 422 COPILOT_NOT_CONFIGURED i inferència WSS aïllada."""
    # Assegurem la política FORCE RLS a la BD de test (idempotent amb la migració a025)
    await admin_session.execute(text("ALTER TABLE public.copilot_configs ENABLE ROW LEVEL SECURITY;"))
    await admin_session.execute(text("ALTER TABLE public.copilot_configs FORCE ROW LEVEL SECURITY;"))
    await admin_session.execute(
        text("DROP POLICY IF EXISTS copilot_configs_strict_isolation ON public.copilot_configs;")
    )
    await admin_session.execute(
        text(
            """
            CREATE POLICY copilot_configs_strict_isolation ON public.copilot_configs
                FOR ALL
                USING (empresa_id = NULLIF(current_setting('app.current_empresa_id', true), '')::uuid)
                WITH CHECK (empresa_id = NULLIF(current_setting('app.current_empresa_id', true), '')::uuid);
            """
        )
    )

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
            assert len(chat_calls) >= 1
            sent_body = chat_calls[0]["body"]
            assert sent_body["model"] == "qwen2.5-alfa-local"
            sys_msg = sent_body["messages"][0]["content"]
            assert "PROMPT_EXCLUSIU_ALFA_123" in sys_msg
            assert "RAG_EXCLUSIU_ALFA_456" in sys_msg
            assert "SUBAGENT_PLAN_ALFA_789" in sys_msg

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
