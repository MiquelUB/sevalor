"use client";

import React, { useState, useEffect } from "react";
import { Users, Truck, AlertTriangle, CheckCircle2, Wrench, ShieldAlert } from "lucide-react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import { CrearOTModal } from "@/components/gestio/CrearOTModal";

export default function GestioDashboardPage() {
  const [showModalOT, setShowModalOT] = useState(false);
  return (
    <div className="flex flex-col h-full bg-slate-50 dark:bg-slate-950 p-4 md:p-6 space-y-6 overflow-y-auto">
      {/* 1. HUD DE PULSO OPERATIVO EN TIEMPO REAL (RF-07) */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
        {/* Cuadrillas Activas */}
        <Link href="/gestio/operaris" className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm flex items-center justify-between hover:border-emerald-500 transition-colors cursor-pointer block">
          <div>
            <p className="text-[10px] font-mono font-bold text-slate-500 uppercase tracking-wider mb-1">Cuadrilles Actives</p>
            <div className="flex items-baseline gap-2">
              <h3 className="text-2xl font-black text-slate-800 dark:text-slate-100">0</h3>
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
              <h3 className="text-2xl font-black text-slate-800 dark:text-slate-100">0</h3>
              <span className="text-xs font-bold text-slate-600 dark:text-slate-400">Total</span>
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
              <h3 className="text-2xl font-black text-red-600 dark:text-red-400">0</h3>
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
              <h3 className="text-2xl font-black text-slate-800 dark:text-slate-100">0</h3>
              <span className="text-xs font-bold text-slate-600 dark:text-slate-400">En Ruta</span>
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
              <h3 className="text-2xl font-black text-amber-600 dark:text-amber-400">0</h3>
              <span className="text-xs font-bold text-amber-600/80">Estoc / ITV</span>
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
          Obrir Mapa Interactiu Completo
        </Link>
      </div>

      {/* 3. MAPA EMBEGUT (RF-08) */}
      <div className="flex-1 min-h-[500px] rounded-3xl overflow-hidden border border-slate-200 dark:border-slate-800 shadow-sm relative">
        <div className="absolute inset-0 bg-slate-100 dark:bg-slate-900 flex items-center justify-center">
          {/* Iframe del mapa para reutilizar la vista sin duplicar código complejo */}
          <iframe 
            src="/gestio/mapa?embed=true" 
            className="w-full h-full border-0"
            title="Mapa Central"
          />
        </div>
      </div>

      {showModalOT && (
        <CrearOTModal 
          onClose={() => setShowModalOT(false)} 
          onSuccess={() => window.location.reload()}
        />
      )}
    </div>
  );
}
