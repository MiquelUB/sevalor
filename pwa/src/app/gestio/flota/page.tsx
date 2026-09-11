"use client";
import { apiFetch } from "@/lib/api";


import React, { useState, useEffect } from "react";
import Link from "next/link";
import {
  Truck,
  Shield,
  ShieldAlert,
  ShieldCheck,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Fuel,
  BatteryCharging,
  Zap,
  Activity,
  Plus,
  Search,
  Filter,
  RefreshCw,
  FileText,
  Wrench,
  Car,
  ChevronRight,
  AlertCircle,
  Check,
  X,
  PlusCircle,
  HelpCircle,
  ExternalLink,
} from "lucide-react";

interface VehicleItem {
  id: string;
  matricula: string;
  marca: string;
  model: string;
  tipus: string;
  distintiu_ambiental: string;
  estat: string;
  odometre_acumulat: number;
  horometre_acumulat: number;
  conductor_habitual_id: string | null;
  conductor_nom: string;
  data_proxima_itv: string | null;
  dies_propera_itv: number | null;
  alerta_itv_cadena: string;
  regim_adquisicio: string;
  renting_limit_km: number;
  renting_ocupacio_percent: number;
  renting_alerta: boolean;
  renting_nivell_alerta: string;
  consum_format: string;
  consum_l_100km: number | null;
  consum_mitjana_historica: number | null;
  consum_adblue_litres: number;
  anomalia_consum: boolean;
  anomalia_descartada: boolean;
  descarte_detalls?: {
    motiu: string;
    observacions?: string;
    data_resolucio: string;
  };
}

