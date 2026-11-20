"use client";

import React, { useState, useEffect } from "react";
import { useGestio } from "@/lib/gestio-context";
import { apiFetch } from "@/lib/api";
import {
  Users,
  Clock,
  Send,
  Shield,
  ShieldAlert,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  QrCode,
  Lock,
  Plus,
  Trash2,
  Info,
  Check,
  X,
  Radio,
  ExternalLink,
  KeyRound,
  Copy,
  Mail,
  DollarSign,
} from "lucide-react";

// Tipus de pestanyes (Paleta Camaleònica i Node Sobirà són exclusius de Superadmin)
type PestanyaConfig = "personal" | "jornada" | "telegram" | "barema";

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

interface CredencialsModalState {
  obert: boolean;
  titol: string;
  nom_complet: string;
  email: string;
  contrasenya: string;
  rol: string;
  secret_2fa?: string;
  login_url: string;
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

  const [pestanyaActiva, setPestanyaActivaState] = useState<PestanyaConfig>("jornada");
  const setPestanyaActiva = (tab: PestanyaConfig) => {
    setPestanyaActivaState(tab);
    if (typeof window !== "undefined") {
      try {
        sessionStorage.setItem("sevalor_config_tab", tab);
      } catch {
        // Ignorar si sessionStorage no està disponible
      }
    }
  };

  useEffect(() => {
    if (typeof window !== "undefined") {
      try {
        const savedTab = sessionStorage.getItem("sevalor_config_tab") as PestanyaConfig | null;
        if (
          savedTab &&
          ["personal", "jornada", "telegram", "barema"].includes(savedTab)
        ) {
          setPestanyaActivaState(savedTab);
        }
      } catch {
        // Ignorar
      }
    }
  }, []);

  // Dades informatives d'empresa per a la capçalera (lectura des del backend - Zero Mock)
  const [nomEmpresa, setNomEmpresa] = useState("");
  const [nifEmpresa, setNifEmpresa] = useState("");
  const [adrecaEmpresa, setAdrecaEmpresa] = useState("");
  const [subdominiEmpresa, setSubdominiEmpresa] = useState("");
  const [dominiCustomEmpresa, setDominiCustomEmpresa] = useState<string | null>(null);
  const [monograma, setMonograma] = useState("--");
  const [logotipCarregat, setLogotipCarregat] = useState<string | null>(null);

  useEffect(() => {
    apiFetch("/gestio/configuracio/empresa")
      .then((data: any) => {
        if (data.nom) setNomEmpresa(data.nom);
        if (data.nif) setNifEmpresa(data.nif);
        if (data.adreca) setAdrecaEmpresa(data.adreca);
        if (data.subdomini) setSubdominiEmpresa(data.subdomini);
        if (data.domini_custom) setDominiCustomEmpresa(data.domini_custom);
        if (data.monograma) setMonograma(data.monograma);
        if (data.id && data.logotip_path) {
          setLogotipCarregat(`/api/v1/public/tenant/${data.id}/logo`);
        }
      })
      .catch(() => {
        console.error("Error carregant configuració d'empresa");
      });
  }, []);

  const fqdnEmpresa =
    dominiCustomEmpresa ||
    (subdominiEmpresa ? `${subdominiEmpresa}.projectexinoxano.cat` : "Sense subdomini assignat");

  // Estat d'Usuaris Administratius (carregat del backend)
  const [usuaris, setUsuaris] = useState<UsuariAdmin[]>([]);

