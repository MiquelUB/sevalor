import asyncio
import uuid
from sqlalchemy import select, text
from app.core.db import AsyncSessionLocal, set_tenant_context
from app.models.models import Client

async def test():
    empresa_id = "095ea559-8162-4998-b4ca-d96ed839afc5"
    async with AsyncSessionLocal() as session:
        await set_tenant_context(session, empresa_id)
        
        stmt_nif = select(Client).where(Client.empresa_id == uuid.UUID(empresa_id), Client.nif == "TESTNIF")
        result_nif = await session.execute(stmt_nif)
        
        c = Client(
            empresa_id=uuid.UUID(empresa_id),
            codi="TEST-AUTOC2",
            rao_social="TEST RLS",
            nif="00000000T"
        )
        session.add(c)
        await session.flush()
        
        try:
            await session.refresh(c)
            print("Refresh successful!")
        except Exception as e:
            print("Refresh failed:", e)

        res = await session.execute(text("SHOW app.current_empresa_id"))
        print("Setting is:", res.scalar())
        await session.rollback()

asyncio.run(test())
