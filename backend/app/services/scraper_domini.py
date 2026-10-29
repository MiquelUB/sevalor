"""
scraper_domini.py  ->  backend/app/services/scraper_domini.py

Descàrrega de les pàgines ÚTILS d'un domini (contacte, legal, equip), text que conserva
footer/<address>/mailto/tel, dades estructurades (JSON-LD) i descoberta per CP via OSM.

Dependències noves: selectolax, extruct
"""
from __future__ import annotations

import asyncio
import re
import time
import urllib.robotparser
from collections import defaultdict
from typing import Awaitable, Callable
from urllib.parse import urljoin, urlparse

import extruct
import httpx
from selectolax.lexbor import (
    LexborHTMLParser as HTMLParser,  # selectolax >= 1.0 ja no inclou 'modest'
)

from app.services.prospeccio_validacio import USER_AGENT, Pagina, norm

# ───────────────────────── Descobriment de pàgines útils ─────────────────────────
PATRONS = {
    "contacte": r"contact|on-som|donde-estamos|ubicaci",
    "legal": r"avis-legal|aviso-legal|legal|privacitat|privacidad",
    "equip": r"equip|equipo|nosaltres|nosotros|qui-som|quienes-somos|empresa|about|team",
}
_sem_domini: dict[str, asyncio.Semaphore] = defaultdict(lambda: asyncio.Semaphore(2))


def pagines_utils(html_home: str, base: str, max_per_tipus: int = 2) -> list[str]:
    """Troba, a partir dels enllaços de la portada, les pàgines de contacte/legal/equip."""
    host = urlparse(base).netloc
    trobades: dict[str, list[str]] = {k: [] for k in PATRONS}
    for a in HTMLParser(html_home).css("a[href]"):
        url = urljoin(base, (a.attributes.get("href") or "").split("#")[0])
        if urlparse(url).netloc != host:
            continue
        clau = (url + " " + (a.text() or "")).lower()
        for tipus, pat in PATRONS.items():
            if (re.search(pat, clau) and url not in trobades[tipus]
                    and len(trobades[tipus]) < max_per_tipus):
                trobades[tipus].append(url)
    return [u for lst in trobades.values() for u in lst]


# ───────────────────────── HTML -> text (conserva footer) ─────────────────────────
def html_a_text(html: str) -> str:
    tree = HTMLParser(html)
    tree.strip_tags(["script", "style", "noscript", "svg"])
    return tree.body.text(separator="\n", strip=True) if tree.body else ""


def blocs_extra(html: str) -> str:
    """mailto:, tel: i <address>: sovint contenen les dades que el text net perd."""
    tree = HTMLParser(html)
    extra: list[str] = []
    for a in tree.css("a[href]"):
        h = (a.attributes.get("href") or "").strip()
        if h.lower().startswith(("mailto:", "tel:")):
            extra.append(h.split("?")[0])
    for n in tree.css("address, [itemprop='address']"):
        extra.append(n.text(separator=" ", strip=True))
    return "\n".join(extra)


def _pagina(url: str, html: str) -> Pagina:
    return Pagina(url=url, html=html, text=html_a_text(html) + "\n" + blocs_extra(html))


# ───────────────────────── HTTP robust ─────────────────────────
async def _get(client: httpx.AsyncClient, url: str, intents: int = 3) -> str | None:
    for n in range(intents):
        try:
            r = await client.get(url, timeout=15)
            if r.status_code in (429, 500, 502, 503, 504):
                await asyncio.sleep(2 ** n)
                continue
            if r.status_code == 200:
                ct = r.headers.get("content-type", "").lower()
                if "text/html" in ct or "text/plain" in ct or not ct:
                    return r.text
            return None
        except httpx.HTTPError:
            await asyncio.sleep(2 ** n)
    return None


# ───────────────────────── Caché i Robots.txt ─────────────────────────
_cache_robots: dict[str, tuple[float, urllib.robotparser.RobotFileParser | None]] = {}
_cache_pagines: dict[str, tuple[float, list[Pagina]]] = {}
ROBOTS_CACHE_TTL = 86400  # 24 hores
CACHE_PAGINES_TTL = 3600   # 1 hora


async def _comprovar_robots_txt(client: httpx.AsyncClient, base: str, url: str) -> bool:
    """Verifica si el robots.txt del domini permet l'accés pel nostre User-Agent."""
    ara = time.time()
    rp: urllib.robotparser.RobotFileParser | None = None
    if base in _cache_robots:
        t, parsed_rp = _cache_robots[base]
        if ara - t < ROBOTS_CACHE_TTL:
            rp = parsed_rp

    if rp is None and base not in _cache_robots:
        try:
            r = await client.get(f"{base}/robots.txt", timeout=6.0)
            if r.status_code == 200 and r.text.strip():
                rp = urllib.robotparser.RobotFileParser()
                rp.parse(r.text.splitlines())
            else:
                rp = None
        except Exception:
            rp = None
        _cache_robots[base] = (ara, rp)

    if rp is None:
        return True

    try:
        return rp.can_fetch(USER_AGENT, url)
    except Exception:
        return True


