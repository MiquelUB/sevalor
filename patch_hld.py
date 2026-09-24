import re

with open("sevalor_AgentV2/docs/sdd/specs/000-high-level-definition.md", "r") as f:
    content = f.read()

content = content.replace("**Status**: Draft", "**Status**: IMPLEMENTED (V2 SPRINT DONE)")

content = content.replace('''### User Story 4 - Agent IA Operatiu (Tools & Live Data) (Priority: P0)

Com a gestor, vull que el Copilot IA no sigui només un chatbot, sinó un "Agent" que tingui accés a eines (Tools/Funcions) per consultar dades en temps real (API/SQL) sobre agenda, operaris, stock i economia. Vull que l'agent pugui creuar dades, raonar i executar accions (prèvia confirmació).''',
'''### User Story 4 - Agent IA Operatiu (Tools & Live Data) (Priority: P0) - 🟢 IMPLEMENTAT

Com a gestor, vull que el Copilot IA no sigui només un chatbot, sinó un "Agent" que tingui accés a eines (Tools/Funcions) per consultar dades en temps real (API/SQL) sobre agenda, operaris, stock i economia. Vull que l'agent pugui creuar dades, raonar i executar accions (prèvia confirmació).''')

content = content.replace('''### User Story 5 - IA Multimodal (Priority: P1)

Com a operari al camp, vull poder fer una fotografia a la placa de característiques d'una màquina (chiller, UTA) perquè l'IA multimodal n'identifiqui el model exacte i m'ofereixi automàticament els manuals o protocols de manteniment relacionats des del RAG documental.''',
'''### User Story 5 - IA Multimodal (Priority: P1) - 🟢 IMPLEMENTAT

Com a operari al camp, vull poder fer una fotografia a la placa de característiques d'una màquina (chiller, UTA) perquè l'IA multimodal n'identifiqui el model exacte i m'ofereixi automàticament els manuals o protocols de manteniment relacionats des del RAG documental.''')

with open("sevalor_AgentV2/docs/sdd/specs/000-high-level-definition.md", "w") as f:
    f.write(content)

print("Patch applied to HLD")
