with open("backend/app/api/v1/gestio/magatzem.py", "r") as f:
    lines = f.readlines()
out = []
imports = []
for line in lines:
    if line.startswith("import ") or line.startswith("from "):
        imports.append(line)
    else:
        out.append(line)
        
final = imports + out
with open("backend/app/api/v1/gestio/magatzem.py", "w") as f:
    f.writelines(final)