  useEffect(() => {
    apiFetch<UsuariAdmin[]>("/gestio/configuracio/usuaris")
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
  const [credencialsModal, setCredencialsModal] = useState<CredencialsModalState | null>(null);
  const [copiatCamp, setCopiatCamp] = useState<string | null>(null);

  const [modalQr2fa, setModalQr2fa] = useState<{ obert: boolean; usuariNom: string; secret: string } | null>(null);

  // Slots de Jornada Laboral (carregats del backend)
  const [slots, setSlots] = useState<SlotJornadaItem[]>([]);
  const [modalNouSlot, setModalNouSlot] = useState(false);
  const [slotNom, setSlotNom] = useState("");
  const [slotModalitat, setSlotModalitat] = useState<"JORNADA_CONTINUADA" | "JORNADA_PARTIDA" | "TORN_ESPECIAL">("JORNADA_CONTINUADA");
  const [slotEntrada, setSlotEntrada] = useState("08:00");
  const [slotSortida, setSlotSortida] = useState("16:00");
  const [slotIniciDinar, setSlotIniciDinar] = useState("13:00");
  const [slotFiDinar, setSlotFiDinar] = useState("14:00");
  const [slotHores, setSlotHores] = useState("40");
  const [slotIntensivaEstiu, setSlotIntensivaEstiu] = useState(false);
  const [slotDataIniciEstiu, setSlotDataIniciEstiu] = useState("");
  const [slotDataFiEstiu, setSlotDataFiEstiu] = useState("");
  const [slotEntradaEstiu, setSlotEntradaEstiu] = useState("07:00");
  const [slotSortidaEstiu, setSlotSortidaEstiu] = useState("15:00");
  const [creantSlot, setCreantSlot] = useState(false);

  const carregarSlots = () => {
    apiFetch<SlotJornadaItem[]>("/gestio/configuracio/slots")
      .then(setSlots)
      .catch(() => setSlots([]));
  };

  useEffect(() => {
    carregarSlots();
  }, []);

  // Barema de Preus i Tarifes (Spec 01 FR-017)
  const [preuHoraStd, setPreuHoraStd] = useState("0");
  const [tarifaUrgencia, setTarifaUrgencia] = useState("0");
  const [suplementDespl, setSuplementDespl] = useState("0");
  const [margeMatPct, setMargeMatPct] = useState("0");
  const [partidesBarema, setPartidesBarema] = useState<
    Array<{ codi: string; descripcio: string; unitat: string; preu_eur: number }>
  >([]);
  const [novaPartidaCodi, setNovaPartidaCodi] = useState("");
  const [novaPartidaDesc, setNovaPartidaDesc] = useState("");
  const [novaPartidaUnitat, setNovaPartidaUnitat] = useState("u");
  const [novaPartidaPreu, setNovaPartidaPreu] = useState("");
  const [desantBarema, setDesantBarema] = useState(false);

  useEffect(() => {
    if (esEnginyer) return;
    apiFetch<any>("/gestio/configuracio/barema")
      .then((data) => {
        if (!data) return;
        if (data.preu_hora_standard_eur != null) setPreuHoraStd(String(data.preu_hora_standard_eur));
        if (data.tarifa_urgencia_eur != null) setTarifaUrgencia(String(data.tarifa_urgencia_eur));
        if (data.suplement_desplacament_eur != null) setSuplementDespl(String(data.suplement_desplacament_eur));
        if (data.marge_materials_defecte_pct != null) setMargeMatPct(String(data.marge_materials_defecte_pct));
        if (Array.isArray(data.partides)) setPartidesBarema(data.partides);
      })
      .catch(() => {});
  }, [esEnginyer]);

  // Telegram Bot
  const [telegramToken, setTelegramToken] = useState("");
  const [telegramSecret, setTelegramSecret] = useState("");
  const [telegramEstat, setTelegramEstat] = useState<"OPERATIU" | "ERROR_CONNEXIO" | "NO_CONFIGURAT">("NO_CONFIGURAT");
  const [telegramTestant, setTelegramTestant] = useState(false);

  useEffect(() => {
    // Carregar configuració de Telegram del backend
    apiFetch("/gestio/configuracio/telegram")
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

  // Funció per copiar al portapapers amb fallback segur
  const copiarAlPortapapers = async (text: string, camp: string) => {
    try {
      if (navigator?.clipboard?.writeText) {
        await navigator.clipboard.writeText(text);
      } else {
        const textArea = document.createElement("textarea");
        textArea.value = text;
        document.body.appendChild(textArea);
        textArea.select();
        document.execCommand("copy");
        document.body.removeChild(textArea);
      }
      setCopiatCamp(camp);
      setTimeout(() => setCopiatCamp(null), 2500);
      mostrarFeedback("EXIT", "Dades copiades al portapapers.");
    } catch {
      mostrarFeedback("ERROR", "No s'ha pogut copiar automàticament.");
    }
  };

  // Creació d'Usuari Administratiu (amb generació de credencials i visualització completa)
  const handleCrearUsuari = async (e: React.FormEvent) => {
    e.preventDefault();
    if (esEnginyer) {
      mostrarFeedback("ERROR", "Veto d'Enginyer (HTTP 403): Alta d'usuaris denegada.");
      return;
    }

    const payload = {
      nom: nouUsuariNom.trim(),
      cognoms: nouUsuariCognoms.trim(),
      nif: nouUsuariNif.trim().toUpperCase(),
      email: nouUsuariEmail.trim().toLowerCase(),
      rol: nouUsuariRol,
    };

    try {
      const resp = await apiFetch<any>("/gestio/configuracio/usuaris", {
        method: "POST",
        body: JSON.stringify(payload),
      });

      const nouUsuari: UsuariAdmin = {
        id: resp.id,
        nom: resp.nom || payload.nom,
        cognoms: resp.cognoms || payload.cognoms,
        nom_complet: resp.nom_complet || `${payload.nom} ${payload.cognoms}`.trim(),
        nif: resp.nif || payload.nif,
        email: resp.email || payload.email,
        telefon: resp.telefon || undefined,
        rol: resp.rol || payload.rol,
        estat: resp.estat || "ACTIU",
        totp_activat: !!resp.totp_activat,
        slot_jornada_id: resp.slot_jornada_id,
        data_ultim_acces: "Mai",
      };

      setUsuaris((prev) => [...prev, nouUsuari]);
      setModalNouUsuari(false);
      setNouUsuariNom("");
      setNouUsuariCognoms("");
      setNouUsuariNif("");
      setNouUsuariEmail("");

      const contrasenya = resp.contrasenya_generada || resp.contrasenya_temporal_12_caracters;
      setContrasenyaGenerada(contrasenya);
      setCredencialsModal({
        obert: true,
        titol: "Alta d'Empleat Completada — Credencials d'Accés",
        nom_complet: nouUsuari.nom_complet,
        email: nouUsuari.email,
        contrasenya: contrasenya,
        rol: nouUsuari.rol,
        secret_2fa: resp.secret_2fa,
        login_url: resp.login_url || "/gestio/login",
      });

      mostrarFeedback("EXIT", "Usuari creat correctament. Credencials d'accés generades.");
    } catch (err: any) {
      mostrarFeedback(
        "ERROR",
        err?.message || "No s'ha pogut crear l'usuari. Verifiqueu la connexió amb el backend."
      );
    }
  };

  // Restablir Contrasenya d'Usuari Administratiu
  const handleRestablirContrasenya = async (u: UsuariAdmin) => {
    if (esEnginyer) {
      mostrarFeedback("ERROR", "Veto d'Enginyer (HTTP 403): Acció no permesa.");
      return;
    }
    if (!window.confirm(`Voleu generar una nova contrasenya d'accés per a ${u.nom_complet}? L'anterior quedarà invalidada immediatament.`)) {
      return;
    }

    try {
      const resp = await apiFetch<any>(`/gestio/configuracio/usuaris/${u.id}/reset-password`, {
        method: "POST",
      });
      const contrasenya = resp.contrasenya_generada || resp.contrasenya_temporal_12_caracters;
      setContrasenyaGenerada(contrasenya);
      setCredencialsModal({
        obert: true,
        titol: "Nova Contrasenya d'Accés Generada",
        nom_complet: u.nom_complet,
        email: u.email,
        contrasenya: contrasenya,
        rol: u.rol,
        secret_2fa: resp.secret_2fa,
        login_url: resp.login_url || "/gestio/login",
      });
      mostrarFeedback("EXIT", `Nova contrasenya generada per a ${u.nom_complet}.`);
    } catch (err: any) {
      mostrarFeedback("ERROR", err?.message || "No s'ha pogut restablir la contrasenya de l'usuari.");
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
      await apiFetch(`/gestio/configuracio/usuaris/${id}`, { method: "DELETE" });
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
      const data = await apiFetch<{ secret?: string; secret_2fa?: string }>(
        `/gestio/configuracio/usuaris/${u.id}/reset-2fa`,
        { method: "POST" }
      );
      setModalQr2fa({
        obert: true,
        usuariNom: u.nom_complet,
        secret: data.secret_2fa || data.secret || "",
      });
      mostrarFeedback("EXIT", `2FA reiniciat per a ${u.nom_complet}. Escanegeu el codi QR amb Google Authenticator.`);
    } catch (err: any) {
      mostrarFeedback("ERROR", err?.message || "No s'ha pogut reiniciar el 2FA.");
    }
  };

  // Test de connexió de Telegram (RF-20, EDGE-09)
  const handleProvarTelegram = async () => {
    setTelegramTestant(true);
    try {
      const res = await apiFetch<{ estat: string; missatge?: string; bot_username?: string }>(
        "/gestio/configuracio/telegram/provar",
        { method: "POST" }
      );
      if (res?.estat === "OPERATIU") {
        setTelegramEstat("OPERATIU");
        mostrarFeedback("EXIT", res.missatge || "Connexió getMe satisfactòria amb el Bot de Telegram.");
      } else {
        setTelegramEstat(res?.estat === "NO_CONFIGURAT" ? "NO_CONFIGURAT" : "ERROR_CONNEXIO");
        mostrarFeedback("ERROR", res?.missatge || "No s'ha pogut verificar la connexió del Bot de Telegram.");
      }
    } catch {
      setTelegramEstat("ERROR_CONNEXIO");
      mostrarFeedback("ERROR", "No s'ha pogut connectar amb el Bot de Telegram.");
    } finally {
      setTelegramTestant(false);
    }
  };

  const handleCrearSlot = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!slotNom.trim()) return;
    setCreantSlot(true);
    try {
      await apiFetch("/gestio/configuracio/slots", {
        method: "POST",
        body: JSON.stringify({
          nom: slotNom.trim(),
          modalitat: slotModalitat,
          hora_entrada_teorica: slotEntrada,
          hora_sortida_teorica: slotSortida,
          hora_inici_dinar: slotModalitat === "JORNADA_PARTIDA" ? slotIniciDinar : null,
          hora_fi_dinar: slotModalitat === "JORNADA_PARTIDA" ? slotFiDinar : null,
          hores_convenio_setmanals: Number(slotHores) || 40,
          es_intensiva_estiu: slotIntensivaEstiu,
          data_inici_estiu: slotIntensivaEstiu && slotDataIniciEstiu ? slotDataIniciEstiu : null,
          data_fi_estiu: slotIntensivaEstiu && slotDataFiEstiu ? slotDataFiEstiu : null,
          hora_entrada_estiu: slotIntensivaEstiu ? slotEntradaEstiu : null,
          hora_sortida_estiu: slotIntensivaEstiu ? slotSortidaEstiu : null,
        }),
      });
      setModalNouSlot(false);
      setSlotNom("");
      carregarSlots();
      mostrarFeedback("EXIT", "Slot de jornada laboral creat i desat correctament.");
    } catch (err: any) {
      mostrarFeedback("ERROR", err?.message || "No s'ha pogut crear l'slot de jornada.");
    } finally {
      setCreantSlot(false);
    }
  };

  const handleDesarBarema = async (e: React.FormEvent) => {
    e.preventDefault();
    if (esEnginyer) return;
    setDesantBarema(true);
    try {
      await apiFetch("/gestio/configuracio/barema", {
        method: "PUT",
        body: JSON.stringify({
          preu_hora_standard_eur: Number(preuHoraStd) || 0,
          tarifa_urgencia_eur: Number(tarifaUrgencia) || 0,
          suplement_desplacament_eur: Number(suplementDespl) || 0,
          marge_materials_defecte_pct: Number(margeMatPct) || 0,
          partides: partidesBarema,
        }),
      });
      mostrarFeedback("EXIT", "Barema de preus i tarifes corporatives desat al disc sobirà.");
    } catch (err: any) {
      mostrarFeedback("ERROR", err?.message || "No s'ha pogut desar el barema de preus.");
    } finally {
      setDesantBarema(false);
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
                <img
                  src={logotipCarregat}
                  alt="Logotip"
                  className="w-full h-full object-cover"
                  onError={() => setLogotipCarregat(null)}
                />
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
                {nomEmpresa || "Sense nom"} • NIF: {nifEmpresa || "—"} • Adreça: {adrecaEmpresa || "No especificada"} • Domini:{" "}
                <span className="font-mono text-emerald-600 dark:text-emerald-400">
                  {fqdnEmpresa}
                </span>
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
              <strong className="font-bold">Mode Consulta (Veto d'Enginyer — Spec 011 RF-03):</strong> Tens accés de lectura a la configuració corporativa i al teu slot de jornada assignat. Les modificacions d'usuaris administratius, horaris, barema i paràmetres de Telegram estan reservades a Gerència (Boss) i Secretaria.
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

        {/* SELECTOR DE PESTANYES (Paleta Camaleònica i Node Sobirà gestionats exclusivament des de Superadmin) */}
        <div className="flex flex-wrap items-center gap-2 mt-5 border-t border-slate-200 dark:border-slate-800 pt-4">
          <button
            onClick={() => setPestanyaActiva("personal")}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all ${
              pestanyaActiva === "personal"
                ? "bg-primary text-primary-foreground shadow-md"
                : "text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800"
            }`}
          >
            <Users className="w-3.5 h-3.5" />
            <span>Personal d'Oficina & 2FA TOTP</span>
            <span className="px-1.5 py-0.5 text-[9px] rounded-full bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
              {usuaris.length}
            </span>
          </button>

          <button
            onClick={() => setPestanyaActiva("jornada")}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all ${
              pestanyaActiva === "jornada"
                ? "bg-primary text-primary-foreground shadow-md"
                : "text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800"
            }`}
          >
            <Clock className="w-3.5 h-3.5" />
            <span>Slots de Jornada & Estiu</span>
          </button>

          <button
            onClick={() => setPestanyaActiva("telegram")}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all ${
              pestanyaActiva === "telegram"
                ? "bg-primary text-primary-foreground shadow-md"
                : "text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800"
            }`}
          >
            <Send className="w-3.5 h-3.5" />
            <span>Bot de Telegram Corporatiu</span>
            <span
              className={`w-2 h-2 rounded-full ${
                telegramEstat === "OPERATIU" ? "bg-emerald-500" : "bg-red-500"
              }`}
            />
          </button>

          {!esEnginyer && (
            <button
              onClick={() => setPestanyaActiva("barema")}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all ${
                pestanyaActiva === "barema"
                  ? "bg-primary text-primary-foreground shadow-md"
                  : "text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800"
              }`}
            >
              <DollarSign className="w-3.5 h-3.5" />
              <span>Barema de Preus</span>
            </button>
          )}
        </div>
      </div>

      {/* ========================================================================= */}
      {/* 1. PERSONAL D'OFICINA & 2FA TOTP (RF-01 a RF-07, EDGE-01, EDGE-05)        */}
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
                          {/* Botó Restablir Contrasenya */}
                          <button
                            type="button"
                            disabled={esEnginyer}
                            onClick={() => handleRestablirContrasenya(u)}
                            className="p-1.5 rounded-lg text-slate-500 hover:text-emerald-600 hover:bg-emerald-50 dark:hover:bg-emerald-950/40 transition-colors disabled:opacity-40"
                            title="Generar nova contrasenya temporal"
                          >
                            <KeyRound className="w-3.5 h-3.5" />
                          </button>

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
            {!esEnginyer && (
              <button
                type="button"
                onClick={() => setModalNouSlot(true)}
                className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-bold bg-primary hover:opacity-90 text-primary-foreground shadow-sm"
              >
                <Plus className="w-4 h-4" />
                <span>+ Nou Slot de Jornada</span>
              </button>
            )}
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
                    await apiFetch("/gestio/configuracio/telegram", {
                      method: "PUT",
                      body: JSON.stringify({
                        telegram_bot_token: telegramToken,
                        telegram_webhook_secret: telegramSecret,
                      }),
                    });
                    mostrarFeedback("EXIT", "Credencials de Telegram desades amb èxit.");
                  } catch (err: any) {
                    mostrarFeedback("ERROR", err?.message || "No s'han pogut desar les credencials.");
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
              <button onClick={() => { setModalNouUsuari(false); }} className="text-slate-400 hover:text-slate-600">
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleCrearUsuari} className="space-y-3 text-xs">
              <div>
                <label className="font-bold text-slate-700 dark:text-slate-300 block mb-1">Nom</label>
                <input
                  required
                  type="text"
                  placeholder="Ex: Joan"
                  value={nouUsuariNom}
                  onChange={(e) => setNouUsuariNom(e.target.value)}
                  className="w-full px-3 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white"
                />
              </div>
              <div>
                <label className="font-bold text-slate-700 dark:text-slate-300 block mb-1">Cognoms</label>
                <input
                  type="text"
                  placeholder="Ex: Garcia Font"
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
                  placeholder="Ex: 12345678Z"
                  value={nouUsuariNif}
                  onChange={(e) => setNouUsuariNif(e.target.value)}
                  className="w-full px-3 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white font-mono"
                />
              </div>
              <div>
                <label className="font-bold text-slate-700 dark:text-slate-300 block mb-1">Email Corporatiu (Login)</label>
                <input
                  required
                  type="email"
                  placeholder="Ex: joan@instal-lacions.cat"
                  value={nouUsuariEmail}
                  onChange={(e) => setNouUsuariEmail(e.target.value)}
                  className="w-full px-3 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white font-mono"
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
                  className="px-4 py-1.5 rounded-lg font-bold bg-emerald-600 hover:bg-emerald-700 text-white shadow-sm"
                >
                  Donar d'Alta i Generar Credencials
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL CRE仮想/REINICI CREDENCIALS D'ACCÉS (EMAIL + CONTRASENYA TEMPORAL) */}
      {credencialsModal && (
        <div className="fixed inset-0 z-50 bg-slate-950/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl max-w-lg w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-start justify-between border-b border-slate-100 dark:border-slate-800 pb-3">
              <div className="flex items-center gap-2.5">
                <div className="w-10 h-10 rounded-xl bg-emerald-100 dark:bg-emerald-950/80 text-emerald-600 dark:text-emerald-400 flex items-center justify-center shadow-sm">
                  <KeyRound className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                    {credencialsModal.titol}
                  </h3>
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    {credencialsModal.nom_complet} • <span className="font-bold text-emerald-600">{credencialsModal.rol}</span>
                  </p>
                </div>
              </div>
              <button
                onClick={() => setCredencialsModal(null)}
                className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 p-1 rounded-lg transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="p-3.5 rounded-xl bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800/60 text-xs text-amber-800 dark:text-amber-300 flex items-start gap-2.5">
              <ShieldAlert className="w-4 h-4 shrink-0 mt-0.5" />
              <p>
                <strong>Dades d'inici de sessió confidencials:</strong> Copieu aquestes credencials per fer-les arribar al treballador. La contrasenya temporal només es mostra en aquesta finestra.
              </p>
            </div>

            <div className="space-y-3 text-xs">
              {/* Email / Login */}
              <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-800 flex items-center justify-between">
                <div className="space-y-0.5">
                  <span className="text-[10px] font-mono uppercase text-slate-400 font-bold flex items-center gap-1">
                    <Mail className="w-3 h-3 text-slate-500" />
                    Correu d'Accés (Email de Login)
                  </span>
                  <p className="text-sm font-mono font-bold text-slate-900 dark:text-white select-all">
                    {credencialsModal.email}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => copiarAlPortapapers(credencialsModal.email, "email")}
                  className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-semibold bg-white dark:bg-slate-700 hover:bg-slate-100 dark:hover:bg-slate-600 text-slate-700 dark:text-slate-200 border border-slate-200 dark:border-slate-600 shadow-sm transition-colors"
                >
                  {copiatCamp === "email" ? (
                    <>
                      <Check className="w-3.5 h-3.5 text-emerald-600" />
                      <span className="text-emerald-600">Copiat</span>
                    </>
                  ) : (
                    <>
                      <Copy className="w-3.5 h-3.5" />
                      <span>Copiar</span>
                    </>
                  )}
                </button>
              </div>

              {/* Contrasenya temporal */}
              <div className="p-3.5 rounded-xl bg-emerald-50/70 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800 flex items-center justify-between">
                <div className="space-y-0.5">
                  <span className="text-[10px] font-mono uppercase text-emerald-700 dark:text-emerald-300 font-bold flex items-center gap-1">
                    <Lock className="w-3 h-3" />
                    Codi / Contrasenya Temporal (12 caràcters)
                  </span>
                  <p className="text-base font-mono font-black text-emerald-900 dark:text-emerald-200 tracking-wider select-all">
                    {credencialsModal.contrasenya}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => copiarAlPortapapers(credencialsModal.contrasenya, "pwd")}
                  className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-bold bg-emerald-600 hover:bg-emerald-700 text-white shadow-sm transition-colors"
                >
                  {copiatCamp === "pwd" ? (
                    <>
                      <Check className="w-3.5 h-3.5" />
                      <span>Copiat</span>
                    </>
                  ) : (
                    <>
                      <Copy className="w-3.5 h-3.5" />
                      <span>Copiar</span>
                    </>
                  )}
                </button>
              </div>

