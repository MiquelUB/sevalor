"""
prospeccio_validacio.py  ->  backend/app/services/prospeccio_validacio.py

Validacions DURES (sense LLM) del pipeline de prospecció de Sevalor Suite.
Funcions pures i testables. Principi: el LLM redacta i puntua, però NO decideix
CP, Espanya, vertical ni gatekeeper: això ho decideix el codi.

Dependències noves: phonenumbers, python-stdnum
"""
from __future__ import annotations

import asyncio
import re
import time
import unicodedata
from dataclasses import dataclass
from urllib.parse import urlparse

import phonenumbers
from stdnum.es import nif as _nif

# ───────────────────────── Configuració ─────────────────────────
USER_AGENT = "SevalorSuite/1.0 (contacte: tecnic@sevalor.net)"  # Nominatim ho exigeix
GEOCODE_MODE = "marcar"          # "marcar" | "descartar": què fer si Nominatim retorna un altre CP
PERMET_SENSE_GATEKEEPER = True   # False => sense gatekeeper verificat = DESCARTAT
TLD_PERMESOS = {"es", "cat", "com", "eu", "net", "org", "info"}


# ───────────────────────── Utilitats ─────────────────────────
@dataclass
class Pagina:
    url: str
    html: str
    text: str


def norm(s: str | None) -> str:
    """Minúscules, sense accents i amb espais col·lapsats."""
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s).lower().strip()


# ───────────────────────── 1. Adreça i CP ─────────────────────────
RE_VIA = re.compile(
    r"(?:\bc/|\b(?:calle|carrer|avda|av|avinguda|avenida|pla[çc]a|plaza|passeig|paseo|"
    r"pol[íi]gon|pol\.?\s*ind|ronda|cam[íi]|camino|carretera|ctra|travessera|rambla|gran\s+via)\b\.?)",
    re.I,
)


def adreca_valida_per_cp(text: str, cp: str) -> str | None:
    """
    Retorna l'adreça només si hi ha via + número (o s/n) + CP EXACTE.
    Mai fa fallback al municipi: '25001 Lleida' tot sol NO és una adreça.
    """
    for m in re.finditer(rf"(?<!\d){re.escape(cp)}(?!\d)", text or ""):
        ini = max(0, m.start() - 120)
        prefix = text[ini:m.start()]
        via = None
        for via in RE_VIA.finditer(prefix):
            pass  # ens quedem amb l'última via abans del CP
        if via and re.search(r"\d|s/n", prefix[via.end():], re.I):
            # després del CP, només el municipi (fins a 3 paraules amb majúscula, a la mateixa línia)
            resta = re.match(r"[ \t]+[A-ZÀ-ÖØ-Ý][^\s,;|.]*(?:[ \t]+[A-ZÀ-ÖØ-Ý][^\s,;|.]*){0,2}",
                             text[m.end():])
            fi = m.end() + (resta.end() if resta else 0)
            return " ".join(text[ini + via.start(): fi].split())
    return None


_geo_lock = asyncio.Lock()
_geo_last = 0.0


async def cp_geocodificat(client, adreca: str) -> str | None:
    """
    CP que Nominatim assigna a l'adreça (None si no es pot determinar).
    Política de Nominatim: màx. 1 req/s i User-Agent propi. Per a volum alt,
    autoallotja'l o canvia a CartoCiudad (IGN).
    """
    global _geo_last
    async with _geo_lock:
        espera = 1.1 - (time.monotonic() - _geo_last)
        if espera > 0:
            await asyncio.sleep(espera)
        _geo_last = time.monotonic()
    try:
        r = await client.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": adreca, "countrycodes": "es", "format": "jsonv2",
                    "addressdetails": 1, "limit": 1},
            headers={"User-Agent": USER_AGENT},
            timeout=10,
        )
        r.raise_for_status()
        dades = r.json()
        return (dades[0].get("address") or {}).get("postcode") if dades else None
    except Exception:
        return None


# ───────────────────────── 2. Espanya i directoris ─────────────────────────
RE_CP_ES = re.compile(r"(?<!\d)(?:0[1-9]|[1-4]\d|5[0-2])\d{3}(?!\d)")


def tld(url: str) -> str:
    host = urlparse(url).hostname or ""
    return host.rsplit(".", 1)[-1].lower()


def telefons_es(text: str) -> set[str]:
    """Telèfons espanyols VÀLIDS (fix o mòbil) en format E.164."""
    out: set[str] = set()
    for m in phonenumbers.PhoneNumberMatcher(text or "", "ES"):
        n = m.number
        if n.country_code == 34 and phonenumbers.is_valid_number(n):
            out.add(phonenumbers.format_number(n, phonenumbers.PhoneNumberFormat.E164))
    return out


def es_domini_espanyol(url: str, text: str) -> bool:
    """TLD permès + almenys un telèfon espanyol vàlid al text."""
    return tld(url) in TLD_PERMESOS and bool(telefons_es(text))


