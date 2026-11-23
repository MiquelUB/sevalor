"""
Motor Unificat de Facturació Legal Veri*factu (RD 1007/2023 i Ordre HAC/1177/2024).

Implementa:
- Encadenament SHA-256 oficial d'Alta (Art. 13.1) i Anul·lació (Art. 13.2) en majúscules hex (64 chars).
- Codi QR tributari oficial AEAT (Art. 20-21): ISO/IEC 18004 nivell M, 35x35 mm, marge blanc (border=4).
- Format canònic de sèrie/número: <SERIE>-<EXERCICI>-<NUM:04d> (ex. F-2026-0001, R-2026-0001, SAAS-2026-0001).
- Bloqueig pessimista SELECT FOR UPDATE sobre verifactu_cadena_tenant i series_fiscals_verifactu.
- Renderització HTML -> PDF amb Jinja2 (autoescape=True) + WeasyPrint (url_fetcher bloquejat anti-SSRF)
  i tokens HSL del Chameleon UI Engine.
- Xifratge simètric AES-256-GCM per a IBAN d'emissor i contrasenya de certificat PKCS#12 (.p12).
"""

from __future__ import annotations

import base64
import colorsys
import hashlib
import io
import logging
import os
import urllib.parse
import uuid
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence
from zoneinfo import ZoneInfo

import jinja2
import segno
import weasyprint
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from weasyprint.urls import URLFetcher as _WeasyURLFetcher

from app.core.config import settings
from app.models.models import SerieFiscalVerifactu, VerifactuCadenaTenant

logger = logging.getLogger("verifactu")

MADRID_TZ = ZoneInfo("Europe/Madrid")
TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"

QR_AEAT_URLS = {
    ("PREPRODUCCIO", "VERIFACTU"): "https://prewww2.aeat.es/wlpl/TIKE-CONT/ValidarQR",
    ("PRODUCCIO", "VERIFACTU"): "https://www2.agenciatributaria.gob.es/wlpl/TIKE-CONT/ValidarQR",
    ("PREPRODUCCIO", "NO_VERIFACTU"): "https://prewww2.aeat.es/wlpl/TIKE-CONT/ValidarQRNoVerifactu",
    ("PRODUCCIO", "NO_VERIFACTU"): "https://www2.agenciatributaria.gob.es/wlpl/TIKE-CONT/ValidarQRNoVerifactu",
}

TIPUS_FACTURA_LABELS: Dict[str, str] = {
    "F1": "F1 · Factura ordinària (Art. 6, 7.2 i 7.3 RD 1619/2012)",
    "F2": "F2 · Factura simplificada",
    "F3": "F3 · Factura emesa en substitució de factures simplificades",
    "R1": "R1 · Factura rectificativa (Art. 80.1, 80.2 i 80.6 LIVA)",
    "R2": "R2 · Factura rectificativa per concurs de creditors (Art. 80.3 LIVA)",
    "R3": "R3 · Factura rectificativa per crèdit incobrable (Art. 80.4 LIVA)",
    "R4": "R4 · Factura rectificativa (Resta de causes)",
    "R5": "R5 · Factura rectificativa en factures simplificades",
}


