"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Server, Lock, Mail, ArrowRight, Activity, Settings, Globe } from "lucide-react";
import { getApiBaseUrl, setAuthToken } from "@/lib/api";

export default function SuperadminLogin() {
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
        throw new Error(errorData.detail || `Error ${resp.status}: Accés denegat`);
      }

      const data = await resp.json();
      
      if (data.rol !== "SUPERADMIN") {
        throw new Error("Accés restringit: només comptes SaaS Superadmin");
      }

      // Guardar cookie per al Middleware
      const isHttps = typeof window !== "undefined" && window.location.protocol === "https:";
      const secureFlag = isHttps ? "; Secure" : "";
      document.cookie = `sevalor_access_token=${data.access_token}; path=/; max-age=86400; SameSite=Lax${secureFlag}`;
      
      // Guardar token al localStorage per a apiFetch
      setAuthToken(data.access_token);
      localStorage.setItem("sevalor_user", JSON.stringify(data));
      window.location.href = "/superadmin/telemetria";
    } catch (err: any) {
      setError(err.message || "Error al connectar amb el servidor. Comprova la URL de l'API.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-slate-950">
      <div className="w-full max-w-md bg-slate-900 rounded-3xl shadow-2xl overflow-hidden border border-slate-800">
        
        {/* Capçalera */}
        <div className="bg-slate-950 p-8 text-center relative overflow-hidden">
          <div className="absolute top-0 right-0 p-4 opacity-5">
            <Server className="w-32 h-32 text-white" />
          </div>
          <div className="relative z-10 flex flex-col items-center">
            <div className="w-16 h-16 bg-amber-600 rounded-2xl flex items-center justify-center mb-4 shadow-lg shadow-amber-500/20">
              <Activity className="w-8 h-8 text-white" />
            </div>
            <h1 className="text-2xl font-bold text-white tracking-tight">SaaS Master</h1>
            <p className="text-amber-500 mt-2 text-sm font-mono tracking-widest uppercase">Node Central (Superadmin)</p>
          </div>
        </div>

        {/* Formulari */}
        <div className="p-8">
          {error && (
            <div className="mb-6 p-4 bg-red-900/30 border border-red-800 rounded-xl text-red-400 text-sm font-medium flex items-center gap-2">
              <Lock className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleLogin} className="space-y-5">
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-1.5 font-mono">
                [USER_NODE]
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <Mail className="h-5 w-5 text-slate-500" />
                </div>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="block w-full pl-10 pr-3 py-3 border border-slate-700 rounded-xl bg-slate-800 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-amber-500 font-mono transition-shadow"
                  placeholder="admin@sevalor.com"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-300 mb-1.5 font-mono">
                [SECURE_KEY]
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <Lock className="h-5 w-5 text-slate-500" />
                </div>
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="block w-full pl-10 pr-3 py-3 border border-slate-700 rounded-xl bg-slate-800 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-amber-500 font-mono transition-shadow"
                  placeholder="••••••••"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full flex items-center justify-center gap-2 py-3 px-4 border border-transparent rounded-xl text-sm font-bold text-slate-900 bg-amber-500 hover:bg-amber-400 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-amber-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {loading ? "INITIALIZING..." : "SYSTEM OVERRIDE"}
              {!loading && <ArrowRight className="w-4 h-4" />}
            </button>
          </form>

          {/* Opcions de xarxa / servidor */}
          <div className="mt-6 pt-4 border-t border-slate-800 flex flex-col items-center">
            <button
              type="button"
              onClick={() => setShowConfig(!showConfig)}
              className="text-xs text-slate-500 hover:text-slate-300 flex items-center gap-1 transition-colors"
            >
              <Settings className="w-3.5 h-3.5" />
              <span>Configuració del servidor API</span>
            </button>

            {showConfig && (
              <form onSubmit={handleSaveApiUrl} className="mt-3 w-full space-y-2 text-xs">
                <label className="block font-medium text-slate-400">
                  URL base de l&apos;API backend:
                </label>
                <div className="flex gap-2">
                  <div className="relative flex-1">
                    <Globe className="w-3.5 h-3.5 absolute left-2.5 top-2.5 text-slate-500" />
                    <input
                      type="text"
                      value={apiUrl}
                      onChange={(e) => setApiUrl(e.target.value)}
                      placeholder="https://api.domini.com/api/v1"
                      className="w-full pl-8 pr-2 py-1.5 border border-slate-700 rounded-lg bg-slate-800 text-slate-200"
                    />
                  </div>
                  <button
                    type="submit"
                    className="px-3 py-1.5 bg-amber-600 text-white rounded-lg font-medium hover:bg-amber-500"
                  >
                    Desar
                  </button>
                </div>
              </form>
            )}

            <p className="text-[10px] text-slate-600 font-mono mt-3">
              UNAUTHORIZED ACCESS IS STRICTLY PROHIBITED
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
