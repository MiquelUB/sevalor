import asyncio
from httpx import AsyncClient, ASGITransport
import sys
sys.path.insert(0, "./backend")
from app.main import app
from app.core.db import AsyncSessionLocal
from app.models.models import Usuari
from sqlalchemy import select
from app.api.v1.auth import verify_password
import bcrypt

async def debug():
    async with AsyncSessionLocal() as session:
        res = await session.execute(select(Usuari).where(Usuari.email == "admin@sevalor.com"))
        u = res.scalars().first()
        print("Hash in DB:", u.password_hash)
        print("Verify with Password123!:", verify_password("Password123!", u.password_hash))
        print("Verify directly:", bcrypt.checkpw(b"Password123!", u.password_hash.encode('utf-8')))

asyncio.run(debug())
