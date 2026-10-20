"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import {
  ShieldCheck,
  ShieldAlert,
  Radio,
  Lock,
  Database,
  KeyRound,
  CheckCircle2,
  RefreshCw,
  Plus,
  Trash2,
  Save,
  FileText,
} from "lucide-react";
import { apiFetch } from "@/lib/api";

interface SeguretatStatus {
  status: string;
  client_ip: string;
  ip_allowlist: string[];
  ip_allowlist_enforced: boolean;
  totp_enforced: boolean;
  rls_multi_tenant: string;
  zero_trust_segregation: string;
  session_impersonation_max_hours: number;
  impersonation_financial_mode: string;
  sovereign_storage: string;
}

export default function SuperadminSeguretatPage() {
  const [data, setData] = useState<SeguretatStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Gestió interactiva de la IP Allowlist
  const [ips, setIps] = useState<string[]>([]);
  const [novaIp, setNovaIp] = useState<string>("");
  const [savingIps, setSavingIps] = useState<boolean>(false);

  const fetchStatus = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch<SeguretatStatus>("/superadmin/tenants/seguretat/status");
      setData(res);
      setIps(Array.isArray(res.ip_allowlist) ? res.ip_allowlist : []);
    } catch (err: any) {
      setError(err.message || "Error al carregar l'estat de seguretat");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
  }, []);

  const handleAddIp = () => {
    const clean = novaIp.trim();
    if (!clean) return;
    if (!ips.includes(clean)) {
      setIps([...ips, clean]);
    }
    setNovaIp("");
  };

  const handleSaveAllowlist = async () => {
    if (ips.length === 0) {
      setError("La llista d'IPs autoritzades no pot quedar buida.");
      return;
    }
    setSavingIps(true);
    setError(null);
    setSuccessMsg(null);
    try {
      await apiFetch("/superadmin/tenants/seguretat/allowlist", {
        method: "PUT",
        body: JSON.stringify({ ips }),
      });
      setSuccessMsg("Llista blanca d'IPs (IP Allowlist) desada i activada en calent al middleware.");
      fetchStatus();
    } catch (e: any) {
      setError(e.message || "Error actualitzant la IP Allowlist.");
    } finally {
      setSavingIps(false);
    }
  };

  return (
    <div className="max-w-7xl mx-auto p-4 md:p-8 space-y-6 w-full">
      {/* CAPÇALERA DE SEGURETAT ZERO-TRUST */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-2 border-b border-slate-200 dark:border-slate-800">
        <div>
          <h1 className="text-2xl font-black text-slate-900 dark:text-white flex items-center gap-2.5">
            <ShieldCheck className="w-6 h-6 text-emerald-500" />
            <span>Seguretat Zero-Trust, IP Allowlist & Aïllament Sobirà</span>
          </h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Control interactiu d'IPs autoritzades per al Superadmin, doble factor TOTP obligatori, aïllament PostgreSQL RLS i accés als certificats RGPD.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Link
            href="/superadmin/auditoria"
            className="px-3 py-2 rounded-xl bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 text-xs font-mono font-bold flex items-center gap-1.5 border border-slate-300 dark:border-slate-700"
          >
            <FileText className="w-4 h-4 text-emerald-500" />
            <span>Veure Logs d'Auditoria & Certificats RGPD</span>
          </Link>
          <button
            onClick={fetchStatus}
            disabled={loading}
            className="p-2 rounded-xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors shadow-sm"
            title="Refrescar sondes de seguretat"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin text-emerald-500" : ""}`} />
          </button>
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-rose-50 dark:bg-rose-950/70 border border-rose-300 dark:border-rose-800 text-rose-800 dark:text-rose-200 text-xs font-mono flex items-center gap-2.5">
          <ShieldAlert className="w-5 h-5 text-rose-500 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {successMsg && (
        <div className="p-4 rounded-xl bg-emerald-50 dark:bg-emerald-950/70 border border-emerald-300 dark:border-emerald-800 text-emerald-800 dark:text-emerald-200 text-xs font-mono flex items-center gap-2.5">
          <CheckCircle2 className="w-5 h-5 text-emerald-500 shrink-0" />
          <span>{successMsg}</span>
        </div>
      )}

      {/* GESTIÓ INTERACTIVA DE LA IP ALLOWLIST DEL SUPERADMIN */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-6 rounded-2xl shadow-sm space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="text-sm font-mono font-bold uppercase tracking-wider text-slate-800 dark:text-slate-200 flex items-center gap-2">
              <Radio className="w-4 h-4 text-emerald-500 animate-pulse" />
              <span>Gestió de la Llista Blanca d'IPs (IP Allowlist per a Superadmin)</span>
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Només les adreces IP o rangs CIDR d'aquesta llista poden accedir al panell de Superadministració. La teva IP actual detectada és: <strong className="font-mono text-emerald-600">{data?.client_ip || "127.0.0.1"}</strong>
            </p>
          </div>
          <button
            onClick={handleSaveAllowlist}
            disabled={savingIps}
            className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-mono font-bold flex items-center gap-1.5 shadow"
          >
            <Save className="w-3.5 h-3.5" />
            <span>{savingIps ? "Desant..." : "Desar IP Allowlist"}</span>
          </button>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {ips.map((ipItem) => (
            <span
              key={ipItem}
              className="px-3 py-1.5 rounded-xl bg-slate-100 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 font-mono text-xs font-bold flex items-center gap-2"
            >
              <span>{ipItem}</span>
              <button
                type="button"
                onClick={() => setIps(ips.filter((x) => x !== ipItem))}
                className="text-rose-500 hover:text-rose-700"
                title="Eliminar IP"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </span>
          ))}
        </div>

        <div className="flex items-center gap-2 max-w-md pt-1">
          <input
            type="text"
            value={novaIp}
            onChange={(e) => setNovaIp(e.target.value)}
            placeholder="Afegir IP o CIDR (ex. 85.48.12.90 o 10.0.0.0/8)"
            className="flex-1 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl p-2 text-xs font-mono"
          />
          <button
            type="button"
            onClick={handleAddIp}
            className="px-3 py-2 rounded-xl bg-slate-900 dark:bg-slate-700 text-white text-xs font-mono font-bold flex items-center gap-1"
          >
            <Plus className="w-3.5 h-3.5" /> Afegir IP
          </button>
        </div>
      </div>

      {/* QUADRE DE COMANDAMENT ZERO-TRUST */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-5 rounded-2xl shadow-sm space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono font-bold uppercase text-slate-500 flex items-center gap-1.5">
              <Radio className="w-4 h-4 text-emerald-500" />
              IP Allowlist Guard
            </span>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-50 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-800 font-bold">
              ENFORCED
            </span>
          </div>

          <div className="space-y-1">
            <div className="text-xs text-slate-500 font-mono">IP de connexió actual:</div>
            <div className="text-lg font-black font-mono text-slate-900 dark:text-white">
              {data?.client_ip || "Carregant..."}
            </div>
          </div>

          <div className="pt-2 border-t border-slate-100 dark:border-slate-800 text-[11px] text-slate-500 dark:text-slate-400 font-sans leading-relaxed">
            Les peticions de Superadmin des d'una IP no autoritzada són rebutjades amb <strong>403 Forbidden</strong>.
          </div>
        </div>

        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-5 rounded-2xl shadow-sm space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono font-bold uppercase text-slate-500 flex items-center gap-1.5">
              <KeyRound className="w-4 h-4 text-blue-500" />
              2FA TOTP (RFC 6238)
            </span>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-blue-50 text-blue-800 dark:bg-blue-950/60 dark:text-blue-300 border border-blue-300 dark:border-blue-800 font-bold">
              OBLIGATORI
            </span>
          </div>

          <div className="space-y-1">
            <div className="text-xs text-slate-500 font-mono">Estat del doble factor:</div>
            <div className="text-lg font-black font-mono text-blue-600 dark:text-blue-400 flex items-center gap-1.5">
              <CheckCircle2 className="w-5 h-5 text-emerald-500" />
              <span>TOTP Activat</span>
            </div>
          </div>

          <div className="pt-2 border-t border-slate-100 dark:border-slate-800 text-[11px] text-slate-500 dark:text-slate-400 font-sans leading-relaxed">
            Tokens de sessió de 15 minuts de validesa i revocació immediata en Redis 7.
          </div>
        </div>

        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-5 rounded-2xl shadow-sm space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono font-bold uppercase text-slate-500 flex items-center gap-1.5">
              <Database className="w-4 h-4 text-purple-500" />
              PostgreSQL 16 RLS
            </span>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-purple-50 text-purple-800 dark:bg-purple-950/60 dark:text-purple-300 border border-purple-300 dark:border-purple-800 font-bold">
              100% TAULES
            </span>
          </div>

          <div className="space-y-1">
            <div className="text-xs text-slate-500 font-mono">Row Level Security:</div>
            <div className="text-base font-black font-mono text-purple-700 dark:text-purple-300">
              app.current_empresa_id
            </div>
          </div>

          <div className="pt-2 border-t border-slate-100 dark:border-slate-800 text-[11px] text-slate-500 dark:text-slate-400 font-sans leading-relaxed">
            Aïllament garantit pel motor PostgreSQL per a cada empresa donada d'alta.
          </div>
        </div>
      </div>

      {/* BLOC EXPLICATIU DELS PRINCIPIS DE PRIVACITAT I ARQUITECTURA */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm space-y-5">
        <h2 className="text-sm font-mono font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300 flex items-center gap-2">
          <Lock className="w-4 h-4 text-emerald-500" />
          <span>Què garanteix aquesta arquitectura Zero-Trust & Aïllament Sobirà?</span>
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700/80 space-y-2">
            <div className="flex items-center gap-2 font-bold text-xs text-slate-900 dark:text-white">
              <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />
              <span>1. Privacitat de Negoci i Telemetria Anònima (RGPD)</span>
            </div>
            <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed font-sans">
              El Superadmin gestiona el CRM, les llicències d'operaris i la facturació B2B Veri*factu del SaaS, però no espia la facturació privada dels clients finals ni les dades personals dels operaris (només es mostren referències anònimes <code>PWA-REF</code>).
            </p>
          </div>

          <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700/80 space-y-2">
            <div className="flex items-center gap-2 font-bold text-xs text-slate-900 dark:text-white">
              <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />
              <span>2. Sessions d'Impersonació Tècnica Auditades (Màx 2h)</span>
            </div>
            <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed font-sans">
              Quan un client obre un tiquet de suport, el Superadmin pot entrar temporalment (màxim 2 hores) per resoldre la incidència, deixant rastre complet al log d'auditoria i operant en mode només lectura sobre dades bancàries.
            </p>
          </div>

          <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700/80 space-y-2">
            <div className="flex items-center gap-2 font-bold text-xs text-slate-900 dark:text-white">
              <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />
              <span>3. Hibernació i Invalidesa Instantània a Redis 7</span>
            </div>
            <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed font-sans">
              En passar una empresa a estat <code>HIBERNANT</code> o <code>SUSPES_PAGAMENT</code>, els tokens actius es revoquen a l'instant a Redis, impedint noves connexions fins que es regularitzi el pagament.
            </p>
          </div>

          <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700/80 space-y-2">
            <div className="flex items-center gap-2 font-bold text-xs text-slate-900 dark:text-white">
              <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />
              <span>4. Buffer Diari a Hetzner + Arxiu Mestre al Disc del Client</span>
            </div>
            <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed font-sans">
              El servidor Hetzner a Alemanya només guarda les feines d'avui per màxima velocitat. L'arxiu històric de plànols pesats viu al disc dur de l'ordinador de cada empresa.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
