path = "/media/akaun/Project_1/SEVALOR/pwa/src/lib/api.ts"
with open(path, "r") as f:
    text = f.read()

target = """export function extractTenantId(): string | null {
  if (typeof window === "undefined") return null;
  const host = window.location.hostname;
  const parts = host.split(".");

  // Patró: tenant.localhost:3000 → tenant
  if (parts.length >= 3 && parts[0] !== "www" && parts[0] !== "api" && parts[0] !== "app") {
    return parts[0];
  }

  // Si no es pot extreure, intentar llegir de localStorage
  return localStorage.getItem("sevalor_tenant_id");
}"""

replacement = """export function extractTenantId(): string | null {
  if (typeof window === "undefined") return null;
  
  // En aquesta fase, la API backend espera estrictament un UUID vàlid a la capçalera X-Empresa-ID.
  // Els subdominis com 'tenant' no serveixen per a X-Empresa-ID directament (llevat que hi hagi un endpoint de resolució).
  // Per tant, només lliurem l'ID si tenim l'UUID explícit desat.
  
  const saved = localStorage.getItem("sevalor_tenant_id");
  if (saved) return saved;
  
  return null;
}"""

if target in text:
    text = text.replace(target, replacement)
    print("api.ts fixed")
else:
    print("target not found in api.ts")

with open(path, "w") as f:
    f.write(text)
