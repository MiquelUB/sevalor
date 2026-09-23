
with open("app/api/v1/gestio/magatzem.py", "r") as f:
    content = f.read()

content = content.replace('"numero_document": "ALB-2026-001",', '"numero_document": f"ALB-2026-{random.randint(100, 999)}",')

with open("app/api/v1/gestio/magatzem.py", "w") as f:
    f.write(content)
