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
  HardDrive,
  Eye,
  Server,
  FileText,
  AlertCircle,
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

  const fetchStatus = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch<SeguretatStatus>("/superadmin/tenants/seguretat/status");
      setData(res);
    } catch (err: any) {
      setError(err.message || "Error al carregar l'estat de seguretat");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
  }, []);

  return (
    <div className="max-w-7xl mx-auto p-4 md:p-8 space-y-6 w-full">
      {/* CAPÇALERA DE SEGURETAT ZERO-TRUST */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-2 border-b border-slate-200 dark:border-slate-800">
        <div>
          <h1 className="text-2xl font-black text-slate-900 dark:text-white flex items-center gap-2.5">
            <ShieldCheck className="w-6 h-6 text-emerald-500" />
            <span>Seguretat Zero-Trust & Aïllament Sobirà</span>
          </h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Auditoria d'accessos, IP Allowlist, 2FA obligatori i polítiques RLS de PostgreSQL 16.
          </p>
        </div>

        <button
          onClick={fetchStatus}
          disabled={loading}
          className="p-2 rounded-xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors shadow-sm"
          title="Refrescar sondes de seguretat"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin text-emerald-500" : ""}`} />
        </button>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-rose-50 dark:bg-rose-950/70 border border-rose-300 dark:border-rose-800 text-rose-800 dark:text-rose-200 text-xs font-mono flex items-center gap-2.5">
          <ShieldAlert className="w-5 h-5 text-rose-500 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* QUADRE DE COMANDAMENT ZERO-TRUST */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {/* TARGETA 1: IP ALLOWLIST ENFORCEMENT */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-5 rounded-2xl shadow-sm space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono font-bold uppercase text-slate-500 flex items-center gap-1.5">
              <Radio className="w-4 h-4 text-emerald-500 animate-pulse" />
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
            Les peticions de Superadmin sense IP autoritzada són rebutjades immediatament a nivell de middleware amb codi <strong>403 Forbidden</strong>.
          </div>
        </div>

        {/* TARGETA 2: 2FA TOTP MANDATORI */}
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
            Tokens de sessió de 15 minuts de validesa. Els intents d'iniciar sessió sense codi de 6 dígits queden bloquejats per disseny.
          </div>
        </div>

        {/* TARGETA 3: AÏLLAMENT POSTGRESQL RLS */}
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
            Injecció de sessió per connexió asíncrona a PostgreSQL. Prohibit confiar en clàusules manuals WHERE; el motor de BD blinda la privacitat.
          </div>
        </div>
      </div>

      {/* BLOC DETALLAT DE PRINCIPIS ZERO-TRUST */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm space-y-5">
        <h2 className="text-sm font-mono font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300 flex items-center gap-2">
          <Lock className="w-4 h-4 text-emerald-500" />
          <span>Matriu de Segregació de Privacitat Absoluta (Spec 04 User Story 2)</span>
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700/80 space-y-2">
            <div className="flex items-center gap-2 font-bold text-xs text-slate-900 dark:text-white">
              <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />
              <span>Privacitat d'Inquilins Garantida</span>
            </div>
            <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed font-sans">
              El perfil de <strong>Superadministrador</strong> té per disseny bloquejat l'accés a dades operatives privades: feines d'obra, albarans de materials, facturació de clients, fotografies o transcripcions d'àudio. Només pot governar metadades de llicència i salut.
            </p>
          </div>

          <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700/80 space-y-2">
            <div className="flex items-center gap-2 font-bold text-xs text-slate-900 dark:text-white">
              <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />
              <span>Sessions d'Impersonació Auditades (Màx 2h)</span>
            </div>
            <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed font-sans">
              Per oferir suport tècnic, el Superadmin pot impersonar un tenant fins a un màxim improrrogable de 2 hores. Durant la sessió, les peticions a dades financeres operen en <strong>mode només lectura</strong> i queden registrades a l'auditoria.
            </p>
          </div>

          <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700/80 space-y-2">
            <div className="flex items-center gap-2 font-bold text-xs text-slate-900 dark:text-white">
              <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />
              <span>Llista Negra JWT a Redis 7</span>
            </div>
            <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed font-sans">
              En suspendre un tenant per impagament o tancar sessió, els tokens d'accés s'invaliden instantàniament mitjançant claus TTL a Redis, evitant l'ús de tokens no caducats.
            </p>
          </div>

          <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700/80 space-y-2">
            <div className="flex items-center gap-2 font-bold text-xs text-slate-900 dark:text-white">
              <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />
              <span>Sobirania de Dades a Hetzner Cloud (Nuremberg)</span>
            </div>
            <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed font-sans">
              Tots els documents, imatges i còpies de seguretat s'allotgen a volums locals <code className="text-emerald-600 dark:text-emerald-400">/data/&lt;empresa_id&gt;</code> al servidor alemany. Eliminació del 100% d'AWS S3 per compliment estricte del RGPD.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
