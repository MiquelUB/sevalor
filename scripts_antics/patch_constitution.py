with open("sdd_sevalor/constitution.md", "r") as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if "Si el código contradice la especificación aprobada, la especificación prevalece." in line:
        lines.insert(i+1, "**Regla Estricta de IA:** Queda terminantemente prohibido tocar el código fuente sin actualizar primero la Spec correspondiente y mostrar un `diff` de los cambios para la aprobación del CTO.\n")
        break

with open("sdd_sevalor/constitution.md", "w") as f:
    f.writelines(lines)