async def descarregar_pagines(
    client: httpx.AsyncClient,
    url: str,
    max_pagines: int = 6,
    fallback_js: Callable[[str], Awaitable[str | None]] | None = None,
) -> list[Pagina]:
    """
    Portada + pàgines útils descobertes amb suport de robots.txt i memòria cau.
    Si el text és pràcticament buit (web feta amb JS), usa `fallback_js(url) -> markdown`.
    """
    p = urlparse(url)
    base = f"{p.scheme}://{p.netloc}"
    ara = time.time()

    # 1. Comprovar memòria cau
    if base in _cache_pagines:
        t_pag, pags = _cache_pagines[base]
        if ara - t_pag < CACHE_PAGINES_TTL and pags:
            return pags

    # 2. Comprovar robots.txt
    if not await _comprovar_robots_txt(client, base, base + "/"):
        return []

    async with _sem_domini[p.netloc]:
        home = await _get(client, base + "/")
        if not home:
            return []
        pagines = [_pagina(base + "/", home)]
        urls = [u for u in pagines_utils(home, base)[: max_pagines - 1] if await _comprovar_robots_txt(client, base, u)]
        htmls = await asyncio.gather(*(_get(client, u) for u in urls))
        pagines += [_pagina(u, h) for u, h in zip(urls, htmls) if h]

    if fallback_js and sum(len(x.text) for x in pagines) < 500:
        md = await fallback_js(base + "/")
        if md:
            pagines = [Pagina(url=base + "/", html="", text=md)]

    _cache_pagines[base] = (ara, pagines)
    return pagines


# ───────────────────────── Dades estructurades (JSON-LD) ─────────────────────────
TIPUS_NEGOCI = {"LocalBusiness", "Organization", "Electrician", "Plumber", "HVACBusiness",
                "HomeAndConstructionBusiness", "GeneralContractor", "RoofingContractor"}


def jsonld_negoci(html: str, url: str) -> list[dict]:
    out: list[dict] = []
    try:
        blocs = extruct.extract(html, base_url=url, syntaxes=["json-ld"])["json-ld"]
    except Exception:
        return out
    for bloc in blocs:
        for node in (bloc.get("@graph") or [bloc]):
            if not isinstance(node, dict):
                continue
            t = node.get("@type")
            t = t if isinstance(t, list) else [t]
            if TIPUS_NEGOCI & set(t):
                a = node.get("address") or {}
                if isinstance(a, dict):
                    out.append({"cp": a.get("postalCode"), "carrer": a.get("streetAddress"),
                                "tel": node.get("telephone"), "email": node.get("email")})
    return out


def adreca_jsonld(pagines: list[Pagina], cp: str) -> str | None:
    """Adreça del JSON-LD només si el CP coincideix i hi ha carrer amb número."""
    for p in pagines:
        if not p.html:
            continue
        for n in jsonld_negoci(p.html, p.url):
            carrer = (n.get("carrer") or "").strip()
            if str(n.get("cp", "")).strip() == cp and re.search(r"\d|s/n", carrer, re.I):
                return f"{carrer}, {cp}"
    return None


# ───────────────────────── Descoberta per CP exacte (OSM/Overpass) ─────────────────────────
# Ajusta els tags a les teves verticals. Cobertura irregular: és una font addicional.
OSM_TAGS: dict[str, list[tuple[str, str]]] = {
    "baixa tensio": [("craft", "electrician")],
    "solar": [("craft", "electrician")],
    "fontaneria": [("craft", "plumber")],
    "climatitzacio": [("craft", "hvac")],
    "edificacio": [("craft", "builder")],
}


OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]


async def osm_per_cp(client: httpx.AsyncClient, cp: str, vertical: str) -> list[dict]:
    v = norm(vertical)
    tags: list[tuple[str, str]] = []
    for k, t_list in OSM_TAGS.items():
        if k in v:
            tags.extend(t_list)
    if not tags:
        return []

    # Eliminar duplicats mantenint ordre
    tags = list(dict.fromkeys(tags))
    filtres = "".join(f'nwr["addr:postcode"="{cp}"]["{k}"="{val}"];' for k, val in tags)
    query = f"[out:json][timeout:15];({filtres});out tags center;"

    for endpoint in OVERPASS_ENDPOINTS:
        try:
            r = await client.post(endpoint, data={"data": query}, timeout=15.0)
            if r.status_code == 200:
                out: list[dict] = []
                for e in r.json().get("elements", []):
                    t = e.get("tags", {})
                    web = t.get("website") or t.get("contact:website")
                    if web:
                        if not web.startswith("http"):
                            web = "https://" + web
                        out.append({"url": web, "title": t.get("name", "")})
                return out
        except Exception:
            continue
    return []
