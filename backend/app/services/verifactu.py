"""
Motor de Facturació Legal Veri*factu (RD 1007/2023) amb ReportLab.

Implementa:
- Generació de PDF amb QR estructurat segons especificació AEAT.
- Hash SHA-256 encadenat amb bloqueig pessimista (SELECT FOR UPDATE).
- Estil camaleònic per tenant (--color-primary, --color-secondary, logotip).
- Outbox Pattern: la factura es consolida localment i l'enviament SOAP es delega a outbox_aeat.
- Zero Mock Data: si no hi ha factura anterior, hash_anterior = None (Dia 0 real).
"""

import hashlib
import logging
import uuid
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("verifactu")

# ---------------------------------------------------------------------------
# Esquema QR Veri*factu (segons RD 1007/2023 i Ordre HAC/1177/2024)
# El QR ha de codificar: NIF emissor + NIF destinatari + Sèrie + Número +
#   Hash SHA-256 + Import + Data emissió
# ---------------------------------------------------------------------------
QR_BASE_URL = "https://sede.aeat.gob.es/verifactu/"


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
) -> str:
    """
    Calcula el hash SHA-256 encadenat per a Veri*factu (RF-12, RF-13).

    La cadena inclou TOTS els camps immutables de la factura més el hash de
    la factura precedent. Això garanteix la integritat de l'encadenament.
    """
    raw = (
        f"{empresa_nif}|{client_nif}|{serie}|{numero_factura}|"
        f"{base_imposable:.2f}|{quota_iva:.2f}|{import_total:.2f}|"
        f"{data_emissio}|{hash_anterior or ''}"
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def generar_qr_verifactu(
    nif_emissor: str,
    nif_destinatari: str,
    serie: str,
    numero: int,
    hash_sha256: str,
    import_total: float,
    data_emissio: str,
) -> str:
    """
    Genera el contingut del codi QR estructurat segons l'especificació AEAT.
    El QR conté una URL de consulta pública + paràmetres codificats.

    Format: URL_BASE?nif_emissor=X&nif_destinatari=Y&serie=Z&num=N&hash=H&import=I&data=D
    """
    params = (
        f"nif_e={nif_emissor}&nif_d={nif_destinatari}&serie={serie}&"
        f"num={numero}&hash={hash_sha256}&import={import_total:.2f}&data={data_emissio}"
    )
    return f"{QR_BASE_URL}consulta?{params}"


async def obtenir_hash_anterior_amb_lock(
    db: AsyncSession,
    empresa_id: uuid.UUID,
    serie: str,
) -> Optional[str]:
    """
    Recupera el hash SHA-256 de la factura precedent de la mateixa sèrie
    amb bloqueig pessimista (SELECT FOR UPDATE) per evitar condicions de
    carrera en l'encadenament (RF-05 Event-driven, Spec 024).

    En mode testing (TESTING=1), omet FOR UPDATE per evitar conflictes
    amb SAVEPOINT.

    Retorna None si no hi ha factura anterior (Dia 0 real).
    """
    import os

    base_sql = (
        "SELECT hash_sha256 FROM factures_capcalera "
        "WHERE empresa_id = :emp_id AND serie = :serie "
        "ORDER BY created_at DESC LIMIT 1"
    )
    if os.getenv("TESTING") != "1":
        base_sql += " FOR UPDATE"
    stmt = text(base_sql)
    result = await db.execute(stmt, {"emp_id": str(empresa_id), "serie": serie})
    row = result.fetchone()
    if row:
        return str(row[0])
    return None


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
) -> dict:
    """
    Genera el PDF de factura Veri*factu amb ReportLab.

    Pasos (Spec 024 RF-05):
    1. SELECT FOR UPDATE sobre la darrera factura de la sèrie (hash anterior).
    2. Càlcul del nou hash SHA-256 encadenat.
    3. Generació del codi QR.
    4. Creació del PDF amb ReportLab: caixetí, estil camaleònic, QR.
    5. Retorn de metadades per a la inserció a FacturaCapcalera.

    Args:
        db: Sessió asíncrona (ha de tenir RLS actiu via get_db_with_tenant_context).
        empresa_id: UUID de l'empresa.
        [altres paràmetres de facturació]

    Returns:
        dict amb: hash_sha256, hash_anterior, qr_content, pdf_path, estat_generacio
    """
    # Pas 1: Bloqueig pessimista i hash anterior
    hash_anterior = await obtenir_hash_anterior_amb_lock(db, empresa_id, serie)

    # Pas 2: Calcular hash encadenat
    hash_actual = generar_sha256_encadenat(
        empresa_nif=empresa_nif,
        client_nif=client_nif,
        serie=serie,
        numero_factura=numero_factura,
        base_imposable=base_imposable,
        quota_iva=quota_iva,
        import_total=import_total,
        data_emissio=data_emissio,
        hash_anterior=hash_anterior,
    )

    # Pas 3: Generar contingut QR
    qr_content = generar_qr_verifactu(
        nif_emissor=empresa_nif,
        nif_destinatari=client_nif,
        serie=serie,
        numero=numero_factura,
        hash_sha256=hash_actual,
        import_total=import_total,
        data_emissio=data_emissio,
    )

    # Pas 4: Generar PDF amb ReportLab
    from reportlab.graphics.barcode import qr
    from reportlab.lib.colors import HexColor
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    c = canvas.Canvas(ruta_desti, pagesize=A4)

    # Interpretar HSL per a colors
    try:
        h_part, s_part, l_part = primari_hsl.replace("%", "").split()
        primary_color = HexColor(f"hsl({int(h_part)}, {int(s_part)}%, {int(l_part)}%)")
    except (ValueError, AttributeError):
        primary_color = HexColor("#1b4332")

    # Capçalera amb nom empresa
    c.setFont("Helvetica-Bold", 14)
    c.setFillColor(primary_color)
    c.drawString(30, A4[1] - 50, empresa_nom)
    c.setFont("Helvetica", 10)
    c.setFillColor(HexColor("#333333"))
    c.drawString(30, A4[1] - 70, f"NIF: {empresa_nif}")
    c.line(30, A4[1] - 80, A4[0] - 30, A4[1] - 80)

    # Dades del client
    c.setFont("Helvetica-Bold", 11)
    c.drawString(30, A4[1] - 110, "CLIENT:")
    c.setFont("Helvetica", 10)
    c.drawString(30, A4[1] - 130, f"{client_nom} (NIF: {client_nif})")

    # Cos de la factura
    c.setFont("Helvetica-Bold", 12)
    c.drawString(30, A4[1] - 170, f"FACTURA {serie}-{numero_factura:05d}")
    c.setFont("Helvetica", 10)
    c.drawString(30, A4[1] - 190, f"Data: {data_emissio}")
    c.drawString(30, A4[1] - 210, f"Base Imposable: {base_imposable:.2f} €")
    c.drawString(30, A4[1] - 230, f"Quota IVA: {quota_iva:.2f} €")
    c.setFont("Helvetica-Bold", 12)
    c.drawString(30, A4[1] - 260, f"TOTAL: {import_total:.2f} €")

    # QR
    try:
        qr_code = qr.QrCodeWidget(qr_content, barWidth=60, barHeight=60)
        bounds = qr_code.getBounds()
        qr_width = bounds[2] - bounds[0]
        qr_height = bounds[3] - bounds[1]
        qr_scale = 60 / max(qr_width, qr_height)
        c.saveState()
        c.translate(A4[0] - 100, A4[1] - 230)
        c.scale(qr_scale, qr_scale)
        qr_code.drawOn(c, 0, 0)
        c.restoreState()
        c.setFont("Helvetica", 6)
        c.setFillColor(HexColor("#666666"))
        c.drawString(A4[0] - 110, A4[1] - 235, "Veri*factu QR")
    except Exception as e:
        logger.warning(f"No s'ha pogut generar el QR al PDF: {e}")

    # Peu: Hash encadenat
    c.setFont("Helvetica", 7)
    c.setFillColor(HexColor("#999999"))
    c.drawString(30, 50, f"Hash SHA-256: {hash_actual}")
    if hash_anterior:
        c.drawString(30, 35, f"Hash anterior: {hash_anterior}")
    else:
        c.drawString(30, 35, "Hash anterior: (Primera factura de la sèrie)")

    c.showPage()
    c.save()

    logger.info(
        "PDF Veri*factu generat: %s | Sèrie: %s | Núm: %s | Hash: %s",
        ruta_desti,
        serie,
        numero_factura,
        hash_actual,
    )

    return {
        "hash_sha256": hash_actual,
        "hash_anterior": hash_anterior,
        "qr_content": qr_content,
        "pdf_path": ruta_desti,
        "estat_generacio": "GENERAT",
    }


