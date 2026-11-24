"""Servei de gestió completa de Pressupostos: línies per seccions, plantilla HTML + PDF WeasyPrint, token HMAC i enviament Email/Telegram."""

import base64
import hashlib
import hmac
import logging
import re
import smtplib
import time
import urllib.parse
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import weasyprint  # type: ignore[import-untyped]
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.core.config import settings
from app.models.models import Client, Empresa, Pressupost
from app.services.sovereign_storage import SovereignStorageGateway
from app.services.verifactu import _blocked_url_fetcher, parse_hsl_to_css_and_hex

logger = logging.getLogger("sevalor.pressupost_service")

DEFAULT_VALIDESA_DIES = 30
TOKEN_TTL_SEGONS = 90 * 24 * 3600  # 90 dies

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
_jinja_env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)


def _q2(val: Decimal | float | int | str) -> Decimal:
    return Decimal(str(val)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _fmt_eur(val: Decimal | float | int | str) -> str:
    d = _q2(val)
    return f"{d:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def _fmt_qty(val: Decimal | float | int | str) -> str:
    d = Decimal(str(val)).normalize()
    s = format(d, "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s.replace(".", ",")


def _fmt_date_ca(val: Optional[str | date | datetime]) -> str:
    if not val:
        return "—"
    if isinstance(val, datetime):
        return val.strftime("%d/%m/%Y")
    if isinstance(val, date):
        return val.strftime("%d/%m/%Y")
    raw = str(val).strip()
    if not raw:
        return "—"
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(raw[:19], fmt).strftime("%d/%m/%Y")
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).strftime("%d/%m/%Y")
    except ValueError:
        return raw


def _parse_date(val: Optional[str | date | datetime]) -> date:
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    if val:
        raw = str(val).strip()
        for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
            try:
                return datetime.strptime(raw[:10], fmt).date()
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
        except ValueError:
            pass
    return datetime.now(timezone.utc).date()


# Mapa oficial INE de províncies per prefix de 2 dígits del Codi Postal espanyol
PROVINCIES_PER_PREFIX_CP: Dict[str, str] = {
    "01": "Àlava",
    "02": "Albacete",
    "03": "Alacant",
    "04": "Almeria",
    "05": "Àvila",
    "06": "Badajoz",
    "07": "Illes Balears",
    "08": "Barcelona",
    "09": "Burgos",
    "10": "Càceres",
    "11": "Cadis",
    "12": "Castelló",
    "13": "Ciudad Real",
    "14": "Còrdova",
    "15": "La Corunya",
    "16": "Conca",
    "17": "Girona",
    "18": "Granada",
    "19": "Guadalajara",
    "20": "Guipúscoa",
    "21": "Huelva",
    "22": "Osca",
    "23": "Jaén",
    "24": "Lleó",
    "25": "Lleida",
    "26": "La Rioja",
    "27": "Lugo",
    "28": "Madrid",
    "29": "Màlaga",
    "30": "Múrcia",
    "31": "Navarra",
    "32": "Ourense",
    "33": "Astúries",
    "34": "Palència",
    "35": "Las Palmas",
    "36": "Pontevedra",
    "37": "Salamanca",
    "38": "Santa Cruz de Tenerife",
    "39": "Cantàbria",
    "40": "Segòvia",
    "41": "Sevilla",
    "42": "Sòria",
    "43": "Tarragona",
    "44": "Terol",
    "45": "Toledo",
    "46": "València",
    "47": "Valladolid",
    "48": "Biscaia",
    "49": "Zamora",
    "50": "Saragossa",
    "51": "Ceuta",
    "52": "Melilla",
}

_RE_CP_ES = re.compile(r"\b((?:0[1-9]|[1-4]\d|5[0-2])\d{3})\b")
_RE_EMAIL_FALLBACK = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_RE_TEL_FALLBACK = re.compile(r"(?:\+?34[\s.-]*)?(?:[6789]\d{2}[\s.-]?\d{2,3}[\s.-]?\d{2,3}(?:[\s.-]?\d{2})?)")


def parsejar_adreca_fiscal(
    adreca_fiscal: Optional[str],
    codi_postal: Optional[str] = None,
    poblacio: Optional[str] = None,
    provincia: Optional[str] = None,
) -> Dict[str, Optional[str]]:
    """Separa una adreça fiscal composta (ex: 'C/ Major 12, 08500 Vic (Barcelona)') en carrer, CP, població i província.

    Respecta sempre els camps explícits (`codi_postal`, `poblacio`, `provincia`) quan ja venen informats.
    """
    raw_adr = (adreca_fiscal or "").strip()
    cp_out = (codi_postal or "").strip() or None
    pob_out = (poblacio or "").strip() or None
    prov_out = (provincia or "").strip() or None
    carrer_out: Optional[str] = raw_adr or None

    if raw_adr and (not cp_out or not pob_out or not prov_out):
        m_cp = _RE_CP_ES.search(raw_adr)
        if m_cp:
            cp_detectat = m_cp.group(1)
            abans = raw_adr[: m_cp.start()].strip(" ,;-/\n\t")
            despres = raw_adr[m_cp.end() :].strip(" ,;-/\n\t")

            if not cp_out:
                cp_out = cp_detectat
            if abans:
                carrer_out = abans

            # Extreure província entre parèntesis si hi és: "Vic (Barcelona)"
            m_paren = re.search(r"\(([^()]{2,60})\)\s*$", despres)
            if m_paren:
                if not prov_out:
                    prov_out = m_paren.group(1).strip()
                despres = despres[: m_paren.start()].strip(" ,;-/")

            # Si queden parts separades per coma: "Valls, Tarragona" o "Valls, Tarragona, Espanya"
            if despres:
                segments = [s.strip() for s in re.split(r"[,;/]", despres) if s.strip()]
                # Descartar país genèric al final
                if len(segments) >= 2 and segments[-1].lower() in ("espanya", "españa", "spain", "catalunya"):
                    segments.pop()
                if segments:
                    if not pob_out:
                        pob_out = segments[0]
                    if len(segments) >= 2 and not prov_out:
                        prov_out = segments[1]

    if cp_out and not prov_out:
        prov_out = PROVINCIES_PER_PREFIX_CP.get(cp_out[:2])

    return {
        "adreca": carrer_out,
        "codi_postal": cp_out,
        "poblacio": pob_out,
        "provincia": prov_out,
    }


def extreure_contacte_fallback(
    email: Optional[str],
    telefon: Optional[str],
    dades_contacte: Optional[str],
) -> Tuple[Optional[str], Optional[str]]:
    """Si email o telèfon falten al client però figuren a `dades_contacte`, els recupera netament."""
    em = (email or "").strip() or None
    tel = (telefon or "").strip() or None
    dades = (dades_contacte or "").strip()
    if dades:
        if not em:
            m_em = _RE_EMAIL_FALLBACK.search(dades)
            if m_em:
                em = m_em.group(0).strip()
        if not tel:
            m_tel = _RE_TEL_FALLBACK.search(dades)
            if m_tel:
                tel = m_tel.group(0).strip()
    return em, tel


def _construir_cp_poblacio_provincia(
    cp: Optional[str], poblacio: Optional[str], provincia: Optional[str]
) -> Optional[str]:
    parts: List[str] = []
    if cp and cp.strip():
        parts.append(cp.strip())
    if poblacio and poblacio.strip():
        parts.append(poblacio.strip())
    head = " ".join(parts).strip()
    prov = (provincia or "").strip()
    if head and prov:
        return f"{head} ({prov})"
    if head:
        return head
    if prov:
        return prov
    return None


def calcular_totals_pressupost_complet(
    linies: Sequence[Dict[str, Any]],
    descompte_global_pct: float = 0.0,
) -> Dict[str, Any]:
    """Calcula línies normalitzades (amb seccions i detall), subtotal brut, descompte global, base, IVA i total."""
    linies_norm: List[Dict[str, Any]] = []
    bases_brutes_per_iva: Dict[Decimal, Decimal] = {}

    for raw in linies:
        concepte = str(raw.get("concepte") or "").strip()[:200]
        if not concepte:
            continue
        seccio_raw = str(raw.get("seccio") or "").strip()[:120]
        detall_raw = str(raw.get("detall") or "").strip()[:600]
        tipus_linia = str(raw.get("tipus_linia") or "ALTRE").strip().upper()[:30]

        qt = Decimal(str(raw.get("quantitat") if raw.get("quantitat") is not None else 1))
        preu = Decimal(str(raw.get("preu_unitari") if raw.get("preu_unitari") is not None else 0))
        dto = Decimal(str(raw.get("descompte_pct") if raw.get("descompte_pct") is not None else 0))
        iva = Decimal(str(raw.get("tipus_iva") if raw.get("tipus_iva") is not None else 21))

        qt = max(Decimal("0.001"), qt)
        preu = max(Decimal("0.00"), preu)
        dto = min(Decimal("100.00"), max(Decimal("0.00"), dto))
        iva = max(Decimal("0.00"), iva)

        factor = Decimal("1.00") - (dto / Decimal("100.00"))
        subtotal = _q2(qt * preu * factor)
        bases_brutes_per_iva[iva] = bases_brutes_per_iva.get(iva, Decimal("0.00")) + subtotal

        linies_norm.append(
            {
                "article_id": str(raw["article_id"]) if raw.get("article_id") else None,
                "vehicle_id": str(raw["vehicle_id"]) if raw.get("vehicle_id") else None,
                "eina_id": str(raw["eina_id"]) if raw.get("eina_id") else None,
                "operari_id": str(raw["operari_id"]) if raw.get("operari_id") else None,
                "seccio": seccio_raw or None,
                "tipus_linia": tipus_linia,
                "concepte": concepte,
                "detall": detall_raw or None,
                "quantitat": float(qt),
                "preu_unitari": float(preu),
                "descompte_pct": float(dto),
                "tipus_iva": float(iva),
                "subtotal": float(subtotal),
            }
        )

    subtotal_brut = _q2(sum(bases_brutes_per_iva.values(), Decimal("0.00")))
    dto_global = min(
        Decimal("100.00"), max(Decimal("0.00"), Decimal(str(descompte_global_pct or 0)))
    )
    factor_global = Decimal("1.00") - (dto_global / Decimal("100.00"))

    bases_netes_per_iva: Dict[Decimal, Decimal] = {}
    for tipus_k, base_b in bases_brutes_per_iva.items():
        bases_netes_per_iva[tipus_k] = _q2(base_b * factor_global)

    base_total = _q2(sum(bases_netes_per_iva.values(), Decimal("0.00")))
    descompte_global_import = _q2(subtotal_brut - base_total)

    desglossament_iva: List[Dict[str, float]] = []
    iva_total = Decimal("0.00")
    for tipus_k in sorted(bases_netes_per_iva.keys()):
        b_net = bases_netes_per_iva[tipus_k]
        quota_k = _q2(b_net * (tipus_k / Decimal("100.00")))
        iva_total += quota_k
        desglossament_iva.append(
            {
                "tipus_iva": float(tipus_k),
                "base": float(b_net),
                "quota": float(quota_k),
            }
        )

    iva_total = _q2(iva_total)
    total = _q2(base_total + iva_total)
    return {
        "linies": linies_norm,
        "subtotal_brut": float(subtotal_brut),
        "descompte_global_pct": float(dto_global),
        "descompte_global_import": float(descompte_global_import),
        "base_imposable": float(base_total),
        "quota_iva": float(iva_total),
        "total": float(total),
        "desglossament_iva": desglossament_iva,
    }


def calcular_totals_linies_pressupost(
    linies: Sequence[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], float, float, float]:
    """Compatibilitat enrere: calcula (linies_norm, base_imposable, quota_iva, total)."""
    res = calcular_totals_pressupost_complet(linies, descompte_global_pct=0.0)
    return res["linies"], res["base_imposable"], res["quota_iva"], res["total"]


def generar_token_acceptacio_pressupost(
    empresa_id: uuid.UUID,
    pressupost_id: uuid.UUID,
    ttl_seconds: int = TOKEN_TTL_SEGONS,
) -> str:
    """Genera un token HMAC-SHA256 verificable per a l'enllaç públic d'acceptació del pressupost."""
    exp = int(time.time()) + ttl_seconds
    payload_raw = f"{empresa_id}.{pressupost_id}.{exp}".encode("utf-8")
    payload_b64 = base64.urlsafe_b64encode(payload_raw).decode("ascii").rstrip("=")
    sig = hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        payload_b64.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()[:32]
    return f"{payload_b64}.{sig}"


def verificar_token_acceptacio_pressupost(token: str) -> Optional[Tuple[uuid.UUID, uuid.UUID]]:
    """Verifica el token HMAC públic i retorna (empresa_id, pressupost_id) o None si és invàlid/caducat."""
    if not token or "." not in token:
        return None
    try:
        payload_b64, sig = token.rsplit(".", 1)
        expected_sig = hmac.new(
            settings.SECRET_KEY.encode("utf-8"),
            payload_b64.encode("ascii"),
            hashlib.sha256,
        ).hexdigest()[:32]
        if not hmac.compare_digest(sig, expected_sig):
            return None
        pad = "=" * ((4 - len(payload_b64) % 4) % 4)
        decoded = base64.urlsafe_b64decode(payload_b64 + pad).decode("utf-8")
        emp_str, pres_str, exp_str = decoded.split(".")
        if int(exp_str) < int(time.time()):
            return None
        return uuid.UUID(emp_str), uuid.UUID(pres_str)
    except Exception:
        return None


def construir_acceptacio_url(base_origin: Optional[str], token: str) -> str:
    """Construeix la URL pública d'acceptació per al client."""
    if base_origin:
        return f"{base_origin.rstrip('/')}/pressupost/{token}"
    domain = settings.DOMAIN or "sevalor.app"
    proto = "http" if "localhost" in domain or "127.0.0.1" in domain else "https"
    return f"{proto}://{domain}/pressupost/{token}"


async def carregar_detalls_pressupostos_map(
    db: Any,
    empresa_id: uuid.UUID,
) -> Dict[str, Dict[str, Any]]:
    """Llegeix els detalls JSON dels pressupostos des de SovereignStorageGateway en batch."""
    entitats = await SovereignStorageGateway.llegir_entitats_json(db, empresa_id, "pressupostos")
    mapa: Dict[str, Dict[str, Any]] = {}
    for ent in entitats:
        eid = ent.get("id")
        if eid and not str(ent.get("origen", "")).startswith("COPILOT_IA"):
            mapa[str(eid)] = ent
    return mapa


async def desar_detalls_pressupost_disc(
    db: Any,
    empresa_id: uuid.UUID,
    pressupost: Pressupost,
    detalls: Dict[str, Any],
) -> None:
    """Desa la fitxa completa del pressupost (línies, recursos, condicions, notes) al disc sobirà."""
    payload = {
        **detalls,
        "id": str(pressupost.id),
        "client_id": str(pressupost.client_id),
        "numero": pressupost.numero,
        "total": float(pressupost.total or 0.0),
        "estat": pressupost.estat,
        "created_at": pressupost.created_at.isoformat() if pressupost.created_at else None,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        ruta = await SovereignStorageGateway.desar_entitat_json(
            db=db,
            empresa_id=empresa_id,
            categoria="pressupostos",
            item_id=str(pressupost.id),
            dades=payload,
        )
        if not str(ruta).startswith("transit://"):
            await SovereignStorageGateway.drenar_cua_transit_empresa(db, empresa_id)
    except Exception as exc:
        logger.warning("No s'ha pogut sincronitzar el pressupost %s al disc: %s", pressupost.id, exc)


def renderitzar_html_pressupost(
    *,
    empresa: Optional[Empresa],
    client: Optional[Client],
    pressupost: Pressupost,
    detalls: Dict[str, Any],
    logotip_bytes: Optional[bytes] = None,
    logotip_mime: str = "image/png",
) -> str:
    """Renderitza la plantilla HTML oficial del pressupost (Chameleon HSL, sense QR Veri*factu, auto-escaping XSS)."""
    primari_hsl = empresa.primari_hsl if empresa and empresa.primari_hsl else "166 22% 24%"
    accent_css, tint_css, _ = parse_hsl_to_css_and_hex(primari_hsl)

    logotip_data_uri = None
    if logotip_bytes:
        b64_logo = base64.b64encode(logotip_bytes).decode("ascii")
        logotip_data_uri = f"data:{logotip_mime};base64,{b64_logo}"

    # Emissor
    emp_nom = (empresa.nom if empresa and empresa.nom else "Sevalor Suite").strip()
    emp_rao_raw = (
        getattr(empresa, "rao_social_fiscal", None) if empresa else None
    )
    emp_rao = str(emp_rao_raw or emp_nom).strip()
    emp_eslogan = (
        getattr(empresa, "eslogan_activitat", None) or getattr(empresa, "vertical", None) or ""
    ).strip() or None
    emp_nif = (empresa.nif if empresa and empresa.nif else "").strip() or None
    emp_adreca = (empresa.adreca if empresa and empresa.adreca else "").strip() or None
    emp_cp = getattr(empresa, "codi_postal", None) if empresa else None
    emp_pob = getattr(empresa, "poblacio", None) if empresa else None
    emp_prov = getattr(empresa, "provincia", None) if empresa else None
    emp_cp_pob = _construir_cp_poblacio_provincia(emp_cp, emp_pob, emp_prov)
    emp_tel = (getattr(empresa, "telefon_facturacio", None) or "").strip() if empresa else ""
    emp_mail = (getattr(empresa, "email_facturacio", None) or "").strip() if empresa else ""
    emp_contacte_parts = [p for p in (emp_tel, emp_mail) if p]
    emp_rm = (getattr(empresa, "dades_registre_mercantil", None) or "").strip() if empresa else ""

    # Client (prioritza snapshot del pressupost amb fallback a fitxa del client i parser d'adreça fiscal)
    cli_codi = str(
        detalls.get("client_codi") or (getattr(client, "codi", None) if client else None) or ""
    ).strip() or None
    cli_rao = str(
        detalls.get("client_rao_social")
        or (client.rao_social if client else None)
        or "Client"
    ).strip()
    cli_nif = str(
        detalls.get("client_nif") or (client.nif if client else None) or ""
    ).strip() or None
    cli_adreca_raw = str(
        detalls.get("client_adreca") or (client.adreca_fiscal if client else None) or ""
    ).strip() or None
    cli_cp_raw = detalls.get("client_codi_postal") or (getattr(client, "codi_postal", None) if client else None)
    cli_pob_raw = detalls.get("client_poblacio") or (getattr(client, "poblacio", None) if client else None)
    cli_prov_raw = detalls.get("client_provincia") or (getattr(client, "provincia", None) if client else None)
    parsed_adr = parsejar_adreca_fiscal(cli_adreca_raw, cli_cp_raw, cli_pob_raw, cli_prov_raw)
    cli_adreca = parsed_adr["adreca"]
    cli_cp_pob = _construir_cp_poblacio_provincia(
        parsed_adr["codi_postal"], parsed_adr["poblacio"], parsed_adr["provincia"]
    )
    cli_persona = str(
        detalls.get("client_persona_contacte")
        or (getattr(client, "persona_contacte", None) if client else None)
        or ""
    ).strip()
    cli_dades_contacte = str(
        detalls.get("client_dades_contacte")
        or (getattr(client, "dades_contacte", None) if client else None)
        or ""
    ).strip() or None
    cli_email_raw = str(
        detalls.get("client_email") or (client.email if client else None) or ""
    ).strip()
    cli_tel_raw = str(
        detalls.get("client_telefon") or (client.telefon if client else None) or ""
    ).strip()
    cli_email_fb, cli_tel_fb = extreure_contacte_fallback(cli_email_raw, cli_tel_raw, cli_dades_contacte)
    cli_email = cli_email_fb or ""
    cli_tel = cli_tel_fb or ""

    cli_contacte_parts: List[str] = []
    if cli_persona:
        cli_contacte_parts.append(f"Atenció: {cli_persona}")
    if cli_tel:
        cli_contacte_parts.append(cli_tel)
    if cli_email:
        cli_contacte_parts.append(cli_email)

    # Metadades
    data_pres_dt = _parse_date(detalls.get("data_pressupost") or pressupost.created_at)
    dies_validesa = int(detalls.get("validesa_dies") or DEFAULT_VALIDESA_DIES)
    data_validesa_dt = data_pres_dt + timedelta(days=dies_validesa)
    referencia_client = str(detalls.get("referencia_client") or "").strip() or cli_codi or "—"
    elaborat_per = str(detalls.get("elaborat_per") or "").strip() or emp_nom

    # Objecte
    titol = str(detalls.get("titol") or f"Pressupost {pressupost.numero}").strip()
    descripcio = str(detalls.get("descripcio") or "").strip() or None
    adreca_obra = str(detalls.get("adreca_obra") or "").strip() or None

    # Recursos operatius (suport multi-slot vehicle/maquinària pesant + km + hores)
    def _format_slot_desplacament(slot: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
        v_nom = str(slot.get("vehicle_nom") or "").strip() or None
        s_km = slot.get("km") if "km" in slot else slot.get("desplacament_km")
        s_pkm = slot.get("preu_km") if "preu_km" in slot else slot.get("desplacament_preu_km")
        s_fix = slot.get("import_fix") if "import_fix" in slot else slot.get("desplacament_import_fix")
        s_hores = slot.get("hores") if "hores" in slot else slot.get("desplacament_hores")
        s_phora = slot.get("preu_hora") if "preu_hora" in slot else slot.get("desplacament_preu_hora")
        parts: List[str] = []
        if s_km and float(s_km) > 0:
            if s_pkm and float(s_pkm) > 0:
                parts.append(f"{_fmt_qty(s_km)} km ({_fmt_eur(s_pkm)} €/km)")
            else:
                parts.append(f"{_fmt_qty(s_km)} km")
        if s_fix and float(s_fix) > 0:
            parts.append(f"tarifa fixa {_fmt_eur(s_fix)} €")
        if s_hores and float(s_hores) > 0:
            if s_phora and float(s_phora) > 0:
                parts.append(f"{_fmt_qty(s_hores)} h ({_fmt_eur(s_phora)} €/h)")
            else:
                parts.append(f"{_fmt_qty(s_hores)} h")
        return v_nom, (" + ".join(parts) if parts else None)

    raw_slots = detalls.get("vehicles_desplacaments") or []
    vehicles_resums: List[str] = []
    desp_resums: List[str] = []
    if isinstance(raw_slots, list) and raw_slots:
        for sl in raw_slots:
            if not isinstance(sl, dict):
                continue
            v_n, d_r = _format_slot_desplacament(sl)
            if v_n and d_r:
                vehicles_resums.append(f"{v_n}: {d_r}")
            elif v_n:
                vehicles_resums.append(v_n)
            elif d_r:
                desp_resums.append(d_r)
        vehicle_nom = " | ".join(vehicles_resums) if vehicles_resums else (str(detalls.get("vehicle_nom") or "").strip() or None)
        desplacament_resum = " | ".join(desp_resums) if desp_resums else None
    else:
        vehicle_nom, desplacament_resum = _format_slot_desplacament(detalls)

    eines_resum_list = detalls.get("eines_resum") or []
    eines_labels: List[str] = []
    for eina in eines_resum_list:
        if isinstance(eina, dict):
            nom_e = str(eina.get("nom") or "").strip()
            mod_e = str(eina.get("model") or "").strip()
            qt_e = eina.get("quantitat")
            ut_e = str(eina.get("unitat") or "").strip()
            cost_e = eina.get("cost_eur")
            if nom_e:
                base_lbl = f"{nom_e} ({mod_e})" if mod_e else nom_e
                extra_e: List[str] = []
                if qt_e and float(qt_e) > 0 and (ut_e or (cost_e and float(cost_e) > 0)):
                    extra_e.append(f"{_fmt_qty(qt_e)} {ut_e or 'ut'}")
                if cost_e and float(cost_e) > 0:
                    extra_e.append(f"{_fmt_eur(cost_e)} €/{ut_e or 'ut'}")
                if extra_e:
                    base_lbl = f"{base_lbl} — {' · '.join(extra_e)}"
                eines_labels.append(base_lbl)
        elif isinstance(eina, str) and eina.strip():
            eines_labels.append(eina.strip())
    eines_text = ", ".join(eines_labels) if eines_labels else None
    mostrar_recursos = bool(vehicle_nom or desplacament_resum or eines_text)

    # Partides agrupades per secció conservant ordre d'aparició
    raw_linies = detalls.get("linies") or []
    descompte_global_pct = float(detalls.get("descompte_global_pct") or 0.0)
    if raw_linies:
        calc = calcular_totals_pressupost_complet(
            raw_linies, descompte_global_pct=descompte_global_pct
        )
        linies_calc = calc["linies"]
        subtotal_dec = _q2(calc["subtotal_brut"])
        dto_global_pct_dec = _q2(calc["descompte_global_pct"])
        dto_global_imp_dec = _q2(calc["descompte_global_import"])
        base_dec = _q2(calc["base_imposable"])
        total_dec = _q2(calc["total"])
        desglossament_iva_raw = calc["desglossament_iva"]
    else:
        total_dec = _q2(pressupost.total or 0.0)
        raw_base_det = detalls.get("base_imposable")
        base_dec = _q2(raw_base_det) if raw_base_det is not None else total_dec
        iva_dec = _q2(detalls.get("quota_iva") or 0.0)
        subtotal_dec = base_dec
        dto_global_pct_dec = Decimal("0.00")
        dto_global_imp_dec = Decimal("0.00")
        iva_pct_est = _q2((iva_dec / base_dec) * Decimal("100")) if base_dec > 0 else Decimal("0.00")
        linies_calc = [
            {
                "seccio": None,
                "concepte": titol,
                "detall": None,
                "quantitat": 1.0,
                "preu_unitari": float(base_dec),
                "descompte_pct": 0.0,
                "tipus_iva": float(iva_pct_est),
                "subtotal": float(base_dec),
            }
        ]
        desglossament_iva_raw = [
            {"tipus_iva": float(iva_pct_est), "base": float(base_dec), "quota": float(iva_dec)}
        ]

    seccions_linies: List[Dict[str, Any]] = []
    for lin in linies_calc:
        sec_nom = (lin.get("seccio") or "").strip() or None
        dto_lin = _q2(lin.get("descompte_pct") or 0.0)
        lin_view = {
            "concepte": lin.get("concepte") or "",
            "detall": lin.get("detall") or None,
            "quantitat_fmt": _fmt_qty(lin.get("quantitat") or 1),
            "preu_unitari_fmt": _fmt_eur(lin.get("preu_unitari") or 0),
            "descompte_fmt": _fmt_qty(dto_lin),
            "te_descompte": dto_lin > Decimal("0.00"),
            "iva_fmt": _fmt_qty(lin.get("tipus_iva") if lin.get("tipus_iva") is not None else 21),
            "import_fmt": _fmt_eur(lin.get("subtotal") or 0),
        }
        if seccions_linies and seccions_linies[-1]["nom"] == sec_nom:
            seccions_linies[-1]["linies"].append(lin_view)
        else:
            seccions_linies.append({"nom": sec_nom, "linies": [lin_view]})

    desglossament_iva_view = [
        {
            "tipus_iva_fmt": _fmt_qty(item["tipus_iva"]),
            "base_fmt": _fmt_eur(item["base"]),
            "quota_fmt": _fmt_eur(item["quota"]),
        }
        for item in desglossament_iva_raw
    ]

    # Condicions & acompte
    forma_pagament = str(detalls.get("forma_pagament") or "").strip() or "Transferència bancària"
    pct_acompte = max(Decimal("0.00"), min(Decimal("100.00"), _q2(detalls.get("percentatge_acompte") or 0)))
    import_acompte = _q2(total_dec * pct_acompte / Decimal("100.00"))
    termini_execucio = str(detalls.get("termini_execucio") or "").strip() or None

    # Notes i acceptació
    notes_exclusions = str(detalls.get("notes_exclusions") or "").strip() or None
    mencio_legal = str(detalls.get("mencio_legal") or "").strip() or None
    nom_signant = str(detalls.get("nom_signant_client") or "").strip() or None
    data_acceptacio = (
        _fmt_date_ca(detalls.get("data_resposta_client"))
        if pressupost.estat == "APROVAT" and detalls.get("data_resposta_client")
        else None
    )

    # Peu mercantil
    peu_parts = [emp_rao]
    if emp_nif:
        peu_parts.append(f"NIF/CIF {emp_nif}")
    if emp_adreca:
        peu_parts.append(emp_adreca)
    if emp_cp_pob:
        peu_parts.append(emp_cp_pob)
    if emp_rm:
        peu_parts.append(emp_rm)

    template = _jinja_env.get_template("pressupost.html")
    return template.render(
        accent_hsl_css=accent_css,
        tint_hsl_css=tint_css,
        logotip_data_uri=logotip_data_uri,
        numero=pressupost.numero,
        emissor={
            "nom_comercial": emp_nom,
            "rao_social": emp_rao,
            "eslogan": emp_eslogan,
            "nif": emp_nif,
            "adreca": emp_adreca,
            "cp_poblacio_provincia": emp_cp_pob,
            "contacte_linia": " · ".join(emp_contacte_parts) if emp_contacte_parts else None,
        },
        client={
            "codi": cli_codi,
            "rao_social": cli_rao,
            "nif": cli_nif,
            "adreca": cli_adreca,
            "cp_poblacio_provincia": cli_cp_pob,
            "contacte_linia": " · ".join(cli_contacte_parts) if cli_contacte_parts else None,
            "dades_contacte": cli_dades_contacte,
        },
        meta={
            "data_pressupost": _fmt_date_ca(data_pres_dt),
            "data_validesa": _fmt_date_ca(data_validesa_dt),
            "referencia_client": referencia_client,
            "elaborat_per": elaborat_per,
        },
        objecte={
            "titol": titol,
            "descripcio": descripcio,
            "adreca_obra": adreca_obra,
        },
        recursos={
            "mostrar": mostrar_recursos,
            "vehicle_nom": vehicle_nom,
            "desplacament_resum": desplacament_resum,
            "eines_text": eines_text,
        },
        seccions_linies=seccions_linies,
        totals={
            "subtotal_fmt": _fmt_eur(subtotal_dec),
            "te_descompte_global": dto_global_pct_dec > Decimal("0.00") and dto_global_imp_dec > Decimal("0.00"),
            "descompte_global_pct_fmt": _fmt_qty(dto_global_pct_dec),
            "descompte_global_import_fmt": _fmt_eur(dto_global_imp_dec),
            "base_imposable_fmt": _fmt_eur(base_dec),
            "total_fmt": _fmt_eur(total_dec),
        },
        desglossament_iva=desglossament_iva_view,
        condicions={
            "forma_pagament": forma_pagament,
            "te_acompte": pct_acompte > Decimal("0.00"),
            "percentatge_acompte_fmt": _fmt_qty(pct_acompte),
            "import_acompte_fmt": _fmt_eur(import_acompte),
            "termini_execucio": termini_execucio,
            "dies_validesa": dies_validesa,
        },
        notes={
            "notes_exclusions": notes_exclusions,
            "mencio_legal": mencio_legal,
        },
        acceptacio={
            "nom_signant": nom_signant,
            "data_acceptacio": data_acceptacio,
        },
        peu_mercantil=" · ".join(peu_parts),
    )


def generar_pdf_pressupost_bytes(
    *,
    empresa: Optional[Empresa],
    client: Optional[Client],
    pressupost: Pressupost,
    detalls: Dict[str, Any],
    acceptacio_url: Optional[str] = None,
    logotip_bytes: Optional[bytes] = None,
    logotip_mime: str = "image/png",
) -> bytes:
    """Genera el PDF corporatiu del pressupost amb la plantilla HTML oficial i WeasyPrint (url_fetcher bloquejat)."""
    _ = acceptacio_url  # Un pressupost no porta QR tributari ni enllaç imprès a la capçalera segons plantilla oficial
    html_str = renderitzar_html_pressupost(
        empresa=empresa,
        client=client,
        pressupost=pressupost,
        detalls=detalls,
        logotip_bytes=logotip_bytes,
        logotip_mime=logotip_mime,
    )
    pdf_bytes = weasyprint.HTML(
        string=html_str,
        base_url=str(TEMPLATE_DIR),
        url_fetcher=_blocked_url_fetcher,
    ).write_pdf()
    return bytes(pdf_bytes or b"")


def enviar_pressupost_email_smtp(
    *,
    empresa_nom: str,
    destinatari_email: str,
    assumpte: str,
    cos_missatge: str,
    numero_pressupost: str,
    pdf_bytes: bytes,
) -> Tuple[bool, Optional[str]]:
    """Envia el pressupost per SMTP real amb el PDF adjunt. Retorna (True, None) o (False, motiu)."""
    smtp_host = (settings.STALWART_SMTP_HOST or "").strip()
    smtp_port = int(settings.STALWART_SMTP_PORT or 587)
    smtp_user = (settings.STALWART_USER or "").strip()
    smtp_pass = settings.STALWART_PASSWORD

    if not smtp_host or (smtp_host in ("localhost", "127.0.0.1") and not smtp_pass):
        return (
            False,
            "El servidor de correu SMTP no està configurat a l'entorn (STALWART_SMTP_HOST / STALWART_PASSWORD).",
        )

    msg = EmailMessage()
    msg["From"] = f"{empresa_nom} <{smtp_user or 'no-reply@sevalor.app'}>"
    msg["To"] = destinatari_email.strip()
    msg["Subject"] = assumpte.strip()
    msg.set_content(cos_missatge)
    msg.add_attachment(
        pdf_bytes,
        maintype="application",
        subtype="pdf",
        filename=f"PRESSUPOST_{numero_pressupost}.pdf",
    )

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=10.0) as server:
            server.ehlo()
            if smtp_port in (587, 25):
                try:
                    server.starttls()
                    server.ehlo()
                except smtplib.SMTPException:
                    pass
            if smtp_user and smtp_pass:
                server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        return True, None
    except Exception as exc:
        logger.warning("Error enviant pressupost %s per SMTP (%s:%s): %s", numero_pressupost, smtp_host, smtp_port, exc)
        return False, f"No s'ha pogut connectar al servidor SMTP ({smtp_host}:{smtp_port}): {exc}"


def construir_mailto_url(email_desti: str, assumpte: str, cos: str) -> str:
    """Construeix una URL mailto: segura per obrir al client de correu local si no hi ha SMTP."""
    query = urllib.parse.urlencode({"subject": assumpte, "body": cos}, quote_via=urllib.parse.quote)
    return f"mailto:{urllib.parse.quote(email_desti.strip(), safe='@')}?{query}"
