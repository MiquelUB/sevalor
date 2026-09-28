path = "/media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/magatzem.py"
with open(path, "r") as f:
    text = f.read()

target = """        quantitat_factura = sum([float(l.quantitat) for l in payload.linies])"""
replacement = """        # Com que les eines no generen MovimentEstoc, només sumem les quantitats de MATERIALS de la factura per quadrar-ho
        quantitat_factura = sum([float(l.quantitat) for l in payload.linies if l.tipus != "EINA"])"""

if target in text:
    text = text.replace(target, replacement)
    print("Factura validation fixed!")
else:
    print("Target not found")

with open(path, "w") as f:
    f.write(text)
