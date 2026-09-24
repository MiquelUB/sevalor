with open("backend/tests/test_telegram_rag.py", "r") as f:
    content = f.read()

content = content.replace(
"""    admin_session.add(Empresa(id=uuid.UUID(empresa_id), nom="Test Empresa", nif=boss_nif, subdomini="testragbot", pla_subscripcio="STARTER", estat_pagament="ACTIU"))
    
    # Crear client""",
"""    admin_session.add(Empresa(id=uuid.UUID(empresa_id), nom="Test Empresa", nif=boss_nif, subdomini="testragbot", pla_subscripcio="STARTER", estat_pagament="ACTIU"))
    await admin_session.flush()
    
    # Crear client"""
)

with open("backend/tests/test_telegram_rag.py", "w") as f:
    f.write(content)
