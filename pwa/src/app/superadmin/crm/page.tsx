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
  Compass,
  Send,
  Edit,
  RefreshCw,
  Globe,
  Share2,
  CheckSquare,
  XCircle,
  Award,
  Sliders,
  CalendarClock,
  ArrowUpRight,
  MapPin,
  Briefcase,
  Instagram,
  Linkedin,
  Trash2,
} from "lucide-react";
import { apiFetch, getApiBaseUrl, getAuthToken } from "@/lib/api";

// ==========================================
// INTERFÍCIES DE DADES (ZERO MOCK)
// ==========================================

interface Lead {
  id: string;
  nom_empresa: string;
  nom_contacte: string;
  carrec_contacte?: string | null;
  email: string;
  telefon?: string | null;
  cif?: string | null;
  web_url?: string | null;
  domini_normalitzat?: string | null;
  adreca_fisica?: string | null;
  codi_postal?: string | null;
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
  score_qualificacio?: number;
  rao_tancament_exit?: string | null;
  es_tancament_replicable?: boolean;
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
  rao_tancament_exit?: string | null;
  requisits_replicables?: string | null;
  es_replicable?: boolean;
  created_at: string;
}

interface PipelineData {
  etapes: string[];
  totals_mrr: Record<string, number>;
  columnes: Record<string, Oportunitat[]>;
}

interface CandidatCP {
  id: string;
  nom_empresa: string;
  cif?: string | null;
  web_url?: string | null;
  domini_normalitzat?: string | null;
  adreca_fisica?: string | null;
  codi_postal: string;
  vertical: string;
  fonts_investigades?: string | null;
  fonts_urls?: Record<string, string> | null;
  email_detectat?: string | null;
  telefon_detectat?: string | null;
  mx_validat?: boolean;
  operaris_estimats: number;
  decisor_nom?: string | null;
  decisor_carrec?: string | null;
  fita_recent?: string | null;
  punt_dolor?: string | null;
  angle_atac?: string | null;
  score: number;
  estat_decisio: "SELECCIONAT" | "SELECCIONAT_SENSE_GATEKEEPER" | "DESCARTAT" | "DUPLICAT" | "ERROR_EXTRACCIO";
  cp_geocode_retornat?: string | null;
  cp_geocode_coincideix?: boolean | null;
  gatekeeper_font_url?: string | null;
  gatekeeper_cita?: string | null;
  gatekeeper_confianca?: string | null;
  vector_duplicitat?: "CIF" | "DOMINI_WEB" | "ADRECA_FISICA" | null;
  motiu_detallat_ia?: string | null;
  corregit_huma: boolean;
  decisio_humana?: string | null;
  motiu_correccio_humana?: string | null;
  lead_id?: string | null;
  created_at: string;
}

interface TascaCP {
  id: string;
  codi_postal: string;
  vertical: string;
  operaris_minims: number;
  estat: string;
  total_trobats: number;
  total_seleccionats: number;
  total_descartats: number;
  total_duplicats: number;
  resum_execucio?: string | null;
  created_at: string;
  completed_at?: string | null;
  candidats?: CandidatCP[];
}

interface CalendariItem {
  id: string;
  lead_id: string;
  nom_empresa: string;
  vertical: string;
  nom_contacte: string;
  destinatari: string;
  telefon?: string | null;
  tipus_item_calendari: string;
  pas_sequencia: number;
  tempo_dies_offset: number;
  data_programada: string;
  direccio: string;
  estat_enviament: string;
  estat_calendari: string;
  assumpte: string;
  cos_text: string;
  message_id?: string | null;
  in_reply_to?: string | null;
  intencio_ia?: string | null;
  es_avui: boolean;
  pendent_aprovacio: boolean;
  sent_at?: string | null;
}

