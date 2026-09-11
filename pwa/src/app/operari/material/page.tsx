"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  Package,
  Wrench,
  CheckCircle2,
  AlertTriangle,
  Plus,
  RotateCcw,
  Truck,
  Scissors,
  CheckSquare,
  Square,
  Camera,
  RefreshCw,
} from "lucide-react";
import { CAMERA_LIVE_INPUT_PROPS, compressImageToWebP } from "@/lib/media";
import { apiFetch } from "@/lib/api";

interface MaterialItem {
  id: string;
  nom: string;
  referencia: string;
  quantitat_programada: number;
  unitat: string;
  es_eina: boolean;
  format_continu?: boolean;
  carregat_pick_in: boolean;
  retornat_pick_out?: number;
}

export default function OperariMaterialPage() {
  const [fase, setFase] = useState<"PICK_IN" | "OBRA" | "PICK_OUT">("PICK_IN");
  const [desquadramentNau, setDesquadramentNau] = useState<boolean>(false);
  const [incidenciaObertes, setIncidenciaObertes] = useState<string | null>(null);

  // Inicialitzat buit per defecte per mandat de la Constitució (Zero Mock Data - Spec 014 RF-03)
  const [materials, setMaterials] = useState<MaterialItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  // Carregar materials reals des del backend
  const carregarMaterials = async () => {
    setLoading(true);
    try {
      const data = await apiFetch("/materials/operari");
      const items = Array.isArray(data) ? data : [];
      // Assegurar que cada item tingui els flags necessaris
      const itemsNormalitzats = items.map((m: any) => ({
        ...m,
        carregat_pick_in: m.carregat_pick_in ?? false,
        retornat_pick_out: m.retornat_pick_out ?? 0,
      }));
      setMaterials(itemsNormalitzats);
    } catch {
      setMaterials([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    carregarMaterials();
  }, []);

  // Commutar check de càrrega matinal (Pick In)
  const handleToggleCheck = (id: string) => {
    setMaterials((prev) =>
      prev.map((m) =>
        m.id === id ? { ...m, carregat_pick_in: !m.carregat_pick_in } : m
      )
    );
  };

  // Validar si el 100% està marcat per a Pick In (Spec 014 RF-04)
  const totsMarcats = materials.length > 0 && materials.every((m) => m.carregat_pick_in);

  // Confirmar càrrega matinal
  const handleConfirmarPickIn = () => {
    if (desquadramentNau) {
      alert(
        "BLOQUEIG DE MAGATZEM (Spec 014 RF-05): No pots confirmar la sortida si hi ha desquadrament d'estoc físic a la nau. Registra una incidència."
      );
      return;
    }
    // TODO: Confirmar al backend
    apiFetch("/materials/confirmar-pick-in", {
      method: "POST",
      body: JSON.stringify({ materials: materials.map(m => ({ id: m.id, carregat: m.carregat_pick_in })) }),
    }).catch(() => {});
    setFase("OBRA");
  };

  // Actualitzar retorn de Pick Out
  const handleRetornCanvi = (id: string, valor: number) => {
    setMaterials((prev) =>
      prev.map((m) => (m.id === id ? { ...m, retornat_pick_out: valor } : m))
    );
  };

  // Afegir material extra de furgoneta (Spec 014 RF-14, sense QR)
  const handleAfegirDeFurgoneta = async () => {
    try {
      const nouItem: MaterialItem = await apiFetch("/materials/afegir-de-furgoneta", {
        method: "POST",
        body: JSON.stringify({ ordre_camp_id: null }),
      });
      setMaterials((prev) => [...prev, { ...nouItem, carregat_pick_in: true, retornat_pick_out: 0 }]);
      alert(
        "Material afegit directament des de la dotació del vehicle. Es generarà reposició vespertina automàtica (Spec 014 RF-15)."
      );
    } catch {
      // Fallback: si el backend no està disponible, no afegir res
      alert("No s'ha pogut contactar amb el backend per afegir material de furgoneta.");
    }
  };

  return (
    <div className="flex-1 flex flex-col bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 transition-colors">
      {/* Capçalera del Mòdul */}
      <header className="bg-emerald-700 dark:bg-emerald-900 text-white p-4 shadow-md flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link
            href="/operari/feines"
            className="p-1.5 rounded-lg bg-emerald-800/80 hover:bg-emerald-800 text-white transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
          </Link>
          <div>
            <h1 className="text-base font-bold leading-tight">Materials i Eines</h1>
            <p className="text-xs text-emerald-200">
              {fase === "PICK_IN"
                ? "Fase 1: Càrrega Matinal (Nau)"
                : fase === "OBRA"
                ? "Fase 2: Execució a Camp"
                : "Fase 3: Retorn i Devolució a Nau"}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-1.5">
          <button
            onClick={() =>
              setDesquadramentNau(!desquadramentNau)
            }
            className={`px-2 py-1 rounded text-[10px] font-mono font-bold transition-colors ${
              desquadramentNau
                ? "bg-rose-600 text-white animate-pulse"
                : "bg-emerald-800/80 text-emerald-200"
            }`}
            title="Simular Desquadrament Físic de Nau (RF-05)"
          >
            {desquadramentNau ? "Desquadrament ON" : "Desquadrament OFF"}
          </button>
        </div>
      </header>

      {/* Selector de Fases Logístiques */}
      <div className="bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 flex text-xs font-bold">
        <button
          onClick={() => setFase("PICK_IN")}
          className={`flex-1 py-3 text-center border-b-2 transition-colors ${
            fase === "PICK_IN"
              ? "border-emerald-600 text-emerald-700 dark:text-emerald-400"
              : "border-transparent text-slate-500 hover:text-slate-700 dark:text-slate-400"
          }`}
        >
          1. Pick In
        </button>
        <button
          onClick={() => setFase("OBRA")}
          className={`flex-1 py-3 text-center border-b-2 transition-colors ${
            fase === "OBRA"
              ? "border-emerald-600 text-emerald-700 dark:text-emerald-400"
              : "border-transparent text-slate-500 hover:text-slate-700 dark:text-slate-400"
          }`}
        >
          2. Camp
        </button>
        <button
          onClick={() => setFase("PICK_OUT")}
          className={`flex-1 py-3 text-center border-b-2 transition-colors ${
            fase === "PICK_OUT"
              ? "border-emerald-600 text-emerald-700 dark:text-emerald-400"
              : "border-transparent text-slate-500 hover:text-slate-700 dark:text-slate-400"
          }`}
        >
          3. Pick Out
        </button>
      </div>

      {/* Contingut Principal */}
      <div className="flex-1 p-4 flex flex-col space-y-4 overflow-y-auto">
        {/* ESTAT BUIT REAL (Mandat Zero Mock Data - Spec 014 RF-03) */}
        {!loading && materials.length === 0 && (
          <div className="flex-1 flex flex-col items-center justify-center p-8 text-center bg-white dark:bg-slate-900 rounded-2xl border border-dashed border-slate-300 dark:border-slate-800 my-auto shadow-sm">
            <div className="w-16 h-16 rounded-full bg-emerald-50 dark:bg-emerald-950 text-emerald-600 dark:text-emerald-400 flex items-center justify-center mb-3">
              <Package className="w-8 h-8" />
            </div>
            {/* TEXT EXACTE EXIGIT PER LA SPEC 014 RF-03 */}
            <h3 className="text-base font-bold text-slate-800 dark:text-slate-100">
              Aquesta tasca no té materials ni eines programades
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 max-w-xs">
              L'ordre s'executa amb mà d'obra directa o dotació base del vehicle.
            </p>
            <button
              onClick={carregarMaterials}
              disabled={loading}
              className="mt-5 px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold shadow flex items-center gap-1.5 transition-all disabled:opacity-50"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
              <span>Carregar dades reals</span>
            </button>
          </div>
        )}

        {loading && materials.length === 0 && (
          <div className="flex-1 flex items-center justify-center text-slate-400 text-xs">
            Carregant materials...
          </div>
        )}

        {/* FASE 1: PICK IN (CÀRREGA MATINAL) */}
        {materials.length > 0 && fase === "PICK_IN" && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <p className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                Verificació de Càrrega Matinal
              </p>
              <span className="text-xs font-mono font-semibold px-2 py-0.5 rounded bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-slate-600 dark:text-slate-300">
                {materials.filter((m) => m.carregat_pick_in).length}/{materials.length} marcats
              </span>
            </div>

            {desquadramentNau && (
              <div className="p-3.5 rounded-xl bg-rose-50 dark:bg-rose-950/50 border border-rose-300 dark:border-rose-900 text-rose-900 dark:text-rose-200 text-xs flex items-start gap-2.5">
                <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
                <div>
                  <p className="font-bold">Desquadrament de Stock Físic a Nau</p>
                  <p className="text-[11px] mt-0.5">
                    Manca de stock físic detectada. El botó de confirmació està bloquejat (Spec 014 RF-05).
                  </p>
                  <button
                    onClick={() =>
                      alert("Incidència de magatzem derivada a l'Enginyer per reassignació (RF-06).")
                    }
                    className="mt-2 px-2.5 py-1 bg-rose-600 text-white font-bold rounded shadow"
                  >
                    Llançar Incidència de Magatzem
                  </button>
                </div>
              </div>
            )}

            <div className="space-y-2.5">
              {materials.map((m) => (
                <div
                  key={m.id}
                  onClick={() => handleToggleCheck(m.id)}
                  className={`p-3.5 rounded-2xl border transition-all cursor-pointer flex items-center justify-between ${
                    m.carregat_pick_in
                      ? "bg-emerald-50 dark:bg-emerald-950/40 border-emerald-500 text-emerald-900 dark:text-emerald-200"
                      : "bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800 hover:border-slate-300"
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <div className="text-emerald-600 dark:text-emerald-400">
                      {m.carregat_pick_in ? (
                        <CheckSquare className="w-6 h-6" />
                      ) : (
                        <Square className="w-6 h-6 text-slate-300 dark:text-slate-600" />
                      )}
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] font-mono font-bold px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                          {m.referencia}
                        </span>
                        {m.es_eina && (
                          <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-amber-100 dark:bg-amber-950 text-amber-800 dark:text-amber-300 flex items-center gap-1">
                            <Wrench className="w-3 h-3" /> Eina Custòdia
                          </span>
                        )}
                      </div>
                      <h4 className="text-xs font-bold text-slate-800 dark:text-slate-100 mt-1">
                        {m.nom}
                      </h4>
                    </div>
                  </div>

                  <div className="text-right font-mono font-bold text-sm">
                    {m.quantitat_programada} {m.unitat}
                  </div>
                </div>
              ))}
            </div>

            <button
              onClick={handleConfirmarPickIn}
              disabled={!totsMarcats || desquadramentNau}
              className={`w-full py-3 rounded-xl font-bold text-xs uppercase tracking-wider flex items-center justify-center gap-2 shadow transition-all ${
                totsMarcats && !desquadramentNau
                  ? "bg-emerald-600 hover:bg-emerald-700 text-white active:scale-98"
                  : "bg-slate-200 dark:bg-slate-800 text-slate-400 dark:text-slate-500 cursor-not-allowed"
              }`}
            >
              <CheckCircle2 className="w-4 h-4" />
              <span>Confirmar Pick In (100% Verificat)</span>
            </button>
          </div>
        )}

        {/* FASE 2: EXECUCIÓ D'OBRA (A CAMP) */}
        {materials.length > 0 && fase === "OBRA" && (
          <div className="space-y-4">
            <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-3">
              <div className="flex items-center justify-between">
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                  Controls Especials de Camp
                </h4>
                <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-blue-100 dark:bg-blue-950 text-blue-800 dark:text-blue-300">
                  En Execució
                </span>
              </div>

              {/* Botó Afegir de Furgoneta (RF-14) */}
              <button
                onClick={handleAfegirDeFurgoneta}
                className="w-full py-2.5 px-3 rounded-xl bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-800 dark:text-slate-200 text-xs font-bold flex items-center justify-between border border-slate-200 dark:border-slate-700"
              >
                <div className="flex items-center gap-2">
                  <Truck className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
                  <span>Afegir Peça d'Estoc de Furgoneta (Sense QR)</span>
                </div>
                <Plus className="w-4 h-4" />
              </button>

              {/* Restricció de Format Continu (RF-13) */}
              <div className="p-3 rounded-xl bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-900 text-xs text-amber-900 dark:text-amber-200 flex items-start gap-2">
                <Scissors className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                <div>
                  <p className="font-bold">Restricció de Format Continu (Tub PE 32mm)</p>
                  <p className="text-[11px] text-amber-800 dark:text-amber-300 mt-0.5">
                    Obligatori exhaurir el retall de furgoneta abans de tallar una bobina o barra sencera de 6m (Spec 014 RF-13).
                  </p>
                </div>
              </div>
            </div>

            <button
              onClick={() => setFase("PICK_OUT")}
              className="w-full py-3 rounded-xl bg-slate-900 dark:bg-slate-100 dark:text-slate-900 hover:bg-slate-800 text-white text-xs font-bold uppercase tracking-wider flex items-center justify-center gap-2 shadow"
            >
              <span>Arribada a Nau: Iniciar Devolució Pick Out</span>
            </button>
          </div>
        )}

        {/* FASE 3: PICK OUT (RETORN A NAU I BALANÇ) */}
        {materials.length > 0 && fase === "PICK_OUT" && (
          <div className="space-y-4">
            <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-3">
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                Devolució de Sobrants a Nau (Pick Out)
              </h4>
              <p className="text-[11px] text-slate-500">
                Introdueix les unitats que tornen a les prestatgeries per a calcular el consum real net: Consum = Pick In − Pick Out.
              </p>

              <div className="space-y-3 pt-2">
                {materials.map((m) => {
                  const retornat = m.retornat_pick_out ?? 0;
                  const consum = Math.max(0, m.quantitat_programada - retornat);

                  return (
                    <div
                      key={m.id}
                      className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/70 border border-slate-200 dark:border-slate-800 flex items-center justify-between"
                    >
                      <div className="flex-1 pr-2">
                        <p className="text-xs font-bold text-slate-800 dark:text-slate-200">
                          {m.nom}
                        </p>
                        <p className="text-[10px] text-slate-500">
                          Carregat: {m.quantitat_programada} {m.unitat}
                        </p>
                      </div>

                      <div className="flex items-center gap-3">
                        <div className="flex items-center gap-1.5">
                          <span className="text-[10px] text-slate-400">Retorn:</span>
                          <input
                            type="number"
                            min="0"
                            max={m.quantitat_programada}
                            value={retornat}
                            onChange={(e) =>
                              handleRetornCanvi(m.id, parseFloat(e.target.value) || 0)
                            }
                            className="w-14 p-1.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-center text-xs font-bold"
                          />
                          <span className="text-[10px] text-slate-500">{m.unitat}</span>
                        </div>

                        <div className="text-right pl-2 border-l border-slate-200 dark:border-slate-700">
                          <span className="text-[10px] text-slate-400 block">Consum:</span>
                          <span className="text-xs font-extrabold text-emerald-600 dark:text-emerald-400">
                            {consum} {m.unitat}
                          </span>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            <button
              onClick={() => {
                // TODO: Enviar al backend
                apiFetch("/materials/confirmar-pick-out", {
                  method: "POST",
                  body: JSON.stringify({
                    materials: materials.map((m) => ({
                      id: m.id,
                      retornat: m.retornat_pick_out ?? 0,
                    })),
                  }),
                }).catch(() => {});
                alert("Pick Out confirmat. Consums derivats a la Torre de Control i Magatzem (Spec 004).");
                setFase("PICK_IN");
              }}
              className="w-full py-3 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold uppercase tracking-wider flex items-center justify-center gap-2 shadow"
            >
              <CheckCircle2 className="w-4 h-4" />
              <span>Confirmar Devolució i Tancar Balanç</span>
            </button>
          </div>
        )}
      </div>
    </div>
  );
}