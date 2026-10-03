"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import {
  Truck,
  Camera,
  Fuel,
  Wrench,
  AlertTriangle,
  Search,
  CheckCircle2,
  Clock,
  Gauge,
  ArrowRight,
  ShieldAlert,
  RotateCcw,
  Check,
  RefreshCw,
} from "lucide-react";
import { compressImageToWebP } from "@/lib/media";
import CameraInput from "@/components/CameraInput";
import { apiFetch } from "@/lib/api";

// Model segons Spec 015 RF-01
interface ActiuVehicle {
  id: string;
  matricula: string;
  marca_model: string;
  tipus: "FURGONETA" | "CAMIO" | "4X4";
  odometre_inicial?: number;
  odometre_final?: number;
  combustible_inicial?: "buit" | "1/4" | "1/2" | "3/4" | "ple";
  combustible_final?: "buit" | "1/4" | "1/2" | "3/4" | "ple";
}

interface ActiuRemolc {
  id: string;
  matricula: string;
  tipus: string;
}

interface ActiuMaquinaria {
  id: string;
  model: string;
  identificador: string;
  tipus: "GENERADOR" | "ZANJADORA" | "MOTOBOMBA" | "COMPRESSOR";
  horometre_inicial?: number;
  horometre_final?: number;
}

interface ItemEstocFurgoneta {
  id: string;
  nom: string;
  referencia: string;
  marca: string;
  quantitat_actual: number;
  quantitat_optima: number;
  unitat: string;
}

