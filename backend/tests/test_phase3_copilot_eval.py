"""
Tests d'Avaluació de Fase 3: Copilot Agent amb Tool Calling i Fallback Sobirà
(Spec 012 / SDD SEVALOR v4.0).

Cobreix:
- TEST-F3-01: Tool calling get_real_stock (Article 'Cable 6mm²' amb 327 unitats -> resposta dinàmica i log BD).
- TEST-F3-02: Tool calling get_closest_vehicle (Càlcul Haversine i selecció del vehicle realment més proper).
- TEST-F3-03: Veto financer per a ENGINYER (HTTP 403 i registre denegat_per_rol).
- TEST-F3-04: Copilot inaccessible per a OPERARI (HTTP 403).
- TEST-F3-05: Fallback sobirà quan no hi ha node Whisper/IA (sense mock data).
"""

import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.config import settings
from app.main import app
from app.models.models import (
    Article,
    Client,
    ConsultaXatCopilot,
    Empresa,
    EstocMagatzem,
    Magatzem,
    OrdreTreball,
    Usuari,
    Vehicle,
)
from app.workers.tasks import transcriure_audio_task


def generar_token(usuari_id: uuid.UUID, empresa_id: uuid.UUID, rol: str) -> str:
    """Genera un token JWT vàlid per a proves amb el rol i empresa indicats."""
    payload = {
        "sub": str(usuari_id),
        "rol": rol,
        "empresa_id": str(empresa_id),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


@pytest.mark.asyncio
async def test_f3_01_tool_calling_stock_real(admin_session, boss_token):
    """
    TEST-F3-01: Consulta d'estoc en temps real via Tool Calling.
    Verifica que l'agent selecciona 'get_real_stock', consulta la BD real,
    retorna 327 unitats i guarda el log d'auditoria amb tool_name i tool_result.
    """
    token_jwt, empresa_id_str = boss_token
    empresa_id = uuid.UUID(empresa_id_str)
    decoded = jwt.decode(token_jwt, options={"verify_signature": False})
    usuari_id = uuid.UUID(decoded["sub"])

    # 1. Crear entorn de negoci a la BD
    empresa = Empresa(
        id=empresa_id,
        nom="Instal·lacions Vallès SL",
        nif="B" + uuid.uuid4().hex[:8].upper(),
        subdomini="ivalles-" + uuid.uuid4().hex[:5],
        pla_subscripcio="ENTERPRISE",
        estat_pagament="ACTIU",
        vertical="SEVALOR",
    )
    admin_session.add(empresa)
    await admin_session.flush()

    usuari = Usuari(
        id=usuari_id,
        empresa_id=empresa_id,
        nom="Joan",
        cognoms="Directe",
        nif="47890123A",
        rol="BOSS",
        estat="ACTIU",
    )
    admin_session.add(usuari)

    magatzem = Magatzem(
        id=uuid.uuid4(),
        empresa_id=empresa_id,
        nom="Magatzem Central Sabadell",
        tipus="CENTRAL",
    )
    admin_session.add(magatzem)

    article = Article(
        id=uuid.uuid4(),
        empresa_id=empresa_id,
        referencia_inventari="CAB-6MM-NEGRE",
        nom="Cable 6mm²",
        familia="ELECTRICITAT",
        unitat_mesura="METRES",
        preu_cost=1.85,
        preu_venda=3.50,
        estoc_minim=50.0,
        estoc_optim=500.0,
    )
    admin_session.add(article)
    await admin_session.flush()

    # Inserim exactament 327 unitats físiques sense reserves
    estoc = EstocMagatzem(
        id=uuid.uuid4(),
        empresa_id=empresa_id,
        magatzem_id=magatzem.id,
        article_id=article.id,
        quantitat_fisica=327.0,
        quantitat_virtual_reservada=0.0,
    )
    admin_session.add(estoc)
    await admin_session.flush()

    headers = {
        "Authorization": f"Bearer {token_jwt}",
        "X-Empresa-ID": str(empresa_id),
    }

    # 2. Executar la crida a l'agent Copilot
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post(
            "/api/v1/gestio/copilot/xat",
            json={"pregunta": "Quant de stock ens queda de Cable 6mm²?"},
            headers=headers,
        )

    assert res.status_code == 200, f"Error en la consulta: {res.text}"
    data = res.json()

    # 3. Assertions sobre la resposta
    assert data["tool_utilitzada"] == "get_real_stock"
    assert "327" in data["resposta"] or (data.get("tool_resultat") and data["tool_resultat"].get("total_disponible") == 327.0)

    # 4. Assertions d'auditoria a la base de dades
    stmt_log = select(ConsultaXatCopilot).where(
        ConsultaXatCopilot.empresa_id == empresa_id,
        ConsultaXatCopilot.usuari_id == usuari_id,
    ).order_by(ConsultaXatCopilot.created_at.desc())
    res_log = await admin_session.execute(stmt_log)
    log_db = res_log.scalars().first()

    assert log_db is not None, "El registre de consulta a la BD no s'ha creat"
    assert log_db.tool_name == "get_real_stock"
    assert log_db.tool_result is not None
    assert log_db.tool_result.get("total_disponible") == 327.0


@pytest.mark.asyncio
async def test_f3_02_tool_calling_vehicle_proper(admin_session, boss_token):
    """
    TEST-F3-02: Selecció autònoma del vehicle més proper mitjançant fórmula Haversine.
    Configura 2 vehicles reals a la BD (Vehicle A a 0.4 km, Vehicle B a 25 km).
    Verifica que l'agent selecciona 'get_closest_vehicle' i escull el Vehicle A.
    """
    token_jwt, empresa_id_str = boss_token
    empresa_id = uuid.UUID(empresa_id_str)
    decoded = jwt.decode(token_jwt, options={"verify_signature": False})
    usuari_id = uuid.UUID(decoded["sub"])

    empresa = Empresa(
        id=empresa_id,
        nom="Transports i Serveis SL",
        nif="B" + uuid.uuid4().hex[:8].upper(),
        subdomini="trans-" + uuid.uuid4().hex[:5],
        pla_subscripcio="ENTERPRISE",
        estat_pagament="ACTIU",
        vertical="SEVALOR",
    )
    admin_session.add(empresa)
    await admin_session.flush()

    usuari = Usuari(
        id=usuari_id,
        empresa_id=empresa_id,
        nom="Carles",
        cognoms="Logística",
        nif="38112233B",
        rol="BOSS",
        estat="ACTIU",
    )
    admin_session.add(usuari)

    client = Client(
        id=uuid.uuid4(),
        empresa_id=empresa_id,
        codi="CLI-001",
        rao_social="Client Proximitat",
        nif="B" + uuid.uuid4().hex[:8].upper(),
    )
    admin_session.add(client)

    # Vehicle A: a Barcelona centre (prop de 41.3850, 2.1730) -> a ~0.15 km
    vehicle_a = Vehicle(
        id=uuid.uuid4(),
        empresa_id=empresa_id,
        matricula="1111-AAA",
        marca="Renault",
        model="Kangoo E-Tech",
        tipus="ELECTRIC",
        estat="OPERATIU",
    )
    admin_session.add(vehicle_a)

    # Vehicle B: a Mataró -> a ~28 km
    vehicle_b = Vehicle(
        id=uuid.uuid4(),
        empresa_id=empresa_id,
        matricula="2222-BBB",
        marca="Ford",
        model="Transit Custom",
        tipus="THERMIC",
        estat="OPERATIU",
    )
    admin_session.add(vehicle_b)
    await admin_session.flush()

    # OT per posicionar Vehicle A prop de [41.3850, 2.1730]
    ot_a = OrdreTreball(
        id=uuid.uuid4(),
        empresa_id=empresa_id,
        codi="OT-PROX-A",
        client_id=client.id,
        titol="Manteniment Plaça Catalunya",
        adreca="41.3860, 2.1740",
        estat="EN_CURS",
        vehicle_id=vehicle_a.id,
    )
    admin_session.add(ot_a)

    # OT per posicionar Vehicle B lluny
    ot_b = OrdreTreball(
        id=uuid.uuid4(),
        empresa_id=empresa_id,
        codi="OT-PROX-B",
        client_id=client.id,
        titol="Instal·lació Polígon Mataró",
        adreca="41.5500, 2.4400",
        estat="EN_CURS",
        vehicle_id=vehicle_b.id,
    )
    admin_session.add(ot_b)
    await admin_session.flush()

    headers = {
        "Authorization": f"Bearer {token_jwt}",
        "X-Empresa-ID": str(empresa_id),
    }

    # 1. Comprovar l'endpoint dedicat de flota propers
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res_flota = await ac.get(
            "/api/v1/gestio/flota/propers?lat=41.3850&lng=2.1730&limit=5",
            headers=headers,
        )
        assert res_flota.status_code == 200
        propers = res_flota.json()
        assert len(propers) >= 2
        assert propers[0]["matricula"] == "1111-AAA"
        assert propers[0]["distancia_km"] < 1.0
        assert propers[1]["matricula"] == "2222-BBB"
        assert propers[1]["distancia_km"] > 20.0

        # 2. Comprovar el Copilot Xat amb Tool Calling
        res_xat = await ac.post(
            "/api/v1/gestio/copilot/xat",
            json={"pregunta": "Quin vehicle està més a prop de l'obra a 41.3850, 2.1730?"},
            headers=headers,
        )
        assert res_xat.status_code == 200
        data_xat = res_xat.json()

        assert data_xat["tool_utilitzada"] == "get_closest_vehicle"
        assert "1111-AAA" in data_xat["resposta"]
        assert data_xat["tool_resultat"]["vehicle_mes_proper"]["matricula"] == "1111-AAA"

    # 3. Validar auditoria a la BD
    stmt_log = select(ConsultaXatCopilot).where(
        ConsultaXatCopilot.empresa_id == empresa_id,
        ConsultaXatCopilot.usuari_id == usuari_id,
    ).order_by(ConsultaXatCopilot.created_at.desc())
    res_log = await admin_session.execute(stmt_log)
    log_db = res_log.scalars().first()

    assert log_db is not None
    assert log_db.tool_name == "get_closest_vehicle"
    assert log_db.tool_result["vehicle_mes_proper"]["matricula"] == "1111-AAA"


@pytest.mark.asyncio
async def test_f3_03_veto_financer(admin_session):
    """
    TEST-F3-03: Veto financer estricte per al rol ENGINYER (HTTP 403 Forbidden).
    La consulta financera ha de ser blocada i auditada a la BD amb denegat_per_rol=True.
    """
    empresa_id = uuid.uuid4()
    enginyer_id = uuid.uuid4()

    empresa = Empresa(
        id=empresa_id,
        nom="Enginyeria Vallès SL",
        nif="B" + uuid.uuid4().hex[:8].upper(),
        subdomini="eng-" + uuid.uuid4().hex[:5],
        pla_subscripcio="PRO",
        estat_pagament="ACTIU",
        vertical="SEVALOR",
    )
    admin_session.add(empresa)

    usuari = Usuari(
        id=enginyer_id,
        empresa_id=empresa_id,
        nom="Pau",
        cognoms="Tècnic",
        nif="55443322C",
        rol="ENGINYER",
        estat="ACTIU",
    )
    admin_session.add(usuari)
    await admin_session.flush()

    token_enginyer = generar_token(enginyer_id, empresa_id, "ENGINYER")
    headers = {
        "Authorization": f"Bearer {token_enginyer}",
        "X-Empresa-ID": str(empresa_id),
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post(
            "/api/v1/gestio/copilot/xat",
            json={"pregunta": "Quant cobrem per hora als operaris en les tarifes?"},
            headers=headers,
        )

    assert res.status_code == 403
    assert "seguretat" in res.json().get("detail", "").lower()

    # Comprovar registre denegat a la BD
    stmt_log = select(ConsultaXatCopilot).where(
        ConsultaXatCopilot.empresa_id == empresa_id,
        ConsultaXatCopilot.usuari_id == enginyer_id,
    ).order_by(ConsultaXatCopilot.created_at.desc())
    res_log = await admin_session.execute(stmt_log)
    log_db = res_log.scalars().first()

    assert log_db is not None
    assert log_db.denegat_per_rol is True


@pytest.mark.asyncio
async def test_f3_04_copilot_inaccessible_operari(admin_session):
    """
    TEST-F3-04: L'operari té prohibit l'accés al copilot de gestió (/gestio/copilot).
    Ha de rebre HTTP 403 Forbidden.
    """
    empresa_id = uuid.uuid4()
    operari_id = uuid.uuid4()

    empresa = Empresa(
        id=empresa_id,
        nom="Camp Serveis SL",
        nif="B" + uuid.uuid4().hex[:8].upper(),
        subdomini="camp-" + uuid.uuid4().hex[:5],
        pla_subscripcio="STARTER",
        estat_pagament="ACTIU",
        vertical="SEVALOR",
    )
    admin_session.add(empresa)

    usuari = Usuari(
        id=operari_id,
        empresa_id=empresa_id,
        nom="Manel",
        cognoms="Camp",
        nif="99887766D",
        rol="OPERARI",
        estat="ACTIU",
    )
    admin_session.add(usuari)
    await admin_session.flush()

    token_operari = generar_token(operari_id, empresa_id, "OPERARI")
    headers = {
        "Authorization": f"Bearer {token_operari}",
        "X-Empresa-ID": str(empresa_id),
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post(
            "/api/v1/gestio/copilot/xat",
            json={"pregunta": "Com puc consultar l'estoc del magatzem?"},
            headers=headers,
        )

    assert res.status_code == 403


def test_f3_05_fallback_sense_ia():
    """
    TEST-F3-05: Comportament quan el node Whisper/IA no està operatiu.
    La tasca Celery ha de retornar el missatge de fallback sobirà sense cap mock string ni caiguda del procés.
    """
    empresa_id = str(uuid.uuid4())
    fake_path = "/tmp/audio_inexistent_123.wav"

    res = transcriure_audio_task(fake_path, empresa_id)

    assert isinstance(res, dict)
    assert res.get("estat") == "COMPLETADO"
    assert "node Whisper inactiu" in res.get("transcripcio", "")
    # Assegurar absència de valors mock hardcodejats
    assert "mock" not in res.get("transcripcio", "").lower()
    assert "fals" not in res.get("transcripcio", "").lower()
