"use client";

import React, { createContext, useContext, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

interface ChameleonBrand {
  primari_hsl: string;   // "210 100% 15%"
  secundari_hsl: string; // "38 92% 50%"
  accent_hsl: string;    // "190 90% 50%"
  logotip_path?: string;
  empresa_nom?: string;
}

interface ChameleonContextValue {
  brand: ChameleonBrand | null;
  loading: boolean;
  error: string | null;
}

const ChameleonContext = createContext<ChameleonContextValue>({
  brand: null,
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
  root.style.setProperty("--color-primary", brand.primari_hsl);
  root.style.setProperty("--color-primary-foreground", "0 0% 100%");
  root.style.setProperty("--color-secondary", brand.secundari_hsl);
  root.style.setProperty("--color-secondary-foreground", "0 0% 100%");
  root.style.setProperty("--color-accent", brand.accent_hsl);
  root.style.setProperty("--color-accent-foreground", "0 0% 100%");
}

/**
 * Carrega la configuració de marca de l'empresa des del backend.
 */
export function ChameleonProvider({ children }: { children: React.ReactNode }) {
  const [brand, setBrand] = useState<ChameleonBrand | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<ChameleonBrand>("/gestio/configuracio/marca")
      .then((data) => {
        setBrand(data);
        applyChameleonCSS(data);
      })
      .catch((err) => {
        console.warn("[Chameleon] No s'ha pogut carregar la marca de l'empresa:", err.message);
        setError("Marca no disponible");
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <ChameleonContext.Provider value={{ brand, loading, error }}>
      {children}
    </ChameleonContext.Provider>
  );
}