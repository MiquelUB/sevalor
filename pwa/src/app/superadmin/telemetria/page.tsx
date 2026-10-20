"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import {
  Activity,
  Cpu,
  Database,
  Radio,
  ShieldAlert,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  Terminal,
  Zap,
  Users,
  ArrowRight,
  PlusCircle,
  AlertCircle,
  Wifi,
  WifiOff,
  Smartphone,
  LifeBuoy,
} from "lucide-react";
import { apiFetch } from "@/lib/api";

interface PwaSessioAnonima {
  pwa_ref: string;
  estat: string;
}

interface TenantLlicencia {
  id: string;
  subdomini: string;
  nom: string;
  vertical: "SEVALOR" | "ELECTRICPRO" | "HYDROPRO" | "BUILDINGPRO";
  operaris_actius: number;
  operaris_connectats: number;
  pwa_sessions_anonimes: PwaSessioAnonima[];
  quota_operaris: number;
  buffer_utilitzat_mb: number;
  quota_buffer_mb: number;
  disc_utilitzat_mb: number;
  disc_quota_mb: number;
  estat_pc_empresa: "ONLINE" | "OFFLINE" | "NO_CONFIGURAT";
  tiquets_oberts: number;
  features: {
    copilot_ia: boolean;
    flota_avancada: boolean;
    planols_tecnics: boolean;
    telegram_bot: boolean;
  };
  estat: string;
  estat_pagament: string;
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

  const [errorCarrega, setErrorCarrega] = useState<string | null>(null);
  const [uptimePercent, setUptimePercent] = useState<number | null>(null);
  const [uptimeSegons, setUptimeSegons] = useState<number | null>(null);
  const [p50Latency, setP50Latency] = useState<number | null>(null);
  const [p95Latency, setP95Latency] = useState<number | null>(null);
  const [p99Latency, setP99Latency] = useState<number | null>(null);

  const [microserveis, setMicroserveis] = useState<any[]>([]);

  const [poolOcupacioPercent, setPoolOcupacioPercent] = useState<number | null>(null);
  const [poolConnexionsActives, setPoolConnexionsActives] = useState<number | null>(null);
  const [poolConnexionsMax, setPoolConnexionsMax] = useState<number | null>(null);

  const [tasquesPerMinut, setTasquesPerMinut] = useState<number | null>(null);
  const [queueWaitMs, setQueueWaitMs] = useState<number | null>(null);
  const [tasquesPendents, setTasquesPendents] = useState<number | null>(null);

  const [whisperAvgInferenceSec, setWhisperAvgInferenceSec] = useState<number | null>(null);
  const [cpuUsagePercent, setCpuUsagePercent] = useState<number | null>(null);
  const [ramUsageMb, setRamUsageMb] = useState<number | null>(null);
  const [ramTotalMb, setRamTotalMb] = useState<number | null>(null);
  const [nodeDescripcio, setNodeDescripcio] = useState<string | null>(null);

  const [tenants, setTenants] = useState<TenantLlicencia[]>([]);
  const [filtreEmpresaId, setFiltreEmpresaId] = useState<string>("TOTES");

  const [tracesError, setTracesError] = useState<ErrorTrace[]>([]);
  const [mostrantTraces, setMostrantTraces] = useState<boolean>(false);

