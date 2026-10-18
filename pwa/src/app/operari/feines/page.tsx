"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useAssignacions } from "@/lib/hooks/useAssignacions";
import { OrdreTreballLocal } from "@/lib/types/operari";

function AssignacioCard({ ordre }: { ordre: OrdreTreballLocal }) {
  const dataFmt = ordre.data_programada
    ? new Date(ordre.data_programada).toLocaleDateString("ca-ES", {
        day: "2-digit",
        month: "short",
      })
    : "Avui";
  const clientNom =
    ordre.client_nom ||
    (ordre as any).client?.rao_social ||
    "Client no especificat";
  const estat = ordre.estat_local || (ordre as any).estat || "PENDENT";
  const prioritat = ((ordre as any).prioritat || "NORMAL").toUpperCase();
  const isUrgent = prioritat === "URGENT" || prioritat === "CRITICA" || prioritat === "ALTA";
  const isEnCurs = ["EN_TRANSIT", "EN_RUTA", "EN_OBRA", "EN_CURS"].includes(estat);

  const barColor = isUrgent
    ? "bg-error"
    : isEnCurs
    ? "bg-secondary-container"
    : "bg-primary";

  const badgeClasses = isUrgent
    ? "bg-error-container text-on-error-container"
    : isEnCurs
    ? "bg-secondary-container/15 text-secondary"
    : "bg-primary-fixed text-on-primary-fixed-variant";

  return (
    <div className="bg-surface-container-lowest dark:bg-slate-900 rounded-xl shadow-[0_2px_8px_rgba(2,36,72,0.06)] overflow-hidden relative flex border border-outline-variant/20 dark:border-slate-800 mb-3 transition-transform active:scale-[0.99]">
      {/* Vertical Status Bar (4px Stitch Industrial Accent) */}
      <div className={`w-1.5 ${barColor} shrink-0`} />

      <div className="p-4 flex-1 flex flex-col gap-3">
        {/* Card Header */}
        <div className="flex justify-between items-start gap-2">
          <div className="flex flex-col">
            <span className="text-[11px] font-mono font-bold text-on-surface-variant dark:text-slate-400 tracking-wider uppercase">
              #{ordre.codi}
            </span>
            <h3 className="text-[17px] font-bold text-primary dark:text-white leading-snug mt-0.5">
              {ordre.titol}
            </h3>
          </div>
          <span
            className={`inline-flex items-center px-2.5 py-1 rounded-full text-[10px] font-extrabold uppercase tracking-wider shrink-0 ${badgeClasses}`}
          >
            {isUrgent ? "URGENT" : estat.replace("_", " ")}
          </span>
        </div>

        {/* Client & Description */}
        <div className="space-y-1.5">
          <div className="flex items-center gap-2 text-on-surface-variant dark:text-slate-300">
            <span className="material-symbols-outlined text-[18px] text-secondary shrink-0">
              business
            </span>
            <span className="text-xs font-semibold truncate">{clientNom}</span>
          </div>

          {(ordre as any).adreca && (
            <div className="flex items-center gap-2 text-on-surface-variant dark:text-slate-400">
              <span className="material-symbols-outlined text-[18px] text-primary dark:text-slate-400 shrink-0">
                location_on
              </span>
              <span className="text-xs font-medium truncate">
                {(ordre as any).adreca}
              </span>
            </div>
          )}

          {ordre.descripcio && (
            <p className="text-xs text-on-surface-variant dark:text-slate-400 line-clamp-2 pt-0.5">
              {ordre.descripcio}
            </p>
          )}
        </div>

        {/* Footer Metadata & Action */}
        <div className="pt-2 border-t border-surface-container dark:border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-1.5 text-xs font-mono text-on-surface-variant dark:text-slate-400">
            <span className="material-symbols-outlined text-[16px]">
              schedule
            </span>
            <span>🗓 {dataFmt}</span>
          </div>

          <Link
            href={`/operari/feines/${ordre.id}`}
            className={`px-4 py-2 rounded-lg text-xs font-bold uppercase tracking-wider flex items-center gap-1.5 shadow-sm transition-all active:scale-95 ${
              isEnCurs
                ? "bg-secondary-container text-white"
                : "bg-primary text-white"
            }`}
          >
            <span>Obrir Feina</span>
            <span className="material-symbols-outlined text-[16px]">
              arrow_forward
            </span>
          </Link>
        </div>
      </div>
    </div>
  );
}

