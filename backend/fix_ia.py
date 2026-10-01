import re
with open("/media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/ia.py", "r") as f:
    content = f.read()

content = content.replace("incidencia_id=incidencia_id,", "incidencia_id=uuid.UUID(incidencia_id) if incidencia_id else None,")
content = content.replace("ordre_treball_id=ordre_treball_id,", "ordre_treball_id=uuid.UUID(ordre_treball_id) if ordre_treball_id else None,")

with open("/media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/ia.py", "w") as f:
    f.write(content)
