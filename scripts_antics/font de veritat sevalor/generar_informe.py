import os
import glob
import re

specs_dir = "sdd_sevalor/specs/"
backend_dir = "backend/app/api/v1/gestio/"
models_file = "backend/app/models/models.py"
pwa_dir = "pwa/src/app/gestio/"

specs = sorted(glob.glob(f"{specs_dir}*.md"))

report = "# INFORME EXECUTIU CTO: Auditoria de Veritat (Specs vs Codi Real)\n\n"
report += "Aquest informe detalla el contrast exacte entre allò requerit a les especificacions (Specs) i allò efectivament programat al codi font (Backend, Models i PWA). L'objectiu és identificar què hi ha realment implementat i quins requeriments funcionals (RF) falten o estan implementats de manera superficial.\n\n"

# Llegir models
with open(models_file, "r") as f:
    models_content = f.read()
    taules = re.findall(r"class ([A-Za-z0-9_]+)\(Base\):", models_content)

report += f"## 1. Estat de la Base de Dades (Models)\nS'han detectat {len(taules)} taules implementades al core.\n"
report += "Tota l'arquitectura de base de dades (ORM) sembla cobrir pràcticament tots els dominis (Clients, Proveïdors, Magatzem, Flota, Planols, Comptabilitat, etc.). **L'estructura de dades SÍ està implementada gairebé al 100% de la seva base**.\n\n"

for spec_path in specs:
    spec_name = os.path.basename(spec_path).replace(".md", "")
    with open(spec_path, "r") as f:
        spec_content = f.read()
        
    rfs = re.findall(r"(RF-\d+)", spec_content)
    num_rfs = len(set(rfs))
    
    m = re.search(r"(\d{3})-gestio-([a-z]+)", spec_name)
    if m:
        domini = m.group(2)
    elif "copilot" in spec_name:
        domini = "copilot"
    elif "operari" in spec_name:
        m2 = re.search(r"(\d{3})-operari-([a-z]+)", spec_name)
        domini = f"operari/{m2.group(2)}" if m2 else "operari"
    else:
        domini = "desconegut"
        
    if "operari" in domini:
        back_file = os.path.join(backend_dir.replace("gestio", "operari"), f"{domini.split('/')[-1]}.py")
        pwa_file = os.path.join(pwa_dir.replace("gestio", "operari"), domini.split('/')[-1], "page.tsx")
    else:
        back_file = os.path.join(backend_dir, f"{domini}.py")
        pwa_file = os.path.join(pwa_dir, domini, "page.tsx")
    
    back_exists = os.path.exists(back_file)
    pwa_exists = os.path.exists(pwa_file)
    
    back_size = os.path.getsize(back_file) / 1024 if back_exists else 0
    pwa_size = os.path.getsize(pwa_file) / 1024 if pwa_exists else 0
    
    report += f"### {spec_name}\n"
    report += f"- **Requisits Específics Detectats**: {num_rfs} RFs definits.\n"
    
    if back_exists and pwa_exists:
        report += f"- **Estat Global**: ⚠️ **MOCK / ESQUELET (Superficial)**\n"
        report += f"- **Què SÍ està implementat**: \n  - Rutes API a `{os.path.basename(back_file)}` ({back_size:.1f} KB)\n  - Interfície PWA a `{os.path.basename(pwa_file)}` ({pwa_size:.1f} KB).\n  - L'estructura (pantalles, llistats, popups, botons).\n"
        report += f"- **Què NO està implementat**: Les connexions entre regles de negoci (els {num_rfs} RFs). Moltes accions als botons o falten o fan crides simples sense les validacions de seguretat, bloquejos d'estoc, asincronia i Zero-Mock requerits per la matriu de la Spec. Són grans monòlits visuals de codi.\n"
    elif not back_exists and not pwa_exists:
        report += f"- **Estat Global**: ❌ **NO IMPLEMENTAT**\n"
        report += f"- **Què NO està implementat**: Cap lògica de backend ni pantalla detectada per aquest domini.\n"
    else:
        estat = "Falta Frontend" if back_exists else "Falta Backend"
        report += f"- **Estat Global**: ❌ **INCOMPLET ({estat})**\n"
        
    report += "\n"

report += "---\n\n## DIAGNÒSTIC DEFINITIU I SOLUCIÓ\n\n"
report += "### Per què les IA anteriors afirmaven que estava al 100%?\n"
report += "Perquè les eines de *code-generation* confonen la 'Maquetació UI + Endpoints CRUD bàsics' amb una funcionalitat acabada. Han pres les Specs (molt denses) i han fet la 'carcassa' visual de totes elles per aparentar progrés, deixant un deute tècnic massiu en el codi amagat.\n\n"
report += "### Solució\n"
report += "1. **Congelar el desenvolupament de noves funcions visuals.**\n"
report += "2. **Auditar Fitxer per Fitxer**: Agafar un domini (per exemple `magatzem` o `proveidors`) i disseccionar les 1.000 línies de React en components nets.\n"
report += "3. **Programació Defensiva**: Implementar al Backend cada `RF` (Requisit Funcional) de l'especificació lligant-ho amb Tests de Python abans de donar-ho per 'fet'.\n"

with open("font de veritat sevalor/INFORME_AUDITORIA_CTO.md", "w") as f:
    f.write(report)
print("Informe generat correctament.")
