"""Tests d'integració i unitaris de l'OCR d'Alta d'Operari (Spec 008).

Valida:
1. Lectura multiformat (.md, .pdf, .jpg, .png, .txt, .doc, .docx).
2. Emmagatzematge sempre al disc dur del client (SovereignStorageGateway).
3. Alertes del Copilot per caducitat de carnets i PRL (caducats o a <= 30 dies / 1 mes de caducar).
4. Avís de manca de documents NO bloquejant en l'alta de l'operari.
"""

import io
import uuid
import zipfile
from datetime import date, timedelta

import pytest

from app.models.models import Usuari
from app.services.ocr_service import (
    consolidar_i_validar_ocr_operari,
    processar_dni_ocr,
    processar_ocr_document_operari,
)


@pytest.mark.asyncio
async def test_ocr_operari_tots_els_formats_md_pdf_jpg_png_txt_doc_docx():
    """Comprova que el motor OCR llegeix arxius .md, .pdf, .jpg, .png, .txt, .doc i .docx."""
    # 1. Markdown (.md) - DNI
    dni_md = (
        "# DNI ESPANYA\n"
        "**Cognoms / Apellidos:** Soler Vila\n"
        "**Nom / Nombre:** Jordi\n"
        "**NIF:** 47821948B\n"
        "**Data de naixement:** 14/05/1988\n"
        "**Validesa:** 20/11/2026\n"
    ).encode("utf-8")
    res_md = await processar_ocr_document_operari(dni_md, filename="dni_jordi.md")
    assert res_md["status"] == "EXTRET_AUTOMATIC"
    assert res_md["nif"] == "47821948B"
    assert res_md["nom"] == "Jordi"
    assert res_md["cognoms"] == "Soler Vila"
    assert res_md["data_naixement"] == "1988-05-14"
    assert res_md["dni_caducitat"] == "2026-11-20"

    # 2. Text (.txt) - Permís de conduir C + CAP
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

    # 3. Word (.docx) - Contracte RRHH
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

    # 4. Word clàssic (.doc) - Certificat PRL
    doc_bytes = (
        "CERTIFICAT PRL RECURS PREVENTIU 60H i OPERADOR DE GRUA CAMIÓ\n"
        "Treballador: Jordi Soler Vila\n"
        "NIF: 47821948B\n"
        "Vigència PRL: 05/12/2026\n"
    ).encode("utf-8")
    res_doc = await processar_ocr_document_operari(doc_bytes, filename="certificat_prl.doc")
    assert res_doc["tipus_document"] == "CERTIFICAT_PRL"
    assert "OPERADOR_GRUA_CAMIO" in res_doc["certificats_prl"]
    assert "PRL_60H_RECURS_PREVENTIU" in res_doc["certificats_prl"]
    assert res_doc["prl_certificat_vigencia"] == "2026-12-05"

    # 5. PDF real generat amb PyMuPDF (.pdf)
    import fitz

    pdf_doc = fitz.open()
    page = pdf_doc.new_page()
    page.insert_text(
        (50, 72),
        "DOCUMENT NACIONAL D'IDENTITAT\nTitular: Jordi Soler Vila\nNIF: 47821948B\nCaducitat: 15/06/2030",
    )
    pdf_bytes = pdf_doc.tobytes()
    res_pdf = await processar_ocr_document_operari(pdf_bytes, filename="dni_oficial.pdf")
    assert res_pdf["nif"] == "47821948B"
    assert res_pdf["nom"] == "Jordi"
    assert res_pdf["cognoms"] == "Soler Vila"
    assert res_pdf["dni_caducitat"] == "2030-06-15"

    # 6. Imatges (.jpg i .png)
    jpg_bytes = b"\xff\xd8\xff\xe0JFIF\x00DNI Titular: Jordi Soler Vila NIF: 47821948B Caducitat: 20/11/2026"
    res_jpg = await processar_ocr_document_operari(jpg_bytes, filename="dni_foto.jpg")
    assert res_jpg["nif"] == "47821948B"

    png_bytes = b"\x89PNG\r\n\x1a\nDNI Titular: Jordi Soler Vila NIF: 47821948B Caducitat: 20/11/2026"
    res_png = await processar_ocr_document_operari(png_bytes, filename="dni_foto.png")
    assert res_png["nif"] == "47821948B"


