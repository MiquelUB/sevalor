import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.models import Empresa


@pytest.mark.asyncio
async def test_tiquet_ocr_ia(admin_session, headers, boss_token):
    token, empresa_id = boss_token
    boss_nif = "B" + str(uuid.uuid4())[:8].upper()

    admin_session.add(
        Empresa(
            id=uuid.UUID(empresa_id),
            nom="Test IA Tiquets",
            nif=boss_nif,
            subdomini="tiquets-" + str(uuid.uuid4())[:5],
            pla_subscripcio="STARTER",
            estat_pagament="ACTIU",
        )
    )
    await admin_session.flush()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/api/v1/operari/tiquets", headers=headers)
        assert res.status_code == 200

        # Test 1: Upload a ticket for OCR (Magic bytes validation returns 200 or 422, never 404)
        file_content = b"fake image data representing a ticket"
        files = {"arxiu": ("tiquet_test.jpg", file_content, "image/jpeg")}

        ocr_res = await ac.post("/api/v1/operari/tiquets/ocr", headers=headers, files=files)
        assert ocr_res.status_code in (200, 422), f"OCR endpoint no hauria de retornar 404: {ocr_res.status_code}"

        if ocr_res.status_code == 200:
            data = ocr_res.json()
            assert "import" in data or "total" in data

        # Test 2: AI extraction / text parsing for unstructured expense (Spec 03 / Spec 018)
        ai_res = await ac.post(
            "/api/v1/operari/tiquets/parse",
            headers=headers,
            json={"text": "He gastat 50 euros en gasoil avui"},
        )
        assert ai_res.status_code == 200, f"Parse endpoint ha de retornar 200: {ai_res.status_code}"
        parsed = ai_res.json()
        assert "import" in parsed
        assert parsed["import"] == 50.0
        assert parsed["categoria"] == "CARBURANT"

        # Test 3: List tickets and verify structure
        list_res = await ac.get("/api/v1/operari/tiquets", headers=headers)
        assert list_res.status_code == 200
        assert isinstance(list_res.json(), list)
