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

  return (
    <div className="flex-1 flex flex-col md:flex-row gap-4 relative">
      {/* Panell de Feines Pendents */}
      <div className="w-full md:w-80 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4 flex flex-col shadow-sm">
        <h2 className="text-sm font-bold uppercase tracking-wider text-slate-500 mb-3 flex items-center justify-between">
          <span>Feines Pendents</span>
          <span className="bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 px-2 py-0.5 rounded-full text-xs">
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
                className={`p-3 bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700/60 rounded-lg cursor-grab active:cursor-grabbing hover:border-emerald-500 transition-all ${
                  draggingId === feina.id ? "opacity-50 border-emerald-500 ring-2 ring-emerald-500/20" : ""
                }`}
              >
                <div className="flex justify-between items-start mb-1">
                  <span className="text-xs font-bold text-slate-800 dark:text-slate-100">{feina.codi}</span>
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
        </div>
      </div>

      {/* Visor Cartogràfic / Zona Mapa */}
      <div className="flex-1 bg-slate-100 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl relative overflow-hidden flex flex-col min-h-[400px]">
        {/* Toggle Satèl·lit / Topogràfic */}
        <div className="absolute top-4 left-4 z-10 flex bg-white/90 dark:bg-slate-900/90 backdrop-blur rounded-lg border border-slate-200 dark:border-slate-800 p-0.5 shadow-sm">
          <button
            onClick={() => onModeVisorChange && onModeVisorChange("SAT")}
            className={`px-3 py-1 text-xs font-bold rounded-md transition-colors ${
              modeVisor === "SAT"
                ? "bg-slate-900 dark:bg-slate-100 text-white dark:text-slate-900"
                : "text-slate-600 dark:text-slate-400"
            }`}
          >
            Ortofoto PNOA
          </button>
          <button
            onClick={() => onModeVisorChange && onModeVisorChange("TOPO")}
            className={`px-3 py-1 text-xs font-bold rounded-md transition-colors ${
              modeVisor === "TOPO"
                ? "bg-slate-900 dark:bg-slate-100 text-white dark:text-slate-900"
                : "text-slate-600 dark:text-slate-400"
            }`}
          >
            Cadastre / Topogràfic
          </button>
        </div>

        {/* Simulació Cartogràfica Interactiva amb Grid Vectorial */}
        <div className="flex-1 relative flex items-center justify-center p-8 bg-slate-950">
          <div className="absolute inset-0 opacity-20 bg-[radial-gradient(#10b981_1px,transparent_1px)] [background-size:16px_16px]" />
          
          <div className="grid grid-cols-2 lg:grid-cols-3 gap-4 w-full max-w-4xl z-10">
            {operaris.map((operari) => {
              const assignedFeines = feines.filter((f) => f.cap_de_colla_id === operari.id);
              return (
                <div
                  key={operari.id}
                  onDragOver={handleDragOver}
                  onDrop={(e) => handleDrop(e, operari.id)}
                  className="bg-slate-900/80 backdrop-blur border-2 border-dashed border-slate-700 hover:border-emerald-500 rounded-xl p-4 transition-all flex flex-col min-h-[160px]"
                >
                  <div className="flex items-center gap-2 mb-2 pb-2 border-b border-slate-800">
                    <div className="w-8 h-8 rounded-full bg-emerald-500/20 text-emerald-400 font-bold text-xs flex items-center justify-center border border-emerald-500/30">
                      {operari.nom[0]}
                      {operari.cognoms[0]}
                    </div>
                    <div>
                      <h3 className="text-xs font-bold text-white leading-tight">
                        {operari.nom} {operari.cognoms}
                      </h3>
                      <span className="text-[10px] text-emerald-400 font-mono">En Servei (Cap de Colla)</span>
                    </div>
                  </div>

                  <div className="flex-1 space-y-1.5">
                    {assignedFeines.length === 0 ? (
                      <div className="h-full flex flex-col items-center justify-center text-center p-2 text-slate-500 text-[11px]">
                        <span>Arrossega una feina aquí</span>
                        <span className="text-[9px] text-slate-600">(Drop & Go per assignar)</span>
                      </div>
                    ) : (
                      assignedFeines.map((af) => (
                        <div
                          key={af.id}
                          className="bg-slate-800 border border-slate-700 rounded p-1.5 text-xs flex items-center justify-between text-slate-200"
                        >
                          <span className="font-bold text-[10px] text-emerald-400">{af.codi}</span>
                          <span className="text-[10px] truncate max-w-[120px]">{af.titol}</span>
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
