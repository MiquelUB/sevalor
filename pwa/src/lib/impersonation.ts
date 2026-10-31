/**
 * Flux d'impersonació Superadmin → empresa.
 *
 * - Si l'empresa té domini propi, el backend retorna `handoff_url` amb un codi d'un sol ús
 *   (60 s). Naveguem cap allà sense tocar la sessió Superadmin del host d'administració.
 * - Si no, es manté el flux al mateix host: es desa el token d'impersonació i s'obre /gestio.
 */
import { apiFetch, getAuthToken, setAuthToken } from "@/lib/api";

export const IMPERSONATION_RETURN_KEY = "sevalor_impersonation_return";

interface ImpersonateResponse {
  access_token: string;
  empresa_id: string;
  handoff_url?: string | null;
}

export async function iniciarImpersonacio(
  tenantIdOrSlug: string,
  tenantNom: string,
  targetPath: string = "/gestio"
): Promise<void> {
  const data = await apiFetch<ImpersonateResponse>(
    `/superadmin/tenants/${encodeURIComponent(tenantIdOrSlug)}/impersonate`,
    { method: "POST" }
  );
  if (!data?.access_token) {
    throw new Error("El servidor no ha retornat cap sessió d'impersonació.");
  }

  // 1. Traspàs al domini propi de l'empresa (la sessió Superadmin queda intacta aquí)
  if (data.handoff_url && /^https:\/\/[^/]+\/impersonacio#code=/.test(data.handoff_url)) {
    window.location.href = data.handoff_url;
    return;
  }

  // 2. Fallback: mateix host d'administració
  const empresaId = data.empresa_id || tenantIdOrSlug;
  const currentToken = getAuthToken();
  if (currentToken) {
    localStorage.setItem("sevalor_superadmin_token", currentToken);
  }
  setAuthToken(data.access_token);
  localStorage.setItem(
    "sevalor_user",
    JSON.stringify({
      ...data,
      is_impersonation: true,
      empresa_id: empresaId,
      empresa_nom: tenantNom,
      rol: "SUPERADMIN",
    })
  );
  localStorage.setItem("sevalor_tenant_id", empresaId);
  if (typeof sessionStorage !== "undefined") {
    sessionStorage.setItem("sevalor_tenant_id", empresaId);
  }
  window.location.href = targetPath;
}
