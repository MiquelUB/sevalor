"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  Bot,
  Camera,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Cpu,
  ExternalLink,
  FileText,
  Layers,
  Pencil,
  RefreshCw,
  Save,
  Search,
  Send,
  Settings2,
  Shield,
  Sparkles,
  Trash2,
  Wrench,
  X,
} from "lucide-react";
import { apiFetch } from "@/lib/api";
import { useGestio } from "@/lib/gestio-context";
import {
  CopilotErrorModal,
  extractCopilotPopupError,
  type CopilotPopupError,
} from "@/components/CopilotErrorModal";

type PestanyaCopilot = "XAT" | "CONFIG" | "RAG" | "GARANTIES" | "INCIDENCIES" | "RECONCILIACIO";

interface CopilotConfigState {
  system_prompt: string;
  rag_prompt: string;
  subagent_prompts: Record<string, string>;
  subagent_enabled: Record<string, boolean>;
  contrast_rules: string[];
  router_hints: string;
  idiosincrasia: Record<string, string>;
  synthesis_max_tokens: number;
  llm_model: string;
  llm_chat_model: string;
  llm_vision_model: string;
  hardware_profile: "32GB" | "16GB";
  timeout_budget_s: number;
  router_timeout_s: number;
}

const SUBAGENTS_CATALEG: Array<{ id: string; nom: string; ambit: string }> = [
  {
    id: "subagent_planificacio_equip",
    nom: "Planificació i Equip",
    ambit: "Ordres de treball, agenda, operaris, fitxatges i plantilla.",
  },
  {
    id: "subagent_logistica_estoc",
    nom: "Magatzem i Proveïment",
    ambit: "Estoc real, materials sota mínims, proveïdors i albarans.",
  },
  {
    id: "subagent_flota_despatx",
    nom: "Flota i Desplaçaments",
    ambit: "Vehicles, ITV, assegurances, conductors i proximitat GPS.",
  },
  {
    id: "subagent_auditoria_marge",
    nom: "Auditoria Financera i Marge",
    ambit: "Imports pendents de facturar, rendibilitat i desviacions (només Direcció).",
  },
  {
    id: "subagent_peritatge_camp",
    nom: "Peritatge Tècnic de Camp",
    ambit: "Incidències d'obra, dictàmens HITL i garanties d'equips.",
  },
  {
    id: "subagent_general_rag",
    nom: "General i RAG Corporatiu",
    ambit: "Protocols interns, manuals, fitxes de clients i finques.",
  },
  {
    id: "subagent_ocr_vision",
    nom: "Digitalització OCR",
    ambit: "Lectura d'albarans, tiquets i documents escanejats.",
  },
  {
    id: "subagent_client_telegram",
    nom: "Concierge Telegram",
    ambit: "Comunicació i consultes de clients a través del canal Telegram.",
  },
];

interface IaStatusResp {
  estat: string;
  node_ia_actiu?: boolean;
  url?: string | null;
  model_actiu?: string;
  models_disponibles?: string[];
  latencia_ms?: number | null;
  error?: string;
}

interface EstatNodeResp {
  node_actiu: boolean;
  estat: string;
  url_ordinador?: string | null;
  proveidor?: string;
  sobirania_dades?: string;
  model_llm?: string;
  vertical_activa?: string;
  ai_act_compliance?: string;
  missatge?: string;
}

interface ChatMessage {
  sender: "user" | "bot";
  text: string;
  error?: boolean;
  links?: Array<{ titol: string; url: string }>;
  subagent?: string | null;
  latencyMs?: number | null;
  actionContext?: { action: string; payload: Record<string, any>; missatge?: string } | null;
}

interface RagDoc {
  id: string;
  titol: string;
  contingut: string;
  tags?: string;
}

interface ClientOpt {
  id: string;
  codi?: string;
  rao_social: string;
}

interface FeinaOpt {
  id: string;
  codi: string;
  titol: string;
  estat?: string;
}

interface MemorandumItem {
  id: string;
  ordre_treball_id?: string | null;
  dictamen_pericial: string;
  motiu_dictamen?: string | null;
  avis_soroll_sever?: boolean;
  cost_estimat_total?: number | null;
  validat_per_enginyer: boolean;
  estat: string;
  created_at: string;
}

interface AlertaCopilotItem {
  id: string;
  tipus_alerta: string;
  missatge: string;
  data_fi_garantia?: string | null;
  estat: string;
  created_at: string;
}

