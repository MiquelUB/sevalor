"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Server,
  Activity,
  ArrowRight,
  ShieldAlert,
  Zap,
  Edit,
  RefreshCw,
  Building2,
  HardDrive,
  Users,
  Eye,
  CheckCircle2,
  AlertTriangle,
  Sparkles,
  Layers,
  Truck,
  MessageSquare,
} from "lucide-react";
import { apiFetch, setAuthToken } from "@/lib/api";

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
  disc_quota_mb: number;
  disc_utilitzat_mb: number;
  feature_copilot_ia: boolean;
  feature_flota: boolean;
  feature_planols: boolean;
  feature_telegram: boolean;
  data_alta?: string;
  created_at?: string;
}

export default function EmpresesPage() {
  const router = useRouter();
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [impersonatingId, setImpersonatingId] = useState<string | null>(null);

  const fetchTenants = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiFetch<Tenant[]>("/superadmin/tenants");
      setTenants(data || []);
    } catch (err: any) {
      setError(err.message || "Error al carregar els tenants");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTenants();
  }, []);

  const getStatusColor = (estat: string) => {
    switch (estat) {
      case "TRIAL":
        return "bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300 border-blue-200 dark:border-blue-800";
      case "ACTIU":
        return "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800";
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
    if (!confirm("Vols iniciar una sessió d'impersonació tècnica (màx 2h) sobre aquest tenant? Tindràs accés de només lectura a dades financeres.")) {
      return;
    }
    setImpersonatingId(tenantId);
    try {
      const data = await apiFetch<any>(`/superadmin/tenants/${tenantId}/impersonate`, {
        method: "POST",
      });
      if (data && data.access_token) {
        setAuthToken(data.access_token);
        localStorage.setItem("sevalor_user", JSON.stringify({
          ...data,
          is_impersonation: true,
          empresa_id: tenantId,
          rol: "SUPERADMIN",
        }));
        localStorage.setItem("sevalor_tenant_id", tenantId);
        window.location.href = "/gestio";
      }
    } catch (e: any) {
      alert("Error en l'intent d'impersonació: " + (e.message || "Error desconegut"));
    } finally {
      setImpersonatingId(null);
    }
  };

  return (
    <div className="max-w-7xl mx-auto p-4 md:p-8 space-y-6 w-full">
      {/* CAPÇALERA DE PÀGINA */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-2 border-b border-slate-200 dark:border-slate-800">
        <div>
          <h1 className="text-2xl font-black text-slate-900 dark:text-white flex items-center gap-2.5">
            <Server className="w-6 h-6 text-emerald-600" />
            <span>Gestió de Tenants & Llicències</span>
          </h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Governança SaaS, aïllament multi-tenant RLS, cicle de vida, quotes i feature flags.
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

      {error && (
        <div className="p-4 rounded-xl bg-rose-50 dark:bg-rose-950/70 border border-rose-300 dark:border-rose-800 text-rose-800 dark:text-rose-200 text-xs font-mono flex items-center gap-3">
          <ShieldAlert className="w-5 h-5 text-rose-500 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {loading ? (
        <div className="p-16 text-center text-xs font-mono text-slate-400">
          Carregant empreses i metadades de llicència...
        </div>
      ) : tenants.length === 0 ? (
        <div className="p-12 text-center bg-white dark:bg-slate-900 rounded-2xl border border-dashed border-slate-300 dark:border-slate-800 shadow-sm space-y-4">
          <Building2 className="w-12 h-12 text-slate-400 mx-auto" />
          <div className="space-y-1">
            <h3 className="text-sm font-bold text-slate-800 dark:text-slate-200 font-mono">
              Cap empresa registrada a la base de dades
            </h3>
            <p className="text-xs text-slate-500 max-w-sm mx-auto">
              Estat inicial del sistema (Dia 0 Real). Crea el primer inquilí amb l'assistent d'onboarding.
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
                  <th className="p-4 font-semibold">Pla &amp; Quota</th>
                  <th className="p-4 font-semibold">Estat</th>
                  <th className="p-4 font-semibold text-center">Disc Hetzner</th>
                  <th className="p-4 font-semibold">Mòduls Actius</th>
                  <th className="p-4 font-semibold text-right">Governança</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {tenants.map((t) => {
                  const pla = t.pla_subscripcio || t.pla || "STARTER";
                  const estat = t.estat_pagament || t.estat || "TRIAL";
                  const nom = t.nom || t.rao_social || "Sense nom";
                  const dominiAccio = t.domini_custom || `${t.subdomini}.sevalor.app`;

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
                          <span className="text-emerald-700 dark:text-emerald-400 font-bold">{dominiAccio}</span>
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
                          <span>/ {t.quota_operaris || 5} operaris</span>
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

                      {/* Consum Disc */}
                      <td className="p-4 text-center font-mono text-[11px]">
                        <div className="text-slate-800 dark:text-slate-200 font-bold">
                          {t.disc_utilitzat_mb || 0} MB
                        </div>
                        <div className="text-[10px] text-slate-400">
                          de {t.disc_quota_mb || 10240} MB
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
                            title="Copilot IA"
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
                            title="Gestió de Flota"
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
                            title="Plànols Tècnics"
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
                            title="Bot Telegram"
                          >
                            <MessageSquare className="w-2.5 h-2.5" />
                            Bot
                          </span>
                        </div>
                      </td>

                      {/* Accions: Editar i Impersonar */}
                      <td className="p-4 text-right">
                        <div className="flex items-center justify-end gap-2">
                          <button
                            onClick={() => handleImpersonate(t.id)}
                            disabled={impersonatingId === t.id}
                            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 text-xs font-mono font-medium transition-colors"
                            title="Iniciar sessió d'impersonació (2h màxim, només lectura financera)"
                          >
                            <Eye className="w-3.5 h-3.5 text-blue-500" />
                            <span>{impersonatingId === t.id ? "Impersonant..." : "Impersonar"}</span>
                          </button>

                          <Link
                            href={`/superadmin/empreses/${t.id}`}
                            className="inline-flex items-center gap-1 px-3 py-1 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold transition-colors shadow-sm"
                          >
                            <Edit className="w-3.5 h-3.5" />
                            <span>Editar</span>
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
