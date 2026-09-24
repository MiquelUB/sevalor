import os
import shutil

# Move constitution to rules
if os.path.exists("sdd_sevalor/constitution.md"):
    shutil.move("sdd_sevalor/constitution.md", "sevalor_AgentV2/.antigravity/rules.md")

# Move AGENTS to architecture
if os.path.exists("sdd_sevalor/AGENTS.md"):
    shutil.move("sdd_sevalor/AGENTS.md", "sevalor_AgentV2/docs/sdd/architecture.md")

# Move plans
if os.path.exists("sdd_sevalor/plan-v2.md"):
    shutil.move("sdd_sevalor/plan-v2.md", "sevalor_AgentV2/.antigravity/memory/plans/plan-v2.md")
if os.path.exists("sdd_sevalor/tareas-implementacio-sevalor.md"):
    shutil.move("sdd_sevalor/tareas-implementacio-sevalor.md", "sevalor_AgentV2/.antigravity/memory/plans/tareas-implementacio-sevalor.md")

# Move specs folder
if os.path.exists("sdd_sevalor/specs"):
    shutil.move("sdd_sevalor/specs", "sevalor_AgentV2/docs/sdd/specs")
    # Touch tasks.md to act as an index
    with open("sevalor_AgentV2/docs/sdd/tasks.md", "w") as f:
        f.write("# Tasks & Requisits\nLes especificacions detallades estan a la carpeta `specs/`.\n")

# Move Historial_implementacion to memory/plans/historic
if os.path.exists("sdd_sevalor/HIstorial_implementacion"):
    shutil.move("sdd_sevalor/HIstorial_implementacion", "sevalor_AgentV2/.antigravity/memory/plans/Historial_implementacion")

# Move error/audit reports to errors.md
if os.path.exists("sdd_sevalor/informe_auditoria_sevalor.md"):
    with open("sdd_sevalor/informe_auditoria_sevalor.md", "r") as src, open("sevalor_AgentV2/.antigravity/memory/errors.md", "w") as dst:
        dst.write(src.read())

# Move anything from Docs_SEVALOR to a general docs folder or sort them
if os.path.exists("Docs_SEVALOR"):
    shutil.move("Docs_SEVALOR", "sevalor_AgentV2/docs/Docs_SEVALOR_legacy")

# Clean up remaining sdd_sevalor
if os.path.exists("sdd_sevalor"):
    shutil.move("sdd_sevalor", "sevalor_AgentV2/docs/sdd_sevalor_legacy")

print("Done")
