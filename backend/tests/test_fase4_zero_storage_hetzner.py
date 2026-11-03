"""Tests de Fase 4: Validació de Desacoblament de Superadmin i Purga Zero-Storage a Hetzner."""

import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.services.sovereign_storage import MAPA_CARPETES_CLIENT
from app.workers.tasks import buidar_buffer_diari_cap_a_disc_client


@pytest.mark.asyncio
async def test_verificar_disc_dur_superadmin_autoinit_21_carpetes(
    async_client: AsyncClient, tmp_path: Path
):
    """Comprova que l'endpoint de Superadmin /verificar-disc-dur inicialitza físicament les 21 carpetes oficials."""
    sa_token = jwt.encode(
        {
            "sub": "00000000-0000-0000-0000-000000000000",
            "rol": "SUPERADMIN",
            "empresa_id": None,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
            "totp_activat": True,
            "ip_allowlist": ["*"],
        },
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    sa_headers = {"Authorization": f"Bearer {sa_token}"}

    disc_client = tmp_path / "disc_verificacio_superadmin"

    payload = {"disc_dur_url": str(disc_client)}
    resp = await async_client.post(
        "/superadmin/tenants/verificar-disc-dur",
        json=payload,
        headers=sa_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "OK"
    assert data["carpetes_creades"] == len(set(MAPA_CARPETES_CLIENT.values()))

    # Comprovar físicament que les carpetes de negoci, copilot i protocols existeixen
    assert (disc_client / "01_clients" / "fitxes").is_dir()
    assert (disc_client / "03_magatzem" / "articles_i_estoc").is_dir()
    assert (disc_client / "04_factures" / "emeses_verifactu_pdf").is_dir()
    assert (disc_client / "05_planols" / "arxius_base").is_dir()
    assert (disc_client / "09_copilot_ia" / "prompt_sistema").is_dir()
    assert (disc_client / "10_protocols_i_manuals" / "procediments_interns").is_dir()


def test_tasca_celery_purga_buffer_zero_storage(tmp_path: Path):
    """Comprova que la tasca Celery buidar_buffer_diari_cap_a_disc_client purga els buffers residuals d'Hetzner."""
    temp_dir = Path("/tmp/sevalor_factures_temp")
    temp_dir.mkdir(parents=True, exist_ok=True)

    dummy_file_1 = temp_dir / "FACTURA_TEMP_TEST_1.pdf"
    dummy_file_2 = temp_dir / "FACTURA_TEMP_TEST_2.pdf"
    dummy_file_1.write_bytes(b"%PDF-1.4 dummy buffer hetzner")
    dummy_file_2.write_bytes(b"%PDF-1.4 dummy buffer hetzner 2")

    assert dummy_file_1.exists()
    assert dummy_file_2.exists()

    resultat = buidar_buffer_diari_cap_a_disc_client()
    assert resultat["purged_files"] >= 2
    assert resultat["purged_bytes"] > 0

    assert not dummy_file_1.exists()
    assert not dummy_file_2.exists()


@pytest.mark.asyncio
async def test_desacoblament_disc_dur_sense_copilot_ia(
    async_client: AsyncClient, admin_session, tmp_path: Path
):
    """Comprova que el disc dur sobirà està sempre actiu per a un tenant fins i tot si té copilot_ia desmarcat."""
    sa_token = jwt.encode(
        {
            "sub": "00000000-0000-0000-0000-000000000000",
            "rol": "SUPERADMIN",
            "empresa_id": None,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
            "totp_activat": True,
            "ip_allowlist": ["*"],
        },
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    sa_headers = {"Authorization": f"Bearer {sa_token}"}

    disc_client = tmp_path / "disc_tenant_sense_ia"
    slug_rnd = f"trad-{uuid.uuid4().hex[:4]}"
    tenant_payload = {
        "rao_social": "Tècnics Tradicionals SL",
        "nif": f"B{uuid.uuid4().int % 10000000:07d}T",
        "slug": slug_rnd,
        "subdomini": slug_rnd,
        "vertical": "CAMP",
        "pla_subscripcio": "STARTER",
        "disc_dur_url": str(disc_client),
        "boss_nif": "12345678B",
        "boss_nom": "Pere",
        "boss_cognoms": "Vila",
        "boss_email": f"pere_{uuid.uuid4().hex[:4]}@tradicionals.cat",
        "feature_flags": {
            "copilot_ia": False,
            "gps_tracking": True,
        },
    }

    resp = await async_client.post(
        "/superadmin/tenants/onboarding",
        json=tenant_payload,
        headers=sa_headers,
    )
    assert resp.status_code == 201, resp.text
    emp_data = resp.json()["tenant"]

    # Verificar que disc_dur_url es manté i no s'esborra
    assert emp_data["disc_dur_url"] == str(disc_client)
    # I que les 21 carpetes al disc estan inicialitzades
    assert (disc_client / "01_clients" / "fitxes").is_dir()
    assert (disc_client / "05_planols" / "arxius_base").is_dir()