  const fetchTelemetria = async () => {
    setCarregant(true);
    setErrorCarrega(null);
    try {
      const data = await apiFetch<any>("/superadmin/telemetria/kpis");
      setUptimePercent(data.uptime_percent ?? null);
      setUptimeSegons(data.uptime_seconds ?? null);
      setP50Latency(data.latencies_ms?.p50 ?? null);
      setP95Latency(data.latencies_ms?.p95 ?? null);
      setP99Latency(data.latencies_ms?.p99 ?? null);
      setNodeDescripcio(data.node ?? null);
      if (data.concurrency) {
        setPoolOcupacioPercent(data.concurrency.db_pool_occupancy_percent ?? null);
        setPoolConnexionsActives(data.concurrency.db_pool_active ?? null);
        setPoolConnexionsMax(data.concurrency.db_pool_max ?? null);
      }
      if (data.celery_queues) {
        setTasquesPerMinut(data.celery_queues.tasks_per_minute ?? null);
        setQueueWaitMs(data.celery_queues.queue_wait_ms ?? null);
        const valors = Object.values(data.celery_queues.queues || {}).filter(
          (val: any) => typeof val === "number"
        ) as number[];
        setTasquesPendents(valors.length ? valors.reduce((acc, val) => acc + val, 0) : null);
      }
      if (data.cpu_ia_telemetry) {
        setWhisperAvgInferenceSec(data.cpu_ia_telemetry.whisper_avg_inference_sec ?? null);
        setCpuUsagePercent(data.cpu_ia_telemetry.cpu_utilization_percent ?? null);
        setRamUsageMb(data.cpu_ia_telemetry.ram_utilization_mb ?? null);
        setRamTotalMb(data.cpu_ia_telemetry.ram_total_mb ?? null);
      }
      if (data.microservices && typeof data.microservices === "object") {
        setMicroserveis(
          Object.entries(data.microservices).map(([id, s]: [string, any]) => ({
            id,
            nom: id,
            tipus: s.type ?? "",
            versio: s.version ?? "—",
            ping: s.ping ?? "—",
            estat: s.status ?? "UNKNOWN",
          }))
        );
      }
      if (Array.isArray(data.tenants)) {
        setTenants(data.tenants);
      }
    } catch (e) {
      setErrorCarrega(
        e instanceof Error ? e.message : "No s'han pogut carregar les mètriques del backend"
      );
    } finally {
      setDarreraActualitzacio(new Date().toLocaleTimeString());
      setCarregant(false);
    }
  };

  const fmt = (v: number | null, unitat = "", decimals = 0): string =>
    v === null || v === undefined ? "—" : `${decimals ? v.toFixed(decimals) : v}${unitat}`;

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

  const handleToggleFeature = async (tenantId: string, featureKey: keyof TenantLlicencia["features"]) => {
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

    try {
      await apiFetch(`/superadmin/telemetria/tenants/${tenantId}/features`, {
        method: "PATCH",
        body: JSON.stringify({ feature_key: featureKey, enabled: newVal }),
      });
    } catch {
      // Revertir si cal
    }
  };

  const tenantsMostrats =
    filtreEmpresaId === "TOTES" ? tenants : tenants.filter((t) => t.id === filtreEmpresaId);

