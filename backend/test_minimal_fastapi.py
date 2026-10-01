import asyncio
from fastapi import FastAPI, UploadFile, File
from httpx import AsyncClient, ASGITransport

app = FastAPI()

@app.post("/test")
async def test_endpoint(audio: UploadFile = File(...)):
    return {"ok": True}

async def main():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        files = {"audio": ("test.webm", b"data", "audio/webm")}
        resp = await client.post("/test", files=files)
        print(resp.json())

asyncio.run(main())
