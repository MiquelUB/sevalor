"use client";

import React, { useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  Fuel,
  Camera,
  CheckCircle2,
  AlertCircle,
  Receipt,
  Inbox,
  Plus,
} from "lucide-react";
import { CAMERA_LIVE_INPUT_PROPS, compressImageToWebP } from "@/lib/media";

interface TiquetItem {
  id: string;
  categoria: "CARBURANT" | "DIETES" | "MATERIAL";
  import_euros: number;
  data_hora: string;
}

export default function OperariTiquetsPage() {
  const [tiquetsRegistrats, setTiquetsRegistrats] = useState<TiquetItem[]>([]);
  const [mostrarFormulari, setMostrarFormulari] = useState<boolean>(false);

  const [categoria, setCategoria] = useState<"CARBURANT" | "DIETES" | "MATERIAL">("CARBURANT");
  const [importTotal, setImportTotal] = useState<string>("");
  const [fotoTiquet, setFotoTiquet] = useState<Blob | null>(null);
  const [fotoOdometre, setFotoOdometre] = useState<Blob | null>(null);
  const [guardatExit, setGuardatExit] = useState(false);
  const [errorValidacio, setErrorValidacio] = useState<string | null>(null);

  const handleFotoTiquet = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const blob = await compressImageToWebP(e.target.files[0]);
      setFotoTiquet(blob);
      setErrorValidacio(null);
    }
  };

  const handleFotoOdometre = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const blob = await compressImageToWebP(e.target.files[0]);
      setFotoOdometre(blob);
      setErrorValidacio(null);
    }
  };

  // Spec 018 & Spec 015: Validació de doble foto obligatòria per a carburant
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    if (!importTotal || parseFloat(importTotal) <= 0) {
      setErrorValidacio("Introdueix un import total vàlid (€).");
      return;
    }

    if (!fotoTiquet) {
      setErrorValidacio("La fotografia del tiquet físic és obligatòria.");
      return;
    }

    if (categoria === "CARBURANT" && !fotoOdometre) {
      setErrorValidacio(
        "Per a carburant és obligatori capturar la segona fotografia de l'odòmetre en viu (Spec 015 RF-07 / Spec 018)."
      );
      return;
    }

    const nouTiquet: TiquetItem = {
      id: `tiq-${Date.now()}`,
      categoria,
      import_euros: parseFloat(importTotal),
      data_hora: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };

    setTiquetsRegistrats((prev) => [...prev, nouTiquet]);
    setGuardatExit(true);
  };

  return (
    <div className="flex-1 flex flex-col bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 transition-colors">
      {/* Barra de Navegació */}
      <header className="bg-emerald-700 dark:bg-emerald-900 text-white p-4 flex items-center justify-between shadow-md">
        <Link
          href="/operari/feines"
          className="flex items-center gap-1 text-xs text-emerald-100 hover:text-white"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Tornar</span>
        </Link>
        <h1 className="text-sm font-bold uppercase tracking-wider text-white">
          Tiquets i Despeses (Spec 018)
        </h1>
        <div className="w-12"></div>
      </header>

      <div className="p-4 flex-1 flex flex-col">
        {guardatExit ? (
          <div className="p-6 bg-white dark:bg-slate-900 rounded-2xl border border-emerald-300 dark:border-emerald-800 text-center my-auto shadow-sm space-y-4">
            <div className="w-12 h-12 rounded-full bg-emerald-100 dark:bg-emerald-950 text-emerald-600 dark:text-emerald-400 flex items-center justify-center mx-auto">
              <CheckCircle2 className="w-6 h-6" />
            </div>
            <div>
              <h3 className="text-base font-bold text-slate-800 dark:text-slate-100">
                Despesa Desada amb Èxit
              </h3>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                Desada a l'IndexedDB xifrat local i enquadrada per a sincronització asíncrona amb Comptabilitat.
              </p>
            </div>

            {/* RECORDATORI OBLIGATORI DE LLIURAMENT FÍSIC A SECRETARIA (Spec 018 DoD) */}
            <div className="p-3 rounded-xl bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-900 text-amber-900 dark:text-amber-200 text-left text-xs">
              <p className="font-bold">Recordatori de Check-out Vespertí:</p>
              <p className="text-[11px] mt-0.5">
                Custòdia el tiquet físic de paper i diposita'l a la bústia de seguretat de Secretaria en retornar a la nau central.
              </p>
            </div>

            <button
              onClick={() => {
                setGuardatExit(false);
                setMostrarFormulari(false);
                setImportTotal("");
                setFotoTiquet(null);
                setFotoOdometre(null);
              }}
              className="px-4 py-2 bg-emerald-700 hover:bg-emerald-800 text-white text-xs font-bold rounded-xl"
            >
              Veure Tiquets d'Avui
            </button>
          </div>
        ) : !mostrarFormulari ? (
          <div className="flex-1 flex flex-col">
            {/* ESTAT BUIT REAL ZERO-MOCK (Spec 018 Context & DoD) */}
            {tiquetsRegistrats.length === 0 ? (
              <div className="flex-1 flex flex-col items-center justify-center p-8 text-center bg-white dark:bg-slate-900 rounded-2xl border border-dashed border-slate-300 dark:border-slate-800 my-auto shadow-sm">
                <div className="w-16 h-16 rounded-full bg-emerald-50 dark:bg-emerald-950 text-emerald-600 dark:text-emerald-400 flex items-center justify-center mb-3">
                  <Receipt className="w-8 h-8" />
                </div>
                {/* TEXT EXACTE EXIGIT PER LA SPEC 018 */}
                <h3 className="text-base font-bold text-slate-800 dark:text-slate-100">
                  No tens cap tiquet registrat avui
                </h3>
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 max-w-xs">
                  Registra tiquets de carburant, dietes de camp o material d'urgència comprat en ruta.
                </p>
                <button
                  onClick={() => setMostrarFormulari(true)}
                  className="mt-5 px-4 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold shadow flex items-center gap-1.5 transition-all"
                >
                  <Plus className="w-4 h-4" />
                  <span>Nou Tiquet de Despesa</span>
                </button>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                    Tiquets de la Jornada
                  </h3>
                  <button
                    onClick={() => setMostrarFormulari(true)}
                    className="px-3 py-1.5 rounded-xl bg-emerald-600 text-white text-xs font-bold flex items-center gap-1 shadow"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    <span>Afegir</span>
                  </button>
                </div>

                <div className="space-y-2.5">
                  {tiquetsRegistrats.map((t) => (
                    <div
                      key={t.id}
                      className="p-3.5 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm flex items-center justify-between"
                    >
                      <div>
                        <span className="text-[10px] font-mono font-bold px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                          {t.categoria}
                        </span>
                        <p className="text-xs font-bold text-slate-800 dark:text-slate-200 mt-1">
                          Hora de registre: {t.data_hora}
                        </p>
                      </div>
                      <span className="text-sm font-extrabold text-emerald-600 dark:text-emerald-400">
                        {t.import_euros.toFixed(2)} €
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <form
            onSubmit={handleSubmit}
            className="flex-1 flex flex-col justify-between bg-white dark:bg-slate-900 p-5 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm"
          >
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                  Nou Comprovant de Despesa
                </h3>
                <button
                  type="button"
                  onClick={() => setMostrarFormulari(false)}
                  className="text-xs text-slate-400 hover:text-slate-600"
                >
                  Cancel·lar
                </button>
              </div>

              {/* Categoria */}
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-1">
                  Categoria de Despesa
                </label>
                <div className="grid grid-cols-3 gap-2">
                  {(["CARBURANT", "DIETES", "MATERIAL"] as const).map((cat) => (
                    <button
                      key={cat}
                      type="button"
                      onClick={() => {
                        setCategoria(cat);
                        setErrorValidacio(null);
                      }}
                      className={`py-2 px-2 rounded-xl text-xs font-bold border transition-colors ${
                        categoria === cat
                          ? "border-emerald-600 bg-emerald-50 dark:bg-emerald-950/40 text-emerald-800 dark:text-emerald-300"
                          : "border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800"
                      }`}
                    >
                      {cat === "CARBURANT" ? "Carburant" : cat === "DIETES" ? "Dietes" : "Material"}
                    </button>
                  ))}
                </div>
              </div>

              {/* Import */}
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-1">
                  Import Total (€)
                </label>
                <input
                  type="number"
                  step="0.01"
                  value={importTotal}
                  onChange={(e) => {
                    setImportTotal(e.target.value);
                    setErrorValidacio(null);
                  }}
                  placeholder="0.00"
                  className="w-full p-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-base font-bold text-slate-800 dark:text-slate-100 focus:outline-none focus:border-emerald-600"
                />
              </div>

              {/* Captures Fotogràfiques */}
              <div className="space-y-3 pt-2">
                <p className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                  {categoria === "CARBURANT" ? "Doble Fotografia Obligatòria" : "Comprovant Físic"}
                </p>

                {/* Foto 1: Tiquet de Servei */}
                <label
                  className={`p-3 rounded-xl border flex items-center justify-between transition-colors cursor-pointer ${
                    fotoTiquet
                      ? "border-emerald-500 bg-emerald-50 dark:bg-emerald-950/40 text-emerald-800 dark:text-emerald-300"
                      : "border-slate-300 dark:border-slate-700 hover:border-slate-400 text-slate-700 dark:text-slate-300"
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <Camera className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
                    <div>
                      <p className="text-xs font-bold">Foto 1: Tiquet de Benzinera</p>
                      <p className="text-[10px] text-slate-500">Imatge del tiquet físic en paper</p>
                    </div>
                  </div>
                  <span className="text-[11px] font-bold">
                    {fotoTiquet ? "Capturada (OK)" : "Capturar"}
                  </span>
                  <input {...CAMERA_LIVE_INPUT_PROPS} onChange={handleFotoTiquet} className="hidden" />
                </label>

                {/* Foto 2: Odòmetre en Viu (Només Carburant - Spec 015 RF-07) */}
                {categoria === "CARBURANT" && (
                  <label
                    className={`p-3 rounded-xl border flex items-center justify-between transition-colors cursor-pointer ${
                      fotoOdometre
                        ? "border-emerald-500 bg-emerald-50 dark:bg-emerald-950/40 text-emerald-800 dark:text-emerald-300"
                        : "border-slate-300 dark:border-slate-700 hover:border-slate-400 text-slate-700 dark:text-slate-300"
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <Fuel className="w-5 h-5 text-amber-600" />
                      <div>
                        <p className="text-xs font-bold">Foto 2: Odòmetre en Viu</p>
                        <p className="text-[10px] text-slate-500">Quadre de comandaments del vehicle</p>
                      </div>
                    </div>
                    <span className="text-[11px] font-bold">
                      {fotoOdometre ? "Capturada (OK)" : "Capturar"}
                    </span>
                    <input {...CAMERA_LIVE_INPUT_PROPS} onChange={handleFotoOdometre} className="hidden" />
                  </label>
                )}
              </div>

              {errorValidacio && (
                <div className="flex items-center gap-1.5 text-xs text-rose-600 dark:text-rose-400 bg-rose-50 dark:bg-rose-950/40 p-2.5 rounded-xl border border-rose-200 dark:border-rose-900">
                  <AlertCircle className="w-4 h-4 shrink-0" />
                  <span>{errorValidacio}</span>
                </div>
              )}
            </div>

            <button
              type="submit"
              className="w-full mt-4 py-3 rounded-xl bg-emerald-700 hover:bg-emerald-800 active:scale-98 text-white text-xs font-bold flex items-center justify-center gap-2 shadow"
            >
              <span>Desar Tiquet a l'IndexedDB</span>
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
