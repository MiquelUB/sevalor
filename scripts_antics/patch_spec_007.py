with open("sdd_sevalor/specs/007-gestio-comptabilitat.md", "r") as f:
    content = f.read()

new_detail = """
--------------------------------------------------------------------------------
Detalls Tècnics - Hash Encadenat (Veri*factu - Tasca 5.1)
- L'entitat `FacturaClient` (o equivalent que representi la factura emesa) ha d'incorporar un camp `hash_cadena` (String, nullable per a factures antigues).
- La generació d'una nova factura computarà un Hash SHA-256 combinant l'ID, el número de factura, l'import total i el `hash_cadena` de l'immediatament anterior factura emesa per aquella empresa. Si és la primera, la cadena prèvia serà un valor nul o string buit.
- Això garanteix la immutabilitat estructural (Constitució Punt 5) imposada per la nova normativa espanyola.
"""

content = content + new_detail + "\n"

with open("sdd_sevalor/specs/007-gestio-comptabilitat.md", "w") as f:
    f.write(content)
