import re

path = "sevalor_AgentV2/docs/sdd/specs/000-high-level-definition.md"
with open(path, "r") as f:
    text = f.read()

target = """- **FR-009**: L'Agent IA MUST executar-se de manera local (Appliance Local 32GB/64GB) per garantir la sobirania absoluta de les dades del client."""
replace = """- **FR-009**: L'Agent IA MUST executar-se de manera local (Appliance Local 32GB/64GB) per garantir la sobirania absoluta de les dades del client.
- **FR-010**: El sistema MUST suportar "Alta Màgica OCR (Zero Data Entry)" com a política global. Totes les entitats principals (Vehicles, Treballadors, Albarans, Factures, Contractes) han de permetre la creació a partir de l'anàlisi automatitzat de fotografies o PDFs documentals."""

text = text.replace(target, replace)

with open(path, "w") as f:
    f.write(text)
print("Updated FR-010 in 000-high-level-definition")
