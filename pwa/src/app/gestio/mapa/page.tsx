"use client";

import React, { useState, useEffect } from "react";
import {
  Compass,
  Layers,
  MapPin,
  Radio,
  Sliders,
  AlertTriangle,
  CheckCircle2,
  Users,
  Truck,
  Activity,
  Maximize2,
  Minimize2,
  Search,
  Eye,
  EyeOff,
  Wrench,
  Clock,
  ShieldAlert,
} from "lucide-react";
import { useGestio } from "@/lib/gestio-context";
import { apiFetch } from "@/lib/api";

interface IntervencioActiva {
  id: string;
  codi: string;
  client: string;
  titol: string;
  cap_colla: string;
  estat: "EN_OBRA" | "EN_RUTA" | "PENDENT" | "INCIDENCIA";
  coords: [number, number];
  sector: string;
  pressio_bar: number;
  codi_candat: string;
}

export default function GestioMapaPage() {
  const { rolActiu } = useGestio();

  // Mode de visualització GIS
  const [modeVisor, setModeVisor] = useState<"SAT" | "TOPO" | "CADASTRE">("SAT");

  // Commutadors de capes vectorials (Spec 001 RF-05)
  const [capaSigpac, setCapaSigpac] = useState<boolean>(true);
  const [capaCanonades, setCapaCanonades] = useState<boolean>(true);
  const [capaSensors, setCapaSensors] = useState<boolean>(true);
  const [capaColles, setCapaColles] = useState<boolean>(true);

  // Drawer lateral d'inspecció tècnica
  const [drawerObert, setDrawerObert] = useState<boolean>(true);

  // Dades d'intervencions carregades des del backend (Zero Mock Data)
  const [intervencions, setIntervencions] = useState<IntervencioActiva[]>([]);

  useEffect(() => {
    apiFetch<IntervencioActiva[]>("/intervencions/actives")
      .then(setIntervencions)
      .catch(() => setIntervencions([])); // Fallback buit
  }, []);

  const [intervencioSeleccionada, setIntervencioSeleccionada] = useState<IntervencioActiva | null>(intervencions[0] || null);

  return (
    <div className="flex-1 flex flex-col h-[calc(100vh-3.5rem)] relative overflow-hidden bg-slate-900 text-white select-none">
      {/* ===================================================================== */}
      {/* 1. VISOR CARTOGRÀFIC GIS TELEMETRIA TÀCTICA                           */}
      {/* ===================================================================== */}
      <div className="relative flex-1 h-full overflow-hidden bg-slate-950">
        {/* Capa de fons ortofoto satèl·lit / Dusk */}
        <div
          className="absolute inset-0 w-full h-full bg-cover bg-center transition-all duration-500 opacity-80"
          style={{
            backgroundImage:
              modeVisor === "SAT"
                ? "radial-gradient(circle at 50% 50%, rgba(2, 36, 72, 0.4), rgba(0, 14, 36, 0.95)), url('https://images.unsplash.com/photo-1524661135-423995f22d0b?auto=format&fit=crop&w=2000&q=80')"
                : modeVisor === "TOPO"
                ? "linear-gradient(rgba(15, 23, 42, 0.85), rgba(15, 23, 42, 0.95)), url('https://images.unsplash.com/photo-1506744038136-46273834b3fb?auto=format&fit=crop&w=2000&q=80')"
                : "linear-gradient(rgba(30, 41, 59, 0.9), rgba(15, 23, 42, 0.95))",
          }}
        />

        {/* Tactical SVG Engineering Vectors: PE-100 pipes, cadastre polygons */}
        <svg className="absolute inset-0 w-full h-full pointer-events-none z-10" xmlns="http://www.w3.org/2000/svg">
          <defs>
            <filter id="glow-cyan" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="3" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
            <filter id="glow-red" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="4" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
            <pattern id="tactical-grid" width="48" height="48" patternUnits="userSpaceOnUse">
              <path d="M 48 0 L 0 0 0 48" fill="none" stroke="rgba(76, 215, 246, 0.08)" strokeWidth="0.75" />
              <circle cx="48" cy="48" r="1" fill="rgba(76, 215, 246, 0.2)" />
            </pattern>
          </defs>

          {/* Dynamic Tactical Grid */}
          <rect width="100%" height="100%" fill="url(#tactical-grid)" />

          {/* Xarxa de Canonades PE-100 (Capa activa) */}
          {capaCanonades && (
            <g strokeLinecap="round" strokeLinejoin="round">
              {/* Alimentador Primari PE-100 63mm */}
              <path
                d="M 160,540 L 320,440 L 510,380 L 720,320 L 940,290 L 1140,210"
                fill="none"
                filter="url(#glow-cyan)"
                stroke="#38bdf8"
                strokeWidth="3"
                strokeDasharray="6,4"
              />
              {/* Ramal Secundari 32mm */}
              <path
                d="M 510,380 L 580,500 L 710,530 L 830,600"
                fill="none"
                stroke="#38bdf8"
                strokeWidth="2"
                strokeDasharray="4,4"
                className="opacity-70"
              />
              {/* Tram d'Incidència amb alta pressió */}
              <path
                d="M 720,320 L 800,390 L 880,370"
                fill="none"
                filter="url(#glow-red)"
                stroke="#f43f5e"
                strokeWidth="3"
                className="animate-pulse"
              />
            </g>
          )}

          {/* Polígon Parcel·lari SIGPAC Finca Els Arcs */}
          {capaSigpac && (
            <polygon
              points="440,280 620,240 760,330 700,460 520,430 430,340"
              fill="rgba(56, 189, 248, 0.08)"
              filter="url(#glow-cyan)"
              stroke="#38bdf8"
              strokeWidth="1.5"
              strokeDasharray="8,3"
            />
          )}
        </svg>

        {/* MARCADORS D'ACTIUS EN DIRECTE (Colles de Camp i Sensors IoT) */}
        {intervencions.length > 0 && (
          <div className="absolute inset-0 pointer-events-none z-20">
            {/* Marcador Colla 01 en obra */}
            {capaColles && (
              <div
                style={{ left: "54%", top: "42%" }}
                onClick={() => {
                  setIntervencioSeleccionada(intervencions[0]);
                  setDrawerObert(true);
                }}
                className="absolute -translate-x-1/2 -translate-y-1/2 pointer-events-auto cursor-pointer flex flex-col items-center group"
              >
                <div className="w-9 h-9 rounded-full bg-emerald-500/20 border-2 border-emerald-400 flex items-center justify-center text-white shadow-lg shadow-emerald-500/30 group-hover:scale-110 transition-transform">
                  <span className="w-3 h-3 rounded-full bg-emerald-400 animate-ping absolute"></span>
                  <MapPin className="w-5 h-5 fill-emerald-500 text-white" />
                </div>
                <div className="mt-1 px-2 py-0.5 rounded bg-slate-900/90 border border-slate-700 text-[10px] font-mono font-bold text-white shadow">
                  Colla 01 • En Obra
                </div>
              </div>
            )}

            {/* Marcador Sensor IoT de Pressió (Normal) */}
            {capaSensors && (
              <div
                style={{ left: "38%", top: "48%" }}
                className="absolute -translate-x-1/2 -translate-y-1/2 pointer-events-auto flex flex-col items-center"
              >
                <div className="w-7 h-7 rounded-lg bg-blue-500/20 border border-blue-400 flex items-center justify-center text-blue-300 shadow">
                  <Activity className="w-4 h-4" />
                </div>
                <span className="text-[9px] font-mono bg-slate-900/80 px-1 rounded text-blue-300 mt-0.5 border border-slate-700">
                  P-04: 14.2 bar
                </span>
              </div>
            )}

            {/* Marcador Sensor IoT de Pressió (Alerta Baixa) */}
            {capaSensors && (
              <div
                style={{ left: "68%", top: "37%" }}
                className="absolute -translate-x-1/2 -translate-y-1/2 pointer-events-auto flex flex-col items-center animate-bounce"
              >
                <div className="w-7 h-7 rounded-lg bg-rose-500/20 border border-rose-500 flex items-center justify-center text-rose-400 shadow shadow-rose-500/30">
                  <AlertTriangle className="w-4 h-4" />
                </div>
                <span className="text-[9px] font-mono bg-rose-950 px-1 rounded text-rose-300 mt-0.5 border border-rose-800 font-bold">
                  P-07: 2.1 bar
                </span>
              </div>
            )}
          </div>
        )}

        {/* TOP FLOATING HUD: Operational Tickers & Layer Selectors */}
        <div className="absolute top-3 left-3 right-3 z-30 flex flex-wrap items-center justify-between gap-2 pointer-events-none">
          {/* Ticker Esquerre: Localització i RTK */}
          <div className="flex items-center gap-2 pointer-events-auto bg-slate-900/90 backdrop-blur-md px-3 py-2 rounded-xl border border-slate-800 shadow-lg">
            <Radio className="w-4 h-4 text-emerald-400 animate-pulse" />
            <div>
              <p className="text-[10px] font-mono text-slate-400 uppercase tracking-wider">
                Sector Hidràulic Nord
              </p>
              <h3 className="text-xs font-bold text-white">Solsonès Central • Sector B-04</h3>
            </div>
            <div className="h-5 w-px bg-slate-700 mx-1"></div>
            <span className="text-[10px] font-mono font-semibold text-emerald-400 bg-emerald-950/60 px-1.5 py-0.5 rounded border border-emerald-800">
              CADASTRE VINCULAT
            </span>
          </div>

          {/* Ticker Centre-Dreta: Selectors de Capes i Manera de Visualització */}
          <div className="flex items-center gap-2 pointer-events-auto bg-slate-900/90 backdrop-blur-md p-1.5 rounded-xl border border-slate-800 shadow-lg">
            {/* View Mode Buttons */}
            <div className="flex items-center bg-slate-800 p-0.5 rounded-lg text-xs font-mono">
              <button
                onClick={() => setModeVisor("SAT")}
                className={`px-2.5 py-1 rounded-md transition-colors ${
                  modeVisor === "SAT"
                    ? "bg-emerald-600 text-white font-bold"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                Satèl·lit 2D
              </button>
              <button
                onClick={() => setModeVisor("TOPO")}
                className={`px-2.5 py-1 rounded-md transition-colors ${
                  modeVisor === "TOPO"
                    ? "bg-emerald-600 text-white font-bold"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                Topogràfic 3D
              </button>
              <button
                onClick={() => setModeVisor("CADASTRE")}
                className={`px-2.5 py-1 rounded-md transition-colors ${
                  modeVisor === "CADASTRE"
                    ? "bg-emerald-600 text-white font-bold"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                Cadastre
              </button>
            </div>

            <div className="h-5 w-px bg-slate-700"></div>

            {/* Checkboxes de Capes Vectorials */}
            <div className="hidden lg:flex items-center gap-1.5 text-[11px] font-mono">
              <label className="flex items-center gap-1.5 px-2 py-1 rounded bg-slate-800/80 cursor-pointer hover:bg-slate-800">
                <input
                  type="checkbox"
                  checked={capaSigpac}
                  onChange={(e) => setCapaSigpac(e.target.checked)}
                  className="accent-emerald-500 rounded w-3.5 h-3.5"
                />
                <span className="text-slate-200">SIGPAC</span>
              </label>

              <label className="flex items-center gap-1.5 px-2 py-1 rounded bg-slate-800/80 cursor-pointer hover:bg-slate-800">
                <input
                  type="checkbox"
                  checked={capaCanonades}
                  onChange={(e) => setCapaCanonades(e.target.checked)}
                  className="accent-emerald-500 rounded w-3.5 h-3.5"
                />
                <span className="text-sky-300">Canonades PE</span>
              </label>

              <label className="flex items-center gap-1.5 px-2 py-1 rounded bg-slate-800/80 cursor-pointer hover:bg-slate-800">
                <input
                  type="checkbox"
                  checked={capaSensors}
                  onChange={(e) => setCapaSensors(e.target.checked)}
                  className="accent-emerald-500 rounded w-3.5 h-3.5"
                />
                <span className="text-amber-300">Sensors IoT</span>
              </label>

              <label className="flex items-center gap-1.5 px-2 py-1 rounded bg-slate-800/80 cursor-pointer hover:bg-slate-800">
                <input
                  type="checkbox"
                  checked={capaColles}
                  onChange={(e) => setCapaColles(e.target.checked)}
                  className="accent-emerald-500 rounded w-3.5 h-3.5"
                />
                <span className="text-emerald-300">Colles</span>
              </label>
            </div>

            {/* Botó Toggle Drawer */}
            <button
              onClick={() => setDrawerObert(!drawerObert)}
              className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300"
              title="Commutar Tauler d'Inspecció"
            >
              <Sliders className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* ESTAT BUIT CANÒNIC ZERO MOCK DATA */}
        {intervencions.length === 0 && (
          <div className="absolute inset-0 flex items-center justify-center z-30 pointer-events-none">
            <div className="p-8 rounded-2xl bg-slate-900/90 border border-slate-800 text-center max-w-sm shadow-2xl backdrop-blur-md pointer-events-auto">
              <div className="w-14 h-14 rounded-full bg-slate-800 text-emerald-400 flex items-center justify-center mx-auto mb-3 border border-slate-700">
                <Compass className="w-7 h-7" />
              </div>
              <h3 className="text-sm font-bold text-white">
                No hi ha intervencions actives sobre el mapa
              </h3>
              <p className="text-xs text-slate-400 mt-1">
                La Torre de Control està a l'espera de noves ordres de treball o colles en ruta.
              </p>
              <button
                onClick={() => {
                  apiFetch<IntervencioActiva[]>("/intervencions/actives")
                    .then(setIntervencions)
                    .catch(() => setIntervencions([]));
                }}
                className="mt-4 px-3 py-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold shadow"
              >
                Carregar Intervencions d'Obra
              </button>
            </div>
          </div>
        )}
      </div>

      {/* ===================================================================== */}
      {/* 2. DRAWER LATERAL D'INSPECCIÓ TÈCNICA D'ENGINYERIA                     */}
      {/* ===================================================================== */}
      {drawerObert && intervencioSeleccionada && (
        <aside className="w-96 bg-white dark:bg-slate-900 border-l border-slate-200 dark:border-slate-800 p-4 flex flex-col justify-between overflow-y-auto z-40 shadow-2xl text-slate-900 dark:text-slate-100 transition-colors">
          <div className="space-y-4">
            {/* Capçalera del Drawer */}
            <div className="flex items-start justify-between pb-3 border-b border-slate-200 dark:border-slate-800">
              <div>
                <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300">
                  {intervencioSeleccionada.codi}
                </span>
                <h3 className="text-sm font-bold text-slate-800 dark:text-slate-100 mt-1">
                  Inspecció Tècnica d'Obra
                </h3>
                <p className="text-xs text-slate-500">{intervencioSeleccionada.client}</p>
              </div>
              <button
                onClick={() => setDrawerObert(false)}
                className="p-1 rounded text-slate-400 hover:text-slate-600 dark:hover:text-white"
              >
                &times;
              </button>
            </div>

            {/* Dades de la Finca i Coordenades WGS84 */}
            <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-800 space-y-2 text-xs">
              <div className="flex items-center justify-between">
                <span className="text-slate-500 text-[11px]">Coordenades WGS84:</span>
                <span className="font-mono font-bold text-slate-800 dark:text-slate-200">
                  {intervencioSeleccionada.coords[0].toFixed(4)} N, {intervencioSeleccionada.coords[1].toFixed(4)} E
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-500 text-[11px]">Codi Candat Accés:</span>
                <span className="font-mono font-bold px-1.5 py-0.5 rounded bg-amber-100 dark:bg-amber-950 text-amber-800 dark:text-amber-300">
                  {intervencioSeleccionada.codi_candat}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-500 text-[11px]">Cap de Colla:</span>
                <span className="font-bold text-slate-800 dark:text-slate-200">
                  {intervencioSeleccionada.cap_colla}
                </span>
              </div>
            </div>

            {/* Telemetria Hidràulica IoT en temps real */}
            <div className="p-3 rounded-xl bg-blue-50 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-900 space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-blue-900 dark:text-blue-300 flex items-center gap-1.5">
                  <Activity className="w-4 h-4 text-blue-600 dark:text-blue-400" />
                  Telemetria Xarxa Hidràulica
                </span>
                <span className="text-[10px] font-mono px-1.5 py-0.5 bg-blue-600 text-white rounded font-bold">
                  IoT LIVE
                </span>
              </div>
              <div className="flex items-baseline justify-between pt-1">
                <span className="text-xs text-slate-600 dark:text-slate-300">Pressió de Treball:</span>
                <span className="text-lg font-black font-mono text-blue-700 dark:text-blue-400">
                  {intervencioSeleccionada.pressio_bar} bar
                </span>
              </div>
              <p className="text-[10px] text-blue-600 dark:text-blue-400">
                Límit de seguretat admès: 16.0 bar (Canonada PE-100 PN16)
              </p>
            </div>

            {/* VETO D'ENGINYER (Spec 001 RF-03 / Spec 005): S'oculta qualsevol informació econòmica */}
            {rolActiu === "ENGINYER" ? (
              <div className="p-3 rounded-xl bg-slate-100 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 text-center">
                <p className="text-[10px] font-mono text-slate-500 uppercase tracking-wider">
                  Veto d'Enginyer Actiu (Spec 001 RF-03)
                </p>
                <p className="text-xs text-slate-600 dark:text-slate-300 mt-1">
                  Les mètriques financeres, costos i marges d'obra queden restringides a la Direcció.
                </p>
              </div>
            ) : (
              <div className="p-3 rounded-xl bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800 space-y-1">
                <p className="text-[10px] font-mono uppercase font-bold text-emerald-800 dark:text-emerald-300">
                  Dades Administratives (Visibles per Boss/Secretaria)
                </p>
                <div className="flex justify-between text-xs">
                  <span className="text-slate-500">Pressupost Aprovat:</span>
                  <span className="font-bold text-slate-800 dark:text-slate-100">1.840,00 €</span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-slate-500">Marge Estimat:</span>
                  <span className="font-bold text-emerald-600">32.4%</span>
                </div>
              </div>
            )}
          </div>

          <div className="pt-3 border-t border-slate-200 dark:border-slate-800 space-y-2">
            <button
              onClick={() => alert("S'ha emès l'avís d'inspecció a la PWA de la Colla 01.")}
              className="w-full py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold shadow transition-all"
            >
              Emetre Ordre d'Inspecció a Camp
            </button>
            <button
              onClick={() => setIntervencions([])}
              className="w-full py-2 rounded-xl bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-600 dark:text-slate-400 text-xs font-semibold"
            >
              Provar Estat Buit (Zero-Mock)
            </button>
          </div>
        </aside>
      )}
    </div>
  );
}
