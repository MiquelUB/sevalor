"""
Tests d'Avaluació de Fase 4: Canal Transaccional (Telegram) i Portal Client
(Spec 009 / SDD SEVALOR v4.0).

Cobreix:
- TEST-F4-01: Aprovació de pressupost via callback_query de Telegram (estat APROVAT, token_signatura TG-APROV-).
- TEST-F4-02: Rebuig de pressupost via callback_query de Telegram (estat REBUTJAT).
- TEST-F4-03: Pressupost inexistent o id invàlid a Telegram (missatge d'error 'no existeix').
- TEST-F4-04: Despatx del pressupost al client via POST /gestio/pressupostos/{id}/enviar-telegram.
- TEST-F4-05: Generació asíncrona de PDF oficial post-obra via Celery (generar_informe_post_obra).
"""

import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.main import app
from app.models.models import Client, Empresa, Pressupost, Usuari
from app.workers.tasks import generar_informe_post_obra


def generar_token(usuari_id: uuid.UUID, empresa_id: uuid.UUID, rol: str = "BOSS") -> str:
    """Genera un token JWT vàlid per a proves."""
    payload = {
        "sub": str(usuari_id),
        "rol": rol,
        "empresa_id": str(empresa_id),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


@pytest.mark.asyncio
async def test_f4_01_aprovacio_pressupost_telegram(admin_session, boss_token):
    """
    TEST-F4-01: Aprovació de Pressupost via Telegram Inline Keyboard.
    1. Crear empresa + client vinculat a Telegram + pressupost PENDENT.
    2. Enviar callback_query d'aprovació al webhook de Telegram.
    3. Consultar GET /gestio/pressupostos/{id} i verificar:
       - estat == 'APROVAT'
       - token_signatura comença per 'TG-APROV-'
    """
    token_jwt, empresa_id_str = boss_token
    empresa_id = uuid.UUID(empresa_id_str)
    decoded = jwt.decode(token_jwt, options={"verify_signature": False})
    usuari_id = uuid.UUID(decoded["sub"])

    # 1. Crear empresa i usuari
    empresa = Empresa(
        id=empresa_id,
        nom="Constructora del Maresme SL",
        nif="B" + uuid.uuid4().hex[:8].upper(),
        subdomini="maresme-" + uuid.uuid4().hex[:5],
        pla_subscripcio="ENTERPRISE",
        estat_pagament="ACTIU",
        vertical="SEVALOR",
    )
    admin_session.add(empresa)
    await admin_session.flush()

    usuari = Usuari(
        id=usuari_id,
        empresa_id=empresa_id,
        nom="Marta",
        cognoms="Oficina",
        nif="44556677E",
        rol="BOSS",
        estat="ACTIU",
    )
    admin_session.add(usuari)

    chat_id = 998877661
    client = Client(
        id=uuid.uuid4(),
        empresa_id=empresa_id,
        codi="CLI-TG-01",
        rao_social="Comunitat Propietaris Diagonal 400",
        nif="H" + uuid.uuid4().hex[:8].upper(),
        telegram_chat_id=chat_id,
        estat_canal_telegram="ACTIU",
    )
    admin_session.add(client)
    await admin_session.flush()

    pressupost = Pressupost(
        id=uuid.uuid4(),
        empresa_id=empresa_id,
        client_id=client.id,
        numero="PRES-2026-0099",
        total=4250.75,
        estat="PENDENT",
    )
    admin_session.add(pressupost)
    await admin_session.flush()

    # 2. Simular el callback_query del webhook de Telegram
    payload_telegram = {
        "callback_query": {
            "id": "cbq_01",
            "message": {
                "chat": {"id": chat_id}
            },
            "data": f"aprovar_pressupost:{pressupost.id}"
        }
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res_hook = await ac.post("/api/v1/webhooks/telegram", json=payload_telegram)
        assert res_hook.status_code == 200
        assert res_hook.json().get("action") == "callback_processed"

        # 3. Verificar via endpoint oficial GET /gestio/pressupostos/{id}
        headers = {
            "Authorization": f"Bearer {token_jwt}",
            "X-Empresa-ID": str(empresa_id),
        }
        res_get = await ac.get(f"/api/v1/gestio/pressupostos/{pressupost.id}", headers=headers)
        assert res_get.status_code == 200
        p_data = res_get.json()

        # 4. Assertions d'Estat i Token de Signatura
        assert p_data["estat"] == "APROVAT"
        assert p_data["token_signatura"] is not None
        assert p_data["token_signatura"].startswith(f"TG-APROV-{chat_id}-")


@pytest.mark.asyncio
async def test_f4_02_rebuig_pressupost_telegram(admin_session, boss_token):
    """
    TEST-F4-02: Rebuig de Pressupost via Telegram.
    Verifica que l'estat commuta a 'REBUTJAT'.
    """
    token_jwt, empresa_id_str = boss_token
    empresa_id = uuid.UUID(empresa_id_str)
    decoded = jwt.decode(token_jwt, options={"verify_signature": False})
    usuari_id = uuid.UUID(decoded["sub"])

    empresa = Empresa(
        id=empresa_id,
        nom="Clima i Reformes SL",
        nif="B" + uuid.uuid4().hex[:8].upper(),
        subdomini="clima-" + uuid.uuid4().hex[:5],
        pla_subscripcio="ENTERPRISE",
        estat_pagament="ACTIU",
        vertical="SEVALOR",
    )
    admin_session.add(empresa)
    await admin_session.flush()

    usuari = Usuari(
        id=usuari_id,
        empresa_id=empresa_id,
        nom="Jordi",
        cognoms="Admin",
        nif="11223344F",
        rol="BOSS",
        estat="ACTIU",
    )
    admin_session.add(usuari)

    chat_id = 998877662
    client = Client(
        id=uuid.uuid4(),
        empresa_id=empresa_id,
        codi="CLI-TG-02",
        rao_social="Client Rebuig Proposta",
        nif="B" + uuid.uuid4().hex[:8].upper(),
        telegram_chat_id=chat_id,
        estat_canal_telegram="ACTIU",
    )
    admin_session.add(client)
    await admin_session.flush()

    pressupost = Pressupost(
        id=uuid.uuid4(),
        empresa_id=empresa_id,
        client_id=client.id,
        numero="PRES-2026-0100",
        total=1800.00,
        estat="PENDENT",
    )
    admin_session.add(pressupost)
    await admin_session.flush()

    payload_telegram = {
        "callback_query": {
            "id": "cbq_02",
            "message": {
                "chat": {"id": chat_id}
            },
            "data": f"rebutjar_pressupost:{pressupost.id}"
        }
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res_hook = await ac.post("/api/v1/webhooks/telegram", json=payload_telegram)
        assert res_hook.status_code == 200

        headers = {
            "Authorization": f"Bearer {token_jwt}",
            "X-Empresa-ID": str(empresa_id),
        }
        res_get = await ac.get(f"/api/v1/gestio/pressupostos/{pressupost.id}", headers=headers)
        assert res_get.status_code == 200
        p_data = res_get.json()

        assert p_data["estat"] == "REBUTJAT"


@pytest.mark.asyncio
async def test_f4_03_pressupost_inexistent_telegram(admin_session):
    """
    TEST-F4-03: Intent d'aprovació d'un pressupost inexistent via callback_query.
    El bot ha de respondre amb missatge d'error ('no existeix').
    """
    from app.services.telegram_service import telegram_service

    empresa_id = uuid.uuid4()
    empresa = Empresa(
        id=empresa_id,
        nom="Seguretat Total SL",
        nif="B" + uuid.uuid4().hex[:8].upper(),
        subdomini="seg-" + uuid.uuid4().hex[:5],
        pla_subscripcio="ENTERPRISE",
        estat_pagament="ACTIU",
        vertical="SEVALOR",
    )
    admin_session.add(empresa)
    await admin_session.flush()

    chat_id = 998877663
    client = Client(
        id=uuid.uuid4(),
        empresa_id=empresa_id,
        codi="CLI-TG-03",
        rao_social="Client Control Errors",
        nif="B" + uuid.uuid4().hex[:8].upper(),
        telegram_chat_id=chat_id,
        estat_canal_telegram="ACTIU",
    )
    admin_session.add(client)
    await admin_session.flush()

    fake_uuid = uuid.uuid4()
    resposta = await telegram_service.processar_callback_query(
        admin_session, chat_id, f"aprovar_pressupost:{fake_uuid}"
    )

    assert "no existeix" in resposta.lower()


@pytest.mark.asyncio
async def test_f4_04_enviar_pressupost_via_telegram_endpoint(admin_session, boss_token):
    """
    TEST-F4-04: Despatx d'un pressupost pendent via endpoint POST /gestio/pressupostos/{id}/enviar-telegram.
    """
    token_jwt, empresa_id_str = boss_token
    empresa_id = uuid.UUID(empresa_id_str)
    decoded = jwt.decode(token_jwt, options={"verify_signature": False})
    usuari_id = uuid.UUID(decoded["sub"])

    empresa = Empresa(
        id=empresa_id,
        nom="Instal·lacions del Vallès SL",
        nif="B" + uuid.uuid4().hex[:8].upper(),
        subdomini="inst-" + uuid.uuid4().hex[:5],
        pla_subscripcio="ENTERPRISE",
        estat_pagament="ACTIU",
        vertical="SEVALOR",
    )
    admin_session.add(empresa)
    await admin_session.flush()

    usuari = Usuari(
        id=usuari_id,
        empresa_id=empresa_id,
        nom="Laura",
        cognoms="Gestora",
        nif="88776655G",
        rol="BOSS",
        estat="ACTIU",
    )
    admin_session.add(usuari)

    chat_id = 998877664
    client = Client(
        id=uuid.uuid4(),
        empresa_id=empresa_id,
        codi="CLI-TG-04",
        rao_social="Client Notificable",
        nif="B" + uuid.uuid4().hex[:8].upper(),
        telegram_chat_id=chat_id,
        estat_canal_telegram="ACTIU",
    )
    admin_session.add(client)
    await admin_session.flush()

    pressupost = Pressupost(
        id=uuid.uuid4(),
        empresa_id=empresa_id,
        client_id=client.id,
        numero="PRES-2026-0205",
        total=3100.50,
        estat="PENDENT",
    )
    admin_session.add(pressupost)
    await admin_session.flush()

    headers = {
        "Authorization": f"Bearer {token_jwt}",
        "X-Empresa-ID": str(empresa_id),
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post(f"/api/v1/gestio/pressupostos/{pressupost.id}/enviar-telegram", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "enviat"
        assert data["numero"] == "PRES-2026-0205"
        assert data["chat_id"] == chat_id


def test_f4_05_generacio_pdf_post_obra():
    """
    TEST-F4-05: Generació asíncrona de PDF oficial post-obra via Celery (F4-T04).
    """
    ot_id = str(uuid.uuid4())
    empresa_id = str(uuid.uuid4())

    res = generar_informe_post_obra(
        ordre_treball_id=ot_id,
        empresa_id=empresa_id,
        client_nom="Client Demostració SL",
        dades_informe={"hores_reals": 4.5, "cost_materials": 340.20},
    )

    assert isinstance(res, dict)
    assert res.get("status") == "COMPLETED"
    assert res.get("file_path", "").endswith(".pdf")
    assert ot_id in res.get("file_path", "")


@pytest.mark.asyncio
async def test_f4_06_cicle_complet_pressupost_edicio_pdf_email_portal_i_rls(
    admin_session: AsyncSession,
    tmp_path,
    monkeypatch,
):
    """
    TEST-F4-06: Cicle complet de pressupostos:
    creació amb línies -> edició -> PDF ReportLab -> email/registre enviament ->
    RBAC ENGINYER + RLS multi-tenant -> portal públic client (acceptació) -> conversió a OT.
    """
    from datetime import datetime, timedelta, timezone

    import jwt
    from httpx import ASGITransport, AsyncClient

    from app.core.config import settings
    from app.main import app
    from app.models.models import Client, Empresa, Usuari
    from app.services.sovereign_storage import SovereignStorageGateway

    monkeypatch.setattr(SovereignStorageGateway, "TRANSIT_QUEUE_DIR", tmp_path / "transit")

    emp_a_id = uuid.uuid4()
    emp_b_id = uuid.uuid4()
    boss_a_id = uuid.uuid4()
    eng_a_id = uuid.uuid4()
    boss_b_id = uuid.uuid4()
    client_a_id = uuid.uuid4()

    emp_a = Empresa(
        id=emp_a_id,
        nom="Instal·lacions Lleida SL",
        nif=f"B{emp_a_id.hex[:8].upper()}",
        subdomini=f"pres-a-{emp_a_id.hex[:6]}",
    )
    emp_b = Empresa(
        id=emp_b_id,
        nom="Competidor Pressupost B SL",
        nif=f"B{emp_b_id.hex[:8].upper()}",
        subdomini=f"pres-b-{emp_b_id.hex[:6]}",
    )
    admin_session.add_all([emp_a, emp_b])
    await admin_session.flush()

    boss_a = Usuari(
        id=boss_a_id,
        empresa_id=emp_a_id,
        nom="Marc",
        cognoms="Cap",
        nif=f"BA{boss_a_id.hex[:6].upper()}",
        rol="BOSS",
        pin_hash="dummy",
    )
    eng_a = Usuari(
        id=eng_a_id,
        empresa_id=emp_a_id,
        nom="Laura",
        cognoms="Enginyera",
        nif=f"EA{eng_a_id.hex[:6].upper()}",
        rol="ENGINYER",
        pin_hash="dummy",
    )
    boss_b = Usuari(
        id=boss_b_id,
        empresa_id=emp_b_id,
        nom="Pere",
        cognoms="Altre",
        nif=f"BB{boss_b_id.hex[:6].upper()}",
        rol="BOSS",
        pin_hash="dummy",
    )
    client_a = Client(
        id=client_a_id,
        empresa_id=emp_a_id,
        codi=f"CLI-{client_a_id.hex[:5].upper()}",
        rao_social="Client Pressupost A SL",
        nif="B99887766",
        email="client.a@example.com",
        telefon="+34600111222",
        adreca_fiscal="Carrer Major 1, Lleida",
    )
    admin_session.add_all([boss_a, eng_a, boss_b, client_a])
    await admin_session.commit()

    def _mk_headers(u_id: uuid.UUID, e_id: uuid.UUID, rol: str) -> dict[str, str]:
        tok = jwt.encode(
            {
                "sub": str(u_id),
                "empresa_id": str(e_id),
                "rol": rol,
                "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
            },
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
        )
        return {"Authorization": f"Bearer {tok}", "X-Empresa-ID": str(e_id)}

    headers_boss_a = _mk_headers(boss_a_id, emp_a_id, "BOSS")
    headers_eng_a = _mk_headers(eng_a_id, emp_a_id, "ENGINYER")
    headers_boss_b = _mk_headers(boss_b_id, emp_b_id, "BOSS")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test/api/v1") as client:
        # 1. Crear pressupost amb línies
        res_create = await client.post(
            "/gestio/pressupostos",
            json={
                "client_id": str(client_a_id),
                "numero": f"PRE-{uuid.uuid4().hex[:6].upper()}",
                "titol": "Substitució caldera Baxi",
                "descripcio": "Inclou desmuntatge i posada en marxa",
                "validesa_dies": 15,
                "linies": [
                    {
                        "concepte": "Caldera condensació",
                        "quantitat": 1,
                        "preu_unitari": 1200.0,
                        "tipus_iva": 21.0,
                    },
                    {
                        "concepte": "Mà d'obra tècnica",
                        "quantitat": 4,
                        "preu_unitari": 45.0,
                        "tipus_iva": 21.0,
                    },
                ],
            },
            headers=headers_boss_a,
        )
        assert res_create.status_code == 201, res_create.text
        created = res_create.json()
        pid = created["id"]
        assert created["estat"] == "PENDENT"
        assert created["base_imposable"] == pytest.approx(1380.0, abs=0.01)
        assert created["quota_iva"] == pytest.approx(289.8, abs=0.01)
        assert created["total"] == pytest.approx(1669.8, abs=0.01)
        assert len(created["linies"]) == 2
        assert created["acceptacio_url"]

        # 2. Editar pressupost (5h de mà d'obra -> base 1425, IVA 299.25, total 1724.25)
        res_put = await client.put(
            f"/gestio/pressupostos/{pid}",
            json={
                "titol": "Substitució caldera Baxi Platinum",
                "linies": [
                    {
                        "concepte": "Caldera condensació",
                        "quantitat": 1,
                        "preu_unitari": 1200.0,
                        "tipus_iva": 21.0,
                    },
                    {
                        "concepte": "Mà d'obra tècnica",
                        "quantitat": 5,
                        "preu_unitari": 45.0,
                        "tipus_iva": 21.0,
                    },
                ],
            },
            headers=headers_boss_a,
        )
        assert res_put.status_code == 200, res_put.text
        updated = res_put.json()
        assert updated["titol"] == "Substitució caldera Baxi Platinum"
        assert updated["base_imposable"] == pytest.approx(1425.0, abs=0.01)
        assert updated["quota_iva"] == pytest.approx(299.25, abs=0.01)
        assert updated["total"] == pytest.approx(1724.25, abs=0.01)

        # 3. Descarregar PDF oficial
        res_pdf = await client.get(f"/gestio/pressupostos/{pid}/pdf", headers=headers_boss_a)
        assert res_pdf.status_code == 200, res_pdf.text
        assert res_pdf.headers.get("content-type", "").startswith("application/pdf")
        assert res_pdf.content.startswith(b"%PDF")

        # 4. Intentar enviament per Email (en local sense SMTP retorna mailto_url i acceptacio_url honestos)
        res_email = await client.post(
            f"/gestio/pressupostos/{pid}/enviar-email",
            json={"email_destinatari": "client.a@example.com"},
            headers=headers_boss_a,
        )
        assert res_email.status_code == 200, res_email.text
        email_data = res_email.json()
        assert email_data["email_destinatari"] == "client.a@example.com"
        assert email_data["acceptacio_url"]
        assert email_data["mailto_url"].startswith("mailto:client.a@example.com")

        # 5. Registrar enviament via WhatsApp / Enllaç manual -> queda traçabilitat del canal
        res_reg = await client.post(
            f"/gestio/pressupostos/{pid}/registrar-enviament",
            json={"canal": "WHATSAPP", "destinatari": "+34600111222"},
            headers=headers_boss_a,
        )
        assert res_reg.status_code == 200, res_reg.text
        reg_data = res_reg.json()
        assert reg_data["canal_enviament"] == "WHATSAPP"
        assert reg_data["data_enviament"] is not None

        # 6. RBAC Principi VI: ENGINYER té imports econòmics emmascarats
        res_eng_list = await client.get("/gestio/pressupostos", headers=headers_eng_a)
        assert res_eng_list.status_code == 200, res_eng_list.text
        eng_item = next(p for p in res_eng_list.json() if p["id"] == pid)
        assert eng_item["total"] == 0.0
        assert eng_item["base_imposable"] == 0.0

        res_fitxa_eng = await client.get(f"/gestio/clients/{client_a_id}/fitxa-360", headers=headers_eng_a)
        assert res_fitxa_eng.status_code == 200, res_fitxa_eng.text
        fitxa_eng_p = next(p for p in res_fitxa_eng.json()["pressupostos"] if p["id"] == pid)
        assert fitxa_eng_p["total"] is None

        res_fitxa_boss = await client.get(f"/gestio/clients/{client_a_id}/fitxa-360", headers=headers_boss_a)
        assert res_fitxa_boss.status_code == 200, res_fitxa_boss.text
        fitxa_boss_p = next(p for p in res_fitxa_boss.json()["pressupostos"] if p["id"] == pid)
        assert fitxa_boss_p["total"] == pytest.approx(1724.25, abs=0.01)

        # 7. RLS Aïllament multi-tenant: Empresa B NO pot veure, editar, descarregar ni enviar pressupost d'A
        assert (await client.get(f"/gestio/pressupostos/{pid}", headers=headers_boss_b)).status_code == 404
        assert (
            await client.put(f"/gestio/pressupostos/{pid}", json={"titol": "Hack"}, headers=headers_boss_b)
        ).status_code == 404
        assert (await client.get(f"/gestio/pressupostos/{pid}/pdf", headers=headers_boss_b)).status_code == 404
        assert (
            await client.post(
                f"/gestio/pressupostos/{pid}/enviar-email",
                json={"email_destinatari": "x@y.cat"},
                headers=headers_boss_b,
            )
        ).status_code == 404

        # 8. Portal Públic del Client (sense cap token d'usuari intern ni capçalera tenant)
        token_portal = created["acceptacio_url"].rstrip("/").split("/")[-1]
        res_pub = await client.get(f"/public/pressupostos/{token_portal}")
        assert res_pub.status_code == 200, res_pub.text
        pub_data = res_pub.json()
        assert pub_data["empresa"]["nom"] == "Instal·lacions Lleida SL"
        assert pub_data["client_nom"] == "Client Pressupost A SL"
        assert pub_data["total"] == pytest.approx(1724.25, abs=0.01)
        assert len(pub_data["linies"]) == 2

        res_pub_pdf = await client.get(f"/public/pressupostos/{token_portal}/pdf")
        assert res_pub_pdf.status_code == 200
        assert res_pub_pdf.content.startswith(b"%PDF")

        res_pub_bad = await client.get("/public/pressupostos/token-invalid-123")
        assert res_pub_bad.status_code in (400, 403, 404)

        res_pub_accept = await client.post(
            f"/public/pressupostos/{token_portal}/respondre",
            json={"accio": "APROVAR", "comentari": "Conforme"},
        )
        assert res_pub_accept.status_code == 200, res_pub_accept.text
        assert res_pub_accept.json()["estat"] == "APROVAT"

        res_after_accept = await client.get(f"/gestio/pressupostos/{pid}", headers=headers_boss_a)
        assert res_after_accept.status_code == 200
        after_data = res_after_accept.json()
        assert after_data["estat"] == "APROVAT"
        assert (after_data.get("token_signatura") or "").startswith("PORTAL-APROV-")

        # 9. Conversió del pressupost aprovat a Ordre de Treball (OT)
        res_ot = await client.post(
            f"/gestio/pressupostos/{pid}/convertir-ot",
            json={},
            headers=headers_boss_a,
        )
        assert res_ot.status_code == 201, res_ot.text
        ot_data = res_ot.json()
        assert ot_data["status"] == "convertit"
        assert ot_data["ordre_treball_id"]
        assert ot_data["codi_ot"].startswith("OT-")

