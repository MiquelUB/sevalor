"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import {
  Server,
  ArrowRight,
  ShieldAlert,
  Zap,
  Edit,
  RefreshCw,
  Building2,
  Users,
  Eye,
  Sparkles,
  Layers,
  Truck,
  MessageSquare,
  Download,
  PauseCircle,
  FileText,
  Cpu,
} from "lucide-react";
import { apiFetch, getApiBaseUrl } from "@/lib/api";
import { iniciarImpersonacio } from "@/lib/impersonation";

interface Tenant {
  id: string;
  nom: string;
  rao_social: string;
  nif?: string;
  subdomini: string;
  domini_custom?: string;
  vertical: string;
  estat: string;
  estat_pagament: string;
  pla: string;
  pla_subscripcio: string;
  quota_operaris: number;
  operaris_actius: number;
  quota_buffer_mb?: number;
  buffer_utilitzat_mb?: number;
  disc_quota_mb: number;
  disc_utilitzat_mb: number;
  tarifa_llicencia_base?: number;
  tarifa_per_operari?: number;
  tarifa_config_ia?: number;
  equips_ia_venuts?: Array<{ concepte: string; unitats: number; preu_unitari: number }>;
  node_ia_actiu?: boolean;
  node_ia_url?: string;
  feature_copilot_ia: boolean;
  feature_flota: boolean;
  feature_planols: boolean;
  feature_telegram: boolean;
  data_alta?: string;
  created_at?: string;
}