def renderitzar_pdf_factura_verifactu(
    *,
    empresa_nom: str,
    empresa_nif: str,
    primari_hsl: str,
    client_nom: str,
    client_nif: str,
    serie: str,
    numero_factura: int,
    data_emissio: str,
    data_venciment: Optional[str] = None,
    estat_document: str = "EMESA",
    linies: Optional[list] = None,
    base_imposable: float,
    quota_iva: float,
    import_suplits: float = 0.0,
    import_retencio: float = 0.0,
    import_retencio_garantia: float = 0.0,
    import_total: float,
    es_isp: bool = False,
    hash_actual: str = "",
    hash_anterior: Optional[str] = None,
    qr_content: Optional[str] = None,
    ruta_desti: str,
) -> str:
    """Renderitza un PDF legal amb línies detallades i QR Veri*factu (o marca d'esborrany si és pre-factura)."""
    from reportlab.graphics.barcode import qr
    from reportlab.lib.colors import HexColor
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    c = canvas.Canvas(ruta_desti, pagesize=A4)

    try:
        h_part, s_part, l_part = (primari_hsl or "150 40 20").replace("%", "").split()
        primary_color = HexColor(f"hsl({int(float(h_part))}, {int(float(s_part))}%, {int(float(l_part))}%)")
    except (ValueError, AttributeError):
        primary_color = HexColor("#1b4332")

    es_esborrany = estat_document == "ESBORRANY_PREFACTURA"

    # Capçalera empresa
    c.setFont("Helvetica-Bold", 14)
    c.setFillColor(primary_color)
    c.drawString(30, A4[1] - 48, empresa_nom)
    c.setFont("Helvetica", 9.5)
    c.setFillColor(HexColor("#333333"))
    c.drawString(30, A4[1] - 65, f"NIF: {empresa_nif}")
    c.line(30, A4[1] - 75, A4[0] - 30, A4[1] - 75)

    # Títol document
    c.setFont("Helvetica-Bold", 13)
    titol = (
        f"PRE-FACTURA (ESBORRANY) {serie}-{numero_factura:04d}"
        if es_esborrany
        else f"FACTURA {serie}-{numero_factura:04d}"
    )
    c.drawString(30, A4[1] - 100, titol)
    c.setFont("Helvetica", 9.5)
    c.drawString(30, A4[1] - 118, f"Data d'emissió: {data_emissio}")
    if data_venciment:
        c.drawString(220, A4[1] - 118, f"Venciment: {data_venciment}")

    # Client
    c.setFont("Helvetica-Bold", 10)
    c.drawString(30, A4[1] - 142, "CLIENT:")
    c.setFont("Helvetica", 9.5)
    c.drawString(85, A4[1] - 142, f"{client_nom} (NIF: {client_nif})")

    if es_esborrany:
        c.setFont("Helvetica-Bold", 9)
        c.setFillColor(HexColor("#b45309"))
        c.drawString(30, A4[1] - 160, "DOCUMENT NO DEFINITIU — PENDENT DE VALIDACIÓ HUMANA I EMISSIÓ VERI*FACTU")
        c.setFillColor(HexColor("#333333"))
    elif qr_content:
        try:
            qr_code = qr.QrCodeWidget(qr_content, barWidth=60, barHeight=60)
            bounds = qr_code.getBounds()
            qr_width = bounds[2] - bounds[0]
            qr_height = bounds[3] - bounds[1]
            qr_scale = 60 / max(qr_width, qr_height)
            c.saveState()
            c.translate(A4[0] - 95, A4[1] - 155)
            c.scale(qr_scale, qr_scale)
            qr_code.drawOn(c, 0, 0)
            c.restoreState()
            c.setFont("Helvetica", 6)
            c.setFillColor(HexColor("#666666"))
            c.drawString(A4[0] - 98, A4[1] - 164, "Veri*factu QR")
            c.setFillColor(HexColor("#333333"))
        except Exception as exc:
            logger.warning("No s'ha pogut generar el QR al PDF: %s", exc)

    # Taula de línies
    y = A4[1] - 190
    c.setFont("Helvetica-Bold", 8.5)
    c.drawString(30, y, "Concepte")
    c.drawRightString(335, y, "Qt.")
    c.drawRightString(405, y, "Preu u.")
    c.drawRightString(455, y, "Dto%")
    c.drawRightString(500, y, "IVA%")
    c.drawRightString(565, y, "Subtotal")
    y -= 6
    c.line(30, y, A4[0] - 30, y)
    y -= 14

    c.setFont("Helvetica", 8.5)
    for lin in linies or []:
        if y < 140:
            c.showPage()
            y = A4[1] - 60
            c.setFont("Helvetica", 8.5)
        concepte = str((lin.get("concepte") if isinstance(lin, dict) else getattr(lin, "concepte", None)) or "")[:58]
        qt = float((lin.get("quantitat") if isinstance(lin, dict) else getattr(lin, "quantitat", None)) or 1.0)
        preu = float((lin.get("preu_venda_unitari") if isinstance(lin, dict) else getattr(lin, "preu_venda_unitari", None)) or 0.0)
        dto = float((lin.get("descompte_aplicat_pct") if isinstance(lin, dict) else getattr(lin, "descompte_aplicat_pct", None)) or 0.0)
        iva = float((lin.get("tipus_iva") if isinstance(lin, dict) else getattr(lin, "tipus_iva", None)) or 0.0)
        sub = float((lin.get("subtotal") if isinstance(lin, dict) else getattr(lin, "subtotal", None)) or 0.0)
        c.drawString(30, y, concepte)
        c.drawRightString(335, y, f"{qt:.2f}")
        c.drawRightString(405, y, f"{preu:.2f}")
        c.drawRightString(455, y, f"{dto:.1f}")
        c.drawRightString(500, y, f"{iva:.0f}")
        c.drawRightString(565, y, f"{sub:.2f} €")
        y -= 14

    y -= 10
    c.line(340, y, A4[0] - 30, y)
    y -= 16
    c.setFont("Helvetica", 9.5)
    c.drawString(350, y, "Base Imposable:")
    c.drawRightString(565, y, f"{base_imposable:.2f} €")
    y -= 14
    c.drawString(350, y, "Quota IVA:")
    c.drawRightString(565, y, f"{quota_iva:.2f} €")
    if import_suplits > 0:
        y -= 14
        c.drawString(350, y, "Suplerts (554):")
        c.drawRightString(565, y, f"{import_suplits:.2f} €")
    if import_retencio > 0:
        y -= 14
        c.drawString(350, y, "Retenció IRPF:")
        c.drawRightString(565, y, f"-{import_retencio:.2f} €")
    if import_retencio_garantia > 0:
        y -= 14
        c.drawString(350, y, "Retenció Garantia (4308):")
        c.drawRightString(565, y, f"-{import_retencio_garantia:.2f} €")
    y -= 18
    c.setFont("Helvetica-Bold", 11.5)
    c.drawString(350, y, "TOTAL EXIGIBLE:")
    c.drawRightString(565, y, f"{import_total:.2f} €")

    if es_isp:
        c.setFont("Helvetica-Oblique", 7.5)
        c.drawString(
            30,
            72,
            "Operació amb inversió del subjecte passiu d'acord amb l'art. 84.U.2n.f de la Llei 37/1992 de l'IVA.",
        )

    if not es_esborrany and hash_actual:
        c.setFont("Helvetica", 7)
        c.setFillColor(HexColor("#999999"))
        c.drawString(30, 50, f"Hash SHA-256: {hash_actual}")
        c.drawString(
            30,
            35,
            f"Hash anterior: {hash_anterior}" if hash_anterior else "Hash anterior: (Primera factura de la sèrie)",
        )

    c.showPage()
    c.save()
    return ruta_desti


# Aliases per compatibilitat amb tests existents
calcular_hash_verifactu = generar_sha256_encadenat
generar_qr_verifactu_aeat = generar_qr_verifactu
generar_contingut_qr_aeat = generar_qr_verifactu
generar_pdf_factura = generar_factura_pdf
