"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { Server, Activity, ArrowRight, ShieldAlert, Zap, Edit } from "lucide-react";
import { getAuthHeader } from "@/lib/auth";

interface Tenant {
  id: string;
  nom: string;
  rao_social: string;
  subdomini: string;
  estat_pagament: string;
  pla_subscripcio: string;
  feature_copilot_ia: boolean;
  feature_flota: boolean;
  feature_planols: boolean;
  feature_telegram: boolean;
}

export default function EmpresesPage() {
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchTenants();
  }, []);

  const fetchTenants = async () => {
    try {
      const res = await fetch("http://localhost:8000/api/v1/superadmin/tenants", {
        headers: getAuthHeader(),
      });
      if (!res.ok) throw new Error("Error fetching tenants");
      const data = await res.json();
      setTenants(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const getStatusColor = (estat: string) => {
    switch (estat) {
      case "TRIAL": return "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200";
      case "ACTIU": return "bg-emerald-100 text-emerald-800 dark:bg-emerald-900 dark:text-emerald-200";
      case "SUSPES": return "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200";
      case "ELIMINAT": return "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200";
      default: return "bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-200";
    }
  };

  if (loading) return <div className="p-8 text-center text-slate-500">Carregant empreses...</div>;
  if (error) return <div className="p-8 text-center text-red-500">{error}</div>;

  return (
    <div className="max-w-6xl mx-auto p-4 md:p-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Server className="w-6 h-6 text-emerald-600" />
            Gestió d'Empreses (Tenants)
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Mòdul de governança de llicències i facturació SaaS.
          </p>
        </div>
        <Link
          href="/superadmin/tenants/onboarding"
          className="bg-emerald-600 hover:bg-emerald-700 text-white px-4 py-2 rounded-lg text-sm font-bold flex items-center gap-2 transition-colors"
        >
          <Zap className="w-4 h-4" />
          Nou Onboarding
        </Link>
      </div>

      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden shadow-sm">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-50 dark:bg-slate-800/50 border-b border-slate-200 dark:border-slate-800 text-slate-500 dark:text-slate-400 font-mono text-xs uppercase tracking-wider">
            <tr>
              <th className="p-4 font-semibold">Tenant</th>
              <th className="p-4 font-semibold">Pla</th>
              <th className="p-4 font-semibold">Estat</th>
              <th className="p-4 font-semibold hidden md:table-cell">Mòduls</th>
              <th className="p-4 font-semibold text-right">Accions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
            {tenants.map(t => (
              <tr key={t.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors">
                <td className="p-4">
                  <div className="font-bold text-slate-900 dark:text-white">{t.nom || t.rao_social}</div>
                  <div className="text-xs text-slate-500 font-mono mt-0.5">{t.subdomini}.campopro.cat</div>
                </td>
                <td className="p-4">
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-bold uppercase tracking-wider bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200">
                    {t.pla_subscripcio}
                  </span>
                </td>
                <td className="p-4">
                  <span className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-bold uppercase tracking-wider ${getStatusColor(t.estat_pagament)}`}>
                    {t.estat_pagament}
                  </span>
                </td>
                <td className="p-4 hidden md:table-cell">
                  <div className="flex gap-1">
                    {t.feature_copilot_ia && <span className="w-2 h-2 rounded-full bg-blue-500" title="Copilot IA" />}
                    {t.feature_flota && <span className="w-2 h-2 rounded-full bg-orange-500" title="Flota" />}
                    {t.feature_planols && <span className="w-2 h-2 rounded-full bg-indigo-500" title="Plànols" />}
                    {t.feature_telegram && <span className="w-2 h-2 rounded-full bg-sky-500" title="Telegram" />}
                  </div>
                </td>
                <td className="p-4 text-right">
                  <Link
                    href={`/superadmin/empreses/${t.id}`}
                    className="inline-flex items-center gap-1.5 text-emerald-600 hover:text-emerald-700 dark:text-emerald-500 dark:hover:text-emerald-400 font-semibold transition-colors"
                  >
                    <Edit className="w-4 h-4" />
                    <span>Editar</span>
                  </Link>
                </td>
              </tr>
            ))}
            {tenants.length === 0 && (
              <tr>
                <td colSpan={5} className="p-8 text-center text-slate-500">
                  No hi ha cap empresa registrada.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
