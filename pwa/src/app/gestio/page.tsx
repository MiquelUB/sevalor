"use client";

import React, { useState, useEffect } from "react";
import { Users, Truck, AlertTriangle, CheckCircle2, Wrench, ShieldAlert, Calendar, MapPin, Eye, FileText } from "lucide-react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import { CrearOTModal } from "@/components/gestio/CrearOTModal";

export default function GestioDashboardPage() {
  const [showModalOT, setShowModalOT] = useState(false);
  const [hud, setHud] = useState({
    active_jobs: 0,
    completed_jobs: 0,
    open_incidents: 0,
    teams_on_field: 0,
    critical_stock: 0,
    vehicles_with_alerts: 0,
  });
  const [feinesRecents, setFeinesRecents] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const carregarDades = () => {
    Promise.all([
      apiFetch<any>("/gestio/dashboard/hud").catch(() => null),
      apiFetch<any[]>("/gestio/feines?limit=10").catch(() => []),
    ])
      .then(([hudData, feinesData]) => {
        if (hudData) setHud(hudData);
        if (Array.isArray(feinesData)) setFeinesRecents(feinesData);
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    carregarDades();
  }, []);

  return (
    <div className="flex flex-col h-full bg-slate-50 dark:bg-slate-950 p-4 md:p-6 space-y-6 overflow-y-auto">
      {/* 1. HUD DE POLSO OPERATIVO EN TIEMPO REAL (RF-07 & FR-018) */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
        {/* Cuadrillas Activas */}
        <Link href="/gestio/operaris" className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm flex items-center justify-between hover:border-emerald-500 transition-colors cursor-pointer block">
          <div>
            <p className="text-[10px] font-mono font-bold text-slate-500 uppercase tracking-wider mb-1">Cuadrilles Actives</p>
            <div className="flex items-baseline gap-2">
              <h3 className="text-2xl font-black text-slate-800 dark:text-slate-100">{hud.teams_on_field}</h3>
              <span className="text-xs font-bold text-emerald-600 dark:text-emerald-400">En Faena</span>
            </div>
          </div>
          <div className="w-10 h-10 rounded-full bg-emerald-50 dark:bg-emerald-900/20 flex items-center justify-center">
            <Users className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
          </div>
        </Link>

        {/* Órdenes de Trabajo */}
        <Link href="/gestio/mapa" className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm flex items-center justify-between hover:border-blue-500 transition-colors cursor-pointer block">
          <div>
            <p className="text-[10px] font-mono font-bold text-slate-500 uppercase tracking-wider mb-1">Feines d'Avui</p>
            <div className="flex items-baseline gap-2">
              <h3 className="text-2xl font-black text-slate-800 dark:text-slate-100">{hud.active_jobs}</h3>
              <span className="text-xs font-bold text-slate-600 dark:text-slate-400">Actives</span>
            </div>
          </div>
          <div className="w-10 h-10 rounded-full bg-blue-50 dark:bg-blue-900/20 flex items-center justify-center">
            <CheckCircle2 className="w-5 h-5 text-blue-600 dark:text-blue-400" />
          </div>
        </Link>

        {/* Incidencias Urgentes */}
        <Link href="/gestio/notificacions" className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-red-200 dark:border-red-900/50 shadow-sm flex items-center justify-between relative overflow-hidden hover:border-red-500 transition-colors cursor-pointer block">
          <div className="absolute top-0 right-0 w-16 h-16 bg-red-500/10 rounded-bl-full -mr-4 -mt-4 animate-pulse"></div>
          <div>
            <p className="text-[10px] font-mono font-bold text-red-500 uppercase tracking-wider mb-1">Incidències Obra</p>
            <div className="flex items-baseline gap-2">
              <h3 className="text-2xl font-black text-red-600 dark:text-red-400">{hud.open_incidents}</h3>
              <span className="text-xs font-bold text-red-500">Obertes</span>
            </div>
          </div>
          <div className="w-10 h-10 rounded-full bg-red-100 dark:bg-red-900/30 flex items-center justify-center">
            <AlertTriangle className="w-5 h-5 text-red-600 dark:text-red-400" />
          </div>
        </Link>

        {/* Estado Flota */}
        <Link href="/gestio/flota" className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm flex items-center justify-between hover:border-slate-500 transition-colors cursor-pointer block">
          <div>
            <p className="text-[10px] font-mono font-bold text-slate-500 uppercase tracking-wider mb-1">Estat Flota</p>
            <div className="flex items-baseline gap-2">
              <h3 className="text-2xl font-black text-slate-800 dark:text-slate-100">{hud.vehicles_with_alerts}</h3>
              <span className="text-xs font-bold text-slate-600 dark:text-slate-400">Averies</span>
            </div>
          </div>
          <div className="w-10 h-10 rounded-full bg-slate-100 dark:bg-slate-800 flex items-center justify-center">
            <Truck className="w-5 h-5 text-slate-600 dark:text-slate-300" />
          </div>
        </Link>

        {/* Alertas Preventivas */}
        <Link href="/gestio/magatzem" className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-amber-200 dark:border-amber-900/50 shadow-sm flex items-center justify-between hover:border-amber-500 transition-colors cursor-pointer block">
          <div>
            <p className="text-[10px] font-mono font-bold text-amber-600 uppercase tracking-wider mb-1">Alertes Tècniques</p>
            <div className="flex items-baseline gap-2">
              <h3 className="text-2xl font-black text-amber-600 dark:text-amber-400">{hud.critical_stock}</h3>
              <span className="text-xs font-bold text-amber-600/80">Estoc Crític</span>
            </div>
          </div>
          <div className="w-10 h-10 rounded-full bg-amber-50 dark:bg-amber-900/20 flex items-center justify-center">
            <ShieldAlert className="w-5 h-5 text-amber-600 dark:text-amber-400" />
          </div>
        </Link>
      </div>

      {/* 2. ACCIONES RÁPIDAS (RF-05) */}
      <div className="flex flex-wrap gap-3">
        <button 
          onClick={() => setShowModalOT(true)}
          className="px-5 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-bold shadow-sm flex items-center gap-2 transition-all cursor-pointer"
        >
          <Wrench className="w-4 h-4" />
          Crear Ordre de Treball
        </button>
        <Link 
          href="/gestio/mapa" 
          className="px-5 py-2.5 rounded-xl bg-slate-800 dark:bg-slate-100 hover:bg-slate-700 dark:hover:bg-white text-white dark:text-slate-900 text-sm font-bold shadow-sm flex items-center gap-2 transition-all"
        >
          Obrir Mapa Interactiu Complet
        </Link>
      </div>

      {/* 3. MAPA EMBEGUT (RF-08) */}
      <div className="min-h-[480px] rounded-3xl overflow-hidden border border-slate-200 dark:border-slate-800 shadow-sm relative">
        <div className="absolute inset-0 bg-slate-100 dark:bg-slate-900 flex items-center justify-center">
          <iframe 
            src="/gestio/mapa?embed=true" 
            className="w-full h-full border-0"
            title="Mapa Central"
          />
        </div>
      </div>

      {/* 4. LLISTAT DE FEINES RECENTS (Zero Mock) */}
      <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm p-6 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <FileText className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
            <h2 className="text-base font-bold text-slate-800 dark:text-slate-100">
              Ordres de Treball Registrades al Sistema
            </h2>
          </div>
          <Link
            href="/gestio/mapa"
            className="text-xs font-bold text-emerald-600 dark:text-emerald-400 hover:underline flex items-center gap-1"
          >
            Veure totes al mapa →
          </Link>
        </div>

        {feinesRecents.length === 0 ? (
          <div className="p-8 text-center bg-slate-50 dark:bg-slate-800/40 rounded-xl border border-dashed border-slate-200 dark:border-slate-800">
            <p className="text-sm font-medium text-slate-500">
              No hi ha ordres de treball registrades per a aquesta empresa.
            </p>
            <button
              onClick={() => setShowModalOT(true)}
              className="mt-3 px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold transition-colors"
            >
              + Crear la primera Ordre de Treball
            </button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-slate-100 dark:border-slate-800 text-[11px] font-mono text-slate-400 uppercase tracking-wider">
                  <th className="py-2.5 px-3">Codi</th>
                  <th className="py-2.5 px-3">Títol / Descripció</th>
                  <th className="py-2.5 px-3">Client</th>
                  <th className="py-2.5 px-3">Cap de Colla</th>
                  <th className="py-2.5 px-3">Estat</th>
                  <th className="py-2.5 px-3">Data Planificada</th>
                  <th className="py-2.5 px-3">Ubicació</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
                {feinesRecents.map((feina) => (
                  <tr key={feina.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/40 transition-colors">
                    <td className="py-3 px-3 font-mono font-bold text-emerald-600 dark:text-emerald-400 text-xs">
                      {feina.codi}
                    </td>
                    <td className="py-3 px-3 font-medium text-slate-800 dark:text-slate-200">
                      <div>{feina.titol}</div>
                      {feina.descripcio && (
                        <div className="text-xs text-slate-400 line-clamp-1">{feina.descripcio}</div>
                      )}
                    </td>
                    <td className="py-3 px-3 text-xs font-medium text-slate-600 dark:text-slate-300">
                      {feina.client_nom || "-"}
                    </td>
                    <td className="py-3 px-3 text-xs">
                      {feina.cap_de_colla_nom ? (
                        <span className="font-semibold text-slate-700 dark:text-slate-300 flex items-center gap-1">
                          <Users className="w-3.5 h-3.5 text-blue-500" />
                          {feina.cap_de_colla_nom}
                        </span>
                      ) : (
                        <span className="text-amber-500 text-[11px] font-medium italic">Pendent d'assignar</span>
                      )}
                    </td>
                    <td className="py-3 px-3">
                      <span
                        className={`text-[11px] font-bold px-2 py-0.5 rounded-full border ${
                          feina.estat === "PENDENT"
                            ? "bg-amber-500/10 text-amber-600 border-amber-500/20"
                            : feina.estat === "ASSIGNADA" || feina.estat === "PROGRAMADA"
                            ? "bg-blue-500/10 text-blue-600 border-blue-500/20"
                            : "bg-emerald-500/10 text-emerald-600 border-emerald-500/20"
                        }`}
                      >
                        {feina.estat}
                      </span>
                    </td>
                    <td className="py-3 px-3 text-xs text-slate-500 flex items-center gap-1.5">
                      <Calendar className="w-3.5 h-3.5 text-slate-400" />
                      {feina.data_planificacio}
                    </td>
                    <td className="py-3 px-3 text-xs text-slate-500">
                      <div className="flex items-center gap-1 truncate max-w-xs">
                        <MapPin className="w-3.5 h-3.5 text-emerald-500 shrink-0" />
                        <span className="truncate">{feina.adreca}</span>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {showModalOT && (
        <CrearOTModal 
          onClose={() => setShowModalOT(false)} 
          onSuccess={() => carregarDades()}
        />
      )}
    </div>
  );
}
