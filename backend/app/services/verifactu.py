"""
Motor de Facturació Legal Veri*factu (RD 1007/2023) amb ReportLab.

Implementa:
- Generació de PDF amb QR estructurat segons especificació AEAT.
- Hash SHA-256 encadenat amb bloqueig pessimista (SELECT FOR UPDATE).
- Estil camaleònic per tenant (--color-primary, --color-secondary, logotip).
- Outbox Pattern: la factura es consolida localment i l'enviament SOAP es delega a outbox_aeat.
- Zero Mock Data: si no hi ha factura anterior, hash_anterior = None (Dia 0 real).
"""

import uuid
import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select, text
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
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas
    from reportlab.lib.colors import HexColor
    from reportlab.graphics.barcode import qr

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
        ruta_desti, serie, numero_factura, hash_actual,
    )

    return {
        "hash_sha256": hash_actual,
        "hash_anterior": hash_anterior,
        "qr_content": qr_content,
        "pdf_path": ruta_desti,
        "estat_generacio": "GENERAT",
    }


# Aliases per compatibilitat amb tests existents
calcular_hash_verifactu = generar_sha256_encadenat
generar_qr_verifactu_aeat = generar_qr_verifactu
generar_contingut_qr_aeat = generar_qr_verifactu
generar_pdf_factura = generar_factura_pdf