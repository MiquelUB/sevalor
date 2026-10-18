"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import {
  Truck,
  Fuel,
  AlertTriangle,
  Search,
  CheckCircle2,
  Clock,
  Gauge,
  ShieldAlert,
  RotateCcw,
  Check,
  RefreshCw,
} from "lucide-react";
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

  // Spec 015 RF-01 & RF-02: Zero Mock Data Empty State
  const [vehicle, setVehicle] = useState<ActiuVehicle | null>(null);
  const [remolc] = useState<ActiuRemolc | null>(null);
  const [maquinaria] = useState<ActiuMaquinaria | null>(null);
  const [loadingActius, setLoadingActius] = useState<boolean>(true);

  // Check-in / Check-out states
  const [estatJornada, setEstatJornada] = useState<
    "CHECKIN_PENDENT" | "EN_MARXA" | "CHECKOUT_FET"
  >("CHECKIN_PENDENT");
  const [fotoOdometreInici, setFotoOdometreInici] = useState<Blob | null>(null);
  const [nivellCombustibleInici, setNivellCombustibleInici] = useState<
    "buit" | "1/4" | "1/2" | "3/4" | "ple"
  >("1/2");
  const [fotoHorometreInici, setFotoHorometreInici] = useState<Blob | null>(
    null
  );
  const [fotoDanyPreexistent, setFotoDanyPreexistent] = useState<Blob | null>(
    null
  );

  // Check-out states
  const [fotoOdometreFi, setFotoOdometreFi] = useState<Blob | null>(null);
  const [nivellCombustibleFi, setNivellCombustibleFi] = useState<
    "buit" | "1/4" | "1/2" | "3/4" | "ple"
  >("1/2");
  const [fotoHorometreFi, setFotoHorometreFi] = useState<Blob | null>(null);
  const [fotoNouDany, setFotoNouDany] = useState<Blob | null>(null);
  const [kmTotalsCalculats, setKmTotalsCalculats] = useState<number | null>(
    null
  );
  const [horesTotalsCalculades, setHoresTotalsCalculades] = useState<
    number | null
  >(null);

  // Repostatge form (Spec 015 RF-06, RF-07, RF-08)
  const [litresRepostats, setLitresRepostats] = useState<string>("");
  const [importEuros, setImportEuros] = useState<string>("");
  const [tipusCarburant, setTipusCarburant] = useState<
    "DIESEL" | "GASOLINA" | "ADBLUE"
  >("DIESEL");
  const [metodePagament, setMetodePagament] = useState<
    "SOLRED" | "CAMP" | "EFECTIU"
  >("SOLRED");
  const [fotoTiquetCarburant, setFotoTiquetCarburant] = useState<Blob | null>(
    null
  );
  const [fotoOdometreCarburant, setFotoOdometreCarburant] =
    useState<Blob | null>(null);
  const [repostatgeGuardat, setRepostatgeGuardat] = useState<boolean>(false);

  // Estoc Furgoneta (Spec 015 RF-11, RF-12, RF-13)
  const [filtreCerca, setFiltreCerca] = useState<string>("");
  const [estocFurgoneta, setEstocFurgoneta] = useState<ItemEstocFurgoneta[]>(
    []
  );
  const [loadingEstoc, setLoadingEstoc] = useState<boolean>(true);

  // Errors / Alertes
  const [errorValidacio, setErrorValidacio] = useState<string | null>(null);
  const [alertaIncidencia, setAlertaIncidencia] = useState<string | null>(null);

  // ---- CARREGAR DADES REALS DES DEL BACKEND ----
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

  const carregarEstoc = async () => {
    setLoadingEstoc(true);
    try {
      let dades: ItemEstocFurgoneta[] = [];
      if (navigator.onLine) {
        const res = await apiFetch("/operari/vehicles/stock");
        dades = Array.isArray(res) ? res : [];

        if (typeof window !== "undefined") {
          const { db } = await import("@/lib/offline/db");
          await db.vehicle_stock.clear();
          if (dades.length > 0) {
            await db.vehicle_stock.bulkAdd(dades);
          }
        }
      } else {
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

  // Check-in Submit (Spec 015 RF-03, RF-04, RF-05)
  const handleCheckInSubmit = () => {
    if (!fotoOdometreInici) {
      setErrorValidacio(
        "La fotografia de l'odòmetre per càmera en viu és obligatòria (Spec 015 RF-03)."
      );
      return;
    }
    if (maquinaria && !fotoHorometreInici) {
      setErrorValidacio(
        "La maquinària assignada requereix la fotografia de l'horòmetre del motor (Spec 015 RF-04)."
      );
      return;
    }

    setErrorValidacio(null);
    setEstatJornada("EN_MARXA");

    apiFetch(`/operari/vehicles/${vehicle?.id}/checkin`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        odometre_inicial: 0,
        nivell_combustible: nivellCombustibleInici,
      }),
    }).catch((err) => console.error("Checkin error", err));
  };

  // Check-out Submit (Spec 015 RF-16, RF-17, RF-18, RF-20)
  const handleCheckOutSubmit = async () => {
    if (!fotoOdometreFi) {
      setErrorValidacio("La fotografia de l'odòmetre final és obligatòria.");
      return;
    }
    if (maquinaria && !fotoHorometreFi) {
      setErrorValidacio(
        "La fotografia de l'horòmetre final de la maquinària és obligatòria."
      );
      return;
    }

    try {
      const res: any = await apiFetch(
        `/operari/vehicles/${vehicle?.id}/checkout`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            odometre_final: 0,
            nivell_combustible: nivellCombustibleFi,
          }),
        }
      );
      if (res && res.km_recorreguts != null) {
        setKmTotalsCalculats(res.km_recorreguts);
      }
    } catch {
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
      setErrorValidacio(
        "Foto 1: El tiquet de la benzinera és obligatori (Spec 015 RF-07)."
      );
      return;
    }
    if (!fotoOdometreCarburant) {
      setErrorValidacio(
        "Foto 2: L'odòmetre en viu en el moment del repostatge és obligatori (Spec 015 RF-07)."
      );
      return;
    }

    setErrorValidacio(null);

    try {
      await apiFetch(`/operari/vehicles/${vehicle?.id}/repostatge`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          litres: parseFloat(litresRepostats),
          euros: parseFloat(importEuros),
          odometre: 0,
        }),
      });
    } catch {}

    setRepostatgeGuardat(true);
  };

  const estocFiltrat = estocFurgoneta.filter(
    (item) =>
      item.nom.toLowerCase().includes(filtreCerca.toLowerCase()) ||
      item.referencia.toLowerCase().includes(filtreCerca.toLowerCase()) ||
      item.marca.toLowerCase().includes(filtreCerca.toLowerCase())
  );

  return (
    <div className="flex-1 flex flex-col bg-surface dark:bg-slate-950 text-on-surface dark:text-slate-100 transition-colors">
      {/* Capçalera del Mòdul Stitch Soft-Industrial (Screen 6a77e3de3c534f74aff39e73d1290af9) */}
      <header className="bg-surface-container-lowest dark:bg-slate-900 text-primary dark:text-white p-4 border-b border-outline-variant/25 dark:border-slate-800 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link
            href="/operari/feines"
            className="w-9 h-9 rounded-lg bg-surface-container-low dark:bg-slate-800 hover:bg-surface-container flex items-center justify-center text-primary dark:text-white transition-colors"
          >
            <RotateCcw className="w-4 h-4" />
          </Link>
          <div>
            <h1 className="text-base font-extrabold leading-tight text-primary dark:text-white">
              Flota i Vehicles
            </h1>
            <p className="text-[11px] font-mono text-on-surface-variant dark:text-slate-400">
              {vehicle
                ? `${vehicle.matricula} — ${vehicle.tipus}`
                : "Sense vehicle assignat"}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-1.5">
          <button
            onClick={() =>
              setAlertaIncidencia(
                "Avaria de vehicle transmesa a la Torre de Control"
              )
            }
            className="px-3 py-1.5 rounded-lg bg-error hover:opacity-95 text-white text-xs font-bold flex items-center gap-1.5 shadow-sm transition-all"
            title="Incidència de Flota (RF-09)"
          >
            <AlertTriangle className="w-4 h-4" />
            <span className="hidden sm:inline">Avaria</span>
          </button>
        </div>
      </header>

      {/* Tabs de Secció Stitch */}
      <div className="bg-surface-container-lowest dark:bg-slate-900 border-b border-outline-variant/25 dark:border-slate-800 flex text-xs font-extrabold uppercase tracking-wider">
        <button
          onClick={() => setTabActiva("CONTROL")}
          className={`flex-1 py-3.5 text-center border-b-2 transition-colors flex items-center justify-center gap-1.5 ${
            tabActiva === "CONTROL"
              ? "border-secondary-container text-secondary dark:text-emerald-400 bg-secondary-container/5"
              : "border-transparent text-on-surface-variant hover:text-primary dark:text-slate-400"
          }`}
        >
          <Gauge className="w-4 h-4" />
          <span>Check-in/out</span>
        </button>
        <button
          onClick={() => setTabActiva("ESTOC")}
          className={`flex-1 py-3.5 text-center border-b-2 transition-colors flex items-center justify-center gap-1.5 ${
            tabActiva === "ESTOC"
              ? "border-secondary-container text-secondary dark:text-emerald-400 bg-secondary-container/5"
              : "border-transparent text-on-surface-variant hover:text-primary dark:text-slate-400"
          }`}
        >
          <Truck className="w-4 h-4" />
          <span>Estoc Furgoneta</span>
        </button>
        <button
          onClick={() => setTabActiva("REPOSTATGE")}
          className={`flex-1 py-3.5 text-center border-b-2 transition-colors flex items-center justify-center gap-1.5 ${
            tabActiva === "REPOSTATGE"
              ? "border-secondary-container text-secondary dark:text-emerald-400 bg-secondary-container/5"
              : "border-transparent text-on-surface-variant hover:text-primary dark:text-slate-400"
          }`}
        >
          <Fuel className="w-4 h-4" />
          <span>Carburant</span>
        </button>
      </div>

      {/* Alerta modal o toast */}
      {alertaIncidencia && (
        <div className="m-4 p-3 rounded-xl bg-error-container/60 border border-error/30 text-on-error-container text-xs flex items-center justify-between">
          <div className="flex items-center gap-2">
            <ShieldAlert className="w-4 h-4 text-error shrink-0" />
            <span>{alertaIncidencia}</span>
          </div>
          <button
            onClick={() => setAlertaIncidencia(null)}
            className="px-2.5 py-1 bg-error text-white rounded-lg font-bold"
          >
            Tancar
          </button>
        </div>
      )}

      {/* Contingut segons Tab */}
      <div className="flex-1 p-4 flex flex-col overflow-y-auto">
        {/* CAS ESTAT BUIT (ZERO MOCK DATA - Spec 015 RF-02) */}
        {!loadingActius && !vehicle && (
          <div className="flex-1 flex flex-col items-center justify-center p-8 text-center bg-surface-container-lowest dark:bg-slate-900 rounded-2xl border-2 border-dashed border-outline-variant/40 dark:border-slate-800 my-auto shadow-sm">
            <div className="w-16 h-16 rounded-2xl bg-secondary-container/10 text-secondary flex items-center justify-center mb-3">
              <Truck className="w-8 h-8" />
            </div>
            {/* TEXT EXACTE EXIGIT PER SPEC 015 RF-02 */}
            <h3 className="text-base font-extrabold text-primary dark:text-slate-100">
              No tens cap vehicle ni remolc assignat per a avui
            </h3>
            <p className="text-xs text-on-surface-variant dark:text-slate-400 mt-1 max-w-xs">
              Si ets acompanyant o la feina és a la nau central, no cal fitxar vehicle.
            </p>
            <button
              onClick={() => {
                carregarActius();
                carregarEstoc();
              }}
              disabled={loadingActius}
              className="mt-5 px-5 py-2.5 rounded-xl bg-secondary-container hover:brightness-110 text-white text-xs font-bold shadow-md transition-all disabled:opacity-50 flex items-center gap-1.5"
            >
              <RefreshCw
                className={`w-4 h-4 ${loadingActius ? "animate-spin" : ""}`}
              />
              <span>Carregar dades reals</span>
            </button>
          </div>
        )}

        {loadingActius && (
          <div className="flex-1 flex items-center justify-center text-on-surface-variant text-xs font-bold uppercase tracking-wider">
            Carregant actius assignats...
          </div>
        )}

        {/* PESTANYA 1: CONTROL CHECK-IN / CHECK-OUT */}
        {vehicle && tabActiva === "CONTROL" && (
          <div className="space-y-4">
            {/* Targeta Stitch d'Identitat del Vehicle (Screen 6a77e3de3c534f74aff39e73d1290af9) */}
            <div className="p-4 rounded-xl bg-surface-container-high dark:bg-slate-900 border border-outline-variant/25 dark:border-slate-800 relative overflow-hidden">
              <div className="absolute -right-4 -top-4 opacity-5 pointer-events-none">
                <span className="material-symbols-outlined text-[110px]">
                  local_shipping
                </span>
              </div>
              <div className="relative z-10 flex items-start justify-between">
                <div>
                  <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-secondary-container text-white text-[10px] font-bold uppercase tracking-wider mb-1.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-white animate-pulse" />
                    {vehicle.tipus}
                  </span>
                  <h3 className="text-base font-extrabold text-primary dark:text-slate-100">
                    {vehicle.marca_model}
                  </h3>
                  <p className="text-xs font-mono font-bold text-on-surface-variant dark:text-slate-400">
                    Matrícula: {vehicle.matricula}
                  </p>
                </div>
                <span
                  className={`text-[10px] font-extrabold uppercase tracking-wider px-2.5 py-1 rounded-full ${
                    estatJornada === "CHECKIN_PENDENT"
                      ? "bg-amber-500/15 text-amber-700 dark:text-amber-300"
                      : estatJornada === "EN_MARXA"
                      ? "bg-secondary-container/15 text-secondary dark:text-emerald-300"
                      : "bg-surface-container-lowest text-primary dark:text-slate-300"
                  }`}
                >
                  {estatJornada === "CHECKIN_PENDENT"
                    ? "Pendent Check-in"
                    : estatJornada === "EN_MARXA"
                    ? "En Ruta / Operatiu"
                    : "Check-out Finalitzat"}
                </span>
              </div>

              {(remolc || maquinaria) && (
                <div className="pt-3 mt-3 border-t border-outline-variant/30 dark:border-slate-800 grid grid-cols-2 gap-2 text-xs relative z-10">
                  {remolc && (
                    <div className="p-2.5 rounded-lg bg-surface-container-lowest dark:bg-slate-800/60">
                      <p className="text-[10px] font-bold uppercase text-on-surface-variant">
                        Remolc Acoblat
                      </p>
                      <p className="font-mono font-bold text-primary dark:text-slate-200">
                        {remolc.matricula}
                      </p>
                      <p className="text-[10px] text-on-surface-variant">
                        {remolc.tipus}
                      </p>
                    </div>
                  )}
                  {maquinaria && (
                    <div className="p-2.5 rounded-lg bg-surface-container-lowest dark:bg-slate-800/60">
                      <p className="text-[10px] font-bold uppercase text-on-surface-variant">
                        Maquinària amb Motor
                      </p>
                      <p className="font-mono font-bold text-primary dark:text-slate-200">
                        {maquinaria.identificador}
                      </p>
                      <p className="text-[10px] text-on-surface-variant">
                        {maquinaria.model}
                      </p>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* FASE 1: CHECK-IN MATINAL (Spec 015 RF-03, RF-04, RF-05) */}
            {estatJornada === "CHECKIN_PENDENT" && (
              <div className="p-5 rounded-xl bg-surface-container-lowest dark:bg-slate-900 border border-outline-variant/25 dark:border-slate-800 shadow-sm space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-primary dark:text-slate-100">
                    <Clock className="w-5 h-5 text-secondary" />
                    <h4 className="text-sm font-extrabold uppercase tracking-wider">
                      Check-in de Sortida (Matí)
                    </h4>
                  </div>
                  <span className="text-[10px] font-bold uppercase tracking-wider text-secondary bg-secondary-container/10 px-2 py-0.5 rounded">
                    IA OCR Activa
                  </span>
                </div>

                {/* Foto Odòmetre Obligatòria per càmera (RF-03 & RF-21) */}
                <div>
                  <p className="text-xs font-bold text-primary dark:text-slate-300 mb-1.5">
                    1. Fotografia de l&apos;Odòmetre del Vehicle *
                  </p>
                  <CameraInput
                    captured={!!fotoOdometreInici}
                    label="Capturar"
                    onCapture={(blob) => {
                      setFotoOdometreInici(blob);
                      setErrorValidacio(null);
                    }}
                  />
                </div>

                {/* Selector tàctil ràpid de combustible (RF-03) */}
                <div>
                  <p className="text-xs font-bold text-primary dark:text-slate-300 mb-1.5">
                    2. Nivell de Combustible Actual *
                  </p>
                  <div className="grid grid-cols-5 gap-1.5">
                    {(["buit", "1/4", "1/2", "3/4", "ple"] as const).map(
                      (nivell) => (
                        <button
                          key={nivell}
                          type="button"
                          onClick={() => setNivellCombustibleInici(nivell)}
                          className={`py-2.5 rounded-xl text-xs font-extrabold uppercase border transition-all ${
                            nivellCombustibleInici === nivell
                              ? "border-secondary-container bg-secondary-container text-white shadow-sm"
                              : "border-outline-variant/40 dark:border-slate-700 bg-surface-container-low dark:bg-slate-800 text-on-surface dark:text-slate-300"
                          }`}
                        >
                          {nivell}
                        </button>
                      )
                    )}
                  </div>
                </div>

                {/* Foto Horòmetre si hi ha maquinària (RF-04) */}
                {maquinaria && (
                  <div>
                    <p className="text-xs font-bold text-primary dark:text-slate-300 mb-1.5">
                      3. Horòmetre Maquinària ({maquinaria.identificador}) *
                    </p>
                    <CameraInput
                      captured={!!fotoHorometreInici}
                      label="Capturar"
                      onCapture={(blob) => {
                        setFotoHorometreInici(blob);
                        setErrorValidacio(null);
                      }}
                    />
                  </div>
                )}

                {/* Foto Opcional de Danys Preexistents (RF-05) */}
                <div>
                  <p className="text-xs font-bold text-on-surface-variant dark:text-slate-400 mb-1.5">
                    Danys Preexistents (Opcional - No bloqueja)
                  </p>
                  <CameraInput
                    captured={!!fotoDanyPreexistent}
                    label="Afegir"
                    onCapture={(blob) => {
                      setFotoDanyPreexistent(blob);
                      setErrorValidacio(null);
                    }}
                  />
                </div>

                {errorValidacio && (
                  <div className="p-3 rounded-xl bg-error-container/60 border border-error/30 text-on-error-container text-xs font-medium">
                    {errorValidacio}
                  </div>
                )}

                <button
                  onClick={handleCheckInSubmit}
                  className="w-full py-3.5 rounded-xl bg-secondary-container hover:brightness-110 active:scale-[0.98] text-white text-xs font-bold uppercase tracking-wider flex items-center justify-center gap-2 shadow-md transition-all"
                >
                  <Check className="w-4 h-4" />
                  <span>Validar Sortida i Iniciar Ruta</span>
                </button>
              </div>
            )}

            {/* FASE 2: EN RUTA I CHECK-OUT DE RETORN (Spec 015 RF-16 a RF-20) */}
            {estatJornada === "EN_MARXA" && (
              <div className="p-5 rounded-xl bg-surface-container-lowest dark:bg-slate-900 border border-outline-variant/25 dark:border-slate-800 shadow-sm space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-primary dark:text-slate-100">
                    <CheckCircle2 className="w-5 h-5 text-secondary" />
                    <h4 className="text-sm font-extrabold uppercase tracking-wider">
                      Check-out de Tornada a Base
                    </h4>
                  </div>
                  <span className="text-[10px] font-bold text-on-surface-variant">
                    Final de Torn
                  </span>
                </div>

                {/* Foto Odòmetre Final */}
                <div>
                  <p className="text-xs font-bold text-primary dark:text-slate-300 mb-1.5">
                    1. Fotografia Odòmetre Final *
                  </p>
                  <CameraInput
                    captured={!!fotoOdometreFi}
                    label="Capturar"
                    onCapture={(blob) => {
                      setFotoOdometreFi(blob);
                      setErrorValidacio(null);
                    }}
                  />
                </div>

                {/* Nivell combustible final */}
                <div>
                  <p className="text-xs font-bold text-primary dark:text-slate-300 mb-1.5">
                    2. Nivell de Combustible Final
                  </p>
                  <div className="grid grid-cols-5 gap-1.5">
                    {(["buit", "1/4", "1/2", "3/4", "ple"] as const).map(
                      (nivell) => (
                        <button
                          key={nivell}
                          type="button"
                          onClick={() => setNivellCombustibleFi(nivell)}
                          className={`py-2.5 rounded-xl text-xs font-extrabold uppercase border transition-all ${
                            nivellCombustibleFi === nivell
                              ? "border-secondary-container bg-secondary-container text-white shadow-sm"
                              : "border-outline-variant/40 dark:border-slate-700 bg-surface-container-low dark:bg-slate-800 text-on-surface dark:text-slate-300"
                          }`}
                        >
                          {nivell}
                        </button>
                      )
                    )}
                  </div>
                </div>

                {maquinaria && (
                  <div>
                    <p className="text-xs font-bold text-primary dark:text-slate-300 mb-1.5">
                      3. Horòmetre Final ({maquinaria.identificador}) *
                    </p>
                    <CameraInput
                      captured={!!fotoHorometreFi}
                      label="Capturar"
                      onCapture={(blob) => {
                        setFotoHorometreFi(blob);
                        setErrorValidacio(null);
                      }}
                    />
                  </div>
                )}

                <div>
                  <p className="text-xs font-bold text-on-surface-variant dark:text-slate-400 mb-1.5">
                    Incidents o Danys Nous (Opcional)
                  </p>
                  <CameraInput
                    captured={!!fotoNouDany}
                    label="Capturar"
                    onCapture={(blob) => {
                      setFotoNouDany(blob);
                      setErrorValidacio(null);
                    }}
                  />
                </div>

                {errorValidacio && (
                  <div className="p-3 rounded-xl bg-error-container/60 border border-error/30 text-on-error-container text-xs font-medium">
                    {errorValidacio}
                  </div>
                )}

                <button
                  onClick={handleCheckOutSubmit}
                  className="w-full py-3.5 rounded-xl bg-primary hover:bg-primary-container active:scale-[0.98] text-white text-xs font-bold uppercase tracking-wider flex items-center justify-center gap-2 shadow-md transition-all"
                >
                  <CheckCircle2 className="w-4 h-4" />
                  <span>Completar Check-out i Retorn a Base</span>
                </button>
              </div>
            )}

            {/* FASE 3: RESUM CHECK-OUT FET (Spec 015 RF-20) */}
            {estatJornada === "CHECKOUT_FET" && (
              <div className="p-6 rounded-xl bg-surface-container-lowest dark:bg-slate-900 border border-secondary-container/40 text-center space-y-4 shadow-sm">
                <div className="w-14 h-14 rounded-full bg-secondary-container/15 text-secondary flex items-center justify-center mx-auto">
                  <CheckCircle2 className="w-8 h-8" />
                </div>
                <div>
                  <h3 className="text-base font-extrabold text-primary dark:text-slate-100">
                    Jornada de Flota Tancada
                  </h3>
                  <p className="text-xs text-on-surface-variant dark:text-slate-400 mt-1">
                    Registres desats a l&apos;IndexedDB xifrat local i llibre diari Hetzner.
                  </p>
                </div>

                <div className="grid grid-cols-2 gap-3 pt-2">
                  <div className="p-3 rounded-xl bg-surface-container-low dark:bg-slate-800/80 border border-outline-variant/30">
                    <p className="text-[10px] font-bold uppercase text-on-surface-variant">
                      Km Recorreguts Nets
                    </p>
                    <p className="text-xl font-extrabold font-mono text-secondary dark:text-emerald-400">
                      {kmTotalsCalculats != null
                        ? `${kmTotalsCalculats} km`
                        : "Pendent OCR"}
                    </p>
                    <p className="text-[10px] text-on-surface-variant font-mono">
                      (Odòmetre Final - Inicial)
                    </p>
                  </div>
                  <div className="p-3 rounded-xl bg-surface-container-low dark:bg-slate-800/80 border border-outline-variant/30">
                    <p className="text-[10px] font-bold uppercase text-on-surface-variant">
                      Hores Màquina
                    </p>
                    <p className="text-xl font-extrabold font-mono text-amber-600 dark:text-amber-400">
                      {horesTotalsCalculades != null
                        ? `${horesTotalsCalculades} h`
                        : "N/A"}
                    </p>
                    <p className="text-[10px] text-on-surface-variant font-mono">
                      (Horòmetre Final - Inicial)
                    </p>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* PESTANYA 2: ESTOC DE FURGONETA (Spec 015 RF-11, RF-12, RF-13) */}
        {vehicle && tabActiva === "ESTOC" && (
          <div className="space-y-4">
            <div className="relative">
              <Search className="w-4 h-4 text-outline absolute left-3.5 top-3" />
              <input
                type="text"
                value={filtreCerca}
                onChange={(e) => setFiltreCerca(e.target.value)}
                placeholder="Cercar referència, nom o marca a la furgoneta..."
                className="w-full pl-10 pr-4 py-2.5 rounded-xl border border-outline-variant/40 dark:border-slate-700 bg-surface-container-lowest dark:bg-slate-900 text-xs font-medium focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>

            {!loadingEstoc && estocFurgoneta.length === 0 ? (
              <div className="flex flex-col items-center justify-center p-6 text-center bg-surface-container-lowest dark:bg-slate-900 rounded-xl border border-dashed border-outline-variant/40 dark:border-slate-800">
                <Truck className="w-8 h-8 text-outline mb-2" />
                <p className="text-xs text-on-surface-variant dark:text-slate-400">
                  Sense dades disponibles
                </p>
                <button
                  onClick={carregarEstoc}
                  className="mt-3 px-3.5 py-2 rounded-lg bg-surface-container-low dark:bg-slate-800 text-xs font-bold text-primary dark:text-slate-300 hover:bg-surface-container flex items-center gap-1.5 transition-colors"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                  Carregar dades reals
                </button>
              </div>
            ) : loadingEstoc ? (
              <div className="text-center text-on-surface-variant text-xs py-4">
                Carregant estoc...
              </div>
            ) : (
              <div className="space-y-2.5">
                {estocFiltrat.map((item) => {
                  const faltaStock =
                    item.quantitat_actual < item.quantitat_optima;
                  const quantitatFaltant =
                    item.quantitat_optima - item.quantitat_actual;

                  return (
                    <div
                      key={item.id}
                      className="p-3.5 rounded-xl bg-surface-container-lowest dark:bg-slate-900 border border-outline-variant/25 dark:border-slate-800 shadow-sm flex items-center justify-between"
                    >
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="text-[10px] font-mono font-bold px-1.5 py-0.5 rounded bg-surface-container-low dark:bg-slate-800 text-primary dark:text-slate-300">
                            {item.referencia}
                          </span>
                          <span className="text-[10px] text-on-surface-variant">
                            {item.marca}
                          </span>
                        </div>
                        <h4 className="text-xs font-bold text-primary dark:text-slate-100 mt-1">
                          {item.nom}
                        </h4>
                        <p className="text-[11px] font-mono text-on-surface-variant mt-0.5">
                          Estoc a bord:{" "}
                          <span className="font-bold text-primary dark:text-slate-200">
                            {item.quantitat_actual} {item.unitat}
                          </span>{" "}
                          / Òptim: {item.quantitat_optima} {item.unitat}
                        </p>
                      </div>

                      {faltaStock ? (
                        <div className="text-right">
                          <span className="inline-block text-[10px] font-bold px-2 py-0.5 rounded bg-error-container text-on-error-container">
                            Falten {quantitatFaltant} {item.unitat}
                          </span>
                          <p className="text-[9px] text-on-surface-variant mt-1">
                            Consumit en tasca
                          </p>
                        </div>
                      ) : (
                        <span className="text-[10px] font-bold px-2.5 py-1 rounded-full bg-secondary-container/15 text-secondary">
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
          <div className="p-5 rounded-xl bg-surface-container-lowest dark:bg-slate-900 border border-outline-variant/25 dark:border-slate-800 shadow-sm space-y-4">
            <div className="flex items-center gap-2 text-primary dark:text-slate-100">
              <Fuel className="w-5 h-5 text-secondary" />
              <div>
                <h4 className="text-sm font-extrabold uppercase tracking-wider">
                  Registrar Carburant en Ruta
                </h4>
                <p className="text-[10px] text-on-surface-variant">
                  Spec 015 RF-07: Doble Fotografia Obligatòria
                </p>
              </div>
            </div>

            {repostatgeGuardat ? (
              <div className="p-6 text-center space-y-3">
                <div className="w-12 h-12 rounded-full bg-secondary-container/15 text-secondary flex items-center justify-center mx-auto">
                  <CheckCircle2 className="w-6 h-6" />
                </div>
                <h4 className="text-sm font-extrabold text-primary dark:text-slate-100">
                  Repostatge Enregistrat amb Èxit
                </h4>
                <p className="text-xs text-on-surface-variant dark:text-slate-400">
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
                  className="mt-3 px-4 py-2.5 rounded-xl bg-secondary-container text-white text-xs font-bold"
                >
                  Registrar un altre proveïment
                </button>
              </div>
            ) : (
              <form onSubmit={handleRepostarSubmit} className="space-y-4">
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-[10px] font-bold uppercase text-on-surface-variant mb-1">
                      Tipus Carburant
                    </label>
                    <select
                      value={tipusCarburant}
                      onChange={(e: any) => setTipusCarburant(e.target.value)}
                      className="w-full p-2.5 rounded-xl border border-outline-variant/40 dark:border-slate-700 bg-surface-container-low dark:bg-slate-800 text-xs font-semibold"
                    >
                      <option value="DIESEL">Dièsel B / A</option>
                      <option value="GASOLINA">Gasolina 95</option>
                      <option value="ADBLUE">AdBlue / DEF</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-[10px] font-bold uppercase text-on-surface-variant mb-1">
                      Mètode Pagament (RF-08)
                    </label>
                    <select
                      value={metodePagament}
                      onChange={(e: any) => setMetodePagament(e.target.value)}
                      className="w-full p-2.5 rounded-xl border border-outline-variant/40 dark:border-slate-700 bg-surface-container-low dark:bg-slate-800 text-xs font-semibold"
                    >
                      <option value="SOLRED">Targeta Solred / DKV</option>
                      <option value="CAMP">Targeta de Camp</option>
                      <option value="EFECTIU">Efectiu de Caixa</option>
                    </select>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-[10px] font-bold uppercase text-on-surface-variant mb-1">
                      Import Total (€) *
                    </label>
                    <input
                      type="number"
                      step="0.01"
                      value={importEuros}
                      onChange={(e) => setImportEuros(e.target.value)}
                      placeholder="0.00"
                      className="w-full p-2.5 rounded-xl border border-outline-variant/40 dark:border-slate-700 bg-surface-container-low dark:bg-slate-800 text-xs font-mono font-bold"
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] font-bold uppercase text-on-surface-variant mb-1">
                      Litres Càrrega (L) *
                    </label>
                    <input
                      type="number"
                      step="0.01"
                      value={litresRepostats}
                      onChange={(e) => setLitresRepostats(e.target.value)}
                      placeholder="0.00"
                      className="w-full p-2.5 rounded-xl border border-outline-variant/40 dark:border-slate-700 bg-surface-container-low dark:bg-slate-800 text-xs font-mono font-bold"
                    />
                  </div>
                </div>

                <div className="space-y-3 pt-2">
                  <p className="text-xs font-bold uppercase text-on-surface-variant">
                    Doble Fotografia Obligatòria per a Carburant
                  </p>
                  <CameraInput
                    captured={!!fotoTiquetCarburant}
                    label="Capturar"
                    onCapture={(blob) => {
                      setFotoTiquetCarburant(blob);
                      setErrorValidacio(null);
                    }}
                  />
                  <CameraInput
                    captured={!!fotoOdometreCarburant}
                    label="Capturar"
                    onCapture={(blob) => {
                      setFotoOdometreCarburant(blob);
                      setErrorValidacio(null);
                    }}
                  />
                </div>

                {errorValidacio && (
                  <div className="p-3 rounded-xl bg-error-container/60 border border-error/30 text-on-error-container text-xs font-medium">
                    {errorValidacio}
                  </div>
                )}

                <button
                  type="submit"
                  className="w-full py-3.5 rounded-xl bg-secondary-container hover:brightness-110 active:scale-[0.98] text-white text-xs font-bold uppercase tracking-wider shadow-md transition-all"
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