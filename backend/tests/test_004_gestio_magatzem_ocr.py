import pytest
import uuid
from datetime import date, timedelta
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.models.models import Empresa, Usuari
from sqlalchemy import text

@pytest.mark.asyncio
async def test_albara_ocr_i_confirmacio(admin_session, headers, boss_token):
    token, empresa_id = boss_token
    boss_nif = "B" + str(uuid.uuid4())[:8].upper()
    
    admin_session.add(Empresa(
        id=uuid.UUID(empresa_id), nom='Test OCR Magatzem', nif=boss_nif, subdomini='testocr-' + str(uuid.uuid4())[:5], pla_subscripcio='STARTER', estat_pagament='ACTIU'
    ))
    await admin_session.flush()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Pas 1: Pujar arxiu
        file_content = b"Mock PDF/Image Data"
        files = {"fitxer": ("albara.pdf", file_content, "application/pdf")}
        res_ocr = await ac.post("/api/v1/gestio/magatzem/albara/ocr", files=files, headers=headers)
        assert res_ocr.status_code == 200
        data_ocr = res_ocr.json()
        assert data_ocr["proveidor"]["nom"] == "PROVEIDOR DETECTAT S.L."

        # Pas 2: Confirmar Albarà
        data_albara = (date.today() - timedelta(days=2)).isoformat()
        payload_confirmar = {
            "proveidor": data_ocr["proveidor"],
            "numero_document": data_ocr["numero_document"],
            "tipus_document": "ALBARA",
            "data_document": data_albara,
            "numero_albarans_vinculats": [],
            "linies": [
                {
                    "referencia": "CAB-2MM-01",
                    "nom": "Bobina Cable Flex",
                    "quantitat": 100,
                    "preu": 0.50,
                    "descompte_percent": 0.0,
                    "tipus": "MATERIAL"
                },
                {
                    "referencia": "TLL-18V",
                    "nom": "Tornavis",
                    "quantitat": 1,
                    "preu": 150.0,
                    "descompte_percent": 10.0,
                    "tipus": "EINA"
                }
            ]
        }
        res_conf = await ac.post("/api/v1/gestio/magatzem/albara/confirmar", json=payload_confirmar, headers=headers)
        assert res_conf.status_code == 201
        data_conf = res_conf.json()
        assert data_conf["estat"] == "OK"
        
        # Pas 3: Provar duplicat (ha de fallar)
        res_dup = await ac.post("/api/v1/gestio/magatzem/albara/confirmar", json=payload_confirmar, headers=headers)
        assert res_dup.status_code == 400
        assert "Albarà ja pujat" in res_dup.json()["detail"]
        
        # Pas 4: Confirmar Factura
        payload_factura = payload_confirmar.copy()
        payload_factura["tipus_document"] = "FACTURA"
        payload_factura["numero_document"] = "FAC-999"
        payload_factura["data_document"] = date.today().isoformat()
        payload_factura["numero_albarans_vinculats"] = [data_ocr["numero_document"]]
        
        res_fac = await ac.post("/api/v1/gestio/magatzem/albara/confirmar", json=payload_factura, headers=headers)
        assert res_fac.status_code == 201
        data_fac = res_fac.json()
        assert data_fac["estat"] == "OK"
