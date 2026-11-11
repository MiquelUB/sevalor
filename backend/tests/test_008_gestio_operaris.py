import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.core.config import settings
from app.main import app
from app.models.models import Empresa, Usuari


@pytest.fixture
def boss_token(admin_session):
    # Generem un UUID per a l'empresa
    empresa_id = str(uuid.uuid4())

    payload = {
        "sub": str(uuid.uuid4()),
        "rol": "BOSS",
        "empresa_id": empresa_id,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15)
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return token, empresa_id

@pytest.fixture
def headers(boss_token):
    token, _ = boss_token
    return {"Authorization": f"Bearer {token}"}

@pytest.mark.asyncio
async def test_alta_operari_nou(admin_session, headers, boss_token):
    _, empresa_id = boss_token

    # Inserim l'empresa de prova via BD manual per poder complir amb les Foreign Keys
    admin_session.add(Empresa(
        id=uuid.UUID(empresa_id), nom='Test Company', nif='NIF' + str(uuid.uuid4())[:8], subdomini='sub' + str(uuid.uuid4())[:6], pla_subscripcio='STARTER', estat_pagament='ACTIU'
    ))
    await admin_session.flush()
    await admin_session.flush()

    payload = {
        "nif": "12345678Z",
        "nom": "Joan",
        "cognoms": "Pérez",
        "telefon": "+34600100200",
        "especialitat": "SISTEMES_REG",
        "cost_hora_eur": 25.50
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/api/v1/gestio/operaris", json=payload, headers=headers)

        assert res.status_code == 201, f"Error: {res.text}"
        data = res.json()
        assert data["nif"] == payload["nif"]
        assert data["nom"] == payload["nom"]
        assert data["estat"] == "ACTIU"
        assert data["rol"] == "OPERARI"
        assert "pin_hash" not in data # Seguretat: no retornar el PIN

        # Validem que s'ha desat a la DB
        result = await admin_session.execute(text("SELECT nif, pin_hash, telefon FROM usuaris WHERE id = :id"), {"id": data["id"]})
        row = result.fetchone()
        assert row is not None
        assert row.nif == "12345678Z"
        assert row.pin_hash is not None # El PIN s'ha de generar i hashear
        assert row.telefon == "+34600100200"

@pytest.mark.asyncio
async def test_reset_pin_operari(admin_session, headers, boss_token):
    _, empresa_id = boss_token

    # 1. Crear empresa
    admin_session.add(Empresa(
        id=uuid.UUID(empresa_id), nom='Test Reset', nif='RES' + str(uuid.uuid4())[:8], subdomini='sub' + str(uuid.uuid4())[:6], pla_subscripcio='STARTER', estat_pagament='ACTIU'
    ))
    await admin_session.flush()

    # 2. Crear operari bloquejat
    operari_id = str(uuid.uuid4())
    admin_session.add(Usuari(
        id=uuid.UUID(operari_id), empresa_id=uuid.UUID(empresa_id), nif='RESET123', nom='Maria', rol='OPERARI', pin_bloquejat=True, intents_pin_fallits=4
    ))
    await admin_session.flush()
    await admin_session.flush()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post(f"/api/v1/gestio/operaris/{operari_id}/reset-pin", headers=headers)
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["missatge"] == "Nou PIN generat i tramès per SMS"
        assert data["pin_bloquejat"] is False
        assert data["intents_pin_fallits"] == 0

        # Validem a BD que els intents s'han posat a 0
        result = await admin_session.execute(text("SELECT pin_bloquejat, intents_pin_fallits FROM usuaris WHERE id = :id"), {"id": operari_id})
        row = result.fetchone()
        assert row.pin_bloquejat is False
        assert row.intents_pin_fallits == 0


@pytest.mark.asyncio
async def test_editar_operari_boss_i_secretaria(admin_session, boss_token):
    boss_jwt, empresa_id = boss_token

    admin_session.add(Empresa(
        id=uuid.UUID(empresa_id),
        nom='Test Editar Operari',
        nif='EDT' + str(uuid.uuid4())[:8],
        subdomini='sub' + str(uuid.uuid4())[:6],
        pla_subscripcio='STARTER',
        estat_pagament='ACTIU'
    ))
    await admin_session.flush()

    operari_id = str(uuid.uuid4())
    admin_session.add(Usuari(
        id=uuid.UUID(operari_id),
        empresa_id=uuid.UUID(empresa_id),
        nif='47821948B',
        nom='Jordi',
        cognoms='Soler',
        telefon='+34611223344',
        rol='OPERARI',
        especialitat='SISTEMES_REG',
        cost_hora_eur=22.50,
        estat='ACTIU',
    ))
    await admin_session.flush()

    # 1. Edició amb rol BOSS
    boss_headers = {"Authorization": f"Bearer {boss_jwt}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res_boss = await ac.put(
            f"/api/v1/gestio/operaris/{operari_id}",
            json={
                "nom": "Jordi Miquel",
                "cognoms": "Soler Vila",
                "telefon": "+34699887766",
                "rol": "CAP_DE_COLLA",
                "especialitat": "ELECTRICITAT",
                "estat_operatiu": "EN_FEINA",
                "cost_hora_eur": 28.00,
                "carnet_conduir": "B+E",
                "carnet_caducitat": "2031-06-30",
                "prl_certificat_vigencia": "2028-12-31",
            },
            headers=boss_headers,
        )
        assert res_boss.status_code == 200, res_boss.text
        data_boss = res_boss.json()
        assert data_boss["nom"] == "Jordi Miquel"
        assert data_boss["rol"] == "CAP_DE_COLLA"
        assert data_boss["especialitat"] == "ELECTRICITAT"
        assert data_boss["cost_hora_eur"] == 28.00

        # 2. Edició amb rol SECRETARIA
        secretaria_jwt = jwt.encode(
            {
                "sub": str(uuid.uuid4()),
                "rol": "SECRETARIA",
                "empresa_id": empresa_id,
                "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
            },
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
        )
        sec_headers = {"Authorization": f"Bearer {secretaria_jwt}"}
        res_sec = await ac.put(
            f"/api/v1/gestio/operaris/{operari_id}",
            json={
                "telefon": "+34655443322",
                "cost_hora_eur": 30.50,
                "estat_operatiu": "DISPONIBLE",
            },
            headers=sec_headers,
        )
        assert res_sec.status_code == 200, res_sec.text
        data_sec = res_sec.json()
        assert data_sec["telefon"] == "+34655443322"
        assert data_sec["cost_hora_eur"] == 30.50

        # 3. Veto d'ENGINYER (403 Forbidden)
        enginyer_jwt = jwt.encode(
            {
                "sub": str(uuid.uuid4()),
                "rol": "ENGINYER",
                "empresa_id": empresa_id,
                "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
            },
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
        )
        eng_headers = {"Authorization": f"Bearer {enginyer_jwt}"}
        res_eng = await ac.put(
            f"/api/v1/gestio/operaris/{operari_id}",
            json={"cost_hora_eur": 50.00},
            headers=eng_headers,
        )
        assert res_eng.status_code == 403, res_eng.text


@pytest.mark.asyncio
async def test_metrics_operaris_i_fitxa_360(admin_session, boss_token):
    boss_jwt, empresa_id = boss_token
    emp_uuid = uuid.UUID(empresa_id)

    admin_session.add(Empresa(
        id=emp_uuid,
        nom='Test Metrics 360',
        nif='MET' + str(uuid.uuid4())[:8],
        subdomini='sub' + str(uuid.uuid4())[:6],
        pla_subscripcio='STARTER',
        estat_pagament='ACTIU'
    ))
    await admin_session.flush()

    operari_id = str(uuid.uuid4())
    admin_session.add(Usuari(
        id=uuid.UUID(operari_id),
        empresa_id=emp_uuid,
        nif='99887766K',
        nom='Carles',
        cognoms='Roca',
        telefon='+34677889900',
        rol='OPERARI',
        especialitat='OBRA_CIVIL',
        cost_hora_eur=24.00,
        estat='ACTIU',
    ))
    await admin_session.flush()

    boss_headers = {"Authorization": f"Bearer {boss_jwt}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Obtenir mètriques de capçalera (Zero Mock)
        res_m = await ac.get("/api/v1/gestio/operaris/metrics", headers=boss_headers)
        assert res_m.status_code == 200, res_m.text
        m = res_m.json()
        assert m["total_operaris"] >= 1
        assert "compliment_horari_avui_percent" in m
        assert "valoracio_mitjana_clients" in m
        assert "km_conduits_mes" in m
        assert "total_eines_assignades" in m

        # 2. Obtenir eines de l'operari
        res_eines = await ac.get(f"/api/v1/gestio/operaris/{operari_id}/eines", headers=boss_headers)
        assert res_eines.status_code == 200
        assert isinstance(res_eines.json(), list)

        # 3. Obtenir incidències de l'operari
        res_inc = await ac.get(f"/api/v1/gestio/operaris/{operari_id}/incidencies", headers=boss_headers)
        assert res_inc.status_code == 200
        assert isinstance(res_inc.json(), list)

        # 4. Obtenir feines de l'operari
        res_feines = await ac.get(f"/api/v1/gestio/operaris/{operari_id}/feines", headers=boss_headers)
        assert res_feines.status_code == 200
        assert isinstance(res_feines.json(), list)

        # 5. Obtenir shifts amb rol BOSS (200)
        res_shifts = await ac.get(f"/api/v1/gestio/operaris/{operari_id}/shifts", headers=boss_headers)
        assert res_shifts.status_code == 200
        assert isinstance(res_shifts.json(), list)

        # 6. Veto d'Enginyer sobre shifts (403)
        eng_jwt = jwt.encode(
            {
                "sub": str(uuid.uuid4()),
                "rol": "ENGINYER",
                "empresa_id": empresa_id,
                "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
            },
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
        )
        res_veto = await ac.get(f"/api/v1/gestio/operaris/{operari_id}/shifts", headers={"Authorization": f"Bearer {eng_jwt}"})
        assert res_veto.status_code == 403


@pytest.mark.asyncio
async def test_ocr_operari_multiformat_i_alertes_copilot():
    """Valida que l'OCR d'operari llegeix .md, .pdf, .jpg, .png, .txt, .doc, .docx,
    genera alertes Copilot de caducitat (caducat o <= 30 dies) i informa de manca de documents sense bloquejar l'alta.
    """
    import io
    import zipfile
    from datetime import date

    from app.services.ocr_service import (
        consolidar_i_validar_ocr_operari,
        processar_ocr_document_operari,
    )

    data_ref = date(2026, 11, 11)

    # 1. Fitxer .md (DNI)
    dni_md = (
        "# DNI ESPANYA\n"
        "**Cognoms / Apellidos:** Soler Vila\n"
        "**Nom / Nombre:** Jordi\n"
        "**NIF:** 47821948B\n"
        "**Data de naixement:** 14/05/1988\n"
        "**Validesa:** 20/11/2026\n"
    ).encode("utf-8")
    res_md = await processar_ocr_document_operari(dni_md, filename="dni_jordi.md")
    assert res_md["nif"] == "47821948B"
    assert res_md["nom"] == "Jordi"
    assert res_md["cognoms"] == "Soler Vila"
    assert res_md["dni_caducitat"] == "2026-11-20"

    # 2. Fitxer .txt (Carnet de conduir a menys d'un mes de caducar: 15 dies)
    carnet_txt = (
        "PERMÍS DE CONDUIR DGT\n"
        "1. Soler Vila\n"
        "2. Jordi\n"
        "4d. NIF: 47821948B\n"
        "9. Categories: B, B+E, C\n"
        "4b. Caducitat del carnet: 26/11/2026\n"
        "Observacions: Codi 95 CAP VIGENT\n"
    ).encode("utf-8")
    res_txt = await processar_ocr_document_operari(carnet_txt, filename="carnet_dgt.txt")
    assert res_txt["tipus_document"] == "CARNET_CONDUIR"
    assert res_txt["carnet_conduir"] == "C"
    assert res_txt["carnet_caducitat"] == "2026-11-26"
    assert res_txt["te_cap_vigent"] is True

    # 3. Fitxer .docx (ZIP amb word/document.xml - Contracte RRHH)
    docx_buf = io.BytesIO()
    with zipfile.ZipFile(docx_buf, "w") as zf:
        xml_content = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            "<w:body>"
            "<w:p><w:r><w:t>CONTRACTE LABORAL RRHH - NIF: 47821948B</w:t></w:r></w:p>"
            "<w:p><w:r><w:t>Telèfon: +34612345678 | Email: jordi.soler@campopro.cat</w:t></w:r></w:p>"
            "<w:p><w:r><w:t>Especialitat: ELECTRICITAT | Cost/hora: 26.50 EUR</w:t></w:r></w:p>"
            "</w:body></w:document>"
        )
        zf.writestr("word/document.xml", xml_content)
    res_docx = await processar_ocr_document_operari(docx_buf.getvalue(), filename="contracte.docx")
    assert res_docx["telefon"] == "+34612345678"
    assert res_docx["email"] == "jordi.soler@campopro.cat"
    assert res_docx["especialitat"] == "ELECTRICITAT"
    assert res_docx["cost_hora_eur"] == 26.50

    # 4. Fitxer .doc i .jpg/.png amb metadates incrustades
    doc_bytes = b"FITXA OPERARI .DOC\nNom: Jordi\nCognoms: Soler Vila\nNIF: 47821948B\n"
    res_doc = await processar_ocr_document_operari(doc_bytes, filename="fitxa.doc")
    assert res_doc["nif"] == "47821948B"

    jpg_bytes = b"\xff\xd8\xff\xe0JFIF\x00DNI Titular: Jordi Soler Vila NIF: 47821948B Caducitat: 2026-11-20"
    res_jpg = await processar_ocr_document_operari(jpg_bytes, filename="dni_scan.jpg")
    assert res_jpg["nif"] == "47821948B"

    png_bytes = b"\x89PNG\r\n\x1a\nDNI Titular: Jordi Soler Vila NIF: 47821948B Caducitat: 2026-11-20"
    res_png = await processar_ocr_document_operari(png_bytes, filename="dni_scan.png")
    assert res_png["nif"] == "47821948B"

    # 5. Consolidació SENSE Certificat PRL: ha d'alertar de carnet a punt de caducar (<=30 dies)
    # i informar de manca de CERTIFICAT_PRL SENSE bloquejar l'alta!
    consolidat = consolidar_i_validar_ocr_operari([res_md, res_txt, res_docx], data_referencia=data_ref)
    assert consolidat["apte_alta_operari"] is True
    assert consolidat["bloqueja_alta"] is False
    assert "CERTIFICAT_PRL" in consolidat["documents_pendents"]

    codis_alertes = [a["codi"] for a in consolidat["alertes_copilot"]]
    assert "CARNET_PROPER_CADUCAR" in codis_alertes
    assert "DNI_PROPER_CADUCAR" in codis_alertes
    assert "MANCA_DOCUMENTACIO_RRHH" in codis_alertes
    assert all(a["bloquejant_alta"] is False for a in consolidat["alertes_copilot"])

    # 6. Escenari amb Carnet CADUCAT (< data_ref): alerta CRITICAL però no bloqueja l'alta
    carnet_caducat = await processar_ocr_document_operari(
        b"PERMIS DE CONDUIR\nNIF: 47821948B\nCarnet: B\nCaducitat del carnet: 01/10/2026\n",
        filename="carnet_caducat.txt",
    )
    cons_cad = consolidar_i_validar_ocr_operari([carnet_caducat], data_referencia=data_ref)
    assert cons_cad["bloqueja_alta"] is False
    assert any(a["codi"] == "CARNET_CADUCAT" and a["severitat"] == "CRITICAL" for a in cons_cad["alertes_copilot"])