              {/* URL d'accés */}
              <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-800 flex items-center justify-between">
                <div className="space-y-0.5">
                  <span className="text-[10px] font-mono uppercase text-slate-400 font-bold">
                    Punt d'Accés al Dashboard
                  </span>
                  <p className="font-mono text-slate-700 dark:text-slate-300 text-[11px]">
                    {typeof window !== "undefined" ? `${window.location.origin}/gestio/login` : credencialsModal.login_url}
                  </p>
                </div>
                <a
                  href={credencialsModal.login_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="p-1.5 rounded-lg text-slate-500 hover:text-emerald-600 transition-colors"
                  title="Obrir pantalla de login"
                >
                  <ExternalLink className="w-4 h-4" />
                </a>
              </div>

              {/* Secret 2FA provisional */}
              {credencialsModal.secret_2fa && (
                <div className="p-2.5 rounded-xl bg-purple-50 dark:bg-purple-950/30 border border-purple-200 dark:border-purple-800/60 flex items-center justify-between">
                  <div className="space-y-0.5">
                    <span className="text-[10px] font-mono uppercase text-purple-700 dark:text-purple-300 font-bold">
                      Clau Secreta 2FA TOTP (Provisional)
                    </span>
                    <p className="font-mono text-[11px] text-purple-900 dark:text-purple-200 select-all">
                      {credencialsModal.secret_2fa}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => copiarAlPortapapers(credencialsModal.secret_2fa || "", "2fa")}
                    className="text-purple-700 dark:text-purple-300 hover:underline text-[11px] font-semibold flex items-center gap-1"
                  >
                    {copiatCamp === "2fa" ? <Check className="w-3 h-3 text-emerald-600" /> : <Copy className="w-3 h-3" />}
                    <span>{copiatCamp === "2fa" ? "Copiat" : "Copiar"}</span>
                  </button>
                </div>
              )}
            </div>

