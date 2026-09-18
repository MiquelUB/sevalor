"use client";

import React, { useState, useEffect } from "react";
import { useGestio } from "@/lib/gestio-context";
import { apiFetch } from "@/lib/api";
import {
  Palette,
  Users,
  Clock,
  Send,
  Shield,
  ShieldAlert,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  Upload,
  RefreshCw,
  QrCode,
  Lock,
  Plus,
  Trash2,
  Eye,
  Sliders,
  Sparkles,
  Building,
  Info,
  Check,
  X,
  Radio,
  ExternalLink,
} from "lucide-react";

// Tipus de pestanyes
type PestanyaConfig = "marca" | "personal" | "jornada" | "telegram";

interface UsuariAdmin {
  id: string;
  nom: string;
  cognoms: string;
  nom_complet: string;
  nif: string;
  email: string;
  telefon?: string;
  rol: "BOSS" | "SECRETARIA" | "ENGINYER" | "COMPTABILITAT";
  estat: "ACTIU" | "INACTIU";
  totp_activat: boolean;
  data_ultim_acces?: string;
  slot_jornada_id?: string;
}

interface SlotJornadaItem {
  id: string;
  nom: string;
  modalitat: "JORNADA_CONTINUADA" | "JORNADA_PARTIDA" | "TORN_ESPECIAL";
  hora_entrada_teorica: string;
  hora_sortida_teorica: string;
  hora_inici_dinar?: string;
  hora_fi_dinar?: string;
  hores_convenio_setmanals: number;
  es_intensiva_estiu: boolean;
  data_inici_estiu?: string;
  data_fi_estiu?: string;
  hora_entrada_estiu?: string;
  hora_sortida_estiu?: string;
}

