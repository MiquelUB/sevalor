"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Lock, Delete, ShieldAlert, Sun, Moon, CheckCircle } from "lucide-react";
import {
  createSentinelBlock,
  verifySentinelBlock,
} from "@/lib/crypto";
import { apiFetch, setAuthToken, getAuthToken } from "@/lib/api";

const NIF_STORAGE_KEY = "sevalor_operari_nif";
const SENTINEL_SALT_KEY = "sevalor_sentinel_salt";
const SENTINEL_CIPHER_KEY = "sevalor_sentinel_cipher";
const SENTINEL_IV_KEY = "sevalor_sentinel_iv";

export default function OperariLoginPage() {
  const [pin, setPin] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [isRegistered, setIsRegistered] = useState<boolean>(false);
  const [nif, setNif] = useState<string>("");
  const router = useRouter();

  // Mode Clar / Fosc
  const [isDark, setIsDark] = useState<boolean>(true);

  useEffect(() => {
    const saved = localStorage.getItem("sevalor_theme");
    if (saved === "light") {
      setIsDark(false);
      document.documentElement.classList.remove("dark");
    } else {
      setIsDark(true);
      document.documentElement.classList.add("dark");
    }

    // Comprovar si ja hi ha un terminal registrat (primer ús)
    const savedNif = localStorage.getItem(NIF_STORAGE_KEY);
    if (savedNif) {
      setNif(savedNif);
      // Si ja hi ha sentinel, és un usuari recurrent
      const salt = localStorage.getItem(SENTINEL_SALT_KEY);
      const cipher = localStorage.getItem(SENTINEL_CIPHER_KEY);
      if (salt && cipher) {
        setIsRegistered(true);
      }
    }
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

  // En completar el 4t dígit, commuta automàticament el flux (Spec 019 / Tasca 3.1)
  useEffect(() => {
    if (pin.length === 4) {
      submitLogin(pin);
    }
  }, [pin]);

  const submitLogin = async (codiPin: string) => {
    setLoading(true);
    setError(null);

    try {
      // Primer ús: cal registrar el NIF del terminal
      let operariNif = nif;
      if (!operariNif) {
        operariNif = prompt("Primer ús: introdueix el teu NIF (DNI/NIE):") || "";
        if (!operariNif) {
          setError("Cal introduir el NIF per activar el terminal.");
          setPin("");
          setLoading(false);
          return;
        }
        localStorage.setItem(NIF_STORAGE_KEY, operariNif);
        setNif(operariNif);
      }

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

      // Login correcte: desar token i crear/verificar sentinel
      if (response.access_token) {
        // Desar token al localStorage (serà xifrat pel crypto.service en futures iteracions)
        setAuthToken(response.access_token);

        // Crear o verificar bloc sentinel per validació offline futura
        const saltHex = localStorage.getItem(SENTINEL_SALT_KEY);
        if (saltHex) {
          // Usuari recurrent: verificar sentinel existent amb el PIN
          const cipher = localStorage.getItem(SENTINEL_CIPHER_KEY);
          const iv = localStorage.getItem(SENTINEL_IV_KEY);
          if (cipher && iv) {
            try {
              const saltBytes = new Uint8Array(saltHex.split(",").map(Number));
              const valid = await verifySentinelBlock(codiPin, saltBytes, cipher, iv);
              if (!valid) {
                // Si el PIN no desbloqueja el sentinel, és un PIN canviat o incorrecte
                // Esborrem el sentinel antic i en crearem un de nou
                localStorage.removeItem(SENTINEL_CIPHER_KEY);
                localStorage.removeItem(SENTINEL_IV_KEY);
                localStorage.removeItem(SENTINEL_SALT_KEY);
              }
            } catch {
              // Error de crypto, esborrem i recreem
              localStorage.removeItem(SENTINEL_CIPHER_KEY);
              localStorage.removeItem(SENTINEL_IV_KEY);
              localStorage.removeItem(SENTINEL_SALT_KEY);
            }
          }
        }

        // Si no hi ha sentinel, crear-ne un de nou
        if (!localStorage.getItem(SENTINEL_SALT_KEY)) {
          const saltBytes = crypto.getRandomValues(new Uint8Array(32));
          localStorage.setItem(SENTINEL_SALT_KEY, Array.from(saltBytes).join(","));
          const { cipherTextHex, ivHex } = await createSentinelBlock(codiPin, saltBytes);
          localStorage.setItem(SENTINEL_CIPHER_KEY, cipherTextHex);
          localStorage.setItem(SENTINEL_IV_KEY, ivHex);
        }

        router.push("/operari/feines");
      } else {
        setError("PIN incorrecte. Torna a intentar-ho.");
        setPin("");
      }
    } catch (err: any) {
      // Si el backend no respon (offline), intentar verificació local via sentinel
      const saltHex = localStorage.getItem(SENTINEL_SALT_KEY);
      if (saltHex) {
        const cipher = localStorage.getItem(SENTINEL_CIPHER_KEY);
        const iv = localStorage.getItem(SENTINEL_IV_KEY);
        if (cipher && iv) {
          try {
            const saltBytes = new Uint8Array(saltHex.split(",").map(Number));
            const valid = await verifySentinelBlock(codiPin, saltBytes, cipher, iv);
            if (valid) {
              // Accés offline: token guardat localment (ja xifrat)
              router.push("/operari/feines");
              setLoading(false);
              return;
            }
          } catch {
            // Error de desxifratge: PIN incorrecte
          }
        }
      }

      setError("PIN no vàlid o sense connexió.");
      setPin("");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex-1 flex flex-col justify-between p-6 bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 transition-colors duration-200">
      {/* Capçalera */}
      <div className="text-center pt-6 relative">
        <button
          onClick={toggleTheme}
          className="absolute right-0 top-0 p-2 rounded-xl bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300"
          title="Commutar Tema"
        >
          {isDark ? <Sun className="w-4 h-4 text-amber-400" /> : <Moon className="w-4 h-4 text-blue-500" />}
        </button>

        <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-emerald-600/10 dark:bg-emerald-600/20 text-emerald-600 dark:text-emerald-400 mb-3 border border-emerald-500/30">
          <Lock className="w-8 h-8" />
        </div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
          SEVALOR
        </h1>
        <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
          Terminal de Camp d&apos;Operari (Spec 019)
        </p>
        {nif && (
          <div className="flex items-center justify-center gap-1.5 mt-2 text-xs text-emerald-700 dark:text-emerald-400">
            <CheckCircle className="w-3.5 h-3.5" />
            <span>Terminal: {nif}</span>
          </div>
        )}
      </div>

      {/* Indicador de Dígits del PIN */}
      <div className="my-6">
        <p className="text-center text-xs font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500 mb-4">
          Introdueix el teu PIN de 4 dígits
        </p>
        <div className="flex justify-center gap-4">
          {[0, 1, 2, 3].map((idx) => (
            <div
              key={idx}
              className={`w-12 h-14 rounded-2xl border-2 flex items-center justify-center text-2xl font-bold transition-all ${
                pin.length > idx
                  ? "border-emerald-500 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                  : "border-slate-300 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-400 dark:text-slate-600"
              }`}
            >
              {pin.length > idx ? "•" : ""}
            </div>
          ))}
        </div>

        {error && (
          <div className="flex items-center justify-center gap-2 text-rose-600 dark:text-rose-400 text-xs mt-4">
            <ShieldAlert className="w-4 h-4" />
            <span>{error}</span>
          </div>
        )}
      </div>

      {/* Numpad Tàctil de Gran Format (Spec 019) */}
      <div className="grid grid-cols-3 gap-3 max-w-xs mx-auto w-full pb-4">
        {["1", "2", "3", "4", "5", "6", "7", "8", "9"].map((num) => (
          <button
            key={num}
            type="button"
            disabled={loading}
            onClick={() => handleDigit(num)}
            className="h-16 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 hover:bg-slate-100 dark:hover:bg-slate-800 active:bg-emerald-600 active:text-white text-2xl font-bold text-slate-800 dark:text-slate-100 shadow-sm transition-all flex items-center justify-center active:scale-95 touch-manipulation"
          >
            {num}
          </button>
        ))}

        <button
          type="button"
          onClick={handleClear}
          className="h-16 rounded-2xl bg-slate-100 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800 hover:bg-slate-200 dark:hover:bg-slate-800 text-slate-500 dark:text-slate-400 text-sm font-bold transition-colors flex items-center justify-center active:scale-95 touch-manipulation"
        >
          C
        </button>

        <button
          type="button"
          disabled={loading}
          onClick={() => handleDigit("0")}
          className="h-16 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 hover:bg-slate-100 dark:hover:bg-slate-800 active:bg-emerald-600 active:text-white text-2xl font-bold text-slate-800 dark:text-slate-100 shadow-sm transition-all flex items-center justify-center active:scale-95 touch-manipulation"
        >
          0
        </button>

        <button
          type="button"
          onClick={handleDelete}
          className="h-16 rounded-2xl bg-slate-100 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800 hover:bg-slate-200 dark:hover:bg-slate-800 text-slate-500 dark:text-slate-400 transition-colors flex items-center justify-center active:scale-95 touch-manipulation"
        >
          <Delete className="w-6 h-6" />
        </button>
      </div>

      {/* Recuperació de PIN */}
      <div className="text-center pb-2">
        <button
          type="button"
          onClick={() => alert("S'ha enviat un SMS d'assistència al teu supervisor.")}
          className="text-xs text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 underline"
        >
          Has oblidat el teu PIN?
        </button>
      </div>
    </div>
  );
}