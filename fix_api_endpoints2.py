import re

path = "/media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/flota.py"
with open(path, "r") as f:
    text = f.read()

target = """        nom_arxiu=file.filename,
        ruta_arxiu=file_path,
        creat_per_id=uuid.UUID(current_user["sub"])
    )"""

replace = """        nom_arxiu=file.filename,
        ruta_arxiu=file_path,
        creat_per_id=None
    )"""

text = text.replace(target, replace)

with open(path, "w") as f:
    f.write(text)
print("creat_per_id fixed")
