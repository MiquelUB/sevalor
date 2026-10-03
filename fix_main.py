import re

with open("backend/app/main.py", "r") as f:
    lines = f.readlines()

imports = []
code = []

for line in lines:
    if line.startswith("import ") or line.startswith("from "):
        imports.append(line)
    else:
        code.append(line)

out = []
for i in imports:
    out.append(i)
for c in code:
    out.append(c)

with open("backend/app/main.py", "w") as f:
    f.writelines(out)
