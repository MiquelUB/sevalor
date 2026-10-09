"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import {
  FileCode,
  FileText,
  Terminal,
  ShieldCheck,
  RefreshCw,
  AlertTriangle,
  Download,
  Building2,
  Clock,
  CheckCircle2,
  Layers,
  ArrowRight,
} from "lucide-react";
import { apiFetch, getApiBaseUrl } from "@/lib/api";

interface CertificatDestruccio {
  tenant_id: string;
  nom: string;
  nif: string;
  subdomini: string;
  domini_custom?: string;
  data_baixa: string;
  estat: string;
  certificat_disponible: boolean;
  certificat_path: string | null;
  custodia_anys: number;
  periode_gracia_dies: number;
  gdpr_compliance: string;
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

export default function SuperadminAuditoriaPage() {
  const [activeTab, setActiveTab] = useState<"certificats" | "traces">("certificats");
  const [certificats, setCertificats] = useState<CertificatDestruccio[]>([]);
  const [traces, setTraces] = useState<ErrorTrace[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const carregarDades = async () => {
    setLoading(true);
    setError(null);
    try {
      if (activeTab === "certificats") {
        const data = await apiFetch<CertificatDestruccio[]>("/superadmin/tenants/auditoria/certificats");
        setCertificats(data || []);
      } else {
        const data = await apiFetch<ErrorTrace[]>("/superadmin/telemetria/traces-error?limit=20");
        setTraces(data || []);
      }
    } catch (err: any) {
      setError(err.message || "Error al carregar registres d'auditoria");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    carregarDades();
  }, [activeTab]);

  return (
    <div className="max-w-7xl mx-auto p-4 md:p-8 space-y-6 w-full">
      {/* CAPÇALERA D'AUDITORIA & COMPLIANCE */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-2 border-b border-slate-200 dark:border-slate-800">
        <div>
          <h1 className="text-2xl font-black text-slate-900 dark:text-white flex items-center gap-2.5">
            <FileCode className="w-6 h-6 text-emerald-500" />
            <span>Auditoria, Baixes RGPD & Traces SRE</span>
          </h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Certificats oficials de destrucció de dades (5 anys de custòdia) i traces d'execució tècnica.
          </p>
        </div>

        <button
          onClick={carregarDades}
          disabled={loading}
          className="p-2 rounded-xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors shadow-sm"
          title="Refrescar dades"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin text-emerald-500" : ""}`} />
        </button>
      </div>

      {/* PESTANYES D'AUDITORIA */}
      <div className="flex items-center gap-2 border-b border-slate-200 dark:border-slate-800 pb-1">
        <button
          onClick={() => setActiveTab("certificats")}
          className={`px-4 py-2 rounded-xl text-xs font-mono font-bold flex items-center gap-2 transition-all ${
            activeTab === "certificats"
              ? "bg-emerald-600 text-white shadow-sm"
              : "text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800"
          }`}
        >
          <FileText className="w-4 h-4" />
          <span>Certificats de Destrucció ({certificats.length})</span>
        </button>

        <button
          onClick={() => setActiveTab("traces")}
          className={`px-4 py-2 rounded-xl text-xs font-mono font-bold flex items-center gap-2 transition-all ${
            activeTab === "traces"
              ? "bg-emerald-600 text-white shadow-sm"
              : "text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800"
          }`}
        >
          <Terminal className="w-4 h-4" />
          <span>Traces d'Error SRE (superadmin_telemetry)</span>
        </button>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-rose-50 dark:bg-rose-950/70 border border-rose-300 dark:border-rose-800 text-rose-800 dark:text-rose-200 text-xs font-mono flex items-center gap-2.5">
          <AlertTriangle className="w-4 h-4 text-rose-500 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* CONTINGUT SEGONS PESTANYA */}
      {activeTab === "certificats" && (
        <div className="space-y-4">
          <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 flex items-center gap-3 text-xs text-slate-600 dark:text-slate-400 font-sans">
            <ShieldCheck className="w-5 h-5 text-emerald-500 shrink-0" />
            <span>
              <strong>Garantia RGPD Art. 17:</strong> En executar una baixa de servei, s'emet un certificat PDF firmat criptogràficament que s'arxiva al servidor de Hetzner a Alemanya durant 5 anys per a possibles auditories de l'AEPD.
            </span>
          </div>

          {loading ? (
            <div className="p-12 text-center text-xs font-mono text-slate-400">
              Consultant certificats de destrucció al disc sobirà...
            </div>
          ) : certificats.length === 0 ? (
            <div className="p-12 text-center bg-white dark:bg-slate-900 rounded-2xl border border-dashed border-slate-300 dark:border-slate-800 shadow-sm space-y-2">
              <CheckCircle2 className="w-10 h-10 text-emerald-500 mx-auto" />
              <h3 className="text-sm font-bold text-slate-800 dark:text-slate-200 font-mono">
                Cap tenant en procés de baixa o destrucció
              </h3>
              <p className="text-xs text-slate-500 max-w-sm mx-auto font-sans">
                Tots els tenants registrats es troben en estat actiu o de prova. Els certificats s'arxiven aquí quan s'executa un offboarding.
              </p>
            </div>
          ) : (
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl overflow-hidden shadow-sm">
              <table className="w-full text-left text-xs font-medium">
                <thead className="bg-slate-50 dark:bg-slate-800/60 border-b border-slate-200 dark:border-slate-800 text-slate-500 font-mono text-[11px] uppercase tracking-wider">
                  <tr>
                    <th className="p-4 font-semibold">Empresa & NIF</th>
                    <th className="p-4 font-semibold">Data Baixa</th>
                    <th className="p-4 font-semibold">Estat Purga</th>
                    <th className="p-4 font-semibold">Custòdia Legal</th>
                    <th className="p-4 font-semibold text-right">Certificat Oficial</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {certificats.map((c) => (
                    <tr key={c.tenant_id} className="hover:bg-slate-50 dark:hover:bg-slate-800/40 transition-colors">
                      <td className="p-4">
                        <div className="font-bold text-slate-900 dark:text-white text-sm">{c.nom}</div>
                        <div className="text-[11px] font-mono text-slate-500">{c.nif} • {c.domini_custom || `${c.subdomini}.sevalor.app`}</div>
                      </td>
                      <td className="p-4 font-mono text-[11px] text-slate-600 dark:text-slate-400">
                        {new Date(c.data_baixa).toLocaleDateString("ca-ES", {
                          year: "numeric",
                          month: "short",
                          day: "numeric",
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </td>
                      <td className="p-4">
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-rose-50 text-rose-700 dark:bg-rose-950/60 dark:text-rose-300 border border-rose-200 dark:border-rose-800">
                          {c.estat}
                        </span>
                      </td>
                      <td className="p-4 font-mono text-[11px] text-slate-500">
                        {c.custodia_anys} anys (fins a {new Date(new Date(c.data_baixa).getTime() + 5 * 365 * 86400000).getFullYear()})
                      </td>
                      <td className="p-4 text-right">
                        {c.certificat_disponible ? (
                          <a
                            href={`${getApiBaseUrl()}/superadmin/tenants/auditoria/certificats/${c.tenant_id}/descarregar`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs shadow-sm transition-colors"
                          >
                            <Download className="w-3.5 h-3.5" />
                            <span>Descarregar PDF</span>
                          </a>
                        ) : (
                          <span className="text-[11px] font-mono text-slate-400 italic">
                            Certificat pendent de generació
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {activeTab === "traces" && (
        <div className="space-y-4">
          <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 flex items-center gap-3 text-xs text-slate-600 dark:text-slate-400 font-sans">
            <Terminal className="w-5 h-5 text-blue-500 shrink-0" />
            <span>
              <strong>Esquema Segregat:</strong> Les traces tècniques s'emmagatzemen a l'esquema independent <code className="text-blue-600 dark:text-blue-400">superadmin_telemetry</code> sense incloure paràmetres personals, dades de factures o transcripcions d'operaris.
            </span>
          </div>

          {loading ? (
            <div className="p-12 text-center text-xs font-mono text-slate-400">
              Llegint traces d'error des de superadmin_telemetry...
            </div>
          ) : traces.length === 0 ? (
            <div className="p-12 text-center bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-2">
              <CheckCircle2 className="w-10 h-10 text-emerald-500 mx-auto" />
              <h3 className="text-sm font-bold text-slate-800 dark:text-slate-200 font-mono">
                0 errors 500 registrats
              </h3>
              <p className="text-xs text-slate-500 max-w-sm mx-auto font-sans">
                La plataforma s'executa amb 100% d'estabilitat i sense fallades crítiques.
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {traces.map((t) => (
                <div
                  key={t.id}
                  className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 font-mono text-xs space-y-2 shadow-sm"
                >
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="font-bold text-rose-600 dark:text-rose-400">
                      {t.metode} {t.endpoint} • HTTP {t.status_code}
                    </span>
                    <span className="text-slate-400 text-[10px]">{t.creat_a}</span>
                  </div>
                  <pre className="text-[10px] text-slate-700 dark:text-slate-300 overflow-x-auto bg-slate-50 dark:bg-slate-950 p-3 rounded-xl border border-slate-200 dark:border-slate-800 font-mono">
                    {t.stack_trace}
                  </pre>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
