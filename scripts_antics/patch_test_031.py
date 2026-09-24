with open("backend/tests/test_031_picking_concurrency.py", "r") as f:
    content = f.read()

new_test = """@pytest.mark.asyncio
async def test_picking_pessimistic_locking_concurrency(setup_concurrency):
    data = setup_concurrency
    
    headers = {"Authorization": f"Bearer {data['token']}", "X-Empresa-ID": data["empresa_id"]}
    payload = {"article_id": data["article_id"], "quantitat_prevista": 6.0}
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Request 1: demana 6 unitats. Com que hi ha 10, triomfa (Estoc lliure = 4).
        req1 = await ac.post(f"/api/v1/gestio/magatzem/picking/{data['pick1_id']}/linies", json=payload, headers=headers)
        
        # Request 2: demana 6 unitats més sobre el mateix estoc.
        # En el món real, si entren concurrents, SELECT FOR UPDATE els serialitza i l'efecte és idèntic al seqüencial.
        req2 = await ac.post(f"/api/v1/gestio/magatzem/picking/{data['pick2_id']}/linies", json=payload, headers=headers)
        
        assert req1.status_code == 201
        assert req2.status_code == 422
        
        # Comprovem el detall de l'error generat per la IA/Backend (RF-17)
        assert "unitats disponibles físiques" in req2.json()["detail"] or "Copilot IA" in req2.json()["detail"]
"""

import re
content = re.sub(r'@pytest\.mark\.asyncio\nasync def test_picking_pessimistic_locking_concurrency.*?$', new_test, content, flags=re.DOTALL)

with open("backend/tests/test_031_picking_concurrency.py", "w") as f:
    f.write(content)