  return (
    <div className="flex-1 p-6 space-y-6 overflow-y-auto bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 font-sans transition-colors">
      {/* CAPÇALERA DEL TAULER */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-slate-200 dark:border-slate-800">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-white flex items-center gap-2">
              <Activity className="w-5 h-5 text-emerald-500" />
              Telemetria per Empresa (Anònima RGPD) & Salut del Servidor
            </h1>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-800 font-bold">
              TELEMETRIA ANÒNIMA D'OPERARIS (PWA-REF)
            </span>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Control d'operaris connectats per empresa mitjançant referències anònimes de PWA (sense dades personals), estat de l'ordinador local de cada client i salut del node Hetzner.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <select
            value={filtreEmpresaId}
            onChange={(e) => setFiltreEmpresaId(e.target.value)}
            className="px-3 py-1.5 rounded-lg bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-xs font-mono font-bold"
          >
            <option value="TOTES">Totes les Empreses ({tenants.length})</option>
            {tenants.map((t) => (
              <option key={t.id} value={t.id}>
                {t.nom} ({t.subdomini})
              </option>
            ))}
          </select>

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

      {errorCarrega && (
        <div className="p-3.5 rounded-xl bg-rose-50 dark:bg-rose-950/70 border border-rose-300 dark:border-rose-800 flex items-center gap-3 text-rose-900 dark:text-rose-200 text-xs font-mono shadow-sm">
          <ShieldAlert className="w-5 h-5 text-rose-500 shrink-0" />
          <div>
            <strong>No s'han pogut carregar les mètriques reals.</strong> {errorCarrega}
          </div>
        </div>
      )}

      {/* BLOC PRINCIPAL: TELEMETRIA INDIVIDUAL PER EMPRESA DONADA D'ALTA (ANÒNIMA RGPD) */}
      <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border-2 border-emerald-500/30 dark:border-emerald-800/50 space-y-4 shadow-sm transition-colors">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h3 className="text-sm font-bold font-mono uppercase tracking-wider text-slate-800 dark:text-slate-200 flex items-center gap-2">
              <Smartphone className="w-4 h-4 text-emerald-500" />
              <span>1. Telemetria Individual per Empresa: Operaris Connectats (Anònims) & Estat PC Client</span>
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
              Per complir estrictament amb la Llei de Protecció de Dades (RGPD), només es mostra el recompte d'operaris i el número de referència tècnica de la PWA (<code>PWA-REF-xxxx</code>), mai noms ni NIFs d'operaris.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Link
              href="/superadmin/tenants/onboarding"
              className="px-2.5 py-1 rounded bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-mono font-bold flex items-center gap-1 transition-colors"
            >
              <PlusCircle className="w-3.5 h-3.5" />
              <span>Alta Empresa</span>
            </Link>
          </div>
        </div>

        {tenantsMostrats.length === 0 ? (
          <div className="p-10 rounded-xl border border-dashed border-slate-300 dark:border-slate-800 text-center space-y-3 bg-slate-50 dark:bg-slate-950/40">
            <div className="w-12 h-12 rounded-full bg-emerald-100 dark:bg-emerald-950/60 text-emerald-600 dark:text-emerald-400 flex items-center justify-center mx-auto border border-emerald-300 dark:border-emerald-800">
              <Users className="w-6 h-6" />
            </div>
            <div className="space-y-1">
              <h4 className="text-sm font-bold text-slate-800 dark:text-slate-200 font-mono">
                No hi ha cap empresa registrada
              </h4>
              <p className="text-xs text-slate-500 font-mono max-w-md mx-auto">
                Dóna d'alta la primera empresa per visualitzar la seva telemetria anònima de PWA i l'estat del seu ordinador local.
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
                    <th className="p-3.5">Empresa & Subdomini</th>
                    <th className="p-3.5">Operaris Connectats & Referències PWA Anònimes (RGPD)</th>
                    <th className="p-3.5 text-center">Ordinador Local Client (Arxiu / IA)</th>
                    <th className="p-3.5 text-center">Buffer Diari Hetzner</th>
                    <th className="p-3.5 text-center">Feature Flags</th>
                    <th className="p-3.5 text-right">Estat CRM</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200 dark:divide-slate-800 font-mono text-[11px]">
                  {tenantsMostrats.map((t) => (
                    <tr key={t.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/40 transition-colors">
                      <td className="p-3.5">
                        <Link href={`/superadmin/empreses/${t.id}`} className="font-bold text-slate-900 dark:text-white hover:text-emerald-600">
                          {t.nom}
                        </Link>
                        <p className="text-[10px] text-slate-500">{t.subdomini} • {t.vertical}</p>
                        {t.tiquets_oberts > 0 && (
                          <span className="inline-flex items-center gap-1 mt-1 px-1.5 py-0.5 rounded bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300 text-[9px] font-bold">
                            <LifeBuoy className="w-2.5 h-2.5" /> {t.tiquets_oberts} tiquet(s) obert(s)
                          </span>
                        )}
                      </td>

                      <td className="p-3.5">
                        <div className="font-bold text-slate-900 dark:text-white">
                          <span className="text-emerald-600 dark:text-emerald-400">
                            {t.operaris_connectats ?? t.operaris_actius} operaris s'han connectat
                          </span>{" "}
                          <span className="text-slate-400 font-normal">
                            (Llicència màx: {t.quota_operaris})
                          </span>
                        </div>
                        <div className="flex flex-wrap gap-1 mt-1.5">
                          {Array.isArray(t.pwa_sessions_anonimes) && t.pwa_sessions_anonimes.length > 0 ? (
                            t.pwa_sessions_anonimes.map((s) => (
                              <span
                                key={s.pwa_ref}
                                className="px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-300 dark:border-slate-700 text-[9px] font-bold"
                                title="Identificador tècnic anònim de PWA (Sense dades personals)"
                              >
                                {s.pwa_ref}
                              </span>
                            ))
                          ) : (
                            <span className="text-[10px] text-slate-400">Cap sessió PWA activa</span>
                          )}
                        </div>
                      </td>

                      <td className="p-3.5 text-center">
                        {t.estat_pc_empresa === "ONLINE" ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 border border-emerald-300 text-[10px] font-bold">
                            <Wifi className="w-3 h-3" /> PC ONLINE
                          </span>
                        ) : t.estat_pc_empresa === "OFFLINE" ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300 border border-rose-300 text-[10px] font-bold">
                            <WifiOff className="w-3 h-3" /> PC APAGAT (OFFLINE)
                          </span>
                        ) : (
                          <span className="text-[10px] text-slate-400">No configurat</span>
                        )}
                      </td>

                      <td className="p-3.5 text-center">
                        <span className="font-bold text-slate-800 dark:text-slate-200">
                          {t.buffer_utilitzat_mb ?? t.disc_utilitzat_mb} MB
                        </span>{" "}
                        <span className="text-slate-400">/ {t.quota_buffer_mb ?? 500} MB</span>
                        <span className="block text-[9px] text-slate-400">Només feines d'avui</span>
                      </td>

                      <td className="p-3.5">
                        <div className="flex items-center justify-center gap-1 text-[10px]">
                          <button
                            onClick={() => handleToggleFeature(t.id, "copilot_ia")}
                            className={`px-2 py-0.5 rounded border transition-colors ${
                              t.features?.copilot_ia
                                ? "border-emerald-600 bg-emerald-50 text-emerald-800 dark:border-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300 font-bold"
                                : "border-slate-300 bg-slate-100 text-slate-400 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-500 line-through"
                            }`}
                          >
                            Copilot
                          </button>
                          <button
                            onClick={() => handleToggleFeature(t.id, "flota_avancada")}
                            className={`px-2 py-0.5 rounded border transition-colors ${
                              t.features?.flota_avancada
                                ? "border-emerald-600 bg-emerald-50 text-emerald-800 dark:border-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300 font-bold"
                                : "border-slate-300 bg-slate-100 text-slate-400 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-500 line-through"
                            }`}
                          >
                            Flota
                          </button>
                          <button
                            onClick={() => handleToggleFeature(t.id, "planols_tecnics")}
                            className={`px-2 py-0.5 rounded border transition-colors ${
                              t.features?.planols_tecnics
                                ? "border-emerald-600 bg-emerald-50 text-emerald-800 dark:border-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300 font-bold"
                                : "border-slate-300 bg-slate-100 text-slate-400 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-500 line-through"
                            }`}
                          >
                            Plànols
                          </button>
                          <button
                            onClick={() => handleToggleFeature(t.id, "telegram_bot")}
                            className={`px-2 py-0.5 rounded border transition-colors ${
                              t.features?.telegram_bot
                                ? "border-emerald-600 bg-emerald-50 text-emerald-800 dark:border-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300 font-bold"
                                : "border-slate-300 bg-slate-100 text-slate-400 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-500 line-through"
                            }`}
                          >
                            Telegram
                          </button>
                        </div>
                      </td>

                      <td className="p-3.5 text-right">
                        <span
                          className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${
                            t.estat_pagament === "HIBERNANT"
                              ? "bg-amber-100 text-amber-800 border-amber-300 dark:bg-amber-950 dark:text-amber-300"
                              : t.estat === "AL_DIA"
                              ? "bg-emerald-100 text-emerald-800 border-emerald-300 dark:bg-emerald-950 dark:text-emerald-400"
                              : "bg-rose-100 text-rose-800 border-rose-300 dark:bg-rose-950 dark:text-rose-400"
                          }`}
                        >
                          {t.estat_pagament || t.estat}
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

      {/* BLOC 2: SALUT GLOBAL DEL CLÚSTER HETZNER (INFRAESTRUCTURA COMPARTIDA) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 space-y-1 shadow-sm">
          <div className="flex items-center justify-between text-slate-500 dark:text-slate-400 text-xs font-mono">
            <span>Uptime del Servidor Hetzner</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-500" />
          </div>
          <h3 className="text-2xl font-black font-mono text-emerald-600 dark:text-emerald-400">
            {uptimeSegons === null
              ? "—"
              : uptimeSegons >= 86400
              ? `${Math.floor(uptimeSegons / 86400)}d ${Math.floor((uptimeSegons % 86400) / 3600)}h`
              : `${Math.floor(uptimeSegons / 3600)}h ${Math.floor((uptimeSegons % 3600) / 60)}m`}
          </h3>
          <p className="text-[10px] text-slate-500 font-mono">
            Node: {nodeDescripcio ?? "Hetzner Cloud"}
          </p>
        </div>

        <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 space-y-1 shadow-sm">
          <div className="flex items-center justify-between text-slate-500 dark:text-slate-400 text-xs font-mono">
            <span>Latència API (p95)</span>
            <Zap className="w-4 h-4 text-emerald-500" />
          </div>
          <h3 className="text-2xl font-black font-mono text-slate-900 dark:text-white">
            {fmt(p95Latency, " ms")}
          </h3>
          <p className="text-[10px] text-slate-500 font-mono">
            p50: {fmt(p50Latency, "ms")} • p99: {fmt(p99Latency, "ms")}
          </p>
        </div>

        <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 space-y-1 shadow-sm">
          <div className="flex items-center justify-between text-slate-500 dark:text-slate-400 text-xs font-mono">
            <span>Pool PostgreSQL asyncpg</span>
            <Database className="w-4 h-4 text-blue-500" />
          </div>
          <h3 className="text-2xl font-black font-mono text-blue-600 dark:text-blue-400">
            {fmt(poolConnexionsActives)} / {fmt(poolConnexionsMax)}
          </h3>
          <p className="text-[10px] text-slate-500 font-mono">
            Ocupació: {fmt(poolOcupacioPercent, "%")}
          </p>
        </div>

        <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 space-y-1 shadow-sm">
          <div className="flex items-center justify-between text-slate-500 dark:text-slate-400 text-xs font-mono">
            <span>CPU & RAM Node Hetzner</span>
            <Cpu className="w-4 h-4 text-amber-500" />
          </div>
          <h3 className="text-2xl font-black font-mono text-slate-900 dark:text-white">
            {fmt(cpuUsagePercent, "%")} CPU
          </h3>
          <p className="text-[10px] text-slate-500 font-mono">
            RAM: {ramUsageMb === null ? "—" : (ramUsageMb / 1024).toFixed(1)} / {ramTotalMb === null ? "—" : (ramTotalMb / 1024).toFixed(1)} GB
          </p>
        </div>
      </div>

      {/* BLOC 3: HEALTH CHECK DELS 7 MICROSERVEIS */}
      <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 space-y-4 shadow-sm">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-bold font-mono uppercase tracking-wider text-slate-700 dark:text-slate-300 flex items-center gap-2">
            <Radio className="w-4 h-4 text-emerald-500 animate-pulse" />
            <span>2. Matriu d'Estat dels 7 Microserveis del Servidor</span>
          </h3>
          <span className="text-[11px] font-mono text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/60 px-2 py-0.5 rounded border border-emerald-200 dark:border-emerald-800 font-bold">
            {microserveis.filter((s: any) => s.estat === "HEALTHY").length}/{microserveis.length} HEALTHY
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
          {microserveis.map((servei) => (
            <div
              key={servei.id}
              className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700/80 space-y-2 flex flex-col justify-between"
            >
              <div>
                <div className="flex items-center justify-between">
                  <span
                    className={`w-2 h-2 rounded-full ${
                      servei.estat === "HEALTHY"
                        ? "bg-emerald-500"
                        : servei.estat === "DOWN"
                        ? "bg-rose-500"
                        : "bg-slate-400"
                    }`}
                  />
                  <span className="text-[10px] font-mono text-slate-400">{servei.ping}</span>
                </div>
                <h4 className="text-xs font-bold font-mono text-slate-900 dark:text-white mt-1">{servei.nom}</h4>
                <p className="text-[10px] text-slate-500 dark:text-slate-400 leading-tight mt-0.5">{servei.tipus}</p>
              </div>
              <div className="pt-2 border-t border-slate-200 dark:border-slate-700/60 flex items-center justify-between text-[10px] font-mono text-slate-500">
                <span>{servei.versio}</span>
                <span className="font-bold">
                  {servei.estat === "HEALTHY" ? "UP" : servei.estat === "DOWN" ? "DOWN" : "SENSE SONDA"}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* BLOC 4: AUDITORIA DE TRACES D'ERROR SRE */}
      <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 space-y-4 shadow-sm">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-bold font-mono uppercase tracking-wider text-slate-700 dark:text-slate-300 flex items-center gap-2">
              <Terminal className="w-4 h-4 text-blue-500" />
              <span>3. Auditoria SRE: Traces d'Error Segregades (superadmin_telemetry)</span>
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
              Esquema PostgreSQL aïllat sense payloads de negoci ni dades personals
            </p>
          </div>
          <button
            onClick={() => {
              setMostrantTraces(!mostrantTraces);
              if (!mostrantTraces) fetchTracesError();
            }}
            className="px-3 py-1 rounded-lg bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 text-xs font-mono font-bold border border-slate-300 dark:border-slate-700 transition-colors"
          >
            {mostrantTraces ? "Amagar Traces" : "Consultar Traces"}
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
