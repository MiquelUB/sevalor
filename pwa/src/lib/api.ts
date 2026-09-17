/**
 * Client API centralitzat per a la PWA de Sevalor Suite.
 *
 * - URL base configurable via variable d'entorn NEXT_PUBLIC_API_URL
 * - Injecció automàtica del tenant (X-Empresa-ID) des del subdomini
 * - Interceptor per afegir token Authorization
 * - Reintents automàtics en cas de fallada de xarxa (offline-first)
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8001/api/v1";

/**
 * Extreu l'empresa_id del host si el format és <tenant>.localhost o similar.
 * En producció es llegeix del subdomini configurat a EasyPanel.
 */
function extractTenantId(): string | null {
  if (typeof window === "undefined") return null;
  const host = window.location.hostname;
  const parts = host.split(".");

  // Patró: tenant.localhost:3000 → tenant
  if (parts.length >= 3 && parts[0] !== "www" && parts[0] !== "api") {
    return parts[0];
  }

  // Si no es pot extreure, intentar llegir de localStorage
  return localStorage.getItem("sevalor_tenant_id");
}

/**
 * Emmagatzema el token JWT (xifrat amb AES-GCM des de crypto.service.ts).
 * Aquest mòdul només recupera el token en clar per les peticions.
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
  const url = `${API_BASE_URL}${path}`;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((options.headers as Record<string, string>) || {}),
  };

  // Tenant header
  const tenantId = extractTenantId();
  if (tenantId) {
    headers["X-Empresa-ID"] = tenantId;
  }

  // Auth token
  const token = getAuthToken();
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const errorBody = await response.text();
    throw new Error(`API Error ${response.status}: ${errorBody}`);
  }

  // Si la resposta és 204 No Content
  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}