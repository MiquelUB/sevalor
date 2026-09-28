import glob

def patch_spec(filepath, title, what, why):
    with open(filepath, "r") as f:
        content = f.read()
    
    if "Alta Màgica OCR" in content: return

    rf_target = "### Requisitos Funcionales"
    rf_replacement = f"""### Requisitos Funcionales

#### RF-00: Alta Màgica OCR (Zero Data Entry)
- **QUÉ**: {what}
- **PER QUÉ**: {why}
- **CÓMO**: Mediante un endpoint predictivo asíncrono que procesa el documento con visión artificial y devuelve la estructura JSON rellenada para su confirmación visual en la UI."""

    if rf_target in content:
        content = content.replace(rf_target, rf_replacement)
        with open(filepath, "w") as f:
            f.write(content)
        print(f"Patched {filepath}")

patch_spec("sevalor_AgentV2/docs/sdd/specs/002-gestio-clients.md", "Clients", 
    "El sistema debe permitir dar de alta un Cliente (CIF, Razón Social, Dirección, IBAN) simplemente subiendo un documento oficial (como un recibo, un contrato o tarjeta CIF).",
    "Para aplicar la política global de Zero Data Entry, ahorrando tiempo de teclado y minimizando errores tipográficos.")

patch_spec("sevalor_AgentV2/docs/sdd/specs/003-gestio-proveidors.md", "Proveïdors",
    "El sistema debe permitir registrar un Proveedor y sus Certificados (CAE) automáticamente subiendo sus documentos fiscales (Factura proforma o CIF).",
    "Política global Zero Data Entry: acelerar el onboarding de la cadena de suministro evitando la introducción manual de los 20 campos de la ficha.")

patch_spec("sevalor_AgentV2/docs/sdd/specs/007-gestio-comptabilitat.md", "Comptabilitat",
    "El registro de Gastos y Tickets debe realizarse fotografiando el ticket original, de forma que el OCR extraiga Proveedor, NIF, Base Imponible, IVA y Total de forma determinista.",
    "Para conseguir un asiento contable automático y preciso, eliminando el picado manual de tickets a final de mes.")

