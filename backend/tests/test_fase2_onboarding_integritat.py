import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.config import settings
from app.core.db import set_tenant_context
from app.core.security import blind_email, blind_nif
from app.models.models import Empresa, Usuari
from app.services.vault_tunnel import empresa_target_key, vault_tunnel_broker
from tests.wss_test_helpers import LiveUvicornServer, RunningWssAgent, wait_for


@pytest.mark.asyncio
async def test_onboarding_persistencia_100_i_fitxers_inicials_disc(
    async_client: AsyncClient, db_session, tmp_path: Path
):
    """Comprova que l'alta desa adreça, DNI del Boss separat, nom/cognoms compostos, telèfon null si buit, i escriu empresa.json, boss.json i system_prompt.txt al disc via Túnel Invers Natiu WSS."""
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
    disc_client = tmp_path / f"vault_sevalormante_{uuid.uuid4().hex[:6]}"
    slug = f"sevalormante-{uuid.uuid4().hex[:6]}"
    cif_empresa = f"B{uuid.uuid4().int % 10000000:07d}A"
    dni_boss = f"{uuid.uuid4().int % 100000000:08d}Z"

    payload = {
        "rao_social": "Sevalormante Serveis Tècnics SL",
        "nif": cif_empresa,
        "adreca": "Avinguda Generalitat 120, Tortosa",
        "slug": slug,
        "subdomini": slug,
        "vertical": "Manteniment Integral",
        "pla_subscripcio": "ENTERPRISE",
        "agent_prompt_system": "Ets el Copilot tècnic de Sevalormante.",
        "boss_nif": dni_boss,
        "boss_nom": "Joan Josep",
        "boss_cognoms": "Rovira i Soler",
        "boss_email": f"jjrovira_{slug}@sevalormante.cat",
        "boss_telefon": None,
        "feature_flags": {"copilot_ia": True, "flota_avancada": True},
    }

    resp = await async_client.post(
        "/api/v1/superadmin/tenants/onboarding",
        json=payload,
        headers={"Authorization": f"Bearer {sa_token}"},
    )
    assert resp.status_code == 201, resp.text
    tenant = resp.json()["tenant"]
    emp_uuid = uuid.UUID(tenant["id"])
    assert tenant["domini_complet"] == f"{slug}.projectexinoxano.cat"
    assert tenant["disc_dur_url"] == f"wss-tunnel://{emp_uuid}"
    assert tenant["node_ia_url"] == f"wss-tunnel://{emp_uuid}"

    await set_tenant_context(db_session, None, is_superadmin=True)
    emp_db = (
        await db_session.execute(select(Empresa).where(Empresa.id == emp_uuid))
    ).scalar_one()
    boss_db = (
        await db_session.execute(select(Usuari).where(Usuari.empresa_id == emp_db.id))
    ).scalar_one()

    # Zero-Storage Hetzner: PostgreSQL només conserva pseudònims i índexs cecs
    assert emp_db.nom == f"Tenant-{slug}"
    assert emp_db.adreca is None
    assert emp_db.nif == blind_nif(cif_empresa)
    assert emp_db.agent_prompt_system is None
    assert emp_db.pla_subscripcio == "ENTERPRISE"
    assert emp_db.disc_dur_url == f"wss-tunnel://{emp_uuid}"
    assert emp_db.vault_token is not None
    assert emp_db.vault_token.startswith("svlt_")
    assert emp_db.telegram_webhook_secret is None
    assert tenant["vault_token"] == emp_db.vault_token
    assert boss_db.nif == blind_nif(dni_boss)
    assert boss_db.nif != emp_db.nif
    assert boss_db.nom == "Usuari"
    assert boss_db.cognoms == ""
    assert boss_db.email == blind_email(f"jjrovira_{slug}@sevalormante.cat")
    assert boss_db.telefon is None

    # En connectar el PC del client via Túnel WSS, es creen les 38 carpetes i es drenen empresa.json, boss.json i system_prompt.txt
    fitxa_empresa = disc_client / "11_configuracio_i_backups/identitat_camaleo/empresa.json"
    fitxa_boss = disc_client / f"08_flota_i_operaris/operaris/{boss_db.id}.json"
    prompt_file = disc_client / "09_copilot_ia/prompt_sistema/system_prompt.txt"

    try:
        async with LiveUvicornServer() as server:
            async with RunningWssAgent(
                server.http_url,
                role="EMPRESA",
                token=emp_db.vault_token,
                empresa_id=str(emp_uuid),
                disk_a=disc_client,
            ):
                await wait_for(
                    lambda: fitxa_empresa.is_file() and fitxa_boss.is_file() and prompt_file.is_file(),
                    timeout=8.0,
                )
    finally:
        await vault_tunnel_broker.disconnect(empresa_target_key(emp_uuid))

    assert fitxa_empresa.is_file()
    assert fitxa_boss.is_file()
    assert prompt_file.is_file()
    emp_disk_data = json.loads(fitxa_empresa.read_text("utf-8"))
    boss_disk_data = json.loads(fitxa_boss.read_text("utf-8"))
    assert emp_disk_data["nif"] == cif_empresa
    assert emp_disk_data["adreca"] == "Avinguda Generalitat 120, Tortosa"
    assert boss_disk_data["nif"] == dni_boss
    assert boss_disk_data["nom"] == "Joan Josep"
    assert boss_disk_data["cognoms"] == "Rovira i Soler"
    assert prompt_file.read_text("utf-8") == "Ets el Copilot tècnic de Sevalormante."
