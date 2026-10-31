"use client";

import React, { useEffect, useRef, useState } from "react";
import { ShieldCheck, AlertTriangle } from "lucide-react";
import { clearAuthToken, setAuthToken } from "@/lib/api";
import { IMPERSONATION_RETURN_KEY } from "@/lib/impersonation";

interface IntercanviResponse {
  access_token: string;
  rol: string;
  empresa_id: string;
  empresa_nom: string;
  is_impersonation: boolean;
  return_url: string;
}

/**
 * Aterratge de la impersonació al domini propi de l'empresa.
 * Bescanvia el codi d'un sol ús (#code=...) per la sessió d'impersonació i obre /gestio.
 */
export default function ImpersonacioPage() {
  const [error, setError] = useState<string | null>(null);
  const executat = useRef(false);

  useEffect(() => {
    if (executat.current) return;
    executat.current = true;

    const hash = window.location.hash.replace(/^#/, "");
    const code = new URLSearchParams(hash).get("code") || "";
    // Eliminar el codi de la barra d'adreces i de l'historial immediatament
    window.history.replaceState(null, "", window.location.pathname);

    if (!code) {
      setError("Falta el codi d'impersonació. Torna-ho a iniciar des del panell Superadmin.");
      return;
    }

    const bescanviar = async () => {
      try {
        const res = await fetch("/api/v1/auth/impersonacio/intercanvi", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ code }),
          credentials: "same-origin",
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.detail || "No s'ha pogut validar la sessió d'impersonació.");
        }
        const data: IntercanviResponse = await res.json();

        // Partir d'un estat net en aquest domini (cap sessió prèvia d'un altre usuari)
        clearAuthToken();
        setAuthToken(data.access_token);
        localStorage.setItem(
          "sevalor_user",
          JSON.stringify({
            rol: "SUPERADMIN",
            is_impersonation: true,
            empresa_id: data.empresa_id,
            empresa_nom: data.empresa_nom,
          })
        );
        localStorage.setItem("sevalor_tenant_id", data.empresa_id);
        sessionStorage.setItem("sevalor_tenant_id", data.empresa_id);
        if (data.return_url) {
          localStorage.setItem(IMPERSONATION_RETURN_KEY, data.return_url);
        }
        window.location.replace("/gestio");
      } catch (e: any) {
        setError(e.message || "No s'ha pogut validar la sessió d'impersonació.");
      }
    };

    bescanviar();
  }, []);

  if (error) {
    return (
      <main className="min-h-screen flex items-center justify-center bg-slate-950 p-4">
        <div className="max-w-md w-full bg-slate-900 border border-rose-800/60 rounded-2xl p-6 text-center space-y-4">
          <div className="w-12 h-12 rounded-full bg-rose-950/80 text-rose-400 flex items-center justify-center mx-auto border border-rose-800">
            <AlertTriangle className="w-6 h-6" />
          </div>
          <h1 className="text-lg font-bold text-white">No s&apos;ha pogut obrir la sessió</h1>
          <p className="text-sm text-slate-400 leading-relaxed">{error}</p>
          <p className="text-xs text-slate-500">
            Els codis d&apos;impersonació caduquen als 60 segons i només es poden fer servir una vegada.
          </p>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen flex items-center justify-center bg-slate-950 p-4">
      <div className="flex flex-col items-center gap-3 text-slate-300">
        <ShieldCheck className="w-8 h-8 text-primary animate-pulse" />
        <p className="text-sm">Obrint la sessió d&apos;impersonació…</p>
      </div>
    </main>
  );
}
