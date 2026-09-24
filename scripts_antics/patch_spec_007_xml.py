with open("sdd_sevalor/specs/007-gestio-comptabilitat.md", "r") as f:
    content = f.read()

new_detail = """
--------------------------------------------------------------------------------
Detalls Tècnics - Generador XML AEAT (Veri*factu - Tasca 5.2)
- El backend ha d'exposar un endpoint (`GET /api/v1/gestio/comptabilitat/factures/{id}/xml`) que exporti la factura en format XML estructurat d'acord amb els esquemes XSD públics de l'AEAT per a Veri*factu.
- Aquest generador ha de suportar el cas específic d'"Inversión del Sujeto Pasivo" (ISP). En aquests casos, la quota d'IVA repercutit ha de ser 0,00€ i el tag XML corresponent (`CausaExencion` o similar, si escau normativament) ha d'indicar aquesta casuística.
- El XML generat ha d'incloure el `hash_sha256` calculat a la fase anterior.
"""

content = content + new_detail + "\n"

with open("sdd_sevalor/specs/007-gestio-comptabilitat.md", "w") as f:
    f.write(content)
