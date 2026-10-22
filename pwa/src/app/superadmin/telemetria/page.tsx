"use client";

import React, { useState, useEffect, useRef } from "react";
import Link from "next/link";
import {
  Activity,
  Cpu,
  Database,
  Radio,
  ShieldAlert,
  CheckCircle2,
  RefreshCw,
  Terminal,
  Zap,
  Users,
  ArrowRight,
  PlusCircle,
  Wifi,
  WifiOff,
  Smartphone,
  LifeBuoy,
  Clock,
  Building2,
  ExternalLink,
  PhoneCall,
  Calendar,
  Layers,
  Pause,
  Play,
} from "lucide-react";
import { apiFetch } from "@/lib/api";

interface PwaSessioAnonima {
  pwa_ref: string;
  estat: string;
}

interface TenantLlicencia {
  id: string;
  subdomini: string;
  domini_custom?: string;
  nom: string;
  vertical: "SEVALOR" | "ELECTRICPRO" | "HYDROPRO" | "BUILDINGPRO";
  operaris_actius: number;
  operaris_connectats: number;
  pwa_sessions_anonimes: (string | PwaSessioAnonima)[];
  quota_operaris: number;
  buffer_utilitzat_mb: number;
  quota_buffer_mb: number;
  disc_utilitzat_mb: number;
  disc_quota_mb: number;
  estat_pc_empresa: "ONLINE" | "OFFLINE" | "NO_CONFIGURAT";
  agent_actiu?: boolean;
  agent_url?: string;
  tiquets_oberts: number;
  features: {
    copilot_ia: boolean;
    flota_avancada: boolean;
    planols_tecnics: boolean;
    telegram_bot: boolean;
  };
  estat: string;
  estat_pagament: string;
  darrera_activitat?: string | null;
  total_jornades_registrades?: number;
  data_onboarding?: string | null;
  dies_trial_restants?: number | null;
  dies_trial_consumits?: number | null;
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

function formatTempsRelatiu(isoString?: string | null): string {
  if (!isoString) return "Sense activitat recent";
  try {
    const diffMs = Date.now() - new Date(isoString).getTime();
    if (diffMs < 0) return "Ara mateix";
    const diffSec = Math.floor(diffMs / 1000);
    if (diffSec < 60) return `Fa ${diffSec}s`;
    const diffMin = Math.floor(diffSec / 60);
    if (diffMin < 60) return `Fa ${diffMin}m`;
    const diffHours = Math.floor(diffMin / 60);
    if (diffHours < 24) return `Fa ${diffHours}h`;
    const diffDays = Math.floor(diffHours / 24);
    return `Fa ${diffDays} dies`;
  } catch {
    return "Sense activitat recent";
  }
}

export default function SuperadminTelemetriaPage() {
  const [mounted, setMounted] = useState<boolean>(false);
  const [carregant, setCarregant] = useState<boolean>(false);
  const [segonsDesDeRefresc, setSegonsDesDeRefresc] = useState<number>(0);
  const [autoRefrescActiu, setAutoRefrescActiu] = useState<boolean>(true);

  const [errorCarrega, setErrorCarrega] = useState<string | null>(null);
  const [deployOperatiu, setDeployOperatiu] = useState<boolean>(true);
  const [p50Latency, setP50Latency] = useState<number | null>(null);
  const [p95Latency, setP95Latency] = useState<number | null>(null);
  const [p99Latency, setP99Latency] = useState<number | null>(null);

  const [microserveis, setMicroserveis] = useState<any[]>([]);

  const [poolOcupacioPercent, setPoolOcupacioPercent] = useState<number | null>(null);
  const [poolConnexionsActives, setPoolConnexionsActives] = useState<number | null>(null);
  const [poolConnexionsMax, setPoolConnexionsMax] = useState<number | null>(null);

  const [cpuUsagePercent, setCpuUsagePercent] = useState<number | null>(null);
  const [ramUsageMb, setRamUsageMb] = useState<number | null>(null);
  const [ramTotalMb, setRamTotalMb] = useState<number | null>(null);
  const [nodeDescripcio, setNodeDescripcio] = useState<string | null>(null);

  const [tenants, setTenants] = useState<TenantLlicencia[]>([]);
  const [empresaSeleccionadaId, setEmpresaSeleccionadaId] = useState<string>("");

  const [tracesError, setTracesError] = useState<ErrorTrace[]>([]);
  const [mostrantTraces, setMostrantTraces] = useState<boolean>(false);

  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  const fetchTelemetria = async () => {
    setCarregant(true);
    setErrorCarrega(null);
    try {
      const data = await apiFetch<any>("/superadmin/telemetria/kpis");
      setDeployOperatiu(true);
      setP50Latency(data.latencies_ms?.p50 ?? null);
      setP95Latency(data.latencies_ms?.p95 ?? null);
      setP99Latency(data.latencies_ms?.p99 ?? null);
      setNodeDescripcio(data.node ?? null);
      if (data.concurrency) {
        setPoolOcupacioPercent(data.concurrency.db_pool_occupancy_percent ?? null);
        setPoolConnexionsActives(data.concurrency.db_pool_active ?? null);
        setPoolConnexionsMax(data.concurrency.db_pool_max ?? null);
      }
      if (data.cpu_ia_telemetry) {
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
        if (data.tenants.length > 0 && !empresaSeleccionadaId) {
          setEmpresaSeleccionadaId(data.tenants[0].id);
        }
      }
      setSegonsDesDeRefresc(0);
    } catch (e) {
      setDeployOperatiu(false);
      setErrorCarrega(
        e instanceof Error ? e.message : "El servei backend no respon a la comprovació de telemetria."
      );
    } finally {
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
    setMounted(true);
    fetchTelemetria();
  }, []);

  // Comptador de segons des de l'últim refresc i auto-refresc periòdic (cada 30s)
  useEffect(() => {
    const timer = setInterval(() => {
      setSegonsDesDeRefresc((prev) => prev + 1);
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    if (intervalRef.current) clearInterval(intervalRef.current);
    if (autoRefrescActiu) {
      intervalRef.current = setInterval(() => {
        fetchTelemetria();
      }, 30000); // 30 segons
    }
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [autoRefrescActiu]);

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
      // Revertir si falla
    }
  };

  // Empresa actualment seleccionada (NOMÉS UNA a la vegada)
  const tenantActiu = tenants.find((t) => t.id === empresaSeleccionadaId) || tenants[0];

  const esTrial = (tenantActiu?.estat_pagament || tenantActiu?.estat || "").toUpperCase() === "TRIAL";
  const diesRestants = tenantActiu?.dies_trial_restants ?? 14;
  const diesConsumits = tenantActiu?.dies_trial_consumits ?? 0;
  const agentOffline = tenantActiu?.estat_pc_empresa === "OFFLINE";
  const agentOnline = tenantActiu?.estat_pc_empresa === "ONLINE";

  if (!mounted) {
    return (
      <div className="flex-1 p-6 space-y-6 overflow-y-auto bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 font-sans">
        <div className="flex items-center justify-between pb-4 border-b border-slate-200 dark:border-slate-800">
          <div className="space-y-2">
            <div className="h-6 w-64 bg-slate-200 dark:bg-slate-800 rounded-lg animate-pulse" />
            <div className="h-4 w-96 bg-slate-200 dark:bg-slate-800 rounded-lg animate-pulse" />
          </div>
          <div className="h-9 w-28 bg-slate-200 dark:bg-slate-800 rounded-lg animate-pulse" />
        </div>
        <div className="h-64 bg-slate-100 dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-6 space-y-4 animate-pulse">
          <div className="h-8 w-1/3 bg-slate-200 dark:bg-slate-800 rounded-lg" />
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 pt-4">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-24 bg-slate-200 dark:bg-slate-800 rounded-xl" />
            ))}
          </div>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-28 bg-slate-100 dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-4 space-y-2 animate-pulse">
              <div className="h-4 w-20 bg-slate-200 dark:bg-slate-800 rounded" />
              <div className="h-8 w-32 bg-slate-200 dark:bg-slate-800 rounded" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 p-6 space-y-6 overflow-y-auto bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 font-sans transition-colors">
      {/* CAPÇALERA AMB CONTROL D'AUTO-REFRESC I ESTAT GLOBAL */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-slate-200 dark:border-slate-800">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-white flex items-center gap-2">
              <Activity className="w-5 h-5 text-emerald-500" />
              Telemetria per Empresa & Salut del Servidor
            </h1>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-800 font-bold">
              CUSTOMER SUCCESS & TRIAL 14D
            </span>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Supervisió individualitzada per empresa: estat de l'agent local (PC de nau), activitat d'operaris i salut de la infraestructura.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* Indicador de temps des de l'últim refresc */}
          <div
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-xs font-mono"
            suppressHydrationWarning
          >
            <Clock className="w-3.5 h-3.5 text-slate-400" />
            <span className="text-slate-500" suppressHydrationWarning>
              {segonsDesDeRefresc === 0 ? "Actualitzat ara" : `Fa ${segonsDesDeRefresc}s`}
            </span>
          </div>

          {/* Commutador d'Auto-refresc */}
          <button
            onClick={() => setAutoRefrescActiu(!autoRefrescActiu)}
            title={autoRefrescActiu ? "Pausar auto-refresc cada 30s" : "Activar auto-refresc cada 30s"}
            className={`px-3 py-1.5 rounded-lg text-xs font-mono font-bold flex items-center gap-1.5 border transition-colors ${
              autoRefrescActiu
                ? "bg-emerald-50 dark:bg-emerald-950/60 border-emerald-300 dark:border-emerald-800 text-emerald-700 dark:text-emerald-300"
                : "bg-slate-100 dark:bg-slate-800 border-slate-300 dark:border-slate-700 text-slate-600 dark:text-slate-400"
            }`}
          >
            {autoRefrescActiu ? <Pause className="w-3 h-3 text-emerald-600" /> : <Play className="w-3 h-3" />}
            <span>Auto (30s): {autoRefrescActiu ? "ON" : "OFF"}</span>
          </button>

          {/* Botó de Refresc Immediat */}
          <button
            onClick={fetchTelemetria}
            disabled={carregant}
            className="px-3.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-mono font-bold flex items-center gap-1.5 shadow-sm transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${carregant ? "animate-spin" : ""}`} />
            <span>Refrescar</span>
          </button>
        </div>
      </div>

      {errorCarrega && (
        <div className="p-4 rounded-xl bg-rose-50 dark:bg-rose-950/70 border border-rose-300 dark:border-rose-800 flex items-center gap-3 text-rose-900 dark:text-rose-200 text-xs font-mono shadow-sm">
          <ShieldAlert className="w-5 h-5 text-rose-500 shrink-0" />
          <div>
            <strong>Error de comunicació amb el servei de telemetria:</strong> {errorCarrega}
          </div>
        </div>
      )}

      {/* SECCIÓ 1: TELEMETRIA INDIVIDUAL PER EMPRESA (CUSTOMER SUCCESS & TRIAL HEALTH) */}
      <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border-2 border-emerald-500/30 dark:border-emerald-800/50 space-y-5 shadow-sm">
        {/* SELECTOR D'UNA SOLA EMPRESA */}
        <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-slate-200 dark:border-slate-800">
          <div className="flex items-center gap-2">
            <Building2 className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
            <span className="text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300 font-mono">
              Empresa en Consulta (1 sola a la vegada):
            </span>
            <select
              value={tenantActiu?.id || ""}
              onChange={(e) => setEmpresaSeleccionadaId(e.target.value)}
              className="px-3 py-1.5 rounded-lg bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-xs font-mono font-bold text-slate-900 dark:text-white"
            >
              {tenants.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.nom} — {t.subdomini} [{t.estat_pagament || t.estat}]
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-center gap-2">
            {tenantActiu && (
              <Link
                href={`/superadmin/empreses/${tenantActiu.id}`}
                className="px-3 py-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-800 dark:text-slate-200 text-xs font-mono font-bold flex items-center gap-1.5 transition-colors border border-slate-300 dark:border-slate-700"
              >
                <span>Fitxa Completa CRM</span>
                <ExternalLink className="w-3 h-3" />
              </Link>
            )}
            <Link
              href="/superadmin/tenants/onboarding"
              className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-mono font-bold flex items-center gap-1.5 transition-colors shadow-sm"
            >
              <PlusCircle className="w-3.5 h-3.5" />
              <span>Alta Empresa</span>
            </Link>
          </div>
        </div>

        {!tenantActiu ? (
          <div className="p-10 rounded-xl border border-dashed border-slate-300 dark:border-slate-800 text-center space-y-3 bg-slate-50 dark:bg-slate-950/40">
            <Users className="w-8 h-8 text-slate-400 mx-auto" />
            <h4 className="text-sm font-bold text-slate-800 dark:text-slate-200 font-mono">
              Cap empresa donada d'alta al sistema
            </h4>
            <p className="text-xs text-slate-500 font-mono">
              Crea el primer tenant per visualitzar la salut del seu node local i l'activitat d'operaris.
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {/* CAPÇALERA INDIVIDUALITZADA D'ÈXIT DE CLIENT I ESTAT DE SUBSCRIPCIÓ */}
            <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 flex flex-wrap items-center justify-between gap-4">
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-lg font-bold text-slate-900 dark:text-white font-mono">
                    {tenantActiu.nom}
                  </h2>
                  <span className="text-[10px] px-2 py-0.5 rounded font-mono font-bold bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-300">
                    {tenantActiu.vertical}
                  </span>
                </div>
                <p className="text-xs text-slate-500 font-mono mt-0.5">
                  FQDN: <strong className="text-emerald-600 dark:text-emerald-400">{tenantActiu.domini_custom || `${tenantActiu.subdomini}.sevalor.app`}</strong>
                </p>
              </div>

              {/* BLOC DE SUBSCRIPCIÓ & TRIAL */}
              <div className="flex items-center gap-3">
                {esTrial ? (
                  <div className="p-2.5 rounded-lg bg-amber-50 dark:bg-amber-950/60 border border-amber-300 dark:border-amber-800 text-amber-900 dark:text-amber-200 text-xs font-mono space-y-0.5">
                    <div className="flex items-center gap-1.5 font-bold">
                      <Calendar className="w-3.5 h-3.5 text-amber-600 dark:text-amber-400" />
                      <span>PERÍODE DE PROVA (14 DIES)</span>
                    </div>
                    <p className="text-[11px] text-amber-800 dark:text-amber-300 font-sans">
                      Dia {diesConsumits} de 14 • Queden <strong>{diesRestants} dies restants</strong>
                    </p>
                  </div>
                ) : (
                  <span className="px-3 py-1.5 rounded-lg border text-xs font-mono font-bold bg-emerald-50 text-emerald-800 border-emerald-300 dark:bg-emerald-950 dark:text-emerald-300">
                    ESTAT: {tenantActiu.estat_pagament || tenantActiu.estat}
                  </span>
                )}
              </div>
            </div>

            {/* AVÍS PROACTIU DE SUPORT SI EL TRIAL TÉ L'ORDINADOR APAGAT O INACTIVITAT */}
            {esTrial && (agentOffline || diesRestants <= 3) && (
              <div className="p-3.5 rounded-xl bg-amber-100/80 dark:bg-amber-950/80 border border-amber-400 text-amber-950 dark:text-amber-200 text-xs font-sans flex items-center justify-between gap-3 shadow-sm">
                <div className="flex items-center gap-2">
                  <PhoneCall className="w-4 h-4 text-amber-600 shrink-0" />
                  <div>
                    <strong>Atenció Proactiva de Suport (Customer Success):</strong>{" "}
                    {agentOffline
                      ? "L'empresa està en Trial però té l'ordinador local de la nau apagat. Trucar al client per revisar la posada en marxa del node d'arxiu i IA."
                      : `El Trial finalitza en ${diesRestants} dies. Contactar per tancar la quota definitiva d'operaris.`}
                  </div>
                </div>
                <Link
                  href={`/superadmin/empreses/${tenantActiu.id}`}
                  className="px-2.5 py-1 rounded bg-amber-700 hover:bg-amber-600 text-white text-[11px] font-mono font-bold shrink-0 transition-colors"
                >
                  Contactar al CRM
                </Link>
              </div>
            )}

            {/* 4 TARGETES CLAU DE SALUT I DIAGNÒSTIC INDIVIDUAL */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
              {/* 1. ESTAT DE L'AGENT LOCAL (PC OFICINA) */}
              <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 space-y-1.5">
                <div className="flex items-center justify-between text-xs font-mono text-slate-500">
                  <span>Agent Local (PC Nau)</span>
                  {agentOnline ? (
                    <Wifi className="w-4 h-4 text-emerald-500" />
                  ) : (
                    <WifiOff className="w-4 h-4 text-rose-500" />
                  )}
                </div>
                <div className="pt-0.5">
                  {agentOnline ? (
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 font-mono font-bold text-xs">
                      🟢 PC OFICINA ONLINE
                    </span>
                  ) : agentOffline ? (
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300 font-mono font-bold text-xs">
                      🔴 PC OFICINA APAGAT
                    </span>
                  ) : (
                    <span className="text-xs font-mono text-slate-400">Node no configurat</span>
                  )}
                </div>
                <p className="text-[10px] text-slate-500 leading-tight">
                  Allotja l'arxiu històric i executa la IA local sobirana.
                </p>
              </div>

              {/* 2. OPERARIS I CONNEXIÓ */}
              <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 space-y-1.5">
                <div className="flex items-center justify-between text-xs font-mono text-slate-500">
                  <span>Operaris Connectats</span>
                  <Smartphone className="w-4 h-4 text-blue-500" />
                </div>
                <h3 className="text-xl font-bold font-mono text-slate-900 dark:text-white">
                  {tenantActiu.operaris_connectats ?? tenantActiu.operaris_actius}{" "}
                  <span className="text-xs font-normal text-slate-400">
                    / {tenantActiu.quota_operaris} llicència
                  </span>
                </h3>
                <p className="text-[10px] text-slate-500 font-mono">
                  {tenantActiu.operaris_actius} operaris donats d'alta
                </p>
              </div>

              {/* 3. DARRERA ACTIVITAT & JORNADES */}
              <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 space-y-1.5">
                <div className="flex items-center justify-between text-xs font-mono text-slate-500">
                  <span>Darrera Connexió</span>
                  <Clock className="w-4 h-4 text-amber-500" />
                </div>
                <h3
                  className="text-base font-bold font-mono text-slate-900 dark:text-white"
                  suppressHydrationWarning
                >
                  {formatTempsRelatiu(tenantActiu.darrera_activitat)}
                </h3>
                <p className="text-[10px] text-slate-500 font-mono">
                  {tenantActiu.total_jornades_registrades ?? 0} jornades acumulades
                </p>
              </div>

              {/* 4. BUFFER DIARI HETZNER */}
              <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 space-y-1.5">
                <div className="flex items-center justify-between text-xs font-mono text-slate-500">
                  <span>Buffer Diari Hetzner</span>
                  <Database className="w-4 h-4 text-emerald-500" />
                </div>
                <h3 className="text-xl font-bold font-mono text-slate-900 dark:text-white">
                  {tenantActiu.buffer_utilitzat_mb ?? tenantActiu.disc_utilitzat_mb ?? 0} MB{" "}
                  <span className="text-xs font-normal text-slate-400">
                    / {tenantActiu.quota_buffer_mb ?? 500} MB
                  </span>
                </h3>
                <p className="text-[10px] text-slate-500 leading-tight">
                  Feines del dia i fotos pendents de bolcat a la nau.
                </p>
              </div>
            </div>

            {/* BARRA INFERIOR: SESSIONS ANÒNIMES PWA, FEATURE FLAGS I TIQUETS */}
            <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 flex flex-wrap items-center justify-between gap-4 text-xs font-mono">
              <div className="flex items-center gap-2">
                <span className="text-slate-500 font-bold">Sessions PWA Anònimes (RGPD):</span>
                <div className="flex flex-wrap gap-1">
                  {Array.isArray(tenantActiu.pwa_sessions_anonimes) &&
                  tenantActiu.pwa_sessions_anonimes.length > 0 ? (
                    tenantActiu.pwa_sessions_anonimes.map((item, idx) => {
                      const refStr = typeof item === "string" ? item : item.pwa_ref;
                      return (
                        <span
                          key={idx}
                          className="px-2 py-0.5 rounded bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 text-[10px] font-bold text-slate-700 dark:text-slate-300"
                        >
                          {refStr}
                        </span>
                      );
                    })
                  ) : (
                    <span className="text-slate-400 text-[11px]">Cap sessió activa en aquest moment</span>
                  )}
                </div>
              </div>

              {/* FEATURE FLAGS COMMUTABLES */}
              <div className="flex items-center gap-1.5">
                <span className="text-slate-400 text-[11px]">Mòduls:</span>
                <button
                  onClick={() => handleToggleFeature(tenantActiu.id, "copilot_ia")}
                  className={`px-2 py-0.5 rounded border text-[10px] font-bold transition-colors ${
                    tenantActiu.features?.copilot_ia
                      ? "bg-emerald-100 text-emerald-800 border-emerald-300 dark:bg-emerald-950 dark:text-emerald-300"
                      : "bg-slate-200 text-slate-400 line-through dark:bg-slate-800"
                  }`}
                >
                  Copilot
                </button>
                <button
                  onClick={() => handleToggleFeature(tenantActiu.id, "flota_avancada")}
                  className={`px-2 py-0.5 rounded border text-[10px] font-bold transition-colors ${
                    tenantActiu.features?.flota_avancada
                      ? "bg-emerald-100 text-emerald-800 border-emerald-300 dark:bg-emerald-950 dark:text-emerald-300"
                      : "bg-slate-200 text-slate-400 line-through dark:bg-slate-800"
                  }`}
                >
                  Flota
                </button>
                <button
                  onClick={() => handleToggleFeature(tenantActiu.id, "planols_tecnics")}
                  className={`px-2 py-0.5 rounded border text-[10px] font-bold transition-colors ${
                    tenantActiu.features?.planols_tecnics
                      ? "bg-emerald-100 text-emerald-800 border-emerald-300 dark:bg-emerald-950 dark:text-emerald-300"
                      : "bg-slate-200 text-slate-400 line-through dark:bg-slate-800"
                  }`}
                >
                  Plànols
                </button>
                <button
                  onClick={() => handleToggleFeature(tenantActiu.id, "telegram_bot")}
                  className={`px-2 py-0.5 rounded border text-[10px] font-bold transition-colors ${
                    tenantActiu.features?.telegram_bot
                      ? "bg-emerald-100 text-emerald-800 border-emerald-300 dark:bg-emerald-950 dark:text-emerald-300"
                      : "bg-slate-200 text-slate-400 line-through dark:bg-slate-800"
                  }`}
                >
                  Telegram
                </button>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* SECCIÓ 2: SALUT GLOBAL DEL CLÚSTER HETZNER (INFRAESTRUCTURA COMPARTIDA) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* TARGETA 1: ESTAT DEL DEPLOYMENT (BINARI CLAR: VERD / VERMELL) */}
        <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 space-y-1.5 shadow-sm">
          <div className="flex items-center justify-between text-slate-500 dark:text-slate-400 text-xs font-mono">
            <span>Estat del Deploy Hetzner</span>
            {deployOperatiu ? (
              <CheckCircle2 className="w-4 h-4 text-emerald-500" />
            ) : (
              <ShieldAlert className="w-4 h-4 text-rose-500" />
            )}
          </div>
          <div className="pt-0.5">
            {deployOperatiu ? (
              <div className="flex items-center gap-1.5 text-emerald-600 dark:text-emerald-400 font-bold font-mono text-base">
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
                <span>DEPLOY OPERATIU (UP)</span>
              </div>
            ) : (
              <div className="flex items-center gap-1.5 text-rose-600 dark:text-rose-400 font-bold font-mono text-base">
                <span className="w-2.5 h-2.5 rounded-full bg-rose-500" />
                <span>SERVEI CAIGUT (DOWN)</span>
              </div>
            )}
          </div>
          <p className="text-[10px] text-slate-500 font-mono">
            {nodeDescripcio ?? "CPX21 Nuremberg • 2 vCPU / 3.7 GB RAM"}
          </p>
        </div>

        {/* TARGETA 2: LATÈNCIA API (p95) */}
        <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 space-y-1.5 shadow-sm">
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

        {/* TARGETA 3: POOL POSTGRESQL ASYNCPG */}
        <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 space-y-1.5 shadow-sm">
          <div className="flex items-center justify-between text-slate-500 dark:text-slate-400 text-xs font-mono">
            <span>Pool PostgreSQL asyncpg</span>
            <Database className="w-4 h-4 text-blue-500" />
          </div>
          <h3 className="text-2xl font-black font-mono text-blue-600 dark:text-blue-400">
            {fmt(poolConnexionsActives)} / {fmt(poolConnexionsMax)}
          </h3>
          <p className="text-[10px] text-slate-500 font-mono">
            Ocupació global: {fmt(poolOcupacioPercent, "%")} (totes les empreses)
          </p>
        </div>

        {/* TARGETA 4: CPU & RAM HETZNER (AMB CLARIFICACIÓ D'ESCALABILITAT) */}
        <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 space-y-1.5 shadow-sm">
          <div className="flex items-center justify-between text-slate-500 dark:text-slate-400 text-xs font-mono">
            <span>Node Hetzner (Orquestador Relay)</span>
            <Cpu className="w-4 h-4 text-amber-500" />
          </div>
          <h3 className="text-xl font-black font-mono text-slate-900 dark:text-white">
            {fmt(cpuUsagePercent, "%")} CPU • RAM {ramUsageMb === null ? "—" : (ramUsageMb / 1024).toFixed(1)} / {ramTotalMb === null ? "—" : (ramTotalMb / 1024).toFixed(1)} GB
          </h3>
          <p className="text-[10px] text-slate-500 leading-tight">
            Trànsit HTTP i coordinació. La IA pesada i fotos resideixen al PC local.
          </p>
        </div>
      </div>

      {/* SECCIÓ 3: MATRIU DELS 7 MICROSERVEIS */}
      <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 space-y-4 shadow-sm">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-bold font-mono uppercase tracking-wider text-slate-700 dark:text-slate-300 flex items-center gap-2">
            <Radio className="w-4 h-4 text-emerald-500 animate-pulse" />
            <span>Matriu d'Estat dels 7 Microserveis del Servidor</span>
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

      {/* SECCIÓ 4: AUDITORIA SRE DE TRACES D'ERROR SEGREGADES */}
      <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 space-y-4 shadow-sm">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-bold font-mono uppercase tracking-wider text-slate-700 dark:text-slate-300 flex items-center gap-2">
              <Terminal className="w-4 h-4 text-blue-500" />
              <span>Auditoria SRE: Traces d'Error Segregades (superadmin_telemetry)</span>
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
              Esquema PostgreSQL aïllat per a depuració tècnica sense payloads de negoci ni dades personals
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
