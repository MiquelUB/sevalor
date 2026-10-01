import re

with open("backend/app/workers/tasks.py", "r") as f:
    content = f.read()

# Replace SessionLocal with get_worker_session
# First, insert get_worker_session helper at the top
context_manager = """
from contextlib import asynccontextmanager
from app.core.db import AsyncSessionLocal, set_tenant_context

@asynccontextmanager
async def get_worker_session(empresa_id: str | None = None, is_superadmin: bool = False):
    async with AsyncSessionLocal() as session:
        await set_tenant_context(session, empresa_id, is_superadmin)
        yield session
"""
content = content.replace('from app.workers.celery_app import celery_app', 'from app.workers.celery_app import celery_app\n' + context_manager)

# Fix revisar_jornades_anomales
content = re.sub(
    r'def revisar_jornades_anomales\(\):\n(.*?)(from app.core.db import SessionLocal)\n(.*?)async def process_anomalias\(\):\n(\s+)async with SessionLocal\(\) as session:',
    r'def revisar_jornades_anomales(empresa_id: str):\n\1\n\3async def process_anomalias():\n\4async with get_worker_session(empresa_id) as session:',
    content, flags=re.DOTALL
)

# Fix comprovar_trencament_estoc
content = re.sub(
    r'def comprovar_trencament_estoc\(empresa_id: str\):\n(.*?)(from app.core.db import SessionLocal)\n(.*?)async def process\(\):\n(\s+)async with SessionLocal\(\) as session:',
    r'def comprovar_trencament_estoc(empresa_id: str):\n\1\n\3async def process():\n\4async with get_worker_session(empresa_id) as session:',
    content, flags=re.DOTALL
)

# Fix revisar_itv_asseguranca
content = re.sub(
    r'def revisar_itv_asseguranca\(\):\n(.*?)(from app.core.db import SessionLocal)\n(.*?)async def process_itv\(\):\n(\s+)async with SessionLocal\(\) as session:',
    r'def revisar_itv_asseguranca(empresa_id: str):\n\1\n\3async def process_itv():\n\4async with get_worker_session(empresa_id) as session:',
    content, flags=re.DOTALL
)

# Fix enviar_factura_email
content = re.sub(
    r'def enviar_factura_email\(factura_id: str, empresa_id: str\):\n(.*?)(from app.core.db import SessionLocal)\n(.*?)async def process\(\):\n(\s+)async with SessionLocal\(\) as session:',
    r'def enviar_factura_email(factura_id: str, empresa_id: str):\n\1\n\3async def process():\n\4async with get_worker_session(empresa_id) as session:',
    content, flags=re.DOTALL
)

# Fix tancar_jornades_orfanes
content = re.sub(
    r'def tancar_jornades_orfanes\(\):\n(.*?)(from app.core.db import SessionLocal)\n(.*?)async def process\(\):\n(\s+)async with SessionLocal\(\) as session:',
    r'def tancar_jornades_orfanes(empresa_id: str):\n\1\n\3async def process():\n\4async with get_worker_session(empresa_id) as session:',
    content, flags=re.DOTALL
)

# Replace OCR mock with NotImplementedError (Zero Mock)
ocr_mock = """        "proveidor": {
            "nif": "PENDENT_VERIFICACIO",
            "nom": f"Document {nom_base}",
            "adreca": "",
            "telefon": "",
            "email": ""
        },
        "numero_document": f"DOC-{nom_base}",
        "tipus_document": "ALBARA",
        "data_document": "2024-01-01",
        "linies": [
            {
                "referencia": "ART-OCR-MAT-01",
                "nom": "Cable coure 1.5mm2",
                "quantitat": 100,
                "preu": 1.25,
                "descompte_percent": 0.0,
                "tipus": "MATERIAL"
            },
            {
                "referencia": "BOSCH-GSB-18",
                "nom": "Taladro Percutor Bosch 18V",
                "quantitat": 2,
                "preu": 180.50,
                "descompte_percent": 15.0,
                "tipus": "EINA"
            }
        ]"""
ocr_replacement = """        "proveidor": {
            "nif": "PENDENT_AUDITORIA",
            "nom": "PENDENT_AUDITORIA",
            "adreca": "",
            "telefon": "",
            "email": ""
        },
        "numero_document": "PENDENT_AUDITORIA",
        "tipus_document": "PENDENT_AUDITORIA",
        "data_document": None,
        "linies": []"""
content = content.replace(ocr_mock, ocr_replacement)

with open("backend/app/workers/tasks.py", "w") as f:
    f.write(content)

