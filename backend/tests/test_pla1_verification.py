"""Tests d'integració i RLS Zero-Mock per al PLA 1 (Bloc de Camp Operari: Specs 015, 018, 019, 020)."""

import uuid

import bcrypt
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.api.v1.operari_auth import create_access_token
from app.core.db import set_tenant_context
from app.core.redis import get_redis_client
from app.main import app
from app.models.models import Empresa, Incidencia, TiquetDespesa, Usuari, Vehicle

MINIMAL_WEBP_BYTES = b"RIFF\x24\x00\x00\x00WEBPVP8 " + b"\x00" * 30


def _hash_pin(pin: str) -> str:
    return bcrypt.hashpw(pin.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


@pytest_asyncio.fixture
async def setup_pla1_tenants(admin_session):
    """Prepara dos tenants independents (Tenant A i Tenant B) sobre SAVEPOINT real."""
    emp_a = uuid.uuid4()
    emp_b = uuid.uuid4()
    op_a_id = uuid.uuid4()
    op_no_tg_id = uuid.uuid4()
    boss_a_id = uuid.uuid4()
    op_b_id = uuid.uuid4()
    boss_b_id = uuid.uuid4()
    veh_a_id = uuid.uuid4()

    nif_op_a = f"PLA1A{emp_a.hex[:6]}"
    nif_op_no_tg = f"PLA1N{emp_a.hex[:6]}"
    nif_boss_a = f"PLA1BA{emp_a.hex[:5]}"
    nif_op_b = f"PLA1B{emp_b.hex[:6]}"
    nif_boss_b = f"PLA1BB{emp_b.hex[:5]}"
    pin_real = "1234"
    pin_hash = _hash_pin(pin_real)

    admin_session.add_all(
        [
            Empresa(
                id=emp_a,
                nom="Tenant A Camp",
                nif=f"B10{emp_a.hex[:6]}",
                subdomini=f"tpla1a-{emp_a.hex[:5]}",
                pla_subscripcio="PRO",
                estat_pagament="ACTIU",
            ),
            Empresa(
                id=emp_b,
                nom="Tenant B Camp",
                nif=f"B20{emp_b.hex[:6]}",
                subdomini=f"tpla1b-{emp_b.hex[:5]}",
                pla_subscripcio="PRO",
                estat_pagament="ACTIU",
            ),
        ]
    )
    await admin_session.flush()

    admin_session.add_all(
        [
            Usuari(
                id=boss_a_id,
                empresa_id=emp_a,
                nif=nif_boss_a,
                nom="Boss",
                cognoms="A",
                rol="BOSS",
                estat="ACTIU",
                pin_hash=pin_hash,
            ),
            Usuari(
                id=op_a_id,
                empresa_id=emp_a,
                nif=nif_op_a,
                nom="Operari",
                cognoms="Telegram",
                telefon=f"611{emp_a.hex[:6]}",
                rol="OPERARI",
                estat="ACTIU",
                pin_hash=pin_hash,
                telegram_chat_id=987654321,
                carnet_conduir="B",
            ),
            Usuari(
                id=op_no_tg_id,
                empresa_id=emp_a,
                nif=nif_op_no_tg,
                nom="Operari",
                cognoms="SenseTG",
                telefon=f"612{emp_a.hex[:6]}",
                rol="OPERARI",
                estat="ACTIU",
                pin_hash=pin_hash,
                telegram_chat_id=None,
            ),
            Usuari(
                id=boss_b_id,
                empresa_id=emp_b,
                nif=nif_boss_b,
                nom="Boss",
                cognoms="B",
                rol="BOSS",
                estat="ACTIU",
                pin_hash=pin_hash,
            ),
            Usuari(
                id=op_b_id,
                empresa_id=emp_b,
                nif=nif_op_b,
                nom="Operari",
                cognoms="B",
                telefon=f"622{emp_b.hex[:6]}",
                rol="OPERARI",
                estat="ACTIU",
                pin_hash=pin_hash,
                telegram_chat_id=123456789,
            ),
        ]
    )
    await admin_session.flush()

    admin_session.add(
        Vehicle(
            id=veh_a_id,
            empresa_id=emp_a,
            matricula=f"99{emp_a.hex[:5].upper()}",
            marca="Ford",
            model="Ranger",
            tipus="FURGONETA",
            estat="DISPONIBLE",
            odometre_acumulat=50000,
        )
    )
    await admin_session.flush()

    return {
        "emp_a": emp_a,
        "emp_b": emp_b,
        "op_a_id": op_a_id,
        "op_no_tg_id": op_no_tg_id,
        "boss_a_id": boss_a_id,
        "op_b_id": op_b_id,
        "boss_b_id": boss_b_id,
        "veh_a_id": veh_a_id,
        "nif_op_a": nif_op_a,
        "nif_op_no_tg": nif_op_no_tg,
        "nif_op_b": nif_op_b,
        "pin": pin_real,
        "token_op_a": create_access_token(
            str(op_a_id), "OPERARI", str(emp_a), __import__("datetime").timedelta(hours=1)
        ),
        "token_op_b": create_access_token(
            str(op_b_id), "OPERARI", str(emp_b), __import__("datetime").timedelta(hours=1)
        ),
        "token_boss_a": create_access_token(
            str(boss_a_id), "BOSS", str(emp_a), __import__("datetime").timedelta(hours=1)
        ),
        "token_boss_b": create_access_token(
            str(boss_b_id), "BOSS", str(emp_b), __import__("datetime").timedelta(hours=1)
        ),
    }


@pytest.mark.asyncio
async def test_enrolament_telegram_otp_i_aillament_rls(setup_pla1_tenants, admin_session):
    """(Spec 019) Verifica enrolament Telegram OTP real a Redis, consum i aïllament entre tenants."""
    ctx = setup_pla1_tenants
    redis = await get_redis_client()
    assert redis is not None
    redis_key = f"pwa_enrol_otp:{ctx['emp_a']}:{ctx['op_a_id']}"
    await redis.delete(redis_key)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1") as ac:
        # 1. Operari sense Telegram vinculat -> error 400 net
        res_no_tg = await ac.post(
            "/operari/enrolar/solicitar-otp",
            headers={"X-Empresa-ID": str(ctx["emp_a"])},
            json={"telefon_o_nif": ctx["nif_op_no_tg"], "empresa_id": str(ctx["emp_a"])},
        )
        assert res_no_tg.status_code == 400
        assert "Telegram vinculat" in res_no_tg.json()["detail"]

        # 2. Operari amb Telegram vinculat -> genera OTP de 6 dígits a Redis real
        res_req = await ac.post(
            "/operari/enrolar/solicitar-otp",
            headers={"X-Empresa-ID": str(ctx["emp_a"])},
            json={"telefon_o_nif": ctx["nif_op_a"], "empresa_id": str(ctx["emp_a"])},
        )
        assert res_req.status_code == 200, res_req.text
        assert res_req.json()["status"] == "OTP_SENT_TELEGRAM"

        otp_real = await redis.get(redis_key)
        assert otp_real is not None and len(otp_real) == 6 and otp_real.isdigit()

        # 3. Aïllament multi-tenant: Tenant B no pot verificar l'OTP de Tenant A
        res_cross = await ac.post(
            "/operari/enrolar/verificar-otp",
            headers={"X-Empresa-ID": str(ctx["emp_b"])},
            json={
                "telefon_o_nif": ctx["nif_op_a"],
                "otp_code": otp_real,
                "device_fingerprint": "attacker-tenant-b",
                "empresa_id": str(ctx["emp_b"]),
            },
        )
        assert res_cross.status_code in (401, 403)

        # 4. Verificació OTP incorrecta -> 401 i manté l'OTP
        res_wrong = await ac.post(
            "/operari/enrolar/verificar-otp",
            headers={"X-Empresa-ID": str(ctx["emp_a"])},
            json={
                "telefon_o_nif": ctx["nif_op_a"],
                "otp_code": "000000" if otp_real != "000000" else "999999",
                "device_fingerprint": "iphone-15-pro",
                "empresa_id": str(ctx["emp_a"]),
            },
        )
        assert res_wrong.status_code == 401

        # 5. Verificació OTP correcta -> emet device_token, persisteix dispositiu_referencia i esborra clau Redis
        res_ok = await ac.post(
            "/operari/enrolar/verificar-otp",
            headers={"X-Empresa-ID": str(ctx["emp_a"])},
            json={
                "telefon_o_nif": ctx["nif_op_a"],
                "otp_code": otp_real,
                "device_fingerprint": "iphone-15-pro",
                "empresa_id": str(ctx["emp_a"]),
            },
        )
        assert res_ok.status_code == 200, res_ok.text
        body = res_ok.json()
        assert body["status"] == "ENROLLED"
        assert body["device_token"].startswith("dev_")
        assert await redis.get(redis_key) is None

    await set_tenant_context(admin_session, None, is_superadmin=True)
    row = (
        await admin_session.execute(
            select(Usuari.dispositiu_referencia).where(Usuari.id == ctx["op_a_id"])
        )
    ).scalar_one()
    assert row is not None and body["device_token"] in row


@pytest.mark.asyncio
async def test_reset_pin_telegram_rexifrat_idb_i_rls(setup_pla1_tenants, admin_session):
    """(Spec 019) Verifica restabliment de PIN via Gestió/Telegram, incidència i rexifrat_idb."""
    ctx = setup_pla1_tenants

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1") as ac:
        # Boss Tenant B intenta resetejar PIN d'Operari Tenant A -> bloquejat per aïllament tenant
        res_cross = await ac.post(
            f"/gestio/operaris/{ctx['op_a_id']}/reset-pin",
            headers={"Authorization": f"Bearer {ctx['token_boss_b']}", "X-Empresa-ID": str(ctx["emp_b"])},
        )
        assert res_cross.status_code == 404

        # Boss Tenant A reseteja PIN d'Operari Tenant A -> canal Telegram, requereix_rexifrat_idb=True i incidència
        res_reset = await ac.post(
            f"/gestio/operaris/{ctx['op_a_id']}/reset-pin",
            headers={"Authorization": f"Bearer {ctx['token_boss_a']}", "X-Empresa-ID": str(ctx["emp_a"])},
        )
        assert res_reset.status_code == 200, res_reset.text
        reset_data = res_reset.json()
        nou_pin = reset_data["pin_generat"]
        assert len(nou_pin) == 4 and nou_pin.isdigit()
        assert reset_data["requereix_rexifrat_idb"] is True

        await set_tenant_context(admin_session, None, is_superadmin=True)
        inc = (
            await admin_session.execute(
                select(Incidencia).where(
                    Incidencia.empresa_id == ctx["emp_a"],
                    Incidencia.operari_id == ctx["op_a_id"],
                    Incidencia.tipus == "SEGURETAT_RESTABLIMENT_PIN",
                )
            )
        ).scalar_one_or_none()
        assert inc is not None
        assert inc.ambit == "SEGURETAT"

        # Primer login amb el nou PIN ha de retornar requereix_rexifrat_idb=True i després resetejar-lo
        res_login1 = await ac.post(
            "/operari_auth/login",
            headers={"X-Empresa-ID": str(ctx["emp_a"])},
            json={"nif": ctx["nif_op_a"], "pin": nou_pin},
        )
        assert res_login1.status_code == 200, res_login1.text
        assert res_login1.json()["requereix_rexifrat_idb"] is True

        res_login2 = await ac.post(
            "/operari_auth/login",
            headers={"X-Empresa-ID": str(ctx["emp_a"])},
            json={"nif": ctx["nif_op_a"], "pin": nou_pin},
        )
        assert res_login2.status_code == 200
        assert res_login2.json()["requereix_rexifrat_idb"] is False

        # També provar flux /api/v1/operari/recuperar-pin per NIF
        res_rec = await ac.post(
            "/operari/recuperar-pin",
            headers={"X-Empresa-ID": str(ctx["emp_a"])},
            json={"telefon_o_nif": ctx["nif_op_a"], "empresa_id": str(ctx["emp_a"])},
        )
        assert res_rec.status_code == 200
        assert res_rec.json()["status"] == "PIN_RESET_TELEGRAM_SENT"


@pytest.mark.asyncio
async def test_alerta_forca_bruta_3_intents(setup_pla1_tenants, admin_session):
    """(Spec 019) Verifica que el 3r intent fallit genera incidència FORCA_BRUTA_PIN i l'endpoint explícit funciona."""
    ctx = setup_pla1_tenants

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1") as ac:
        for _ in range(3):
            r = await ac.post(
                "/operari_auth/login",
                headers={"X-Empresa-ID": str(ctx["emp_a"])},
                json={"nif": ctx["nif_op_a"], "pin": "0000" if ctx["pin"] != "0000" else "9999"},
            )
            assert r.status_code == 401

        await set_tenant_context(admin_session, None, is_superadmin=True)
        inc_res = await admin_session.execute(
            select(Incidencia).where(
                Incidencia.empresa_id == ctx["emp_a"],
                Incidencia.operari_id == ctx["op_a_id"],
                Incidencia.tipus == "FORCA_BRUTA_PIN",
            )
        )
        inc = inc_res.scalar_one_or_none()
        assert inc is not None
        assert inc.gravetat == "CRITICA"

        res_explicit = await ac.post(
            "/operari/alerta-forca-bruta",
            headers={"X-Empresa-ID": str(ctx["emp_a"])},
            json={
                "telefon_o_nif": ctx["nif_op_a"],
                "empresa_id": str(ctx["emp_a"]),
                "intents_fallits": 3,
                "device_token": "dev_test_brute",
            },
        )
        assert res_explicit.status_code == 201
        assert res_explicit.json()["status"] == "ALERT_RECORDED"


@pytest.mark.asyncio
async def test_tiquets_captura_rapida_zero_tecleig_i_rls(
    async_client, setup_pla1_tenants, admin_session
):
    """(Spec 018) Verifica captura ràpida WebP sense OCR/imports al terminal, doble foto CARBURANT i RLS."""
    ctx = setup_pla1_tenants
    headers_op_a = {
        "Authorization": f"Bearer {ctx['token_op_a']}",
        "X-Empresa-ID": str(ctx["emp_a"]),
    }
    headers_op_b = {
        "Authorization": f"Bearer {ctx['token_op_b']}",
        "X-Empresa-ID": str(ctx["emp_b"]),
    }
    headers_boss_a = {
        "Authorization": f"Bearer {ctx['token_boss_a']}",
        "X-Empresa-ID": str(ctx["emp_a"]),
    }

    # 1. CARBURANT sense segona foto odòmetre -> HTTP 422
    res_no_odo = await async_client.post(
        "/operari/tiquets/captura-rapida",
        headers=headers_op_a,
        data={"categoria": "CARBURANT"},
        files={"foto_tiquet": ("tiquet.webp", MINIMAL_WEBP_BYTES, "image/webp")},
    )
    assert res_no_odo.status_code == 422
    assert "segona foto" in res_no_odo.json()["detail"].lower()

    # 2. Fitxer corrupte / no imatge (magic bytes invàlids) -> HTTP 422
    res_bad_magic = await async_client.post(
        "/operari/tiquets/captura-rapida",
        headers=headers_op_a,
        data={"categoria": "FERRETERIA"},
        files={"foto_tiquet": ("fake.webp", b"NOT_A_REAL_IMAGE", "image/webp")},
    )
    assert res_bad_magic.status_code == 422

    # 3. FERRETERIA vàlid sense import manual -> HTTP 201, PENDENT_PROCESSAMENT i NULLs a BD
    res_ferr = await async_client.post(
        "/operari/tiquets/captura-rapida",
        headers=headers_op_a,
        data={"categoria": "FERRETERIA"},
        files={"foto_tiquet": ("captura.webp", MINIMAL_WEBP_BYTES, "image/webp")},
    )
    assert res_ferr.status_code == 201, res_ferr.text
    ferr_data = res_ferr.json()
    assert ferr_data["estat_aprovacio"] == "PENDENT_PROCESSAMENT"
    assert ferr_data["nom_fitxer_visible"].startswith("tiquet_tmp_")
    assert "import_total" not in ferr_data

    row_ferr = (
        await admin_session.execute(
            select(TiquetDespesa).where(TiquetDespesa.id == uuid.UUID(ferr_data["id"]))
        )
    ).scalar_one()
    assert row_ferr.import_total is None
    assert row_ferr.base_imposable is None
    assert row_ferr.estat_aprovacio == "PENDENT_PROCESSAMENT"

    # 4. CARBURANT amb doble foto -> HTTP 201
    res_carb = await async_client.post(
        "/operari/tiquets/captura-rapida",
        headers=headers_op_a,
        data={"categoria": "CARBURANT", "vehicle_id": str(ctx["veh_a_id"])},
        files={
            "foto_tiquet": ("carburant.webp", MINIMAL_WEBP_BYTES, "image/webp"),
            "foto_odometre": ("odometre.webp", MINIMAL_WEBP_BYTES, "image/webp"),
        },
    )
    assert res_carb.status_code == 201, res_carb.text
    assert res_carb.json()["te_foto_odometre"] is True

    # 5. Llista safata d'avui: Tenant A veu els 2 sense preus ni miniatures; Tenant B veu 0 (RLS)
    res_avui_a = await async_client.get("/operari/tiquets/avui", headers=headers_op_a)
    assert res_avui_a.status_code == 200
    assert len(res_avui_a.json()) == 2
    assert all("import_total" not in item for item in res_avui_a.json())

    res_avui_b = await async_client.get("/operari/tiquets/avui", headers=headers_op_b)
    assert res_avui_b.status_code == 200
    assert res_avui_b.json() == []

    # 6. Verificar que /gestio/comptabilitat/tiquets no peta amb NULLs
    res_gestio_tiq = await async_client.get(
        "/gestio/comptabilitat/tiquets", headers=headers_boss_a
    )
    assert res_gestio_tiq.status_code == 200, res_gestio_tiq.text

    # 7. Checkout custòdia neteja safata d'avui
    res_cust = await async_client.post(
        "/operari/tiquets/checkout-custodia",
        headers=headers_op_a,
        json={},
    )
    assert res_cust.status_code == 200
    assert res_cust.json()["confirmats"] == 2

    res_avui_post = await async_client.get("/operari/tiquets/avui", headers=headers_op_a)
    assert res_avui_post.status_code == 200
    assert res_avui_post.json() == []


@pytest.mark.asyncio
async def test_jornada_odometre_foto_zero_tecleig(async_client, setup_pla1_tenants):
    """(Spec 015/020) Verifica captura de foto d'odòmetre i assignació de vehicle sense km manuals."""
    ctx = setup_pla1_tenants
    headers_op_a = {
        "Authorization": f"Bearer {ctx['token_op_a']}",
        "X-Empresa-ID": str(ctx["emp_a"]),
    }

    res_inici = await async_client.post(
        "/operari/jornada/inici",
        headers=headers_op_a,
        json={"latitud": 41.6176, "longitud": 0.6200},
    )
    assert res_inici.status_code == 201, res_inici.text
    jornada_id = res_inici.json()["id"]

    # Pujada invàlida -> 422
    res_bad = await async_client.post(
        f"/operari/jornada/{jornada_id}/odometre-foto",
        headers=headers_op_a,
        data={"moment": "INICI"},
        files={"foto_odometre": ("bad.bin", b"INVALID", "image/webp")},
    )
    assert res_bad.status_code == 422

    # Pujada WebP vàlida -> 201
    res_foto = await async_client.post(
        f"/operari/jornada/{jornada_id}/odometre-foto",
        headers=headers_op_a,
        data={"vehicle_id": str(ctx["veh_a_id"]), "moment": "INICI"},
        files={"foto_odometre": ("odo.webp", MINIMAL_WEBP_BYTES, "image/webp")},
    )
    assert res_foto.status_code == 201, res_foto.text
    foto_path = res_foto.json()["foto_odometre_path"]

    # Assignació vehicle sense km_actuals però amb odometre_foto_path -> 200
    res_assign = await async_client.post(
        f"/operari/jornada/{jornada_id}/vehicle",
        headers=headers_op_a,
        json={
            "vehicle_id": str(ctx["veh_a_id"]),
            "odometre_foto_path": foto_path,
        },
    )
    assert res_assign.status_code == 200, res_assign.text
    assert res_assign.json()["odometre_foto_path"] == foto_path
