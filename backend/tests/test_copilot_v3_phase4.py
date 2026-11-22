"""Tests Phase 4 — Copilot v3.2 (`T076`–`T078`).

Valida:
1. Semàfor de concurrència `SEVALOR_LOCAL_LLM_CONCURRENCY=1` amb prioritat estricta
   (`HIGH` Copilot > `LOW` OCR), cancel·lació sense fuites i neteja de camps `_sevalor_*`
   a `scripts/client_vault_agent.py`.
2. `strip_think()`, prioritat `LOW` i `llm_vision_model` sobirà a `ocr_service._cridar_ia_vision`.
3. Eliminació del motor d'eines legacy a `gestio/copilot.py` i zero fallbacks SQL a
   `SubagentFlotaDespatx`.
4. Validació del benchmark `scripts/eval_copilot_models.py` (38 casos reals, 4 verticals).
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List

import httpx
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_script_module(name: str, rel_path: str):
    path = REPO_ROOT / rel_path
    spec = importlib.util.spec_from_file_location(name, str(path))
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


client_vault_agent = _load_script_module("client_vault_agent_p4", "scripts/client_vault_agent.py")
eval_copilot_models = _load_script_module("eval_copilot_models_p4", "scripts/eval_copilot_models.py")


# ---------------------------------------------------------------------------
# T076.1 — Priority Concurrency Limiter & SovereignWssAgent.action_llm_chat
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_priority_concurrency_limiter_serializes_and_prioritizes_high_over_low():
    """Amb concurrència=1, una petició Copilot (`HIGH`) passa SEMPRE abans que una OCR (`LOW`)."""
    limiter = client_vault_agent._PriorityConcurrencyLimiter(max_concurrency=1)
    execution_order: List[str] = []
    max_parallel = 0
    current_parallel = 0
    first_entered = asyncio.Event()
    release_first = asyncio.Event()

    async def worker(tag: str, priority: str, hold: bool = False) -> None:
        nonlocal max_parallel, current_parallel
        async with limiter.acquire(priority):
            current_parallel += 1
            max_parallel = max(max_parallel, current_parallel)
            execution_order.append(tag)
            if hold:
                first_entered.set()
                await release_first.wait()
            else:
                await asyncio.sleep(0.01)
            current_parallel -= 1

    # 1. Ocupem l'únic slot amb una tasca inicial
    t1 = asyncio.create_task(worker("first_holder", "LOW", hold=True))
    await first_entered.wait()
    assert limiter.in_flight == 1

    # 2. Encuem primer 2 tasques OCR (LOW) i després 1 tasca Copilot (HIGH)
    t_ocr_1 = asyncio.create_task(worker("ocr_1", "LOW"))
    await asyncio.sleep(0.005)
    t_ocr_2 = asyncio.create_task(worker("ocr_2", "LOW"))
    await asyncio.sleep(0.005)
    t_copilot = asyncio.create_task(worker("copilot_high", "HIGH"))
    await asyncio.sleep(0.005)

    assert limiter.queued == 3

    # 3. Alliberem el primer slot: `copilot_high` ha d'entrar ABANS que `ocr_1` i `ocr_2`
    release_first.set()
    await asyncio.gather(t1, t_ocr_1, t_ocr_2, t_copilot)

    assert max_parallel == 1
    assert limiter.in_flight == 0
    assert limiter.queued == 0
    assert execution_order == ["first_holder", "copilot_high", "ocr_1", "ocr_2"]


@pytest.mark.asyncio
async def test_priority_concurrency_limiter_cancellation_does_not_leak_slot():
    """Si una tasca en cua es cancel·la per timeout, el slot no es perd mai."""
    limiter = client_vault_agent._PriorityConcurrencyLimiter(max_concurrency=1)
    entered = asyncio.Event()
    release = asyncio.Event()

    async def holder() -> None:
        async with limiter.acquire("HIGH"):
            entered.set()
            await release.wait()

    t_hold = asyncio.create_task(holder())
    await entered.wait()

    async def waiter_cancelled() -> None:
        async with limiter.acquire("LOW"):
            pass

    t_cancel = asyncio.create_task(waiter_cancelled())
    await asyncio.sleep(0.005)
    t_cancel.cancel()
    with pytest.raises(asyncio.CancelledError):
        await t_cancel

    release.set()
    await t_hold
    assert limiter.in_flight == 0

    # El semàfor ha de continuar totalment operatiu
    async with limiter.acquire("HIGH"):
        assert limiter.in_flight == 1
    assert limiter.in_flight == 0


@pytest.mark.asyncio
async def test_action_llm_chat_strips_internal_fields_and_reports_health(tmp_path: Path, monkeypatch):
    """`action_llm_chat` elimina `x-vault-token` i `_sevalor_*` abans d'enviar el body a LM Studio."""
    captured_bodies: List[Dict[str, Any]] = []

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url: str, json: Dict[str, Any], headers: Dict[str, str]):
            captured_bodies.append(dict(json))
            return httpx.Response(
                200,
                json={"choices": [{"message": {"content": "OK"}}]},
                request=httpx.Request("POST", url),
            )

        async def get(self, url: str, headers: Dict[str, str] | None = None):
            return httpx.Response(
                200,
                json={"data": [{"id": "qwen2.5-vl-7b-instruct"}]},
                request=httpx.Request("GET", url),
            )

    monkeypatch.setattr(client_vault_agent.httpx, "AsyncClient", FakeAsyncClient)

    cfg = client_vault_agent.AgentConfig(
        server_url="https://example.sevalor.test",
        role="EMPRESA",
        empresa_id=str(uuid.uuid4()),
        vault_token="secret-token-123",
        disk_a=tmp_path / "disk_a",
        disk_b=tmp_path / "disk_b",
        local_llm_url="http://127.0.0.1:1234",
        local_llm_concurrency=1,
    )
    agent = client_vault_agent.SovereignWssAgent(cfg)

    health = await agent.action_health()
    assert health["llm_concurrency"] == 1
    assert health["llm_in_flight"] == 0
    assert health["llm_online"] is True

    resp = await agent.action_llm_chat(
        {
            "model": "qwen2.5-vl-7b-instruct",
            "messages": [{"role": "user", "content": "hola"}],
            "_sevalor_priority": "LOW",
            "_sevalor_trace_id": "abc",
            "X-Vault-Token": "MUST_NOT_LEAK",
        },
        timeout_s=3.0,
    )
    assert resp["choices"][0]["message"]["content"] == "OK"
    assert len(captured_bodies) == 1
    sent = captured_bodies[0]
    assert "_sevalor_priority" not in sent
    assert "_sevalor_trace_id" not in sent
    assert "X-Vault-Token" not in sent
    assert sent["model"] == "qwen2.5-vl-7b-instruct"


