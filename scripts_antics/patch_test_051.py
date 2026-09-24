with open("backend/tests/test_051_factura_hash.py", "r") as f:
    content = f.read()

content = content.replace("rao_social='Client Test'", "codi='CLI-1', rao_social='Client Test'")

with open("backend/tests/test_051_factura_hash.py", "w") as f:
    f.write(content)
