/**
 * Client API centralitzat per a la PWA de Sevalor Suite.
 *
 * - URL base configurable via variable d'entorn NEXT_PUBLIC_API_URL
 * - Suport resilient per entorns remots (EasyPanel, Nginx) i locals
 * - Injecció automàtica del tenant (X-Empresa-ID) des del subdomini o localStorage
 * - Interceptor per afegir token Authorization
 * - Gestió d'errors neta i descriptiva
 */

export interface ApiStructuredError extends Error {
  status?: number;
  code?: string;
  motiu?: string;
  titol?: string;
  passos_solucio?: string[];
}

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

  const isFormData = typeof FormData !== "undefined" && options.body instanceof FormData;
  const headers: Record<string, string> = {
    ...(isFormData ? {} : { "Content-Type": "application/json" }),
    ...((options.headers as Record<string, string>) || {}),
  };
  if (isFormData && headers["Content-Type"]) {
    delete headers["Content-Type"];
  }

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
      credentials: options.credentials || "include",
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
    let errorMotiu: string | undefined;
    let errorTitol: string | undefined;
    let errorPassos: string[] | undefined;
    try {
      const errorJson = await response.json();
      const rawDetail = errorJson?.detail ?? errorJson?.message;
      if (typeof rawDetail === "string" && rawDetail.trim()) {
        errorDetail = rawDetail;
      } else if (Array.isArray(rawDetail)) {
        const msgs = rawDetail
          .map((item: any) =>
            typeof item === "string" ? item : item?.msg || item?.message || JSON.stringify(item)
          )
          .filter(Boolean);
        if (msgs.length > 0) errorDetail = msgs.join("; ");
      } else if (rawDetail && typeof rawDetail === "object") {
        if (typeof rawDetail.code === "string") {
          errorCode = rawDetail.code;
        }
        if (typeof rawDetail.motiu === "string") {
          errorMotiu = rawDetail.motiu;
        }
        if (typeof rawDetail.titol === "string") {
          errorTitol = rawDetail.titol;
        }
        if (Array.isArray(rawDetail.passos_solucio)) {
          errorPassos = rawDetail.passos_solucio
            .map((p: unknown) => String(p || "").trim())
            .filter(Boolean);
        }
        errorDetail =
          (typeof rawDetail.message === "string" && rawDetail.message) ||
          (typeof rawDetail.detail === "string" && rawDetail.detail) ||
          JSON.stringify(rawDetail);
      }
      if (typeof errorJson?.code === "string") {
        errorCode = errorJson.code;
      }
      if (typeof errorJson?.motiu === "string" && !errorMotiu) {
        errorMotiu = errorJson.motiu;
      }
    } catch {
      const errorText = await response.text().catch(() => "");
      if (errorText) errorDetail = errorText;
    }

    const attachMeta = (err: ApiStructuredError, fallbackCode?: string): ApiStructuredError => {
      err.status = response.status;
      if (errorCode || fallbackCode) err.code = errorCode || fallbackCode;
      if (errorMotiu) err.motiu = errorMotiu;
      if (errorTitol) err.titol = errorTitol;
      if (errorPassos && errorPassos.length > 0) err.passos_solucio = errorPassos;
      return err;
    };

    if (response.status === 503 && errorCode === "NODE_EMPRESA_OFFLINE") {
      throw attachMeta(
        new Error(
          errorDetail ||
            "Ordinador central de l'empresa apagat: Tens cobertura mòbil, però l'ordinador d'oficina de l'empresa està apagat o desconnectat."
        ) as ApiStructuredError,
        "NODE_EMPRESA_OFFLINE"
      );
    }

    if ([502, 503, 504].includes(response.status)) {
      const safeDetail = typeof errorDetail === "string" ? errorDetail : String(errorDetail || "");
      throw attachMeta(
        new Error(
          safeDetail.includes("Error 50")
            ? "Base de dades central no disponible temporalment: Tens cobertura mòbil, però el servidor de dades no respon en aquest instant."
            : safeDetail
        ) as ApiStructuredError,
        "DB_UNAVAILABLE"
      );
    }

    throw attachMeta(new Error(errorDetail) as ApiStructuredError);
  }

  // Si la resposta és 204 No Content
  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}