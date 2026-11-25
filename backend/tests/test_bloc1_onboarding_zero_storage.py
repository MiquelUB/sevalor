"""Tests d'integració del BLOC 1: Onboarding Zero-Storage, Blind HMAC Auth, Disc Superadmin i Túnel WSS Únic.

Normativa estricta (Auditoria_i_Normativa_Tests_Backend.md & ADR-001):
- PostgreSQL 16 real amb SAVEPOINT (zero mocks de BD).
- `SovereignWssAgent` reals (`scripts/client_vault_agent.py`) sobre `WS /api/v1/vault-tunnel/connect`.
- Verificació estricta Zero-PII a Hetzner i persistència física real als discs d'Empresa (38 carpetes) i Superadmin (20 carpetes).
"""

import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.config import settings
from app.core.db import set_tenant_context
from app.core.security import blind_email, blind_nif, blind_telefon
from app.main import app
from app.models.models import Empresa, Usuari
from app.services.sovereign_storage import (
    CARPETES_SUPERADMIN,
    MAPA_CARPETES_CLIENT,
    SovereignStorageGateway,
)
from app.services.vault_tunnel import (
    SUPERADMIN_TARGET_KEY,
    empresa_target_key,
    vault_tunnel_broker,
)
from tests.wss_test_helpers import (
    LiveUvicornServer,
    RunningWssAgent,
    live_empresa_wss_context,
    live_superadmin_wss_context,
    start_local_llm_server,
    wait_for,
)


