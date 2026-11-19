import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from httpx import AsyncClient

from app.core.config import settings


@pytest.fixture(scope="function")
def headers_enginyer():
    empresa_id = str(uuid.uuid4())
    payload = {
        "sub": str(uuid.uuid4()),
        "rol": "ENGINYER",
        "empresa_id": empresa_id,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return {
        "Authorization": f"Bearer {token}",
        "X-Empresa-ID": empresa_id,
    }

@pytest.mark.asyncio
async def test_configuracio_empresa_boss_only(async_client: AsyncClient, headers_enginyer):
    payload = {"nom": "Nova Empresa SA"}

    response = await async_client.put(
        "/gestio/configuracio/empresa",
        json=payload,
        headers=headers_enginyer
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_configuracio_node_ia_permisos_i_actualitzacio(
    async_client: AsyncClient, headers, headers_enginyer, admin_session
):
    from sqlalchemy import select

    from app.models.models import Empresa

    # 1. Crear l'empresa per al Boss de prova
    empresa_id_boss = uuid.UUID(headers["X-Empresa-ID"])
    res = await admin_session.execute(select(Empresa).where(Empresa.id == empresa_id_boss))
    empresa = res.scalar_one_or_none()
    if not empresa:
        empresa = Empresa(
            id=empresa_id_boss,
            nom="Empresa Sobirana Test",
            nif=f"B{empresa_id_boss.hex[:8].upper()}",
            vertical="ELECTRICPRO",
            node_ia_actiu=False,
            node_ia_url=None,
        )
        admin_session.add(empresa)
        await admin_session.commit()

    # 2. Intent d'actualització per part d'ENGINYER -> 403 Veto
    resp_enginyer = await async_client.put(
        "/gestio/configuracio/node-ia",
        json={"node_ia_url": "http://192.168.1.100:1234/v1", "node_ia_actiu": True},
        headers=headers_enginyer,
    )
    assert resp_enginyer.status_code == 403

    # 3. Estat inicial del node -> SENSE_ORDINADOR_DEDICAT
    resp_estat_inicial = await async_client.get(
        "/gestio/copilot/estat-node",
        headers=headers,
    )
    assert resp_estat_inicial.status_code == 200
    dades_inicials = resp_estat_inicial.json()
    assert dades_inicials["node_actiu"] is False
    assert dades_inicials["estat"] == "SENSE_ORDINADOR_DEDICAT"

    # 4. Actualització autoritzada pel Boss
    resp_boss = await async_client.put(
        "/gestio/configuracio/node-ia",
        json={
            "node_ia_url": "https://ia.empresa-sobirana.cat/v1",
            "node_ia_actiu": True,
            "agent_prompt_system": "Prioritza sempre les normatives REBT ITC-BT-28.",
        },
        headers=headers,
    )
    assert resp_boss.status_code == 200
    assert resp_boss.json()["status"] == "OK"

    # 5. Consulta de paràmetres de node-ia desada
    resp_get = await async_client.get(
        "/gestio/configuracio/node-ia",
        headers=headers,
    )
    assert resp_get.status_code == 200
    dades_node = resp_get.json()
    assert dades_node["node_ia_url"] == "https://ia.empresa-sobirana.cat/v1"
    assert dades_node["node_ia_actiu"] is True
    assert dades_node["te_ordinador_dedicat"] is True
    assert "REBT" in dades_node["agent_prompt_system"]

    # 6. Estat del Copilot reflectint l'ordinador dedicat actiu
    resp_estat_actiu = await async_client.get(
        "/gestio/copilot/estat-node",
        headers=headers,
    )
    assert resp_estat_actiu.status_code == 200
    dades_actiu = resp_estat_actiu.json()
    assert dades_actiu["node_actiu"] is True
    assert dades_actiu["estat"] == "ORDINADOR_DEDICAT_ACTIU"
    assert dades_actiu["proveidor"] == "Ordinador Local Dedicat de l'Empresa"


@pytest.mark.asyncio
async def test_crear_usuari_administratiu_i_login_amb_2fa(
    async_client: AsyncClient, headers, admin_session
):
    import re

    from sqlalchemy import select

    from app.models.models import Empresa

    empresa_id_boss = uuid.UUID(headers["X-Empresa-ID"])
    subdomini = f"sevalormante-{empresa_id_boss.hex[:6]}"
    res = await admin_session.execute(select(Empresa).where(Empresa.id == empresa_id_boss))
    empresa = res.scalar_one_or_none()
    if not empresa:
        empresa = Empresa(
            id=empresa_id_boss,
            nom="Sevalor Manteniments S.L.",
            nif=f"B{empresa_id_boss.hex[:8].upper()}",
            subdomini=subdomini,
            estat_pagament="ACTIU",
        )
        admin_session.add(empresa)
        await admin_session.commit()

    # 1. Alta d'usuari SECRETARIA sota RLS (sense fallada per db.refresh després de db.commit)
    email_sec = f"coll-{empresa_id_boss.hex[:4]}@sevalormante.cat"
    resp_create = await async_client.post(
        "/gestio/configuracio/usuaris",
        json={
            "nom": "Marta",
            "cognoms": "Coll",
            "nif": f"4{empresa_id_boss.hex[:7].upper()}Z",
            "email": email_sec,
            "rol": "SECRETARIA",
        },
        headers=headers,
    )
    assert resp_create.status_code == 200, resp_create.text
    data_create = resp_create.json()
    assert data_create["status"] == "OK"
    pwd_temp = data_create["contrasenya_generada"]
    secret_2fa = data_create["secret_2fa"]

    # Verificar que secret_2fa és Base32 vàlid RFC 4648 (A-Z i 2-7)
    assert re.fullmatch(r"[A-Z2-7]{16}", secret_2fa), f"Secret Base32 invàlid: {secret_2fa}"

    # 2. Intent de crear el mateix email una segona vegada -> 409 Conflict
    resp_dup = await async_client.post(
        "/gestio/configuracio/usuaris",
        json={
            "nom": "Marta",
            "cognoms": "Coll 2",
            "nif": f"5{empresa_id_boss.hex[:7].upper()}A",
            "email": email_sec,
            "rol": "SECRETARIA",
        },
        headers=headers,
    )
    assert resp_dup.status_code == 409

    # 3. Login des del subdomini de l'empresa enganxant la Clau manual 2FA TOTP al camp totp_code
    resp_login = await async_client.post(
        "/auth/login",
        json={
            "email": email_sec,
            "password": f"  {pwd_temp}  ",  # amb espais accidentals de copia-enganxa
            "totp_code": secret_2fa,
        },
        headers={"Host": f"{subdomini}.projectexinoxano.cat"},
    )
    assert resp_login.status_code == 200, resp_login.text
    login_json = resp_login.json()
    assert login_json["rol"] == "SECRETARIA"
    assert login_json["empresa_id"] == str(empresa_id_boss)
    assert "access_token" in login_json

    # 4. Restablir contrasenya i tornar a iniciar sessió
    usuari_id = data_create["id"]
    resp_reset = await async_client.post(
        f"/gestio/configuracio/usuaris/{usuari_id}/reset-password",
        headers=headers,
    )
    assert resp_reset.status_code == 200, resp_reset.text
    nova_pwd = resp_reset.json()["contrasenya_generada"]

    resp_login_2 = await async_client.post(
        "/auth/login",
        json={
            "email": email_sec,
            "password": nova_pwd,
        },
        headers={"Host": f"{subdomini}.projectexinoxano.cat"},
    )
    assert resp_login_2.status_code == 200, resp_login_2.text


@pytest.mark.asyncio
async def test_copilot_diagnostic_503_i_provar_node_ia_amb_vault_i_feature_flags(
    async_client: AsyncClient, headers, admin_session
):
    """
    Reprodueix i valida la solució del bug de desincronització Configuració vs Copilot:
    1) GET/PUT /gestio/configuracio/node-ia exposen feature_copilot_ia i copilot_operatiu.
    2) POST /gestio/configuracio/node-ia/provar accepta URLs no desades al cos, suporta disc_dur_url
       i envia X-Vault-Token contra un servidor HTTP real (Zero Mock).
    3) POST /gestio/copilot/xat i GET /gestio/copilot/ia-status informen el motiu exacte quan
       manca feature_copilot_ia, node_ia_actiu o URL del túnel.
    """
    import json
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    from sqlalchemy import select

    from app.models.models import Empresa

    vault_secret = "svlt_probe_cfg_42"
    seen_tokens: list[str] = []

    class _LocalIaHandler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args) -> None:
            return

        def do_GET(self) -> None:
            tok = self.headers.get("X-Vault-Token") or ""
            seen_tokens.append(tok)
            if tok != vault_secret:
                self.send_response(403)
                self.end_headers()
                return
            if self.path.startswith("/v1/models"):
                body = json.dumps(
                    {
                        "data": [
                            {"id": "qwen2.5-vl-7b-instruct"},
                            {"id": "deepseek-coder-v2-lite-instruct"},
                            {"id": "text-embedding-nomic-embed-text-v1.5"},
                        ]
                    }
                ).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_response(404)
            self.end_headers()

    srv = ThreadingHTTPServer(("127.0.0.1", 0), _LocalIaHandler)
    port = srv.server_address[1]
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()

    try:
        empresa_id_boss = uuid.UUID(headers["X-Empresa-ID"])
        res = await admin_session.execute(select(Empresa).where(Empresa.id == empresa_id_boss))
        empresa = res.scalar_one_or_none()
        if not empresa:
            empresa = Empresa(
                id=empresa_id_boss,
                nom="Empresa Diagnostic Copilot SL",
                nif=f"B{empresa_id_boss.hex[:8].upper()}",
                subdomini=f"diagcop-{empresa_id_boss.hex[:6]}",
                estat_pagament="ACTIU",
                feature_copilot_ia=False,
                node_ia_actiu=True,
                node_ia_url=f"http://127.0.0.1:{port}",
                vault_token=vault_secret,
            )
            admin_session.add(empresa)
        else:
            empresa.feature_copilot_ia = False
            empresa.node_ia_actiu = True
            empresa.node_ia_url = f"http://127.0.0.1:{port}"
            empresa.vault_token = vault_secret
        await admin_session.commit()

        # 1. GET /node-ia ha d'exposar feature_copilot_ia=False i copilot_operatiu=False
        resp_get = await async_client.get("/gestio/configuracio/node-ia", headers=headers)
        assert resp_get.status_code == 200, resp_get.text
        dades_get = resp_get.json()
        assert dades_get["feature_copilot_ia"] is False
        assert dades_get["copilot_operatiu"] is False

        # 2. POST /node-ia/provar amb URL en cos (abans de desar) + vault_token -> OPERATIU + feature_copilot_ia=False
        resp_probe = await async_client.post(
            "/gestio/configuracio/node-ia/provar",
            json={"node_ia_url": f"http://127.0.0.1:{port}"},
            headers=headers,
        )
        assert resp_probe.status_code == 200, resp_probe.text
        probe_data = resp_probe.json()
        assert probe_data["estat"] == "OPERATIU"
        assert "qwen2.5-vl-7b-instruct" in probe_data["models_disponibles"]
        assert probe_data["feature_copilot_ia"] is False
        assert vault_secret in seen_tokens

        # 3. Copilot /xat ha d'indicar el motiu exacte: FEATURE_COPILOT_DESACTIVAT
        resp_xat_feat = await async_client.post(
            "/gestio/copilot/xat",
            json={"pregunta": "Hola"},
            headers=headers,
        )
        assert resp_xat_feat.status_code == 503, resp_xat_feat.text
        det_feat = resp_xat_feat.json()["detail"]
        assert det_feat["code"] == "COPILOT_DESACTIVAT"
        assert det_feat["motiu"] == "FEATURE_COPILOT_DESACTIVAT"

        # 4. /ia-status també exposa motiu=FEATURE_COPILOT_DESACTIVAT
        resp_st_feat = await async_client.get("/gestio/copilot/ia-status", headers=headers)
        assert resp_st_feat.status_code == 200, resp_st_feat.text
        assert resp_st_feat.json()["motiu"] == "FEATURE_COPILOT_DESACTIVAT"

        # 5. Activem feature_copilot_ia=True però node_ia_actiu=False -> motiu NODE_IA_INACTIU
        empresa.feature_copilot_ia = True
        empresa.node_ia_actiu = False
        await admin_session.commit()

        resp_xat_node = await async_client.post(
            "/gestio/copilot/xat",
            json={"pregunta": "Hola"},
            headers=headers,
        )
        assert resp_xat_node.status_code == 503, resp_xat_node.text
        det_node = resp_xat_node.json()["detail"]
        assert det_node["code"] == "COPILOT_DESACTIVAT"
        assert det_node["motiu"] == "NODE_IA_INACTIU"

        # 6. POST /node-ia/provar amb activar_si_operatiu=True (defecte) ha de persistir node_ia_actiu=True al backend!
        resp_probe_act = await async_client.post(
            "/gestio/configuracio/node-ia/provar",
            json={"node_ia_url": f"http://127.0.0.1:{port}"},
            headers=headers,
        )
        assert resp_probe_act.status_code == 200, resp_probe_act.text
        probe_act = resp_probe_act.json()
        assert probe_act["estat"] == "OPERATIU"
        assert probe_act["node_ia_actiu"] is True
        assert probe_act["copilot_operatiu"] is True

        # Verificar que GET /ia-status ara és ONLINE i selecciona model de xat (no embedding)
        resp_st_ok = await async_client.get("/gestio/copilot/ia-status", headers=headers)
        assert resp_st_ok.status_code == 200, resp_st_ok.text
        st_ok = resp_st_ok.json()
        assert st_ok["estat"] == "ONLINE"
        assert st_ok["node_ia_actiu"] is True
        assert "embed" not in st_ok["model_actiu"].lower()

        # 7. Token Vault erroni -> TOKEN_INVALID (no 500, no fals positiu)
        empresa.vault_token = "svlt_token_incorrecte_999"
        await admin_session.commit()
        resp_bad_tok = await async_client.post(
            "/gestio/configuracio/node-ia/provar",
            json={"node_ia_url": f"http://127.0.0.1:{port}"},
            headers=headers,
        )
        assert resp_bad_tok.status_code == 200, resp_bad_tok.text
        assert resp_bad_tok.json()["estat"] == "TOKEN_INVALID"

        # 8. Priorització de túnel públic HTTPS sobre loopback sense dependre de /.dockerenv
        from app.core.network_utils import get_candidate_ia_tunnel_urls, resoldre_url_tunel_ia

        pub_url = "https://node-client.projectexinoxano.cat"
        assert resoldre_url_tunel_ia("http://127.0.0.1:1234", pub_url) == pub_url
        cands = get_candidate_ia_tunnel_urls("http://127.0.0.1:1234", pub_url)
        assert cands[0] == pub_url
    finally:
        srv.shutdown()
        srv.server_close()


@pytest.mark.asyncio
async def test_aillament_exclusiu_dues_empreses_i_persistencia_triple(
    async_client: AsyncClient, admin_session, tmp_path, monkeypatch
):
    """
    Certifica l'arquitectura sobirana multi-tenant (1 Empresa = 1 Copilot exclusiu + 1 Disc Dur exclusiu):
    1) Alta de 2 empreses independents (Empresa A i Empresa B), cadascuna amb el seu propi servidor
       Vault/Copilot, el seu propi token i la seva pròpia carpeta física de disc dur.
    2) Persistència triple simultània a:
       - PostgreSQL (taula empreses)
       - Disc Superadmin (01_tenants_b2b/fitxes_empreses/<empresa_id>.json)
       - Disc Exclusiu de cada empresa (11_configuracio_i_backups/identitat_camaleo/empresa.json,
         boss.json i 09_copilot_ia/prompt_sistema/system_prompt.txt).
    3) Creació real d'arxius dins les carpetes corresponents sense cap barreja ni contaminació creuada.
    4) Autocuració automàtica des de la fitxa del Superadmin si es perden camps a SQL, mantenint la
       connexió activa quan es torna a entrar a la fitxa o a Configuració.
    """
    import json
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from pathlib import Path
    from urllib.parse import unquote

    from sqlalchemy import select

    from app.models.models import Empresa
    from app.services.sovereign_storage import (
        MAPA_CARPETES_CLIENT,
        SovereignStorageGateway,
        inicialitzar_arbre_carpetes_disc,
        inicialitzar_arbre_carpetes_superadmin,
    )

    superadmin_root = tmp_path / "Sevalor_Superadmin_docs"
    disc_empresa_a = tmp_path / "Sevalormante_docs_exclusiu_A"
    disc_empresa_b = tmp_path / "HydroNord_docs_exclusiu_B"

    inicialitzar_arbre_carpetes_superadmin(superadmin_root)
    inicialitzar_arbre_carpetes_disc(disc_empresa_a)
    inicialitzar_arbre_carpetes_disc(disc_empresa_b)

    # Redirigim el Disc Superadmin al tmp_path per aïllar el test
    monkeypatch.setenv("SUPERADMIN_VAULT_URL", str(superadmin_root))

    token_a = "svlt_exclusiu_empresa_a_111111"
    token_b = "svlt_exclusiu_empresa_b_222222"

    def _make_vault_and_ia_handler(root_dir: Path, expected_token: str, model_name: str):
        class _VaultIaHandler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args) -> None:
                return

            def _check_auth(self) -> bool:
                tok = self.headers.get("X-Vault-Token") or ""
                auth = self.headers.get("Authorization") or ""
                if tok == expected_token or auth == f"Bearer {expected_token}":
                    return True
                self.send_response(403)
                self.end_headers()
                return False

            def do_GET(self) -> None:
                if self.path.startswith("/health"):
                    body = json.dumps(
                        {
                            "status": "OK",
                            "service": "SEVALOR_CLIENT_VAULT_GATEWAY",
                            "role": "EMPRESA",
                            "primary_writable": True,
                            "carpetes_actives": len(MAPA_CARPETES_CLIENT),
                            "carpetes_count": len(MAPA_CARPETES_CLIENT),
                        }
                    ).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(body)
                    return

                if not self._check_auth():
                    return

                if self.path.startswith("/v1/models"):
                    body = json.dumps({"data": [{"id": model_name}]}).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(body)
                    return

                if self.path.startswith("/entitats/"):
                    parts = [unquote(p) for p in self.path.split("/") if p]
                    sub_or_item = "/".join(parts[1:])
                    dir_path = root_dir / sub_or_item
                    if dir_path.is_dir():
                        items = []
                        for fp in sorted(dir_path.glob("*.json")):
                            try:
                                items.append(json.loads(fp.read_text(encoding="utf-8")))
                            except Exception:
                                continue
                        body = json.dumps(items).encode("utf-8")
                        self.send_response(200)
                        self.send_header("Content-Type", "application/json")
                        self.end_headers()
                        self.wfile.write(body)
                        return
                    if len(parts) >= 3:
                        subcarpeta = "/".join(parts[1:-1])
                        ent_id = parts[-1]
                        fpath = root_dir / subcarpeta / f"{ent_id}.json"
                        if fpath.exists():
                            data = fpath.read_bytes()
                            self.send_response(200)
                            self.send_header("Content-Type", "application/json")
                            self.end_headers()
                            self.wfile.write(data)
                            return
                self.send_response(404)
                self.end_headers()

            def do_DELETE(self) -> None:
                if not self._check_auth():
                    return
                if self.path.startswith("/entitats/"):
                    parts = [unquote(p) for p in self.path.split("/") if p]
                    if len(parts) >= 3:
                        subcarpeta = "/".join(parts[1:-1])
                        ent_id = parts[-1]
                        fpath = root_dir / subcarpeta / f"{ent_id}.json"
                        fpath.unlink(missing_ok=True)
                        body = json.dumps({"status": "DELETED"}).encode("utf-8")
                        self.send_response(200)
                        self.send_header("Content-Type", "application/json")
                        self.end_headers()
                        self.wfile.write(body)
                        return
                self.send_response(404)
                self.end_headers()

            def do_PUT(self) -> None:
                if not self._check_auth():
                    return
                length = int(self.headers.get("Content-Length") or "0")
                raw = self.rfile.read(length) if length > 0 else b"{}"
                if self.path.startswith("/entitats/"):
                    parts = [unquote(p) for p in self.path.split("/") if p]
                    if len(parts) >= 3:
                        subcarpeta = "/".join(parts[1:-1])
                        ent_id = parts[-1]
                        target = root_dir / subcarpeta / f"{ent_id}.json"
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(raw)
                        body = json.dumps({"status": "SYNCED", "path": str(target)}).encode()
                        self.send_response(200)
                        self.send_header("Content-Type", "application/json")
                        self.end_headers()
                        self.wfile.write(body)
                        return
                self.send_response(404)
                self.end_headers()

            def do_POST(self) -> None:
                if not self._check_auth():
                    return
                length = int(self.headers.get("Content-Length") or "0")
                raw = self.rfile.read(length) if length > 0 else b""
                if self.path.startswith("/admin/inicialitzar-ruta"):
                    inicialitzar_arbre_carpetes_disc(root_dir)
                    body = json.dumps(
                        {
                            "status": "OK",
                            "mode": "HTTP_VAULT",
                            "carpetes_count": len(MAPA_CARPETES_CLIENT),
                        }
                    ).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(body)
                    return
                if self.path.startswith("/fitxers/"):
                    from email.parser import BytesParser
                    from email.policy import default as email_default_policy

                    parts = [unquote(p) for p in self.path.split("/") if p]
                    subcarpeta = "/".join(parts[1:])
                    ctype = self.headers.get("Content-Type") or ""
                    filename = "uploaded.bin"
                    file_bytes = raw
                    if "multipart/form-data" in ctype:
                        msg = BytesParser(policy=email_default_policy).parsebytes(
                            f"Content-Type: {ctype}\r\n\r\n".encode("utf-8") + raw
                        )
                        for part in msg.iter_parts():
                            cd = part.get("Content-Disposition") or ""
                            if 'name="nom_desti"' in cd:
                                val = part.get_payload(decode=True)
                                if val:
                                    filename = val.decode("utf-8").strip()
                            elif 'name="fitxer"' in cd:
                                fn = part.get_filename()
                                if fn and filename == "uploaded.bin":
                                    filename = fn
                                payload = part.get_payload(decode=True)
                                if payload is not None:
                                    file_bytes = payload
                    target = root_dir / subcarpeta / filename
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(file_bytes)
                    body = json.dumps({"status": "OK", "rel_path": f"{subcarpeta}/{filename}"}).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(body)
                    return
                self.send_response(404)
                self.end_headers()

        return _VaultIaHandler

    srv_a = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        _make_vault_and_ia_handler(disc_empresa_a, token_a, "qwen2.5-vl-7b-empresa-A"),
    )
    srv_b = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        _make_vault_and_ia_handler(disc_empresa_b, token_b, "deepseek-coder-v2-empresa-B"),
    )
    thread_a = threading.Thread(target=srv_a.serve_forever, daemon=True)
    thread_b = threading.Thread(target=srv_b.serve_forever, daemon=True)
    thread_a.start()
    thread_b.start()

    url_a = f"http://127.0.0.1:{srv_a.server_address[1]}"
    url_b = f"http://127.0.0.1:{srv_b.server_address[1]}"

    superadmin_jwt = jwt.encode(
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
    sa_headers = {"Authorization": f"Bearer {superadmin_jwt}"}

    try:
        # 1. Alta d'Empresa A i Empresa B via Onboarding amb discs i copilots 100% independents
        suf_a = uuid.uuid4().hex[:6]
        suf_b = uuid.uuid4().hex[:6]

        resp_onb_a = await async_client.post(
            "/superadmin/tenants/onboarding",
            json={
                "rao_social": f"Empresa Exclusiva A {suf_a} SL",
                "nif": f"B{suf_a.upper()}11",
                "subdomini": f"emp-a-{suf_a}",
                "vertical": "ELECTRICPRO",
                "pla_subscripcio": "PRO",
                "estat_inicial": "ACTIU",
                "node_ia_url": url_a,
                "disc_dur_url": url_a,
                "vault_token": token_a,
                "agent_prompt_system": "Prompt exclusiu Empresa A REBT.",
                "boss_nif": f"4{suf_a.upper()}1A",
                "boss_nom": "Arnau",
                "boss_cognoms": "Vila A",
                "boss_email": f"arnau.{suf_a}@empresaa.cat",
                "feature_flags": {
                    "copilot_ia": True,
                    "flota_avancada": True,
                    "planols_tecnics": True,
                    "telegram_bot": True,
                },
            },
            headers=sa_headers,
        )
        assert resp_onb_a.status_code == 201, resp_onb_a.text
        id_a = resp_onb_a.json()["tenant"]["id"]

        resp_onb_b = await async_client.post(
            "/superadmin/tenants/onboarding",
            json={
                "rao_social": f"Empresa Exclusiva B {suf_b} SL",
                "nif": f"B{suf_b.upper()}22",
                "subdomini": f"emp-b-{suf_b}",
                "vertical": "HYDROPRO",
                "pla_subscripcio": "PRO",
                "estat_inicial": "ACTIU",
                "node_ia_url": url_b,
                "disc_dur_url": url_b,
                "vault_token": token_b,
                "agent_prompt_system": "Prompt exclusiu Empresa B Aigua.",
                "boss_nif": f"5{suf_b.upper()}2B",
                "boss_nom": "Berta",
                "boss_cognoms": "Serra B",
                "boss_email": f"berta.{suf_b}@empresab.cat",
                "feature_flags": {
                    "copilot_ia": True,
                    "flota_avancada": True,
                    "planols_tecnics": True,
                    "telegram_bot": True,
                },
            },
            headers=sa_headers,
        )
        assert resp_onb_b.status_code == 201, resp_onb_b.text
        id_b = resp_onb_b.json()["tenant"]["id"]

        # 2. Verificació de Persistència Triple (Superadmin Disk + Disc Exclusiu A + Disc Exclusiu B)
        fitxa_sa_a = superadmin_root / "01_tenants_b2b/fitxes_empreses" / f"{id_a}.json"
        fitxa_sa_b = superadmin_root / "01_tenants_b2b/fitxes_empreses" / f"{id_b}.json"
        assert fitxa_sa_a.exists(), "La fitxa d'Empresa A ha de viure al disc de Superadmin"
        assert fitxa_sa_b.exists(), "La fitxa d'Empresa B ha de viure al disc de Superadmin"

        dades_sa_a = json.loads(fitxa_sa_a.read_text(encoding="utf-8"))
        dades_sa_b = json.loads(fitxa_sa_b.read_text(encoding="utf-8"))
        assert dades_sa_a["disc_dur_url"] == url_a
        assert dades_sa_a["vault_token"] == token_a
        assert dades_sa_a["node_ia_actiu"] is True
        assert dades_sa_b["disc_dur_url"] == url_b
        assert dades_sa_b["vault_token"] == token_b
        assert dades_sa_b["node_ia_actiu"] is True

        # Fitxers reals creats dins la carpeta exclusiva de cada empresa
        emp_json_a = disc_empresa_a / "11_configuracio_i_backups/identitat_camaleo/empresa.json"
        boss_json_a = disc_empresa_a / "11_configuracio_i_backups/identitat_camaleo/boss.json"
        prompt_txt_a = disc_empresa_a / "09_copilot_ia/prompt_sistema/system_prompt.txt"
        assert emp_json_a.exists()
        assert boss_json_a.exists()
        assert prompt_txt_a.exists()
        dades_disc_a = json.loads(emp_json_a.read_text(encoding="utf-8"))
        assert dades_disc_a["id"] == id_a
        assert dades_disc_a["disc_dur_url"] == url_a
        assert dades_disc_a["vault_token"] == token_a
        assert "Empresa A REBT" in prompt_txt_a.read_text(encoding="utf-8")

        emp_json_b = disc_empresa_b / "11_configuracio_i_backups/identitat_camaleo/empresa.json"
        boss_json_b = disc_empresa_b / "11_configuracio_i_backups/identitat_camaleo/boss.json"
        prompt_txt_b = disc_empresa_b / "09_copilot_ia/prompt_sistema/system_prompt.txt"
        assert emp_json_b.exists()
        assert boss_json_b.exists()
        assert prompt_txt_b.exists()
        dades_disc_b = json.loads(emp_json_b.read_text(encoding="utf-8"))
        assert dades_disc_b["id"] == id_b
        assert dades_disc_b["disc_dur_url"] == url_b
        assert dades_disc_b["vault_token"] == token_b
        assert "Empresa B Aigua" in prompt_txt_b.read_text(encoding="utf-8")

        # 3. Escriptura d'arxius reals d'entitats: cada empresa escriu NOMÉS al seu disc dur exclusiu
        ref_cli_a = await SovereignStorageGateway.desar_entitat_json(
            admin_session,
            id_a,
            "clients",
            "client_exclusiu_a",
            {"nom": "Client A", "empresa_id": id_a},
        )
        assert "01_clients/fitxes/client_exclusiu_a.json" in ref_cli_a
        assert (disc_empresa_a / "01_clients/fitxes/client_exclusiu_a.json").exists()
        assert not (disc_empresa_b / "01_clients/fitxes/client_exclusiu_a.json").exists()

        ref_cli_b = await SovereignStorageGateway.desar_entitat_json(
            admin_session,
            id_b,
            "clients",
            "client_exclusiu_b",
            {"nom": "Client B", "empresa_id": id_b},
        )
        assert "01_clients/fitxes/client_exclusiu_b.json" in ref_cli_b
        assert (disc_empresa_b / "01_clients/fitxes/client_exclusiu_b.json").exists()
        assert not (disc_empresa_a / "01_clients/fitxes/client_exclusiu_b.json").exists()

        # 4. Cada empresa es connecta únicament al seu Copilot exclusiu
        headers_boss_a = {
            "Authorization": f"Bearer {jwt.encode({'sub': str(uuid.uuid4()), 'rol': 'BOSS', 'empresa_id': id_a, 'exp': datetime.now(timezone.utc) + timedelta(minutes=15)}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)}",
            "X-Empresa-ID": id_a,
        }
        headers_boss_b = {
            "Authorization": f"Bearer {jwt.encode({'sub': str(uuid.uuid4()), 'rol': 'BOSS', 'empresa_id': id_b, 'exp': datetime.now(timezone.utc) + timedelta(minutes=15)}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)}",
            "X-Empresa-ID": id_b,
        }

        st_a = await async_client.get("/gestio/copilot/ia-status", headers=headers_boss_a)
        assert st_a.status_code == 200
        assert st_a.json()["estat"] == "ONLINE"
        assert st_a.json()["model_actiu"] == "qwen2.5-vl-7b-empresa-A"

        st_b = await async_client.get("/gestio/copilot/ia-status", headers=headers_boss_b)
        assert st_b.status_code == 200
        assert st_b.json()["estat"] == "ONLINE"
        assert st_b.json()["model_actiu"] == "deepseek-coder-v2-empresa-B"

        # 5. Autocuració: si es buiden accidentalment els camps de túnel a SQL, en tornar a entrar es restauren de la fitxa Superadmin
        from app.core.db import set_tenant_context

        await set_tenant_context(admin_session, None, is_superadmin=True)
        res_emp_a = await admin_session.execute(select(Empresa).where(Empresa.id == uuid.UUID(id_a)))
        emp_a_obj = res_emp_a.scalar_one()
        emp_a_obj.node_ia_url = None
        emp_a_obj.disc_dur_url = None
        emp_a_obj.node_ia_actiu = False
        await admin_session.commit()

        resp_cfg_a = await async_client.get("/gestio/configuracio/node-ia", headers=headers_boss_a)
        assert resp_cfg_a.status_code == 200
        cfg_a = resp_cfg_a.json()
        assert cfg_a["node_ia_url"] == url_a
        assert cfg_a["disc_dur_url"] == url_a
        assert cfg_a["node_ia_actiu"] is True
        assert cfg_a["copilot_operatiu"] is True
    finally:
        srv_a.shutdown()
        srv_a.server_close()
        srv_b.shutdown()
        srv_b.server_close()


@pytest.mark.asyncio
async def test_superadmin_crm_vault_offline_no_bloqueja_feature_flags_i_motiu_tunel_buit(
    async_client: AsyncClient, admin_session, monkeypatch
):
    """
    Regressió producció Hetzner:
    1) Quan el túnel del Disc Superadmin està offline, PUT /superadmin/tenants/{id}/crm NO pot
       retornar 503 i avortar el desat de /feature-flags; retorna 200 amb superadmin_vault_sync=False.
    2) PUT /superadmin/tenants/{id}/feature-flags persisteix node_ia_url, disc_dur_url i node_ia_actiu=True
       a PostgreSQL malgrat el Disc Superadmin estigui desconnectat.
    3) Si una empresa té feature_copilot_ia=True però cap URL desada (node_ia_url=None, disc_dur_url=None),
       tant /gestio/copilot/xat com /gestio/copilot/ia-status informen motiu='TUNEL_NO_CONFIGURAT'
       en lloc d'emmascarar-ho com a NODE_IA_INACTIU.
    """
    import socket

    from sqlalchemy import select

    from app.core.db import set_tenant_context
    from app.models.models import Empresa

    # Trobem un port TCP tancat real per simular un Disc Superadmin offline a Hetzner
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    closed_port = sock.getsockname()[1]
    sock.close()

    monkeypatch.setenv("SUPERADMIN_VAULT_URL", f"http://127.0.0.1:{closed_port}")
    monkeypatch.setenv("SUPERADMIN_VAULT_SECRET", "svlt_sup_offline_regression_test")

    emp_id = uuid.uuid4()
    boss_id = uuid.uuid4()
    await set_tenant_context(admin_session, None, is_superadmin=True)
    emp = Empresa(
        id=emp_id,
        nom="Empresa Regressio Tunel Buit",
        nif=f"B{str(emp_id.int)[:8]}",
        subdomini=f"reg-{str(emp_id)[:8]}",
        vertical="SEVALOR",
        estat_pagament="ACTIU",
        pla_subscripcio="PRO",
        feature_copilot_ia=True,
        node_ia_actiu=False,
        node_ia_url=None,
        disc_dur_url=None,
    )
    admin_session.add(emp)
    await admin_session.commit()

    sa_headers = {
        "Authorization": f"Bearer {jwt.encode({'sub': str(uuid.uuid4()), 'rol': 'SUPERADMIN', 'totp_activat': True, 'ip_allowlist': ['127.0.0.1', 'testclient'], 'exp': datetime.now(timezone.utc) + timedelta(minutes=15)}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)}"
    }
    boss_headers = {
        "Authorization": f"Bearer {jwt.encode({'sub': str(boss_id), 'rol': 'BOSS', 'empresa_id': str(emp_id), 'exp': datetime.now(timezone.utc) + timedelta(minutes=15)}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)}",
        "X-Empresa-ID": str(emp_id),
    }

    # 1. Sense cap URL desada -> motiu exacte TUNEL_NO_CONFIGURAT (no NODE_IA_INACTIU)
    r_xat_buit = await async_client.post(
        "/gestio/copilot/xat",
        json={"pregunta": "Hola"},
        headers=boss_headers,
    )
    assert r_xat_buit.status_code == 503, r_xat_buit.text
    assert r_xat_buit.json()["detail"]["code"] == "COPILOT_DESACTIVAT"
    assert r_xat_buit.json()["detail"]["motiu"] == "TUNEL_NO_CONFIGURAT"

    r_st_buit = await async_client.get("/gestio/copilot/ia-status", headers=boss_headers)
    assert r_st_buit.status_code == 200, r_st_buit.text
    assert r_st_buit.json()["motiu"] == "TUNEL_NO_CONFIGURAT"

    # 2. PUT /crm amb Disc Superadmin offline retorna 200 OK (no 503) amb avís
    r_crm = await async_client.put(
        f"/superadmin/tenants/{emp_id}/crm",
        json={
            "tarifa_llicencia_base": 150.0,
            "tarifa_per_operari": 25.0,
            "tarifa_config_ia": 0.0,
            "equips_ia_venuts": [],
            "notes_crm": "Test regressio",
            "quota_buffer_mb": 500,
        },
        headers=sa_headers,
    )
    assert r_crm.status_code == 200, r_crm.text
    assert r_crm.json()["superadmin_vault_sync"] is False
    assert "superadmin_vault_avis" in r_crm.json()

    # 3. PUT /feature-flags persisteix URLs i node_ia_actiu=True malgrat Disc Superadmin offline
    tunel_pub = "https://sevalormante-node.projectexinoxano.cat"
    r_ff = await async_client.put(
        f"/superadmin/tenants/{emp_id}/feature-flags",
        json={
            "feature_copilot_ia": True,
            "feature_flota": True,
            "feature_planols": False,
            "feature_telegram": True,
            "node_ia_url": tunel_pub,
            "disc_dur_url": tunel_pub,
            "node_ia_actiu": True,
        },
        headers=sa_headers,
    )
    assert r_ff.status_code == 200, r_ff.text
    ff = r_ff.json()["feature_flags"]
    assert ff["node_ia_actiu"] is True
    assert ff["node_ia_url"] == tunel_pub
    assert ff["disc_dur_url"] == tunel_pub

    # Verificar persistència real a PostgreSQL
    await set_tenant_context(admin_session, None, is_superadmin=True)
    admin_session.expire_all()
    emp_db = (await admin_session.execute(select(Empresa).where(Empresa.id == emp_id))).scalar_one()
    assert emp_db.node_ia_actiu is True
    assert emp_db.node_ia_url == tunel_pub
    assert emp_db.disc_dur_url == tunel_pub