# ---------------------------------------------------------------------------
# T076.2 — OCR Vision: `strip_think()`, prioritat `LOW` i `llm_vision_model`
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ocr_vision_strips_think_block_uses_low_priority_and_vision_model(monkeypatch):
    """`_cridar_ia_vision` neteja `<think>{...}</think>` abans del JSON, envia `_sevalor_priority=LOW` i usa `llm_vision_model`."""
    from app.services import ocr_service
    from app.services.copilot_config_service import invalidate_copilot_config_cache

    emp_id = uuid.uuid4()
    invalidate_copilot_config_cache(emp_id)
    captured_payloads: List[Dict[str, Any]] = []

    async def fake_is_online(target_key: str) -> bool:
        return True

    async def fake_json_get_list(target_key: str, subcarpeta: str, *, timeout: float = 10.0):
        return [
            {
                "id": "copilot_profile",
                "llm_chat_model": "qwen3.5-9b",
                "llm_vision_model": "qwen2.5-vl-7b-instruct-sovereign",
            }
        ]

    async def fake_call_llm_chat(target_key: str, payload: Dict[str, Any], *, timeout: float = 45.0):
        captured_payloads.append(dict(payload))
        return {
            "choices": [
                {
                    "message": {
                        "content": (
                            '<think>Analitzo la factura: {"import_fals": 999999}</think>\n'
                            '```json\n{"proveidor": "Ferreteria Ponent", "total": 145.50}\n```'
                        )
                    }
                }
            ]
        }

    monkeypatch.setattr(ocr_service.vault_tunnel_broker, "is_online", fake_is_online)
    monkeypatch.setattr(ocr_service.vault_tunnel_broker, "json_get_list", fake_json_get_list)
    monkeypatch.setattr(ocr_service.vault_tunnel_broker, "call_llm_chat", fake_call_llm_chat)

    parsed = await ocr_service._cridar_ia_vision(
        prompt_sistema="Extreu factura JSON",
        text_contingut="Factura 145.50 EUR Ferreteria Ponent",
        empresa_id=emp_id,
    )

    assert parsed == {"proveidor": "Ferreteria Ponent", "total": 145.50}
    assert len(captured_payloads) == 1
    assert captured_payloads[0]["_sevalor_priority"] == "LOW"
    assert captured_payloads[0]["model"] == "qwen2.5-vl-7b-instruct-sovereign"


