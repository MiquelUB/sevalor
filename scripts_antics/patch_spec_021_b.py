with open("sdd_sevalor/specs/021-superadmin-onboarding-tenants.md", "r") as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if "El rol `sevalor_app` serà l'únic autoritzat a connectar-se per heretar aquestes polítiques." in line:
        insert_text = """    RF-07.1 (System Constraint) — Prohibició de Filtratge Manual a l'Aplicació: A causa de l'activació del RLS, QUEDA TERMINANTMENT PROHIBIT incloure clàusules manuals `WHERE empresa_id = X` o similars en les consultes SQLAlchemy de l'API (repositoris de magatzem, proveïdors, clients...). Tot l'aïllament multi-tenant es delegarà exclusivament al motor PostgreSQL.
"""
        lines.insert(i+1, insert_text)
        break

with open("sdd_sevalor/specs/021-superadmin-onboarding-tenants.md", "w") as f:
    f.writelines(lines)
