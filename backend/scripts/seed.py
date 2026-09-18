import asyncio
import os
import sys
import uuid
import bcrypt
from sqlalchemy import select, func

# Inject backend path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.db import AsyncSessionLocal, engine
from app.core.db import Base
from app.models import models  # Ensure all models are registered
from app.models.models import Empresa, Usuari
from app.api.v1.gestio.operaris import hash_pin

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

async def seed():
    print("⏳ Creant taules de la base de dades si no existeixen...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Taules comprovades correctament!")

    async with AsyncSessionLocal() as session:
        # 1. Empresa Principal
        stmt = select(Empresa).where(Empresa.subdomini == "admin")
        res = await session.execute(stmt)
        empresa = res.scalars().first()

        if not empresa:
            empresa = Empresa(
                id=uuid.uuid4(),
                nom="Sevalor Central",
                nif="B12345678",
                subdomini="admin",
                pla_subscripcio="ENTERPRISE",
                estat_pagament="ACTIU",
            )
            session.add(empresa)
            await session.flush()
            print(f"🏢 Nova Empresa creada: {empresa.nom} (ID: {empresa.id})")
        else:
            print(f"🏢 Empresa existent utilitzada: {empresa.nom} (ID: {empresa.id})")

        # 2. Superadmin (/superadmin/login)
        stmt_super = select(Usuari).where(func.lower(Usuari.email) == "admin@sevalor.com")
        res_super = await session.execute(stmt_super)
        superadmin = res_super.scalars().first()

        pass_hash = hash_password("Password123!")
        pin_h = hash_pin("1234")

        if not superadmin:
            superadmin = Usuari(
                id=uuid.uuid4(),
                empresa_id=empresa.id,
                nif="SUPERADMIN",
                nom="Super",
                cognoms="Admin",
                email="admin@sevalor.com",
                password_hash=pass_hash,
                pin_hash=pin_h,
                rol="SUPERADMIN",
                estat="ACTIU"
            )
            session.add(superadmin)
            print("👑 Superadmin creat: admin@sevalor.com")
        else:
            superadmin.password_hash = pass_hash
            superadmin.pin_hash = pin_h
            superadmin.rol = "SUPERADMIN"
            superadmin.estat = "ACTIU"
            print("👑 Superadmin actualitzat: admin@sevalor.com")

        # 3. Gestió / Oficina (/gestio/login)
        stmt_boss = select(Usuari).where(func.lower(Usuari.email) == "gestio@sevalor.com")
        res_boss = await session.execute(stmt_boss)
        boss = res_boss.scalars().first()

        if not boss:
            boss = Usuari(
                id=uuid.uuid4(),
                empresa_id=empresa.id,
                nif="BOSS001",
                nom="Director",
                cognoms="Oficina",
                email="gestio@sevalor.com",
                password_hash=pass_hash,
                pin_hash=pin_h,
                rol="BOSS",
                estat="ACTIU"
            )
            session.add(boss)
            print("💼 Usuari de Gestió creat: gestio@sevalor.com")
        else:
            boss.password_hash = pass_hash
            boss.pin_hash = pin_h
            boss.rol = "BOSS"
            boss.estat = "ACTIU"
            print("💼 Usuari de Gestió actualitzat: gestio@sevalor.com")

        # 4. Operari de Camp (/operari/login)
        stmt_op = select(Usuari).where(func.upper(Usuari.nif) == "12345678A")
        res_op = await session.execute(stmt_op)
        operari = res_op.scalars().first()

        if not operari:
            operari = Usuari(
                id=uuid.uuid4(),
                empresa_id=empresa.id,
                nif="12345678A",
                nom="Joan",
                cognoms="Operari",
                email="operari@sevalor.com",
                password_hash=pass_hash,
                pin_hash=pin_h,
                rol="OPERARI",
                estat="ACTIU"
            )
            session.add(operari)
            print("🚜 Operari creat: 12345678A")
        else:
            operari.pin_hash = pin_h
            operari.password_hash = pass_hash
            operari.rol = "OPERARI"
            operari.estat = "ACTIU"
            print("🚜 Operari actualitzat: 12345678A")

        await session.commit()


if __name__ == "__main__":
    asyncio.run(seed())
