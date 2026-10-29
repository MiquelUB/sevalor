"""
searxng_service.py -> backend/app/services/searxng_service.py

Client asíncron per al metabuscador privat SearXNG desplegat a la xarxa interna de Sevalor Suite.
Consulta Google Web, Google Maps, DuckDuckGo i Qwant sense anuncis ni rastreig, retornant JSON net.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings

logger = logging.getLogger(__name__)

# Dominis d'agregadors, xarxes socials i portals que no són empreses instal·ladores
DIRECTORIS_I_XARXES_IGNORAR = {
    "google.com", "google.es", "bing.com", "yahoo.com", "duckduckgo.com",
    "facebook.com", "instagram.com", "linkedin.com", "twitter.com", "x.com",
    "youtube.com", "tiktok.com", "pinterest.com",
    "wikipedia.org", "boe.es", "gencat.cat", "administracion.gob.es",
    "paginasamarillas.es", "habitissimo.es", "milanuncios.com", "wallapop.com",
    "infocif.es", "axesor.es", "einforma.com", "empresite.eleconomista.es",
    "cronoshare.com", "pronto-pro.es", "yelp.es", "tripadvisor.es",
}


def _es_domini_ignorable(url: str) -> bool:
    try:
        host = urlparse(url).netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        return any(d in host for d in DIRECTORIS_I_XARXES_IGNORAR)
    except Exception:
        return True


class SearxngService:
    """Servei asíncron de cerca sobre instància SearXNG."""

    def __init__(self, base_url: Optional[str] = None) -> None:
        self.base_url = (base_url or getattr(settings, "SEARXNG_URL", "http://localhost:8888")).rstrip("/")

    async def cercar(
        self,
        query: str,
        language: str = "ca",
        engines: str = "google,duckduckgo,qwant",
        max_results: int = 20,
        timeout: float = 3.0,
    ) -> List[Dict[str, Any]]:
        """Executa una cerca contra SearXNG i retorna resultats deduplicats i filtrats."""
        if not query or not query.strip():
            return []

        params = {
            "q": query.strip(),
            "format": "json",
            "language": language,
            "engines": engines,
        }

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.get(f"{self.base_url}/search", params=params)
                if resp.status_code != 200:
                    logger.debug("SearXNG ha retornat codi HTTP %s per a query %r", resp.status_code, query)
                    return []
                data = resp.json()
        except Exception as e:
            logger.debug("SearXNG no disponible a %s: %s", self.base_url, e)
            return []

        bruts = data.get("results", [])
        candidats: List[Dict[str, Any]] = []
        dominis_vistos: set[str] = set()

        for item in bruts:
            url = item.get("url", "")
            if not url or not url.startswith(("http://", "https://")):
                continue
            if _es_domini_ignorable(url):
                continue

            host = urlparse(url).netloc.lower()
            if host in dominis_vistos:
                continue
            dominis_vistos.add(host)

            candidats.append({
                "url": url,
                "title": item.get("title", ""),
                "snippet": item.get("content", ""),
                "engine": item.get("engine", ""),
            })

            if len(candidats) >= max_results:
                break

        return candidats

    async def cercar_web_empresa(self, rao_social: str, municipi: str) -> Optional[str]:
        """Cerca específica per trobar la pàgina web oficial d'una empresa censada."""
        q = f'"{rao_social}" {municipi} web'
        resultats = await self.cercar(q, max_results=2, timeout=2.5)
        if resultats:
            return resultats[0]["url"]
        return None
