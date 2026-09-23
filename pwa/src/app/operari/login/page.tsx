"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Lock, Delete, ShieldAlert, Sun, Moon, User, ArrowRight, Settings, Globe } from "lucide-react";
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
    <div className="min-h-screen flex flex-col justify-between p-4 sm:p-6 bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 transition-colors duration-200">
      
      {/* Capçalera */}
      <div className="text-center pt-2 sm:pt-4 relative max-w-sm mx-auto w-full">
        <button
          onClick={toggleTheme}
          className="absolute right-0 top-0 p-2 rounded-xl bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300 shadow-sm"
          title="Commutar Tema"
        >
          {isDark ? <Sun className="w-4 h-4 text-amber-400" /> : <Moon className="w-4 h-4 text-blue-500" />}
        </button>

        <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-emerald-600/10 dark:bg-emerald-600/20 text-emerald-600 dark:text-emerald-400 mb-2 border border-emerald-500/30 shadow-inner">
          <Lock className="w-7 h-7" />
        </div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
          SEVALOR
        </h1>
        <p className="text-xs text-slate-500 dark:text-slate-400">
          Terminal de Camp d&apos;Operari
        </p>
      </div>

      {/* Cos central: Formulari NIF + PIN */}
      <div className="my-auto py-2 max-w-xs mx-auto w-full">
        
        {/* Error Alert */}
        {error && (
          <div className="mb-4 p-3 bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 rounded-xl text-red-600 dark:text-red-400 text-xs font-medium flex items-center gap-2">
            <ShieldAlert className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Camp NIF / DNI editable clar i directe */}
        <div className="mb-4">
          <label className="block text-xs font-semibold uppercase tracking-wider text-slate-600 dark:text-slate-300 mb-1.5">
            DNI / NIF de l&apos;Operari
          </label>
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
              <User className="w-4 h-4" />
            </div>
            <input
              type="text"
              required
              value={nif}
              onChange={handleNifChange}
              placeholder="ex: 12345678A"
              className="block w-full pl-9 pr-3 py-2.5 text-base font-mono font-bold uppercase tracking-wider rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-900 dark:text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-emerald-500 shadow-sm"
            />
          </div>
        </div>

        {/* Indicador de Dígits del PIN */}
        <div className="mb-4">
          <p className="text-center text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-2">
            PIN de 4 dígits
          </p>
          <div className="flex justify-center gap-3">
            {[0, 1, 2, 3].map((idx) => (
              <div
                key={idx}
                className={`w-11 h-13 sm:w-12 sm:h-14 rounded-2xl border-2 flex items-center justify-center text-2xl font-bold transition-all ${
                  pin.length > idx
                    ? "border-emerald-500 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 shadow-sm"
                    : "border-slate-300 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-400 dark:text-slate-600"
                }`}
              >
                {pin.length > idx ? "•" : ""}
              </div>
            ))}
          </div>
        </div>

        {/* Numpad Tàctil de Gran Format */}
        <div className="grid grid-cols-3 gap-2 sm:gap-3 w-full pb-2">
          {["1", "2", "3", "4", "5", "6", "7", "8", "9"].map((num) => (
            <button
              key={num}
              type="button"
              disabled={loading}
              onClick={() => handleDigit(num)}
              className="h-14 sm:h-16 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 hover:bg-slate-100 dark:hover:bg-slate-800 active:bg-emerald-600 active:text-white text-2xl font-bold text-slate-800 dark:text-slate-100 shadow-sm transition-all flex items-center justify-center active:scale-95 touch-manipulation"
            >
              {num}
            </button>
          ))}

          <button
            type="button"
            onClick={handleClear}
            className="h-14 sm:h-16 rounded-2xl bg-slate-100 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800 hover:bg-slate-200 dark:hover:bg-slate-800 text-slate-500 dark:text-slate-400 text-sm font-bold transition-colors flex items-center justify-center active:scale-95 touch-manipulation"
          >
            C
          </button>

          <button
            type="button"
            disabled={loading}
            onClick={() => handleDigit("0")}
            className="h-14 sm:h-16 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 hover:bg-slate-100 dark:hover:bg-slate-800 active:bg-emerald-600 active:text-white text-2xl font-bold text-slate-800 dark:text-slate-100 shadow-sm transition-all flex items-center justify-center active:scale-95 touch-manipulation"
          >
            0
          </button>

          <button
            type="button"
            onClick={handleDelete}
            className="h-14 sm:h-16 rounded-2xl bg-slate-100 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800 hover:bg-slate-200 dark:hover:bg-slate-800 text-slate-500 dark:text-slate-400 transition-colors flex items-center justify-center active:scale-95 touch-manipulation"
          >
            <Delete className="w-6 h-6" />
          </button>
        </div>

        {/* Botó directe d'Entrar */}
        <button
          type="button"
          disabled={loading || pin.length !== 4 || !nif.trim()}
          onClick={() => submitLogin(pin)}
          className="w-full mt-2 py-3 px-4 rounded-xl text-sm font-bold text-white bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 shadow-lg shadow-emerald-600/20 transition-all"
        >
          {loading ? "Comprovant accés..." : "Entrar al Terminal"}
          {!loading && <ArrowRight className="w-4 h-4" />}
        </button>
      </div>

      {/* Peu de pàgina: Configuració API */}
      <div className="text-center pt-2 pb-1 max-w-xs mx-auto w-full">
        <button
          type="button"
          onClick={() => setShowConfig(!showConfig)}
          className="text-xs text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 flex items-center justify-center gap-1 mx-auto transition-colors"
        >
          <Settings className="w-3 h-3" />
          <span>Configuració del servidor API</span>
        </button>

        {showConfig && (
          <form onSubmit={handleSaveApiUrl} className="mt-2 w-full space-y-2 text-xs">
            <label className="block font-medium text-slate-600 dark:text-slate-400 text-left">
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
                  className="w-full pl-8 pr-2 py-1.5 border border-slate-300 dark:border-slate-700 rounded-lg bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-200"
                />
              </div>
              <button
                type="submit"
                className="px-3 py-1.5 bg-emerald-600 text-white rounded-lg font-medium hover:bg-emerald-700"
              >
                Desar
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}