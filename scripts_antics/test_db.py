import asyncio
import asyncpg
import sys
import os

# parse from backend/tests/conftest.py
url = None
with open("backend/tests/conftest.py") as f:
    for line in f:
        if "TEST_DB_URL =" in line:
            url = line.split('"')[1]
            break

async def run():
    print(f"Connecting to {url}")
    conn = await asyncpg.connect(url.replace("+asyncpg", ""))
    rows = await conn.fetch("SELECT relname FROM pg_class WHERE relrowsecurity = true;")
    print("TABLES WITH RLS:")
    for r in rows:
        print(r['relname'])
    await conn.close()

asyncio.run(run())
