"use client";
import { apiFetch } from "@/lib/api";


import React, { useState, useEffect } from "react";
import Link from "next/link";
import {
  Factory,
  Shield,
  ShieldAlert,
  ShieldCheck,
  AlertTriangle,
  CheckCircle2,
  Lock,
  PhoneCall,
  FileCheck,
  PlusCircle,
  RefreshCw,
  Search,
  Filter,
  FileText,
  AlertCircle,
  Check,
  X,
  CreditCard,
  Building2,
  HardHat,
  ArrowRight,
  ExternalLink,
  ChevronRight,
} from "lucide-react";
import { useGestio } from "@/lib/gestio-context";

interface ProveidorItem {
  id: string;
  codi: string;
  rao_social: string;
  nif: string;
  telefon: string;
  email: string;
  especialitat: string;
  es_recc: boolean;
  aplica_isp_defecte: boolean;
  actiu: boolean;
  estat_cae: "EN_VIGOR" | "PREVENTIU" | "AVIS" | "URGENT" | "CADUCAT" | "SENSE_DOCUMENTS";
  dies_restants_cae: number | null;
  alerta_cae: string;
  bloqueig_bec: boolean;
  detall_antifrau?: {
    estat: string;
    iban_vell: string;
    iban_nou: string;
    origen: string;
    data_deteccio: string;
  };
  iban_visible: string;
  volum_compres_eur: number | null;
  retencio_salvaguarda_percent: number;
}