def _q2(val: Any) -> Decimal:
    return Decimal(str(val or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _fmt_eur(val: Any) -> str:
    return f"{_q2(val):.2f}"


def _fmt_qty(val: Any) -> str:
    d = Decimal(str(val or 0))
    if d == d.to_integral_value():
        return f"{int(d)}"
    return f"{d.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):.2f}"


# ---------------------------------------------------------------------------
# Criptografia Simètrica AES-256-GCM (IBAN d'emissor i Passphrase .p12)
# ---------------------------------------------------------------------------
_ENC_PREFIX = "VFENC1:"


def _derive_aes_key() -> bytes:
    secret = (settings.SECRET_KEY or "sevalor-default-key").encode("utf-8")
    return hashlib.sha256(b"sevalor-verifactu-aes256|" + secret).digest()


def xifrar_secret_verifactu(plain_text: Optional[str]) -> Optional[str]:
    if not plain_text:
        return None
    s = plain_text.strip()
    if not s:
        return None
    if s.startswith(_ENC_PREFIX):
        return s
    aes = AESGCM(_derive_aes_key())
    nonce = os.urandom(12)
    ct = aes.encrypt(nonce, s.encode("utf-8"), b"verifactu-v1")
    token = base64.urlsafe_b64encode(nonce + ct).decode("ascii")
    return f"{_ENC_PREFIX}{token}"


def desxifrar_secret_verifactu(cipher_text: Optional[str]) -> str:
    if not cipher_text:
        return ""
    s = cipher_text.strip()
    if not s:
        return ""
    if not s.startswith(_ENC_PREFIX):
        return s
    try:
        raw = base64.urlsafe_b64decode(s[len(_ENC_PREFIX) :].encode("ascii"))
        nonce, ct = raw[:12], raw[12:]
        aes = AESGCM(_derive_aes_key())
        return aes.decrypt(nonce, ct, b"verifactu-v1").decode("utf-8")
    except Exception as exc:
        logger.warning("Error desxifrant secret Veri*factu: %s", exc)
        return ""


# ---------------------------------------------------------------------------
# Chameleon UI: Conversió segura HSL -> CSS HSL + RGB Hex
# ---------------------------------------------------------------------------
def parse_hsl_to_css_and_hex(hsl_str: Optional[str]) -> tuple[str, str, str]:
    """
    Converteix '210 100% 15%' o '150 40 20' en:
    (accent_hsl_css, tint_hsl_css, hex_color_per_reportlab)
    """
    raw = (hsl_str or "166 22% 24%").replace("%", "").replace(",", " ").strip()
    parts = [p for p in raw.split() if p]
    try:
        h = float(parts[0]) % 360.0
        s = max(0.0, min(100.0, float(parts[1])))
        l_val = max(0.0, min(100.0, float(parts[2])))
    except (IndexError, ValueError):
        h, s, l_val = 166.0, 22.0, 24.0

    accent_css = f"hsl({int(round(h))}, {int(round(s))}%, {int(round(l_val))}%)"
    tint_s = max(8, min(30, int(round(s * 0.35))))
    tint_css = f"hsl({int(round(h))}, {tint_s}%, 96%)"

    r, g, b = colorsys.hls_to_rgb(h / 360.0, l_val / 100.0, s / 100.0)
    hex_str = f"#{int(round(r * 255)):02x}{int(round(g * 255)):02x}{int(round(b * 255)):02x}"
    return accent_css, tint_css, hex_str


# ---------------------------------------------------------------------------
# Formatadors i Càlculs Oficials Ordre HAC/1177/2024 (Art. 13, 20 i 21)
# ---------------------------------------------------------------------------
def format_num_serie(serie: str, exercici: int, numero: int) -> str:
    """
    Format canònic unificat per a PDF, QR i XML AEAT: <SERIE>-<EXERCICI>-<NUM:04d>.
    Exemples: F-2026-0001, R-2026-0001, SAAS-2026-0001.
    """
    s = (serie or "F").strip().upper()
    ex_str = str(int(exercici))
    num_int = int(numero)
    if s == ex_str:
        return f"F-{ex_str}-{num_int:04d}"
    if s.endswith(f"-{ex_str}"):
        return f"{s}-{num_int:04d}"
    return f"{s}-{ex_str}-{num_int:04d}"


def format_fecha_aeat(data_val: date | datetime | str) -> str:
    """Converteix una data al format obligatori AEAT DD-MM-YYYY."""
    if isinstance(data_val, datetime):
        return data_val.date().strftime("%d-%m-%Y")
    if isinstance(data_val, date):
        return data_val.strftime("%d-%m-%Y")
    s = str(data_val or "").strip()
    if len(s) >= 10:
        s10 = s[:10]
        if s10[4:5] == "-" and s10[7:8] == "-":
            y, m, d = s10.split("-")
            return f"{d}-{m}-{y}"
        if s10[2:3] == "-" and s10[5:6] == "-":
            return s10
        if s10[2:3] == "/" and s10[5:6] == "/":
            return s10.replace("/", "-")
    return datetime.now(MADRID_TZ).strftime("%d-%m-%Y")


def generar_timestamp_huso_aeat(dt: Optional[datetime] = None) -> str:
    """Retorna FechaHoraHusoGenRegistro en format ISO 8601 amb fus horari (YYYY-MM-DDTHH:MM:SS+01:00)."""
    target = dt.astimezone(MADRID_TZ) if dt and dt.tzinfo else (dt.replace(tzinfo=MADRID_TZ) if dt else datetime.now(MADRID_TZ))
    return target.isoformat(timespec="seconds")


def normalitzar_huella_anterior(hash_anterior: Optional[str]) -> str:
    """Al primer registre de la cadena, Huella ha de ser cadena buida ''."""
    if not hash_anterior:
        return ""
    h = str(hash_anterior).strip()
    if h == "0" * 64 or h.upper() in ("GENESIS", "ESBORRANY_PREFACTURA", "PRIMER_REGISTRO", "NONE"):
        return ""
    return h.upper()


def calcular_huella_alta_hac1177(
    *,
    nif_emissor: str,
    num_serie_factura: str,
    fecha_expedicion: date | datetime | str,
    tipus_factura: str = "F1",
    cuota_total: float | Decimal,
    importe_total: float | Decimal,
    hash_anterior: Optional[str],
    fecha_hora_huso: Optional[str] = None,
) -> tuple[str, str, str]:
    """
    Calcula l'empremta SHA-256 d'un registre d'alta segons l'Art. 13.1 de l'Ordre HAC/1177/2024.

    Cadena exacta:
    IDEmisorFactura=<NIF>&NumSerieFactura=<NUMSERIE>&FechaExpedicionFactura=<DD-MM-YYYY>&TipoFactura=<F1>&CuotaTotal=<0.00>&ImporteTotal=<0.00>&Huella=<ANTERIOR_O_BUIT>&FechaHoraHusoGenRegistro=<ISO8601>

    Returns:
        (huella_sha256_upper, cadena_raw, fecha_hora_huso_utilitzada)
    """
    nif_clean = (nif_emissor or "").strip().upper()
    num_serie_clean = (num_serie_factura or "").strip()
    fecha_dd_mm_yyyy = format_fecha_aeat(fecha_expedicion)
    tipus_clean = (tipus_factura or "F1").strip().upper()
    cuota_str = _fmt_eur(cuota_total)
    importe_str = _fmt_eur(importe_total)
    huella_ant = normalitzar_huella_anterior(hash_anterior)
    ts_huso = (fecha_hora_huso or "").strip() or generar_timestamp_huso_aeat()

    raw = (
        f"IDEmisorFactura={nif_clean}"
        f"&NumSerieFactura={num_serie_clean}"
        f"&FechaExpedicionFactura={fecha_dd_mm_yyyy}"
        f"&TipoFactura={tipus_clean}"
        f"&CuotaTotal={cuota_str}"
        f"&ImporteTotal={importe_str}"
        f"&Huella={huella_ant}"
        f"&FechaHoraHusoGenRegistro={ts_huso}"
    )
    huella = hashlib.sha256(raw.encode("utf-8")).hexdigest().upper()
    return huella, raw, ts_huso


def calcular_huella_anulacio_hac1177(
    *,
    nif_emissor: str,
    num_serie_anulada: str,
    fecha_expedicion_anulada: date | datetime | str,
    hash_anterior: Optional[str],
    fecha_hora_huso: Optional[str] = None,
) -> tuple[str, str, str]:
    """
    Calcula l'empremta SHA-256 d'un registre d'anul·lació segons l'Art. 13.2 de l'Ordre HAC/1177/2024.

    Cadena exacta:
    IDEmisorFacturaAnulada=<NIF>&NumSerieFacturaAnulada=<NUMSERIE>&FechaExpedicionFacturaAnulada=<DD-MM-YYYY>&Huella=<ANTERIOR_O_BUIT>&FechaHoraHusoGenRegistro=<ISO8601>
    """
    nif_clean = (nif_emissor or "").strip().upper()
    num_serie_clean = (num_serie_anulada or "").strip()
    fecha_dd_mm_yyyy = format_fecha_aeat(fecha_expedicion_anulada)
    huella_ant = normalitzar_huella_anterior(hash_anterior)
    ts_huso = (fecha_hora_huso or "").strip() or generar_timestamp_huso_aeat()

    raw = (
        f"IDEmisorFacturaAnulada={nif_clean}"
        f"&NumSerieFacturaAnulada={num_serie_clean}"
        f"&FechaExpedicionFacturaAnulada={fecha_dd_mm_yyyy}"
        f"&Huella={huella_ant}"
        f"&FechaHoraHusoGenRegistro={ts_huso}"
    )
    huella = hashlib.sha256(raw.encode("utf-8")).hexdigest().upper()
    return huella, raw, ts_huso


def generar_url_qr_aeat_hac1177(
    *,
    nif_emissor: str,
    num_serie_factura: str,
    fecha_expedicion: date | datetime | str,
    importe_total: float | Decimal,
    entorn: Optional[str] = None,
    modalitat: Optional[str] = None,
) -> str:
    """
    Genera la URL oficial de coteig del QR tributari segons Art. 20-21 Ordre HAC/1177/2024.
    Format: https://.../wlpl/TIKE-CONT/ValidarQR?nif=X&numserie=Y&fecha=DD-MM-YYYY&importe=0.00
    """
    env_key = ((entorn or settings.VERIFACTU_ENV or "PREPRODUCCIO").strip().upper())
    if env_key not in ("PREPRODUCCIO", "PRODUCCIO"):
        env_key = "PREPRODUCCIO"
    mod_key = ((modalitat or settings.VERIFACTU_MODALITAT or "VERIFACTU").strip().upper())
    if mod_key not in ("VERIFACTU", "NO_VERIFACTU"):
        mod_key = "VERIFACTU"

    base_url = QR_AEAT_URLS[(env_key, mod_key)]
    nif_enc = urllib.parse.quote((nif_emissor or "").strip().upper(), safe="")
    numserie_enc = urllib.parse.quote((num_serie_factura or "").strip(), safe="")
    fecha_str = format_fecha_aeat(fecha_expedicion)
    importe_str = _fmt_eur(importe_total)
    return f"{base_url}?nif={nif_enc}&numserie={numserie_enc}&fecha={fecha_str}&importe={importe_str}"


def generar_qr_svg_verifactu(qr_url: str) -> str:
    """
    Genera un codi QR vectorial SVG conforme a ISO/IEC 18004 amb nivell de correcció M
    i zona de silenci (border=4) per a una impressió exacta de 35x35 mm.
    """
    qr_obj = segno.make(qr_url, error="m", micro=False)
    buf = io.BytesIO()
    qr_obj.save(
        buf,
        kind="svg",
        xmldecl=False,
        svgns=False,
        omitsize=True,
        border=4,
        dark="#000000",
        light="#ffffff",
    )
    return buf.getvalue().decode("utf-8")


# ---------------------------------------------------------------------------
# Servei Central Transaccional d'Encadenament i Numeració (SELECT FOR UPDATE)
# ---------------------------------------------------------------------------
class VerifactuCoreService:
    """Servei únic de numeració correlativa, encadenament SHA-256 i QR per a Tenants i Superadmin."""

    @staticmethod
    async def obtenir_o_bloquejar_cadena_tenant(
        db: AsyncSession,
        empresa_id: uuid.UUID,
    ) -> VerifactuCadenaTenant:
        stmt = (
            select(VerifactuCadenaTenant)
            .where(VerifactuCadenaTenant.empresa_id == empresa_id)
            .with_for_update()
        )
        cadena = (await db.execute(stmt)).scalar_one_or_none()
        if not cadena:
            cadena = VerifactuCadenaTenant(
                empresa_id=empresa_id,
                ultim_hash_sha256=None,
                ultim_num_serie=None,
                ultima_data_expedicio=None,
                ultim_tipus_registre=None,
            )
            db.add(cadena)
            await db.flush()
        return cadena

    @staticmethod
    async def obtenir_o_bloquejar_serie(
        db: AsyncSession,
        empresa_id: uuid.UUID,
        codi_serie: str,
        exercici: int,
    ) -> SerieFiscalVerifactu:
        stmt = (
            select(SerieFiscalVerifactu)
            .where(
                SerieFiscalVerifactu.empresa_id == empresa_id,
                SerieFiscalVerifactu.codi_serie == codi_serie,
                SerieFiscalVerifactu.exercici == exercici,
            )
            .with_for_update()
        )
        serie_row = (await db.execute(stmt)).scalar_one_or_none()
        if not serie_row:
            serie_row = SerieFiscalVerifactu(
                empresa_id=empresa_id,
                codi_serie=codi_serie,
                exercici=exercici,
                ultim_numero=0,
                ultim_hash_sha256="0" * 64,
            )
            db.add(serie_row)
            await db.flush()
        return serie_row

    @classmethod
    async def adquirir_seguent_registre_alta(
        cls,
        *,
        db: AsyncSession,
        empresa_id: uuid.UUID,
        empresa_nif: str,
        serie: str,
        exercici: int,
        data_emissio: date | datetime | str,
        tipus_factura: str = "F1",
        cuota_total: float | Decimal,
        importe_total_verifactu: float | Decimal,
        numero_forcat: Optional[int] = None,
        entorn: Optional[str] = None,
        fecha_hora_huso: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Adquireix bloqueig pessimista (SELECT FOR UPDATE) sobre la cadena de l'empresa i la sèrie fiscal,
        assigna el número correlatiu, calcula la Huella SHA-256 HAC/1177/2024 i la URL QR oficial.
        """
        serie_clean = (serie or "F").strip().upper()
        cadena = await cls.obtenir_o_bloquejar_cadena_tenant(db, empresa_id)
        serie_row = await cls.obtenir_o_bloquejar_serie(db, empresa_id, serie_clean, int(exercici))

        if numero_forcat is not None and int(numero_forcat) > 0:
            num_factura = int(numero_forcat)
            if num_factura > serie_row.ultim_numero:
                serie_row.ultim_numero = num_factura
        else:
            serie_row.ultim_numero += 1
            num_factura = serie_row.ultim_numero

        num_serie = format_num_serie(serie_clean, int(exercici), num_factura)
        hash_ant_raw = cadena.ultim_hash_sha256
        if not hash_ant_raw and serie_row.ultim_hash_sha256 and serie_row.ultim_hash_sha256 != "0" * 64:
            hash_ant_raw = serie_row.ultim_hash_sha256
        hash_anterior = normalitzar_huella_anterior(hash_ant_raw) or None

        huella, cadena_raw, ts_huso = calcular_huella_alta_hac1177(
            nif_emissor=empresa_nif,
            num_serie_factura=num_serie,
            fecha_expedicion=data_emissio,
            tipus_factura=tipus_factura,
            cuota_total=cuota_total,
            importe_total=importe_total_verifactu,
            hash_anterior=hash_anterior,
            fecha_hora_huso=fecha_hora_huso,
        )

        qr_url = generar_url_qr_aeat_hac1177(
            nif_emissor=empresa_nif,
            num_serie_factura=num_serie,
            fecha_expedicion=data_emissio,
            importe_total=importe_total_verifactu,
            entorn=entorn,
        )

        serie_row.ultim_hash_sha256 = huella
        cadena.ultim_hash_sha256 = huella
        cadena.ultim_num_serie = num_serie
        cadena.ultima_data_expedicio = format_fecha_aeat(data_emissio)
        cadena.ultim_tipus_registre = "ALTA"
        cadena.updated_at = datetime.now(MADRID_TZ)
        await db.flush()

        return {
            "serie": serie_clean,
            "exercici": int(exercici),
            "numero_factura": num_factura,
            "num_serie_verifactu": num_serie,
            "hash_anterior": hash_anterior,
            "hash_sha256": huella,
            "fecha_hora_huso_gen_registro": ts_huso,
            "qr_verifactu_payload": qr_url,
            "cadena_raw": cadena_raw,
        }

    @classmethod
    async def registrar_anulacio_cadena(
        cls,
        *,
        db: AsyncSession,
        empresa_id: uuid.UUID,
        empresa_nif: str,
        num_serie_anulada: str,
        data_emissio_anulada: date | datetime | str,
        fecha_hora_huso: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Registra un RegistroAnulacion encadenat a la mateixa cadena SHA-256 de l'empresa (Art. 13.2 HAC/1177/2024).
        """
        cadena = await cls.obtenir_o_bloquejar_cadena_tenant(db, empresa_id)
        hash_anterior = normalitzar_huella_anterior(cadena.ultim_hash_sha256) or None

        huella_anul, cadena_raw, ts_huso = calcular_huella_anulacio_hac1177(
            nif_emissor=empresa_nif,
            num_serie_anulada=num_serie_anulada,
            fecha_expedicion_anulada=data_emissio_anulada,
            hash_anterior=hash_anterior,
            fecha_hora_huso=fecha_hora_huso,
        )

        cadena.ultim_hash_sha256 = huella_anul
        cadena.ultim_num_serie = num_serie_anulada
        cadena.ultima_data_expedicio = format_fecha_aeat(data_emissio_anulada)
        cadena.ultim_tipus_registre = "ANULACION"
        cadena.updated_at = datetime.now(MADRID_TZ)
        await db.flush()

        return {
            "hash_anterior": hash_anterior,
            "hash_anulacio_sha256": huella_anul,
            "fecha_hora_huso_gen_registro": ts_huso,
            "cadena_raw": cadena_raw,
        }


# ---------------------------------------------------------------------------
# Renderització Segura HTML -> PDF amb Jinja2 + WeasyPrint (Opció A)
# ---------------------------------------------------------------------------


class _SovereignSafeURLFetcher(_WeasyURLFetcher):
    """
    Bloqueja qualsevol accés de xarxa (http/https/ftp) o sistema de fitxers (file://) des de WeasyPrint
    per prevenir SSRF i Local File Inclusion. Només permet data: URIs generades pel servidor.
    """

    def __init__(self) -> None:
        super().__init__(allowed_protocols={"data"}, allow_redirects=False, fail_on_errors=False)

    def fetch(self, url: str, headers: Any = None) -> Any:
        if not str(url).startswith("data:"):
            raise ValueError(f"SSRF_PROTECTION: Accés a recurs extern bloquejat a WeasyPrint: {url}")
        return super().fetch(url, headers=headers)


_blocked_url_fetcher = _SovereignSafeURLFetcher()


_jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=jinja2.select_autoescape(["html", "xml"]),
)


def _construir_cp_poblacio_provincia(
    cp: Optional[str], poblacio: Optional[str], provincia: Optional[str]
) -> str:
    part_esq = " ".join(p.strip() for p in [cp or "", poblacio or ""] if p and p.strip())
    prov = (provincia or "").strip()
    if part_esq and prov:
        return f"{part_esq} ({prov})"
    return part_esq or (f"({prov})" if prov else "")


def renderitzar_html_factura_verifactu(
    *,
    empresa_nom: str,
    empresa_nif: str,
    primari_hsl: Optional[str] = "166 22% 24%",
    empresa_rao_social: Optional[str] = None,
    empresa_eslogan: Optional[str] = None,
    empresa_adreca: Optional[str] = None,
    empresa_cp: Optional[str] = None,
    empresa_poblacio: Optional[str] = None,
    empresa_provincia: Optional[str] = None,
    empresa_telefon: Optional[str] = None,
    empresa_email: Optional[str] = None,
    empresa_registre_mercantil: Optional[str] = None,
    empresa_titular_compte: Optional[str] = None,
    empresa_iban: Optional[str] = None,
    logotip_bytes: Optional[bytes] = None,
    logotip_mime: str = "image/png",
    client_nom: str,
    client_nif: str,
    client_adreca: Optional[str] = None,
    client_cp: Optional[str] = None,
    client_poblacio: Optional[str] = None,
    client_provincia: Optional[str] = None,
    client_email: Optional[str] = None,
    serie: str,
    numero_factura: int,
    exercici: Optional[int] = None,
    num_serie_verifactu: Optional[str] = None,
    tipus_factura: str = "F1",
    tipus_rectificacio: Optional[str] = None,
    num_serie_rectificada: Optional[str] = None,
    data_factura_rectificada: Optional[str] = None,
    motiu_rectificacio: Optional[str] = None,
    data_emissio: str | date | datetime,
    data_operacio: Optional[str | date | datetime] = None,
    data_venciment: Optional[str | date | datetime] = None,
    metode_pagament: str = "TRANSFERENCIA",
    referencia_comanda: Optional[str] = None,
    estat_document: str = "EMESA",
    estat_anulacio: str = "ACTIVA",
    linies: Optional[Sequence[Any]] = None,
    base_imposable: float | Decimal = 0.0,
    quota_iva: float | Decimal = 0.0,
    quota_recarrec_equivalencia: float | Decimal = 0.0,
    import_total_verifactu: Optional[float | Decimal] = None,
    import_suplits: float | Decimal = 0.0,
    import_retencio: float | Decimal = 0.0,
    import_retencio_garantia: float | Decimal = 0.0,
    import_total: float | Decimal = 0.0,
    es_isp: bool = False,
    mencio_legal: Optional[str] = None,
    notes_factura: Optional[str] = None,
    hash_actual: str = "",
    hash_anterior: Optional[str] = None,
    qr_content: Optional[str] = None,
    csv_aeat: Optional[str] = None,
    modalitat_verifactu: str = "VERIFACTU",
) -> str:
    """Compila l'HTML de la factura Veri*factu amb Jinja2 (autoescape=True) i QR SVG nivell M."""
    accent_css, tint_css, _ = parse_hsl_to_css_and_hex(primari_hsl)
    es_esborrany = estat_document == "ESBORRANY_PREFACTURA"
    es_anulada = estat_anulacio == "ANULADA_VERIFACTU"

    data_exp_fmt = format_fecha_aeat(data_emissio)
    ex_int = int(exercici) if exercici else int(data_exp_fmt.split("-")[2])
    num_serie = num_serie_verifactu or format_num_serie(serie, ex_int, numero_factura)

    if es_esborrany:
        titol_document = "Pre-factura (Esborrany)"
    elif tipus_factura.upper().startswith("R") or serie.upper().startswith("R"):
        titol_document = "Factura rectificativa"
    else:
        titol_document = "Factura"

    qr_svg = ""
    if not es_esborrany and not es_anulada:
        base_imp_dec = _q2(base_imposable)
        iva_dec = _q2(quota_iva)
        rec_dec = _q2(quota_recarrec_equivalencia)
        imp_vf_dec = (
            _q2(import_total_verifactu)
            if import_total_verifactu is not None
            else _q2(base_imp_dec + iva_dec + rec_dec)
        )
        qr_url = qr_content or generar_url_qr_aeat_hac1177(
            nif_emissor=empresa_nif,
            num_serie_factura=num_serie,
            fecha_expedicion=data_exp_fmt,
            importe_total=imp_vf_dec,
        )
        qr_svg = generar_qr_svg_verifactu(qr_url)

    logotip_data_uri = None
    if logotip_bytes:
        b64_logo = base64.b64encode(logotip_bytes).decode("ascii")
        logotip_data_uri = f"data:{logotip_mime};base64,{b64_logo}"

    # Processar línies i desglossament per tipus d'IVA
    linies_ctx: List[Dict[str, Any]] = []
    te_descomptes_linia = False
    te_recarrec_equivalencia = _q2(quota_recarrec_equivalencia) > Decimal("0.00")
    buckets_iva: Dict[Decimal, Dict[str, Decimal]] = {}

    for raw_lin in linies or []:
        get_v = (lambda k: raw_lin.get(k)) if isinstance(raw_lin, dict) else (lambda k: getattr(raw_lin, k, None))
        concepte = str(get_v("concepte") or "Concepte")
        detall = str(get_v("descripcio_detall") or get_v("detall") or "").strip() or None
        qt = Decimal(str(get_v("quantitat") or 1))
        preu = _q2(get_v("preu_venda_unitari") or get_v("preu_unitari") or 0)
        dto = _q2(get_v("descompte_aplicat_pct") or get_v("descompte") or 0)
        if dto > Decimal("0.00"):
            te_descomptes_linia = True
        compte_pgc = str(get_v("compte_pgc") or "700000")
        iva_pct = Decimal("0.00") if (es_isp or compte_pgc.startswith("554")) else _q2(get_v("tipus_iva") or get_v("tipus_iva_pct") or 0)
        rec_pct = _q2(get_v("tipus_recarrec_equivalencia") or 0)
        sub_val = get_v("subtotal")
        if sub_val is not None:
            sub = _q2(sub_val)
        else:
            factor = Decimal("1.00") - (dto / Decimal("100.00"))
            sub = _q2(qt * preu * factor)

        rec_quota = _q2(get_v("quota_recarrec_linia") or (sub * rec_pct / Decimal("100.00")))
        if rec_quota > Decimal("0.00"):
            te_recarrec_equivalencia = True

        linies_ctx.append(
            {
                "concepte": concepte,
                "detall": detall,
                "quantitat_fmt": _fmt_qty(qt),
                "preu_unitari_fmt": _fmt_eur(preu),
                "descompte_fmt": _fmt_qty(dto),
                "iva_fmt": _fmt_qty(iva_pct),
                "import_fmt": _fmt_eur(sub),
            }
        )

        if not compte_pgc.startswith("554"):
            b = buckets_iva.setdefault(
                iva_pct,
                {"base": Decimal("0.00"), "quota": Decimal("0.00"), "recarrec": Decimal("0.00")},
            )
            b["base"] += sub
            b["recarrec"] += rec_quota

    if not linies_ctx:
        base_dec = _q2(base_imposable)
        iva_dec = _q2(quota_iva)
        iva_pct_calc = _q2((iva_dec / base_dec) * Decimal("100")) if base_dec > 0 and not es_isp else Decimal("0.00")
        linies_ctx.append(
            {
                "concepte": f"Serveis facturats ({num_serie})",
                "detall": None,
                "quantitat_fmt": "1",
                "preu_unitari_fmt": _fmt_eur(base_dec),
                "descompte_fmt": "0",
                "iva_fmt": _fmt_qty(iva_pct_calc),
                "import_fmt": _fmt_eur(base_dec),
            }
        )
        buckets_iva[iva_pct_calc] = {
            "base": base_dec,
            "quota": iva_dec,
            "recarrec": _q2(quota_recarrec_equivalencia),
        }

    desglossament_iva = []
    for tipus_k in sorted(buckets_iva.keys()):
        b_item = buckets_iva[tipus_k]
        quota_b = Decimal("0.00") if es_isp else _q2(b_item["base"] * (tipus_k / Decimal("100.00")))
        desglossament_iva.append(
            {
                "tipus_iva_fmt": _fmt_qty(tipus_k),
                "base_fmt": _fmt_eur(b_item["base"]),
                "quota_fmt": _fmt_eur(quota_b),
                "recarrec_fmt": _fmt_eur(b_item["recarrec"]),
            }
        )

    base_total_dec = _q2(base_imposable)
    iva_total_dec = _q2(quota_iva)
    rec_total_dec = _q2(quota_recarrec_equivalencia)
    total_fiscal_dec = (
        _q2(import_total_verifactu)
        if import_total_verifactu is not None
        else _q2(base_total_dec + iva_total_dec + rec_total_dec)
    )
    suplerts_dec = _q2(import_suplits)
    ret_irpf_dec = _q2(import_retencio)
    ret_gar_dec = _q2(import_retencio_garantia)
    liquid_dec = _q2(import_total) if import_total is not None else _q2(
        total_fiscal_dec + suplerts_dec - ret_irpf_dec - ret_gar_dec
    )

    irpf_pct_fmt = ""
    if ret_irpf_dec > Decimal("0.00") and base_total_dec > Decimal("0.00"):
        irpf_pct_fmt = _fmt_qty(_q2((ret_irpf_dec / base_total_dec) * Decimal("100")))

    mostrar_liquid_diferent = (
        suplerts_dec > Decimal("0.00")
        or ret_irpf_dec > Decimal("0.00")
        or ret_gar_dec > Decimal("0.00")
        or liquid_dec != total_fiscal_dec
    )

    mencio_isp = (
        "Operació amb inversió del subjecte passiu d'acord amb l'art. 84.U.2n.f de la Llei 37/1992 de l'IVA."
        if es_isp
        else None
    )
    mencio_final = mencio_legal or mencio_isp

    rect_ctx = None
    if tipus_factura.upper().startswith("R") or serie.upper().startswith("R") or motiu_rectificacio or num_serie_rectificada:
        mod_codi = (tipus_rectificacio or "S").strip().upper()
        rect_ctx = {
            "codi_tipus": tipus_factura.upper() if tipus_factura.upper().startswith("R") else "R1",
            "num_serie_rectificada": num_serie_rectificada or "original",
            "data_rectificada": format_fecha_aeat(data_factura_rectificada) if data_factura_rectificada else None,
            "modalitat_label": "Per diferències (I)" if mod_codi == "I" else "Per substitució (S)",
            "motiu": motiu_rectificacio or "Rectificació fiscal Veri*factu",
        }

    contacte_parts = [p.strip() for p in [empresa_telefon or "", empresa_email or ""] if p and p.strip()]
    emissor_cp_pob = _construir_cp_poblacio_provincia(empresa_cp, empresa_poblacio, empresa_provincia)
    client_cp_pob = _construir_cp_poblacio_provincia(client_cp, client_poblacio, client_provincia)

    rao_emissor = (empresa_rao_social or empresa_nom or "Empresa Emissora").strip()
    peu_parts = [rao_emissor, f"NIF/CIF {empresa_nif}"]
    if empresa_adreca:
        peu_parts.append(empresa_adreca.strip())
    if emissor_cp_pob:
        peu_parts.append(emissor_cp_pob)
    if empresa_registre_mercantil:
        peu_parts.append(empresa_registre_mercantil.strip())

    tipus_key = (tipus_factura or "F1").strip().upper()
    template = _jinja_env.get_template("factura_verifactu.html")
    return template.render(
        accent_hsl_css=accent_css,
        tint_hsl_css=tint_css,
        titol_document=titol_document,
        num_serie_verifactu=num_serie,
        es_esborrany=es_esborrany,
        es_anulada=es_anulada,
        qr_svg=qr_svg,
        mostrar_llegenda_verifactu=(modalitat_verifactu.upper() == "VERIFACTU"),
        logotip_data_uri=logotip_data_uri,
        emissor={
            "nom_comercial": empresa_nom,
            "rao_social": rao_emissor,
            "eslogan": empresa_eslogan,
            "nif": empresa_nif,
            "adreca": empresa_adreca,
            "cp_poblacio_provincia": emissor_cp_pob,
            "contacte_linia": " · ".join(contacte_parts) if contacte_parts else None,
        },
        client={
            "rao_social": client_nom,
            "nif": client_nif,
            "adreca": client_adreca,
            "cp_poblacio_provincia": client_cp_pob,
            "email": client_email,
        },
        meta={
            "data_expedicio": data_exp_fmt,
            "data_operacio": format_fecha_aeat(data_operacio) if data_operacio else data_exp_fmt,
            "data_venciment": format_fecha_aeat(data_venciment) if data_venciment else data_exp_fmt,
            "tipus_factura_label": TIPUS_FACTURA_LABELS.get(tipus_key, tipus_key),
            "referencia": (referencia_comanda or "—").strip(),
            "forma_pagament": (metode_pagament or "TRANSFERÈNCIA").strip(),
        },
        rectificativa=rect_ctx,
        te_descomptes_linia=te_descomptes_linia,
        te_recarrec_equivalencia=te_recarrec_equivalencia,
        linies=linies_ctx,
        desglossament_iva=desglossament_iva,
        totals={
            "base_imposable_fmt": _fmt_eur(base_total_dec),
            "te_descompte_global": False,
            "descompte_pct_fmt": "0",
            "descompte_import_fmt": "0.00",
            "quota_iva_fmt": _fmt_eur(iva_total_dec),
            "te_recarrec": te_recarrec_equivalencia,
            "quota_recarrec_fmt": _fmt_eur(rec_total_dec),
            "import_total_verifactu_fmt": _fmt_eur(total_fiscal_dec),
            "te_suplerts": suplerts_dec > Decimal("0.00"),
            "import_suplerts_fmt": _fmt_eur(suplerts_dec),
            "te_retencio_irpf": ret_irpf_dec > Decimal("0.00"),
            "irpf_pct_fmt": irpf_pct_fmt,
            "import_retencio_fmt": _fmt_eur(ret_irpf_dec),
            "te_retencio_garantia": ret_gar_dec > Decimal("0.00"),
            "import_retencio_garantia_fmt": _fmt_eur(ret_gar_dec),
            "mostrar_liquid_diferent": mostrar_liquid_diferent,
            "liquid_exigible_fmt": _fmt_eur(liquid_dec),
        },
        pagament={
            "titular": empresa_titular_compte or rao_emissor,
            "iban": desxifrar_secret_verifactu(empresa_iban) if empresa_iban else None,
        },
        notes={
            "mencio_legal": mencio_final,
            "notes_factura": notes_factura,
        },
        peu_mercantil=" · ".join(peu_parts),
        hash_actual=hash_actual,
        hash_anterior=hash_anterior,
        csv_aeat=csv_aeat,
    )


def renderitzar_pdf_factura_verifactu_bytes(**kwargs: Any) -> bytes:
    """Renderitza l'HTML de la factura a PDF binari amb WeasyPrint i url_fetcher bloquejat."""
    html_str = renderitzar_html_factura_verifactu(**kwargs)
    pdf_bytes = weasyprint.HTML(
        string=html_str,
        base_url=str(TEMPLATE_DIR),
        url_fetcher=_blocked_url_fetcher,
    ).write_pdf()
    return bytes(pdf_bytes or b"")


def renderitzar_pdf_factura_verifactu(*, ruta_desti: str, **kwargs: Any) -> str:
    """Renderitza el PDF de factura Veri*factu amb WeasyPrint i el desa a ruta_desti."""
    pdf_bytes = renderitzar_pdf_factura_verifactu_bytes(**kwargs)
    with open(ruta_desti, "wb") as f_out:
        f_out.write(pdf_bytes)
    return ruta_desti


# ---------------------------------------------------------------------------
# Funcions de Compatibilitat i Wrappers (API pública de verifactu.py)
# ---------------------------------------------------------------------------
def generar_sha256_encadenat(
    empresa_nif: str,
    client_nif: str,
    serie: str,
    numero_factura: int,
    base_imposable: float,
    quota_iva: float,
    import_total: float,
    data_emissio: str,
    hash_anterior: Optional[str],
    tipus_factura: str = "F1",
    exercici: Optional[int] = None,
    num_serie_verifactu: Optional[str] = None,
    fecha_hora_huso: Optional[str] = None,
) -> str:
    """Calcula la Huella SHA-256 encadenada segons l'Art. 13.1 de l'Ordre HAC/1177/2024."""
    fecha_fmt = format_fecha_aeat(data_emissio)
    ex = int(exercici) if exercici else int(fecha_fmt.split("-")[2])
    num_serie = num_serie_verifactu or format_num_serie(serie, ex, numero_factura)
    importe_vf = _q2(Decimal(str(base_imposable or 0)) + Decimal(str(quota_iva or 0)))
    if importe_vf == Decimal("0.00") and float(import_total or 0) > 0:
        importe_vf = _q2(import_total)
    huella, _, _ = calcular_huella_alta_hac1177(
        nif_emissor=empresa_nif,
        num_serie_factura=num_serie,
        fecha_expedicion=fecha_fmt,
        tipus_factura=tipus_factura,
        cuota_total=quota_iva,
        importe_total=importe_vf,
        hash_anterior=hash_anterior,
        fecha_hora_huso=fecha_hora_huso,
    )
    return huella


def generar_qr_verifactu(
    nif_emissor: str,
    nif_destinatari: str,
    serie: str,
    numero: int,
    hash_sha256: str,
    import_total: float,
    data_emissio: str,
    exercici: Optional[int] = None,
    num_serie_verifactu: Optional[str] = None,
    entorn: Optional[str] = None,
) -> str:
    """Genera la URL del QR tributari oficial AEAT segons l'Art. 20-21 de l'Ordre HAC/1177/2024."""
    fecha_fmt = format_fecha_aeat(data_emissio)
    ex = int(exercici) if exercici else int(fecha_fmt.split("-")[2])
    num_serie = num_serie_verifactu or format_num_serie(serie, ex, numero)
    return generar_url_qr_aeat_hac1177(
        nif_emissor=nif_emissor,
        num_serie_factura=num_serie,
        fecha_expedicion=fecha_fmt,
        importe_total=import_total,
        entorn=entorn,
    )


async def generar_factura_pdf(
    db: AsyncSession,
    empresa_id: uuid.UUID,
    empresa_nom: str,
    empresa_nif: str,
    logotip_path: Optional[str],
    primari_hsl: str,
    secundari_hsl: str,
    client_nom: str,
    client_nif: str,
    serie: str,
    numero_factura: int,
    base_imposable: float,
    quota_iva: float,
    import_total: float,
    data_emissio: str,
    ruta_desti: str,
    tipus_factura: str = "F1",
) -> dict:
    """
    Adquireix el següent registre d'alta encadenat amb VerifactuCoreService i renderitza el PDF amb WeasyPrint.
    """
    fecha_fmt = format_fecha_aeat(data_emissio)
    exercici = int(fecha_fmt.split("-")[2])
    importe_vf = _q2(Decimal(str(base_imposable or 0)) + Decimal(str(quota_iva or 0)))

    reg = await VerifactuCoreService.adquirir_seguent_registre_alta(
        db=db,
        empresa_id=empresa_id,
        empresa_nif=empresa_nif,
        serie=serie,
        exercici=exercici,
        data_emissio=data_emissio,
        tipus_factura=tipus_factura,
        cuota_total=quota_iva,
        importe_total_verifactu=importe_vf,
        numero_forcat=numero_factura,
    )

    renderitzar_pdf_factura_verifactu(
        empresa_nom=empresa_nom,
        empresa_nif=empresa_nif,
        primari_hsl=primari_hsl,
        client_nom=client_nom,
        client_nif=client_nif,
        serie=serie,
        numero_factura=reg["numero_factura"],
        exercici=exercici,
        num_serie_verifactu=reg["num_serie_verifactu"],
        tipus_factura=tipus_factura,
        data_emissio=data_emissio,
        base_imposable=base_imposable,
        quota_iva=quota_iva,
        import_total_verifactu=float(importe_vf),
        import_total=import_total,
        hash_actual=reg["hash_sha256"],
        hash_anterior=reg["hash_anterior"],
        qr_content=reg["qr_verifactu_payload"],
        ruta_desti=ruta_desti,
    )

    return {
        "exercici": exercici,
        "numero_factura": reg["numero_factura"],
        "num_serie_verifactu": reg["num_serie_verifactu"],
        "hash_sha256": reg["hash_sha256"],
        "hash_anterior": reg["hash_anterior"],
        "fecha_hora_huso_gen_registro": reg["fecha_hora_huso_gen_registro"],
        "qr_content": reg["qr_verifactu_payload"],
        "pdf_path": ruta_desti,
        "estat_generacio": "GENERAT",
    }


calcular_hash_verifactu = generar_sha256_encadenat
generar_qr_verifactu_aeat = generar_qr_verifactu
generar_contingut_qr_aeat = generar_qr_verifactu
generar_pdf_factura = generar_factura_pdf
