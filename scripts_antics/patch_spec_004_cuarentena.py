with open("sdd_sevalor/specs/004-gestio-magatzem.md", "r") as f:
    content = f.read()

old_rf = """        Incidències: Camp de text lliure i foto per registrar mermes de materials danyats o eines trencades."""
new_rf = """        Incidències: Camp de text lliure i foto per registrar mermes de materials danyats o eines trencades.
        - **Detall Tècnic de Cuarentena (Pick-out):** Qualsevol `quantitat_mermada` reportada al confirmar la devolució (Pick-out) es descomptarà de l'estoc net disponible i s'inserirà en un registre de Base de Dades amb estat de `CUARENTENA`, bloquejant totalment el seu ús futur en noves ordres de treball."""

content = content.replace(old_rf, new_rf)

with open("sdd_sevalor/specs/004-gestio-magatzem.md", "w") as f:
    f.write(content)
