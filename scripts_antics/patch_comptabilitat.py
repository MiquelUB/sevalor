with open("backend/app/api/v1/gestio/comptabilitat.py", "r") as f:
    content = f.read()

import re

# We need to find where the `FacturaCapcalera` is created.
# Looks like:
# nova_factura = FacturaCapcalera(
#         empresa_id=uuid.UUID(empresa_id),
#         numero_factura=payload.numero_factura,
#         serie=payload.serie,
#         ...
#     )
#     db.add(nova_factura)

# We will inject the Hash chaining logic before `nova_factura` is created.

hash_logic = """
    # Tasca 5.1: Hash Encadenat (Veri*factu)
    stmt_last = select(FacturaCapcalera.hash_cadena).where(
        FacturaCapcalera.empresa_id == uuid.UUID(empresa_id)
    ).order_by(FacturaCapcalera.numero_factura.desc()).limit(1).with_for_update()
    
    result_last = await db.execute(stmt_last)
    prev_hash = result_last.scalar_one_or_none() or ""
    
    import hashlib
    hash_payload = f"{empresa_id}|{payload.numero_factura}|{import_total:.2f}|{prev_hash}"
    nou_hash = hashlib.sha256(hash_payload.encode('utf-8')).hexdigest()

    nova_factura = FacturaCapcalera(
        hash_cadena=nou_hash,
"""

content = content.replace("    nova_factura = FacturaCapcalera(\n", hash_logic)

with open("backend/app/api/v1/gestio/comptabilitat.py", "w") as f:
    f.write(content)
