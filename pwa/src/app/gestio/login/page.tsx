"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Shield, Lock, Mail, ArrowRight, Building2, Settings, Globe } from "lucide-react";
import { getApiBaseUrl, setAuthToken } from "@/lib/api";

export default function GestioLogin() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [showConfig, setShowConfig] = useState(false);
  const [apiUrl, setApiUrl] = useState("");

  useEffect(() => {
    setApiUrl(getApiBaseUrl());
  }, []);

  const handleSaveApiUrl = (e: React.FormEvent) => {
    e.preventDefault();
    if (apiUrl) {
      localStorage.setItem("sevalor_api_url", apiUrl.trim().replace(/\/+$/, ""));
      setShowConfig(false);
      setError("");
    }
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const baseUrl = apiUrl || getApiBaseUrl();
      const resp = await fetch(`${baseUrl}/auth/login`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ email: email.trim(), password }),
      });

      if (!resp.ok) {
        const errorData = await resp.json().catch(() => ({}));
        throw new Error(errorData.detail || `Error ${resp.status}: Credencials incorrectes`);
      }

      const data = await resp.json();
      
      // Guardar cookie per al Middleware
      const isHttps = typeof window !== "undefined" && window.location.protocol === "https:";
      const secureFlag = isHttps ? "; Secure" : "";
      document.cookie = `sevalor_access_token=${data.access_token}; path=/; max-age=86400; SameSite=Lax${secureFlag}`;
      
      // Guardar token al localStorage per a apiFetch
      setAuthToken(data.access_token);
      // Guardar dades d'usuari
      localStorage.setItem("sevalor_user", JSON.stringify(data));

      window.location.href = "/gestio/mapa";
    } catch (err: any) {
      setError(err.message || "Error al connectar amb el servidor. Comprova la URL de l'API.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-slate-100 dark:bg-slate-950">
      <div className="w-full max-w-md bg-white dark:bg-slate-900 rounded-3xl shadow-xl overflow-hidden border border-slate-200 dark:border-slate-800">
        
        {/* Capçalera */}
        <div className="bg-slate-900 p-8 text-center relative overflow-hidden">
          <div className="absolute top-0 right-0 p-4 opacity-10">
            <Shield className="w-32 h-32 text-white" />
          </div>
          <div className="relative z-10 flex flex-col items-center">
            <div className="w-16 h-16 bg-emerald-600 rounded-2xl flex items-center justify-center mb-4 shadow-lg shadow-emerald-500/30">
              <Building2 className="w-8 h-8 text-white" />
            </div>
            <h1 className="text-2xl font-bold text-white tracking-tight">SEVALOR Oficina</h1>
            <p className="text-slate-400 mt-2 text-sm">Accés corporatiu segur (Gestió)</p>
          </div>
        </div>

        {/* Formulari */}
        <div className="p-8">
          {error && (
            <div className="mb-6 p-4 bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 rounded-xl text-red-600 dark:text-red-400 text-sm font-medium flex items-center gap-2">
              <Shield className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleLogin} className="space-y-5">
            <div>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1.5">
                Correu electrònic
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <Mail className="h-5 w-5 text-slate-400" />
                </div>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="block w-full pl-10 pr-3 py-3 border border-slate-200 dark:border-slate-700 rounded-xl bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-emerald-500 transition-shadow"
                  placeholder="gestio@sevalor.com"
                />
              </div>
            </div>

            <div>
              <div className="flex justify-between items-center mb-1.5">
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
                  Contrasenya
                </label>
              </div>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <Lock className="h-5 w-5 text-slate-400" />
                </div>
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="block w-full pl-10 pr-3 py-3 border border-slate-200 dark:border-slate-700 rounded-xl bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-emerald-500 transition-shadow"
                  placeholder="••••••••"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full flex items-center justify-center gap-2 py-3 px-4 border border-transparent rounded-xl text-sm font-bold text-white bg-emerald-600 hover:bg-emerald-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {loading ? "Autenticant..." : "Entrar al Panell"}
              {!loading && <ArrowRight className="w-4 h-4" />}
            </button>
          </form>

          {/* Opcions de xarxa / servidor */}
          <div className="mt-6 pt-4 border-t border-slate-200 dark:border-slate-800 flex flex-col items-center">
            <button
              type="button"
              onClick={() => setShowConfig(!showConfig)}
              className="text-xs text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 flex items-center gap-1 transition-colors"
            >
              <Settings className="w-3.5 h-3.5" />
              <span>Configuració del servidor API</span>
            </button>

            {showConfig && (
              <form onSubmit={handleSaveApiUrl} className="mt-3 w-full space-y-2 text-xs">
                <label className="block font-medium text-slate-600 dark:text-slate-400">
                  URL base de l&apos;API backend:
                </label>
                <div className="flex gap-2">
                  <div className="relative flex-1">
                    <Globe className="w-3.5 h-3.5 absolute left-2.5 top-2.5 text-slate-400" />
                    <input
                      type="text"
                      value={apiUrl}
                      onChange={(e) => setApiUrl(e.target.value)}
                      placeholder="https://api.domini.com/api/v1"
                      className="w-full pl-8 pr-2 py-1.5 border border-slate-300 dark:border-slate-700 rounded-lg bg-slate-50 dark:bg-slate-800 text-slate-800 dark:text-slate-200"
                    />
                  </div>
                  <button
                    type="submit"
                    className="px-3 py-1.5 bg-slate-800 dark:bg-slate-700 text-white rounded-lg font-medium hover:bg-slate-700"
                  >
                    Desar
                  </button>
                </div>
              </form>
            )}

            <p className="text-[11px] text-slate-400 dark:text-slate-500 font-mono mt-3">
              Entorn protegit per Zero-Trust RLS
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
