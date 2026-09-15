"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { Server, Lock, Mail, ArrowRight, Activity } from "lucide-react";

export default function SuperadminLogin() {
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
        throw new Error("Accés denegat");
      }

      const data = await resp.json();
      
      if (data.rol !== "SUPERADMIN") {
        throw new Error("Només comptes SaaS Superadmin");
      }

      // Guardar cookie
      document.cookie = `sevalor_access_token=${data.access_token}; path=/; max-age=86400; SameSite=Strict`;
      
      localStorage.setItem("sevalor_user", JSON.stringify(data));
      router.push("/superadmin/telemetria");
    } catch (err: any) {
      setError(err.message || "Error al connectar amb el servidor");
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
            <p className="text-amber-500 mt-2 text-sm font-mono tracking-widest uppercase">Node Central</p>
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
                  placeholder="master@sevalor.app"
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
          
          <div className="mt-6 text-center">
            <p className="text-[10px] text-slate-600 font-mono">
              UNAUTHORIZED ACCESS IS STRICTLY PROHIBITED
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}