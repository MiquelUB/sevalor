"""Tests unitaris per a EasypanelService (Zero Mock en lògica de sanejament i protocol REST)."""

from unittest.mock import AsyncMock, patch

import pytest

from app.core.config import settings
from app.services.easypanel_service import EasypanelService


def test_sanititzar_domini_valid():
    assert EasypanelService._sanititzar_domini("sevalormante.projectexinoxano.cat") == "sevalormante.projectexinoxano.cat"
    assert EasypanelService._sanititzar_domini("https://SEVALORMANTE.projectexinoxano.cat/") == "sevalormante.projectexinoxano.cat"
    assert EasypanelService._sanititzar_domini("http://demo.empresa.cat:3000/test") == "demo.empresa.cat"


def test_sanititzar_domini_invalid():
    with pytest.raises(ValueError):
        EasypanelService._sanititzar_domini("domini_invalid")
    with pytest.raises(ValueError):
        EasypanelService._sanititzar_domini("https://; rm -rf /")
    with pytest.raises(ValueError):
        EasypanelService._sanititzar_domini("")


@pytest.mark.asyncio
async def test_afegir_domini_pwa_anti_conflict():
    """Verifica que abans de registrar es purguen dominis orfes i es creï al servei sevalor-pwa."""
    with patch.object(settings, "EASYPANEL_API_KEY", "test_key"), \
         patch.object(settings, "EASYPANEL_URL", "http://127.0.0.1:3000"), \
         patch.object(settings, "EASYPANEL_PROJECT", "sevalor"), \
         patch.object(settings, "EASYPANEL_SERVICE_PWA", "sevalor-pwa"), \
         patch.object(EasypanelService, "verificar_dns_resolucio", new_callable=AsyncMock) as mock_dns:

        mock_dns.return_value = {"resolt": True, "status": "DNS_CORRECTE", "ips": ["178.104.83.189"], "detail": "OK"}

        # Simular httpx AsyncClient
        calls = []

        class MockResponse:
            def __init__(self, status_code, json_data=None, text=""):
                self.status_code = status_code
                self._json_data = json_data or {}
                self.text = text

            def json(self):
                return self._json_data

        async def mock_get(url, **kwargs):
            calls.append(("GET", url, kwargs))
            # Retornar un domini antic orfe assignat a pwa
            return MockResponse(200, [
                {
                    "id": "sevalor-pwa-sevalormante-projectexinoxano-cat",
                    "host": "sevalormante.projectexinoxano.cat",
                    "serviceDestination": {"projectName": "sevalor", "serviceName": "pwa", "port": 3000}
                }
            ])

        async def mock_post(url, **kwargs):
            calls.append(("POST", url, kwargs))
            return MockResponse(201, {"id": kwargs.get("json", {}).get("id")})

        with patch("httpx.AsyncClient.get", side_effect=mock_get), \
             patch("httpx.AsyncClient.post", side_effect=mock_post):

            res = await EasypanelService.afegir_domini_pwa("sevalormante.projectexinoxano.cat")

            assert res["ok"] is True
            assert res["status"] == "SSL_ACTIU"

            # Verificar que s'ha demanat la purga del domini antic
            del_calls = [c for c in calls if c[0] == "POST" and "deleteDomain" in c[1]]
            assert len(del_calls) >= 1
            deleted_ids = [c[2]["json"]["id"] for c in del_calls]
            assert "sevalor-pwa-sevalormante-projectexinoxano-cat" in deleted_ids

            # Verificar que s'ha creat apuntant a sevalor-pwa
            create_calls = [c for c in calls if c[0] == "POST" and "createDomain" in c[1]]
            assert len(create_calls) == 1
            created_payload = create_calls[0][2]["json"]
            assert created_payload["serviceDestination"]["serviceName"] == "sevalor-pwa"
            assert created_payload["host"] == "sevalormante.projectexinoxano.cat"


@pytest.mark.asyncio
async def test_afegir_domini_pwa_update_fallback_on_400():
    """Verifica que si createDomain respon 400 'already used', s'aplica updateDomain automàticament."""
    with patch.object(settings, "EASYPANEL_API_KEY", "test_key"), \
         patch.object(settings, "EASYPANEL_URL", "http://127.0.0.1:3000"), \
         patch.object(settings, "EASYPANEL_PROJECT", "sevalor"), \
         patch.object(settings, "EASYPANEL_SERVICE_PWA", "sevalor-pwa"), \
         patch.object(EasypanelService, "verificar_dns_resolucio", new_callable=AsyncMock) as mock_dns:

        mock_dns.return_value = {"resolt": True, "status": "DNS_CORRECTE", "ips": ["178.104.83.189"], "detail": "OK"}

        calls = []

        class MockResponse:
            def __init__(self, status_code, json_data=None, text=""):
                self.status_code = status_code
                self._json_data = json_data or {}
                self.text = text

            def json(self):
                return self._json_data

        async def mock_get(url, **kwargs):
            calls.append(("GET", url, kwargs))
            return MockResponse(200, [])

        async def mock_post(url, **kwargs):
            calls.append(("POST", url, kwargs))
            if "createDomain" in url:
                return MockResponse(400, text='{"message":"Domain already used"}')
            if "updateDomain" in url:
                return MockResponse(200, json_data={"ok": True})
            return MockResponse(200, json_data={"ok": True})

        with patch("httpx.AsyncClient.get", side_effect=mock_get), \
             patch("httpx.AsyncClient.post", side_effect=mock_post):

            res = await EasypanelService.afegir_domini_pwa("sevalormante.projectexinoxano.cat")

            assert res["ok"] is True
            assert res["status"] == "SSL_ACTIU"
            update_calls = [c for c in calls if c[0] == "POST" and "updateDomain" in c[1]]
            assert len(update_calls) == 1

