"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Delete, ShieldAlert, Sun, Moon, User, ArrowRight, Settings, Globe } from "lucide-react";
import {
  createSentinelBlock,
  verifySentinelBlock,
} from "@/lib/crypto";
import { apiFetch, setAuthToken, getApiBaseUrl } from "@/lib/api";

const NIF_STORAGE_KEY = "sevalor_operari_nif";
const SENTINEL_SALT_KEY = "sevalor_sentinel_salt";
const SENTINEL_CIPHER_KEY = "sevalor_sentinel_cipher";
const SENTINEL_IV_KEY = "sevalor_sentinel_iv";

export default function OperariLoginPage() {
  const [pin, setPin] = useState<string>("");
  const [nif, setNif] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [showConfig, setShowConfig] = useState(false);
  const [apiUrl, setApiUrl] = useState("");
  const [isOffline, setIsOffline] = useState(false);
  const router = useRouter();

  // Mode Clar / Fosc
  const [isDark, setIsDark] = useState<boolean>(true);

  useEffect(() => {
    const savedTheme = localStorage.getItem("sevalor_theme");
    if (savedTheme === "light") {
      setIsDark(false);
      document.documentElement.classList.remove("dark");
    } else {
      setIsDark(true);
      document.documentElement.classList.add("dark");
    }

    const savedNif = localStorage.getItem(NIF_STORAGE_KEY);
    if (savedNif) {
      setNif(savedNif);
    }

    setApiUrl(getApiBaseUrl());
    setIsOffline(typeof navigator !== "undefined" && !navigator.onLine);

    const handleOnline = () => setIsOffline(false);
    const handleOffline = () => setIsOffline(true);
    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);
    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, []);

  const toggleTheme = () => {
    if (isDark) {
      document.documentElement.classList.remove("dark");
      localStorage.setItem("sevalor_theme", "light");
      setIsDark(false);
    } else {
      document.documentElement.classList.add("dark");
      localStorage.setItem("sevalor_theme", "dark");
      setIsDark(true);
    }
  };

  const handleNifChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value.toUpperCase().trim();
    setNif(val);
    localStorage.setItem(NIF_STORAGE_KEY, val);
    setError(null);
  };

  const handleDigit = (digit: string) => {
    if (pin.length < 4) {
      const nouPin = pin + digit;
      setPin(nouPin);
      setError(null);
    }
  };

  const handleClear = () => {
    setPin("");
    setError(null);
  };

  const handleDelete = () => {
    setPin((prev) => prev.slice(0, -1));
    setError(null);
  };

  // En completar el 4t dígit, commuta automàticament el flux si tenim NIF
  useEffect(() => {
    if (pin.length === 4) {
      if (!nif.trim()) {
        setError("Si us plau, escriu el teu DNI/NIF primer.");
        setPin("");
        return;
      }
      submitLogin(pin);
    }
  }, [pin]);

  const submitLogin = async (codiPin: string) => {
    const operariNif = nif.trim().toUpperCase();
    if (!operariNif) {
      setError("Cal introduir el DNI/NIF per accedir.");
      setPin("");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      localStorage.setItem(NIF_STORAGE_KEY, operariNif);

      // Autenticació contra backend
      const response = await apiFetch<{
        access_token: string;
        usuari: { id: string; nom: string; rol: string };
      }>("/operari_auth/login", {
        method: "POST",
        body: JSON.stringify({
          nif: operariNif,
          pin: codiPin,
        }),
      });

      if (response && response.access_token) {
        setAuthToken(response.access_token);
        const isHttps = typeof window !== "undefined" && window.location.protocol === "https:";
        const secureFlag = isHttps ? "; Secure" : "";
        document.cookie = `sevalor_access_token=${response.access_token}; path=/; max-age=86400; SameSite=Lax${secureFlag}`;

        // Sentinel offline handling
        const saltHex = localStorage.getItem(SENTINEL_SALT_KEY);
        if (saltHex) {
          const cipher = localStorage.getItem(SENTINEL_CIPHER_KEY);
          const iv = localStorage.getItem(SENTINEL_IV_KEY);
          if (cipher && iv) {
            try {
              const saltBytes = new Uint8Array(saltHex.split(",").map(Number));
              const valid = await verifySentinelBlock(codiPin, saltBytes, cipher, iv);
              if (!valid) {
                localStorage.removeItem(SENTINEL_CIPHER_KEY);
                localStorage.removeItem(SENTINEL_IV_KEY);
                localStorage.removeItem(SENTINEL_SALT_KEY);
              }
            } catch {
              localStorage.removeItem(SENTINEL_CIPHER_KEY);
              localStorage.removeItem(SENTINEL_IV_KEY);
              localStorage.removeItem(SENTINEL_SALT_KEY);
            }
          }
        }

        if (!localStorage.getItem(SENTINEL_SALT_KEY)) {
          const saltBytes = crypto.getRandomValues(new Uint8Array(32));
          localStorage.setItem(SENTINEL_SALT_KEY, Array.from(saltBytes).join(","));
          const { cipherTextHex, ivHex } = await createSentinelBlock(codiPin, saltBytes);
          localStorage.setItem(SENTINEL_CIPHER_KEY, cipherTextHex);
          localStorage.setItem(SENTINEL_IV_KEY, ivHex);
        }

        sessionStorage.setItem("sevalor_session_pin", codiPin);
        window.location.href = "/operari/feines";
      } else {
        setError("PIN incorrecte. Torna a intentar-ho.");
        setPin("");
      }
    } catch (err: any) {
      // Intentar validació offline via sentinel si falla la xarxa
      const saltHex = localStorage.getItem(SENTINEL_SALT_KEY);
      if (saltHex) {
        const cipher = localStorage.getItem(SENTINEL_CIPHER_KEY);
        const iv = localStorage.getItem(SENTINEL_IV_KEY);
        if (cipher && iv) {
          try {
            const saltBytes = new Uint8Array(saltHex.split(",").map(Number));
            const valid = await verifySentinelBlock(codiPin, saltBytes, cipher, iv);
            if (valid) {
              sessionStorage.setItem("sevalor_session_pin", codiPin);
              window.location.href = "/operari/feines";
              setLoading(false);
              return;
            }
          } catch {
            // Ignorar
          }
        }
      }

      setError(err.message || "Error al connectar amb el servidor.");
      setPin("");
    } finally {
      setLoading(false);
    }
  };

  const handleSaveApiUrl = (e: React.FormEvent) => {
    e.preventDefault();
    if (apiUrl) {
      localStorage.setItem("sevalor_api_url", apiUrl.trim().replace(/\/+$/, ""));
      setShowConfig(false);
      setError(null);
    }
  };

  return (
    <div className="min-h-screen flex flex-col justify-between p-5 bg-gradient-to-b from-[#1E3A5F] to-[#0F172A] text-white select-none relative overflow-hidden">
      {/* Decorative Background Elements */}
      <div className="fixed -bottom-24 -left-24 w-64 h-64 bg-secondary-container/10 rounded-full blur-3xl pointer-events-none" />
      <div className="fixed -top-24 -right-24 w-64 h-64 bg-primary-container/20 rounded-full blur-3xl pointer-events-none" />

      {/* Top Status Bar & Branding (Stitch Screen 1cd4053a312544f2a66347703d5d6945) */}
      <header className="w-full flex flex-col items-center pt-2 relative z-10">
        <div className="w-full flex items-center justify-between mb-4">
          {/* Status Indicator Badge */}
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-amber-500/15 border border-amber-500/30">
            <span className="material-symbols-outlined text-amber-400 text-[16px]">
              {isOffline ? "cloud_off" : "verified_user"}
            </span>
            <span className="text-[11px] font-bold uppercase tracking-wider text-amber-400">
              {isOffline ? "Mode fora de línia actiu" : "Terminal Segur Zero-Trust"}
            </span>
          </div>

          <button
            onClick={toggleTheme}
            className="p-2 rounded-xl bg-white/10 hover:bg-white/20 text-white/80 transition-colors"
            title="Commutar Tema"
          >
            {isDark ? <Sun className="w-4 h-4 text-amber-400" /> : <Moon className="w-4 h-4 text-sky-300" />}
          </button>
        </div>

        {/* Logo & Brand Name */}
        <div className="flex flex-col items-center gap-1.5">
          <div className="w-14 h-14 rounded-2xl bg-white/10 backdrop-blur-md flex items-center justify-center border border-white/15 shadow-xl">
            <span
              className="material-symbols-outlined text-secondary-container text-[32px]"
              style={{ fontVariationSettings: "'FILL' 1" }}
            >
              agriculture
            </span>
          </div>
          <div className="text-center">
            <h1 className="text-2xl font-extrabold tracking-tight text-white">
              Sevalor <span className="text-secondary-container">SEVALOR</span>
            </h1>
            <p className="text-slate-400 text-xs font-medium mt-0.5">
              Introdueix el teu DNI/NIF i PIN d&apos;operari
            </p>
          </div>
        </div>
      </header>

      {/* Main Content: NIF + PIN Indicators & Tactile Keypad */}
      <div className="w-full max-w-[320px] mx-auto flex flex-col items-center gap-4 my-auto py-3 relative z-10">
        {/* Error Alert */}
        {error && (
          <div className="w-full p-3 bg-rose-500/20 border border-rose-400/40 rounded-xl text-rose-200 text-xs font-medium flex items-center gap-2">
            <ShieldAlert className="w-4 h-4 shrink-0 text-rose-400" />
            <span>{error}</span>
          </div>
        )}

        {/* Camp NIF / DNI editable */}
        <div className="w-full">
          <label className="block text-[10px] font-bold uppercase tracking-widest text-slate-300 mb-1.5">
            DNI / NIF de l&apos;Operari
          </label>
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
              <User className="w-4 h-4" />
            </div>
            <input
              type="text"
              required
              value={nif}
              onChange={handleNifChange}
              placeholder="ex: 12345678A"
              className="block w-full pl-10 pr-3 py-2.5 text-sm font-mono font-bold uppercase tracking-wider rounded-xl border border-white/15 bg-white/10 backdrop-blur-md text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-secondary-container shadow-inner"
            />
          </div>
        </div>

        {/* 4-Dot & Box PIN Display */}
        <div className="flex flex-col items-center gap-2 py-1">
          <span className="text-[10px] font-bold uppercase tracking-widest text-slate-400">
            PIN de 4 dígits
          </span>
          <div className="flex items-center justify-center gap-4" role="status" aria-label="PIN progress">
            {[0, 1, 2, 3].map((idx) => {
              const filled = pin.length > idx;
              return (
                <div
                  key={idx}
                  className={`w-11 h-12 rounded-2xl border-2 flex items-center justify-center text-xl font-bold transition-all ${
                    filled
                      ? "border-secondary-container bg-secondary-container/20 text-secondary-container shadow-[0_0_12px_rgba(30,132,73,0.4)]"
                      : "border-white/20 bg-white/5 text-white/30"
                  }`}
                >
                  {filled ? "•" : ""}
                </div>
              );
            })}
          </div>
        </div>

        {/* Numeric Keypad (3x4 Grid Stitch Circular Tactile Buttons) */}
        <div className="grid grid-cols-3 gap-x-5 gap-y-3 w-full justify-items-center">
          {["1", "2", "3", "4", "5", "6", "7", "8", "9"].map((num) => (
            <button
              key={num}
              type="button"
              disabled={loading}
              onClick={() => handleDigit(num)}
              className="w-[68px] h-[68px] rounded-full bg-white/10 hover:bg-white/15 active:bg-secondary-container active:scale-95 transition-all flex items-center justify-center text-2xl font-bold text-white border border-white/10 shadow-lg touch-manipulation"
            >
              {num}
            </button>
          ))}

          <button
            type="button"
            onClick={handleClear}
            className="w-[68px] h-[68px] rounded-full bg-white/5 hover:bg-white/10 active:bg-white/20 active:scale-95 transition-all flex items-center justify-center text-sm font-bold text-slate-300 border border-white/5 touch-manipulation"
            title="Netejar PIN"
          >
            C
          </button>

          <button
            type="button"
            disabled={loading}
            onClick={() => handleDigit("0")}
            className="w-[68px] h-[68px] rounded-full bg-white/10 hover:bg-white/15 active:bg-secondary-container active:scale-95 transition-all flex items-center justify-center text-2xl font-bold text-white border border-white/10 shadow-lg touch-manipulation"
          >
            0
          </button>

          <button
            type="button"
            onClick={handleDelete}
            aria-label="Esborrar"
            className="w-[68px] h-[68px] rounded-full bg-transparent hover:bg-white/5 active:bg-white/15 active:scale-95 transition-all flex items-center justify-center text-slate-300 touch-manipulation"
          >
            <Delete className="w-6 h-6" />
          </button>
        </div>

        {/* Primary Action Button (Stitch Green CTA) */}
        <button
          type="button"
          disabled={loading || pin.length !== 4 || !nif.trim()}
          onClick={() => submitLogin(pin)}
          className="w-full h-13 py-3.5 mt-1 rounded-xl bg-secondary-container hover:brightness-110 active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-xl shadow-black/20 flex items-center justify-center gap-2 text-white font-bold text-sm tracking-wide uppercase"
        >
          <span>{loading ? "Comprovant accés..." : "Entrar al Terminal"}</span>
          {!loading && <ArrowRight className="w-4 h-4" />}
        </button>
      </div>

      {/* Footer Metadata & Server Config */}
      <footer className="w-full flex flex-col items-center gap-2 pb-1 relative z-10 max-w-xs mx-auto">
        <button
          type="button"
          onClick={() => setShowConfig(!showConfig)}
          className="text-slate-400 hover:text-white text-xs font-medium transition-colors py-1 px-3 rounded-lg flex items-center gap-1.5"
        >
          <Settings className="w-3.5 h-3.5" />
          <span>Configuració del servidor API</span>
        </button>

        {showConfig && (
          <form onSubmit={handleSaveApiUrl} className="w-full space-y-2 text-xs bg-slate-900/90 p-3 rounded-xl border border-white/10">
            <label className="block font-medium text-slate-300 text-left">
              URL de l&apos;API:
            </label>
            <div className="flex gap-2">
              <div className="relative flex-1">
                <Globe className="w-3.5 h-3.5 absolute left-2.5 top-2.5 text-slate-400" />
                <input
                  type="text"
                  value={apiUrl}
                  onChange={(e) => setApiUrl(e.target.value)}
                  placeholder="https://api.domini.com/api/v1"
                  className="w-full pl-8 pr-2 py-1.5 border border-white/15 rounded-lg bg-slate-800 text-white"
                />
              </div>
              <button
                type="submit"
                className="px-3 py-1.5 bg-secondary-container text-white rounded-lg font-bold hover:brightness-110"
              >
                Desar
              </button>
            </div>
          </form>
        )}

        <div className="flex items-center gap-2 opacity-40">
          <span className="text-[10px] font-bold tracking-widest uppercase text-slate-400">
            v4.0 • AES-GCM 256 Offline Ready
          </span>
        </div>
      </footer>
    </div>
  );
}