"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { Shield, Lock, Mail, ArrowRight, Building2 } from "lucide-react";

export default function GestioLogin() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const resp = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8001/api/v1"}/auth/login`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ email, password }),
      });

      if (!resp.ok) {
        throw new Error("Credencials incorrectes");
      }

      const data = await resp.json();
      
      // Guardar cookie
      document.cookie = `sevalor_access_token=${data.access_token}; path=/; max-age=86400; SameSite=Strict`;
      
      // Guardar dades d'usuari
      localStorage.setItem("sevalor_user", JSON.stringify(data));

      router.push("/gestio/mapa");
    } catch (err: any) {
      setError(err.message || "Error al connectar amb el servidor");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
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
            <p className="text-slate-400 mt-2 text-sm">Accés corporatiu segur</p>
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
                  placeholder="admin@empresa.com"
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
          
          <div className="mt-6 text-center">
            <p className="text-xs text-slate-500 dark:text-slate-400 font-mono">
              Entorn protegit per Zero-Trust RLS
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}