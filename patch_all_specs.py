import glob

policy = """
> [!IMPORTANT]
> **Política Global: Alta Màgica OCR (Zero Data Entry)**
> Tot el sistema implementa la funcionalitat d'Alta Màgica OCR, permetent l'alta d'entitats (Vehicles, Treballadors, Albarans, Factures, Contractes, Clients, Proveïdors) mitjançant l'anàlisi automatitzat de fotografies o PDFs, sense necessitat de picar les dades manualment.
"""

for filepath in glob.glob("sevalor_AgentV2/docs/sdd/specs/0*.md"):
    with open(filepath, "r") as f:
        content = f.read()
        
    if "Alta Màgica OCR" in content:
        continue
        
    # Inserir just abans de la primera secció de Requisits
    if "Requisits Funcionals" in content:
        content = content.replace("Requisits Funcionals", policy + "\nRequisits Funcionals")
    elif "Requisitos Funcionales" in content:
        content = content.replace("Requisitos Funcionales", policy + "\nRequisitos Funcionales")
    else:
        content += "\n" + policy
        
    with open(filepath, "w") as f:
        f.write(content)
    print(f"Patched {filepath}")