def _make_superadmin_headers() -> dict[str, str]:
    token = jwt.encode(
        {
            "sub": "00000000-0000-0000-0000-000000000000",
            "rol": "SUPERADMIN",
            "empresa_id": None,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
            "totp_activat": True,
            "ip_allowlist": ["testclient", "127.0.0.1", "localhost", "*"],
        },
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_bloc1_inicialitzar_disc_superadmin_endpoint(tmp_path: Path, monkeypatch) -> None:
    """Verifica POST /superadmin/tenants/disc-superadmin/inicialitzar creant les 20 carpetes via Túnel WSS."""
    sup_a = tmp_path / "sup_primary"
    sup_b = tmp_path / "sup_backup"
    sa_secret = f"svlt_sa_{uuid.uuid4().hex[:12]}"
    monkeypatch.delenv("SUPERADMIN_VAULT_URL", raising=False)
    monkeypatch.setenv("SUPERADMIN_VAULT_SECRET", sa_secret)

    sa_headers = _make_superadmin_headers()
    boss_headers = {
        "Authorization": f"Bearer {jwt.encode({'sub': str(uuid.uuid4()), 'rol': 'BOSS', 'empresa_id': str(uuid.uuid4()), 'exp': datetime.now(timezone.utc) + timedelta(minutes=10)}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)}"
    }

    async with live_superadmin_wss_context(sa_secret, sup_a, disk_b=sup_b):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            r_forbidden = await ac.post(
                "/api/v1/superadmin/tenants/disc-superadmin/inicialitzar",
                headers=boss_headers,
            )
            assert r_forbidden.status_code == 403

            r_ok = await ac.post(
                "/api/v1/superadmin/tenants/disc-superadmin/inicialitzar",
                headers=sa_headers,
            )
            assert r_ok.status_code == 200, r_ok.text
            data = r_ok.json()
            assert data["status"] == "OK"
            assert data["role"] == "SUPERADMIN"
            assert data["mode"] == "WSS_TUNNEL"
            assert data["carpetes_count"] == 20
            for carpeta in CARPETES_SUPERADMIN:
                assert (sup_a / carpeta).is_dir()
                assert (sup_b / carpeta).is_dir()


@pytest.mark.asyncio
async def test_bloc1_onboarding_bloqueja_tunel_caigut_o_buit(
    db_session, tmp_path: Path, monkeypatch
) -> None:
    """ADR-001 (WSS-only):
    1) Rebutja explícitament URLs HTTP/HTTPS entrants (422) sense crear registres a Postgres.
    2) Crear empresa ACTIU sense URL externa genera automàticament `wss-tunnel://<id>`,
       retorna `comanda_install_wss` i encua fitxes xifrades `SVENC1:` (QUEUED) sense bloquejar l'alta.
    """
    sa_headers = _make_superadmin_headers()

    base_payload = {
        "nif": f"B{uuid.uuid4().int % 90000000 + 10000000}",
        "rao_social": "Fals Túnel SL",
        "vertical": "ElectricPro",
        "pla_subscripcio": "PRO",
        "estat_inicial": "ACTIU",
        "quota_operaris": 5,
        "boss_nif": f"{uuid.uuid4().int % 90000000 + 10000000}Z",
        "boss_nom": "Pau",
        "boss_cognoms": "Serra",
        "agent_prompt_system": "Copilot especialista en baixa tensió.",
        "feature_flags": {"copilot_ia": True},
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. URL HTTP entrant -> 422 ADR-001 i 0 registres a Postgres
        slug_http = f"httpbad-{uuid.uuid4().hex[:6]}"
        r_http = await ac.post(
            "/api/v1/superadmin/tenants/onboarding",
            json={
                **base_payload,
                "slug": slug_http,
                "subdomini": slug_http,
                "boss_email": f"pau1@{slug_http}.cat",
                "disc_dur_url": "http://127.0.0.1:9001",
            },
            headers=sa_headers,
        )
        assert r_http.status_code == 422, r_http.text
        assert (
            await db_session.execute(select(Empresa).where(Empresa.subdomini == slug_http))
        ).scalars().first() is None

        # 2. Alta ACTIU sense URL externa -> 201 CREATED amb wss-tunnel://<id> + comanda 1-clic + cua SVENC1:
        slug_ok = f"wssok-{uuid.uuid4().hex[:6]}"
        r_ok = await ac.post(
            "/api/v1/superadmin/tenants/onboarding",
            json={
                **base_payload,
                "slug": slug_ok,
                "subdomini": slug_ok,
                "boss_email": f"pau2@{slug_ok}.cat",
            },
            headers=sa_headers,
        )
        assert r_ok.status_code == 201, r_ok.text
        body = r_ok.json()
        emp_id = body["tenant"]["id"]
        assert body["tenant"]["disc_dur_url"] == f"wss-tunnel://{emp_id}"
        assert body["tenant"]["node_ia_url"] == f"wss-tunnel://{emp_id}"
        assert body["vault_sync"]["status"] == "QUEUED"
        assert "--role EMPRESA" in body["comanda_install_wss"]


@pytest.mark.asyncio
async def test_bloc1_onboarding_complet_i_zero_storage_hetzner(
    db_session, tmp_path: Path, monkeypatch
) -> None:
    """Verifica onboarding end-to-end Zero-Storage 100% sobre WSS:
    - 38 carpetes + fitxes reals al disc de l'Empresa.
    - 20 carpetes + fitxa B2B/tarifes + factura Veri*factu PDF al disc del Superadmin.
    - Zero PII / tarifes / prompt en clar a Hetzner PostgreSQL.
    - Login real via POST /api/v1/auth/login usant índex cec HMAC-SHA256.
    """
    lm_srv, lm_url, _ = start_local_llm_server(model_name="qwen2.5-coder-7b-instruct")

    emp_a = tmp_path / "disc_emp_a"
    emp_b = tmp_path / "disc_emp_b"
    sup_a = tmp_path / "disc_sup_a"
    sup_b = tmp_path / "disc_sup_b"
    token_emp = f"svlt_emp_{uuid.uuid4().hex[:12]}"
    token_sup = f"svlt_sup_{uuid.uuid4().hex[:12]}"

    monkeypatch.delenv("SUPERADMIN_VAULT_URL", raising=False)
    monkeypatch.setenv("SUPERADMIN_VAULT_SECRET", token_sup)

    sa_headers = _make_superadmin_headers()
    slug = f"electrotec-{uuid.uuid4().hex[:6]}"
    cif_real = f"B{uuid.uuid4().int % 90000000 + 10000000}"
    boss_nif_real = f"{uuid.uuid4().int % 90000000 + 10000000}Z"
    boss_email_real = f"gerencia.{slug}@electrotec-sobira.cat"
    boss_tel_real = "+34611223344"
    rao_social_real = "Electrotec Manteniments Sobirans S.L."
    adreca_real = "Polígon Industrial Campredó, Nau 14, Tortosa"
    prompt_real = "Ets el Copilot REBT dedicat d'Electrotec."

    emp_agent: RunningWssAgent | None = None
    emp_id_created: uuid.UUID | None = None

    try:
        async with LiveUvicornServer() as server:
            async with RunningWssAgent(
                server.http_url,
                role="SUPERADMIN",
                token=token_sup,
                disk_a=sup_a,
                disk_b=sup_b,
            ):
                await wait_for(lambda: vault_tunnel_broker.is_online(SUPERADMIN_TARGET_KEY))

                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                    r_init_sup = await ac.post(
                        "/api/v1/superadmin/tenants/disc-superadmin/inicialitzar",
                        headers=sa_headers,
                    )
                    assert r_init_sup.status_code == 200

                    r_onb = await ac.post(
                        "/api/v1/superadmin/tenants/onboarding",
                        json={
                            "rao_social": rao_social_real,
                            "nif": cif_real,
                            "adreca": adreca_real,
                            "slug": slug,
                            "subdomini": slug,
                            "vertical": "ElectricPro",
                            "pla_subscripcio": "PRO",
                            "estat_inicial": "ACTIU",
                            "quota_operaris": 12,
                            "tarifa_llicencia_base": 180.0,
                            "tarifa_per_operari": 19.5,
                            "tarifa_config_ia": 250.0,
                            "equips_ia_venuts": [
                                {"concepte": "MiniPC GPU", "unitats": 1, "preu_unitari": 790.0, "modalitat": "VENDA"}
                            ],
                            "notes_crm": "Client prioritari amb instal·lació local.",
                            "vault_token": token_emp,
                            "agent_prompt_system": prompt_real,
                            "boss_nif": boss_nif_real,
                            "boss_nom": "Montserrat",
                            "boss_cognoms": "Ferrer i Vallès",
                            "boss_email": boss_email_real,
                            "boss_telefon": boss_tel_real,
                            "feature_flags": {
                                "copilot_ia": True,
                                "flota_avancada": True,
                                "planols_tecnics": True,
                                "telegram_bot": True,
                            },
                        },
                        headers=sa_headers,
                    )
                    assert r_onb.status_code == 201, r_onb.text
                    onb_data = r_onb.json()
                    emp_id = uuid.UUID(onb_data["tenant"]["id"])
                    emp_id_created = emp_id
                    boss_id = uuid.UUID(onb_data["tenant"]["boss_usuari_id"])
                    assert onb_data["tenant"]["disc_dur_url"] == f"wss-tunnel://{emp_id}"

                    # Connectem l'agent WSS de l'empresa -> auto-creació 38 carpetes + drenatge fitxes inicials
                    emp_agent = RunningWssAgent(
                        server.http_url,
                        role="EMPRESA",
                        token=token_emp,
                        empresa_id=str(emp_id),
                        disk_a=emp_a,
                        disk_b=emp_b,
                        llm_url=lm_url,
                    ).start()
                    await wait_for(lambda: vault_tunnel_broker.is_online(empresa_target_key(emp_id)))
                    await wait_for(
                        lambda: (emp_a / "11_configuracio_i_backups/identitat_camaleo/empresa.json").is_file()
                        and (emp_a / f"08_flota_i_operaris/operaris/{boss_id}.json").is_file()
                        and (emp_a / "09_copilot_ia/prompt_sistema/copilot_profile.json").is_file(),
                        timeout=8.0,
                    )

                    # 1. Verificar ZERO PII i ZERO dades comercials en clar a PostgreSQL (Hetzner)
                    await set_tenant_context(db_session, None, is_superadmin=True)
                    emp_db = (await db_session.execute(select(Empresa).where(Empresa.id == emp_id))).scalar_one()
                    boss_db = (await db_session.execute(select(Usuari).where(Usuari.id == boss_id))).scalar_one()

                    assert emp_db.nom == f"Tenant-{slug}"
                    assert rao_social_real not in emp_db.nom
                    assert emp_db.nif == blind_nif(cif_real)
                    assert emp_db.nif != cif_real
                    assert emp_db.adreca is None
                    assert float(emp_db.tarifa_llicencia_base) == 0.0
                    assert float(emp_db.tarifa_per_operari) == 0.0
                    assert float(emp_db.tarifa_config_ia) == 0.0
                    assert emp_db.equips_ia_venuts == []
                    assert emp_db.notes_crm is None
                    assert emp_db.agent_prompt_system is None

                    assert boss_db.nom == "Usuari"
                    assert boss_db.cognoms == ""
                    assert boss_db.nif == blind_nif(boss_nif_real)
                    assert boss_db.email == blind_email(boss_email_real)
                    assert boss_db.telefon == blind_telefon(boss_tel_real)

                    # 2. Verificar les 38 carpetes + fitxes reals al disc de l'Empresa
                    for carpeta in MAPA_CARPETES_CLIENT.values():
                        assert (emp_a / carpeta).is_dir()
                    empresa_json = json.loads(
                        (emp_a / "11_configuracio_i_backups/identitat_camaleo/empresa.json").read_text("utf-8")
                    )
                    boss_json = json.loads(
                        (emp_a / f"08_flota_i_operaris/operaris/{boss_id}.json").read_text("utf-8")
                    )
                    assert empresa_json["nom"] == rao_social_real
                    assert empresa_json["nif"] == cif_real
                    assert empresa_json["adreca"] == adreca_real
                    assert boss_json["nom"] == "Montserrat"
                    assert boss_json["email"] == boss_email_real
                    profile_json = json.loads(
                        (emp_a / "09_copilot_ia/prompt_sistema/copilot_profile.json").read_text("utf-8")
                    )
                    assert profile_json["system_prompt"] == prompt_real
                    assert not (emp_a / "09_copilot_ia/prompt_sistema/system_prompt.txt").exists()

                    # 3. Verificar fitxa comercial + llicències al Disc del Superadmin
                    fitxa_sa = json.loads(
                        (sup_a / f"01_tenants_b2b/fitxes_empreses/{emp_id}.json").read_text("utf-8")
                    )
                    llic_sa = json.loads(
                        (sup_a / f"01_tenants_b2b/llicencies_i_contractes/{emp_id}.json").read_text("utf-8")
                    )
                    assert fitxa_sa["rao_social"] == rao_social_real
                    assert fitxa_sa["nif"] == cif_real
                    assert fitxa_sa["boss_email"] == boss_email_real
                    assert float(llic_sa["tarifa_llicencia_base"]) == 180.0
                    assert float(llic_sa["tarifa_per_operari"]) == 19.5

                    # 4. Verificar que GET /superadmin/tenants/{id} retorna dades comercials enriquides + tunnel_online=True
                    r_det = await ac.get(f"/api/v1/superadmin/tenants/{emp_id}", headers=sa_headers)
                    assert r_det.status_code == 200
                    assert r_det.json()["rao_social"] == rao_social_real
                    assert r_det.json()["tarifa_llicencia_base"] == 180.0
                    assert r_det.json()["tunnel_online"] is True

                    # 5. Establir contrasenya i autenticar el BOSS amb el seu email REAL tot i índex cec a Hetzner
                    r_pwd = await ac.post(
                        f"/api/v1/superadmin/tenants/{emp_id}/set-boss-password",
                        json={"password": "ClauSegura2026!"},
                        headers=sa_headers,
                    )
                    assert r_pwd.status_code == 200, r_pwd.text
                    assert boss_email_real in r_pwd.json()["missatge"]

                    r_login = await ac.post(
                        "/api/v1/auth/login",
                        json={"email": boss_email_real, "password": "ClauSegura2026!"},
                    )
                    assert r_login.status_code == 200, r_login.text
                    login_json = r_login.json()
                    assert login_json["empresa_id"] == str(emp_id)
                    assert login_json["rol"] == "BOSS"
                    assert "access_token" in login_json

                    # 6. Verificar Facturació B2B Veri*factu desada al Disc de Superadmin (JSON + PDF)
                    r_pref = await ac.post(
                        "/api/v1/superadmin/crm/prefactures",
                        json={
                            "empresa_id": str(emp_id),
                            "periode_facturacio": "2026-11",
                            "import_onboarding": 180.0,
                            "num_operaris": 12,
                            "preu_per_operari": 19.5,
                        },
                        headers=sa_headers,
                    )
                    assert r_pref.status_code == 201, r_pref.text
                    pref_id = r_pref.json()["id"]
                    assert r_pref.json()["client_nom_snapshot"] == rao_social_real

                    r_emit = await ac.post(
                        f"/api/v1/superadmin/crm/prefactures/{pref_id}/verificar-i-emetre",
                        headers=sa_headers,
                    )
                    assert r_emit.status_code == 200, r_emit.text
                    assert r_emit.json()["pdf_path"].startswith("superadmin-vault://")
                    assert (sup_a / f"02_facturacio_saas/factures_b2b_pdf/factura_saas_{pref_id}.pdf").is_file()

                    r_pdf = await ac.get(f"/api/v1/superadmin/crm/factures/{pref_id}/pdf", headers=sa_headers)
                    assert r_pdf.status_code == 200
                    assert r_pdf.content.startswith(b"%PDF")
    finally:
        if emp_agent is not None:
            await emp_agent.stop()
        if emp_id_created is not None:
            await vault_tunnel_broker.disconnect(empresa_target_key(emp_id_created))
        await vault_tunnel_broker.disconnect(SUPERADMIN_TARGET_KEY)
        lm_srv.shutdown()
        lm_srv.server_close()


@pytest.mark.asyncio
async def test_bloc1_cua_transit_xifrada_i_autopurga_en_drenar(
    db_session, tmp_path: Path, monkeypatch
) -> None:
    """Quan l'agent WSS de l'empresa està offline: cua xifrada SVENC1 a Hetzner + auto-purga en tornar online."""
    transit_dir = tmp_path / "transit_queue_bloc1"
    transit_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("SOVEREIGN_TRANSIT_QUEUE_DIR", str(transit_dir))
    monkeypatch.setattr(SovereignStorageGateway, "TRANSIT_QUEUE_DIR", transit_dir)

    emp_a = tmp_path / "disc_transit_a"
    emp_b = tmp_path / "disc_transit_b"
    token_emp = f"svlt_transit_{uuid.uuid4().hex[:10]}"

    sa_headers = _make_superadmin_headers()
    slug = f"transit-{uuid.uuid4().hex[:6]}"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r_onb = await ac.post(
            "/api/v1/superadmin/tenants/onboarding",
            json={
                "rao_social": "Transit Logistics Test SL",
                "nif": f"B{uuid.uuid4().int % 90000000 + 10000000}",
                "slug": slug,
                "subdomini": slug,
                "vertical": "CampoPro",
                "pla_subscripcio": "STARTER",
                "estat_inicial": "ACTIU",
                "vault_token": token_emp,
                "boss_nif": f"{uuid.uuid4().int % 90000000 + 10000000}K",
                "boss_nom": "Oriol",
                "boss_cognoms": "Mas",
                "boss_email": f"oriol@{slug}.cat",
                "feature_flags": {"copilot_ia": False},
            },
            headers=sa_headers,
        )
        assert r_onb.status_code == 201, r_onb.text
        emp_id = uuid.UUID(r_onb.json()["tenant"]["id"])

    # 1. Amb el túnel WSS APAGAT -> escriure entitat s'ha d'encuar xifrada SVENC1 a transit_dir
    res_path = await SovereignStorageGateway.desar_entitat_json(
        db_session,
        emp_id,
        "clients",
        "cli_off_1",
        {"id": "cli_off_1", "nom": "Client Secret Offline", "nif": "B11111111"},
    )
    assert res_path.startswith("transit://")
    emp_transit_dir = transit_dir / str(emp_id)
    bin_files = list(emp_transit_dir.glob("*.bin"))
    assert len(bin_files) >= 1
    assert any(b"Client Secret Offline" not in f.read_bytes() and f.read_bytes().startswith(b"SVENC1:") for f in bin_files)
    assert not (emp_a / "01_clients/fitxes/cli_off_1.json").exists()

    # 2. Encendre l'agent WSS real de l'empresa -> auto-drenatge i auto-purga a Hetzner
    async with live_empresa_wss_context(emp_id, token_emp, emp_a, disk_b=emp_b, start_llm=False):
        dest_cli = emp_a / "01_clients/fitxes/cli_off_1.json"
        await wait_for(lambda: dest_cli.is_file(), timeout=8.0)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            r_drain = await ac.post(
                f"/api/v1/superadmin/tenants/{emp_id}/inicialitzar-disc",
                headers=sa_headers,
            )
            assert r_drain.status_code == 200, r_drain.text
            assert r_drain.json()["status"] == "SYNCED"
            assert r_drain.json()["transit_drain"]["pendents"] == 0

        assert json.loads(dest_cli.read_text("utf-8"))["nom"] == "Client Secret Offline"
        assert not emp_transit_dir.exists() or not any(emp_transit_dir.iterdir())
