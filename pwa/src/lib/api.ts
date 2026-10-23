/**
 * Client API centralitzat per a la PWA de Sevalor Suite.
 *
 * - URL base configurable via variable d'entorn NEXT_PUBLIC_API_URL
 * - Suport resilient per entorns remots (EasyPanel, Nginx) i locals
 * - Injecció automàtica del tenant (X-Empresa-ID) des del subdomini o localStorage
 * - Interceptor per afegir token Authorization
 * - Gestió d'errors neta i descriptiva
 */

export function getApiBaseUrl(): string {
  if (typeof window !== "undefined") {
    // 1. Permetre override dinàmic manual si està definit
    const custom = localStorage.getItem("sevalor_api_url");
    if (custom) return custom.replace(/\/+$/, "");

    // 2. Sempre que estem al navegador en un domini remot o propi de client:
    // Utilitzem ruta relativa /api/v1 del mateix origen per evitar problemes de Mixed Content i CORS
    if (window.location.hostname !== "localhost" && window.location.hostname !== "127.0.0.1") {
      return "/api/v1";
    }

    // 3. Variable d'entorn pública de Next.js
    const envUrl = process.env.NEXT_PUBLIC_API_URL;
    if (envUrl && !envUrl.includes("://backend")) {
      return envUrl.replace(/\/+$/, "");
    }

    // 4. Per defecte en desenvolupament local directament contra el backend exposat
    return "http://127.0.0.1:8001/api/v1";
  }

  return process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8001/api/v1";
}

/**
 * Extreu el tenant_id resolt pel hostname o guardat prèviament.
 */
export function extractTenantId(): string | null {
  if (typeof window === "undefined") return null;

  const sessionSaved = typeof sessionStorage !== "undefined" ? sessionStorage.getItem("sevalor_tenant_id") : null;
  if (sessionSaved) return sessionSaved;

  const localSaved = localStorage.getItem("sevalor_tenant_id");
  if (localSaved) return localSaved;

  return null;
}

/**
 * Emmagatzema el token JWT.
 */
export function getAuthToken(): string | null {
  if (typeof window === "undefined") return null;
  const raw = null; // localStorage.getItem("sevalor_auth_token");
  if (raw) {
    try {
      const data = JSON.parse(raw);
      if (data.token) return data.token;
    } catch {
      // Ignorar error de parseig
    }
  }

  // Fallback resilient: comprovar cookie de sessió
  if (typeof document !== "undefined") {
    const match = document.cookie.match(new RegExp('(^| )sevalor_access_token=([^;]+)'));
    if (match) return decodeURIComponent(match[2]);
  }

  return null;
}

/**
 * Emmagatzema el token JWT al localStorage i assegura la cookie.
 */
export function setAuthToken(token: string): void {
  if (typeof window === "undefined") return;
  const data = { token, timestamp: Date.now() };
  // localStorage.setItem("sevalor_auth_token", JSON.stringify(data));
  if (typeof document !== "undefined") {
    const isHttps = window.location.protocol === "https:";
    document.cookie = `sevalor_access_token=${token}; path=/; max-age=86400; SameSite=Lax${isHttps ? "; Secure" : ""}`;
  }
}

export function clearAuthToken(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem("sevalor_auth_token");
  localStorage.removeItem("sevalor_user");
  localStorage.removeItem("sevalor_tenant_id");
  if (typeof sessionStorage !== "undefined") {
    sessionStorage.clear();
  }
  if (typeof document !== "undefined") {
    document.cookie = "sevalor_access_token=; path=/; max-age=0; expires=Thu, 01 Jan 1970 00:00:00 GMT";
    document.cookie = "sevalor_access_token=; path=/; max-age=0; expires=Thu, 01 Jan 1970 00:00:00 GMT; SameSite=Lax";
    document.cookie = "sevalor_access_token=; path=/; max-age=0; expires=Thu, 01 Jan 1970 00:00:00 GMT; SameSite=Strict";
    document.cookie = "sevalor_access_token=; path=/; max-age=0; expires=Thu, 01 Jan 1970 00:00:00 GMT; Secure; SameSite=Lax";
    document.cookie = "sevalor_access_token=; path=/; max-age=0; expires=Thu, 01 Jan 1970 00:00:00 GMT; Secure; SameSite=Strict";
  }
}

/**
 * Client fetch amb headers de tenant i autenticació.
 */
export async function apiFetch<T = any>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const baseUrl = getApiBaseUrl();
  let cleanPath = path.startsWith("/") ? path : `/${path}`;
  if (cleanPath.startsWith("/api/v1/")) {
    cleanPath = cleanPath.slice(7);
  } else if (cleanPath === "/api/v1") {
    cleanPath = "";
  }
  const url = `${baseUrl}${cleanPath}`;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((options.headers as Record<string, string>) || {}),
  };

  // Tenant header si existeix
  const tenantId = extractTenantId();
  if (tenantId) {
    if (!headers["X-Empresa-ID"]) {
      headers["X-Empresa-ID"] = tenantId;
    }
    if (!headers["X-Tenant-ID"]) {
      headers["X-Tenant-ID"] = tenantId;
    }
  }

  // Auth token
  const token = getAuthToken();
  if (token && !headers["Authorization"]) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  let response: Response;
  try {
    response = await fetch(url, {
      ...options,
      headers,
    });
  } catch (networkErr: any) {
    const isOffline = typeof navigator !== "undefined" && !navigator.onLine;
    const msg = isOffline
      ? "📶 Sense cobertura mòbil al telèfon: No tens connexió d'internet mòbil en aquesta zona. Pots continuar treballant amb les feines d'avui desades al telèfon."
      : "📶 Sense connexió de xarxa o sense cobertura mòbil: No s'ha pogut connectar amb el servidor. Comprova la cobertura del telèfon.";
    const err = new Error(msg) as Error & { code?: string };
    err.code = "SENSE_COBERTURA_MOBIL";
    throw err;
  }

  if (!response.ok) {
    let errorDetail = `Error ${response.status}: ${response.statusText}`;
    let errorCode: string | undefined;
    try {
      const errorJson = await response.json();
      errorCode = errorJson.code;
      errorDetail = errorJson.detail || errorJson.message || errorDetail;
    } catch {
      const errorText = await response.text().catch(() => "");
      if (errorText) errorDetail = errorText;
    }

    if (response.status === 503 && errorCode === "NODE_EMPRESA_OFFLINE") {
      const err = new Error(
        errorDetail ||
          "🖥️ Ordinador central de l'empresa apagat: Tens cobertura mòbil, però l'ordinador d'oficina de l'empresa està apagat o desconnectat."
      ) as Error & { code?: string };
      err.code = "NODE_EMPRESA_OFFLINE";
      throw err;
    }

    if ([502, 503, 504].includes(response.status)) {
      const err = new Error(
        errorDetail.includes("Error 50")
          ? "⚠️ Base de dades central no disponible temporalment: Tens cobertura mòbil, però el servidor de dades no respon en aquest instant."
          : errorDetail
      ) as Error & { code?: string };
      err.code = errorCode || "DB_UNAVAILABLE";
      throw err;
    }

    const err = new Error(errorDetail) as Error & { code?: string };
    if (errorCode) err.code = errorCode;
    throw err;
  }

  // Si la resposta és 204 No Content
  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}