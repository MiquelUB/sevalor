"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { Briefcase, AlertCircle, Plus, Calendar, FileText, ChevronRight } from "lucide-react";
import { getAuthHeader } from "@/lib/auth";

interface Contracte {
  id: string;
  client_id: string;
  numero_contracte: string;
  data_inici: string;
  data_fi: string | null;
  import_anual: number;
  estat: string;
}

interface Alerta {
  revisio_id: string;
  contracte_id: string;
  numero_contracte: string;
  data_prevista: string;
  dies_restants: number;
  estat: string;
}

export default function ContractesPage() {
  const [contractes, setContractes] = useState<Contracte[]>([]);
  const [alertes, setAlertes] = useState<Alerta[]>([]);
  const [mrr, setMrr] = useState<number>(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [resC, resA, resM] = await Promise.all([
        fetch("http://localhost:8000/api/v1/gestio/contractes", { headers: getAuthHeader() }),
        fetch("http://localhost:8000/api/v1/gestio/contractes/alertes/venciments", { headers: getAuthHeader() }),
        fetch("http://localhost:8000/api/v1/gestio/contractes/kpis/mrr", { headers: getAuthHeader() })
      ]);
      if (resC.ok) setContractes(await resC.json());
      if (resA.ok) setAlertes(await resA.json());
      if (resM.ok) {
        const d = await resM.json();
        setMrr(d.mrr);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const getEstatColor = (estat: string) => {
    switch (estat) {
      case "ACTIU": return "bg-emerald-100 text-emerald-800 dark:bg-emerald-900 dark:text-emerald-200";
      case "BAIXA": return "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200";
      default: return "bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-200";
    }
  };

  if (loading) return <div className="p-8 text-slate-500">Carregant contractes...</div>;

  return (
    <div className="p-4 md:p-8 max-w-7xl mx-auto space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white flex items-center gap-2">
            <Briefcase className="w-6 h-6 text-primary-600" />
            Contractes de Manteniment
          </h1>
          <p className="text-sm text-slate-500 mt-1">Gestió del cicle de vida i revisions preventives</p>
        </div>
        <Link
          href="/gestio/contractes/nou"
          className="bg-primary-600 hover:bg-primary-700 text-white px-4 py-2 rounded-lg font-bold flex items-center gap-2 transition-colors"
        >
          <Plus className="w-4 h-4" />
          Nou Contracte
        </Link>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* KPI MRR */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-6 rounded-xl shadow-sm flex flex-col justify-center">
          <p className="text-sm text-slate-500 font-bold uppercase tracking-wider mb-1">MRR (Mensual Recurrent)</p>
          <p className="text-3xl font-black text-slate-900 dark:text-white">{(mrr).toFixed(2)} €</p>
          <p className="text-xs text-slate-400 mt-2">Ingressos recurrents mensuals derivats de contractes actius.</p>
        </div>

        {/* Alertes (2 cols) */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-6 rounded-xl shadow-sm md:col-span-2">
          <h2 className="text-sm font-bold uppercase tracking-wider text-amber-600 dark:text-amber-500 mb-4 flex items-center gap-2">
            <AlertCircle className="w-4 h-4" />
            Venciments i Revisions a 15 dies
          </h2>
          {alertes.length === 0 ? (
            <p className="text-sm text-slate-500">No hi ha cap alerta de manteniment a curt termini.</p>
          ) : (
            <div className="space-y-3">
              {alertes.map(a => (
                <div key={a.revisio_id} className="flex items-center justify-between p-3 rounded-lg bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-900/50">
                  <div className="flex items-center gap-3">
                    <Calendar className="w-5 h-5 text-amber-600 dark:text-amber-500" />
                    <div>
                      <p className="text-sm font-bold text-slate-900 dark:text-white">
                        Revisió Contracte {a.numero_contracte}
                      </p>
                      <p className="text-xs text-amber-700 dark:text-amber-400">
                        {a.dies_restants < 0 ? `Vencuda fa ${Math.abs(a.dies_restants)} dies` : `Venç en ${a.dies_restants} dies`}
                      </p>
                    </div>
                  </div>
                  <Link href={`/gestio/contractes/${a.contracte_id}`} className="text-xs font-bold bg-white dark:bg-slate-800 px-3 py-1.5 rounded border border-amber-300 dark:border-amber-700 hover:bg-amber-100 transition-colors">
                    Veure
                  </Link>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden shadow-sm">
        <div className="p-4 border-b border-slate-200 dark:border-slate-800">
          <h2 className="text-sm font-bold uppercase tracking-wider text-slate-500 flex items-center gap-2">
            <FileText className="w-4 h-4" />
            Llistat de Contractes
          </h2>
        </div>
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-50 dark:bg-slate-800/50 border-b border-slate-200 dark:border-slate-800 text-slate-500 font-mono text-xs uppercase tracking-wider">
            <tr>
              <th className="p-4 font-semibold">Núm. Contracte</th>
              <th className="p-4 font-semibold">Data Inici</th>
              <th className="p-4 font-semibold">Data Fi</th>
              <th className="p-4 font-semibold">Import Anual</th>
              <th className="p-4 font-semibold">Estat</th>
              <th className="p-4 font-semibold text-right">Detall</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
            {contractes.map(c => (
              <tr key={c.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors group cursor-pointer" onClick={() => window.location.href = `/gestio/contractes/${c.id}`}>
                <td className="p-4 font-bold text-slate-900 dark:text-white">
                  {c.numero_contracte}
                </td>
                <td className="p-4 text-slate-600 dark:text-slate-400 font-mono">{c.data_inici}</td>
                <td className="p-4 text-slate-600 dark:text-slate-400 font-mono">{c.data_fi || '---'}</td>
                <td className="p-4 font-mono font-medium text-slate-900 dark:text-white">{c.import_anual.toFixed(2)} €</td>
                <td className="p-4">
                  <span className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-bold uppercase tracking-wider ${getEstatColor(c.estat)}`}>
                    {c.estat}
                  </span>
                </td>
                <td className="p-4 text-right">
                  <ChevronRight className="w-5 h-5 text-slate-400 group-hover:text-primary-600 inline-block" />
                </td>
              </tr>
            ))}
            {contractes.length === 0 && (
              <tr>
                <td colSpan={6} className="p-8 text-center text-slate-500">
                  Sense contractes de manteniment registrats.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
