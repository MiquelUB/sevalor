"use client";

import React, { useState, useEffect, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import {
  ShieldCheck,
  Lock,
  CheckCircle2,
  AlertTriangle,
  Building2,
  ArrowRight,
  Eye,
  EyeOff,
  KeyRound,
} from "lucide-react";

interface InfoActivacio {
  valid: boolean;
  usuari_id: string;
  nom: string;
  cognoms: string;
  email: string;
  empresa_id: string;
  empresa_nom: string;
  subdomini: string;
  primari_hsl?: string;
  logotip_path?: string;
}

function ContingutActivacio() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const token = searchParams.get("token") || "";

  const [loading, setLoading] = useState(true);
  const [errorVerificacio, setErrorVerificacio] = useState<string | null>(null);
  const [info, setInfo] = useState<InfoActivacio | null>(null);

  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  const [submitting, setSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [activat, setActivat] = useState(false);

  useEffect(() => {
    if (!token) {
      setErrorVerificacio("No s'ha proporcionat cap token d'activació a l'enllaç.");
      setLoading(false);
      return;
    }

    const verificarToken = async () => {
      try {
        const res = await fetch(`/api/v1/auth/activacio/verificar?token=${encodeURIComponent(token)}`);
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.detail || "L'enllaç d'activació és invàlid o ha caducat.");
        }
        const data: InfoActivacio = await res.json();
        setInfo(data);
      } catch (err: any) {
        setErrorVerificacio(err.message || "Error verificant l'enllaç d'activació.");
      } finally {
        setLoading(false);
      }
    };

    verificarToken();
  }, [token]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    if (password.length < 8) {
      setErrorMessage("La contrasenya ha de tenir com a mínim 8 caràcters.");
      return;
    }

    if (password !== passwordConfirm) {
      setErrorMessage("Les dues contrasenyes no coincideixen.");
      return;
    }

    setSubmitting(true);
    try {
      const res = await fetch("/api/v1/auth/activacio", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          token,
          password,
          password_confirm: passwordConfirm,
        }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Error en activar el compte.");
      }

      setActivat(true);
    } catch (err: any) {
      setErrorMessage(err.message || "Error processant l'activació.");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-900 text-white font-mono p-4">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-4 border-emerald-500 border-t-transparent rounded-full animate-spin" />
          <p className="text-sm text-slate-400">Verificant credencials d'alta sobirana...</p>
        </div>
      </div>
    );
  }

  if (errorVerificacio || !info) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-950 p-4">
        <div className="max-w-md w-full bg-slate-900 border border-rose-800/60 rounded-2xl p-6 shadow-2xl text-center space-y-4">
          <div className="w-12 h-12 rounded-full bg-rose-950/80 text-rose-400 flex items-center justify-center mx-auto border border-rose-800">
            <AlertTriangle className="w-6 h-6" />
          </div>
          <h2 className="text-lg font-bold text-white">Enllaç d'Activació Invàlid</h2>
          <p className="text-xs text-slate-400 leading-relaxed font-sans">
            {errorVerificacio || "L'enllaç d'activació ha caducat (validesa màxima de 24 hores) o és incorrecte."}
          </p>
          <div className="pt-2">
            <button
              onClick={() => router.push("/gestio/login")}
              className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-white text-xs font-mono font-bold transition-colors"
            >
              Anar al Login de Gestió
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (activat) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-950 p-4">
        <div className="max-w-md w-full bg-slate-900 border border-emerald-500/50 rounded-2xl p-8 shadow-2xl text-center space-y-5">
          <div className="w-16 h-16 rounded-full bg-emerald-950/80 text-emerald-400 flex items-center justify-center mx-auto border border-emerald-500">
            <CheckCircle2 className="w-8 h-8" />
          </div>
          <div>
            <h2 className="text-xl font-black text-white">Compte Activat Correctament!</h2>
            <p className="text-xs text-slate-400 mt-1 font-sans">
              La teva contrasenya de gerència per a <strong>{info.empresa_nom}</strong> s'ha desat amb xifratge segur bcrypt.
            </p>
          </div>
          <button
            onClick={() => router.push("/gestio/login")}
            className="w-full py-3 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold font-mono flex items-center justify-center gap-2 shadow-lg transition-all"
          >
            <span>Iniciar Sessió a Gestió</span>
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-950 p-4">
      <div className="max-w-md w-full bg-slate-900 border border-slate-800 rounded-2xl p-6 md:p-8 shadow-2xl space-y-6">
        {/* Capçalera */}
        <div className="space-y-2 text-center">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-950/60 border border-emerald-800/60 text-emerald-300 text-xs font-mono font-bold">
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>Activació de Compte de Gerència</span>
          </div>
          <h1 className="text-2xl font-black text-white tracking-tight">
            Benvingut/da, {info.nom}!
          </h1>
          <p className="text-xs text-slate-400 font-sans">
            S'ha donat d'alta correctament l'empresa <strong className="text-slate-200">{info.empresa_nom}</strong>.
            Si us plau, definiu la vostra contrasenya segura per accedir a la consola de governança.
          </p>
        </div>

        {/* Formulari d'Alta de Contrasenya */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-bold text-slate-300 mb-1">
              Correu de Gerència
            </label>
            <input
              type="text"
              disabled
              value={info.email}
              className="w-full p-2.5 rounded-xl border border-slate-700 bg-slate-800/50 text-slate-400 font-mono text-xs cursor-not-allowed"
            />
          </div>

          <div>
            <label className="block text-xs font-bold text-slate-300 mb-1">
              Nova Contrasenya (Mínim 8 caràcters)
            </label>
            <div className="relative">
              <input
                type={showPassword ? "text" : "password"}
                required
                minLength={8}
                placeholder="••••••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full p-2.5 pr-10 rounded-xl border border-slate-700 bg-slate-800 text-white font-mono text-xs focus:outline-none focus:border-emerald-500"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-2.5 text-slate-400 hover:text-slate-200"
              >
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>

          <div>
            <label className="block text-xs font-bold text-slate-300 mb-1">
              Confirmar Contrasenya
            </label>
            <input
              type={showPassword ? "text" : "password"}
              required
              minLength={8}
              placeholder="••••••••••••"
              value={passwordConfirm}
              onChange={(e) => setPasswordConfirm(e.target.value)}
              className="w-full p-2.5 rounded-xl border border-slate-700 bg-slate-800 text-white font-mono text-xs focus:outline-none focus:border-emerald-500"
            />
          </div>

          {errorMessage && (
            <div className="p-3 rounded-xl bg-rose-950/60 border border-rose-800 text-rose-200 text-xs font-medium flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
              <span>{errorMessage}</span>
            </div>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="w-full py-3 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-mono text-xs font-bold flex items-center justify-center gap-2 shadow-lg transition-all"
          >
            <KeyRound className="w-4 h-4" />
            <span>{submitting ? "Desant contrasenya..." : "Activar Compte & Accedir"}</span>
          </button>
        </form>
      </div>
    </div>
  );
}

export default function ActivacioPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center bg-slate-950 text-white font-mono text-xs">
          Carregant...
        </div>
      }
    >
      <ContingutActivacio />
    </Suspense>
  );
}
