"use client";

import React, { useState, useEffect } from "react";
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
  RefreshCw,
  X,
} from "lucide-react";
import { apiFetch } from "@/lib/api";
import { CAMERA_LIVE_INPUT_PROPS, compressImageToWebP } from "@/lib/media";

interface TiquetItem {
  id: string;
  vehicle_id?: string;
  operari_id: string;
  litres: number;
  import_euros: number;
  odometre_valor: number;
  estat_ocr: string;
  created_at?: string;
}

export default function OperariTiquetsPage() {
  const [tiquetsRegistrats, setTiquetsRegistrats] = useState<TiquetItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [mostrarFormulari, setMostrarFormulari] = useState<boolean>(false);

  const [categoria, setCategoria] = useState<"CARBURANT" | "DIETES" | "MATERIAL">("CARBURANT");
  const [importTotal, setImportTotal] = useState<string>("");
  const [litres, setLitres] = useState<string>("35.0");
  const [odometre, setOdometre] = useState<string>("125400");
  const [fotoTiquet, setFotoTiquet] = useState<Blob | null>(null);
  const [fotoOdometre, setFotoOdometre] = useState<Blob | null>(null);
  const [guardant, setGuardant] = useState(false);
  const [errorValidacio, setErrorValidacio] = useState<string | null>(null);

  const carregarTiquets = async () => {
    setLoading(true);
    try {
      const data = await apiFetch<TiquetItem[]>("/operari/tiquets");
      setTiquetsRegistrats(data || []);
    } catch {
      setTiquetsRegistrats([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    carregarTiquets();
  }, []);

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

  // Validació de doble foto obligatòria per a carburant (Spec 015 RF-07 / Spec 018)
  const handleSubmit = async (e: React.FormEvent) => {
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

    setGuardant(true);
    setErrorValidacio(null);

    try {
      await apiFetch<TiquetItem>("/operari/tiquets", {
        method: "POST",
        body: JSON.stringify({
          litres: parseFloat(litres) || 30.0,
          import_euros: parseFloat(importTotal),
          odometre_valor: parseInt(odometre, 10) || 100000,
          tiquet_foto_path: "/docs/tiquets/ticket_operari_live.webp",
          odometre_foto_path: "/docs/tiquets/odometre_operari_live.webp",
        }),
      });
      setMostrarFormulari(false);
      setImportTotal("");
      setFotoTiquet(null);
      setFotoOdometre(null);
      await carregarTiquets();
    } catch (err: any) {
      setErrorValidacio(err.message || "Error al desar el tiquet a la base de dades");
    } finally {
      setGuardant(false);
    }
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
        <button
          onClick={carregarTiquets}
          className="p-1 text-emerald-200 hover:text-white"
          title="Refrescar llista"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
        </button>
      </header>

      <div className="p-4 flex-1 flex flex-col overflow-y-auto">
        {mostrarFormulari ? (
          <form
            onSubmit={handleSubmit}
            className="bg-white dark:bg-slate-900 p-5 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-4"
          >
            <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-3">
              <h2 className="text-sm font-bold text-slate-800 dark:text-slate-100 flex items-center gap-2">
                <Receipt className="w-4 h-4 text-emerald-600" />
                Registrar Nova Despesa
              </h2>
              <button
                type="button"
                onClick={() => setMostrarFormulari(false)}
                className="p-1 text-slate-400 hover:text-slate-600"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-500 mb-1">
                Tipus de Despesa
              </label>
              <select
                value={categoria}
                onChange={(e) => setCategoria(e.target.value as any)}
                className="w-full p-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-xs font-semibold"
              >
                <option value="CARBURANT">Carburant / Repostatge (Doble Foto Obligatòria)</option>
                <option value="DIETES">Dietes i Manutenció</option>
                <option value="MATERIAL">Compra d'Urgència Material</option>
              </select>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-500 mb-1">
                  Import Total (€) *
                </label>
                <input
                  type="number"
                  step="0.01"
                  required
                  placeholder="0.00"
                  value={importTotal}
                  onChange={(e) => setImportTotal(e.target.value)}
                  className="w-full p-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm font-bold font-mono"
                />
              </div>

              {categoria === "CARBURANT" && (
                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-slate-500 mb-1">
                    Litres Subministrats
                  </label>
                  <input
                    type="number"
                    step="0.1"
                    placeholder="35.0"
                    value={litres}
                    onChange={(e) => setLitres(e.target.value)}
                    className="w-full p-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm font-mono"
                  />
                </div>
              )}
            </div>

            {categoria === "CARBURANT" && (
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-500 mb-1">
                  Quilometratge Actual Odòmetre (km)
                </label>
                <input
                  type="number"
                  placeholder="125400"
                  value={odometre}
                  onChange={(e) => setOdometre(e.target.value)}
                  className="w-full p-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-xs font-mono"
                />
              </div>
            )}

            {/* Captura fotogràfica */}
            <div className="space-y-2">
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-500">
                Fotos de Justificant
              </label>
              <div className="grid grid-cols-2 gap-3">
                <label className="p-3 border-2 border-dashed border-slate-300 dark:border-slate-700 rounded-xl flex flex-col items-center justify-center text-center cursor-pointer hover:border-emerald-500 transition-colors">
                  <Camera className="w-5 h-5 text-emerald-600 mb-1" />
                  <span className="text-[10px] font-bold text-slate-700 dark:text-slate-300">
                    {fotoTiquet ? "Tiquet capturat ✓" : "Foto Tiquet (Viu)"}
                  </span>
                  <input
                    {...CAMERA_LIVE_INPUT_PROPS}
                    onChange={handleFotoTiquet}
                    className="hidden"
                  />
                </label>

                {categoria === "CARBURANT" && (
                  <label className="p-3 border-2 border-dashed border-slate-300 dark:border-slate-700 rounded-xl flex flex-col items-center justify-center text-center cursor-pointer hover:border-emerald-500 transition-colors">
                    <Fuel className="w-5 h-5 text-emerald-600 mb-1" />
                    <span className="text-[10px] font-bold text-slate-700 dark:text-slate-300">
                      {fotoOdometre ? "Odòmetre capturat ✓" : "Foto Odòmetre"}
                    </span>
                    <input
                      {...CAMERA_LIVE_INPUT_PROPS}
                      onChange={handleFotoOdometre}
                      className="hidden"
                    />
                  </label>
                )}
              </div>
            </div>

            {errorValidacio && (
              <div className="p-3 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900 text-rose-700 dark:text-rose-300 text-xs flex items-center gap-2">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>{errorValidacio}</span>
              </div>
            )}

            <button
              type="submit"
              disabled={guardant}
              className="w-full py-3 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold flex items-center justify-center gap-2 shadow disabled:opacity-50"
            >
              <Receipt className="w-4 h-4" />
              <span>{guardant ? "Desant tiquet a la BD..." : "Desar i Validar Despesa"}</span>
            </button>
          </form>
        ) : (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-xs font-bold uppercase tracking-wider text-slate-500">
                Tiquets Registrats Aquest Mes
              </h2>
              <button
                onClick={() => setMostrarFormulari(true)}
                className="px-3 py-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold flex items-center gap-1 shadow transition-all"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Afegir Tiquet</span>
              </button>
            </div>

            {loading && tiquetsRegistrats.length === 0 ? (
              <div className="p-8 text-center text-slate-400 text-xs">
                <RefreshCw className="w-5 h-5 animate-spin text-emerald-600 mx-auto mb-2" />
                <span>Carregant tiquets...</span>
              </div>
            ) : tiquetsRegistrats.length === 0 ? (
              <div className="p-8 text-center bg-white dark:bg-slate-900 rounded-2xl border border-dashed border-slate-200 dark:border-slate-800 space-y-2">
                <Inbox className="w-10 h-10 mx-auto text-slate-300 dark:text-slate-700" />
                <h3 className="text-sm font-bold text-slate-700 dark:text-slate-300">
                  Sense tiquets registrats
                </h3>
                <p className="text-xs text-slate-400 max-w-xs mx-auto">
                  Estat Dia-0: Captura els rebuts de carburant i dietes per a la liquidació automàtica.
                </p>
                <button
                  onClick={() => setMostrarFormulari(true)}
                  className="mt-2 px-3 py-1.5 bg-emerald-600 text-white rounded-xl text-xs font-bold"
                >
                  + Donar d'Alta Primer Tiquet
                </button>
              </div>
            ) : (
              <div className="space-y-2">
                {tiquetsRegistrats.map((tiq) => (
                  <div
                    key={tiq.id}
                    className="p-3.5 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm flex items-center justify-between"
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-9 h-9 rounded-lg bg-emerald-50 dark:bg-emerald-950/50 text-emerald-600 flex items-center justify-center">
                        <Fuel className="w-4 h-4" />
                      </div>
                      <div>
                        <p className="text-xs font-bold text-slate-900 dark:text-white">
                          Carburant ({tiq.litres} L)
                        </p>
                        <p className="text-[10px] text-slate-400 font-mono">
                          Odòmetre: {tiq.odometre_valor} km • {tiq.estat_ocr}
                        </p>
                      </div>
                    </div>
                    <span className="text-sm font-black font-mono text-emerald-600 dark:text-emerald-400">
                      {tiq.import_euros?.toFixed(2)} €
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
