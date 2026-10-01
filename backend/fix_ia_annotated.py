import re

with open("/media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/ia.py", "r") as f:
    content = f.read()

content = content.replace("from typing import Any, Dict, Optional", "from typing import Any, Dict, Optional, Annotated")
content = content.replace(
    "    audio: UploadFile = File(...),",
    "    audio: Annotated[UploadFile, File(...)],"
)
content = content.replace(
    "    foto: Optional[UploadFile] = File(None),",
    "    foto: Annotated[Optional[UploadFile], File(None)] = None,"
)
content = content.replace(
    "    incidencia_id: Optional[str] = Form(None),",
    "    incidencia_id: Annotated[Optional[str], Form(None)] = None,"
)
content = content.replace(
    "    ordre_treball_id: Optional[str] = Form(None),",
    "    ordre_treball_id: Annotated[Optional[str], Form(None)] = None,"
)

with open("/media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/ia.py", "w") as f:
    f.write(content)
