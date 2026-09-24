import asyncio
import uuid
import httpx
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from app.models.models import Empresa, Usuari

async def run():
    engine = create_async_engine("postgresql+asyncpg://postgres:postgres@localhost:5433/sevalor")
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        # Get an active user
        result = await session.execute(select(Usuari).limit(1))
        user = result.scalars().first()
        if not user:
            print("No users found.")
            return

        import jwt
        from datetime import datetime, timedelta
        from app.core.config import settings
        
        expire = datetime.utcnow() + timedelta(minutes=60)
        to_encode = {"sub": str(user.id), "rol": user.rol, "empresa_id": str(user.empresa_id), "exp": expire}
        token = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        
        async with httpx.AsyncClient(base_url="http://127.0.0.1:8000") as client:
            print(f"Token: {token}")
            
            resp = await client.get("/api/v1/gestio/magatzem/articles", headers={"Authorization": f"Bearer {token}", "X-Empresa-ID": str(user.empresa_id)})
            print("Status:", resp.status_code)
            
            client_res = await session.execute(select(app.models.models.Client).where(app.models.models.Client.empresa_id == user.empresa_id).limit(1))
            cli = client_res.scalars().first()
            if cli:
                resp2 = await client.get(f"/api/v1/gestio/clients/{cli.id}/fitxa360", headers={"Authorization": f"Bearer {token}", "X-Empresa-ID": str(user.empresa_id)})
                print("Status Fitxa:", resp2.status_code)
                print("Body Fitxa:", resp2.text)

import app.models.models
asyncio.run(run())