interface CalendariResponse {
  total_esdeveniments: number;
  pendents_aprovacio_avui: number;
  items: CalendariItem[];
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

function extreureUrlsFonts(
  fontsRaw?: string | null,
  webUrl?: string | null,
  fontsUrlsObj?: Record<string, string> | null
): Record<string, string> {
  const mapa: Record<string, string> = {};
  if (webUrl && (webUrl.startsWith("http://") || webUrl.startsWith("https://"))) {
    mapa.web = webUrl.trim();
  }
  if (fontsUrlsObj && typeof fontsUrlsObj === "object") {
    for (const [k, v] of Object.entries(fontsUrlsObj)) {
      if (typeof v === "string" && (v.startsWith("http://") || v.startsWith("https://"))) {
        mapa[k.toLowerCase()] = v.trim();
      }
    }
  }
  if (fontsRaw) {
    for (const part of fontsRaw.split(",")) {
      const item = part.trim();
      if (item.includes("|")) {
        const [canal, url] = item.split("|", 2);
        if (url && (url.startsWith("http://") || url.startsWith("https://"))) {
          mapa[canal.trim().toLowerCase()] = url.trim();
        }
      }
    }
  }
  return mapa;
}

export default function SuperadminCrmPage() {
  const router = useRouter();

  // Pestanya Principal
  const [activeTab, setActiveTab] = useState<"pipeline" | "explorador" | "calendari" | "leads">("pipeline");
  const [loading, setLoading] = useState(true);

  // Pipeline & Leads Generals
  const [pipeline, setPipeline] = useState<PipelineData | null>(null);
  const [leads, setLeads] = useState<Lead[]>([]);
  const [searchTerm, setSearchTerm] = useState("");
  const [filtreVertical, setFiltreVertical] = useState("");

  // Formulari Nou Lead Manual
  const [showNouLeadModal, setShowNouLeadModal] = useState(false);
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

  // Fitxa Detall Lead & Demos
  const [selectedLeadId, setSelectedLeadId] = useState<string | null>(null);
  const [leadDetall, setLeadDetall] = useState<any | null>(null);
  const [loadingDetall, setLoadingDetall] = useState(false);
  const [leadCorreus, setLeadCorreus] = useState<any[]>([]);
  const [demoVertical, setDemoVertical] = useState("CampoPro");
  const [demoDies, setDemoDies] = useState(7);
  const [activantDemo, setActivantDemo] = useState(false);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const [novaNota, setNovaNota] = useState("");
  const [tipusNota, setTipusNota] = useState("NOTA");
  const [afegintNota, setAfegintNota] = useState(false);

  // ==========================================
  // ESTATS T014: EXPLORADOR DE LEADS PER CP
  // ==========================================
  const [codiPostalInput, setCodiPostalInput] = useState("25001");
  const [verticalInput, setVerticalInput] = useState("Instal·lacions de reg per degoteig i bombament solar");
  const [operarisMinims, setOperarisMinims] = useState(5);
  const [tasquesCP, setTasquesCP] = useState<TascaCP[]>([]);
  const [tascaSeleccionadaId, setTascaSeleccionadaId] = useState<string | null>(null);
  const [tascaSeleccionada, setTascaSeleccionada] = useState<TascaCP | null>(null);
  const [candidatsCP, setCandidatsCP] = useState<CandidatCP[]>([]);
  const [filtreDecisio, setFiltreDecisio] = useState<
    "TOTS" | "SELECCIONAT" | "SELECCIONAT_SENSE_GATEKEEPER" | "DESCARTAT" | "DUPLICAT" | "ERROR_EXTRACCIO"
  >("TOTS");
  const [executantCerca, setExecutantCerca] = useState(false);
  const [preparacioSeguentCpMsg, setPreparacioSeguentCpMsg] = useState<string | null>(null);
  const [consoleLogs, setConsoleLogs] = useState<Array<{ time: string; text: string; type: "info" | "success" | "warn" | "error" }>>([
    {
      time: new Date().toLocaleTimeString("ca-ES"),
      text: "Consola de Prospecció Atòmica per Codi Postal llesta. Deduplicació 3 vectors (CIF, Domini, Adreça) i Doble Bucle d'Aprenentatge actius.",
      type: "info",
    },
  ]);

  // Modal Corregir Criteri (T014)
  const [modalCorregir, setModalCorregir] = useState<{
    open: boolean;
    candidat: CandidatCP | null;
    novaDecisio: "SELECCIONAT" | "DESCARTAT";
    motiu: string;
  }>({
    open: false,
    candidat: null,
    novaDecisio: "SELECCIONAT",
    motiu: "",
  });
  const [guardantCorreccio, setGuardantCorreccio] = useState(false);

  // ==========================================
  // ESTATS T015: CALENDARI COMERCIAL & CAMPANYES
  // ==========================================
  const [calendariData, setCalendariData] = useState<CalendariResponse | null>(null);
  const [loadingCalendari, setLoadingCalendari] = useState(false);
  const [filtreCalendari, setFiltreCalendari] = useState<"AVUI" | "TOTS" | "CORREUS" | "REUNIONS">("AVUI");
  const [enviantCorreuId, setEnviantCorreuId] = useState<string | null>(null);

  // Modal Editar Esborrany Correu (T015)
  const [modalEditarCorreu, setModalEditarCorreu] = useState<{
    open: boolean;
    item: CalendariItem | null;
    assumpte: string;
    cos: string;
    dataProgramada: string;
  }>({
    open: false,
    item: null,
    assumpte: "",
    cos: "",
    dataProgramada: "",
  });
  const [guardantEsborrany, setGuardantEsborrany] = useState(false);

  // Modal Nou Esdeveniment Manual al Calendari (T015)
  const [modalNouEsdeveniment, setModalNouEsdeveniment] = useState<{
    open: boolean;
    leadId: string;
    tipus: "SEGUIMENT_CALENDARI" | "REUNIO_DEMO" | "NOTA";
    titol: string;
    descripcio: string;
    dataProgramada: string;
  }>({
    open: false,
    leadId: "",
    tipus: "SEGUIMENT_CALENDARI",
    titol: "",
    descripcio: "",
    dataProgramada: new Date(Date.now() + 86400000).toISOString().slice(0, 16),
  });
  const [guardantNouEsdeveniment, setGuardantNouEsdeveniment] = useState(false);

  // ==========================================
  // ESTATS T016: REGISTRAR TANCAMENT D'ÈXIT REPLICABLE (GUANYAT)
  // ==========================================
  const [modalRegistrarExit, setModalRegistrarExit] = useState<{
    open: boolean;
    oportunitat: Oportunitat | null;
    rao: string;
    requisits: string;
    replicable: boolean;
  }>({
    open: false,
    oportunitat: null,
    rao: "",
    requisits: "",
    replicable: true,
  });
  const [guardantExit, setGuardantExit] = useState(false);
  const [feedbackExitCreat, setFeedbackExitCreat] = useState<string | null>(null);

  // ==========================================
  // ESTATS EDICIÓ I ESBORRAT DE LEADS I DEALS (OPORTUNITATS)
  // ==========================================
  const [modalEditarLead, setModalEditarLead] = useState<{
    open: boolean;
    leadId: string;
    nom_empresa: string;
    nom_contacte: string;
    carrec_contacte: string;
    email: string;
    telefon: string;
    cif: string;
    web_url: string;
    adreca_fisica: string;
    codi_postal: string;
    vertical: string;
    operaris_estimats: number;
    estat_qualificacio: string;
    notes: string;
  }>({
    open: false,
    leadId: "",
    nom_empresa: "",
    nom_contacte: "",
    carrec_contacte: "",
    email: "",
    telefon: "",
    cif: "",
    web_url: "",
    adreca_fisica: "",
    codi_postal: "",
    vertical: "CampoPro",
    operaris_estimats: 5,
    estat_qualificacio: "QUALIFICAT",
    notes: "",
  });
  const [guardantEditarLead, setGuardantEditarLead] = useState(false);

  const [modalEditarDeal, setModalEditarDeal] = useState<{
    open: boolean;
    mode: "edit" | "create";
    oportunitatId: string;
    leadId: string;
    nomEmpresa: string;
    titol: string;
    etapa: string;
    valor_mensual_estimat: number;
    valor_ia_setup: number;
    probabilitat_percent: number;
  }>({
    open: false,
    mode: "edit",
    oportunitatId: "",
    leadId: "",
    nomEmpresa: "",
    titol: "",
    etapa: "PROSPECCIO",
    valor_mensual_estimat: 90,
    valor_ia_setup: 150,
    probabilitat_percent: 30,
  });
  const [guardantDeal, setGuardantDeal] = useState(false);

  // ==========================================
  // CARREGAR DADES GENERALS
  // ==========================================
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

  const carregarTasquesCP = async () => {
    try {
      const tasques = await apiFetch<TascaCP[]>("/superadmin/crm/prospeccio/tasques-cp");
      setTasquesCP(tasques);
      if (tasques.length > 0 && !tascaSeleccionadaId) {
        setTascaSeleccionadaId(tasques[0].id);
        carregarDetallTascaCP(tasques[0].id);
      }
    } catch (e) {
      console.error("Error carregant tasques CP:", e);
    }
  };

  const carregarDetallTascaCP = async (tascaId: string) => {
    try {
      const detall = await apiFetch<TascaCP>(`/superadmin/crm/prospeccio/tasques-cp/${tascaId}`);
      setTascaSeleccionada(detall);
      setCandidatsCP(detall.candidats || []);
    } catch (e) {
      console.error("Error carregant detall tasca CP:", e);
    }
  };

  const carregarCalendari = async () => {
    setLoadingCalendari(true);
    try {
      const res = await apiFetch<CalendariResponse>("/superadmin/crm/prospeccio/calendari");
      setCalendariData(res);
    } catch (e) {
      console.error("Error carregant calendari:", e);
    } finally {
      setLoadingCalendari(false);
    }
  };

  useEffect(() => {
    carregarDades();
    carregarTasquesCP();
    carregarCalendari();
  }, []);

  useEffect(() => {
    if (activeTab === "calendari") {
      carregarCalendari();
    } else if (activeTab === "explorador") {
      carregarTasquesCP();
    }
  }, [activeTab]);

  // ==========================================
  // FITXA LEAD & CORREUS
  // ==========================================
  const obrirDetallLead = async (id: string) => {
    setSelectedLeadId(id);
    setLoadingDetall(true);
    try {
      const [resLead, resCorreus] = await Promise.all([
        apiFetch<any>(`/superadmin/crm/prospeccio/leads/${id}`),
        apiFetch<any[]>(`/superadmin/crm/prospeccio/leads/${id}/correus`).catch(() => []),
      ]);
      setLeadDetall(resLead);
      setLeadCorreus(resCorreus);
      setDemoVertical(resLead.vertical || "CampoPro");
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
    // Si la nova etapa és GUANYAT, obrir obligatòriament el modal de registre d'èxit replicable (T016)
    if (novaEtapa === "GUANYAT") {
      const op = pipeline ? Object.values(pipeline.columnes).flat().find((o) => o.id === oportunitatId) : null;
      if (op) {
        setModalRegistrarExit({
          open: true,
          oportunitat: op,
          rao: "",
          requisits: `${op.vertical}, mobilitat tècnica d'operaris, gestió sense paper`,
          replicable: true,
        });
        return;
      }
    }

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

  const obrirModalEditarLead = (leadObj: any) => {
    setModalEditarLead({
      open: true,
      leadId: leadObj.id,
      nom_empresa: leadObj.nom_empresa || "",
      nom_contacte: leadObj.nom_contacte || "",
      carrec_contacte: leadObj.carrec_contacte || "",
      email: leadObj.email || "",
      telefon: leadObj.telefon || "",
      cif: leadObj.cif || "",
      web_url: leadObj.web_url || "",
      adreca_fisica: leadObj.adreca_fisica || "",
      codi_postal: leadObj.codi_postal || "",
      vertical: leadObj.vertical || "CampoPro",
      operaris_estimats: Number(leadObj.operaris_estimats || 5),
      estat_qualificacio: leadObj.estat_qualificacio || "QUALIFICAT",
      notes: leadObj.notes || "",
    });
  };

  const handleGuardarEditarLead = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!modalEditarLead.leadId) return;
    setGuardantEditarLead(true);
    try {
      await apiFetch(`/superadmin/crm/prospeccio/leads/${modalEditarLead.leadId}`, {
        method: "PUT",
        body: JSON.stringify({
          nom_empresa: modalEditarLead.nom_empresa,
          nom_contacte: modalEditarLead.nom_contacte,
          carrec_contacte: modalEditarLead.carrec_contacte,
          email: modalEditarLead.email,
          telefon: modalEditarLead.telefon,
          cif: modalEditarLead.cif,
          web_url: modalEditarLead.web_url,
          adreca_fisica: modalEditarLead.adreca_fisica,
          codi_postal: modalEditarLead.codi_postal,
          vertical: modalEditarLead.vertical,
          operaris_estimats: Number(modalEditarLead.operaris_estimats),
          estat_qualificacio: modalEditarLead.estat_qualificacio,
          notes: modalEditarLead.notes,
        }),
      });
      const editedId = modalEditarLead.leadId;
      setModalEditarLead({ ...modalEditarLead, open: false });
      await carregarDades();
      if (selectedLeadId === editedId) {
        await obrirDetallLead(editedId);
      }
    } catch (err: any) {
      alert("Error actualitzant prospecte: " + (err.message || err));
    } finally {
      setGuardantEditarLead(false);
    }
  };

  const handleEliminarLead = async (leadId: string, nomEmpresa: string) => {
    if (!confirm(`Segur que vols eliminar el prospecte '${nomEmpresa}' i tots els seus deals i activitats?`)) return;
    try {
      await apiFetch(`/superadmin/crm/prospeccio/leads/${leadId}`, {
        method: "DELETE",
      });
      if (selectedLeadId === leadId) {
        setSelectedLeadId(null);
        setLeadDetall(null);
      }
      await carregarDades();
      await carregarCalendari();
      if (tascaSeleccionadaId) await carregarDetallTascaCP(tascaSeleccionadaId);
    } catch (err: any) {
      alert("Error eliminant prospecte: " + (err.message || err));
    }
  };

  const obrirModalEditarDeal = (op: any, nomEmpresaFallback = "") => {
    setModalEditarDeal({
      open: true,
      mode: "edit",
      oportunitatId: op.id,
      leadId: op.lead_id || selectedLeadId || "",
      nomEmpresa: op.nom_empresa || nomEmpresaFallback || "",
      titol: op.titol || "",
      etapa: op.etapa || "PROSPECCIO",
      valor_mensual_estimat: Number(op.valor_mensual_estimat ?? 0),
      valor_ia_setup: Number(op.valor_ia_setup ?? 150),
      probabilitat_percent: Number(op.probabilitat_percent ?? 30),
    });
  };

  const obrirModalNouDeal = (leadObj: any) => {
    setModalEditarDeal({
      open: true,
      mode: "create",
      oportunitatId: "",
      leadId: leadObj.id,
      nomEmpresa: leadObj.nom_empresa || "",
      titol: `Llicència ${leadObj.vertical || "CampoPro"} - ${leadObj.nom_empresa || ""}`,
      etapa: "PROSPECCIO",
      valor_mensual_estimat: Number((leadObj.operaris_estimats || 5) * 18),
      valor_ia_setup: 150,
      probabilitat_percent: 30,
    });
  };

  const handleGuardarDeal = async (e: React.FormEvent) => {
    e.preventDefault();
    setGuardantDeal(true);
    try {
      if (modalEditarDeal.mode === "create") {
        await apiFetch("/superadmin/crm/prospeccio/oportunitats", {
          method: "POST",
          body: JSON.stringify({
            lead_id: modalEditarDeal.leadId,
            titol: modalEditarDeal.titol,
            etapa: modalEditarDeal.etapa,
            valor_mensual_estimat: Number(modalEditarDeal.valor_mensual_estimat),
            valor_ia_setup: Number(modalEditarDeal.valor_ia_setup),
            probabilitat_percent: Number(modalEditarDeal.probabilitat_percent),
          }),
        });
      } else {
        await apiFetch(`/superadmin/crm/prospeccio/oportunitats/${modalEditarDeal.oportunitatId}`, {
          method: "PUT",
          body: JSON.stringify({
            titol: modalEditarDeal.titol,
            etapa: modalEditarDeal.etapa,
            valor_mensual_estimat: Number(modalEditarDeal.valor_mensual_estimat),
            valor_ia_setup: Number(modalEditarDeal.valor_ia_setup),
            probabilitat_percent: Number(modalEditarDeal.probabilitat_percent),
          }),
        });
      }
      const targetLeadId = modalEditarDeal.leadId;
      setModalEditarDeal({ ...modalEditarDeal, open: false });
      await carregarDades();
      if (selectedLeadId && selectedLeadId === targetLeadId) {
        await obrirDetallLead(selectedLeadId);
      }
    } catch (err: any) {
      alert("Error desant deal: " + (err.message || err));
    } finally {
      setGuardantDeal(false);
    }
  };

  const handleEliminarDeal = async (oportunitatId: string, titolDeal: string) => {
    if (!confirm(`Segur que vols eliminar el deal '${titolDeal}' del Pipeline?`)) return;
    try {
      await apiFetch(`/superadmin/crm/prospeccio/oportunitats/${oportunitatId}`, {
        method: "DELETE",
      });
      await carregarDades();
      if (selectedLeadId) {
        await obrirDetallLead(selectedLeadId);
      }
    } catch (err: any) {
      alert("Error eliminant deal: " + (err.message || err));
    }
  };

  const handleEliminarCandidatCp = async (candidatId: string, nomEmpresa: string) => {
    if (!confirm(`Segur que vols eliminar el candidat '${nomEmpresa}' d'aquest lot de Codi Postal?`)) return;
    try {
      await apiFetch(`/superadmin/crm/prospeccio/candidats/${candidatId}`, {
        method: "DELETE",
      });
      if (tascaSeleccionadaId) await carregarDetallTascaCP(tascaSeleccionadaId);
      await carregarTasquesCP();
    } catch (err: any) {
      alert("Error eliminant candidat: " + (err.message || err));
    }
  };

  const handleActivarDemo = async () => {
    if (!selectedLeadId) return;
    setActivantDemo(true);
    try {
      await apiFetch<any>(`/superadmin/crm/prospeccio/leads/${selectedLeadId}/activar-demo`, {
        method: "POST",
        body: JSON.stringify({
          vertical: demoVertical,
          durada_dies: Number(demoDies),
          recrear: false,
        }),
      });
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

  // ==========================================
  // ACCIONS T014: EXPLORADOR PER CP & STREAMING SSE
  // ==========================================

  const iniciarStreamSSE = async (tascaId: string) => {
    try {
      const token = getAuthToken();
      const baseUrl = getApiBaseUrl();
      const url = `${baseUrl}/superadmin/crm/prospeccio/tasques-cp/${tascaId}/stream`;

      const headers: Record<string, string> = {};
      if (token) headers["Authorization"] = `Bearer ${token}`;

      const response = await fetch(url, { headers });
      if (!response.body) return;

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const data = JSON.parse(line.slice(6));
              const hora = new Date().toLocaleTimeString("ca-ES");
              if (data.pas === "INICI") {
                setConsoleLogs((prev) => [
                  { time: hora, text: `[INICI] Lot CP ${data.codi_postal} connectat via SSE stream.`, type: "info" },
                  ...prev,
                ]);
              } else if (data.pas === "COMPLETAT") {
                setConsoleLogs((prev) => [
                  {
                    time: hora,
                    text: `[COMPLETAT] Trobats: ${data.total_trobats} | Seleccionats: ${data.total_seleccionats} | Descartats: ${data.total_descartats} | Duplicats: ${data.total_duplicats}`,
                    type: "success",
                  },
                  ...prev,
                ]);
              }
            } catch {
              // Parse error ignorat
            }
          }
        }
      }
    } catch (err) {
      console.warn("SSE stream completat o no disponible:", err);
    }
  };

  const handleLlançarCercaCp = async () => {
    if (!codiPostalInput.trim() || !verticalInput.trim()) {
      alert("Cal indicar el Codi Postal i la Vertical / Sector.");
      return;
    }

    setExecutantCerca(true);
    setPreparacioSeguentCpMsg(null);
    const hora = new Date().toLocaleTimeString("ca-ES");

    setConsoleLogs((prev) => [
      {
        time: hora,
        text: `[INICI] Llançant lot atòmic per CP ${codiPostalInput.trim()} amb vertical "${verticalInput.trim()}" (mín. ${operarisMinims} operaris)...`,
        type: "info",
      },
      {
        time: hora,
        text: `[INVESTIGACIÓ] Multi-canal activat: Web, LinkedIn, Instagram, Premsa i Adjudicacions Oficials.`,
        type: "info",
      },
      {
        time: hora,
        text: `[DEDUPLICACIÓ] Comprovació 3 vectors (CIF, Domini Web, Adreça Física) contra clients i opt-out RGPD.`,
        type: "info",
      },
      ...prev,
    ]);

    try {
      const res = await apiFetch<any>("/superadmin/crm/prospeccio/tasques-cp", {
        method: "POST",
        body: JSON.stringify({
          codi_postal: codiPostalInput.trim(),
          vertical: verticalInput.trim(),
          operaris_minims: Number(operarisMinims),
          limit: 5,
        }),
      });

      const horaFi = new Date().toLocaleTimeString("ca-ES");
      setConsoleLogs((prev) => [
        {
          time: horaFi,
          text: `[ÈXIT] Cerca finalitzada per al CP ${res.codi_postal}. Trobats: ${res.total_trobats}, Seleccionats: ${res.total_seleccionats}, Descartats: ${res.total_descartats}, Duplicats: ${res.total_duplicats}.`,
          type: "success",
        },
        ...prev,
      ]);

      setTascaSeleccionadaId(res.tasca_id);
      await carregarTasquesCP();
      await carregarDetallTascaCP(res.tasca_id);
      await carregarDades();
      await carregarCalendari();
      iniciarStreamSSE(res.tasca_id);
    } catch (err: any) {
      const horaErr = new Date().toLocaleTimeString("ca-ES");
      setConsoleLogs((prev) => [
        { time: horaErr, text: `[ERROR] Fallada executant cerca: ${err.message || err}`, type: "error" },
        ...prev,
      ]);
      // Recarregar les dades de PostgreSQL perquè el backend pot haver completat el lot
      try {
        await carregarTasquesCP();
        await carregarDades();
        await carregarCalendari();
      } catch {
        // Ignorar si falla la recàrrega
      }
      alert("Error executant cerca: " + (err.message || err));
    } finally {
      setExecutantCerca(false);
    }
  };

  const handlePrepararSeguentCp = () => {
    // Incrementa el codi postal numèricament (ex: 25001 -> 25002) sense executar automàticament (FR-003)
    const num = parseInt(codiPostalInput.replace(/\D/g, ""), 10);
    if (!isNaN(num)) {
      const seguent = String(num + 1).padStart(5, "0");
      setCodiPostalInput(seguent);
      setPreparacioSeguentCpMsg(
        `Següent Codi Postal preparat (${seguent}). Revisa la vertical i fes clic a 'Llançar Cerca Atòmica' quan estiguis llest.`
      );
    }
  };

  const handleGuardarCorreccioCriteri = async () => {
    if (!modalCorregir.candidat) return;
    if (modalCorregir.motiu.trim().length < 10) {
      alert("La justificació humana ha de tenir com a mínim 10 caràcters per alimentar el Doble Bucle d'Aprenentatge.");
      return;
    }

    setGuardantCorreccio(true);
    try {
      await apiFetch(`/superadmin/crm/prospeccio/candidats/${modalCorregir.candidat.id}/corregir-criteri`, {
        method: "POST",
        body: JSON.stringify({
          nova_decisio: modalCorregir.novaDecisio,
          motiu_correccio_humana: modalCorregir.motiu.trim(),
        }),
      });

      setModalCorregir({ open: false, candidat: null, novaDecisio: "SELECCIONAT", motiu: "" });
      if (tascaSeleccionadaId) await carregarDetallTascaCP(tascaSeleccionadaId);
      await carregarDades();
      await carregarCalendari();
    } catch (err: any) {
      alert("Error guardant correcció: " + (err.message || err));
    } finally {
      setGuardantCorreccio(false);
    }
  };

  // ==========================================
  // ACCIONS T015: CALENDARI & ENVIAMENT HITL
  // ==========================================

  const handleAprovarIEnviarCorreu = async (correuId: string) => {
    if (!confirm("Vols aprovar i enviar aquest correu immediatament des de tecnic@sevalor.net?")) return;

    setEnviantCorreuId(correuId);
    try {
      await apiFetch(`/superadmin/crm/prospeccio/correus/${correuId}/enviar`, {
        method: "POST",
      });
      await carregarCalendari();
      if (selectedLeadId) await obrirDetallLead(selectedLeadId);
    } catch (err: any) {
      alert("Error enviant correu: " + (err.message || err));
    } finally {
      setEnviantCorreuId(null);
    }
  };

  const handleGuardarEsborranyCorreu = async () => {
    if (!modalEditarCorreu.item) return;

    setGuardantEsborrany(true);
    try {
      await apiFetch(`/superadmin/crm/prospeccio/correus/${modalEditarCorreu.item.id}/esborrany`, {
        method: "PUT",
        body: JSON.stringify({
          assumpte: modalEditarCorreu.assumpte,
          cos_text: modalEditarCorreu.cos,
          data_programada: modalEditarCorreu.dataProgramada
            ? new Date(modalEditarCorreu.dataProgramada).toISOString()
            : undefined,
        }),
      });
      setModalEditarCorreu({ open: false, item: null, assumpte: "", cos: "", dataProgramada: "" });
      await carregarCalendari();
      if (selectedLeadId) await obrirDetallLead(selectedLeadId);
    } catch (err: any) {
      alert("Error desant esborrany: " + (err.message || err));
    } finally {
      setGuardantEsborrany(false);
    }
  };

  const handleCrearEsdevenimentManual = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!modalNouEsdeveniment.leadId || !modalNouEsdeveniment.titol.trim()) {
      alert("Selecciona un prospecte i un títol d'esdeveniment.");
      return;
    }

    setGuardantNouEsdeveniment(true);
    try {
      await apiFetch("/superadmin/crm/prospeccio/calendari/esdeveniments", {
        method: "POST",
        body: JSON.stringify({
          lead_id: modalNouEsdeveniment.leadId,
          tipus: modalNouEsdeveniment.tipus,
          titol: modalNouEsdeveniment.titol.trim(),
          descripcio: modalNouEsdeveniment.descripcio.trim() || undefined,
          data_programada: new Date(modalNouEsdeveniment.dataProgramada).toISOString(),
        }),
      });
      setModalNouEsdeveniment({
        open: false,
        leadId: "",
        tipus: "SEGUIMENT_CALENDARI",
        titol: "",
        descripcio: "",
        dataProgramada: new Date(Date.now() + 86400000).toISOString().slice(0, 16),
      });
      await carregarCalendari();
    } catch (err: any) {
      alert("Error creant esdeveniment: " + (err.message || err));
    } finally {
      setGuardantNouEsdeveniment(false);
    }
  };

  // ==========================================
  // ACCIONS T016: REGISTRAR TANCAMENT GUANYAT REPLICABLE
  // ==========================================

  const handleGuardarTancamentExit = async () => {
    if (!modalRegistrarExit.oportunitat) return;
    if (modalRegistrarExit.rao.trim().length < 5) {
      alert("La raó del tancament d'èxit ha de tenir com a mínim 5 caràcters per alimentar el cercador d'empreses bessones.");
      return;
    }

    setGuardantExit(true);
    try {
      await apiFetch(`/superadmin/crm/prospeccio/oportunitats/${modalRegistrarExit.oportunitat.id}/registrar-exit`, {
        method: "POST",
        body: JSON.stringify({
          rao_tancament_exit: modalRegistrarExit.rao.trim(),
          requisits_replicables: modalRegistrarExit.requisits.trim() || undefined,
          es_replicable: modalRegistrarExit.replicable,
        }),
      });

      setFeedbackExitCreat(
        `🏆 Tancament registrat com a GUANYAT! Patró desat a saas_criteris_feedback per buscar empreses bessones (Lookalikes Boost ≥ 85).`
      );
      setModalRegistrarExit({ open: false, oportunitat: null, rao: "", requisits: "", replicable: true });
      await carregarDades();
      if (selectedLeadId) await obrirDetallLead(selectedLeadId);
      setTimeout(() => setFeedbackExitCreat(null), 8000);
    } catch (err: any) {
      alert("Error registrant tancament d'èxit: " + (err.message || err));
    } finally {
      setGuardantExit(false);
    }
  };

  // Càlcul de mètriques ràpides
  const totalLeads = leads.length;
  const totalDemosActives = leads.filter((l) => l.demo_activa).length;
  const totalMrrPipeline = pipeline ? Object.values(pipeline.totals_mrr).reduce((acc, v) => acc + v, 0) : 0;
  const pendentsAprovacioAvuiCount = calendariData?.pendents_aprovacio_avui || 0;

  // Filtre de candidats a l'explorador
  const candidatsFiltrats = candidatsCP.filter((c) => {
    if (filtreDecisio === "TOTS") return true;
    return c.estat_decisio === filtreDecisio;
  });

  // Filtre d'esdeveniments del calendari
  const itemsCalendariFiltrats = (calendariData?.items || []).filter((item) => {
    if (filtreCalendari === "AVUI") return item.pendent_aprovacio || item.es_avui;
    if (filtreCalendari === "CORREUS") return item.tipus_item_calendari.startsWith("EMAIL");
    if (filtreCalendari === "REUNIONS") return item.tipus_item_calendari === "REUNIO_DEMO" || item.tipus_item_calendari === "SEGUIMENT_CALENDARI";
    return true;
  });

  // Filtre de prospectes generals
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
                Prospecció Atòmica per CP, Calendari HITL (D0, D+4, D+8) i Doble Bucle d'Aprenentatge (Zero Mocks)
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2.5">
          {pendentsAprovacioAvuiCount > 0 && (
            <button
              onClick={() => {
                setActiveTab("calendari");
                setFiltreCalendari("AVUI");
              }}
              className="px-3 py-1.5 rounded-xl bg-amber-500 hover:bg-amber-400 text-slate-950 text-xs font-bold flex items-center gap-1.5 shadow-sm transition-all animate-pulse"
            >
              <AlertTriangle className="w-4 h-4 fill-current" />
              <span>{pendentsAprovacioAvuiCount} Aprovacions HITL Avui</span>
            </button>
          )}

          <button
            onClick={() => setShowNouLeadModal(true)}
            className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold flex items-center gap-2 shadow-sm transition-all"
          >
            <Plus className="w-4 h-4" />
            <span>Nou Prospecte Manual</span>
          </button>
        </div>
      </div>

      {/* FEEDBACK DE TANCAMENT GUANYAT REPLICABLE */}
      {feedbackExitCreat && (
        <div className="p-3.5 rounded-2xl bg-emerald-50 dark:bg-emerald-950/60 border border-emerald-300 dark:border-emerald-800 text-emerald-900 dark:text-emerald-200 text-xs flex items-center justify-between shadow-sm animate-in fade-in">
          <div className="flex items-center gap-2 font-medium">
            <Award className="w-4 h-4 text-emerald-600 shrink-0" />
            <span>{feedbackExitCreat}</span>
          </div>
          <button onClick={() => setFeedbackExitCreat(null)} className="text-emerald-700 hover:text-emerald-950 font-bold">
            ✕
          </button>
        </div>
      )}

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
            <span>Agenda HITL d'Avui</span>
            <Clock className="w-4 h-4 text-blue-500" />
          </div>
          <div className="text-2xl font-bold text-blue-600 dark:text-blue-400 mt-1">{pendentsAprovacioAvuiCount} pendents</div>
          <div className="text-[11px] text-slate-400 mt-1">Correus i seguiments per enviar avui</div>
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
          onClick={() => setActiveTab("explorador")}
          className={`pb-3 flex items-center gap-2 border-b-2 transition-all ${
            activeTab === "explorador"
              ? "border-indigo-600 text-indigo-600 dark:text-indigo-400"
              : "border-transparent text-slate-500 hover:text-slate-900 dark:hover:text-white"
          }`}
        >
          <Compass className="w-4 h-4" />
          <span>Explorador de Leads per CP (Atòmic)</span>
        </button>

        <button
          onClick={() => setActiveTab("calendari")}
          className={`pb-3 flex items-center gap-2 border-b-2 transition-all relative ${
            activeTab === "calendari"
              ? "border-indigo-600 text-indigo-600 dark:text-indigo-400"
              : "border-transparent text-slate-500 hover:text-slate-900 dark:hover:text-white"
          }`}
        >
          <Calendar className="w-4 h-4" />
          <span>Calendari Comercial & Campanyes</span>
          {pendentsAprovacioAvuiCount > 0 && (
            <span className="px-1.5 py-0.5 rounded-full bg-amber-500 text-slate-950 font-mono text-[10px] font-bold">
              {pendentsAprovacioAvuiCount}
            </span>
          )}
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
        /* ============================================================
           PESTANYA 1: PIPELINE KANBAN (TWENTY CRM STYLE)
           ============================================================ */
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
                        <div className="text-[10px] text-slate-400 truncate font-medium" title={op.titol}>
                          {op.titol}
                        </div>

                        {/* Indicador de Demo de 7 dies si està en curs */}
                        {op.demo_activa && (
                          <div className="flex items-center gap-1.5 px-2 py-1 rounded-lg bg-amber-50 dark:bg-amber-950/50 border border-amber-200 dark:border-amber-800/60 text-[10px] text-amber-800 dark:text-amber-300 font-mono font-semibold">
                            <Clock className="w-3 h-3 text-amber-600 shrink-0" />
                            <span>Queden {op.dies_restants_demo}d de demo (7D)</span>
                          </div>
                        )}

                        {/* Indicador de tancament replicable */}
                        {op.es_replicable && (
                          <div className="flex items-center gap-1 text-[10px] text-emerald-600 dark:text-emerald-400 font-semibold">
                            <Award className="w-3 h-3" />
                            <span>Cas Replicable (Lookalike)</span>
                          </div>
                        )}

                        <div className="flex items-center justify-between pt-1 border-t border-slate-100 dark:border-slate-700/60 text-[11px]">
                          <span className="font-bold text-slate-900 dark:text-slate-100 font-mono">
                            {op.valor_mensual_estimat} €/m
                          </span>

                          {/* Controls ràpids per editar, eliminar i moure el Deal */}
                          <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                            <button
                              title="Editar Deal / Oportunitat"
                              onClick={(e) => {
                                e.stopPropagation();
                                obrirModalEditarDeal(op);
                              }}
                              className="p-1 rounded hover:bg-indigo-50 dark:hover:bg-indigo-950/50 text-slate-500 hover:text-indigo-600"
                            >
                              <Edit className="w-3 h-3" />
                            </button>

                            <button
                              title="Eliminar Deal / Oportunitat"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleEliminarDeal(op.id, op.titol);
                              }}
                              className="p-1 rounded hover:bg-rose-50 dark:hover:bg-rose-950/50 text-slate-400 hover:text-rose-600"
                            >
                              <Trash2 className="w-3 h-3" />
                            </button>

                            {etapaKey !== "GUANYAT" && (
                              <button
                                title="Passar a Guanyat Replicable (T016)"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setModalRegistrarExit({
                                    open: true,
                                    oportunitat: op,
                                    rao: "",
                                    requisits: `${op.vertical}, mobilitat tècnica d'operaris, gestió sense paper`,
                                    replicable: true,
                                  });
                                }}
                                className="p-1 rounded hover:bg-emerald-50 dark:hover:bg-emerald-950/50 text-emerald-600"
                              >
                                <Award className="w-3.5 h-3.5" />
                              </button>
                            )}

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
      ) : activeTab === "explorador" ? (
        /* ============================================================
           PESTANYA 2: EXPLORADOR DE LEADS PER CP (T014)
           ============================================================ */
        <div className="space-y-6">
          {/* Caixa de Paràmetres de Cerca Atòmica */}
          <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-4">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 pb-3 border-b border-slate-100 dark:border-slate-800">
              <div>
                <h3 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2">
                  <Compass className="w-4 h-4 text-indigo-600" />
                  <span>Prospecció Atòmica per Codi Postal & Vertical Lliure</span>
                </h3>
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                  Llança investigacions multi-canal sense encadenar codis postals automàticament (respectant FR-003).
                </p>
              </div>

              {/* Botó Preparar Següent CP */}
              <button
                type="button"
                onClick={handlePrepararSeguentCp}
                className="px-3.5 py-1.5 rounded-xl border border-slate-300 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800 text-xs font-semibold flex items-center gap-1.5 transition-colors self-start md:self-auto"
                title="Avança el Codi Postal al següent número sense llançar la cerca automàticament"
              >
                <span>Preparar Següent CP</span>
                <ArrowRight className="w-3.5 h-3.5 text-indigo-500" />
              </button>
            </div>

            {preparacioSeguentCpMsg && (
              <div className="p-3 rounded-xl bg-blue-50 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-900 text-xs text-blue-800 dark:text-blue-300 flex items-center justify-between">
                <span>{preparacioSeguentCpMsg}</span>
                <button onClick={() => setPreparacioSeguentCpMsg(null)} className="font-bold">✕</button>
              </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-12 gap-3.5">
              {/* Codi Postal */}
              <div className="md:col-span-3">
                <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">Codi Postal (5 dígits) *</label>
                <div className="relative mt-1">
                  <MapPin className="w-4 h-4 absolute left-3 top-2.5 text-slate-400" />
                  <input
                    type="text"
                    required
                    maxLength={10}
                    placeholder="ex: 25001"
                    value={codiPostalInput}
                    onChange={(e) => setCodiPostalInput(e.target.value)}
                    className="w-full pl-9 pr-3 py-2 text-xs font-mono font-bold rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                </div>
              </div>

              {/* Vertical Lliure */}
              <div className="md:col-span-6">
                <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                  Vertical / Sector escrit lliurement per l'humà *
                </label>
                <input
                  type="text"
                  required
                  list="verticals-suggerides"
                  placeholder="ex: Manteniment de climatització industrial, instal·lacions elèctriques..."
                  value={verticalInput}
                  onChange={(e) => setVerticalInput(e.target.value)}
                  className="w-full mt-1 px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
                <datalist id="verticals-suggerides">
                  <option value="CampoPro (Reg & Agrícola)" />
                  <option value="ElectricPro (Baixa Tensió)" />
                  <option value="HydroPro (Fontaneria)" />
                  <option value="BuildingPro (Edificació)" />
                  <option value="Climatització Industrial" />
                  <option value="Xarxes & Telecomunicacions" />
                </datalist>

                {/* Badges de suggeriment ràpid */}
                <div className="flex flex-wrap gap-1.5 mt-2">
                  {[
                    "CampoPro (Reg & Agrícola)",
                    "ElectricPro (Baixa Tensió)",
                    "HydroPro (Fontaneria)",
                    "BuildingPro (Edificació)",
                    "Climatització Industrial",
                    "Xarxes & Telecomunicacions",
                  ].map((sug) => (
                    <button
                      key={sug}
                      type="button"
                      onClick={() => setVerticalInput(sug)}
                      className="px-2 py-0.5 rounded-md text-[10px] font-medium bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-600 dark:text-slate-300 transition-colors"
                    >
                      {sug}
                    </button>
                  ))}
                </div>
              </div>

              {/* Mínim Operaris */}
              <div className="md:col-span-3">
                <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">Mínim Operaris</label>
                <div className="flex items-center gap-2 mt-1">
                  <input
                    type="number"
                    min={1}
                    max={100}
                    value={operarisMinims}
                    onChange={(e) => setOperarisMinims(Number(e.target.value))}
                    className="w-20 px-3 py-2 text-xs font-mono font-bold rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white"
                  />
                  <button
                    type="button"
                    onClick={handleLlançarCercaCp}
                    disabled={executantCerca}
                    className="flex-1 py-2 px-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-bold flex items-center justify-center gap-1.5 shadow-sm transition-all"
                  >
                    {executantCerca ? (
                      <>
                        <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                        <span>Investigant...</span>
                      </>
                    ) : (
                      <>
                        <Play className="w-3.5 h-3.5 fill-current" />
                        <span>Llançar Cerca Atòmica</span>
                      </>
                    )}
                  </button>
                </div>
              </div>
            </div>
          </div>

          {/* Consola SSE en Temps Real */}
          <div className="p-4 rounded-2xl bg-slate-950 border border-slate-800 text-slate-200 font-mono text-xs space-y-2 shadow-inner">
            <div className="flex items-center justify-between pb-2 border-b border-slate-800 text-[11px] text-slate-400">
              <span className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                <span>CONSOLA D'INVESTIGACIÓ MULTI-CANAL EN DIRECTE (SSE STREAM)</span>
              </span>
              <span>Firecrawl + MX Shield + DeepSeek Lead Scoring</span>
            </div>
            <div className="max-h-36 overflow-y-auto space-y-1 text-[11px] pr-2">
              {consoleLogs.map((log, i) => (
                <div key={i} className="flex items-start gap-2 leading-relaxed">
                  <span className="text-slate-500 shrink-0">[{log.time}]</span>
                  <span
                    className={
                      log.type === "success"
                        ? "text-emerald-400 font-bold"
                        : log.type === "error"
                        ? "text-rose-400 font-bold"
                        : log.type === "warn"
                        ? "text-amber-400"
                        : "text-slate-300"
                    }
                  >
                    {log.text}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Selector de Lots Executats Anteriorment */}
          {tasquesCP.length > 0 && (
            <div className="flex items-center gap-2 overflow-x-auto pb-1 text-xs">
              <span className="text-slate-500 font-semibold shrink-0">Lots Previs:</span>
              {tasquesCP.map((t) => (
                <button
                  key={t.id}
                  onClick={() => {
                    setTascaSeleccionadaId(t.id);
                    carregarDetallTascaCP(t.id);
                  }}
                  className={`px-3 py-1.5 rounded-xl border text-xs font-mono font-medium shrink-0 transition-colors ${
                    tascaSeleccionadaId === t.id
                      ? "bg-indigo-600 text-white border-indigo-600 shadow-sm"
                      : "bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-100"
                  }`}
                >
                  CP {t.codi_postal} ({t.total_seleccionats} sel / {t.total_trobats} trobats)
                </button>
              ))}
            </div>
          )}

          {/* Taula d'Auditoria Transparent de Candidats */}
          <div className="space-y-3">
            <div className="flex flex-col sm:flex-row items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300">
                  Candidats Auditats ({candidatsFiltrats.length})
                </h4>
                {tascaSeleccionada && (
                  <span className="text-[11px] text-slate-400">
                    — CP {tascaSeleccionada.codi_postal} ({tascaSeleccionada.vertical})
                  </span>
                )}
              </div>

              {/* Filtres per Estat de Decisió */}
              <div className="flex items-center gap-1.5 text-xs bg-slate-100 dark:bg-slate-800/80 p-1 rounded-xl">
                {(["TOTS", "SELECCIONAT", "SELECCIONAT_SENSE_GATEKEEPER", "DESCARTAT", "DUPLICAT", "ERROR_EXTRACCIO"] as const).map((tab) => (
                  <button
                    key={tab}
                    onClick={() => setFiltreDecisio(tab)}
                    className={`px-3 py-1 rounded-lg text-xs font-semibold transition-all ${
                      filtreDecisio === tab
                        ? "bg-white dark:bg-slate-900 text-slate-900 dark:text-white shadow-sm"
                        : "text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
                    }`}
                  >
                    {tab === "TOTS"
                      ? "Tots"
                      : tab === "SELECCIONAT"
                      ? "Seleccionades"
                      : tab === "SELECCIONAT_SENSE_GATEKEEPER"
                      ? "Sense GK (Telèfon)"
                      : tab === "DESCARTAT"
                      ? "Descartades"
                      : tab === "DUPLICAT"
                      ? "Duplicades (3 Vectors)"
                      : "Errors Extracció"}
                  </button>
                ))}
              </div>
            </div>

            <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 overflow-hidden shadow-sm">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 dark:bg-slate-800/60 text-slate-500 dark:text-slate-400 font-semibold border-b border-slate-200 dark:border-slate-800">
                  <tr>
                    <th className="py-3 px-4">Empresa & CIF</th>
                    <th className="py-3 px-4">Decisor / Gatekeeper</th>
                    <th className="py-3 px-4">Fonts Multi-Canal</th>
                    <th className="py-3 px-4">Score & Decisió</th>
                    <th className="py-3 px-4">Motiu IA / Humà</th>
                    <th className="py-3 px-4 text-right">Accions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {candidatsFiltrats.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="text-center py-10 text-slate-400">
                        Cap candidat trobat per al filtre seleccionat.
                      </td>
                    </tr>
                  ) : (
                    candidatsFiltrats.map((cand) => {
                      const urlsMap = extreureUrlsFonts(cand.fonts_investigades, cand.web_url, cand.fonts_urls);
                      return (
                      <tr key={cand.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/40 transition-colors">
                        <td className="py-3 px-4">
                          <div className="font-bold text-slate-900 dark:text-white">{cand.nom_empresa}</div>
                          <div className="text-[11px] font-mono text-slate-400 flex items-center gap-1">
                            <span>{cand.cif || "Sense CIF"} •</span>
                            {urlsMap.web ? (
                              <a
                                href={urlsMap.web}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-indigo-600 dark:text-indigo-400 hover:underline inline-flex items-center gap-0.5"
                              >
                                <span>{cand.domini_normalitzat || urlsMap.web}</span>
                                <ExternalLink className="w-2.5 h-2.5" />
                              </a>
                            ) : (
                              <span>{cand.domini_normalitzat || "Sense web"}</span>
                            )}
                          </div>
                          {cand.adreca_fisica ? (
                            <div className="text-[10px] text-slate-600 dark:text-slate-400 truncate max-w-xs font-medium">
                              📍 {cand.adreca_fisica}
                            </div>
                          ) : (
                            <div className="text-[10px] text-rose-500 font-medium">
                              Sense adreça física verificada al CP {cand.codi_postal}
                            </div>
                          )}
                          {cand.cp_geocode_coincideix === false && (
                            <div
                              className="text-[9px] font-mono font-bold text-amber-700 dark:text-amber-300 bg-amber-50 dark:bg-amber-950/40 px-1.5 py-0.5 rounded border border-amber-200 dark:border-amber-800 mt-0.5 inline-block"
                              title={`Nominatim geocodifica com a CP ${cand.cp_geocode_retornat || "desconegut"}`}
                            >
                              ⚠️ Geocode discrepant: CP {cand.cp_geocode_retornat || "N/A"}
                            </div>
                          )}
                        </td>

                        <td className="py-3 px-4">
                          {cand.decisor_nom ? (
                            <div className="font-semibold text-slate-900 dark:text-slate-100">
                              {cand.decisor_nom}
                            </div>
                          ) : (
                            <div className="text-[11px] font-medium text-rose-600 dark:text-rose-400">
                              Sense Gatekeeper nominal verificat
                            </div>
                          )}
                          <div className="text-[11px] text-slate-400">{cand.decisor_carrec || "Sense càrrec"}</div>
                          {cand.gatekeeper_font_url && (
                            <div className="mt-0.5">
                              <a
                                href={cand.gatekeeper_font_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="inline-flex items-center gap-1 text-[9px] font-semibold text-emerald-700 dark:text-emerald-300 hover:underline"
                                title={cand.gatekeeper_cita || "Font gatekeeper verificada"}
                              >
                                <CheckCircle2 className="w-2.5 h-2.5" />
                                <span>GK verificat ({cand.gatekeeper_confianca || "alta"})</span>
                                <ExternalLink className="w-2 h-2" />
                              </a>
                            </div>
                          )}
                          {cand.email_detectat && (
                            <div className="text-[11px] font-mono text-indigo-600 dark:text-indigo-400">
                              {cand.email_detectat}
                            </div>
                          )}
                        </td>

                        <td className="py-3 px-4">
                          <div className="flex flex-wrap gap-1">
                            {urlsMap.web && (
                              <a
                                href={urlsMap.web}
                                target="_blank"
                                rel="noopener noreferrer"
                                title={urlsMap.web}
                                className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-blue-50 hover:bg-blue-100 dark:bg-blue-950/50 dark:hover:bg-blue-900/70 text-blue-700 dark:text-blue-300 font-mono text-[9px] font-bold underline-offset-2 hover:underline"
                              >
                                <Globe className="w-2.5 h-2.5" /> Web <ExternalLink className="w-2 h-2" />
                              </a>
                            )}
                            {urlsMap.linkedin && (
                              <a
                                href={urlsMap.linkedin}
                                target="_blank"
                                rel="noopener noreferrer"
                                title={urlsMap.linkedin}
                                className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-sky-50 hover:bg-sky-100 dark:bg-sky-950/50 dark:hover:bg-sky-900/70 text-sky-700 dark:text-sky-300 font-mono text-[9px] font-bold underline-offset-2 hover:underline"
                              >
                                <Linkedin className="w-2.5 h-2.5" /> LinkedIn <ExternalLink className="w-2 h-2" />
                              </a>
                            )}
                            {urlsMap.instagram && (
                              <a
                                href={urlsMap.instagram}
                                target="_blank"
                                rel="noopener noreferrer"
                                title={urlsMap.instagram}
                                className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-pink-50 hover:bg-pink-100 dark:bg-pink-950/50 dark:hover:bg-pink-900/70 text-pink-700 dark:text-pink-300 font-mono text-[9px] font-bold underline-offset-2 hover:underline"
                              >
                                <Instagram className="w-2.5 h-2.5" /> Instagram <ExternalLink className="w-2 h-2" />
                              </a>
                            )}
                            {urlsMap.maps && (
                              <a
                                href={urlsMap.maps}
                                target="_blank"
                                rel="noopener noreferrer"
                                title={urlsMap.maps}
                                className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-amber-50 hover:bg-amber-100 dark:bg-amber-950/50 dark:hover:bg-amber-900/70 text-amber-700 dark:text-amber-300 font-mono text-[9px] font-bold underline-offset-2 hover:underline"
                              >
                                <MapPin className="w-2.5 h-2.5" /> Maps <ExternalLink className="w-2 h-2" />
                              </a>
                            )}
                            {urlsMap.premsa && (
                              <a
                                href={urlsMap.premsa}
                                target="_blank"
                                rel="noopener noreferrer"
                                title={urlsMap.premsa}
                                className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-emerald-50 hover:bg-emerald-100 dark:bg-emerald-950/50 dark:hover:bg-emerald-900/70 text-emerald-700 dark:text-emerald-300 font-mono text-[9px] font-bold underline-offset-2 hover:underline"
                              >
                                <FileText className="w-2.5 h-2.5" /> Premsa <ExternalLink className="w-2 h-2" />
                              </a>
                            )}
                          </div>
                          {cand.fita_recent && (
                            <div className="text-[10px] text-slate-500 mt-1 line-clamp-1 italic">
                              "{cand.fita_recent}"
                            </div>
                          )}
                        </td>

                        <td className="py-3 px-4">
                          <div className="flex items-center gap-2">
                            <span
                              className={`px-2 py-0.5 rounded-full font-mono font-bold text-[10px] ${
                                cand.estat_decisio === "SELECCIONAT"
                                  ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300"
                                  : cand.estat_decisio === "SELECCIONAT_SENSE_GATEKEEPER"
                                  ? "bg-sky-100 text-sky-800 dark:bg-sky-950 dark:text-sky-300 border border-sky-300 dark:border-sky-800"
                                  : cand.estat_decisio === "DUPLICAT"
                                  ? "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300"
                                  : cand.estat_decisio === "ERROR_EXTRACCIO"
                                  ? "bg-orange-100 text-orange-800 dark:bg-orange-950 dark:text-orange-300"
                                  : "bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300"
                              }`}
                            >
                              {cand.estat_decisio === "SELECCIONAT_SENSE_GATEKEEPER"
                                ? "SEL. SENSE GK"
                                : cand.estat_decisio}
                            </span>
                            <span className="font-mono text-xs font-bold text-slate-700 dark:text-slate-300">
                              {cand.score}/100
                            </span>
                          </div>
                          {cand.vector_duplicitat && (
                            <div className="text-[10px] text-amber-700 dark:text-amber-400 font-mono mt-0.5">
                              Vector: {cand.vector_duplicitat}
                            </div>
                          )}
                        </td>

                        <td className="py-3 px-4 max-w-xs">
                          {cand.corregit_huma ? (
                            <div className="space-y-0.5">
                              <span className="px-1.5 py-0.5 rounded bg-indigo-100 dark:bg-indigo-950 text-indigo-700 dark:text-indigo-300 text-[9px] font-bold">
                                Corregit per l'Humà: {cand.decisio_humana}
                              </span>
                              <p className="text-[10px] text-slate-600 dark:text-slate-300 italic line-clamp-2">
                                "{cand.motiu_correccio_humana}"
                              </p>
                            </div>
                          ) : (
                            <p className="text-[11px] text-slate-500 line-clamp-2">{cand.motiu_detallat_ia}</p>
                          )}
                        </td>

                        <td className="py-3 px-4 text-right">
                          <div className="flex items-center justify-end gap-1.5">
                            <button
                              onClick={() =>
                                setModalCorregir({
                                  open: true,
                                  candidat: cand,
                                  novaDecisio: cand.estat_decisio.startsWith("SELECCIONAT")
                                    ? "DESCARTAT"
                                    : "SELECCIONAT",
                                  motiu: "",
                                })
                              }
                              className="px-2.5 py-1 rounded-xl bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 text-xs font-semibold flex items-center gap-1.5 transition-colors"
                            >
                              <Sliders className="w-3.5 h-3.5 text-indigo-500" />
                              <span>Corregir Criteri</span>
                            </button>

                            <button
                              title="Eliminar candidat del lot"
                              onClick={() => handleEliminarCandidatCp(cand.id, cand.nom_empresa)}
                              className="p-1.5 rounded-xl bg-rose-50 hover:bg-rose-100 dark:bg-rose-950/40 dark:hover:bg-rose-900/60 text-rose-600 dark:text-rose-400 transition-colors"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        </td>
                      </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      ) : activeTab === "calendari" ? (
        /* ============================================================
           PESTANYA 3: CALENDARI COMERCIAL & CAMPANYES (T015)
           ============================================================ */
        <div className="space-y-6">
          <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-4">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 pb-3 border-b border-slate-100 dark:border-slate-800">
              <div>
                <h3 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2">
                  <Calendar className="w-4 h-4 text-indigo-600" />
                  <span>Calendari Comercial Integrat & Seqüències d'Emails</span>
                </h3>
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                  Campanya de 3 emails amb tempo (Dia 0, Dia +4, Dia +8) enviats des de tecnic@sevalor.net amb Human-in-the-Loop obligatori.
                </p>
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={() => setModalNouEsdeveniment({ ...modalNouEsdeveniment, open: true })}
                  className="px-3.5 py-1.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold flex items-center gap-1.5 shadow-sm transition-all"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>Nou Esdeveniment Manual</span>
                </button>
              </div>
            </div>

            {/* Sub-filtres de calendari */}
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-1.5 text-xs bg-slate-100 dark:bg-slate-800/80 p-1 rounded-xl">
                <button
                  onClick={() => setFiltreCalendari("AVUI")}
                  className={`px-3 py-1 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all ${
                    filtreCalendari === "AVUI"
                      ? "bg-white dark:bg-slate-900 text-slate-900 dark:text-white shadow-sm"
                      : "text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
                  }`}
                >
                  <AlertTriangle className="w-3.5 h-3.5 text-amber-500" />
                  <span>Agenda d'Avui (HITL Urgent)</span>
                  {pendentsAprovacioAvuiCount > 0 && (
                    <span className="px-1.5 py-0.2 rounded-full bg-amber-500 text-slate-950 font-mono text-[10px] font-bold">
                      {pendentsAprovacioAvuiCount}
                    </span>
                  )}
                </button>

                <button
                  onClick={() => setFiltreCalendari("TOTS")}
                  className={`px-3 py-1 rounded-lg text-xs font-semibold transition-all ${
                    filtreCalendari === "TOTS"
                      ? "bg-white dark:bg-slate-900 text-slate-900 dark:text-white shadow-sm"
                      : "text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
                  }`}
                >
                  Tots els Esdeveniments ({calendariData?.total_esdeveniments || 0})
                </button>

                <button
                  onClick={() => setFiltreCalendari("CORREUS")}
                  className={`px-3 py-1 rounded-lg text-xs font-semibold transition-all ${
                    filtreCalendari === "CORREUS"
                      ? "bg-white dark:bg-slate-900 text-slate-900 dark:text-white shadow-sm"
                      : "text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
                  }`}
                >
                  Només Seqüències de Correu (3 Passos)
                </button>

                <button
                  onClick={() => setFiltreCalendari("REUNIONS")}
                  className={`px-3 py-1 rounded-lg text-xs font-semibold transition-all ${
                    filtreCalendari === "REUNIONS"
                      ? "bg-white dark:bg-slate-900 text-slate-900 dark:text-white shadow-sm"
                      : "text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
                  }`}
                >
                  Reunions Demo & Seguiments
                </button>
              </div>

              <button
                onClick={carregarCalendari}
                className="px-2.5 py-1 rounded-lg border border-slate-200 dark:border-slate-800 hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-400 text-xs flex items-center gap-1"
              >
                <RefreshCw className={`w-3 h-3 ${loadingCalendari ? "animate-spin" : ""}`} />
                <span>Actualitzar</span>
              </button>
            </div>
          </div>

          {/* Llista d'Items del Calendari */}
          <div className="space-y-3">
            {itemsCalendariFiltrats.length === 0 ? (
              <div className="p-12 text-center text-slate-400 border border-dashed border-slate-200 dark:border-slate-800 rounded-2xl">
                Cap esdeveniment programat per a aquesta visualització.
              </div>
            ) : (
              itemsCalendariFiltrats.map((item) => (
                <div
                  key={item.id}
                  className={`p-4 rounded-2xl bg-white dark:bg-slate-900 border transition-all shadow-sm ${
                    item.pendent_aprovacio
                      ? "border-amber-300 dark:border-amber-800 bg-amber-50/10"
                      : "border-slate-200 dark:border-slate-800"
                  }`}
                >
                  <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 pb-3 border-b border-slate-100 dark:border-slate-800/60">
                    <div className="flex items-center gap-2.5">
                      {/* Badge de Tempo */}
                      <span
                        className={`px-2.5 py-1 rounded-xl text-xs font-mono font-bold border ${
                          (item.tipus_item_calendari === "EMAIL_CAMPANYA" && item.pas_sequencia === 1) ||
                          item.tipus_item_calendari === "EMAIL_PAS_1"
                            ? "bg-amber-50 text-amber-900 border-amber-300 dark:bg-amber-950/60 dark:text-amber-200"
                            : (item.tipus_item_calendari === "EMAIL_CAMPANYA" && item.pas_sequencia === 2) ||
                              item.tipus_item_calendari === "EMAIL_PAS_2"
                            ? "bg-blue-50 text-blue-900 border-blue-300 dark:bg-blue-950/60 dark:text-blue-200"
                            : (item.tipus_item_calendari === "EMAIL_CAMPANYA" && item.pas_sequencia === 3) ||
                              item.tipus_item_calendari === "EMAIL_PAS_3"
                            ? "bg-purple-50 text-purple-900 border-purple-300 dark:bg-purple-950/60 dark:text-purple-200"
                            : item.tipus_item_calendari === "REUNIO_DEMO"
                            ? "bg-emerald-50 text-emerald-900 border-emerald-300 dark:bg-emerald-950/60 dark:text-emerald-200"
                            : item.tipus_item_calendari === "VENCIMENT_DEMO"
                            ? "bg-rose-50 text-rose-900 border-rose-300 dark:bg-rose-950/60 dark:text-rose-200"
                            : "bg-slate-100 text-slate-800 border-slate-300 dark:bg-slate-800 dark:text-slate-200"
                        }`}
                      >
                        {(item.tipus_item_calendari === "EMAIL_CAMPANYA" && item.pas_sequencia === 1) ||
                        item.tipus_item_calendari === "EMAIL_PAS_1"
                          ? "Pas 1 [D0]: 1r Contacte (Gatekeeper -> PWA + Telegram)"
                          : (item.tipus_item_calendari === "EMAIL_CAMPANYA" && item.pas_sequencia === 2) ||
                            item.tipus_item_calendari === "EMAIL_PAS_2"
                          ? "Pas 2 [D+4]: Cas d'Èxit Replicable"
                          : (item.tipus_item_calendari === "EMAIL_CAMPANYA" && item.pas_sequencia === 3) ||
                            item.tipus_item_calendari === "EMAIL_PAS_3"
                          ? "Pas 3 [D+8]: Activació Demo Real 7 Dies"
                          : item.tipus_item_calendari === "REUNIO_DEMO"
                          ? "Reunió Demo Agendada"
                          : item.tipus_item_calendari === "SEGUIMENT_CALENDARI"
                          ? "Seguiment Comercial (Objecció Temps)"
                          : item.tipus_item_calendari === "RESPOSTA_INBOUND"
                          ? "Resposta Entrant (Inbound)"
                          : "Caducitat Demo 7 Dies"}
                      </span>

                      {/* Estat de l'esdeveniment */}
                      {item.pendent_aprovacio ? (
                        <span className="px-2 py-0.5 rounded-full bg-amber-500 text-slate-950 text-[10px] font-bold animate-pulse">
                          ⚠️ Pendent d'Aprovació Avui
                        </span>
                      ) : item.estat_enviament === "APROVAT_ENVIAT" || item.estat_enviament === "ENVIAT" ? (
                        <span className="px-2 py-0.5 rounded-full bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300 text-[10px] font-bold">
                          ✓ Enviat
                        </span>
                      ) : item.estat_enviament === "PAUSAT_PER_RESPOSTA" ? (
                        <span className="px-2 py-0.5 rounded-full bg-blue-100 dark:bg-blue-950 text-blue-800 dark:text-blue-300 text-[10px] font-bold">
                          Pausat per Resposta Inbound
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 text-[10px] font-bold">
                          {item.estat_enviament}
                        </span>
                      )}
                    </div>

                    <div className="flex items-center gap-2 text-xs text-slate-500 font-mono">
                      <CalendarClock className="w-3.5 h-3.5" />
                      <span>
                        Programat per:{" "}
                        {new Date(item.data_programada).toLocaleDateString("ca-ES", {
                          day: "2-digit",
                          month: "2-digit",
                          year: "numeric",
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </span>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-12 gap-4 pt-3">
                    {/* Dades del Prospecte */}
                    <div className="md:col-span-4 space-y-1">
                      <div className="font-bold text-xs text-slate-900 dark:text-white flex items-center gap-1.5">
                        <Building2 className="w-3.5 h-3.5 text-indigo-500" />
                        <span>{item.nom_empresa}</span>
                      </div>
                      <div className="text-[11px] text-slate-600 dark:text-slate-400">
                        {item.nom_contacte} • <span className="font-mono">{item.destinatari}</span>
                      </div>
                      <div className="text-[10px] font-mono text-slate-400">
                        Vertical: {item.vertical} {item.telefon && `• Tel: ${item.telefon}`}
                      </div>
                    </div>

                    {/* Assumpte i Cos */}
                    <div className="md:col-span-5 space-y-1">
                      <div className="text-xs font-semibold text-slate-800 dark:text-slate-200">
                        Assumpte: {item.assumpte}
                      </div>
                      <p className="text-[11px] text-slate-500 line-clamp-2 italic">"{item.cos_text}"</p>
                      <div className="text-[10px] font-mono text-slate-400">
                        Remitent oficial: <strong>tecnic@sevalor.net</strong>
                      </div>
                    </div>

                    {/* Botons d'Acció HITL */}
                    <div className="md:col-span-3 flex flex-col justify-center items-end gap-2">
                      {item.estat_enviament === "ESBORRANY_PROGRAMAT" && (
                        <>
                          <button
                            onClick={() => handleAprovarIEnviarCorreu(item.id)}
                            disabled={enviantCorreuId === item.id}
                            className="w-full sm:w-auto px-3 py-1.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-bold flex items-center justify-center gap-1.5 shadow-sm transition-all"
                          >
                            <Send className="w-3 h-3" />
                            <span>
                              {enviantCorreuId === item.id ? "Enviant..." : "Aprovar i Enviar des de tecnic@sevalor.net"}
                            </span>
                          </button>

                          <button
                            onClick={() =>
                              setModalEditarCorreu({
                                open: true,
                                item: item,
                                assumpte: item.assumpte,
                                cos: item.cos_text,
                                dataProgramada: item.data_programada.slice(0, 16),
                              })
                            }
                            className="px-3 py-1 rounded-lg border border-slate-200 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300 text-xs font-semibold flex items-center gap-1.5"
                          >
                            <Edit className="w-3 h-3" />
                            <span>Revisar / Editar Esborrany</span>
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      ) : (
        /* ============================================================
           PESTANYA 4: TAULA DE PROSPECTES / LEADS
           ============================================================ */
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
                      <td className="py-3 px-4">
                        <div className="font-bold text-slate-900 dark:text-white">{l.nom_empresa}</div>
                        {l.es_tancament_replicable && (
                          <span className="text-[10px] text-emerald-600 dark:text-emerald-400 font-semibold flex items-center gap-1 mt-0.5">
                            <Award className="w-3 h-3" /> Cas Replicable (Lookalike)
                          </span>
                        )}
                      </td>
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
                        <div className="flex items-center justify-end gap-1.5">
                          <button
                            onClick={() => obrirDetallLead(l.id)}
                            className="px-2.5 py-1 rounded-lg bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 text-xs font-semibold"
                          >
                            Veure Fitxa
                          </button>
                          <button
                            title="Editar Prospecte"
                            onClick={() => obrirModalEditarLead(l)}
                            className="p-1.5 rounded-lg bg-indigo-50 hover:bg-indigo-100 dark:bg-indigo-950/50 dark:hover:bg-indigo-900/70 text-indigo-600 dark:text-indigo-400"
                          >
                            <Edit className="w-3.5 h-3.5" />
                          </button>
                          <button
                            title="Eliminar Prospecte"
                            onClick={() => handleEliminarLead(l.id, l.nom_empresa)}
                            className="p-1.5 rounded-lg bg-rose-50 hover:bg-rose-100 dark:bg-rose-950/50 dark:hover:bg-rose-900/70 text-rose-600 dark:text-rose-400"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ============================================================
          MODAL DETALL LEAD & GESTIÓ DEMO 7 DIES + CORREUS
          ============================================================ */}
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
                    {leadDetall?.carrec_contacte && <span>({leadDetall.carrec_contacte})</span>}
                    <span>•</span>
                    <span>{leadDetall?.email}</span>
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-2">
                {leadDetall && (
                  <>
                    <button
                      type="button"
                      onClick={() => obrirModalEditarLead(leadDetall)}
                      className="px-3 py-1.5 rounded-xl bg-indigo-50 hover:bg-indigo-100 dark:bg-indigo-950/60 dark:hover:bg-indigo-900/80 text-indigo-700 dark:text-indigo-300 text-xs font-semibold flex items-center gap-1.5 transition-colors"
                    >
                      <Edit className="w-3.5 h-3.5" />
                      <span>Editar Lead</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => handleEliminarLead(leadDetall.id, leadDetall.nom_empresa)}
                      className="px-3 py-1.5 rounded-xl bg-rose-50 hover:bg-rose-100 dark:bg-rose-950/60 dark:hover:bg-rose-900/80 text-rose-700 dark:text-rose-300 text-xs font-semibold flex items-center gap-1.5 transition-colors"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                      <span>Eliminar</span>
                    </button>
                  </>
                )}
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
                  {/* Columna Esquerra: Dades del Lead & Conversió */}
                  <div className="space-y-4">
                    <div className="p-4 rounded-2xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800 space-y-3">
                      <h4 className="text-xs font-bold text-slate-900 dark:text-white uppercase tracking-wider">
                        Dades de Qualificació
                      </h4>

                      <div>
                        <label className="text-[11px] text-slate-500">Vertical (Configurable / 100% Oberta)</label>
                        <input
                          type="text"
                          value={demoVertical}
                          onChange={(e) => setDemoVertical(e.target.value)}
                          placeholder="ex: CampoPro, Climatització industrial..."
                          className="w-full mt-1 px-3 py-1.5 text-xs rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 font-semibold text-slate-900 dark:text-white"
                        />
                      </div>

                      <div>
                        <label className="text-[11px] text-slate-500">Operaris Estimats & Score IA</label>
                        <div className="text-xs font-bold font-mono mt-0.5 text-slate-900 dark:text-white">
                          {leadDetall?.operaris_estimats} operaris • Score: {leadDetall?.score_qualificacio ?? 0}/100
                        </div>
                      </div>

                      {(leadDetall?.cif || leadDetall?.web_url || leadDetall?.domini_normalitzat) && (
                        <div>
                          <label className="text-[11px] text-slate-500">CIF & Enllaços Comprobables</label>
                          <div className="text-xs font-mono mt-0.5 text-slate-900 dark:text-white">
                            {leadDetall?.cif || "Sense CIF"}
                          </div>
                          {(() => {
                            const lUrls = extreureUrlsFonts(
                              leadDetall?.fonts_investigades,
                              leadDetall?.web_url,
                              leadDetall?.fonts_urls
                            );
                            return (
                              <div className="flex flex-wrap gap-1.5 mt-1.5">
                                {lUrls.web && (
                                  <a
                                    href={lUrls.web}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-blue-50 hover:bg-blue-100 dark:bg-blue-950/60 text-blue-700 dark:text-blue-300 font-mono text-[10px] font-bold hover:underline"
                                  >
                                    <Globe className="w-3 h-3" /> Web <ExternalLink className="w-2.5 h-2.5" />
                                  </a>
                                )}
                                {lUrls.linkedin && (
                                  <a
                                    href={lUrls.linkedin}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-sky-50 hover:bg-sky-100 dark:bg-sky-950/60 text-sky-700 dark:text-sky-300 font-mono text-[10px] font-bold hover:underline"
                                  >
                                    <Linkedin className="w-3 h-3" /> LinkedIn <ExternalLink className="w-2.5 h-2.5" />
                                  </a>
                                )}
                                {lUrls.instagram && (
                                  <a
                                    href={lUrls.instagram}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-pink-50 hover:bg-pink-100 dark:bg-pink-950/60 text-pink-700 dark:text-pink-300 font-mono text-[10px] font-bold hover:underline"
                                  >
                                    <Instagram className="w-3 h-3" /> Instagram <ExternalLink className="w-2.5 h-2.5" />
                                  </a>
                                )}
                                {lUrls.maps && (
                                  <a
                                    href={lUrls.maps}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-amber-50 hover:bg-amber-100 dark:bg-amber-950/60 text-amber-700 dark:text-amber-300 font-mono text-[10px] font-bold hover:underline"
                                  >
                                    <MapPin className="w-3 h-3" /> Maps <ExternalLink className="w-2.5 h-2.5" />
                                  </a>
                                )}
                              </div>
                            );
                          })()}
                        </div>
                      )}

                      {leadDetall?.adreca_fisica && (
                        <div>
                          <label className="text-[11px] text-slate-500">Adreça Física (CP {leadDetall?.codi_postal})</label>
                          <div className="text-xs mt-0.5 text-slate-800 dark:text-slate-200 font-medium">
                            📍 {leadDetall.adreca_fisica}
                          </div>
                        </div>
                      )}

                      {leadDetall?.fita_recent && (
                        <div>
                          <label className="text-[11px] text-slate-500">Fita Multi-Canal Detectada</label>
                          <div className="text-[11px] italic mt-0.5 text-slate-700 dark:text-slate-300">
                            "{leadDetall.fita_recent}"
                          </div>
                        </div>
                      )}

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

                    {/* GESTIÓ DE DEALS / OPORTUNITATS DEL PROSPECTE */}
                    <div className="p-4 rounded-2xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800 space-y-2.5">
                      <div className="flex items-center justify-between">
                        <h4 className="text-xs font-bold text-slate-900 dark:text-white uppercase tracking-wider flex items-center gap-1.5">
                          <Briefcase className="w-3.5 h-3.5 text-indigo-500" />
                          <span>Deals / Oportunitats ({leadDetall?.oportunitats?.length || 0})</span>
                        </h4>
                        <button
                          type="button"
                          onClick={() => obrirModalNouDeal(leadDetall)}
                          className="px-2 py-1 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-[10px] font-bold flex items-center gap-1"
                        >
                          <Plus className="w-3 h-3" />
                          <span>Nou Deal</span>
                        </button>
                      </div>

                      {(!leadDetall?.oportunitats || leadDetall.oportunitats.length === 0) ? (
                        <div className="text-[11px] text-slate-400 py-2 text-center border border-dashed border-slate-200 dark:border-slate-700 rounded-xl">
                          Sense deals al Pipeline.
                        </div>
                      ) : (
                        <div className="space-y-2">
                          {leadDetall.oportunitats.map((opItem: any) => (
                            <div
                              key={opItem.id}
                              className="p-2.5 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 text-xs space-y-1.5"
                            >
                              <div className="font-bold text-slate-900 dark:text-white line-clamp-1">{opItem.titol}</div>
                              <div className="flex items-center justify-between text-[11px] font-mono">
                                <span className="px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 font-semibold">
                                  {opItem.etapa}
                                </span>
                                <span className="font-bold text-indigo-600 dark:text-indigo-400">
                                  {opItem.valor_mensual_estimat} €/m ({opItem.probabilitat_percent}%)
                                </span>
                              </div>
                              <div className="flex items-center justify-end gap-1.5 pt-1 border-t border-slate-100 dark:border-slate-800">
                                <button
                                  type="button"
                                  onClick={() => obrirModalEditarDeal(opItem, leadDetall.nom_empresa)}
                                  className="px-2 py-1 rounded-lg bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 text-[10px] font-semibold flex items-center gap-1"
                                >
                                  <Edit className="w-3 h-3 text-indigo-500" />
                                  <span>Editar Deal</span>
                                </button>
                                <button
                                  type="button"
                                  onClick={() => handleEliminarDeal(opItem.id, opItem.titol)}
                                  className="px-2 py-1 rounded-lg bg-rose-50 hover:bg-rose-100 dark:bg-rose-950/50 dark:hover:bg-rose-900/70 text-rose-600 dark:text-rose-400 text-[10px] font-semibold flex items-center gap-1"
                                >
                                  <Trash2 className="w-3 h-3" />
                                  <span>Eliminar</span>
                                </button>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>

                    {/* BOTÓ T016: REGISTRAR TANCAMENT D'ÈXIT REPLICABLE DES DE LA FITXA DEL PROSPECTE */}
                    {leadDetall?.oportunitats && leadDetall.oportunitats.length > 0 && (
                      <div className="p-4 rounded-2xl bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-900/60 space-y-2">
                        <div className="text-xs font-bold text-emerald-900 dark:text-emerald-200 flex items-center gap-1.5">
                          <Award className="w-4 h-4 text-emerald-600" />
                          <span>Tancament d'Èxit Replicable (GUANYAT)</span>
                        </div>
                        <p className="text-[11px] text-emerald-700 dark:text-emerald-300">
                          Registra la raó per la qual ens ha contractat i activa la cerca d'empreses bessones (Lookalikes).
                        </p>
                        <button
                          type="button"
                          onClick={() => {
                            const opRaw = leadDetall.oportunitats[0];
                            setModalRegistrarExit({
                              open: true,
                              oportunitat: {
                                id: opRaw.id,
                                lead_id: leadDetall.id,
                                nom_empresa: leadDetall.nom_empresa,
                                nom_contacte: leadDetall.nom_contacte,
                                email: leadDetall.email,
                                telefon: leadDetall.telefon,
                                vertical: leadDetall.vertical,
                                titol: opRaw.titol,
                                etapa: opRaw.etapa,
                                valor_mensual_estimat: opRaw.valor_mensual_estimat,
                                valor_ia_setup: opRaw.valor_ia_setup || 0,
                                probabilitat_percent: opRaw.probabilitat_percent,
                                demo_activa: Boolean(leadDetall?.demo?.demo_activa),
                                created_at: opRaw.created_at || leadDetall.created_at,
                              },
                              rao: leadDetall.rao_tancament_exit || "",
                              requisits: `${leadDetall.vertical}, ${leadDetall.operaris_estimats} operaris, gestió sense paper`,
                              replicable: true,
                            });
                          }}
                          className="w-full mt-2 py-2 px-3 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold flex items-center justify-center gap-1.5 shadow-sm transition-colors"
                        >
                          <Award className="w-3.5 h-3.5" />
                          <span>Registrar Tancament d'Èxit Replicable (GUANYAT)</span>
                        </button>
                      </div>
                    )}

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

                  {/* Columna Central & Dreta: Demo + Seqüència Correus + Timeline */}
                  <div className="space-y-4 md:col-span-2">
                    {/* Demo 7 Dies */}
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
                        <div className="space-y-4">
                          <div className="p-3.5 rounded-xl bg-emerald-50 dark:bg-emerald-950/50 border border-emerald-300 text-emerald-900 dark:text-emerald-200 text-xs">
                            <div className="font-bold flex items-center gap-1.5">
                              <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                              <span>Demo activa connectada a la IA central de Sevalor</span>
                            </div>
                            <p className="mt-1 text-[11px] text-emerald-800/90 dark:text-emerald-300/80">
                              Subdomini aïllat a PostgreSQL RLS: <strong>{leadDetall.demo.subdomini}.sevalor.app</strong>.
                            </p>
                          </div>

                          <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 space-y-2.5 text-xs font-mono">
                            <div className="flex items-center justify-between bg-white dark:bg-slate-800 p-2 rounded-lg border border-slate-200 dark:border-slate-700">
                              <div>
                                <span className="text-slate-400">Usuari: </span>
                                <strong>{leadDetall.email}</strong>
                              </div>
                              <button onClick={() => copiarPortapapers(leadDetall.email, "user")}>
                                {copiedKey === "user" ? <Check className="w-3.5 h-3.5 text-emerald-500" /> : <Copy className="w-3.5 h-3.5" />}
                              </button>
                            </div>

                            <div className="flex items-center justify-between bg-white dark:bg-slate-800 p-2 rounded-lg border border-slate-200 dark:border-slate-700">
                              <div>
                                <span className="text-slate-400">Password / PIN: </span>
                                <strong>Password123! / 0000</strong>
                              </div>
                            </div>
                          </div>

                          <button
                            onClick={handleActivarDemo}
                            disabled={activantDemo}
                            className="px-3.5 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 dark:bg-slate-700 text-slate-800 dark:text-slate-200 text-xs font-semibold flex items-center gap-1.5 transition-colors"
                          >
                            <RotateCcw className="w-3.5 h-3.5" />
                            <span>Prorrogar 7 dies més</span>
                          </button>
                        </div>
                      ) : (
                        <div className="space-y-4">
                          <p className="text-xs text-slate-600 dark:text-slate-300">
                            Crea automàticament un tenant aïllat a PostgreSQL amb dades reals de prova de la vertical{" "}
                            <strong>{demoVertical}</strong>, connectat a la IA central de demos (7 dies).
                          </p>

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

                    {/* Campanya de 3 Emails del Lead (T015 - Revisió, edició i enviament des de la fitxa del prospecte) */}
                    {leadCorreus.length > 0 && (
                      <div className="p-5 rounded-2xl border bg-white dark:bg-slate-800/60 border-slate-200 dark:border-slate-700 shadow-sm space-y-3">
                        <h4 className="text-xs font-bold text-slate-900 dark:text-white uppercase tracking-wider flex items-center gap-1.5">
                          <Mail className="w-4 h-4 text-indigo-500" />
                          <span>Campanya de 3 Emails (D0, D+4, D+8)</span>
                        </h4>

                        <div className="space-y-2.5">
                          {leadCorreus.map((c: any) => (
                            <div
                              key={c.id}
                              className="p-3 rounded-xl bg-slate-50 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800 text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-3"
                            >
                              <div className="space-y-0.5">
                                <div className="font-semibold text-slate-900 dark:text-white">
                                  Pas {c.pas_sequencia ?? 1} [{c.tempo_dies_offset === 0 ? "D0" : `D+${c.tempo_dies_offset}`}]:{" "}
                                  {c.assumpte}
                                </div>
                                <div className="text-[10px] text-slate-400 font-mono">
                                  Estat: {c.estat_enviament} • Programat: {new Date(c.data_programada).toLocaleDateString("ca-ES")}
                                </div>
                              </div>

                              {c.estat_enviament === "ESBORRANY_PROGRAMAT" && (
                                <div className="flex items-center gap-2 shrink-0">
                                  <button
                                    type="button"
                                    onClick={() =>
                                      setModalEditarCorreu({
                                        open: true,
                                        item: {
                                          ...c,
                                          lead_id: leadDetall.id,
                                          nom_empresa: leadDetall.nom_empresa,
                                          vertical: leadDetall.vertical,
                                          nom_contacte: leadDetall.nom_contacte,
                                          es_avui: false,
                                          pendent_aprovacio: true,
                                          estat_calendari: c.estat_enviament,
                                        },
                                        assumpte: c.assumpte,
                                        cos: c.cos_text,
                                        dataProgramada: c.data_programada.slice(0, 16),
                                      })
                                    }
                                    className="px-2.5 py-1 rounded-lg border border-slate-200 dark:border-slate-700 hover:bg-slate-200 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300 text-[11px] font-semibold flex items-center gap-1"
                                  >
                                    <Edit className="w-3 h-3" />
                                    <span>Revisar / Editar</span>
                                  </button>

                                  <button
                                    type="button"
                                    onClick={() => handleAprovarIEnviarCorreu(c.id)}
                                    disabled={enviantCorreuId === c.id}
                                    className="px-2.5 py-1 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-[11px] font-bold flex items-center gap-1"
                                  >
                                    <Send className="w-3 h-3" />
                                    <span>
                                      {enviantCorreuId === c.id ? "Enviant..." : "Aprovar i Enviar des de tecnic@sevalor.net"}
                                    </span>
                                  </button>
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Timeline d'Interaccions & Notes */}
                    <div className="p-5 rounded-2xl border bg-white dark:bg-slate-800/60 border-slate-200 dark:border-slate-700 shadow-sm space-y-4">
                      <h4 className="text-xs font-bold text-slate-900 dark:text-white uppercase tracking-wider flex items-center gap-1.5">
                        <MessageSquare className="w-4 h-4 text-indigo-500" />
                        <span>Timeline d'Interaccions & Notes Comercials</span>
                      </h4>

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

                      <div className="space-y-3 pt-2 max-h-48 overflow-y-auto">
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

      {/* ============================================================
          MODAL CORREGIR CRITERI (T014 - JUSTIFICACIÓ OBLIGATÒRIA >= 10)
          ============================================================ */}
      {modalCorregir.open && modalCorregir.candidat && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in">
          <div className="w-full max-w-lg bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-2xl overflow-hidden space-y-4">
            <div className="p-6 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between bg-slate-50/50 dark:bg-slate-800/30">
              <h3 className="text-base font-bold text-slate-900 dark:text-white flex items-center gap-2">
                <Sliders className="w-5 h-5 text-indigo-600" />
                <span>Corregir Criteri de Prospecció (Doble Bucle)</span>
              </h3>
              <button
                onClick={() => setModalCorregir({ ...modalCorregir, open: false })}
                className="text-slate-400 hover:text-slate-600"
              >
                ✕
              </button>
            </div>

            <div className="p-6 space-y-4">
              <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 text-xs space-y-1">
                <div className="font-bold text-slate-900 dark:text-white">
                  Empresa: {modalCorregir.candidat.nom_empresa}
                </div>
                <div className="text-slate-500 font-mono">
                  Decisió IA Original: {modalCorregir.candidat.estat_decisio} (Score: {modalCorregir.candidat.score}/100)
                </div>
                {modalCorregir.candidat.motiu_detallat_ia && (
                  <div className="text-[11px] text-slate-600 dark:text-slate-400 italic">
                    "{modalCorregir.candidat.motiu_detallat_ia}"
                  </div>
                )}
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">Nova Decisió Humana *</label>
                <div className="grid grid-cols-2 gap-3 mt-1.5">
                  <button
                    type="button"
                    onClick={() => setModalCorregir({ ...modalCorregir, novaDecisio: "SELECCIONAT" })}
                    className={`py-2 px-3 rounded-xl border text-xs font-bold transition-all ${
                      modalCorregir.novaDecisio === "SELECCIONAT"
                        ? "bg-emerald-600 text-white border-emerald-600 shadow-sm"
                        : "bg-slate-50 dark:bg-slate-800 border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300"
                    }`}
                  >
                    ✓ SELECCIONAT
                  </button>

                  <button
                    type="button"
                    onClick={() => setModalCorregir({ ...modalCorregir, novaDecisio: "DESCARTAT" })}
                    className={`py-2 px-3 rounded-xl border text-xs font-bold transition-all ${
                      modalCorregir.novaDecisio === "DESCARTAT"
                        ? "bg-rose-600 text-white border-rose-600 shadow-sm"
                        : "bg-slate-50 dark:bg-slate-800 border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300"
                    }`}
                  >
                    ✕ DESCARTAT
                  </button>
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between">
                  <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                    Justificació Humana Obligatòria (Mínim 10 caràcters) *
                  </label>
                  <span
                    className={`text-[11px] font-mono font-bold ${
                      modalCorregir.motiu.trim().length >= 10 ? "text-emerald-600" : "text-rose-500"
                    }`}
                  >
                    {modalCorregir.motiu.trim().length} / 10 mín.
                  </span>
                </div>
                <textarea
                  required
                  rows={3}
                  placeholder="Per què canvies el criteri de la IA? (ex: Són una botiga de venda al detall sense operaris al terreny / Tenen 8 furgonetes d'instal·lació de reg confirmades a Instagram)..."
                  value={modalCorregir.motiu}
                  onChange={(e) => setModalCorregir({ ...modalCorregir, motiu: e.target.value })}
                  className="w-full mt-1 px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
                <p className="text-[10px] text-slate-400 mt-1">
                  Aquesta justificació alimentarà el Doble Bucle d'Aprenentatge (Bucle 1: Descart Humà) per no repetir aquest error en futures cerques.
                </p>
              </div>

              <div className="pt-3 flex items-center justify-end gap-2 border-t border-slate-100 dark:border-slate-800">
                <button
                  type="button"
                  onClick={() => setModalCorregir({ ...modalCorregir, open: false })}
                  className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-500 hover:text-slate-700"
                >
                  Cancel·lar
                </button>
                <button
                  type="button"
                  onClick={handleGuardarCorreccioCriteri}
                  disabled={guardantCorreccio || modalCorregir.motiu.trim().length < 10}
                  className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-bold shadow-sm"
                >
                  {guardantCorreccio ? "Guardant regla..." : "Guardar Correcció & Aprendre"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ============================================================
          MODAL REGISTRAR TANCAMENT GUANYAT REPLICABLE (T016)
          ============================================================ */}
      {modalRegistrarExit.open && modalRegistrarExit.oportunitat && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in">
          <div className="w-full max-w-lg bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-2xl overflow-hidden space-y-4">
            <div className="p-6 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between bg-emerald-50/50 dark:bg-emerald-950/30">
              <h3 className="text-base font-bold text-slate-900 dark:text-white flex items-center gap-2">
                <Award className="w-5 h-5 text-emerald-600" />
                <span>🏆 Registrar Tancament d'Èxit Replicable (GUANYAT)</span>
              </h3>
              <button
                onClick={() => setModalRegistrarExit({ ...modalRegistrarExit, open: false })}
                className="text-slate-400 hover:text-slate-600"
              >
                ✕
              </button>
            </div>

            <div className="p-6 space-y-4">
              <div className="p-3.5 rounded-xl bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-300 dark:border-emerald-800 text-xs space-y-1">
                <div className="font-bold text-emerald-900 dark:text-emerald-200">
                  Empresa: {modalRegistrarExit.oportunitat.nom_empresa}
                </div>
                <div className="text-emerald-700 dark:text-emerald-300 font-mono">
                  Valor MRR: {modalRegistrarExit.oportunitat.valor_mensual_estimat} €/mes • Vertical:{" "}
                  {modalRegistrarExit.oportunitat.vertical}
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between">
                  <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                    Raó del Tancament d'Èxit (Per què ens han contractat?) *
                  </label>
                  <span
                    className={`text-[11px] font-mono font-bold ${
                      modalRegistrarExit.rao.trim().length >= 5 ? "text-emerald-600" : "text-rose-500"
                    }`}
                  >
                    {modalRegistrarExit.rao.trim().length} / 5 mín.
                  </span>
                </div>
                <textarea
                  required
                  rows={3}
                  placeholder="ex: Tenien 12 instal·ladors i perden 2 hores diàries fent albarans a mà; la PWA mòbil amb el Bot de Telegram els ha resolt el problema en només 4 dies..."
                  value={modalRegistrarExit.rao}
                  onChange={(e) => setModalRegistrarExit({ ...modalRegistrarExit, rao: e.target.value })}
                  className="w-full mt-1 px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-emerald-500"
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                  Requisits del Perfil d'Empresa Replicable
                </label>
                <input
                  type="text"
                  placeholder="ex: quadrilla > 8 operaris, mobilitat tècnica dispersa, gestió d'albarans sense paper"
                  value={modalRegistrarExit.requisits}
                  onChange={(e) => setModalRegistrarExit({ ...modalRegistrarExit, requisits: e.target.value })}
                  className="w-full mt-1 px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800"
                />
              </div>

              <div className="flex items-center gap-2 pt-2">
                <input
                  type="checkbox"
                  id="replicable-toggle"
                  checked={modalRegistrarExit.replicable}
                  onChange={(e) => setModalRegistrarExit({ ...modalRegistrarExit, replicable: e.target.checked })}
                  className="w-4 h-4 rounded border-slate-300 text-emerald-600 focus:ring-emerald-500"
                />
                <label htmlFor="replicable-toggle" className="text-xs font-medium text-slate-700 dark:text-slate-300">
                  Activar cerca d'empreses bessones (Lookalikes Boost ≥ 85) al Doble Bucle d'Aprenentatge
                </label>
              </div>

              <div className="pt-3 flex items-center justify-end gap-2 border-t border-slate-100 dark:border-slate-800">
                <button
                  type="button"
                  onClick={() => setModalRegistrarExit({ ...modalRegistrarExit, open: false })}
                  className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-500 hover:text-slate-700"
                >
                  Cancel·lar
                </button>
                <button
                  type="button"
                  onClick={handleGuardarTancamentExit}
                  disabled={guardantExit || modalRegistrarExit.rao.trim().length < 5}
                  className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-xs font-bold shadow-sm"
                >
                  {guardantExit ? "Registrant tancament..." : "🏆 Confirmar GUANYAT & Guardar Patró"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ============================================================
          MODAL REVISAR / EDITAR ESBORRANY DE CORREU (T015)
          ============================================================ */}
      {modalEditarCorreu.open && modalEditarCorreu.item && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in">
          <div className="w-full max-w-2xl bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-2xl overflow-hidden space-y-4">
            <div className="p-6 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between bg-slate-50/50 dark:bg-slate-800/30">
              <h3 className="text-base font-bold text-slate-900 dark:text-white flex items-center gap-2">
                <Edit className="w-5 h-5 text-indigo-600" />
                <span>Revisar / Editar Esborrany de Correu</span>
              </h3>
              <button
                onClick={() => setModalEditarCorreu({ ...modalEditarCorreu, open: false })}
                className="text-slate-400 hover:text-slate-600"
              >
                ✕
              </button>
            </div>

            <div className="p-6 space-y-4">
              <div className="grid grid-cols-2 gap-3 text-xs font-mono">
                <div className="p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700">
                  <span className="text-slate-400">Remitent oficial: </span>
                  <strong>tecnic@sevalor.net</strong>
                </div>
                <div className="p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700">
                  <span className="text-slate-400">Destinatari: </span>
                  <strong>{modalEditarCorreu.item.destinatari}</strong>
                </div>
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">Assumpte del Correu</label>
                <input
                  type="text"
                  required
                  value={modalEditarCorreu.assumpte}
                  onChange={(e) => setModalEditarCorreu({ ...modalEditarCorreu, assumpte: e.target.value })}
                  className="w-full mt-1 px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800"
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                  Cos del Correu (Canals exclusius: PWA per a operaris i Bot Oficial de Telegram)
                </label>
                <textarea
                  required
                  rows={8}
                  value={modalEditarCorreu.cos}
                  onChange={(e) => setModalEditarCorreu({ ...modalEditarCorreu, cos: e.target.value })}
                  className="w-full mt-1 px-3 py-2 text-xs font-mono rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800"
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">Data i Hora Programada</label>
                <input
                  type="datetime-local"
                  value={modalEditarCorreu.dataProgramada}
                  onChange={(e) => setModalEditarCorreu({ ...modalEditarCorreu, dataProgramada: e.target.value })}
                  className="w-full mt-1 px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 font-mono"
                />
              </div>

              <div className="pt-3 flex items-center justify-end gap-2 border-t border-slate-100 dark:border-slate-800">
                <button
                  type="button"
                  onClick={() => setModalEditarCorreu({ ...modalEditarCorreu, open: false })}
                  className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-500 hover:text-slate-700"
                >
                  Cancel·lar
                </button>
                <button
                  type="button"
                  onClick={handleGuardarEsborranyCorreu}
                  disabled={guardantEsborrany}
                  className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold shadow-sm"
                >
                  {guardantEsborrany ? "Desant canvis..." : "Guardar Esborrany"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ============================================================
          MODAL NOU ESDEVENIMENT MANUAL AL CALENDARI (T015)
          ============================================================ */}
      {modalNouEsdeveniment.open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in">
          <div className="w-full max-w-lg bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-2xl overflow-hidden space-y-4">
            <div className="p-6 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between bg-slate-50/50 dark:bg-slate-800/30">
              <h3 className="text-base font-bold text-slate-900 dark:text-white flex items-center gap-2">
                <CalendarClock className="w-5 h-5 text-indigo-600" />
                <span>Afegir Esdeveniment Manual al Calendari</span>
              </h3>
              <button
                onClick={() => setModalNouEsdeveniment({ ...modalNouEsdeveniment, open: false })}
                className="text-slate-400 hover:text-slate-600"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleCrearEsdevenimentManual} className="p-6 space-y-4">
              <div>
                <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">Prospecte Associat *</label>
                <select
                  required
                  value={modalNouEsdeveniment.leadId}
                  onChange={(e) => setModalNouEsdeveniment({ ...modalNouEsdeveniment, leadId: e.target.value })}
                  className="w-full mt-1 px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white font-semibold"
                >
                  <option value="">-- Selecciona un prospecte --</option>
                  {leads.map((l) => (
                    <option key={l.id} value={l.id}>
                      {l.nom_empresa} ({l.nom_contacte})
                    </option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">Tipus d'Esdeveniment</label>
                  <select
                    value={modalNouEsdeveniment.tipus}
                    onChange={(e) =>
                      setModalNouEsdeveniment({
                        ...modalNouEsdeveniment,
                        tipus: e.target.value as "SEGUIMENT_CALENDARI" | "REUNIO_DEMO" | "NOTA",
                      })
                    }
                    className="w-full mt-1 px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 font-semibold"
                  >
                    <option value="SEGUIMENT_CALENDARI">Seguiment Comercial (Objecció Temps)</option>
                    <option value="REUNIO_DEMO">Reunió de Demo (Presentació)</option>
                    <option value="NOTA">Nota de Calendari</option>
                  </select>
                </div>

                <div>
                  <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">Data i Hora *</label>
                  <input
                    type="datetime-local"
                    required
                    value={modalNouEsdeveniment.dataProgramada}
                    onChange={(e) => setModalNouEsdeveniment({ ...modalNouEsdeveniment, dataProgramada: e.target.value })}
                    className="w-full mt-1 px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 font-mono"
                  />
                </div>
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">Títol de l'Esdeveniment *</label>
                <input
                  type="text"
                  required
                  placeholder="ex: Trucada de seguiment sol·licitada pel client"
                  value={modalNouEsdeveniment.titol}
                  onChange={(e) => setModalNouEsdeveniment({ ...modalNouEsdeveniment, titol: e.target.value })}
                  className="w-full mt-1 px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800"
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">Descripció / Detalls</label>
                <textarea
                  rows={3}
                  placeholder="Anotacions sobre el motiu de la reunió o seguiment..."
                  value={modalNouEsdeveniment.descripcio}
                  onChange={(e) => setModalNouEsdeveniment({ ...modalNouEsdeveniment, descripcio: e.target.value })}
                  className="w-full mt-1 px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800"
                />
              </div>

              <div className="pt-3 flex items-center justify-end gap-2 border-t border-slate-100 dark:border-slate-800">
                <button
                  type="button"
                  onClick={() => setModalNouEsdeveniment({ ...modalNouEsdeveniment, open: false })}
                  className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-500 hover:text-slate-700"
                >
                  Cancel·lar
                </button>
                <button
                  type="submit"
                  disabled={guardantNouEsdeveniment}
                  className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold shadow-sm"
                >
                  {guardantNouEsdeveniment ? "Creant..." : "Afegir al Calendari"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ============================================================
          MODAL NOU PROSPECTE (LEAD MANUAL)
          ============================================================ */}
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
                  <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">Vertical (100% Oberta)</label>
                  <input
                    type="text"
                    required
                    placeholder="ex: CampoPro, Climatització industrial..."
                    value={nouLead.vertical}
                    onChange={(e) => setNouLead({ ...nouLead, vertical: e.target.value })}
                    className="w-full mt-1 px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 font-semibold"
                  />
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

      {/* ============================================================
          MODAL EDITAR PROSPECTE (LEAD)
          ============================================================ */}
      {modalEditarLead.open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in">
          <div className="w-full max-w-2xl bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-2xl overflow-hidden max-h-[90vh] flex flex-col">
            <div className="p-6 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between bg-slate-50/50 dark:bg-slate-800/30">
              <h3 className="text-base font-bold text-slate-900 dark:text-white flex items-center gap-2">
                <Edit className="w-5 h-5 text-indigo-600" />
                <span>Editar Prospecte (Lead)</span>
              </h3>
              <button
                onClick={() => setModalEditarLead({ ...modalEditarLead, open: false })}
                className="text-slate-400 hover:text-slate-600"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleGuardarEditarLead} className="p-6 space-y-4 overflow-y-auto">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">Nom de l'Empresa *</label>
                  <input
                    type="text"
                    required
                    value={modalEditarLead.nom_empresa}
                    onChange={(e) => setModalEditarLead({ ...modalEditarLead, nom_empresa: e.target.value })}
                    className="w-full mt-1 px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800"
                  />
                </div>
                <div>
                  <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">CIF / NIF</label>
                  <input
                    type="text"
                    placeholder="B12345678"
                    value={modalEditarLead.cif}
                    onChange={(e) => setModalEditarLead({ ...modalEditarLead, cif: e.target.value })}
                    className="w-full mt-1 px-3 py-2 text-xs font-mono rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                    Nom del Gatekeeper (Persona Real) *
                  </label>
                  <input
                    type="text"
                    required
                    value={modalEditarLead.nom_contacte}
                    onChange={(e) => setModalEditarLead({ ...modalEditarLead, nom_contacte: e.target.value })}
                    className="w-full mt-1 px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800"
                  />
                </div>
                <div>
                  <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">Càrrec del Decisor</label>
                  <input
                    type="text"
                    placeholder="Gerent / Director Tècnic"
                    value={modalEditarLead.carrec_contacte}
                    onChange={(e) => setModalEditarLead({ ...modalEditarLead, carrec_contacte: e.target.value })}
                    className="w-full mt-1 px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">Email *</label>
                  <input
                    type="email"
                    required
                    value={modalEditarLead.email}
                    onChange={(e) => setModalEditarLead({ ...modalEditarLead, email: e.target.value })}
                    className="w-full mt-1 px-3 py-2 text-xs font-mono rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800"
                  />
                </div>
                <div>
                  <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">Telèfon</label>
                  <input
                    type="tel"
                    placeholder="+34600123456"
                    value={modalEditarLead.telefon}
                    onChange={(e) => setModalEditarLead({ ...modalEditarLead, telefon: e.target.value })}
                    className="w-full mt-1 px-3 py-2 text-xs font-mono rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div className="sm:col-span-2">
                  <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">Adreça Física Real</label>
                  <input
                    type="text"
                    placeholder="Pol. Ind. El Segre, C/ Josep Baró, 14, 25001 Lleida"
                    value={modalEditarLead.adreca_fisica}
                    onChange={(e) => setModalEditarLead({ ...modalEditarLead, adreca_fisica: e.target.value })}
                    className="w-full mt-1 px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800"
                  />
                </div>
                <div>
                  <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">Codi Postal</label>
                  <input
                    type="text"
                    placeholder="25001"
                    value={modalEditarLead.codi_postal}
                    onChange={(e) => setModalEditarLead({ ...modalEditarLead, codi_postal: e.target.value })}
                    className="w-full mt-1 px-3 py-2 text-xs font-mono rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div>
                  <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">Web URL</label>
                  <input
                    type="text"
                    placeholder="https://empresa.cat"
                    value={modalEditarLead.web_url}
                    onChange={(e) => setModalEditarLead({ ...modalEditarLead, web_url: e.target.value })}
                    className="w-full mt-1 px-3 py-2 text-xs font-mono rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800"
                  />
                </div>
                <div>
                  <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">Vertical *</label>
                  <input
                    type="text"
                    required
                    value={modalEditarLead.vertical}
                    onChange={(e) => setModalEditarLead({ ...modalEditarLead, vertical: e.target.value })}
                    className="w-full mt-1 px-3 py-2 text-xs font-semibold rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800"
                  />
                </div>
                <div>
                  <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">Operaris Estimats</label>
                  <input
                    type="number"
                    min={1}
                    max={500}
                    value={modalEditarLead.operaris_estimats}
                    onChange={(e) => setModalEditarLead({ ...modalEditarLead, operaris_estimats: Number(e.target.value) })}
                    className="w-full mt-1 px-3 py-2 text-xs font-mono rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">Estat de Qualificació</label>
                  <select
                    value={modalEditarLead.estat_qualificacio}
                    onChange={(e) => setModalEditarLead({ ...modalEditarLead, estat_qualificacio: e.target.value })}
                    className="w-full mt-1 px-3 py-2 text-xs font-semibold rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800"
                  >
                    <option value="NOU">NOU</option>
                    <option value="QUALIFICAT">QUALIFICAT</option>
                    <option value="DEMO_ACTIVA">DEMO_ACTIVA</option>
                    <option value="CONVERTIT">CONVERTIT</option>
                    <option value="DESCARTAT">DESCARTAT</option>
                  </select>
                </div>
                <div>
                  <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">Notes</label>
                  <input
                    type="text"
                    value={modalEditarLead.notes}
                    onChange={(e) => setModalEditarLead({ ...modalEditarLead, notes: e.target.value })}
                    className="w-full mt-1 px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800"
                  />
                </div>
              </div>

              <div className="pt-4 flex items-center justify-between gap-2 border-t border-slate-100 dark:border-slate-800">
                <button
                  type="button"
                  onClick={() => handleEliminarLead(modalEditarLead.leadId, modalEditarLead.nom_empresa)}
                  className="px-3.5 py-2 rounded-xl bg-rose-50 hover:bg-rose-100 dark:bg-rose-950/60 text-rose-700 dark:text-rose-300 text-xs font-bold flex items-center gap-1.5"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                  <span>Eliminar Prospecte</span>
                </button>

                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setModalEditarLead({ ...modalEditarLead, open: false })}
                    className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-500 hover:text-slate-700"
                  >
                    Cancel·lar
                  </button>
                  <button
                    type="submit"
                    disabled={guardantEditarLead}
                    className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-bold shadow-sm"
                  >
                    {guardantEditarLead ? "Desant..." : "Guardar Canvis"}
                  </button>
                </div>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ============================================================
          MODAL EDITAR / CREAR DEAL (OPORTUNITAT DEL PIPELINE)
          ============================================================ */}
      {modalEditarDeal.open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in">
          <div className="w-full max-w-lg bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-2xl overflow-hidden">
            <div className="p-6 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between bg-slate-50/50 dark:bg-slate-800/30">
              <h3 className="text-base font-bold text-slate-900 dark:text-white flex items-center gap-2">
                <Briefcase className="w-5 h-5 text-indigo-600" />
                <span>
                  {modalEditarDeal.mode === "create"
                    ? `Nou Deal per a ${modalEditarDeal.nomEmpresa}`
                    : `Editar Deal (${modalEditarDeal.nomEmpresa})`}
                </span>
              </h3>
              <button
                onClick={() => setModalEditarDeal({ ...modalEditarDeal, open: false })}
                className="text-slate-400 hover:text-slate-600"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleGuardarDeal} className="p-6 space-y-4">
              <div>
                <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">Títol del Deal / Oportunitat *</label>
                <input
                  type="text"
                  required
                  value={modalEditarDeal.titol}
                  onChange={(e) => setModalEditarDeal({ ...modalEditarDeal, titol: e.target.value })}
                  className="w-full mt-1 px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800"
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">Etapa del Pipeline *</label>
                <select
                  value={modalEditarDeal.etapa}
                  onChange={(e) => setModalEditarDeal({ ...modalEditarDeal, etapa: e.target.value })}
                  className="w-full mt-1 px-3 py-2 text-xs font-semibold rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800"
                >
                  {Object.entries(ETAPA_LABELS).map(([k, v]) => (
                    <option key={k} value={k}>
                      {v.label} — {v.desc}
                    </option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">MRR (€/mes)</label>
                  <input
                    type="number"
                    min={0}
                    step="0.01"
                    value={modalEditarDeal.valor_mensual_estimat}
                    onChange={(e) =>
                      setModalEditarDeal({ ...modalEditarDeal, valor_mensual_estimat: Number(e.target.value) })
                    }
                    className="w-full mt-1 px-3 py-2 text-xs font-mono rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800"
                  />
                </div>
                <div>
                  <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">Setup IA (€)</label>
                  <input
                    type="number"
                    min={0}
                    step="0.01"
                    value={modalEditarDeal.valor_ia_setup}
                    onChange={(e) => setModalEditarDeal({ ...modalEditarDeal, valor_ia_setup: Number(e.target.value) })}
                    className="w-full mt-1 px-3 py-2 text-xs font-mono rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800"
                  />
                </div>
                <div>
                  <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">Probabilitat (%)</label>
                  <input
                    type="number"
                    min={0}
                    max={100}
                    value={modalEditarDeal.probabilitat_percent}
                    onChange={(e) =>
                      setModalEditarDeal({ ...modalEditarDeal, probabilitat_percent: Number(e.target.value) })
                    }
                    className="w-full mt-1 px-3 py-2 text-xs font-mono rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800"
                  />
                </div>
              </div>

              <div className="pt-4 flex items-center justify-between gap-2 border-t border-slate-100 dark:border-slate-800">
                {modalEditarDeal.mode === "edit" ? (
                  <button
                    type="button"
                    onClick={() => {
                      const idToDel = modalEditarDeal.oportunitatId;
                      const titolToDel = modalEditarDeal.titol;
                      setModalEditarDeal({ ...modalEditarDeal, open: false });
                      handleEliminarDeal(idToDel, titolToDel);
                    }}
                    className="px-3.5 py-2 rounded-xl bg-rose-50 hover:bg-rose-100 dark:bg-rose-950/60 text-rose-700 dark:text-rose-300 text-xs font-bold flex items-center gap-1.5"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                    <span>Eliminar Deal</span>
                  </button>
                ) : (
                  <div />
                )}

                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setModalEditarDeal({ ...modalEditarDeal, open: false })}
                    className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-500 hover:text-slate-700"
                  >
                    Cancel·lar
                  </button>
                  <button
                    type="submit"
                    disabled={guardantDeal}
                    className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-bold shadow-sm"
                  >
                    {guardantDeal ? "Desant..." : modalEditarDeal.mode === "create" ? "Crear Deal" : "Guardar Deal"}
                  </button>
                </div>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
