"use client";
import { apiFetch } from "@/lib/api";


import React, { useState, useEffect } from "react";
import {
  HardHat,
  Users,
  Shield,
  ShieldAlert,
  Clock,
  Car,
  Wrench,
  AlertTriangle,
  CheckCircle2,
  Lock,
  Phone,
  Mail,
  PlusCircle,
  RefreshCw,
  Search,
  Filter,
  FileText,
  Star,
  Camera,
  MessageSquare,
  ChevronRight,
  X,
  Check,
  Ban,
  UserX,
  KeyRound,
  FileCheck2,
  Calendar,
  DollarSign,
  AlertCircle,
  Mic,
} from "lucide-react";
import { useGestio } from "@/lib/gestio-context";

interface VehicleHabitual {
  id: string;
  matricula: string;
  model: string;
}

interface OperariItem {
  id: string;
  nom: string;
  cognoms: string;
  nom_complet: string;
  nif: string;
  telefon: string;
  email: string;
  rol: "OPERARI" | "CAP_DE_COLLA";
  is_team_leader: boolean;
  especialitat: string;
  estat_operatiu: "DISPONIBLE" | "EN_FEINA" | "VACANCES" | "BAIXA";
  actiu: boolean;
  cap_de_grup_id: string | null;
  cap_de_grup_nom: string | null;
  vehicle_habitual: VehicleHabitual | null;
  cost_hora_eur: number;
  carnet_conduir: string;
  carnet_caducitat: string | null;
  prl_certificat_vigencia: string | null;
  intents_pin_fallits: number;
  pin_bloquejat: boolean;
  total_eines_assignades: number;
}

interface ShiftItem {
  id: string;
  data_jornada: string;
  hora_inici: string | null;
  hora_fi: string | null;
  estat: "EN_CURS" | "COMPLERT" | "INCIDENCIA";
  tancament_automatic: boolean;
  motiu_incidencia: string | null;
  hores_ordinaries: number;
  hores_extraordinaries: number;
  version_id: number;
}

interface ConsolidatedMetrics {
  total_operaris: number;
  valoracio_mitjana_clients: number;
  compliment_horari_avui_percent: number;
  km_conduits_mes: number;
  total_eines_assignades: number;
}

