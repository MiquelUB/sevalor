with open("backend/app/api/v1/gestio/comptabilitat.py", "r") as f:
    content = f.read()

new_endpoint = """
from fastapi.responses import Response
import xml.etree.ElementTree as ET

@router.get("/factures/{factura_id}/xml")
async def exportar_factura_xml(
    factura_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = request.state.empresa_id
    if not empresa_id:
        raise HTTPException(status_code=401)

    stmt = select(FacturaCapcalera).where(
        FacturaCapcalera.id == factura_id,
        FacturaCapcalera.empresa_id == uuid.UUID(empresa_id)
    )
    factura = (await db.execute(stmt)).scalars().first()
    if not factura:
        raise HTTPException(status_code=404, detail="Factura no trobada")

    # Creació de l'estructura XML Veri*factu
    root = ET.Element("RegistroAlta")
    
    # Dades identificatives
    id_factura = ET.SubElement(root, "IDFactura")
    num_serie = ET.SubElement(id_factura, "NumSerieFactura")
    num_serie.text = f"{factura.serie}-{factura.numero_factura}"
    data_exp = ET.SubElement(id_factura, "FechaExpedicionFactura")
    data_exp.text = factura.data_emissio.strftime("%d-%m-%Y")
    
    # Desglossament i Inversió de Subjecte Passiu (ISP)
    desglose = ET.SubElement(root, "Desglose")
    if factura.quota_iva == 0.0:
        detalle = ET.SubElement(desglose, "DetalleExenta")
        causa = ET.SubElement(detalle, "CausaExencion")
        causa.text = "I"  # Codi I = Inversión Sujeto Pasivo
        base = ET.SubElement(detalle, "BaseImponible")
        base.text = f"{factura.base_imposable:.2f}"
    else:
        detalle = ET.SubElement(desglose, "DetalleSujeta")
        base = ET.SubElement(detalle, "BaseImponible")
        base.text = f"{factura.base_imposable:.2f}"
        quota = ET.SubElement(detalle, "CuotaRepercutida")
        quota.text = f"{factura.quota_iva:.2f}"

    # Encadenament
    encadenamiento = ET.SubElement(root, "Encadenamiento")
    reg_ant = ET.SubElement(encadenamiento, "RegistroAnterior")
    if factura.hash_anterior:
        reg_ant.text = factura.hash_anterior
    else:
        reg_ant.text = "PRIMER_REGISTRO"

    # Sistema informàtic
    sist_info = ET.SubElement(root, "SistemaInformatico")
    hash_node = ET.SubElement(sist_info, "Hash")
    hash_node.text = factura.hash_sha256

    xml_str = ET.tostring(root, encoding="utf-8", xml_declaration=True).decode("utf-8")
    
    return Response(content=xml_str, media_type="application/xml")
"""

content = content + new_endpoint

with open("backend/app/api/v1/gestio/comptabilitat.py", "w") as f:
    f.write(content)
