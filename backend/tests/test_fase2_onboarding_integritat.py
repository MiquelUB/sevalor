import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.config import settings
from app.models.models import Empresa, Usuari


@pytest.mark.asyncio
async def test_onboarding_persistencia_100_i_fitxers_inicials_disc(
    async_client: AsyncClient, db_session, tmp_path: Path
):
    """Comprova que l'alta desa adreça, DNI del Boss separat, nom/cognoms compostos, telèfon null si buit, i escriu empresa.json, boss.json i system_prompt.txt al disc."""
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
        "disc_dur_url": str(disc_client),
        "node_ia_url": str(disc_client),
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
    assert tenant["domini_complet"] == f"{slug}.projectexinoxano.cat"

    emp_db = (
        await db_session.execute(select(Empresa).where(Empresa.id == uuid.UUID(tenant["id"])))
    ).scalar_one()
    boss_db = (
        await db_session.execute(select(Usuari).where(Usuari.empresa_id == emp_db.id))
    ).scalar_one()

    assert emp_db.adreca == "Avinguda Generalitat 120, Tortosa"
    assert emp_db.pla_subscripcio == "ENTERPRISE"
    assert emp_db.disc_dur_url == str(disc_client)
    assert emp_db.vault_token is not None
    assert emp_db.vault_token.startswith("svlt_")
    assert emp_db.telegram_webhook_secret is None
    assert tenant["vault_token"] == emp_db.vault_token
    assert boss_db.nif == dni_boss
    assert boss_db.nif != emp_db.nif
    assert boss_db.nom == "Joan Josep"
    assert boss_db.cognoms == "Rovira i Soler"
    assert boss_db.telefon is None

    # Verificar que les carpetes del disc contenen les dades des del minut 1
    fitxa_empresa = disc_client / "11_configuracio_i_backups/identitat_camaleo/empresa.json"
    fitxa_boss = disc_client / f"08_flota_i_operaris/operaris/{boss_db.id}.json"
    prompt_file = disc_client / "09_copilot_ia/prompt_sistema/system_prompt.txt"

    assert fitxa_empresa.is_file()
    assert fitxa_boss.is_file()
    assert prompt_file.is_file()
    assert json.loads(fitxa_empresa.read_text("utf-8"))["nif"] == cif_empresa
    assert prompt_file.read_text("utf-8") == "Ets el Copilot tècnic de Sevalormante."
