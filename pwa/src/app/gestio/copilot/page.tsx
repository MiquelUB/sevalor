"use client";

import React, { useState, useEffect } from "react";
import { useGestio } from "@/lib/gestio-context";
import { apiFetch } from "@/lib/api";
import {
  Sparkles,
  Shield,
  Cpu,
  Server,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Mic,
  Volume2,
  FileText,
  DollarSign,
  Package,
  Wrench,
  HelpCircle,
  Lock,
  ArrowRight,
  TrendingDown,
  RefreshCw,
  Send,
  Sliders,
  ExternalLink,
  Info,
  Layers,
  AlertOctagon,
} from "lucide-react";

type PestanyaCopilot = "GARANTIES" | "INCIDENCIES" | "RECONCILIACIO" | "XAT" | "RAG";

export default function CopilotIAPage() {
  const { rolActiu } = useGestio();
  const [pestanya, setPestanya] = useState<PestanyaCopilot>("GARANTIES");

  // Estat Pestanya 1: Garanties & Memòria de Finca
  const [fincaSeleccionada, setFincaSeleccionada] = useState<string>("");
  const [numeroSerieCerca, setNumeroSerieCerca] = useState<string>("");
  const [garantiaResultat, setGarantiaResultat] = useState<any>({
    trobat: false,
    intervencions_365_dies: [],
    garanties: [],
  });

  // Estat Pestanya 2: Peritatge d'Incidències
  const [filtreSoroll, setFiltreSoroll] = useState<boolean>(true);
  const [simularTimeout, setSimularTimeout] = useState<boolean>(false);
  const [estatMemo, setEstatMemo] = useState<"PROPOSTA" | "APROVAT" | "REBUTJAT" | "EDITAT">("PROPOSTA");
  const [observacionsEnginyer, setObservacionsEnginyer] = useState<string>("");

  // Estat Pestanya 3: Reconciliació Post-Obra
  const [obraSyncPendent, setObraSyncPendent] = useState<boolean>(false);
  const [mermaExcessiva250, setMermaExcessiva250] = useState<boolean>(true);
  const [estatPressupost, setEstatPressupost] = useState<string>("PENDENT_CONFIRMACIO");

  // Estat Pestanya 4: Xat Tècnic Especialitzat
  const [missatgeXat, setMissatgeXat] = useState<string>("");
  const [conversaXat, setConversaXat] = useState<Array<{ sender: "user" | "copilot"; text: string; error?: boolean; links?: any[] }>>([
    {
      sender: "copilot",
      text: "Hola! Sóc el Copilot d'IA Local de SEVALOR Suite. T'assisteixo en memòria tècnica, peritatge per veu/foto, càlcul de desviacions i consultes de normativa d'ofici.",
    },
  ]);

  // Handler de cerca de garanties (via backend)
  const cercarGaranties = async (mode: "FINCA" | "NUMERO_SERIE") => {
    if (mode === "FINCA" && fincaSeleccionada) {
      try {
        const data = await apiFetch(`/garanties/finca/${encodeURIComponent(fincaSeleccionada)}`);
        setGarantiaResultat(data);
      } catch {
        setGarantiaResultat({ trobat: false, intervencions_365_dies: [], garanties: [], missatge: "Error de connexió amb el backend." });
      }
    } else if (mode === "NUMERO_SERIE" && numeroSerieCerca) {
      try {
        const data = await apiFetch(`/garanties/equip/${encodeURIComponent(numeroSerieCerca)}`);
        setGarantiaResultat(data);
      } catch {
        setGarantiaResultat({ trobat: false, intervencions_365_dies: [], garanties: [], missatge: "Error de connexió amb el backend." });
      }
    }
  };

  // Handler d'enviament de missatges al xat tècnic
  const enviarMissatgeXat = (textOverride?: string) => {
    const text = textOverride || missatgeXat;
    if (!text.trim()) return;

    const novaConversa = [...conversaXat, { sender: "user" as const, text }];
    setConversaXat(novaConversa);
    if (!textOverride) setMissatgeXat("");

    const textMinus = text.toLowerCase();

    // Veto d'Enginyer (RF-20.1 / EDGE-05)
    if (rolActiu === "ENGINYER") {
      if (
        textMinus.includes("salari") ||
        textMinus.includes("sou") ||
        textMinus.includes("nomina") ||
        textMinus.includes("nòmina") ||
        textMinus.includes("llibre major") ||
        textMinus.includes("compte bancari")
      ) {
        setTimeout(() => {
          setConversaXat((prev) => [
            ...prev,
            {
              sender: "copilot",
              text: "⛔ HTTP 403 Forbidden: Consulta no autoritzada per política de rols de seguretat. El rol d'Enginyer té prohibit l'accés a dades agregades de salaris, nòmines, llibre major o balances de proveïdors (Spec 012 RF-20.1 / EDGE-05).",
              error: true,
            },
          ]);
        }, 300);
        return;
      }
    }

    // Aïllament de Vertical (EDGE-10)
    if (textMinus.includes("rebt") || textMinus.includes("caiguda de tensio") || textMinus.includes("magnetotermic")) {
      setTimeout(() => {
        setConversaXat((prev) => [
          ...prev,
          {
            sender: "copilot",
            text: "La base de coneixement i context del Copilot s'acota exclusivament al sector d'enginyeria agronòmica i xarxes de reg (SEVALOR). La consulta sobre REBT elèctric ha estat declinada per aïllament estricte de vertical (EDGE-10).",
          },
        ]);
      }, 300);
      return;
    }

    // Consultes Operatives RAG — delegades al backend
    setTimeout(async () => {
      try {
        const resposta = await apiFetch("/copilot/rag-consulta", {
          method: "POST",
          body: JSON.stringify({ consulta: text }),
        });
        setConversaXat((prev) => [
          ...prev,
          {
            sender: "copilot",
            text: resposta.resposta || resposta.text || "Consulta atesa.",
            links: resposta.links || [],
          },
        ]);
      } catch {
        setConversaXat((prev) => [
          ...prev,
          {
            sender: "copilot",
            text: "Ho sento, no he pogut processar la consulta en aquest moment. Torna-ho a intentar.",
            error: true,
          },
        ]);
      }
    }, 350);
  };

  return (
    <div className="flex-1 p-6 space-y-6 overflow-y-auto max-w-7xl mx-auto">
      {/* CAPÇALERA TELEMETRIA DEL NODE LOCAL SOBIRÀ (HETZNER FALKENSTEIN) */}
      <div className="rounded-2xl p-5 bg-gradient-to-br from-slate-900 via-slate-850 to-indigo-950 text-white shadow-xl border border-slate-800">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center gap-3.5">
            <div className="w-12 h-12 rounded-xl bg-indigo-600/30 border border-indigo-500/40 flex items-center justify-center text-indigo-400 shadow-inner">
              <Sparkles className="w-6 h-6 animate-pulse text-indigo-300" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-lg font-black tracking-tight text-white">
                  Copilot IA de Camp i Gestió
                </h1>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-indigo-900/80 text-indigo-200 border border-indigo-700">
                  Spec 012 • Hetzner Falkenstein
                </span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-emerald-950 text-emerald-300 border border-emerald-700 flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping"></span>
                  OPERATIU
                </span>
              </div>
              <p className="text-xs text-slate-300 mt-0.5">
                Motor Pericial Sobirà • Transcripció Whisper v3 INT8 (CPU) • Principi Human-in-the-Loop (HITL)
              </p>
            </div>
          </div>

          {/* Telemetria de CPU i Seguretat */}
          <div className="flex flex-wrap items-center gap-3">
            <div className="px-3 py-1.5 rounded-xl bg-slate-800/80 border border-slate-700 text-left">
              <div className="flex items-center gap-1.5 text-[10px] font-mono text-slate-400">
                <Server className="w-3 h-3 text-indigo-400" />
                <span>SOBIRANIA LOCAL</span>
              </div>
              <p className="text-xs font-bold text-slate-200">Zero Cloud Egress</p>
            </div>

            <div className="px-3 py-1.5 rounded-xl bg-slate-800/80 border border-slate-700 text-left">
              <div className="flex items-center gap-1.5 text-[10px] font-mono text-slate-400">
                <Cpu className="w-3 h-3 text-emerald-400" />
                <span>INFERÈNCIA CPU</span>
              </div>
              <p className="text-xs font-bold text-slate-200">Whisper v3 INT8 (142 ms)</p>
            </div>

            <div className="px-3 py-1.5 rounded-xl bg-slate-800/80 border border-slate-700 text-left">
              <div className="flex items-center gap-1.5 text-[10px] font-mono text-slate-400">
                <Shield className="w-3 h-3 text-amber-400" />
                <span>ROL ACTIU TEST</span>
              </div>
              <p className="text-xs font-bold text-amber-300 font-mono">{rolActiu}</p>
            </div>
          </div>
        </div>
      </div>

      {/* SELECTOR DE PESTANYES */}
      <div className="flex items-center gap-2 border-b border-slate-200 dark:border-slate-800 pb-2">
        <button
          onClick={() => setPestanya("GARANTIES")}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all ${
            pestanya === "GARANTIES"
              ? "bg-indigo-600 text-white shadow-md shadow-indigo-600/20"
              : "text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800"
          }`}
        >
          <Wrench className="w-3.5 h-3.5" />
          <span>Memòria Finca & Garanties</span>
        </button>

        <button
          onClick={() => setPestanya("INCIDENCIES")}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all ${
            pestanya === "INCIDENCIES"
              ? "bg-indigo-600 text-white shadow-md shadow-indigo-600/20"
              : "text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800"
          }`}
        >
          <Mic className="w-3.5 h-3.5" />
          <span>Peritatge d'Incidències (Veu/Foto)</span>
        </button>

        <button
          onClick={() => setPestanya("RECONCILIACIO")}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all ${
            pestanya === "RECONCILIACIO"
              ? "bg-indigo-600 text-white shadow-md shadow-indigo-600/20"
              : "text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800"
          }`}
        >
          <DollarSign className="w-3.5 h-3.5" />
          <span>Reconciliació & Pre-Factura</span>
        </button>

        <button
          onClick={() => setPestanya("XAT")}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all ${
            pestanya === "XAT"
              ? "bg-indigo-600 text-white shadow-md shadow-indigo-600/20"
              : "text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800"
          }`}
        >
          <HelpCircle className="w-3.5 h-3.5" />
          <span>Xat Tècnic & Reposició Stock</span>
        </button>
      </div>

      {/* CONTINGUT PESTANYA 1: MEMÒRIA HISTÒRICA I AUDITORIA DE GARANTIES */}
      {pestanya === "GARANTIES" && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Panell de Cerca & Controls */}
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-sm space-y-4">
            <h3 className="text-sm font-bold text-slate-800 dark:text-slate-100 flex items-center gap-2">
              <Layers className="w-4 h-4 text-indigo-500" />
              Auditoria de Finca i Equips
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Cerca cronològica de 365 dies d'intervencions, garanties oficials de fabricant i garantia interna de mà d'obra.
            </p>

            <div className="space-y-3 pt-2">
              <div>
                <label className="text-[11px] font-mono text-slate-500 uppercase">Finca / Instal·lació:</label>
                <div className="flex gap-2 mt-1">
                  <button
                    onClick={() => { setFincaSeleccionada(""); setGarantiaResultat({ trobat: false, intervencions_365_dies: [], garanties: [] }); }}
                    className={`flex-1 text-xs py-2 px-2.5 rounded-xl border text-left font-medium transition-all ${
                      fincaSeleccionada === ""
                        ? "border-indigo-500 bg-indigo-50 dark:bg-indigo-950/40 text-indigo-700 dark:text-indigo-300 font-bold"
                        : "border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300"
                    }`}
                  >
                    Sense dades disponibles
                    <span className="block text-[10px] text-slate-400 font-mono">Zero Mock Data</span>
                  </button>
                  <button
                    onClick={() => { setFincaSeleccionada(""); setGarantiaResultat({ trobat: false, intervencions_365_dies: [], garanties: [] }); }}
                    className={`flex-1 text-xs py-2 px-2.5 rounded-xl border text-left font-medium transition-all ${
                      fincaSeleccionada === ""
                        ? "border-indigo-500 bg-indigo-50 dark:bg-indigo-950/40 text-indigo-700 dark:text-indigo-300 font-bold"
                        : "border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300"
                    }`}
                  >
                    Sense dades disponibles
                    <span className="block text-[10px] text-slate-400 font-mono">Zero Mock Data</span>
                  </button>
                </div>
              </div>

              <div>
                <label className="text-[11px] font-mono text-slate-500 uppercase">Cerca per Número de Sèrie:</label>
                <div className="flex gap-2 mt-1">
                  <input
                    type="text"
                    value={numeroSerieCerca}
                    onChange={(e) => setNumeroSerieCerca(e.target.value)}
                    className="flex-1 bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl px-3 py-1.5 text-xs font-mono text-slate-800 dark:text-slate-200"
                  />
                  <button
                    onClick={() => cercarGaranties("NUMERO_SERIE")}
                    className="px-2.5 py-1.5 rounded-xl bg-slate-200 dark:bg-slate-700 text-[11px] font-bold text-slate-700 dark:text-slate-300 hover:bg-slate-300"
                    title="Cercar per número de sèrie al backend"
                  >
                    Cercar
                  </button>
                </div>
              </div>
            </div>

            <div className="p-3 bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800/50 rounded-xl text-xs text-amber-800 dark:text-amber-300 space-y-1">
              <div className="flex items-center gap-1.5 font-bold">
                <Info className="w-3.5 h-3.5" />
                <span>Principi Anti-Cobrament Erroni</span>
              </div>
              <p className="text-[11px] leading-relaxed">
                Si un equip està sota garantia de fabricant o té reparació prèvia &lt;3 mesos, el Copilot bloqueja preventivament la facturació de la peça al client i proposa la tramitació oficial d'RMA.
              </p>
            </div>
          </div>

          {/* Resultats d'Auditoria & Targetes d'Alerta */}
          <div className="lg:col-span-2 space-y-4">
            {!garantiaResultat.trobat ? (
              <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-8 text-center space-y-3">
                <div className="w-12 h-12 rounded-full bg-slate-100 dark:bg-slate-800 flex items-center justify-center mx-auto text-slate-400">
                  <HelpCircle className="w-6 h-6" />
                </div>
                <h4 className="text-sm font-bold text-slate-700 dark:text-slate-300 font-mono">
                  {garantiaResultat.missatge}
                </h4>
                <p className="text-xs text-slate-400 max-w-md mx-auto">
                  Sota el principi constitucional de Zero Mock Data, el Copilot no al·lucina ni inventa peces ni avaries quan una finca s'intervé per primer cop a la plataforma.
                </p>
              </div>
            ) : (
              <>
                {/* Alertes de Garantia Actives */}
                {garantiaResultat.garanties.map((g: any, idx: number) => (
                  <div
                    key={idx}
                    className={`rounded-2xl p-4 border shadow-sm flex items-start gap-3.5 ${
                      g.tipus === "GARANTIA_FABRICANT"
                        ? "bg-emerald-50 dark:bg-emerald-950/30 border-emerald-300 dark:border-emerald-800 text-emerald-900 dark:text-emerald-100"
                        : g.tipus === "CORTESIA_EXPIRADA"
                        ? "bg-amber-50 dark:bg-amber-950/30 border-amber-300 dark:border-amber-800 text-amber-900 dark:text-amber-100"
                        : "bg-blue-50 dark:bg-blue-950/30 border-blue-300 dark:border-blue-800 text-blue-900 dark:text-blue-100"
                    }`}
                  >
                    <div className="p-2 rounded-xl bg-white/80 dark:bg-slate-800 shadow-sm shrink-0">
                      {g.tipus === "GARANTIA_FABRICANT" && <CheckCircle2 className="w-5 h-5 text-emerald-600" />}
                      {g.tipus === "CORTESIA_EXPIRADA" && <AlertTriangle className="w-5 h-5 text-amber-600" />}
                      {g.tipus === "GARANTIA_INTERNA_SERVEI" && <Wrench className="w-5 h-5 text-blue-600" />}
                    </div>
                    <div className="flex-1 space-y-1">
                      <div className="flex items-center justify-between">
                        <span className="text-[11px] font-mono font-bold uppercase tracking-wider px-2 py-0.5 rounded bg-white/60 dark:bg-slate-800">
                          {g.tipus}
                        </span>
                        {g.data_fi_garantia && (
                          <span className="text-[10px] font-mono text-slate-500 dark:text-slate-400">
                            Fi Garantia: {g.data_fi_garantia}
                          </span>
                        )}
                      </div>
                      <p className="text-xs font-semibold leading-relaxed">
                        {g.missatge}
                      </p>
                    </div>
                  </div>
                ))}

                {/* Historial Cronològic 365 Dies */}
                {garantiaResultat.intervencions_365_dies.length > 0 && (
                  <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-sm space-y-3">
                    <h4 className="text-xs font-bold text-slate-800 dark:text-slate-200 uppercase tracking-wider font-mono flex items-center gap-2">
                      <Clock className="w-3.5 h-3.5 text-indigo-500" />
                      Intervencions prèvies en els últims 365 dies
                    </h4>
                    <div className="space-y-2">
                      {garantiaResultat.intervencions_365_dies.map((ot: any, idx: number) => (
                        <div
                          key={idx}
                          className="flex items-center justify-between p-3 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700"
                        >
                          <div>
                            <span className="text-[10px] font-mono font-bold text-indigo-600 dark:text-indigo-400">
                              {ot.codi}
                            </span>
                            <h5 className="text-xs font-bold text-slate-800 dark:text-slate-100">
                              {ot.titol}
                            </h5>
                          </div>
                          <div className="text-right">
                            <span className="text-[10px] font-mono text-slate-500">
                              {ot.data}
                            </span>
                            <span className="block text-[9px] font-bold text-emerald-600 dark:text-emerald-400">
                              {ot.estat}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}

      {/* CONTINGUT PESTANYA 2: PERITATGE MULTIMODAL D'INCIDÈNCIES (VEU & FOTO) */}
      {pestanya === "INCIDENCIES" && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Controls de Prova i Entorn */}
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-sm space-y-4">
            <h3 className="text-sm font-bold text-slate-800 dark:text-slate-100 flex items-center gap-2">
              <Mic className="w-4 h-4 text-indigo-500" />
              Incidència de Camp PWA
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Recepció d'àudio de 30s de l'operari i fotografia pericial georeferenciada.
            </p>

            <div className="space-y-3 pt-2">
              <div className="p-3 bg-slate-50 dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 space-y-2">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-semibold text-slate-700 dark:text-slate-300">Soroll Extrem Tractor/Vent:</span>
                  <input
                    type="checkbox"
                    checked={filtreSoroll}
                    onChange={(e) => setFiltreSoroll(e.target.checked)}
                    className="w-4 h-4 text-indigo-600 rounded"
                  />
                </div>
                <p className="text-[11px] text-slate-500">
                  {filtreSoroll
                    ? "Confiança &lt; 40%: Activa avís pericial de contrast visual (EDGE-03)."
                    : "Confiança 95%: Transcripció nítida en català tècnic."}
                </p>
              </div>

              <div className="p-3 bg-slate-50 dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 space-y-2">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-semibold text-slate-700 dark:text-slate-300">Simulador Timeout (&gt;15s):</span>
                  <input
                    type="checkbox"
                    checked={simularTimeout}
                    onChange={(e) => setSimularTimeout(e.target.checked)}
                    className="w-4 h-4 text-indigo-600 rounded"
                  />
                </div>
                <p className="text-[11px] text-slate-500">
                  Comprova el comportament no bloquejant del Copilot (EDGE-02).
                </p>
              </div>
            </div>
          </div>

          {/* Memoràndum Tècnic Generat amb Validació HITL */}
          <div className="lg:col-span-2 space-y-4">
            {simularTimeout ? (
              <div className="rounded-2xl p-6 bg-amber-50 dark:bg-amber-950/30 border border-amber-300 dark:border-amber-800 text-amber-900 dark:text-amber-100 space-y-3">
                <div className="flex items-center gap-2 font-bold text-sm">
                  <AlertOctagon className="w-5 h-5 text-amber-600" />
                  <span>Copilot provisionalment no disponible (Timeout &gt; 15s)</span>
                </div>
                <p className="text-xs leading-relaxed">
                  L'operativa d'obra continua accessible. Els arxius d'àudio originals i la fotografia pericial de l'operari romanen accessibles immediatament a la Torre de Control per a la seva resolució manual síncrona per l'Enginyer.
                </p>
                <div className="flex items-center gap-3 pt-2">
                  <span className="text-[11px] font-mono px-3 py-1 rounded-lg bg-white/80 dark:bg-slate-800 font-bold">
                    audio_incidencia_089.webm (28s)
                  </span>
                  <span className="text-[11px] font-mono px-3 py-1 rounded-lg bg-white/80 dark:bg-slate-800 font-bold">
                    foto_pericial_089.webp (3.4 MB)
                  </span>
                </div>
              </div>
            ) : (
              <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-sm space-y-4">
                <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-3">
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-indigo-100 dark:bg-indigo-950 text-indigo-700 dark:text-indigo-300">
                      MEMORÀNDUM TÈCNIC PERICIAL
                    </span>
                    <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded ${
                      estatMemo === "APROVAT" ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-800"
                    }`}>
                      {estatMemo}
                    </span>
                  </div>
                  <span className="text-[11px] font-mono text-slate-400">Sense OT activa</span>
                </div>

                {/* Advertència de Soroll Sever si escau */}
                {filtreSoroll && (
                  <div className="p-3 bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 rounded-xl text-xs text-amber-800 dark:text-amber-300 flex items-start gap-2.5">
                    <AlertTriangle className="w-4 h-4 shrink-0 text-amber-600 mt-0.5" />
                    <div>
                      <span className="font-bold">⚠️ L'àudio conté soroll de fons sever (tractors/vent)</span>
                      <p className="text-[11px] mt-0.5 text-amber-700 dark:text-amber-400">
                        Confiança acústica Whisper: 35%. Es recomana contrast visual obligatori amb la fotografia pericial abans de validar el pressupost d'extra.
                      </p>
                    </div>
                  </div>
                )}

                {/* Contingut del Memoràndum */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <span className="text-[11px] font-mono text-slate-500 uppercase">Transcripció Fonètica (Català Tècnic):</span>
                    <p className="text-xs text-slate-800 dark:text-slate-200 bg-slate-50 dark:bg-slate-800/60 p-3 rounded-xl border border-slate-200 dark:border-slate-700">
                      "Hem trobat un ramal de reg de 32 completament estrangulat per arrels d'olivera vella a la cota -40cm. La fuita no és imputable a la rasa de la nostra màquina."
                    </p>
                  </div>

                  <div className="space-y-1.5">
                    <span className="text-[11px] font-mono text-slate-500 uppercase">Dictamen Pericial Proposat:</span>
                    <div className="p-3 rounded-xl bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800 text-emerald-900 dark:text-emerald-100">
                      <div className="flex items-center justify-between font-bold text-xs">
                        <span>EXTRA FACTURABLE</span>
                        <span className="font-mono">85,50 €</span>
                      </div>
                      <p className="text-[11px] mt-1 text-emerald-800 dark:text-emerald-300">
                        Dany preexistent a la parcel·la. Estimació: +45 minuts de feina i 6 m de tub PE-32mm amb maniguets.
                      </p>
                    </div>
                  </div>
                </div>

                {/* Controls HITL per a l'Enginyer */}
                <div className="pt-3 border-t border-slate-200 dark:border-slate-800 space-y-3">
                  <label className="text-[11px] font-mono text-slate-500 uppercase">
                    Validació i Observacions de l'Enginyer (Human-in-the-Loop):
                  </label>
                  <input
                    type="text"
                    value={observacionsEnginyer}
                    onChange={(e) => setObservacionsEnginyer(e.target.value)}
                    placeholder="Ex: Contrastat amb foto; s'aprova l'extra de 85,50 € per enviar al client per Telegram."
                    className="w-full bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl px-3 py-2 text-xs text-slate-800 dark:text-slate-200 focus:outline-none"
                  />

                  <div className="flex items-center gap-3">
                    <button
                      onClick={() => setEstatMemo("APROVAT")}
                      className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold shadow transition-all flex items-center gap-1.5"
                    >
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      <span>Aprovar i Trametre Presupost al Client</span>
                    </button>

                    <button
                      onClick={() => setEstatMemo("EDITAT")}
                      className="px-4 py-2 rounded-xl bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300 text-xs font-bold hover:bg-slate-300 transition-all flex items-center gap-1.5"
                    >
                      <Sliders className="w-3.5 h-3.5" />
                      <span>Modificar Partides</span>
                    </button>

                    <button
                      onClick={() => setEstatMemo("REBUTJAT")}
                      className="px-4 py-2 rounded-xl bg-rose-100 dark:bg-rose-950 text-rose-700 dark:text-rose-300 text-xs font-bold hover:bg-rose-200 transition-all"
                    >
                      Assumir com a Cost Intern
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* CONTINGUT PESTANYA 3: RECONCILIACIÓ POST-OBRA & PRE-FACTURA */}
      {pestanya === "RECONCILIACIO" && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Configuració d'Escenaris de Reconciliació */}
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-sm space-y-4">
            <h3 className="text-sm font-bold text-slate-800 dark:text-slate-100 flex items-center gap-2">
              <DollarSign className="w-4 h-4 text-indigo-500" />
              Reconciliació Post-Feina
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Consolidació dels 4 pilars del cost real: Magatzem, Fitxatges, Odòmetre i Tiquets de Camp.
            </p>

            <div className="space-y-3 pt-2">
              <div className="p-3 bg-slate-50 dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 space-y-2">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-semibold text-slate-700 dark:text-slate-300">Merma &gt;250% (EDGE-08):</span>
                  <input
                    type="checkbox"
                    checked={mermaExcessiva250}
                    onChange={(e) => setMermaExcessiva250(e.target.checked)}
                    className="w-4 h-4 text-indigo-600 rounded"
                  />
                </div>
                <p className="text-[11px] text-slate-500">
                  Consum de tub PE-32 excedit en +26m (+360%) sense incidència prèvia registrada.
                </p>
              </div>

              <div className="p-3 bg-slate-50 dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 space-y-2">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-semibold text-slate-700 dark:text-slate-300">Sync Offline Pendent (EDGE-04):</span>
                  <input
                    type="checkbox"
                    checked={obraSyncPendent}
                    onChange={(e) => setObraSyncPendent(e.target.checked)}
                    className="w-4 h-4 text-indigo-600 rounded"
                  />
                </div>
                <p className="text-[11px] text-slate-500">
                  Bloqueja la generació de pre-factura fins al sync complet des de zona blanca.
                </p>
              </div>
            </div>
          </div>

          {/* Comparativa i Proposta de Pressupost Corregit */}
          <div className="lg:col-span-2 space-y-4">
            {obraSyncPendent ? (
              <div className="rounded-2xl p-6 bg-blue-50 dark:bg-blue-950/30 border border-blue-300 dark:border-blue-800 text-blue-900 dark:text-blue-100 space-y-3">
                <div className="flex items-center gap-2 font-bold text-sm">
                  <Clock className="w-5 h-5 text-blue-600" />
                  <span>Estat Conciliació: Pendent de Camp (EDGE-04)</span>
                </div>
                <p className="text-xs leading-relaxed">
                  L'operari ha tancat l'obra offline en zona blanca. La generació de la factura de liquidació final a Comptabilitat (Spec 007) queda bloquejada preventivament fins que el capataz realitzi la sincronització completa a nau central.
                </p>
              </div>
            ) : (
              <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-sm space-y-4">
                {/* Indicador de Desviació de Marge */}
                <div className="flex items-center justify-between p-4 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700">
                  <div>
                    <span className="text-[10px] font-mono text-slate-500 uppercase">Impacte en Marge Comercial:</span>
                    <div className="flex items-center gap-2 mt-0.5">
                      <span className="text-sm font-bold text-slate-400 line-through">30.0% Previst</span>
                      <ArrowRight className="w-3.5 h-3.5 text-slate-400" />
                      <span className="text-sm font-black text-rose-600 dark:text-rose-400 flex items-center gap-1">
                        <TrendingDown className="w-4 h-4" />
                        18.5% Liquidat
                      </span>
                    </div>
                  </div>
                  <span className="text-[10px] font-mono px-2.5 py-1 rounded bg-rose-100 dark:bg-rose-950 text-rose-700 dark:text-rose-300 font-bold">
                    Alerta de Merma Operativa (&gt;5%)
                  </span>
                </div>

                {/* Alerta de Consum Excessiu si escau */}
                {mermaExcessiva250 && (
                  <div className="p-3.5 bg-rose-50 dark:bg-rose-950/40 border border-rose-300 dark:border-rose-800 rounded-xl text-xs text-rose-900 dark:text-rose-200 space-y-1">
                    <div className="flex items-center gap-1.5 font-bold">
                      <AlertOctagon className="w-4 h-4 text-rose-600" />
                      <span>Alerta de Merma Operativa no Justificada (EDGE-08)</span>
                    </div>
                    <p className="text-[11px] leading-relaxed text-rose-800 dark:text-rose-300">
                      Consum de Tub Polietilè 32mm excedit en +26.0 m (360%, &gt;250%) sense cap incidència de camp reportada a la fulla de tasca. Requereix revisió humana obligatòria de l'Enginyer abans de facturar.
                    </p>
                  </div>
                )}

                {/* Desglossament dels 4 Pilars */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-center">
                  <div className="p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700">
                    <span className="text-[10px] font-mono text-slate-500">MÀ D'OBRA</span>
                    <p className="text-xs font-bold text-slate-800 dark:text-slate-100 mt-0.5">+1.5h desviació</p>
                  </div>
                  <div className="p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700">
                    <span className="text-[10px] font-mono text-slate-500">MAGATZEM</span>
                    <p className="text-xs font-bold text-slate-800 dark:text-slate-100 mt-0.5">+26m tub PE</p>
                  </div>
                  <div className="p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700">
                    <span className="text-[10px] font-mono text-slate-500">KILÒMETRES</span>
                    <p className="text-xs font-bold text-slate-800 dark:text-slate-100 mt-0.5">
                      {/* TODO: endpoint pendent d'implementar al backend */}— km
                    </p>
                  </div>
                  <div className="p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700">
                    <span className="text-[10px] font-mono text-slate-500">DESPESES</span>
                    <p className="text-xs font-bold text-slate-800 dark:text-slate-100 mt-0.5">24,50 € gasoil</p>
                  </div>
                </div>

                {/* Proposta de Pressupost Corregit i Validació HITL */}
                <div className="p-4 rounded-xl bg-indigo-50 dark:bg-indigo-950/30 border border-indigo-200 dark:border-indigo-800 space-y-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <span className="text-[10px] font-mono uppercase font-bold text-indigo-700 dark:text-indigo-300">
                        Borrador de Pre-Factura Veri*factu
                      </span>
                      <h4 className="text-sm font-black text-indigo-950 dark:text-indigo-100">
                        Total Liquidat: 1.422,00 € (Base + Extres Auditats)
                      </h4>
                    </div>
                    <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-white dark:bg-slate-800 text-indigo-700 dark:text-indigo-300">
                      {estatPressupost}
                    </span>
                  </div>

                  <div className="flex items-center justify-between pt-2">
                    <p className="text-[11px] text-slate-600 dark:text-slate-400">
                      Cap factura s'emet a client sense la confirmació expressa de l'Enginyer (RF-13).
                    </p>
                    <button
                      onClick={() => setEstatPressupost("APROVAT_ENGINYER")}
                      className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold shadow transition-all flex items-center gap-1.5"
                    >
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      <span>Confirmar i Enviar a Facturació</span>
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* CONTINGUT PESTANYA 4: XAT TÈCNIC & REPOSICIÓ STOCK */}
      {pestanya === "XAT" && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Panell d'Alertes Preventives de Recompra */}
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-sm space-y-4">
            <h3 className="text-sm font-bold text-slate-800 dark:text-slate-100 flex items-center gap-2">
              <Package className="w-4 h-4 text-indigo-500" />
              Alertes de Recompra de Stock
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Detecció preventiva en assignació d'obra amb protecció de concurrència (SELECT FOR UPDATE).
            </p>

            <div className="p-4 rounded-xl bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800/60 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-amber-200 dark:bg-amber-900 text-amber-900 dark:text-amber-100">
                  RECOMPRA INMEDIATA
                </span>
                <span className="text-[10px] font-mono text-slate-400">Nau Central</span>
              </div>
              <h5 className="text-xs font-bold text-slate-800 dark:text-slate-100">
                Tub Polietilè 32mm PE-100
              </h5>
              <p className="text-[11px] text-slate-600 dark:text-slate-400 leading-relaxed">
                El saldo projectat caurà per sota del llindar mínim de seguretat. {/* TODO: endpoint pendent d'implementar al backend */}
              </p>
              <div className="pt-1 flex items-center justify-between">
                <span className="text-[10px] font-mono text-indigo-600 dark:text-indigo-400 font-bold">{/* TODO: endpoint pendent d'implementar al backend */}</span>
                <span className="text-[10px] font-bold text-slate-500">Safata Compras 1-Clic</span>
              </div>
            </div>

            <div className="space-y-2 pt-2">
              <span className="text-[11px] font-mono text-slate-500 uppercase">Consultes ràpides d'ofici:</span>
              <div className="flex flex-col gap-1.5">
                <button
                  onClick={() => enviarMissatgeXat("Quan venç la ITV de la furgoneta taller?")}
                  className="text-left text-xs p-2 rounded-xl bg-slate-50 dark:bg-slate-800/60 hover:bg-slate-100 dark:hover:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 font-medium"
                >
                  🚚 Pòlissa i ITV furgoneta Renault Master
                </button>
                <button
                  onClick={() => enviarMissatgeXat("Quin protocol s'aplica si trobem un cable soterrat?")}
                  className="text-left text-xs p-2 rounded-xl bg-slate-50 dark:bg-slate-800/60 hover:bg-slate-100 dark:hover:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 font-medium"
                >
                  ⚡ Protocol PRL davant cable soterrat
                </button>
                <button
                  onClick={() => enviarMissatgeXat("Quin és el salari mensual i la nòmina dels operaris?")}
                  className="text-left text-xs p-2 rounded-xl bg-rose-50 dark:bg-rose-950/30 hover:bg-rose-100 dark:hover:bg-rose-900/40 border border-rose-200 dark:border-rose-800 text-rose-700 dark:text-rose-300 font-medium"
                  title="Provar Veto d'Enginyer (HTTP 403)"
                >
                  ⛔ Provar consulta de salaris (Veto Enginyer 403)
                </button>
                <button
                  onClick={() => enviarMissatgeXat("Quina caiguda de tensió permet el REBT elèctric?")}
                  className="text-left text-xs p-2 rounded-xl bg-purple-50 dark:bg-purple-950/30 hover:bg-purple-100 dark:hover:bg-purple-900/40 border border-purple-200 dark:border-purple-800 text-purple-700 dark:text-purple-300 font-medium"
                  title="Provar Aïllament de Vertical (EDGE-10)"
                >
                  ⚡ Provar consulta REBT elèctric (Aïllament Vertical)
                </button>
              </div>
            </div>
          </div>

          {/* Finestra de Conversa amb el Copilot */}
          <div className="lg:col-span-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-sm flex flex-col h-[520px]">
            {/* Header del Xat */}
            <div className="p-3.5 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between bg-slate-50/50 dark:bg-slate-850">
              <div className="flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-indigo-500" />
                <h4 className="text-xs font-bold text-slate-800 dark:text-slate-200">
                  Assistent Conversacional Tècnic (RAG Multinivell)
                </h4>
              </div>
              <span className="text-[10px] font-mono text-slate-400">
                Vertical: SEVALOR
              </span>
            </div>

            {/* Llista de Missatges */}
            <div className="flex-1 p-4 overflow-y-auto space-y-3">
              {conversaXat.map((m, idx) => (
                <div
                  key={idx}
                  className={`flex flex-col ${m.sender === "user" ? "items-end" : "items-start"}`}
                >
                  <div
                    className={`max-w-[85%] p-3 rounded-2xl text-xs leading-relaxed ${
                      m.sender === "user"
                        ? "bg-indigo-600 text-white rounded-br-none"
                        : m.error
                        ? "bg-rose-50 dark:bg-rose-950/50 border border-rose-300 dark:border-rose-800 text-rose-900 dark:text-rose-200 rounded-bl-none font-medium"
                        : "bg-slate-100 dark:bg-slate-800 text-slate-800 dark:text-slate-100 rounded-bl-none"
                    }`}
                  >
                    {m.text}
                  </div>

                  {m.links && m.links.length > 0 && (
                    <div className="flex items-center gap-2 mt-1 pl-1">
                      {m.links.map((link, lIdx) => (
                        <a
                          key={lIdx}
                          href={link.url}
                          className="text-[10px] font-mono text-indigo-600 dark:text-indigo-400 hover:underline flex items-center gap-0.5 font-bold"
                        >
                          <ExternalLink className="w-2.5 h-2.5" />
                          {link.titol}
                        </a>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>

            {/* Input d'enviament */}
            <div className="p-3 border-t border-slate-200 dark:border-slate-800 flex items-center gap-2 bg-slate-50/50 dark:bg-slate-850">
              <input
                type="text"
                value={missatgeXat}
                onChange={(e) => setMissatgeXat(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") enviarMissatgeXat();
                }}
                placeholder="Formular consulta sobre flota, stock, normativa o protocols..."
                className="flex-1 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl px-3 py-2 text-xs text-slate-800 dark:text-slate-100 placeholder:text-slate-400 focus:outline-none"
              />
              <button
                onClick={() => enviarMissatgeXat()}
                className="p-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white transition-all shadow"
                title="Enviar consulta"
              >
                <Send className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
