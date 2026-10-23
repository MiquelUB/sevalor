"use client";

import React, { createContext, useContext, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

export interface ChameleonBrand {
  tenant_id?: string;
  primari_hsl: string;   // "210 100% 15%"
  secundari_hsl: string; // "38 92% 50%"
  accent_hsl: string;    // "190 90% 50%"
  logotip_path?: string;
  empresa_nom?: string;
}

interface ChameleonContextValue {
  brand: ChameleonBrand | null;
  tenantId: string | null;
  loading: boolean;
  error: string | null;
}

const ChameleonContext = createContext<ChameleonContextValue>({
  brand: null,
  tenantId: null,
  loading: true,
  error: null,
});

export function useChameleon() {
  return useContext(ChameleonContext);
}

/**
 * Injecta variables CSS HSL al :root del document en temps real.
 */
function applyChameleonCSS(brand: ChameleonBrand) {
  if (typeof document === "undefined") return;
  const root = document.documentElement;

  // Aplicar colors primari, secundari i accent
  if (brand.primari_hsl) {
    root.style.setProperty("--color-primary", brand.primari_hsl);
    root.style.setProperty("--chameleon-primary", brand.primari_hsl);
    root.style.setProperty("--color-primary-foreground", "0 0% 100%");
  }
  if (brand.secundari_hsl) {
    root.style.setProperty("--color-secondary", brand.secundari_hsl);
    root.style.setProperty("--chameleon-secondary", brand.secundari_hsl);
    root.style.setProperty("--color-secondary-foreground", "0 0% 100%");
  }
  if (brand.accent_hsl) {
    root.style.setProperty("--color-accent", brand.accent_hsl);
    root.style.setProperty("--chameleon-accent", brand.accent_hsl);
    root.style.setProperty("--color-secondary-container", brand.accent_hsl);
    root.style.setProperty("--color-accent-foreground", "0 0% 100%");
  }
}

/**
 * Carrega la configuració de marca de l'empresa des del backend.
 */
export function ChameleonProvider({ children }: { children: React.ReactNode }) {
  const [brand, setBrand] = useState<ChameleonBrand | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Si estem a la secció superadmin o el token és de Superadmin, no cal marca camaleònica de tenant
    if (typeof window !== "undefined") {
      if (window.location.pathname.startsWith("/superadmin")) {
        setLoading(false);
        return;
      }
      try {
        const tokenRaw = localStorage.getItem("sevalor_auth_token");
        if (tokenRaw) {
          const parsed = JSON.parse(tokenRaw);
          const jwtToken = parsed?.token;
          if (jwtToken && typeof jwtToken === "string") {
            const parts = jwtToken.split(".");
            if (parts.length === 3) {
              const payload = JSON.parse(atob(parts[1]));
              if (payload?.is_superadmin || payload?.rol === "SUPERADMIN") {
                setLoading(false);
                return;
              }
            }
          }
        }
      } catch {
        // Ignorar errors de parsing de token
      }
    }

    const loadBrand = async () => {
      const hostname = typeof window !== "undefined" ? window.location.hostname : "";
      try {
        // 1. Intentar endpoint públic per domini/host (funciona abans i després de login)
        const endpoint = hostname
          ? `/public/tenant-config?domain=${encodeURIComponent(hostname)}`
          : "/public/tenant/resolve";
        const publicTenant = await apiFetch<any>(endpoint);
        if (publicTenant && (publicTenant.id || publicTenant.tenant_id)) {
          const tenantId = String(publicTenant.tenant_id || publicTenant.id);
          const brandData: ChameleonBrand = {
            tenant_id: tenantId,
            primari_hsl: publicTenant.color_primari || publicTenant.primari_hsl || "152 60% 25%",
            secundari_hsl: publicTenant.color_secundari || publicTenant.secundari_hsl || "152 45% 15%",
            accent_hsl: publicTenant.color_accent || publicTenant.accent_hsl || "38 92% 50%",
            logotip_path: publicTenant.logotip_url || publicTenant.logotip_path,
            empresa_nom: publicTenant.nom_comercial || publicTenant.rao_social || publicTenant.nom,
          };

          if (typeof sessionStorage !== "undefined") {
            sessionStorage.setItem("sevalor_tenant_id", tenantId);
            if (brandData.empresa_nom) {
              sessionStorage.setItem("sevalor_tenant_nom", brandData.empresa_nom);
            }
            if (brandData.logotip_path) {
              sessionStorage.setItem("sevalor_tenant_logo", brandData.logotip_path);
            }
          }

          setBrand(brandData);
          applyChameleonCSS(brandData);
          setLoading(false);
          return;
        }
      } catch {
        // Fallback per a entorns locals o sense resolució per host
      }

      // 2. Si no ha resolt pel host, provar endpoint de gestió de marca
      try {
        const data = await apiFetch<ChameleonBrand>("/gestio/configuracio/marca");
        if (data) {
          setBrand(data);
          applyChameleonCSS(data);
        }
      } catch (err: any) {
        if (!err?.message?.includes("401") && !err?.message?.includes("403") && !err?.message?.includes("404")) {
          console.warn("[Chameleon] No s'ha pogut carregar la marca:", err.message);
        }
        setError("Marca no disponible");
      } finally {
        setLoading(false);
      }
    };

    loadBrand();
  }, []);

  return (
    <ChameleonContext.Provider value={{ brand, tenantId: brand?.tenant_id || null, loading, error }}>
      {children}
    </ChameleonContext.Provider>
  );
}