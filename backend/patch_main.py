import re

with open('/media/akaun/Project_1/SEVALOR/backend/app/main.py', 'r') as f:
    content = f.read()

import_line = "from app.api.v1.gestio.dashboard import router as dashboard_router\n"
if "gestio.dashboard" not in content:
    content = content.replace("from app.api.v1.gestio.cerca import router as cerca_router", import_line + "from app.api.v1.gestio.cerca import router as cerca_router")

include_line = "app.include_router(dashboard_router, prefix=settings.API_V1_STR)\n"
if "dashboard_router" not in content:
    pass # Wait, if I already added it in the previous step it would be.
    
if "app.include_router(dashboard_router" not in content:
    content = content.replace("app.include_router(feines_router, prefix=settings.API_V1_STR)", include_line + "app.include_router(feines_router, prefix=settings.API_V1_STR)")

with open('/media/akaun/Project_1/SEVALOR/backend/app/main.py', 'w') as f:
    f.write(content)