@pytest.mark.asyncio
async def test_alertes_copilot_caducitat_i_manca_documents_no_bloquejant():
    """Comprova que el Copilot alerta quan el carnet/PRL està caducat o a <= 30 dies (un mes) de caducar,
    i informa de la manca de documents sense bloquejar mai l'alta de l'operari.
    """
    data_ref = date(2026, 11, 11)

    # A. Només s'adjunta DNI i Carnet de Conduir que caduca d'aquí a 15 dies (<= 30 dies), però FALTA el PRL
    doc_dni = await processar_ocr_document_operari(
        b"DNI\nNom: Marc\nCognoms: Puig Ferrer\nNIF: 39841209K\nValidesa: 2031-05-10\n",
        filename="dni.md",
    )
    doc_carnet = await processar_ocr_document_operari(
        b"CARNET DE CONDUIR\nNIF: 39841209K\nCategories: B, B+E\nCaducitat del carnet: 26/11/2026\n",
        filename="carnet.txt",
    )

    consolidat = consolidar_i_validar_ocr_operari([doc_dni, doc_carnet], data_referencia=data_ref)
    assert consolidat["nif"] == "39841209K"
    assert consolidat["carnet_conduir"] == "B+E"
    assert consolidat["carnet_caducitat"] == "2026-11-26"

    # La manca del certificat PRL s'informa però NO bloqueja l'alta
    assert "CERTIFICAT_PRL" in consolidat["documents_pendents"]
    assert consolidat["apte_alta_operari"] is True
    assert consolidat["bloqueja_alta"] is False

    alertes_map = {a["codi"]: a for a in consolidat["alertes_copilot"]}
    assert "CARNET_PROPER_CADUCAR" in alertes_map
    assert alertes_map["CARNET_PROPER_CADUCAR"]["severitat"] == "WARNING"
    assert alertes_map["CARNET_PROPER_CADUCAR"]["dies_restants"] == 15
    assert alertes_map["CARNET_PROPER_CADUCAR"]["bloquejant_alta"] is False

    assert "MANCA_DOCUMENTACIO_RRHH" in alertes_map
    assert alertes_map["MANCA_DOCUMENTACIO_RRHH"]["bloquejant_alta"] is False

    # B. Carnet CADUCAT (< data_ref): genera alerta CRITICAL però tampoc bloqueja l'alta a RRHH
    doc_carnet_caducat = await processar_ocr_document_operari(
        b"CARNET DE CONDUIR\nNIF: 39841209K\nCategories: C\nCaducitat del carnet: 01/11/2026\n",
        filename="carnet_caducat.md",
    )
    cons_caducat = consolidar_i_validar_ocr_operari([doc_dni, doc_carnet_caducat], data_referencia=data_ref)
    assert cons_caducat["apte_alta_operari"] is True
    assert cons_caducat["bloqueja_alta"] is False
    alertes_cad = {a["codi"]: a for a in cons_caducat["alertes_copilot"]}
    assert "CARNET_CADUCAT" in alertes_cad
    assert alertes_cad["CARNET_CADUCAT"]["severitat"] == "CRITICAL"
    assert alertes_cad["CARNET_CADUCAT"]["dies_restants"] == -10
    assert alertes_cad["CARNET_CADUCAT"]["bloquejant_alta"] is False