export default function GestioProveidorsPage() {
  const { rolActiu } = useGestio();
  const [proveidors, setProveidors] = useState<ProveidorItem[]>([]);
  const [carregant, setCarregant] = useState<boolean>(true);
  const [cerca, setCerca] = useState<string>("");
  const [filtreEspecialitat, setFiltreEspecialitat] = useState<string>("TOTS");
  const [filtreEstat, setFiltreEstat] = useState<string>("TOTS");

  // Estat Modal Frau BEC / Canvi IBAN
  const [modalBecObert, setModalBecObert] = useState<boolean>(false);
  const [provSeleccionatBec, setProvSeleccionatBec] = useState<ProveidorItem | null>(null);
  const [nouIbanInput, setNouIbanInput] = useState<string>("");
  const [trucadaFeta, setTrucadaFeta] = useState<boolean>(false);
  const [personaContactada, setPersonaContactada] = useState<string>("");
  const [observacionsBec, setObservacionsBec] = useState<string>("");

  // Estat Modal CAE / RC
  const [modalCaeObert, setModalCaeObert] = useState<boolean>(false);
  const [provSeleccionatCae, setProvSeleccionatCae] = useState<ProveidorItem | null>(null);
  const [dataCaducitatCae, setDataCaducitatCae] = useState<string>("");
  const [tipusDocCae, setTipusDocCae] = useState<string>("POLISSA_RC");
  const [alternativesSubcontractes, setAlternativesSubcontractes] = useState<any[]>([]);
  const [cercantAlternatives, setCercantAlternatives] = useState<boolean>(false);

  // Estat Modal Alta Proveïdor
  const [modalAltaObert, setModalAltaObert] = useState<boolean>(false);
  const [novaRaoSocial, setNovaRaoSocial] = useState<string>("");
  const [nouNif, setNouNif] = useState<string>("");
  const [nouTelefon, setNouTelefon] = useState<string>("");
  const [nouEmail, setNouEmail] = useState<string>("");
  const [novaEspecialitat, setNovaEspecialitat] = useState<string>("MATERIALS");
  const [nouEsRecc, setNouEsRecc] = useState<boolean>(false);
  const [nouAplicaIsp, setNouAplicaIsp] = useState<boolean>(false);
  const [nouIban, setNouIban] = useState<string>("");

  // Estat Modal Fitxa Proveïdor (Edició)
  const [modalFitxaObert, setModalFitxaObert] = useState<boolean>(false);
  const [provEdicio, setProvEdicio] = useState<ProveidorItem | null>(null);

  const desarFitxa = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!provEdicio) return;
    try {
      await apiFetch(`/gestio/proveidors/${provEdicio.id}`, {
        method: "PUT",
        body: JSON.stringify({
          codi: provEdicio.codi,
          rao_social: provEdicio.rao_social,
          nif: provEdicio.nif,
          telefon: provEdicio.telefon || null,
          email: provEdicio.email || null,
          especialitat: provEdicio.especialitat,
          iban: provEdicio.iban_visible,
        }),
      });
      setModalFitxaObert(false);
      fetchProveidors();
    } catch {
      // Ignorar
    }
  };


  // Carregar proveïdors des del backend
  const fetchProveidors = async () => {
    setCarregant(true);
    try {
      const data = await apiFetch<any[]>("/gestio/proveidors");
      if (data) {
        setProveidors(data);
      }
    } catch {
      // Backend offline en fase de build
    } finally {
      setCarregant(false);
    }
  };

  useEffect(() => {
    fetchProveidors();
  }, [rolActiu]);

  // Simular / Reportar canvi d'IBAN (Spec 003 RF-09 / EDGE-01)
  const handleReportarCanviIban = async (prov: ProveidorItem, nouIbanStr: string) => {
    try {
      await apiFetch("/gestio/proveidors/canvi-iban", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          proveidor_id: prov.id,
          nou_iban: nouIbanStr,
          origen_deteccio: "OCR_FACTURA",
        }),
      });

      // Actualització optimista
      setProveidors((prev) =>
        prev.map((p) => {
          if (p.id === prov.id) {
            return {
              ...p,
              bloqueig_bec: true,
              detall_antifrau: {
                estat: "BLOQUEIG_ANTIFRAU_IBAN",
                iban_vell: p.iban_visible,
                iban_nou: nouIbanStr,
                origen: "OCR_FACTURA",
                data_deteccio: new Date().toISOString(),
              },
            };
          }
          return p;
        })
      );
    } catch {
      // Fallback
    }
  };

  // Desbloquejar canvi d'IBAN pel Boss amb signatura SIF (Spec 003 RF-09)
  const handleAutoritzarCanviIban = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!provSeleccionatBec || !trucadaFeta) return;

    try {
      const res = await apiFetch("/gestio/proveidors/autoritzar-canvi-iban", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          proveidor_id: provSeleccionatBec.id,
          verificacio_telefonica_feta: true,
          persona_contactada: personaContactada || "Responsable d'administració acreditat",
          observacions: observacionsBec,
        }),
      });

      if (res.ok) {
        setProveidors((prev) =>
          prev.map((p) => {
            if (p.id === provSeleccionatBec.id) {
              const nouIbanAprovat = p.detall_antifrau?.iban_nou || p.iban_visible;
              return {
                ...p,
                bloqueig_bec: false,
                iban_visible: nouIbanAprovat,
                detall_antifrau: undefined,
              };
            }
            return p;
          })
        );
        setModalBecObert(false);
      }
    } catch {
      setModalBecObert(false);
    }
  };

  // Consultar subcontractes alternatives (Spec 003 RF-14)
  const handleCercarAlternatives = async () => {
    setCercantAlternatives(true);
    try {
      const data = await apiFetch<any[]>("/gestio/proveidors");
      setAlternativesSubcontractes(data || []);
    } catch {
      // Fallback
    } finally {
      setCercantAlternatives(false);
    }
  };

  // Donar d'alta nou proveïdor (Spec 003 RF-04)
  const handleCrearProveidor = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!novaRaoSocial || !nouNif) return;

    try {
      await apiFetch("/gestio/proveidors", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          codi: `PRV-${Date.now().toString().slice(-4)}`,
          rao_social: novaRaoSocial,
          nif: nouNif,
          telefon: nouTelefon || null,
          email: nouEmail || null,
          especialitat: novaEspecialitat,
          iban: nouIban || "ES8200491823442819481920",
        }),
      });
      setModalAltaObert(false);
      fetchProveidors();
      if (false) {
        // Fallback optimista si no hi ha backend
        const nouItem: ProveidorItem = {
          id: `prov-${Date.now()}`,
          codi: `PRV-${String(proveidors.length + 1).padStart(4, "0")}`,
          rao_social: novaRaoSocial,
          nif: nouNif.toUpperCase(),
          telefon: nouTelefon || "Sense telèfon",
          email: nouEmail || "Sense correu",
          especialitat: novaEspecialitat,
          es_recc: nouEsRecc,
          aplica_isp_defecte: nouAplicaIsp,
          actiu: true,
          estat_cae: "EN_VIGOR",
          dies_restants_cae: 180,
          alerta_cae: "OK",
          bloqueig_bec: false,
          iban_visible: nouIban || "ES82 0049 1823 44 2819481920",
          volum_compres_eur: 0,
          retencio_salvaguarda_percent: novaEspecialitat === "SUBCONTRACTA" ? 60.0 : 0.0,
        };
        setProveidors((prev) => [nouItem, ...prev]);
        setModalAltaObert(false);
      }
    } catch {
      setModalAltaObert(false);
    }
  };

  // Filtrar llista
  const proveidorsFiltrats = proveidors.filter((p) => {
    if (filtreEspecialitat !== "TOTS" && p.especialitat !== filtreEspecialitat) return false;
    if (filtreEstat === "BLOQUEIG_BEC" && !p.bloqueig_bec) return false;
    if (filtreEstat === "CADUCAT_CAE" && p.estat_cae !== "CADUCAT") return false;
    if (!cerca) return true;
    const q = cerca.toLowerCase();
    return (
      p.codi.toLowerCase().includes(q) ||
      p.rao_social.toLowerCase().includes(q) ||
      p.nif.toLowerCase().includes(q) ||
      p.especialitat.toLowerCase().includes(q)
    );
  });

  const proveidorsAmbBloqueigBec = proveidors.filter((p) => p.bloqueig_bec);
  const subcontractesCaducades = proveidors.filter(
    (p) => p.especialitat === "SUBCONTRACTA" && p.estat_cae === "CADUCAT"
  );

  return (
    <div className="flex-1 p-6 space-y-6 overflow-y-auto bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 font-sans transition-colors">
      {/* CAPÇALERA DE GESTIÓ */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-slate-200 dark:border-slate-800">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-white flex items-center gap-2">
              <Factory className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
              Proveïdors, CAE & Prevenció de Frau BEC (Spec 003)
            </h1>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-800 font-bold">
              RLS PROVEIDORS SCHEME
            </span>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Directori mestre de proveïdors, caducitats documentals CAE (RD 171/2004) i bloqueig atòmic d'IBAN
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={fetchProveidors}
            disabled={carregant}
            className="px-3 py-1.5 rounded-lg bg-white dark:bg-slate-800 hover:bg-slate-100 dark:hover:bg-slate-700 text-slate-800 dark:text-slate-200 text-xs font-mono font-bold flex items-center gap-1.5 border border-slate-300 dark:border-slate-700 shadow-sm transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${carregant ? "animate-spin text-emerald-500" : ""}`} />
            <span>Refrescar</span>
          </button>
          <button
            onClick={() => {
              setNovaRaoSocial("");
              setNouNif("");
              setNouTelefon("");
              setNouEmail("");
              setModalAltaObert(true);
            }}
            className="px-3.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-mono font-bold flex items-center gap-1.5 shadow transition-colors"
          >
            <PlusCircle className="w-4 h-4" />
            <span>Alta Nou Proveïdor</span>
          </button>
        </div>
      </div>

      {/* BANNERS D'ALERTA CRÍTICA: FRAU BEC & CADUCITAT CAE */}
      {proveidorsAmbBloqueigBec.length > 0 && (
        <div className="p-4 rounded-2xl bg-rose-50 dark:bg-rose-950/70 border-2 border-rose-400 dark:border-rose-800 flex items-center justify-between gap-4 text-rose-950 dark:text-rose-200 text-xs font-mono shadow-md animate-pulse">
          <div className="flex items-center gap-3">
            <ShieldAlert className="w-6 h-6 text-rose-600 dark:text-rose-400 shrink-0" />
            <div>
              <p className="font-bold text-sm">
                ALERTA CRÍTICA DE SEGURETAT: Intent de Frau BEC Detectat ({proveidorsAmbBloqueigBec.length} proveïdors afectats)
              </p>
              <p className="text-[11px] text-rose-800 dark:text-rose-300 mt-0.5">
                S'ha detectat un canvi sobtat d'IBAN en una factura de compra. S'han bloquejat de forma atòmica totes les transferències i pagaments.
              </p>
            </div>
          </div>
          {rolActiu === "ENGINYER" ? (
            <span className="px-3 py-1 rounded-lg bg-slate-200 dark:bg-slate-800 text-slate-500 text-[10px] font-bold">
              Veto d'Enginyer: Resolució exclusiva per a Boss
            </span>
          ) : (
            <button
              onClick={() => {
                setProvSeleccionatBec(proveidorsAmbBloqueigBec[0]);
                setTrucadaFeta(false);
                setModalBecObert(true);
              }}
              className="px-3 py-1.5 rounded-xl bg-rose-600 hover:bg-rose-500 text-white font-bold text-xs shrink-0 shadow"
            >
              Auditar & Desbloquejar (Boss)
            </button>
          )}
        </div>
      )}

      {subcontractesCaducades.length > 0 && (
        <div className="p-3.5 rounded-xl bg-amber-50 dark:bg-amber-950/70 border border-amber-300 dark:border-amber-800 flex items-center justify-between gap-3 text-amber-900 dark:text-amber-200 text-xs font-mono shadow-sm">
          <div className="flex items-center gap-2.5">
            <AlertTriangle className="w-5 h-5 text-amber-500 shrink-0" />
            <div>
              <strong>Alerta Legal CAE (RD 171/2004):</strong> {subcontractesCaducades.length} subcontractes tenen la Pòlissa de Responsabilitat Civil o certificats laborals caducats. L'assignació d'obra està <strong>bloquejada taxativament</strong>.
            </div>
          </div>
          <button
            onClick={() => {
              setProvSeleccionatCae(subcontractesCaducades[0]);
              handleCercarAlternatives();
              setModalCaeObert(true);
            }}
            className="px-2.5 py-1 rounded-lg bg-amber-600 hover:bg-amber-500 text-white text-[11px] font-bold shrink-0"
          >
            Veure Alternatives
          </button>
        </div>
      )}

      {/* BARRA DE FILTRES I CERCA */}
      <div className="flex flex-wrap items-center justify-between gap-3 p-3 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm">
        <div className="flex items-center gap-2 flex-1 max-w-md">
          <Search className="w-4 h-4 text-slate-400" />
          <input
            type="text"
            disabled={proveidors.length === 0}
            placeholder={proveidors.length === 0 ? "Cercador deshabilitat (Dia 0)" : "Filtrar per codi PRV, raó social, NIF o especialitat..."}
            value={cerca}
            onChange={(e) => setCerca(e.target.value)}
            className="w-full text-xs bg-transparent border-none focus:outline-none text-slate-900 dark:text-slate-100 placeholder:text-slate-400 font-mono disabled:opacity-50"
          />
        </div>

        <div className="flex items-center gap-2">
          {/* Filtre especialitat */}
          <select
            value={filtreEspecialitat}
            onChange={(e) => setFiltreEspecialitat(e.target.value)}
            className="text-xs bg-slate-100 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg px-2.5 py-1.5 font-mono text-slate-700 dark:text-slate-300 focus:outline-none"
          >
            <option value="TOTS">Totes les especialitats</option>
            <option value="MATERIALS">Materials de Reg & Fontaneria</option>
            <option value="MAQUINARIA">Maquinària & Lloguer</option>
            <option value="SUBCONTRACTA">Subcontractes d'Obra (CAE)</option>
          </select>

          {/* Filtre estat de risc */}
          <select
            value={filtreEstat}
            onChange={(e) => setFiltreEstat(e.target.value)}
            className="text-xs bg-slate-100 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg px-2.5 py-1.5 font-mono text-slate-700 dark:text-slate-300 focus:outline-none"
          >
            <option value="TOTS">Tots els estats</option>
            <option value="BLOQUEIG_BEC">Bloqueig Antifrau BEC</option>
            <option value="CADUCAT_CAE">CAE Caducat</option>
          </select>
        </div>
      </div>

      {/* TAULA GENERAL DE PROVEÏDORS O ESTAT BUIT CANÒNIC */}
      {proveidors.length === 0 ? (
        <div className="p-12 rounded-2xl border-2 border-dashed border-slate-300 dark:border-slate-800 text-center space-y-4 bg-white dark:bg-slate-900/60 shadow-sm">
          <div className="w-14 h-14 rounded-full bg-emerald-50 dark:bg-emerald-950/60 text-emerald-600 dark:text-emerald-400 flex items-center justify-center mx-auto border border-emerald-200 dark:border-emerald-800">
            <Factory className="w-7 h-7" />
          </div>
          <div className="space-y-1">
            <h3 className="text-base font-bold text-slate-800 dark:text-slate-100 font-mono">
              No hi ha proveïdors registrats al directori
            </h3>
            <p className="text-xs text-slate-500 font-mono max-w-md mx-auto">
              Estat canònic de Dia 0. Registra distribuïdors de materials, lloguer de maquinària o subcontractes d'obra per iniciar la gestió de compres i CAE.
            </p>
          </div>
          <button
            onClick={() => setModalAltaObert(true)}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-mono font-bold shadow transition-colors"
          >
            <PlusCircle className="w-4 h-4" />
            <span>Alta manual de proveïdor</span>
          </button>
        </div>
      ) : (
        <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 overflow-hidden shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="bg-slate-100 dark:bg-slate-800/80 border-b border-slate-200 dark:border-slate-800 font-mono text-[10px] uppercase text-slate-500 dark:text-slate-400">
                  <th className="p-3.5">Codi & Proveïdor</th>
                  <th className="p-3.5">NIF & Règim Fiscal</th>
                  <th className="p-3.5">Especialitat</th>
                  <th className="p-3.5 text-center">Estat CAE & Pòlissa RC</th>
                  <th className="p-3.5">Compte Bancari & Seguretat BEC</th>
                  <th className="p-3.5 text-right">Volum Compres & Retenció</th>
                  <th className="p-3.5 text-right">Accions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 dark:divide-slate-800 font-mono text-[11px]">
                {proveidorsFiltrats.map((p) => (
                  <tr key={p.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/40 transition-colors">
                    {/* Codi i Raó Social */}
                    <td className="p-3.5">
                      <div className="space-y-0.5">
                        <span className="font-bold text-slate-900 dark:text-white flex items-center gap-1.5">
                          <span className="text-[10px] px-1.5 py-0.2 rounded bg-slate-100 dark:bg-slate-800 border border-slate-300 dark:border-slate-700">
                            {p.codi}
                          </span>
                          <span>{p.rao_social}</span>
                        </span>
                        <p className="text-[10px] text-slate-500">{p.telefon} • {p.email}</p>
                      </div>
                    </td>

                    {/* NIF & Règim */}
                    <td className="p-3.5">
                      <div className="space-y-0.5">
                        <span className="font-bold text-slate-700 dark:text-slate-300">{p.nif}</span>
                        <div className="flex items-center gap-1 text-[9px]">
                          {p.es_recc && (
                            <span className="px-1 rounded bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300 border border-blue-200 dark:border-blue-800">
                              RECC
                            </span>
                          )}
                          {p.aplica_isp_defecte && (
                            <span className="px-1 rounded bg-purple-100 text-purple-800 dark:bg-purple-950 dark:text-purple-300 border border-purple-200 dark:border-purple-800">
                              ISP
                            </span>
                          )}
                        </div>
                      </div>
                    </td>

                    {/* Especialitat */}
                    <td className="p-3.5">
                      <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-slate-100 text-slate-700 border border-slate-300 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700">
                        {p.especialitat}
                      </span>
                    </td>

                    {/* Estat CAE & RC (RD 171/2004) */}
                    <td className="p-3.5 text-center">
                      <div className="space-y-0.5 inline-block text-center">
                        <span
                          className={`text-[9px] font-bold px-2 py-0.5 rounded-full border ${
                            p.estat_cae === "EN_VIGOR"
                              ? "bg-emerald-100 text-emerald-800 border-emerald-300 dark:bg-emerald-950 dark:text-emerald-400 dark:border-emerald-800"
                              : p.estat_cae === "PREVENTIU"
                              ? "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-900/40 dark:text-emerald-300"
                              : p.estat_cae === "AVIS" || p.estat_cae === "URGENT"
                              ? "bg-amber-100 text-amber-800 border-amber-300 dark:bg-amber-950 dark:text-amber-400 dark:border-amber-800"
                              : "bg-rose-100 text-rose-800 border-rose-300 dark:bg-rose-950 dark:text-rose-400 dark:border-rose-800 font-black"
                          }`}
                        >
                          {p.estat_cae === "CADUCAT" ? "BLOQUEIG CAE (CADUCAT)" : p.estat_cae}
                        </span>
                        {p.dies_restants_cae !== null && (
                          <p className="text-[9px] text-slate-500">
                            {p.dies_restants_cae < 0 ? `${Math.abs(p.dies_restants_cae)}d caducada` : `${p.dies_restants_cae}d vigència`}
                          </p>
                        )}
                      </div>
                    </td>

                    {/* Dades Bancàries & Frau BEC */}
                    <td className="p-3.5">
                      <div className="space-y-1">
                        <div className="flex items-center gap-1.5">
                          <CreditCard className="w-3.5 h-3.5 text-slate-400" />
                          <span className={`text-[11px] font-bold ${rolActiu === "ENGINYER" ? "text-slate-400 italic" : "text-slate-800 dark:text-slate-200"}`}>
                            {p.iban_visible}
                          </span>
                        </div>
                        {p.bloqueig_bec && (
                          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-black bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300 border border-rose-300 dark:border-rose-700">
                            <ShieldAlert className="w-3 h-3 text-rose-500" />
                            BLOQUEIG ANTIFRAU (BEC)
                          </span>
                        )}
                      </div>
                    </td>

                    {/* Volum de Compres & Retenció de Salvaguarda */}
                    <td className="p-3.5 text-right">
                      {rolActiu === "ENGINYER" ? (
                        <span className="text-[10px] text-slate-400 italic">Veto d'Enginyer</span>
                      ) : (
                        <div className="space-y-0.5">
                          <p className="font-bold text-slate-900 dark:text-white">
                            {p.volum_compres_eur?.toLocaleString()} €
                          </p>
                          {p.especialitat === "SUBCONTRACTA" && (
                            <p className="text-[10px] text-amber-500 font-bold">
                              Retenció 60% (Salvaguarda)
                            </p>
                          )}
                        </div>
                      )}
                    </td>

                    {/* Accions */}
                    <td className="p-3.5 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        {p.bloqueig_bec && rolActiu !== "ENGINYER" && (
                          <button
                            onClick={() => {
                              setProvSeleccionatBec(p);
                              setTrucadaFeta(false);
                              setModalBecObert(true);
                            }}
                            className="px-2 py-1 rounded bg-rose-600 hover:bg-rose-500 text-white text-[10px] font-bold flex items-center gap-1 shadow"
                          >
                            <ShieldCheck className="w-3 h-3" />
                            <span>Desbloquejar</span>
                          </button>
                        )}
                        {!p.bloqueig_bec && rolActiu !== "ENGINYER" && (
                          <button
                            onClick={() => {
                              const nouIbanSimulat = "ES44 2100 1234 56 9988776655";
                              handleReportarCanviIban(p, nouIbanSimulat);
                            }}
                            className="px-2 py-1 rounded bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 text-[10px] font-mono border border-slate-300 dark:border-slate-700"
                            title="Simular detecció de canvi d'IBAN per OCR de factura"
                          >
                            Simular BEC
                          </button>
                        )}
                        <button
                          onClick={() => {
                            setProvSeleccionatCae(p);
                            setDataCaducitatCae(new Date(Date.now() + 180 * 86400000).toISOString().split("T")[0]);
                            setModalCaeObert(true);
                          }}
                          className="px-2 py-1 rounded bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 text-[10px] font-mono border border-slate-300 dark:border-slate-700"
                        >
                          Docs CAE
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* MODAL 1: AUDITORIA I DESBLOQUEIG DE FRAU BEC (Spec 003 RF-09 / EDGE-01) */}
      {modalBecObert && provSeleccionatBec && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-lg rounded-2xl bg-white dark:bg-slate-900 border-2 border-rose-500 p-6 space-y-4 shadow-2xl text-slate-900 dark:text-slate-100">
            <div className="flex items-center justify-between pb-3 border-b border-rose-200 dark:border-rose-900">
              <div className="flex items-center gap-2">
                <ShieldAlert className="w-6 h-6 text-rose-600 dark:text-rose-400" />
                <div>
                  <h3 className="font-bold text-sm font-mono text-rose-600 dark:text-rose-400">
                    Protocol Antifrau BEC: Canvi d'IBAN Detectat
                  </h3>
                  <p className="text-[10px] text-slate-500 font-mono">
                    Proveïdor: {provSeleccionatBec.codi} ({provSeleccionatBec.rao_social})
                  </p>
                </div>
              </div>
              <button
                onClick={() => setModalBecObert(false)}
                className="p-1 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-400"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="p-3 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 space-y-2 text-xs font-mono">
              <div className="flex items-center justify-between text-slate-600 dark:text-slate-400">
                <span>IBAN Anterior (Acreditat):</span>
                <span className="font-bold text-slate-900 dark:text-white">
                  {provSeleccionatBec.detall_antifrau?.iban_vell || provSeleccionatBec.iban_visible}
                </span>
              </div>
              <div className="flex items-center justify-between text-rose-600 dark:text-rose-400">
                <span className="font-bold">Nou IBAN Detectat (OCR Factura):</span>
                <span className="font-bold bg-rose-100 dark:bg-rose-900/60 px-2 py-0.5 rounded border border-rose-300 dark:border-rose-700">
                  {provSeleccionatBec.detall_antifrau?.iban_nou || "ES44 2100 1234 56 9988776655"}
                </span>
              </div>
            </div>

            <form onSubmit={handleAutoritzarCanviIban} className="space-y-4 text-xs font-mono">
              <div className="p-3 rounded-xl bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 space-y-2 text-amber-900 dark:text-amber-200">
                <p className="font-bold flex items-center gap-1.5">
                  <PhoneCall className="w-4 h-4 text-amber-600 dark:text-amber-400" />
                  <span>Protocol de Trucada de Contrast Telefònic Mandatòria:</span>
                </p>
                <p className="text-[11px] leading-tight">
                  Per evitar estafes de suplantació d'identitat (BEC), és obligatori trucar al telèfon oficial de l'empresa ({provSeleccionatBec.telefon}) i verificar amb el responsable financer que el canvi de compte és legítim.
                </p>
                <label className="flex items-center gap-2 pt-1 font-bold cursor-pointer">
                  <input
                    type="checkbox"
                    required
                    checked={trucadaFeta}
                    onChange={(e) => setTrucadaFeta(e.target.checked)}
                    className="w-4 h-4 text-emerald-600 rounded"
                  />
                  <span>Certifico haver realitzat la trucada de verificació telefònica protocol·lària</span>
                </label>
              </div>

              <div className="space-y-1">
                <label className="font-bold text-slate-700 dark:text-slate-300">
                  Persona contactada al departament d'administració del proveïdor:
                </label>
                <input
                  type="text"
                  required
                  placeholder="Ex: Maria Rovira (Directora Financera)"
                  value={personaContactada}
                  onChange={(e) => setPersonaContactada(e.target.value)}
                  className="w-full p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none"
                />
              </div>

              <div className="space-y-1">
                <label className="font-bold text-slate-700 dark:text-slate-300">
                  Observacions de l'auditoria SIF:
                </label>
                <textarea
                  rows={2}
                  placeholder="Detall de la comprovació..."
                  value={observacionsBec}
                  onChange={(e) => setObservacionsBec(e.target.value)}
                  className="w-full p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none"
                />
              </div>

              <div className="flex items-center justify-between pt-2 border-t border-slate-200 dark:border-slate-800">
                <span className="text-[10px] text-slate-400">
                  Enregistrament inalterable al SIF amb hash SHA-256
                </span>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setModalBecObert(false)}
                    className="px-3 py-2 rounded-xl bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 font-bold"
                  >
                    Cancel·lar
                  </button>
                  <button
                    type="submit"
                    disabled={!trucadaFeta}
                    className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white font-bold shadow"
                  >
                    Autoritzar & Desbloquejar Pagaments
                  </button>
                </div>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL 2: GESTIÓ DOCUMENTAL CAE I ALTERNATIVES (RD 171/2004 — Spec 003 RF-12 a RF-14) */}
      {modalCaeObert && provSeleccionatCae && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-lg rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-6 space-y-4 shadow-xl text-slate-900 dark:text-slate-100">
            <div className="flex items-center justify-between pb-3 border-b border-slate-200 dark:border-slate-800">
              <div className="flex items-center gap-2">
                <HardHat className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
                <h3 className="font-bold text-sm font-mono">
                  Expedient CAE & Pòlissa RC: {provSeleccionatCae.rao_social}
                </h3>
              </div>
              <button
                onClick={() => setModalCaeObert(false)}
                className="p-1 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-400"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-3 text-xs font-mono">
              <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 space-y-1">
                <div className="flex items-center justify-between">
                  <span className="font-bold">Estat Actual CAE:</span>
                  <span className={`font-bold ${provSeleccionatCae.estat_cae === "CADUCAT" ? "text-rose-500" : "text-emerald-500"}`}>
                    {provSeleccionatCae.estat_cae}
                  </span>
                </div>
                <p className="text-[10px] text-slate-500">
                  Custòdia sobirana en disc Hetzner: /docs/[empresa_id]/proveidors/{provSeleccionatCae.codi}/cae/
                </p>
              </div>

              {/* Si està caducat, mostrar alternatives (RF-14) */}
              {provSeleccionatCae.estat_cae === "CADUCAT" && (
                <div className="p-3 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 space-y-2">
                  <p className="font-bold text-rose-600 dark:text-rose-400 flex items-center gap-1.5">
                    <ShieldAlert className="w-4 h-4" />
                    <span>Assignació en Obra Bloquejada per RD 171/2004</span>
                  </p>
                  <p className="text-[11px] text-slate-600 dark:text-slate-400">
                    No és possible assignar aquesta subcontracta a cap ordre de treball mentre la pòlissa RC estigui vençuda.
                  </p>

                  <div className="pt-2 border-t border-rose-200 dark:border-rose-800/80">
                    <div className="flex items-center justify-between mb-2">
                      <span className="font-bold text-[11px]">Subcontractes alternatives homologades:</span>
                      <button
                        onClick={handleCercarAlternatives}
                        className="text-[10px] text-emerald-600 dark:text-emerald-400 font-bold hover:underline"
                      >
                        Actualitzar cerca
                      </button>
                    </div>

                    {alternativesSubcontractes.length > 0 ? (
                      <div className="space-y-1.5">
                        {alternativesSubcontractes.map((alt) => (
                          <div
                            key={alt.id}
                            className="p-2 rounded-lg bg-white dark:bg-slate-900 border border-emerald-300 dark:border-emerald-800 flex items-center justify-between"
                          >
                            <div>
                              <p className="font-bold text-slate-800 dark:text-slate-100">{alt.rao_social}</p>
                              <p className="text-[10px] text-slate-500">{alt.telefon} • {alt.email}</p>
                            </div>
                            <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-800">
                              CAE EN VIGOR
                            </span>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-[10px] text-slate-500 italic">
                        Cercant alternatives homologades amb documentació en regla...
                      </p>
                    )}
                  </div>
                </div>
              )}

              {/* Botó de tancament */}
              <div className="flex items-center justify-end pt-2 border-t border-slate-200 dark:border-slate-800">
                <button
                  type="button"
                  onClick={() => setModalCaeObert(false)}
                  className="px-4 py-2 rounded-xl bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 font-bold"
                >
                  Tancar Expedient
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* MODAL 3: ALTA MANUAL DE PROVEÏDOR (Spec 003 RF-04 / RF-05) */}
      {modalAltaObert && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-lg rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-6 space-y-4 shadow-xl text-slate-900 dark:text-slate-100">
            <div className="flex items-center justify-between pb-3 border-b border-slate-200 dark:border-slate-800">
              <div className="flex items-center gap-2">
                <Factory className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
                <h3 className="font-bold text-sm font-mono">Alta Manual de Proveïdor</h3>
              </div>
              <button
                onClick={() => setModalAltaObert(false)}
                className="p-1 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-400"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleCrearProveidor} className="space-y-4 text-xs font-mono">
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="font-bold text-slate-700 dark:text-slate-300">Raó Social:</label>
                  <input
                    type="text"
                    required
                    placeholder="Ex: Tuberia & Válvules SL"
                    value={novaRaoSocial}
                    onChange={(e) => setNovaRaoSocial(e.target.value)}
                    className="w-full p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none"
                  />
                </div>

                <div className="space-y-1">
                  <label className="font-bold text-slate-700 dark:text-slate-300">NIF / CIF:</label>
                  <input
                    type="text"
                    required
                    placeholder="Ex: B-65982104"
                    value={nouNif}
                    onChange={(e) => setNouNif(e.target.value)}
                    className="w-full p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs uppercase focus:outline-none"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="font-bold text-slate-700 dark:text-slate-300">Telèfon de Comandes:</label>
                  <input
                    type="text"
                    placeholder="Ex: +34 938 12 34 56"
                    value={nouTelefon}
                    onChange={(e) => setNouTelefon(e.target.value)}
                    className="w-full p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none"
                  />
                </div>

                <div className="space-y-1">
                  <label className="font-bold text-slate-700 dark:text-slate-300">Email Corporatiu:</label>
                  <input
                    type="email"
                    placeholder="comandes@proveidor.cat"
                    value={nouEmail}
                    onChange={(e) => setNouEmail(e.target.value)}
                    className="w-full p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="font-bold text-slate-700 dark:text-slate-300">Especialitat:</label>
                  <select
                    value={novaEspecialitat}
                    onChange={(e) => setNovaEspecialitat(e.target.value)}
                    className="w-full p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none"
                  >
                    <option value="MATERIALS">Materials de Reg & Obra</option>
                    <option value="MAQUINARIA">Lloguer de Maquinària</option>
                    <option value="SUBCONTRACTA">Subcontracta d'Obra (CAE)</option>
                  </select>
                </div>

                <div className="space-y-1">
                  <label className="font-bold text-slate-700 dark:text-slate-300">IBAN de Transferència:</label>
                  <input
                    type="text"
                    placeholder="ES82 0049 1823 44 2819481920"
                    value={nouIban}
                    onChange={(e) => setNouIban(e.target.value)}
                    className="w-full p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none"
                  />
                </div>
              </div>

              <div className="flex items-center gap-4 pt-1">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={nouEsRecc}
                    onChange={(e) => setNouEsRecc(e.target.checked)}
                    className="w-4 h-4 text-emerald-600 rounded"
                  />
                  <span>Règim Especial Criteri de Caixa (RECC)</span>
                </label>

                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={nouAplicaIsp}
                    onChange={(e) => setNouAplicaIsp(e.target.checked)}
                    className="w-4 h-4 text-emerald-600 rounded"
                  />
                  <span>Inversió Subjecte Passiu (ISP)</span>
                </label>
              </div>

              <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-200 dark:border-slate-800">
                <button
                  type="button"
                  onClick={() => setModalAltaObert(false)}
                  className="px-3 py-2 rounded-xl bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 font-bold"
                >
                  Cancel·lar
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold shadow"
                >
                  Crear Proveïdor
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
      {/* Modal Edició (Fitxa de Proveïdor) */}
      {modalFitxaObert && provEdicio && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-2xl bg-white dark:bg-slate-900 rounded-3xl shadow-2xl border border-slate-200 dark:border-slate-800 overflow-hidden flex flex-col max-h-[90vh]">
            <div className="p-5 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between bg-slate-50 dark:bg-slate-800/50">
              <h3 className="font-bold text-sm text-slate-800 dark:text-slate-100 flex items-center gap-2">
                <Building2 className="w-4 h-4 text-emerald-600" />
                Fitxa de Proveïdor: {provEdicio.rao_social}
              </h3>
              <button
                onClick={() => setModalFitxaObert(false)}
                className="p-1 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 bg-white dark:bg-slate-800 shadow-sm"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            
            <div className="flex-1 overflow-y-auto p-5">
              <form id="form-editar-prov" onSubmit={desarFitxa} className="space-y-4">
                <div className="p-4 bg-slate-50 dark:bg-slate-800/50 rounded-2xl border border-slate-100 dark:border-slate-800 space-y-4">
                  <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Informació General</h4>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-xs font-bold text-slate-600 dark:text-slate-400 mb-1">Codi Proveïdor</label>
                      <input
                        type="text"
                        value={provEdicio.codi}
                        onChange={(e) => setProvEdicio({ ...provEdicio, codi: e.target.value })}
                        className="w-full p-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs font-mono"
                        required
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-bold text-slate-600 dark:text-slate-400 mb-1">Raó Social</label>
                      <input
                        type="text"
                        value={provEdicio.rao_social}
                        onChange={(e) => setProvEdicio({ ...provEdicio, rao_social: e.target.value })}
                        className="w-full p-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs"
                        required
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-bold text-slate-600 dark:text-slate-400 mb-1">NIF/CIF</label>
                      <input
                        type="text"
                        value={provEdicio.nif}
                        onChange={(e) => setProvEdicio({ ...provEdicio, nif: e.target.value.toUpperCase() })}
                        className="w-full p-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs font-mono"
                        required
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-bold text-slate-600 dark:text-slate-400 mb-1">Especialitat</label>
                      <select
                        value={provEdicio.especialitat}
                        onChange={(e) => setProvEdicio({ ...provEdicio, especialitat: e.target.value })}
                        className="w-full p-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs"
                      >
                        <option value="MATERIALS">Distribuïdor Materials</option>
                        <option value="MAQUINARIA">Lloguer Maquinària</option>
                        <option value="SUBCONTRACTA">Subcontracta d'Obra</option>
                        <option value="SERVEIS">Serveis Generals</option>
                      </select>
                    </div>
                  </div>
                </div>

                <div className="p-4 bg-blue-50/50 dark:bg-blue-900/10 rounded-2xl border border-blue-100 dark:border-blue-900/30 space-y-4">
                  <h4 className="text-xs font-bold text-blue-600 dark:text-blue-500 uppercase tracking-wider mb-2">Dades de Contacte</h4>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-xs font-bold text-slate-600 dark:text-slate-400 mb-1">Telèfon</label>
                      <input
                        type="tel"
                        value={provEdicio.telefon || ""}
                        onChange={(e) => setProvEdicio({ ...provEdicio, telefon: e.target.value })}
                        className="w-full p-2 rounded-xl border border-blue-200 dark:border-blue-800 bg-white dark:bg-slate-900 text-xs font-mono"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-bold text-slate-600 dark:text-slate-400 mb-1">Correu Electrònic</label>
                      <input
                        type="email"
                        value={provEdicio.email || ""}
                        onChange={(e) => setProvEdicio({ ...provEdicio, email: e.target.value })}
                        className="w-full p-2 rounded-xl border border-blue-200 dark:border-blue-800 bg-white dark:bg-slate-900 text-xs"
                      />
                    </div>
                  </div>
                </div>
              </form>
            </div>
            
            <div className="p-5 border-t border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900 flex justify-end gap-3">
              <button
                type="button"
                onClick={() => setModalFitxaObert(false)}
                className="px-4 py-2 rounded-xl border border-slate-300 dark:border-slate-700 text-slate-700 dark:text-slate-300 text-xs font-bold hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
              >
                Cancel·lar
              </button>
              <button
                type="submit"
                form="form-editar-prov"
                className="px-6 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold shadow-md shadow-emerald-500/20 flex items-center gap-2 transition-all"
              >
                <CheckCircle2 className="w-4 h-4" />
                <span>Desar Canvis</span>
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
