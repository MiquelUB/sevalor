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
async def test_configuracio_marca_i_node_ia_eliminats_de_gestio(
    async_client: AsyncClient, headers, headers_enginyer, admin_session
):
    """
    Verifica que Paleta Camaleònica (edició/ADN/logotip) i Node Sobirà (node-ia)
    han estat eliminats de /gestio/configuracio (exclusius de Superadmin),
    mantenint GET /gestio/configuracio/marca en mode només lectura per a la UI Camaleònica
    i sense exposar URLs del túnel a GET /gestio/configuracio/empresa.
    """
    from sqlalchemy import select

    from app.models.models import Empresa

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

    # 1. Tots els endpoints de Node Sobirà a /gestio/configuracio retornen 404
    for method, url, kwargs in [
        ("GET", "/gestio/configuracio/node-ia", {"headers": headers}),
        (
            "PUT",
            "/gestio/configuracio/node-ia",
            {"json": {"node_ia_url": "https://ia.empresa.cat/v1", "node_ia_actiu": True}, "headers": headers},
        ),
        (
            "PUT",
            "/gestio/configuracio/node-ia",
            {"json": {"node_ia_url": "http://192.168.1.100:1234/v1", "node_ia_actiu": True}, "headers": headers_enginyer},
        ),
        ("POST", "/gestio/configuracio/node-ia/provar", {"json": {}, "headers": headers}),
    ]:
        resp = await async_client.request(method, url, **kwargs)
        assert resp.status_code == 404, f"{method} {url} hauria de retornar 404, obtingut {resp.status_code}"

    # 2. Totes les mutacions de Marca / Paleta Camaleònica / Logotip a /gestio/configuracio eliminades
    resp_put_marca = await async_client.put(
        "/gestio/configuracio/marca",
        json={"color_primari": "210 80% 45%"},
        headers=headers,
    )
    assert resp_put_marca.status_code == 405

    for url in [
        "/gestio/configuracio/marca/adn",
        "/gestio/configuracio/marca/adn/aprovar",
        "/gestio/configuracio/logotip",
    ]:
        resp = await async_client.post(url, json={}, headers=headers)
        assert resp.status_code == 404, f"POST {url} hauria de retornar 404, obtingut {resp.status_code}"

    # 3. GET /gestio/configuracio/marca continua funcionant en mode només lectura per a Chameleon UI
    resp_get_marca = await async_client.get("/gestio/configuracio/marca", headers=headers)
    assert resp_get_marca.status_code == 200
    marca_data = resp_get_marca.json()
    assert "primari_hsl" in marca_data
    assert "secundari_hsl" in marca_data
    assert "accent_hsl" in marca_data

    # 4. GET /gestio/configuracio/empresa no exposa node_ia_url ni disc_dur_url
    resp_get_empresa = await async_client.get("/gestio/configuracio/empresa", headers=headers)
    assert resp_get_empresa.status_code == 200
    emp_data = resp_get_empresa.json()
    assert "node_ia_url" not in emp_data
    assert "disc_dur_url" not in emp_data

    # 5. Estat inicial del Copilot reflecteix SENSE_ORDINADOR_DEDICAT
    resp_estat_inicial = await async_client.get(
        "/gestio/copilot/estat-node",
        headers=headers,
    )
    assert resp_estat_inicial.status_code == 200
    dades_inicials = resp_estat_inicial.json()
    assert dades_inicials["node_actiu"] is False
    assert dades_inicials["estat"] == "SENSE_ORDINADOR_DEDICAT"


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
    async_client: AsyncClient, headers, admin_session, tmp_path
):
    """
    ADR-001 (WSS-only): Valida el diagnòstic 503 del Copilot i la verificació del Node IA des de Superadmin:
    1) POST /superadmin/tenants/verificar-node-ia consulta el Túnel Invers WSS en viu i retorna models reals.
    2) POST /gestio/copilot/xat i GET /gestio/copilot/ia-status informen el motiu exacte:
       FEATURE_COPILOT_DESACTIVAT, NODE_IA_INACTIU, TUNEL_OFFLINE, ONLINE.
    """
    from sqlalchemy import select

    import app.core.network_utils as net_utils
    from app.models.models import Empresa
    from tests.wss_test_helpers import live_empresa_wss_context

    vault_secret = "svlt_probe_cfg_42"
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
            node_ia_url=f"wss-tunnel://{empresa_id_boss}",
            disc_dur_url=f"wss-tunnel://{empresa_id_boss}",
            vault_token=vault_secret,
        )
        admin_session.add(empresa)
    else:
        empresa.feature_copilot_ia = False
        empresa.node_ia_actiu = True
        empresa.node_ia_url = f"wss-tunnel://{empresa_id_boss}"
        empresa.disc_dur_url = f"wss-tunnel://{empresa_id_boss}"
        empresa.vault_token = vault_secret
    await admin_session.commit()

    sa_headers = {
        "Authorization": f"Bearer {jwt.encode({'sub': str(uuid.uuid4()), 'rol': 'SUPERADMIN', 'totp_activat': True, 'ip_allowlist': ['127.0.0.1', 'testclient'], 'exp': datetime.now(timezone.utc) + timedelta(minutes=15)}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)}"
    }

    async with live_empresa_wss_context(
        empresa_id_boss,
        vault_secret,
        tmp_path / "diag_cop_disk",
        model_name="qwen2.5-vl-7b-instruct",
    ):
        # 1. Verificació de connectivitat via Superadmin sobre WSS -> OK
        resp_probe = await async_client.post(
            "/superadmin/tenants/verificar-node-ia",
            json={"empresa_id": str(empresa_id_boss)},
            headers=sa_headers,
        )
        assert resp_probe.status_code == 200, resp_probe.text
        probe_data = resp_probe.json()
        assert probe_data["status"] == "OK"
        assert "qwen2.5-vl-7b-instruct" in probe_data["models"]

        # 2. Copilot /xat ha d'indicar el motiu exacte: FEATURE_COPILOT_DESACTIVAT
        resp_xat_feat = await async_client.post(
            "/gestio/copilot/xat",
            json={"pregunta": "Hola"},
            headers=headers,
        )
        assert resp_xat_feat.status_code == 503, resp_xat_feat.text
        det_feat = resp_xat_feat.json()["detail"]
        assert det_feat["code"] == "COPILOT_DESACTIVAT"
        assert det_feat["motiu"] == "FEATURE_COPILOT_DESACTIVAT"

        # 3. /ia-status també exposa motiu=FEATURE_COPILOT_DESACTIVAT
        resp_st_feat = await async_client.get("/gestio/copilot/ia-status", headers=headers)
        assert resp_st_feat.status_code == 200, resp_st_feat.text
        assert resp_st_feat.json()["motiu"] == "FEATURE_COPILOT_DESACTIVAT"

        # 4. Activem feature_copilot_ia=True però node_ia_actiu=False -> motiu NODE_IA_INACTIU
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

        # 5. Superadmin POST /verificar-node-ia persisteix node_ia_actiu=True al backend!
        resp_probe_act = await async_client.post(
            "/superadmin/tenants/verificar-node-ia",
            json={"empresa_id": str(empresa_id_boss)},
            headers=sa_headers,
        )
        assert resp_probe_act.status_code == 200, resp_probe_act.text
        probe_act = resp_probe_act.json()
        assert probe_act["status"] == "OK"
        assert probe_act["node_ia_actiu"] is True

        # Verificar que GET /ia-status ara és ONLINE
        resp_st_ok = await async_client.get("/gestio/copilot/ia-status", headers=headers)
        assert resp_st_ok.status_code == 200, resp_st_ok.text
        st_ok = resp_st_ok.json()
        assert st_ok["estat"] == "ONLINE"
        assert st_ok["node_ia_actiu"] is True
        assert "embed" not in st_ok["model_actiu"].lower()

    # 6. Quan el túnel WSS es desconnecta -> TUNEL_OFFLINE
    resp_off = await async_client.post(
        "/superadmin/tenants/verificar-node-ia",
        json={"empresa_id": str(empresa_id_boss)},
        headers=sa_headers,
    )
    assert resp_off.status_code == 200
    assert resp_off.json()["motiu"] == "TUNEL_OFFLINE"

    # 7. ADR-001: Helpers WSS sobirans i eliminació de funcions Docker/HTTP antigues
    for removed_fn in (
        "get_docker_host_gateways",
        "get_candidate_node_urls",
        "get_candidate_ia_tunnel_urls",
        "resolve_effective_node_url",
        "is_private_or_loopback_url",
    ):
        assert not hasattr(net_utils, removed_fn)

    wss_uri = net_utils.build_wss_tunnel_uri(empresa_id_boss)
    assert wss_uri == f"wss-tunnel://{empresa_id_boss}"
    assert net_utils.extract_wss_tunnel_target(wss_uri) == str(empresa_id_boss)
    assert net_utils.resoldre_url_tunel_ia("http://127.0.0.1:1234", wss_uri) == wss_uri


