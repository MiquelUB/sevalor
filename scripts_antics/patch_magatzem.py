with open("backend/app/api/v1/gestio/magatzem.py", "r") as f:
    content = f.read()

old_logic = """        estoc.quantitat_fisica = float(estoc.quantitat_fisica) - quantitat_mermada"""
new_logic = """        estoc.quantitat_fisica = float(estoc.quantitat_fisica) - quantitat_mermada
        estoc.quantitat_cuarentena = float(estoc.quantitat_cuarentena) + quantitat_mermada"""

content = content.replace(old_logic, new_logic)

with open("backend/app/api/v1/gestio/magatzem.py", "w") as f:
    f.write(content)
