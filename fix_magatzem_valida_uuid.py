import re
path = "/media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/magatzem.py"
with open(path, "r") as f:
    text = f.read()

# I will replace `emp_uuid = valida_uuid(empresa_id)` with a try-except block converting to uuid.
# Actually, since it's used many times, I can just DEFINE `valida_uuid` at the top of the file!

target = """from pydantic import BaseModel, Field, ConfigDict"""
replacement = """from pydantic import BaseModel, Field, ConfigDict

def valida_uuid(id_str: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(id_str))
    except Exception:
        raise HTTPException(status_code=400, detail="Identificador d'empresa invàlid.")
"""
if target in text:
    text = text.replace(target, replacement)
    print("valida_uuid defined")
else:
    print("target not found")

with open(path, "w") as f:
    f.write(text)