@pytest.mark.asyncio
async def test_aillament_exclusiu_dues_empreses_i_persistencia_triple(
    async_client: AsyncClient, admin_session, tmp_path, monkeypatch
):
    """
    Certifica l'arquitectura sobirana multi-tenant 100% WSS (1 Empresa = 1 Copilot + 1 Disc Dur):
    1) Alta de 2 empreses independents (Empresa A i Empresa B), cadascuna amb el seu propi
       `SovereignWssAgent`, el seu propi token, LLM i carpeta física exclusiva.
    2) Persistència triple simultània (PostgreSQL + Disc Superadmin + Disc Exclusiu de cada empresa).
    3) Zero contaminació creuada entre Empresa A i Empresa B.
    4) Autocuració automàtica des de la fitxa del Superadmin si es buiden els camps a SQL.
    """
    import json

    from sqlalchemy import select

    from app.core.db import set_tenant_context
    from app.models.models import Empresa
    from app.services.sovereign_storage import (
        SovereignStorageGateway,
        inicialitzar_arbre_carpetes_superadmin,
    )
    from app.services.vault_tunnel import empresa_target_key, vault_tunnel_broker
    from tests.wss_test_helpers import (
        LiveUvicornServer,
        RunningWssAgent,
        start_local_llm_server,
        wait_for,
    )

    superadmin_root = tmp_path / "Sevalor_Superadmin_docs"
    disc_empresa_a = tmp_path / "Sevalormante_docs_exclusiu_A"
    disc_empresa_b = tmp_path / "HydroNord_docs_exclusiu_B"
    inicialitzar_arbre_carpetes_superadmin(superadmin_root)
    monkeypatch.setenv("SUPERADMIN_VAULT_URL", str(superadmin_root))

    token_a = "svlt_exclusiu_empresa_a_111111"
    token_b = "svlt_exclusiu_empresa_b_222222"

    llm_a_srv, llm_a_url, _ = start_local_llm_server(model_name="qwen2.5-vl-7b-empresa-A")
    llm_b_srv, llm_b_url, _ = start_local_llm_server(model_name="deepseek-coder-v2-empresa-B")

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

    agent_a: RunningWssAgent | None = None
    agent_b: RunningWssAgent | None = None
    id_a: str | None = None
    id_b: str | None = None

    try:
        async with LiveUvicornServer() as server:
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

            url_a = f"wss-tunnel://{id_a}"
            url_b = f"wss-tunnel://{id_b}"

            agent_a = RunningWssAgent(
                server.http_url,
                role="EMPRESA",
                token=token_a,
                empresa_id=id_a,
                disk_a=disc_empresa_a,
                llm_url=llm_a_url,
            ).start()
            agent_b = RunningWssAgent(
                server.http_url,
                role="EMPRESA",
                token=token_b,
                empresa_id=id_b,
                disk_a=disc_empresa_b,
                llm_url=llm_b_url,
            ).start()

            emp_json_a = disc_empresa_a / "11_configuracio_i_backups/identitat_camaleo/empresa.json"
            boss_json_a = disc_empresa_a / "11_configuracio_i_backups/identitat_camaleo/boss.json"
            prompt_txt_a = disc_empresa_a / "09_copilot_ia/prompt_sistema/system_prompt.txt"
            emp_json_b = disc_empresa_b / "11_configuracio_i_backups/identitat_camaleo/empresa.json"
            boss_json_b = disc_empresa_b / "11_configuracio_i_backups/identitat_camaleo/boss.json"
            prompt_txt_b = disc_empresa_b / "09_copilot_ia/prompt_sistema/system_prompt.txt"

            await wait_for(
                lambda: emp_json_a.exists()
                and boss_json_a.exists()
                and prompt_txt_a.exists()
                and emp_json_b.exists()
                and boss_json_b.exists()
                and prompt_txt_b.exists(),
                timeout=8.0,
            )

            # 2. Persistència Triple
            fitxa_sa_a = superadmin_root / "01_tenants_b2b/fitxes_empreses" / f"{id_a}.json"
            fitxa_sa_b = superadmin_root / "01_tenants_b2b/fitxes_empreses" / f"{id_b}.json"
            assert fitxa_sa_a.exists()
            assert fitxa_sa_b.exists()
            dades_sa_a = json.loads(fitxa_sa_a.read_text(encoding="utf-8"))
            dades_sa_b = json.loads(fitxa_sa_b.read_text(encoding="utf-8"))
            assert dades_sa_a["disc_dur_url"] == url_a
            assert dades_sa_a["vault_token"] == token_a
            assert dades_sa_b["disc_dur_url"] == url_b
            assert dades_sa_b["vault_token"] == token_b

            dades_disc_a = json.loads(emp_json_a.read_text(encoding="utf-8"))
            assert dades_disc_a["id"] == id_a
            assert dades_disc_a["disc_dur_url"] == url_a
            assert "Empresa A REBT" in prompt_txt_a.read_text(encoding="utf-8")

            dades_disc_b = json.loads(emp_json_b.read_text(encoding="utf-8"))
            assert dades_disc_b["id"] == id_b
            assert dades_disc_b["disc_dur_url"] == url_b
            assert "Empresa B Aigua" in prompt_txt_b.read_text(encoding="utf-8")

            # 3. Aïllament estricte d'escriptura d'entitats
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
            assert st_a.json()["estat"] == "ONLINE", st_a.json()
            assert st_a.json()["model_actiu"] == "qwen2.5-vl-7b-empresa-A"

            st_b = await async_client.get("/gestio/copilot/ia-status", headers=headers_boss_b)
            assert st_b.status_code == 200
            assert st_b.json()["estat"] == "ONLINE"
            assert st_b.json()["model_actiu"] == "deepseek-coder-v2-empresa-B"

            # 5. Autocuració des de la fitxa Superadmin
            await set_tenant_context(admin_session, None, is_superadmin=True)
            res_emp_a = await admin_session.execute(select(Empresa).where(Empresa.id == uuid.UUID(id_a)))
            emp_a_obj = res_emp_a.scalar_one()
            emp_a_obj.node_ia_url = None
            emp_a_obj.disc_dur_url = None
            emp_a_obj.node_ia_actiu = False
            await admin_session.commit()

            resp_cfg_a = await async_client.get(f"/superadmin/tenants/{id_a}", headers=sa_headers)
            assert resp_cfg_a.status_code == 200
            cfg_a = resp_cfg_a.json()
            assert cfg_a["node_ia_url"] == url_a
            assert cfg_a["disc_dur_url"] == url_a
            assert cfg_a["node_ia_actiu"] is True

            st_healed = await async_client.get("/gestio/copilot/ia-status", headers=headers_boss_a)
            assert st_healed.status_code == 200
            assert st_healed.json()["estat"] == "ONLINE"
    finally:
        if agent_a is not None:
            await agent_a.stop()
        if agent_b is not None:
            await agent_b.stop()
        if id_a:
            await vault_tunnel_broker.disconnect(empresa_target_key(id_a))
        if id_b:
            await vault_tunnel_broker.disconnect(empresa_target_key(id_b))
        llm_a_srv.shutdown()
        llm_a_srv.server_close()
        llm_b_srv.shutdown()
        llm_b_srv.server_close()


