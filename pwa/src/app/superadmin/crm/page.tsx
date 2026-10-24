"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Target,
  Plus,
  Play,
  Clock,
  Calendar,
  Building2,
  Mail,
  Phone,
  User,
  Users,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  TrendingUp,
  FileText,
  MessageSquare,
  Sparkles,
  ExternalLink,
  ChevronRight,
  RotateCcw,
  ShieldAlert,
  Search,
  Filter,
  Layers,
  Copy,
  Check,
  Zap,
} from "lucide-react";
import { apiFetch } from "@/lib/api";

interface Lead {
  id: string;
  nom_empresa: string;
  nom_contacte: string;
  email: string;
  telefon?: string | null;
  vertical: string;
  origen: string;
  estat_qualificacio: string;
  operaris_estimats: number;
  notes?: string | null;
  empresa_demo_id?: string | null;
  data_inici_demo?: string | null;
  data_fi_demo?: string | null;
  dies_demo_durada: number;
  dies_restants_demo?: number | null;
  demo_activa: boolean;
  created_at: string;
}

interface Oportunitat {
  id: string;
  lead_id: string;
  nom_empresa: string;
  nom_contacte: string;
  email: string;
  telefon?: string | null;
  vertical: string;
  titol: string;
  etapa: string;
  valor_mensual_estimat: number;
  valor_ia_setup: number;
  probabilitat_percent: number;
  data_tancament_prevista?: string | null;
  dies_restants_demo?: number | null;
  demo_activa: boolean;
  created_at: string;
}

interface PipelineData {
  etapes: string[];
  totals_mrr: Record<string, number>;
  columnes: Record<string, Oportunitat[]>;
}

const ETAPA_LABELS: Record<string, { label: string; desc: string; color: string }> = {
  PROSPECCIO: { label: "1. Prospecció", desc: "Primer contacte", color: "bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-200" },
  QUALIFICACIO: { label: "2. Qualificació", desc: "Avaluació necessitats", color: "bg-blue-50 text-blue-800 dark:bg-blue-950/60 dark:text-blue-300" },
  DEMO_7_DIES: { label: "3. Demo 7 Dies", desc: "Prova pilot en curs", color: "bg-amber-50 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300" },
  PROPOSTA: { label: "4. Proposta", desc: "Pressupost enviat", color: "bg-purple-50 text-purple-800 dark:bg-purple-950/60 dark:text-purple-300" },
  NEGOCIACIO: { label: "5. Negociació", desc: "Tancant acord", color: "bg-indigo-50 text-indigo-800 dark:bg-indigo-950/60 dark:text-indigo-300" },
  GUANYAT: { label: "6. Guanyat 🎉", desc: "Llest per Onboarding", color: "bg-emerald-50 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300" },
  PERDUT: { label: "Perdut", desc: "Descartat o no tancat", color: "bg-rose-50 text-rose-800 dark:bg-rose-950/60 dark:text-rose-300" },
};

const VERTICAL_COLORS: Record<string, string> = {
  CampoPro: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/50 dark:text-emerald-300 border-emerald-300",
  ElectricPro: "bg-blue-100 text-blue-800 dark:bg-blue-900/50 dark:text-blue-300 border-blue-300",
  HydroPro: "bg-cyan-100 text-cyan-800 dark:bg-cyan-900/50 dark:text-cyan-300 border-cyan-300",
  BuildingPro: "bg-amber-100 text-amber-800 dark:bg-amber-900/50 dark:text-amber-300 border-amber-300",
};

