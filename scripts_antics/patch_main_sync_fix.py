with open("backend/app/main.py", "r") as f:
    content = f.read()

mount_sync = 'app.include_router(sync_router, prefix=settings.API_V1_STR + "/operari_pwa")\n'
if 'app.include_router(sync_router' not in content:
    content = content.replace('app.include_router(vehicles_pwa_router, prefix=settings.API_V1_STR)\n', 'app.include_router(vehicles_pwa_router, prefix=settings.API_V1_STR)\n' + mount_sync)

with open("backend/app/main.py", "w") as f:
    f.write(content)
