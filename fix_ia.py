with open("backend/app/api/v1/gestio/ia.py", "r") as f:
    content = f.read()

import_limiter = """from fastapi import APIRouter, Depends, HTTPException, status, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
"""

content = content.replace('from fastapi import APIRouter, Depends, HTTPException, status', import_limiter)

route_def = """@router.post("/rag", response_model=RagQueryOut, status_code=status.HTTP_200_OK)
@limiter.limit("10/minute")
async def consultar_ia_rag(
    request: Request,
    dades: RagQueryIn,"""

content = content.replace("""@router.post("/rag", response_model=RagQueryOut, status_code=status.HTTP_200_OK)
async def consultar_ia_rag(
    dades: RagQueryIn,""", route_def)

with open("backend/app/api/v1/gestio/ia.py", "w") as f:
    f.write(content)