export default function GestioFlotaPage() {
  const [vehicles, setVehicles] = useState<VehicleItem[]>([]);
  const [carregant, setCarregant] = useState<boolean>(true);
  const [cerca, setCerca] = useState<string>("");
  const [filtreTipus, setFiltreTipus] = useState<string>("TOTS");
  const [filtreEstat, setFiltreEstat] = useState<string>("TOTS");

  // Estat del formulari / modal d'ITV
  const [modalItvObert, setModalItvObert] = useState<boolean>(false);
  const [vehicleSeleccionatItv, setVehicleSeleccionatItv] = useState<VehicleItem | null>(null);
  const [veredicteItv, setVeredicteItv] = useState<"FAVORABLE" | "LEVE" | "DESFAVORABLE" | "NEGATIVA">("FAVORABLE");
  const [dataNovaItv, setDataNovaItv] = useState<string>("");
  const [defectesItv, setDefectesItv] = useState<string>("");

  // Estat del formulari / modal de Descarte d'Anomalia de Consum
  const [modalDescarteObert, setModalDescarteObert] = useState<boolean>(false);
  const [vehicleSeleccionatConsum, setVehicleSeleccionatConsum] = useState<VehicleItem | null>(null);
  const [motiuTipificat, setMotiuTipificat] = useState<string>("CARREGA_PESADA");
  const [observacionsDescarte, setObservacionsDescarte] = useState<string>("");

  // Estat del formulari / modal de Nou Vehicle
  const [modalNouVehicleObert, setModalNouVehicleObert] = useState<boolean>(false);
  const [novaMatricula, setNovaMatricula] = useState<string>("");
  const [novaMarca, setNovaMarca] = useState<string>("");
  const [nouModel, setNouModel] = useState<string>("");
  const [nouTipus, setNouTipus] = useState<string>("DIESEL");
  const [nouDistintiu, setNouDistintiu] = useState<string>("C");
  const [nouOdometre, setNouOdometre] = useState<number>(0);
  const [nouRegim, setNouRegim] = useState<string>("PROPIETAT");
  const [nouLimitKm, setNouLimitKm] = useState<number>(100000);

  // Carregar vehicles des del backend
  const fetchVehicles = async () => {
    setCarregant(true);
    try {
      const res = await apiFetch("/gestio/flota/vehicles");
      if (res.ok) {
        const data = await res.json();
        setVehicles(data);
      }
    } catch {
      // Backend offline o construcció estàtica
    } finally {
      setCarregant(false);
    }
  };

  useEffect(() => {
    fetchVehicles();
  }, []);

  // Registrar resolució d'ITV (Spec 006 RF-18)
  const handleRegistrarItv = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!vehicleSeleccionatItv) return;

    try {
      const res = await apiFetch("/gestio/flota/registrar-itv", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          vehicle_id: vehicleSeleccionatItv.id,
          veredicte: veredicteItv,
          data_proxima_itv: dataNovaItv || new Date(Date.now() + 365 * 86400000).toISOString().split("T")[0],
          defectes_detectats: defectesItv,
        }),
      });

      if (res.ok) {
        setModalItvObert(false);
        fetchVehicles();
      } else {
        // Fallback optimista si no hi ha backend
        setVehicles((prev) =>
          prev.map((v) => {
            if (v.id === vehicleSeleccionatItv.id) {
              const nouEstat =
                veredicteItv === "FAVORABLE"
                  ? "OPERATIU"
                  : veredicteItv === "LEVE"
                  ? "LEVE"
                  : veredicteItv === "DESFAVORABLE"
                  ? "DESFAVORABLE"
                  : "INACTIVAT";
              return { ...v, estat: nouEstat, data_proxima_itv: dataNovaItv };
            }
            return v;
          })
        );
        setModalItvObert(false);
      }
    } catch {
      // Error de xarxa
      setModalItvObert(false);
    }
  };

  // Descartar anomalia de consum (Spec 006 RF-16)
  const handleDescartarAnomalia = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!vehicleSeleccionatConsum) return;

    try {
      await apiFetch("/gestio/flota/descartar-anomalia-consum", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          vehicle_id: vehicleSeleccionatConsum.id,
          motiu_tipificat: motiuTipificat,
          observacions: observacionsDescarte,
        }),
      });

      // Actualització optimista
      setVehicles((prev) =>
        prev.map((v) => {
          if (v.id === vehicleSeleccionatConsum.id) {
            return {
              ...v,
              anomalia_consum: false,
              anomalia_descartada: true,
              descarte_detalls: {
                motiu: motiuTipificat,
                observacions: observacionsDescarte,
                data_resolucio: new Date().toISOString().split("T")[0],
              },
            };
          }
          return v;
        })
      );
      setModalDescarteObert(false);
    } catch {
      setModalDescarteObert(false);
    }
  };

  // Donar d'alta nou vehicle (Spec 006 RF-05)
  const handleCrearVehicle = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!novaMatricula || !novaMarca || !nouModel) return;

    try {
      const res = await apiFetch("/gestio/flota/vehicles", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          matricula: novaMatricula,
          marca: novaMarca,
          model: nouModel,
          tipus: nouTipus,
          distintiu_ambiental: nouDistintiu,
          odometre_acumulat: nouOdometre,
          regim_adquisicio: nouRegim,
          renting_limit_km: nouLimitKm,
        }),
      });

      if (res.ok) {
        setModalNouVehicleObert(false);
        fetchVehicles();
      } else {
        // Fallback optimista per a entorn local
        const nouItem: VehicleItem = {
          id: `veh-${Date.now()}`,
          matricula: novaMatricula.toUpperCase(),
          marca: novaMarca,
          model: nouModel,
          tipus: nouTipus,
          distintiu_ambiental: nouDistintiu,
          estat: "OPERATIU",
          odometre_acumulat: nouOdometre,
          horometre_acumulat: 0,
          conductor_habitual_id: null,
          conductor_nom: "Sense conductor assignat",
          data_proxima_itv: null,
          dies_propera_itv: null,
          alerta_itv_cadena: "OK",
          regim_adquisicio: nouRegim,
          renting_limit_km: nouLimitKm,
          renting_ocupacio_percent: Math.round((nouOdometre / nouLimitKm) * 100),
          renting_alerta: (nouOdometre / nouLimitKm) >= 0.9,
          renting_nivell_alerta: (nouOdometre / nouLimitKm) >= 0.9 ? "90%" : "NOMINAL",
          consum_format: nouTipus === "REMOLC" ? "N/A (Exempt)" : "8.2 L/100km",
          consum_l_100km: 8.2,
          consum_mitjana_historica: 8.0,
          consum_adblue_litres: 0,
          anomalia_consum: false,
          anomalia_descartada: false,
        };
        setVehicles((prev) => [nouItem, ...prev]);
        setModalNouVehicleObert(false);
      }
    } catch {
      setModalNouVehicleObert(false);
    }
  };

  // Filtrar vehicles
  const vehiclesFiltrats = vehicles.filter((v) => {
    if (filtreTipus !== "TOTS" && v.tipus !== filtreTipus) return false;
    if (filtreEstat !== "TOTS" && v.estat !== filtreEstat) return false;
    if (!cerca) return true;
    const q = cerca.toLowerCase();
    return (
      v.matricula.toLowerCase().includes(q) ||
      v.marca.toLowerCase().includes(q) ||
      v.model.toLowerCase().includes(q) ||
      v.conductor_nom.toLowerCase().includes(q) ||
      v.distintiu_ambiental.toLowerCase().includes(q)
    );
  });

  return (
    <div className="flex-1 p-6 space-y-6 overflow-y-auto bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 font-sans transition-colors">
      {/* CAPÇALERA SUPERIOR */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-slate-200 dark:border-slate-800">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-white flex items-center gap-2">
              <Truck className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
              Gestió de Flota, ITV & Consum (Spec 006)
            </h1>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-800 font-bold">
              RLS VEHICLES SCHEME
            </span>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Control tècnic, 4 veredictes d'ITV, anàlisi de consum l/100km i llindars de rènting 90/95/100%
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={fetchVehicles}
            disabled={carregant}
            className="px-3 py-1.5 rounded-lg bg-white dark:bg-slate-800 hover:bg-slate-100 dark:hover:bg-slate-700 text-slate-800 dark:text-slate-200 text-xs font-mono font-bold flex items-center gap-1.5 border border-slate-300 dark:border-slate-700 shadow-sm transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${carregant ? "animate-spin text-emerald-500" : ""}`} />
            <span>Refrescar</span>
          </button>
          <button
            onClick={() => {
              setNovaMatricula("");
              setNovaMarca("");
              setNouModel("");
              setModalNouVehicleObert(true);
            }}
            className="px-3.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-mono font-bold flex items-center gap-1.5 shadow transition-colors"
          >
            <PlusCircle className="w-4 h-4" />
            <span>Registrar Nou Vehicle</span>
          </button>
        </div>
      </div>

      {/* BARRA DE FILTRES I CERCA */}
      <div className="flex flex-wrap items-center justify-between gap-3 p-3 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm">
        <div className="flex items-center gap-2 flex-1 max-w-md">
          <Search className="w-4 h-4 text-slate-400" />
          <input
            type="text"
            disabled={vehicles.length === 0}
            placeholder={vehicles.length === 0 ? "Cercador deshabilitat (Dia 0)" : "Filtrar per matrícula, marca, model, distintiu DGT o conductor..."}
            value={cerca}
            onChange={(e) => setCerca(e.target.value)}
            className="w-full text-xs bg-transparent border-none focus:outline-none text-slate-900 dark:text-slate-100 placeholder:text-slate-400 font-mono disabled:opacity-50"
          />
        </div>

        <div className="flex items-center gap-2">
          {/* Filtre per tipus */}
          <select
            value={filtreTipus}
            onChange={(e) => setFiltreTipus(e.target.value)}
            className="text-xs bg-slate-100 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg px-2.5 py-1.5 font-mono text-slate-700 dark:text-slate-300 focus:outline-none"
          >
            <option value="TOTS">Tots els tipus</option>
            <option value="DIESEL">Dièsel</option>
            <option value="EV">100% Elèctric (EV)</option>
            <option value="PHEV">Híbrid Enchufable (PHEV)</option>
            <option value="MAQUINARIA">Maquinària</option>
            <option value="REMOLC">Remolc</option>
          </select>

          {/* Filtre per estat */}
          <select
            value={filtreEstat}
            onChange={(e) => setFiltreEstat(e.target.value)}
            className="text-xs bg-slate-100 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg px-2.5 py-1.5 font-mono text-slate-700 dark:text-slate-300 focus:outline-none"
          >
            <option value="TOTS">Tots els estats</option>
            <option value="OPERATIU">Operatiu (Verd)</option>
            <option value="LEVE">Operatiu Defectes Lleus</option>
            <option value="DESFAVORABLE">ITV Desfavorable (Immobilitzat)</option>
            <option value="INACTIVAT">ITV Negativa (Grua)</option>
            <option value="EN_TALLER">En Taller</option>
          </select>
        </div>
      </div>

      {/* TAULA DE FLOTA O ESTAT BUIT CANÒNIC ZERO MOCK DATA */}
      {vehicles.length === 0 ? (
        <div className="p-12 rounded-2xl border-2 border-dashed border-slate-300 dark:border-slate-800 text-center space-y-4 bg-white dark:bg-slate-900/60 shadow-sm">
          <div className="w-14 h-14 rounded-full bg-emerald-50 dark:bg-emerald-950/60 text-emerald-600 dark:text-emerald-400 flex items-center justify-center mx-auto border border-emerald-200 dark:border-emerald-800">
            <Truck className="w-7 h-7" />
          </div>
          <div className="space-y-1">
            <h3 className="text-base font-bold text-slate-800 dark:text-slate-100 font-mono">
              No hi ha vehicles registrats a la flota
            </h3>
            <p className="text-xs text-slate-500 font-mono max-w-md mx-auto">
              Estat canònic de Dia 0. Registra el primer vehicle, furgoneta, pick-up, maquinària o remolc per iniciar la gestió de flota.
            </p>
          </div>
          <button
            onClick={() => setModalNouVehicleObert(true)}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-mono font-bold shadow transition-colors"
          >
            <PlusCircle className="w-4 h-4" />
            <span>Registrar nou vehicle / actiu</span>
          </button>
        </div>
      ) : (
        <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 overflow-hidden shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="bg-slate-100 dark:bg-slate-800/80 border-b border-slate-200 dark:border-slate-800 font-mono text-[10px] uppercase text-slate-500 dark:text-slate-400">
                  <th className="p-3.5">Matrícula & Id</th>
                  <th className="p-3.5">Tipus & Distintiu DGT</th>
                  <th className="p-3.5">Marca & Model</th>
                  <th className="p-3.5 text-center">Règim & Rènting</th>
                  <th className="p-3.5">Custodi / Conductor</th>
                  <th className="p-3.5 text-center">Odòmetre / Horòmetre</th>
                  <th className="p-3.5 text-center">Estat Operatiu</th>
                  <th className="p-3.5 text-right">Estat Legal, ITV & Consum</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 dark:divide-slate-800 font-mono text-[11px]">
                {vehiclesFiltrats.map((v) => (
                  <tr key={v.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/40 transition-colors">
                    {/* 1. Matrícula */}
                    <td className="p-3.5">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-slate-900 dark:text-white px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 tracking-wider">
                          {v.matricula}
                        </span>
                      </div>
                    </td>

                    {/* 2. Tipologia & Distintiu DGT (RF-01) */}
                    <td className="p-3.5">
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] font-bold text-slate-600 dark:text-slate-300">
                          {v.tipus}
                        </span>
                        {/* Distintiu ambiental DGT inmutable */}
                        <span
                          className={`text-[9px] font-bold px-1.5 py-0.2 rounded border ${
                            v.distintiu_ambiental === "ZERO"
                              ? "bg-blue-100 text-blue-800 border-blue-300 dark:bg-blue-950 dark:text-blue-300 dark:border-blue-800"
                              : v.distintiu_ambiental === "ECO"
                              ? "bg-emerald-100 text-emerald-800 border-emerald-300 dark:bg-emerald-950 dark:text-emerald-300 dark:border-emerald-800"
                              : v.distintiu_ambiental === "C"
                              ? "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-900/40 dark:text-emerald-400"
                              : v.distintiu_ambiental === "B"
                              ? "bg-amber-100 text-amber-800 border-amber-300 dark:bg-amber-950 dark:text-amber-300 dark:border-amber-800"
                              : "bg-slate-200 text-slate-700 border-slate-300 dark:bg-slate-800 dark:text-slate-400"
                          }`}
                        >
                          DGT: {v.distintiu_ambiental}
                        </span>
                      </div>
                    </td>

                    {/* 3. Marca i Model */}
                    <td className="p-3.5">
                      <p className="font-bold text-slate-900 dark:text-white">{v.marca}</p>
                      <p className="text-[10px] text-slate-500">{v.model}</p>
                    </td>

                    {/* 4. Règim d'Adquisició & Llindars Rènting 90/95/100% (RF-06, RF-29) */}
                    <td className="p-3.5 text-center">
                      <div className="space-y-1 inline-block text-left w-28">
                        <div className="flex items-center justify-between text-[10px]">
                          <span className="text-slate-500">{v.regim_adquisicio}</span>
                          <span
                            className={`font-bold ${
                              v.renting_ocupacio_percent >= 100
                                ? "text-rose-500"
                                : v.renting_ocupacio_percent >= 95
                                ? "text-orange-500"
                                : v.renting_ocupacio_percent >= 90
                                ? "text-amber-500"
                                : "text-slate-400"
                            }`}
                          >
                            {v.renting_ocupacio_percent}%
                          </span>
                        </div>
                        {/* Barra de progrés */}
                        <div className="w-full h-1.5 rounded-full bg-slate-200 dark:bg-slate-700 overflow-hidden">
                          <div
                            className={`h-full transition-all ${
                              v.renting_ocupacio_percent >= 100
                                ? "bg-rose-500"
                                : v.renting_ocupacio_percent >= 95
                                ? "bg-orange-500"
                                : v.renting_ocupacio_percent >= 90
                                ? "bg-amber-500"
                                : "bg-emerald-500"
                            }`}
                            style={{ width: `${Math.min(100, v.renting_ocupacio_percent)}%` }}
                          ></div>
                        </div>
                        {v.renting_alerta && (
                          <p className="text-[9px] font-bold text-amber-500">
                            Límit {v.renting_nivell_alerta} assolit!
                          </p>
                        )}
                      </div>
                    </td>

                    {/* 5. Custodi / Conductor */}
                    <td className="p-3.5">
                      <p className="font-semibold text-slate-800 dark:text-slate-200">{v.conductor_nom}</p>
                    </td>

                    {/* 6. Odòmetre Acumulat Continu (1 Vehicle = 1 Historial) */}
                    <td className="p-3.5 text-center">
                      <span className="font-bold text-slate-900 dark:text-white">
                        {v.odometre_acumulat.toLocaleString()} km
                      </span>
                    </td>

                    {/* 7. Estat Operatiu (7 estats canònics) */}
                    <td className="p-3.5 text-center">
                      <span
                        className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${
                          v.estat === "OPERATIU"
                            ? "bg-emerald-100 text-emerald-800 border-emerald-300 dark:bg-emerald-950 dark:text-emerald-400 dark:border-emerald-800"
                            : v.estat === "LEVE"
                            ? "bg-lime-100 text-lime-800 border-lime-300 dark:bg-lime-950 dark:text-lime-300 dark:border-lime-800"
                            : v.estat === "EN_TALLER"
                            ? "bg-amber-100 text-amber-800 border-amber-300 dark:bg-amber-950 dark:text-amber-400 dark:border-amber-800"
                            : v.estat === "DESFAVORABLE"
                            ? "bg-rose-100 text-rose-800 border-rose-300 dark:bg-rose-950 dark:text-rose-400 dark:border-rose-800"
                            : v.estat === "INACTIVAT"
                            ? "bg-red-200 text-red-900 border-red-400 dark:bg-red-950 dark:text-red-300 dark:border-red-800"
                            : "bg-slate-100 text-slate-700 border-slate-300 dark:bg-slate-800 dark:text-slate-400"
                        }`}
                      >
                        {v.estat === "LEVE" ? "Operatiu (Defectes Lleus)" : v.estat}
                      </span>
                    </td>

                    {/* 8. Estat Legal, ITV & Consum (RF-16 & RF-18) */}
                    <td className="p-3.5 text-right">
                      <div className="space-y-1 inline-block text-right">
                        {/* Indicador de Consum & Descarte */}
                        <div className="flex items-center justify-end gap-1.5">
                          <span className="text-[10px] text-slate-600 dark:text-slate-300 font-bold">
                            {v.consum_format}
                          </span>
                          {v.anomalia_consum && (
                            <button
                              onClick={() => {
                                setVehicleSeleccionatConsum(v);
                                setModalDescarteObert(true);
                              }}
                              className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300 border border-amber-300 dark:border-amber-700 hover:bg-amber-200 flex items-center gap-0.5"
                              title="Anomalia de consum >10%. Clica per descartar amb motiu tipificat."
                            >
                              <AlertTriangle className="w-2.5 h-2.5" />
                              <span>&gt;10% Anomalia</span>
                            </button>
                          )}
                          {v.anomalia_descartada && (
                            <span className="text-[9px] text-slate-400" title={`Descartat: ${v.descarte_detalls?.motiu}`}>
                              (Justificat)
                            </span>
                          )}
                        </div>

                        {/* Estat ITV i Botó de Resolució en 4 Veredictes */}
                        <div className="flex items-center justify-end gap-1.5">
                          <span className="text-[10px] text-slate-500">
                            {v.data_proxima_itv ? `ITV: ${v.data_proxima_itv}` : "ITV pendent"}
                          </span>
                          <button
                            onClick={() => {
                              setVehicleSeleccionatItv(v);
                              setDataNovaItv(
                                new Date(Date.now() + 365 * 86400000).toISOString().split("T")[0]
                              );
                              setModalItvObert(true);
                            }}
                            className="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-100 hover:bg-slate-200 text-slate-700 dark:bg-slate-800 dark:hover:bg-slate-700 dark:text-slate-300 border border-slate-300 dark:border-slate-700"
                          >
                            Resoldre ITV
                          </button>
                        </div>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* MODAL 1: RESOLUCIÓ D'ITV EN 4 VEREDICTES (Spec 006 RF-18) */}
      {modalItvObert && vehicleSeleccionatItv && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-lg rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-6 space-y-4 shadow-xl text-slate-900 dark:text-slate-100">
            <div className="flex items-center justify-between pb-3 border-b border-slate-200 dark:border-slate-800">
              <div className="flex items-center gap-2">
                <Shield className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
                <h3 className="font-bold text-sm font-mono">
                  Resolució d'ITV: {vehicleSeleccionatItv.matricula}
                </h3>
              </div>
              <button
                onClick={() => setModalItvObert(false)}
                className="p-1 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-400"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleRegistrarItv} className="space-y-4 text-xs font-mono">
              {/* Selecció dels 4 Veredictes */}
              <div className="space-y-2">
                <label className="font-bold text-slate-700 dark:text-slate-300">
                  Veredicte Oficial de la Inspecció (4 Vies):
                </label>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={() => setVeredicteItv("FAVORABLE")}
                    className={`p-3 rounded-xl border text-left space-y-1 transition-colors ${
                      veredicteItv === "FAVORABLE"
                        ? "border-emerald-600 bg-emerald-50 text-emerald-900 dark:bg-emerald-950/60 dark:text-emerald-300"
                        : "border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800"
                    }`}
                  >
                    <div className="font-bold flex items-center gap-1.5 text-emerald-600 dark:text-emerald-400">
                      <CheckCircle2 className="w-4 h-4" />
                      <span>Favorable Neta</span>
                    </div>
                    <p className="text-[10px] text-slate-500 leading-tight">
                      El vehicle recupera l'estat Operatiu [Verd].
                    </p>
                  </button>

                  <button
                    type="button"
                    onClick={() => setVeredicteItv("LEVE")}
                    className={`p-3 rounded-xl border text-left space-y-1 transition-colors ${
                      veredicteItv === "LEVE"
                        ? "border-lime-600 bg-lime-50 text-lime-900 dark:bg-lime-950/60 dark:text-lime-300"
                        : "border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800"
                    }`}
                  >
                    <div className="font-bold flex items-center gap-1.5 text-lime-600 dark:text-lime-400">
                      <Check className="w-4 h-4" />
                      <span>Favorable DL</span>
                    </div>
                    <p className="text-[10px] text-slate-500 leading-tight">
                      Operatiu [Verd Clar] amb defectes lleus a manteniment.
                    </p>
                  </button>

                  <button
                    type="button"
                    onClick={() => setVeredicteItv("DESFAVORABLE")}
                    className={`p-3 rounded-xl border text-left space-y-1 transition-colors ${
                      veredicteItv === "DESFAVORABLE"
                        ? "border-rose-600 bg-rose-50 text-rose-900 dark:bg-rose-950/60 dark:text-rose-300"
                        : "border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800"
                    }`}
                  >
                    <div className="font-bold flex items-center gap-1.5 text-rose-600 dark:text-rose-400">
                      <AlertTriangle className="w-4 h-4" />
                      <span>Desfavorable</span>
                    </div>
                    <p className="text-[10px] text-slate-500 leading-tight">
                      Immobilitzat + 2 mesos de termini + obertura d'OT a taller.
                    </p>
                  </button>

                  <button
                    type="button"
                    onClick={() => setVeredicteItv("NEGATIVA")}
                    className={`p-3 rounded-xl border text-left space-y-1 transition-colors ${
                      veredicteItv === "NEGATIVA"
                        ? "border-red-700 bg-red-50 text-red-900 dark:bg-red-950/60 dark:text-red-300"
                        : "border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800"
                    }`}
                  >
                    <div className="font-bold flex items-center gap-1.5 text-red-700 dark:text-red-400">
                      <ShieldAlert className="w-4 h-4" />
                      <span>Negativa</span>
                    </div>
                    <p className="text-[10px] text-slate-500 leading-tight">
                      Immobilització total + avís obligatori de grua.
                    </p>
                  </button>
                </div>
              </div>

              {/* Data nova ITV */}
              <div className="space-y-1">
                <label className="font-bold text-slate-700 dark:text-slate-300">
                  Nova Data de Venciment:
                </label>
                <input
                  type="date"
                  required
                  value={dataNovaItv}
                  onChange={(e) => setDataNovaItv(e.target.value)}
                  className="w-full p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none"
                />
              </div>

              {/* Defectes detectats si no és favorable neta */}
              {veredicteItv !== "FAVORABLE" && (
                <div className="space-y-1">
                  <label className="font-bold text-slate-700 dark:text-slate-300">
                    Defectes detectats en l'informe oficial:
                  </label>
                  <textarea
                    rows={3}
                    placeholder="Descriu els defectes lleus o greus reflectits a la inspecció..."
                    value={defectesItv}
                    onChange={(e) => setDefectesItv(e.target.value)}
                    className="w-full p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none"
                  />
                </div>
              )}

              {/* Botons d'acció */}
              <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-200 dark:border-slate-800">
                <button
                  type="button"
                  onClick={() => setModalItvObert(false)}
                  className="px-3 py-2 rounded-xl bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 text-slate-700 dark:text-slate-300 font-bold"
                >
                  Cancel·lar
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold shadow"
                >
                  Confirmar Resolució ITV
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL 2: DESCARTE TIPICAT D'ANOMALIA DE CONSUM (>10%) (Spec 006 RF-16) */}
      {modalDescarteObert && vehicleSeleccionatConsum && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-md rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-6 space-y-4 shadow-xl text-slate-900 dark:text-slate-100">
            <div className="flex items-center justify-between pb-3 border-b border-slate-200 dark:border-slate-800">
              <div className="flex items-center gap-2">
                <Fuel className="w-5 h-5 text-amber-500" />
                <h3 className="font-bold text-sm font-mono">
                  Descartar Anomalia de Consum: {vehicleSeleccionatConsum.matricula}
                </h3>
              </div>
              <button
                onClick={() => setModalDescarteObert(false)}
                className="p-1 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-400"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <p className="text-xs text-slate-500 font-mono">
              Consum registrat ({vehicleSeleccionatConsum.consum_l_100km} L/100km) superior en més d'un 10% a la mitjana consolidada ({vehicleSeleccionatConsum.consum_mitjana_historica} L/100km).
            </p>

            <form onSubmit={handleDescartarAnomalia} className="space-y-4 text-xs font-mono">
              <div className="space-y-1">
                <label className="font-bold text-slate-700 dark:text-slate-300">
                  Motiu Tipificat Homologat:
                </label>
                <select
                  value={motiuTipificat}
                  onChange={(e) => setMotiuTipificat(e.target.value)}
                  className="w-full p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none"
                >
                  <option value="CARREGA_PESADA">Càrrega pesada / arrastre de remolc</option>
                  <option value="CLIMATOLOGIA_ADVERSA">Climatologia adversa / ús intensiu de calefacció</option>
                  <option value="RUTA_MUNTANYA">Ruta de muntanya / pistes de terra</option>
                  <option value="FUGA_MECANICA">Pèrdua de combustible / fuga mecànica revisada en taller</option>
                  <option value="ALTRES">Altres motius justificats</option>
                </select>
              </div>

              <div className="space-y-1">
                <label className="font-bold text-slate-700 dark:text-slate-300">
                  Observacions / Justificació:
                </label>
                <textarea
                  rows={3}
                  placeholder="Detalla les circumstàncies de la desviació..."
                  value={observacionsDescarte}
                  onChange={(e) => setObservacionsDescarte(e.target.value)}
                  className="w-full p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-200 dark:border-slate-800">
                <button
                  type="button"
                  onClick={() => setModalDescarteObert(false)}
                  className="px-3 py-2 rounded-xl bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 text-slate-700 dark:text-slate-300 font-bold"
                >
                  Cancel·lar
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 rounded-xl bg-amber-600 hover:bg-amber-500 text-white font-bold shadow"
                >
                  Justificar & Tancar Anomalia
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL 3: REGISTRE DE NOU VEHICLE / MAQUINÀRIA / REMOLC (Spec 006 RF-05) */}
      {modalNouVehicleObert && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-lg rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-6 space-y-4 shadow-xl text-slate-900 dark:text-slate-100">
            <div className="flex items-center justify-between pb-3 border-b border-slate-200 dark:border-slate-800">
              <div className="flex items-center gap-2">
                <Car className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
                <h3 className="font-bold text-sm font-mono">Alta de Nou Vehicle a la Flota</h3>
              </div>
              <button
                onClick={() => setModalNouVehicleObert(false)}
                className="p-1 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-400"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleCrearVehicle} className="space-y-4 text-xs font-mono">
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="font-bold text-slate-700 dark:text-slate-300">
                    Matrícula / Codi d'Actiu:
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="Ex: 8392-MBB o MINI-EXC-01"
                    value={novaMatricula}
                    onChange={(e) => setNovaMatricula(e.target.value)}
                    className="w-full p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs uppercase focus:outline-none"
                  />
                </div>

                <div className="space-y-1">
                  <label className="font-bold text-slate-700 dark:text-slate-300">
                    Distintiu Ambiental DGT:
                  </label>
                  <select
                    value={nouDistintiu}
                    onChange={(e) => setNouDistintiu(e.target.value)}
                    className="w-full p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none"
                  >
                    <option value="ZERO">0 Emissions (Blau)</option>
                    <option value="ECO">ECO (Verd/Blau)</option>
                    <option value="C">C (Verd)</option>
                    <option value="B">B (Groc)</option>
                    <option value="SENSE">Sense Distintiu</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="font-bold text-slate-700 dark:text-slate-300">Marca:</label>
                  <input
                    type="text"
                    required
                    placeholder="Ex: Renault, Toyota, Kubota"
                    value={novaMarca}
                    onChange={(e) => setNovaMarca(e.target.value)}
                    className="w-full p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none"
                  />
                </div>

                <div className="space-y-1">
                  <label className="font-bold text-slate-700 dark:text-slate-300">Model & Versió:</label>
                  <input
                    type="text"
                    required
                    placeholder="Ex: Master E-Tech L2H2"
                    value={nouModel}
                    onChange={(e) => setNouModel(e.target.value)}
                    className="w-full p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="font-bold text-slate-700 dark:text-slate-300">
                    Tipus de Propulsió:
                  </label>
                  <select
                    value={nouTipus}
                    onChange={(e) => setNouTipus(e.target.value)}
                    className="w-full p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none"
                  >
                    <option value="DIESEL">Dièsel (Combustió)</option>
                    <option value="GASOLINA">Gasolina</option>
                    <option value="EV">100% Elèctric (EV)</option>
                    <option value="PHEV">Híbrid Enchufable (PHEV)</option>
                    <option value="MAQUINARIA">Maquinària d'Obra (Horòmetre)</option>
                    <option value="REMOLC">Remolc de Transport (Exempt Consum)</option>
                  </select>
                </div>

                <div className="space-y-1">
                  <label className="font-bold text-slate-700 dark:text-slate-300">
                    Règim d'Adquisició:
                  </label>
                  <select
                    value={nouRegim}
                    onChange={(e) => setNouRegim(e.target.value)}
                    className="w-full p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none"
                  >
                    <option value="PROPIETAT">Compra en Propietat (Amortització)</option>
                    <option value="RENTING">Rènting / Lísing (Límits de km)</option>
                    <option value="SUBSTITUCIO">Vehicle de Sustitució Temporal</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="font-bold text-slate-700 dark:text-slate-300">
                    Odòmetre Inicial (km):
                  </label>
                  <input
                    type="number"
                    min={0}
                    value={nouOdometre}
                    onChange={(e) => setNouOdometre(Number(e.target.value))}
                    className="w-full p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none"
                  />
                </div>

                <div className="space-y-1">
                  <label className="font-bold text-slate-700 dark:text-slate-300">
                    Límit Contractual (km):
                  </label>
                  <input
                    type="number"
                    min={1000}
                    value={nouLimitKm}
                    onChange={(e) => setNouLimitKm(Number(e.target.value))}
                    className="w-full p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none"
                  />
                </div>
              </div>

              <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-200 dark:border-slate-800">
                <button
                  type="button"
                  onClick={() => setModalNouVehicleObert(false)}
                  className="px-3 py-2 rounded-xl bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 text-slate-700 dark:text-slate-300 font-bold"
                >
                  Cancel·lar
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold shadow"
                >
                  Donar d'Alta Vehicle
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
