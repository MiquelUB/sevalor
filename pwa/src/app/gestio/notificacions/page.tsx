"use client";

import React, { useState, useMemo } from "react";
import {
  Bell,
  Search,
  Send,
  MessageSquare,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Phone,
  Mail,
  FileText,
  Paperclip,
  X,
  ExternalLink,
  Shield,
  ShieldAlert,
  Bot,
  Truck,
  MapPin,
  Check,
  RotateCcw,
  Sparkles,
  Link as LinkIcon,
  HelpCircle,
  Archive,
  Image as ImageIcon,
  DollarSign,
  User,
  Radio,
  Plus,
} from "lucide-react";
import { useGestio } from "@/lib/gestio-context";

// Tipus de dades per a Spec 009
interface MissatgeUI {
  id: string;
  remitent_tipus: "OFICINA" | "CLIENT" | "BOT_IA" | "SISTEMA_CAMP";
  canal: "TELEGRAM" | "EMAIL" | "SMS" | "WEB_PWA";
  contingut_text: string;
  tipus_esdeveniment: string;
  adjunt_url?: string;
  token_aprobacio?: string;
  estat_aprobacio?: "PENDENT" | "ACCEPTAT" | "MODIFICACIONS_SOLICITADES";
  token_descarrega_factura?: string;
  hora: string;
}

interface ConversaUI {
  id: string;
  client_id: string;
  client_nom: string;
  client_codi: string;
  client_telefon?: string;
  client_email?: string;
  telegram_vinculat: boolean;
  ordre_treball_ref?: string;
  estat: "VERMELL_PRIORITARI" | "BLAU_OBERT" | "VERD_SOLUCIONAT";
  titol: string;
  ultim_missatge: string;
  ultim_missatge_hora: string;
  num_sense_llegir: number;
  es_arxivada: boolean;
  missatges: MissatgeUI[];
}

