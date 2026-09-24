with open("sdd_sevalor/specs/021-superadmin-onboarding-tenants.md", "r") as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if "RF-07" in line and "habiliti les polítiques de Row Level Security" in line:
        insert_text = """        - **Detall Tècnic RLS (Base de Dades):** Tota taula core (`Client`, `Article`, `OrdreTreball`, `Vehicle`, etc.) tindrà activat `ALTER TABLE ... ENABLE ROW LEVEL SECURITY;`.
        - La política d'accés obligatòria serà: `CREATE POLICY tenant_isolation_policy ON <taula> USING (empresa_id = current_setting('app.current_empresa_id')::uuid)`.
        - El rol `sevalor_app` serà l'únic autoritzat a connectar-se per heretar aquestes polítiques.
"""
        lines.insert(i+1, insert_text)
        break

with open("sdd_sevalor/specs/021-superadmin-onboarding-tenants.md", "w") as f:
    f.writelines(lines)
