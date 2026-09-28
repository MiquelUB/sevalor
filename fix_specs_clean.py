import re
import glob

def clean_and_inject(filepath, rf00_title, rf00_what, rf00_why):
    with open(filepath, "r") as f:
        content = f.read()

    # 1. Remove the misplaced global policy block if it exists
    global_policy = "> [!IMPORTANT]\n> **Política Global: Alta Màgica OCR (Zero Data Entry)**\n> Tot el sistema implementa la funcionalitat d'Alta Màgica OCR, permetent l'alta d'entitats (Vehicles, Treballadors, Albarans, Factures, Contractes, Clients, Proveïdors) mitjançant l'anàlisi automatitzat de fotografies o PDFs, sense necessitat de picar les dades manualment.\n"
    
    content = content.replace(global_policy, "")
    content = content.replace("Els 29 \nRequisits Funcionals", "Els 29 Requisits Funcionals")

    # 2. Re-inject the global policy cleanly at the top (after the header)
    if "Context i Objectiu" in content:
        content = content.replace("Context i Objectiu", global_policy + "\nContext i Objectiu")
    elif "Contexto y Objetivo" in content:
        content = content.replace("Contexto y Objetivo", global_policy + "\nContexto y Objetivo")
    elif "Contexto i Objectiu" in content:
        content = content.replace("Contexto i Objectiu", global_policy + "\nContexto i Objectiu")
    else:
        # Just put it at the very top under the main header
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if line.startswith('# '):
                lines.insert(i + 1, "\n" + global_policy)
                break
        content = "\n".join(lines)

    # 3. Add the specific RF-00 if requested
    if rf00_title and "RF-00" not in content:
        rf_text = f"""
### Requisits Funcionals (RF)

#### RF-00: {rf00_title}
- **QUÈ**: {rf00_what}
- **PER QUÈ**: {rf00_why}
- **COM**: Mitjançant el processament asíncron d'imatges i PDFs via motor d'IA local (Vision LLM / OCR), injectant les dades pre-omplertes a la PWA.
"""
        # Try to find "Requisits Funcionals" or "Requisitos Funcionales" and replace the FIRST occurrence
        if "### Requisits Funcionals" in content:
            content = content.replace("### Requisits Funcionals", rf_text, 1)
        elif "### Requisitos Funcionales" in content:
            content = content.replace("### Requisitos Funcionales", rf_text, 1)
        elif "Requisits Funcionals (RF" in content:
            pass # already there
            
    with open(filepath, "w") as f:
        f.write(content)
    print(f"Cleaned and patched {filepath}")

# Process them
clean_and_inject("sevalor_AgentV2/docs/sdd/specs/002-gestio-clients.md", 
    "Alta Màgica de Client via OCR", 
    "El sistema permetrà donar d'alta un client carregant un document oficial (com un rebut, una factura o el CIF/NIF).",
    "Per complir l'estàndard 'Zero Data Entry' de l'arquitectura, agilitzant l'onboarding.")

clean_and_inject("sevalor_AgentV2/docs/sdd/specs/003-gestio-proveidors.md", 
    "Alta Màgica de Proveïdor via OCR",
    "Alta automatitzada de proveïdors a partir de targetes CIF o factures proforma.",
    "Per evitar l'entrada manual repetitiva d'IBANs, NIFs i dades de contacte del proveïdor.")

clean_and_inject("sevalor_AgentV2/docs/sdd/specs/007-gestio-comptabilitat.md", 
    "Entrada Automàtica de Tiquets i Despeses via OCR",
    "L'usuari pujarà una foto d'un tiquet o factura i el sistema extreurà imports, base, IVA, CIF i el classificarà comptablement.",
    "Elimina la necessitat de picar factures a final de mes.")

clean_and_inject("sevalor_AgentV2/docs/sdd/specs/008-gestio-operaris.md", 
    "Alta Automàtica d'Operari via DNI/NIE",
    "L'alta d'un treballador es fa fotografiant l'anvers i revers del document d'identitat.",
    "Estalvia temps i assegura una transcripció sense errades per a l'alta d'usuaris a la base de dades.")

# Also clean the other specs just to fix the misplaced global policy
for filepath in glob.glob("sevalor_AgentV2/docs/sdd/specs/0*.md"):
    if filepath not in [
        "sevalor_AgentV2/docs/sdd/specs/002-gestio-clients.md",
        "sevalor_AgentV2/docs/sdd/specs/003-gestio-proveidors.md",
        "sevalor_AgentV2/docs/sdd/specs/007-gestio-comptabilitat.md",
        "sevalor_AgentV2/docs/sdd/specs/008-gestio-operaris.md"
    ]:
        clean_and_inject(filepath, None, None, None)

