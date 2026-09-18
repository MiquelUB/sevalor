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

    // 2. Variable d'entorn pública de Next.js
    const envUrl = process.env.NEXT_PUBLIC_API_URL;
    if (envUrl) {
      const isLocalUrl = envUrl.includes("127.0.0.1") || envUrl.includes("localhost");
      const isLocalBrowser = window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1";
      // Si és una URL remota o estem en local, usem envUrl
      if (!isLocalUrl || isLocalBrowser) {
        return envUrl.replace(/\/+$/, "");
      }
    }

    // 3. Si estem al navegador en un domini remot (EasyPanel / VPS):
    // Utilitzem ruta relativa /api/v1 del mateix domini per evitar Mixed Content i CORS
    if (window.location.hostname !== "localhost" && window.location.hostname !== "127.0.0.1") {
      return `${window.location.origin}/api/v1`;
    }

    // 4. Per defecte en desenvolupament local
    return envUrl ? envUrl.replace(/\/+$/, "") : "http://127.0.0.1:8001/api/v1";
  }

  return process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8001/api/v1";
}

/**
 * Extreu l'empresa_id del host si el format és <tenant>.localhost o similar.
 * En producció es llegeix del subdomini configurat a EasyPanel.
 */
export function extractTenantId(): string | null {
  if (typeof window === "undefined") return null;
  const host = window.location.hostname;
  const parts = host.split(".");

  // Patró: tenant.localhost:3000 → tenant
  if (parts.length >= 3 && parts[0] !== "www" && parts[0] !== "api" && parts[0] !== "app") {
    return parts[0];
  }

  // Si no es pot extreure, intentar llegir de localStorage
  return localStorage.getItem("sevalor_tenant_id");
}

/**
 * Emmagatzema el token JWT.
 */
export function getAuthToken(): string | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem("sevalor_auth_token");
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
  localStorage.setItem("sevalor_auth_token", JSON.stringify(data));
  if (typeof document !== "undefined") {
    document.cookie = `sevalor_access_token=${token}; path=/; max-age=86400; SameSite=Strict`;
  }
}

export function clearAuthToken(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem("sevalor_auth_token");
  localStorage.removeItem("sevalor_user");
  if (typeof document !== "undefined") {
    document.cookie = "sevalor_access_token=; path=/; max-age=0; SameSite=Strict";
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
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const url = `${baseUrl}${normalizedPath}`;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((options.headers as Record<string, string>) || {}),
  };

  // Tenant header si existeix
  const tenantId = extractTenantId();
  if (tenantId && !headers["X-Empresa-ID"]) {
    headers["X-Empresa-ID"] = tenantId;
  }

  // Auth token
  const token = getAuthToken();
  if (token && !headers["Authorization"]) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let errorDetail = `Error ${response.status}: ${response.statusText}`;
    try {
      const errorJson = await response.json();
      errorDetail = errorJson.detail || errorJson.message || errorDetail;
    } catch {
      const errorText = await response.text().catch(() => "");
      if (errorText) errorDetail = errorText;
    }
    throw new Error(errorDetail);
  }

  // Si la resposta és 204 No Content
  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}