            <div className="pt-2 border-t border-slate-100 dark:border-slate-800 flex flex-col sm:flex-row gap-2">
              <button
                type="button"
                onClick={() => {
                  const urlLogin = typeof window !== "undefined" ? `${window.location.origin}/gestio/login` : "/gestio/login";
                  const textACopiar = [
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                    "SEVALOR Suite — Credencials d'Accés del Treballador",
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                    `Nom del treballador: ${credencialsModal.nom_complet}`,
                    `Rol corporatiu: ${credencialsModal.rol}`,
                    `Email d'accés (Login): ${credencialsModal.email}`,
                    `Contrasenya temporal: ${credencialsModal.contrasenya}`,
                    `Enllaç al Dashboard: ${urlLogin}`,
                    credencialsModal.secret_2fa ? `Clau manual 2FA TOTP: ${credencialsModal.secret_2fa}` : "",
                    "",
                    "* En el primer inici de sessió caldrà configurar l'aplicació d'autenticació 2FA (Google Authenticator / Aegis).",
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                  ].filter(Boolean).join("\n");
                  copiarAlPortapapers(textACopiar, "tot");
                }}
                className="flex-1 flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl text-xs font-bold bg-emerald-600 hover:bg-emerald-700 text-white shadow-sm transition-colors"
              >
                {copiatCamp === "tot" ? (
                  <>
                    <Check className="w-4 h-4" />
                    <span>Credencials Copiades al Portapapers!</span>
                  </>
                ) : (
                  <>
                    <Copy className="w-4 h-4" />
                    <span>Copiar Totes les Credencials d'Accés</span>
                  </>
                )}
              </button>

