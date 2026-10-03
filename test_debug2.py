import asyncio
import sys
sys.path.insert(0, "./backend")
from app.core.db import AsyncSessionLocal
from app.models.models import Usuari
from sqlalchemy import select, func
from app.api.v1.auth import verify_password
from pydantic import BaseModel, EmailStr

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

async def debug():
    req = LoginRequest(email="admin@sevalor.com", password="Password123!")
    async with AsyncSessionLocal() as session:
        stmt = select(Usuari).where(
            func.lower(Usuari.email) == req.email.lower()
        )
        result = await session.execute(stmt)
        usuari = result.scalars().first()
        
        if not usuari:
            print("Usuari not found")
            return
            
        print("Found usuari:", usuari.email)
        is_valid = verify_password(req.password, usuari.password_hash)
        print("Password valid:", is_valid)
        print("Role:", usuari.rol)

asyncio.run(debug())
