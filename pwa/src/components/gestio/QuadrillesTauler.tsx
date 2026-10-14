"use client";

import React, { useState } from "react";
import { Users, Truck, Phone, Navigation, MapPin, Briefcase, Plus, Check } from "lucide-react";
import { Feina, Operari } from "@/components/gestio/Map";

interface QuadrillesTaulerProps {
  operaris: Operari[];
  feines: Feina[];
  selectedOperariId: string | null;
  onSelectOperari: (operariId: string) => void;
  onSelectFeina?: (feinaId: string) => void;
  onDropAssignment: (feinaId: string, versio: number, operariId: string) => Promise<void>;
}

export function QuadrillesTauler({
  operaris,
  feines,
  selectedOperariId,
  onSelectOperari,
  onSelectFeina,
  onDropAssignment,
}: QuadrillesTaulerProps) {
  const [dragOverOperariId, setDragOverOperariId] = useState<string | null>(null);

  const handleDragOver = (e: React.DragEvent, operariId: string) => {
    e.preventDefault();
    if (dragOverOperariId !== operariId) {
      setDragOverOperariId(operariId);
    }
  };

  const handleDragLeave = () => {
    setDragOverOperariId(null);
  };

  const handleDrop = async (e: React.DragEvent, operariId: string) => {
    e.preventDefault();
    setDragOverOperariId(null);
    const feinaId = e.dataTransfer.getData("feinaId");
    const versioStr = e.dataTransfer.getData("versio");
    if (!feinaId || !versioStr) return;
    await onDropAssignment(feinaId, parseInt(versioStr, 10), operariId);
    onSelectOperari(operariId);
  };

  return (
    <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm p-5 space-y-4">
      {/* Capçalera del Tauler d'Operaris */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 border-b border-slate-100 dark:border-slate-800">
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-xl bg-blue-50 dark:bg-blue-900/30 flex items-center justify-center text-blue-600 dark:text-blue-400">
            <Users className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-bold text-slate-800 dark:text-slate-100">
                Quadrilles Actives de Camp
              </h2>
              <span className="text-xs font-mono font-bold px-2 py-0.5 rounded-full bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300">
                {operaris.length} en servei
              </span>
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Clica per centrar al mapa • Arrossega ordres de treball sobre cada colla per assignar-les (Drop & Go)
            </p>
          </div>
        </div>
      </div>

      {/* Grid de Targetes d'Operaris */}
      {operaris.length === 0 ? (
        <div className="p-8 text-center bg-slate-50 dark:bg-slate-800/40 rounded-xl border border-dashed border-slate-200 dark:border-slate-800">
          <p className="text-sm font-medium text-slate-500">
            No hi ha cap operari actiu en servei actualment.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3.5">
          {operaris.map((operari) => {
            const assignedFeines = feines.filter((f) => f.cap_de_colla_id === operari.id);
            const isSelected = selectedOperariId === operari.id;
            const isDragOver = dragOverOperariId === operari.id;

            return (
              <div
                key={operari.id}
                onDragOver={(e) => handleDragOver(e, operari.id)}
                onDragLeave={handleDragLeave}
                onDrop={(e) => handleDrop(e, operari.id)}
                onClick={() => onSelectOperari(operari.id)}
                className={`group relative rounded-xl border-2 transition-all p-3.5 flex flex-col justify-between shadow-sm cursor-pointer select-none ${
                  isDragOver
                    ? "border-emerald-500 bg-emerald-50 dark:bg-emerald-950/40 ring-4 ring-emerald-500/20 scale-[1.01]"
                    : isSelected
                    ? "border-blue-500 bg-blue-50/50 dark:bg-blue-950/30 ring-2 ring-blue-500/20 shadow-md"
                    : "border-slate-200 dark:border-slate-800 bg-slate-50/60 dark:bg-slate-800/50 hover:border-blue-400 dark:hover:border-blue-500 hover:bg-white dark:hover:bg-slate-800"
                }`}
              >
                {/* Dades de l'operari */}
                <div>
                  <div className="flex items-start justify-between gap-2 pb-2.5 mb-2.5 border-b border-slate-200/80 dark:border-slate-700/60">
                    <div className="flex items-center gap-2.5 min-w-0">
                      <div className="w-8 h-8 rounded-full bg-blue-500/20 text-blue-600 dark:text-blue-400 font-bold text-xs flex items-center justify-center border border-blue-500/30 shrink-0">
                        {operari.nom[0]}
                        {operari.cognoms ? operari.cognoms[0] : ""}
                      </div>
                      <div className="min-w-0">
                        <h3 className="text-xs font-bold text-slate-800 dark:text-slate-100 leading-tight truncate">
                          {operari.nom} {operari.cognoms || ""}
                        </h3>
                        <span className="text-[11px] text-blue-600 dark:text-blue-400 font-mono block truncate">
                          {operari.rol}
                        </span>
                      </div>
                    </div>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded-full font-bold bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700 shrink-0">
                      {assignedFeines.length} OT
                    </span>
                  </div>

                  {/* Accions ràpides: Centrar al mapa & Telèfon */}
                  <div className="flex items-center justify-between text-[11px] mb-2.5 text-slate-500 dark:text-slate-400">
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        onSelectOperari(operari.id);
                      }}
                      className="inline-flex items-center gap-1 font-bold text-blue-600 dark:text-blue-400 hover:underline"
                    >
                      <Navigation className="w-3 h-3" />
                      <span>Centrar al mapa</span>
                    </button>

                    {operari.telefon && (
                      <a
                        href={`tel:${operari.telefon}`}
                        onClick={(e) => e.stopPropagation()}
                        className="inline-flex items-center gap-1 hover:text-emerald-500 transition-colors"
                      >
                        <Phone className="w-3 h-3" />
                        <span>{operari.telefon}</span>
                      </a>
                    )}
                  </div>

                  {/* Llistat de feines assignades / Zona Drop & Go */}
                  <div className="space-y-1.5 max-h-32 overflow-y-auto pr-1">
                    {assignedFeines.length === 0 ? (
                      <div className="py-2.5 px-2 text-center rounded-lg border border-dashed border-slate-200 dark:border-slate-700 text-slate-400 text-[11px]">
                        <span>Cap feina assignada. Arrossega una ordre aquí</span>
                      </div>
                    ) : (
                      assignedFeines.map((feina) => (
                        <div
                          key={feina.id}
                          onClick={(e) => {
                            e.stopPropagation();
                            if (onSelectFeina) onSelectFeina(feina.id);
                          }}
                          className="p-1.5 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700/80 hover:border-emerald-500 text-xs flex items-center justify-between transition-colors shadow-2xs group/item"
                          title="Clica per veure al mapa"
                        >
                          <div className="flex items-center gap-1.5 min-w-0">
                            <span className="font-mono font-bold text-[10px] text-emerald-600 dark:text-emerald-400 shrink-0">
                              {feina.codi}
                            </span>
                            <span className="text-[11px] text-slate-700 dark:text-slate-300 truncate">
                              {feina.titol}
                            </span>
                          </div>
                          <MapPin className="w-3 h-3 text-slate-400 group-hover/item:text-emerald-500 shrink-0 ml-1" />
                        </div>
                      ))
                    )}
                  </div>
                </div>

                {/* Zona Drop & Go Highlight */}
                {isDragOver && (
                  <div className="mt-2 text-center py-1 text-[11px] font-bold text-emerald-600 dark:text-emerald-400 bg-emerald-100/60 dark:bg-emerald-900/40 rounded-lg">
                    Deixa anar per assignar aquesta feina
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
