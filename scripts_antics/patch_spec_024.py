with open("sdd_sevalor/specs/024-workers-processament-asincron.md", "r") as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if "connectats al broker Redis 7 mitjançant contrasenya." in line:
        insert_text = """        - **Detall Tècnic d'Infraestructura:** El `docker-compose.yml` inclourà els serveis `redis`, `celery_worker` i `celery_beat`. Es requerirà obligatòriament una tasca base `ping()` asíncrona per a sondejos de salut (Health Checks).
"""
        lines.insert(i+1, insert_text)
        break

with open("sdd_sevalor/specs/024-workers-processament-asincron.md", "w") as f:
    f.writelines(lines)