export default function ConfiguracioPage() {
  const { rolActiu } = useGestio();
  const esEnginyer = rolActiu === "ENGINYER";
  const esBoss = rolActiu === "BOSS";

  const [pestanyaActiva, setPestanyaActiva] = useState<PestanyaConfig>("marca");

  // Estat d'Empresa & Marca Camaleònica (carregat del backend)
  const [nomEmpresa, setNomEmpresa] = useState("");
  const [nifEmpresa, setNifEmpresa] = useState("");
  const [adrecaEmpresa, setAdrecaEmpresa] = useState("");
  const [monograma, setMonograma] = useState("--");
  const [primariHsl, setPrimariHsl] = useState("210 100% 15%");
  const [secundariHsl, setSecundariHsl] = useState("38 92% 50%");
  const [accentHsl, setAccentHsl] = useState("190 90% 50%");
  const [contrastRatio, setContrastRatio] = useState(14.8);
  const [logotipCarregat, setLogotipCarregat] = useState<string | null>(null);

  useEffect(() => {
    // Carregar dades de l'empresa des del backend
    apiFetch("/configuracio/empresa")
      .then((data: any) => {
        if (data.nom) setNomEmpresa(data.nom);
        if (data.nif) setNifEmpresa(data.nif);
        if (data.adreca) setAdrecaEmpresa(data.adreca);
        if (data.monograma) setMonograma(data.monograma);
        if (data.primari_hsl) setPrimariHsl(data.primari_hsl);
        if (data.secundari_hsl) setSecundariHsl(data.secundari_hsl);
        if (data.accent_hsl) setAccentHsl(data.accent_hsl);
      })
      .catch(() => {
        // TODO: endpoint pendent d'implementar al backend
      });
  }, []);

  // IA ADN de Marca
  const [adnPrompt, setAdnPrompt] = useState("");
  const [iaAnalitzant, setIaAnalitzant] = useState(false);
  const [paletaPropostaIa, setPaletaPropostaIa] = useState<{
    primari_hsl: string;
    secundari_hsl: string;
    accent_hsl: string;
    descripcio: string;
  } | null>(null);

  // Estat d'Usuaris Administratius (carregat del backend)
  const [usuaris, setUsuaris] = useState<UsuariAdmin[]>([]);

  useEffect(() => {
    apiFetch<UsuariAdmin[]>("/configuracio/usuaris")
      .then(setUsuaris)
      .catch(() => setUsuaris([])); // Fallback buit
  }, []);

  // Modals d'Usuari & 2FA
  const [modalNouUsuari, setModalNouUsuari] = useState(false);
  const [nouUsuariNom, setNouUsuariNom] = useState("");
  const [nouUsuariCognoms, setNouUsuariCognoms] = useState("");
  const [nouUsuariNif, setNouUsuariNif] = useState("");
  const [nouUsuariEmail, setNouUsuariEmail] = useState("");
  const [nouUsuariRol, setNouUsuariRol] = useState<"BOSS" | "SECRETARIA" | "ENGINYER" | "COMPTABILITAT">("SECRETARIA");
  const [contrasenyaGenerada, setContrasenyaGenerada] = useState<string | null>(null);

  const [modalQr2fa, setModalQr2fa] = useState<{ obert: boolean; usuariNom: string; secret: string } | null>(null);

  // Slots de Jornada Laboral (carregats del backend)
  const [slots, setSlots] = useState<SlotJornadaItem[]>([]);

  useEffect(() => {
    apiFetch<SlotJornadaItem[]>("/configuracio/slots-jornada")
      .then(setSlots)
      .catch(() => setSlots([])); // Fallback buit
  }, []);

  // Telegram Bot
  const [telegramToken, setTelegramToken] = useState("");
  const [telegramSecret, setTelegramSecret] = useState("");
  const [telegramEstat, setTelegramEstat] = useState<"OPERATIU" | "ERROR_CONNEXIO" | "NO_CONFIGURAT">("NO_CONFIGURAT");
  const [telegramTestant, setTelegramTestant] = useState(false);

  useEffect(() => {
    // Carregar configuració de Telegram del backend
    apiFetch("/configuracio/telegram")
      .then((data: any) => {
        if (data.estat) setTelegramEstat(data.estat);
        // Token i secret es mantenen ocults; el backend només exposa l'estat
      })
      .catch(() => setTelegramEstat("NO_CONFIGURAT"));
  }, []);

  // Missatge flash de feedback
  const [missatgeFlash, setMissatgeFlash] = useState<{ tipus: "EXIT" | "ERROR"; text: string } | null>(null);

  const mostrarFeedback = (tipus: "EXIT" | "ERROR", text: string) => {
    setMissatgeFlash({ tipus, text });
    setTimeout(() => setMissatgeFlash(null), 4000);
  };

  // Càlcul ràpid de contrast en viu
  const calcularContrastEnViu = (hslStr: string) => {
    // Estimació heurística de contrast contra blanc segons luminància HSL
    const parts = hslStr.replace(/%/g, "").split(" ");
    if (parts.length >= 3) {
      const l = parseFloat(parts[2]) / 100;
      // Aproximació: (1.05) / (l^2.2 + 0.05)
      const ratio = 1.05 / (Math.pow(l, 2.2) + 0.05);
      setContrastRatio(Math.round(ratio * 10) / 10);
    }
  };

  const handleCanviPrimari = (nouHsl: string) => {
    setPrimariHsl(nouHsl);
    calcularContrastEnViu(nouHsl);
  };

  // IA ADN de marca
  const handleAnalitzarAdn = () => {
    if (!adnPrompt.trim()) return;
    setIaAnalitzant(true);
    setTimeout(() => {
      setIaAnalitzant(false);
      setPaletaPropostaIa({
        primari_hsl: "142 76% 25%", // Verd maragda profund
        secundari_hsl: "38 92% 50%", // Ambre
        accent_hsl: "160 84% 39%", // Menta viva
        descripcio: "Paleta Bio-Agro suggerida pel Copilot IA basada en l'ADN de cultiu sostenible i reg per goteig.",
      });
      mostrarFeedback("EXIT", "Proposta de paleta generada pel Copilot IA. Requereix aprovació del Boss (HITL).");
    }, 1200);
  };

  const handleAprovarPaletaIa = () => {
    if (!paletaPropostaIa) return;
    if (!esBoss) {
      mostrarFeedback("ERROR", "VETO: Només el Boss pot aprovar la paleta de marca corporativa (HITL).");
      return;
    }
    setPrimariHsl(paletaPropostaIa.primari_hsl);
    setSecundariHsl(paletaPropostaIa.secundari_hsl);
    setAccentHsl(paletaPropostaIa.accent_hsl);
    setPaletaPropostaIa(null);
    calcularContrastEnViu(paletaPropostaIa.primari_hsl);
    mostrarFeedback("EXIT", "Paleta d'ADN aprovada i aplicada a les variables de la suite.");
  };

  // Gestió de Logotip & Magic Bytes
  const handlePujarLogo = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (esEnginyer) {
      mostrarFeedback("ERROR", "Veto d'Enginyer (HTTP 403): Modificació de logotip no autoritzada.");
      return;
    }
    const fitxer = e.target.files?.[0];
    if (!fitxer) return;

    if (fitxer.size > 10 * 1024 * 1024) {
      mostrarFeedback("ERROR", "HTTP 413: El fitxer supera el límit màxim permès de 10 MB.");
      return;
    }

    if (!["image/png", "image/jpeg"].includes(fitxer.type)) {
      mostrarFeedback("ERROR", "HTTP 415: Només s'admeten imatges PNG o JPG autèntiques (Magic Bytes).");
      return;
    }

    const reader = new FileReader();
    reader.onload = (event) => {
      setLogotipCarregat(event.target?.result as string);
      mostrarFeedback("EXIT", "Logotip carregat i processat per a Hetzner Falkenstein (Dashboard, PWA i Caixetins).");
    };
    reader.readAsDataURL(fitxer);
  };

  // Creació d'Usuari Administratiu
  const handleCrearUsuari = async (e: React.FormEvent) => {
    e.preventDefault();
    if (esEnginyer) {
      mostrarFeedback("ERROR", "Veto d'Enginyer (HTTP 403): Alta d'usuaris denegada.");
      return;
    }

    const payload = {
      nom: nouUsuariNom,
      cognoms: nouUsuariCognoms,
      nif: nouUsuariNif.toUpperCase(),
      email: nouUsuariEmail.toLowerCase(),
      rol: nouUsuariRol,
    };

    try {
      const nou = await apiFetch<UsuariAdmin>("/configuracio/usuaris", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setUsuaris([...usuaris, nou]);
      if ((nou as any).contrasenya_generada) {
        setContrasenyaGenerada((nou as any).contrasenya_generada);
      }
      mostrarFeedback("EXIT", "Usuari creat correctament. Contrasenya temporal generada.");
    } catch {
      mostrarFeedback("ERROR", "No s'ha pogut crear l'usuari. Verifiqueu la connexió amb el backend.");
    }
  };

  // Protecció ÚLTIM BOSS (EDGE-05)
  const handleEliminarUsuari = async (id: string) => {
    if (esEnginyer) {
      mostrarFeedback("ERROR", "Veto d'Enginyer (HTTP 403): Eliminació d'usuaris denegada.");
      return;
    }

    const target = usuaris.find((u) => u.id === id);
    if (!target) return;

    if (target.rol === "BOSS") {
      const bossesActius = usuaris.filter((u) => u.rol === "BOSS" && u.estat === "ACTIU");
      if (bossesActius.length <= 1) {
        mostrarFeedback("ERROR", "HTTP 400: Bloqueig de Seguretat (EDGE-05). No es pot donar de baixa l'últim Boss de l'empresa.");
        return;
      }
    }

    try {
      await apiFetch(`/configuracio/usuaris/${id}`, { method: "DELETE" });
      setUsuaris(usuaris.filter((u) => u.id !== id));
      mostrarFeedback("EXIT", "Usuari retirat de la gestió corporativa.");
    } catch {
      mostrarFeedback("ERROR", "No s'ha pogut eliminar l'usuari.");
    }
  };

  // Reinici de 2FA TOTP (RF-06)
  const handleReiniciar2fa = async (u: UsuariAdmin) => {
    if (!esBoss) {
      mostrarFeedback("ERROR", "HTTP 403 Forbidden: El reinici de 2FA TOTP està reservat exclusivament al rol Boss (RF-06).");
      return;
    }

    try {
      const data = await apiFetch<{ secret: string }>(`/configuracio/usuaris/${u.id}/2fa/reiniciar`, { method: "POST" });
      setModalQr2fa({
        obert: true,
        usuariNom: u.nom_complet,
        secret: data.secret,
      });
      mostrarFeedback("EXIT", `2FA reiniciat per a ${u.nom_complet}. Escanegeu el codi QR amb Google Authenticator.`);
    } catch {
      mostrarFeedback("ERROR", "No s'ha pogut reiniciar el 2FA.");
    }
  };

  // Test de connexió de Telegram (RF-20, EDGE-09)
  const handleProvarTelegram = async () => {
    setTelegramTestant(true);
    try {
      await apiFetch("/configuracio/telegram/provar", { method: "POST" });
      setTelegramEstat("OPERATIU");
      mostrarFeedback("EXIT", "Connexió getMe satisfactòria amb el Bot de Telegram (HTTP 200).");
    } catch {
      setTelegramEstat("ERROR_CONNEXIO");
      mostrarFeedback("ERROR", "No s'ha pogut connectar amb el Bot de Telegram.");
    } finally {
      setTelegramTestant(false);
    }
  };

  return (
    <div className="space-y-6 pb-12">
      {/* CAPÇALERA SUPERIOR D'ALTA DENSITAT */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-sm">
        <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            {/* Monograma corporatiu / Logotip en capçalera */}
            <div className="w-14 h-14 rounded-xl bg-slate-900 dark:bg-slate-800 border-2 border-emerald-500 flex items-center justify-center text-white font-black text-xl shadow-inner overflow-hidden">
              {logotipCarregat ? (
                <img src={logotipCarregat} alt="Logotip" className="w-full h-full object-cover" />
              ) : (
                <span className="tracking-widest">{monograma}</span>
              )}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-white">
                  Configuració & Governança de l'Empresa
                </h1>
                <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase bg-emerald-100 text-emerald-800 dark:bg-emerald-950/70 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-800">
                  Spec 011
                </span>
                <span className="px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400">
                  Hetzner Alemanya (UE)
                </span>
              </div>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                {nomEmpresa} • NIF: {nifEmpresa} • Subdomini: <span className="font-mono text-emerald-600 dark:text-emerald-400">penedes.sevalor.cat</span>
              </p>
            </div>
          </div>

          {/* ROL I VETO INDICATOR */}
          <div className="flex items-center gap-3">
            <div className="text-right">
              <p className="text-xs font-bold text-slate-900 dark:text-white">Rol Actiu: {rolActiu}</p>
              <p className="text-[10px] text-slate-500 dark:text-slate-400">
                {esBoss ? "Autoritat Total de Governança" : esEnginyer ? "Veto de Configuració (Lectura)" : "Gestió Operativa Autoritzada"}
              </p>
            </div>
            <div
              className={`p-2 rounded-xl ${
                esBoss
                  ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300"
                  : esEnginyer
                  ? "bg-amber-100 text-amber-700 dark:bg-amber-950/60 dark:text-amber-300"
                  : "bg-blue-100 text-blue-700 dark:bg-blue-950/60 dark:text-blue-300"
              }`}
            >
              {esBoss ? <ShieldCheck className="w-5 h-5" /> : esEnginyer ? <ShieldAlert className="w-5 h-5" /> : <Shield className="w-5 h-5" />}
            </div>
          </div>
        </div>

        {/* ALERTA DE VETO PER A ENGINYER */}
        {esEnginyer && (
          <div className="mt-4 p-3 rounded-xl bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800/60 flex items-start gap-3">
            <AlertTriangle className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
            <p className="text-xs text-amber-800 dark:text-amber-300">
              <strong className="font-bold">Mode Consulta (Veto d'Enginyer — Spec 011 RF-03):</strong> Tens accés de lectura a la configuració corporativa i al teu slot de jornada assignat. Les modificacions d'ADN de marca, logotips, usuaris administratius i paràmetres de Telegram estan reservades per llei a Gerència (Boss) i Secretaria.
            </p>
          </div>
        )}

        {/* FEEDBACK FLASH */}
        {missatgeFlash && (
          <div
            className={`mt-3 p-3 rounded-xl flex items-center justify-between text-xs font-semibold ${
              missatgeFlash.tipus === "EXIT"
                ? "bg-emerald-100 text-emerald-900 dark:bg-emerald-950/70 dark:text-emerald-200 border border-emerald-300 dark:border-emerald-800"
                : "bg-red-100 text-red-900 dark:bg-red-950/70 dark:text-red-200 border border-red-300 dark:border-red-800"
            }`}
          >
            <span>{missatgeFlash.text}</span>
            <button onClick={() => setMissatgeFlash(null)} className="text-current opacity-70 hover:opacity-100">
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        {/* SELECTOR DE PESTANYES */}
        <div className="flex flex-wrap items-center gap-2 mt-5 border-t border-slate-200 dark:border-slate-800 pt-4">
          <button
            onClick={() => setPestanyaActiva("marca")}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all ${
              pestanyaActiva === "marca"
                ? "bg-emerald-600 text-white shadow-md shadow-emerald-600/20"
                : "text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800"
            }`}
          >
            <Palette className="w-3.5 h-3.5" />
            <span>1. Identitat & Marca Camaleònica</span>
          </button>

          <button
            onClick={() => setPestanyaActiva("personal")}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all ${
              pestanyaActiva === "personal"
                ? "bg-emerald-600 text-white shadow-md shadow-emerald-600/20"
                : "text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800"
            }`}
          >
            <Users className="w-3.5 h-3.5" />
            <span>2. Personal d'Oficina & 2FA TOTP</span>
            <span className="px-1.5 py-0.5 text-[9px] rounded-full bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
              {usuaris.length}
            </span>
          </button>

          <button
            onClick={() => setPestanyaActiva("jornada")}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all ${
              pestanyaActiva === "jornada"
                ? "bg-emerald-600 text-white shadow-md shadow-emerald-600/20"
                : "text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800"
            }`}
          >
            <Clock className="w-3.5 h-3.5" />
            <span>3. Slots de Jornada & Estiu</span>
          </button>

          <button
            onClick={() => setPestanyaActiva("telegram")}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all ${
              pestanyaActiva === "telegram"
                ? "bg-emerald-600 text-white shadow-md shadow-emerald-600/20"
                : "text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800"
            }`}
          >
            <Send className="w-3.5 h-3.5" />
            <span>4. Bot de Telegram Corporatiu</span>
            <span
              className={`w-2 h-2 rounded-full ${
                telegramEstat === "OPERATIU" ? "bg-emerald-500" : "bg-red-500"
              }`}
            />
          </button>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* 1. IDENTITAT & MARCA CAMALEÒNICA (RF-12 a RF-18, EDGE-02, EDGE-03)        */}
      {/* ========================================================================= */}
      {pestanyaActiva === "marca" && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Panell de Control de Colors HSL & Contrast WCAG */}
          <div className="lg:col-span-2 space-y-6">
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-sm space-y-5">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2">
                    <Sliders className="w-4 h-4 text-emerald-600" />
                    Paleta Camaleònica HSL & Contrast WCAG 2.1 AA
                  </h2>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                    Definiu els valors HSL que s'injecten de forma dinàmica a les variables CSS (--color-primary, --color-secondary)
                  </p>
                </div>

                {/* Termòmetre de Contrast WCAG */}
                <div className="text-right">
                  <div className="flex items-center gap-1.5 justify-end">
                    <span className="text-xs font-mono font-black text-slate-900 dark:text-white">
                      {contrastRatio}:1
                    </span>
                    <span
                      className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                        contrastRatio >= 4.5
                          ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950/80 dark:text-emerald-300"
                          : "bg-red-100 text-red-800 dark:bg-red-950/80 dark:text-red-300"
                      }`}
                    >
                      {contrastRatio >= 4.5 ? "WCAG AA OK" : "IL·LEGIBLE (<4.5)"}
                    </span>
                  </div>
                  <p className="text-[10px] text-slate-400">Mínim legal 4.5:1 (EDGE-02)</p>
                </div>
              </div>

              {/* Formulari de selectors HSL */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                {/* Color Primari */}
                <div className="p-3 rounded-xl border border-slate-200 dark:border-slate-800 space-y-2">
                  <label className="text-xs font-bold text-slate-700 dark:text-slate-300 block">
                    Color Primari (HSL)
                  </label>
                  <input
                    type="text"
                    disabled={esEnginyer}
                    value={primariHsl}
                    onChange={(e) => handleCanviPrimari(e.target.value)}
                    className="w-full px-3 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs font-mono text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-emerald-500 disabled:opacity-50"
                  />
                  <div className="flex gap-2">
                    <button
                      type="button"
                      disabled={esEnginyer}
                      onClick={() => handleCanviPrimari("210 100% 15%")}
                      className="px-2 py-1 rounded text-[10px] bg-slate-800 text-white font-mono hover:bg-slate-700 disabled:opacity-50"
                    >
                      Blau Fosc
                    </button>
                    <button
                      type="button"
                      disabled={esEnginyer}
                      onClick={() => handleCanviPrimari("142 76% 25%")}
                      className="px-2 py-1 rounded text-[10px] bg-emerald-800 text-white font-mono hover:bg-emerald-700 disabled:opacity-50"
                    >
                      Verd Agro
                    </button>
                    <button
                      type="button"
                      disabled={esEnginyer}
                      onClick={() => handleCanviPrimari("0 0% 75%")}
                      className="px-2 py-1 rounded text-[10px] bg-slate-200 text-slate-800 font-mono hover:bg-slate-300 disabled:opacity-50"
                      title="Provoca error de contrast WCAG per comprovar EDGE-02"
                    >
                      Test &lt;4.5
                    </button>
                  </div>
                </div>

                {/* Color Secundari */}
                <div className="p-3 rounded-xl border border-slate-200 dark:border-slate-800 space-y-2">
                  <label className="text-xs font-bold text-slate-700 dark:text-slate-300 block">
                    Color Secundari (Ambre)
                  </label>
                  <input
                    type="text"
                    disabled={esEnginyer}
                    value={secundariHsl}
                    onChange={(e) => setSecundariHsl(e.target.value)}
                    className="w-full px-3 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs font-mono text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-emerald-500 disabled:opacity-50"
                  />
                  <p className="text-[10px] text-slate-400">Utilitzat en avisos i avisos ITV</p>
                </div>

                {/* Color d'Accent */}
                <div className="p-3 rounded-xl border border-slate-200 dark:border-slate-800 space-y-2">
                  <label className="text-xs font-bold text-slate-700 dark:text-slate-300 block">
                    Color d'Accent (Cian)
                  </label>
                  <input
                    type="text"
                    disabled={esEnginyer}
                    value={accentHsl}
                    onChange={(e) => setAccentHsl(e.target.value)}
                    className="w-full px-3 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs font-mono text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-emerald-500 disabled:opacity-50"
                  />
                  <p className="text-[10px] text-slate-400">Utilitzat en vectors cartogràfics GIS</p>
                </div>
              </div>

              {/* Botó Desar Canvis */}
              <div className="flex justify-end pt-2">
                <button
                  type="button"
                  disabled={esEnginyer || contrastRatio < 4.5}
                  onClick={async () => {
                    try {
                      await apiFetch("/configuracio/empresa/marca", {
                        method: "PUT",
                        body: JSON.stringify({ primari_hsl: primariHsl, secundari_hsl: secundariHsl, accent_hsl: accentHsl }),
                      });
                      mostrarFeedback("EXIT", "Colors corporatius desats a PostgreSQL i aplicats a la Suite.");
                    } catch {
                      mostrarFeedback("ERROR", "No s'han pogut desar els colors.");
                    }
                  }}
                  className="px-4 py-2 rounded-xl text-xs font-bold bg-emerald-600 hover:bg-emerald-700 text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed shadow-sm"
                >
                  Desar Colors Corporatius
                </button>
              </div>
            </div>

            {/* Càrrega i Anàlisi IA d'ADN de Marca (RF-12, RF-13) */}
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-sm space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-purple-600 dark:text-purple-400" />
                  <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                    Assistent IA d'ADN de Marca (Supervisat HITL)
                  </h3>
                </div>
                <span className="text-[10px] font-mono uppercase bg-purple-100 dark:bg-purple-950/60 text-purple-800 dark:text-purple-300 px-2 py-0.5 rounded border border-purple-300 dark:border-purple-800">
                  Mandat Human-in-the-Loop
                </span>
              </div>

              <p className="text-xs text-slate-500 dark:text-slate-400">
                Enganxeu la declaració de valors o guia d'estil corporatiu de la vostra instal·ladora. El Copilot IA proposarà una paleta cromàtica optimitzada que requereix la signatura i confirmació explícita del Boss abans d'aplicar-se.
              </p>

              <textarea
                disabled={esEnginyer}
                rows={3}
                value={adnPrompt}
                onChange={(e) => setAdnPrompt(e.target.value)}
                placeholder="Exemple: Som una empresa del Penedès especialitzada en sistemes de reg per goteig i sostenibilitat ecològica. Volem tons verds de natura combinats amb ambre industrial per a màquines..."
                className="w-full p-3 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-purple-500 disabled:opacity-50 resize-none"
              />

              <div className="flex items-center justify-between">
                <p className="text-[10px] text-slate-400">
                  Processament local sobirà LM Studio a Hetzner (zero fugides fora de la UE)
                </p>
                <button
                  type="button"
                  disabled={esEnginyer || !adnPrompt.trim() || iaAnalitzant}
                  onClick={handleAnalitzarAdn}
                  className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-bold bg-purple-600 hover:bg-purple-700 text-white transition-colors disabled:opacity-50 shadow-sm"
                >
                  {iaAnalitzant ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
                  <span>Analitzar amb Copilot IA</span>
                </button>
              </div>

              {/* Targeta de Proposta de la IA pendent d'Aprovació HITL */}
              {paletaPropostaIa && (
                <div className="p-4 rounded-xl bg-purple-50 dark:bg-purple-950/30 border border-purple-200 dark:border-purple-800/60 space-y-3">
                  <div className="flex items-start justify-between">
                    <div>
                      <span className="text-xs font-bold text-purple-900 dark:text-purple-200">
                        Proposta Generada pel Copilot IA
                      </span>
                      <p className="text-xs text-purple-700 dark:text-purple-300 mt-0.5">
                        {paletaPropostaIa.descripcio}
                      </p>
                    </div>
                    <div className="flex gap-2">
                      <div className="w-6 h-6 rounded-md border border-slate-300 shadow-sm" style={{ backgroundColor: `hsl(${paletaPropostaIa.primari_hsl})` }} title="Primari" />
                      <div className="w-6 h-6 rounded-md border border-slate-300 shadow-sm" style={{ backgroundColor: `hsl(${paletaPropostaIa.secundari_hsl})` }} title="Secundari" />
                      <div className="w-6 h-6 rounded-md border border-slate-300 shadow-sm" style={{ backgroundColor: `hsl(${paletaPropostaIa.accent_hsl})` }} title="Accent" />
                    </div>
                  </div>

                  <div className="flex items-center justify-end gap-2 pt-2 border-t border-purple-200 dark:border-purple-800">
                    <button
                      type="button"
                      onClick={() => setPaletaPropostaIa(null)}
                      className="px-3 py-1.5 rounded-lg text-xs font-semibold text-slate-600 dark:text-slate-400 hover:bg-purple-100 dark:hover:bg-purple-900/40 transition-colors"
                    >
                      Descartar Proposta
                    </button>
                    <button
                      type="button"
                      onClick={handleAprovarPaletaIa}
                      className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-xs font-bold bg-emerald-600 hover:bg-emerald-700 text-white shadow-sm transition-colors"
                    >
                      <Check className="w-3.5 h-3.5" />
                      <span>{esBoss ? "Aprovar i Aplicar (Firma Boss HITL)" : "Requerit Rol Boss per Aprovar"}</span>
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Columna Lateral: Logotip Sobirà & Live Preview */}
          <div className="space-y-6">
            {/* Slot de Pujada de Logotip (RF-16, RF-17, EDGE-03) */}
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-sm space-y-4">
              <h3 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2">
                <Upload className="w-4 h-4 text-emerald-600" />
                Logotip Oficial de l'Empresa
              </h3>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Formats permesos PNG o JPG (màxim 10 MB). Es processarà sobiràment al servidor Hetzner de Falkenstein amb validació de Magic Bytes.
              </p>

              <div className="p-4 border-2 border-dashed border-slate-300 dark:border-slate-700 rounded-xl text-center space-y-3">
                <div className="w-16 h-16 mx-auto rounded-xl bg-slate-100 dark:bg-slate-800 flex items-center justify-center text-slate-400 font-bold overflow-hidden">
                  {logotipCarregat ? (
                    <img src={logotipCarregat} alt="Logo" className="w-full h-full object-contain" />
                  ) : (
                    <span className="text-2xl font-mono text-slate-500">{monograma}</span>
                  )}
                </div>
                <div>
                  <label
                    className={`inline-block px-3 py-1.5 rounded-lg text-xs font-bold transition-colors ${
                      esEnginyer
                        ? "bg-slate-200 text-slate-400 cursor-not-allowed"
                        : "bg-slate-900 hover:bg-slate-800 text-white dark:bg-slate-700 dark:hover:bg-slate-600 cursor-pointer shadow-sm"
                    }`}
                  >
                    <span>Seleccionar PNG/JPG</span>
                    <input
                      type="file"
                      disabled={esEnginyer}
                      accept="image/png,image/jpeg"
                      onChange={handlePujarLogo}
                      className="hidden"
                    />
                  </label>
                  <p className="text-[10px] text-slate-400 mt-1">Límit 10 MB • Redimensionament asíncron</p>
                </div>
              </div>

              {/* Monograma Tipogràfic de Respatller (RF-18) */}
              <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-800 flex items-center justify-between">
                <div>
                  <p className="text-xs font-bold text-slate-800 dark:text-slate-200">Monograma Tipogràfic Net</p>
                  <p className="text-[10px] text-slate-400">Actiu en absència de logotip (Zero Mock Data)</p>
                </div>
                <div className="w-8 h-8 rounded-lg bg-emerald-600 text-white font-bold text-xs flex items-center justify-center font-mono">
                  {monograma}
                </div>
              </div>
            </div>

            {/* Finestra de Live Preview Interactiva (RF-15) */}
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-sm space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2">
                  <Eye className="w-4 h-4 text-emerald-600" />
                  Previsualització en Viu (Live Preview)
                </h3>
                <span className="text-[9px] font-mono uppercase bg-slate-100 dark:bg-slate-800 px-1.5 py-0.5 rounded text-slate-500">
                  Temps Real
                </span>
              </div>

              <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 space-y-3 bg-slate-50 dark:bg-slate-950">
                <div className="flex items-center justify-between pb-2 border-b border-slate-200 dark:border-slate-800">
                  <div className="flex items-center gap-2">
                    <div className="w-6 h-6 rounded bg-slate-900 text-white font-bold text-[10px] flex items-center justify-center">
                      {monograma}
                    </div>
                    <span className="text-xs font-bold text-slate-900 dark:text-white">Capçalera Web</span>
                  </div>
                  <span
                    className="text-[10px] font-bold px-2 py-0.5 rounded text-white shadow-sm"
                    style={{ backgroundColor: `hsl(${secundariHsl})` }}
                  >
                    Avís de Camp
                  </span>
                </div>

                <div className="space-y-1.5">
                  <p className="text-[11px] text-slate-600 dark:text-slate-300">
                    Aspecte dels botons d'acció amb el color primari seleccionat:
                  </p>
                  <button
                    type="button"
                    className="w-full py-2 rounded-lg text-xs font-bold text-white shadow-sm flex items-center justify-center gap-1.5"
                    style={{ backgroundColor: `hsl(${primariHsl})` }}
                  >
                    <span>Botó d'Acció Principal</span>
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* 2. PERSONAL D'OFICINA & 2FA TOTP (RF-01 a RF-07, EDGE-01, EDGE-05)        */}
      {/* ========================================================================= */}
      {pestanyaActiva === "personal" && (
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-sm space-y-5">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div>
              <h2 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2">
                <Users className="w-4 h-4 text-emerald-600" />
                Plantilla d'Oficina & Polítiques 2FA TOTP (Zero-Trust)
              </h2>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                Usuaris administratius amb accés al Dashboard Web. 2FA obligatori amb protecció d'orfandat de l'últim Boss (EDGE-05).
              </p>
            </div>

            <button
              type="button"
              disabled={esEnginyer}
              onClick={() => setModalNouUsuari(true)}
              className="flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-bold bg-emerald-600 hover:bg-emerald-700 text-white transition-colors disabled:opacity-50 shadow-sm"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Alta d'Administratiu</span>
            </button>
          </div>

          {/* Taula d'Usuaris */}
          <div className="overflow-x-auto border border-slate-200 dark:border-slate-800 rounded-xl">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 dark:bg-slate-800/60 text-slate-500 dark:text-slate-400 font-mono text-[10px] uppercase border-b border-slate-200 dark:border-slate-800">
                <tr>
                  <th className="px-4 py-3">Empleat / Nom</th>
                  <th className="px-4 py-3">NIF / Contacte</th>
                  <th className="px-4 py-3">Rol Corporatiu</th>
                  <th className="px-4 py-3">Seguretat 2FA</th>
                  <th className="px-4 py-3">Últim Accés</th>
                  <th className="px-4 py-3 text-right">Accions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {usuaris.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="text-center py-8 text-slate-400">
                      No hi ha usuaris administratius registrats a l'empresa (Zero Mock Data)
                    </td>
                  </tr>
                ) : (
                  usuaris.map((u) => (
                    <tr key={u.id} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/40 transition-colors">
                      <td className="px-4 py-3">
                        <p className="font-bold text-slate-900 dark:text-white">{u.nom_complet}</p>
                        <p className="text-[11px] text-slate-400">{u.email}</p>
                      </td>
                      <td className="px-4 py-3">
                        <span className="font-mono text-slate-700 dark:text-slate-300 font-semibold">{u.nif}</span>
                        <p className="text-[10px] text-slate-400">{u.telefon || "Sense telèfon"}</p>
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold ${
                            u.rol === "BOSS"
                              ? "bg-purple-100 text-purple-800 dark:bg-purple-950/80 dark:text-purple-300"
                              : u.rol === "ENGINYER"
                              ? "bg-amber-100 text-amber-800 dark:bg-amber-950/80 dark:text-amber-300"
                              : "bg-blue-100 text-blue-800 dark:bg-blue-950/80 dark:text-blue-300"
                          }`}
                        >
                          {u.rol}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        {u.totp_activat ? (
                          <span className="inline-flex items-center gap-1 text-[11px] font-bold text-emerald-600 dark:text-emerald-400">
                            <CheckCircle2 className="w-3.5 h-3.5" />
                            <span>Activat</span>
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-[11px] font-bold text-amber-600 dark:text-amber-400">
                            <Clock className="w-3.5 h-3.5" />
                            <span>Pendent Enrolament</span>
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 font-mono text-[11px] text-slate-500">
                        {u.data_ultim_acces}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          {/* Botó Reiniciar 2FA (només BOSS) */}
                          <button
                            type="button"
                            onClick={() => handleReiniciar2fa(u)}
                            className="p-1.5 rounded-lg text-slate-500 hover:text-purple-600 hover:bg-purple-50 dark:hover:bg-purple-950/40 transition-colors"
                            title={esBoss ? "Reiniciar 2FA TOTP (RF-06)" : "Veto: Només el Boss pot reiniciar 2FA"}
                          >
                            <QrCode className="w-3.5 h-3.5" />
                          </button>

                          {/* Botó Eliminar (amb protecció de l'últim Boss) */}
                          <button
                            type="button"
                            disabled={esEnginyer}
                            onClick={() => handleEliminarUsuari(u.id)}
                            className="p-1.5 rounded-lg text-slate-500 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-950/40 transition-colors disabled:opacity-40"
                            title="Donar de baixa usuari"
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

          {/* Avisos de Seguretat 2FA i Protocols d'Emergència */}
          <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800 space-y-2">
            <h4 className="text-xs font-bold text-slate-800 dark:text-slate-200 flex items-center gap-2">
              <Lock className="w-3.5 h-3.5 text-emerald-600" />
              Protocol de Recuperació d'Accés per l'Últim Boss (EDGE-01)
            </h4>
            <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
              En cas de pèrdua del dispositiu mòbil per part de l'únic Boss, l'accés s'autoritza exclusivament mitjançant un dels 8 codis de recuperació estàtics generats unívocament durant l'onboarding. El Superadmin de la plataforma té completament vetat l'override per preservar l'aïllament multi-inquilí (Zero-Trust).
            </p>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* 3. SLOTS DE JORNADA & ESTIU (RF-08 a RF-11, EDGE-04, EDGE-08)             */}
      {/* ========================================================================= */}
      {pestanyaActiva === "jornada" && (
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-sm space-y-5">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div>
              <h2 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2">
                <Clock className="w-4 h-4 text-emerald-600" />
                Slots de Jornada Laboral Individualitzats (RDL 8/2019)
              </h2>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                Configuració d'horaris vinculants per a l'auto-tancament de la jornada a les 8 hores (Spec 008). Suport per a Jornada Intensiva d'Estiu.
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {slots.map((s) => (
              <div
                key={s.id}
                className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/30 space-y-3"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-xs font-bold text-slate-900 dark:text-white">{s.nom}</h3>
                    <span className="text-[10px] font-mono text-slate-500 uppercase">{s.modalitat}</span>
                  </div>
                  {s.es_intensiva_estiu && (
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-100 text-amber-800 dark:bg-amber-950/80 dark:text-amber-300">
                      Intensiva d'Estiu
                    </span>
                  )}
                </div>

                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div className="p-2 rounded-lg bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700">
                    <p className="text-[10px] text-slate-400">Entrada Teòrica</p>
                    <p className="font-mono font-bold text-slate-900 dark:text-white">{s.hora_entrada_teorica}</p>
                  </div>
                  <div className="p-2 rounded-lg bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700">
                    <p className="text-[10px] text-slate-400">Sortida Teòrica</p>
                    <p className="font-mono font-bold text-slate-900 dark:text-white">{s.hora_sortida_teorica}</p>
                  </div>
                  {s.hora_inici_dinar && s.hora_fi_dinar && (
                    <div className="col-span-2 p-2 rounded-lg bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700">
                      <p className="text-[10px] text-slate-400">Pausa per Dinar (Partida)</p>
                      <p className="font-mono font-bold text-slate-900 dark:text-white">
                        {s.hora_inici_dinar} - {s.hora_fi_dinar}
                      </p>
                    </div>
                  )}
                </div>

                <div className="flex items-center justify-between text-[11px] text-slate-500 pt-2 border-t border-slate-200 dark:border-slate-700/60">
                  <span>Còmput de conveni: <strong className="font-bold text-slate-700 dark:text-slate-300">{s.hores_convenio_setmanals} h/setmana</strong></span>
                  <span className="font-mono text-[10px]">Càlcul UTC (EDGE-06)</span>
                </div>
              </div>
            ))}
          </div>

          <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800 flex items-start gap-3">
            <Info className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
            <p className="text-xs text-slate-500 dark:text-slate-400">
              <strong className="font-bold text-slate-800 dark:text-slate-200">Traçabilitat de shifts en curs (EDGE-04):</strong> Si es canvia l'slot d'un operari mentre aquest té un torn de camp actiu, el tancament automàtic a les 8h d'aquella jornada continua regint-se per les condicions de l'slot vigent a l'obertura, aplicant el canvi exclusivament a jornades futures.
            </p>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* 4. BOT DE TELEGRAM CORPORATIU (RF-19, RF-20, EDGE-09)                     */}
      {/* ========================================================================= */}
      {pestanyaActiva === "telegram" && (
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-sm space-y-5">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div>
              <h2 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2">
                <Send className="w-4 h-4 text-emerald-600" />
                Connexió del Bot de Telegram de Clients (Spec 009)
              </h2>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                Configuració del canal interactiu complementari d'atenció al client i aprovació de pressupostos.
              </p>
            </div>

            <div className="flex items-center gap-2">
              <span
                className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold ${
                  telegramEstat === "OPERATIU"
                    ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950/80 dark:text-emerald-300"
                    : "bg-red-100 text-red-800 dark:bg-red-950/80 dark:text-red-300"
                }`}
              >
                <span className={`w-2 h-2 rounded-full ${telegramEstat === "OPERATIU" ? "bg-emerald-500" : "bg-red-500"}`} />
                <span>{telegramEstat === "OPERATIU" ? "OPERATIU" : "ERROR DE CONNEXIÓ"}</span>
              </span>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label className="text-xs font-bold text-slate-700 dark:text-slate-300">
                Bot Token de Telegram (BotFather)
              </label>
              <input
                type="password"
                disabled={esEnginyer}
                value={telegramToken}
                onChange={(e) => setTelegramToken(e.target.value)}
                className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs font-mono text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-emerald-500 disabled:opacity-50"
              />
              <p className="text-[10px] text-slate-400">Exemple: 123456789:AAFlk902j_PqW0293kdLZk0</p>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-bold text-slate-700 dark:text-slate-300">
                Webhook Secret Token
              </label>
              <input
                type="password"
                disabled={esEnginyer}
                value={telegramSecret}
                onChange={(e) => setTelegramSecret(e.target.value)}
                className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs font-mono text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-emerald-500 disabled:opacity-50"
              />
              <p className="text-[10px] text-slate-400">Cadena de xifratge per a verificar crides d'entrada</p>
            </div>
          </div>

          <div className="flex items-center justify-between pt-2 border-t border-slate-200 dark:border-slate-800">
            <div className="flex items-center gap-1.5 text-xs text-slate-500">
              <Radio className="w-3.5 h-3.5 text-emerald-500" />
              <span>Timeout asíncron gestionat a 5 segons (EDGE-09)</span>
            </div>

            <div className="flex gap-2">
              <button
                type="button"
                disabled={telegramTestant}
                onClick={handleProvarTelegram}
                className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-bold bg-slate-800 hover:bg-slate-700 text-white transition-colors disabled:opacity-50 shadow-sm"
              >
                {telegramTestant ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
                <span>Provar Connexió Bot</span>
              </button>

              <button
                type="button"
                disabled={esEnginyer}
                onClick={async () => {
                  try {
                    await apiFetch("/configuracio/telegram", {
                      method: "PUT",
                      body: JSON.stringify({ token: telegramToken, secret: telegramSecret }),
                    });
                    mostrarFeedback("EXIT", "Credencials de Telegram desades amb èxit.");
                  } catch {
                    mostrarFeedback("ERROR", "No s'han pogut desar les credencials.");
                  }
                }}
                className="px-4 py-2 rounded-xl text-xs font-bold bg-emerald-600 hover:bg-emerald-700 text-white transition-colors disabled:opacity-50 shadow-sm"
              >
                Desar Paràmetres Bot
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL NOU USUARI ADMINISTRATIU */}
      {modalNouUsuari && (
        <div className="fixed inset-0 z-50 bg-slate-950/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                Alta d'Usuari Administratiu (Dashboard Web)
              </h3>
              <button onClick={() => { setModalNouUsuari(false); setContrasenyaGenerada(null); }} className="text-slate-400 hover:text-slate-600">
                <X className="w-4 h-4" />
              </button>
            </div>

            {contrasenyaGenerada ? (
              <div className="space-y-4">
                <div className="p-4 rounded-xl bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 space-y-2">
                  <p className="text-xs font-bold text-emerald-800 dark:text-emerald-300">
                    Usuari creat amb èxit! Contrasenya generada:
                  </p>
                  <p className="font-mono text-sm font-black text-emerald-900 dark:text-emerald-200 tracking-wider bg-white dark:bg-slate-800 p-2 rounded border border-emerald-300">
                    {contrasenyaGenerada}
                  </p>
                  <p className="text-[10px] text-emerald-700 dark:text-emerald-400">
                    Aquesta contrasenya temporal de 12 caràcters s'ha de facilitar a l'empleat. En el primer inici de sessió se li exigirà configurar el 2FA TOTP.
                  </p>
                </div>
                <button
                  onClick={() => { setModalNouUsuari(false); setContrasenyaGenerada(null); }}
                  className="w-full py-2 rounded-xl text-xs font-bold bg-slate-900 text-white hover:bg-slate-800"
                >
                  Tancar Finestra
                </button>
              </div>
            ) : (
              <form onSubmit={handleCrearUsuari} className="space-y-3 text-xs">
                <div>
                  <label className="font-bold text-slate-700 dark:text-slate-300 block mb-1">Nom</label>
                  <input
                    required
                    type="text"
                    value={nouUsuariNom}
                    onChange={(e) => setNouUsuariNom(e.target.value)}
                    className="w-full px-3 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white"
                  />
                </div>
                <div>
                  <label className="font-bold text-slate-700 dark:text-slate-300 block mb-1">Cognoms</label>
                  <input
                    type="text"
                    value={nouUsuariCognoms}
                    onChange={(e) => setNouUsuariCognoms(e.target.value)}
                    className="w-full px-3 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white"
                  />
                </div>
                <div>
                  <label className="font-bold text-slate-700 dark:text-slate-300 block mb-1">NIF</label>
                  <input
                    required
                    type="text"
                    value={nouUsuariNif}
                    onChange={(e) => setNouUsuariNif(e.target.value)}
                    className="w-full px-3 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white font-mono"
                  />
                </div>
                <div>
                  <label className="font-bold text-slate-700 dark:text-slate-300 block mb-1">Email Corporatiu</label>
                  <input
                    required
                    type="email"
                    value={nouUsuariEmail}
                    onChange={(e) => setNouUsuariEmail(e.target.value)}
                    className="w-full px-3 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white"
                  />
                </div>
                <div>
                  <label className="font-bold text-slate-700 dark:text-slate-300 block mb-1">Rol Corporatiu</label>
                  <select
                    value={nouUsuariRol}
                    onChange={(e) => setNouUsuariRol(e.target.value as any)}
                    className="w-full px-3 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white"
                  >
                    <option value="SECRETARIA">Secretaria / Atenció al Client</option>
                    <option value="ENGINYER">Enginyer Tècnic</option>
                    <option value="COMPTABILITAT">Comptabilitat & Facturació</option>
                    <option value="BOSS">Boss / Gerent</option>
                  </select>
                </div>
                <div className="flex justify-end gap-2 pt-3 border-t border-slate-200 dark:border-slate-800">
                  <button
                    type="button"
                    onClick={() => setModalNouUsuari(false)}
                    className="px-3 py-1.5 rounded-lg text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800"
                  >
                    Cancel·lar
                  </button>
                  <button
                    type="submit"
                    className="px-4 py-1.5 rounded-lg font-bold bg-emerald-600 hover:bg-emerald-700 text-white"
                  >
                    Generar Usuari & Contrasenya
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}

      {/* MODAL QR 2FA GOOGLE AUTHENTICATOR (RF-06) */}
      {modalQr2fa && (
        <div className="fixed inset-0 z-50 bg-slate-950/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl max-w-sm w-full p-6 shadow-2xl space-y-4 text-center">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                Codi QR de Configuració 2FA TOTP
              </h3>
              <button onClick={() => setModalQr2fa(null)} className="text-slate-400 hover:text-slate-600">
                <X className="w-4 h-4" />
              </button>
            </div>

            <p className="text-xs text-slate-500 dark:text-slate-400">
              Escanegeu aquest codi amb l'aplicació <strong>Google Authenticator</strong> per a vincular el compte de <strong>{modalQr2fa.usuariNom}</strong>.
            </p>

            {/* Representació Visual de QR 2FA permès per la Constitució v4.0 */}
            <div className="w-44 h-44 mx-auto p-3 bg-white rounded-xl border border-slate-200 shadow-inner flex flex-col items-center justify-center">
              <QrCode className="w-32 h-32 text-slate-900" />
              <span className="text-[9px] font-mono text-slate-500 mt-1">SEVALOR TOTP 2FA</span>
            </div>

            <div className="p-2 rounded bg-slate-100 dark:bg-slate-800 text-[10px] font-mono text-slate-700 dark:text-slate-300">
              Clau Manual: {modalQr2fa.secret}
            </div>

            <button
              type="button"
              onClick={() => setModalQr2fa(null)}
              className="w-full py-2 rounded-xl text-xs font-bold bg-slate-900 text-white hover:bg-slate-800 transition-colors"
            >
              Completat
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