@pytest.mark.asyncio
async def test_persistencia_disc_dur_client_i_calcul_alertes_operari(tmp_path, monkeypatch):
    """Comprova que les dades de l'OCR, els fitxers i les alertes es guarden sempre al disc dur del client."""
    import json

    from fastapi import UploadFile
    from starlette.datastructures import Headers

    from app.api.v1.gestio.operaris import (
        _calcular_alertes_copilot_operari,
        _executar_ocr_operari_i_desar_al_disc,
        _persistir_alertes_operari_disc,
    )

    monkeypatch.setenv("CLIENT_DISKS_MOUNT_ROOT", str(tmp_path))
    empresa_id = uuid.uuid4()

    dni_bytes = (
        "# DNI ESPANYA\nNom: Anna\nCognoms: Serra Bosch\nNIF: 41239876Z\nValidesa: 2029-10-10\n"
    ).encode("utf-8")
    carnet_bytes = (
        f"PERMÍS DE CONDUIR\nNIF: 41239876Z\nCategories: B, C\n"
        f"Caducitat del carnet: {(date.today() + timedelta(days=14)).strftime('%d/%m/%Y')}\n"
    ).encode("utf-8")

    up_dni = UploadFile(
        file=io.BytesIO(dni_bytes),
        filename="dni_anna.md",
        headers=Headers({"content-type": "text/markdown"}),
    )
    up_carnet = UploadFile(
        file=io.BytesIO(carnet_bytes),
        filename="carnet_anna.txt",
        headers=Headers({"content-type": "text/plain"}),
    )

    res = await _executar_ocr_operari_i_desar_al_disc(
        db=None,  # type: ignore[arg-type]
        empresa_id=str(empresa_id),
        all_files=[up_dni, up_carnet],
    )

    assert res["nif"] == "41239876Z"
    assert res["apte_alta_operari"] is True
    assert res["bloqueja_alta"] is False
    assert len(res["documents_processats"]) == 2

    # Verifica que els fitxers, metadades i alertes existeixen físicament al disc dur del client
    arrel_empresa = tmp_path / f"disc_{empresa_id}"
    dir_docs = arrel_empresa / "08_flota_i_operaris" / "operaris" / "documents_rrhh"
    dir_operaris = arrel_empresa / "08_flota_i_operaris" / "operaris"
    dir_alertes = arrel_empresa / "08_flota_i_operaris" / "operaris" / "alertes_rrhh"

    fitxers_docs = list(dir_docs.glob("*"))
    fitxers_draft = list(dir_operaris.glob("ocr_draft_*.json"))
    fitxers_alertes = list(dir_alertes.glob("*.json"))
    assert len(fitxers_docs) >= 4  # 2 arxius binaris + 2 metadades doc_*.json
    assert len(fitxers_draft) >= 1
    assert len(fitxers_alertes) >= 1

    contingut_draft = json.loads(fitxers_draft[0].read_text(encoding="utf-8"))
    assert contingut_draft["nif"] == "41239876Z"
    assert "CERTIFICAT_PRL" in contingut_draft["documents_pendents"]

    # Verifica el càlcul d'alertes sobre l'entitat Usuari i la seva persistència al disc
    avui = date.today()
    op = Usuari(
        id=uuid.uuid4(),
        empresa_id=empresa_id,
        nom="Anna",
        cognoms="Serra Bosch",
        nif="41239876Z",
        rol="OPERARI",
        carnet_conduir="C",
        carnet_caducitat=avui + timedelta(days=12),
        prl_certificat_vigencia=None,
    )
    alertes_op, pendents_op = _calcular_alertes_copilot_operari(op, avui=avui)
    codis_op = {a["codi"] for a in alertes_op}
    assert "CARNET_PROPER_CADUCAR" in codis_op
    assert "MANCA_DOCUMENTACIO_RRHH" in codis_op
    assert "CERTIFICAT_PRL" in pendents_op

    await _persistir_alertes_operari_disc(None, empresa_id, op, alertes_op)  # type: ignore[arg-type]
    fitxer_alerta_op = dir_alertes / f"alerta_operari_{op.id}_carnet_proper_caducar.json"
    assert fitxer_alerta_op.exists()

    # També comprova la retrocompatibilitat de processar_dni_ocr
    res_legacy = await processar_dni_ocr(dni_bytes, filename="dni_anna.md")
    assert res_legacy["raw_data"]["nif"] == "41239876Z"
    assert res_legacy["apte_alta_operari"] is True