def sembla_directori(text: str, max_tels: int = 8, max_cps: int = 6) -> bool:
    """Una web d'empresa no llista molts telèfons ni molts CP diferents. Calibra amb fixtures reals."""
    cps = set(RE_CP_ES.findall(text or ""))
    return len(cps) > max_cps or len(telefons_es(text)) > max_tels


# ───────────────────────── 3. Vertical ─────────────────────────
# Afegeix aquí les teves verticals (claus i termes ja normalitzats: sense accents).
VERTICALS: dict[str, list[str]] = {
    "baixa tensio": ["baja tension", "baixa tensio", "rebt", "instalaciones electricas",
                     "instalacions electriques", "instal·lacions electriques",
                     "electricista", "electricitat", "electricidad"],
    "solar": ["fotovoltaic", "solar", "autoconsumo", "autoconsum", "placas solares", "plaques solars"],
    "climatitzacio": ["climatizacion", "climatitzacio", "aire acondicionado", "aire condicionat",
                      "calefaccion", "calefaccio", "bomba de calor", "frio industrial"],
    "reg agricola": ["riego", "reg agricola", "regadio", "regadiu", "goteo", "aspersion", "aspersio"],
    "fontaneria": ["fontaneria", "fontanero", "fontaner", "saneamiento", "sanejament"],
    "manteniment industrial": ["mantenimiento industrial", "manteniment industrial",
                               "automatizacion", "automatitzacio", "mecanica"],
    "edificacio": ["construccion", "construccio", "reformas", "reformes", "edificacion",
                   "edificacio", "obra civil", "rehabilitacion", "rehabilitacio"],
}


def termes_vertical(vertical: str) -> list[str]:
    v = norm(vertical)
    trobats: list[str] = []
    for clau, termes in VERTICALS.items():
        if clau in v or any(t in v for t in termes):
            trobats.extend(termes)
    if trobats:
        return list(dict.fromkeys(trobats))
    return [t for t in v.split() if len(t) > 3]  # fallback: paraules de la vertical


def coincideix_vertical(text: str, vertical: str, minim: int = 2) -> bool:
    termes = termes_vertical(vertical)
    if not termes:
        return False
    t = norm(text)
    return sum(1 for x in termes if x in t) >= min(minim, len(termes))


# ───────────────────────── 4. Gatekeeper verificat ─────────────────────────
NOM = (r"[A-ZÀ-ÖØ-Ý][a-zà-öø-ÿ'·\-]+"
       r"(?:\s+(?:(?:de|del|de\s+la|dels|la|i|y)\s+)?[A-ZÀ-ÖØ-Ý][a-zà-öø-ÿ'·\-]+){1,3}")
CARREC = (r"(?i:gerent[ea]?|administrador(?:a|\s+[uú]nic[oa])?"
          r"|director[a]?(?:\s+general|\s+t[eè]cnic[oa])?"
          r"|propietari[oa]?|fundador[a]?|titular|apoderad[oa]|responsable)")
RE_NOM_CARREC = re.compile(rf"(?P<nom>{NOM})\s*[,\-–—|:(]\s*(?P<carrec>{CARREC})\b")
RE_CARREC_NOM = re.compile(rf"(?P<carrec>{CARREC})\s*[:\-–—]?\s*(?P<nom>{NOM})")

STOP = {
    "aviso", "avis", "legal", "politica", "privacidad", "privacitat", "cookies", "contacto",
    "contacte", "atencion", "servicio", "servei", "tecnico", "tecnic", "instalaciones",
    "instalacions", "departamento", "departament", "oficina", "gerencia", "direccion",
    "direccio", "empresa", "grupo", "general", "comercial", "calidad", "qualitat",
    "administracion", "administracio", "condiciones", "condicions",
}
PARTICULES = {"de", "del", "la", "dels", "i", "y"}


@dataclass
class Gatekeeper:
    nom: str
    carrec: str
    font_url: str
    cita: str
    confianca: str  # "alta" (>=2 pàgines) | "mitjana" (1 pàgina)


def nom_persona_plausible(nom: str) -> bool:
    tokens = nom.split()
    if not 2 <= len(tokens) <= 5:
        return False
    return not any(norm(t).strip(".,") in STOP for t in tokens if norm(t) not in PARTICULES)


def trobar_gatekeeper(pagines: list[tuple[str, str]]) -> Gatekeeper | None:
    """
    pagines: [(url, text)] ordenades per prioritat (legal, equip, resta).
    Només retorna un nom que apareix LITERALMENT al text, amb un càrrec adjacent.
    """
    for url, text in pagines:
        for rx in (RE_NOM_CARREC, RE_CARREC_NOM):
            for m in rx.finditer(text or ""):
                nom = " ".join(m.group("nom").split())
                if not nom_persona_plausible(nom):
                    continue
                n = norm(nom)
                suport = sum(1 for _, t in pagines if n in norm(t))
                cita = " ".join(text[max(0, m.start() - 60): m.end() + 60].split())
                return Gatekeeper(nom, m.group("carrec").lower(), url, cita,
                                  "alta" if suport >= 2 else "mitjana")
    return None


