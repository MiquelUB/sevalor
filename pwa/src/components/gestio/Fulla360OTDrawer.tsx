"use client";

import React, { useCallback, useEffect, useState } from "react";
import {
  X,
  FileText,
  MapPin,
  Users,
  Calendar,
  Package,
  Wrench,
  Clock,
  Layers,
  Edit,
  Truck,
  ExternalLink,
  CheckCircle2,
  AlertTriangle,
  AlertCircle,
  Phone,
  ShieldCheck,
  Receipt,
  Loader2,
  Camera,
  PenTool,
  CheckSquare,
  Square,
  ZoomIn,
} from "lucide-react";
import Link from "next/link";
import { Feina, DisclaimerOT } from "@/components/gestio/Map";
import { FacturaComercialModal } from "@/components/gestio/FacturaComercialModal";
import { useGestio } from "@/lib/gestio-context";
import { apiFetch, extractTenantId, getApiBaseUrl, getAuthToken } from "@/lib/api";

interface MaterialConciliacio {
  linia_id: string;
  picking_id: string;
  article_id: string;
  article_nom: string;
  referencia_inventari?: string | null;
  unitat_mesura: string;
  origen_estoc: "NAU" | "FURGONETA" | string;
  magatzem_nom?: string | null;
  quantitat_prevista: number;
  quantitat_carregada_pick_in: number;
  quantitat_retornada_pick_out: number;
  quantitat_mermada: number;
  consum_real: number;
  preu_venda_unitari: number;
  subtotal_pvp: number;
}

interface IncidenciaConciliacio {
  id: string;
  ambit: string;
  tipus?: string | null;
  gravetat?: string | null;
  estat: string;
  text_observacions?: string | null;
  created_at?: string | null;
}

interface TiquetConciliacio {
  id: string;
  categoria: string;
  data_tiquet?: string | null;
  rao_social?: string | null;
  import_total: number;
  estat_aprovacio: string;
}

interface CapaGisConciliacio {
  id: string;
  nom: string;
  disciplina?: string | null;
  origen?: string | null;
  created_at?: string | null;
}

interface ConciliacioCompleta {
  ordre_treball_id: string;
  codi: string;
  titol: string;
  estat: string;
  versio: number;
  client_id: string;
  client_nom?: string | null;
  vehicle?: { id: string; matricula: string; marca_model: string } | null;
  planol?: { id: string; titol: string; codi_referencia?: string | null } | null;
  disclaimer: DisclaimerOT;
  validacio: {
    validada: boolean;
    validada_per_id?: string | null;
    validada_per_nom?: string | null;
    data_validacio?: string | null;
    notes_validacio_tecnica?: string | null;
    checklist_conciliacio: Record<string, boolean>;
  };
  temps_i_gps: {
    te_tram_obert: boolean;
    temps_acumulat_segons: number;
    hores_previstes: number;
    hores_reals: number;
    desviacio_hores: number;
    desviacio_geovalla: boolean;
    justificacio_geovalla?: string | null;
    te_foto_geovalla: boolean;
    trams_count: number;
  };
  fotos_qa: {
    inicial: boolean;
    intermedia: boolean;
    final: boolean;
    total_pujades: number;
    protocol_complet: boolean;
  };
  signatura: {
    present: boolean;
    path?: string | null;
    nom_receptor?: string | null;
    dni_receptor?: string | null;
    observacions_tancament?: string | null;
    data_signatura?: string | null;
  };
  materials: {
    estat_picking?: string | null;
    total_linies: number;
    alerta_consum_excessiu: boolean;
    detall_merma?: string | null;
    linies: MaterialConciliacio[];
  };
  eines?: Array<{
    id: string;
    nom: string;
    model?: string | null;
    numero_serie: string;
    estat: string;
  }>;
  incidencies: {
    total: number;
    obertes: number;
    items: IncidenciaConciliacio[];
  };
  tiquets: {
    total: number;
    import_total: number;
    items: TiquetConciliacio[];
  };
  capes_gis: CapaGisConciliacio[];
  pressupost?: {
    id: string;
    numero: string;
    estat: string;
    total: number;
  } | null;
  factura?: {
    id: string;
    serie: string;
    numero_factura: number;
    estat_document: string;
    estat_cobrament?: string;
    data_emissio?: string | null;
    base_imposable: number;
    quota_iva: number;
    liquid_exigible: number;
  } | null;
  resum_comercial: {
    import_pressupostat: number;
    hores_previstes: number;
    hores_reals: number;
    preu_venda_hora_aplicat: number;
    valor_ma_obra_pvp: number;
    valor_materials_pvp: number;
    total_tiquets_camp: number;
    total_valorat_pvp: number;
  };
  preparada_per_prefacturar: boolean;
  motius_bloqueig_prefacturacio: string[];
}

interface AjustPickingDraft {
  carregat: string;
  retornat: string;
  merma: string;
}

const CHECKLIST_ITEMS = [
  { key: "hores_revisades", label: "Hores reals i trams GPS verificats" },
  { key: "materials_conciliats", label: "Materials (Nau i Furgoneta) i mermes conciliats" },
  { key: "evidencies_comprovades", label: "Fotos QA i signatura / receptor comprovats" },
  { key: "incidencies_tiquets", label: "Incidències, tiquets i plànols As-Built revisats" },
] as const;

interface Fulla360OTDrawerProps {
  feina: Feina | null;
  isOpen: boolean;
  onClose: () => void;
  onEdit?: (feinaId: string) => void;
  onFocusMapa?: (feinaId: string) => void;
  onPrefacturaCreated?: () => void;
}

function disclaimerBannerStyle(codi: string): string {
  switch (codi) {
    case "NO_CONCLOSA":
      return "bg-surface-container-high dark:bg-slate-800 border-outline-variant/50 text-on-surface dark:text-slate-200";
    case "CONCLOSA_PENDENT_VALIDACIO":
      return "bg-amber-50 dark:bg-amber-950/40 border-amber-300 dark:border-amber-700 text-amber-950 dark:text-amber-200";
    case "VALIDADA_PENDENT_FACTURAR":
      return "bg-primary/10 dark:bg-primary/20 border-primary/40 text-primary dark:text-slate-100";
    case "PREFACTURADA":
      return "bg-amber-100/70 dark:bg-amber-950/50 border-amber-400 dark:border-amber-700 text-amber-950 dark:text-amber-200";
    case "FACTURADA":
      return "bg-emerald-50 dark:bg-emerald-950/40 border-emerald-300 dark:border-emerald-700 text-emerald-900 dark:text-emerald-200";
    default:
      return "bg-surface-container-low border-outline-variant/40 text-on-surface";
  }
}

