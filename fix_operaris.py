import re
with open("backend/app/api/v1/gestio/operaris.py", "r") as f:
    lines = f.readlines()
out = []
imports = []
for line in lines:
    if "from datetime import datetime, timezone" in line or "from fastapi import File, UploadFile" in line or "from app.api.v1.operari_pwa.jornada import JornadaInici" in line or "from app.models.models import RegistreJornadaLaboral" in line or "from app.services.ocr_service import processar_dni_ocr" in line or "from app.core.security import veto_enginyer_finances" in line:
        imports.append(line)
    else:
        out.append(line)
final = []
for idx, line in enumerate(out):
    final.append(line)
    if "from app.models.models import" in line and "Usuari" in line and not out[idx-1].startswith("from"):
        final.extend(imports)

with open("backend/app/api/v1/gestio/operaris.py", "w") as f:
    f.writelines(final)
