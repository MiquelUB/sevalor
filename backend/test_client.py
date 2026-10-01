from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
resp = client.post("/api/v1/gestio/copilot/rag", json={"prompt": "hola"})
print(resp.status_code)
print(resp.json())
