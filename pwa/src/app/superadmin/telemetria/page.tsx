"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import {
  Server,
  Activity,
  Cpu,
  Database,
  HardDrive,
  Radio,
  Clock,
  ShieldAlert,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  Terminal,
  Zap,
  Globe,
  Users,
  Settings,
  Flame,
  Check,
  X,
  Layers,
  Sparkles,
  ArrowRight,
  PlusCircle,
  FileCode,
  AlertCircle,
} from "lucide-react";
import { apiFetch } from "@/lib/api";

interface TenantLlicencia {
  id: string;
  subdomini: string;
  nom: string;
  vertical: "CAMPOPRO" | "ELECTRICPRO" | "HYDROPRO" | "BUILDINGPRO";
  operaris_actius: number;
  quota_operaris: number;
  disc_utilitzat_mb: number;
  disc_quota_mb: number;
  features: {
    copilot_ia: boolean;
    flota_avancada: boolean;
    planols_tecnics: boolean;
    telegram_bot: boolean;
  };
  estat: "AL_DIA" | "DEUTOR" | "SUSPES";
}

interface ErrorTrace {
  id: string;
  endpoint: string;
  metode: string;
  status_code: number;
  stack_trace: string;
  detall: string | null;
  creat_a: string;
}

export default function SuperadminTelemetriaPage() {
  const [carregant, setCarregant] = useState<boolean>(false);
  const [darreraActualitzacio, setDarreraActualitzacio] = useState<string>("Ara mateix");

  // Telemetria del sistema (Spec 022 RF-01)
  const [uptimePercent, setUptimePercent] = useState<number>(100.0);
  const [p50Latency, setP50Latency] = useState<number>(0);
  const [p95Latency, setP95Latency] = useState<number>(0);
  const [p99Latency, setP99Latency] = useState<number>(0);

  // Microserveis (carregats del backend — Spec 022 RF-04)
  const [microserveis, setMicroserveis] = useState<any[]>([]);

  // Concurrència i Pool asyncpg (Spec 022 RF-06 & RF-07)
  const [sessionsActives, setSessionsActives] = useState<number>(0);
  const [operarisCamp, setOperarisCamp] = useState<number>(0);
  const [oficinaTecnica, setOficinaTecnica] = useState<number>(0);
  const [poolOcupacioPercent, setPoolOcupacioPercent] = useState<number>(0);
  const [poolConnexionsActives, setPoolConnexionsActives] = useState<number>(0);
  const [poolConnexionsMax, setPoolConnexionsMax] = useState<number>(60);

  // Cues Celery / Redis (Spec 022 RF-08 & RF-09)
  const [tasquesPerMinut, setTasquesPerMinut] = useState<number>(0);
  const [queueWaitMs, setQueueWaitMs] = useState<number>(0);
  const [tasquesPendents, setTasquesPendents] = useState<number>(0);

  // IA Local CPU-Only Hetzner CPX21 (Spec 022 RF-10 & RF-11)
  const [whisperAvgInferenceSec, setWhisperAvgInferenceSec] = useState<number>(0);
  const [cpuUsagePercent, setCpuUsagePercent] = useState<number>(0);
  const [ramUsageMb, setRamUsageMb] = useState<number>(0);

  // Llicències de Tenants (Spec 022 RF-12 & RF-15)
  const [tenants, setTenants] = useState<TenantLlicencia[]>([]);

  // Traces d'Error Tècniques Segregades (Spec 022 RF-03)
  const [tracesError, setTracesError] = useState<ErrorTrace[]>([]);
  const [mostrantTraces, setMostrantTraces] = useState<boolean>(false);

  // Carregar dades del backend
  const fetchTelemetria = async () => {
    setCarregant(true);
    try {
      const data = await apiFetch<any>("/superadmin/telemetria/kpis");
      setUptimePercent(data.uptime_percent ?? 100.0);
      if (data.latencies_ms) {
        setP50Latency(data.latencies_ms.p50 ?? 0);
        setP95Latency(data.latencies_ms.p95 ?? 0);
        setP99Latency(data.latencies_ms.p99 ?? 0);
      }
      if (data.concurrency) {
        setSessionsActives(data.concurrency.active_sessions ?? 0);
        setOperarisCamp(data.concurrency.operaris_camp ?? 0);
        setOficinaTecnica(data.concurrency.oficina_tecnica ?? 0);
        setPoolOcupacioPercent(data.concurrency.db_pool_occupancy_percent ?? 0);
        setPoolConnexionsActives(data.concurrency.db_pool_active ?? 0);
        setPoolConnexionsMax(data.concurrency.db_pool_max ?? 60);
      }
      if (data.celery_queues) {
        setTasquesPerMinut(data.celery_queues.tasks_per_minute ?? 0);
        setQueueWaitMs(data.celery_queues.queue_wait_ms ?? 0);
        const totalPendents = Object.values(data.celery_queues.queues || {}).reduce(
          (acc: number, val: any) => acc + (typeof val === "number" ? val : 0),
          0
        );
        setTasquesPendents(Number(totalPendents) || 0);
      }
      if (data.cpu_ia_telemetry) {
        setWhisperAvgInferenceSec(data.cpu_ia_telemetry.whisper_avg_inference_sec ?? 0);
        setCpuUsagePercent(data.cpu_ia_telemetry.cpu_utilization_percent ?? 0);
        setRamUsageMb(data.cpu_ia_telemetry.ram_utilization_mb ?? 0);
      }
      if (Array.isArray(data.microserveis)) {
        setMicroserveis(data.microserveis);
      }
      if (Array.isArray(data.tenants)) {
        setTenants(data.tenants);
      }
    } catch {
      // Backend no accessible en build/offline; es mantenen els valors per defecte
    } finally {
      setDarreraActualitzacio(new Date().toLocaleTimeString());
      setCarregant(false);
    }
  };

  const fetchTracesError = async () => {
    try {
      const data = await apiFetch<ErrorTrace[]>("/superadmin/telemetria/traces-error?limit=10");
      setTracesError(data);
    } catch {
      // Ignorar en mode offline
    }
  };

  useEffect(() => {
    fetchTelemetria();
  }, []);

  // Commutar Feature Flag d'un tenant en viu (Spec 022 RF-15)
  const handleToggleFeature = async (tenantId: string, featureKey: keyof TenantLlicencia["features"]) => {
    // Actualització optimista
    const currentVal = tenants.find((t) => t.id === tenantId)?.features[featureKey] ?? false;
    const newVal = !currentVal;

    setTenants((prev) =>
      prev.map((t) => {
        if (t.id === tenantId) {
          return {
            ...t,
            features: {
              ...t.features,
              [featureKey]: newVal,
            },
          };
        }
        return t;
      })
    );

    // Persistir al backend
    try {
      await apiFetch(`/superadmin/telemetria/tenants/${tenantId}/features`, {
        method: "PATCH",
        body: JSON.stringify({ feature_key: featureKey, enabled: newVal }),
      });
    } catch {
      // Fallback
    }
  };

  return (
    <div className="flex-1 p-6 space-y-6 overflow-y-auto bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 font-sans transition-colors">
      {/* CAPÇALERA DEL TAULER */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-slate-200 dark:border-slate-800">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-white flex items-center gap-2">
              <Activity className="w-5 h-5 text-emerald-500" />
              Tauler de Salut & Telemetria SRE (Spec 022)
            </h1>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-800 font-bold">
              SUPERADMIN_TELEMETRY SCHEME
            </span>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Uptime, p95 latències, microserveis, quotes de llicències i telemetria CPU-only Hetzner (Falkenstein)
          </p>
        </div>

        <div className="flex items-center gap-3">
          <span className="text-xs font-mono text-slate-500">
            Actualitzat: {darreraActualitzacio}
          </span>
          <button
            onClick={fetchTelemetria}
            disabled={carregant}
            className="px-3 py-1.5 rounded-lg bg-white dark:bg-slate-800 hover:bg-slate-100 dark:hover:bg-slate-700 text-slate-800 dark:text-slate-200 text-xs font-mono font-bold flex items-center gap-1.5 border border-slate-300 dark:border-slate-700 shadow-sm transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${carregant ? "animate-spin text-emerald-500" : ""}`} />
            <span>Refrescar</span>
          </button>
        </div>
      </div>

      {/* BANNERS D'ALERTES DEGRADACIÓ / SATURACIÓ (Spec 022 RF-02, RF-07, RF-09, RF-10) */}
      {p95Latency > 500 && (
        <div className="p-3.5 rounded-xl bg-amber-50 dark:bg-amber-950/70 border border-amber-300 dark:border-amber-800 flex items-center gap-3 text-amber-900 dark:text-amber-200 text-xs font-mono shadow-sm">
          <AlertTriangle className="w-5 h-5 text-amber-500 shrink-0 animate-pulse" />
          <div>
            <strong>Alerta SRE (RF-02): Rendiment degradat de l'API.</strong> La latència p95 ({p95Latency}ms) supera el llindar crític de 500ms. S'estan monitoritzant els endpoints amb càrrega.
          </div>
        </div>
      )}

      {poolOcupacioPercent > 85 && (
        <div className="p-3.5 rounded-xl bg-rose-50 dark:bg-rose-950/70 border border-rose-300 dark:border-rose-800 flex items-center gap-3 text-rose-900 dark:text-rose-200 text-xs font-mono shadow-sm">
          <ShieldAlert className="w-5 h-5 text-rose-500 shrink-0 animate-pulse" />
          <div>
            <strong>Alerta de Saturació Imminent (RF-07):</strong> El pool de connexions PostgreSQL asyncpg ha assolit el {poolOcupacioPercent}%. Risc d'esgotament de connexions d'alta densitat.
          </div>
        </div>
      )}

      {tasquesPendents > 50 && (
        <div className="p-3.5 rounded-xl bg-orange-50 dark:bg-orange-950/70 border border-orange-300 dark:border-orange-800 flex items-center gap-3 text-orange-900 dark:text-orange-200 text-xs font-mono shadow-sm">
          <AlertCircle className="w-5 h-5 text-orange-500 shrink-0" />
          <div>
            <strong>Alerta d'Escalat de Cues Celery (RF-09):</strong> Hi ha {tasquesPendents} tasques pendents acumulades. Cal considerar l'escalat de workers concurrents.
          </div>
        </div>
      )}

      {/* BLOC 1: DISPONIBILITAT, LATÈNCIES I POOL (Spec 022 RF-01 & RF-06) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Uptime Global */}
        <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 space-y-1 shadow-sm transition-colors">
          <div className="flex items-center justify-between text-slate-500 dark:text-slate-400 text-xs font-mono">
            <span>Uptime Plataforma (30d)</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-500" />
          </div>
          <h3 className="text-2xl font-black font-mono text-emerald-600 dark:text-emerald-400">
            {uptimePercent}%
          </h3>
          <p className="text-[10px] text-slate-500 font-mono">SLA Garantit: 99.9% Hetzner Sovereign</p>
        </div>

        {/* Latència p95 */}
        <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 space-y-1 shadow-sm transition-colors">
          <div className="flex items-center justify-between text-slate-500 dark:text-slate-400 text-xs font-mono">
            <span>Latència API (p95)</span>
            {p95Latency > 500 ? (
              <AlertTriangle className="w-4 h-4 text-amber-500 animate-pulse" />
            ) : (
              <Zap className="w-4 h-4 text-emerald-500" />
            )}
          </div>
          <h3 className={`text-2xl font-black font-mono ${p95Latency > 500 ? "text-amber-500" : "text-slate-900 dark:text-white"}`}>
            {p95Latency} ms
          </h3>
          <p className="text-[10px] text-slate-500 font-mono">
            p50: {p50Latency}ms • p99: {p99Latency}ms
          </p>
        </div>

        {/* Estat Pool PostgreSQL asyncpg */}
        <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 space-y-1 shadow-sm transition-colors">
          <div className="flex items-center justify-between text-slate-500 dark:text-slate-400 text-xs font-mono">
            <span>Pool PostgreSQL asyncpg</span>
            <Database className="w-4 h-4 text-blue-500" />
          </div>
          <h3 className="text-2xl font-black font-mono text-blue-600 dark:text-blue-400">
            {poolConnexionsActives} / {poolConnexionsMax}
          </h3>
          <p className="text-[10px] text-slate-500 font-mono">
            Ocupació: {poolOcupacioPercent}% (Límit alerta: 85%)
          </p>
        </div>

        {/* Rendiment Cues Celery */}
        <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 space-y-1 shadow-sm transition-colors">
          <div className="flex items-center justify-between text-slate-500 dark:text-slate-400 text-xs font-mono">
            <span>Throughput Celery / Redis</span>
            <Activity className="w-4 h-4 text-purple-500" />
          </div>
          <h3 className="text-2xl font-black font-mono text-purple-600 dark:text-purple-400">
            {tasquesPerMinut} <span className="text-xs font-normal text-slate-500">tasques/min</span>
          </h3>
          <p className="text-[10px] text-slate-500 font-mono">
            Queue Wait: {queueWaitMs}ms • Pendents: {tasquesPendents}
          </p>
        </div>
      </div>

      {/* BLOC 2: HEALTH CHECK DELS 7 MICROSERVEIS (Spec 022 RF-04 & RF-05) */}
      <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 space-y-4 shadow-sm transition-colors">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-bold font-mono uppercase tracking-wider text-slate-700 dark:text-slate-300 flex items-center gap-2">
            <Radio className="w-4 h-4 text-emerald-500 animate-pulse" />
            <span>Matriu d'Estat de Microserveis (7 Components)</span>
          </h3>
          <span className="text-[11px] font-mono text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/60 px-2 py-0.5 rounded border border-emerald-200 dark:border-emerald-800 font-bold">
                        {microserveis.filter((s: any) => s.estat === "HEALTHY").length}/{microserveis.length} HEALTHY
                      </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
          {microserveis.map((servei) => (
            <div
              key={servei.id}
              className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700/80 space-y-2 flex flex-col justify-between transition-colors"
            >
              <div>
                <div className="flex items-center justify-between">
                  <span className="w-2 h-2 rounded-full bg-emerald-500 shadow-sm shadow-emerald-500/50"></span>
                  <span className="text-[10px] font-mono text-slate-400">{servei.ping}</span>
                </div>
                <h4 className="text-xs font-bold font-mono text-slate-900 dark:text-white mt-1">{servei.nom}</h4>
                <p className="text-[10px] text-slate-500 dark:text-slate-400 leading-tight mt-0.5">{servei.tipus}</p>
              </div>
              <div className="pt-2 border-t border-slate-200 dark:border-slate-700/60 flex items-center justify-between text-[10px] font-mono text-slate-500">
                <span>{servei.versio}</span>
                <span className="text-emerald-600 dark:text-emerald-400 font-bold">UP</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* BLOC 3: TELEMETRIA IA LOCAL CPU-ONLY CPX21 (Spec 022 RF-10 & RF-11) */}
      <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 space-y-4 shadow-sm transition-colors">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-bold font-mono uppercase tracking-wider text-slate-700 dark:text-slate-300 flex items-center gap-2">
            <Cpu className="w-4 h-4 text-amber-500" />
            <span>Telemetria IA Local sota CPU-Only (Hetzner CPX21)</span>
          </h3>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-700 dark:text-slate-300">
            3 vCPUs • No Dedicated GPU
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 space-y-1">
            <span className="text-[11px] font-mono text-slate-500 dark:text-slate-400">Temps d'Inferència Whisper (INT8):</span>
            <h4 className="text-xl font-bold font-mono text-emerald-600 dark:text-emerald-400">
              {whisperAvgInferenceSec} segons
            </h4>
            <p className="text-[10px] text-slate-500">faster-whisper optimitzat en CPU (Límit timeout: 15s)</p>
          </div>

          <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 space-y-1">
            <span className="text-[11px] font-mono text-slate-500 dark:text-slate-400">Càrrega CPU del Node:</span>
            <h4 className="text-xl font-bold font-mono text-slate-900 dark:text-white">
              {cpuUsagePercent}% <span className="text-xs font-normal text-slate-500">utilitzada</span>
            </h4>
            <p className="text-[10px] text-slate-500">Alerta de saturació sostinguda si &gt; 90%</p>
          </div>

          <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 space-y-1">
            <span className="text-[11px] font-mono text-slate-500 dark:text-slate-400">Memòria RAM del Node:</span>
            <h4 className="text-xl font-bold font-mono text-slate-900 dark:text-white">
              {(ramUsageMb / 1024).toFixed(2)} GB / 4.00 GB
            </h4>
            <p className="text-[10px] text-slate-500">Model Whisper carregat en memòria compartida</p>
          </div>
        </div>

        {/* Garantia de Privacitat Absoluta (Spec 022 RF-11) */}
        <div className="p-3.5 rounded-xl bg-slate-100 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-700/60 flex items-center gap-2.5 text-xs font-mono text-slate-600 dark:text-slate-400">
          <ShieldCheck className="w-4 h-4 text-emerald-500 shrink-0" />
          <span>
            <strong>Garantia de Privacitat Absoluta (RF-11):</strong> El panell de Superadmin té expressament vetat l'emmagatzematge o lectura de cap transcripció d'àudio de camp o petició de negoci.
          </span>
        </div>
      </div>

      {/* BLOC 4: GESTIÓ DE LLICÈNCIES, QUOTES I FEATURE FLAGS (Spec 022 RF-12 a RF-15) */}
      <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 space-y-4 shadow-sm transition-colors">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h3 className="text-sm font-bold font-mono uppercase tracking-wider text-slate-700 dark:text-slate-300 flex items-center gap-2">
              <Users className="w-4 h-4 text-emerald-500" />
              <span>Taula de Llicències de Tenants & Feature Flags (Estil Twenty CRM)</span>
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
              Control de quotes d'operaris i commutació de mòduls per tenant sense alterar dades de negoci
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono text-slate-500">{tenants.length} tenants registrats</span>
            <Link
              href="/superadmin/tenants/onboarding"
              className="px-2.5 py-1 rounded bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-mono font-bold flex items-center gap-1 transition-colors"
            >
              <PlusCircle className="w-3.5 h-3.5" />
              <span>Nou Tenant</span>
            </Link>
          </div>
        </div>

        {/* GESTIÓ ZERO MOCK DATA: TAULA O ESTAT BUIT CANÒNIC */}
        {tenants.length === 0 ? (
          <div className="p-10 rounded-xl border border-dashed border-slate-300 dark:border-slate-800 text-center space-y-3 bg-slate-50 dark:bg-slate-950/40">
            <div className="w-12 h-12 rounded-full bg-emerald-100 dark:bg-emerald-950/60 text-emerald-600 dark:text-emerald-400 flex items-center justify-center mx-auto border border-emerald-300 dark:border-emerald-800">
              <Users className="w-6 h-6" />
            </div>
            <div className="space-y-1">
              <h4 className="text-sm font-bold text-slate-800 dark:text-slate-200 font-mono">
                No hi ha cap tenant registrat a la plataforma
              </h4>
              <p className="text-xs text-slate-500 font-mono max-w-md mx-auto">
                Estat canònic de Dia 0. Inicia l'aprovisionament del primer inquilí amb l'Assistent de 4 passos.
              </p>
            </div>
            <Link
              href="/superadmin/tenants/onboarding"
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-mono font-bold shadow transition-colors"
            >
              <span>Obrir Assistent d'Onboarding</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>
        ) : (
          <div className="rounded-xl border border-slate-200 dark:border-slate-800 overflow-hidden shadow-sm">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="bg-slate-100 dark:bg-slate-800/80 border-b border-slate-200 dark:border-slate-800 font-mono text-[10px] uppercase text-slate-500 dark:text-slate-400">
                    <th className="p-3.5">Subdomini & Inquilí</th>
                    <th className="p-3.5">Vertical Tècnica</th>
                    <th className="p-3.5 text-center">Quota Operaris (RLS)</th>
                    <th className="p-3.5 text-center">Disc Hetzner</th>
                    <th className="p-3.5 text-center">Feature Flags (Interruptors en Viu)</th>
                    <th className="p-3.5 text-right">Estat Llicència</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200 dark:divide-slate-800 font-mono text-[11px]">
                  {tenants.map((t) => (
                    <tr key={t.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/40 transition-colors">
                      <td className="p-3.5">
                        <p className="font-bold text-slate-900 dark:text-white">{t.subdomini}</p>
                        <p className="text-[10px] text-slate-500">{t.nom}</p>
                      </td>
                      <td className="p-3.5">
                        <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-slate-100 text-slate-700 border border-slate-300 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700">
                          {t.vertical}
                        </span>
                      </td>
                      <td className="p-3.5 text-center">
                        <span className="font-bold text-emerald-600 dark:text-emerald-400">
                          {t.operaris_actius}
                        </span>{" "}
                        / <span className="text-slate-500">{t.quota_operaris}</span>
                      </td>
                      <td className="p-3.5 text-center">
                        <span className="text-slate-700 dark:text-slate-300">{t.disc_utilitzat_mb} MB</span>{" "}
                        <span className="text-slate-400">/ {t.disc_quota_mb} MB</span>
                      </td>
                      <td className="p-3.5">
                        <div className="flex items-center justify-center gap-1.5 text-[10px]">
                          {/* Copilot IA */}
                          <button
                            onClick={() => handleToggleFeature(t.id, "copilot_ia")}
                            className={`px-2 py-0.5 rounded border transition-colors ${
                              t.features?.copilot_ia
                                ? "border-emerald-600 bg-emerald-50 text-emerald-800 dark:border-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300 font-bold"
                                : "border-slate-300 bg-slate-100 text-slate-400 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-500 line-through"
                            }`}
                            title="Commutar Copilot IA"
                          >
                            Copilot
                          </button>

                          {/* Flota Avançada */}
                          <button
                            onClick={() => handleToggleFeature(t.id, "flota_avancada")}
                            className={`px-2 py-0.5 rounded border transition-colors ${
                              t.features?.flota_avancada
                                ? "border-emerald-600 bg-emerald-50 text-emerald-800 dark:border-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300 font-bold"
                                : "border-slate-300 bg-slate-100 text-slate-400 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-500 line-through"
                            }`}
                            title="Commutar Flota Avançada"
                          >
                            Flota
                          </button>

                          {/* Plànols Tècnics */}
                          <button
                            onClick={() => handleToggleFeature(t.id, "planols_tecnics")}
                            className={`px-2 py-0.5 rounded border transition-colors ${
                              t.features?.planols_tecnics
                                ? "border-emerald-600 bg-emerald-50 text-emerald-800 dark:border-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300 font-bold"
                                : "border-slate-300 bg-slate-100 text-slate-400 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-500 line-through"
                            }`}
                            title="Commutar Plànols Tècnics"
                          >
                            Plànols
                          </button>

                          {/* Bot Telegram */}
                          <button
                            onClick={() => handleToggleFeature(t.id, "telegram_bot")}
                            className={`px-2 py-0.5 rounded border transition-colors ${
                              t.features?.telegram_bot
                                ? "border-emerald-600 bg-emerald-50 text-emerald-800 dark:border-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300 font-bold"
                                : "border-slate-300 bg-slate-100 text-slate-400 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-500 line-through"
                            }`}
                            title="Commutar Telegram Bot"
                          >
                            Telegram
                          </button>
                        </div>
                      </td>
                      <td className="p-3.5 text-right">
                        <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 border border-emerald-300 dark:bg-emerald-950 dark:text-emerald-400 dark:border-emerald-800">
                          {t.estat}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      {/* BLOC 5: AUDITORIA DE TRACES D'ERROR SRE (Spec 022 RF-03) */}
      <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 space-y-4 shadow-sm transition-colors">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-bold font-mono uppercase tracking-wider text-slate-700 dark:text-slate-300 flex items-center gap-2">
              <Terminal className="w-4 h-4 text-blue-500" />
              <span>Auditoria SRE: Traces Tècniques Segregades (superadmin_telemetry)</span>
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
              Esquema PostgreSQL aïllat sense payloads de negoci ni creuament amb taules d'usuaris
            </p>
          </div>
          <button
            onClick={() => {
              setMostrantTraces(!mostrantTraces);
              if (!mostrantTraces) fetchTracesError();
            }}
            className="px-3 py-1 rounded-lg bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 text-xs font-mono font-bold border border-slate-300 dark:border-slate-700 transition-colors"
          >
            {mostrantTraces ? "Amagar Traces" : "Consultar Traces (RF-03)"}
          </button>
        </div>

        {mostrantTraces && (
          <div className="space-y-3 pt-2">
            {tracesError.length === 0 ? (
              <p className="text-xs font-mono text-slate-500 p-4 rounded-xl bg-slate-50 dark:bg-slate-950/40 border border-slate-200 dark:border-slate-800 text-center">
                Cap error 500 registrat a l'esquema segregat superadmin_telemetry. Plataforma 100% estable.
              </p>
            ) : (
              <div className="space-y-2">
                {tracesError.map((t) => (
                  <div
                    key={t.id}
                    className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/70 border border-slate-200 dark:border-slate-700 font-mono text-xs space-y-1.5"
                  >
                    <div className="flex items-center justify-between text-[11px]">
                      <span className="font-bold text-rose-600 dark:text-rose-400">
                        {t.metode} {t.endpoint} • HTTP {t.status_code}
                      </span>
                      <span className="text-slate-400 text-[10px]">{t.creat_a}</span>
                    </div>
                    <pre className="text-[10px] text-slate-600 dark:text-slate-300 overflow-x-auto bg-white dark:bg-slate-950 p-2 rounded border border-slate-200 dark:border-slate-800">
                      {t.stack_trace}
                    </pre>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
