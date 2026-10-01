import asyncio
import asyncpg
import sys

async def main():
    conn = await asyncpg.connect('postgresql://postgres:postgres@127.0.0.1:5433/sevalor')
    row = await conn.fetchrow("SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname = 'usuaris'")
    print(row)
    if row and row['relrowsecurity'] and row['relforcerowsecurity']:
        print("SUCCESS")
    else:
        print("FAIL")
    await conn.close()

asyncio.run(main())