export default function FeinesKanbanPage() {
  const { ordres, loading, error, refetch } = useAssignacions();
  const [searchQuery, setSearchQuery] = useState("");

  const filteredOrdres = ordres.filter((o) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    return (
      o.titol?.toLowerCase().includes(q) ||
      o.codi?.toLowerCase().includes(q) ||
      o.client_nom?.toLowerCase().includes(q) ||
      o.descripcio?.toLowerCase().includes(q)
    );
  });

  const pendents = filteredOrdres.filter((o) =>
    ["PENDENT", "ASSIGNADA", "PROGRAMADA", "PAUSADA"].includes(
      o.estat_local || (o as any).estat
    )
  );
  const enCurs = filteredOrdres.filter((o) =>
    ["EN_TRANSIT", "EN_RUTA", "EN_OBRA", "EN_CURS"].includes(
      o.estat_local || (o as any).estat
    )
  );

  const avuiFormatat = new Intl.DateTimeFormat("ca-ES", {
    day: "numeric",
    month: "short",
  }).format(new Date());

  return (
    <div className="min-h-screen pb-20 bg-surface dark:bg-slate-950">
      {/* Stitch Top Sub-Header & Search Bar */}
      <header className="px-4 pt-4 pb-3 bg-surface-container-lowest dark:bg-slate-900 border-b border-outline-variant/20 dark:border-slate-800 sticky top-0 z-10 shadow-sm">
        <div className="flex items-center justify-between mb-3">
          <div>
            <h1 className="text-xl font-extrabold text-primary dark:text-white tracking-tight">
              Tauler de Feines
            </h1>
            <p className="text-xs text-on-surface-variant dark:text-slate-400 font-medium">
              Les meves feines — Avui, {avuiFormatat}
            </p>
          </div>
          <button
            onClick={refetch}
            className="flex items-center gap-1.5 bg-surface-container-low dark:bg-slate-800 hover:bg-surface-container px-3 py-1.5 rounded-full border border-outline-variant/30 transition-colors"
            title="Sincronitzar assignacions"
          >
            <span className="w-2 h-2 rounded-full bg-secondary-container animate-pulse" />
            <span className="text-[11px] font-bold text-primary dark:text-slate-200 uppercase tracking-wider">
              Sincronitzat
            </span>
          </button>
        </div>

        {/* Search Input */}
        <div className="relative flex items-center">
          <span className="material-symbols-outlined absolute left-3 text-outline text-[20px]">
            search
          </span>
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Cerca per finca, client o codi..."
            className="w-full pl-10 pr-4 py-2.5 bg-surface-container-low dark:bg-slate-800 rounded-xl border border-outline-variant/30 dark:border-slate-700 text-xs font-medium text-on-surface dark:text-white placeholder:text-outline focus:outline-none focus:ring-2 focus:ring-primary"
          />
        </div>
      </header>

      {/* Main Content */}
      <main className="p-4 max-w-md mx-auto">
        {loading && ordres.length === 0 ? (
          <div className="flex flex-col justify-center items-center h-48 gap-2">
            <span className="material-symbols-outlined text-3xl text-primary animate-spin">
              sync
            </span>
            <p className="text-xs font-bold uppercase tracking-wider text-on-surface-variant animate-pulse">
              Carregant assignacions...
            </p>
          </div>
        ) : error ? (
          <div className="p-4 rounded-xl mb-6 border border-error/30 bg-error-container/40 text-on-error-container">
            <h2 className="font-bold text-sm mb-1 flex items-center gap-1.5">
              <span className="material-symbols-outlined text-base">
                error
              </span>
              Error de connexió
            </h2>
            <p className="text-xs mb-3">{error}</p>
            <button
              onClick={refetch}
              className="px-4 py-2 rounded-lg text-xs font-bold bg-surface-container-lowest text-error border border-error/30 shadow-sm"
            >
              Tornar a provar
            </button>
          </div>
        ) : ordres.length === 0 ? (
          /* ZERO MOCK DATA - Empty State */
          <div className="flex flex-col items-center justify-center py-14 px-5 text-center rounded-2xl border-2 border-dashed border-outline-variant/40 bg-surface-container-lowest dark:bg-slate-900 shadow-sm">
            <div
              className="w-14 h-14 rounded-2xl bg-surface-container-low dark:bg-slate-800 flex items-center justify-center text-2xl mb-3"
              role="img"
              aria-label="Buit"
            >
              📋
            </div>
            <h2 className="text-base font-extrabold text-primary dark:text-white mb-1">
              Cap tasca assignada avui
            </h2>
            <p className="text-xs text-on-surface-variant dark:text-slate-400 mb-5 max-w-xs">
              No tens cap ordre de treball programada. Pots revisar de nou més tard.
            </p>
            <button
              onClick={refetch}
              className="px-5 py-2.5 rounded-xl text-xs font-bold uppercase tracking-wider bg-primary text-white shadow-md hover:opacity-95 transition-opacity flex items-center gap-1.5"
            >
              <span className="material-symbols-outlined text-sm">refresh</span>
              Refrescar
            </button>
          </div>
        ) : (
          <div className="space-y-6">
            {/* Column: En Curs */}
            <section>
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-xs font-extrabold uppercase tracking-wider text-primary dark:text-white flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full bg-secondary-container animate-pulse" />
                  En Curs ({enCurs.length})
                </h2>
              </div>
              {enCurs.length > 0 ? (
                enCurs.map((ordre) => (
                  <AssignacioCard key={ordre.id} ordre={ordre} />
                ))
              ) : (
                <div className="p-4 rounded-xl text-xs font-medium text-center border border-dashed border-outline-variant/40 text-on-surface-variant dark:text-slate-400 bg-surface-container-lowest/50 dark:bg-slate-900/40">
                  Cap feina activa en aquest moment.
                </div>
              )}
            </section>

            {/* Column: Pendents */}
            <section>
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-xs font-extrabold uppercase tracking-wider text-on-surface-variant dark:text-slate-400 flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-outline" />
                  Pendents ({pendents.length})
                </h2>
              </div>
              {pendents.length > 0 ? (
                pendents.map((ordre) => (
                  <AssignacioCard key={ordre.id} ordre={ordre} />
                ))
              ) : (
                <div className="p-4 rounded-xl text-xs font-medium text-center border border-dashed border-outline-variant/40 text-on-surface-variant dark:text-slate-400 bg-surface-container-lowest/50 dark:bg-slate-900/40">
                  No queden tasques pendents.
                </div>
              )}
            </section>
          </div>
        )}
      </main>
    </div>
  );
}