def bloc_gatekeeper(gk: Gatekeeper | None) -> str:
    """Text que s'injecta al prompt de l'usuari."""
    if not gk:
        return "cap"
    return f"Nom: {gk.nom} | Càrrec: {gk.carrec} | Font: {gk.font_url} | Cita: «{gk.cita}»"


# ───────────────────────── 5. Dades de contacte ─────────────────────────
RE_ID_FISCAL = re.compile(r"\b(?:[ABCDEFGHJNPQRSUVW]\d{7}[0-9A-J]|[XYZ]\d{7}[A-Z]|\d{8}[A-Z])\b")
EMAIL_JUNK = ("sentry", "wixpress", "example.", "tuemail", "tucorreo", "tudominio",
              "@2x", ".png", ".jpg", ".webp", ".svg")


def ids_fiscals_valids(text: str) -> list[str]:
    """CIF/NIF/NIE amb dígit de control correcte (inclou NIF d'autònom)."""
    vistos: set[str] = set()
    out: list[str] = []
    for c in RE_ID_FISCAL.findall((text or "").upper()):
        if c not in vistos and _nif.is_valid(c):
            vistos.add(c)
            out.append(c)
    return out


def email_valid_forma(email: str) -> bool:
    e = (email or "").strip().lower()
    return bool(re.fullmatch(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", e)) and not any(j in e for j in EMAIL_JUNK)


def email_sembla_del_nom(email: str, nom: str) -> bool:
    """True si el local-part s'assembla al nom verificat (jpuig@, joan.puig@...). info@ => False."""
    local = re.sub(r"[._\-]", "", norm(email.split("@")[0]))
    tokens = [t for t in norm(nom).split() if len(t) > 2 and t not in PARTICULES]
    if len(tokens) < 2:
        return False
    n0, c0 = tokens[0], tokens[1]
    combos = {n0 + c0, n0[0] + c0, c0 + n0, c0 + n0[0], n0, c0}
    return any(c in local for c in combos if len(c) >= 4)


# ───────────────────────── 6. Context per al LLM ─────────────────────────
def ordenar_per_prioritat(pagines: list[Pagina]) -> list[Pagina]:
    def clau(p: Pagina) -> int:
        u = p.url.lower()
        if re.search(r"legal|privacit|privacidad", u):
            return 0
        if re.search(r"equip|equipo|qui-som|quienes|nosaltres|nosotros|about|team|empresa", u):
            return 1
        return 2
    return sorted(pagines, key=clau)


def construir_context(pagines: list[Pagina], max_chars: int = 6000) -> str:
    """Reparteix el pressupost de caràcters entre pàgines (legal > equip > resta)."""
    ordre = ordenar_per_prioritat(pagines)
    restant, parts = max_chars, []
    for i, p in enumerate(ordre):
        quota = restant // (len(ordre) - i)
        tros = p.text[:quota]
        parts.append(f"## {p.url}\n{tros}")
        restant -= len(tros)
    return "\n\n".join(parts)


# ───────────────────────── 7. Regles dures post-IA ─────────────────────────
@dataclass
class ContextValidat:
    ubicacio_ok: bool
    vertical_ok: bool
    gatekeeper: Gatekeeper | None
    fonts_entrada: set[str]        # les mateixes cadenes 'canal|url' que s'han passat al model
    fita_recent: str | None        # la que ha trobat el sistema (no la que digui el model)
    telefon_valid: bool = False    # hi ha un telèfon espanyol vàlid (mínim per a SENSE_GATEKEEPER)


def aplicar_regles_dures(av, ctx: ContextValidat):
    """
    `av` és l'objecte d'avaluació del model (estat_decisio, score, decisor_nom,
    decisor_carrec, fonts_investigades, fita_recent, motiu_detallat_ia).
    El codi sempre té l'última paraula.
    """
    notes: list[str] = []

    if not (ctx.ubicacio_ok and ctx.vertical_ok):
        av.estat_decisio, av.score = "DESCARTAT", min(av.score, 25)
        notes.append("ubicació o vertical no verificades")

    gk = ctx.gatekeeper
    av.decisor_nom = gk.nom if gk else None            # el nom surt del sistema, mai del model
    av.decisor_carrec = gk.carrec if gk else None
    av.fonts_investigades = [f for f in av.fonts_investigades if f in ctx.fonts_entrada]
    av.fita_recent = ctx.fita_recent

    if av.estat_decisio in ("SELECCIONAT", "SELECCIONAT_SENSE_GATEKEEPER") and not gk:
        if PERMET_SENSE_GATEKEEPER and ctx.telefon_valid:
            av.estat_decisio, av.score = "SELECCIONAT_SENSE_GATEKEEPER", min(av.score, 79)
            notes.append("sense gatekeeper verificat")
        else:
            av.estat_decisio, av.score = "DESCARTAT", min(av.score, 49)
            notes.append("sense gatekeeper verificat"
                         + ("" if ctx.telefon_valid else " i sense telèfon espanyol vàlid"))

    if notes:
        av.motiu_detallat_ia = f"{av.motiu_detallat_ia} | [CODI] " + "; ".join(notes)
    return av
