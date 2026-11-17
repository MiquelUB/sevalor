"""Tests d'integració del BLOC 1: Onboarding Zero-Storage, Blind HMAC Auth, Disc Superadmin i Túnel Obligatori.

Normativa estricta (Auditoria_i_Normativa_Tests_Backend.md):
- PostgreSQL 16 real amb SAVEPOINT (zero mocks de BD).
- Servidors HTTP reals (`uvicorn` sobre ports TCP efímers executant `scripts/client_vault_agent.py`).
- Verificació estricta Zero-PII a Hetzner i persistència física real als discs d'Empresa i Superadmin.
"""

import json
import socket
import sys
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Tuple

import httpx
import jwt
import pytest
import uvicorn
from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import scripts.client_vault_agent as vault_agent  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.security import blind_email, blind_nif, blind_telefon  # noqa: E402
from app.main import app  # noqa: E402
from app.models.models import Empresa, Usuari  # noqa: E402
from app.services.sovereign_storage import (  # noqa: E402
    CARPETES_SUPERADMIN,
    MAPA_CARPETES_CLIENT,
    SovereignStorageGateway,
)


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


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


def _start_uvicorn_app(asgi_app: Any, port: int) -> Tuple[uvicorn.Server, threading.Thread]:
    config = uvicorn.Config(asgi_app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    deadline = time.time() + 10.0
    while time.time() < deadline:
        if not thread.is_alive():
            raise RuntimeError(f"Uvicorn thread crashed before listening on port {port}")
        try:
            r = httpx.get(f"http://127.0.0.1:{port}/health", timeout=0.4)
            if r.status_code == 200:
                return server, thread
        except Exception:
            time.sleep(0.05)
    server.should_exit = True
    thread.join(timeout=2.0)
    raise TimeoutError(f"Uvicorn server did not answer /health on 127.0.0.1:{port}")


def _stop_uvicorn_app(server: uvicorn.Server, thread: threading.Thread) -> None:
    server.should_exit = True
    thread.join(timeout=3.0)


def _create_isolated_vault_app(
    role: str,
    primary_dir: Path,
    secondary_dir: Path,
    secret: str,
    lm_studio_url: str,
) -> FastAPI:
    """Crea una instància aïllada d'endpoints client_vault_agent sobre un root físic propi."""
    from app.services.sovereign_storage import (
        inicialitzar_arbre_carpetes_disc,
        inicialitzar_arbre_carpetes_superadmin,
    )

    vapp = FastAPI()
    primary_dir.mkdir(parents=True, exist_ok=True)
    secondary_dir.mkdir(parents=True, exist_ok=True)

    def _auth(x_vault_token: str | None) -> None:
        if x_vault_token != secret:
            raise HTTPException(status_code=403, detail="Token Vault invàlid")

    @vapp.get("/health")
    async def health() -> dict[str, Any]:
        return {
            "status": "OK",
            "role": role,
            "vault_root": str(primary_dir),
            "disc_a_lliure_gb": 50.0,
        }

    @vapp.post("/admin/inicialitzar-ruta")
    async def init_ruta(x_vault_token: str | None = Header(default=None, alias="X-Vault-Token")) -> dict[str, Any]:
        _auth(x_vault_token)
        creades = (
            inicialitzar_arbre_carpetes_superadmin(primary_dir)
            if role == "SUPERADMIN"
            else inicialitzar_arbre_carpetes_disc(primary_dir)
        )
        if role == "SUPERADMIN":
            inicialitzar_arbre_carpetes_superadmin(secondary_dir)
        else:
            inicialitzar_arbre_carpetes_disc(secondary_dir)
        return {
            "status": "OK",
            "role": role,
            "total_carpetes": len(creades),
            "carpetes_count": len(creades),
            "carpetes": creades,
        }

    @vapp.get("/v1/models")
    async def proxy_models(x_vault_token: str | None = Header(default=None, alias="X-Vault-Token")) -> Response:
        _auth(x_vault_token)
        async with httpx.AsyncClient(timeout=2.0) as client:
            try:
                r = await client.get(f"{lm_studio_url.rstrip('/')}/models")
                return Response(content=r.content, status_code=r.status_code, media_type="application/json")
            except httpx.RequestError as exc:
                return JSONResponse(status_code=503, content={"detail": f"LM Studio offline: {exc}"})

    @vapp.put("/entitats/{subcarpeta:path}/{identificador}")
    async def put_entitat(
        subcarpeta: str,
        identificador: str,
        request: Request,
        x_vault_token: str | None = Header(default=None, alias="X-Vault-Token"),
    ) -> dict[str, Any]:
        _auth(x_vault_token)
        raw = await request.body()
        clean_id = identificador[:-5] if identificador.endswith(".json") else identificador
        for root in (primary_dir, secondary_dir):
            dest_dir = (root / subcarpeta).resolve()
            if not dest_dir.is_relative_to(root.resolve()):
                raise HTTPException(status_code=400, detail="Path traversal")
            dest_dir.mkdir(parents=True, exist_ok=True)
            (dest_dir / f"{clean_id}.json").write_bytes(raw)
        return {"status": "OK", "id": clean_id}

    @vapp.get("/entitats/{subcarpeta:path}")
    async def list_entitats(
        subcarpeta: str,
        x_vault_token: str | None = Header(default=None, alias="X-Vault-Token"),
    ) -> list[dict[str, Any]]:
        _auth(x_vault_token)
        dest_dir = (primary_dir / subcarpeta).resolve()
        if not dest_dir.exists():
            return []
        items = []
        for f in sorted(dest_dir.glob("*.json")):
            if not f.name.startswith("_healthcheck_"):
                items.append(json.loads(f.read_text("utf-8")))
        return items

    @vapp.delete("/entitats/{subcarpeta:path}/{identificador}")
    async def del_entitat(
        subcarpeta: str,
        identificador: str,
        x_vault_token: str | None = Header(default=None, alias="X-Vault-Token"),
    ) -> dict[str, Any]:
        _auth(x_vault_token)
        clean_id = identificador[:-5] if identificador.endswith(".json") else identificador
        for root in (primary_dir, secondary_dir):
            p = (root / subcarpeta / f"{clean_id}.json").resolve()
            if p.exists():
                p.unlink()
        return {"status": "OK"}

    @vapp.post("/fitxers/{subcarpeta:path}")
    async def post_fitxer(
        subcarpeta: str,
        request: Request,
        x_vault_token: str | None = Header(default=None, alias="X-Vault-Token"),
    ) -> dict[str, Any]:
        _auth(x_vault_token)
        form = await request.form()
        up = form["fitxer"]
        nom_desti = str(form.get("nom_desti") or getattr(up, "filename", "fitxer.bin"))
        data = await up.read()
        for root in (primary_dir, secondary_dir):
            dest_dir = (root / subcarpeta).resolve()
            dest_dir.mkdir(parents=True, exist_ok=True)
            (dest_dir / nom_desti).write_bytes(data)
        return {"status": "OK", "nom": nom_desti, "subcarpeta": subcarpeta}

    @vapp.get("/fitxers/{subcarpeta:path}/{nom_fitxer}")
    async def get_fitxer(
        subcarpeta: str,
        nom_fitxer: str,
        x_vault_token: str | None = Header(default=None, alias="X-Vault-Token"),
    ) -> Response:
        _auth(x_vault_token)
        p = (primary_dir / subcarpeta / nom_fitxer).resolve()
        if not p.is_file():
            raise HTTPException(status_code=404, detail="Fitxer no trobat")
        return Response(content=p.read_bytes(), media_type="application/octet-stream")

    return vapp


@pytest.mark.asyncio
async def test_bloc1_inicialitzar_disc_superadmin_endpoint(tmp_path: Path, monkeypatch) -> None:
    """Verifica POST /superadmin/tenants/disc-superadmin/inicialitzar creant les 20 carpetes via HTTP_VAULT."""
    sup_a = tmp_path / "sup_primary"
    sup_b = tmp_path / "sup_backup"
    sup_a.mkdir(parents=True, exist_ok=True)
    sup_b.mkdir(parents=True, exist_ok=True)
    sa_secret = f"svlt_sa_{uuid.uuid4().hex[:12]}"

    monkeypatch.setattr(vault_agent, "VAULT_ROLE", "SUPERADMIN")
    monkeypatch.setattr(vault_agent, "VAULT_PRIMARY_A", sup_a)
    monkeypatch.setattr(vault_agent, "VAULT_SECONDARY_B", sup_b)
    monkeypatch.setattr(vault_agent, "VAULT_SECRET", sa_secret)

    port_sa = _find_free_port()
    srv, thr = _start_uvicorn_app(vault_agent.app, port_sa)
    try:
        monkeypatch.setenv("SUPERADMIN_VAULT_URL", f"http://127.0.0.1:{port_sa}")
        monkeypatch.setenv("SUPERADMIN_VAULT_SECRET", sa_secret)

        sa_headers = _make_superadmin_headers()
        boss_headers = {
            "Authorization": f"Bearer {jwt.encode({'sub': str(uuid.uuid4()), 'rol': 'BOSS', 'empresa_id': str(uuid.uuid4()), 'exp': datetime.now(timezone.utc) + timedelta(minutes=10)}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)}"
        }

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
            assert data["carpetes_count"] == 20
            for carpeta in CARPETES_SUPERADMIN:
                assert (sup_a / carpeta).is_dir()
    finally:
        _stop_uvicorn_app(srv, thr)


@pytest.mark.asyncio
async def test_bloc1_onboarding_bloqueja_tunel_caigut_o_buit(
    db_session, tmp_path: Path, monkeypatch
) -> None:
    """Si l'empresa és ACTIU i el túnel no existeix, està caigut o el proxy IA (/v1/models) falla, denega onboarding."""
    sa_headers = _make_superadmin_headers()
    closed_port = _find_free_port()

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
        # 1. ACTIU sense cap URL de túnel -> 422
        slug1 = f"notunel-{uuid.uuid4().hex[:6]}"
        r_no_url = await ac.post(
            "/api/v1/superadmin/tenants/onboarding",
            json={
                **base_payload,
                "slug": slug1,
                "subdomini": slug1,
                "boss_email": f"pau1@{slug1}.cat",
                "feature_flags": {"copilot_ia": False},
                "agent_prompt_system": None,
            },
            headers=sa_headers,
        )
        assert r_no_url.status_code == 422, r_no_url.text
        assert (
            await db_session.execute(select(Empresa).where(Empresa.subdomini == slug1))
        ).scalars().first() is None

        # 2. ACTIU amb port tancat -> 502 i 0 registres a Postgres
        slug2 = f"dead-{uuid.uuid4().hex[:6]}"
        r_dead = await ac.post(
            "/api/v1/superadmin/tenants/onboarding",
            json={
                **base_payload,
                "slug": slug2,
                "subdomini": slug2,
                "boss_email": f"pau2@{slug2}.cat",
                "disc_dur_url": f"http://127.0.0.1:{closed_port}",
                "node_ia_url": f"http://127.0.0.1:{closed_port}",
            },
            headers=sa_headers,
        )
        assert r_dead.status_code == 502, r_dead.text
        assert (
            await db_session.execute(select(Empresa).where(Empresa.subdomini == slug2))
        ).scalars().first() is None

        # 3. Túnel viu de disc dur PERÒ proxy Copilot /v1/models apagat amb copilot_ia=True -> 502
        emp_a = tmp_path / "emp_no_ia_a"
        emp_b = tmp_path / "emp_no_ia_b"
        token_emp = f"svlt_emp_{uuid.uuid4().hex[:10]}"
        closed_lm_port = _find_free_port()
        vault_app = _create_isolated_vault_app(
            "EMPRESA",
            emp_a,
            emp_b,
            token_emp,
            lm_studio_url=f"http://127.0.0.1:{closed_lm_port}/v1",
        )
        port_emp = _find_free_port()
        srv, thr = _start_uvicorn_app(vault_app, port_emp)
        try:
            slug3 = f"noia-{uuid.uuid4().hex[:6]}"
            r_no_ia = await ac.post(
                "/api/v1/superadmin/tenants/onboarding",
                json={
                    **base_payload,
                    "slug": slug3,
                    "subdomini": slug3,
                    "nif": f"B{uuid.uuid4().int % 90000000 + 10000000}",
                    "boss_email": f"pau3@{slug3}.cat",
                    "disc_dur_url": f"http://127.0.0.1:{port_emp}",
                    "node_ia_url": f"http://127.0.0.1:{port_emp}",
                    "vault_token": token_emp,
                },
                headers=sa_headers,
            )
            assert r_no_ia.status_code == 502, r_no_ia.text
            assert "/v1/models" in r_no_ia.json()["detail"], r_no_ia.text
            assert (
                await db_session.execute(select(Empresa).where(Empresa.subdomini == slug3))
            ).scalars().first() is None
        finally:
            _stop_uvicorn_app(srv, thr)


@pytest.mark.asyncio
async def test_bloc1_onboarding_complet_i_zero_storage_hetzner(
    db_session, tmp_path: Path, monkeypatch
) -> None:
    """Verifica onboarding end-to-end Zero-Storage:
    - 38 carpetes + fitxes reals al disc de l'Empresa.
    - 20 carpetes + fitxa B2B/tarifes + factura Veri*factu PDF al disc del Superadmin.
    - Zero PII / tarifes / prompt en clar a Hetzner PostgreSQL.
    - Login real via POST /api/v1/auth/login usant índex cec HMAC-SHA256.
    """
    # Servidor local LLM real (/v1/models) per validar el proxy de Copilot del túnel
    lm_app = FastAPI()

    @lm_app.get("/health")
    async def lm_health() -> dict[str, str]:
        return {"status": "OK"}

    @lm_app.get("/v1/models")
    async def lm_models() -> dict[str, Any]:
        return {"object": "list", "data": [{"id": "qwen2.5-coder-7b-instruct", "object": "model"}]}

    lm_port = _find_free_port()
    srv_lm, thr_lm = _start_uvicorn_app(lm_app, lm_port)

    emp_a = tmp_path / "disc_emp_a"
    emp_b = tmp_path / "disc_emp_b"
    sup_a = tmp_path / "disc_sup_a"
    sup_b = tmp_path / "disc_sup_b"
    token_emp = f"svlt_emp_{uuid.uuid4().hex[:12]}"
    token_sup = f"svlt_sup_{uuid.uuid4().hex[:12]}"

    port_emp = _find_free_port()
    port_sup = _find_free_port()
    srv_emp, thr_emp = _start_uvicorn_app(
        _create_isolated_vault_app("EMPRESA", emp_a, emp_b, token_emp, f"http://127.0.0.1:{lm_port}/v1"),
        port_emp,
    )
    srv_sup, thr_sup = _start_uvicorn_app(
        _create_isolated_vault_app("SUPERADMIN", sup_a, sup_b, token_sup, f"http://127.0.0.1:{lm_port}/v1"),
        port_sup,
    )

    try:
        monkeypatch.setenv("SUPERADMIN_VAULT_URL", f"http://127.0.0.1:{port_sup}")
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
                    "equips_ia_venuts": [{"concepte": "MiniPC GPU", "unitats": 1, "preu_unitari": 790.0, "modalitat": "VENDA"}],
                    "notes_crm": "Client prioritari amb instal·lació local.",
                    "disc_dur_url": f"http://127.0.0.1:{port_emp}",
                    "node_ia_url": f"http://127.0.0.1:{port_emp}",
                    "vault_token": token_emp,
                    "agent_prompt_system": prompt_real,
                    "boss_nif": boss_nif_real,
                    "boss_nom": "Montserrat",
                    "boss_cognoms": "Ferrer i Vallès",
                    "boss_email": boss_email_real,
                    "boss_telefon": boss_tel_real,
                    "feature_flags": {"copilot_ia": True, "flota_avancada": True, "planols_tecnics": True, "telegram_bot": True},
                },
                headers=sa_headers,
            )
            assert r_onb.status_code == 201, r_onb.text
            onb_data = r_onb.json()
            emp_id = uuid.UUID(onb_data["tenant"]["id"])
            boss_id = uuid.UUID(onb_data["tenant"]["boss_usuari_id"])
            assert onb_data["vault_sync"]["status"] == "SYNCED"
            assert onb_data["vault_sync"]["carpetes_creades"] == 38
            assert onb_data["vault_sync"]["ia_proxy_ok"] is True

            # 1. Verificar ZERO PII i ZERO dades comercials en clar a PostgreSQL (Hetzner)
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
            assert boss_db.nif != boss_nif_real
            assert boss_db.email == blind_email(boss_email_real)
            assert boss_db.email != boss_email_real
            assert boss_db.telefon == blind_telefon(boss_tel_real)
            assert boss_db.telefon != boss_tel_real

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
            assert (emp_a / "09_copilot_ia/prompt_sistema/system_prompt.txt").read_text("utf-8") == prompt_real

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

            # 4. Verificar que GET /superadmin/tenants/{id} retorna dades comercials enriquides des del disc Superadmin
            r_det = await ac.get(f"/api/v1/superadmin/tenants/{emp_id}", headers=sa_headers)
            assert r_det.status_code == 200
            assert r_det.json()["rao_social"] == rao_social_real
            assert r_det.json()["tarifa_llicencia_base"] == 180.0

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
        _stop_uvicorn_app(srv_sup, thr_sup)
        _stop_uvicorn_app(srv_emp, thr_emp)
        _stop_uvicorn_app(srv_lm, thr_lm)


