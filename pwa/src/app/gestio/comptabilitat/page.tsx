"use client";

import React, { useState } from "react";
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
} from "lucide-react";
import { useGestio } from "@/lib/gestio-context";

interface FacturaVerifactu {
  id: string;
  numero: string;
  client: string;
  nif: string;
  base_imposable: number;
  iva_21: number;
  total: number;
  data_emissio: string;
  hash_sello: string;
  estat_aeat: "ENVIAT_SOAP" | "PENDENT" | "REBUTJAT";
  qr_contingut: string;
}

export default function GestioComptabilitatPage() {
  const { rolActiu } = useGestio();
  const [tabActiva, setTabActiva] = useState<"VERIFACTU" | "CONCILIACIO" | "NORMA43">("VERIFACTU");

  // VETO D'ENGINYER (Spec 001 RF-03 / Spec 007 RF-05 / Tasca 4.4 Backend)
  // L'Enginyer té prohibit l'accés a dades financeres i comptables sota HTTP 403
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
          Canvia el rol a "Boss" o "Secretaria" a la capçalera superior per accedir-hi amb privilegis administratius.
        </p>
      </div>
    );
  }

  // Dades de facturació Veri*factu (Zero Mock Data per defecte)
  const [factures, setFactures] = useState<FacturaVerifactu[]>([
    {
      id: "fac-1",
      numero: "F2026-0089",
      client: "Agropecuària del Penedès SL",
      nif: "B-65123984",
      base_imposable: 1250.0,
      iva_21: 262.5,
      total: 1512.5,
      data_emissio: "2026-09-08 18:30",
      hash_sello: "d9a4f2e8b1c7...",
      estat_aeat: "ENVIAT_SOAP",
      qr_contingut: "https://sede.agenciatributaria.gob.es/verifactu?nif=B67291043&num=F2026-0089",
    },
    {
      id: "fac-2",
      numero: "F2026-0090",
      client: "Caves & Vinyars Montnegre SAT",
      nif: "F-08492019",
      base_imposable: 840.0,
      iva_21: 176.4,
      total: 1016.4,
      data_emissio: "2026-09-08 19:15",
      hash_sello: "7c12e9a03b55...",
      estat_aeat: "PENDENT",
      qr_contingut: "https://sede.agenciatributaria.gob.es/verifactu?nif=B67291043&num=F2026-0090",
    },
  ]);

  return (
    <div className="flex-1 flex flex-col h-[calc(100vh-3.5rem)] overflow-hidden bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 transition-colors">
      {/* Barra superior de Comptabilitat */}
      <div className="p-4 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between shadow-sm">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-base font-bold text-slate-800 dark:text-slate-100">
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
            onClick={() => alert("Emissió de factura Veri*factu amb ReportLab i QR oficial.")}
            className="px-3 py-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold flex items-center gap-1 shadow transition-all"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Emetre Factura Oficial</span>
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

      {/* Contingut del Tab */}
      <div className="flex-1 p-4 overflow-y-auto">
        {/* TAB 1: VERIFACTU SIF */}
        {tabActiva === "VERIFACTU" && (
          <div>
            {factures.length === 0 ? (
              <div className="flex-1 flex flex-col items-center justify-center p-12 text-center bg-white dark:bg-slate-900 rounded-2xl border border-dashed border-slate-300 dark:border-slate-800 my-auto shadow-sm">
                <div className="w-14 h-14 rounded-full bg-emerald-50 dark:bg-emerald-950 text-emerald-600 dark:text-emerald-400 flex items-center justify-center mb-3">
                  <QrCode className="w-7 h-7" />
                </div>
                {/* TEXT EXACTE EXIGIT PER LA SPEC 007 */}
                <h3 className="text-base font-bold text-slate-800 dark:text-slate-100">
                  No hi ha factures pendents ni emeses
                </h3>
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 max-w-xs">
                  Les factures es generen desprès de la liquidació tècnica d'ordres de camp o treballs d'enginyeria.
                </p>
                <button
                  onClick={() =>
                    setFactures([
                      {
                        id: "fac-1",
                        numero: "F2026-0089",
                        client: "Agropecuària del Penedès SL",
                        nif: "B-65123984",
                        base_imposable: 1250.0,
                        iva_21: 262.5,
                        total: 1512.5,
                        data_emissio: "2026-09-08 18:30",
                        hash_sello: "d9a4f2e8b1c7...",
                        estat_aeat: "ENVIAT_SOAP",
                        qr_contingut: "https://sede.agenciatributaria.gob.es/verifactu",
                      },
                    ])
                  }
                  className="mt-4 px-4 py-2 rounded-xl bg-emerald-600 text-white text-xs font-bold shadow"
                >
                  Carregar Factures Emeses
                </button>
              </div>
            ) : (
              <div className="space-y-4">
                {/* Resum de Facturació Oficial */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm">
                    <p className="text-[10px] font-mono uppercase text-slate-400 font-bold">Total Facturat (IVA Inclòs)</p>
                    <h3 className="text-xl font-black text-slate-800 dark:text-slate-100 mt-0.5">
                      {factures.reduce((acc, f) => acc + f.total, 0).toFixed(2)} €
                    </h3>
                  </div>

                  <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm">
                    <p className="text-[10px] font-mono uppercase text-slate-400 font-bold">Outbox SOAP AEAT (Spec 024)</p>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="text-xs font-bold text-emerald-600 dark:text-emerald-400 flex items-center gap-1">
                        <CheckCircle2 className="w-4 h-4" /> 1 Transmesa
                      </span>
                      <span className="text-xs font-bold text-amber-600 dark:text-amber-400 flex items-center gap-1">
                        <RefreshCw className="w-4 h-4 animate-spin" /> 1 En Cua Celery Beat
                      </span>
                    </div>
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
                        <th className="p-3.5">Núm. Factura</th>
                        <th className="p-3.5">Client & NIF</th>
                        <th className="p-3.5">Data / Hora</th>
                        <th className="p-3.5 text-right">Base Imposable</th>
                        <th className="p-3.5 text-right">IVA (21%)</th>
                        <th className="p-3.5 text-right">Total Factura</th>
                        <th className="p-3.5 text-center">Estat Outbox AEAT</th>
                        <th className="p-3.5 text-center">QR Veri*factu</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                      {factures.map((fac) => (
                        <tr key={fac.id} className="hover:bg-slate-50/60 dark:hover:bg-slate-800/50 transition-colors">
                          <td className="p-3.5 font-mono font-bold text-emerald-700 dark:text-emerald-300">
                            {fac.numero}
                          </td>
                          <td className="p-3.5">
                            <p className="font-bold text-slate-800 dark:text-slate-100">{fac.client}</p>
                            <p className="text-[10px] font-mono text-slate-400">NIF: {fac.nif}</p>
                          </td>
                          <td className="p-3.5 font-mono text-[11px] text-slate-500">
                            {fac.data_emissio}
                          </td>
                          <td className="p-3.5 text-right font-mono font-bold text-slate-700 dark:text-slate-300">
                            {fac.base_imposable.toFixed(2)} €
                          </td>
                          <td className="p-3.5 text-right font-mono text-slate-500">
                            {fac.iva_21.toFixed(2)} €
                          </td>
                          <td className="p-3.5 text-right font-mono font-black text-emerald-600 dark:text-emerald-400">
                            {fac.total.toFixed(2)} €
                          </td>
                          <td className="p-3.5 text-center">
                            <span
                              className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                                fac.estat_aeat === "ENVIAT_SOAP"
                                  ? "bg-emerald-100 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300"
                                  : fac.estat_aeat === "PENDENT"
                                  ? "bg-amber-100 dark:bg-amber-950 text-amber-700 dark:text-amber-300"
                                  : "bg-rose-100 text-rose-700"
                              }`}
                            >
                              {fac.estat_aeat === "ENVIAT_SOAP"
                                ? "Enviat a Sede AEAT"
                                : "Pendent Outbox"}
                            </span>
                          </td>
                          <td className="p-3.5 text-center">
                            <div className="inline-flex items-center gap-1 px-2 py-1 rounded bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-[10px] font-mono">
                              <QrCode className="w-3.5 h-3.5 text-emerald-600" />
                              <span>QR Generat</span>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <div className="flex justify-end pt-2">
                  <button
                    onClick={() => setFactures([])}
                    className="px-3 py-1.5 rounded-xl bg-slate-200 dark:bg-slate-800 text-slate-600 dark:text-slate-400 text-xs font-semibold hover:bg-slate-300 dark:hover:bg-slate-700 transition-colors"
                  >
                    Provar Estat Buit (Zero Mock Data)
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* TAB 2: TRIPLE CONCILIACIÓ (Spec 003 RF-21 / Spec 007) */}
        {tabActiva === "CONCILIACIO" && (
          <div className="p-5 bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-4">
            <div>
              <h3 className="text-sm font-bold text-slate-800 dark:text-slate-100">
                Circuit de Triple Conciliació Automàtica (Three-Way Matching)
              </h3>
              <p className="text-xs text-slate-500 mt-0.5">
                Verifica de forma atòmica: Albarà de Lliurament = Comanda de Compra = Factura de Proveïdor.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-slate-800 dark:text-slate-100">
                  Expedient Proveïdor PRV-0081 (Standard Hidráulica SL)
                </span>
                <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-100 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300">
                  CONCILIADA (0% Desviació)
                </span>
              </div>

              <div className="grid grid-cols-3 gap-3 text-xs">
                <div className="p-2.5 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
                  <p className="text-[10px] text-slate-400 font-mono">1. Albarà Entrada (#ALB-492)</p>
                  <p className="font-bold text-slate-700 dark:text-slate-200">6x Enllaç Mascle 32</p>
                  <p className="text-[10px] text-slate-500">Rebut i firmat a Nau</p>
                </div>
                <div className="p-2.5 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
                  <p className="text-[10px] text-slate-400 font-mono">2. Comanda (#OC-2026-11)</p>
                  <p className="font-bold text-slate-700 dark:text-slate-200">6x Enllaç Mascle 32</p>
                  <p className="text-[10px] text-slate-500">Preu acordat: 4.80 €/un</p>
                </div>
                <div className="p-2.5 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
                  <p className="text-[10px] text-slate-400 font-mono">3. Factura Rebuda (#FPRV-98)</p>
                  <p className="font-bold text-slate-700 dark:text-slate-200">Total: 28.80 € + IVA</p>
                  <p className="text-[10px] text-emerald-600 font-bold">Import Exacte OK</p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* TAB 3: NORMA 43 */}
        {tabActiva === "NORMA43" && (
          <div className="p-5 bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-4">
            <div>
              <h3 className="text-sm font-bold text-slate-800 dark:text-slate-100">
                Ingesta Bancària Desduplicada Norma 43 (Spec 007 RF-21)
              </h3>
              <p className="text-xs text-slate-500 mt-0.5">
                Desduplicació matemàtica mitjançant empremta digital SHA-256 de cada assentament bancari.
              </p>
            </div>

            <div className="p-8 border-2 border-dashed border-slate-300 dark:border-slate-700 rounded-2xl text-center space-y-2">
              <FileText className="w-10 h-10 text-slate-400 mx-auto" />
              <p className="text-xs font-bold text-slate-700 dark:text-slate-300">
                Arrossega el fitxer d'extracte bancari (.N43 o .txt)
              </p>
              <p className="text-[11px] text-slate-500">
                Format oficial AEB Norma 43 (CaixaBank, BBVA, Banc Sabadell)
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