@pytest.mark.asyncio
async def test_superadmin_crm_vault_offline_no_bloqueja_feature_flags_i_motiu_tunel_buit(
    async_client: AsyncClient, admin_session, monkeypatch
):
    """
    Regressió producció Hetzner (ADR-001 WSS-only):
    1) Quan el Disc Superadmin WSS està offline, PUT /superadmin/tenants/{id}/crm retorna 200 amb superadmin_vault_sync=False.
    2) PUT /superadmin/tenants/{id}/feature-flags rebutja URLs HTTP/HTTPS entrants (422) i persisteix wss-tunnel://<id>
       i node_ia_actiu=True a PostgreSQL malgrat el Disc Superadmin estigui desconnectat.
    3) Si node_ia_actiu=False informa NODE_IA_INACTIU; si node_ia_actiu=True però agent WSS offline informa TUNEL_OFFLINE.
    """
    from sqlalchemy import select

    from app.core.db import set_tenant_context
    from app.models.models import Empresa

    monkeypatch.delenv("SUPERADMIN_VAULT_URL", raising=False)
    monkeypatch.setenv("SUPERADMIN_VAULT_SECRET", "svlt_sup_offline_regression_test")

    emp_id = uuid.uuid4()
    boss_id = uuid.uuid4()
    await set_tenant_context(admin_session, None, is_superadmin=True)
    emp = Empresa(
        id=emp_id,
        nom="Empresa Regressio Tunel WSS",
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

    # 1. Amb node_ia_actiu=False -> NODE_IA_INACTIU
    r_xat_buit = await async_client.post(
        "/gestio/copilot/xat",
        json={"pregunta": "Hola"},
        headers=boss_headers,
    )
    assert r_xat_buit.status_code == 503, r_xat_buit.text
    assert r_xat_buit.json()["detail"]["code"] == "COPILOT_DESACTIVAT"
    assert r_xat_buit.json()["detail"]["motiu"] == "NODE_IA_INACTIU"

    r_st_buit = await async_client.get("/gestio/copilot/ia-status", headers=boss_headers)
    assert r_st_buit.status_code == 200, r_st_buit.text
    assert r_st_buit.json()["motiu"] == "NODE_IA_INACTIU"

    # 2. PUT /crm amb Disc Superadmin WSS offline retorna 200 OK (no 503) amb avís
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

    # 3. PUT /feature-flags rebutja URLs HTTP entrants (422) i persisteix wss-tunnel://<id>
    r_ff_bad = await async_client.put(
        f"/superadmin/tenants/{emp_id}/feature-flags",
        json={
            "feature_copilot_ia": True,
            "feature_flota": True,
            "feature_planols": False,
            "feature_telegram": True,
            "node_ia_url": "https://sevalormante-node.projectexinoxano.cat",
            "disc_dur_url": "https://sevalormante-node.projectexinoxano.cat",
            "node_ia_actiu": True,
        },
        headers=sa_headers,
    )
    assert r_ff_bad.status_code == 422

    wss_uri = f"wss-tunnel://{emp_id}"
    r_ff = await async_client.put(
        f"/superadmin/tenants/{emp_id}/feature-flags",
        json={
            "feature_copilot_ia": True,
            "feature_flota": True,
            "feature_planols": False,
            "feature_telegram": True,
            "node_ia_actiu": True,
        },
        headers=sa_headers,
    )
    assert r_ff.status_code == 200, r_ff.text
    ff = r_ff.json()["feature_flags"]
    assert ff["node_ia_actiu"] is True
    assert ff["node_ia_url"] == wss_uri
    assert ff["disc_dur_url"] == wss_uri

    # Verificar persistència real a PostgreSQL i diagnòstic TUNEL_OFFLINE ara que node_ia_actiu=True
    await set_tenant_context(admin_session, None, is_superadmin=True)
    admin_session.expire_all()
    emp_db = (await admin_session.execute(select(Empresa).where(Empresa.id == emp_id))).scalar_one()
    assert emp_db.node_ia_actiu is True
    assert emp_db.node_ia_url == wss_uri
    assert emp_db.disc_dur_url == wss_uri

    r_st_off = await async_client.get("/gestio/copilot/ia-status", headers=boss_headers)
    assert r_st_off.status_code == 200
    assert r_st_off.json()["motiu"] == "TUNEL_OFFLINE"




