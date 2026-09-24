import re

with open("pwa/src/app/gestio/layout.tsx", "r") as f:
    content = f.read()

# 1. Change Torre de Control GIS link
content = content.replace(
    '{ label: "Torre de Control GIS", href: "/gestio/mapa", icon: Compass, badge: "GIS" },',
    '{ label: "Torre de Control GIS", href: "/gestio", icon: Compass, badge: "GIS" },'
)

# 2. Remove the Veto d'Enginyer role selector from the header
veto_block = """          {/* Veto d'Enginyer (Simulador de Rols per Testing) */}
          <div className="flex items-center gap-1.5 px-2 py-1 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg">
            <Shield className="w-3.5 h-3.5 text-amber-600 dark:text-amber-500" />
            <select
              value={rolActiu}
              onChange={(e) => setRolActiu(e.target.value as RolGestio)}
              className="bg-transparent text-xs font-bold text-amber-700 dark:text-amber-400 outline-none cursor-pointer"
            >
              <option value="BOSS">Rol: Administrador (SaaS)</option>
              <option value="ENGINYER">Rol: Enginyer (Veto Financer)</option>
            </select>
          </div>"""
content = content.replace(veto_block, "")

# 3. Remove the problematic /auth/me client-side redirect that logs the user out randomly
auth_check_block = """    apiFetch("/auth/me")
      .then((data: any) => {
        if (!data || data.error) throw new Error();
      })
      .catch(() => {
        handleLogout();
      });"""
content = content.replace(auth_check_block, "// Client-side auth redirect deleted. Middleware.ts handles auth protection securely.")

with open("pwa/src/app/gestio/layout.tsx", "w") as f:
    f.write(content)

print("Issues fixed in layout.")