              <button
                type="button"
                onClick={() => setCredencialsModal(null)}
                className="py-2.5 px-4 rounded-xl text-xs font-bold text-slate-700 dark:text-slate-300 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors"
              >
                Tancar Finestra
              </button>
            </div>
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

      {/* 6. BAREMA DE PREUS ESTÀNDARD (Spec 01 FR-017) */}
      {pestanyaActiva === "barema" && !esEnginyer && (
        <form
          onSubmit={handleDesarBarema}
          className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm space-y-6"
        >
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div>
              <h2 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2">
                <DollarSign className="w-4 h-4 text-primary" />
                Barema de Preus i Tarifes Tècniques (Spec 01 FR-017)
              </h2>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                Tarifes de referència per a pressupostos del Copilot i facturació ràpida d&apos;ordres de treball.
              </p>
            </div>
            <button
              type="submit"
              disabled={desantBarema}
              className="px-4 py-2 rounded-xl text-xs font-bold bg-primary text-primary-foreground hover:opacity-90 disabled:opacity-50 shadow-sm"
            >
              {desantBarema ? "Desant..." : "Desar Barema de Preus"}
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 text-xs">
            <div>
              <label className="block font-bold text-slate-700 dark:text-slate-300 mb-1">
                Preu Hora Estàndard (€/h)
              </label>
              <input
                type="number"
                step="0.5"
                min={0}
                value={preuHoraStd}
                onChange={(e) => setPreuHoraStd(e.target.value)}
                className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800"
              />
            </div>
            <div>
              <label className="block font-bold text-slate-700 dark:text-slate-300 mb-1">
                Tarifa Urgència (€/h)
              </label>
              <input
                type="number"
                step="0.5"
                min={0}
                value={tarifaUrgencia}
                onChange={(e) => setTarifaUrgencia(e.target.value)}
                className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800"
              />
            </div>
            <div>
              <label className="block font-bold text-slate-700 dark:text-slate-300 mb-1">
                Suplement Desplaçament (€)
              </label>
              <input
                type="number"
                step="0.5"
                min={0}
                value={suplementDespl}
                onChange={(e) => setSuplementDespl(e.target.value)}
                className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800"
              />
            </div>
            <div>
              <label className="block font-bold text-slate-700 dark:text-slate-300 mb-1">
                Marge Materials Defecte (%)
              </label>
              <input
                type="number"
                step="0.5"
                min={0}
                value={margeMatPct}
                onChange={(e) => setMargeMatPct(e.target.value)}
                className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800"
              />
            </div>
          </div>

          <div className="space-y-3 border-t border-slate-200 dark:border-slate-800 pt-4 text-xs">
            <h3 className="font-bold text-slate-800 dark:text-slate-200">
              Partides Tipificades del Barema ({partidesBarema.length})
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-5 gap-2">
              <input
                type="text"
                placeholder="Codi (ex: P-REG-01)"
                value={novaPartidaCodi}
                onChange={(e) => setNovaPartidaCodi(e.target.value)}
                className="px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800"
              />
              <input
                type="text"
                placeholder="Descripció tècnica de la partida"
                value={novaPartidaDesc}
                onChange={(e) => setNovaPartidaDesc(e.target.value)}
                className="md:col-span-2 px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800"
              />
              <input
                type="number"
                step="0.01"
                min={0}
                placeholder="Preu €"
                value={novaPartidaPreu}
                onChange={(e) => setNovaPartidaPreu(e.target.value)}
                className="px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800"
              />
              <button
                type="button"
                onClick={() => {
                  if (!novaPartidaCodi.trim() || !novaPartidaDesc.trim() || novaPartidaPreu === "") return;
                  setPartidesBarema((prev) => [
                    ...prev,
                    {
                      codi: novaPartidaCodi.trim().toUpperCase(),
                      descripcio: novaPartidaDesc.trim(),
                      unitat: novaPartidaUnitat.trim() || "u",
                      preu_eur: Number(novaPartidaPreu) || 0,
                    },
                  ]);
                  setNovaPartidaCodi("");
                  setNovaPartidaDesc("");
                  setNovaPartidaPreu("");
                }}
                className="px-3 py-2 rounded-lg bg-slate-800 text-white font-bold hover:bg-slate-700"
              >
                + Afegir Partida
              </button>
            </div>

            {partidesBarema.length > 0 && (
              <div className="divide-y divide-slate-200 dark:divide-slate-800 rounded-xl border border-slate-200 dark:border-slate-800">
                {partidesBarema.map((p, idx) => (
                  <div key={`${p.codi}-${idx}`} className="flex items-center justify-between px-3 py-2">
                    <div>
                      <span className="font-mono font-bold text-primary mr-2">{p.codi}</span>
                      <span>{p.descripcio}</span>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="font-mono font-bold">
                        {Number(p.preu_eur).toFixed(2)} € / {p.unitat}
                      </span>
                      <button
                        type="button"
                        onClick={() => setPartidesBarema((prev) => prev.filter((_, i) => i !== idx))}
                        className="text-rose-500 hover:text-rose-600"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </form>
      )}

      {/* MODAL NOU SLOT DE JORNADA (POST /gestio/configuracio/slots) */}
      {modalNouSlot && (
        <div className="fixed inset-0 z-50 bg-slate-950/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4 text-xs">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                Nou Slot de Jornada Laboral
              </h3>
              <button onClick={() => setModalNouSlot(false)} className="text-slate-400 hover:text-slate-600">
                <X className="w-4 h-4" />
              </button>
            </div>
            <form onSubmit={handleCrearSlot} className="space-y-3">
              <div>
                <label className="block font-bold mb-1">Nom de l&apos;Slot *</label>
                <input
                  required
                  value={slotNom}
                  onChange={(e) => setSlotNom(e.target.value)}
                  placeholder="Ex: Torn Matí Intensiu"
                  className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-bold mb-1">Modalitat</label>
                  <select
                    value={slotModalitat}
                    onChange={(e) => setSlotModalitat(e.target.value as any)}
                    className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800"
                  >
                    <option value="JORNADA_CONTINUADA">Jornada Continuada</option>
                    <option value="JORNADA_PARTIDA">Jornada Partida</option>
                    <option value="TORN_ESPECIAL">Torn Especial</option>
                  </select>
                </div>
                <div>
                  <label className="block font-bold mb-1">Hores Setmanals</label>
                  <input
                    type="number"
                    step="0.5"
                    min={1}
                    value={slotHores}
                    onChange={(e) => setSlotHores(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-bold mb-1">Entrada Teòrica</label>
                  <input
                    type="time"
                    value={slotEntrada}
                    onChange={(e) => setSlotEntrada(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800"
                  />
                </div>
                <div>
                  <label className="block font-bold mb-1">Sortida Teòrica</label>
                  <input
                    type="time"
                    value={slotSortida}
                    onChange={(e) => setSlotSortida(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800"
                  />
                </div>
              </div>
              {slotModalitat === "JORNADA_PARTIDA" && (
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block font-bold mb-1">Inici Dinar</label>
                    <input
                      type="time"
                      value={slotIniciDinar}
                      onChange={(e) => setSlotIniciDinar(e.target.value)}
                      className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800"
                    />
                  </div>
                  <div>
                    <label className="block font-bold mb-1">Fi Dinar</label>
                    <input
                      type="time"
                      value={slotFiDinar}
                      onChange={(e) => setSlotFiDinar(e.target.value)}
                      className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800"
                    />
                  </div>
                </div>
              )}
              <label className="flex items-center gap-2 pt-1">
                <input
                  type="checkbox"
                  checked={slotIntensivaEstiu}
                  onChange={(e) => setSlotIntensivaEstiu(e.target.checked)}
                />
                <span>Activar Jornada Intensiva d&apos;Estiu</span>
              </label>
              {slotIntensivaEstiu && (
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block font-bold mb-1">Inici Estiu</label>
                    <input
                      type="date"
                      required
                      value={slotDataIniciEstiu}
                      onChange={(e) => setSlotDataIniciEstiu(e.target.value)}
                      className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800"
                    />
                  </div>
                  <div>
                    <label className="block font-bold mb-1">Fi Estiu</label>
                    <input
                      type="date"
                      required
                      value={slotDataFiEstiu}
                      onChange={(e) => setSlotDataFiEstiu(e.target.value)}
                      className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800"
                    />
                  </div>
                </div>
              )}
              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setModalNouSlot(false)}
                  className="px-3 py-1.5 rounded-lg border border-slate-300 font-bold"
                >
                  Cancel·lar
                </button>
                <button
                  type="submit"
                  disabled={creantSlot}
                  className="px-4 py-1.5 rounded-lg bg-primary text-primary-foreground font-bold disabled:opacity-50"
                >
                  {creantSlot ? "Desant..." : "Crear Slot"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