export default function SuperadminCrmPage() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<"pipeline" | "leads" | "factures" | "tiquets">("pipeline");
  const [loading, setLoading] = useState(true);
  const [pipeline, setPipeline] = useState<PipelineData | null>(null);
  const [leads, setLeads] = useState<Lead[]>([]);
  const [searchTerm, setSearchTerm] = useState("");
  const [filtreVertical, setFiltreVertical] = useState("");

  // Modals
  const [showNouLeadModal, setShowNouLeadModal] = useState(false);
  const [selectedLeadId, setSelectedLeadId] = useState<string | null>(null);
  const [leadDetall, setLeadDetall] = useState<any | null>(null);
  const [loadingDetall, setLoadingDetall] = useState(false);

  // Formulari Nou Lead
  const [nouLead, setNouLead] = useState({
    nom_empresa: "",
    nom_contacte: "",
    email: "",
    telefon: "",
    vertical: "CampoPro",
    origen: "WEB",
    operaris_estimats: 5,
    valor_mensual_estimat: 75.0,
    notes: "",
  });

  // Modal Activar Demo
  const [demoActivarModal, setDemoActivarModal] = useState(false);
  const [demoVertical, setDemoVertical] = useState("CampoPro");
  const [demoDies, setDemoDies] = useState(7);
  const [activantDemo, setActivantDemo] = useState(false);
  const [demoResult, setDemoResult] = useState<any | null>(null);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  // Nova Activitat
  const [novaNota, setNovaNota] = useState("");
  const [tipusNota, setTipusNota] = useState("NOTA");
  const [afegintNota, setAfegintNota] = useState(false);

  // Carregar dades
  const carregarDades = async () => {
    setLoading(true);
    try {
      const [pipRes, leadsRes] = await Promise.all([
        apiFetch<PipelineData>("/superadmin/crm/prospeccio/pipeline"),
        apiFetch<Lead[]>("/superadmin/crm/prospeccio/leads"),
      ]);
      setPipeline(pipRes);
      setLeads(leadsRes);
    } catch (err) {
      console.error("Error carregant CRM:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    carregarDades();
  }, []);

  const obrirDetallLead = async (id: string) => {
    setSelectedLeadId(id);
    setLoadingDetall(true);
    try {
      const res = await apiFetch<any>(`/superadmin/crm/prospeccio/leads/${id}`);
      setLeadDetall(res);
      setDemoVertical(res.vertical || "CampoPro");
    } catch (e) {
      console.error("Error obrint detall lead:", e);
    } finally {
      setLoadingDetall(false);
    }
  };

  const handleCrearLead = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await apiFetch("/superadmin/crm/prospeccio/leads", {
        method: "POST",
        body: JSON.stringify({
          ...nouLead,
          operaris_estimats: Number(nouLead.operaris_estimats),
          valor_mensual_estimat: Number(nouLead.valor_mensual_estimat),
        }),
      });
      setShowNouLeadModal(false);
      setNouLead({
        nom_empresa: "",
        nom_contacte: "",
        email: "",
        telefon: "",
        vertical: "CampoPro",
        origen: "WEB",
        operaris_estimats: 5,
        valor_mensual_estimat: 75.0,
        notes: "",
      });
      carregarDades();
    } catch (err: any) {
      alert("Error creant lead: " + (err.message || err));
    }
  };

  const handleMoureEtapa = async (oportunitatId: string, novaEtapa: string) => {
    try {
      await apiFetch(`/superadmin/crm/prospeccio/oportunitats/${oportunitatId}/etapa`, {
        method: "PATCH",
        body: JSON.stringify({ etapa: novaEtapa }),
      });
      carregarDades();
    } catch (err) {
      console.error("Error movent etapa:", err);
    }
  };

  const handleActivarDemo = async () => {
    if (!selectedLeadId) return;
    setActivantDemo(true);
    try {
      const res = await apiFetch<any>(`/superadmin/crm/prospeccio/leads/${selectedLeadId}/activar-demo`, {
        method: "POST",
        body: JSON.stringify({
          vertical: demoVertical,
          durada_dies: Number(demoDies),
          recrear: false,
        }),
      });
      setDemoResult(res);
      carregarDades();
      if (selectedLeadId) obrirDetallLead(selectedLeadId);
    } catch (err: any) {
      alert("Error activant demo: " + (err.message || err));
    } finally {
      setActivantDemo(false);
    }
  };

  const handleAfegirNota = async () => {
    if (!selectedLeadId || !novaNota.trim()) return;
    setAfegintNota(true);
    try {
      await apiFetch(`/superadmin/crm/prospeccio/leads/${selectedLeadId}/activitats`, {
        method: "POST",
        body: JSON.stringify({
          tipus: tipusNota,
          titol: novaNota.slice(0, 50),
          descripcio: novaNota,
        }),
      });
      setNovaNota("");
      obrirDetallLead(selectedLeadId);
    } catch (err: any) {
      alert("Error afegint nota: " + (err.message || err));
    } finally {
      setAfegintNota(false);
    }
  };

  const copiarPortapapers = (text: string, key: string) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(null), 2000);
  };

  // Càlcul de mètriques ràpides
  const totalLeads = leads.length;
  const totalDemosActives = leads.filter((l) => l.demo_activa).length;
  const totalMrrPipeline = pipeline
    ? Object.values(pipeline.totals_mrr).reduce((acc, v) => acc + v, 0)
    : 0;

  const leadsFiltrats = leads.filter((l) => {
    const matchQ =
      !searchTerm ||
      l.nom_empresa.toLowerCase().includes(searchTerm.toLowerCase()) ||
      l.nom_contacte.toLowerCase().includes(searchTerm.toLowerCase()) ||
      l.email.toLowerCase().includes(searchTerm.toLowerCase());
    const matchVert = !filtreVertical || l.vertical === filtreVertical;
    return matchQ && matchVert;
  });

  return (
    <div className="flex-1 p-6 space-y-6 overflow-y-auto bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 font-sans">
      {/* HEADER AMB MÈTRIQUES RÀPIDES */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-200 dark:border-slate-800">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-indigo-600 text-white shadow-md">
              <Target className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-white">
                CRM Comercial & Pipeline Sevalor
              </h1>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Gestió de prospectes (Leads), Pipeline Kanban d'Oportunitats i Demos reals de 7 dies
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowNouLeadModal(true)}
            className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold flex items-center gap-2 shadow-sm transition-all"
          >
            <Plus className="w-4 h-4" />
            <span>Nou Prospecte (Lead)</span>
          </button>
        </div>
      </div>

      {/* KPI STATS CARDS */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm">
          <div className="text-xs font-medium text-slate-500 dark:text-slate-400 flex items-center justify-between">
            <span>Prospectes Actius</span>
            <Users className="w-4 h-4 text-indigo-500" />
          </div>
          <div className="text-2xl font-bold text-slate-900 dark:text-white mt-1">{totalLeads}</div>
          <div className="text-[11px] text-slate-400 mt-1">Leads registrats al sistema</div>
        </div>

        <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-amber-200 dark:border-amber-900/60 bg-amber-50/20 shadow-sm">
          <div className="text-xs font-medium text-amber-700 dark:text-amber-400 flex items-center justify-between">
            <span>Demos en Curs (7 Dies)</span>
            <Play className="w-4 h-4 text-amber-500" />
          </div>
          <div className="text-2xl font-bold text-amber-900 dark:text-amber-200 mt-1">{totalDemosActives}</div>
          <div className="text-[11px] text-amber-600/80 mt-1">Tenants efímers amb IA central</div>
        </div>

        <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm">
          <div className="text-xs font-medium text-slate-500 dark:text-slate-400 flex items-center justify-between">
            <span>Valor Pipeline (MRR)</span>
            <TrendingUp className="w-4 h-4 text-emerald-500" />
          </div>
          <div className="text-2xl font-bold text-slate-900 dark:text-white mt-1">
            {totalMrrPipeline.toLocaleString("ca-ES", { minimumFractionDigits: 0 })} €/mes
          </div>
          <div className="text-[11px] text-slate-400 mt-1">Volum estimat en negociació</div>
        </div>

        <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm">
          <div className="text-xs font-medium text-slate-500 dark:text-slate-400 flex items-center justify-between">
            <span>Urgència Comercial</span>
            <Clock className="w-4 h-4 text-blue-500" />
          </div>
          <div className="text-2xl font-bold text-blue-600 dark:text-blue-400 mt-1">7 Dies</div>
          <div className="text-[11px] text-slate-400 mt-1">Durada límit estàndard de Demo</div>
        </div>
      </div>

      {/* PESTANYES DE NAVEGACIÓ CRM */}
      <div className="flex border-b border-slate-200 dark:border-slate-800 gap-6 text-sm font-semibold">
        <button
          onClick={() => setActiveTab("pipeline")}
          className={`pb-3 flex items-center gap-2 border-b-2 transition-all ${
            activeTab === "pipeline"
              ? "border-indigo-600 text-indigo-600 dark:text-indigo-400"
              : "border-transparent text-slate-500 hover:text-slate-900 dark:hover:text-white"
          }`}
        >
          <Layers className="w-4 h-4" />
          <span>Pipeline Kanban</span>
        </button>

        <button
          onClick={() => setActiveTab("leads")}
          className={`pb-3 flex items-center gap-2 border-b-2 transition-all ${
            activeTab === "leads"
              ? "border-indigo-600 text-indigo-600 dark:text-indigo-400"
              : "border-transparent text-slate-500 hover:text-slate-900 dark:hover:text-white"
          }`}
        >
          <Users className="w-4 h-4" />
          <span>Prospectes / Leads ({leads.length})</span>
        </button>

        <Link
          href="/superadmin/empreses"
          className="pb-3 flex items-center gap-2 border-b-2 border-transparent text-slate-500 hover:text-slate-900 dark:hover:text-white transition-all ml-auto"
        >
          <Building2 className="w-4 h-4" />
          <span>Clients & Facturació Veri*factu</span>
          <ChevronRight className="w-3.5 h-3.5" />
        </Link>
      </div>

      {/* CONTINGUT SEGONS PESTANYA */}
      {loading ? (
        <div className="p-12 text-center text-slate-400 animate-pulse text-sm">Carregant dades del CRM...</div>
      ) : activeTab === "pipeline" ? (
        /* KANBAN PIPELINE (TWENTY CRM STYLE) */
        <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-7 gap-3.5 items-start overflow-x-auto pb-6">
          {pipeline?.etapes.map((etapaKey) => {
            const meta = ETAPA_LABELS[etapaKey] || { label: etapaKey, desc: "", color: "bg-slate-100" };
            const oportunitatsCol = pipeline.columnes[etapaKey] || [];
            const totalColMrr = pipeline.totals_mrr[etapaKey] || 0;

            return (
              <div
                key={etapaKey}
                className="flex flex-col rounded-2xl bg-slate-100/70 dark:bg-slate-900/70 border border-slate-200/80 dark:border-slate-800 p-3 min-w-[240px]"
              >
                {/* Capçalera Columna */}
                <div className="pb-2.5 mb-2.5 border-b border-slate-200 dark:border-slate-800">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-slate-800 dark:text-slate-200">{meta.label}</span>
                    <span className="text-[11px] font-mono px-1.5 py-0.5 rounded-full bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-400 font-semibold">
                      {oportunitatsCol.length}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-[11px] text-slate-500 mt-1">
                    <span>{meta.desc}</span>
                    <span className="font-semibold text-slate-700 dark:text-slate-300">
                      {totalColMrr > 0 ? `${totalColMrr} €/m` : "—"}
                    </span>
                  </div>
                </div>

                {/* Targetes del Kanban */}
                <div className="space-y-2.5 flex-1 min-h-[300px]">
                  {oportunitatsCol.length === 0 ? (
                    <div className="text-center py-8 text-[11px] text-slate-400 border border-dashed border-slate-200 dark:border-slate-800 rounded-xl">
                      Buit
                    </div>
                  ) : (
                    oportunitatsCol.map((op) => (
                      <div
                        key={op.id}
                        onClick={() => obrirDetallLead(op.lead_id)}
                        className="p-3 rounded-xl bg-white dark:bg-slate-800/90 border border-slate-200 dark:border-slate-700 hover:border-indigo-400 dark:hover:border-indigo-500 shadow-sm cursor-pointer transition-all hover:shadow space-y-2 group"
                      >
                        <div className="flex items-start justify-between gap-1.5">
                          <h4 className="text-xs font-bold text-slate-900 dark:text-white line-clamp-1 group-hover:text-indigo-600 dark:group-hover:text-indigo-400">
                            {op.nom_empresa}
                          </h4>
                          <span
                            className={`text-[9px] px-1.5 py-0.5 rounded font-mono font-semibold border ${
                              VERTICAL_COLORS[op.vertical] || "bg-slate-100 text-slate-700 border-slate-200"
                            }`}
                          >
                            {op.vertical}
                          </span>
                        </div>

                        <div className="text-[11px] text-slate-500 dark:text-slate-400 flex items-center gap-1.5">
                          <User className="w-3 h-3 text-slate-400" />
                          <span className="truncate">{op.nom_contacte}</span>
                        </div>

                        {/* Indicador de Demo de 7 dies si està en curs */}
                        {op.demo_activa && (
                          <div className="flex items-center gap-1.5 px-2 py-1 rounded-lg bg-amber-50 dark:bg-amber-950/50 border border-amber-200 dark:border-amber-800/60 text-[10px] text-amber-800 dark:text-amber-300 font-mono font-semibold">
                            <Clock className="w-3 h-3 text-amber-600 shrink-0" />
                            <span>Queden {op.dies_restants_demo}d de demo (7D)</span>
                          </div>
                        )}

                        <div className="flex items-center justify-between pt-1 border-t border-slate-100 dark:border-slate-700/60 text-[11px]">
                          <span className="font-bold text-slate-900 dark:text-slate-100 font-mono">
                            {op.valor_mensual_estimat} €/m
                          </span>

                          {/* Controls ràpids per moure d'etapa */}
                          <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                            {etapaKey !== "GUANYAT" && (
                              <button
                                title="Passar a la següent etapa"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  const idx = pipeline.etapes.indexOf(etapaKey);
                                  if (idx < pipeline.etapes.length - 1) {
                                    handleMoureEtapa(op.id, pipeline.etapes[idx + 1]);
                                  }
                                }}
                                className="p-1 rounded hover:bg-slate-100 dark:hover:bg-slate-700 text-slate-500 hover:text-indigo-600"
                              >
                                <ArrowRight className="w-3 h-3" />
                              </button>
                            )}
                          </div>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        /* TAULA DE PROSPECTES / LEADS */
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-3">
            <div className="relative flex-1 w-full sm:max-w-xs">
              <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-400" />
              <input
                type="text"
                placeholder="Cercar per empresa, contacte, email..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-9 pr-3 py-1.5 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            <div className="flex items-center gap-2 w-full sm:w-auto">
              <select
                value={filtreVertical}
                onChange={(e) => setFiltreVertical(e.target.value)}
                className="px-3 py-1.5 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-300"
              >
                <option value="">Totes les Verticals (Obertes)</option>
                <option value="CampoPro">CampoPro (Reg & Agrícola)</option>
                <option value="ElectricPro">ElectricPro (Baixa Tensió)</option>
                <option value="HydroPro">HydroPro (Fontaneria)</option>
                <option value="BuildingPro">BuildingPro (Edificació)</option>
              </select>
            </div>
          </div>

          <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 overflow-hidden shadow-sm">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 dark:bg-slate-800/60 text-slate-500 dark:text-slate-400 font-semibold border-b border-slate-200 dark:border-slate-800">
                <tr>
                  <th className="py-3 px-4">Empresa</th>
                  <th className="py-3 px-4">Contacte / Decisor</th>
                  <th className="py-3 px-4">Vertical</th>
                  <th className="py-3 px-4">Operaris</th>
                  <th className="py-3 px-4">Estat Qualificació</th>
                  <th className="py-3 px-4">Demo 7 Dies</th>
                  <th className="py-3 px-4 text-right">Accions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {leadsFiltrats.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="text-center py-8 text-slate-400">
                      Cap prospecte trobat.
                    </td>
                  </tr>
                ) : (
                  leadsFiltrats.map((l) => (
                    <tr
                      key={l.id}
                      onClick={() => obrirDetallLead(l.id)}
                      className="hover:bg-slate-50 dark:hover:bg-slate-800/40 cursor-pointer transition-colors"
                    >
                      <td className="py-3 px-4 font-bold text-slate-900 dark:text-white">{l.nom_empresa}</td>
                      <td className="py-3 px-4">
                        <div className="font-medium text-slate-800 dark:text-slate-200">{l.nom_contacte}</div>
                        <div className="text-[11px] text-slate-400">{l.email}</div>
                      </td>
                      <td className="py-3 px-4">
                        <span
                          className={`text-[10px] px-2 py-0.5 rounded font-mono font-semibold border ${
                            VERTICAL_COLORS[l.vertical] || "bg-slate-100 text-slate-700 border-slate-200"
                          }`}
                        >
                          {l.vertical}
                        </span>
                      </td>
                      <td className="py-3 px-4 font-mono">{l.operaris_estimats} ops</td>
                      <td className="py-3 px-4">
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                          {l.estat_qualificacio}
                        </span>
                      </td>
                      <td className="py-3 px-4">
                        {l.demo_activa ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-amber-50 dark:bg-amber-950/60 border border-amber-300 text-amber-800 dark:text-amber-300 font-mono text-[10px] font-bold">
                            <Clock className="w-3 h-3 text-amber-600" />
                            <span>Queden {l.dies_restants_demo} dies</span>
                          </span>
                        ) : l.empresa_demo_id ? (
                          <span className="text-[10px] text-slate-400">Expirada</span>
                        ) : (
                          <span className="text-[10px] text-slate-400">Sense demo</span>
                        )}
                      </td>
                      <td className="py-3 px-4 text-right" onClick={(e) => e.stopPropagation()}>
                        <button
                          onClick={() => obrirDetallLead(l.id)}
                          className="px-2.5 py-1 rounded-lg bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 text-xs font-semibold"
                        >
                          Veure Fitxa
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* MODAL DETALL LEAD & GESTIÓ DEMO 7 DIES */}
      {selectedLeadId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in">
          <div className="w-full max-w-4xl max-h-[90vh] bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-2xl flex flex-col overflow-hidden">
            {/* Modal Header */}
            <div className="p-6 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between bg-slate-50/50 dark:bg-slate-800/30">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-xl bg-indigo-100 dark:bg-indigo-950 text-indigo-600 dark:text-indigo-400">
                  <Building2 className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-slate-900 dark:text-white">
                    {leadDetall?.nom_empresa || "Fitxa del Prospecte"}
                  </h3>
                  <div className="flex items-center gap-2 text-xs text-slate-500 mt-0.5">
                    <span>Contacte: {leadDetall?.nom_contacte}</span>
                    <span>•</span>
                    <span>{leadDetall?.email}</span>
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={() => setSelectedLeadId(null)}
                  className="p-1.5 rounded-xl hover:bg-slate-200 dark:hover:bg-slate-800 text-slate-500"
                >
                  ✕
                </button>
              </div>
            </div>

            {/* Modal Body */}
            <div className="p-6 overflow-y-auto flex-1 space-y-6">
              {loadingDetall ? (
                <div className="text-center py-12 text-slate-400 animate-pulse text-xs">Carregant fitxa completa...</div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                  {/* Columna Esquerra: Dades del Lead & Selector Vertical */}
                  <div className="space-y-4">
                    <div className="p-4 rounded-2xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800 space-y-3">
                      <h4 className="text-xs font-bold text-slate-900 dark:text-white uppercase tracking-wider">
                        Dades de Qualificació
                      </h4>

                      <div>
                        <label className="text-[11px] text-slate-500">Vertical (Configurable / Oberta)</label>
                        <select
                          value={demoVertical}
                          onChange={(e) => setDemoVertical(e.target.value)}
                          className="w-full mt-1 px-3 py-1.5 text-xs rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 font-semibold text-slate-900 dark:text-white"
                        >
                          <option value="CampoPro">CampoPro (Reg & Agrícola)</option>
                          <option value="ElectricPro">ElectricPro (Baixa Tensió)</option>
                          <option value="HydroPro">HydroPro (Fontaneria)</option>
                          <option value="BuildingPro">BuildingPro (Edificació)</option>
                        </select>
                      </div>

                      <div>
                        <label className="text-[11px] text-slate-500">Operaris Estimats</label>
                        <div className="text-xs font-bold font-mono mt-0.5 text-slate-900 dark:text-white">
                          {leadDetall?.operaris_estimats} operaris de camp
                        </div>
                      </div>

                      <div>
                        <label className="text-[11px] text-slate-500">Telèfon</label>
                        <div className="text-xs font-mono mt-0.5 text-slate-900 dark:text-white">
                          {leadDetall?.telefon || "No indicat"}
                        </div>
                      </div>

                      <div>
                        <label className="text-[11px] text-slate-500">Origen Comercial</label>
                        <div className="text-xs font-semibold mt-0.5 text-slate-700 dark:text-slate-300">
                          {leadDetall?.origen}
                        </div>
                      </div>
                    </div>

                    {/* BOTÓ DE CONVERSIÓ DIRECTA A ONBOARDING */}
                    <div className="p-4 rounded-2xl bg-indigo-50 dark:bg-indigo-950/40 border border-indigo-200 dark:border-indigo-900/60 space-y-2">
                      <div className="text-xs font-bold text-indigo-900 dark:text-indigo-200 flex items-center gap-1.5">
                        <CheckCircle2 className="w-4 h-4 text-indigo-600" />
                        <span>Convertir en Client Definitiu</span>
                      </div>
                      <p className="text-[11px] text-indigo-700 dark:text-indigo-300">
                        Passa directament a l'Onboarding amb totes les dades pre-emplenades.
                      </p>
                      <Link
                        href={`/superadmin/tenants/onboarding?nom=${encodeURIComponent(
                          leadDetall?.nom_empresa || ""
                        )}&contacte=${encodeURIComponent(leadDetall?.nom_contacte || "")}&email=${encodeURIComponent(
                          leadDetall?.email || ""
                        )}&vertical=${encodeURIComponent(demoVertical)}`}
                        className="w-full mt-2 py-2 px-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold flex items-center justify-center gap-1.5 shadow-sm transition-colors"
                      >
                        <span>Obrir Wizard Onboarding</span>
                        <ArrowRight className="w-3.5 h-3.5" />
                      </Link>
                    </div>
                  </div>

                  {/* Columna Central: Motor Demo 7 Dies */}
                  <div className="space-y-4 md:col-span-2">
                    <div className="p-5 rounded-2xl border bg-white dark:bg-slate-800/60 border-slate-200 dark:border-slate-700 shadow-sm space-y-4">
                      <div className="flex items-center justify-between pb-3 border-b border-slate-100 dark:border-slate-700">
                        <div className="flex items-center gap-2">
                          <Zap className="w-5 h-5 text-amber-500" />
                          <h4 className="text-sm font-bold text-slate-900 dark:text-white">
                            Demo Real de 7 Dies (Aïllada)
                          </h4>
                        </div>
                        {leadDetall?.demo?.demo_activa && (
                          <span className="px-2.5 py-0.5 rounded-full bg-amber-100 dark:bg-amber-950 text-amber-800 dark:text-amber-300 font-mono text-xs font-bold border border-amber-300">
                            Queden {leadDetall.demo.dies_restants} dies
                          </span>
                        )}
                      </div>

                      {leadDetall?.demo?.demo_activa ? (
                        /* DEMO JA ACTIVA: MOSTRAR ACCÉS I CREDENCIALS */
                        <div className="space-y-4">
                          <div className="p-3.5 rounded-xl bg-emerald-50 dark:bg-emerald-950/50 border border-emerald-300 text-emerald-900 dark:text-emerald-200 text-xs">
                            <div className="font-bold flex items-center gap-1.5">
                              <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                              <span>Demo activa connectada a la IA central de Sevalor</span>
                            </div>
                            <p className="mt-1 text-[11px] text-emerald-800/90 dark:text-emerald-300/80">
                              Subdomini aïllat a PostgreSQL RLS: <strong>{leadDetall.demo.subdomini}.sevalor.app</strong>.
                              Caduca el: {new Date(leadDetall.demo.data_fi).toLocaleDateString("ca-ES")}.
                            </p>
                          </div>

                          {/* Caixa de credencials llestes per enviar al client */}
                          <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 space-y-2.5 text-xs font-mono">
                            <div className="text-[11px] font-bold text-slate-600 dark:text-slate-400 uppercase">
                              Credencials de Prova per al Client:
                            </div>

                            <div className="flex items-center justify-between bg-white dark:bg-slate-800 p-2 rounded-lg border border-slate-200 dark:border-slate-700">
                              <div>
                                <span className="text-slate-400">Usuari Oficina: </span>
                                <strong>{leadDetall.email}</strong>
                              </div>
                              <button
                                onClick={() => copiarPortapapers(leadDetall.email, "user")}
                                className="text-slate-400 hover:text-slate-700"
                              >
                                {copiedKey === "user" ? <Check className="w-3.5 h-3.5 text-emerald-500" /> : <Copy className="w-3.5 h-3.5" />}
                              </button>
                            </div>

                            <div className="flex items-center justify-between bg-white dark:bg-slate-800 p-2 rounded-lg border border-slate-200 dark:border-slate-700">
                              <div>
                                <span className="text-slate-400">Password / PIN Boss: </span>
                                <strong>Password123! / 0000</strong>
                              </div>
                              <button
                                onClick={() => copiarPortapapers("Password123!", "pwd")}
                                className="text-slate-400 hover:text-slate-700"
                              >
                                {copiedKey === "pwd" ? <Check className="w-3.5 h-3.5 text-emerald-500" /> : <Copy className="w-3.5 h-3.5" />}
                              </button>
                            </div>

                            <div className="flex items-center justify-between bg-white dark:bg-slate-800 p-2 rounded-lg border border-slate-200 dark:border-slate-700">
                              <div>
                                <span className="text-slate-400">PINs Operaris PWA Mòbil: </span>
                                <strong className="text-indigo-600 dark:text-indigo-400">1111 (Marc) / 2222 (Jordi)</strong>
                              </div>
                            </div>
                          </div>

                          <div className="flex items-center gap-2 pt-2">
                            <button
                              onClick={handleActivarDemo}
                              disabled={activantDemo}
                              className="px-3.5 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 dark:bg-slate-700 text-slate-800 dark:text-slate-200 text-xs font-semibold flex items-center gap-1.5 transition-colors"
                            >
                              <RotateCcw className="w-3.5 h-3.5" />
                              <span>Prorrogar 7 dies més</span>
                            </button>
                          </div>
                        </div>
                      ) : (
                        /* BOTÓ PER ACTIVAR LA DEMO DE 7 DIES */
                        <div className="space-y-4">
                          <p className="text-xs text-slate-600 dark:text-slate-300">
                            Aquesta acció crearà automàticament un tenant aïllat a PostgreSQL amb dades reals de prova
                            de la vertical <strong>{demoVertical}</strong>, connectat a la IA central de demos i amb
                            durada màxima de <strong>7 dies</strong>.
                          </p>

                          <div className="flex items-center gap-3">
                            <div>
                              <label className="text-[11px] text-slate-500">Durada de prova</label>
                              <select
                                value={demoDies}
                                onChange={(e) => setDemoDies(Number(e.target.value))}
                                className="mt-1 px-3 py-1.5 text-xs rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 font-semibold"
                              >
                                <option value={7}>7 Dies (Recomanat - Urgència Comercial)</option>
                                <option value={3}>3 Dies (Demo Ràpida)</option>
                                <option value={14}>14 Dies (Excepcional)</option>
                              </select>
                            </div>
                          </div>

                          <button
                            onClick={handleActivarDemo}
                            disabled={activantDemo}
                            className="w-full py-3 px-4 rounded-xl bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold text-xs flex items-center justify-center gap-2 shadow-md transition-all"
                          >
                            <Play className="w-4 h-4 fill-current" />
                            <span>{activantDemo ? "Generant Tenant i dades..." : "🚀 Activar Demo Real (7 Dies)"}</span>
                          </button>
                        </div>
                      )}
                    </div>

                    {/* TIMELINE D'ACTIVITATS I NOTES (TWENTY CRM STYLE) */}
                    <div className="p-5 rounded-2xl border bg-white dark:bg-slate-800/60 border-slate-200 dark:border-slate-700 shadow-sm space-y-4">
                      <h4 className="text-xs font-bold text-slate-900 dark:text-white uppercase tracking-wider flex items-center gap-1.5">
                        <MessageSquare className="w-4 h-4 text-indigo-500" />
                        <span>Timeline d'Interaccions & Notes Comercials</span>
                      </h4>

                      {/* Formulari d'afegir nota */}
                      <div className="flex gap-2">
                        <input
                          type="text"
                          placeholder="Escriu una nota de trucada, reunió o acord..."
                          value={novaNota}
                          onChange={(e) => setNovaNota(e.target.value)}
                          onKeyDown={(e) => e.key === "Enter" && handleAfegirNota()}
                          className="flex-1 px-3 py-1.5 text-xs rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                        />
                        <button
                          onClick={handleAfegirNota}
                          disabled={afegintNota || !novaNota.trim()}
                          className="px-3 py-1.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-semibold shadow-sm"
                        >
                          Afegir
                        </button>
                      </div>

                      {/* Llista d'activitats */}
                      <div className="space-y-3 pt-2 max-h-60 overflow-y-auto">
                        {leadDetall?.activitats?.length === 0 ? (
                          <div className="text-center py-4 text-xs text-slate-400">Cap nota registrada encara.</div>
                        ) : (
                          leadDetall?.activitats?.map((act: any) => (
                            <div
                              key={act.id}
                              className="p-3 rounded-xl bg-slate-50 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800 text-xs space-y-1"
                            >
                              <div className="flex items-center justify-between">
                                <span className="font-bold text-slate-900 dark:text-white">{act.titol}</span>
                                <span className="text-[10px] text-slate-400">
                                  {new Date(act.created_at).toLocaleDateString("ca-ES", {
                                    day: "2-digit",
                                    month: "2-digit",
                                    hour: "2-digit",
                                    minute: "2-digit",
                                  })}
                                </span>
                              </div>
                              {act.descripcio && <p className="text-slate-600 dark:text-slate-300 text-[11px]">{act.descripcio}</p>}
                            </div>
                          ))
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* MODAL NOU PROSPECTE (LEAD) */}
      {showNouLeadModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in">
          <div className="w-full max-w-lg bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-2xl overflow-hidden">
            <div className="p-6 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between bg-slate-50/50 dark:bg-slate-800/30">
              <h3 className="text-base font-bold text-slate-900 dark:text-white flex items-center gap-2">
                <Plus className="w-5 h-5 text-indigo-600" />
                <span>Registrar Nou Prospecte (Lead)</span>
              </h3>
              <button onClick={() => setShowNouLeadModal(false)} className="text-slate-400 hover:text-slate-600">
                ✕
              </button>
            </div>

            <form onSubmit={handleCrearLead} className="p-6 space-y-4">
              <div>
                <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">Nom de l'Empresa *</label>
                <input
                  type="text"
                  required
                  placeholder="ex: Regs i Serveis del Segrià SL"
                  value={nouLead.nom_empresa}
                  onChange={(e) => setNouLead({ ...nouLead, nom_empresa: e.target.value })}
                  className="w-full mt-1 px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">Nom de Contacte *</label>
                  <input
                    type="text"
                    required
                    placeholder="ex: Jordi Soler"
                    value={nouLead.nom_contacte}
                    onChange={(e) => setNouLead({ ...nouLead, nom_contacte: e.target.value })}
                    className="w-full mt-1 px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800"
                  />
                </div>
                <div>
                  <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">Email *</label>
                  <input
                    type="email"
                    required
                    placeholder="jordi@empresa.cat"
                    value={nouLead.email}
                    onChange={(e) => setNouLead({ ...nouLead, email: e.target.value })}
                    className="w-full mt-1 px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">Telèfon</label>
                  <input
                    type="tel"
                    placeholder="600123456"
                    value={nouLead.telefon}
                    onChange={(e) => setNouLead({ ...nouLead, telefon: e.target.value })}
                    className="w-full mt-1 px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800"
                  />
                </div>
                <div>
                  <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">Vertical (Oberta)</label>
                  <select
                    value={nouLead.vertical}
                    onChange={(e) => setNouLead({ ...nouLead, vertical: e.target.value })}
                    className="w-full mt-1 px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 font-semibold"
                  >
                    <option value="CampoPro">CampoPro (Reg & Agrícola)</option>
                    <option value="ElectricPro">ElectricPro (Baixa Tensió)</option>
                    <option value="HydroPro">HydroPro (Fontaneria)</option>
                    <option value="BuildingPro">BuildingPro (Edificació)</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">Operaris de Camp</label>
                  <input
                    type="number"
                    min={1}
                    max={100}
                    value={nouLead.operaris_estimats}
                    onChange={(e) => setNouLead({ ...nouLead, operaris_estimats: Number(e.target.value) })}
                    className="w-full mt-1 px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 font-mono"
                  />
                </div>
                <div>
                  <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">Valor Estimat (€/mes)</label>
                  <input
                    type="number"
                    min={0}
                    value={nouLead.valor_mensual_estimat}
                    onChange={(e) => setNouLead({ ...nouLead, valor_mensual_estimat: Number(e.target.value) })}
                    className="w-full mt-1 px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 font-mono"
                  />
                </div>
              </div>

              <div className="pt-4 flex items-center justify-end gap-2 border-t border-slate-100 dark:border-slate-800">
                <button
                  type="button"
                  onClick={() => setShowNouLeadModal(false)}
                  className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-500 hover:text-slate-700"
                >
                  Cancel·lar
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold shadow-sm"
                >
                  Registrar Prospecte
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
