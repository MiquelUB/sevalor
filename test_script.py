import asyncio
from httpx import AsyncClient, ASGITransport
import uuid
from datetime import date

async def run():
    from tests.test_004_gestio_magatzem_ocr import app
    print("Testing")

asyncio.run(run())