export default function CopilotIAPage() {
  const { rolActiu } = useGestio();
  const rolUpper = (rolActiu || "").toUpperCase();
  const esEnginyer = rolUpper === "ENGINYER";
  const potEditarConfig = rolUpper === "BOSS" || rolUpper === "ADMIN" || rolUpper === "SUPERADMIN";

  const [pestanya, setPestanya] = useState<PestanyaCopilot>("XAT");
  const [carregantInicial, setCarregantInicial] = useState(true);
  const [iaStatus, setIaStatus] = useState<IaStatusResp | null>(null);
  const [estatNode, setEstatNode] = useState<EstatNodeResp | null>(null);

  // ── 0. CONFIGURACIÓ SOBIRANA DE L'AGENT (Disc Dedicat de l'Empresa) ─────
  const [copilotConfig, setCopilotConfig] = useState<CopilotConfigState>({
    system_prompt: "",
    rag_prompt: "",
    subagent_prompts: {},
    subagent_enabled: {},
    contrast_rules: [],
    router_hints: "",
    idiosincrasia: {},
    synthesis_max_tokens: 700,
    llm_model: "",
    llm_chat_model: "",
    llm_vision_model: "",
    hardware_profile: "32GB",
    timeout_budget_s: 24,
    router_timeout_s: 8,
  });
  const [desantConfig, setDesantConfig] = useState(false);
  const [feedbackConfig, setFeedbackConfig] = useState<{ type: "ok" | "err"; text: string } | null>(null);
  const [subagentObert, setSubagentObert] = useState<string | null>("subagent_planificacio_equip");

  // ── 1. XAT Multi-Agent ──────────────────────────────────────────────────
  const [missatgeXat, setMissatgeXat] = useState("");
  const [imatgeB64, setImatgeB64] = useState<string | null>(null);
  const [enviantXat, setEnviantXat] = useState(false);
  const [executantAccio, setExecutantAccio] = useState(false);
  const [popupError, setPopupError] = useState<CopilotPopupError | null>(null);
  const [ultimaPreguntaFallida, setUltimaPreguntaFallida] = useState<string | null>(null);
  const [conversaXat, setConversaXat] = useState<ChatMessage[]>([
    {
      sender: "bot",
      text: "Hola! Sóc l'orquestrador Copilot IA de Sevalor (8 subagents sobirans). Consulta estoc real, flota, ordres de treball, garanties o documentació tècnica del teu disc local.",
    },
  ]);

  // ── 2. RAG (Disc Sobirà — Crear / Editar / Eliminar) ────────────────────
  const [ragDocs, setRagDocs] = useState<RagDoc[]>([]);
  const [ragEditId, setRagEditId] = useState<string | null>(null);
  const [ragTitol, setRagTitol] = useState("");
  const [ragContingut, setRagContingut] = useState("");
  const [ragTags, setRagTags] = useState("");
  const [ragCerca, setRagCerca] = useState("");
  const [ragConfirmDeleteId, setRagConfirmDeleteId] = useState<string | null>(null);
  const [eliminantRagId, setEliminantRagId] = useState<string | null>(null);
  const [submittingRag, setSubmittingRag] = useState(false);
  const [feedbackRag, setFeedbackRag] = useState<{ type: "ok" | "err"; text: string } | null>(null);

  // ── 3. GARANTIES 365 dies ───────────────────────────────────────────────
  const [clients, setClients] = useState<ClientOpt[]>([]);
  const [garantiaClientId, setGarantiaClientId] = useState("");
  const [garantiaNumSerie, setGarantiaNumSerie] = useState("");
  const [cercantGaranties, setCercantGaranties] = useState(false);
  const [garantiaResultat, setGarantiaResultat] = useState<any | null>(null);

  // ── 4. INCIDÈNCIES & MEMORÀNDUMS HITL ───────────────────────────────────
  const [feines, setFeines] = useState<FeinaOpt[]>([]);
  const [memos, setMemos] = useState<MemorandumItem[]>([]);
  const [peritOtId, setPeritOtId] = useState("");
  const [peritText, setPeritText] = useState("");
  const [peritConfianca, setPeritConfianca] = useState("0.92");
  const [generantPerit, setGenerantPerit] = useState(false);
  const [peritFeedback, setPeritFeedback] = useState<string | null>(null);

  // ── 5. ALERTES & RECONCILIACIÓ POST-OBRA ────────────────────────────────
  const [alertesCopilot, setAlertesCopilot] = useState<AlertaCopilotItem[]>([]);
  const [reconcOtId, setReconcOtId] = useState("");
  const [reconcHoresPrevistes, setReconcHoresPrevistes] = useState("4");
  const [reconcHoresReals, setReconcHoresReals] = useState("5.5");
  const [reconcKmReals, setReconcKmReals] = useState("24");
  const [reconcDespeses, setReconcDespeses] = useState("0");
  const [reconcSyncPendent, setReconcSyncPendent] = useState(false);
  const [executantReconc, setExecutantReconc] = useState(false);
  const [reconcResultat, setReconcResultat] = useState<any | null>(null);

  const carregarDades = async () => {
    setCarregantInicial(true);
    try {
      const [st, node, cfg, docs, clis, ots, memoList, alList] = await Promise.all([
        apiFetch<IaStatusResp>("/gestio/copilot/ia-status").catch(() => null),
        apiFetch<EstatNodeResp>("/gestio/copilot/estat-node").catch(() => null),
        apiFetch<CopilotConfigState>("/gestio/copilot/config").catch(() => null),
        apiFetch<RagDoc[]>("/gestio/copilot/rag/document").catch(() => []),
        apiFetch<ClientOpt[]>("/gestio/clients?limit=200").catch(() => []),
        apiFetch<FeinaOpt[]>("/gestio/feines?limit=100").catch(() => []),
        apiFetch<MemorandumItem[]>("/gestio/copilot/memorandums").catch(() => []),
        apiFetch<AlertaCopilotItem[]>("/gestio/copilot/alertes").catch(() => []),
      ]);
      setIaStatus(st);
      setEstatNode(node);
      if (cfg) {
        const hw: "32GB" | "16GB" = cfg.hardware_profile === "16GB" ? "16GB" : "32GB";
        setCopilotConfig({
          system_prompt: cfg.system_prompt || "",
          rag_prompt: cfg.rag_prompt || "",
          subagent_prompts: cfg.subagent_prompts || {},
          subagent_enabled: cfg.subagent_enabled || {},
          contrast_rules: Array.isArray(cfg.contrast_rules) ? cfg.contrast_rules : [],
          router_hints: cfg.router_hints || "",
          idiosincrasia: cfg.idiosincrasia || {},
          synthesis_max_tokens: Number(cfg.synthesis_max_tokens || 700),
          llm_model: cfg.llm_chat_model || cfg.llm_model || "",
          llm_chat_model: cfg.llm_chat_model || cfg.llm_model || "",
          llm_vision_model: cfg.llm_vision_model || "",
          hardware_profile: hw,
          timeout_budget_s: Number(cfg.timeout_budget_s || (hw === "16GB" ? 30 : 24)),
          router_timeout_s: Number(cfg.router_timeout_s || (hw === "16GB" ? 12 : 8)),
        });
      }
      setRagDocs(Array.isArray(docs) ? docs : []);
      setClients(Array.isArray(clis) ? clis : []);
      setFeines(Array.isArray(ots) ? ots : []);
      setMemos(Array.isArray(memoList) ? memoList : []);
      setAlertesCopilot(Array.isArray(alList) ? alList : []);
    } finally {
      setCarregantInicial(false);
    }
  };

  const desarConfiguracioAgent = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!copilotConfig.system_prompt.trim()) {
      setFeedbackConfig({
        type: "err",
        text: "El Prompt del Sistema és obligatori perquè el Copilot pugui operar.",
      });
      return;
    }
    setDesantConfig(true);
    setFeedbackConfig(null);
    try {
      const chatModel = (copilotConfig.llm_chat_model || copilotConfig.llm_model || "").trim();
      const contrastClean = copilotConfig.contrast_rules
        .map((r) => r.trim())
        .filter((r) => r.length > 0);
      const saved = await apiFetch<CopilotConfigState>("/gestio/copilot/config", {
        method: "PUT",
        body: JSON.stringify({
          system_prompt: copilotConfig.system_prompt.trim(),
          rag_prompt: copilotConfig.rag_prompt.trim(),
          subagent_prompts: copilotConfig.subagent_prompts,
          subagent_enabled: copilotConfig.subagent_enabled,
          contrast_rules: contrastClean,
          router_hints: copilotConfig.router_hints.trim(),
          idiosincrasia: copilotConfig.idiosincrasia,
          synthesis_max_tokens: copilotConfig.synthesis_max_tokens,
          llm_model: chatModel,
          llm_chat_model: chatModel,
          llm_vision_model: (copilotConfig.llm_vision_model || "").trim(),
          hardware_profile: copilotConfig.hardware_profile,
          timeout_budget_s: copilotConfig.timeout_budget_s,
          router_timeout_s: copilotConfig.router_timeout_s,
        }),
      });
      const hw: "32GB" | "16GB" = saved.hardware_profile === "16GB" ? "16GB" : "32GB";
      setCopilotConfig({
        system_prompt: saved.system_prompt || "",
        rag_prompt: saved.rag_prompt || "",
        subagent_prompts: saved.subagent_prompts || {},
        subagent_enabled: saved.subagent_enabled || {},
        contrast_rules: Array.isArray(saved.contrast_rules) ? saved.contrast_rules : [],
        router_hints: saved.router_hints || "",
        idiosincrasia: saved.idiosincrasia || {},
        synthesis_max_tokens: Number(saved.synthesis_max_tokens || 700),
        llm_model: saved.llm_chat_model || saved.llm_model || "",
        llm_chat_model: saved.llm_chat_model || saved.llm_model || "",
        llm_vision_model: saved.llm_vision_model || "",
        hardware_profile: hw,
        timeout_budget_s: Number(saved.timeout_budget_s || (hw === "16GB" ? 30 : 24)),
        router_timeout_s: Number(saved.router_timeout_s || (hw === "16GB" ? 12 : 8)),
      });
      setFeedbackConfig({
        type: "ok",
        text: "Configuració desada al disc dur dedicat de l'empresa (09_copilot_ia/prompt_sistema).",
      });
    } catch (err: any) {
      setFeedbackConfig({
        type: "err",
        text: err?.message || "No s'ha pogut desar la configuració de l'agent.",
      });
    } finally {
      setDesantConfig(false);
    }
  };

  const iniciarEdicioRag = (doc: RagDoc) => {
    setRagEditId(doc.id);
    setRagTitol(doc.titol || "");
    setRagContingut(doc.contingut || "");
    setRagTags(doc.tags || "");
    setFeedbackRag(null);
    setRagConfirmDeleteId(null);
  };

  const cancelarEdicioRag = () => {
    setRagEditId(null);
    setRagTitol("");
    setRagContingut("");
    setRagTags("");
    setFeedbackRag(null);
  };

  const desarDocumentRag = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!ragTitol.trim() || !ragContingut.trim()) return;
    setSubmittingRag(true);
    setFeedbackRag(null);
    try {
      const payload = {
        titol: ragTitol.trim(),
        contingut: ragContingut.trim(),
        tags: ragTags.trim(),
      };
      if (ragEditId) {
        await apiFetch(`/gestio/copilot/rag/document/${encodeURIComponent(ragEditId)}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
        setFeedbackRag({
          type: "ok",
          text: "Protocol actualitzat correctament al disc sobirà local.",
        });
      } else {
        await apiFetch("/gestio/copilot/rag/document", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        setFeedbackRag({
          type: "ok",
          text: "Document afegit i indexat correctament al disc sobirà local.",
        });
      }
      setRagEditId(null);
      setRagTitol("");
      setRagContingut("");
      setRagTags("");
      await carregarDades();
    } catch (err: any) {
      setFeedbackRag({
        type: "err",
        text: `Error desant el document: ${err?.message || "Error de xarxa"}`,
      });
    } finally {
      setSubmittingRag(false);
    }
  };

  const eliminarDocumentRag = async (docId: string) => {
    setEliminantRagId(docId);
    setFeedbackRag(null);
    try {
      await apiFetch(`/gestio/copilot/rag/document/${encodeURIComponent(docId)}`, {
        method: "DELETE",
      });
      if (ragEditId === docId) {
        cancelarEdicioRag();
      }
      setRagConfirmDeleteId(null);
      setFeedbackRag({
        type: "ok",
        text: "Protocol eliminat del disc sobirà local.",
      });
      await carregarDades();
    } catch (err: any) {
      setFeedbackRag({
        type: "err",
        text: `Error eliminant el document: ${err?.message || "Error de xarxa"}`,
      });
    } finally {
      setEliminantRagId(null);
    }
  };

  useEffect(() => {
    carregarDades();
  }, []);

  const handleImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onloadend = () => setImatgeB64(reader.result as string);
    reader.readAsDataURL(file);
  };

  const enviarMissatgeXat = async (preguntaOpcional?: string) => {
    const preguntaFinal = (preguntaOpcional ?? missatgeXat).trim();
    if (!preguntaFinal && !imatgeB64) return;
    const promptTxt = preguntaFinal || "Analitza aquesta imatge tècnica.";
    setConversaXat((prev) => [...prev, { sender: "user", text: promptTxt }]);
    if (!preguntaOpcional) setMissatgeXat("");
    setEnviantXat(true);
    const imgEnviar = imatgeB64;
    setImatgeB64(null);

    try {
      const historial = conversaXat
        .filter((m) => !m.error && m.text)
        .slice(-6)
        .map((m) => ({
          role: m.sender === "user" ? "user" : "assistant",
          content: m.text,
        }));
      const dades = await apiFetch<any>("/gestio/copilot/xat", {
        method: "POST",
        body: JSON.stringify({ pregunta: promptTxt, imatge_b64: imgEnviar, historial }),
      });
      const toolRes = dades?.tool_resultat || dades?.metadata?.tool_resultat;
      const requiresConf = Boolean(toolRes?.requires_confirmation);
      setConversaXat((prev) => [
        ...prev,
        {
          sender: "bot",
          text: dades?.resposta || (requiresConf ? toolRes?.missatge : "Sense resposta."),
          links: Array.isArray(dades?.enllacos) ? dades.enllacos : [],
          subagent: dades?.subagent_utilitzat || null,
          latencyMs: dades?.temps_inferencia_ms ?? null,
          actionContext: requiresConf ? toolRes : null,
        },
      ]);
    } catch (err: any) {
      const structured = extractCopilotPopupError(err);
      if (structured) {
        setUltimaPreguntaFallida(promptTxt);
        setPopupError(structured);
      }
      setConversaXat((prev) => [
        ...prev,
        {
          sender: "bot",
          text: structured
            ? `${structured.titol}: ${structured.message}`
            : err?.message || "No s'ha pogut contactar amb el node IA local.",
          error: true,
        },
      ]);
    } finally {
      setEnviantXat(false);
    }
  };

  const confirmarAccio = async (actionContext: { action: string; payload: Record<string, any> }, idx: number) => {
    setExecutantAccio(true);
    try {
      const dades = await apiFetch<any>("/gestio/copilot/action/confirm", {
        method: "POST",
        body: JSON.stringify({ action: actionContext.action, payload: actionContext.payload }),
      });
      setConversaXat((prev) =>
        prev.map((m, i) =>
          i === idx
            ? {
                ...m,
                actionContext: null,
                text: `${m.text}\n\n✅ ${dades?.missatge || "Acció executada."}`,
              }
            : m
        )
      );
    } catch (err: any) {
      setConversaXat((prev) => [
        ...prev,
        { sender: "bot", text: err?.message || "Error executant acció HITL.", error: true },
      ]);
    } finally {
      setExecutantAccio(false);
    }
  };

  const executarAuditoriaGaranties = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!garantiaClientId && !garantiaNumSerie.trim()) return;
    setCercantGaranties(true);
    try {
      const qs = new URLSearchParams();
      if (garantiaClientId) qs.set("client_id", garantiaClientId);
      if (garantiaNumSerie.trim()) qs.set("numero_serie", garantiaNumSerie.trim());
      const res = await apiFetch<any>(`/gestio/copilot/garanties/auditoria?${qs.toString()}`);
      setGarantiaResultat(res);
    } catch (err: any) {
      setGarantiaResultat({ trobat: false, missatge: err?.message || "Error restaurant auditoria." });
    } finally {
      setCercantGaranties(false);
    }
  };

  const generarPeritatgeIncidencia = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!peritText.trim()) return;
    setGenerantPerit(true);
    setPeritFeedback(null);
    try {
      const res = await apiFetch<any>("/gestio/copilot/incidencies/peritatge", {
        method: "POST",
        body: JSON.stringify({
          ordre_treball_id: peritOtId || null,
          text_dictat_operari: peritText.trim(),
          confianca_acustica: Number(peritConfianca) || 0.9,
        }),
      });
      setPeritFeedback(res?.missatge || "Memoràndum tècnic creat en pendent de validació HITL.");
      setPeritText("");
      await carregarDades();
    } catch (err: any) {
      setPeritFeedback(err?.message || "Error generant peritatge.");
    } finally {
      setGenerantPerit(false);
    }
  };

  const validarMemorandum = async (memoId: string, accio: "APROVAR" | "REBUTJAR") => {
    try {
      await apiFetch(`/gestio/copilot/memorandums/${memoId}/validacio`, {
        method: "PUT",
        body: JSON.stringify({ accio }),
      });
      await carregarDades();
    } catch (err: any) {
      setPeritFeedback(err?.message || "Error validant memoràndum.");
    }
  };

  const executarReconciliacio = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!reconcOtId) return;
    setExecutantReconc(true);
    setReconcResultat(null);
    try {
      const res = await apiFetch<any>("/gestio/copilot/reconciliacio/post-obra", {
        method: "POST",
        body: JSON.stringify({
          ordre_treball_id: reconcOtId,
          hores_previstes: Number(reconcHoresPrevistes) || 0,
          hores_reals: Number(reconcHoresReals) || 0,
          km_reals: Number(reconcKmReals) || 0,
          despeses_camp: Number(reconcDespeses) || 0,
          sync_pendent: reconcSyncPendent,
        }),
      });
      setReconcResultat(res);
    } catch (err: any) {
      setReconcResultat({ missatge: err?.message || "Error executant reconciliació." });
    } finally {
      setExecutantReconc(false);
    }
  };

  const aprovarPressupostReconciliacio = async (auditoriaId: string, confirmar: boolean) => {
    try {
      const res = await apiFetch<any>(`/gestio/copilot/reconciliacio/${auditoriaId}/aprovar-pressupost`, {
        method: "PUT",
        body: JSON.stringify({ confirmar }),
      });
      setReconcResultat((prev: any) =>
        prev ? { ...prev, estat: res.estat, missatge: res.missatge } : res
      );
    } catch (err: any) {
      setReconcResultat((prev: any) =>
        prev ? { ...prev, missatge: err?.message || "Error aprovant pressupost." } : null
      );
    }
  };

  const nodeOnline = iaStatus?.estat === "ONLINE";
  const copilotConfigurat = Boolean(copilotConfig.system_prompt.trim());
  const ragDocsFiltrats = ragDocs.filter((doc) => {
    const q = ragCerca.trim().toLowerCase();
    if (!q) return true;
    return (
      (doc.titol || "").toLowerCase().includes(q) ||
      (doc.contingut || "").toLowerCase().includes(q) ||
      (doc.tags || "").toLowerCase().includes(q)
    );
  });

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6 w-full animate-fade-in">
      {/* Capçalera + Estat en Viu del Node */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-display-lg font-bold text-primary flex items-center gap-2">
            <Sparkles className="w-6 h-6 text-secondary" />
            Centre d&apos;Intel·ligència Copilot IA Local
          </h1>
          <p className="text-sm text-on-surface-variant mt-1">
            8 subagents sobirans, memòria tècnica RAG, auditoria de garanties 365d, peritatge HITL i reconciliació.
          </p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <span
            className={`px-3 py-1.5 rounded-full text-xs font-mono font-bold inline-flex items-center gap-1.5 border ${
              nodeOnline
                ? "bg-emerald-50 border-emerald-200 text-emerald-800"
                : "bg-amber-50 border-amber-200 text-amber-800"
            }`}
          >
            <Cpu className="w-3.5 h-3.5" />
            {nodeOnline
              ? `ONLINE · ${iaStatus?.model_actiu || "LM Studio"}${
                  iaStatus?.latencia_ms != null ? ` (${iaStatus.latencia_ms}ms)` : ""
                }`
              : "NODE OFFLINE"}
          </span>
          <button
            type="button"
            onClick={carregarDades}
            disabled={carregantInicial}
            className="px-3 py-1.5 rounded-xl bg-surface-container-lowest border border-outline-variant/60 text-xs font-bold text-on-surface hover:border-primary inline-flex items-center gap-1.5 cursor-pointer"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${carregantInicial ? "animate-spin" : ""}`} />
            <span>Comprovar Node</span>
          </button>
        </div>
      </div>

      {/* Targetes d'Estat Sobirà */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="p-4 rounded-2xl bg-surface-container-lowest border border-outline-variant/40 shadow-sm">
          <div className="text-[10px] font-mono uppercase text-on-surface-variant font-bold">
            Motor Inferència Local
          </div>
          <div className="text-sm font-bold text-on-surface mt-1 truncate">
            {nodeOnline ? iaStatus?.model_actiu || estatNode?.model_llm : estatNode?.estat || "Desconnectat"}
          </div>
          <div className="text-[11px] text-on-surface-variant mt-1 truncate font-mono">
            {iaStatus?.url || estatNode?.url_ordinador || iaStatus?.error || "Sense túnel configurat"}
          </div>
        </div>
        <div className="p-4 rounded-2xl bg-surface-container-lowest border border-outline-variant/40 shadow-sm">
          <div className="text-[10px] font-mono uppercase text-on-surface-variant font-bold">
            Sobirania i Compliment
          </div>
          <div className="text-sm font-bold text-on-surface mt-1 flex items-center gap-1.5">
            <Shield className="w-4 h-4 text-primary shrink-0" />
            <span>Zero Cloud Egress</span>
          </div>
          <div className="text-[11px] text-on-surface-variant mt-1">
            {estatNode?.ai_act_compliance || "RGPD / AI Act · Disc Local de l'Empresa"}
          </div>
        </div>
        <div className="p-4 rounded-2xl bg-surface-container-lowest border border-outline-variant/40 shadow-sm">
          <div className="text-[10px] font-mono uppercase text-on-surface-variant font-bold">
            Coneixement &amp; Alertes Actives
          </div>
          <div className="text-sm font-bold text-on-surface mt-1">
            {ragDocs.length} protocols RAG · {alertesCopilot.length} alertes
          </div>
          <div className="text-[11px] text-on-surface-variant mt-1">
            {memos.filter((m) => !m.validat_per_enginyer).length} memoràndums pendents de validació HITL
          </div>
        </div>
      </div>

      {/* Avís accionable si falta configurar el Prompt de l'Agent */}
      {!carregantInicial && !copilotConfigurat && (
        <div className="p-4 rounded-2xl bg-amber-50 border border-amber-300 text-amber-950 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-amber-700 shrink-0 mt-0.5" />
            <div>
              <div className="text-sm font-bold">
                El Copilot IA encara no té configurat el prompt d&apos;aquesta empresa
              </div>
              <p className="text-xs text-amber-900/90 mt-0.5">
                Sense el Prompt del Sistema, les consultes retornaran <span className="font-mono font-semibold">COPILOT_NOT_CONFIGURED</span>. Defineix les directrius de l&apos;agent per activar-lo.
              </p>
            </div>
          </div>
          {pestanya !== "CONFIG" && (
            <button
              type="button"
              onClick={() => setPestanya("CONFIG")}
              className="px-4 py-2 rounded-xl bg-primary text-on-primary text-xs font-bold hover:opacity-90 shrink-0 inline-flex items-center gap-1.5 cursor-pointer"
            >
              <Settings2 className="w-3.5 h-3.5" />
              <span>Configurar l&apos;Agent</span>
            </button>
          )}
        </div>
      )}

      {/* Pestanyes */}
      <div className="flex flex-wrap gap-2 border-b border-outline-variant/40 pb-3">
        {(
          [
            { id: "XAT", label: "Xat Multi-Agent", icon: Bot },
            {
              id: "CONFIG",
              label: copilotConfigurat ? "Configuració Agent" : "Configuració Agent (Pendent)",
              icon: Settings2,
            },
            { id: "RAG", label: `Base Coneixement RAG (${ragDocs.length})`, icon: Layers },
            { id: "GARANTIES", label: "Auditoria Garanties 365d", icon: Shield },
            { id: "INCIDENCIES", label: `Peritatge & Memoràndums (${memos.length})`, icon: Wrench },
            { id: "RECONCILIACIO", label: `Reconciliació & Alertes (${alertesCopilot.length})`, icon: AlertTriangle },
          ] as Array<{ id: PestanyaCopilot; label: string; icon: any }>
        ).map((tab) => {
          const Icon = tab.icon;
          const active = pestanya === tab.id;
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => setPestanya(tab.id)}
              className={`px-4 py-2 rounded-xl text-xs font-bold inline-flex items-center gap-2 transition-all cursor-pointer ${
                active
                  ? "bg-primary text-on-primary shadow"
                  : "bg-surface-container-lowest border border-outline-variant/40 text-on-surface-variant hover:text-primary"
              }`}
            >
              <Icon className="w-3.5 h-3.5" />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>

      {/* 1. XAT MULTI-AGENT */}
      {pestanya === "XAT" && (
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-5">
          <div className="lg:col-span-1 space-y-3 bg-surface-container-lowest rounded-2xl border border-outline-variant/40 p-4 shadow-sm h-fit">
            <h3 className="text-xs font-bold uppercase tracking-wider text-on-surface-variant">
              Consultes Ràpides
            </h3>
            <div className="space-y-2">
              {[
                "Quin estoc tenim per sota del mínim?",
                "Quins operaris i ordres tenim actius avui?",
                "Revisa l'estat d'ITV i assegurances de la flota",
                ...(!esEnginyer ? ["Quins pressupostos o imports tenim pendents?"] : []),
              ].map((q) => (
                <button
                  key={q}
                  type="button"
                  disabled={enviantXat}
                  onClick={() => enviarMissatgeXat(q)}
                  className="w-full text-left p-2.5 rounded-xl bg-surface-container-low hover:bg-primary/10 border border-outline-variant/40 hover:border-primary/40 text-xs font-medium text-on-surface transition-colors cursor-pointer disabled:opacity-50"
                >
                  {q}
                </button>
              ))}
            </div>
            {iaStatus?.models_disponibles && iaStatus.models_disponibles.length > 0 && (
              <div className="pt-3 border-t border-outline-variant/30">
                <p className="text-[10px] font-mono uppercase text-on-surface-variant font-bold mb-1">
                  Models carregats al node
                </p>
                <ul className="space-y-1 text-[11px] font-mono text-on-surface-variant">
                  {iaStatus.models_disponibles.map((m) => (
                    <li key={m} className="truncate">• {m}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          <div className="lg:col-span-3 bg-surface-container-lowest rounded-2xl border border-outline-variant/40 shadow-sm flex flex-col h-[560px] overflow-hidden">
            <div className="px-4 py-3 border-b border-outline-variant/30 bg-surface-container-low flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Bot className="w-4 h-4 text-primary" />
                <span className="text-xs font-bold text-on-surface">
                  Orquestrador Multi-Agent Top-2 + Grounding Disc Sobirà
                </span>
              </div>
              <span className="text-[10px] font-mono text-on-surface-variant">
                Vertical: {estatNode?.vertical_activa || "SEVALOR"}
              </span>
            </div>

            <div className="flex-1 p-4 overflow-y-auto space-y-3">
              {conversaXat.map((m, idx) => (
                <div key={idx} className={`flex flex-col ${m.sender === "user" ? "items-end" : "items-start"}`}>
                  <div
                    className={`max-w-[82%] p-3 rounded-2xl text-xs leading-relaxed whitespace-pre-wrap ${
                      m.sender === "user"
                        ? "bg-primary text-on-primary rounded-br-none"
                        : m.error
                        ? "bg-rose-50 border border-rose-300 text-rose-900 rounded-bl-none font-medium"
                        : "bg-surface-container-low border border-outline-variant/40 text-on-surface rounded-bl-none"
                    }`}
                  >
                    {m.text}
                    {m.error && m.text.includes("COPILOT_NOT_CONFIGURED") && (
                      <div className="mt-2 pt-2 border-t border-rose-200">
                        <button
                          type="button"
                          onClick={() => setPestanya("CONFIG")}
                          className="px-3 py-1.5 rounded-lg bg-primary text-on-primary text-[11px] font-bold hover:opacity-90 inline-flex items-center gap-1.5 cursor-pointer"
                        >
                          <Settings2 className="w-3.5 h-3.5" />
                          <span>Obrir Configuració de l&apos;Agent</span>
                        </button>
                      </div>
                    )}
                  </div>
                  {m.sender === "bot" && (m.subagent || m.latencyMs != null) && (
                    <span className="text-[10px] font-mono text-on-surface-variant mt-1 pl-1">
                      {m.subagent ? `Subagent: ${m.subagent}` : ""}
                      {m.subagent && m.latencyMs != null ? " · " : ""}
                      {m.latencyMs != null ? `${m.latencyMs} ms` : ""}
                    </span>
                  )}
                  {m.actionContext && (
                    <div className="mt-2 p-3 bg-primary/10 border border-primary/30 rounded-xl max-w-md">
                      <p className="text-[11px] font-bold text-primary mb-1">Confirmació Humana Requerida:</p>
                      <pre className="text-[10px] bg-surface-container p-2 rounded mb-2 overflow-x-auto">
                        {JSON.stringify(m.actionContext.payload, null, 2)}
                      </pre>
                      <button
                        type="button"
                        disabled={executantAccio}
                        onClick={() => confirmarAccio(m.actionContext!, idx)}
                        className="px-3 py-1.5 rounded-lg bg-primary text-on-primary text-xs font-bold hover:opacity-90 disabled:opacity-50"
                      >
                        {executantAccio ? "Executant..." : "Aprovar i Executar"}
                      </button>
                    </div>
                  )}
                  {m.links && m.links.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mt-1.5 pl-1">
                      {m.links.map((link, lIdx) => (
                        <Link
                          key={lIdx}
                          href={link.url}
                          className="text-[11px] px-2.5 py-1 rounded-lg bg-surface-container text-primary hover:bg-surface-container-high font-semibold inline-flex items-center gap-1"
                        >
                          <ExternalLink className="w-3 h-3" />
                          {link.titol}
                        </Link>
                      ))}
                    </div>
                  )}
                </div>
              ))}
              {enviantXat && (
                <div className="flex items-start">
                  <div className="bg-surface-container-low border border-outline-variant/40 text-on-surface-variant px-3 py-2 rounded-2xl text-xs">
                    Consultant subagents al node local...
                  </div>
                </div>
              )}
            </div>

            <div className="p-3 border-t border-outline-variant/30 bg-surface-container-low space-y-2">
              {imatgeB64 && (
                <div className="relative inline-block">
                  <img src={imatgeB64} alt="Previsualització" className="h-16 w-16 object-cover rounded-lg border border-outline-variant" />
                  <button
                    type="button"
                    onClick={() => setImatgeB64(null)}
                    className="absolute -top-2 -right-2 bg-rose-600 text-white rounded-full p-0.5"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </div>
              )}
              <div className="flex items-center gap-2">
                <label className="p-2.5 rounded-xl bg-surface-container hover:bg-surface-container-high text-on-surface-variant hover:text-primary cursor-pointer">
                  <Camera className="w-4 h-4" />
                  <input type="file" accept="image/*" className="hidden" onChange={handleImageUpload} />
                </label>
                <input
                  type="text"
                  value={missatgeXat}
                  onChange={(e) => setMissatgeXat(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") enviarMissatgeXat();
                  }}
                  placeholder="Pregunta sobre estoc, flota, feines, garanties o normativa..."
                  className="flex-1 bg-surface-container-lowest border border-outline-variant/60 rounded-xl px-3 py-2 text-xs text-on-surface focus:outline-none focus:border-primary"
                />
                <button
                  type="button"
                  disabled={enviantXat || (!missatgeXat.trim() && !imatgeB64)}
                  onClick={() => enviarMissatgeXat()}
                  className="px-4 py-2 rounded-xl bg-primary text-on-primary text-xs font-bold inline-flex items-center gap-1.5 hover:opacity-90 disabled:opacity-50 cursor-pointer"
                >
                  <Send className="w-3.5 h-3.5" />
                  <span>Enviar</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 1B. CONFIGURACIÓ DE L'AGENT (PROMPTS I MODEL LLM PER EMPRESA — RLS ESTRICTE) */}
      {pestanya === "CONFIG" && (
        <form onSubmit={desarConfiguracioAgent} className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          <div className="lg:col-span-7 bg-surface-container-lowest rounded-2xl border border-outline-variant/40 p-6 shadow-sm space-y-5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 className="text-base font-bold text-on-surface flex items-center gap-2">
                  <Settings2 className="w-4 h-4 text-primary" />
                  Configuració Sobirana de l&apos;Agent
                </h2>
                <p className="text-xs text-on-surface-variant mt-1">
                  Aquests prompts i perfils de model resideixen exclusivament al disc dur dedicat de la teva empresa (<span className="font-mono">09_copilot_ia/prompt_sistema</span>), mai a Hetzner.
                </p>
              </div>
              <span
                className={`px-2.5 py-1 rounded-full text-[11px] font-semibold shrink-0 border ${
                  copilotConfigurat
                    ? "bg-emerald-50 border-emerald-200 text-emerald-800"
                    : "bg-amber-50 border-amber-200 text-amber-800"
                }`}
              >
                {copilotConfigurat ? "Actiu" : "Pendent"}
              </span>
            </div>

            {!potEditarConfig && (
              <div className="p-3 rounded-xl bg-surface-container-low border border-outline-variant/50 text-xs text-on-surface-variant">
                Mode lectura: només els rols de Direcció (<span className="font-mono">BOSS</span> / <span className="font-mono">ADMIN</span>) poden modificar la configuració del Copilot.
              </div>
            )}

            {feedbackConfig && (
              <div
                className={`p-3 rounded-xl border text-xs font-medium flex items-center gap-2 ${
                  feedbackConfig.type === "ok"
                    ? "bg-emerald-50 border-emerald-200 text-emerald-800"
                    : "bg-rose-50 border-rose-200 text-rose-800"
                }`}
              >
                {feedbackConfig.type === "ok" ? (
                  <CheckCircle2 className="w-4 h-4 shrink-0" />
                ) : (
                  <AlertTriangle className="w-4 h-4 shrink-0" />
                )}
                <span>{feedbackConfig.text}</span>
              </div>
            )}

            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <label className="text-xs font-bold text-on-surface">
                  Prompt del Sistema (Directrius de l&apos;Empresa) *
                </label>
                <span className="text-[11px] font-mono text-on-surface-variant">
                  {copilotConfig.system_prompt.length} caràcters
                </span>
              </div>
              <textarea
                rows={7}
                required
                disabled={!potEditarConfig}
                value={copilotConfig.system_prompt}
                onChange={(e) =>
                  setCopilotConfig((prev) => ({ ...prev, system_prompt: e.target.value }))
                }
                placeholder="Ex: Ets l'assistent tècnic oficial de [Nom Empresa], especialitzada en instal·lacions i manteniment. Respon sempre en català, amb precisió tècnica i basant-te únicament en les dades del disc local..."
                className="w-full rounded-xl border border-outline-variant bg-surface-container-low text-on-surface p-3 text-xs leading-relaxed outline-none focus:border-primary disabled:opacity-70"
              />
            </div>

            <div className="space-y-1.5">
              <label className="block text-xs font-bold text-on-surface">
                Instruccions RAG i Coneixement Corporatiu
              </label>
              <p className="text-[11px] text-on-surface-variant">
                Indica com ha de prioritzar els protocols interns, paraules clau i documentació del disc sobirà.
              </p>
              <textarea
                rows={4}
                disabled={!potEditarConfig}
                value={copilotConfig.rag_prompt}
                onChange={(e) =>
                  setCopilotConfig((prev) => ({ ...prev, rag_prompt: e.target.value }))
                }
                placeholder="Ex: Quan es consultin protocols interns o normatives, cita sempre el títol exacte del document RAG i avisa si falta informació actualitzada."
                className="w-full rounded-xl border border-outline-variant bg-surface-container-low text-on-surface p-3 text-xs leading-relaxed outline-none focus:border-primary disabled:opacity-70"
              />
            </div>

            <div className="space-y-4 pt-1 border-t border-outline-variant/30">
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                <div className="space-y-1.5">
                  <label className="block text-xs font-bold text-on-surface">
                    Perfil del Mini-PC Dedicat
                  </label>
                  <select
                    disabled={!potEditarConfig}
                    value={copilotConfig.hardware_profile}
                    onChange={(e) => {
                      const hw: "32GB" | "16GB" = e.target.value === "16GB" ? "16GB" : "32GB";
                      setCopilotConfig((prev) => ({
                        ...prev,
                        hardware_profile: hw,
                        timeout_budget_s: hw === "16GB" ? 30 : 24,
                        router_timeout_s: hw === "16GB" ? 12 : 8,
                      }));
                    }}
                    className="w-full rounded-xl border border-outline-variant bg-surface-container-low text-on-surface px-3 py-2.5 text-xs outline-none focus:border-primary disabled:opacity-70"
                  >
                    <option value="32GB">32 GB RAM — Ideal (MoE 35B-A3B · 24 s)</option>
                    <option value="16GB">16 GB RAM — Estàndard (4B / 9B · 30 s)</option>
                  </select>
                </div>
                <div className="space-y-1.5">
                  <label className="block text-xs font-bold text-on-surface">
                    Timeout Router (segons)
                  </label>
                  <input
                    type="number"
                    min={3}
                    max={25}
                    step={1}
                    disabled={!potEditarConfig}
                    value={copilotConfig.router_timeout_s}
                    onChange={(e) =>
                      setCopilotConfig((prev) => ({
                        ...prev,
                        router_timeout_s: Math.max(3, Math.min(25, Number(e.target.value) || 8)),
                      }))
                    }
                    className="w-full rounded-xl border border-outline-variant bg-surface-container-low text-on-surface px-3 py-2.5 text-xs font-mono outline-none focus:border-primary disabled:opacity-70"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="block text-xs font-bold text-on-surface">
                    Pressupost màxim total (s)
                  </label>
                  <input
                    type="number"
                    min={8}
                    max={90}
                    step={1}
                    disabled={!potEditarConfig}
                    value={copilotConfig.timeout_budget_s}
                    onChange={(e) =>
                      setCopilotConfig((prev) => ({
                        ...prev,
                        timeout_budget_s: Math.max(8, Math.min(90, Number(e.target.value) || 24)),
                      }))
                    }
                    className="w-full rounded-xl border border-outline-variant bg-surface-container-low text-on-surface px-3 py-2.5 text-xs font-mono outline-none focus:border-primary disabled:opacity-70"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="block text-xs font-bold text-on-surface">
                    Max tokens síntesi
                  </label>
                  <input
                    type="number"
                    min={250}
                    max={1500}
                    step={50}
                    disabled={!potEditarConfig}
                    value={copilotConfig.synthesis_max_tokens}
                    onChange={(e) =>
                      setCopilotConfig((prev) => ({
                        ...prev,
                        synthesis_max_tokens: Math.max(
                          250,
                          Math.min(1500, Number(e.target.value) || 700),
                        ),
                      }))
                    }
                    className="w-full rounded-xl border border-outline-variant bg-surface-container-low text-on-surface px-3 py-2.5 text-xs font-mono outline-none focus:border-primary disabled:opacity-70"
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <label className="block text-xs font-bold text-on-surface">
                  Pistes per al Router Multi-Subagent (Etapa 1 · opcional)
                </label>
                <p className="text-[11px] text-on-surface-variant">
                  Vocabulari de la vertical, distinció «com/on» (guies) vs cerca de registres i crides paral·leles per consultes transversals.
                </p>
                <textarea
                  rows={2}
                  disabled={!potEditarConfig}
                  value={copilotConfig.router_hints}
                  onChange={(e) =>
                    setCopilotConfig((prev) => ({ ...prev, router_hints: e.target.value }))
                  }
                  placeholder="Ex: Distingeix consultes de procediment ('com es fa') cap a guies RAG; si es pregunta estoc+OT, crida ambdós subagents en paral·lel."
                  className="w-full rounded-xl border border-outline-variant bg-surface-container-low text-on-surface p-3 text-xs leading-relaxed outline-none focus:border-primary disabled:opacity-70"
                />
              </div>

              <div className="space-y-1.5">
                <label className="block text-xs font-bold text-on-surface">
                  Regles de Contrast i Verificació Creuada (Etapa 2 · una regla per línia)
                </label>
                <p className="text-[11px] text-on-surface-variant">
                  Només s&apos;injecten quan responen múltiples subagents; defineixen criteris de desempat propis de l&apos;empresa.
                </p>
                <textarea
                  rows={3}
                  disabled={!potEditarConfig}
                  value={copilotConfig.contrast_rules.join("\n")}
                  onChange={(e) =>
                    setCopilotConfig((prev) => ({
                      ...prev,
                      contrast_rules: e.target.value.split("\n"),
                    }))
                  }
                  placeholder="Ex: Compara sempre l'estoc disponible vs el material reservat per a les OTs del dia i assenyala qualsevol dèficit."
                  className="w-full rounded-xl border border-outline-variant bg-surface-container-low text-on-surface p-3 text-xs leading-relaxed outline-none focus:border-primary disabled:opacity-70"
                />
              </div>

              <div className="space-y-2.5 pt-1 border-t border-outline-variant/20">
                <div>
                  <label className="block text-xs font-bold text-on-surface">
                    Idiosincràsia Operativa de l&apos;Empresa (opcional)
                  </label>
                  <p className="text-[11px] text-on-surface-variant">
                    Només els camps omplerts s&apos;injecten al prefix del Copilot (les xifres configurades aquí queden autoritzades automàticament).
                  </p>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <label className="block text-[11px] font-semibold text-on-surface-variant">
                      Horari de magatzem i lliuraments
                    </label>
                    <input
                      type="text"
                      disabled={!potEditarConfig}
                      value={copilotConfig.idiosincrasia.horari_magatzem || ""}
                      onChange={(e) =>
                        setCopilotConfig((prev) => ({
                          ...prev,
                          idiosincrasia: { ...prev.idiosincrasia, horari_magatzem: e.target.value },
                        }))
                      }
                      placeholder="Ex: Dll-Dv 07:30-13:30 i 15:00-18:00"
                      className="w-full rounded-xl border border-outline-variant bg-surface-container-low text-on-surface px-3 py-2 text-xs outline-none focus:border-primary disabled:opacity-70"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="block text-[11px] font-semibold text-on-surface-variant">
                      Prioritat contractual / SLA
                    </label>
                    <input
                      type="text"
                      disabled={!potEditarConfig}
                      value={copilotConfig.idiosincrasia.prioritat_sla || ""}
                      onChange={(e) =>
                        setCopilotConfig((prev) => ({
                          ...prev,
                          idiosincrasia: { ...prev.idiosincrasia, prioritat_sla: e.target.value },
                        }))
                      }
                      placeholder="Ex: Avaries urgents SLA màxim 4 h; manteniment 48 h"
                      className="w-full rounded-xl border border-outline-variant bg-surface-container-low text-on-surface px-3 py-2 text-xs outline-none focus:border-primary disabled:opacity-70"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="block text-[11px] font-semibold text-on-surface-variant">
                      Zones i rutes de cobertura
                    </label>
                    <input
                      type="text"
                      disabled={!potEditarConfig}
                      value={copilotConfig.idiosincrasia.zones_cobertura || ""}
                      onChange={(e) =>
                        setCopilotConfig((prev) => ({
                          ...prev,
                          idiosincrasia: { ...prev.idiosincrasia, zones_cobertura: e.target.value },
                        }))
                      }
                      placeholder="Ex: Segrià, Pla d'Urgell i Garrigues"
                      className="w-full rounded-xl border border-outline-variant bg-surface-container-low text-on-surface px-3 py-2 text-xs outline-none focus:border-primary disabled:opacity-70"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="block text-[11px] font-semibold text-on-surface-variant">
                      Glossari intern
                    </label>
                    <input
                      type="text"
                      disabled={!potEditarConfig}
                      value={copilotConfig.idiosincrasia.glossari_intern || ""}
                      onChange={(e) =>
                        setCopilotConfig((prev) => ({
                          ...prev,
                          idiosincrasia: { ...prev.idiosincrasia, glossari_intern: e.target.value },
                        }))
                      }
                      placeholder="Ex: 'Quadre A' = Quadre principal nau sud"
                      className="w-full rounded-xl border border-outline-variant bg-surface-container-low text-on-surface px-3 py-2 text-xs outline-none focus:border-primary disabled:opacity-70"
                    />
                  </div>
                </div>
              </div>

              <div className="space-y-2">
                <label className="block text-xs font-bold text-on-surface">
                  Model LLM de Xat i Coordinació (opcional)
                </label>
                <input
                  type="text"
                  disabled={!potEditarConfig}
                  value={copilotConfig.llm_chat_model}
                  onChange={(e) =>
                    setCopilotConfig((prev) => ({
                      ...prev,
                      llm_chat_model: e.target.value,
                      llm_model: e.target.value,
                    }))
                  }
                  placeholder="Ex: qwen3-4b (buit detecta automàticament el model de xat text-only a LM Studio)"
                  className="w-full rounded-xl border border-outline-variant bg-surface-container-low text-on-surface px-3 py-2.5 text-xs font-mono outline-none focus:border-primary disabled:opacity-70"
                />
                {iaStatus?.models_disponibles && iaStatus.models_disponibles.length > 0 && potEditarConfig && (
                  <div className="flex flex-wrap gap-1.5 pt-1">
                    {iaStatus.models_disponibles.map((m) => (
                      <button
                        key={m}
                        type="button"
                        onClick={() =>
                          setCopilotConfig((prev) => ({
                            ...prev,
                            llm_chat_model: m,
                            llm_model: m,
                          }))
                        }
                        className={`px-2.5 py-1 rounded-lg text-[11px] font-mono border transition-colors cursor-pointer ${
                          copilotConfig.llm_chat_model === m
                            ? "bg-primary text-on-primary border-primary"
                            : "bg-surface-container-low text-on-surface-variant border-outline-variant/60 hover:border-primary"
                        }`}
                      >
                        {m}
                      </button>
                    ))}
                  </div>
                )}
              </div>

              <div className="space-y-1.5">
                <label className="block text-xs font-bold text-on-surface">
                  Model LLM de Visió / OCR (opcional)
                </label>
                <input
                  type="text"
                  disabled={!potEditarConfig}
                  value={copilotConfig.llm_vision_model}
                  onChange={(e) =>
                    setCopilotConfig((prev) => ({ ...prev, llm_vision_model: e.target.value }))
                  }
                  placeholder="Ex: qwen2.5-vl-7b-instruct (buit utilitza el model principal si suporta visió)"
                  className="w-full rounded-xl border border-outline-variant bg-surface-container-low text-on-surface px-3 py-2.5 text-xs font-mono outline-none focus:border-primary disabled:opacity-70"
                />
              </div>
            </div>

            {potEditarConfig && (
              <div className="pt-2 flex items-center gap-3">
                <button
                  type="submit"
                  disabled={desantConfig}
                  className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-primary text-on-primary text-xs font-bold hover:opacity-90 disabled:opacity-50 cursor-pointer"
                >
                  <Save className="w-3.5 h-3.5" />
                  <span>{desantConfig ? "Desant configuració..." : "Desar Configuració"}</span>
                </button>
                {copilotConfigurat && (
                  <button
                    type="button"
                    onClick={() => setPestanya("XAT")}
                    className="px-4 py-2.5 rounded-xl border border-outline-variant/60 text-xs font-bold text-on-surface hover:border-primary cursor-pointer"
                  >
                    Anar al Xat
                  </button>
                )}
              </div>
            )}
          </div>

          <div className="lg:col-span-5 bg-surface-container-lowest rounded-2xl border border-outline-variant/40 p-5 shadow-sm space-y-3 h-fit">
            <div>
              <h3 className="text-sm font-bold text-on-surface">
                Prompts Específics per Subagent (8)
              </h3>
              <p className="text-xs text-on-surface-variant mt-0.5">
                Opcional. Afegeix instruccions concretes per a cada especialitat del Copilot.
              </p>
            </div>
            <div className="space-y-2">
              {SUBAGENTS_CATALEG.map((sub) => {
                const obert = subagentObert === sub.id;
                const valor = copilotConfig.subagent_prompts[sub.id] || "";
                const habilitat = copilotConfig.subagent_enabled[sub.id] ?? true;
                const personalitzat = Boolean(valor.trim());
                return (
                  <div
                    key={sub.id}
                    className={`rounded-xl border border-outline-variant/40 bg-surface-container-low overflow-hidden transition-opacity ${
                      habilitat ? "" : "opacity-65"
                    }`}
                  >
                    <button
                      type="button"
                      onClick={() => setSubagentObert(obert ? null : sub.id)}
                      className="w-full px-3.5 py-2.5 flex items-center justify-between gap-2 text-left hover:bg-surface-container transition-colors cursor-pointer"
                    >
                      <div className="min-w-0">
                        <div className="text-xs font-bold text-on-surface flex items-center gap-2">
                          <span className="truncate">{sub.nom}</span>
                          {!habilitat && (
                            <span className="px-1.5 py-0.5 rounded bg-surface-container-high text-on-surface-variant text-[10px] font-semibold shrink-0">
                              Desactivat
                            </span>
                          )}
                          {personalitzat && (
                            <span className="px-1.5 py-0.5 rounded bg-primary/15 text-primary text-[10px] font-semibold shrink-0">
                              Personalitzat
                            </span>
                          )}
                        </div>
                        <div className="text-[11px] text-on-surface-variant truncate">{sub.ambit}</div>
                      </div>
                      {obert ? (
                        <ChevronUp className="w-4 h-4 text-on-surface-variant shrink-0" />
                      ) : (
                        <ChevronDown className="w-4 h-4 text-on-surface-variant shrink-0" />
                      )}
                    </button>
                    {obert && (
                      <div className="px-3.5 pb-3.5 pt-2 space-y-2 border-t border-outline-variant/30">
                        <div className="flex items-center justify-between gap-2">
                          <div className="text-[10px] font-mono text-on-surface-variant">{sub.id}</div>
                          <label className="inline-flex items-center gap-1.5 text-[11px] font-semibold text-on-surface cursor-pointer">
                            <input
                              type="checkbox"
                              disabled={!potEditarConfig}
                              checked={habilitat}
                              onChange={(e) =>
                                setCopilotConfig((prev) => ({
                                  ...prev,
                                  subagent_enabled: {
                                    ...prev.subagent_enabled,
                                    [sub.id]: e.target.checked,
                                  },
                                }))
                              }
                              className="rounded border-outline-variant accent-primary"
                            />
                            <span>Actiu</span>
                          </label>
                        </div>
                        <textarea
                          rows={4}
                          disabled={!potEditarConfig}
                          value={valor}
                          onChange={(e) =>
                            setCopilotConfig((prev) => ({
                              ...prev,
                              subagent_prompts: {
                                ...prev.subagent_prompts,
                                [sub.id]: e.target.value,
                              },
                            }))
                          }
                          placeholder={`Instruccions addicionals per a ${sub.nom}...`}
                          className="w-full rounded-xl border border-outline-variant bg-surface-container-lowest text-on-surface p-2.5 text-xs leading-relaxed outline-none focus:border-primary disabled:opacity-70"
                        />
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </form>
      )}

      {/* 2. AUDITORIA GARANTIES 365 DIES */}
      {pestanya === "GARANTIES" && (
        <div className="bg-surface-container-lowest rounded-2xl border border-outline-variant/40 p-6 shadow-sm space-y-5">
          <div>
            <h2 className="text-base font-bold text-on-surface flex items-center gap-2">
              <Shield className="w-4 h-4 text-primary" />
              Auditoria de Garanties (Fabricant 2 anys / Mà d&apos;Obra 90 dies)
            </h2>
            <p className="text-xs text-on-surface-variant mt-1">
              Comprova l&apos;historial dels últims 365 dies per client o el número de sèrie d&apos;una eina abans de pressupostar.
            </p>
          </div>
          <form onSubmit={executarAuditoriaGaranties} className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <select
              value={garantiaClientId}
              onChange={(e) => setGarantiaClientId(e.target.value)}
              className="rounded-xl border border-outline-variant bg-surface-container-low px-3 py-2 text-xs"
            >
              <option value="">Selecciona Client (opcional)...</option>
              {clients.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.codi ? `${c.codi} · ` : ""}{c.rao_social}
                </option>
              ))}
            </select>
            <input
              type="text"
              value={garantiaNumSerie}
              onChange={(e) => setGarantiaNumSerie(e.target.value)}
              placeholder="Número de sèrie d'equip (opcional)..."
              className="rounded-xl border border-outline-variant bg-surface-container-low px-3 py-2 text-xs"
            />
            <button
              type="submit"
              disabled={cercantGaranties || (!garantiaClientId && !garantiaNumSerie.trim())}
              className="rounded-xl bg-primary text-on-primary text-xs font-bold px-4 py-2 hover:opacity-90 disabled:opacity-50 cursor-pointer"
            >
              {cercantGaranties ? "Auditant..." : "Auditar Garanties"}
            </button>
          </form>

          {garantiaResultat && (
            <div className="space-y-4 pt-2">
              {garantiaResultat.missatge && (
                <div className="p-3 rounded-xl bg-surface-container-low border border-outline-variant/40 text-xs text-on-surface">
                  {garantiaResultat.missatge}
                </div>
              )}
              {Array.isArray(garantiaResultat.garanties) && garantiaResultat.garanties.length > 0 && (
                <div className="space-y-2">
                  {garantiaResultat.garanties.map((g: any, i: number) => (
                    <div
                      key={i}
                      className={`p-3 rounded-xl border text-xs ${
                        g.activa
                          ? "bg-amber-50 border-amber-200 text-amber-900"
                          : "bg-surface-container-low border-outline-variant/40 text-on-surface"
                      }`}
                    >
                      <div className="font-bold">{g.tipus}</div>
                      <p className="mt-1">{g.missatge}</p>
                    </div>
                  ))}
                </div>
              )}
              {Array.isArray(garantiaResultat.intervencions_365_dies) && (
                <div>
                  <h4 className="text-xs font-bold uppercase text-on-surface-variant mb-2">
                    Intervencions darrers 365 dies ({garantiaResultat.intervencions_365_dies.length})
                  </h4>
                  {garantiaResultat.intervencions_365_dies.length === 0 ? (
                    <div className="text-xs text-on-surface-variant">Cap intervenció registrada en els darrers 365 dies.</div>
                  ) : (
                    <div className="divide-y divide-outline-variant/30 border border-outline-variant/30 rounded-xl">
                      {garantiaResultat.intervencions_365_dies.map((it: any) => (
                        <div key={it.ordre_id} className="p-3 flex items-center justify-between text-xs">
                          <div>
                            <span className="font-mono font-bold text-primary mr-2">{it.codi}</span>
                            <span className="font-medium text-on-surface">{it.titol}</span>
                          </div>
                          <span className="font-mono text-on-surface-variant">
                            {it.data} · {it.estat}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* 3. PERITATGE D'INCIDÈNCIES & MEMORÀNDUMS HITL */}
      {pestanya === "INCIDENCIES" && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <form
            onSubmit={generarPeritatgeIncidencia}
            className="bg-surface-container-lowest rounded-2xl border border-outline-variant/40 p-5 shadow-sm space-y-4 h-fit"
          >
            <h2 className="text-base font-bold text-on-surface flex items-center gap-2">
              <Wrench className="w-4 h-4 text-primary" />
              Nou Peritatge d&apos;Incidència (Memoràndum HITL)
            </h2>
            {peritFeedback && (
              <div className="p-3 rounded-xl bg-primary/10 border border-primary/30 text-xs text-primary font-medium">
                {peritFeedback}
              </div>
            )}
            <div>
              <label className="block text-[11px] font-bold uppercase text-on-surface-variant mb-1">
                Ordre de Treball (opcional)
              </label>
              <select
                value={peritOtId}
                onChange={(e) => setPeritOtId(e.target.value)}
                className="w-full rounded-xl border border-outline-variant bg-surface-container-low px-3 py-2 text-xs"
              >
                <option value="">Sense vincular a OT...</option>
                {feines.map((ot) => (
                  <option key={ot.id} value={ot.id}>
                    {ot.codi} · {ot.titol}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-[11px] font-bold uppercase text-on-surface-variant mb-1">
                Dictat / Observació tècnica de camp *
              </label>
              <textarea
                rows={4}
                required
                value={peritText}
                onChange={(e) => setPeritText(e.target.value)}
                placeholder="Ex: En picar paret antiga apareixen canonades corroïdes no visibles a visita prèvia..."
                className="w-full rounded-xl border border-outline-variant bg-surface-container-low px-3 py-2 text-xs"
              />
            </div>
            <div>
              <label className="block text-[11px] font-bold uppercase text-on-surface-variant mb-1">
                Confiança acústica (0.0 – 1.0)
              </label>
              <input
                type="number"
                step="0.05"
                min="0"
                max="1"
                value={peritConfianca}
                onChange={(e) => setPeritConfianca(e.target.value)}
                className="w-32 rounded-xl border border-outline-variant bg-surface-container-low px-3 py-2 text-xs font-mono"
              />
            </div>
            <button
              type="submit"
              disabled={generantPerit}
              className="px-4 py-2 rounded-xl bg-primary text-on-primary text-xs font-bold hover:opacity-90 disabled:opacity-50 cursor-pointer"
            >
              {generantPerit ? "Generant..." : "Generar Proposta de Memoràndum"}
            </button>
          </form>

          <div className="bg-surface-container-lowest rounded-2xl border border-outline-variant/40 p-5 shadow-sm space-y-3">
            <h3 className="text-sm font-bold text-on-surface">Memoràndums Tècnics ({memos.length})</h3>
            {memos.length === 0 ? (
              <div className="p-8 text-center text-xs text-on-surface-variant border border-dashed border-outline-variant/40 rounded-xl">
                Cap memoràndum tècnic registrat.
              </div>
            ) : (
              <div className="space-y-3 max-h-[480px] overflow-y-auto">
                {memos.map((m) => (
                  <div key={m.id} className="p-3.5 rounded-xl border border-outline-variant/40 bg-surface-container-low space-y-2 text-xs">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-bold text-primary">{m.dictamen_pericial}</span>
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-surface-container text-on-surface">
                        {m.estat}
                      </span>
                    </div>
                    {m.motiu_dictamen && <p className="text-on-surface-variant">{m.motiu_dictamen}</p>}
                    {!esEnginyer && m.cost_estimat_total != null && (
                      <div className="font-mono text-[11px] font-bold">
                        Cost estimat: {Number(m.cost_estimat_total).toFixed(2)} €
                      </div>
                    )}
                    {!m.validat_per_enginyer && (
                      <div className="flex gap-2 pt-1">
                        <button
                          type="button"
                          onClick={() => validarMemorandum(m.id, "APROVAR")}
                          className="px-3 py-1 rounded-lg bg-emerald-600 text-white text-[11px] font-bold hover:bg-emerald-700"
                        >
                          Aprovar HITL
                        </button>
                        <button
                          type="button"
                          onClick={() => validarMemorandum(m.id, "REBUTJAR")}
                          className="px-3 py-1 rounded-lg border border-outline-variant text-on-surface text-[11px] font-bold hover:bg-surface-container"
                        >
                          Rebutjar
                        </button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* 4. RECONCILIACIÓ POST-OBRA & ALERTES COPILOT */}
      {pestanya === "RECONCILIACIO" && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="bg-surface-container-lowest rounded-2xl border border-outline-variant/40 p-5 shadow-sm space-y-4">
            <h2 className="text-base font-bold text-on-surface flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-primary" />
              Reconciliació Post-Obra (4 Pilars)
            </h2>
            <form onSubmit={executarReconciliacio} className="space-y-3 text-xs">
              <div>
                <label className="block text-[11px] font-bold uppercase text-on-surface-variant mb-1">
                  Ordre de Treball *
                </label>
                <select
                  required
                  value={reconcOtId}
                  onChange={(e) => setReconcOtId(e.target.value)}
                  className="w-full rounded-xl border border-outline-variant bg-surface-container-low px-3 py-2"
                >
                  <option value="">Selecciona OT...</option>
                  {feines.map((ot) => (
                    <option key={ot.id} value={ot.id}>
                      {ot.codi} · {ot.titol}
                    </option>
                  ))}
                </select>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] font-bold text-on-surface-variant mb-1">Hores previstes</label>
                  <input
                    type="number"
                    step="0.5"
                    value={reconcHoresPrevistes}
                    onChange={(e) => setReconcHoresPrevistes(e.target.value)}
                    className="w-full rounded-xl border border-outline-variant bg-surface-container-low px-3 py-2 font-mono"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-bold text-on-surface-variant mb-1">Hores reals</label>
                  <input
                    type="number"
                    step="0.5"
                    value={reconcHoresReals}
                    onChange={(e) => setReconcHoresReals(e.target.value)}
                    className="w-full rounded-xl border border-outline-variant bg-surface-container-low px-3 py-2 font-mono"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-bold text-on-surface-variant mb-1">Km reals</label>
                  <input
                    type="number"
                    step="1"
                    value={reconcKmReals}
                    onChange={(e) => setReconcKmReals(e.target.value)}
                    className="w-full rounded-xl border border-outline-variant bg-surface-container-low px-3 py-2 font-mono"
                  />
                </div>
                {!esEnginyer && (
                  <div>
                    <label className="block text-[11px] font-bold text-on-surface-variant mb-1">Despeses camp (€)</label>
                    <input
                      type="number"
                      step="0.01"
                      value={reconcDespeses}
                      onChange={(e) => setReconcDespeses(e.target.value)}
                      className="w-full rounded-xl border border-outline-variant bg-surface-container-low px-3 py-2 font-mono"
                    />
                  </div>
                )}
              </div>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={reconcSyncPendent}
                  onChange={(e) => setReconcSyncPendent(e.target.checked)}
                />
                <span>Marcar sincronització offline pendent de camp</span>
              </label>
              <button
                type="submit"
                disabled={executantReconc || !reconcOtId}
                className="px-4 py-2 rounded-xl bg-primary text-on-primary font-bold hover:opacity-90 disabled:opacity-50 cursor-pointer"
              >
                {executantReconc ? "Calculant..." : "Executar Reconciliació Post-Obra"}
              </button>
            </form>

            {reconcResultat && (
              <div className="p-4 rounded-xl border border-outline-variant/50 bg-surface-container-low space-y-2 text-xs">
                <div className="font-bold text-primary">
                  Estat: {reconcResultat.estat || reconcResultat.estat_conciliacio}
                </div>
                {reconcResultat.missatge && <p>{reconcResultat.missatge}</p>}
                {reconcResultat.detall_merma && <p className="text-amber-700">{reconcResultat.detall_merma}</p>}
                {!esEnginyer && reconcResultat.marge_real_liquidat_percentatge != null && (
                  <p className="font-mono">
                    Marge previst {reconcResultat.marge_previst_percentatge}% → Marge real{" "}
                    <strong>{reconcResultat.marge_real_liquidat_percentatge}%</strong>
                  </p>
                )}
                {reconcResultat.auditoria_id && reconcResultat.estat === "PENDENT_CONFIRMACIO" && (
                  <div className="flex gap-2 pt-1">
                    <button
                      type="button"
                      onClick={() => aprovarPressupostReconciliacio(reconcResultat.auditoria_id, true)}
                      className="px-3 py-1.5 rounded-lg bg-emerald-600 text-white font-bold"
                    >
                      Aprovar i Trametre a Facturació
                    </button>
                    <button
                      type="button"
                      onClick={() => aprovarPressupostReconciliacio(reconcResultat.auditoria_id, false)}
                      className="px-3 py-1.5 rounded-lg border border-outline-variant font-bold"
                    >
                      Rebutjar
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>

          <div className="bg-surface-container-lowest rounded-2xl border border-outline-variant/40 p-5 shadow-sm space-y-3">
            <h3 className="text-sm font-bold text-on-surface">
              Alertes Actives de Garantia i Recompra ({alertesCopilot.length})
            </h3>
            {alertesCopilot.length === 0 ? (
              <div className="p-8 text-center text-xs text-on-surface-variant border border-dashed border-outline-variant/40 rounded-xl">
                Cap alerta activa al Copilot.
              </div>
            ) : (
              <div className="space-y-2.5 max-h-[460px] overflow-y-auto">
                {alertesCopilot.map((al) => (
                  <div key={al.id} className="p-3 rounded-xl border border-outline-variant/40 bg-surface-container-low text-xs space-y-1">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-mono font-bold text-primary">{al.tipus_alerta}</span>
                      <span className="text-[10px] font-mono text-on-surface-variant">{al.estat}</span>
                    </div>
                    <p className="text-on-surface">{al.missatge}</p>
                    {al.tipus_alerta === "RECOMPRA_STOCK" && (
                      <Link
                        href="/gestio/magatzem?tab=RECOMPRA_STOCK"
                        className="inline-flex items-center gap-1 text-[11px] font-bold text-primary hover:underline pt-1"
                      >
                        Obrir safata d&apos;emails de recompra →
                      </Link>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* 5. BASE DE CONEIXEMENT RAG (CREAR, EDITAR I ELIMINAR PROTOCOLS) */}
      {pestanya === "RAG" && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="bg-surface-container-lowest rounded-2xl shadow-sm border border-outline-variant/40 p-6 border-l-4 border-l-primary space-y-4 h-fit">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <div className="bg-primary/10 p-2 rounded-full">
                  <Layers className="h-5 w-5 text-primary" />
                </div>
                <div>
                  <h2 className="text-base font-bold text-on-surface">
                    {ragEditId ? "Editar Protocol al Disc Sobirà" : "Nou Protocol al Disc Sobirà"}
                  </h2>
                  <p className="text-xs text-on-surface-variant">
                    Directori <span className="font-mono">10_protocols_i_manuals/procediments_interns</span>
                  </p>
                </div>
              </div>
              {ragEditId && (
                <button
                  type="button"
                  onClick={cancelarEdicioRag}
                  className="px-2.5 py-1 rounded-lg border border-outline-variant text-xs font-semibold text-on-surface-variant hover:text-on-surface inline-flex items-center gap-1 cursor-pointer"
                >
                  <X className="w-3.5 h-3.5" />
                  <span>Cancel·lar</span>
                </button>
              )}
            </div>

            {feedbackRag && (
              <div
                className={`p-3 rounded-xl border text-xs font-body-strong flex items-center gap-2 ${
                  feedbackRag.type === "ok"
                    ? "bg-emerald-50 border-emerald-200 text-emerald-800"
                    : "bg-rose-50 border-rose-200 text-rose-800"
                }`}
              >
                {feedbackRag.type === "ok" ? (
                  <CheckCircle2 className="w-4 h-4 shrink-0" />
                ) : (
                  <AlertTriangle className="w-4 h-4 shrink-0" />
                )}
                <span>{feedbackRag.text}</span>
              </div>
            )}

            <form onSubmit={desarDocumentRag} className="space-y-4">
              <div>
                <label className="block text-xs font-bold text-on-surface-variant mb-1">
                  Títol del Protocol / Document *
                </label>
                <input
                  type="text"
                  name="titol"
                  required
                  value={ragTitol}
                  onChange={(e) => setRagTitol(e.target.value)}
                  className="block w-full rounded-xl border-outline-variant bg-surface-container-low text-on-surface p-2.5 border text-xs outline-none focus:border-primary"
                  placeholder="Ex: Protocol d'Actuació Manteniment Bomba..."
                />
              </div>
              <div>
                <label className="block text-xs font-bold text-on-surface-variant mb-1">
                  Informació, Normativa o Procediment *
                </label>
                <textarea
                  name="contingut"
                  required
                  rows={7}
                  value={ragContingut}
                  onChange={(e) => setRagContingut(e.target.value)}
                  className="block w-full rounded-xl border-outline-variant bg-surface-container-low text-on-surface p-2.5 border text-xs leading-relaxed outline-none focus:border-primary"
                  placeholder="Descriu pas a pas el protocol o detalls tècnics..."
                />
              </div>
              <div>
                <label className="block text-xs font-bold text-on-surface-variant mb-1">
                  Paraules Clau (Tags, separades per coma)
                </label>
                <input
                  type="text"
                  name="tags"
                  value={ragTags}
                  onChange={(e) => setRagTags(e.target.value)}
                  className="block w-full rounded-xl border-outline-variant bg-surface-container-low text-on-surface p-2.5 border text-xs outline-none focus:border-primary"
                  placeholder="ex: manteniment, bomba, hidràulic"
                />
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="submit"
                  disabled={submittingRag}
                  className="inline-flex items-center px-5 py-2.5 rounded-xl text-xs font-bold text-on-primary bg-primary hover:opacity-90 disabled:opacity-60 cursor-pointer"
                >
                  {ragEditId ? (
                    <Save className="mr-2 h-3.5 w-3.5" />
                  ) : (
                    <Send className="mr-2 h-3.5 w-3.5" />
                  )}
                  {submittingRag
                    ? "Desant al disc..."
                    : ragEditId
                    ? "Desar Canvis del Protocol"
                    : "Afegir Protocol al Disc"}
                </button>
                {ragEditId && (
                  <button
                    type="button"
                    onClick={cancelarEdicioRag}
                    className="px-4 py-2.5 rounded-xl border border-outline-variant/60 text-xs font-bold text-on-surface hover:border-primary cursor-pointer"
                  >
                    Descartar
                  </button>
                )}
              </div>
            </form>
          </div>

          <div className="bg-surface-container-lowest rounded-2xl border border-outline-variant/40 p-5 shadow-sm space-y-3">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <h3 className="text-sm font-bold text-on-surface flex items-center gap-2">
                <FileText className="w-4 h-4 text-primary" />
                Protocols i Manuals al Disc ({ragDocs.length})
              </h3>
              {ragDocs.length > 0 && (
                <div className="relative">
                  <Search className="w-3.5 h-3.5 text-on-surface-variant absolute left-2.5 top-1/2 -translate-y-1/2" />
                  <input
                    type="text"
                    value={ragCerca}
                    onChange={(e) => setRagCerca(e.target.value)}
                    placeholder="Filtrar protocols o tags..."
                    className="pl-8 pr-3 py-1.5 rounded-xl border border-outline-variant/60 bg-surface-container-low text-xs text-on-surface outline-none focus:border-primary w-full sm:w-56"
                  />
                </div>
              )}
            </div>

            {ragDocs.length === 0 ? (
              <div className="p-8 text-center text-xs text-on-surface-variant border border-dashed border-outline-variant/40 rounded-xl">
                Encara no hi ha protocols indexats al disc local de l&apos;empresa.
              </div>
            ) : ragDocsFiltrats.length === 0 ? (
              <div className="p-6 text-center text-xs text-on-surface-variant border border-dashed border-outline-variant/40 rounded-xl">
                Cap protocol coincideix amb &ldquo;{ragCerca}&rdquo;.
              </div>
            ) : (
              <div className="space-y-3 max-h-[540px] overflow-y-auto pr-1">
                {ragDocsFiltrats.map((doc) => {
                  const enEdicio = ragEditId === doc.id;
                  const confirmantEliminacio = ragConfirmDeleteId === doc.id;
                  return (
                    <div
                      key={doc.id}
                      className={`p-3.5 rounded-xl border space-y-2 transition-colors ${
                        enEdicio
                          ? "border-primary bg-primary/5"
                          : "border-outline-variant/40 bg-surface-container-low"
                      }`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="text-xs font-bold text-on-surface">{doc.titol}</div>
                        <div className="flex items-center gap-1.5 shrink-0">
                          <button
                            type="button"
                            onClick={() => iniciarEdicioRag(doc)}
                            className="px-2.5 py-1 rounded-lg border border-outline-variant/60 bg-surface-container-lowest text-[11px] font-semibold text-on-surface hover:border-primary hover:text-primary inline-flex items-center gap-1 cursor-pointer"
                          >
                            <Pencil className="w-3 h-3" />
                            <span>Editar</span>
                          </button>
                          {confirmantEliminacio ? (
                            <div className="flex items-center gap-1">
                              <button
                                type="button"
                                disabled={eliminantRagId === doc.id}
                                onClick={() => eliminarDocumentRag(doc.id)}
                                className="px-2 py-1 rounded-lg bg-rose-600 text-white text-[11px] font-bold hover:bg-rose-700 disabled:opacity-50 cursor-pointer"
                              >
                                {eliminantRagId === doc.id ? "..." : "Confirmar"}
                              </button>
                              <button
                                type="button"
                                onClick={() => setRagConfirmDeleteId(null)}
                                className="px-2 py-1 rounded-lg border border-outline-variant text-[11px] text-on-surface-variant hover:text-on-surface cursor-pointer"
                              >
                                No
                              </button>
                            </div>
                          ) : (
                            <button
                              type="button"
                              onClick={() => setRagConfirmDeleteId(doc.id)}
                              className="p-1.5 rounded-lg border border-outline-variant/60 bg-surface-container-lowest text-on-surface-variant hover:border-rose-300 hover:text-rose-700 cursor-pointer"
                              title="Eliminar protocol"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          )}
                        </div>
                      </div>
                      <p className="text-xs text-on-surface-variant whitespace-pre-wrap line-clamp-4">
                        {doc.contingut}
                      </p>
                      {doc.tags && (
                        <div className="flex flex-wrap gap-1 pt-0.5">
                          {doc.tags
                            .split(",")
                            .map((t) => t.trim())
                            .filter(Boolean)
                            .map((tag, i) => (
                              <span
                                key={`${doc.id}-tag-${i}`}
                                className="px-2 py-0.5 rounded-md bg-primary/10 text-primary text-[10px] font-mono"
                              >
                                {tag}
                              </span>
                            ))}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      )}

      <CopilotErrorModal
        error={popupError}
        onClose={() => setPopupError(null)}
        onOpenConfig={potEditarConfig ? () => setPestanya("CONFIG") : undefined}
        onRetry={
          ultimaPreguntaFallida
            ? () => {
                const retryPrompt = ultimaPreguntaFallida;
                setUltimaPreguntaFallida(null);
                enviarMissatgeXat(retryPrompt);
              }
            : undefined
        }
        canCheckStatus={true}
      />
    </div>
  );
}
