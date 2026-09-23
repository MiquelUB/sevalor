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
from sqlalchemy import select

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
