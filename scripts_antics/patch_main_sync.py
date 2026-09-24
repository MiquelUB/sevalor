with open("backend/app/main.py", "r") as f:
    content = f.read()

import_sync = "from app.api.v1.operari_pwa.sync import router as sync_router\n"
if "from app.api.v1.operari_pwa.sync import router as sync_router" not in content:
    content = content.replace("from app.api.v1.operari_pwa.vehicles import router as vehicles_pwa_router\n", "from app.api.v1.operari_pwa.vehicles import router as vehicles_pwa_router\n" + import_sync)

mount_sync = 'app.include_router(sync_router, prefix="/api/v1/operari_pwa")\n'
if 'app.include_router(sync_router, prefix="/api/v1/operari_pwa")' not in content:
    content = content.replace('app.include_router(vehicles_pwa_router, prefix="/api/v1/operari_pwa")\n', 'app.include_router(vehicles_pwa_router, prefix="/api/v1/operari_pwa")\n' + mount_sync)

with open("backend/app/main.py", "w") as f:
    f.write(content)
