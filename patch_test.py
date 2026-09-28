import re

path = "backend/tests/test_006_gestio_flota.py"
with open(path, "r") as f:
    text = f.read()

target = """@pytest.mark.asyncio
async def test_alta_vehicle_completa_amb_spec006(admin_session, headers, boss_token):
    token, empresa_id = boss_token
    payload = {"""

replace = """@pytest.mark.asyncio
async def test_alta_vehicle_completa_amb_spec006(admin_session, headers, boss_token):
    token, empresa_id = boss_token
    boss_nif = "C" + str(uuid.uuid4())[:8].upper()
    admin_session.add(Empresa(
        id=uuid.UUID(empresa_id), nom='Test Flota 2', nif=boss_nif, subdomini='testflota2-' + str(uuid.uuid4())[:5], pla_subscripcio='STARTER', estat_pagament='ACTIU'
    ))
    await admin_session.flush()
    await admin_session.commit()
    payload = {"""

text = text.replace(target, replace)
with open(path, "w") as f:
    f.write(text)