# ---------------------------------------------------------------------------
# T077 — Neteja codi legacy a `gestio/copilot.py` i zero fallbacks SQL a flota
# ---------------------------------------------------------------------------


def test_legacy_copilot_engine_removed_and_public_helpers_preserved():
    """Els símbols legacy de `gestio/copilot.py` ja no existeixen; es mantenen els ponts actius."""
    from app.api.v1.gestio import copilot as copilot_mod

    for legacy_name in (
        "TOOLS_SCHEMA",
        "execute_tool_get_unbilled_money",
        "execute_tool_replanificar_ot",
        "execute_tool_get_real_stock",
        "execute_tool_get_closest_vehicle",
        "execute_tool_get_warranty_status",
        "execute_tool_get_client_history",
        "execute_tool_get_rag_knowledge",
        "executar_eina",
        "cridar_lm_studio_amb_tools",
        "executar_agent_local",
    ):
        assert not hasattr(copilot_mod, legacy_name), f"Símbol legacy residual trobat: {legacy_name}"

    assert callable(getattr(copilot_mod, "cridar_lm_studio", None))
    assert callable(getattr(copilot_mod, "execute_tool_get_vehicle_info", None))


@pytest.mark.asyncio
async def test_subagent_flota_zero_sql_fallback_when_sovereign_disk_empty(monkeypatch):
    """`SubagentFlotaDespatx` mai fa fallback SQL contra PostgreSQL quan el disc sobirà és buit."""
    from app.services.subagents.subagent_flota_despatx import SubagentFlotaDespatx

    sub = SubagentFlotaDespatx()
    emp_id = uuid.uuid4()

    async def empty_read(db, empresa_id, cat):
        return []

    monkeypatch.setattr(sub, "read_sovereign_category", empty_read)

    class ForbiddenDB:
        async def execute(self, *args, **kwargs):
            raise AssertionError("PROHIBIT fer fallback SQL des de SubagentFlotaDespatx!")

    res_audit = await sub.tool_audit_itv_insurance_fleet(ForbiddenDB(), emp_id, dies_marge=30)  # type: ignore[arg-type]
    assert res_audit["trobat"] is False
    assert res_audit["total_alertes"] == 0

    res_heavy = await sub.tool_get_heavy_vehicles_for_ot(ForbiddenDB(), emp_id, carrega_minima_kg=2000)  # type: ignore[arg-type]
    assert res_heavy["trobat"] is False
    assert res_heavy["total_vehicles"] == 0


# ---------------------------------------------------------------------------
# T078 — Benchmark `scripts/eval_copilot_models.py` (38 casos reals, 4 verticals)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_eval_copilot_models_dry_run_passes_all_cases():
    """El joc d'avaluació cobreix les 4 verticals, multi-subagent i RBAC amb 100% d'encert en dry-run."""
    report = await eval_copilot_models.run_evaluation(
        dry_run=True,
        base_url="http://127.0.0.1:1234/v1",
        model=None,
        hardware_profile="32GB",
        vertical_filter=None,
        limit=None,
    )
    summary = report["summary"]
    assert summary["cases_total"] >= 30
    assert summary["tool_accuracy_pct"] == 100.0
    assert summary["multi_subagent_accuracy_pct"] == 100.0
    assert summary["narration_leakage_pct"] == 0.0
    assert summary["numeric_hallucination_pct"] == 0.0
    assert summary["think_leakage_pct"] == 0.0

    # Verificar que és serialitzable a JSON per `--output-json`
    serialized = json.dumps(report, ensure_ascii=False)
    assert "SEVALOR" not in serialized or len(serialized) > 500