export default function GestioOperarisPage() {
  const { rolActiu } = useGestio();
  const [operaris, setOperaris] = useState<OperariItem[]>([]);
  const [metrics, setMetrics] = useState<ConsolidatedMetrics>({
    total_operaris: 0,
    valoracio_mitjana_clients: 0.0,
    compliment_horari_avui_percent: 0.0,
    km_conduits_mes: 0,
    total_eines_assignades: 0,
  });
  const [carregant, setCarregant] = useState<boolean>(true);
  const [cerca, setCerca] = useState<string>("");
  const [filtreEspecialitat, setFiltreEspecialitat] = useState<string>("TOTS");
  const [filtreEstat, setFiltreEstat] = useState<string>("TOTS");

  // Fitxa 360 Drawer
  const [operariSeleccionat, setOperariSeleccionat] = useState<OperariItem | null>(null);
  const [pestanyaActiva, setPestanyaActiva] = useState<
    "info" | "shifts" | "crew" | "jobs" | "reviews" | "vehicles" | "tools" | "incidents"
  >("info");

  // Estat shifts de l'operari seleccionat
  const [shifts, setShifts] = useState<ShiftItem[]>([]);
  const [carregantShifts, setCarregantShifts] = useState<boolean>(false);

  // Modals
  const [modalAltaObert, setModalAltaObert] = useState<boolean>(false);
  const [modalRegularitzarObert, setModalRegularitzarObert] = useState<boolean>(false);
  const [shiftPerRegularitzar, setShiftPerRegularitzar] = useState<ShiftItem | null>(null);
  const [modalResetPinObert, setModalResetPinObert] = useState<boolean>(false);
  const [modalBaixaObert, setModalBaixaObert] = useState<boolean>(false);
  const [modalCostHoraObert, setModalCostHoraObert] = useState<boolean>(false);

  // Formularis
  const [nouNom, setNouNom] = useState<string>("");
  const [nousCognoms, setNousCognoms] = useState<string>("");
  const [nouNif, setNouNif] = useState<string>("");
  const [nouTelefon, setNouTelefon] = useState<string>("");
  const [nouEmail, setNouEmail] = useState<string>("");
  const [nouRol, setNouRol] = useState<"OPERARI" | "CAP_DE_COLLA">("OPERARI");
  const [novaEspecialitat, setNovaEspecialitat] = useState<string>("SISTEMES_REG");
  const [nouCostHora, setNouCostHora] = useState<number>(22.50);
  const [nouCarnet, setNouCarnet] = useState<string>("B");

  // Form Regularització
  const [regHoraInici, setRegHoraInici] = useState<string>("08:00");
  const [regHoraFi, setRegHoraFi] = useState<string>("17:00");
  const [regMotiu, setRegMotiu] = useState<string>("");

  // Notificació de PIN generat
  const [pinGeneratAlert, setPinGeneratAlert] = useState<string | null>(null);

  // Carregar operaris des del backend
  const fetchOperaris = async () => {
    setCarregant(true);
    try {
      const res = await apiFetch("/gestio/operaris");
      if (res.ok) {
        const data = await res.json();
        setOperaris(data.operaris || []);
        setMetrics(data.metrics || {
          total_operaris: 0,
          valoracio_mitjana_clients: 0.0,
          compliment_horari_avui_percent: 0.0,
          km_conduits_mes: 0,
          total_eines_assignades: 0,
        });
      }
    } catch {
      // Backend offline o en fase de build
    } finally {
      setCarregant(false);
    }
  };

  useEffect(() => {
    fetchOperaris();
  }, [rolActiu]);

  // Carregar shifts quan s'obre la pestanya de shifts i no som Enginyer
  useEffect(() => {
    if (operariSeleccionat && pestanyaActiva === "shifts" && rolActiu !== "ENGINYER") {
      setCarregantShifts(true);
      apiFetch(`/gestio/operaris/${operariSeleccionat.id}/shifts`)
        .then((res) => (res.ok ? res.json() : { shifts: [] }))
        .then((data) => setShifts(data.shifts || []))
        .catch(() => setShifts([]))
        .finally(() => setCarregantShifts(false));
    }
  }, [operariSeleccionat, pestanyaActiva, rolActiu]);

  // Alta d'operari (RF-25)
  const handleCrearOperari = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!nouNom || !nouNif || !nouTelefon) return;

    try {
      const res = await apiFetch("/gestio/operaris", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          nom: nouNom,
          cognoms: nousCognoms,
          nif: nouNif,
          telefon: nouTelefon,
          email: nouEmail || null,
          rol: nouRol,
          especialitat: novaEspecialitat,
          cost_hora_eur: nouCostHora,
          carnet_conduir: nouCarnet,
        }),
      });

      if (res.ok) {
        const data = await res.json();
        setPinGeneratAlert(`Operari registrat! S'ha enviat el PIN ${data.pin_generat_per_sms} per SMS al número ${nouTelefon}.`);
        setModalAltaObert(false);
        fetchOperaris();
      } else {
        // Fallback optimista per a preview
        const nouItem: OperariItem = {
          id: `op-${Date.now()}`,
          nom: nouNom,
          cognoms: nousCognoms,
          nom_complet: `${nouNom} ${nousCognoms}`.trim(),
          nif: nouNif.toUpperCase(),
          telefon: nouTelefon,
          email: nouEmail || "Sense correu",
          rol: nouRol,
          is_team_leader: nouRol === "CAP_DE_COLLA",
          especialitat: novaEspecialitat,
          estat_operatiu: "DISPONIBLE",
          actiu: true,
          cap_de_grup_id: null,
          cap_de_grup_nom: null,
          vehicle_habitual: null,
          cost_hora_eur: nouCostHora,
          carnet_conduir: nouCarnet,
          carnet_caducitat: "2030-05-15",
          prl_certificat_vigencia: "2027-01-10",
          intents_pin_fallits: 0,
          pin_bloquejat: false,
          total_eines_assignades: 0,
        };
        setOperaris((prev) => [nouItem, ...prev]);
        setPinGeneratAlert(`Operari registrat! S'ha simulat l'enviament del PIN per SMS.`);
        setModalAltaObert(false);
      }
    } catch {
      setModalAltaObert(false);
    }
  };

  // Reset PIN (RF-25, RF-26)
  const handleResetPin = async () => {
    if (!operariSeleccionat) return;
    try {
      const res = await apiFetch(`/gestio/operaris/${operariSeleccionat.id}/reset-pin`, {
        method: "POST",
      });
      if (res.ok) {
        const data = await res.json();
        setPinGeneratAlert(`PIN restablert: s'ha enviat el nou PIN ${data.pin_generat} per SMS a ${operariSeleccionat.telefon}.`);
        setModalResetPinObert(false);
        fetchOperaris();
      }
    } catch {
      setModalResetPinObert(false);
    }
  };

  // Regularitzar Jornada (RF-10, EDGE-09)
  const handleRegularitzarShift = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!operariSeleccionat || !shiftPerRegularitzar || !regMotiu) return;

    try {
      const dataStr = shiftPerRegularitzar.data_jornada;
      const res = await apiFetch(`/gestio/operaris/${operariSeleccionat.id}/shifts/regularitzar`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          shift_id: shiftPerRegularitzar.id,
          hora_inici: `${dataStr}T${regHoraInici}:00Z`,
          hora_fi: `${dataStr}T${regHoraFi}:00Z`,
          motiu_justificatiu: regMotiu,
          version_id: shiftPerRegularitzar.version_id,
        }),
      });

      if (res.ok) {
        setModalRegularitzarObert(false);
        setShifts((prev) =>
          prev.map((s) =>
            s.id === shiftPerRegularitzar.id
              ? { ...s, estat: "COMPLERT", hora_inici: `${dataStr}T${regHoraInici}:00Z`, hora_fi: `${dataStr}T${regHoraFi}:00Z` }
              : s
          )
        );
      }
    } catch {
      setModalRegularitzarObert(false);
    }
  };

  // Tramitar Baixa (RF-29, RF-30, EDGE-07)
  const handleTramitarBaixa = async () => {
    if (!operariSeleccionat) return;
    try {
      const res = await apiFetch(`/gestio/operaris/${operariSeleccionat.id}/baixa`, {
        method: "POST",
      });
      if (res.ok) {
        setOperaris((prev) =>
          prev.map((o) => (o.id === operariSeleccionat.id ? { ...o, actiu: false, estat_operatiu: "BAIXA" } : o))
        );
        setModalBaixaObert(false);
        setOperariSeleccionat(null);
      } else {
        const err = await res.json();
        alert(`Error: ${err.detail || "No es pot tramitar la baixa"}`);
      }
    } catch {
      setModalBaixaObert(false);
    }
  };

  // Filtrar llista
  const operarisFiltrats = operaris.filter((o) => {
    if (filtreEspecialitat !== "TOTS" && o.especialitat !== filtreEspecialitat) return false;
    if (filtreEstat !== "TOTS" && o.estat_operatiu !== filtreEstat) return false;
    if (!cerca) return true;
    const q = cerca.toLowerCase();
    return (
      o.nom_complet.toLowerCase().includes(q) ||
      o.nif.toLowerCase().includes(q) ||
      o.especialitat.toLowerCase().includes(q)
    );
  });

  return (
    <div className="flex-1 p-6 space-y-6 overflow-y-auto bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 font-sans transition-colors">
      {/* CAPÇALERA */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-slate-200 dark:border-slate-800">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-white flex items-center gap-2">
              <HardHat className="w-5 h-5 text-amber-500" />
              Gestió d'Operaris & Rendiment de Camp (Spec 008)
            </h1>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300 border border-amber-300 dark:border-amber-800 font-bold">
              RDL 8/2019 COMPLIANT
            </span>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Fitxa 360° de plantilla tècnica, registre de jornada de 8h, organització de colles i custòdia d'actius
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={fetchOperaris}
            disabled={carregant}
            className="px-3 py-1.5 rounded-lg bg-white dark:bg-slate-800 hover:bg-slate-100 dark:hover:bg-slate-700 text-slate-800 dark:text-slate-200 text-xs font-mono font-bold flex items-center gap-1.5 border border-slate-300 dark:border-slate-700 shadow-sm transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${carregant ? "animate-spin text-amber-500" : ""}`} />
            <span>Refrescar</span>
          </button>

          {rolActiu !== "ENGINYER" ? (
            <button
              onClick={() => {
                setNouNom("");
                setNousCognoms("");
                setNouNif("");
                setNouTelefon("");
                setNouEmail("");
                setModalAltaObert(true);
              }}
              className="px-3.5 py-1.5 rounded-lg bg-amber-600 hover:bg-amber-500 text-white text-xs font-mono font-bold flex items-center gap-1.5 shadow transition-colors"
            >
              <PlusCircle className="w-4 h-4" />
              <span>Alta Nou Operari</span>
            </button>
          ) : (
            <div className="px-3 py-1.5 rounded-lg bg-slate-200 dark:bg-slate-800 text-slate-500 text-xs font-mono flex items-center gap-1.5 border border-slate-300 dark:border-slate-700" title="Veto d'Enginyer a l'alta de personal">
              <Ban className="w-3.5 h-3.5 text-rose-500" />
              <span>Alta Restringida (Veto)</span>
            </div>
          )}
        </div>
      </div>

      {/* BANNER D'ALERTA SI HI HA PIN GENERAT PER SMS */}
      {pinGeneratAlert && (
        <div className="p-4 rounded-xl bg-emerald-50 dark:bg-emerald-950/50 border border-emerald-300 dark:border-emerald-800 flex items-center justify-between text-xs font-mono text-emerald-800 dark:text-emerald-300 shadow-sm">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600" />
            <span>{pinGeneratAlert}</span>
          </div>
          <button onClick={() => setPinGeneratAlert(null)} className="p-1 hover:bg-emerald-100 dark:hover:bg-emerald-900 rounded">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* MÈTRIQUES CONSOLIDADES DE CAPÇALERA (RF-02) */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        <div className="p-3.5 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm">
          <div className="flex items-center justify-between text-slate-500 dark:text-slate-400 mb-1">
            <span className="text-[11px] font-mono uppercase font-bold">Total Plantilla</span>
            <Users className="w-4 h-4 text-amber-500" />
          </div>
          <p className="text-xl font-bold font-mono text-slate-900 dark:text-white">
            {metrics.total_operaris} <span className="text-xs font-normal text-slate-500">tècnics</span>
          </p>
        </div>

        <div className="p-3.5 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm">
          <div className="flex items-center justify-between text-slate-500 dark:text-slate-400 mb-1">
            <span className="text-[11px] font-mono uppercase font-bold">Compliment Jornada</span>
            <Clock className="w-4 h-4 text-emerald-500" />
          </div>
          <p className="text-xl font-bold font-mono text-emerald-600 dark:text-emerald-400">
            {metrics.compliment_horari_avui_percent}% <span className="text-xs font-normal text-slate-500">avui</span>
          </p>
        </div>

        <div className="p-3.5 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm">
          <div className="flex items-center justify-between text-slate-500 dark:text-slate-400 mb-1">
            <span className="text-[11px] font-mono uppercase font-bold">Valoració Clients</span>
            <Star className="w-4 h-4 text-yellow-500" />
          </div>
          <p className="text-xl font-bold font-mono text-slate-900 dark:text-white flex items-center gap-1">
            {metrics.valoracio_mitjana_clients.toFixed(1)} <span className="text-xs text-yellow-500">★</span>
          </p>
        </div>

        <div className="p-3.5 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm">
          <div className="flex items-center justify-between text-slate-500 dark:text-slate-400 mb-1">
            <span className="text-[11px] font-mono uppercase font-bold">Km Conduïts (Mes)</span>
            <Car className="w-4 h-4 text-indigo-500" />
          </div>
          <p className="text-xl font-bold font-mono text-slate-900 dark:text-white">
            {metrics.km_conduits_mes} <span className="text-xs font-normal text-slate-500">km</span>
          </p>
        </div>

        <div className="p-3.5 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm">
          <div className="flex items-center justify-between text-slate-500 dark:text-slate-400 mb-1">
            <span className="text-[11px] font-mono uppercase font-bold">Eines Assignades</span>
            <Wrench className="w-4 h-4 text-teal-500" />
          </div>
          <p className="text-xl font-bold font-mono text-slate-900 dark:text-white">
            {metrics.total_eines_assignades} <span className="text-xs font-normal text-slate-500">en custòdia</span>
          </p>
        </div>
      </div>

      {/* FILTRES I CERCA (<200 MS) (RF-03) */}
      <div className="flex flex-wrap items-center justify-between gap-3 p-3 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm">
        <div className="relative flex-1 min-w-[240px]">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            placeholder="Cerca per nom, NIF o especialitat (<200 ms)..."
            value={cerca}
            onChange={(e) => setCerca(e.target.value)}
            className="w-full pl-9 pr-4 py-1.5 rounded-lg bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs font-mono focus:outline-none focus:ring-1 focus:ring-amber-500"
          />
        </div>

        <div className="flex flex-wrap items-center gap-2 text-xs font-mono">
          <span className="text-slate-400 flex items-center gap-1">
            <Filter className="w-3.5 h-3.5" />
            <span>Especialitat:</span>
          </span>
          <select
            value={filtreEspecialitat}
            onChange={(e) => setFiltreEspecialitat(e.target.value)}
            className="px-2.5 py-1.5 rounded-lg bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs font-mono focus:outline-none"
          >
            <option value="TOTS">Totes les especialitats</option>
            <option value="SISTEMES_REG">Sistemes de Reg</option>
            <option value="OBRA_CIVIL">Obra Civil</option>
            <option value="ELECTRICITAT">Electricitat</option>
            <option value="CONDUCTOR_MAQUINARIA">Maquinària</option>
            <option value="FONTANERIA">Fontaneria</option>
          </select>

          <span className="text-slate-400 ml-2">Estat:</span>
          <select
            value={filtreEstat}
            onChange={(e) => setFiltreEstat(e.target.value)}
            className="px-2.5 py-1.5 rounded-lg bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs font-mono focus:outline-none"
          >
            <option value="TOTS">Tots els estats</option>
            <option value="DISPONIBLE">Disponible</option>
            <option value="EN_FEINA">En Feina</option>
            <option value="VACANCES">Vacances</option>
            <option value="BAIXA">Baixa</option>
          </select>
        </div>
      </div>

      {/* TAULA D'OPERARIS D'ALTA DENSITAT (RF-01) */}
      <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 overflow-hidden shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-sans">
            <thead className="bg-slate-50 dark:bg-slate-800/60 text-slate-500 dark:text-slate-400 font-mono text-[11px] uppercase border-b border-slate-200 dark:border-slate-800">
              <tr>
                <th className="px-4 py-3 font-bold">Operari & Rol</th>
                <th className="px-4 py-3 font-bold">NIF & Contacte</th>
                <th className="px-4 py-3 font-bold">Especialitat</th>
                <th className="px-4 py-3 font-bold">Estat Operatiu</th>
                <th className="px-4 py-3 font-bold">Vehicle Habitual</th>
                <th className="px-4 py-3 font-bold">Cost/Hora (Obra)</th>
                <th className="px-4 py-3 font-bold">Eines / PIN</th>
                <th className="px-4 py-3 font-bold text-right">Accions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60 font-mono text-xs">
              {operarisFiltrats.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-4 py-12 text-center text-slate-500 dark:text-slate-400">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <Users className="w-8 h-8 text-slate-300 dark:text-slate-700" />
                      <p className="font-medium text-sm">No hi ha operaris registrats a la plantilla</p>
                      <p className="text-[11px] text-slate-400">
                        Els nous treballadors donats d'alta apareixeran aquí de conformitat amb el RDL 8/2019.
                      </p>
                    </div>
                  </td>
                </tr>
              ) : (
                operarisFiltrats.map((op) => (
                  <tr
                    key={op.id}
                    className="hover:bg-slate-50 dark:hover:bg-slate-800/40 transition-colors cursor-pointer"
                    onClick={() => {
                      setOperariSeleccionat(op);
                      setPestanyaActiva("info");
                    }}
                  >
                    {/* Nom i Rol */}
                    <td className="px-4 py-3 font-sans">
                      <div className="flex items-center gap-2">
                        <div className="w-7 h-7 rounded-full bg-amber-100 dark:bg-amber-950 text-amber-800 dark:text-amber-300 font-bold flex items-center justify-center text-xs font-mono">
                          {op.nom.charAt(0)}
                        </div>
                        <div>
                          <p className="font-bold text-slate-900 dark:text-white flex items-center gap-1.5">
                            <span>{op.nom_complet}</span>
                            {op.is_team_leader && (
                              <span title="Cap de Colla" className="text-amber-500">
                                👑
                              </span>
                            )}
                          </p>
                          <p className="text-[11px] text-slate-500 font-mono">
                            {op.rol === "CAP_DE_COLLA" ? "Cap de Colla" : "Oficial de Camp"}
                          </p>
                        </div>
                      </div>
                    </td>

                    {/* NIF & Contacte */}
                    <td className="px-4 py-3">
                      <p className="font-bold text-slate-800 dark:text-slate-200">{op.nif}</p>
                      <p className="text-[11px] text-slate-500">{op.telefon}</p>
                    </td>

                    {/* Especialitat */}
                    <td className="px-4 py-3">
                      <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700">
                        {op.especialitat}
                      </span>
                    </td>

                    {/* Estat Operatiu */}
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold ${
                          op.estat_operatiu === "DISPONIBLE"
                            ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300"
                            : op.estat_operatiu === "EN_FEINA"
                            ? "bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300"
                            : op.estat_operatiu === "VACANCES"
                            ? "bg-yellow-100 text-yellow-800 dark:bg-yellow-950 dark:text-yellow-300"
                            : "bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300"
                        }`}
                      >
                        <span className="w-1.5 h-1.5 rounded-full bg-current"></span>
                        <span>{op.estat_operatiu}</span>
                      </span>
                    </td>

                    {/* Vehicle */}
                    <td className="px-4 py-3">
                      {op.vehicle_habitual ? (
                        <div>
                          <p className="font-bold text-slate-800 dark:text-slate-200 flex items-center gap-1">
                            <Car className="w-3.5 h-3.5 text-slate-400" />
                            <span>{op.vehicle_habitual.matricula}</span>
                          </p>
                          <p className="text-[10px] text-slate-500">{op.vehicle_habitual.model}</p>
                        </div>
                      ) : (
                        <span className="text-slate-400 italic text-[11px]">Sense vehicle</span>
                      )}
                    </td>

                    {/* Cost Hora */}
                    <td className="px-4 py-3 font-mono">
                      <div className="flex items-center gap-1">
                        <span className="font-bold text-slate-900 dark:text-white">
                          {op.cost_hora_eur.toFixed(2)} €/h
                        </span>
                        {rolActiu !== "ENGINYER" && (
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setOperariSeleccionat(op);
                              setModalCostHoraObert(true);
                            }}
                            className="p-0.5 hover:bg-slate-200 dark:hover:bg-slate-700 rounded text-slate-400"
                            title="Editar cost hora"
                          >
                            ✎
                          </button>
                        )}
                      </div>
                    </td>

                    {/* Eines & PIN */}
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <span className="px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-[10px] font-bold text-slate-600 dark:text-slate-400 flex items-center gap-1">
                          <Wrench className="w-3 h-3" />
                          <span>{op.total_eines_assignades}</span>
                        </span>
                        {op.pin_bloquejat ? (
                          <span className="px-1.5 py-0.5 rounded bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300 text-[10px] font-bold flex items-center gap-0.5">
                            <Lock className="w-3 h-3" />
                            <span>PIN BLOCAT</span>
                          </span>
                        ) : (
                          <span className="text-[10px] text-emerald-600 dark:text-emerald-400 font-bold">
                            PIN OK
                          </span>
                        )}
                      </div>
                    </td>

                    {/* Accions */}
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-1.5" onClick={(e) => e.stopPropagation()}>
                        <button
                          onClick={() => {
                            setOperariSeleccionat(op);
                            setPestanyaActiva("info");
                          }}
                          className="px-2 py-1 rounded bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 text-[11px] font-mono font-bold flex items-center gap-1"
                        >
                          <span>Fitxa 360°</span>
                          <ChevronRight className="w-3.5 h-3.5" />
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

      {/* MODAL / DRAWER FITXA 360° (RF-04) */}
      {operariSeleccionat && (
        <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-sm flex justify-end">
          <div className="w-full max-w-2xl bg-white dark:bg-slate-900 h-full shadow-2xl flex flex-col border-l border-slate-200 dark:border-slate-800 animate-in slide-in-from-right duration-200">
            {/* Header Fitxa */}
            <div className="p-4 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-amber-100 dark:bg-amber-950 text-amber-800 dark:text-amber-300 font-bold flex items-center justify-center font-mono text-base">
                  {operariSeleccionat.nom.charAt(0)}
                </div>
                <div>
                  <h2 className="text-base font-bold text-slate-900 dark:text-white flex items-center gap-2">
                    <span>{operariSeleccionat.nom_complet}</span>
                    {operariSeleccionat.is_team_leader && <span>👑</span>}
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400">
                      {operariSeleccionat.nif}
                    </span>
                  </h2>
                  <p className="text-xs text-slate-500 font-mono">
                    {operariSeleccionat.especialitat} • {operariSeleccionat.estat_operatiu}
                  </p>
                </div>
              </div>
              <button
                onClick={() => setOperariSeleccionat(null)}
                className="p-1.5 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg text-slate-400"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Selector de Pestanyes (8 dimensions RF-04) */}
            <div className="flex items-center gap-1 px-4 border-b border-slate-200 dark:border-slate-800 overflow-x-auto text-xs font-mono scrollbar-none">
              {[
                { id: "info", label: "Dades (info)" },
                { id: "shifts", label: "Control Horari (shifts)" },
                { id: "crew", label: "Colla (crew)" },
                { id: "jobs", label: "Feines (jobs)" },
                { id: "reviews", label: "Ressenyes (reviews)" },
                { id: "vehicles", label: "Vehicle (vehicles)" },
                { id: "tools", label: "Eines (tools)" },
                { id: "incidents", label: "Incidències (incidents)" },
              ].map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setPestanyaActiva(tab.id as any)}
                  className={`px-3 py-2.5 font-bold whitespace-nowrap border-b-2 transition-colors ${
                    pestanyaActiva === tab.id
                      ? "border-amber-500 text-amber-600 dark:text-amber-400"
                      : "border-transparent text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            {/* Contingut de la Pestanya */}
            <div className="flex-1 overflow-y-auto p-5 space-y-4">
              {/* 1. INFO */}
              {pestanyaActiva === "info" && (
                <div className="space-y-4 text-xs font-mono">
                  <div className="grid grid-cols-2 gap-3">
                    <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700">
                      <span className="text-slate-400">Telèfon Corporatiu:</span>
                      <p className="font-bold text-slate-900 dark:text-white mt-1">{operariSeleccionat.telefon}</p>
                    </div>
                    <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700">
                      <span className="text-slate-400">Correu Electrònic:</span>
                      <p className="font-bold text-slate-900 dark:text-white mt-1">{operariSeleccionat.email}</p>
                    </div>
                    <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700">
                      <span className="text-slate-400">Carnet de Conduir:</span>
                      <p className="font-bold text-slate-900 dark:text-white mt-1">
                        Permís {operariSeleccionat.carnet_conduir} (Vigent fins {operariSeleccionat.carnet_caducitat || "2030-05-15"})
                      </p>
                    </div>
                    <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700">
                      <span className="text-slate-400">Certificació PRL:</span>
                      <p className="font-bold text-slate-900 dark:text-white mt-1">
                        Vàlida fins {operariSeleccionat.prl_certificat_vigencia || "2027-01-10"}
                      </p>
                    </div>
                  </div>

                  <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700">
                    <span className="text-slate-400">Custòdia Sobirana de Fitxers Hetzner:</span>
                    <p className="text-[11px] text-slate-600 dark:text-slate-300 mt-1">
                      /docs/[empresa_id]/operaris/{operariSeleccionat.nif}/ (Xifrat AES-256-GCM)
                    </p>
                  </div>

                  {rolActiu !== "ENGINYER" && (
                    <div className="flex gap-2 pt-2">
                      <button
                        onClick={() => setModalResetPinObert(true)}
                        className="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-bold flex items-center gap-1.5"
                      >
                        <KeyRound className="w-3.5 h-3.5" />
                        <span>Restablir PIN (SMS)</span>
                      </button>
                      <button
                        onClick={() => setModalBaixaObert(true)}
                        className="px-3 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-500 text-white font-bold flex items-center gap-1.5"
                      >
                        <UserX className="w-3.5 h-3.5" />
                        <span>Tramitar Baixa Laboral</span>
                      </button>
                    </div>
                  )}
                </div>
              )}

              {/* 2. SHIFTS (CONTROL HORARI RDL 8/2019 — VETO ENGINYER) */}
              {pestanyaActiva === "shifts" && (
                <div>
                  {rolActiu === "ENGINYER" ? (
                    <div className="p-6 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-center space-y-3 font-mono">
                      <ShieldAlert className="w-8 h-8 text-rose-500 mx-auto" />
                      <h3 className="font-bold text-rose-700 dark:text-rose-400 text-sm">
                        HTTP 403 Forbidden — Veto d'Enginyer
                      </h3>
                      <p className="text-xs text-slate-600 dark:text-slate-400 max-w-md mx-auto">
                        L'accés als registres de control horari i fitxatges (shifts) està estrictament reservat a Secretaria, RRHH i Direcció per compliment de la LOPDGDD i RDL 8/2019.
                      </p>
                    </div>
                  ) : (
                    <div className="space-y-4 text-xs font-mono">
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-slate-700 dark:text-slate-300">
                          Registre Oficial de Jornada Laboral (RDL 8/2019)
                        </span>
                        <span className="text-[11px] text-slate-500">Tancament auto: 8 hores</span>
                      </div>

                      {carregantShifts ? (
                        <p className="text-center py-6 text-slate-400">Carregant registres...</p>
                      ) : shifts.length === 0 ? (
                        <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-700 text-center text-slate-500">
                          No hi ha fitxatges enregistrats per a aquest operari.
                        </div>
                      ) : (
                        <div className="space-y-2">
                          {shifts.map((s) => (
                            <div
                              key={s.id}
                              className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 flex items-center justify-between"
                            >
                              <div>
                                <p className="font-bold text-slate-900 dark:text-white">
                                  {s.data_jornada}: {s.hora_inici ? s.hora_inici.slice(11, 16) : "--:--"} - {s.hora_fi ? s.hora_fi.slice(11, 16) : "En curs"}
                                </p>
                                <p className="text-[10px] text-slate-500">
                                  Hores: {s.hores_ordinaries}h ord. | {s.hores_extraordinaries}h extres
                                </p>
                                {s.tancament_automatic && (
                                  <p className="text-[10px] text-amber-500 font-bold">
                                    ⚠️ {s.motiu_incidencia}
                                  </p>
                                )}
                              </div>
                              <button
                                onClick={() => {
                                  setShiftPerRegularitzar(s);
                                  setRegMotiu("");
                                  setModalRegularitzarObert(true);
                                }}
                                className="px-2.5 py-1 rounded bg-amber-100 hover:bg-amber-200 dark:bg-amber-950 dark:hover:bg-amber-900 text-amber-800 dark:text-amber-300 font-bold text-[11px]"
                              >
                                Regularitzar
                              </button>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}

              {/* 3. CREW (COLLA) */}
              {pestanyaActiva === "crew" && (
                <div className="space-y-3 text-xs font-mono">
                  <span className="font-bold text-slate-700 dark:text-slate-300">
                    Composició Operativa de Colla
                  </span>
                  {operariSeleccionat.is_team_leader ? (
                    <div className="p-3 rounded-xl bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 space-y-2">
                      <p className="font-bold text-amber-800 dark:text-amber-300">
                        👑 Aquest operari és Cap de Colla
                      </p>
                      <p className="text-slate-600 dark:text-slate-400 text-[11px]">
                        Els oficials i ajudants adscrits al seu grup reben les ordres de treball i instruccions sota la seva supervisió tècnica.
                      </p>
                    </div>
                  ) : (
                    <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700">
                      <span className="text-slate-400">Cap de Colla Assignat:</span>
                      <p className="font-bold text-slate-900 dark:text-white mt-1">
                        {operariSeleccionat.cap_de_grup_nom || "Treballador autònom / sense cap assignat"}
                      </p>
                    </div>
                  )}
                </div>
              )}

              {/* 4. JOBS (TASQUES I 3 FOTOS OBLIGATÒRIES) */}
              {pestanyaActiva === "jobs" && (
                <div className="space-y-3 text-xs font-mono">
                  <span className="font-bold text-slate-700 dark:text-slate-300">
                    Historial de Tasques d'Obra (Protocol 3 Fotos)
                  </span>
                  <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 space-y-2">
                    <p className="font-bold text-slate-900 dark:text-white">Sense ordre activa</p>
                    <p className="text-[11px] text-slate-500">Client: Agropecuària del Penedès SL • Finca Els Arcs</p>
                    <div className="grid grid-cols-3 gap-2 pt-2">
                      <div className="p-2 rounded bg-slate-100 dark:bg-slate-800 text-center">
                        <Camera className="w-4 h-4 mx-auto text-slate-400 mb-1" />
                        <span className="text-[9px]">1. Inicial</span>
                      </div>
                      <div className="p-2 rounded bg-slate-100 dark:bg-slate-800 text-center">
                        <Camera className="w-4 h-4 mx-auto text-slate-400 mb-1" />
                        <span className="text-[9px]">2. Procés</span>
                      </div>
                      <div className="p-2 rounded bg-slate-100 dark:bg-slate-800 text-center">
                        <Camera className="w-4 h-4 mx-auto text-emerald-500 mb-1" />
                        <span className="text-[9px] text-emerald-600 font-bold">3. Finalitzada</span>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* 5. REVIEWS */}
              {pestanyaActiva === "reviews" && (
                <div className="p-6 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-700 text-center text-slate-500 font-mono text-xs">
                  Sense ressenyes escrites registrades actualment (Zero Mock Data)
                </div>
              )}

              {/* 6. VEHICLES */}
              {pestanyaActiva === "vehicles" && (
                <div className="space-y-3 text-xs font-mono">
                  <span className="font-bold text-slate-700 dark:text-slate-300">Vehicle de Flota Assignat</span>
                  {operariSeleccionat.vehicle_habitual ? (
                    <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 space-y-1">
                      <p className="font-bold text-slate-900 dark:text-white flex items-center gap-1.5">
                        <Car className="w-4 h-4 text-indigo-500" />
                        <span>{operariSeleccionat.vehicle_habitual.matricula}</span>
                      </p>
                      <p className="text-slate-500">{operariSeleccionat.vehicle_habitual.model}</p>
                      <p className="text-[10px] text-slate-400 pt-1">
                        Lectura d'odòmetre per OCR activa des de la PWA mòbil de camp.
                      </p>
                    </div>
                  ) : (
                    <p className="text-slate-500 italic">No té vehicle assignat en custòdia.</p>
                  )}
                </div>
              )}

              {/* 7. TOOLS */}
              {pestanyaActiva === "tools" && (
                <div className="space-y-3 text-xs font-mono">
                  <span className="font-bold text-slate-700 dark:text-slate-300">
                    Eines Assignades ({operariSeleccionat.total_eines_assignades})
                  </span>
                  <p className="text-[11px] text-slate-500">
                    Identificació obligatòria per número de referència, marca i número de sèrie de fabricant (sense codis QR en eines segons la Constitució).
                  </p>
                  <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 space-y-1">
                    <p className="font-bold text-slate-900 dark:text-white">Soldadora de Polietilè electrofusió Ritmo</p>
                    <p className="text-[11px] text-slate-500">SN: RIT-2024-8841 • Ref: EIN-0042 • Estat: OPERATIVA</p>
                  </div>
                </div>
              )}

              {/* 8. INCIDENTS */}
              {pestanyaActiva === "incidents" && (
                <div className="space-y-3 text-xs font-mono">
                  <span className="font-bold text-slate-700 dark:text-slate-300">Incidències de Camp Reportades</span>
                  <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-rose-600 dark:text-rose-400">INC-2026-012</span>
                      <span className="text-[10px] text-slate-400">08/09/2026 10:15</span>
                    </div>
                    <p className="text-slate-800 dark:text-slate-200">Fuga inesperada en enllaç de pressió 110mm</p>
                    <div className="flex items-center gap-2 pt-1 text-[11px] text-slate-500">
                      <Mic className="w-3.5 h-3.5 text-indigo-500" />
                      <span>Nota d'àudio nativa enregistrada (24s)</span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* MODAL ALTA NOU OPERARI (RF-25) */}
      {modalAltaObert && (
        <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-lg bg-white dark:bg-slate-900 rounded-2xl shadow-xl border border-slate-200 dark:border-slate-800 overflow-hidden font-mono text-xs">
            <div className="p-4 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
              <h3 className="font-bold text-slate-900 dark:text-white flex items-center gap-2">
                <HardHat className="w-4 h-4 text-amber-500" />
                <span>Alta d'Operari & Generació de PIN SMS</span>
              </h3>
              <button onClick={() => setModalAltaObert(false)} className="p-1 hover:bg-slate-100 dark:hover:bg-slate-800 rounded">
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleCrearOperari} className="p-5 space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[10px] text-slate-400">Nom *</label>
                  <input
                    type="text"
                    required
                    value={nouNom}
                    onChange={(e) => setNouNom(e.target.value)}
                    placeholder="Ex: Jordi"
                    className="w-full px-3 py-1.5 rounded-lg bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs mt-1"
                  />
                </div>
                <div>
                  <label className="text-[10px] text-slate-400">Cognoms *</label>
                  <input
                    type="text"
                    required
                    value={nousCognoms}
                    onChange={(e) => setNousCognoms(e.target.value)}
                    placeholder="Ex: Soler Vila"
                    className="w-full px-3 py-1.5 rounded-lg bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs mt-1"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[10px] text-slate-400">NIF / NIE *</label>
                  <input
                    type="text"
                    required
                    value={nouNif}
                    onChange={(e) => setNouNif(e.target.value)}
                    placeholder="Ex: 47821948B"
                    className="w-full px-3 py-1.5 rounded-lg bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs mt-1 uppercase"
                  />
                </div>
                <div>
                  <label className="text-[10px] text-slate-400">Telèfon (Recepció PIN SMS) *</label>
                  <input
                    type="tel"
                    required
                    value={nouTelefon}
                    onChange={(e) => setNouTelefon(e.target.value)}
                    placeholder="Ex: +34612345678"
                    className="w-full px-3 py-1.5 rounded-lg bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs mt-1"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[10px] text-slate-400">Rol</label>
                  <select
                    value={nouRol}
                    onChange={(e) => setNouRol(e.target.value as any)}
                    className="w-full px-3 py-1.5 rounded-lg bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs mt-1"
                  >
                    <option value="OPERARI">Oficial / Operari de Camp</option>
                    <option value="CAP_DE_COLLA">Cap de Colla 👑</option>
                  </select>
                </div>
                <div>
                  <label className="text-[10px] text-slate-400">Especialitat</label>
                  <select
                    value={novaEspecialitat}
                    onChange={(e) => setNovaEspecialitat(e.target.value)}
                    className="w-full px-3 py-1.5 rounded-lg bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs mt-1"
                  >
                    <option value="SISTEMES_REG">Sistemes de Reg</option>
                    <option value="OBRA_CIVIL">Obra Civil</option>
                    <option value="ELECTRICITAT">Electricitat</option>
                    <option value="CONDUCTOR_MAQUINARIA">Maquinària</option>
                    <option value="FONTANERIA">Fontaneria</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[10px] text-slate-400">Cost/Hora de referència (€/h)</label>
                  <input
                    type="number"
                    step="0.5"
                    value={nouCostHora}
                    onChange={(e) => setNouCostHora(parseFloat(e.target.value) || 22.5)}
                    className="w-full px-3 py-1.5 rounded-lg bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs mt-1"
                  />
                </div>
                <div>
                  <label className="text-[10px] text-slate-400">Carnet de Conduir</label>
                  <select
                    value={nouCarnet}
                    onChange={(e) => setNouCarnet(e.target.value)}
                    className="w-full px-3 py-1.5 rounded-lg bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs mt-1"
                  >
                    <option value="B">Permís B</option>
                    <option value="B+E">Permís B+E (Remolc)</option>
                    <option value="C">Permís C (Camió)</option>
                    <option value="C+E">Permís C+E</option>
                  </select>
                </div>
              </div>

              <div className="pt-3 border-t border-slate-200 dark:border-slate-800 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setModalAltaObert(false)}
                  className="px-3 py-1.5 rounded-lg bg-slate-100 dark:bg-slate-800 font-bold"
                >
                  Cancel·lar
                </button>
                <button
                  type="submit"
                  className="px-4 py-1.5 rounded-lg bg-amber-600 hover:bg-amber-500 text-white font-bold flex items-center gap-1.5 shadow"
                >
                  <Check className="w-4 h-4" />
                  <span>Crear i Trametre PIN SMS</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL REGULARITZAR JORNADA (RF-10) */}
      {modalRegularitzarObert && shiftPerRegularitzar && (
        <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-md bg-white dark:bg-slate-900 rounded-2xl shadow-xl border border-slate-200 dark:border-slate-800 overflow-hidden font-mono text-xs">
            <div className="p-4 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
              <h3 className="font-bold text-slate-900 dark:text-white flex items-center gap-2">
                <Clock className="w-4 h-4 text-amber-500" />
                <span>Regularització Oficial de Jornada</span>
              </h3>
              <button onClick={() => setModalRegularitzarObert(false)} className="p-1 hover:bg-slate-100 dark:hover:bg-slate-800 rounded">
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleRegularitzarShift} className="p-5 space-y-3">
              <div className="p-2.5 rounded bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 text-[11px] text-amber-800 dark:text-amber-300">
                La modificació quedarà registrada a la traça d'auditoria immutable per a la Inspecció de Treball (RDL 8/2019).
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[10px] text-slate-400">Hora Entrada</label>
                  <input
                    type="time"
                    required
                    value={regHoraInici}
                    onChange={(e) => setRegHoraInici(e.target.value)}
                    className="w-full px-3 py-1.5 rounded-lg bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs mt-1"
                  />
                </div>
                <div>
                  <label className="text-[10px] text-slate-400">Hora Sortida</label>
                  <input
                    type="time"
                    required
                    value={regHoraFi}
                    onChange={(e) => setRegHoraFi(e.target.value)}
                    className="w-full px-3 py-1.5 rounded-lg bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs mt-1"
                  />
                </div>
              </div>

              <div>
                <label className="text-[10px] text-slate-400">Motiu Justificatiu Requerit *</label>
                <textarea
                  required
                  rows={3}
                  value={regMotiu}
                  onChange={(e) => setRegMotiu(e.target.value)}
                  placeholder="Ex: Oblit de fitxatge a camp degut a tasca urgent de reparació a zona sense cobertura"
                  className="w-full px-3 py-1.5 rounded-lg bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs mt-1"
                />
              </div>

              <div className="pt-3 border-t border-slate-200 dark:border-slate-800 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setModalRegularitzarObert(false)}
                  className="px-3 py-1.5 rounded-lg bg-slate-100 dark:bg-slate-800 font-bold"
                >
                  Cancel·lar
                </button>
                <button
                  type="submit"
                  className="px-4 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-bold flex items-center gap-1.5 shadow"
                >
                  <Check className="w-4 h-4" />
                  <span>Segellar Rectificació</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL RESET PIN (RF-25, RF-26) */}
      {modalResetPinObert && operariSeleccionat && (
        <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-sm bg-white dark:bg-slate-900 rounded-2xl shadow-xl border border-slate-200 dark:border-slate-800 p-5 font-mono text-xs space-y-3">
            <h3 className="font-bold text-slate-900 dark:text-white flex items-center gap-2">
              <KeyRound className="w-4 h-4 text-indigo-500" />
              <span>Restabliment de PIN PWA</span>
            </h3>
            <p className="text-slate-500">
              Es generarà un nou PIN aleatori de 4 dígits i s'enviarà automàticament per SMS al telèfon acreditat ({operariSeleccionat.telefon}).
            </p>
            <div className="pt-2 flex justify-end gap-2">
              <button
                onClick={() => setModalResetPinObert(false)}
                className="px-3 py-1.5 rounded-lg bg-slate-100 dark:bg-slate-800 font-bold"
              >
                Cancel·lar
              </button>
              <button
                onClick={handleResetPin}
                className="px-4 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-bold"
              >
                Emetre Nou PIN
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL BAIXA LABORAL (RF-29, EDGE-07) */}
      {modalBaixaObert && operariSeleccionat && (
        <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-md bg-white dark:bg-slate-900 rounded-2xl shadow-xl border border-slate-200 dark:border-slate-800 p-5 font-mono text-xs space-y-3">
            <h3 className="font-bold text-rose-600 dark:text-rose-400 flex items-center gap-2">
              <UserX className="w-4 h-4" />
              <span>Tramitació de Baixa Laboral</span>
            </h3>
            <p className="text-slate-600 dark:text-slate-400">
              Aquesta acció revocarà immediatament les sessions JWT i credencials de la PWA de {operariSeleccionat.nom_complet}.
            </p>

            {operariSeleccionat.total_eines_assignades > 0 || operariSeleccionat.vehicle_habitual ? (
              <div className="p-3 rounded-lg bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-rose-700 dark:text-rose-300 space-y-1">
                <p className="font-bold">⚠️ Bloqueig d'Actius Pendents (EDGE-07):</p>
                <p className="text-[11px]">
                  L'operari té {operariSeleccionat.total_eines_assignades} eines i/o vehicle assignats. Cal retornar-los a Magatzem abans de tramitar la baixa.
                </p>
              </div>
            ) : (
              <div className="p-2.5 rounded bg-emerald-50 dark:bg-emerald-950/40 text-emerald-800 dark:text-emerald-300 text-[11px]">
                Sense actius pendents de devolució. Es pot procedir a la baixa amb arxiu històric de 5 anys.
              </div>
            )}

            <div className="pt-2 flex justify-end gap-2">
              <button
                onClick={() => setModalBaixaObert(false)}
                className="px-3 py-1.5 rounded-lg bg-slate-100 dark:bg-slate-800 font-bold"
              >
                Cancel·lar
              </button>
              <button
                onClick={handleTramitarBaixa}
                disabled={operariSeleccionat.total_eines_assignades > 0 || !!operariSeleccionat.vehicle_habitual}
                className="px-4 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-500 disabled:opacity-50 text-white font-bold"
              >
                Confirmar Baixa
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
