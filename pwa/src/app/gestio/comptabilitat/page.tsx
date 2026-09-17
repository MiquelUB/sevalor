"use client";

import React, { useState, useEffect } from "react";
import {
  Receipt,
  QrCode,
  ShieldCheck,
  ShieldAlert,
  AlertTriangle,
  CheckCircle2,
  Lock,
  ArrowRight,
  FileText,
  Search,
  Plus,
  RefreshCw,
  X,
} from "lucide-react";
import { useGestio } from "@/lib/gestio-context";
import { apiFetch } from "@/lib/api";

interface Factura {
  id: string;
  numero_factura: number;
  serie: string;
  client_id: string;
  base_imposable: number;
  quota_iva: number;
  import_retencio: number;
  import_suplits: number;
  liquid_exigible: number;
  hash_sha256: string;
  hash_anterior?: string;
  pdf_path?: string;
  estat_cobrament: string;
  estat_enviament: string;
  created_at?: string;
}

export default function GestioComptabilitatPage() {
  const { rolActiu } = useGestio();
  const [tabActiva, setTabActiva] = useState<"VERIFACTU" | "CONCILIACIO" | "NORMA43">("VERIFACTU");
  const [factures, setFactures] = useState<Factura[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // VETO D'ENGINYER (Spec 001 RF-03 / Spec 007 RF-05)
  if (rolActiu === "ENGINYER") {
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-8 text-center bg-slate-900 text-white min-h-[calc(100vh-3.5rem)]">
        <div className="w-16 h-16 rounded-2xl bg-rose-500/20 text-rose-500 border border-rose-500/30 flex items-center justify-center mb-4 shadow-xl shadow-rose-500/10">
          <ShieldAlert className="w-8 h-8" />
        </div>
        <span className="text-xs font-mono font-bold uppercase tracking-widest text-rose-400 bg-rose-950 px-2 py-1 rounded border border-rose-800">
          HTTP 403 Forbidden
        </span>
        <h2 className="text-xl font-bold mt-3 text-white">
          Veto d'Enginyer a Dades Financeres
        </h2>
        <p className="text-xs text-slate-400 max-w-md mt-2">
          De conformitat amb la Constitució v4.0 de SEVALOR (Spec 001 RF-03 i Spec 007 RF-05), el perfil tècnic d'Enginyer té estrictament restringit l'accés als llibres comptables, marges de beneficis, factures i salaris de la companyia.
        </p>
        <p className="text-[11px] font-mono text-slate-500 mt-4">
          Canvia el rol a "Boss", "Secretaria" o "Comptabilitat" a la capçalera superior per accedir-hi amb privilegis administratius.
        </p>
      </div>
    );
  }

  const carregarFactures = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiFetch<Factura[]>("/gestio/comptabilitat/factures");
      setFactures(data || []);
    } catch (err: any) {
      setError(err.message || "Error al carregar les factures");
      setFactures([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    carregarFactures();
  }, []);

  const totalFacturat = factures.reduce((acc, f) => acc + (f.liquid_exigible || 0), 0);

  return (
    <div className="flex-1 flex flex-col h-[calc(100vh-3.5rem)] overflow-hidden bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 transition-colors">
      {/* Barra superior de Comptabilitat */}
      <div className="p-4 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between shadow-sm">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-base font-bold text-slate-800 dark:text-slate-100 flex items-center gap-2">
              <Receipt className="w-5 h-5 text-emerald-600" />
              Comptabilitat, Tresoreria & Veri*factu (Spec 007)
            </h1>
            <span className="text-[10px] font-mono uppercase bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300 px-1.5 py-0.5 rounded font-bold border border-emerald-300 dark:border-emerald-800">
              AEAT Llei 11/2021
            </span>
          </div>
          <p className="text-xs text-slate-500">
            Encadenament Hash SHA-256 • Outbox SOAP Asíncron • Triple Conciliació • Ingesta Norma 43
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={carregarFactures}
            disabled={loading}
            className="p-2 rounded-xl bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 text-slate-600 dark:text-slate-300 transition-colors"
            title="Refrescar dades"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      {/* Tabs del Mòdul Comptable */}
      <div className="bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 flex text-xs font-bold px-4">
        <button
          onClick={() => setTabActiva("VERIFACTU")}
          className={`py-3 px-4 border-b-2 transition-colors flex items-center gap-1.5 ${
            tabActiva === "VERIFACTU"
              ? "border-emerald-600 text-emerald-600 dark:text-emerald-400"
              : "border-transparent text-slate-500 hover:text-slate-700"
          }`}
        >
          <QrCode className="w-4 h-4" />
          <span>Factures Veri*factu (SIF)</span>
        </button>
        <button
          onClick={() => setTabActiva("CONCILIACIO")}
          className={`py-3 px-4 border-b-2 transition-colors flex items-center gap-1.5 ${
            tabActiva === "CONCILIACIO"
              ? "border-emerald-600 text-emerald-600 dark:text-emerald-400"
              : "border-transparent text-slate-500 hover:text-slate-700"
          }`}
        >
          <Receipt className="w-4 h-4" />
          <span>Triple Conciliació (3-Way Matching)</span>
        </button>
        <button
          onClick={() => setTabActiva("NORMA43")}
          className={`py-3 px-4 border-b-2 transition-colors flex items-center gap-1.5 ${
            tabActiva === "NORMA43"
              ? "border-emerald-600 text-emerald-600 dark:text-emerald-400"
              : "border-transparent text-slate-500 hover:text-slate-700"
          }`}
        >
          <FileText className="w-4 h-4" />
          <span>Banc Norma 43</span>
        </button>
      </div>

      {error && (
        <div className="mx-4 mt-3 p-3 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900 text-rose-700 dark:text-rose-300 text-xs flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-rose-600" />
            <span>{error}</span>
          </div>
          <button onClick={() => setError(null)} className="p-1 hover:text-rose-900">
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* Contingut del Tab */}
      <div className="flex-1 p-4 overflow-y-auto">
        {/* TAB 1: VERIFACTU SIF */}
        {tabActiva === "VERIFACTU" && (
          <div>
            {loading && factures.length === 0 ? (
              <div className="flex-1 flex flex-col items-center justify-center p-12 text-center">
                <RefreshCw className="w-6 h-6 animate-spin text-emerald-600 mb-2" />
                <p className="text-xs text-slate-500">Carregant registre de factures oficials...</p>
              </div>
            ) : factures.length === 0 ? (
              <div className="flex-1 flex flex-col items-center justify-center p-12 text-center bg-white dark:bg-slate-900 rounded-2xl border border-dashed border-slate-300 dark:border-slate-800 my-auto shadow-sm">
                <div className="w-14 h-14 rounded-full bg-emerald-50 dark:bg-emerald-950 text-emerald-600 dark:text-emerald-400 flex items-center justify-center mb-3">
                  <QrCode className="w-7 h-7" />
                </div>
                <h3 className="text-base font-bold text-slate-800 dark:text-slate-100">
                  No hi ha factures pendents ni emeses
                </h3>
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 max-w-xs">
                  Estat Dia-0: Les factures es generen després de la liquidació tècnica d'ordres de camp o treballs d'enginyeria amb encadenament criptogràfic SHA-256.
                </p>
              </div>
            ) : (
              <div className="space-y-4">
                {/* Resum de Facturació Oficial */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm">
                    <p className="text-[10px] font-mono uppercase text-slate-400 font-bold">Total Facturat (IVA Inclòs)</p>
                    <h3 className="text-xl font-black text-slate-800 dark:text-slate-100 mt-0.5">
                      {totalFacturat.toFixed(2)} €
                    </h3>
                  </div>

                  <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm">
                    <p className="text-[10px] font-mono uppercase text-slate-400 font-bold">Total Factures Emeses</p>
                    <h3 className="text-xl font-black text-emerald-600 dark:text-emerald-400 mt-0.5">
                      {factures.length}
                    </h3>
                  </div>

                  <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm">
                    <p className="text-[10px] font-mono uppercase text-slate-400 font-bold">Inalterabilitat SIF (PostgreSQL)</p>
                    <p className="text-xs font-semibold text-emerald-700 dark:text-emerald-300 mt-1 flex items-center gap-1">
                      <ShieldCheck className="w-4 h-4" /> Bloqueig UPDATE / DELETE Actiu
                    </p>
                  </div>
                </div>

                {/* Taula de Factures Veri*factu */}
                <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 overflow-hidden shadow-sm">
                  <table className="w-full text-left text-xs border-collapse">
                    <thead>
                      <tr className="bg-slate-50 dark:bg-slate-850 border-b border-slate-200 dark:border-slate-800 font-mono text-[10px] uppercase text-slate-400">
                        <th className="p-3.5">Sèrie / Núm.</th>
                        <th className="p-3.5">Client ID</th>
                        <th className="p-3.5 text-right">Base Imposable</th>
                        <th className="p-3.5 text-right">Quota IVA</th>
                        <th className="p-3.5 text-right">Líquid Exigible</th>
                        <th className="p-3.5">Hash SHA-256</th>
                        <th className="p-3.5 text-center">Estat AEAT</th>
                        <th className="p-3.5 text-center">Cobrament</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                      {factures.map((fac) => (
                        <tr key={fac.id} className="hover:bg-slate-50/60 dark:hover:bg-slate-800/50 transition-colors">
                          <td className="p-3.5 font-mono font-bold text-emerald-700 dark:text-emerald-300">
                            {fac.serie}-{fac.numero_factura}
                          </td>
                          <td className="p-3.5 font-mono text-slate-500">
                            {fac.client_id}
                          </td>
                          <td className="p-3.5 text-right font-mono text-slate-700 dark:text-slate-300">
                            {fac.base_imposable?.toFixed(2)} €
                          </td>
                          <td className="p-3.5 text-right font-mono text-slate-500">
                            {fac.quota_iva?.toFixed(2)} €
                          </td>
                          <td className="p-3.5 text-right font-mono font-bold text-slate-900 dark:text-white">
                            {fac.liquid_exigible?.toFixed(2)} €
                          </td>
                          <td className="p-3.5 font-mono text-[10px] text-slate-400 truncate max-w-[120px]" title={fac.hash_sha256}>
                            {fac.hash_sha256 ? `${fac.hash_sha256.substring(0, 10)}...` : "—"}
                          </td>
                          <td className="p-3.5 text-center">
                            <span className="px-2 py-0.5 rounded-full text-[9px] font-bold bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300">
                              {fac.estat_enviament || "ENVIAT_SOAP"}
                            </span>
                          </td>
                          <td className="p-3.5 text-center">
                            <span className="px-2 py-0.5 rounded-full text-[9px] font-bold bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                              {fac.estat_cobrament || "PENDENT"}
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
        )}

        {/* TAB 2: CONCILIACIÓ */}
        {tabActiva === "CONCILIACIO" && (
          <div className="flex-1 flex flex-col items-center justify-center p-12 text-center bg-white dark:bg-slate-900 rounded-2xl border border-dashed border-slate-300 dark:border-slate-800 my-auto shadow-sm">
            <Receipt className="w-10 h-10 text-slate-400 mb-3" />
            <h3 className="text-base font-bold text-slate-800 dark:text-slate-100">
              Triple Conciliació Automàtica (3-Way Matching)
            </h3>
            <p className="text-xs text-slate-500 max-w-sm mt-1">
              Estat Dia-0: Creuament automàtic d'Ordres de Compra, Albarans de Magatzem i Factures de Proveïdors.
            </p>
          </div>
        )}

        {/* TAB 3: NORMA 43 */}
        {tabActiva === "NORMA43" && (
          <div className="flex-1 flex flex-col items-center justify-center p-12 text-center bg-white dark:bg-slate-900 rounded-2xl border border-dashed border-slate-300 dark:border-slate-800 my-auto shadow-sm">
            <FileText className="w-10 h-10 text-slate-400 mb-3" />
            <h3 className="text-base font-bold text-slate-800 dark:text-slate-100">
              Ingesta Bancària Cuaderno 43
            </h3>
            <p className="text-xs text-slate-500 max-w-sm mt-1">
              Estat Dia-0: Arrossega fitxers .c43 / .n43 de la teva entitat financera per a la conciliació de moviments.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