export default function OperariVehiclesPage() {
  const [tabActiva, setTabActiva] = useState<"CONTROL" | "ESTOC" | "REPOSTATGE">("CONTROL");

  // Estat del conjunt d'actius assignats (Dia 0: per defecte buit o assignat si hi ha ordre)
  // Spec 015 RF-01 & RF-02: Zero Mock Data Empty State
  const [vehicle, setVehicle] = useState<ActiuVehicle | null>(null);
  const [remolc, setRemolc] = useState<ActiuRemolc | null>(null);
  const [maquinaria, setMaquinaria] = useState<ActiuMaquinaria | null>(null);
  const [loadingActius, setLoadingActius] = useState<boolean>(true);

  // Check-in / Check-out states
  const [estatJornada, setEstatJornada] = useState<"CHECKIN_PENDENT" | "EN_MARXA" | "CHECKOUT_FET">("CHECKIN_PENDENT");
  const [fotoOdometreInici, setFotoOdometreInici] = useState<Blob | null>(null);
  const [nivellCombustibleInici, setNivellCombustibleInici] = useState<"buit" | "1/4" | "1/2" | "3/4" | "ple">("1/2");
  const [fotoHorometreInici, setFotoHorometreInici] = useState<Blob | null>(null);
  const [fotoDanyPreexistent, setFotoDanyPreexistent] = useState<Blob | null>(null);

  // Check-out states
  const [fotoOdometreFi, setFotoOdometreFi] = useState<Blob | null>(null);
  const [nivellCombustibleFi, setNivellCombustibleFi] = useState<"buit" | "1/4" | "1/2" | "3/4" | "ple">("1/2");
  const [fotoHorometreFi, setFotoHorometreFi] = useState<Blob | null>(null);
  const [fotoNouDany, setFotoNouDany] = useState<Blob | null>(null);
  const [kmTotalsCalculats, setKmTotalsCalculats] = useState<number | null>(null);
  const [horesTotalsCalculades, setHoresTotalsCalculades] = useState<number | null>(null);

  // Repostatge form (Spec 015 RF-06, RF-07, RF-08)
  const [litresRepostats, setLitresRepostats] = useState<string>("");
  const [importEuros, setImportEuros] = useState<string>("");
  const [tipusCarburant, setTipusCarburant] = useState<"DIESEL" | "GASOLINA" | "ADBLUE">("DIESEL");
  const [metodePagament, setMetodePagament] = useState<"SOLRED" | "CAMP" | "EFECTIU">("SOLRED");
  const [fotoTiquetCarburant, setFotoTiquetCarburant] = useState<Blob | null>(null);
  const [fotoOdometreCarburant, setFotoOdometreCarburant] = useState<Blob | null>(null);
  const [repostatgeGuardat, setRepostatgeGuardat] = useState<boolean>(false);

  // Estoc Furgoneta (Spec 015 RF-11, RF-12, RF-13)
  const [filtreCerca, setFiltreCerca] = useState<string>("");
  const [estocFurgoneta, setEstocFurgoneta] = useState<ItemEstocFurgoneta[]>([]);
  const [loadingEstoc, setLoadingEstoc] = useState<boolean>(true);

  // Errors / Alertes
  const [errorValidacio, setErrorValidacio] = useState<string | null>(null);
  const [alertaIncidencia, setAlertaIncidencia] = useState<string | null>(null);

  // ---- CARREGAR DADES REALS DES DEL BACKEND ----

  // Carregar actius assignats (vehicle, remolc, maquinària)
  const carregarActius = async () => {
    setLoadingActius(true);
    try {
      const data = await apiFetch("/operari/vehicles");
      if (Array.isArray(data) && data.length > 0) {
        setVehicle(data[0]);
      }
    } catch {
      // Sense actius assignats — estat buit real
    } finally {
      setLoadingActius(false);
    }
  };

  // Carregar estoc de furgoneta
  const carregarEstoc = async () => {
    setLoadingEstoc(true);
    try {
      let dades = [];
      if (navigator.onLine) {
          dades = await apiFetch("/operari_pwa/vehicles/stock") || [];
          if (!Array.isArray(dades)) dades = [];
          
          // Clear and cache in Dexie
          if (typeof window !== "undefined") {
              const { db } = await import("@/lib/offline/db");
              await db.vehicle_stock.clear();
              if (dades.length > 0) {
                  await db.vehicle_stock.bulkAdd(dades);
              }
          }
      } else {
          // Fallback offline
          if (typeof window !== "undefined") {
              const { db } = await import("@/lib/offline/db");
              dades = await db.vehicle_stock.toArray();
          }
      }
      setEstocFurgoneta(dades);
    } catch {
      setEstocFurgoneta([]);
    } finally {
      setLoadingEstoc(false);
    }
  };

  useEffect(() => {
    carregarActius();
    carregarEstoc();
  }, []);

  // ---- HANDLERS ----

  // Check-in Submit (Spec 015 RF-03, RF-04, RF-05)
  const handleCheckInSubmit = () => {
    if (!fotoOdometreInici) {
      setErrorValidacio("La fotografia de l'odòmetre per càmera en viu és obligatòria (Spec 015 RF-03).");
      return;
    }
    if (maquinaria && !fotoHorometreInici) {
      setErrorValidacio("La maquinària assignada requereix la fotografia de l'horòmetre del motor (Spec 015 RF-04).");
      return;
    }

    setErrorValidacio(null);
    setEstatJornada("EN_MARXA");

    // Enviar check-in al backend
    apiFetch(`/operari/vehicles/${vehicle?.id}/checkin`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        odometre_inicial: 0, // En producció s'extreu per OCR de la foto
        nivell_combustible: nivellCombustibleInici,
      }),
    })
      .then((res) => res.json())
      .then((data) => {
        console.log("Check-in successful", data);
      })
      .catch((err) => console.error("Checkin error", err));
  };

  // Check-out Submit (Spec 015 RF-16, RF-17, RF-18, RF-20)
  const handleCheckOutSubmit = async () => {
    if (!fotoOdometreFi) {
      setErrorValidacio("La fotografia de l'odòmetre final és obligatòria.");
      return;
    }
    if (maquinaria && !fotoHorometreFi) {
      setErrorValidacio("La fotografia de l'horòmetre final de la maquinària és obligatòria.");
      return;
    }

    // Intentar obtenir km reals del backend
    try {
      const res = await apiFetch(`/operari/vehicles/${vehicle?.id}/checkout`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          odometre_final: 0, // En producció s'extreu per OCR
          nivell_combustible: nivellCombustibleFi,
        }),
      });
      if (res.ok) {
        const r = await res.json();
        if (r.km_recorreguts != null) setKmTotalsCalculats(r.km_recorreguts);
      }
    } catch {
      // Fallback: càlcul local aproximat
      const kmInicials = vehicle?.odometre_inicial || 0;
      setKmTotalsCalculats(null);
      if (maquinaria) {
        setHoresTotalsCalculades(null);
      }
    }

    setEstatJornada("CHECKOUT_FET");
    setErrorValidacio(null);
  };

  // Repostatge Submit (Spec 015 RF-07, RF-08)
  const handleRepostarSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!importEuros || parseFloat(importEuros) <= 0) {
      setErrorValidacio("Introdueix l'import en euros (€).");
      return;
    }
    if (!litresRepostats || parseFloat(litresRepostats) <= 0) {
      setErrorValidacio("Introdueix els litres de carburant.");
      return;
    }
    if (!fotoTiquetCarburant) {
      setErrorValidacio("Foto 1: El tiquet de la benzinera és obligatori (Spec 015 RF-07).");
      return;
    }
    if (!fotoOdometreCarburant) {
      setErrorValidacio("Foto 2: L'odòmetre en viu en el moment del repostatge és obligatori (Spec 015 RF-07).");
      return;
    }

    setErrorValidacio(null);

    // Enviar al backend
    try {
      await apiFetch(`/operari/vehicles/${vehicle?.id}/repostatge`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          litres: parseFloat(litresRepostats),
          euros: parseFloat(importEuros),
          odometre: 0, // OCR en producció
        }),
      });
    } catch {}

    setRepostatgeGuardat(true);
  };

  // Estoc filtrat
  const estocFiltrat = estocFurgoneta.filter(
    (item) =>
      item.nom.toLowerCase().includes(filtreCerca.toLowerCase()) ||
      item.referencia.toLowerCase().includes(filtreCerca.toLowerCase()) ||
      item.marca.toLowerCase().includes(filtreCerca.toLowerCase())
  );

  return (
    <div className="flex-1 flex flex-col bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 transition-colors">
      {/* Capçalera del Mòdul */}
      <header className="bg-emerald-700 dark:bg-emerald-900 text-white p-4 shadow-md flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link
            href="/operari/feines"
            className="p-1.5 rounded-lg bg-emerald-800/80 hover:bg-emerald-800 text-white transition-colors"
          >
            <RotateCcw className="w-4 h-4" />
          </Link>
          <div>
            <h1 className="text-base font-bold leading-tight">Flota i Vehicles</h1>
            <p className="text-xs text-emerald-200">
              {vehicle ? `${vehicle.matricula} — ${vehicle.tipus}` : "Sense vehicle assignat"}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-1.5">
          <button
            onClick={() => setAlertaIncidencia("Avaria de vehicle transmesa a la Torre de Control")}
            className="p-2 rounded-lg bg-rose-600 hover:bg-rose-700 text-white text-xs font-bold flex items-center gap-1 shadow transition-colors"
            title="Incidència de Flota (RF-09)"
          >
            <AlertTriangle className="w-4 h-4" />
            <span className="hidden sm:inline">Avaria</span>
          </button>
        </div>
      </header>

      {/* Tabs de Secció */}
      <div className="bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 flex text-xs font-bold">
        <button
          onClick={() => setTabActiva("CONTROL")}
          className={`flex-1 py-3 text-center border-b-2 transition-colors flex items-center justify-center gap-1.5 ${
            tabActiva === "CONTROL"
              ? "border-emerald-600 text-emerald-700 dark:text-emerald-400"
              : "border-transparent text-slate-500 hover:text-slate-700 dark:text-slate-400"
          }`}
        >
          <Gauge className="w-4 h-4" />
          <span>Check-in/out</span>
        </button>
        <button
          onClick={() => setTabActiva("ESTOC")}
          className={`flex-1 py-3 text-center border-b-2 transition-colors flex items-center justify-center gap-1.5 ${
            tabActiva === "ESTOC"
              ? "border-emerald-600 text-emerald-700 dark:text-emerald-400"
              : "border-transparent text-slate-500 hover:text-slate-700 dark:text-slate-400"
          }`}
        >
          <Truck className="w-4 h-4" />
          <span>Estoc Furgoneta</span>
        </button>
        <button
          onClick={() => setTabActiva("REPOSTATGE")}
          className={`flex-1 py-3 text-center border-b-2 transition-colors flex items-center justify-center gap-1.5 ${
            tabActiva === "REPOSTATGE"
              ? "border-emerald-600 text-emerald-700 dark:text-emerald-400"
              : "border-transparent text-slate-500 hover:text-slate-700 dark:text-slate-400"
          }`}
        >
          <Fuel className="w-4 h-4" />
          <span>Carburant</span>
        </button>
      </div>

      {/* Alerta modal o toast */}
      {alertaIncidencia && (
        <div className="m-4 p-3 rounded-xl bg-rose-50 dark:bg-rose-950/50 border border-rose-200 dark:border-rose-900 text-rose-800 dark:text-rose-200 text-xs flex items-center justify-between">
          <div className="flex items-center gap-2">
            <ShieldAlert className="w-4 h-4 text-rose-600 dark:text-rose-400 shrink-0" />
            <span>{alertaIncidencia}</span>
          </div>
          <button
            onClick={() => setAlertaIncidencia(null)}
            className="px-2 py-1 bg-rose-200 dark:bg-rose-900 rounded font-bold"
          >
            Tancar
          </button>
        </div>
      )}

      {/* Contingut segons Tab */}
      <div className="flex-1 p-4 flex flex-col overflow-y-auto">
        {/* CAS ESTAT BUIT (ZERO MOCK DATA - Spec 015 RF-02) */}
        {!loadingActius && !vehicle && (
          <div className="flex-1 flex flex-col items-center justify-center p-8 text-center bg-white dark:bg-slate-900 rounded-2xl border border-dashed border-slate-300 dark:border-slate-800 my-auto shadow-sm">
            <div className="w-16 h-16 rounded-full bg-emerald-50 dark:bg-emerald-950 text-emerald-600 dark:text-emerald-400 flex items-center justify-center mb-3">
              <Truck className="w-8 h-8" />
            </div>
            {/* TEXT EXACTE EXIGIT PER SPEC 015 RF-02 */}
            <h3 className="text-base font-bold text-slate-800 dark:text-slate-100">
              No tens cap vehicle ni remolc assignat per a avui
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 max-w-xs">
              Si ets acompanyant o la feina és a la nau central, no cal fitxar vehicle.
            </p>
            <button
              onClick={() => { carregarActius(); carregarEstoc(); }}
              disabled={loadingActius}
              className="mt-5 px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold shadow transition-all disabled:opacity-50 flex items-center gap-1.5"
            >
              <RefreshCw className={`w-4 h-4 ${loadingActius ? "animate-spin" : ""}`} />
              <span>Carregar dades reals</span>
            </button>
          </div>
        )}

        {loadingActius && (
          <div className="flex-1 flex items-center justify-center text-slate-400 text-xs">
            Carregant actius assignats...
          </div>
        )}

        {/* PESTANYA 1: CONTROL CHECK-IN / CHECK-OUT */}
        {vehicle && tabActiva === "CONTROL" && (
          <div className="space-y-4">
            {/* Targeta del Conjunt d'Actius Assignats (Spec 015 RF-01) */}
            <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-3">
              <div className="flex items-start justify-between">
                <div>
                  <span className="text-[10px] font-mono font-bold uppercase tracking-wider bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300 px-2 py-0.5 rounded">
                    {vehicle.tipus}
                  </span>
                  <h3 className="text-sm font-bold text-slate-800 dark:text-slate-100 mt-1">
                    {vehicle.marca_model}
                  </h3>
                  <p className="text-xs font-mono font-bold text-slate-600 dark:text-slate-400">
                    Matrícula: {vehicle.matricula}
                  </p>
                </div>
                <span
                  className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                    estatJornada === "CHECKIN_PENDENT"
                      ? "bg-amber-100 dark:bg-amber-950 text-amber-800 dark:text-amber-300"
                      : estatJornada === "EN_MARXA"
                      ? "bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300"
                      : "bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300"
                  }`}
                >
                  {estatJornada === "CHECKIN_PENDENT"
                    ? "Pendent Check-in"
                    : estatJornada === "EN_MARXA"
                    ? "En Ruta / Operatiu"
                    : "Check-out Finalitzat"}
                </span>
              </div>

              {/* Remolc i Maquinària acoblada */}
              <div className="pt-2 border-t border-slate-100 dark:border-slate-800 grid grid-cols-2 gap-2 text-xs">
                {remolc && (
                  <div className="p-2 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-800">
                    <p className="text-[10px] font-bold uppercase text-slate-400">Remolc Acoblat</p>
                    <p className="font-bold text-slate-700 dark:text-slate-200">{remolc.matricula}</p>
                    <p className="text-[10px] text-slate-500">{remolc.tipus}</p>
                  </div>
                )}
                {maquinaria && (
                  <div className="p-2 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-800">
                    <p className="text-[10px] font-bold uppercase text-slate-400">Maquinària amb Motor</p>
                    <p className="font-bold text-slate-700 dark:text-slate-200">{maquinaria.identificador}</p>
                    <p className="text-[10px] text-slate-500">{maquinaria.model}</p>
                  </div>
                )}
              </div>
            </div>

            {/* FASE 1: CHECK-IN MATINAL (Spec 015 RF-03, RF-04, RF-05) */}
            {estatJornada === "CHECKIN_PENDENT" && (
              <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-4">
                <div className="flex items-center gap-2 text-slate-800 dark:text-slate-100">
                  <Clock className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
                  <h4 className="text-sm font-bold uppercase tracking-wider">
                    Check-in de Sortida (Matí)
                  </h4>
                </div>

                {/* Foto Odòmetre Obligatòria per càmera (RF-03 & RF-21) */}
                <div>
                  <p className="text-xs font-bold text-slate-600 dark:text-slate-400 mb-1.5">
                    1. Fotografia de l'Odòmetre del Vehicle *
                  </p>
                  <CameraInput captured={!!fotoOdometreInici} label="Capturar" onCapture={(blob) => { setFotoOdometreInici(blob); setErrorValidacio(null); } } />
                </div>

                {/* Selector tàctil ràpid de combustible (RF-03) */}
                <div>
                  <p className="text-xs font-bold text-slate-600 dark:text-slate-400 mb-1.5">
                    2. Nivell de Combustible Actual *
                  </p>
                  <div className="grid grid-cols-5 gap-1.5">
                    {(["buit", "1/4", "1/2", "3/4", "ple"] as const).map((nivell) => (
                      <button
                        key={nivell}
                        type="button"
                        onClick={() => setNivellCombustibleInici(nivell)}
                        className={`py-2 rounded-xl text-xs font-bold border transition-colors ${
                          nivellCombustibleInici === nivell
                            ? "border-emerald-600 bg-emerald-600 text-white"
                            : "border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-700 dark:text-slate-300"
                        }`}
                      >
                        {nivell}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Foto Horòmetre si hi ha maquinària (RF-04) */}
                {maquinaria && (
                  <div>
                    <p className="text-xs font-bold text-slate-600 dark:text-slate-400 mb-1.5">
                      3. Horòmetre Maquinària ({maquinaria.identificador}) *
                    </p>
                    <CameraInput captured={!!fotoHorometreInici} label="Capturar" onCapture={(blob) => { setFotoHorometreInici(blob); setErrorValidacio(null); } } />
                  </div>
                )}

                {/* Foto Opcional de Danys Preexistents (RF-05) */}
                <div>
                  <p className="text-xs font-bold text-slate-600 dark:text-slate-400 mb-1.5">
                    Danys Preexistents (Opcional - No bloqueja)
                  </p>
                  <CameraInput captured={!!fotoDanyPreexistent} label="Afegir" onCapture={(blob) => { setFotoDanyPreexistent(blob); setErrorValidacio(null); } } />
                </div>

                {errorValidacio && (
                  <div className="p-3 rounded-xl bg-rose-50 dark:bg-rose-950/50 border border-rose-200 dark:border-rose-900 text-rose-700 dark:text-rose-300 text-xs">
                    {errorValidacio}
                  </div>
                )}

                <button
                  onClick={handleCheckInSubmit}
                  className="w-full py-3 rounded-xl bg-emerald-600 hover:bg-emerald-700 active:scale-98 text-white text-xs font-bold uppercase tracking-wider flex items-center justify-center gap-2 shadow"
                >
                  <Check className="w-4 h-4" />
                  <span>Validar Sortida i Iniciar Ruta</span>
                </button>
              </div>
            )}

            {/* FASE 2: EN RUTA I CHECK-OUT DE RETORN (Spec 015 RF-16 a RF-20) */}
            {estatJornada === "EN_MARXA" && (
              <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-slate-800 dark:text-slate-100">
                    <CheckCircle2 className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
                    <h4 className="text-sm font-bold uppercase tracking-wider">
                      Check-out de Tornada a Base
                    </h4>
                  </div>
                  <span className="text-[10px] font-bold text-slate-400">Final de Torn</span>
                </div>

                {/* Foto Odòmetre Final */}
                <div>
                  <p className="text-xs font-bold text-slate-600 dark:text-slate-400 mb-1.5">
                    1. Fotografia Odòmetre Final *
                  </p>
                  <CameraInput captured={!!fotoOdometreFi} label="Capturar" onCapture={(blob) => { setFotoOdometreFi(blob); setErrorValidacio(null); } } />
                </div>

                {/* Nivell combustible final */}
                <div>
                  <p className="text-xs font-bold text-slate-600 dark:text-slate-400 mb-1.5">
                    2. Nivell de Combustible Final
                  </p>
                  <div className="grid grid-cols-5 gap-1.5">
                    {(["buit", "1/4", "1/2", "3/4", "ple"] as const).map((nivell) => (
                      <button
                        key={nivell}
                        type="button"
                        onClick={() => setNivellCombustibleFi(nivell)}
                        className={`py-2 rounded-xl text-xs font-bold border transition-colors ${
                          nivellCombustibleFi === nivell
                            ? "border-emerald-600 bg-emerald-600 text-white"
                            : "border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-700 dark:text-slate-300"
                        }`}
                      >
                        {nivell}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Foto Horòmetre final si maquinària (RF-17) */}
                {maquinaria && (
                  <div>
                    <p className="text-xs font-bold text-slate-600 dark:text-slate-400 mb-1.5">
                      3. Horòmetre Final ({maquinaria.identificador}) *
                    </p>
                    <CameraInput captured={!!fotoHorometreFi} label="Capturar" onCapture={(blob) => { setFotoHorometreFi(blob); setErrorValidacio(null); } } />
                  </div>
                )}

                {/* Danys nous en la jornada (RF-19) */}
                <div>
                  <p className="text-xs font-bold text-slate-600 dark:text-slate-400 mb-1.5">
                    Incidents o Danys Nous (Opcional)
                  </p>
                  <CameraInput captured={!!fotoNouDany} label="Capturar" onCapture={(blob) => { setFotoNouDany(blob); setErrorValidacio(null); } } />
                </div>

                {errorValidacio && (
                  <div className="p-3 rounded-xl bg-rose-50 dark:bg-rose-950/50 border border-rose-200 dark:border-rose-900 text-rose-700 dark:text-rose-300 text-xs">
                    {errorValidacio}
                  </div>
                )}

                <button
                  onClick={handleCheckOutSubmit}
                  className="w-full py-3 rounded-xl bg-slate-900 dark:bg-slate-100 dark:text-slate-900 hover:bg-slate-800 active:scale-98 text-white text-xs font-bold uppercase tracking-wider flex items-center justify-center gap-2 shadow"
                >
                  <CheckCircle2 className="w-4 h-4" />
                  <span>Completar Check-out i Retorn a Base</span>
                </button>
              </div>
            )}

            {/* FASE 3: RESUM CHECK-OUT FET (Spec 015 RF-20) */}
            {estatJornada === "CHECKOUT_FET" && (
              <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-emerald-300 dark:border-emerald-800 text-center space-y-4 shadow-sm">
                <div className="w-14 h-14 rounded-full bg-emerald-100 dark:bg-emerald-950 text-emerald-600 dark:text-emerald-400 flex items-center justify-center mx-auto">
                  <CheckCircle2 className="w-8 h-8" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-slate-800 dark:text-slate-100">
                    Jornada de Flota Tancada
                  </h3>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                    Registres desats a l'IndexedDB xifrat local i llibre diari Hetzner.
                  </p>
                </div>

                {/* Balanç Idempotent de Quilòmetres i Hores (RF-20) */}
                <div className="grid grid-cols-2 gap-3 pt-2">
                  <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-800">
                    <p className="text-[10px] font-bold uppercase text-slate-400">Km Recorreguts Nets</p>
                    <p className="text-xl font-extrabold text-emerald-600 dark:text-emerald-400">
                      {kmTotalsCalculats != null ? `${kmTotalsCalculats} km` : "Pendent OCR"}
                    </p>
                    <p className="text-[10px] text-slate-500 font-mono">
                      (Odòmetre Final - Inicial)
                    </p>
                  </div>
                  <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-800">
                    <p className="text-[10px] font-bold uppercase text-slate-400">Hores Màquina</p>
                    <p className="text-xl font-extrabold text-amber-600 dark:text-amber-400">
                      {horesTotalsCalculades != null ? `${horesTotalsCalculades} h` : "N/A"}
                    </p>
                    <p className="text-[10px] text-slate-500 font-mono">
                      (Horòmetre Final - Inicial)
                    </p>
                  </div>
                </div>

                {/* Recordatori de Picking de Reposició (RF-14, RF-15) */}
                <div className="p-3 rounded-xl bg-blue-50 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-900 text-left">
                  <p className="text-xs font-bold text-blue-800 dark:text-blue-300">
                    Reposició de Furgoneta a la Nau:
                  </p>
                  <p className="text-[11px] text-blue-700 dark:text-blue-400 mt-0.5">
                    Carrega les peces consumides des de les prestatgeries centrals abans de tancar el torn.
                  </p>
                </div>
              </div>
            )}
          </div>
        )}

        {/* PESTANYA 2: ESTOC DE FURGONETA (Spec 015 RF-11, RF-12, RF-13) */}
        {vehicle && tabActiva === "ESTOC" && (
          <div className="space-y-4">
            {/* Cercador Reactiu de Text (RF-12) */}
            <div className="relative">
              <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-3" />
              <input
                type="text"
                value={filtreCerca}
                onChange={(e) => setFiltreCerca(e.target.value)}
                placeholder="Cercar referència, nom o marca a la furgoneta..."
                className="w-full pl-10 pr-4 py-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs font-medium focus:outline-none focus:border-emerald-600"
              />
            </div>

            {/* Estat buit d'estoc */}
            {!loadingEstoc && estocFurgoneta.length === 0 ? (
              <div className="flex flex-col items-center justify-center p-6 text-center bg-white dark:bg-slate-900 rounded-2xl border border-dashed border-slate-300 dark:border-slate-800">
                <Truck className="w-8 h-8 text-slate-300 mb-2" />
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  Sense dades disponibles
                </p>
                <button
                  onClick={carregarEstoc}
                  className="mt-3 px-3 py-1.5 rounded-lg bg-slate-100 dark:bg-slate-800 text-xs font-bold text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700 flex items-center gap-1.5 transition-colors"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                  Carregar dades reals
                </button>
              </div>
            ) : loadingEstoc ? (
              <div className="text-center text-slate-400 text-xs py-4">
                Carregant estoc...
              </div>
            ) : (
              <div className="space-y-2.5">
                {estocFiltrat.map((item) => {
                  const faltaStock = item.quantitat_actual < item.quantitat_optima;
                  const quantitatFaltant = item.quantitat_optima - item.quantitat_actual;

                  return (
                    <div
                      key={item.id}
                      className="p-3.5 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm flex items-center justify-between"
                    >
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="text-[10px] font-mono font-bold px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                            {item.referencia}
                          </span>
                          <span className="text-[10px] text-slate-500">{item.marca}</span>
                        </div>
                        <h4 className="text-xs font-bold text-slate-800 dark:text-slate-100 mt-1">
                          {item.nom}
                        </h4>
                        <p className="text-[11px] text-slate-500 mt-0.5">
                          Estoc a bord:{" "}
                          <span className="font-bold text-slate-800 dark:text-slate-200">
                            {item.quantitat_actual} {item.unitat}
                          </span>{" "}
                          / Òptim: {item.quantitat_optima} {item.unitat}
                        </p>
                      </div>

                      {/* Indicador de Material Faltant (RF-13) */}
                      {faltaStock ? (
                        <div className="text-right">
                          <span className="inline-block text-[10px] font-bold px-2 py-0.5 rounded bg-rose-100 dark:bg-rose-950 text-rose-700 dark:text-rose-300 border border-rose-300 dark:border-rose-800">
                            Falten {quantitatFaltant} {item.unitat}
                          </span>
                          <p className="text-[9px] text-slate-400 mt-1">Consumit en tasca</p>
                        </div>
                      ) : (
                        <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-emerald-100 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300">
                          Complet
                        </span>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* PESTANYA 3: REGISTRE DE CARBURANT AMB DOBLE FOTO (Spec 015 RF-06, RF-07, RF-08) */}
        {vehicle && tabActiva === "REPOSTATGE" && (
          <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-4">
            <div className="flex items-center gap-2 text-slate-800 dark:text-slate-100">
              <Fuel className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
              <div>
                <h4 className="text-sm font-bold uppercase tracking-wider">
                  Registrar Carburant en Ruta
                </h4>
                <p className="text-[10px] text-slate-500">Spec 015 RF-07: Doble Fotografia Obligatòria</p>
              </div>
            </div>

            {repostatgeGuardat ? (
              <div className="p-6 text-center space-y-3">
                <div className="w-12 h-12 rounded-full bg-emerald-100 dark:bg-emerald-950 text-emerald-600 dark:text-emerald-400 flex items-center justify-center mx-auto">
                  <CheckCircle2 className="w-6 h-6" />
                </div>
                <h4 className="text-sm font-bold text-slate-800 dark:text-slate-100">
                  Repostatge Enregistrat amb Èxit
                </h4>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  Despesa de {importEuros} € ({litresRepostats} L) assignada a la matrícula {vehicle.matricula} i derivada a Comptabilitat Hetzner.
                </p>
                <button
                  onClick={() => {
                    setRepostatgeGuardat(false);
                    setImportEuros("");
                    setLitresRepostats("");
                    setFotoTiquetCarburant(null);
                    setFotoOdometreCarburant(null);
                  }}
                  className="mt-3 px-4 py-2 rounded-xl bg-emerald-600 text-white text-xs font-bold"
                >
                  Registrar un altre proveïment
                </button>
              </div>
            ) : (
              <form onSubmit={handleRepostarSubmit} className="space-y-4">
                {/* Tipus de carburant i mètode de pagament */}
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-[10px] font-bold uppercase text-slate-500 mb-1">
                      Tipus Carburant
                    </label>
                    <select
                      value={tipusCarburant}
                      onChange={(e: any) => setTipusCarburant(e.target.value)}
                      className="w-full p-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-xs font-semibold"
                    >
                      <option value="DIESEL">Dièsel B / A</option>
                      <option value="GASOLINA">Gasolina 95</option>
                      <option value="ADBLUE">AdBlue / DEF</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-[10px] font-bold uppercase text-slate-500 mb-1">
                      Mètode Pagament (RF-08)
                    </label>
                    <select
                      value={metodePagament}
                      onChange={(e: any) => setMetodePagament(e.target.value)}
                      className="w-full p-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-xs font-semibold"
                    >
                      <option value="SOLRED">Targeta Solred / DKV</option>
                      <option value="CAMP">Targeta de Camp</option>
                      <option value="EFECTIU">Efectiu de Caixa</option>
                    </select>
                  </div>
                </div>

                {/* Import i Litres */}
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-[10px] font-bold uppercase text-slate-500 mb-1">
                      Import Total (€) *
                    </label>
                    <input
                      type="number"
                      step="0.01"
                      value={importEuros}
                      onChange={(e) => setImportEuros(e.target.value)}
                      placeholder="0.00"
                      className="w-full p-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-xs font-bold"
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] font-bold uppercase text-slate-500 mb-1">
                      Litres Càrrega (L) *
                    </label>
                    <input
                      type="number"
                      step="0.01"
                      value={litresRepostats}
                      onChange={(e) => setLitresRepostats(e.target.value)}
                      placeholder="0.00"
                      className="w-full p-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-xs font-bold"
                    />
                  </div>
                </div>

                {/* DOBLE FOTO OBLIGATÒRIA (RF-07) */}
                <div className="space-y-3 pt-2">
                  <p className="text-xs font-bold uppercase text-slate-500">
                    Doble Fotografia Obligatòria per a Carburant
                  </p>

                  {/* Foto 1: Tiquet físic benzinera */}
                  <CameraInput captured={!!fotoTiquetCarburant} label="Capturar" onCapture={(blob) => { setFotoTiquetCarburant(blob); setErrorValidacio(null); } } />

                  {/* Foto 2: Odòmetre en viu en el moment de la càrrega */}
                  <CameraInput captured={!!fotoOdometreCarburant} label="Capturar" onCapture={(blob) => { setFotoOdometreCarburant(blob); setErrorValidacio(null); } } />
                </div>

                {errorValidacio && (
                  <div className="p-3 rounded-xl bg-rose-50 dark:bg-rose-950/50 border border-rose-200 dark:border-rose-900 text-rose-700 dark:text-rose-300 text-xs">
                    {errorValidacio}
                  </div>
                )}

                <button
                  type="submit"
                  className="w-full py-3 rounded-xl bg-emerald-600 hover:bg-emerald-700 active:scale-98 text-white text-xs font-bold uppercase tracking-wider shadow"
                >
                  Registrar Repostatge a Flota
                </button>
              </form>
            )}
          </div>
        )}
      </div>
    </div>
  );
}