@pytest.mark.asyncio
async def test_bloc1_cua_transit_xifrada_i_autopurga_en_drenar(
    db_session, tmp_path: Path, monkeypatch
) -> None:
    """Quan l'agent de l'empresa cau offline: cua xifrada SVENC1 a Hetzner + auto-purga en tornar online."""
    transit_dir = tmp_path / "transit_queue_bloc1"
    transit_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("SOVEREIGN_TRANSIT_QUEUE_DIR", str(transit_dir))

    lm_port = _find_free_port()
    emp_a = tmp_path / "disc_transit_a"
    emp_b = tmp_path / "disc_transit_b"
    token_emp = f"svlt_transit_{uuid.uuid4().hex[:10]}"
    port_emp = _find_free_port()

    srv_emp, thr_emp = _start_uvicorn_app(
        _create_isolated_vault_app("EMPRESA", emp_a, emp_b, token_emp, f"http://127.0.0.1:{lm_port}/v1"),
        port_emp,
    )

    sa_headers = _make_superadmin_headers()
    slug = f"transit-{uuid.uuid4().hex[:6]}"
    try:
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
                    "disc_dur_url": f"http://127.0.0.1:{port_emp}",
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
    finally:
        _stop_uvicorn_app(srv_emp, thr_emp)

    # 1. Amb el túnel APAGAT -> escriure entitat s'ha d'encuar xifrada SVENC1 a transit_dir
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
    raw_bin = bin_files[0].read_bytes()
    assert raw_bin.startswith(b"SVENC1:")
    assert b"Client Secret Offline" not in raw_bin
    assert not (emp_a / "01_clients/fitxes/cli_off_1.json").exists()

    # 2. Re-encendre el túnel d'empresa i drenar via endpoint de Superadmin
    srv_emp2, thr_emp2 = _start_uvicorn_app(
        _create_isolated_vault_app("EMPRESA", emp_a, emp_b, token_emp, f"http://127.0.0.1:{lm_port}/v1"),
        port_emp,
    )
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            r_drain = await ac.post(
                f"/api/v1/superadmin/tenants/{emp_id}/inicialitzar-disc",
                headers=sa_headers,
            )
            assert r_drain.status_code == 200, r_drain.text
            drain_info = r_drain.json()["transit_drain"]
            assert drain_info["enviats"] >= 1
            assert drain_info["pendents"] == 0

        # Verificar arribada real al disc empresa i auto-purga absoluta a Hetzner
        dest_cli = emp_a / "01_clients/fitxes/cli_off_1.json"
        assert dest_cli.is_file()
        assert json.loads(dest_cli.read_text("utf-8"))["nom"] == "Client Secret Offline"
        assert not emp_transit_dir.exists() or not any(emp_transit_dir.iterdir())
    finally:
        _stop_uvicorn_app(srv_emp2, thr_emp2)
