"use client";

import React, { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { Shield, Settings, Globe } from "lucide-react";
import { getApiBaseUrl, setAuthToken } from "@/lib/api";
import { useChameleon } from "@/lib/chameleon";

export default function GestioLogin() {
  const router = useRouter();
  const { brand } = useChameleon();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [otpDigits, setOtpDigits] = useState<string[]>(["", "", "", "", "", ""]);
  const otpRefs = useRef<(HTMLInputElement | null)[]>([]);
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

  const handleOtpChange = (index: number, val: string) => {
    const clean = val.replace(/\D/g, "").slice(-1);
    const next = [...otpDigits];
    next[index] = clean;
    setOtpDigits(next);
    if (clean && index < 5) {
      otpRefs.current[index + 1]?.focus();
    }
  };

  const handleOtpKeyDown = (index: number, e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Backspace" && !otpDigits[index] && index > 0) {
      otpRefs.current[index - 1]?.focus();
    }
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const baseUrl = apiUrl || getApiBaseUrl();
      const totpCode = otpDigits.join("");
      const tenantId =
        (typeof sessionStorage !== "undefined" ? sessionStorage.getItem("sevalor_tenant_id") : null) ||
        (typeof localStorage !== "undefined" ? localStorage.getItem("sevalor_tenant_id") : null);

      const resp = await fetch(`${baseUrl}/auth/login`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(tenantId ? { "X-Tenant-ID": tenantId, "X-Empresa-ID": tenantId } : {}),
        },
        body: JSON.stringify({
          email: email.trim(),
          password,
          ...(totpCode.length === 6 ? { totp_code: totpCode } : {}),
        }),
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

      window.location.href = "/gestio";
    } catch (err: any) {
      setError(err.message || "Error al connectar amb el servidor. Comprova la URL de l'API.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="relative min-h-screen w-full flex items-center justify-center p-lg overflow-hidden bg-gradient-to-br from-[#022448] via-[#1E3A5F] to-[#0F172A] font-body-base text-on-surface">
      {/* Subtle Decorative Background Elements (Stitch Design) */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className="absolute -top-[10%] -left-[5%] w-[40%] h-[60%] rounded-full bg-secondary-container/10 blur-[120px]"></div>
        <div className="absolute -bottom-[10%] -right-[5%] w-[40%] h-[60%] rounded-full bg-primary-fixed/5 blur-[120px]"></div>
      </div>

      {/* Login Container Card */}
      <div className="relative z-10 w-full max-w-[440px] bg-surface-container-lowest/95 backdrop-blur-xl rounded-xl shadow-[0_24px_48px_rgba(0,0,0,0.4)] p-xl border border-white/10 transition-all duration-300">
        {/* Branding Header */}
        <div className="flex flex-col items-center text-center mb-xl">
          <div className="mb-md p-sm bg-primary/5 rounded-xl">
            {brand?.logotip_path ? (
              <img
                src={brand.logotip_path}
                alt={brand.empresa_nom || "Logo Empresa"}
                className="h-14 w-auto max-w-[140px] object-contain rounded-xl shadow-sm"
              />
            ) : (
              <div className="h-12 w-12 rounded-xl bg-primary text-white flex items-center justify-center shadow-md">
                <span className="material-symbols-outlined text-3xl">agriculture</span>
              </div>
            )}
          </div>
          <h1 className="font-display-lg text-display-lg text-primary tracking-tight">
            {brand?.empresa_nom ? `Accés ${brand.empresa_nom}` : "Accés Gestió"}
          </h1>
          <p className="text-on-surface-variant text-sm mt-xs">
            {brand?.empresa_nom
              ? "Panell de Gestió Tècnica i Control"
              : "Panell d'Administració i Control Tècnic · SEVALOR"}
          </p>
        </div>

        {error && (
          <div className="mb-lg p-md bg-error-container/80 border border-error/30 rounded-lg text-on-error-container text-sm font-medium flex items-center gap-sm">
            <Shield className="w-4 h-4 shrink-0 text-error" />
            <span>{error}</span>
          </div>
        )}

        {/* Primary Login Form */}
        <form onSubmit={handleLogin} className="space-y-lg">
          {/* Email Field */}
          <div className="space-y-xs">
            <label
              htmlFor="email"
              className="block font-label-caps text-label-caps text-on-surface-variant uppercase"
            >
              Correu electrònic
            </label>
            <div className="relative flex items-center">
              <span className="material-symbols-outlined absolute left-md text-outline text-[20px]">
                mail
              </span>
              <input
                id="email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="gestio@sevalor.com"
                className="w-full pl-11 pr-md py-3 bg-surface-container-low border border-outline-variant/50 rounded-lg text-on-surface placeholder:text-outline/60 focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/10 transition-all"
              />
            </div>
          </div>

          {/* Password Field */}
          <div className="space-y-xs">
            <div className="flex justify-between items-center">
              <label
                htmlFor="password"
                className="block font-label-caps text-label-caps text-on-surface-variant uppercase"
              >
                Contrasenya
              </label>
            </div>
            <div className="relative flex items-center">
              <span className="material-symbols-outlined absolute left-md text-outline text-[20px]">
                lock
              </span>
              <input
                id="password"
                type={showPassword ? "text" : "password"}
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full pl-11 pr-11 py-3 bg-surface-container-low border border-outline-variant/50 rounded-lg text-on-surface placeholder:text-outline/60 focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/10 transition-all"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-md text-outline hover:text-on-surface transition-colors"
              >
                <span className="material-symbols-outlined text-[20px]">
                  {showPassword ? "visibility_off" : "visibility"}
                </span>
              </button>
            </div>
          </div>

          {/* Remember Session */}
          <div className="flex items-center justify-between">
            <label className="flex items-center gap-sm cursor-pointer group">
              <input
                type="checkbox"
                defaultChecked
                className="w-4 h-4 rounded border-outline-variant text-primary focus:ring-primary/20 transition-all cursor-pointer"
              />
              <span className="text-sm text-on-surface-variant group-hover:text-on-surface transition-colors">
                Recordar sessió en aquest equip
              </span>
            </label>
          </div>

          {/* 2FA Section (Stitch Integrated TOTP) */}
          <div className="pt-md border-t border-surface-container-highest">
            <div className="flex items-center gap-xs mb-md">
              <span className="material-symbols-outlined text-secondary text-[18px]">
                verified_user
              </span>
              <span className="font-label-caps text-label-caps text-on-surface uppercase">
                Verificació en dos passos (2FA Opcional)
              </span>
            </div>
            <div className="grid grid-cols-6 gap-sm">
              {otpDigits.map((digit, idx) => (
                <input
                  key={idx}
                  ref={(el) => {
                    otpRefs.current[idx] = el;
                  }}
                  type="text"
                  inputMode="numeric"
                  maxLength={1}
                  value={digit}
                  onChange={(e) => handleOtpChange(idx, e.target.value)}
                  onKeyDown={(e) => handleOtpKeyDown(idx, e)}
                  placeholder="·"
                  className="w-full h-11 text-center font-data-tabular text-lg font-bold bg-surface-container-low border border-outline-variant rounded-lg focus:border-secondary-container focus:ring-2 focus:ring-secondary-container/20 outline-none transition-all"
                />
              ))}
            </div>
          </div>

          {/* Submit CTA */}
          <button
            type="submit"
            disabled={loading}
            className="w-full py-3.5 px-lg bg-primary hover:bg-primary-container text-on-primary font-body-strong rounded-lg shadow-lg shadow-primary/20 hover:shadow-primary/30 active:scale-[0.98] transition-all flex items-center justify-center gap-sm group disabled:opacity-50"
          >
            <span>{loading ? "Autenticant..." : "Entrar al Panell"}</span>
            {!loading && (
              <span className="material-symbols-outlined text-[18px] group-hover:translate-x-1 transition-transform">
                arrow_forward
              </span>
            )}
          </button>
        </form>

        {/* Footer Info & API Server Configuration */}
        <div className="mt-xl pt-md border-t border-surface-container text-center space-y-2">
          <button
            type="button"
            onClick={() => setShowConfig(!showConfig)}
            className="text-xs text-outline hover:text-primary flex items-center justify-center gap-1 mx-auto transition-colors"
          >
            <Settings className="w-3.5 h-3.5" />
            <span>Configuració del servidor API</span>
          </button>

          {showConfig && (
            <form onSubmit={handleSaveApiUrl} className="mt-3 w-full space-y-2 text-xs text-left">
              <label className="block font-medium text-on-surface-variant">
                URL base de l&apos;API backend:
              </label>
              <div className="flex gap-2">
                <div className="relative flex-1">
                  <Globe className="w-3.5 h-3.5 absolute left-2.5 top-2.5 text-outline" />
                  <input
                    type="text"
                    value={apiUrl}
                    onChange={(e) => setApiUrl(e.target.value)}
                    placeholder="https://api.domini.com/api/v1"
                    className="w-full pl-8 pr-2 py-1.5 border border-outline-variant rounded-lg bg-surface-container-low text-on-surface"
                  />
                </div>
                <button
                  type="submit"
                  className="px-3 py-1.5 bg-primary text-white rounded-lg font-medium hover:bg-primary-container"
                >
                  Desar
                </button>
              </div>
            </form>
          )}

          <p className="text-xs text-outline">
            Sistema d&apos;ús exclusiu per a personal autoritzat · Zero-Trust RLS
          </p>
        </div>
      </div>
    </main>
  );
}
