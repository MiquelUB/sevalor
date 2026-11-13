"""Tests d'integració i auditoria Zero-Mock per al PLA 3 (/superadmin telemetry, Celery cues i Whisper INT8)."""

import hashlib
import os
import shutil
import sys
import types
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from app.core.config import settings
from app.main import app
from app.models.models import AlertaSeguretat, Empresa, RegistreBaixaCertificat
from app.services.whisper_service import transcribe_field_audio_local_int8
from app.workers.celery_app import celery_app


def _make_superadmin_headers() -> dict[str, str]:
    emp_id = str(uuid.uuid4())
    payload = {
        "sub": str(uuid.uuid4()),
        "rol": "SUPERADMIN",
        "empresa_id": emp_id,
        "totp_activat": True,
        "ip_allowlist": ["*"],
        "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return {"Authorization": f"Bearer {token}", "X-Empresa-ID": emp_id}


def _make_role_headers(empresa_id: str, rol: str) -> dict[str, str]:
    payload = {
        "sub": str(uuid.uuid4()),
        "rol": rol,
        "empresa_id": empresa_id,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return {"Authorization": f"Bearer {token}", "X-Empresa-ID": empresa_id}


@pytest.mark.asyncio
async def test_pla3_superadmin_telemetry_schema_aillat_i_taules(db_session):
    """Spec 022 (RF-03, RF-06): Verifica que les taules de telemetria viuen a l'esquema superadmin_telemetry."""
    res_tel = await db_session.execute(
        text(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'superadmin_telemetry'
            """
        )
    )
    tel_tables = {row[0] for row in res_tel.all()}
    assert {
        "traces_error",
        "telemetria_sistema",
        "alertes_seguretat",
        "registre_baixes_certificats",
    }.issubset(tel_tables)

    res_pub = await db_session.execute(
        text(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name IN ('telemetria_sistema', 'alertes_seguretat', 'registre_baixes_certificats')
            """
        )
    )
    assert res_pub.all() == []


def test_pla3_celery_tres_cues_prioritat_configurades():
    """Spec 024 (RF-01): Verifica les 3 cues de prioritat (queue_alerts, queue_documents, queue_periodic) i rutes."""
    queues_by_name = {q.name: q for q in celery_app.conf.task_queues}
    assert {"queue_alerts", "queue_documents", "queue_periodic"}.issubset(queues_by_name.keys())
    assert celery_app.conf.task_default_queue == "queue_documents"
    assert celery_app.conf.task_default_exchange == "sevalor"

    assert (
        celery_app.conf.task_routes["comptabilitat.processar_tiquet_ocr_a_gestio"]["queue"]
        == "queue_documents"
    )
    assert (
        celery_app.conf.task_routes["workers.transcriure_audio_whisper_local"]["queue"]
        == "queue_documents"
    )
    assert (
        celery_app.conf.task_routes["workers.enviar_alerta_telegram_critica"]["queue"]
        == "queue_alerts"
    )
    assert (
        celery_app.conf.task_routes["workers.executar_backup_setmanal_tenant"]["queue"]
        == "queue_periodic"
    )
    assert (
        celery_app.conf.task_routes["comptabilitat.processar_outbox_aeat"]["queue"]
        == "queue_periodic"
    )

    registered = set(celery_app.tasks.keys())
    assert "comptabilitat.processar_tiquet_ocr_a_gestio" in registered
    assert "workers.transcriure_audio_whisper_local" in registered
    assert "workers.enviar_alerta_telegram_critica" in registered
    assert "workers.executar_backup_setmanal_tenant" in registered
    assert "comptabilitat.processar_outbox_aeat" in registered


@pytest.mark.asyncio
async def test_pla3_whisper_int8_cpu_saturacio_alerta_i_rbac_telemetria(
    db_session, tmp_path, monkeypatch
):
    """Spec 012/022/024: faster-whisper INT8 registra alerta GROGA a superadmin_telemetry si CPU > 90% i bloqueja rols no-SUPERADMIN."""

    class _Seg:
        def __init__(self, text_val: str) -> None:
            self.text = text_val

    class _Info:
        language = "ca"

    class _FakeWhisperModel:
        def __init__(self, model_size: str, *, device: str, compute_type: str, cpu_threads: int):
            assert model_size == "small"
            assert device == "cpu"
            assert compute_type == "int8"
            assert cpu_threads == 4

        def transcribe(self, audio_path: str, **_kwargs):
            return ([_Seg("Bombeig revisat"), _Seg("vàlvula OK")], _Info())

    fake_fw = types.ModuleType("faster_whisper")
    fake_fw.WhisperModel = _FakeWhisperModel  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "faster_whisper", fake_fw)
    monkeypatch.setattr("app.services.whisper_service._WHISPER_MODEL", None)

    audio_file = tmp_path / "nota_camp.ogg"
    audio_file.write_bytes(b"OggS\x00\x02dummy")

    res_whisper = await transcribe_field_audio_local_int8(
        str(audio_file),
        db=db_session,
        cpu_percent_override=94.5,
    )
    assert res_whisper["text"] == "Bombeig revisat vàlvula OK"
    assert res_whisper["language"] == "ca"
    assert res_whisper["quantization"] == "INT8_LOCAL_CPU"
    assert res_whisper["cpu_percent"] == pytest.approx(94.5)

    alerta = (
        await db_session.execute(
            select(AlertaSeguretat)
            .where(AlertaSeguretat.tipus == "SATURACIO_CPU_WHISPER_INT8")
            .order_by(AlertaSeguretat.creat_a.desc())
            .limit(1)
        )
    ).scalar_one()
    assert alerta.gravetat == "GROGA"
    assert "94.5%" in alerta.detall

    superadmin_headers = _make_superadmin_headers()
    boss_headers = _make_role_headers(str(uuid.uuid4()), "BOSS")
    operari_headers = _make_role_headers(str(uuid.uuid4()), "OPERARI")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Zero-Trust RBAC: BOSS i OPERARI no poden consultar ni capturar telemetria Superadmin
        for denied in (boss_headers, operari_headers):
            r_denied = await ac.get("/api/v1/superadmin/telemetria/alertes", headers=denied)
            assert r_denied.status_code == 403

        # SUPERADMIN llegeix l'alerta i la resol
        r_list = await ac.get(
            "/api/v1/superadmin/telemetria/alertes?resolta=false",
            headers=superadmin_headers,
        )
        assert r_list.status_code == 200, r_list.text
        ids_obertes = {item["id"] for item in r_list.json()}
        assert str(alerta.id) in ids_obertes

        r_resoldre = await ac.patch(
            f"/api/v1/superadmin/telemetria/alertes/{alerta.id}/resoldre",
            headers=superadmin_headers,
        )
        assert r_resoldre.status_code == 200, r_resoldre.text
        assert r_resoldre.json()["resolta"] is True

        # Captura i lectura d'instantània de TelemetriaSistema
        r_snap = await ac.post(
            "/api/v1/superadmin/telemetria/snapshots",
            headers=superadmin_headers,
        )
        assert r_snap.status_code == 201, r_snap.text
        snap_id = r_snap.json()["id"]

        r_snaps = await ac.get(
            "/api/v1/superadmin/telemetria/snapshots?limit=5",
            headers=superadmin_headers,
        )
        assert r_snaps.status_code == 200
        assert snap_id in {s["id"] for s in r_snaps.json()}


@pytest.mark.asyncio
async def test_pla3_baixa_certificat_telemetry_i_cache_busting_sw(db_session, tmp_path):
    """Spec 022 (RF-06) + PWA Cache Busting: baixa registra nif_hash a superadmin_telemetry i sw.js purga obsolets."""
    tenant_id = uuid.uuid4()
    nif_plain = f"B{str(tenant_id.int)[:8]}"
    emp = Empresa(
        id=tenant_id,
        nom=f"Baixa Telemetry {str(tenant_id)[:6]}",
        nif=nif_plain,
        subdomini=f"baixa-{str(tenant_id)[:8]}",
        disc_dur_url=str(tmp_path / f"disc_{tenant_id}"),
        pla_subscripcio="BASIC",
        estat_pagament="ACTIU",
    )
    db_session.add(emp)
    await db_session.flush()

    superadmin_headers = _make_superadmin_headers()

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            r_dest = await ac.post(
                f"/api/v1/superadmin/tenants/{tenant_id}/destruccio",
                headers=superadmin_headers,
            )
            assert r_dest.status_code == 200, r_dest.text

            expected_hash = hashlib.sha256(nif_plain.encode("utf-8")).hexdigest()
            reg = (
                await db_session.execute(
                    select(RegistreBaixaCertificat).where(
                        RegistreBaixaCertificat.tenant_id == tenant_id
                    )
                )
            ).scalar_one()
            assert reg.nif_hash == expected_hash
            assert reg.estat == "ELIMINAT"

            r_baixes = await ac.get(
                "/api/v1/superadmin/telemetria/baixes-certificats?limit=20",
                headers=superadmin_headers,
            )
            assert r_baixes.status_code == 200, r_baixes.text
            assert str(tenant_id) in {b["tenant_id"] for b in r_baixes.json()}
    finally:
        tmp_cert_dir = f"/tmp/sevalor_docs/{tenant_id}"
        if os.path.exists(tmp_cert_dir):
            shutil.rmtree(tmp_cert_dir, ignore_errors=True)

    # Verificació de directiva Cache Busting al Service Worker i Next.js config
    repo_root = Path(__file__).resolve().parents[2]
    sw_text = (repo_root / "pwa" / "public" / "sw.js").read_text(encoding="utf-8")
    assert 'const CACHE_VERSION = "v5"' in sw_text
    assert "purgeObsoleteCaches" in sw_text
    assert "CACHE_BUST" in sw_text
    assert "SKIP_WAITING" in sw_text

    next_cfg = (repo_root / "pwa" / "next.config.js").read_text(encoding="utf-8")
    assert "source: '/sw.js'" in next_cfg
    assert "no-store, no-cache, must-revalidate" in next_cfg
