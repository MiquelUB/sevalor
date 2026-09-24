with open("backend/tests/test_033_backorder_ai.py", "r") as f:
    content = f.read()

content = content.replace("preu_unitari=2.5, descripcio='Test', subtotal=250.0", "preu_unitari=2.5")

with open("backend/tests/test_033_backorder_ai.py", "w") as f:
    f.write(content)
