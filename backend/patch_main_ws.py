import re

with open('/media/akaun/Project_1/SEVALOR/backend/app/main.py', 'r') as f:
    content = f.read()

import_line = "from app.api.v1.gestio.ws import router as ws_router\n"
if "gestio.ws" not in content:
    content = content.replace("from app.api.v1.gestio.cerca import router as cerca_router", import_line + "from app.api.v1.gestio.cerca import router as cerca_router")

include_line = "app.include_router(ws_router, prefix=settings.API_V1_STR)\n"
if "app.include_router(ws_router" not in content:
    content = content.replace("app.include_router(feines_router, prefix=settings.API_V1_STR)", include_line + "app.include_router(feines_router, prefix=settings.API_V1_STR)")

with open('/media/akaun/Project_1/SEVALOR/backend/app/main.py', 'w') as f:
    f.write(content)
