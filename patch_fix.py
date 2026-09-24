import re

with open("backend/app/api/v1/gestio/clients.py", "r") as f:
    content = f.read()

# Remove the local select import
content = content.replace("    from sqlalchemy import select, func", "    from sqlalchemy import func")

with open("backend/app/api/v1/gestio/clients.py", "w") as f:
    f.write(content)

print("Patch applied to clients.py to fix UnboundLocalError")
