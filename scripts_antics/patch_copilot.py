with open("backend/app/api/v1/gestio/copilot.py", "r") as f:
    content = f.read()

# Replace the inner import with nothing, we don't need `from sqlalchemy import select` because it's imported at the top (or should be). Wait, I will just use `db.execute(sqlalchemy.select(...))`? No, I will just remove the import and rely on the global select if it exists, or add it globally.
import re
if "from sqlalchemy import select" in content:
    content = content.replace("from sqlalchemy import select", "")
    content = "from sqlalchemy import select\n" + content

with open("backend/app/api/v1/gestio/copilot.py", "w") as f:
    f.write(content)
