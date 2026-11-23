"""Servei de gestió completa de Pressupostos: línies, PDF ReportLab, token HMAC d'acceptació i enviament Email/Telegram."""

import base64
import hashlib
import hmac
import logging
import os
import smtplib
import time
import urllib.parse
import uuid
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from email.message import EmailMessage
from typing import Any, Dict, List, Optional, Sequence, Tuple

from app.core.config import settings
from app.models.models import Client, Empresa, Pressupost
from app.services.sovereign_storage import SovereignStorageGateway

logger = logging.getLogger("sevalor.pressupost_service")

DEFAULT_VALIDESA_DIES = 30
TOKEN_TTL_SEGONS = 90 * 24 * 3600  # 90 dies


def _q2(val: Decimal | float | int) -> Decimal:
    return Decimal(str(val)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calcular_totals_linies_pressupost(
    linies: Sequence[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], float, float, float]:
    """Calcula subtotals per línia, base imposable, quota IVA i total amb ROUND_HALF_UP."""
    linies_norm: List[Dict[str, Any]] = []
    bases_per_iva: Dict[Decimal, Decimal] = {}

    for raw in linies:
        concepte = str(raw.get("concepte") or "").strip()[:200]
        if not concepte:
            continue
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
        bases_per_iva[iva] = bases_per_iva.get(iva, Decimal("0.00")) + subtotal

        linies_norm.append(
            {
                "article_id": str(raw["article_id"]) if raw.get("article_id") else None,
                "concepte": concepte,
                "quantitat": float(qt),
                "preu_unitari": float(preu),
                "descompte_pct": float(dto),
                "tipus_iva": float(iva),
                "subtotal": float(subtotal),
            }
        )

    base_total = _q2(sum(bases_per_iva.values(), Decimal("0.00")))
    iva_total = _q2(
        sum(
            (_q2(b * (tipus / Decimal("100.00"))) for tipus, b in bases_per_iva.items()),
            Decimal("0.00"),
        )
    )
    total = _q2(base_total + iva_total)
    return linies_norm, float(base_total), float(iva_total), float(total)


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
    """Desa la fitxa completa del pressupost (línies, notes, canals d'enviament) al disc sobirà."""
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


def generar_pdf_pressupost_bytes(
    *,
    empresa: Optional[Empresa],
    client: Optional[Client],
    pressupost: Pressupost,
    detalls: Dict[str, Any],
    acceptacio_url: Optional[str] = None,
) -> bytes:
    """Genera el PDF corporatiu del pressupost amb ReportLab (estil camaleònic + línies + QR)."""
    from reportlab.graphics import renderPDF
    from reportlab.graphics.barcode import qr
    from reportlab.graphics.shapes import Drawing
    from reportlab.lib.colors import HexColor
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    temp_dir = "/tmp/sevalor_pressupostos_temp"
    os.makedirs(temp_dir, exist_ok=True)
    ruta_tmp = os.path.join(temp_dir, f"{uuid.uuid4()}_{pressupost.numero}.pdf")

    try:
        c = canvas.Canvas(ruta_tmp, pagesize=A4)
        primari_hsl = empresa.primari_hsl if empresa else "150 40 20"
        from app.services.verifactu import parse_hsl_to_css_and_hex

        _, _, primary_hex = parse_hsl_to_css_and_hex(primari_hsl)
        primary_color = HexColor(primary_hex)

        # Capçalera empresa
        c.setFont("Helvetica-Bold", 15)
        c.setFillColor(primary_color)
        c.drawString(35, A4[1] - 48, empresa.nom if empresa else "Sevalor Suite")
        c.setFont("Helvetica", 9.5)
        c.setFillColor(HexColor("#444444"))
        c.drawString(35, A4[1] - 64, f"NIF: {empresa.nif if empresa else '—'}")
        if empresa and empresa.adreca:
            c.drawString(35, A4[1] - 78, str(empresa.adreca)[:85])
        c.line(35, A4[1] - 88, A4[0] - 35, A4[1] - 88)

        # Títol pressupost
        c.setFont("Helvetica-Bold", 13)
        c.setFillColor(primary_color)
        c.drawString(35, A4[1] - 112, f"PRESSUPOST {pressupost.numero}")

        c.setFont("Helvetica", 9.5)
        c.setFillColor(HexColor("#333333"))
        data_em = (
            pressupost.created_at.strftime("%Y-%m-%d")
            if pressupost.created_at
            else datetime.now(timezone.utc).strftime("%Y-%m-%d")
        )
        validesa = int(detalls.get("validesa_dies") or DEFAULT_VALIDESA_DIES)
        c.drawString(35, A4[1] - 130, f"Data: {data_em}   ·   Validesa: {validesa} dies   ·   Estat: {pressupost.estat}")

        # Client
        c.setFont("Helvetica-Bold", 10)
        c.drawString(35, A4[1] - 154, "CLIENT:")
        c.setFont("Helvetica", 9.5)
        cli_nom = client.rao_social if client else "Client"
        cli_nif = client.nif if client else "—"
        c.drawString(90, A4[1] - 154, f"{cli_nom} (NIF: {cli_nif})")
        if client and client.adreca_fiscal:
            c.drawString(90, A4[1] - 168, str(client.adreca_fiscal)[:75])

        if acceptacio_url:
            try:
                qr_code = qr.QrCodeWidget(acceptacio_url)
                bounds = qr_code.getBounds()
                qr_w = bounds[2] - bounds[0]
                qr_h = bounds[3] - bounds[1]
                drawing = Drawing(58, 58, transform=[58 / max(qr_w, 1), 0, 0, 58 / max(qr_h, 1), 0, 0])
                drawing.add(qr_code)
                renderPDF.draw(drawing, c, A4[0] - 95, A4[1] - 165)
                c.setFont("Helvetica", 6.5)
                c.setFillColor(HexColor("#666666"))
                c.drawString(A4[0] - 102, A4[1] - 174, "Acceptació online")
                c.setFillColor(HexColor("#333333"))
            except Exception as exc:
                logger.warning("No s'ha pogut dibuixar QR al PDF de pressupost: %s", exc)

        y = A4[1] - 196
        titol = str(detalls.get("titol") or "").strip()
        descripcio = str(detalls.get("descripcio") or "").strip()
        if titol:
            c.setFont("Helvetica-Bold", 10.5)
            c.drawString(35, y, titol[:85])
            y -= 16
        if descripcio:
            c.setFont("Helvetica", 9)
            for line_chunk in [descripcio[i : i + 95] for i in range(0, min(len(descripcio), 285), 95)]:
                c.drawString(35, y, line_chunk)
                y -= 13
            y -= 6

        # Taula de partides
        linies = detalls.get("linies") or []
        if not linies:
            total_val = float(pressupost.total or 0.0)
            linies = [
                {
                    "concepte": titol or f"Pressupost {pressupost.numero}",
                    "quantitat": 1,
                    "preu_unitari": total_val,
                    "descompte_pct": 0,
                    "tipus_iva": 0,
                    "subtotal": total_val,
                }
            ]

        c.setFont("Helvetica-Bold", 8.5)
        c.drawString(35, y, "Concepte / Partida")
        c.drawRightString(335, y, "Qt.")
        c.drawRightString(405, y, "Preu u.")
        c.drawRightString(455, y, "Dto%")
        c.drawRightString(500, y, "IVA%")
        c.drawRightString(560, y, "Subtotal")
        y -= 5
        c.line(35, y, A4[0] - 35, y)
        y -= 15

        c.setFont("Helvetica", 8.5)
        for lin in linies:
            if y < 120:
                c.showPage()
                y = A4[1] - 60
                c.setFont("Helvetica", 8.5)
            concepte = str(lin.get("concepte") or "")[:55]
            qt = float(lin.get("quantitat") or 1)
            preu = float(lin.get("preu_unitari") or 0)
            dto = float(lin.get("descompte_pct") or 0)
            iva = float(lin.get("tipus_iva") if lin.get("tipus_iva") is not None else 21)
            sub = float(lin.get("subtotal") if lin.get("subtotal") is not None else qt * preu * (1 - dto / 100))
            c.drawString(35, y, concepte)
            c.drawRightString(335, y, f"{qt:.2f}")
            c.drawRightString(405, y, f"{preu:.2f}")
            c.drawRightString(455, y, f"{dto:.1f}")
            c.drawRightString(500, y, f"{iva:.0f}")
            c.drawRightString(560, y, f"{sub:.2f} €")
            y -= 15

        total_final = float(pressupost.total) if pressupost.total is not None else 0.0
        raw_base = detalls.get("base_imposable")
        base_imp = float(raw_base) if raw_base is not None else total_final
        quota_iva = float(detalls.get("quota_iva") or 0.0)

        y -= 10
        c.line(340, y, A4[0] - 35, y)
        y -= 16
        c.setFont("Helvetica", 9.5)
        c.drawString(350, y, "Base Imposable:")
        c.drawRightString(560, y, f"{base_imp:.2f} €")
        y -= 14
        c.drawString(350, y, "Quota IVA:")
        c.drawRightString(560, y, f"{quota_iva:.2f} €")
        y -= 18
        c.setFont("Helvetica-Bold", 11.5)
        c.setFillColor(primary_color)
        c.drawString(350, y, "TOTAL PRESSUPOST:")
        c.drawRightString(560, y, f"{total_final:.2f} €")

        if acceptacio_url:
            c.setFont("Helvetica", 8)
            c.setFillColor(HexColor("#555555"))
            c.drawString(35, 45, f"Accepta o revisa aquest pressupost en línia: {acceptacio_url[:95]}")

        c.showPage()
        c.save()

        with open(ruta_tmp, "rb") as f_bin:
            return f_bin.read()
    finally:
        try:
            if os.path.exists(ruta_tmp):
                os.remove(ruta_tmp)
        except OSError:
            pass


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