export function Fulla360OTDrawer({
  feina,
  isOpen,
  onClose,
  onEdit,
  onFocusMapa,
  onPrefacturaCreated,
}: Fulla360OTDrawerProps) {
  const { rolActiu } = useGestio();
  const potAccedirComptabilitat = (rolActiu || "").toUpperCase() !== "ENGINYER";

  const [conc, setConc] = useState<ConciliacioCompleta | null>(null);
  const [loadingConc, setLoadingConc] = useState(false);
  const [errorConc, setErrorConc] = useState<string | null>(null);

  // Evidències carregades amb Blob URL autenticat
  const [evidenciesUrls, setEvidenciesUrls] = useState<Record<string, string>>({});
  const [lightboxUrl, setLightboxUrl] = useState<{ url: string; titol: string } | null>(null);

  // Formulari de validació tècnica
  const [checklist, setChecklist] = useState<Record<string, boolean>>({});
  const [horesEdit, setHoresEdit] = useState<string>("");
  const [notesValidacio, setNotesValidacio] = useState<string>("");
  const [ajustosPicking, setAjustosPicking] = useState<Record<string, AjustPickingDraft>>({});
  const [validant, setValidant] = useState(false);
  const [enviantPrefactura, setEnviantPrefactura] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  // Modal de consulta comercial de factura / pre-factura (tots 3 rols)
  const [facturaModalId, setFacturaModalId] = useState<string | null>(null);

  const carregarConciliacio = useCallback(async (otId: string) => {
    setLoadingConc(true);
    setErrorConc(null);
    try {
      const data = await apiFetch<ConciliacioCompleta>(`/gestio/feines/${otId}/conciliacio`);
      setConc(data);
      setChecklist(data.validacio?.checklist_conciliacio || {});
      setHoresEdit(String(data.temps_i_gps?.hores_reals ?? 0));
      setNotesValidacio(data.validacio?.notes_validacio_tecnica || "");

      const drafts: Record<string, AjustPickingDraft> = {};
      for (const lin of data.materials?.linies || []) {
        drafts[lin.linia_id] = {
          carregat: String(lin.quantitat_carregada_pick_in ?? 0),
          retornat: String(lin.quantitat_retornada_pick_out ?? 0),
          merma: String(lin.quantitat_mermada ?? 0),
        };
      }
      setAjustosPicking(drafts);
    } catch (err: unknown) {
      setErrorConc(err instanceof Error ? err.message : "Error carregant la conciliació de l'OT.");
      setConc(null);
    } finally {
      setLoadingConc(false);
    }
  }, []);

  useEffect(() => {
    if (!isOpen || !feina?.id) return;
    setActionError(null);
    setActionSuccess(null);
    carregarConciliacio(feina.id);
  }, [isOpen, feina?.id, carregarConciliacio]);

  // Carregar imatges d'evidències autenticades via fetch -> Blob URL
  useEffect(() => {
    if (!isOpen || !conc) return;
    let cancelled = false;
    const createdUrls: string[] = [];

    const toFetch: string[] = [];
    if (conc.fotos_qa?.inicial) toFetch.push("foto_inicial");
    if (conc.fotos_qa?.intermedia) toFetch.push("foto_intermedia");
    if (conc.fotos_qa?.final) toFetch.push("foto_final");
    if (conc.signatura?.present) toFetch.push("signatura");
    if (conc.temps_i_gps?.te_foto_geovalla) toFetch.push("foto_geovalla");

    const fetchAll = async () => {
      const token = getAuthToken();
      const tenantId = extractTenantId();
      const headers: Record<string, string> = {};
      if (token) headers["Authorization"] = `Bearer ${token}`;
      if (tenantId) {
        headers["X-Empresa-ID"] = tenantId;
        headers["X-Tenant-ID"] = tenantId;
      }

      const nextMap: Record<string, string> = {};
      await Promise.all(
        toFetch.map(async (tipus) => {
          try {
            const res = await fetch(
              `${getApiBaseUrl()}/gestio/feines/${conc.ordre_treball_id}/evidencies/${tipus}`,
              { headers, credentials: "include" }
            );
            if (!res.ok) return;
            const blob = await res.blob();
            const objUrl = URL.createObjectURL(blob);
            createdUrls.push(objUrl);
            nextMap[tipus] = objUrl;
          } catch {
            // Evidència no disponible
          }
        })
      );
      if (!cancelled) {
        setEvidenciesUrls(nextMap);
      }
    };

    fetchAll();
    return () => {
      cancelled = true;
      createdUrls.forEach((u) => URL.revokeObjectURL(u));
      setEvidenciesUrls({});
    };
  }, [
    isOpen,
    conc?.ordre_treball_id,
    conc?.fotos_qa?.inicial,
    conc?.fotos_qa?.intermedia,
    conc?.fotos_qa?.final,
    conc?.signatura?.present,
    conc?.temps_i_gps?.te_foto_geovalla,
  ]);

  if (!isOpen || !feina) return null;

  const disclaimer: DisclaimerOT = conc?.disclaimer ||
    feina.disclaimer || {
      codi: "NO_CONCLOSA",
      titol: "La feina no ha finalitzat",
      descripcio: "Pendent de conclusió a camp.",
      severitat: "neutral",
      pot_validar: false,
      pot_prefacturar: false,
    };

  const materialsConc = conc?.materials?.linies || [];
  const eines = (conc?.eines && conc.eines.length > 0 ? conc.eines : feina.eines) || [];
  const trams = feina.trams_temps || [];
  const horesPrev = Number(conc?.temps_i_gps?.hores_previstes ?? feina.hores_previstes ?? 0);
  const horesFact = Number(conc?.temps_i_gps?.hores_reals ?? feina.hores_imputades_facturables ?? 0);
  const preuH = Number(conc?.resum_comercial?.preu_venda_hora_aplicat ?? feina.preu_venda_hora_aplicat ?? 0);

  const handleValidarConciliacio = async () => {
    setValidant(true);
    setActionError(null);
    setActionSuccess(null);
    try {
      const horesNum = parseFloat(horesEdit);
      const ajustosPayload = materialsConc
        .map((lin) => {
          const d = ajustosPicking[lin.linia_id];
          if (!d) return null;
          const qIn = parseFloat(d.carregat);
          const qOut = parseFloat(d.retornat);
          const qMerma = parseFloat(d.merma);
          const canviat =
            (!Number.isNaN(qIn) && qIn !== lin.quantitat_carregada_pick_in) ||
            (!Number.isNaN(qOut) && qOut !== lin.quantitat_retornada_pick_out) ||
            (!Number.isNaN(qMerma) && qMerma !== lin.quantitat_mermada);
          if (!canviat) return null;
          return {
            linia_id: lin.linia_id,
            quantitat_carregada_pick_in: Number.isNaN(qIn) ? undefined : qIn,
            quantitat_retornada_pick_out: Number.isNaN(qOut) ? undefined : qOut,
            quantitat_mermada: Number.isNaN(qMerma) ? undefined : qMerma,
          };
        })
        .filter(Boolean);

      const updated = await apiFetch<ConciliacioCompleta>(
        `/gestio/feines/${feina.id}/validar-conciliacio`,
        {
          method: "PUT",
          body: JSON.stringify({
            hores_imputades_facturables: Number.isNaN(horesNum) ? undefined : horesNum,
            ajustos_picking: ajustosPayload.length > 0 ? ajustosPayload : undefined,
            checklist_conciliacio: checklist,
            notes_validacio_tecnica: notesValidacio.trim() || undefined,
          }),
        }
      );
      setConc(updated);
      setActionSuccess(
        "Conciliació tècnica validada correctament. La tasca ja està llesta per passar a pre-facturació."
      );
      onPrefacturaCreated?.();
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : "Error validant la conciliació.");
    } finally {
      setValidant(false);
    }
  };

  const handlePassarAPrefacturacio = async () => {
    setEnviantPrefactura(true);
    setActionError(null);
    setActionSuccess(null);
    try {
      const pref = await apiFetch<{
        id: string;
        serie: string;
        numero_factura: number;
        liquid_exigible: number;
      }>(`/gestio/feines/${feina.id}/passar-a-prefacturacio`, {
        method: "POST",
        body: JSON.stringify({ incloure_tiquets_camp: true }),
      });
      await carregarConciliacio(feina.id);
      setActionSuccess(
        `Pre-factura ${pref.serie}-${String(pref.numero_factura).padStart(4, "0")} creada (${Number(
          pref.liquid_exigible
        ).toFixed(2)} €).`
      );
      onPrefacturaCreated?.();
    } catch (err: unknown) {
      setActionError(
        err instanceof Error ? err.message : "Error passant l'ordre de treball a pre-facturació."
      );
    } finally {
      setEnviantPrefactura(false);
    }
  };

  const fmtHMS = (seg: number) => {
    const s = Math.max(0, Math.floor(seg));
    const hh = Math.floor(s / 3600);
    const mm = Math.floor((s % 3600) / 60);
    const ss = s % 60;
    return `${String(hh).padStart(2, "0")}:${String(mm).padStart(2, "0")}:${String(ss).padStart(2, "0")}`;
  };

  const facturaDoc = conc?.factura;

  return (
    <>
      <div className="fixed inset-0 z-50 overflow-hidden flex justify-end">
        {/* Backdrop */}
        <div
          className="fixed inset-0 bg-slate-950/50 backdrop-blur-xs transition-opacity animate-in fade-in duration-150"
          onClick={onClose}
        />

        {/* Slide-over Drawer Panel */}
        <div className="relative w-full max-w-3xl bg-surface-container-lowest dark:bg-slate-900 h-full shadow-2xl flex flex-col border-l border-outline-variant/30 z-10 transition-transform duration-300 animate-in slide-in-from-right">
          {/* Header */}
          <div className="px-5 py-4 border-b border-outline-variant/20 flex items-center justify-between bg-surface-container-low/60 dark:bg-slate-800/50">
            <div className="flex items-center gap-3 min-w-0">
              <div className="w-10 h-10 rounded-xl bg-primary/10 text-primary flex items-center justify-center shrink-0">
                <FileText className="w-5 h-5" />
              </div>
              <div className="min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-mono text-xs font-bold px-2 py-0.5 rounded-full bg-primary text-white">
                    {feina.codi}
                  </span>
                  <span className="text-[10px] font-label-caps px-2 py-0.5 rounded-full font-bold uppercase bg-surface-container-high text-on-surface">
                    {conc?.estat || feina.estat}
                  </span>
                </div>
                <h2 className="font-section-title text-base text-on-surface dark:text-white mt-1 truncate">
                  Fulla 360° — {feina.titol}
                </h2>
              </div>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="p-2 text-on-surface-variant hover:text-on-surface hover:bg-surface-container rounded-xl transition-colors cursor-pointer shrink-0"
              title="Tancar Fulla 360°"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* HEADER DISCLAIMER PERSISTENT (Requisit Usuari) */}
          <div
            data-testid="fulla360-header-disclaimer"
            className={`px-5 py-3 border-b flex items-center justify-between gap-3 ${disclaimerBannerStyle(
              disclaimer.codi
            )}`}
          >
            <div className="flex items-start gap-2.5 min-w-0">
              {disclaimer.codi === "FACTURADA" || disclaimer.codi === "VALIDADA_PENDENT_FACTURAR" ? (
                <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" />
              ) : disclaimer.codi === "CONCLOSA_PENDENT_VALIDACIO" ||
                disclaimer.codi === "PREFACTURADA" ? (
                <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
              ) : (
                <Clock className="w-4 h-4 shrink-0 mt-0.5" />
              )}
              <div className="min-w-0">
                <p className="text-xs font-extrabold uppercase tracking-wider leading-tight">
                  {disclaimer.titol}
                </p>
                <p className="text-[11px] opacity-90 mt-0.5 leading-snug">{disclaimer.descripcio}</p>
              </div>
            </div>
            {conc?.validacio?.validada && conc.validacio.validada_per_nom && (
              <span className="text-[10px] font-mono px-2 py-1 rounded-lg bg-white/60 dark:bg-slate-900/60 shrink-0 hidden sm:inline-block">
                Validada per {conc.validacio.validada_per_nom}
              </span>
            )}
          </div>

          {/* Content Body (Scrollable) */}
          <div className="flex-1 overflow-y-auto p-5 space-y-5">
            {loadingConc && !conc && (
              <div className="p-6 rounded-xl bg-surface-container-low/60 border border-outline-variant/30 text-center text-xs font-mono text-on-surface-variant flex items-center justify-center gap-2">
                <Loader2 className="w-4 h-4 animate-spin text-primary" />
                <span>Carregant dossier de conciliació PWA i evidències...</span>
              </div>
            )}

            {errorConc && (
              <div className="p-3 rounded-xl bg-error-container/25 border border-error text-error text-xs font-semibold flex items-center gap-2">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>{errorConc}</span>
              </div>
            )}

            {/* 1. Resum Tècnic, Client i Localització */}
            <section className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div className="bg-surface-container-low dark:bg-slate-800/40 p-3.5 rounded-xl border border-outline-variant/30 space-y-1.5">
                <span className="font-label-caps text-on-surface-variant uppercase block text-[10px] flex items-center gap-1">
                  <Users className="w-3.5 h-3.5 text-primary" />
                  <span>Client Titular</span>
                </span>
                <p className="font-body-strong text-primary text-sm">
                  {feina.client_nom || conc?.client_nom || "Client no especificat"}
                </p>
                <p className="text-xs text-on-surface-variant flex items-center gap-1">
                  <Calendar className="w-3 h-3 text-primary" />
                  Planificació: {feina.data_planificacio || "Sense data"} · v{feina.versio || 1}
                </p>
              </div>

              <div className="bg-surface-container-low dark:bg-slate-800/40 p-3.5 rounded-xl border border-outline-variant/30 space-y-1.5">
                <span className="font-label-caps text-on-surface-variant uppercase block text-[10px] flex items-center gap-1">
                  <MapPin className="w-3.5 h-3.5 text-secondary" />
                  <span>Ubicació i Vehicle</span>
                </span>
                <p className="text-xs text-on-surface dark:text-slate-200">
                  {feina.adreca || "Sense adreça registrada"}
                </p>
                {conc?.vehicle && (
                  <p className="text-[11px] font-mono text-secondary flex items-center gap-1">
                    <Truck className="w-3.5 h-3.5" />
                    <span>
                      {conc.vehicle.matricula} · {conc.vehicle.marca_model}
                    </span>
                  </p>
                )}
              </div>
            </section>

            {feina.descripcio && (
              <section className="p-3.5 rounded-xl bg-surface-container-low/60 dark:bg-slate-800/40 border border-outline-variant/30 space-y-1">
                <span className="font-label-caps text-on-surface-variant uppercase block text-[10px]">
                  Instruccions i Detall Importat
                </span>
                <p className="text-xs text-on-surface dark:text-slate-200 whitespace-pre-line leading-relaxed">
                  {feina.descripcio}
                </p>
              </section>
            )}

            {/* Alerta Geovalla GPS */}
            {conc?.temps_i_gps?.desviacio_geovalla && (
              <section className="p-3.5 rounded-xl bg-amber-50 dark:bg-amber-950/35 border border-amber-300 dark:border-amber-700 flex items-start justify-between gap-3">
                <div className="flex items-start gap-2.5">
                  <AlertTriangle className="w-4 h-4 text-amber-700 dark:text-amber-400 shrink-0 mt-0.5" />
                  <div className="text-xs">
                    <p className="font-extrabold uppercase tracking-wider text-amber-900 dark:text-amber-300">
                      Desviació de Geovalla GPS Detectada (&gt;50m)
                    </p>
                    <p className="text-amber-800 dark:text-amber-200 mt-0.5">
                      {conc.temps_i_gps.justificacio_geovalla || "Sense justificació registrada."}
                    </p>
                  </div>
                </div>
                {evidenciesUrls["foto_geovalla"] && (
                  <button
                    type="button"
                    onClick={() =>
                      setLightboxUrl({
                        url: evidenciesUrls["foto_geovalla"],
                        titol: "Evidència Desviació Geovalla",
                      })
                    }
                    className="px-2.5 py-1 rounded-lg bg-amber-700 text-white text-[11px] font-bold shrink-0 cursor-pointer"
                  >
                    Veure Foto
                  </button>
                )}
              </section>
            )}

            {/* 2. Control Horari, Trams GPS i Valoració Comercial */}
            <section className="bg-surface-container-lowest dark:bg-slate-900 p-4 rounded-xl border border-outline-variant/30 space-y-3">
              <div className="flex items-center justify-between border-b border-outline-variant/20 pb-2">
                <div className="flex items-center gap-2">
                  <Clock className="w-4 h-4 text-primary" />
                  <h3 className="font-body-strong text-sm text-on-surface dark:text-white">
                    Control Horari, Trams GPS i Valoració Client
                  </h3>
                </div>
                {conc?.temps_i_gps?.te_tram_obert || feina.te_tram_obert ? (
                  <span className="text-[10px] font-mono font-bold px-2.5 py-0.5 rounded-full bg-emerald-100 text-emerald-800 flex items-center gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-600 animate-pulse" />
                    TEMPS OBERT
                  </span>
                ) : (
                  <span className="text-[10px] font-mono font-bold px-2.5 py-0.5 rounded-full bg-secondary-container/20 text-secondary">
                    {trams.length} {trams.length === 1 ? "tram" : "trams"}
                  </span>
                )}
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
                <div className="p-2.5 rounded-lg bg-surface-container-low dark:bg-slate-800/60 border border-outline-variant/20">
                  <span className="text-[10px] font-label-caps text-on-surface-variant uppercase block">
                    Hores Reals
                  </span>
                  <span className="text-base font-mono font-black text-primary dark:text-white">
                    {horesFact.toFixed(2)} h
                  </span>
                  {horesPrev > 0 && (
                    <span className="block text-[10px] font-mono text-on-surface-variant mt-0.5">
                      Previstes: {horesPrev.toFixed(2)} h
                    </span>
                  )}
                </div>
                <div className="p-2.5 rounded-lg bg-surface-container-low dark:bg-slate-800/60 border border-outline-variant/20">
                  <span className="text-[10px] font-label-caps text-on-surface-variant uppercase block">
                    Mà d&apos;Obra ({preuH.toFixed(2)} €/h)
                  </span>
                  <span className="text-base font-mono font-black text-secondary">
                    {Number(conc?.resum_comercial?.valor_ma_obra_pvp ?? horesFact * preuH).toFixed(2)} €
                  </span>
                  {horesFact === 0 && horesPrev > 0 && preuH > 0 && (
                    <span className="block text-[10px] font-mono text-on-surface-variant mt-0.5">
                      Previst: {(horesPrev * preuH).toFixed(2)} €
                    </span>
                  )}
                </div>
                <div className="p-2.5 rounded-lg bg-surface-container-low dark:bg-slate-800/60 border border-outline-variant/20">
                  <span className="text-[10px] font-label-caps text-on-surface-variant uppercase block">
                    Materials PVP
                  </span>
                  <span className="text-base font-mono font-black text-on-surface dark:text-white">
                    {Number(conc?.resum_comercial?.valor_materials_pvp ?? 0).toFixed(2)} €
                  </span>
                </div>
                <div className="p-2.5 rounded-lg bg-primary/10 border border-primary/30">
                  <span className="text-[10px] font-label-caps text-primary uppercase block font-bold">
                    Valorat Client (Base)
                  </span>
                  <span className="text-base font-mono font-black text-primary">
                    {Number(conc?.resum_comercial?.total_valorat_pvp ?? 0).toFixed(2)} €
                  </span>
                </div>
              </div>

              {trams.length > 0 && (
                <div className="space-y-1 pt-1">
                  {trams.map((t, idx) => (
                    <div
                      key={t.id}
                      className="text-xs px-2.5 py-1.5 rounded-lg bg-surface-container-low/60 dark:bg-slate-800/40 border border-outline-variant/15 flex items-center justify-between"
                    >
                      <span className="font-mono text-[11px] text-on-surface dark:text-slate-200">
                        #{idx + 1} · {new Date(t.hora_inici).toLocaleTimeString("ca-ES", { hour: "2-digit", minute: "2-digit" })} →{" "}
                        {t.hora_fi
                          ? new Date(t.hora_fi).toLocaleTimeString("ca-ES", { hour: "2-digit", minute: "2-digit" })
                          : "En curs"}
                      </span>
                      <span className="font-mono font-bold text-secondary text-[11px]">
                        {t.hora_fi ? fmtHMS(t.durada_segons) : "Actiu"}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </section>

            {/* 3. Evidències PWA: Protocol 3 Fotos QA + Signatura Digital del Client */}
            <section className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* 3 Fotos QA */}
              <div className="bg-surface-container-lowest dark:bg-slate-900 p-4 rounded-xl border border-outline-variant/30 space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="font-body-strong text-xs uppercase tracking-wider text-on-surface dark:text-white flex items-center gap-1.5">
                    <Camera className="w-4 h-4 text-primary" />
                    <span>Evidències Fotogràfiques QA</span>
                  </h3>
                  <span
                    className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded-full ${
                      conc?.fotos_qa?.protocol_complet
                        ? "bg-emerald-100 text-emerald-800"
                        : "bg-amber-100 text-amber-800"
                    }`}
                  >
                    {conc?.fotos_qa?.total_pujades ?? 0} / 3
                  </span>
                </div>

                <div className="grid grid-cols-3 gap-2">
                  {(
                    [
                      { key: "foto_inicial", flag: conc?.fotos_qa?.inicial, label: "Inicial" },
                      { key: "foto_intermedia", flag: conc?.fotos_qa?.intermedia, label: "Intermèdia" },
                      { key: "foto_final", flag: conc?.fotos_qa?.final, label: "Final" },
                    ] as const
                  ).map((item) => {
                    const url = evidenciesUrls[item.key];
                    return (
                      <div
                        key={item.key}
                        className="rounded-lg border border-outline-variant/30 overflow-hidden bg-surface-container-low dark:bg-slate-800/50 flex flex-col"
                      >
                        <div className="aspect-square relative flex items-center justify-center bg-surface-container">
                          {url ? (
                            <button
                              type="button"
                              onClick={() => setLightboxUrl({ url, titol: `Foto QA — ${item.label}` })}
                              className="w-full h-full group relative cursor-pointer"
                            >
                              <img
                                src={url}
                                alt={`Foto ${item.label}`}
                                className="w-full h-full object-cover"
                              />
                              <span className="absolute inset-0 bg-slate-950/0 group-hover:bg-slate-950/35 transition-colors flex items-center justify-center">
                                <ZoomIn className="w-4 h-4 text-white opacity-0 group-hover:opacity-100" />
                              </span>
                            </button>
                          ) : (
                            <span className="text-[10px] text-on-surface-variant px-1 text-center">
                              {item.flag ? "Carregant..." : "No capturada"}
                            </span>
                          )}
                        </div>
                        <span className="text-[10px] font-bold text-center py-1 text-on-surface-variant">
                          {item.label}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Signatura Digital + Receptor + Observacions */}
              <div className="bg-surface-container-lowest dark:bg-slate-900 p-4 rounded-xl border border-outline-variant/30 space-y-2.5">
                <div className="flex items-center justify-between">
                  <h3 className="font-body-strong text-xs uppercase tracking-wider text-on-surface dark:text-white flex items-center gap-1.5">
                    <PenTool className="w-4 h-4 text-secondary" />
                    <span>Signatura i Conformitat Client</span>
                  </h3>
                  <span
                    className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded-full ${
                      conc?.signatura?.present
                        ? "bg-emerald-100 text-emerald-800"
                        : "bg-surface-container-high text-on-surface-variant"
                    }`}
                  >
                    {conc?.signatura?.present ? "SIGNADA" : "PENDENT"}
                  </span>
                </div>

                {evidenciesUrls["signatura"] ? (
                  <button
                    type="button"
                    onClick={() =>
                      setLightboxUrl({
                        url: evidenciesUrls["signatura"],
                        titol: "Signatura Digital del Client",
                      })
                    }
                    className="w-full h-24 rounded-lg border border-outline-variant/30 bg-white p-1.5 flex items-center justify-center cursor-pointer hover:border-primary transition-colors"
                  >
                    <img
                      src={evidenciesUrls["signatura"]}
                      alt="Signatura del client"
                      className="max-h-full max-w-full object-contain"
                    />
                  </button>
                ) : (
                  <div className="h-20 rounded-lg border border-dashed border-outline-variant/40 bg-surface-container-low/40 flex items-center justify-center text-[11px] text-on-surface-variant">
                    {conc?.signatura?.present
                      ? "Carregant signatura..."
                      : "Encara no s'ha recollit signatura digital a camp."}
                  </div>
                )}

                <div className="text-[11px] space-y-0.5 text-on-surface-variant">
                  <p>
                    <strong>Receptor:</strong> {conc?.signatura?.nom_receptor || "—"}
                    {conc?.signatura?.dni_receptor ? ` (${conc.signatura.dni_receptor})` : ""}
                  </p>
                  {conc?.signatura?.observacions_tancament && (
                    <p className="text-on-surface dark:text-slate-200 bg-surface-container-low dark:bg-slate-800/50 p-2 rounded-lg mt-1">
                      <strong>Observacions camp:</strong> {conc.signatura.observacions_tancament}
                    </p>
                  )}
                </div>
              </div>
            </section>

            {/* 4. Taula Comparativa de Materials (Picking Nau + Furgoneta) */}
            <section className="space-y-2.5">
              <div className="flex items-center justify-between">
                <h3 className="font-body-strong text-sm text-on-surface dark:text-white flex items-center gap-1.5">
                  <Package className="w-4 h-4 text-primary" />
                  <span>Conciliació de Materials (Picking Nau + Furgoneta)</span>
                  <span className="text-[11px] font-mono font-bold px-2 py-0.5 rounded-full bg-primary/10 text-primary">
                    {materialsConc.length}
                  </span>
                </h3>
                {conc?.materials?.alerta_consum_excessiu && (
                  <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-error-container/30 text-error">
                    Alerta Consum Excessiu
                  </span>
                )}
              </div>

              {materialsConc.length === 0 ? (
                <div className="p-5 rounded-xl border border-dashed border-outline-variant/40 text-center bg-surface-container-low/30 text-xs text-on-surface-variant">
                  Cap material imputat (ni de nau ni de furgoneta) en aquesta ordre de treball.
                </div>
              ) : (
                <div className="border border-outline-variant/30 rounded-xl overflow-x-auto bg-surface-container-lowest dark:bg-slate-900">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-surface-container-low dark:bg-slate-800/60 text-on-surface-variant border-b border-outline-variant/20 text-[10px] font-label-caps uppercase">
                      <tr>
                        <th className="py-2 px-3">Article</th>
                        <th className="py-2 px-2 text-center">Origen</th>
                        <th className="py-2 px-2 text-right">Previst</th>
                        <th className="py-2 px-2 text-right">Carregat</th>
                        <th className="py-2 px-2 text-right">Retornat</th>
                        <th className="py-2 px-2 text-right">Merma</th>
                        <th className="py-2 px-3 text-right">Consum Real</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-outline-variant/15">
                      {materialsConc.map((lin) => {
                        const draft = ajustosPicking[lin.linia_id];
                        const esEditable = disclaimer.pot_validar;
                        const qInNum = draft ? parseFloat(draft.carregat) : lin.quantitat_carregada_pick_in;
                        const qOutNum = draft ? parseFloat(draft.retornat) : lin.quantitat_retornada_pick_out;
                        const consumCalc = Math.max(
                          0,
                          (Number.isNaN(qInNum) ? 0 : qInNum) - (Number.isNaN(qOutNum) ? 0 : qOutNum)
                        );
                        return (
                          <tr key={lin.linia_id} className="hover:bg-surface-container-low/40">
                            <td className="py-2 px-3">
                              <span className="font-semibold text-on-surface dark:text-slate-100 block">
                                {lin.article_nom}
                              </span>
                              <span className="text-[10px] font-mono text-on-surface-variant">
                                {lin.referencia_inventari || "S/REF"} · {Number(lin.preu_venda_unitari).toFixed(2)} €/{lin.unitat_mesura}
                              </span>
                            </td>
                            <td className="py-2 px-2 text-center">
                              <span
                                className={`text-[10px] font-mono font-bold px-1.5 py-0.5 rounded ${
                                  lin.origen_estoc === "FURGONETA"
                                    ? "bg-secondary-container/25 text-secondary"
                                    : "bg-primary/10 text-primary"
                                }`}
                              >
                                {lin.origen_estoc === "FURGONETA" ? "FURGONETA" : "NAU"}
                              </span>
                            </td>
                            <td className="py-2 px-2 text-right font-mono">{lin.quantitat_prevista}</td>
                            <td className="py-2 px-2 text-right font-mono">
                              {esEditable && draft ? (
                                <input
                                  type="number"
                                  step="0.1"
                                  min="0"
                                  value={draft.carregat}
                                  onChange={(e) =>
                                    setAjustosPicking((prev) => ({
                                      ...prev,
                                      [lin.linia_id]: { ...prev[lin.linia_id], carregat: e.target.value },
                                    }))
                                  }
                                  className="w-16 px-1.5 py-0.5 text-right rounded border border-outline-variant/50 bg-surface-container-low text-xs"
                                />
                              ) : (
                                lin.quantitat_carregada_pick_in
                              )}
                            </td>
                            <td className="py-2 px-2 text-right font-mono">
                              {esEditable && draft ? (
                                <input
                                  type="number"
                                  step="0.1"
                                  min="0"
                                  value={draft.retornat}
                                  onChange={(e) =>
                                    setAjustosPicking((prev) => ({
                                      ...prev,
                                      [lin.linia_id]: { ...prev[lin.linia_id], retornat: e.target.value },
                                    }))
                                  }
                                  className="w-16 px-1.5 py-0.5 text-right rounded border border-outline-variant/50 bg-surface-container-low text-xs"
                                />
                              ) : (
                                lin.quantitat_retornada_pick_out
                              )}
                            </td>
                            <td className="py-2 px-2 text-right font-mono">
                              {esEditable && draft ? (
                                <input
                                  type="number"
                                  step="0.1"
                                  min="0"
                                  value={draft.merma}
                                  onChange={(e) =>
                                    setAjustosPicking((prev) => ({
                                      ...prev,
                                      [lin.linia_id]: { ...prev[lin.linia_id], merma: e.target.value },
                                    }))
                                  }
                                  className="w-16 px-1.5 py-0.5 text-right rounded border border-outline-variant/50 bg-surface-container-low text-xs"
                                />
                              ) : (
                                lin.quantitat_mermada
                              )}
                            </td>
                            <td className="py-2 px-3 text-right font-mono font-bold text-primary">
                              {consumCalc.toFixed(2)} {lin.unitat_mesura}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </section>

            {/* 5. Incidències, Tiquets de Camp i Plànols GIS As-Built */}
            <section className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {/* Incidències */}
              <div className="p-3.5 rounded-xl bg-surface-container-lowest dark:bg-slate-900 border border-outline-variant/30 space-y-2">
                <h4 className="text-[11px] font-extrabold uppercase tracking-wider text-on-surface dark:text-white flex items-center justify-between">
                  <span>Incidències</span>
                  <span className="font-mono text-primary">{conc?.incidencies?.total ?? 0}</span>
                </h4>
                {!conc?.incidencies?.items?.length ? (
                  <p className="text-[11px] text-on-surface-variant">Cap incidència registrada.</p>
                ) : (
                  <div className="space-y-1.5">
                    {conc.incidencies.items.slice(0, 3).map((inc) => (
                      <div key={inc.id} className="p-2 rounded-lg bg-surface-container-low text-[11px]">
                        <span className="font-bold text-amber-700">{inc.ambit}</span> · {inc.estat}
                        {inc.text_observacions && (
                          <p className="text-on-surface-variant line-clamp-2 mt-0.5">
                            {inc.text_observacions}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Tiquets vinculats */}
              <div className="p-3.5 rounded-xl bg-surface-container-lowest dark:bg-slate-900 border border-outline-variant/30 space-y-2">
                <h4 className="text-[11px] font-extrabold uppercase tracking-wider text-on-surface dark:text-white flex items-center justify-between">
                  <span>Tiquets Camp</span>
                  <span className="font-mono text-primary">
                    {conc?.tiquets?.total ?? 0} ({Number(conc?.tiquets?.import_total ?? 0).toFixed(2)} €)
                  </span>
                </h4>
                {!conc?.tiquets?.items?.length ? (
                  <p className="text-[11px] text-on-surface-variant">Cap tiquet imputat a l&apos;OT.</p>
                ) : (
                  <div className="space-y-1.5">
                    {conc.tiquets.items.slice(0, 3).map((tiq) => (
                      <div
                        key={tiq.id}
                        className="p-2 rounded-lg bg-surface-container-low text-[11px] flex items-center justify-between"
                      >
                        <span className="font-semibold">{tiq.categoria}</span>
                        <span className="font-mono font-bold">
                          {Number(tiq.import_total || 0).toFixed(2)} €
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Capes GIS As-Built */}
              <div className="p-3.5 rounded-xl bg-surface-container-lowest dark:bg-slate-900 border border-outline-variant/30 space-y-2">
                <h4 className="text-[11px] font-extrabold uppercase tracking-wider text-on-surface dark:text-white flex items-center justify-between">
                  <span className="inline-flex items-center gap-1">
                    <Layers className="w-3.5 h-3.5 text-secondary" />
                    GIS As-Built
                  </span>
                  <span className="font-mono text-primary">{conc?.capes_gis?.length ?? 0}</span>
                </h4>
                {!conc?.capes_gis?.length ? (
                  <p className="text-[11px] text-on-surface-variant">
                    {conc?.planol ? `Plànol ${conc.planol.codi_referencia || conc.planol.titol} (sense capes noves)` : "Cap capa As-Built vinculada."}
                  </p>
                ) : (
                  <div className="space-y-1.5">
                    {conc.capes_gis.slice(0, 3).map((cap) => (
                      <div key={cap.id} className="p-2 rounded-lg bg-surface-container-low text-[11px]">
                        <span className="font-semibold block truncate">{cap.nom}</span>
                        <span className="text-[10px] font-mono text-on-surface-variant">
                          {cap.disciplina || "GIS"}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </section>

            {/* 6. Documentació Comercial Vinculada (Pressupost / Pre-factura / Factura Final — Tots 3 Rols) */}
            <section className="p-4 rounded-xl bg-surface-container-low/60 dark:bg-slate-800/40 border border-outline-variant/30 space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="font-body-strong text-sm text-on-surface dark:text-white flex items-center gap-1.5">
                  <Receipt className="w-4 h-4 text-primary" />
                  <span>Documentació Comercial del Client (Pressupost / Factura)</span>
                </h3>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {/* Pressupost vinculat */}
                <div className="p-3 rounded-xl bg-surface-container-lowest dark:bg-slate-900 border border-outline-variant/30 flex items-center justify-between gap-2">
                  <div>
                    <span className="text-[10px] font-label-caps uppercase text-on-surface-variant block">
                      Pressupost Vinculat
                    </span>
                    {conc?.pressupost ? (
                      <>
                        <p className="font-mono text-xs font-bold text-primary mt-0.5">
                          {conc.pressupost.numero} · {conc.pressupost.estat}
                        </p>
                        <p className="font-mono text-sm font-black text-on-surface dark:text-white">
                          {Number(conc.pressupost.total || 0).toFixed(2)} €
                        </p>
                      </>
                    ) : (
                      <p className="text-xs text-on-surface-variant mt-0.5">Sense pressupost vinculat</p>
                    )}
                  </div>
                  {conc?.pressupost && (
                    <Link
                      href={`/gestio/pressupostos?id=${conc.pressupost.id}`}
                      onClick={onClose}
                      className="px-2.5 py-1.5 rounded-lg bg-primary/10 hover:bg-primary text-primary hover:text-white text-[11px] font-bold transition-colors inline-flex items-center gap-1"
                    >
                      <ExternalLink className="w-3 h-3" />
                      <span>Veure</span>
                    </Link>
                  )}
                </div>

                {/* Pre-factura / Factura final vinculada */}
                <div className="p-3 rounded-xl bg-surface-container-lowest dark:bg-slate-900 border border-outline-variant/30 flex items-center justify-between gap-2">
                  <div>
                    <span className="text-[10px] font-label-caps uppercase text-on-surface-variant block">
                      Pre-factura / Factura Client
                    </span>
                    {facturaDoc ? (
                      <>
                        <p className="font-mono text-xs font-bold text-primary mt-0.5">
                          {facturaDoc.serie}-{String(facturaDoc.numero_factura).padStart(4, "0")} ·{" "}
                          {facturaDoc.estat_document === "ESBORRANY_PREFACTURA"
                            ? "Pre-factura"
                            : facturaDoc.estat_document}
                        </p>
                        <p className="font-mono text-sm font-black text-on-surface dark:text-white">
                          {Number(facturaDoc.liquid_exigible || 0).toFixed(2)} €
                        </p>
                      </>
                    ) : (
                      <p className="text-xs text-on-surface-variant mt-0.5">Encara no pre-facturada</p>
                    )}
                  </div>
                  {facturaDoc && (
                    <button
                      type="button"
                      data-testid="btn-veure-factura-comercial-ot"
                      onClick={() => setFacturaModalId(facturaDoc.id)}
                      className="px-2.5 py-1.5 rounded-lg bg-primary hover:bg-primary-container text-white text-[11px] font-bold transition-colors inline-flex items-center gap-1 cursor-pointer shrink-0"
                    >
                      <Receipt className="w-3 h-3" />
                      <span>Detall / PDF</span>
                    </button>
                  )}
                </div>
              </div>
            </section>

            {/* 7. Espai Integrat de Validació Tècnica i Pas a Pre-facturació (3 Rols) */}
            {!facturaDoc && (
              <section
                data-testid="fulla360-validacio-workspace"
                className="p-4 rounded-xl bg-surface-container-lowest dark:bg-slate-900 border-2 border-primary/25 space-y-4 shadow-sm"
              >
                <div className="flex items-center justify-between border-b border-outline-variant/20 pb-2.5">
                  <div className="flex items-center gap-2">
                    <ShieldCheck className="w-4 h-4 text-primary" />
                    <h3 className="font-body-strong text-sm text-primary dark:text-white">
                      Espai de Validació Tècnica i Pre-facturació
                    </h3>
                  </div>
                  <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded-full bg-primary/10 text-primary font-bold">
                    {rolActiu || "GESTIÓ"}
                  </span>
                </div>

                {/* Checklist de conciliació */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {CHECKLIST_ITEMS.map((item) => {
                    const checked = Boolean(checklist[item.key]);
                    return (
                      <button
                        key={item.key}
                        type="button"
                        disabled={!disclaimer.pot_validar}
                        onClick={() =>
                          setChecklist((prev) => ({ ...prev, [item.key]: !prev[item.key] }))
                        }
                        className={`p-2.5 rounded-lg border text-left text-xs flex items-center gap-2 transition-colors ${
                          checked
                            ? "bg-primary/10 border-primary/40 text-primary font-semibold"
                            : "bg-surface-container-low/60 border-outline-variant/30 text-on-surface-variant"
                        } disabled:opacity-50 cursor-pointer`}
                      >
                        {checked ? (
                          <CheckSquare className="w-4 h-4 text-primary shrink-0" />
                        ) : (
                          <Square className="w-4 h-4 shrink-0" />
                        )}
                        <span>{item.label}</span>
                      </button>
                    );
                  })}
                </div>

                {/* Ajust d'hores i notes de validació */}
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <div>
                    <label className="block text-[10px] font-label-caps uppercase text-on-surface-variant mb-1">
                      Hores Facturables Conciliades
                    </label>
                    <input
                      type="number"
                      step="0.25"
                      min="0"
                      disabled={!disclaimer.pot_validar}
                      value={horesEdit}
                      onChange={(e) => setHoresEdit(e.target.value)}
                      className="w-full px-3 py-2 text-xs font-mono font-bold rounded-lg border border-outline-variant/50 bg-surface-container-low dark:bg-slate-800 text-on-surface dark:text-white disabled:opacity-50"
                    />
                  </div>
                  <div className="sm:col-span-2">
                    <label className="block text-[10px] font-label-caps uppercase text-on-surface-variant mb-1">
                      Notes de Validació Tècnica
                    </label>
                    <textarea
                      rows={2}
                      disabled={!disclaimer.pot_validar}
                      value={notesValidacio}
                      onChange={(e) => setNotesValidacio(e.target.value)}
                      placeholder="Anotacions de revisió tècnica abans de pre-facturar..."
                      className="w-full px-3 py-1.5 text-xs rounded-lg border border-outline-variant/50 bg-surface-container-low dark:bg-slate-800 text-on-surface dark:text-white resize-none disabled:opacity-50"
                    />
                  </div>
                </div>

                {actionError && (
                  <div className="p-3 rounded-lg bg-error-container/25 border border-error text-error text-xs font-semibold">
                    {actionError}
                  </div>
                )}
                {actionSuccess && (
                  <div className="p-3 rounded-lg bg-emerald-50 border border-emerald-300 text-emerald-900 text-xs font-semibold">
                    {actionSuccess}
                  </div>
                )}

                <div className="flex flex-wrap items-center gap-2.5 pt-1">
                  <button
                    type="button"
                    data-testid="btn-validar-conciliacio"
                    disabled={!disclaimer.pot_validar || validant}
                    onClick={handleValidarConciliacio}
                    className="px-4 py-2.5 rounded-xl bg-primary hover:bg-primary-container text-white text-xs font-bold inline-flex items-center gap-1.5 shadow-sm transition-all disabled:opacity-45 cursor-pointer"
                  >
                    {validant ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <ShieldCheck className="w-3.5 h-3.5" />
                    )}
                    <span>
                      {conc?.validacio?.validada ? "Actualitzar Validació" : "Validar Conciliació"}
                    </span>
                  </button>

                  <button
                    type="button"
                    data-testid="btn-passar-a-prefacturacio"
                    disabled={!disclaimer.pot_prefacturar || enviantPrefactura}
                    onClick={handlePassarAPrefacturacio}
                    className="px-4 py-2.5 rounded-xl bg-secondary hover:opacity-90 text-white text-xs font-bold inline-flex items-center gap-1.5 shadow-sm transition-all disabled:opacity-45 cursor-pointer"
                    title={
                      disclaimer.pot_prefacturar
                        ? "Generar pre-factura Sèrie PRE amb les dades conciliades"
                        : "Cal concloure i validar la Fulla 360° abans de passar a pre-facturació"
                    }
                  >
                    {enviantPrefactura ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <Receipt className="w-3.5 h-3.5" />
                    )}
                    <span>
                      {enviantPrefactura ? "Generant Pre-factura..." : "Passar a Pre-facturació"}
                    </span>
                  </button>
                </div>
              </section>
            )}

            {/* 8. Quadrilla i Eines (Resum compacte) */}
            <section className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div className="p-3.5 rounded-xl bg-surface-container-lowest dark:bg-slate-900 border border-outline-variant/30 space-y-2">
                <h4 className="text-[11px] font-extrabold uppercase tracking-wider text-on-surface dark:text-white flex items-center gap-1.5">
                  <Users className="w-3.5 h-3.5 text-primary" />
                  <span>Quadrilla Assignada</span>
                </h4>
                <p className="text-xs font-bold text-primary">
                  Cap de Colla: {feina.cap_de_colla_nom || "Pendent"}
                </p>
                {feina.operaris_assignats && feina.operaris_assignats.length > 0 && (
                  <div className="space-y-1">
                    {feina.operaris_assignats.map((op) => (
                      <div key={op.id} className="text-[11px] flex items-center justify-between text-on-surface-variant">
                        <span>
                          {op.nom} {op.cognoms || ""}
                        </span>
                        {op.telefon && (
                          <a href={`tel:${op.telefon}`} className="text-primary hover:underline inline-flex items-center gap-0.5">
                            <Phone className="w-3 h-3" /> {op.telefon}
                          </a>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="p-3.5 rounded-xl bg-surface-container-lowest dark:bg-slate-900 border border-outline-variant/30 space-y-2">
                <h4 className="text-[11px] font-extrabold uppercase tracking-wider text-on-surface dark:text-white flex items-center gap-1.5">
                  <Wrench className="w-3.5 h-3.5 text-secondary" />
                  <span>Eines en Custòdia ({eines.length})</span>
                </h4>
                {eines.length === 0 ? (
                  <p className="text-[11px] text-on-surface-variant">Cap eina en custòdia assignada.</p>
                ) : (
                  <div className="space-y-1">
                    {eines.map((eina) => (
                      <div key={eina.id} className="text-[11px] flex items-center justify-between">
                        <span className="font-medium text-on-surface dark:text-slate-200">{eina.nom}</span>
                        <span className="font-mono text-[10px] text-on-surface-variant">{eina.numero_serie}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </section>
          </div>

          {/* Footer Actions */}
          <div className="px-5 py-3.5 border-t border-outline-variant/20 bg-surface-container-low/50 dark:bg-slate-800/40 flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2 flex-wrap">
              <Link
                href="/gestio/planols"
                onClick={onClose}
                className="py-2 px-3 rounded-xl bg-surface-container-high hover:bg-surface-container-highest text-on-surface text-xs font-body-strong transition-colors"
              >
                Plànols GIS
              </Link>
              {onFocusMapa && (
                <button
                  type="button"
                  onClick={() => {
                    onFocusMapa(feina.id);
                    onClose();
                  }}
                  className="py-2 px-3 rounded-xl bg-primary/10 hover:bg-primary text-primary hover:text-white text-xs font-bold transition-colors inline-flex items-center gap-1 cursor-pointer"
                >
                  <MapPin className="w-3.5 h-3.5" />
                  <span>Mapa</span>
                </button>
              )}
              {potAccedirComptabilitat &&
                facturaDoc &&
                facturaDoc.estat_document === "ESBORRANY_PREFACTURA" && (
                  <Link
                    href={`/gestio/comptabilitat?tab=PREFACTURACIO&prefactura_id=${facturaDoc.id}`}
                    onClick={onClose}
                    className="py-2 px-3 rounded-xl bg-amber-600 hover:bg-amber-500 text-white text-xs font-bold inline-flex items-center gap-1.5 shadow-sm"
                  >
                    <Receipt className="w-3.5 h-3.5" />
                    <span>Editar a Comptabilitat</span>
                  </Link>
                )}
            </div>

            <div className="flex items-center gap-2">
              {onEdit && (
                <button
                  type="button"
                  onClick={() => {
                    onEdit(feina.id);
                    onClose();
                  }}
                  className="py-2 px-4 rounded-xl bg-primary hover:bg-primary-container text-white text-xs font-bold transition-all flex items-center gap-1.5 cursor-pointer shadow-sm"
                >
                  <Edit className="w-3.5 h-3.5" />
                  <span>Editar Ordre</span>
                </button>
              )}
              <button
                type="button"
                onClick={onClose}
                className="py-2 px-4 rounded-xl bg-surface-container hover:bg-surface-container-high text-on-surface text-xs font-body-strong transition-colors cursor-pointer"
              >
                Tancar
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Lightbox Evidències */}
      {lightboxUrl && (
        <div
          className="fixed inset-0 z-[80] bg-slate-950/85 backdrop-blur-xs flex flex-col items-center justify-center p-6"
          onClick={() => setLightboxUrl(null)}
        >
          <div className="max-w-4xl w-full flex items-center justify-between text-white mb-3">
            <span className="text-sm font-bold">{lightboxUrl.titol}</span>
            <button
              type="button"
              onClick={() => setLightboxUrl(null)}
              className="p-2 rounded-xl bg-white/15 hover:bg-white/25 cursor-pointer"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
          <img
            src={lightboxUrl.url}
            alt={lightboxUrl.titol}
            className="max-h-[80vh] max-w-full rounded-xl shadow-2xl bg-white object-contain"
            onClick={(e) => e.stopPropagation()}
          />
        </div>
      )}

      {/* Modal Consulta Comercial de Pre-factura / Factura (tots 3 rols) */}
      <FacturaComercialModal facturaId={facturaModalId} onClose={() => setFacturaModalId(null)} />
    </>
  );
}
