with open("sdd_sevalor/specs/013-operari-feines.md", "r") as f:
    content = f.read()

# Adding a clear Technical Detail block at the end
new_block = """
--------------------------------------------------------------------------------
Detalls Tècnics - Dexie.js (IndexedDB)
- S'ha de configurar una taula `fichajes` a la instància de Dexie `SevalorLocalDatabase` (v1) per emmagatzemar esborranys de fitxatges laborals (Drafts) en mode offline (RF-01 / RF-02). Això assegura que si l'operari inicia la jornada sense cobertura, la PWA guardi el registre fins que hi hagi xarxa.
"""
content += new_block

with open("sdd_sevalor/specs/013-operari-feines.md", "w") as f:
    f.write(content)