export default function GestioNotificacionsPage() {
  const { rolActiu } = useGestio();
  const esEnginyer = rolActiu === "ENGINYER";

  // Estat del cercador i filtres
  const [cerca, setCerca] = useState("");
  const [filtreEstat, setFiltreEstat] = useState<string>("TOTS");
  const [mostrarArxivades, setMostrarArxivades] = useState(false);

  // Converses inicials representatives (Dia 0 / Dades de negoci)
  const [converses, setConverses] = useState<ConversaUI[]>([
    {
      id: "conv-1",
      client_id: "cli-01",
      client_nom: "Agropecuària del Penedès SL",
      client_codi: "CLI-0142",
      client_telefon: "+34 651 23 98 40",
      client_email: "administracio@agropenedes.cat",
      telegram_vinculat: true,
      ordre_treball_ref: "",
      estat: "VERMELL_PRIORITARI",
      titol: "Fuita a colze PE-100 Ø110 Finca Els Arcs",
      ultim_missatge: "Fotografia d'avaria enviada pel client",
      ultim_missatge_hora: "10:42",
      num_sense_llegir: 2,
      es_arxivada: false,
      missatges: [
        {
          id: "m-1",
          remitent_tipus: "SISTEMA_CAMP",
          canal: "TELEGRAM",
          contingut_text: "L'equip tècnic de SEVALOR ha iniciat el trajecte cap a la finca (Arribada estimada: 09:30).",
          tipus_esdeveniment: "OPERARI_EN_CAMI",
          hora: "09:05",
        },
        {
          id: "m-2",
          remitent_tipus: "SISTEMA_CAMP",
          canal: "TELEGRAM",
          contingut_text: "La colla ha confirmat l'arribada a la finca Els Arcs i inicia la inspecció del sector B-04.",
          tipus_esdeveniment: "OPERARI_ARRIBAT",
          hora: "09:28",
        },
        {
          id: "m-3",
          remitent_tipus: "CLIENT",
          canal: "TELEGRAM",
          contingut_text: "Hem detectat que l'aigua surt amb molta pressió pel colze de derivació. Us passo una foto.",
          tipus_esdeveniment: "MISSATGE_TEXT",
          hora: "10:35",
        },
        {
          id: "m-4",
          remitent_tipus: "CLIENT",
          canal: "TELEGRAM",
          contingut_text: "Foto d'avaria adjuntada (colze fissurat).",
          tipus_esdeveniment: "INCIDENCIA_FOTO",
          adjunt_url: "/docs/fotos/avaria_colze_110.webp",
          hora: "10:36",
        },
        {
          id: "m-5",
          remitent_tipus: "BOT_IA",
          canal: "TELEGRAM",
          contingut_text: "Aquesta incidència té prioritat alta i l'he traslladat immediatament a l'Enginyer de guàrdia.",
          tipus_esdeveniment: "ESCALADA_IA",
          hora: "10:36",
        },
      ],
    },
    {
      id: "conv-2",
      client_id: "cli-02",
      client_nom: "Finca Mas Salagros Ecoresort",
      client_codi: "CLI-0089",
      client_telefon: "+34 682 99 11 22",
      client_email: "manteniment@massalagros.cat",
      telegram_vinculat: true,
      ordre_treball_ref: "",
      estat: "BLAU_OBERT",
      titol: "Pressupost suplementari Memòndum (Electrobalbula 2\")",
      ultim_missatge: "Pressupost suplementari de 340,00 € pendent d'acceptació",
      ultim_missatge_hora: "Ahir",
      num_sense_llegir: 0,
      es_arxivada: false,
      missatges: [
        {
          id: "m-21",
          remitent_tipus: "OFICINA",
          canal: "TELEGRAM",
          contingut_text: "Hem revisat el sector nord i cal substituir l'electrovàlvula de 2\" malmesa per sobretensió.",
          tipus_esdeveniment: "MISSATGE_TEXT",
          hora: "Ahir 16:15",
        },
        {
          id: "m-22",
          remitent_tipus: "OFICINA",
          canal: "TELEGRAM",
          contingut_text: "Pressupost suplementari Memòndum: Reposició electrovàlvula 2\" Bermad + mà d'obra urgent (Total: 340,00 €).",
          tipus_esdeveniment: "MEMORANDUM_PRESSUPOST",
          token_aprobacio: "TOK-PRES-9941",
          estat_aprobacio: "PENDENT",
          hora: "Ahir 16:16",
        },
      ],
    },
    {
      id: "conv-3",
      client_id: "cli-03",
      client_nom: "Comunitat de Regants Segarra-Garrigues (S-4)",
      client_codi: "CLI-0012",
      client_telefon: "+34 611 00 22 44",
      client_email: "secretaria@regants-sg.cat",
      telegram_vinculat: false,
      ordre_treball_ref: "",
      estat: "VERD_SOLUCIONAT",
      titol: "Manteniment preventiu hidrant H-04 (Tancat)",
      ultim_missatge: "Feina completada amb 3 fotos de protocol",
      ultim_missatge_hora: "04/09",
      num_sense_llegir: 0,
      es_arxivada: true,
      missatges: [
        {
          id: "m-31",
          remitent_tipus: "SISTEMA_CAMP",
          canal: "EMAIL",
          contingut_text: "La feina a la finca ha estat completada i validada amb el protocol de 3 fotografies obligatòries.",
          tipus_esdeveniment: "FEINA_ACABADA",
          hora: "04/09 14:20",
        },
      ],
    },
  ]);

  const [conversaActivaId, setConversaActivaId] = useState<string>("conv-1");
  const [textResposta, setTextResposta] = useState("");
  const [canalSeleccionat, setCanalSeleccionat] = useState<"TELEGRAM" | "EMAIL" | "SMS">("TELEGRAM");

  // Modals & Notificacions
  const [modalInvitacioObert, setModalInvitacioObert] = useState(false);
  const [modalNovaConversaObert, setModalNovaConversaObert] = useState(false);
  const [invitacioGenerada, setInvitacioGenerada] = useState<{ token: string; link: string; expira: string } | null>(null);
  const [alertaVeto, setAlertaVeto] = useState<string | null>(null);
  const [toastExit, setToastExit] = useState<string | null>(null);

  // Conversa seleccionada
  const conversaActiva = useMemo(() => {
    return converses.find((c) => c.id === conversaActivaId) || null;
  }, [converses, conversaActivaId]);

  // Converses filtrades per cercador i estat
  const conversesFiltrades = useMemo(() => {
    return converses.filter((c) => {
      if (!mostrarArxivades && c.es_arxivada) return false;
      if (mostrarArxivades && !c.es_arxivada) return false;
      if (filtreEstat !== "TOTS" && c.estat !== filtreEstat) return false;
      if (!cerca) return true;
      const q = cerca.toLowerCase();
      return (
        c.client_nom.toLowerCase().includes(q) ||
        c.titol.toLowerCase().includes(q) ||
        c.client_codi.toLowerCase().includes(q) ||
        (c.ordre_treball_ref && c.ordre_treball_ref.toLowerCase().includes(q))
      );
    });
  }, [converses, cerca, filtreEstat, mostrarArxivades]);

  // Mètriques agregades
  const metrics = useMemo(() => {
    const total = converses.filter((c) => !c.es_arxivada).length;
    const vermell = converses.filter((c) => c.estat === "VERMELL_PRIORITARI" && !c.es_arxivada).length;
    const blau = converses.filter((c) => c.estat === "BLAU_OBERT" && !c.es_arxivada).length;
    const verd = converses.filter((c) => c.es_arxivada || c.estat === "VERD_SOLUCIONAT").length;
    return { total, vermell, blau, verd };
  }, [converses]);

  // Enviament de missatge manual (HITL)
  const handleEnviarMissatge = (e: React.FormEvent) => {
    e.preventDefault();
    if (!textResposta.trim() || !conversaActiva) return;

    const nouMsg: MissatgeUI = {
      id: `m-${Date.now()}`,
      remitent_tipus: "OFICINA",
      canal: canalSeleccionat,
      contingut_text: textResposta.trim(),
      tipus_esdeveniment: "MISSATGE_TEXT",
      hora: new Date().toLocaleTimeString("ca-ES", { hour: "2-digit", minute: "2-digit" }),
    };

    setConverses((prev) =>
      prev.map((c) => {
        if (c.id !== conversaActiva.id) return c;
        return {
          ...c,
          ultim_missatge: textResposta.trim(),
          ultim_missatge_hora: "Ara",
          estat: c.estat === "VERD_SOLUCIONAT" ? "BLAU_OBERT" : c.estat,
          es_arxivada: false,
          missatges: [...c.missatges, nouMsg],
        };
      })
    );

    setTextResposta("");
    setToastExit("Missatge transmès al client d'acord amb el protocol HITL.");
    setTimeout(() => setToastExit(null), 3000);
  };

  // Marcar conversa com a solucionada (Verd) i arxivar
  const handleMarcarSolucionat = () => {
    if (!conversaActiva) return;
    setConverses((prev) =>
      prev.map((c) => {
        if (c.id !== conversaActiva.id) return c;
        return {
          ...c,
          estat: "VERD_SOLUCIONAT",
          es_arxivada: true,
          num_sense_llegir: 0,
        };
      })
    );
    setToastExit("Conversa marcada com a solucionada i arxivada a la fitxa del client.");
    setTimeout(() => setToastExit(null), 3000);
  };

  // Resposta simulada a Pressupost (Memòndum)
  const handleSimularRespostaPressupost = (token: string, accio: "ACCEPTAR" | "MODIFICACIONS") => {
    setConverses((prev) =>
      prev.map((c) => {
        return {
          ...c,
          missatges: c.missatges.map((m) => {
            if (m.token_aprobacio !== token) return m;
            return {
              ...m,
              estat_aprobacio: accio === "ACCEPTAR" ? "ACCEPTAT" : "MODIFICACIONS_SOLICITADES",
            };
          }),
        };
      })
    );
    if (accio === "ACCEPTAR") {
      setToastExit("Pressupost acceptat pel client amb segellat idempotent. Partida injectada a l'OT.");
    } else {
      setToastExit("Sol·licitud de modificacions rebuda. S'ha alertat a l'enginyer responsable.");
    }
    setTimeout(() => setToastExit(null), 4000);
  };

  // Generar invitació Telegram deep linking (48h)
  const handleGenerarInvitacioTelegram = () => {
    if (!conversaActiva) return;
    const token = Math.random().toString(36).substring(2, 10);
    const expira = new Date(Date.now() + 48 * 3600 * 1000).toLocaleString("ca-ES");
    setInvitacioGenerada({
      token,
      link: `https://t.me/sevalor_bot?start=${token}`,
      expira,
    });
    setModalInvitacioObert(true);
  };

  // Intent d'enviament de factura Veri*factu (comprovació de veto d'enginyer)
  const handleIntentEnviarFactura = () => {
    if (esEnginyer) {
      setAlertaVeto("Veto d'Enginyer (Spec 009 RF-28): L'emissió o enviament de factures Veri*factu està reservada a Secretaria i Direcció. Tenir aquest rol bloqueja la tramesa fiscal amb HTTP 403.");
      return;
    }
    setToastExit("Factura generada i tramesa amb token temporal de 72 hores des d'Hetzner Alemanya.");
    setTimeout(() => setToastExit(null), 3500);
  };

  return (
    <div className="flex flex-col h-[calc(100vh-3.5rem)] bg-slate-100 dark:bg-slate-950 text-slate-900 dark:text-slate-100 overflow-hidden font-sans">
      {/* 1. CAPÇALERA D'ALTA DENSITAT & KPI METRICS */}
      <div className="bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 px-4 py-3 shrink-0 shadow-sm z-20">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-indigo-50 dark:bg-indigo-950/60 border border-indigo-200 dark:border-indigo-800 text-indigo-600 dark:text-indigo-400">
              <MessageSquare className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-base font-bold text-slate-900 dark:text-slate-100 leading-none">
                  Hub de Notificacions & Canal Telegram
                </h1>
                <span className="text-[10px] font-black uppercase px-2 py-0.5 rounded bg-sky-100 dark:bg-sky-950/60 border border-sky-300 dark:border-sky-800 text-sky-800 dark:text-sky-300">
                  Telegram Aiogram
                </span>
                <span className="text-[10px] font-black uppercase px-2 py-0.5 rounded bg-emerald-100 dark:bg-emerald-950/60 border border-emerald-300 dark:border-emerald-800 text-emerald-800 dark:text-emerald-300">
                  RAG LM Studio Local
                </span>
                <span className="text-[10px] font-black uppercase px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 border border-slate-200 dark:border-slate-700">
                  Hetzner UE
                </span>
              </div>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                Safata de comunicació multicanal supervisada (HITL) amb clients finals i traçabilitat d&apos;avisos de camp.
              </p>
            </div>
          </div>

          {/* Mètriques de capçalera (Codi cromàtic) */}
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs">
              <span className="text-slate-500 font-semibold">Actives:</span>
              <span className="font-bold text-slate-900 dark:text-slate-100">{metrics.total}</span>
            </div>

            <button
              onClick={() => setFiltreEstat("VERMELL_PRIORITARI")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-bold transition ${
                filtreEstat === "VERMELL_PRIORITARI"
                  ? "bg-rose-100 dark:bg-rose-950/80 border-rose-300 dark:border-rose-700 text-rose-800 dark:text-rose-300 ring-1 ring-rose-500/30"
                  : "bg-rose-50 dark:bg-rose-950/30 border-rose-200 dark:border-rose-900 text-rose-700 dark:text-rose-400 hover:bg-rose-100 dark:hover:bg-rose-900/50"
              }`}
            >
              <div className="w-2 h-2 rounded-full bg-rose-500 animate-pulse" />
              <span>Prioritàries: {metrics.vermell}</span>
            </button>

            <button
              onClick={() => setFiltreEstat("BLAU_OBERT")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-bold transition ${
                filtreEstat === "BLAU_OBERT"
                  ? "bg-sky-100 dark:bg-sky-950/80 border-sky-300 dark:border-sky-700 text-sky-800 dark:text-sky-300 ring-1 ring-sky-500/30"
                  : "bg-sky-50 dark:bg-sky-950/30 border-sky-200 dark:border-sky-900 text-sky-700 dark:text-sky-400 hover:bg-sky-100 dark:hover:bg-sky-900/50"
              }`}
            >
              <div className="w-2 h-2 rounded-full bg-sky-500" />
              <span>Obertes: {metrics.blau}</span>
            </button>

            <button
              onClick={() => {
                setFiltreEstat("TOTS");
                setMostrarArxivades(!mostrarArxivades);
              }}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-semibold transition ${
                mostrarArxivades
                  ? "bg-emerald-100 dark:bg-emerald-950 border-emerald-300 dark:border-emerald-700 text-emerald-800 dark:text-emerald-300"
                  : "bg-slate-50 dark:bg-slate-800 border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700"
              }`}
            >
              <Archive className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
              <span>{mostrarArxivades ? "Mostrant Arxivades" : `Arxiu (${metrics.verd})`}</span>
            </button>
          </div>
        </div>
      </div>

      {/* 2. ZONA PRINCIPAL DE TREBALL: SAFATA LATERAL + FIL DE XAT UNIFICAT */}
      <div className="flex-1 flex overflow-hidden">
        {/* SAFATA ESQUERRA: LLISTA DE CONVERSES AMB CERCA REACTIVA (<200 ms) */}
        <aside className="w-80 sm:w-96 bg-white dark:bg-slate-900 border-r border-slate-200 dark:border-slate-800 flex flex-col shrink-0 z-10">
          {/* Cercador de clients / OTs */}
          <div className="p-3 border-b border-slate-200 dark:border-slate-800 space-y-2">
            <div className="relative">
              <Search className="w-4 h-4 absolute left-2.5 top-2.5 text-slate-400" />
              <input
                type="text"
                value={cerca}
                onChange={(e) => setCerca(e.target.value)}
                placeholder="Cercar per client, telèfon, CLI o OT..."
                className="w-full pl-8 pr-3 py-1.5 text-xs rounded-lg bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-800 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />
            </div>

            {/* Selectors ràpids d'estat */}
            <div className="flex items-center justify-between text-xs">
              <div className="flex items-center gap-1">
                <button
                  onClick={() => setFiltreEstat("TOTS")}
                  className={`px-2 py-0.5 rounded text-[11px] font-semibold transition ${
                    filtreEstat === "TOTS"
                      ? "bg-slate-200 dark:bg-slate-700 text-slate-900 dark:text-slate-100"
                      : "text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
                  }`}
                >
                  Totes
                </button>
                <button
                  onClick={() => setFiltreEstat("VERMELL_PRIORITARI")}
                  className={`px-2 py-0.5 rounded text-[11px] font-semibold transition ${
                    filtreEstat === "VERMELL_PRIORITARI"
                      ? "bg-rose-100 dark:bg-rose-950 text-rose-700 dark:text-rose-300 font-bold"
                      : "text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
                  }`}
                >
                  Prioritàries
                </button>
                <button
                  onClick={() => setFiltreEstat("BLAU_OBERT")}
                  className={`px-2 py-0.5 rounded text-[11px] font-semibold transition ${
                    filtreEstat === "BLAU_OBERT"
                      ? "bg-sky-100 dark:bg-sky-950 text-sky-700 dark:text-sky-300 font-bold"
                      : "text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
                  }`}
                >
                  Obertes
                </button>
              </div>

              <button
                onClick={() => setModalNovaConversaObert(true)}
                className="text-xs text-indigo-600 dark:text-indigo-400 hover:underline font-bold flex items-center gap-0.5"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Nova</span>
              </button>
            </div>
          </div>

          {/* Llista de converses actives */}
          <div className="flex-1 overflow-y-auto p-2 space-y-1">
            {conversesFiltrades.length === 0 ? (
              <div className="p-8 text-center rounded-xl border border-dashed border-slate-200 dark:border-slate-800 mt-2">
                <Bell className="w-8 h-8 text-slate-300 dark:text-slate-700 mx-auto mb-2" />
                <p className="text-xs font-bold text-slate-700 dark:text-slate-300">
                  No hi ha converses ni notificacions actives
                </p>
                <p className="text-[11px] text-slate-400 mt-1">
                  Els missatges dels clients i avisos de camp apareixeran aquí sota Zero Mock Data.
                </p>
              </div>
            ) : (
              conversesFiltrades.map((conv) => {
                const esSeleccionada = conv.id === conversaActivaId;
                return (
                  <div
                    key={conv.id}
                    onClick={() => setConversaActivaId(conv.id)}
                    className={`p-3 rounded-xl cursor-pointer transition border text-left relative ${
                      esSeleccionada
                        ? "bg-indigo-50/50 dark:bg-indigo-950/40 border-indigo-300 dark:border-indigo-800 shadow-sm"
                        : "bg-transparent border-transparent hover:bg-slate-50 dark:hover:bg-slate-800/50"
                    }`}
                  >
                    {/* Indicador de semàfor d'estat a l'esquerra */}
                    <div
                      className={`absolute left-1.5 top-3.5 bottom-3.5 w-1 rounded-full ${
                        conv.estat === "VERMELL_PRIORITARI"
                          ? "bg-rose-500"
                          : conv.estat === "BLAU_OBERT"
                          ? "bg-sky-500"
                          : "bg-emerald-500"
                      }`}
                    />

                    <div className="pl-2">
                      <div className="flex items-start justify-between gap-1">
                        <span className="text-xs font-bold text-slate-900 dark:text-slate-100 truncate">
                          {conv.client_nom}
                        </span>
                        <span className="text-[10px] font-mono text-slate-400 shrink-0">
                          {conv.ultim_missatge_hora}
                        </span>
                      </div>

                      <div className="text-[11px] font-semibold text-slate-700 dark:text-slate-300 truncate mt-0.5">
                        {conv.titol}
                      </div>

                      <div className="text-[11px] text-slate-500 dark:text-slate-400 truncate mt-1">
                        {conv.ultim_missatge}
                      </div>

                      <div className="flex items-center justify-between mt-2 pt-1 border-t border-slate-200/60 dark:border-slate-800 text-[10px]">
                        <div className="flex items-center gap-1.5">
                          <span className="font-mono text-slate-400">{conv.client_codi}</span>
                          {conv.ordre_treball_ref && (
                            <span className="px-1 py-0.2 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 font-mono">
                              {conv.ordre_treball_ref}
                            </span>
                          )}
                        </div>

                        <div className="flex items-center gap-1.5">
                          {conv.telegram_vinculat ? (
                            <span className="flex items-center gap-0.5 text-sky-600 dark:text-sky-400 font-semibold">
                              <Radio className="w-2.5 h-2.5" /> Telegram
                            </span>
                          ) : (
                            <span className="text-slate-400 flex items-center gap-0.5">
                              <Mail className="w-2.5 h-2.5" /> Email
                            </span>
                          )}

                          {conv.num_sense_llegir > 0 && (
                            <span className="w-4 h-4 rounded-full bg-rose-500 text-white font-bold flex items-center justify-center text-[9px]">
                              {conv.num_sense_llegir}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </aside>

        {/* PANELL CENTRAL: FIL DE CONVERSA UNIFICAT & ACCIONS HITL */}
        <main className="flex-1 flex flex-col bg-slate-50 dark:bg-slate-900/60 overflow-hidden">
          {conversaActiva ? (
            <>
              {/* Capçalera del Xat Actiu */}
              <div className="p-3 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between shrink-0">
                <div className="flex items-center gap-3">
                  <div
                    className={`w-3 h-3 rounded-full ${
                      conversaActiva.estat === "VERMELL_PRIORITARI"
                        ? "bg-rose-500 animate-pulse"
                        : conversaActiva.estat === "BLAU_OBERT"
                        ? "bg-sky-500"
                        : "bg-emerald-500"
                    }`}
                  />
                  <div>
                    <div className="flex items-center gap-2">
                      <h2 className="text-xs sm:text-sm font-bold text-slate-900 dark:text-slate-100 leading-none">
                        {conversaActiva.client_nom}
                      </h2>
                      <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-slate-100 dark:bg-slate-800 text-slate-500">
                        {conversaActiva.client_codi}
                      </span>
                      {conversaActiva.ordre_treball_ref && (
                        <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-indigo-50 dark:bg-indigo-950 text-indigo-700 dark:text-indigo-300 font-semibold">
                          {conversaActiva.ordre_treball_ref}
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-2 mt-1 text-[11px] text-slate-500 dark:text-slate-400">
                      {conversaActiva.client_telefon && <span>{conversaActiva.client_telefon}</span>}
                      <span>•</span>
                      <span>{conversaActiva.titol}</span>
                    </div>
                  </div>
                </div>

                {/* Accions ràpides: Telegram link, Factura, Marcar solucionat */}
                <div className="flex items-center gap-2">
                  <button
                    onClick={handleGenerarInvitacioTelegram}
                    className="flex items-center gap-1.5 px-2.5 py-1 text-xs font-semibold rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 hover:bg-slate-100 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 transition"
                    title="Generar enllaç d'incorporació Telegram de 48h"
                  >
                    <LinkIcon className="w-3.5 h-3.5 text-sky-500" />
                    <span>Invitació Bot (48h)</span>
                  </button>

                  <button
                    onClick={handleIntentEnviarFactura}
                    className={`flex items-center gap-1.5 px-2.5 py-1 text-xs font-semibold rounded-lg border transition ${
                      esEnginyer
                        ? "bg-slate-100 dark:bg-slate-800 border-slate-200 dark:border-slate-700 text-slate-400 cursor-not-allowed"
                        : "bg-white dark:bg-slate-800 border-slate-300 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200"
                    }`}
                    title={esEnginyer ? "Veto d'Enginyer: Facturació restringida" : "Trametre factura amb token segur 72h"}
                  >
                    <DollarSign className="w-3.5 h-3.5 text-emerald-600" />
                    <span>Factura (72h)</span>
                  </button>

                  {!conversaActiva.es_arxivada && (
                    <button
                      onClick={handleMarcarSolucionat}
                      className="flex items-center gap-1.5 px-3 py-1 text-xs font-bold rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white transition shadow-sm"
                    >
                      <Check className="w-3.5 h-3.5" />
                      <span>Solucionat</span>
                    </button>
                  )}
                </div>
              </div>

              {/* Zona de Missatges Cronològics */}
              <div className="flex-1 overflow-y-auto p-4 space-y-3">
                {conversaActiva.missatges.map((msg) => {
                  const esOficina = msg.remitent_tipus === "OFICINA";
                  const esCamp = msg.remitent_tipus === "SISTEMA_CAMP";
                  const esBot = msg.remitent_tipus === "BOT_IA";
                  const esClient = msg.remitent_tipus === "CLIENT";

                  // Targeta especial d'Automatisme de Camp
                  if (esCamp) {
                    return (
                      <div key={msg.id} className="flex justify-center my-2">
                        <div className="max-w-md bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-3 shadow-sm flex items-start gap-2.5">
                          <div className="p-1.5 rounded-lg bg-indigo-50 dark:bg-indigo-950 text-indigo-600 dark:text-indigo-400 shrink-0">
                            {msg.tipus_esdeveniment === "OPERARI_EN_CAMI" ? (
                              <Truck className="w-4 h-4" />
                            ) : msg.tipus_esdeveniment === "OPERARI_ARRIBAT" ? (
                              <MapPin className="w-4 h-4" />
                            ) : (
                              <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                            )}
                          </div>
                          <div className="flex-1 text-xs">
                            <div className="flex items-center justify-between">
                              <span className="font-bold text-slate-800 dark:text-slate-200">
                                {msg.tipus_esdeveniment === "OPERARI_EN_CAMI"
                                  ? "Operari en camí"
                                  : msg.tipus_esdeveniment === "OPERARI_ARRIBAT"
                                  ? "Arribada a finca confirmada"
                                  : "Feina completada sobre terreny"}
                              </span>
                              <span className="text-[10px] font-mono text-slate-400">{msg.hora}</span>
                            </div>
                            <p className="text-slate-600 dark:text-slate-300 mt-1">{msg.contingut_text}</p>
                          </div>
                        </div>
                      </div>
                    );
                  }

                  // Targeta especial de Memòndum de Pressupost
                  if (msg.tipus_esdeveniment === "MEMORANDUM_PRESSUPOST") {
                    return (
                      <div key={msg.id} className="flex justify-end my-2">
                        <div className="max-w-lg bg-white dark:bg-slate-800 border-2 border-indigo-500 rounded-xl p-4 shadow-md text-xs">
                          <div className="flex items-center justify-between pb-2 border-b border-slate-200 dark:border-slate-700">
                            <div className="flex items-center gap-1.5 font-bold text-indigo-600 dark:text-indigo-400">
                              <DollarSign className="w-4 h-4" />
                              <span>Memòndum de Pressupost Suplementari</span>
                            </div>
                            <span className="text-[10px] font-mono text-slate-400">{msg.hora}</span>
                          </div>

                          <p className="mt-2 text-slate-800 dark:text-slate-200">{msg.contingut_text}</p>

                          {/* Botons d'aprovació interactiva */}
                          <div className="mt-3 pt-3 border-t border-slate-200 dark:border-slate-700 flex items-center justify-between gap-2">
                            {msg.estat_aprobacio === "ACCEPTAT" ? (
                              <div className="flex items-center gap-1.5 text-emerald-600 dark:text-emerald-400 font-bold">
                                <CheckCircle2 className="w-4 h-4" />
                                <span>Pressupost Acceptat (Idempotència Segellada)</span>
                              </div>
                            ) : msg.estat_aprobacio === "MODIFICACIONS_SOLICITADES" ? (
                              <div className="flex items-center gap-1.5 text-amber-600 dark:text-amber-400 font-bold">
                                <RotateCcw className="w-4 h-4" />
                                <span>Sol·licitud de Modificacions (En Revisió)</span>
                              </div>
                            ) : (
                              <div className="flex gap-2 w-full">
                                <button
                                  onClick={() =>
                                    handleSimularRespostaPressupost(msg.token_aprobacio!, "ACCEPTAR")
                                  }
                                  className="flex-1 py-1.5 px-3 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white font-bold transition flex items-center justify-center gap-1.5"
                                >
                                  <Check className="w-3.5 h-3.5" />
                                  <span>Acceptar Pressupost</span>
                                </button>
                                <button
                                  onClick={() =>
                                    handleSimularRespostaPressupost(msg.token_aprobacio!, "MODIFICACIONS")
                                  }
                                  className="py-1.5 px-3 rounded-lg border border-slate-300 dark:border-slate-600 text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700 font-semibold transition"
                                >
                                  Sol·licitar canvis
                                </button>
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    );
                  }

                  // Missatges normals de conversa (Oficina / Client / Bot IA)
                  return (
                    <div
                      key={msg.id}
                      className={`flex ${esOficina ? "justify-end" : "justify-start"} my-1`}
                    >
                      <div
                        className={`max-w-md rounded-2xl p-3 shadow-sm text-xs ${
                          esOficina
                            ? "bg-indigo-600 text-white rounded-br-xs"
                            : esBot
                            ? "bg-amber-50 dark:bg-amber-950/40 border border-amber-300 dark:border-amber-800 text-amber-900 dark:text-amber-200 rounded-bl-xs"
                            : "bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-800 dark:text-slate-200 rounded-bl-xs"
                        }`}
                      >
                        <div className="flex items-center justify-between gap-3 text-[10px] opacity-75 mb-1">
                          <span className="font-bold flex items-center gap-1">
                            {esOficina ? (
                              "Oficina Tècnica (HITL)"
                            ) : esBot ? (
                              <>
                                <Bot className="w-3 h-3" /> Assistent IA (RAG Local)
                              </>
                            ) : (
                              conversaActiva.client_nom
                            )}
                          </span>
                          <span className="font-mono">{msg.hora}</span>
                        </div>

                        <p className="leading-relaxed">{msg.contingut_text}</p>

                        {/* Imatge adjunta d'avaria */}
                        {msg.adjunt_url && (
                          <div className="mt-2 rounded-lg overflow-hidden border border-slate-200/40 bg-slate-900/10 p-1">
                            <div className="h-32 bg-slate-800 rounded flex items-center justify-center text-slate-400 font-mono text-[11px]">
                              [Miniatura Fotografia Avaria &le; 15MB • Hetzner AES-256]
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Barra Inferior d'Escriptura (Human-in-the-Loop) */}
              <form
                onSubmit={handleEnviarMissatge}
                className="p-3 bg-white dark:bg-slate-900 border-t border-slate-200 dark:border-slate-800 flex items-center gap-2 shrink-0"
              >
                {/* Selector de Canal */}
                <select
                  value={canalSeleccionat}
                  onChange={(e) => setCanalSeleccionat(e.target.value as any)}
                  className="text-xs p-2 rounded-lg bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 font-semibold"
                >
                  <option value="TELEGRAM">Telegram</option>
                  <option value="EMAIL">Correu Email</option>
                  <option value="SMS">Missatge SMS</option>
                </select>

                <input
                  type="text"
                  value={textResposta}
                  onChange={(e) => setTextResposta(e.target.value)}
                  placeholder="Escriu una resposta supervisada (HITL)..."
                  className="flex-1 text-xs p-2 rounded-lg bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-800 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                />

                <button
                  type="submit"
                  disabled={!textResposta.trim()}
                  className={`p-2 rounded-lg text-white transition ${
                    textResposta.trim()
                      ? "bg-indigo-600 hover:bg-indigo-700"
                      : "bg-slate-300 dark:bg-slate-800 text-slate-400 cursor-not-allowed"
                  }`}
                  title="Enviar resposta al client"
                >
                  <Send className="w-4 h-4" />
                </button>
              </form>
            </>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center p-8 text-center text-slate-400">
              <MessageSquare className="w-12 h-12 text-slate-300 dark:text-slate-700 mb-2" />
              <p className="text-xs font-bold text-slate-600 dark:text-slate-400">
                Seleccioneu una conversa de la safata
              </p>
              <p className="text-[11px] text-slate-400 mt-1 max-w-sm">
                Podreu atendre incidències, consultar alertes de camp i enviar pressupostos en temps real.
              </p>
            </div>
          )}
        </main>
      </div>

      {/* 3. MODALS & TOASTS D'ALERTA */}

      {/* Alerta de Veto d'Enginyer */}
      {alertaVeto && (
        <div className="fixed bottom-6 right-6 z-50 max-w-md bg-rose-900 text-white p-4 rounded-xl shadow-2xl border border-rose-700 flex items-start gap-3 animate-in fade-in duration-200">
          <ShieldAlert className="w-5 h-5 text-rose-300 shrink-0 mt-0.5" />
          <div className="flex-1 text-xs">
            <p className="font-bold text-sm text-rose-100">Acció Bloquejada per Veto</p>
            <p className="text-rose-200 mt-1">{alertaVeto}</p>
          </div>
          <button onClick={() => setAlertaVeto(null)} className="text-rose-300 hover:text-white p-1">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Toast d'Èxit */}
      {toastExit && (
        <div className="fixed bottom-6 right-6 z-50 max-w-md bg-emerald-900 text-white p-4 rounded-xl shadow-2xl border border-emerald-700 flex items-start gap-3 animate-in fade-in duration-200">
          <CheckCircle2 className="w-5 h-5 text-emerald-300 shrink-0 mt-0.5" />
          <div className="flex-1 text-xs">
            <p className="font-bold text-sm text-emerald-100">Operació Executada</p>
            <p className="text-emerald-200 mt-1">{toastExit}</p>
          </div>
          <button onClick={() => setToastExit(null)} className="text-emerald-300 hover:text-white p-1">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* MODAL D'INVITACIÓ DEEP LINKING TELEGRAM (48h) (RF-11) */}
      {modalInvitacioObert && invitacioGenerada && (
        <div className="fixed inset-0 z-50 bg-slate-900/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl max-w-lg w-full shadow-2xl p-6">
            <div className="flex items-center justify-between pb-4 border-b border-slate-200 dark:border-slate-800">
              <div className="flex items-center gap-2">
                <LinkIcon className="w-5 h-5 text-sky-500" />
                <h3 className="text-base font-bold text-slate-900 dark:text-slate-100">
                  Enllaç Profund d&apos;Incorporació Telegram
                </h3>
              </div>
              <button onClick={() => setModalInvitacioObert(false)} className="text-slate-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="mt-4 space-y-4 text-xs">
              <p className="text-slate-600 dark:text-slate-300">
                Aquest enllaç incorpora un token unívoc d&apos;un sol ús. En fer clic, el client quedarà vinculat automàticament al bot oficial de SEVALOR.
              </p>

              <div className="p-3 rounded-lg bg-slate-100 dark:bg-slate-800 font-mono text-slate-800 dark:text-slate-200 break-all select-all border border-slate-200 dark:border-slate-700">
                {invitacioGenerada.link}
              </div>

              <div className="flex items-center justify-between text-[11px] text-slate-500 dark:text-slate-400 pt-2 border-t border-slate-200 dark:border-slate-800">
                <span>Vigència estricta: 48 hores</span>
                <span className="font-semibold text-rose-500">Caduca: {invitacioGenerada.expira}</span>
              </div>
            </div>

            <div className="mt-6 flex justify-end gap-2">
              <button
                onClick={() => setModalInvitacioObert(false)}
                className="px-4 py-2 text-xs font-semibold rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white transition"
              >
                Tancar
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL NOVA CONVERSA (HITL) */}
      {modalNovaConversaObert && (
        <div className="fixed inset-0 z-50 bg-slate-900/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl max-w-md w-full shadow-2xl p-6">
            <div className="flex items-center justify-between pb-4 border-b border-slate-200 dark:border-slate-800">
              <div className="flex items-center gap-2">
                <Plus className="w-5 h-5 text-indigo-600" />
                <h3 className="text-base font-bold text-slate-900 dark:text-slate-100">
                  Nova Conversa amb Client
                </h3>
              </div>
              <button onClick={() => setModalNovaConversaObert(false)} className="text-slate-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="mt-4 space-y-4 text-xs">
              <div>
                <label className="block font-bold text-slate-700 dark:text-slate-300 mb-1">
                  Client de Destí
                </label>
                <input
                  type="text"
                  defaultValue="Finca Can Puig SL"
                  className="w-full p-2 rounded-lg bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700"
                />
              </div>

              <div>
                <label className="block font-bold text-slate-700 dark:text-slate-300 mb-1">
                  Assumpte / Títol de la Conversa
                </label>
                <input
                  type="text"
                  placeholder="Ex: Revisió programada de pressió"
                  className="w-full p-2 rounded-lg bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700"
                />
              </div>
            </div>

            <div className="mt-6 flex justify-end gap-2">
              <button
                onClick={() => setModalNovaConversaObert(false)}
                className="px-4 py-2 text-xs font-semibold rounded-lg text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition"
              >
                Cancel·lar
              </button>
              <button
                onClick={() => {
                  setToastExit("Nova conversa creada a la safata sota HITL.");
                  setModalNovaConversaObert(false);
                  setTimeout(() => setToastExit(null), 3000);
                }}
                className="px-4 py-2 text-xs font-bold rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white transition"
              >
                Iniciar Conversa
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