export default function EmpresesPage() {
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [factures, setFactures] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [impersonatingId, setImpersonatingId] = useState<string | null>(null);
  const [filtreEstat, setFiltreEstat] = useState<string>("TOTS");

  const fetchTenants = async () => {
    setLoading(true);
    setError(null);
    try {
      const [data, factData] = await Promise.all([
        apiFetch<Tenant[]>("/superadmin/tenants"),
        apiFetch<any[]>("/superadmin/crm/factures").catch(() => []),
      ]);
      setTenants(data || []);
      setFactures(factData || []);
    } catch (err: any) {
      setError(err.message || "Error al carregar els clients del CRM");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTenants();
  }, []);

  const getStatusColor = (estat: string) => {
    switch (estat) {
      case "PROSPECTE":
        return "bg-indigo-100 text-indigo-800 dark:bg-indigo-950 dark:text-indigo-300 border-indigo-200 dark:border-indigo-800";
      case "TRIAL":
        return "bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300 border-blue-200 dark:border-blue-800";
      case "ACTIU":
        return "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800";
      case "HIBERNANT":
        return "bg-orange-100 text-orange-800 dark:bg-orange-950 dark:text-orange-300 border-orange-300 dark:border-orange-800";
      case "SUSPES":
      case "SUSPES_PAGAMENT":
        return "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300 border-amber-200 dark:border-amber-800";
      case "ELIMINAT":
      case "BAIXA_OFFBOARDING":
        return "bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300 border-rose-200 dark:border-rose-800";
      default:
        return "bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-200 border-slate-200 dark:border-slate-700";
    }
  };

  const getPlanColor = (pla: string) => {
    switch (pla) {
      case "STARTER":
        return "bg-blue-50 text-blue-700 dark:bg-blue-950/60 dark:text-blue-300 border-blue-300 dark:border-blue-700";
      case "PRO":
        return "bg-purple-50 text-purple-700 dark:bg-purple-950/60 dark:text-purple-300 border-purple-300 dark:border-purple-700";
      case "ENTERPRISE":
        return "bg-amber-50 text-amber-700 dark:bg-amber-950/60 dark:text-amber-300 border-amber-300 dark:border-amber-700";
      default:
        return "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300 border-slate-200 dark:border-slate-700";
    }
  };

  const handleImpersonate = async (tenantId: string) => {
    if (
      !confirm(
        "Vols iniciar una sessió d'impersonació tècnica (màx 2h) sobre aquest tenant? Tindràs accés de només lectura a dades financeres."
      )
    ) {
      return;
    }
    setImpersonatingId(tenantId);
    try {
      const found = tenants.find((t) => t.id === tenantId);
      await iniciarImpersonacio(tenantId, found?.nom || found?.rao_social || "");
    } catch (e: any) {
      alert("Error en l'intent d'impersonació: " + (e.message || "Error desconegut"));
    } finally {
      setImpersonatingId(null);
    }
  };

  const tenantsFiltrats =
    filtreEstat === "TOTS"
      ? tenants
      : tenants.filter((t) => (t.estat_pagament || t.estat) === filtreEstat);

  const totalActius = tenants.filter((t) =>
    ["ACTIU", "TRIAL"].includes(t.estat_pagament || t.estat)
  ).length;
  const totalHibernants = tenants.filter(
    (t) => (t.estat_pagament || t.estat) === "HIBERNANT"
  ).length;
  const totalOperarisActius = tenants.reduce((acc, t) => acc + (t.operaris_actius || 0), 0);
  const totalOperarisQuota = tenants.reduce((acc, t) => acc + (t.quota_operaris || 5), 0);
  const prefacturesPendentsHitl = factures.filter(
    (f) => f.estat === "ESBORRANY_PREFACTURA"
  ).length;

  return (
    <div className="max-w-7xl mx-auto p-4 md:p-8 space-y-6 w-full">
      {/* CAPÇALERA DE PÀGINA */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-2 border-b border-slate-200 dark:border-slate-800">
        <div>
          <h1 className="text-2xl font-black text-slate-900 dark:text-white flex items-center gap-2.5">
            <Server className="w-6 h-6 text-emerald-600" />
            <span>CRM SaaS B2B • Gestió de Clients, Quotes &amp; Facturació Veri*factu</span>
          </h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Cicle de vida (incloent estat Hibernant), quota dinàmica d'operaris, venda d'equips IA, recuperació de dades (.zip) i facturació Veri*factu amb Human-in-the-Loop.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={fetchTenants}
            disabled={loading}
            className="p-2 rounded-xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors shadow-sm"
            title="Refrescar llista"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin text-emerald-500" : ""}`} />
          </button>

          <Link
            href="/superadmin/tenants/onboarding"
            className="bg-emerald-600 hover:bg-emerald-500 text-white px-4 py-2 rounded-xl text-xs font-bold flex items-center gap-2 shadow-sm transition-colors"
          >
            <Zap className="w-4 h-4" />
            <span>Nou Onboarding (Wizard)</span>
          </Link>
        </div>
      </div>

      {/* RESUM EXECUTIU CRM & FACTURACIÓ */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm">
          <span className="text-[11px] font-mono text-slate-500 uppercase">Empreses Actives / Trial</span>
          <div className="text-2xl font-black font-mono text-emerald-600 dark:text-emerald-400 mt-1">
            {totalActius} <span className="text-xs font-normal text-slate-400">/ {tenants.length} totals</span>
          </div>
          <p className="text-[10px] text-slate-400 mt-1 font-mono">Aïllament RLS PostgreSQL actiu</p>
        </div>

        <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm">
          <span className="text-[11px] font-mono text-slate-500 uppercase flex items-center gap-1">
            <PauseCircle className="w-3.5 h-3.5 text-orange-500" />
            <span>En Estat Hibernant</span>
          </span>
          <div className="text-2xl font-black font-mono text-orange-600 dark:text-orange-400 mt-1">
            {totalHibernants}
          </div>
          <p className="text-[10px] text-slate-400 mt-1 font-mono">
            Període de gràcia per impagament abans de baixa
          </p>
        </div>

        <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm">
          <span className="text-[11px] font-mono text-slate-500 uppercase">Operaris Llicenciats</span>
          <div className="text-2xl font-black font-mono text-blue-600 dark:text-blue-400 mt-1">
            {totalOperarisActius} <span className="text-xs font-normal text-slate-400">/ {totalOperarisQuota} quota</span>
          </div>
          <p className="text-[10px] text-slate-400 mt-1 font-mono">Quota variable per empresa (Quota Guard)</p>
        </div>

        <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm">
          <span className="text-[11px] font-mono text-slate-500 uppercase flex items-center gap-1">
            <FileText className="w-3.5 h-3.5 text-purple-500" />
            <span>Pre-factures Pendents HITL</span>
          </span>
          <div className="text-2xl font-black font-mono text-purple-600 dark:text-purple-400 mt-1">
            {prefacturesPendentsHitl}
          </div>
          <p className="text-[10px] text-slate-400 mt-1 font-mono">
            Requereixen verificació humana per Veri*factu
          </p>
        </div>
      </div>

      {/* FILTRES D'ESTAT DEL CRM */}
      <div className="flex items-center gap-2 flex-wrap">
        {[
          { id: "TOTS", label: "Tots els Clients" },
          { id: "ACTIU", label: "Actius" },
          { id: "TRIAL", label: "En Prova (Trial)" },
          { id: "HIBERNANT", label: "Hibernants (Impagament)" },
          { id: "BAIXA_OFFBOARDING", label: "En Baixa / Custòdia" },
          { id: "ELIMINAT", label: "Baixa Definitiva (Històric Fiscal)" },
        ].map((f) => (
          <button
            key={f.id}
            onClick={() => setFiltreEstat(f.id)}
            className={`px-3 py-1.5 rounded-xl text-xs font-mono font-bold border transition-all ${
              filtreEstat === f.id
                ? "bg-emerald-600 text-white border-emerald-600 shadow-sm"
                : "bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-400 border-slate-200 dark:border-slate-800 hover:bg-slate-100"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-rose-50 dark:bg-rose-950/70 border border-rose-300 dark:border-rose-800 text-rose-800 dark:text-rose-200 text-xs font-mono flex items-center gap-3">
          <ShieldAlert className="w-5 h-5 text-rose-500 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {loading ? (
        <div className="p-16 text-center text-xs font-mono text-slate-400">
          Carregant empreses, quotes d'operaris i metadades CRM...
        </div>
      ) : tenantsFiltrats.length === 0 ? (
        <div className="p-12 text-center bg-white dark:bg-slate-900 rounded-2xl border border-dashed border-slate-300 dark:border-slate-800 shadow-sm space-y-4">
          <Building2 className="w-12 h-12 text-slate-400 mx-auto" />
          <div className="space-y-1">
            <h3 className="text-sm font-bold text-slate-800 dark:text-slate-200 font-mono">
              Cap empresa registrada en aquest filtre
            </h3>
            <p className="text-xs text-slate-500 max-w-sm mx-auto">
              Estat real de la base de dades PostgreSQL. Pots crear un nou inquilí amb l'assistent d'onboarding.
            </p>
          </div>
          <Link
            href="/superadmin/tenants/onboarding"
            className="inline-flex items-center gap-2 px-4 py-2 bg-emerald-600 text-white text-xs font-bold rounded-xl shadow transition-colors"
          >
            <span>Iniciar Onboarding</span>
            <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      ) : (
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl overflow-hidden shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-medium">
              <thead className="bg-slate-50 dark:bg-slate-800/60 border-b border-slate-200 dark:border-slate-800 text-slate-500 dark:text-slate-400 font-mono text-[11px] uppercase tracking-wider">
                <tr>
                  <th className="p-4 font-semibold">Tenant &amp; Domini</th>
                  <th className="p-4 font-semibold">Pla &amp; Quota Operaris</th>
                  <th className="p-4 font-semibold">Estat CRM</th>
                  <th className="p-4 font-semibold text-center">Buffer Diari Hetzner &amp; PC Client</th>
                  <th className="p-4 font-semibold">Mòduls Actius</th>
                  <th className="p-4 font-semibold text-right">Governança &amp; Dades</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {tenantsFiltrats.map((t) => {
                  const pla = t.pla_subscripcio || t.pla || "STARTER";
                  const estat = t.estat_pagament || t.estat || "TRIAL";
                  const nom = t.nom || t.rao_social || "Sense nom";
                  const dominiAccio = t.domini_custom || `${t.subdomini}.sevalor.app`;
                  const bufferUsat = t.buffer_utilitzat_mb ?? t.disc_utilitzat_mb ?? 0;
                  const bufferQuota = t.quota_buffer_mb ?? 500;

                  return (
                    <tr
                      key={t.id}
                      className="hover:bg-slate-50 dark:hover:bg-slate-800/40 transition-colors"
                    >
                      {/* Nom, NIF & Domini */}
                      <td className="p-4">
                        <div className="font-bold text-slate-900 dark:text-white text-sm">
                          {nom}
                        </div>
                        <div className="flex items-center gap-2 mt-0.5 text-slate-500 font-mono text-[11px] flex-wrap">
                          <span className="text-emerald-700 dark:text-emerald-400 font-bold">
                            {dominiAccio}
                          </span>
                          {t.domini_custom && (
                            <span className="px-1.5 py-0.2 rounded bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300 text-[9px] font-bold">
                              Domini Propi
                            </span>
                          )}
                          {t.nif && <span className="text-slate-400">• {t.nif}</span>}
                          <span className="px-1.5 py-0.2 rounded bg-slate-100 dark:bg-slate-800 text-[10px]">
                            {t.vertical}
                          </span>
                        </div>
                      </td>

                      {/* Pla i Quota d'operaris */}
                      <td className="p-4">
                        <div className="flex items-center gap-2">
                          <span
                            className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider border ${getPlanColor(
                              pla
                            )}`}
                          >
                            {pla}
                          </span>
                        </div>
                        <div className="text-[11px] font-mono text-slate-500 dark:text-slate-400 mt-1 flex items-center gap-1">
                          <Users className="w-3 h-3 text-slate-400" />
                          <span className="font-bold text-slate-700 dark:text-slate-300">
                            {t.operaris_actius || 0}
                          </span>
                          <span>/ {t.quota_operaris || 5} operaris llicenciats</span>
                        </div>
                      </td>

                      {/* Estat de cicle de vida */}
                      <td className="p-4">
                        <span
                          className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider border ${getStatusColor(
                            estat
                          )}`}
                        >
                          {estat}
                        </span>
                      </td>

                      {/* Consum Buffer Diari + Estat PC Local */}
                      <td className="p-4 text-center font-mono text-[11px]">
                        <div className="text-slate-800 dark:text-slate-200 font-bold">
                          {bufferUsat} MB / {bufferQuota} MB
                        </div>
                        <div className="text-[10px] text-slate-400 flex items-center justify-center gap-1 mt-0.5">
                          <Cpu className="w-3 h-3" />
                          <span>
                            PC Client:{" "}
                            {t.node_ia_url
                              ? t.node_ia_actiu
                                ? "🟢 ONLINE"
                                : "🔴 APAGAT"
                              : "⚪ No config."}
                          </span>
                        </div>
                      </td>

                      {/* Feature Flags */}
                      <td className="p-4">
                        <div className="flex items-center gap-1.5 flex-wrap">
                          <span
                            className={`px-1.5 py-0.5 rounded text-[10px] font-mono flex items-center gap-1 border ${
                              t.feature_copilot_ia
                                ? "bg-emerald-50 text-emerald-700 border-emerald-300 dark:bg-emerald-950/60 dark:text-emerald-300 dark:border-emerald-700 font-bold"
                                : "bg-slate-100 text-slate-400 border-slate-200 dark:bg-slate-800 dark:text-slate-500 dark:border-slate-700 line-through"
                            }`}
                          >
                            <Sparkles className="w-2.5 h-2.5" />
                            IA
                          </span>

                          <span
                            className={`px-1.5 py-0.5 rounded text-[10px] font-mono flex items-center gap-1 border ${
                              t.feature_flota
                                ? "bg-emerald-50 text-emerald-700 border-emerald-300 dark:bg-emerald-950/60 dark:text-emerald-300 dark:border-emerald-700 font-bold"
                                : "bg-slate-100 text-slate-400 border-slate-200 dark:bg-slate-800 dark:text-slate-500 dark:border-slate-700 line-through"
                            }`}
                          >
                            <Truck className="w-2.5 h-2.5" />
                            Flota
                          </span>

                          <span
                            className={`px-1.5 py-0.5 rounded text-[10px] font-mono flex items-center gap-1 border ${
                              t.feature_planols
                                ? "bg-emerald-50 text-emerald-700 border-emerald-300 dark:bg-emerald-950/60 dark:text-emerald-300 dark:border-emerald-700 font-bold"
                                : "bg-slate-100 text-slate-400 border-slate-200 dark:bg-slate-800 dark:text-slate-500 dark:border-slate-700 line-through"
                            }`}
                          >
                            <Layers className="w-2.5 h-2.5" />
                            CAD
                          </span>

                          <span
                            className={`px-1.5 py-0.5 rounded text-[10px] font-mono flex items-center gap-1 border ${
                              t.feature_telegram
                                ? "bg-emerald-50 text-emerald-700 border-emerald-300 dark:bg-emerald-950/60 dark:text-emerald-300 dark:border-emerald-700 font-bold"
                                : "bg-slate-100 text-slate-400 border-slate-200 dark:bg-slate-800 dark:text-slate-500 dark:border-slate-700 line-through"
                            }`}
                          >
                            <MessageSquare className="w-2.5 h-2.5" />
                            Bot
                          </span>
                        </div>
                      </td>

                      {/* Accions: Recuperar Dades (.zip), Impersonar i Editar CRM */}
                      <td className="p-4 text-right">
                        <div className="flex items-center justify-end gap-2">
                          <a
                            href={`${getApiBaseUrl()}/superadmin/tenants/${t.id}/recuperar-dades`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-blue-50 dark:bg-blue-950/60 hover:bg-blue-100 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-800 text-xs font-mono font-bold transition-colors"
                            title="Recuperar i descarregar totes les dades de l'empresa (.zip)"
                          >
                            <Download className="w-3.5 h-3.5" />
                            <span>Dades (.zip)</span>
                          </a>

                          <button
                            onClick={() => handleImpersonate(t.id)}
                            disabled={impersonatingId === t.id}
                            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 text-xs font-mono font-medium transition-colors"
                            title="Iniciar sessió d'impersonació (2h màxim, només lectura financera)"
                          >
                            <Eye className="w-3.5 h-3.5 text-blue-500" />
                            <span>
                              {impersonatingId === t.id ? "Impersonant..." : "Impersonar"}
                            </span>
                          </button>

                          <Link
                            href={`/superadmin/empreses/${t.id}`}
                            className="inline-flex items-center gap-1 px-3 py-1 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold transition-colors shadow-sm"
                          >
                            <Edit className="w-3.5 h-3.5" />
                            <span>CRM &amp; Facturar</span>
                          </Link>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
