"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { Plus, Shield, Building2, ExternalLink, RefreshCw, CheckCircle2 } from "lucide-react";
import { apiFetch } from "@/lib/api";

interface TenantItem {
  id: string;
  rao_social: string;
  subdomini: string;
  vertical: string;
  estat: string;
  pla: string;
  data_alta: string;
}

export default function SuperadminTenantsPage() {
  const [tenants, setTenants] = useState<TenantItem[]>([]);
  const [loading, setLoading] = useState(true);

  const carregarTenants = async () => {
    setLoading(true);
    try {
      const data = await apiFetch<TenantItem[]>("/superadmin/tenants");
      setTenants(data || []);
    } catch {
      setTenants([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    carregarTenants();
  }, []);

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-black text-slate-900 dark:text-white">Tenants de la Plataforma</h1>
          <p className="text-xs text-slate-500 mt-1">Gestió d'empreses, esquemes aïllats i llicències Hetzner.</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={carregarTenants}
            className="p-2 rounded-xl bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-200"
            title="Refrescar"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          </button>
          <Link
            href="/superadmin/tenants/onboarding"
            className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold rounded-xl flex items-center gap-2 shadow"
          >
            <Plus className="w-4 h-4" />
            <span>Nou Tenant (Onboarding)</span>
          </Link>
        </div>
      </div>

      {loading ? (
        <div className="p-12 text-center text-xs text-slate-500">Carregant tenants del sistema...</div>
      ) : tenants.length === 0 ? (
        <div className="p-12 text-center bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-3">
          <Building2 className="w-10 h-10 text-slate-400 mx-auto" />
          <h3 className="text-sm font-bold text-slate-800 dark:text-slate-200">No hi ha cap tenant donat d'alta</h3>
          <p className="text-xs text-slate-500 max-w-xs mx-auto">Comença provisionant el primer tenant des de l'assistent d'onboarding.</p>
          <Link
            href="/superadmin/tenants/onboarding"
            className="inline-flex px-4 py-2 bg-emerald-600 text-white text-xs font-bold rounded-xl shadow"
          >
            Començar Onboarding
          </Link>
        </div>
      ) : (
        <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
          <table className="w-full text-left text-xs font-medium">
            <thead className="bg-slate-50 dark:bg-slate-800/50 text-slate-500 font-bold border-b border-slate-200 dark:border-slate-800">
              <tr>
                <th className="p-3.5">Empresa / Raó Social</th>
                <th className="p-3.5">Subdomini</th>
                <th className="p-3.5">Vertical</th>
                <th className="p-3.5">Pla</th>
                <th className="p-3.5">Estat</th>
                <th className="p-3.5">Data Alta</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
              {tenants.map((t) => (
                <tr key={t.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/30 transition-colors">
                  <td className="p-3.5 font-bold text-slate-900 dark:text-white">{t.rao_social}</td>
                  <td className="p-3.5 font-mono text-emerald-600 dark:text-emerald-400">{t.subdomini}.campopro.cat</td>
                  <td className="p-3.5"><span className="px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-[10px] font-mono">{t.vertical}</span></td>
                  <td className="p-3.5"><span className="px-2 py-0.5 rounded bg-blue-50 dark:bg-blue-950/40 text-blue-600 dark:text-blue-400 text-[10px] font-bold">{t.pla}</span></td>
                  <td className="p-3.5"><span className="px-2 py-0.5 rounded bg-emerald-50 dark:bg-emerald-950 text-emerald-600 dark:text-emerald-400 text-[10px] font-bold">{t.estat}</span></td>
                  <td className="p-3.5 font-mono text-slate-500 text-[11px]">{new Date(t.data_alta).toLocaleDateString("ca-ES")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
