with open("backend/app/main.py", "r") as f:
    lines = f.readlines()

import_idx = 0
for i, line in enumerate(lines):
    if "from app.api.v1.health import router" in line:
        import_idx = i
        break
lines.insert(import_idx + 1, "from app.api.v1.workers import router as workers_router\n")

include_idx = 0
for i, line in enumerate(lines):
    if "app.include_router(telemetria_router" in line:
        include_idx = i
        break
lines.insert(include_idx + 1, 'app.include_router(workers_router, prefix=settings.API_V1_STR + "/workers", tags=["Workers Celery"])\n')

with open("backend/app/main.py", "w") as f:
    f.writelines(lines)
