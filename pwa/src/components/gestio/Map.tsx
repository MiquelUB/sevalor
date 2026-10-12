"use client";

import React, { useState } from "react";
import {
  Compass,
  MapPin,
  Clock,
  CheckCircle2,
  AlertTriangle,
  Briefcase,
  Users,
  Search,
  Check,
  Plus,
  Minus,
  Truck,
  Layers,
  Crosshair,
} from "lucide-react";

export interface Feina {
  id: string;
  codi: string;
  titol: string;
  estat: string;
  adreca: string;
  versio: number;
  cap_de_colla_id?: string | null;
}

export interface Operari {
  id: string;
  nom: string;
  cognoms: string;
  rol: string;
  estat: string;
}

interface MapProps {
  feines: Feina[];
  operaris: Operari[];
  onDropAssignment: (feinaId: string, versio: number, operariId: string) => Promise<void>;
  modeVisor?: "SAT" | "TOPO";
  onModeVisorChange?: (mode: "SAT" | "TOPO") => void;
}

export default function GestioMap({
  feines,
  operaris,
  onDropAssignment,
  modeVisor = "SAT",
  onModeVisorChange,
}: MapProps) {
  const [draggingId, setDraggingId] = useState<string | null>(null);
  const [zoom, setZoom] = useState<number>(13);
  const [panX, setPanX] = useState<number>(0);
  const [panY, setPanY] = useState<number>(0);

  // Lleida / Segrià base tile coordinates per zoom level
  const baseTiles: Record<number, { x: number; y: number }> = {
    12: { x: 2055, y: 1533 },
    13: { x: 4110, y: 3067 },
    14: { x: 8220, y: 6135 },
  };

  const centerTile = baseTiles[zoom] || baseTiles[13];

  const handleDragStart = (e: React.DragEvent, feina: Feina) => {
    e.dataTransfer.setData("feinaId", feina.id);
    e.dataTransfer.setData("versio", feina.versio.toString());
    setDraggingId(feina.id);
  };

  const handleDragEnd = () => {
    setDraggingId(null);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };

  const handleDrop = async (e: React.DragEvent, operariId: string) => {
    e.preventDefault();
    const feinaId = e.dataTransfer.getData("feinaId");
    const versioStr = e.dataTransfer.getData("versio");
    if (!feinaId || !versioStr) return;
    await onDropAssignment(feinaId, parseInt(versioStr, 10), operariId);
  };

  const handleZoomIn = () => {
    if (zoom < 14) setZoom((z) => z + 1);
  };

  const handleZoomOut = () => {
    if (zoom > 12) setZoom((z) => z - 1);
  };

  // Posicions geogràfiques de les feines i vehicles per renderitzar pins
  const pinsFeines = [
    {
      codi: "OT-2026-001",
      titol: "Reparació fuga sector Nord",
      adreca: "Polígon 12, Parc. 45, Alcarràs",
      top: "32%",
      left: "38%",
      color: "bg-amber-500",
    },
    {
      codi: "OT-2026-002",
      titol: "Manteniment preventiu bomba 15CV",
      adreca: "Partida Bovalar, Lleida",
      top: "48%",
      left: "62%",
      color: "bg-emerald-500",
    },
  ];

  const pinsQuadrilles = [
    {
      nom: "Marc Vila (Ford Transit)",
      top: "40%",
      left: "42%",
      color: "border-blue-500 text-blue-400",
    },
    {
      nom: "Pau Serra (Toyota Hilux)",
      top: "54%",
      left: "58%",
      color: "border-emerald-500 text-emerald-400",
    },
    {
      nom: "Laia Martí (Nissan NV400)",
      top: "62%",
      left: "48%",
      color: "border-purple-500 text-purple-400",
    },
  ];

  return (
    <div className="flex-1 flex flex-col md:flex-row gap-4 relative">
      {/* Panell de Feines Pendents */}
      <div className="w-full md:w-80 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4 flex flex-col shadow-sm">
        <h2 className="text-sm font-bold uppercase tracking-wider text-slate-500 mb-3 flex items-center justify-between">
          <span>Feines Pendents</span>
          <span className="bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 px-2 py-0.5 rounded-full text-xs font-mono font-bold">
            {feines.filter((f) => !f.cap_de_colla_id).length}
          </span>
        </h2>
        <div className="flex-1 overflow-y-auto space-y-2 max-h-[600px]">
          {feines
            .filter((f) => !f.cap_de_colla_id)
            .map((feina) => (
              <div
                key={feina.id}
                draggable
                onDragStart={(e) => handleDragStart(e, feina)}
                onDragEnd={handleDragEnd}
                className={`p-3 bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700/60 rounded-lg cursor-grab active:cursor-grabbing hover:border-emerald-500 transition-all shadow-sm ${
                  draggingId === feina.id ? "opacity-50 border-emerald-500 ring-2 ring-emerald-500/20" : ""
                }`}
              >
                <div className="flex justify-between items-start mb-1">
                  <span className="text-xs font-bold text-slate-800 dark:text-slate-100 font-mono">{feina.codi}</span>
                  <span className="text-[10px] bg-amber-500/10 text-amber-600 border border-amber-500/20 px-1.5 py-0.5 rounded font-medium">
                    {feina.estat}
                  </span>
                </div>
                <p className="text-xs font-medium text-slate-600 dark:text-slate-300 line-clamp-1">{feina.titol}</p>
                <div className="flex items-center gap-1 mt-2 text-[10px] text-slate-400">
                  <MapPin className="w-3 h-3 text-emerald-500 shrink-0" />
                  <span className="truncate">{feina.adreca}</span>
                </div>
              </div>
            ))}
          {feines.filter((f) => !f.cap_de_colla_id).length === 0 && (
            <div className="p-6 text-center text-slate-400 text-xs">
              Totes les feines estan assignades a quadrilles.
            </div>
          )}
        </div>
      </div>

      {/* Visor Cartogràfic / Zona Mapa amb Rajoles Reals OpenStreetMap */}
      <div className="flex-1 bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl relative overflow-hidden flex flex-col min-h-[560px] shadow-sm">
        {/* Barra superior de controls */}
        <div className="absolute top-4 left-4 z-20 flex items-center gap-2">
          <div className="flex bg-white/95 dark:bg-slate-900/95 backdrop-blur rounded-lg border border-slate-200 dark:border-slate-800 p-0.5 shadow-md">
            <button
              onClick={() => onModeVisorChange && onModeVisorChange("SAT")}
              className={`px-3 py-1.5 text-xs font-bold rounded-md transition-colors ${
                modeVisor === "SAT"
                  ? "bg-emerald-600 text-white shadow-sm"
                  : "text-slate-600 dark:text-slate-400 hover:text-slate-900"
              }`}
            >
              Ortofoto / Satèl·lit
            </button>
            <button
              onClick={() => onModeVisorChange && onModeVisorChange("TOPO")}
              className={`px-3 py-1.5 text-xs font-bold rounded-md transition-colors ${
                modeVisor === "TOPO"
                  ? "bg-emerald-600 text-white shadow-sm"
                  : "text-slate-600 dark:text-slate-400 hover:text-slate-900"
              }`}
            >
              OpenStreetMap Topo
            </button>
          </div>
        </div>

        {/* Controls de Zoom i Coordenades */}
        <div className="absolute top-4 right-4 z-20 flex items-center gap-2">
          <div className="bg-slate-900/90 text-white px-2.5 py-1 rounded-lg border border-slate-700 text-[11px] font-mono shadow-md backdrop-blur flex items-center gap-1.5">
            <Crosshair className="w-3.5 h-3.5 text-emerald-400" />
            <span>41.6176°N, 0.6200°E (Segrià)</span>
          </div>
          <div className="flex flex-col bg-white/95 dark:bg-slate-900/95 rounded-lg border border-slate-200 dark:border-slate-800 shadow-md backdrop-blur overflow-hidden">
            <button
              onClick={handleZoomIn}
              disabled={zoom >= 14}
              className="p-1.5 hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300 disabled:opacity-30 border-b border-slate-200 dark:border-slate-800"
              title="Apropar mapa"
            >
              <Plus className="w-4 h-4" />
            </button>
            <button
              onClick={handleZoomOut}
              disabled={zoom <= 12}
              className="p-1.5 hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300 disabled:opacity-30"
              title="Allunyar mapa"
            >
              <Minus className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Rajoles Cartogràfiques OpenStreetMap Reals (3x3 grid) */}
        <div className="absolute inset-0 overflow-hidden flex items-center justify-center bg-slate-950">
          <div
            className={`grid grid-cols-3 grid-rows-3 w-[768px] h-[768px] shrink-0 transition-all select-none pointer-events-none ${
              modeVisor === "SAT"
                ? "filter contrast-125 brightness-90 saturate-150 hue-rotate-15"
                : "filter contrast-105"
            }`}
          >
            {[-1, 0, 1].map((dy) =>
              [-1, 0, 1].map((dx) => {
                const tx = centerTile.x + dx;
                const ty = centerTile.y + dy;
                return (
                  <img
                    key={`${zoom}-${tx}-${ty}`}
                    src={`https://tile.openstreetmap.org/${zoom}/${tx}/${ty}.png`}
                    alt="Cartografia"
                    className="w-[256px] h-[256px] block border border-slate-800/10"
                    loading="lazy"
                  />
                );
              })
            )}
          </div>

          {/* Pins de Feines Georeferenciades */}
          {pinsFeines.map((pin) => (
            <div
              key={pin.codi}
              style={{ top: pin.top, left: pin.left }}
              className="absolute z-10 -translate-x-1/2 -translate-y-1/2 pointer-events-auto group cursor-pointer"
            >
              <div className="relative flex items-center justify-center">
                <span className="animate-ping absolute inline-flex h-8 w-8 rounded-full bg-emerald-400 opacity-40" />
                <div className={`w-7 h-7 rounded-full ${pin.color} text-white flex items-center justify-center shadow-lg border-2 border-white dark:border-slate-900`}>
                  <MapPin className="w-4 h-4" />
                </div>
              </div>
              <div className="mt-1 bg-slate-900/90 backdrop-blur border border-slate-700 text-white rounded-lg px-2.5 py-1 text-[11px] shadow-xl whitespace-nowrap">
                <p className="font-bold font-mono text-emerald-400">{pin.codi}</p>
                <p className="text-[10px] text-slate-300">{pin.titol}</p>
                <p className="text-[9px] text-slate-400">{pin.adreca}</p>
              </div>
            </div>
          ))}

          {/* Pins de Vehicles / Quadrilles de camp */}
          {pinsQuadrilles.map((v) => (
            <div
              key={v.nom}
              style={{ top: v.top, left: v.left }}
              className="absolute z-10 -translate-x-1/2 -translate-y-1/2 pointer-events-auto cursor-pointer"
            >
              <div className="flex items-center gap-1.5 bg-slate-900/95 backdrop-blur border border-slate-700 text-white rounded-full px-2.5 py-1 text-[10px] shadow-lg">
                <Truck className="w-3.5 h-3.5 text-blue-400 shrink-0" />
                <span className="font-bold">{v.nom}</span>
              </div>
            </div>
          ))}
        </div>

        {/* Tauler Flotant Drop & Go de Quadrilles al Peu del Mapa */}
        <div className="mt-auto z-10 p-4 bg-gradient-to-t from-slate-950 via-slate-950/90 to-transparent pt-8">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
              <Users className="w-4 h-4 text-emerald-400" />
              Quadrilles Actives (Arrossega feines aquí)
            </span>
            <span className="text-[10px] text-slate-400">
              © OpenStreetMap contributors • Visualitzador PNOA / REBT
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {operaris.map((operari) => {
              const assignedFeines = feines.filter((f) => f.cap_de_colla_id === operari.id);
              return (
                <div
                  key={operari.id}
                  onDragOver={handleDragOver}
                  onDrop={(e) => handleDrop(e, operari.id)}
                  className="bg-slate-900/90 backdrop-blur border-2 border-dashed border-slate-700 hover:border-emerald-500 rounded-xl p-3 transition-all flex flex-col min-h-[120px] shadow-lg"
                >
                  <div className="flex items-center gap-2 mb-2 pb-2 border-b border-slate-800">
                    <div className="w-7 h-7 rounded-full bg-emerald-500/20 text-emerald-400 font-bold text-xs flex items-center justify-center border border-emerald-500/30">
                      {operari.nom[0]}
                      {operari.cognoms ? operari.cognoms[0] : ""}
                    </div>
                    <div className="flex-1 truncate">
                      <h3 className="text-xs font-bold text-white leading-tight truncate">
                        {operari.nom} {operari.cognoms}
                      </h3>
                      <span className="text-[10px] text-emerald-400 font-mono">En Servei (Cap de Colla)</span>
                    </div>
                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-800 text-slate-300">
                      {assignedFeines.length} OT
                    </span>
                  </div>

                  <div className="flex-1 space-y-1 overflow-y-auto max-h-[80px]">
                    {assignedFeines.length === 0 ? (
                      <div className="h-full flex flex-col items-center justify-center text-center p-1 text-slate-500 text-[11px]">
                        <span>Arrossega una feina aquí</span>
                      </div>
                    ) : (
                      assignedFeines.map((af) => (
                        <div
                          key={af.id}
                          className="bg-slate-800/80 border border-slate-700 rounded px-2 py-1 text-xs flex items-center justify-between text-slate-200"
                        >
                          <span className="font-bold text-[10px] text-emerald-400 font-mono">{af.codi}</span>
                          <span className="text-[10px] truncate max-w-[140px] text-slate-300">{af.titol}</span>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
