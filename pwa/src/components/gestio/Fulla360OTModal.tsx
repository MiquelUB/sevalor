"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import {
  AlertCircle,
  AlertTriangle,
  AlignLeft,
  Building2,
  Calendar,
  Camera,
  CheckCircle2,
  CheckSquare,
  Clock,
  ExternalLink,
  FileText,
  Layers,
  Loader2,
  Map as MapIcon,
  MapPin,
  Package,
  PenTool,
  Plus,
  Receipt,
  Save,
  Search,
  ShieldCheck,
  Sparkles,
  Square,
  Trash2,
  TrendingUp,
  Truck,
  User,
  Users,
  Warehouse,
  Wrench,
  X,
  ZoomIn,
} from "lucide-react";
import { apiFetch, extractTenantId, getApiBaseUrl, getAuthToken } from "@/lib/api";
import { geocodificarAdreca } from "@/lib/geocoding";
import { useGestio } from "@/lib/gestio-context";
import { DisclaimerOT, Feina } from "@/components/gestio/Map";
import { FacturaComercialModal } from "@/components/gestio/FacturaComercialModal";
import type { PressupostItem, PressupostLinia } from "@/components/gestio/PressupostModal";

export type Fulla360OTMode = "CREATE" | "FROM_PRESSUPOST" | "EDIT" | "VIEW_360";

export interface Fulla360OTModalProps {
  mode: Fulla360OTMode;
  isOpen?: boolean;
  feinaId?: string | null;
  initialFeina?: Feina | null;
  initialClientId?: string;
  initialPressupost?: PressupostItem | null;
  onClose: () => void;
  onSuccess?: (result?: { id: string; codi?: string }) => void;
  onFocusMapa?: (feinaId: string) => void;
  onPrefacturaCreated?: () => void;
}

interface PickingLiniaForm {
  id?: string;
  article_id: string;
  article_nom: string;
  referencia_inventari: string;
  quantitat_prevista: number;
  unitat_mesura: string;
  preu_venda_unitari: number;
  preu_cost_pmp: number;
  estoc_disponible: number;
  magatzem_id?: string | null;
}

interface MaterialConciliacio {
  linia_id: string;
  picking_id: string;
  article_id: string;
  article_nom: string;
  referencia_inventari?: string | null;
  unitat_mesura: string;
  origen_estoc: string;
  magatzem_nom?: string | null;
  quantitat_prevista: number;
  quantitat_carregada_pick_in: number;
  quantitat_retornada_pick_out: number;
  quantitat_mermada: number;
  consum_real: number;
  quantitat_facturable?: number;
  preu_venda_unitari: number;
  tipus_iva?: number;
  subtotal_pvp: number;
  preu_cost_pmp?: number | null;
  cost_real_pmp?: number | null;
}

interface PropostaPrefacturaLinia {
  concepte: string;
  quantitat: number;
  preu_venda_unitari: number;
  tipus_iva: number;
  article_id?: string | null;
  subtotal: number;
  origen: string;
}

interface PropostaPrefactura {
  linies: PropostaPrefacturaLinia[];
  base_imposable: number;
  quota_iva: number;
  liquid_exigible: number;
  te_pressupost_vinculat?: boolean;
}

interface ConciliacioCompleta {
  ordre_treball_id: string;
  codi: string;
  titol: string;
  estat: string;
  versio: number;
  client_id: string;
  client_nom?: string | null;
  vehicle?: {
    id: string;
    matricula: string;
    marca_model: string;
    carnet_necessari?: string | null;
    cost_per_km_eur?: number | null;
    preu_km_facturable?: number | null;
    km_imputats?: number | null;
    odometre_inici?: number | null;
    odometre_fi?: number | null;
    estat_pickout?: string | null;
    valor_desplacament_pvp?: number | null;
  } | null;
  operaris_assignats?: Array<{
    id: string;
    nom: string;
    rol?: string | null;
    es_cap_de_colla?: boolean;
    telefon?: string | null;
  }>;
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
    hores_previstes_human?: string;
    hores_reals: number;
    hores_reals_human?: string;
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
    linies_pendents_facturar?: Array<{
      tipus_linia?: string;
      concepte: string;
      quantitat: number;
      preu_unitari: number;
      tipus_iva?: number;
      subtotal: number;
    }>;
    partides_pressupost_addicionals?: Array<{
      tipus_linia: string;
      concepte: string;
      quantitat: number;
      preu_unitari: number;
      tipus_iva: number;
      subtotal: number;
    }>;
  };
  eines?: Array<{
    id: string;
    nom: string;
    model?: string | null;
    numero_serie: string;
    estat: string;
    en_custodia_efectiva?: boolean;
    requereix_pickout?: boolean;
    custodiat_per_id?: string | null;
  }>;
  incidencies: {
    total: number;
    obertes: number;
    items: Array<{
      id: string;
      ambit: string;
      estat: string;
      text_observacions?: string | null;
    }>;
  };
  tiquets: {
    total: number;
    import_total: number;
    items: Array<{
      id: string;
      categoria: string;
      import_total: number;
    }>;
  };
  capes_gis: Array<{
    id: string;
    nom: string;
    disciplina?: string | null;
  }>;
  pressupost?: {
    id: string;
    numero: string;
    estat: string;
    total: number;
    base_imposable?: number;
    descompte_global_pct?: number;
  } | null;
  factura?: {
    id: string;
    serie: string;
    numero_factura: number;
    estat_document: string;
    base_imposable: number;
    quota_iva: number;
    liquid_exigible: number;
  } | null;
  proposta_prefactura?: PropostaPrefactura | null;
  resum_comercial: {
    import_pressupostat: number;
    hores_previstes: number;
    hores_reals: number;
    km_imputats: number;
    preu_venda_hora_aplicat: number;
    valor_ma_obra_previst_pvp?: number;
    valor_ma_obra_pvp: number;
    valor_materials_pvp: number;
    valor_desplacament_pvp?: number;
    valor_partides_pressupost_pvp?: number;
    total_tiquets_camp: number;
    total_previst_pvp?: number;
    total_valorat_pvp: number;
    total_prefactura_base?: number;
    total_prefactura_iva?: number;
    total_prefactura_liquid?: number;
  };
  resum_intern?: {
    cost_materials_previst_pmp?: number | null;
    cost_materials_pmp?: number | null;
    cost_mermes_pmp?: number | null;
    cost_ma_obra_previst?: number | null;
    cost_ma_obra_real?: number | null;
    cost_flota_real?: number | null;
    cost_tiquets_camp?: number | null;
    cost_total_previst?: number | null;
    cost_total_real?: number | null;
    marge_previst_eur?: number | null;
    marge_previst_percentatge?: number | null;
    marge_real_eur?: number | null;
    marge_real_percentatge?: number | null;
    bloqueig_marge_critic?: boolean | null;
  } | null;
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

const JERARQUIA_CARNETS: Record<string, string[]> = {
  "N/A": ["N/A", "AM", "A1", "A2", "A", "B", "BE", "B+E", "C1", "C1E", "C", "CE", "C+E", "D1", "D"],
  B: ["B", "BE", "B+E", "C1", "C1E", "C", "CE", "C+E", "D1", "D"],
  "B+E": ["BE", "B+E", "C1E", "CE", "C+E"],
  BE: ["BE", "B+E", "C1E", "CE", "C+E"],
  C1: ["C1", "C1E", "C", "CE", "C+E"],
  C: ["C", "CE", "C+E"],
  "C+E": ["CE", "C+E"],
  CE: ["CE", "C+E"],
  D: ["D"],
};

function latLngToTile(lat: number, lng: number, zoom: number) {
  const n = Math.pow(2, zoom);
  const tileX = Math.floor(((lng + 180) / 360) * n);
  const latRad = (lat * Math.PI) / 180;
  const tileY = Math.floor(
    ((1 - Math.log(Math.tan(latRad) + 1 / Math.cos(latRad)) / Math.PI) / 2) * n
  );
  return { x: tileX, y: tileY };
}

interface MiniMapOTProps {
  adreca: string;
  latitud?: number | null;
  longitud?: number | null;
  codi?: string;
}

function MiniMapOT({ adreca, latitud, longitud, codi }: MiniMapOTProps) {
  const coords = useMemo(() => {
    let lat = latitud != null && Number(latitud) !== 0 ? Number(latitud) : 41.3879;
    let lng = longitud != null && Number(longitud) !== 0 ? Number(longitud) : 2.1699;
    if ((!latitud || !longitud) && adreca) {
      const g = geocodificarAdreca(adreca, lat, lng);
      lat = g.lat;
      lng = g.lng;
    }
    return { lat, lng };
  }, [adreca, latitud, longitud]);

  const zoom = 14;
  const tile = latLngToTile(coords.lat, coords.lng, zoom);

  return (
    <div className="relative w-full h-36 rounded-lg overflow-hidden border border-outline-variant/30 bg-slate-950 flex items-center justify-center select-none">
      <div className="grid grid-cols-3 grid-rows-3 w-[768px] h-[768px] absolute pointer-events-none opacity-90 scale-50 transform">
        {[-1, 0, 1].map((dy) =>
          [-1, 0, 1].map((dx) => {
            const tx = tile.x + dx;
            const ty = tile.y + dy;
            const tileUrl = `https://tile.openstreetmap.org/${zoom}/${tx}/${ty}.png`;
            return (
              <img
                key={`${tx}-${ty}`}
                src={tileUrl}
                alt="MiniMap Tile"
                className="w-[256px] h-[256px] block object-cover"
                loading="lazy"
              />
            );
          })
        )}
      </div>
      {/* Pin central de l'OT */}
      <div className="relative z-10 flex flex-col items-center">
        <div className="w-6 h-6 rounded-full bg-primary text-white flex items-center justify-center shadow-lg border-2 border-white animate-bounce">
          <MapPin className="w-3.5 h-3.5" />
        </div>
        <span className="mt-1 px-1.5 py-0.5 rounded bg-slate-900/90 text-white font-mono text-[9px] font-bold border border-slate-700 shadow-sm">
          {codi || "OT"}
        </span>
      </div>
      <div className="absolute bottom-1 right-1.5 text-[8px] text-slate-400/80 bg-slate-950/70 px-1 py-0.5 rounded pointer-events-none">
        © OpenStreetMap
      </div>
    </div>
  );
}

const SECCIONS_MA_OBRA_KW = [
  "mà d'obra",
  "ma d'obra",
  "mà dobra",
  "ma dobra",
  "mano de obra",
  "treballs tècnics",
  "treballs tecnics",
  "muntatge",
  "instal·lació",
  "instal.lacio",
  "hores",
];

const SECCIONS_MATERIAL_KW = ["material", "subministr", "suministr", "recanvi", "peces"];
const RE_REF_PREFIX = /^\s*\[([^\]]{1,50})\]/;
const RE_UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function esLiniaMaObra(lin: PressupostLinia): boolean {
  const tipus = (lin.tipus_linia || "").trim().toUpperCase();
  if (tipus === "MA_OBRA" || Boolean(lin.operari_id)) return true;
  if (["MATERIAL", "EINA", "DESPLACAMENT", "MAQUINARIA"].includes(tipus)) return false;
  if (lin.article_id || lin.eina_id || lin.vehicle_id) return false;
  const sec = (lin.seccio || "").trim().toLowerCase();
  return SECCIONS_MA_OBRA_KW.some((k) => sec.includes(k));
}

function esLiniaMaterial(lin: PressupostLinia): boolean {
  if (lin.article_id) return true;
  const tipus = (lin.tipus_linia || "").trim().toUpperCase();
  if (tipus === "MATERIAL") return true;
  if (["MA_OBRA", "EINA", "DESPLACAMENT", "MAQUINARIA"].includes(tipus)) return false;
  if (lin.eina_id || lin.vehicle_id || lin.operari_id) return false;
  const sec = (lin.seccio || "").trim().toLowerCase();
  return SECCIONS_MATERIAL_KW.some((k) => sec.includes(k));
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

function addHoursToTime(hhmm: string, hours: number): string {
  const [hStr, mStr] = hhmm.split(":");
  const baseMin = (parseInt(hStr || "8", 10) || 8) * 60 + (parseInt(mStr || "0", 10) || 0);
  const totalMin = baseMin + Math.round(hours * 60);
  if (totalMin >= 24 * 60) return "";
  const hh = Math.floor(totalMin / 60);
  const mm = totalMin % 60;
  return `${String(hh).padStart(2, "0")}:${String(mm).padStart(2, "0")}`;
}

function diffHoursBetweenTimes(startHHMM: string, endHHMM: string): number {
  if (!startHHMM || !endHHMM) return 0;
  const [sh, sm] = startHHMM.split(":").map((x) => parseInt(x, 10));
  const [eh, em] = endHHMM.split(":").map((x) => parseInt(x, 10));
  if ([sh, sm, eh, em].some((n) => Number.isNaN(n))) return 0;
  const diffMin = eh * 60 + em - (sh * 60 + sm);
  return diffMin > 0 ? Math.round((diffMin / 60) * 100) / 100 : 0;
}

function fmtHMS(seg: number): string {
  const s = Math.max(0, Math.floor(seg));
  const hh = Math.floor(s / 3600);
  const mm = Math.floor((s % 3600) / 60);
  const ss = s % 60;
  return `${String(hh).padStart(2, "0")}:${String(mm).padStart(2, "0")}:${String(ss).padStart(2, "0")}`;
}

export function Fulla360OTModal({
  mode,
  isOpen = true,
  feinaId,
  initialFeina,
  initialClientId,
  initialPressupost,
  onClose,
  onSuccess,
  onFocusMapa,
  onPrefacturaCreated,
}: Fulla360OTModalProps) {
  const { rolActiu } = useGestio();
  const rolUp = (rolActiu || "").toUpperCase();
  const potVeureCostosInterns = rolUp === "BOSS" || rolUp === "SECRETARIA";
  const potAccedirComptabilitat = rolUp !== "ENGINYER";

  const resolvedFeinaId = feinaId || initialFeina?.id || null;
  const isExistingOT = (mode === "EDIT" || mode === "VIEW_360") && Boolean(resolvedFeinaId);
  const isFromPressupost = mode === "FROM_PRESSUPOST" && Boolean(initialPressupost);

  // Loading & submission state
  const [bootLoading, setBootLoading] = useState(isExistingOT || isFromPressupost);
  const [saving, setSaving] = useState(false);
  const [pressupostLoading, setPressupostLoading] = useState(false);
  const [copilotLoading, setCopilotLoading] = useState(false);
  const [copilotActiu, setCopilotActiu] = useState(false);
  const [modalFeedback, setModalFeedback] = useState<{
    type: "ok" | "err";
    text: string;
    href?: string;
  } | null>(null);
  const [iaDraft, setIaDraft] = useState<{
    id: string;
    titol: string;
    resum_tecnic?: string | null;
    feines_historiques_similars?: number;
    linies: { concepte: string; quantitat: number; preu_unitari?: number | null; total?: number | null }[];
    total_estimat?: number | null;
  } | null>(null);

  // Catalogs (100% real from API)
  const [clients, setClients] = useState<any[]>([]);
  const [finques, setFinques] = useState<any[]>([]);
  const [operaris, setOperaris] = useState<any[]>([]);
  const [vehicles, setVehicles] = useState<any[]>([]);
  const [planols, setPlanols] = useState<any[]>([]);
  const [articles, setArticles] = useState<any[]>([]);
  const [eines, setEines] = useState<any[]>([]);
  const [magatzems, setMagatzems] = useState<any[]>([]);
  const [selectedMagatzemId, setSelectedMagatzemId] = useState<string>("");
  const [prioritat, setPrioritat] = useState<"BAIXA" | "NORMAL" | "ALTA" | "URGENT">("NORMAL");

  // Core OT structured form state
  const [formData, setFormData] = useState({
    codi: initialFeina?.codi || `OT-${Math.floor(1000 + Math.random() * 9000)}`,
    versio: initialFeina?.versio || 1,
    titol: initialFeina?.titol || initialPressupost?.titol || "",
    descripcio: initialFeina?.descripcio || initialPressupost?.descripcio || "",
    adreca: initialFeina?.adreca || initialPressupost?.adreca_obra || "",
    client_id: initialClientId || initialPressupost?.client_id || "",
    finca_id: initialPressupost?.finca_id || "",
    cap_de_colla_id: initialFeina?.cap_de_colla_id || "",
    vehicle_id: initialFeina?.vehicle_id || initialPressupost?.vehicle_id || "",
    planol_id: "",
    data_planificacio:
      initialFeina?.data_planificacio || new Date().toISOString().split("T")[0],
    estat: initialFeina?.estat || "PENDENT",
    latitud: initialFeina?.latitud ?? (null as number | null),
    longitud: initialFeina?.longitud ?? (null as number | null),
  });

  // Structured scheduling & economics fields (NEVER dumped into descripcio!)
  const [horesPrevistes, setHoresPrevistes] = useState<string>(
    initialFeina?.hores_previstes && initialFeina.hores_previstes > 0
      ? String(initialFeina.hores_previstes)
      : ""
  );
  const [horaInici, setHoraInici] = useState<string>("");
  const [horaFi, setHoraFi] = useState<string>("");
  const [franjaManual, setFranjaManual] = useState<boolean>(false);
  const [originalHoraIniciIso, setOriginalHoraIniciIso] = useState<string | null>(null);
  const [originalHoraFiIso, setOriginalHoraFiIso] = useState<string | null>(null);
  const [preuHoraInput, setPreuHoraInput] = useState<string>(
    initialFeina?.preu_venda_hora_aplicat != null
      ? String(initialFeina.preu_venda_hora_aplicat)
      : ""
  );
  const [kmImputatsInput, setKmImputatsInput] = useState<string>(
    initialFeina?.km_imputats ? String(initialFeina.km_imputats) : "0"
  );
  const [importPressupostatNet, setImportPressupostatNet] = useState<number>(
    Number(initialFeina?.import_pressupostat_net ?? initialPressupost?.base_imposable ?? 0)
  );
  const [importPressupostatBrut, setImportPressupostatBrut] = useState<number>(
    Number(initialFeina?.import_pressupostat ?? initialPressupost?.total ?? 0)
  );

  // Crew / Quadrilla
  const [collaOperariIds, setCollaOperariIds] = useState<string[]>([]);
  const [selectedCollaCandidate, setSelectedCollaCandidate] = useState<string>("");

  // Picking (Materials)
  const [liniesPicking, setLiniesPicking] = useState<PickingLiniaForm[]>([]);
  const [unmatchedPressupostMaterials, setUnmatchedPressupostMaterials] = useState<
    Array<{ concepte: string; quantitat: number; preu_unitari: number }>
  >([]);
  const [filtreFamilia, setFiltreFamilia] = useState<string>("TOTES");
  const [cercaArticle, setCercaArticle] = useState<string>("");
  const [selectedArticle, setSelectedArticle] = useState<any | null>(null);
  const [currentQty, setCurrentQty] = useState<number>(1);
  const [isArticleDropdownOpen, setIsArticleDropdownOpen] = useState(false);
  const articleComboboxRef = useRef<HTMLDivElement>(null);

  // Eines en Custòdia
  const [selectedEinaIds, setSelectedEinaIds] = useState<string[]>([]);
  const [unmatchedPressupostEines, setUnmatchedPressupostEines] = useState<string[]>([]);
  const [cercaEina, setCercaEina] = useState<string>("");
  const [selectedEina, setSelectedEina] = useState<any | null>(null);
  const [isEinaDropdownOpen, setIsEinaDropdownOpen] = useState(false);
  const einaComboboxRef = useRef<HTMLDivElement>(null);

  // Loaded Pressupost source (when mode === FROM_PRESSUPOST)
  const [pressupostSource, setPressupostSource] = useState<PressupostItem | null>(
    initialPressupost || null
  );

  // Conciliació 360° & Evidències (for EDIT / VIEW_360)
  const [loadedFeina, setLoadedFeina] = useState<Feina | null>(initialFeina || null);
  const [conc, setConc] = useState<ConciliacioCompleta | null>(null);
  const [loadingConc, setLoadingConc] = useState(false);
  const [evidenciesUrls, setEvidenciesUrls] = useState<Record<string, string>>({});
  const [lightboxUrl, setLightboxUrl] = useState<{ url: string; titol: string } | null>(null);
  const [checklist, setChecklist] = useState<Record<string, boolean>>({});
  const [horesConcEdit, setHoresConcEdit] = useState<string>("0");
  const [kmConcEdit, setKmConcEdit] = useState<string>("0");
  const [notesValidacio, setNotesValidacio] = useState<string>("");
  const [ajustosPicking, setAjustosPicking] = useState<Record<string, AjustPickingDraft>>({});
  const [validant, setValidant] = useState(false);
  const [enviantPrefactura, setEnviantPrefactura] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);
  const [facturaModalId, setFacturaModalId] = useState<string | null>(null);

  const isLockedByInvoice = Boolean(
    conc?.factura && conc.factura.estat_document !== "ESBORRANY_PREFACTURA"
  );

  // Close autocomplete dropdowns on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (articleComboboxRef.current && !articleComboboxRef.current.contains(e.target as Node)) {
        setIsArticleDropdownOpen(false);
      }
      if (einaComboboxRef.current && !einaComboboxRef.current.contains(e.target as Node)) {
        setIsEinaDropdownOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const carregarConciliacio = useCallback(async (otId: string) => {
    setLoadingConc(true);
    try {
      const data = await apiFetch<ConciliacioCompleta>(`/gestio/feines/${otId}/conciliacio`);
      setConc(data);
      setChecklist(data.validacio?.checklist_conciliacio || {});
      setHoresConcEdit(String(data.temps_i_gps?.hores_reals ?? 0));
      setKmConcEdit(String(data.vehicle?.km_imputats ?? data.resum_comercial?.km_imputats ?? 0));
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
    } catch {
      setConc(null);
    } finally {
      setLoadingConc(false);
    }
  }, []);

  // Boot: load catalogs + existing OT or source Pressupost
  useEffect(() => {
    if (!isOpen) return;
    let cancelled = false;
    setBootLoading(true);
    setModalFeedback(null);
    setActionError(null);
    setActionSuccess(null);

    Promise.all([
      apiFetch<any>("/gestio/clients?limit=250").catch(() => []),
      apiFetch<any>("/gestio/operaris").catch(() => []),
      apiFetch<any>("/gestio/flota").catch(() => []),
      apiFetch<any>("/gestio/planols").catch(() => []),
      apiFetch<any>("/gestio/magatzem/articles?limit=300").catch(() => []),
      apiFetch<any>("/gestio/magatzem/eines").catch(() => []),
      apiFetch<any>("/gestio/magatzem/magatzems").catch(() => []),
      apiFetch<any>("/gestio/configuracio/empresa").catch(() => null),
      apiFetch<any>("/gestio/configuracio/barema").catch(() => null),
      isExistingOT && resolvedFeinaId
        ? apiFetch<any>(`/gestio/feines/${resolvedFeinaId}`).catch(() => null)
        : Promise.resolve(null),
      isFromPressupost && initialPressupost?.id
        ? apiFetch<PressupostItem>(`/gestio/pressupostos/${initialPressupost.id}`).catch(
            () => initialPressupost
          )
        : Promise.resolve(null),
    ])
      .then(
        ([
          clientsData,
          operarisData,
          flotaData,
          planolsData,
          articlesData,
          einesData,
          magatzemsData,
          empresaCfg,
          baremaCfg,
          feinaData,
          presFull,
        ]) => {
          if (cancelled) return;
          const cliList = Array.isArray(clientsData) ? clientsData : clientsData?.items || [];
          const opsList = (
            Array.isArray(operarisData) ? operarisData : operarisData?.operaris || []
          ).filter((o: any) => !o.estat || o.estat === "ACTIU");
          const vehList = Array.isArray(flotaData) ? flotaData : flotaData?.vehicles || [];
          const planList = Array.isArray(planolsData) ? planolsData : [];
          const artList = Array.isArray(articlesData) ? articlesData : [];
          const einaList = Array.isArray(einesData) ? einesData : [];
          const magList = Array.isArray(magatzemsData)
            ? magatzemsData
            : magatzemsData?.magatzems || [];

          setClients(cliList);
          setOperaris(opsList);
          setVehicles(vehList);
          setPlanols(planList);
          setArticles(artList);
          setEines(einaList);
          setMagatzems(magList);
          setCopilotActiu(
            Boolean(empresaCfg?.feature_copilot_ia === true && empresaCfg?.node_ia_actiu === true)
          );

          const baremaRate =
            baremaCfg?.preu_hora_standard_eur != null
              ? Number(baremaCfg.preu_hora_standard_eur)
              : 0;

          // Case A: Existing OT (EDIT / VIEW_360)
          if (isExistingOT && feinaData) {
            setLoadedFeina(feinaData);
            setFormData({
              codi: feinaData.codi || "",
              versio: feinaData.versio || 1,
              titol: feinaData.titol || "",
              descripcio: feinaData.descripcio || "",
              adreca: feinaData.adreca || "",
              client_id: feinaData.client_id || "",
              finca_id: feinaData.finca_id || "",
              cap_de_colla_id: feinaData.cap_de_colla_id || "",
              vehicle_id: feinaData.vehicle_id || "",
              planol_id: feinaData.planol_id || "",
              data_planificacio:
                feinaData.data_planificacio || new Date().toISOString().split("T")[0],
              estat: feinaData.estat || "PENDENT",
              latitud: feinaData.latitud ?? null,
              longitud: feinaData.longitud ?? null,
            });
            setOriginalHoraIniciIso(feinaData.hora_inici_prevista || null);
            setOriginalHoraFiIso(feinaData.hora_fi_prevista || null);
            setFranjaManual(false);
            setHoresPrevistes(
              feinaData.hores_previstes && Number(feinaData.hores_previstes) > 0
                ? String(Number(feinaData.hores_previstes))
                : ""
            );
            if (feinaData.hora_inici_prevista) {
              const d = new Date(feinaData.hora_inici_prevista);
              if (!Number.isNaN(d.getTime())) {
                setHoraInici(
                  `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`
                );
              }
            }
            if (feinaData.hora_fi_prevista) {
              const d = new Date(feinaData.hora_fi_prevista);
              if (!Number.isNaN(d.getTime())) {
                setHoraFi(
                  `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`
                );
              }
            }
            setPreuHoraInput(
              feinaData.preu_venda_hora_aplicat != null
                ? String(Number(feinaData.preu_venda_hora_aplicat))
                : baremaRate > 0
                  ? String(baremaRate)
                  : ""
            );
            setKmImputatsInput(String(Number(feinaData.km_imputats || 0)));
            setImportPressupostatBrut(Number(feinaData.import_pressupostat || 0));
            setImportPressupostatNet(Number(feinaData.import_pressupostat_net || 0));

            if (Array.isArray(feinaData.linies_picking)) {
              setLiniesPicking(
                feinaData.linies_picking.map((lp: any) => {
                  const artDef = artList.find((a: any) => a.id === lp.article_id);
                  const pmp = Number(
                    artDef?.preu_cost_mitja || artDef?.preu_cost || 0
                  );
                  return {
                    id: lp.id,
                    article_id: lp.article_id,
                    article_nom: lp.article_nom || artDef?.nom || "Article",
                    referencia_inventari:
                      lp.referencia_inventari || artDef?.referencia_inventari || "S/REF",
                    quantitat_prevista: Number(lp.quantitat_prevista) || 1,
                    unitat_mesura: lp.unitat_mesura || artDef?.unitat_mesura || "UNITAT",
                    preu_venda_unitari: Number(
                      lp.preu_venda_unitari ?? artDef?.preu_venda ?? 0
                    ),
                    preu_cost_pmp: pmp,
                    estoc_disponible: Number(
                      lp.estoc_disponible ?? artDef?.estoc_disponible ?? artDef?.estoc_real ?? 0
                    ),
                    magatzem_id: lp.magatzem_id || null,
                  };
                })
              );
            }
            if (Array.isArray(feinaData.eina_ids)) {
              setSelectedEinaIds(feinaData.eina_ids);
            } else if (Array.isArray(feinaData.eines)) {
              setSelectedEinaIds(feinaData.eines.map((e: any) => e.id));
            }
            if (Array.isArray(feinaData.operaris_ids)) {
              setCollaOperariIds(
                feinaData.operaris_ids.filter((id: string) => id !== feinaData.cap_de_colla_id)
              );
            }
            if (feinaData.client_id) {
              apiFetch<any>(`/gestio/clients/${feinaData.client_id}/fitxa360`)
                .then((res) => !cancelled && setFinques(res?.finques || []))
                .catch(() => !cancelled && setFinques([]));
            }
            carregarConciliacio(feinaData.id);
          }

          // Case B: Converting an accepted Pressupost -> OT (FROM_PRESSUPOST)
          else if (isFromPressupost && presFull) {
            setPressupostSource(presFull);
            const liniesP: PressupostLinia[] = Array.isArray(presFull.linies)
              ? presFull.linies
              : [];

            // 1. Hours & hourly rate from MA_OBRA lines (fallback MAQUINARIA)
            let hMaObra = 0;
            let hMaObraPreu = 0;
            let impMaObraPreu = 0;
            let hMaqLin = 0;
            const opIdsFromLines: string[] = [];

            for (const lin of liniesP) {
              if (lin.operari_id && !opIdsFromLines.includes(lin.operari_id)) {
                opIdsFromLines.push(lin.operari_id);
              }
              const q = Math.max(0, Number(lin.quantitat || 0));
              const pu = Math.max(0, Number(lin.preu_unitari || 0));
              const dto = Math.min(100, Math.max(0, Number(lin.descompte_pct || 0)));
              const sub = lin.subtotal != null ? Number(lin.subtotal) : q * pu * (1 - dto / 100);
              if (esLiniaMaObra(lin)) {
                hMaObra += q;
                if (q > 0 && pu > 0) {
                  hMaObraPreu += q;
                  impMaObraPreu += sub;
                }
              } else if ((lin.tipus_linia || "").toUpperCase() === "MAQUINARIA") {
                hMaqLin += q;
              }
            }

            // 2. Vehicle & km from slots / top-level / lines
            const slots = Array.isArray(presFull.vehicles_desplacaments)
              ? presFull.vehicles_desplacaments
              : [];
            let vehId = presFull.vehicle_id || "";
            if (!vehId) {
              const slWithVeh = slots.find((s) => Boolean(s.vehicle_id));
              if (slWithVeh?.vehicle_id) vehId = slWithVeh.vehicle_id;
            }
            if (!vehId) {
              const linWithVeh = liniesP.find((l) => Boolean(l.vehicle_id));
              if (linWithVeh?.vehicle_id) vehId = linWithVeh.vehicle_id;
            }
            let kmSum = 0;
            let hMaqSlots = 0;
            if (slots.length > 0) {
              for (const sl of slots) {
                kmSum += Math.max(0, Number(sl.km || 0));
                hMaqSlots += Math.max(0, Number(sl.hores || 0));
              }
            } else {
              kmSum = Math.max(0, Number(presFull.desplacament_km || 0));
              hMaqSlots = Math.max(0, Number(presFull.desplacament_hores || 0));
            }

            const horesTotals =
              Math.round((hMaObra > 0 ? hMaObra : hMaqLin > 0 ? hMaqLin : hMaqSlots) * 100) /
              100;
            const rateFinal =
              hMaObraPreu > 0 && impMaObraPreu > 0
                ? Math.round((impMaObraPreu / hMaObraPreu) * 100) / 100
                : baremaRate;

            // 3. Materials -> structured Picking lines (by article_id, [REF], or name)
            const artById = new Map<string, any>(artList.map((a: any) => [a.id, a]));
            const artByRef = new Map<string, any>();
            const artByNom = new Map<string, any>();
            for (const a of artList) {
              if (a.referencia_inventari) {
                artByRef.set(String(a.referencia_inventari).trim().toLowerCase(), a);
              }
              if (a.nom) {
                artByNom.set(String(a.nom).trim().toLowerCase(), a);
              }
            }

            const pickingAgg = new Map<string, PickingLiniaForm>();
            const unmatchedMats: Array<{
              concepte: string;
              quantitat: number;
              preu_unitari: number;
            }> = [];

            for (const lin of liniesP) {
              if (!esLiniaMaterial(lin)) continue;
              const qt = Math.max(0.001, Number(lin.quantitat || 1));
              let matchedArt = lin.article_id ? artById.get(lin.article_id) : null;
              if (!matchedArt) {
                const rawC = (lin.concepte || "").trim();
                const mRef = RE_REF_PREFIX.exec(rawC);
                if (mRef) {
                  matchedArt =
                    artByRef.get(mRef[1].trim().toLowerCase()) ||
                    artByNom.get(rawC.slice(mRef[0].length).trim().toLowerCase()) ||
                    null;
                } else if (rawC) {
                  matchedArt = artByNom.get(rawC.toLowerCase()) || null;
                }
              }

              if (matchedArt) {
                const prev = pickingAgg.get(matchedArt.id);
                if (prev) {
                  prev.quantitat_prevista =
                    Math.round((prev.quantitat_prevista + qt) * 1000) / 1000;
                } else {
                  pickingAgg.set(matchedArt.id, {
                    article_id: matchedArt.id,
                    article_nom: matchedArt.nom,
                    referencia_inventari: matchedArt.referencia_inventari || "S/REF",
                    quantitat_prevista: qt,
                    unitat_mesura: matchedArt.unitat_mesura || "UNITAT",
                    preu_venda_unitari: Number(
                      lin.preu_unitari > 0 ? lin.preu_unitari : matchedArt.preu_venda ?? 0
                    ),
                    preu_cost_pmp: Number(
                      matchedArt.preu_cost_mitja || matchedArt.preu_cost || 0
                    ),
                    estoc_disponible: Number(
                      matchedArt.estoc_disponible ?? matchedArt.estoc_real ?? 0
                    ),
                  });
                }
              } else if (lin.concepte?.trim()) {
                unmatchedMats.push({
                  concepte: lin.concepte.trim(),
                  quantitat: qt,
                  preu_unitari: Number(lin.preu_unitari || 0),
                });
              }
            }

            // 4. Tools -> structured EinaCustodia IDs (by UUID, S/N, or name)
            const einaById = new Map<string, any>(einaList.map((e: any) => [e.id, e]));
            const einaBySn = new Map<string, any>();
            const einaByNom = new Map<string, any>();
            for (const e of einaList) {
              if (e.numero_serie) einaBySn.set(String(e.numero_serie).trim().toLowerCase(), e);
              if (e.nom) einaByNom.set(String(e.nom).trim().toLowerCase(), e);
            }

            const resolvedEinaIds: string[] = [];
            const unmatchedTools: string[] = [];
            const pushEina = (id: string) => {
              if (id && einaById.has(id) && !resolvedEinaIds.includes(id)) {
                resolvedEinaIds.push(id);
              }
            };
            for (const eid of presFull.eines_ids || []) {
              if (RE_UUID.test(eid)) pushEina(eid);
            }
            for (const er of presFull.eines_resum || []) {
              if (er.id && RE_UUID.test(er.id) && einaById.has(er.id)) {
                pushEina(er.id);
              } else {
                const m =
                  (er.numero_serie ? einaBySn.get(er.numero_serie.trim().toLowerCase()) : null) ||
                  (er.nom ? einaByNom.get(er.nom.trim().toLowerCase()) : null);
                if (m) {
                  pushEina(m.id);
                } else if (er.nom?.trim()) {
                  unmatchedTools.push(er.nom.trim());
                }
              }
            }
            for (const lin of liniesP) {
              if (lin.eina_id && RE_UUID.test(lin.eina_id)) pushEina(lin.eina_id);
            }

            // 5. Operators (budgets normally have NO operari — user will pick Cap de Colla here)
            const activeOpIds = opIdsFromLines.filter((id) =>
              opsList.some((o: any) => o.id === id)
            );
            const capInicial = activeOpIds[0] || "";
            const suportInicial = activeOpIds.slice(1);

            const cliObj = cliList.find((c: any) => c.id === presFull.client_id);
            const adrecaObra =
              presFull.adreca_obra ||
              presFull.client_adreca ||
              cliObj?.adreca_fiscal ||
              "";

            setFormData({
              codi: `OT-${Math.floor(1000 + Math.random() * 9000)}`,
              versio: 1,
              titol: presFull.titol || `Execució ${presFull.numero}`,
              descripcio: (presFull.descripcio || "").trim(),
              adreca: adrecaObra,
              client_id: presFull.client_id || "",
              finca_id: presFull.finca_id || "",
              cap_de_colla_id: capInicial,
              vehicle_id: vehId,
              planol_id: "",
              data_planificacio: new Date().toISOString().split("T")[0],
              estat: capInicial ? "ASSIGNADA" : "PENDENT",
              latitud: null,
              longitud: null,
            });
            setCollaOperariIds(suportInicial);
            setHoresPrevistes(horesTotals > 0 ? String(horesTotals) : "");
            if (horesTotals > 0) {
              setHoraInici("08:00");
              setHoraFi(addHoursToTime("08:00", horesTotals));
            }
            setPreuHoraInput(rateFinal > 0 ? String(rateFinal) : "");
            setKmImputatsInput(String(Math.round(kmSum)));
            setImportPressupostatNet(Number(presFull.base_imposable || presFull.total || 0));
            setImportPressupostatBrut(Number(presFull.total || 0));
            setLiniesPicking(Array.from(pickingAgg.values()));
            setUnmatchedPressupostMaterials(unmatchedMats);
            setSelectedEinaIds(resolvedEinaIds);
            setUnmatchedPressupostEines(unmatchedTools);

            if (presFull.client_id) {
              apiFetch<any>(`/gestio/clients/${presFull.client_id}/fitxa360`)
                .then((res) => !cancelled && setFinques(res?.finques || []))
                .catch(() => !cancelled && setFinques([]));
            }
          }

          // Case C: CREATE fresh OT
          else {
            if (baremaRate > 0) {
              setPreuHoraInput(String(baremaRate));
            }
            if (initialClientId) {
              apiFetch<any>(`/gestio/clients/${initialClientId}/fitxa360`)
                .then((res) => !cancelled && setFinques(res?.finques || []))
                .catch(() => !cancelled && setFinques([]));
            }
          }
        }
      )
      .finally(() => {
        if (!cancelled) setBootLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [isOpen, isExistingOT, isFromPressupost, resolvedFeinaId, initialPressupost, initialClientId, carregarConciliacio]);

  // Load authenticated evidence images (fotos QA + signatura + geovalla)
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
      if (!cancelled) setEvidenciesUrls(nextMap);
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

  // Client change handler -> load finques
  const handleClientChange = (clientId: string) => {
    setFormData((prev) => ({ ...prev, client_id: clientId, finca_id: "" }));
    if (clientId) {
      apiFetch<any>(`/gestio/clients/${clientId}/fitxa360`)
        .then((data) => setFinques(data?.finques || []))
        .catch(() => setFinques([]));
    } else {
      setFinques([]);
    }
  };

  // Filtered catalogs for comboboxes
  const familiesArticles = useMemo(
    () =>
      Array.from(
        new Set(
          articles.map((a) => (a.familia ? String(a.familia).trim() : "GENERAL")).filter(Boolean)
        )
      ).sort(),
    [articles]
  );

  const filteredArticles = useMemo(() => {
    const term = cercaArticle.trim().toLowerCase();
    return articles
      .filter((art) => {
        const fam = art.familia ? String(art.familia).trim() : "GENERAL";
        if (filtreFamilia !== "TOTES" && fam !== filtreFamilia) return false;
        if (!term) return true;
        return (
          (art.nom || "").toLowerCase().includes(term) ||
          (art.referencia_inventari || "").toLowerCase().includes(term)
        );
      })
      .slice(0, 12);
  }, [articles, filtreFamilia, cercaArticle]);

  const filteredEines = useMemo(() => {
    const term = cercaEina.trim().toLowerCase();
    return eines
      .filter((e) => !selectedEinaIds.includes(e.id))
      .filter((e) => {
        if (!term) return true;
        return (
          (e.nom || "").toLowerCase().includes(term) ||
          (e.model || "").toLowerCase().includes(term) ||
          (e.numero_serie || "").toLowerCase().includes(term)
        );
      })
      .slice(0, 12);
  }, [eines, selectedEinaIds, cercaEina]);

  // Driver license compatibility live check (FR-012)
  const selectedCapObj = useMemo(
    () => operaris.find((o) => o.id === formData.cap_de_colla_id) || null,
    [operaris, formData.cap_de_colla_id]
  );
  const selectedVehicleObj = useMemo(
    () => vehicles.find((v) => v.id === formData.vehicle_id) || null,
    [vehicles, formData.vehicle_id]
  );

  const avísCarnet = useMemo(() => {
    if (!selectedCapObj || !selectedVehicleObj) return null;
    const req = String(selectedVehicleObj.carnet_necessari || "B").trim().toUpperCase();
    if (!req || req === "N/A") return null;
    const opPerm = String(selectedCapObj.carnet_conduir || "B").trim().toUpperCase();
    const allowed = JERARQUIA_CARNETS[req] || [req];
    if (!allowed.includes(opPerm)) {
      return `El vehicle ${selectedVehicleObj.matricula} requereix permís ${req}, però ${selectedCapObj.nom} té permís ${opPerm}.`;
    }
    return null;
  }, [selectedCapObj, selectedVehicleObj]);

  // Real-time economic evaluation (Commercial + Internal BOSS/SECRETARIA)
  const economiaLive = useMemo(() => {
    const hPrev = Math.max(0, parseFloat(horesPrevistes) || 0);
    const hReal = Number(conc?.temps_i_gps?.hores_reals ?? loadedFeina?.hores_imputades_facturables ?? 0);
    const ratePvp = Math.max(0, parseFloat(preuHoraInput) || 0);
    const km = Math.max(0, parseInt(kmImputatsInput || "0", 10) || 0);

    const maObraPrevPvp = Math.round(hPrev * ratePvp * 100) / 100;
    const maObraRealPvp = Math.round(hReal * ratePvp * 100) / 100;

    const materialsPvp =
      Math.round(
        liniesPicking.reduce(
          (sum, l) => sum + Number(l.quantitat_prevista || 0) * Number(l.preu_venda_unitari || 0),
          0
        ) * 100
      ) / 100;

    const materialsPmp =
      Math.round(
        liniesPicking.reduce(
          (sum, l) => sum + Number(l.quantitat_prevista || 0) * Number(l.preu_cost_pmp || 0),
          0
        ) * 100
      ) / 100;

    const costHoraOp = Number(
      selectedCapObj?.cost_hora_eur ?? selectedCapObj?.cost_hora_referencia ?? 0
    );
    const costMaObraPrev =
      conc?.resum_intern?.cost_ma_obra_previst != null
        ? Number(conc.resum_intern.cost_ma_obra_previst)
        : Math.round(hPrev * costHoraOp * 100) / 100;

    const costKmVeh = Number(selectedVehicleObj?.cost_per_km_eur || 0) > 0
      ? Number(selectedVehicleObj.cost_per_km_eur)
      : 0.32;
    const costFlota =
      conc?.resum_intern?.cost_flota_real != null
        ? Number(conc.resum_intern.cost_flota_real)
        : Math.round(km * costKmVeh * 100) / 100;

    const tiquetsCamp = Number(conc?.tiquets?.import_total ?? 0);
    const totalPrevistPvp = Math.round((maObraPrevPvp + materialsPvp) * 100) / 100;
    const baseIngressos =
      importPressupostatNet > 0
        ? importPressupostatNet
        : totalPrevistPvp;

    const costTotalPrevist = Math.round((materialsPmp + costMaObraPrev + costFlota) * 100) / 100;
    const margePrevistEur = Math.round((baseIngressos - costTotalPrevist) * 100) / 100;
    const margePrevistPct =
      baseIngressos > 0 ? Math.round((margePrevistEur / baseIngressos) * 10000) / 100 : 0;

    return {
      hPrev,
      hReal,
      ratePvp,
      km,
      maObraPrevPvp,
      maObraRealPvp,
      materialsPvp,
      materialsPmp,
      costMaObraPrev,
      costFlota,
      tiquetsCamp,
      totalPrevistPvp,
      baseIngressos,
      costTotalPrevist,
      margePrevistEur,
      margePrevistPct,
    };
  }, [
    horesPrevistes,
    preuHoraInput,
    kmImputatsInput,
    liniesPicking,
    selectedCapObj,
    selectedVehicleObj,
    importPressupostatNet,
    conc,
    loadedFeina,
  ]);

  // Handlers for hours <-> start/end bidirectional sync
  const handleHoresPrevistesChange = (rawVal: string) => {
    setHoresPrevistes(rawVal);
    setFranjaManual(true);
    const hNum = parseFloat(rawVal);
    if (!Number.isNaN(hNum) && hNum > 0) {
      const baseStart = horaInici || "08:00";
      if (!horaInici) setHoraInici(baseStart);
      setHoraFi(addHoursToTime(baseStart, hNum));
    }
  };

  const handleHoraIniciChange = (val: string) => {
    setHoraInici(val);
    setFranjaManual(true);
    const hNum = parseFloat(horesPrevistes);
    if (val && horaFi) {
      const diff = diffHoursBetweenTimes(val, horaFi);
      if (diff > 0) setHoresPrevistes(String(diff));
    } else if (val && !Number.isNaN(hNum) && hNum > 0) {
      setHoraFi(addHoursToTime(val, hNum));
    }
  };

  const handleHoraFiChange = (val: string) => {
    setHoraFi(val);
    setFranjaManual(true);
    if (horaInici && val) {
      const diff = diffHoursBetweenTimes(horaInici, val);
      if (diff > 0) setHoresPrevistes(String(diff));
    }
  };

  // Crew handlers
  const addOperariToColla = (opId?: string) => {
    const idToAdd = opId || selectedCollaCandidate;
    if (!idToAdd || idToAdd === formData.cap_de_colla_id) return;
    if (!collaOperariIds.includes(idToAdd)) {
      setCollaOperariIds((prev) => [...prev, idToAdd]);
    }
    setSelectedCollaCandidate("");
  };

  const removeOperariFromColla = (idToRemove: string) => {
    setCollaOperariIds((prev) => prev.filter((id) => id !== idToRemove));
  };

  // Picking handlers
  const handleSelectArticle = (art: any) => {
    setSelectedArticle(art);
    setCercaArticle(`[${art.referencia_inventari}] ${art.nom}`);
    setIsArticleDropdownOpen(false);
  };

  const handleClearArticle = () => {
    setSelectedArticle(null);
    setCercaArticle("");
    setIsArticleDropdownOpen(false);
  };

  const addLiniaPicking = () => {
    if (!selectedArticle || currentQty <= 0) return;
    const estocDisp = Number(
      selectedArticle.estoc_disponible ?? selectedArticle.estoc_real ?? 0
    );
    const existingIdx = liniesPicking.findIndex((l) => l.article_id === selectedArticle.id);
    if (existingIdx >= 0) {
      setLiniesPicking((prev) =>
        prev.map((l, i) =>
          i === existingIdx ? { ...l, quantitat_prevista: l.quantitat_prevista + currentQty } : l
        )
      );
    } else {
      setLiniesPicking((prev) => [
        ...prev,
        {
          article_id: selectedArticle.id,
          article_nom: selectedArticle.nom,
          referencia_inventari: selectedArticle.referencia_inventari || "S/REF",
          quantitat_prevista: currentQty,
          unitat_mesura: selectedArticle.unitat_mesura || "UNITAT",
          preu_venda_unitari: Number(selectedArticle.preu_venda || 0),
          preu_cost_pmp: Number(selectedArticle.preu_cost_mitja || selectedArticle.preu_cost || 0),
          estoc_disponible: estocDisp,
          magatzem_id: selectedMagatzemId || null,
        },
      ]);
    }
    handleClearArticle();
    setCurrentQty(1);
  };

  const updateQtyPicking = (articleId: string, novaQ: number) => {
    if (novaQ <= 0) return;
    setLiniesPicking((prev) =>
      prev.map((l) => (l.article_id === articleId ? { ...l, quantitat_prevista: novaQ } : l))
    );
  };

  const removeLiniaPicking = (articleId: string) => {
    setLiniesPicking((prev) => prev.filter((l) => l.article_id !== articleId));
  };

  // Tool handlers
  const handleSelectEina = (eina: any) => {
    setSelectedEina(eina);
    setCercaEina(`${eina.nom} (SN: ${eina.numero_serie})`);
    setIsEinaDropdownOpen(false);
  };

  const addEina = () => {
    if (!selectedEina || selectedEinaIds.includes(selectedEina.id)) return;
    setSelectedEinaIds((prev) => [...prev, selectedEina.id]);
    setSelectedEina(null);
    setCercaEina("");
  };

  const removeEina = (einaId: string) => {
    setSelectedEinaIds((prev) => prev.filter((id) => id !== einaId));
  };

  // Main form submission (handles CREATE, FROM_PRESSUPOST, and EDIT/VIEW_360 save!)
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setModalFeedback(null);

    const adrecaNet = formData.adreca.trim();
    if (!formData.titol.trim()) {
      setModalFeedback({ type: "err", text: "El títol de la intervenció és obligatori." });
      return;
    }
    if (!formData.client_id) {
      setModalFeedback({ type: "err", text: "Selecciona un client titular." });
      return;
    }
    if (!adrecaNet) {
      setModalFeedback({
        type: "err",
        text: "L'adreça o coordenades GPS de l'obra són obligatòries.",
      });
      return;
    }
    if (isFromPressupost && !formData.cap_de_colla_id) {
      setModalFeedback({
        type: "err",
        text: "Assigna un Cap de Colla / Operari responsable abans de crear l'Ordre de Treball des del pressupost.",
      });
      return;
    }
    if (avísCarnet) {
      setModalFeedback({ type: "err", text: avísCarnet });
      return;
    }

    setSaving(true);
    try {
      const geo = geocodificarAdreca(
        adrecaNet,
        formData.latitud ?? undefined,
        formData.longitud ?? undefined
      );
      const hPrevNum = parseFloat(horesPrevistes);
      const hasHoresPrev = !Number.isNaN(hPrevNum) && hPrevNum > 0;
      const rateNum = parseFloat(preuHoraInput);
      const kmNum = Math.max(0, parseInt(kmImputatsInput || "0", 10) || 0);

      const horaIniciIso =
        isExistingOT && !franjaManual && originalHoraIniciIso
          ? originalHoraIniciIso
          : horaInici
            ? `${formData.data_planificacio}T${horaInici}:00`
            : null;
      const horaFiIso =
        isExistingOT && !franjaManual && originalHoraFiIso
          ? originalHoraFiIso
          : horaFi && diffHoursBetweenTimes(horaInici, horaFi) > 0
            ? `${formData.data_planificacio}T${horaFi}:00`
            : null;

      const allOperarisIds = Array.from(
        new Set([formData.cap_de_colla_id, ...collaOperariIds].filter(Boolean))
      );

      if (isFromPressupost && pressupostSource) {
        const convPayload = {
          codi: formData.codi.trim() || undefined,
          titol: formData.titol.trim(),
          descripcio: formData.descripcio.trim() || null,
          adreca: adrecaNet,
          finca_id: formData.finca_id || null,
          planol_id: formData.planol_id || null,
          data_planificacio: formData.data_planificacio,
          hores_previstes: hasHoresPrev ? hPrevNum : null,
          hora_inici_prevista: horaIniciIso,
          hora_fi_prevista: horaFiIso,
          preu_venda_hora_aplicat: !Number.isNaN(rateNum) && rateNum >= 0 ? rateNum : null,
          cap_de_colla_id: formData.cap_de_colla_id || null,
          operaris_ids: allOperarisIds,
          vehicle_id: formData.vehicle_id || null,
          km_imputats: kmNum,
          eina_ids: selectedEinaIds,
          magatzem_id: selectedMagatzemId || null,
          linies_picking: liniesPicking.map((l) => ({
            article_id: l.article_id,
            quantitat_prevista: Number(l.quantitat_prevista),
            magatzem_id: l.magatzem_id || selectedMagatzemId || null,
          })),
          latitud: geo.lat,
          longitud: geo.lng,
          forcar_si_pendent: pressupostSource.estat === "PENDENT",
        };

        const res = await apiFetch<{ ordre_treball_id: string; codi_ot: string }>(
          `/gestio/pressupostos/${pressupostSource.id}/convertir-ot`,
          {
            method: "POST",
            body: JSON.stringify(convPayload),
          }
        );
        onSuccess?.({ id: res.ordre_treball_id, codi: res.codi_ot });
        onClose();
        return;
      }

      if (isExistingOT && resolvedFeinaId) {
        const updPayload = {
          titol: formData.titol.trim(),
          descripcio: formData.descripcio.trim() || null,
          client_id: formData.client_id || null,
          finca_id: formData.finca_id || null,
          planol_id: formData.planol_id || null,
          adreca: adrecaNet,
          data_planificacio: formData.data_planificacio,
          hores_previstes: hasHoresPrev ? hPrevNum : null,
          hora_inici_prevista: horaIniciIso,
          hora_fi_prevista: horaFiIso,
          preu_venda_hora_aplicat: !Number.isNaN(rateNum) && rateNum >= 0 ? rateNum : null,
          km_imputats: kmNum,
          estat: formData.estat,
          cap_de_colla_id: formData.cap_de_colla_id || null,
          operaris_ids: allOperarisIds,
          vehicle_id: formData.vehicle_id || null,
          latitud: geo.lat,
          longitud: geo.lng,
          versio: formData.versio,
          eina_ids: selectedEinaIds,
          linies_picking: liniesPicking.map((l) => ({
            article_id: l.article_id,
            quantitat_prevista: Number(l.quantitat_prevista),
            magatzem_id: l.magatzem_id || selectedMagatzemId || null,
          })),
        };
        const updated = await apiFetch<Feina>(`/gestio/feines/${resolvedFeinaId}`, {
          method: "PUT",
          body: JSON.stringify(updPayload),
        });
        setFormData((prev) => ({ ...prev, versio: updated.versio || prev.versio + 1 }));
        setLoadedFeina(updated);
        await carregarConciliacio(resolvedFeinaId);
        setModalFeedback({ type: "ok", text: `Ordre ${updated.codi} actualitzada correctament.` });
        onSuccess?.({ id: updated.id, codi: updated.codi });
        if (mode === "EDIT") {
          onClose();
        }
        return;
      }

      // CREATE new OT
      const createPayload = {
        codi: formData.codi.trim(),
        client_id: formData.client_id,
        finca_id: formData.finca_id || null,
        planol_id: formData.planol_id || null,
        titol: formData.titol.trim(),
        adreca: adrecaNet,
        descripcio: formData.descripcio.trim() || null,
        estat:
          formData.cap_de_colla_id || collaOperariIds.length > 0
            ? "ASSIGNADA"
            : formData.estat || "PENDENT",
        data_planificacio: formData.data_planificacio,
        hores_previstes: hasHoresPrev ? hPrevNum : null,
        hora_inici_prevista: horaIniciIso,
        hora_fi_prevista: horaFiIso,
        preu_venda_hora_aplicat: !Number.isNaN(rateNum) && rateNum >= 0 ? rateNum : null,
        km_imputats: kmNum,
        vehicle_id: formData.vehicle_id || null,
        cap_de_colla_id: formData.cap_de_colla_id || null,
        operaris_ids: allOperarisIds.length > 0 ? allOperarisIds : null,
        latitud: geo.lat,
        longitud: geo.lng,
        eina_ids: selectedEinaIds.length > 0 ? selectedEinaIds : null,
        magatzem_id: selectedMagatzemId || null,
        linies_picking:
          liniesPicking.length > 0
            ? liniesPicking.map((l) => ({
                article_id: l.article_id,
                quantitat_prevista: Number(l.quantitat_prevista),
                magatzem_id: l.magatzem_id || selectedMagatzemId || null,
              }))
            : null,
      };
      const created = await apiFetch<Feina>("/gestio/feines", {
        method: "POST",
        body: JSON.stringify(createPayload),
      });
      onSuccess?.({ id: created.id, codi: created.codi });
      onClose();
    } catch (err: any) {
      setModalFeedback({
        type: "err",
        text: err?.message || "No s'ha pogut desar l'ordre de treball.",
      });
    } finally {
      setSaving(false);
    }
  };

  // Constitutional Triple Button: Create manual budget from current OT sheet
  const handleGenerarPressupost = async () => {
    setModalFeedback(null);
    if (!formData.client_id) {
      setModalFeedback({ type: "err", text: "Selecciona un client abans de generar el pressupost." });
      return;
    }
    const liniesPayload: any[] = [];
    const hPrev = parseFloat(horesPrevistes);
    const rate = parseFloat(preuHoraInput);
    if (!Number.isNaN(hPrev) && hPrev > 0) {
      liniesPayload.push({
        seccio: "Mà d'obra i instal·lació",
        tipus_linia: "MA_OBRA",
        concepte: "Mà d'obra tècnica especialitzada",
        quantitat: hPrev,
        preu_unitari: !Number.isNaN(rate) && rate >= 0 ? rate : 0,
        descompte_pct: 0,
        tipus_iva: 21,
      });
    }
    for (const l of liniesPicking) {
      liniesPayload.push({
        article_id: l.article_id,
        seccio: "Materials i subministraments",
        tipus_linia: "MATERIAL",
        concepte: `[${l.referencia_inventari}] ${l.article_nom}`,
        quantitat: l.quantitat_prevista,
        preu_unitari: l.preu_venda_unitari,
        descompte_pct: 0,
        tipus_iva: 21,
      });
    }
    const totalCalc = liniesPayload.reduce(
      (acc, l) => acc + l.preu_unitari * l.quantitat * (1 + l.tipus_iva / 100),
      0
    );
    setPressupostLoading(true);
    try {
      const suffix = Date.now().toString().slice(-4);
      const numero = `PRE-${formData.codi}-${suffix}`.slice(0, 30);
      const kmVal = parseInt(kmImputatsInput || "0", 10) || 0;
      const created = await apiFetch<any>("/gestio/pressupostos", {
        method: "POST",
        body: JSON.stringify({
          client_id: formData.client_id,
          numero,
          titol: formData.titol.trim() || `Pressupost ${numero}`,
          descripcio: formData.descripcio.trim() || undefined,
          finca_id: formData.finca_id || undefined,
          adreca_obra: formData.adreca.trim() || undefined,
          vehicle_id: formData.vehicle_id || undefined,
          desplacament_km: kmVal > 0 ? kmVal : undefined,
          eines_ids: selectedEinaIds.length > 0 ? selectedEinaIds : undefined,
          total: Number(totalCalc.toFixed(2)),
          linies: liniesPayload.length > 0 ? liniesPayload : undefined,
        }),
      });
      setModalFeedback({
        type: "ok",
        text: `Pressupost ${created.numero} generat (${Number(created.total).toFixed(2)} €).`,
        href: `/gestio/pressupostos?id=${created.id}&revisar=1`,
      });
    } catch (err: any) {
      setModalFeedback({ type: "err", text: err?.message || "Error generant el pressupost." });
    } finally {
      setPressupostLoading(false);
    }
  };

  // Constitutional Triple Button: Copilot IA Budget Draft
  const handlePressupostCopilot = async () => {
    if (!copilotActiu) return;
    setModalFeedback(null);
    const basePrompt = [formData.titol.trim(), formData.descripcio.trim()].filter(Boolean).join(" — ");
    if (!basePrompt) {
      setModalFeedback({
        type: "err",
        text: "Escriu un títol o descripció tècnica perquè el Copilot IA redacti la proposta.",
      });
      return;
    }
    setCopilotLoading(true);
    try {
      const res = await apiFetch<any>("/gestio/pressupostos/generar-ia", {
        method: "POST",
        body: JSON.stringify({ prompt: basePrompt, client_id: formData.client_id || null }),
      });
      if (res?.draft) {
        setIaDraft({
          id: res.id,
          titol: res.draft.titol || "Esborrany Copilot",
          resum_tecnic: res.draft.resum_tecnic,
          feines_historiques_similars: res.draft.feines_historiques_similars,
          linies: Array.isArray(res.draft.linies) ? res.draft.linies : [],
          total_estimat: res.draft.total_estimat ?? null,
        });
        setModalFeedback({
          type: "ok",
          text: res.missatge || "Esborrany PENDENT_AUDITORIA generat al disc sobirà.",
        });
      }
    } catch (err: any) {
      setModalFeedback({ type: "err", text: err?.message || "El Node IA local no respon (503)." });
    } finally {
      setCopilotLoading(false);
    }
  };

  const handleConfirmarEsborranyIA = async () => {
    if (!iaDraft || !formData.client_id) {
      setModalFeedback({ type: "err", text: "Selecciona un client per consolidar el pressupost." });
      return;
    }
    setPressupostLoading(true);
    try {
      const suffix = Date.now().toString().slice(-4);
      const numero = `IA-${formData.codi}-${suffix}`.slice(0, 30);
      const liniesIa = (iaDraft.linies || []).map((l) => ({
        concepte: l.concepte,
        quantitat: Number(l.quantitat || 1),
        preu_unitari: Number(l.preu_unitari ?? 0),
        descompte_pct: 0,
        tipus_iva: 21,
      }));
      const created = await apiFetch<any>("/gestio/pressupostos", {
        method: "POST",
        body: JSON.stringify({
          client_id: formData.client_id,
          numero,
          titol: iaDraft.titol || formData.titol.trim() || `Pressupost ${numero}`,
          descripcio: iaDraft.resum_tecnic || formData.descripcio.trim() || undefined,
          finca_id: formData.finca_id || undefined,
          adreca_obra: formData.adreca.trim() || undefined,
          vehicle_id: formData.vehicle_id || undefined,
          eines_ids: selectedEinaIds.length > 0 ? selectedEinaIds : undefined,
          total: Number(iaDraft.total_estimat ?? 0),
          linies: liniesIa.length > 0 ? liniesIa : undefined,
        }),
      });
      setModalFeedback({
        type: "ok",
        text: `Pressupost ${created.numero} consolidat.`,
        href: `/gestio/pressupostos?id=${created.id}&revisar=1`,
      });
    } catch (err: any) {
      setModalFeedback({ type: "err", text: err?.message || "Error consolidant el pressupost." });
    } finally {
      setPressupostLoading(false);
    }
  };

  // Conciliation validation & Pre-invoicing (3 Rols)
  const handleValidarConciliacio = async () => {
    if (!resolvedFeinaId) return;
    setValidant(true);
    setActionError(null);
    setActionSuccess(null);
    try {
      const horesNum = parseFloat(horesConcEdit);
      const kmNum = parseInt(kmConcEdit, 10);
      const ajustosPayload = (conc?.materials?.linies || [])
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
        `/gestio/feines/${resolvedFeinaId}/validar-conciliacio`,
        {
          method: "PUT",
          body: JSON.stringify({
            hores_imputades_facturables: Number.isNaN(horesNum) ? undefined : horesNum,
            km_imputats: !Number.isNaN(kmNum) && kmNum >= 0 ? kmNum : undefined,
            ajustos_picking: ajustosPayload.length > 0 ? ajustosPayload : undefined,
            checklist_conciliacio: checklist,
            notes_validacio_tecnica: notesValidacio.trim() || undefined,
          }),
        }
      );
      setConc(updated);
      setHoresConcEdit(String(updated.temps_i_gps?.hores_reals ?? 0));
      setKmConcEdit(String(updated.vehicle?.km_imputats ?? updated.resum_comercial?.km_imputats ?? 0));
      if (updated.resum_comercial?.km_imputats != null) {
        setKmImputatsInput(String(updated.resum_comercial.km_imputats));
      }
      setActionSuccess(
        "Conciliació tècnica validada correctament. La tasca ja està llesta per passar a pre-facturació."
      );
      onPrefacturaCreated?.();
      onSuccess?.({ id: resolvedFeinaId, codi: formData.codi });
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : "Error validant la conciliació.");
    } finally {
      setValidant(false);
    }
  };

  const handlePassarAPrefacturacio = async () => {
    if (!resolvedFeinaId) return;
    setEnviantPrefactura(true);
    setActionError(null);
    setActionSuccess(null);
    try {
      const pref = await apiFetch<{
        id: string;
        serie: string;
        numero_factura: number;
        liquid_exigible: number;
      }>(`/gestio/feines/${resolvedFeinaId}/passar-a-prefacturacio`, {
        method: "POST",
        body: JSON.stringify({ incloure_tiquets_camp: true }),
      });
      await carregarConciliacio(resolvedFeinaId);
      setActionSuccess(
        `Pre-factura ${pref.serie}-${String(pref.numero_factura).padStart(4, "0")} creada (${Number(
          pref.liquid_exigible
        ).toFixed(2)} €).`
      );
      onPrefacturaCreated?.();
      onSuccess?.({ id: resolvedFeinaId, codi: formData.codi });
    } catch (err: unknown) {
      setActionError(
        err instanceof Error ? err.message : "Error passant l'ordre de treball a pre-facturació."
      );
    } finally {
      setEnviantPrefactura(false);
    }
  };

  if (!isOpen) return null;

  const disclaimer: DisclaimerOT | null = isExistingOT
    ? conc?.disclaimer ||
      loadedFeina?.disclaimer || {
        codi: "NO_CONCLOSA",
        titol: "NO CONCLOSA — La feina no ha finalitzat",
        descripcio: "Pendent de conclusió a camp.",
        severitat: "neutral",
        pot_validar: false,
        pot_prefacturar: false,
      }
    : null;

  const facturaDoc = conc?.factura || null;
  const materialsConc = conc?.materials?.linies || [];
  const trams = loadedFeina?.trams_temps || [];
  const step1Done = Boolean(formData.titol.trim() && formData.client_id);
  const step2Done = Boolean(formData.adreca.trim());
  const step3Done = Boolean(formData.cap_de_colla_id);
  const step4Done = liniesPicking.length > 0 || selectedEinaIds.length > 0;

  return (
    <>
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/60 backdrop-blur-sm p-3 sm:p-4">
        <div className="bg-surface dark:bg-slate-950 rounded-2xl shadow-2xl w-full max-w-6xl overflow-hidden flex flex-col max-h-[94vh] border border-outline-variant/40">
          {/* Top Unified Header */}
          <div className="flex items-center justify-between px-5 sm:px-6 py-4 bg-surface-container-lowest dark:bg-slate-900 border-b border-outline-variant/30 gap-3">
            <div className="flex items-center gap-3 min-w-0">
              <div className="w-10 h-10 rounded-xl bg-primary text-on-primary flex items-center justify-center shadow-sm shrink-0">
                <FileText className="w-5 h-5" />
              </div>
              <div className="min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <h2 className="font-section-title text-base sm:text-lg text-primary dark:text-white truncate">
                    {isFromPressupost
                      ? `Fulla 360° OT · Conversió Pressupost ${pressupostSource?.numero || ""}`
                      : isExistingOT
                        ? `Fulla 360° OT · ${formData.titol || formData.codi}`
                        : "Fulla 360° OT · Nova Ordre de Treball"}
                  </h2>
                  <span className="font-mono text-[11px] font-bold px-2.5 py-0.5 rounded-full bg-primary text-on-primary">
                    {formData.codi}
                  </span>
                  <span className="font-mono text-[10px] font-bold px-2 py-0.5 rounded-full bg-surface-container-high text-on-surface uppercase">
                    {conc?.estat || formData.estat}
                  </span>
                  {(pressupostSource || conc?.pressupost) && (
                    <span className="font-mono text-[10px] font-bold px-2 py-0.5 rounded-full bg-secondary-container/25 text-secondary">
                      Pressupost {(pressupostSource || conc?.pressupost)?.numero}
                    </span>
                  )}
                </div>
                <p className="text-xs text-on-surface-variant mt-0.5 truncate">
                  Model únic operatiu i econòmic: planificació horària, equip, vehicle, fulla de picking, eines i facturació.
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="p-2 rounded-xl hover:bg-surface-container-high text-on-surface-variant hover:text-primary transition-colors cursor-pointer shrink-0"
              title="Tancar Fulla 360°"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Sub-header: Disclaimer (existing OT) OR 4-step progress (create / from pressupost) */}
          {isExistingOT && disclaimer ? (
            <div
              data-testid="fulla360-header-disclaimer"
              className={`px-6 py-2.5 border-b flex items-center justify-between gap-3 ${disclaimerBannerStyle(
                disclaimer.codi
              )}`}
            >
              <div className="flex items-start gap-2 min-w-0">
                {disclaimer.codi === "FACTURADA" ||
                disclaimer.codi === "VALIDADA_PENDENT_FACTURAR" ? (
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
                  <p className="text-[11px] opacity-90 mt-0.5 leading-snug">
                    {disclaimer.descripcio}
                  </p>
                </div>
              </div>
              {conc?.validacio?.validada && conc.validacio.validada_per_nom && (
                <span className="text-[10px] font-mono px-2 py-1 rounded-lg bg-white/60 dark:bg-slate-900/60 shrink-0 hidden sm:inline-block">
                  Validada per {conc.validacio.validada_per_nom}
                </span>
              )}
            </div>
          ) : (
            <div className="bg-surface-container-low px-6 py-3 border-b border-outline-variant/30">
              <div className="flex items-center justify-between relative max-w-4xl mx-auto">
                <div className="absolute top-1/2 left-0 w-full h-0.5 bg-surface-container-highest -translate-y-1/2 z-0" />
                {[
                  { n: 1, label: "Dades i Hores", done: step1Done },
                  { n: 2, label: "Ubicació i Plànol", done: step2Done },
                  { n: 3, label: "Equip i Vehicle", done: step3Done },
                  { n: 4, label: "Materials i Eines", done: step4Done },
                ].map((s) => (
                  <div
                    key={s.n}
                    className="relative z-10 flex items-center gap-2 bg-surface-container-low px-2.5"
                  >
                    <div
                      className={`w-6 h-6 rounded-full flex items-center justify-center font-bold text-xs transition-colors ${
                        s.done
                          ? "bg-primary text-on-primary shadow-sm"
                          : "bg-surface-container-highest text-on-surface-variant"
                      }`}
                    >
                      {s.n}
                    </div>
                    <span
                      className={`text-xs hidden sm:inline ${
                        s.done ? "font-body-strong text-primary" : "text-on-surface-variant"
                      }`}
                    >
                      {s.label}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Main Unified 2-Column Scrollable Body */}
          {bootLoading ? (
            <div className="p-16 flex flex-col items-center justify-center gap-3">
              <Loader2 className="w-8 h-8 text-primary animate-spin" />
              <p className="text-xs font-mono text-on-surface-variant">
                Carregant la Fulla 360° de l&apos;Ordre de Treball...
              </p>
            </div>
          ) : (
            <form
              id="form-fulla-360-ot"
              onSubmit={handleSubmit}
              className="flex-1 overflow-y-auto p-5 sm:p-6 space-y-6"
            >
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
                {/* LEFT COLUMN (7 Cols): Dades Bàsiques & Hores + Materials Picking + Eines + Camp/Conciliació */}
                <div className="lg:col-span-7 space-y-5">
                  {/* CARD 1: Dades Bàsiques, Planificació i Hores de Treball */}
                  <section className="bg-surface-container-lowest dark:bg-slate-900 p-5 rounded-xl shadow-xs border border-outline-variant/30 space-y-4">
                    <div className="flex items-center justify-between border-b border-outline-variant/20 pb-2.5">
                      <h3 className="font-section-title text-base text-primary dark:text-white flex items-center gap-2">
                        <FileText className="w-4 h-4 text-primary" />
                        <span>1. Dades Bàsiques, Hores i Tarifa</span>
                      </h3>
                      <span className="font-mono text-xs bg-primary/10 text-primary px-2 py-0.5 rounded font-bold">
                        {formData.codi}
                      </span>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
                      <div>
                        <label className="block text-[11px] font-semibold text-on-surface-variant mb-1">
                          Codi Referència *
                        </label>
                        <input
                          required
                          disabled={isExistingOT}
                          type="text"
                          value={formData.codi}
                          onChange={(e) => setFormData({ ...formData, codi: e.target.value })}
                          className="w-full px-3 py-2 bg-surface-container-low rounded-lg border border-outline-variant focus:border-primary outline-none text-xs font-mono font-bold disabled:opacity-60"
                        />
                      </div>

                      <div>
                        <label className="block text-[11px] font-semibold text-on-surface-variant mb-1 flex items-center gap-1">
                          <Calendar className="w-3.5 h-3.5 text-primary" /> Data Planificació *
                        </label>
                        <input
                          required
                          disabled={isLockedByInvoice}
                          type="date"
                          value={formData.data_planificacio}
                          onChange={(e) => {
                            setFormData({ ...formData, data_planificacio: e.target.value });
                            setFranjaManual(true);
                          }}
                          className="w-full px-3 py-2 bg-surface-container-low rounded-lg border border-outline-variant focus:border-primary outline-none text-xs font-mono disabled:opacity-60"
                        />
                      </div>

                      {/* Structured Hours & Hourly Rate (dedicated billing/planning fields) */}
                      <div className="md:col-span-2 grid grid-cols-2 sm:grid-cols-4 gap-2.5 p-3 rounded-xl bg-surface-container-low/70 border border-outline-variant/30">
                        <div>
                          <label className="block text-[10px] font-bold text-primary mb-1 flex items-center gap-1">
                            <Clock className="w-3 h-3" /> Hores Previstes (h)
                          </label>
                          <input
                            type="number"
                            step="0.25"
                            min="0"
                            disabled={isLockedByInvoice}
                            placeholder="Ex: 8"
                            value={horesPrevistes}
                            onChange={(e) => handleHoresPrevistesChange(e.target.value)}
                            className="w-full px-2.5 py-1.5 bg-surface-container-lowest rounded-lg border border-primary/40 focus:border-primary outline-none text-xs font-mono font-bold text-primary disabled:opacity-60"
                          />
                        </div>

                        <div>
                          <label className="block text-[10px] font-semibold text-on-surface-variant mb-1">
                            Tarifa PVP (€/h)
                          </label>
                          <input
                            type="number"
                            step="0.01"
                            min="0"
                            disabled={isLockedByInvoice}
                            placeholder="0.00"
                            value={preuHoraInput}
                            onChange={(e) => setPreuHoraInput(e.target.value)}
                            className="w-full px-2.5 py-1.5 bg-surface-container-lowest rounded-lg border border-outline-variant focus:border-primary outline-none text-xs font-mono font-bold disabled:opacity-60"
                          />
                        </div>

                        <div>
                          <label className="block text-[10px] font-semibold text-on-surface-variant mb-1">
                            Hora Inici
                          </label>
                          <input
                            type="time"
                            disabled={isLockedByInvoice}
                            value={horaInici}
                            onChange={(e) => handleHoraIniciChange(e.target.value)}
                            className="w-full px-2 py-1.5 bg-surface-container-lowest rounded-lg border border-outline-variant focus:border-primary outline-none text-xs font-mono disabled:opacity-60"
                          />
                        </div>

                        <div>
                          <label className="block text-[10px] font-semibold text-on-surface-variant mb-1">
                            Hora Fi
                          </label>
                          <input
                            type="time"
                            disabled={isLockedByInvoice}
                            value={horaFi}
                            onChange={(e) => handleHoraFiChange(e.target.value)}
                            className="w-full px-2 py-1.5 bg-surface-container-lowest rounded-lg border border-outline-variant focus:border-primary outline-none text-xs font-mono disabled:opacity-60"
                          />
                        </div>
                      </div>

                      <div className="md:col-span-2">
                        <label className="block text-[11px] font-semibold text-on-surface-variant mb-1">
                          Títol de la Intervenció *
                        </label>
                        <input
                          required
                          disabled={isLockedByInvoice}
                          type="text"
                          placeholder="Ex: Instal·lació bomba de pressió sector Nord"
                          value={formData.titol}
                          onChange={(e) => setFormData({ ...formData, titol: e.target.value })}
                          className="w-full px-3 py-2 bg-surface-container-low rounded-lg border border-outline-variant focus:border-primary outline-none text-xs font-medium disabled:opacity-60"
                        />
                      </div>

                      <div>
                        <label className="block text-[11px] font-semibold text-on-surface-variant mb-1 flex items-center gap-1">
                          <Building2 className="w-3.5 h-3.5" /> Client Titular *
                        </label>
                        <select
                          required
                          disabled={isLockedByInvoice || isFromPressupost}
                          value={formData.client_id}
                          onChange={(e) => handleClientChange(e.target.value)}
                          className="w-full px-3 py-2 bg-surface-container-low rounded-lg border border-outline-variant focus:border-primary outline-none text-xs disabled:opacity-60"
                        >
                          <option value="">Selecciona un client...</option>
                          {clients.map((c) => (
                            <option key={c.id || c.codi} value={c.id}>
                              {c.rao_social} {c.nif ? `(${c.nif})` : ""}
                            </option>
                          ))}
                        </select>
                      </div>

                      {isExistingOT ? (
                        <div>
                          <label className="block text-[11px] font-semibold text-on-surface-variant mb-1">
                            Estat Operatiu
                          </label>
                          <select
                            disabled={isLockedByInvoice}
                            value={formData.estat}
                            onChange={(e) => setFormData({ ...formData, estat: e.target.value })}
                            className="w-full px-3 py-2 bg-surface-container-low rounded-lg border border-outline-variant focus:border-primary outline-none text-xs font-semibold disabled:opacity-60"
                          >
                            <option value="PENDENT">PENDENT</option>
                            <option value="ASSIGNADA">ASSIGNADA</option>
                            <option value="PROGRAMADA">PROGRAMADA</option>
                            <option value="EN_RUTA">EN RUTA</option>
                            <option value="EN_OBRA">EN OBRA</option>
                            <option value="EN_CURS">EN CURS</option>
                            <option value="COMPLETADA">COMPLETADA</option>
                            <option value="TANCADA">TANCADA</option>
                            <option value="BLOQUEJADA">BLOQUEJADA</option>
                          </select>
                        </div>
                      ) : (
                        <div>
                          <label className="block text-[11px] font-semibold text-on-surface-variant mb-1">
                            Prioritat Operativa
                          </label>
                          <div className="grid grid-cols-4 gap-1.5">
                            {(["BAIXA", "NORMAL", "ALTA", "URGENT"] as const).map((p) => (
                              <button
                                key={p}
                                type="button"
                                onClick={() => setPrioritat(p)}
                                className={`py-2 px-1 rounded-lg text-[10px] font-bold border transition-all cursor-pointer ${
                                  prioritat === p
                                    ? p === "URGENT"
                                      ? "border-error bg-error-container/30 text-error"
                                      : "border-secondary bg-secondary-container/25 text-secondary"
                                    : "border-outline-variant bg-surface-container-low text-on-surface-variant"
                                }`}
                              >
                                {p}
                              </button>
                            ))}
                          </div>
                        </div>
                      )}

                      <div className="md:col-span-2">
                        <label className="block text-[11px] font-semibold text-on-surface-variant mb-1 flex items-center gap-1">
                          <AlignLeft className="w-3.5 h-3.5" /> Instruccions Tècniques (Descripció neta)
                        </label>
                        <textarea
                          rows={2}
                          disabled={isLockedByInvoice}
                          placeholder="Detalla tasques a executar i instruccions d'accés. Els materials, eines, hores i vehicle van als seus blocs propis..."
                          value={formData.descripcio}
                          onChange={(e) => setFormData({ ...formData, descripcio: e.target.value })}
                          className="w-full px-3 py-2 bg-surface-container-low rounded-lg border border-outline-variant focus:border-primary outline-none text-xs resize-none disabled:opacity-60"
                        />
                      </div>
                    </div>
                  </section>

                  {/* CARD 2: Materials (Fulla de Picking i Facturació) + Eines en Custòdia */}
                  <section className="bg-surface-container-lowest dark:bg-slate-900 p-5 rounded-xl shadow-xs border border-outline-variant/30 space-y-5">
                    <div className="flex items-center justify-between border-b border-outline-variant/20 pb-2.5">
                      <h3 className="font-section-title text-base text-primary dark:text-white flex items-center gap-2">
                        <Package className="w-4 h-4 text-primary" />
                        <span>4. Materials (Fulla de Picking) i Eines en Custòdia</span>
                      </h3>
                      <span className="font-mono text-[11px] font-bold text-secondary">
                        {liniesPicking.length} mat · {selectedEinaIds.length} eines
                      </span>
                    </div>

                    {/* Materials Picking sub-block */}
                    <div className="bg-surface-container-low/70 p-4 rounded-xl border border-outline-variant/30 space-y-3">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <h4 className="font-body-strong text-xs text-primary flex items-center gap-1.5">
                          <Package className="w-3.5 h-3.5" />
                          <span>Materials assignats a Picking i Facturació</span>
                        </h4>
                        {magatzems.length > 0 && !isLockedByInvoice && (
                          <div className="flex items-center gap-1.5">
                            <Warehouse className="w-3.5 h-3.5 text-secondary shrink-0" />
                            <select
                              value={selectedMagatzemId}
                              onChange={(e) => setSelectedMagatzemId(e.target.value)}
                              className="px-2 py-1 rounded-lg border border-outline-variant bg-surface-container-lowest text-[11px] text-on-surface outline-none"
                            >
                              <option value="">Qualsevol magatzem amb estoc</option>
                              {magatzems.map((m) => (
                                <option key={m.id} value={m.id}>
                                  {m.nom}
                                </option>
                              ))}
                            </select>
                          </div>
                        )}
                      </div>

                      {unmatchedPressupostMaterials.length > 0 && (
                        <div className="p-3 rounded-lg bg-amber-50 dark:bg-amber-950/30 border border-amber-300 dark:border-amber-700 text-xs space-y-1.5">
                          <p className="font-bold text-amber-900 dark:text-amber-200 flex items-center gap-1.5">
                            <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
                            <span>
                              Materials del pressupost sense article de catàleg vinculat ({unmatchedPressupostMaterials.length})
                            </span>
                          </p>
                          <p className="text-[11px] text-amber-800 dark:text-amber-300">
                            Cerca&apos;ls al selector de baix per vincular-los al picking de magatzem (el seu PVP ja està inclòs a l&apos;import pressupostat):
                          </p>
                          <div className="flex flex-wrap gap-1.5">
                            {unmatchedPressupostMaterials.map((um, idx) => (
                              <button
                                key={idx}
                                type="button"
                                onClick={() => {
                                  setCercaArticle(um.concepte);
                                  setCurrentQty(um.quantitat);
                                  setIsArticleDropdownOpen(true);
                                }}
                                className="px-2 py-1 rounded-md bg-white dark:bg-slate-900 border border-amber-300 text-[11px] font-medium text-amber-950 dark:text-amber-200 hover:border-primary cursor-pointer"
                              >
                                {um.concepte} (x{um.quantitat})
                              </button>
                            ))}
                          </div>
                        </div>
                      )}

                      {!isLockedByInvoice && (
                        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 items-start">
                          <div>
                            <label className="block text-[10px] font-semibold text-on-surface-variant mb-1">
                              Família
                            </label>
                            <select
                              value={filtreFamilia}
                              onChange={(e) => {
                                setFiltreFamilia(e.target.value);
                                setIsArticleDropdownOpen(true);
                              }}
                              className="w-full px-2.5 py-2 rounded-lg border border-outline-variant bg-surface-container-lowest text-xs outline-none"
                            >
                              <option value="TOTES">Totes ({articles.length})</option>
                              {familiesArticles.map((f) => (
                                <option key={f} value={f}>
                                  {f}
                                </option>
                              ))}
                            </select>
                          </div>

                          <div className="sm:col-span-2 relative" ref={articleComboboxRef}>
                            <label className="block text-[10px] font-semibold text-on-surface-variant mb-1">
                              Cerca article al catàleg (ref. o nom)
                            </label>
                            <div className="relative">
                              <input
                                type="text"
                                value={cercaArticle}
                                onFocus={() => setIsArticleDropdownOpen(true)}
                                onChange={(e) => {
                                  setCercaArticle(e.target.value);
                                  setSelectedArticle(null);
                                  setIsArticleDropdownOpen(true);
                                }}
                                placeholder="Escriu per cercar material..."
                                className="w-full pl-8 pr-7 py-2 rounded-lg border border-outline-variant bg-surface-container-lowest text-xs outline-none focus:border-primary"
                              />
                              <Search className="w-3.5 h-3.5 text-on-surface-variant absolute left-2.5 top-2.5 pointer-events-none" />
                              {cercaArticle && (
                                <button
                                  type="button"
                                  onClick={handleClearArticle}
                                  className="absolute right-2 top-2 text-on-surface-variant hover:text-primary cursor-pointer"
                                >
                                  <X className="w-3.5 h-3.5" />
                                </button>
                              )}
                            </div>

                            {isArticleDropdownOpen && (
                              <div className="absolute top-full left-0 right-0 mt-1 z-30 bg-surface-container-lowest dark:bg-slate-900 border border-outline-variant/60 rounded-xl shadow-xl overflow-hidden max-h-52 overflow-y-auto">
                                {filteredArticles.length > 0 ? (
                                  filteredArticles.map((art) => (
                                    <button
                                      key={art.id}
                                      type="button"
                                      onClick={() => handleSelectArticle(art)}
                                      className="w-full text-left px-3 py-2 text-xs hover:bg-surface-container border-b border-outline-variant/20 last:border-b-0 flex items-center justify-between gap-2 cursor-pointer"
                                    >
                                      <div className="min-w-0">
                                        <span className="font-mono text-[11px] font-bold text-primary mr-1">
                                          [{art.referencia_inventari}]
                                        </span>
                                        <span className="font-medium text-on-surface">{art.nom}</span>
                                      </div>
                                      <div className="text-right shrink-0 font-mono text-[11px]">
                                        <span className="text-secondary font-bold">
                                          {Number(art.preu_venda || 0).toFixed(2)} €
                                        </span>
                                        <span className="block text-[10px] text-on-surface-variant">
                                          Disp: {Number(art.estoc_disponible ?? art.estoc_real ?? 0)}{" "}
                                          {art.unitat_mesura}
                                        </span>
                                      </div>
                                    </button>
                                  ))
                                ) : (
                                  <div className="p-3 text-center text-xs text-on-surface-variant">
                                    Cap article coincideix amb la cerca.
                                  </div>
                                )}
                              </div>
                            )}
                          </div>
                        </div>
                      )}

                      {selectedArticle && !isLockedByInvoice && (
                        <div className="pt-2 border-t border-outline-variant/25 flex flex-wrap items-end gap-2.5">
                          <div className="flex-1 min-w-[180px] p-2 rounded-lg bg-primary/5 border border-primary/20">
                            <p className="text-xs font-bold text-primary truncate">
                              [{selectedArticle.referencia_inventari}] {selectedArticle.nom}
                            </p>
                            <p className="text-[10px] font-mono text-on-surface-variant">
                              PVP: {Number(selectedArticle.preu_venda || 0).toFixed(2)} €/{selectedArticle.unitat_mesura} · Estoc:{" "}
                              {Number(selectedArticle.estoc_disponible ?? selectedArticle.estoc_real ?? 0)}
                            </p>
                          </div>
                          <div className="w-24">
                            <label className="block text-[10px] font-semibold text-on-surface-variant mb-0.5">
                              Quantitat
                            </label>
                            <input
                              type="number"
                              min="0.001"
                              step="any"
                              value={currentQty}
                              onChange={(e) => setCurrentQty(parseFloat(e.target.value) || 0)}
                              className="w-full px-2 py-1.5 rounded-lg border border-outline-variant bg-surface-container-lowest text-xs font-mono font-bold text-center"
                            />
                          </div>
                          <button
                            type="button"
                            onClick={addLiniaPicking}
                            disabled={currentQty <= 0}
                            className="px-3.5 py-2 rounded-lg bg-primary text-on-primary text-xs font-bold hover:opacity-90 disabled:opacity-40 inline-flex items-center gap-1 cursor-pointer"
                          >
                            <Plus className="w-3.5 h-3.5" /> Afegir
                          </button>
                        </div>
                      )}

                      {liniesPicking.length > 0 ? (
                        <div className="border border-outline-variant/30 rounded-xl overflow-x-auto bg-surface-container-lowest dark:bg-slate-900">
                          <table className="w-full text-left text-xs">
                            <thead className="bg-surface-container-low text-on-surface-variant border-b border-outline-variant/20 text-[10px] uppercase">
                              <tr>
                                <th className="py-2 px-3">Ref / Article</th>
                                <th className="py-2 px-2 text-center w-28">Qt. Prevista</th>
                                <th className="py-2 px-2 text-right">PVP u.</th>
                                <th className="py-2 px-3 text-right">Subtotal</th>
                                {!isLockedByInvoice && <th className="py-2 px-2 w-10" />}
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-outline-variant/15">
                              {liniesPicking.map((lin) => (
                                <tr key={lin.article_id}>
                                  <td className="py-2 px-3">
                                    <span className="font-mono text-[10px] font-bold text-primary mr-1">
                                      [{lin.referencia_inventari}]
                                    </span>
                                    <span className="font-medium text-on-surface">
                                      {lin.article_nom}
                                    </span>
                                    <span className="block text-[10px] font-mono text-on-surface-variant">
                                      Estoc disp: {lin.estoc_disponible} {lin.unitat_mesura}
                                    </span>
                                  </td>
                                  <td className="py-2 px-2 text-center">
                                    {isLockedByInvoice ? (
                                      <span className="font-mono font-bold">
                                        {lin.quantitat_prevista} {lin.unitat_mesura}
                                      </span>
                                    ) : (
                                      <input
                                        type="number"
                                        step="any"
                                        min="0.001"
                                        value={lin.quantitat_prevista}
                                        onChange={(e) =>
                                          updateQtyPicking(
                                            lin.article_id,
                                            parseFloat(e.target.value) || 0
                                          )
                                        }
                                        className="w-20 px-2 py-1 rounded border border-outline-variant bg-surface-container-low text-xs font-mono font-bold text-center"
                                      />
                                    )}
                                  </td>
                                  <td className="py-2 px-2 text-right font-mono text-on-surface-variant">
                                    {lin.preu_venda_unitari.toFixed(2)} €
                                  </td>
                                  <td className="py-2 px-3 text-right font-mono font-bold text-primary">
                                    {(lin.quantitat_prevista * lin.preu_venda_unitari).toFixed(2)} €
                                  </td>
                                  {!isLockedByInvoice && (
                                    <td className="py-2 px-2 text-right">
                                      <button
                                        type="button"
                                        onClick={() => removeLiniaPicking(lin.article_id)}
                                        className="p-1 text-error hover:bg-error/10 rounded cursor-pointer"
                                        title="Eliminar línia"
                                      >
                                        <Trash2 className="w-3.5 h-3.5" />
                                      </button>
                                    </td>
                                  )}
                                </tr>
                              ))}
                            </tbody>
                            <tfoot className="bg-surface-container-low/60 border-t border-outline-variant/25">
                              <tr>
                                <td colSpan={3} className="py-2 px-3 text-right text-[11px] font-bold text-on-surface-variant">
                                  Total Materials Picking (PVP)
                                </td>
                                <td className="py-2 px-3 text-right font-mono font-black text-primary">
                                  {economiaLive.materialsPvp.toFixed(2)} €
                                </td>
                                {!isLockedByInvoice && <td />}
                              </tr>
                            </tfoot>
                          </table>
                        </div>
                      ) : (
                        <div className="p-3.5 text-center text-xs text-on-surface-variant border border-dashed border-outline-variant/40 rounded-lg">
                          Cap material assignat a la fulla de picking d&apos;aquesta OT.
                        </div>
                      )}
                    </div>

                    {/* Eines en Custòdia sub-block */}
                    <div className="bg-surface-container-low/70 p-4 rounded-xl border border-outline-variant/30 space-y-3">
                      <h4 className="font-body-strong text-xs text-primary flex items-center gap-1.5">
                        <Wrench className="w-3.5 h-3.5" />
                        <span>Eines i Maquinària en Custòdia ({selectedEinaIds.length})</span>
                      </h4>

                      {unmatchedPressupostEines.length > 0 && (
                        <div className="p-2.5 rounded-lg bg-amber-50 dark:bg-amber-950/30 border border-amber-300 dark:border-amber-700 text-[11px] text-amber-900 dark:text-amber-200">
                          <strong>Eines del pressupost fora d&apos;inventari:</strong>{" "}
                          {unmatchedPressupostEines.join(", ")} — selecciona una eina de l&apos;inventari si vols registrar-ne la custòdia.
                        </div>
                      )}

                      {!isLockedByInvoice && (
                        <div className="flex items-end gap-2 flex-wrap">
                          <div className="flex-1 min-w-[220px] relative" ref={einaComboboxRef}>
                            <input
                              type="text"
                              value={cercaEina}
                              onFocus={() => setIsEinaDropdownOpen(true)}
                              onChange={(e) => {
                                setCercaEina(e.target.value);
                                setSelectedEina(null);
                                setIsEinaDropdownOpen(true);
                              }}
                              placeholder="Cerca eina per nom, model o núm. sèrie..."
                              className="w-full pl-8 pr-7 py-2 rounded-lg border border-outline-variant bg-surface-container-lowest text-xs outline-none focus:border-primary"
                            />
                            <Search className="w-3.5 h-3.5 text-on-surface-variant absolute left-2.5 top-2.5 pointer-events-none" />
                            {isEinaDropdownOpen && (
                              <div className="absolute top-full left-0 right-0 mt-1 z-30 bg-surface-container-lowest dark:bg-slate-900 border border-outline-variant/60 rounded-xl shadow-xl max-h-48 overflow-y-auto">
                                {filteredEines.length > 0 ? (
                                  filteredEines.map((eina) => (
                                    <button
                                      key={eina.id}
                                      type="button"
                                      onClick={() => handleSelectEina(eina)}
                                      className="w-full text-left px-3 py-2 text-xs hover:bg-surface-container border-b border-outline-variant/20 last:border-b-0 flex items-center justify-between gap-2 cursor-pointer"
                                    >
                                      <div>
                                        <span className="font-bold text-primary">{eina.nom}</span>
                                        {eina.model && (
                                          <span className="ml-1 text-on-surface-variant">
                                            ({eina.model})
                                          </span>
                                        )}
                                        <span className="block text-[10px] font-mono text-on-surface-variant">
                                          SN: {eina.numero_serie}
                                        </span>
                                      </div>
                                      <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-surface-container-high">
                                        {eina.estat}
                                      </span>
                                    </button>
                                  ))
                                ) : (
                                  <div className="p-3 text-center text-xs text-on-surface-variant">
                                    Cap eina disponible coincideix.
                                  </div>
                                )}
                              </div>
                            )}
                          </div>
                          <button
                            type="button"
                            onClick={addEina}
                            disabled={!selectedEina}
                            className="px-3.5 py-2 rounded-lg bg-primary text-on-primary text-xs font-bold hover:opacity-90 disabled:opacity-40 inline-flex items-center gap-1 cursor-pointer"
                          >
                            <Plus className="w-3.5 h-3.5" /> Vincular
                          </button>
                        </div>
                      )}

                      {selectedEinaIds.length > 0 ? (
                        <ul className="space-y-1.5">
                          {selectedEinaIds.map((eid) => {
                            const eDef =
                              eines.find((e) => e.id === eid) ||
                              conc?.eines?.find((e) => e.id === eid) ||
                              loadedFeina?.eines?.find((e) => e.id === eid);
                            const estatEina = eDef?.estat || "DISPONIBLE";
                            const isAvariada = estatEina === "AVARIADA";
                            const isEnCustodia = eDef?.en_custodia_efectiva ?? (estatEina !== "DISPONIBLE");

                            return (
                              <li
                                key={eid}
                                className={`flex items-center justify-between px-3 py-2 rounded-lg border text-xs ${
                                  isAvariada
                                    ? "bg-amber-50/50 dark:bg-amber-950/20 border-amber-300 dark:border-amber-700"
                                    : "bg-surface-container-lowest dark:bg-slate-900 border-outline-variant/30"
                                }`}
                              >
                                <div className="flex items-center gap-2 min-w-0">
                                  <Wrench className={`w-3.5 h-3.5 shrink-0 ${isAvariada ? "text-amber-600" : "text-secondary"}`} />
                                  <span className="font-bold text-primary truncate">
                                    {eDef?.nom || "Eina"}
                                  </span>
                                  <span className="font-mono text-[10px] text-on-surface-variant">
                                    SN: {eDef?.numero_serie || "—"}
                                  </span>
                                  <span
                                    className={`text-[9px] font-bold px-2 py-0.5 rounded-full ${
                                      isAvariada
                                        ? "bg-amber-200 text-amber-900 dark:bg-amber-900 dark:text-amber-200"
                                        : isEnCustodia
                                        ? "bg-primary/10 text-primary"
                                        : "bg-surface-container text-on-surface-variant"
                                    }`}
                                  >
                                    {isAvariada ? "AVARIADA (En custòdia - Pendent Pick-Out)" : estatEina}
                                  </span>
                                </div>
                                {!isLockedByInvoice && (
                                  <button
                                    type="button"
                                    onClick={() => removeEina(eid)}
                                    className="p-1 text-error hover:bg-error/10 rounded cursor-pointer"
                                    title="Desvincular eina"
                                  >
                                    <Trash2 className="w-3.5 h-3.5" />
                                  </button>
                                )}
                              </li>
                            );
                          })}
                        </ul>
                      ) : (
                        <div className="p-3 text-center text-xs text-on-surface-variant border border-dashed border-outline-variant/40 rounded-lg">
                          Cap eina en custòdia assignada a aquesta ordre.
                        </div>
                      )}
                    </div>
                  </section>

                  {/* DOSSIER 360° DE CAMP, EVIDÈNCIES, CONCILIACIÓ I VALIDACIÓ (Només en OT existent) */}
                  {isExistingOT && (
                    <section className="bg-surface-container-lowest dark:bg-slate-900 p-5 rounded-xl shadow-xs border border-outline-variant/30 space-y-4">
                      <div className="flex items-center justify-between border-b border-outline-variant/20 pb-2.5">
                        <h3 className="font-section-title text-base text-primary dark:text-white flex items-center gap-2">
                          <ShieldCheck className="w-4 h-4 text-primary" />
                          <span>5. Seguiment de Camp, Evidències PWA i Validació</span>
                        </h3>
                        {loadingConc && <Loader2 className="w-4 h-4 animate-spin text-primary" />}
                      </div>

                      {/* Resum de Conciliació d'Hores i Estat Operatiu Real */}
                      <div className="p-3.5 rounded-xl bg-surface-container-low border border-outline-variant/30 space-y-2.5">
                        <div className="flex items-center justify-between text-xs font-bold">
                          <span className="flex items-center gap-1.5 text-primary">
                            <Clock className="w-3.5 h-3.5 text-primary" />
                            <span>Conciliació d&apos;Hores (Previstes vs Reals)</span>
                          </span>
                          <span
                            className={`font-mono text-[10px] px-2 py-0.5 rounded-full font-bold ${
                              conc?.disclaimer?.codi === "VALIDADA_PENDENT_FACTURAR" || conc?.validacio?.validada
                                ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300"
                                : conc?.disclaimer?.codi === "CONCLOSA_PENDENT_VALIDACIO"
                                ? "bg-amber-100 text-amber-800 dark:bg-amber-950/40 dark:text-amber-300"
                                : "bg-sky-100 text-sky-800 dark:bg-sky-950/40 dark:text-sky-300"
                            }`}
                          >
                            {conc?.disclaimer?.titol || formData.estat}
                          </span>
                        </div>
                        <div className="grid grid-cols-3 gap-2 text-center text-xs">
                          <div className="p-2 rounded-lg bg-surface-container-lowest border border-outline-variant/20">
                            <span className="text-[10px] text-on-surface-variant block">Pressupostades / Previstes</span>
                            <span className="font-mono font-bold text-sm">
                              {Number(conc?.temps_i_gps?.hores_previstes ?? horesPrevistes ?? 0).toFixed(2)} h
                            </span>
                            <span className="block text-[10px] font-mono text-on-surface-variant">
                              {conc?.temps_i_gps?.hores_previstes_human ||
                                `${Math.floor(Number(horesPrevistes || 0))}h ${Math.round((Number(horesPrevistes || 0) % 1) * 60)}m`}
                            </span>
                          </div>
                          <div className="p-2 rounded-lg bg-surface-container-lowest border border-outline-variant/20">
                            <span className="text-[10px] text-on-surface-variant block">Reals (Operari / Cronòmetre)</span>
                            <span className="font-mono font-bold text-sm text-secondary">
                              {Number(conc?.temps_i_gps?.hores_reals ?? 0).toFixed(2)} h
                            </span>
                            <span className="block text-[10px] font-mono text-secondary">
                              {conc?.temps_i_gps?.hores_reals_human ||
                                `${Math.floor(Number(conc?.temps_i_gps?.hores_reals || 0))}h ${Math.round((Number(conc?.temps_i_gps?.hores_reals || 0) % 1) * 60)}m`}
                            </span>
                          </div>
                          <div className="p-2 rounded-lg bg-surface-container-lowest border border-outline-variant/20">
                            <span className="text-[10px] text-on-surface-variant block">Desviació</span>
                            <span
                              className={`font-mono font-bold text-sm ${
                                Number(conc?.temps_i_gps?.desviacio_hores ?? 0) > 0
                                  ? "text-error"
                                  : "text-emerald-700 dark:text-emerald-400"
                              }`}
                            >
                              {Number(conc?.temps_i_gps?.desviacio_hores ?? 0) > 0 ? "+" : ""}
                              {Number(conc?.temps_i_gps?.desviacio_hores ?? 0).toFixed(2)} h
                            </span>
                            <span className="block text-[10px] text-on-surface-variant">
                              {Number(conc?.temps_i_gps?.desviacio_hores ?? 0) <= 0
                                ? "Dins de marge"
                                : "Excés de temps"}
                            </span>
                          </div>
                        </div>
                      </div>

                      {/* Quadrilla d'Operaris de Camp (Cap de colla + Operaris) */}
                      {conc?.operaris_assignats && conc.operaris_assignats.length > 0 && (
                        <div className="p-3 rounded-xl bg-surface-container-low border border-outline-variant/30 space-y-2">
                          <span className="text-xs font-bold text-primary flex items-center gap-1.5">
                            <Users className="w-3.5 h-3.5 text-primary" />
                            <span>Equip Quadrilla de Camp ({conc.operaris_assignats.length})</span>
                          </span>
                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                            {conc.operaris_assignats.map((op) => (
                              <div
                                key={op.id}
                                className="px-2.5 py-1.5 rounded-lg bg-surface-container-lowest border border-outline-variant/20 flex items-center justify-between text-xs"
                              >
                                <div className="min-w-0">
                                  <span className="font-bold truncate block">
                                    {op.nom}
                                  </span>
                                  <span className="text-[10px] text-on-surface-variant">
                                    {op.es_cap_de_colla ? "Cap de Colla" : op.rol || "Operari"}
                                    {op.telefon ? ` · ${op.telefon}` : ""}
                                  </span>
                                </div>
                                <span
                                  className={`text-[9px] font-bold px-1.5 py-0.5 rounded-full ${
                                    op.es_cap_de_colla
                                      ? "bg-primary/10 text-primary"
                                      : "bg-surface-container text-on-surface-variant"
                                  }`}
                                >
                                  {op.es_cap_de_colla ? "RESPONSABLE" : "OPERARI"}
                                </span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Alerta Geovalla GPS */}
                      {conc?.temps_i_gps?.desviacio_geovalla && (
                        <div className="p-3 rounded-xl bg-amber-50 dark:bg-amber-950/35 border border-amber-300 flex items-start justify-between gap-2 text-xs">
                          <div className="flex items-start gap-2">
                            <AlertTriangle className="w-4 h-4 text-amber-700 shrink-0 mt-0.5" />
                            <div>
                              <p className="font-bold text-amber-900">Desviació de Geovalla GPS (&gt;50m)</p>
                              <p className="text-amber-800 mt-0.5">
                                {conc.temps_i_gps.justificacio_geovalla || "Sense justificació."}
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
                              className="px-2.5 py-1 rounded-lg bg-amber-700 text-white text-[11px] font-bold cursor-pointer"
                            >
                              Veure Foto
                            </button>
                          )}
                        </div>
                      )}

                      {/* Trams de temps reals */}
                      {trams.length > 0 && (
                        <div className="space-y-1.5">
                          <span className="text-[11px] font-bold text-on-surface-variant block">
                            Trams de Temps Reals ({trams.length})
                          </span>
                          {trams.map((t, idx) => (
                            <div
                              key={t.id}
                              className="text-xs px-3 py-1.5 rounded-lg bg-surface-container-low border border-outline-variant/20 flex items-center justify-between"
                            >
                              <span className="font-mono text-[11px]">
                                #{idx + 1} ·{" "}
                                {new Date(t.hora_inici).toLocaleTimeString("ca-ES", {
                                  hour: "2-digit",
                                  minute: "2-digit",
                                })}{" "}
                                →{" "}
                                {t.hora_fi
                                  ? new Date(t.hora_fi).toLocaleTimeString("ca-ES", {
                                      hour: "2-digit",
                                      minute: "2-digit",
                                    })
                                  : "En curs"}
                              </span>
                              <span className="font-mono font-bold text-secondary">
                                {t.hora_fi ? fmtHMS(t.durada_segons) : "Actiu"}
                              </span>
                            </div>
                          ))}
                        </div>
                      )}

                      {/* Evidències PWA: 3 Fotos QA + Signatura */}
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
                        <div className="p-3 rounded-xl bg-surface-container-low/50 border border-outline-variant/30 space-y-2">
                          <div className="flex items-center justify-between text-xs font-bold">
                            <span className="flex items-center gap-1.5">
                              <Camera className="w-3.5 h-3.5 text-primary" /> Fotos QA
                            </span>
                            <span className="font-mono text-[10px] px-2 py-0.5 rounded-full bg-primary/10 text-primary">
                              {conc?.fotos_qa?.total_pujades ?? 0} / 3
                            </span>
                          </div>
                          <div className="grid grid-cols-3 gap-1.5">
                            {(
                              [
                                { key: "foto_inicial", flag: conc?.fotos_qa?.inicial, label: "Inicial" },
                                { key: "foto_intermedia", flag: conc?.fotos_qa?.intermedia, label: "Mitja" },
                                { key: "foto_final", flag: conc?.fotos_qa?.final, label: "Final" },
                              ] as const
                            ).map((it) => {
                              const url = evidenciesUrls[it.key];
                              return (
                                <div
                                  key={it.key}
                                  className="rounded-lg border border-outline-variant/30 overflow-hidden bg-surface-container-lowest flex flex-col"
                                >
                                  <div className="aspect-square flex items-center justify-center bg-surface-container relative">
                                    {url ? (
                                      <button
                                        type="button"
                                        onClick={() =>
                                          setLightboxUrl({ url, titol: `Foto QA — ${it.label}` })
                                        }
                                        className="w-full h-full group relative cursor-pointer"
                                      >
                                        <img
                                          src={url}
                                          alt={it.label}
                                          className="w-full h-full object-cover"
                                        />
                                        <span className="absolute inset-0 bg-slate-950/0 group-hover:bg-slate-950/35 flex items-center justify-center">
                                          <ZoomIn className="w-4 h-4 text-white opacity-0 group-hover:opacity-100" />
                                        </span>
                                      </button>
                                    ) : (
                                      <span className="text-[9px] text-on-surface-variant text-center px-1">
                                        {it.flag ? "..." : "Pendent"}
                                      </span>
                                    )}
                                  </div>
                                  <span className="text-[10px] text-center py-0.5 font-semibold text-on-surface-variant">
                                    {it.label}
                                  </span>
                                </div>
                              );
                            })}
                          </div>
                        </div>

                        <div className="p-3 rounded-xl bg-surface-container-low/50 border border-outline-variant/30 space-y-2">
                          <div className="flex items-center justify-between text-xs font-bold">
                            <span className="flex items-center gap-1.5">
                              <PenTool className="w-3.5 h-3.5 text-secondary" /> Signatura Client
                            </span>
                            <span className="font-mono text-[10px] px-2 py-0.5 rounded-full bg-surface-container-high">
                              {conc?.signatura?.present ? "SIGNADA" : "PENDENT"}
                            </span>
                          </div>
                          {evidenciesUrls["signatura"] ? (
                            <button
                              type="button"
                              onClick={() =>
                                setLightboxUrl({
                                  url: evidenciesUrls["signatura"],
                                  titol: "Signatura del Client",
                                })
                              }
                              className="w-full h-20 rounded-lg border border-outline-variant/30 bg-white p-1 flex items-center justify-center cursor-pointer"
                            >
                              <img
                                src={evidenciesUrls["signatura"]}
                                alt="Signatura"
                                className="max-h-full max-w-full object-contain"
                              />
                            </button>
                          ) : (
                            <div className="h-16 rounded-lg border border-dashed border-outline-variant/40 flex items-center justify-center text-[11px] text-on-surface-variant">
                              Sense signatura recollida a camp
                            </div>
                          )}
                          <p className="text-[11px] text-on-surface-variant">
                            Receptor: <strong>{conc?.signatura?.nom_receptor || "—"}</strong>
                          </p>
                        </div>
                      </div>

                      {/* Resum Pick-In / Pick-Out i Estat del Picking */}
                      {isExistingOT && conc?.materials && (
                        <div className="p-3 rounded-xl bg-surface-container-low border border-outline-variant/30 space-y-2">
                          <div className="flex items-center justify-between text-xs">
                            <span className="font-bold text-primary flex items-center gap-1.5">
                              <Package className="w-3.5 h-3.5 text-primary" />
                              <span>Resum Picking de Materials ({conc.materials.total_linies} línies)</span>
                            </span>
                            <span className="font-mono text-[10px] px-2 py-0.5 rounded-full font-bold bg-primary/10 text-primary">
                              Estat: {conc.materials.estat_picking || "PENDENT"}
                            </span>
                          </div>

                          {/* Avís de materials del pressupost pendents d'importar/facturar */}
                          {conc.materials.linies_pendents_facturar && conc.materials.linies_pendents_facturar.length > 0 && (
                            <div className="p-2.5 rounded-lg bg-amber-50 dark:bg-amber-950/35 border border-amber-300 text-xs text-amber-950 dark:text-amber-200 space-y-1">
                              <div className="flex items-center gap-1.5 font-bold">
                                <AlertTriangle className="w-3.5 h-3.5 text-amber-700 shrink-0" />
                                <span>Ítems del pressupost pendents de facturar o sense picking vinculat:</span>
                              </div>
                              <ul className="list-disc list-inside space-y-0.5 text-[11px] text-amber-900 dark:text-amber-300">
                                {conc.materials.linies_pendents_facturar.map((lpf, idx) => (
                                  <li key={idx}>
                                    <strong>{lpf.concepte}</strong> — {lpf.quantitat} u. ({lpf.subtotal.toFixed(2)} €)
                                  </li>
                                ))}
                              </ul>
                            </div>
                          )}
                        </div>
                      )}

                      {/* Conciliació de Materials (Pick-In / Pick-Out / Merma) */}
                      {materialsConc.length > 0 && (
                        <div className="border border-outline-variant/30 rounded-xl overflow-x-auto">
                          <table className="w-full text-left text-xs">
                            <thead className="bg-surface-container-low text-on-surface-variant text-[10px] uppercase">
                              <tr>
                                <th className="py-2 px-3">Conciliació Material</th>
                                <th className="py-2 px-2 text-right">Prev.</th>
                                <th className="py-2 px-2 text-right">Pick-In</th>
                                <th className="py-2 px-2 text-right">Retorn</th>
                                <th className="py-2 px-2 text-right">Merma</th>
                                <th className="py-2 px-2 text-right">Consum</th>
                                <th className="py-2 px-2 text-right">PVP Unit.</th>
                                <th className="py-2 px-3 text-right">Subtotal (€)</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-outline-variant/15">
                              {materialsConc.map((lin) => {
                                const d = ajustosPicking[lin.linia_id];
                                const qInRaw = d ? parseFloat(d.carregat) : lin.quantitat_carregada_pick_in;
                                const qOutRaw = d ? parseFloat(d.retornat) : lin.quantitat_retornada_pick_out;
                                const qIn = Number.isNaN(qInRaw) ? 0 : qInRaw;
                                const qOut = Number.isNaN(qOutRaw) ? 0 : qOutRaw;
                                const cons = Math.max(0, qIn - qOut);
                                const qBill = qIn > 0 ? cons : qOut > 0 ? 0 : Number(lin.quantitat_prevista || 0);
                                const subtotalPvp = qBill * Number(lin.preu_venda_unitari || 0);

                                return (
                                  <tr key={lin.linia_id}>
                                    <td className="py-1.5 px-3 font-medium">
                                      <div>{lin.article_nom}</div>
                                      <div className="text-[10px] font-mono text-on-surface-variant">
                                        {lin.origen_estoc} · {lin.referencia_inventari || "S/REF"}
                                      </div>
                                    </td>
                                    <td className="py-1.5 px-2 text-right font-mono">{lin.quantitat_prevista}</td>
                                    <td className="py-1.5 px-2 text-right">
                                      {disclaimer?.pot_validar ? (
                                        <input
                                          type="number"
                                          step="0.1"
                                          min="0"
                                          value={d?.carregat ?? "0"}
                                          onChange={(e) =>
                                            setAjustosPicking((prev) => ({
                                              ...prev,
                                              [lin.linia_id]: { ...prev[lin.linia_id], carregat: e.target.value },
                                            }))
                                          }
                                          className="w-16 px-1.5 py-0.5 text-right rounded border border-outline-variant text-xs font-mono"
                                        />
                                      ) : (
                                        <span className="font-mono">{lin.quantitat_carregada_pick_in}</span>
                                      )}
                                    </td>
                                    <td className="py-1.5 px-2 text-right">
                                      {disclaimer?.pot_validar ? (
                                        <input
                                          type="number"
                                          step="0.1"
                                          min="0"
                                          value={d?.retornat ?? "0"}
                                          onChange={(e) =>
                                            setAjustosPicking((prev) => ({
                                              ...prev,
                                              [lin.linia_id]: { ...prev[lin.linia_id], retornat: e.target.value },
                                            }))
                                          }
                                          className="w-16 px-1.5 py-0.5 text-right rounded border border-outline-variant text-xs font-mono"
                                        />
                                      ) : (
                                        <span className="font-mono">{lin.quantitat_retornada_pick_out}</span>
                                      )}
                                    </td>
                                    <td className="py-1.5 px-2 text-right">
                                      {disclaimer?.pot_validar ? (
                                        <input
                                          type="number"
                                          step="0.1"
                                          min="0"
                                          value={d?.merma ?? "0"}
                                          onChange={(e) =>
                                            setAjustosPicking((prev) => ({
                                              ...prev,
                                              [lin.linia_id]: { ...prev[lin.linia_id], merma: e.target.value },
                                            }))
                                          }
                                          className="w-16 px-1.5 py-0.5 text-right rounded border border-outline-variant text-xs font-mono"
                                        />
                                      ) : (
                                        <span className="font-mono">{lin.quantitat_mermada}</span>
                                      )}
                                    </td>
                                    <td className="py-1.5 px-2 text-right font-mono font-bold text-primary">
                                      <span>{qBill.toFixed(2)}</span>
                                      {qIn === 0 && qBill > 0 && (
                                        <span className="block text-[9px] font-normal text-on-surface-variant">
                                          (prev.)
                                        </span>
                                      )}
                                    </td>
                                    <td className="py-1.5 px-2 text-right font-mono text-on-surface-variant">
                                      {Number(lin.preu_venda_unitari || 0).toFixed(2)} €
                                    </td>
                                    <td className="py-1.5 px-3 text-right font-mono font-bold text-secondary">
                                      {subtotalPvp.toFixed(2)} €
                                    </td>
                                  </tr>
                                );
                              })}
                            </tbody>
                          </table>
                        </div>
                      )}

                      {/* Incidències, Tiquets i GIS */}
                      <div className="grid grid-cols-3 gap-2.5 text-xs">
                        <div className="p-2.5 rounded-lg bg-surface-container-low/60 border border-outline-variant/25">
                          <span className="text-[10px] font-bold text-on-surface-variant block">Incidències</span>
                          <span className="font-mono font-bold text-primary">{conc?.incidencies?.total ?? 0}</span>
                        </div>
                        <div className="p-2.5 rounded-lg bg-surface-container-low/60 border border-outline-variant/25">
                          <span className="text-[10px] font-bold text-on-surface-variant block">Tiquets Camp</span>
                          <span className="font-mono font-bold text-primary">
                            {Number(conc?.tiquets?.import_total ?? 0).toFixed(2)} €
                          </span>
                        </div>
                        <div className="p-2.5 rounded-lg bg-surface-container-low/60 border border-outline-variant/25">
                          <span className="text-[10px] font-bold text-on-surface-variant block">Capes GIS</span>
                          <span className="font-mono font-bold text-primary">{conc?.capes_gis?.length ?? 0}</span>
                        </div>
                      </div>

                      {/* Documentació Comercial Vinculada */}
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                        <div className="p-3 rounded-xl bg-surface-container-low/50 border border-outline-variant/30 flex items-center justify-between gap-2">
                          <div>
                            <span className="text-[10px] font-semibold text-on-surface-variant block">
                              Pressupost Vinculat
                            </span>
                            {conc?.pressupost ? (
                              <p className="font-mono text-xs font-bold text-primary">
                                {conc.pressupost.numero} · {Number(conc.pressupost.total).toFixed(2)} €
                              </p>
                            ) : (
                              <p className="text-xs text-on-surface-variant">Sense pressupost</p>
                            )}
                          </div>
                          {conc?.pressupost && (
                            <Link
                              href={`/gestio/pressupostos?id=${conc.pressupost.id}`}
                              onClick={onClose}
                              className="px-2.5 py-1 rounded-lg bg-primary/10 text-primary text-[11px] font-bold hover:bg-primary hover:text-on-primary inline-flex items-center gap-1"
                            >
                              <ExternalLink className="w-3 h-3" /> Veure
                            </Link>
                          )}
                        </div>

                        <div className="p-3 rounded-xl bg-surface-container-low/50 border border-outline-variant/30 flex items-center justify-between gap-2">
                          <div>
                            <span className="text-[10px] font-semibold text-on-surface-variant block">
                              Pre-factura / Factura
                            </span>
                            {facturaDoc ? (
                              <p className="font-mono text-xs font-bold text-primary">
                                {facturaDoc.serie}-{String(facturaDoc.numero_factura).padStart(4, "0")} ·{" "}
                                {Number(facturaDoc.liquid_exigible).toFixed(2)} €
                              </p>
                            ) : (
                              <p className="text-xs text-on-surface-variant">Encara no pre-facturada</p>
                            )}
                          </div>
                          {facturaDoc && (
                            <button
                              type="button"
                              data-testid="btn-veure-factura-comercial-ot"
                              onClick={() => setFacturaModalId(facturaDoc.id)}
                              className="px-2.5 py-1 rounded-lg bg-primary text-on-primary text-[11px] font-bold inline-flex items-center gap-1 cursor-pointer"
                            >
                              <Receipt className="w-3 h-3" /> Detall / PDF
                            </button>
                          )}
                        </div>
                      </div>

                      {/* Espai de Validació Tècnica i Pas a Pre-facturació */}
                      {!facturaDoc && disclaimer && (
                        <div
                          data-testid="fulla360-validacio-workspace"
                          className="p-4 rounded-xl bg-surface-container-low/40 border-2 border-primary/25 space-y-3"
                        >
                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                            {CHECKLIST_ITEMS.map((item) => {
                              const checked = Boolean(checklist[item.key]);
                              return (
                                <button
                                  key={item.key}
                                  type="button"
                                  disabled={!disclaimer.pot_validar}
                                  onClick={() =>
                                    setChecklist((prev) => ({
                                      ...prev,
                                      [item.key]: !prev[item.key],
                                    }))
                                  }
                                  className={`p-2 rounded-lg border text-left text-xs flex items-center gap-2 cursor-pointer disabled:opacity-50 ${
                                    checked
                                      ? "bg-primary/10 border-primary/40 text-primary font-semibold"
                                      : "bg-surface-container-lowest border-outline-variant/30 text-on-surface-variant"
                                  }`}
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

                          <div className="grid grid-cols-1 sm:grid-cols-4 gap-2.5">
                            <div>
                              <label className="block text-[10px] font-semibold text-on-surface-variant mb-1">
                                Hores Facturables Conciliades
                              </label>
                              <input
                                type="number"
                                step="0.25"
                                min="0"
                                disabled={!disclaimer.pot_validar}
                                value={horesConcEdit}
                                onChange={(e) => setHoresConcEdit(e.target.value)}
                                className="w-full px-2.5 py-1.5 text-xs font-mono font-bold rounded-lg border border-outline-variant bg-surface-container-lowest disabled:opacity-50"
                              />
                              {disclaimer.pot_validar && (
                                <div className="flex flex-wrap gap-1 mt-1">
                                  {Number(conc?.temps_i_gps?.hores_previstes || 0) > 0 && (
                                    <button
                                      type="button"
                                      onClick={() =>
                                        setHoresConcEdit(
                                          String(Number(conc?.temps_i_gps?.hores_previstes || 0))
                                        )
                                      }
                                      className="text-[10px] px-1.5 py-0.5 rounded bg-primary/10 text-primary font-semibold hover:bg-primary/20 cursor-pointer"
                                    >
                                      Pressup. ({Number(conc?.temps_i_gps?.hores_previstes || 0).toFixed(2)} h)
                                    </button>
                                  )}
                                  {Number(conc?.temps_i_gps?.hores_reals || 0) > 0 && (
                                    <button
                                      type="button"
                                      onClick={() =>
                                        setHoresConcEdit(
                                          String(Number(conc?.temps_i_gps?.hores_reals || 0))
                                        )
                                      }
                                      className="text-[10px] px-1.5 py-0.5 rounded bg-surface-container-high text-on-surface-variant font-semibold hover:bg-surface-container cursor-pointer"
                                    >
                                      Reals ({Number(conc?.temps_i_gps?.hores_reals || 0).toFixed(2)} h)
                                    </button>
                                  )}
                                </div>
                              )}
                            </div>
                            <div>
                              <label className="block text-[10px] font-semibold text-on-surface-variant mb-1">
                                Km Facturables (Vehicle)
                              </label>
                              <input
                                type="number"
                                step="1"
                                min="0"
                                disabled={!disclaimer.pot_validar}
                                value={kmConcEdit}
                                onChange={(e) => setKmConcEdit(e.target.value)}
                                className="w-full px-2.5 py-1.5 text-xs font-mono font-bold rounded-lg border border-outline-variant bg-surface-container-lowest disabled:opacity-50"
                              />
                              {conc?.vehicle?.preu_km_facturable != null && (
                                <span className="block text-[10px] text-on-surface-variant mt-1 font-mono">
                                  {Number(conc.vehicle.preu_km_facturable).toFixed(2)} €/km
                                </span>
                              )}
                            </div>
                            <div className="sm:col-span-2">
                              <label className="block text-[10px] font-semibold text-on-surface-variant mb-1">
                                Notes de Validació Tècnica
                              </label>
                              <input
                                type="text"
                                disabled={!disclaimer.pot_validar}
                                value={notesValidacio}
                                onChange={(e) => setNotesValidacio(e.target.value)}
                                placeholder="Anotacions de revisió tècnica abans de pre-facturar..."
                                className="w-full px-2.5 py-1.5 text-xs rounded-lg border border-outline-variant bg-surface-container-lowest disabled:opacity-50"
                              />
                            </div>
                          </div>

                          {/* Previsualització exacta de les línies que importarà la Pre-factura */}
                          {conc?.proposta_prefactura && conc.proposta_prefactura.linies.length > 0 && (
                            <div className="rounded-xl border border-outline-variant/35 bg-surface-container-lowest overflow-hidden">
                              <div className="px-3 py-2 bg-surface-container-low/80 border-b border-outline-variant/25 flex items-center justify-between text-xs">
                                <span className="font-bold text-primary flex items-center gap-1.5">
                                  <Receipt className="w-3.5 h-3.5 text-primary" />
                                  <span>
                                    Desglossament de la Pre-factura a Generar ({conc.proposta_prefactura.linies.length} partides)
                                  </span>
                                </span>
                                <span className="font-mono font-extrabold text-primary">
                                  {Number(conc.proposta_prefactura.liquid_exigible).toFixed(2)} € (IVA incl.)
                                </span>
                              </div>
                              <div className="overflow-x-auto">
                                <table className="w-full text-left text-[11px]">
                                  <thead className="bg-surface-container-low/40 text-on-surface-variant border-b border-outline-variant/20">
                                    <tr>
                                      <th className="py-1.5 px-3 font-semibold">Partida</th>
                                      <th className="py-1.5 px-2 font-semibold">Origen</th>
                                      <th className="py-1.5 px-2 text-right font-semibold">Quant.</th>
                                      <th className="py-1.5 px-2 text-right font-semibold">Preu u.</th>
                                      <th className="py-1.5 px-2 text-right font-semibold">IVA</th>
                                      <th className="py-1.5 px-3 text-right font-semibold">Subtotal</th>
                                    </tr>
                                  </thead>
                                  <tbody className="divide-y divide-outline-variant/15">
                                    {conc.proposta_prefactura.linies.map((pl, idx) => (
                                      <tr key={`${pl.origen}-${idx}`}>
                                        <td className="py-1.5 px-3 font-medium text-on-surface">
                                          {pl.concepte}
                                        </td>
                                        <td className="py-1.5 px-2">
                                          <span className="text-[9px] font-mono font-bold px-1.5 py-0.5 rounded bg-surface-container-high text-on-surface-variant">
                                            {pl.origen.replace(/_/g, " ")}
                                          </span>
                                        </td>
                                        <td className="py-1.5 px-2 text-right font-mono">
                                          {Number(pl.quantitat).toFixed(2)}
                                        </td>
                                        <td className="py-1.5 px-2 text-right font-mono">
                                          {Number(pl.preu_venda_unitari).toFixed(2)} €
                                        </td>
                                        <td className="py-1.5 px-2 text-right font-mono text-on-surface-variant">
                                          {Number(pl.tipus_iva).toFixed(0)}%
                                        </td>
                                        <td className="py-1.5 px-3 text-right font-mono font-bold text-primary">
                                          {Number(pl.subtotal).toFixed(2)} €
                                        </td>
                                      </tr>
                                    ))}
                                  </tbody>
                                  <tfoot className="bg-surface-container-low/60 border-t border-outline-variant/30 font-mono text-[11px]">
                                    <tr>
                                      <td colSpan={5} className="py-1.5 px-3 text-right text-on-surface-variant">
                                        Base imposable: {Number(conc.proposta_prefactura.base_imposable).toFixed(2)} € · IVA:{" "}
                                        {Number(conc.proposta_prefactura.quota_iva).toFixed(2)} €
                                      </td>
                                      <td className="py-1.5 px-3 text-right font-black text-primary">
                                        {Number(conc.proposta_prefactura.liquid_exigible).toFixed(2)} €
                                      </td>
                                    </tr>
                                  </tfoot>
                                </table>
                              </div>
                            </div>
                          )}

                          {actionError && (
                            <div className="p-2.5 rounded-lg bg-error-container/25 border border-error text-error text-xs font-semibold">
                              {actionError}
                            </div>
                          )}
                          {actionSuccess && (
                            <div className="p-2.5 rounded-lg bg-emerald-50 border border-emerald-300 text-emerald-900 text-xs font-semibold">
                              {actionSuccess}
                            </div>
                          )}

                          <div className="flex flex-wrap items-center gap-2">
                            <button
                              type="button"
                              data-testid="btn-validar-conciliacio"
                              disabled={!disclaimer.pot_validar || validant}
                              onClick={handleValidarConciliacio}
                              className="px-3.5 py-2 rounded-xl bg-primary text-on-primary text-xs font-bold inline-flex items-center gap-1.5 disabled:opacity-45 cursor-pointer"
                            >
                              {validant ? (
                                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                              ) : (
                                <ShieldCheck className="w-3.5 h-3.5" />
                              )}
                              <span>
                                {conc?.validacio?.validada
                                  ? "Actualitzar Validació"
                                  : "Validar Conciliació"}
                              </span>
                            </button>
                            <button
                              type="button"
                              data-testid="btn-passar-a-prefacturacio"
                              disabled={!disclaimer.pot_prefacturar || enviantPrefactura}
                              onClick={handlePassarAPrefacturacio}
                              className="px-3.5 py-2 rounded-xl bg-secondary text-white text-xs font-bold inline-flex items-center gap-1.5 disabled:opacity-45 cursor-pointer"
                            >
                              {enviantPrefactura ? (
                                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                              ) : (
                                <Receipt className="w-3.5 h-3.5" />
                              )}
                              <span>
                                {enviantPrefactura ? "Generant..." : "Passar a Pre-facturació"}
                              </span>
                            </button>
                          </div>
                        </div>
                      )}
                    </section>
                  )}
                </div>

                {/* RIGHT COLUMN (5 Cols): Ubicació/Plànol + Equip & Vehicle/Km + Avaluació Econòmica & Accions */}
                <div className="lg:col-span-5 space-y-5">
                  {/* CARD 3: Ubicació GIS, Finca i Plànol */}
                  <section className="bg-surface-container-lowest dark:bg-slate-900 p-5 rounded-xl shadow-xs border border-outline-variant/30 space-y-3.5">
                    <h3 className="font-section-title text-base text-primary dark:text-white border-b border-outline-variant/20 pb-2.5 flex items-center gap-2">
                      <MapPin className="w-4 h-4 text-primary" />
                      <span>2. Ubicació GIS, Finca i Plànol</span>
                    </h3>

                    <div>
                      <label className="block text-[11px] font-semibold text-on-surface-variant mb-1">
                        Finca del Client (Opcional)
                      </label>
                      <select
                        disabled={isLockedByInvoice || !formData.client_id || finques.length === 0}
                        value={formData.finca_id}
                        onChange={(e) => {
                          const selId = e.target.value;
                          const selF = finques.find((f) => f.id === selId);
                          setFormData((prev) => ({
                            ...prev,
                            finca_id: selId,
                            adreca:
                              selF?.adreca ||
                              (selF?.latitud && selF?.longitud
                                ? `${selF.latitud}, ${selF.longitud}`
                                : prev.adreca),
                            latitud: selF?.latitud != null ? Number(selF.latitud) : prev.latitud,
                            longitud: selF?.longitud != null ? Number(selF.longitud) : prev.longitud,
                          }));
                        }}
                        className="w-full px-3 py-2 bg-surface-container-low rounded-lg border border-outline-variant text-xs disabled:opacity-50"
                      >
                        <option value="">
                          {!formData.client_id
                            ? "Selecciona un client primer..."
                            : finques.length === 0
                              ? "Sense finques registrades"
                              : "Sense finca específica"}
                        </option>
                        {finques.map((f) => (
                          <option key={f.id} value={f.id}>
                            {f.nom || f.nom_finca || f.adreca || f.id}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div>
                      <label className="block text-[11px] font-semibold text-on-surface-variant mb-1">
                        Adreça / Coordenades GPS *
                      </label>
                      <input
                        required
                        disabled={isLockedByInvoice}
                        type="text"
                        placeholder="Ex: Polígon 4, Parcel·la 12 o 41.6176, 0.6200"
                        value={formData.adreca}
                        onChange={(e) => setFormData({ ...formData, adreca: e.target.value })}
                        className="w-full px-3 py-2 bg-surface-container-low rounded-lg border border-outline-variant focus:border-primary outline-none text-xs disabled:opacity-60"
                      />
                    </div>

                    {/* Mini-mapa cartogràfic real sempre visible */}
                    <div className="pt-1">
                      <MiniMapOT
                        adreca={formData.adreca}
                        latitud={formData.latitud}
                        longitud={formData.longitud}
                        codi={formData.codi}
                      />
                    </div>

                    <div>
                      <label className="block text-[11px] font-semibold text-on-surface-variant mb-1 flex items-center justify-between">
                        <span className="flex items-center gap-1">
                          <MapIcon className="w-3.5 h-3.5 text-primary" /> Plànol Tècnic (Opcional)
                        </span>
                        {formData.planol_id && !isLockedByInvoice && (
                          <button
                            type="button"
                            onClick={() => setFormData({ ...formData, planol_id: "" })}
                            className="text-[10px] text-error hover:underline cursor-pointer"
                          >
                            Desvincular
                          </button>
                        )}
                      </label>
                      <select
                        disabled={isLockedByInvoice}
                        value={formData.planol_id}
                        onChange={(e) => setFormData({ ...formData, planol_id: e.target.value })}
                        className="w-full px-3 py-2 bg-surface-container-low rounded-lg border border-outline-variant text-xs disabled:opacity-60"
                      >
                        <option value="">Sense plànol vinculat</option>
                        {planols.map((p) => (
                          <option key={p.id} value={p.id}>
                            [{p.codi_referencia}] {p.titol} ({p.tipus_fitxer})
                          </option>
                        ))}
                      </select>
                    </div>
                  </section>

                  {/* CARD 4: Assignació d'Equip (Quadrilla) i Vehicle Assignat */}
                  <section
                    className={`bg-surface-container-lowest dark:bg-slate-900 p-5 rounded-xl shadow-xs border space-y-3.5 ${
                      isFromPressupost && !formData.cap_de_colla_id
                        ? "border-amber-400 ring-2 ring-amber-200/60"
                        : "border-outline-variant/30"
                    }`}
                  >
                    <div className="flex items-center justify-between border-b border-outline-variant/20 pb-2.5">
                      <h3 className="font-section-title text-base text-primary dark:text-white flex items-center gap-2">
                        <Users className="w-4 h-4 text-primary" />
                        <span>3. Equip (Quadrilla) i Vehicle Assignat</span>
                      </h3>
                      <span className="font-mono text-[10px] font-bold text-on-surface-variant">
                        {collaOperariIds.length + (formData.cap_de_colla_id ? 1 : 0)} operaris
                      </span>
                    </div>

                    {isFromPressupost && !formData.cap_de_colla_id && (
                      <div className="p-3 rounded-xl bg-amber-50 dark:bg-amber-950/35 border border-amber-300 text-xs text-amber-950 dark:text-amber-200 flex items-start gap-2">
                        <AlertTriangle className="w-4 h-4 text-amber-700 shrink-0 mt-0.5" />
                        <span>
                          <strong>Assignació d&apos;operari necessària:</strong> el pressupost defineix{" "}
                          <strong>{economiaLive.hPrev.toFixed(2)} h</strong> de treball però no té cap operari assignat. Selecciona el Cap de Colla per activar l&apos;OT.
                        </span>
                      </div>
                    )}

                    <div>
                      <label className="block text-[11px] font-semibold text-on-surface-variant mb-1 flex items-center justify-between">
                        <span className="flex items-center gap-1">
                          <User className="w-3.5 h-3.5 text-primary" />
                          <span>
                            Cap de Colla (Responsable) {isFromPressupost ? "*" : ""}
                          </span>
                        </span>
                      </label>
                      <select
                        required={isFromPressupost}
                        disabled={isLockedByInvoice}
                        value={formData.cap_de_colla_id}
                        onChange={(e) => {
                          const newCap = e.target.value;
                          setFormData((prev) => ({
                            ...prev,
                            cap_de_colla_id: newCap,
                            estat: newCap && prev.estat === "PENDENT" ? "ASSIGNADA" : prev.estat,
                          }));
                          setCollaOperariIds((prev) => prev.filter((id) => id !== newCap));
                        }}
                        className="w-full px-3 py-2 bg-surface-container-low rounded-lg border border-outline-variant focus:border-primary outline-none text-xs disabled:opacity-60"
                      >
                        <option value="">
                          {isFromPressupost
                            ? "Selecciona el Cap de Colla responsable..."
                            : "Pendent d'assignar"}
                        </option>
                        {operaris.map((op) => (
                          <option key={op.id} value={op.id}>
                            {op.nom} {op.cognoms || ""} — {op.rol}
                            {op.carnet_conduir ? ` (Carnet ${op.carnet_conduir})` : ""}
                          </option>
                        ))}
                      </select>
                    </div>

                    {/* Operaris de suport */}
                    {!isLockedByInvoice && (
                      <div className="flex gap-2">
                        <select
                          value={selectedCollaCandidate}
                          onChange={(e) => setSelectedCollaCandidate(e.target.value)}
                          className="flex-1 px-2.5 py-1.5 bg-surface-container-low rounded-lg border border-outline-variant text-xs outline-none"
                        >
                          <option value="">Afegir operari de suport a la colla...</option>
                          {operaris
                            .filter(
                              (op) =>
                                op.id !== formData.cap_de_colla_id &&
                                !collaOperariIds.includes(op.id)
                            )
                            .map((op) => (
                              <option key={op.id} value={op.id}>
                                {op.nom} {op.cognoms || ""} — {op.rol}
                              </option>
                            ))}
                        </select>
                        <button
                          type="button"
                          disabled={!selectedCollaCandidate}
                          onClick={() => addOperariToColla()}
                          className="px-3 py-1.5 rounded-lg bg-primary text-on-primary text-xs font-bold disabled:opacity-40 cursor-pointer"
                        >
                          + Afegir
                        </button>
                      </div>
                    )}

                    {collaOperariIds.length > 0 && (
                      <div className="space-y-1">
                        {collaOperariIds.map((cId) => {
                          const op = operaris.find((o) => o.id === cId);
                          if (!op) return null;
                          return (
                            <div
                              key={cId}
                              className="px-2.5 py-1.5 rounded-lg bg-surface-container-low border border-outline-variant/30 flex items-center justify-between text-xs"
                            >
                              <span>
                                {op.nom} {op.cognoms || ""}
                              </span>
                              {!isLockedByInvoice && (
                                <button
                                  type="button"
                                  onClick={() => removeOperariFromColla(cId)}
                                  className="text-error hover:bg-error/10 p-0.5 rounded cursor-pointer"
                                >
                                  <X className="w-3.5 h-3.5" />
                                </button>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    )}

                    {/* Vehicle Assignat & Km Previstos */}
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 pt-2 border-t border-outline-variant/20">
                      <div className="sm:col-span-2">
                        <label className="block text-[11px] font-semibold text-on-surface-variant mb-1 flex items-center gap-1">
                          <Truck className="w-3.5 h-3.5 text-primary" /> Vehicle Assignat (Flota)
                        </label>
                        <select
                          disabled={isLockedByInvoice}
                          value={formData.vehicle_id}
                          onChange={(e) => setFormData({ ...formData, vehicle_id: e.target.value })}
                          className="w-full px-2.5 py-2 bg-surface-container-low rounded-lg border border-outline-variant focus:border-primary outline-none text-xs disabled:opacity-60"
                        >
                          <option value="">Sense vehicle assignat</option>
                          {vehicles.map((v) => (
                            <option key={v.id} value={v.id}>
                              {v.matricula} — {v.marca} {v.model}
                              {v.carnet_necessari ? ` [${v.carnet_necessari}]` : ""}
                            </option>
                          ))}
                        </select>
                      </div>

                      <div>
                        <label className="block text-[11px] font-semibold text-on-surface-variant mb-1">
                          Desplaç. (km)
                        </label>
                        <input
                          type="number"
                          min="0"
                          step="1"
                          disabled={isLockedByInvoice}
                          value={kmImputatsInput}
                          onChange={(e) => setKmImputatsInput(e.target.value)}
                          className="w-full px-2.5 py-2 bg-surface-container-low rounded-lg border border-outline-variant focus:border-primary outline-none text-xs font-mono font-bold disabled:opacity-60"
                        />
                      </div>
                    </div>

                    {/* Resum de Validació i Pick-Out del Vehicle (Conciliació) */}
                    {isExistingOT && conc?.vehicle && (
                      <div className="p-3 rounded-lg bg-surface-container-low border border-outline-variant/30 text-xs space-y-2">
                        <div className="flex items-center justify-between">
                          <span className="font-bold text-primary flex items-center gap-1.5">
                            <Truck className="w-3.5 h-3.5 text-primary" /> Validació Pick-Out Vehicle
                          </span>
                          <span
                            className={`font-mono text-[10px] px-2 py-0.5 rounded-full font-bold ${
                              conc.vehicle.estat_pickout === "COMPLERT"
                                ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300"
                                : conc.vehicle.estat_pickout === "RETORNAT"
                                ? "bg-sky-100 text-sky-800 dark:bg-sky-950/40 dark:text-sky-300"
                                : "bg-amber-100 text-amber-800 dark:bg-amber-950/40 dark:text-amber-300"
                            }`}
                          >
                            {conc.vehicle.estat_pickout || "PENDENT"}
                          </span>
                        </div>
                        <div className="grid grid-cols-3 gap-2 text-center text-[11px]">
                          <div className="p-1.5 rounded bg-surface-container-lowest border border-outline-variant/20">
                            <span className="text-[10px] text-on-surface-variant block">Odòmetre Inici</span>
                            <span className="font-mono font-bold">
                              {conc.vehicle.odometre_inici != null ? `${conc.vehicle.odometre_inici} km` : "—"}
                            </span>
                          </div>
                          <div className="p-1.5 rounded bg-surface-container-lowest border border-outline-variant/20">
                            <span className="text-[10px] text-on-surface-variant block">Odòmetre Final</span>
                            <span className="font-mono font-bold">
                              {conc.vehicle.odometre_fi != null ? `${conc.vehicle.odometre_fi} km` : "—"}
                            </span>
                          </div>
                          <div className="p-1.5 rounded bg-surface-container-lowest border border-outline-variant/20">
                            <span className="text-[10px] text-on-surface-variant block">Km Facturables</span>
                            <span className="font-mono font-bold text-primary">
                              {conc.vehicle.km_imputats || Number(kmImputatsInput) || 0} km (
                              {Number(conc.vehicle.valor_desplacament_pvp || 0).toFixed(2)} €)
                            </span>
                          </div>
                        </div>
                      </div>
                    )}

                    {avísCarnet && (
                      <div className="p-2.5 rounded-lg bg-error-container/30 border border-error text-error text-xs font-semibold flex items-start gap-1.5">
                        <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                        <span>{avísCarnet}</span>
                      </div>
                    )}
                  </section>

                  {/* CARD 5: AVALUACIÓ ECONÒMICA REAL I DOCK D'ACCIONS */}
                  <section className="bg-primary text-on-primary p-5 rounded-xl shadow-lg space-y-4">
                    <div className="flex items-center justify-between border-b border-white/15 pb-2.5">
                      <span className="font-body-strong text-xs flex items-center gap-1.5">
                        <TrendingUp className="w-4 h-4" />
                        <span>Avaluació Econòmica Real (OT)</span>
                      </span>
                      <span className="font-mono text-[10px] bg-white/15 px-2 py-0.5 rounded-full font-bold">
                        {formData.cap_de_colla_id ? "ASSIGNADA" : "PENDENT"}
                      </span>
                    </div>

                    {/* Commercial Valuation (Visible to ENGINYER, SECRETARIA, BOSS) */}
                    <div className="grid grid-cols-2 gap-2.5 text-xs">
                      <div className="p-2.5 rounded-lg bg-white/10">
                        <span className="text-[10px] opacity-80 block">
                          Mà d&apos;Obra ({economiaLive.hPrev.toFixed(2)} h · {economiaLive.ratePvp.toFixed(2)} €/h)
                        </span>
                        <span className="font-mono font-bold text-sm">
                          {economiaLive.maObraPrevPvp.toFixed(2)} €
                        </span>
                        {isExistingOT && economiaLive.hReal > 0 && (
                          <span className="block text-[10px] font-mono opacity-85">
                            Real: {economiaLive.hReal.toFixed(2)} h ({economiaLive.maObraRealPvp.toFixed(2)} €)
                          </span>
                        )}
                      </div>

                      <div className="p-2.5 rounded-lg bg-white/10">
                        <span className="text-[10px] opacity-80 block">
                          Materials Picking ({liniesPicking.length} lín.)
                        </span>
                        <span className="font-mono font-bold text-sm">
                          {economiaLive.materialsPvp.toFixed(2)} €
                        </span>
                      </div>

                      <div className="p-2.5 rounded-lg bg-white/10">
                        <span className="text-[10px] opacity-80 block">Vehicle i Desplaçament</span>
                        <span className="font-mono font-bold text-xs truncate block">
                          {selectedVehicleObj?.matricula || "Sense vehicle"} · {conc?.resum_comercial?.km_imputats ?? economiaLive.km} km
                        </span>
                        {isExistingOT && Number(conc?.resum_comercial?.valor_desplacament_pvp || 0) > 0 && (
                          <span className="block text-[10px] font-mono opacity-85">
                            Desplaç.: {Number(conc?.resum_comercial?.valor_desplacament_pvp).toFixed(2)} €
                          </span>
                        )}
                      </div>

                      <div className="p-2.5 rounded-lg bg-white/20">
                        <span className="text-[10px] opacity-90 block font-semibold">
                          {isExistingOT && conc?.proposta_prefactura
                            ? "Pre-factura Conciliada (IVA incl.)"
                            : importPressupostatNet > 0
                              ? "Base Pressupostada"
                              : "Total Valorat (Base)"}
                        </span>
                        <span className="font-mono font-black text-base">
                          {isExistingOT && conc?.proposta_prefactura
                            ? `${Number(conc.proposta_prefactura.liquid_exigible).toFixed(2)} €`
                            : `${economiaLive.baseIngressos.toFixed(2)} €`}
                        </span>
                        {isExistingOT && conc?.proposta_prefactura ? (
                          <span className="block text-[10px] font-mono opacity-85">
                            Base: {Number(conc.proposta_prefactura.base_imposable).toFixed(2)} €
                            {importPressupostatBrut > 0
                              ? ` · Pressup.: ${importPressupostatBrut.toFixed(2)} €`
                              : ""}
                          </span>
                        ) : (
                          importPressupostatBrut > 0 && (
                            <span className="block text-[10px] font-mono opacity-85">
                              IVA incl.: {importPressupostatBrut.toFixed(2)} €
                            </span>
                          )
                        )}
                      </div>
                    </div>

                    {/* Internal Costs & Margin (BOSS / SECRETARIA ONLY — Strict Barrera Econòmica) */}
                    {potVeureCostosInterns && (
                      <div className="p-3 rounded-xl bg-slate-950/30 border border-white/15 space-y-2 text-xs">
                        <div className="flex items-center justify-between text-[11px] font-bold opacity-90">
                          <span>Costos Interns i Marge Previst</span>
                          <span
                            className={`font-mono px-2 py-0.5 rounded-full ${
                              economiaLive.baseIngressos > 0 && economiaLive.margePrevistPct < 15
                                ? "bg-rose-500/30 text-rose-100"
                                : "bg-emerald-500/30 text-emerald-100"
                            }`}
                          >
                            Marge: {economiaLive.margePrevistEur.toFixed(2)} € (
                            {economiaLive.margePrevistPct.toFixed(1)}%)
                          </span>
                        </div>
                        <div className="grid grid-cols-3 gap-2 font-mono text-[11px]">
                          <div>
                            <span className="opacity-70 block text-[10px]">PMP Materials</span>
                            <strong>{economiaLive.materialsPmp.toFixed(2)} €</strong>
                          </div>
                          <div>
                            <span className="opacity-70 block text-[10px]">Cost Mà d&apos;Obra</span>
                            <strong>{economiaLive.costMaObraPrev.toFixed(2)} €</strong>
                          </div>
                          <div>
                            <span className="opacity-70 block text-[10px]">Cost Flota</span>
                            <strong>{economiaLive.costFlota.toFixed(2)} €</strong>
                          </div>
                        </div>
                        {isExistingOT && conc?.resum_intern?.marge_real_eur != null && (
                          <div className="pt-1.5 border-t border-white/10 flex items-center justify-between font-mono text-[11px]">
                            <span className="opacity-80">Marge Real Liquidat:</span>
                            <strong>
                              {Number(conc.resum_intern.marge_real_eur).toFixed(2)} € (
                              {Number(conc.resum_intern.marge_real_percentatge ?? 0).toFixed(1)}%)
                            </strong>
                          </div>
                        )}
                      </div>
                    )}

                    {/* Feedback / Error / IA Draft */}
                    {modalFeedback && (
                      <div
                        className={`p-3 rounded-lg text-xs border flex flex-col gap-1 ${
                          modalFeedback.type === "ok"
                            ? "bg-emerald-950/50 border-emerald-400/50 text-emerald-100"
                            : "bg-rose-950/60 border-rose-400/60 text-rose-100"
                        }`}
                      >
                        <div className="flex items-start gap-1.5">
                          {modalFeedback.type === "ok" ? (
                            <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-300 mt-0.5" />
                          ) : (
                            <AlertCircle className="w-4 h-4 shrink-0 text-rose-300 mt-0.5" />
                          )}
                          <span>{modalFeedback.text}</span>
                        </div>
                        {modalFeedback.href && (
                          <Link
                            href={modalFeedback.href}
                            onClick={onClose}
                            className="text-[11px] font-bold underline self-end"
                          >
                            Obrir Pressupost →
                          </Link>
                        )}
                      </div>
                    )}

                    {iaDraft && (
                      <div className="p-3 rounded-lg bg-white/10 border border-white/20 space-y-2 text-xs">
                        <div className="flex items-center justify-between">
                          <span className="font-bold">Esborrany Copilot (HITL)</span>
                          {iaDraft.total_estimat != null && (
                            <span className="font-mono font-bold">
                              {Number(iaDraft.total_estimat).toFixed(2)} €
                            </span>
                          )}
                        </div>
                        {iaDraft.resum_tecnic && (
                          <p className="text-[11px] opacity-90">{iaDraft.resum_tecnic}</p>
                        )}
                        <button
                          type="button"
                          disabled={pressupostLoading}
                          onClick={handleConfirmarEsborranyIA}
                          className="w-full py-1.5 rounded-lg bg-white text-primary font-bold text-xs cursor-pointer"
                        >
                          Consolidar Pressupost Oficial
                        </button>
                      </div>
                    )}

                    {/* Action Buttons */}
                    <div className="space-y-2 pt-1">
                      {!isLockedByInvoice && (
                        <button
                          type="submit"
                          disabled={saving || Boolean(avísCarnet)}
                          className="w-full py-2.5 px-4 rounded-xl bg-white text-primary hover:bg-white/95 font-bold text-xs shadow-sm flex items-center justify-center gap-2 disabled:opacity-50 cursor-pointer"
                        >
                          {saving ? (
                            <Loader2 className="w-4 h-4 animate-spin" />
                          ) : (
                            <Save className="w-4 h-4" />
                          )}
                          <span>
                            {saving
                              ? "Desant..."
                              : isFromPressupost
                                ? "Crear Ordre de Treball des del Pressupost"
                                : isExistingOT
                                  ? "Desar Canvis de la Fulla 360°"
                                  : "Generar Tasca (Ordre de Treball)"}
                          </span>
                        </button>
                      )}

                      {mode === "CREATE" && (
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                          <button
                            type="button"
                            disabled={pressupostLoading}
                            onClick={handleGenerarPressupost}
                            className="py-2 px-3 rounded-xl bg-white/15 hover:bg-white/25 text-white text-xs font-bold flex items-center justify-center gap-1.5 cursor-pointer disabled:opacity-50"
                          >
                            <Receipt className="w-3.5 h-3.5" />
                            <span>{pressupostLoading ? "Generant..." : "Generar Pressupost"}</span>
                          </button>
                          <button
                            type="button"
                            disabled={!copilotActiu || copilotLoading}
                            onClick={handlePressupostCopilot}
                            title={
                              copilotActiu
                                ? "Proposta de pressupost amb Copilot IA local"
                                : "Activa el Node IA local per usar el Copilot"
                            }
                            className="py-2 px-3 rounded-xl bg-secondary text-white hover:opacity-90 text-xs font-bold flex items-center justify-center gap-1.5 cursor-pointer disabled:opacity-45"
                          >
                            <Sparkles className="w-3.5 h-3.5" />
                            <span>{copilotLoading ? "Consultant..." : "Pressupost Copilot"}</span>
                          </button>
                        </div>
                      )}

                      {isExistingOT && (
                        <div className="flex flex-wrap items-center gap-2 pt-1">
                          {onFocusMapa && resolvedFeinaId && (
                            <button
                              type="button"
                              onClick={() => {
                                onFocusMapa(resolvedFeinaId);
                                onClose();
                              }}
                              className="flex-1 py-2 px-3 rounded-xl bg-white/15 hover:bg-white/25 text-white text-xs font-bold inline-flex items-center justify-center gap-1 cursor-pointer"
                            >
                              <MapPin className="w-3.5 h-3.5" /> Mapa GIS
                            </button>
                          )}
                          <Link
                            href="/gestio/planols"
                            onClick={onClose}
                            className="flex-1 py-2 px-3 rounded-xl bg-white/15 hover:bg-white/25 text-white text-xs font-bold inline-flex items-center justify-center gap-1"
                          >
                            <Layers className="w-3.5 h-3.5" /> Plànols GIS
                          </Link>
                          {potAccedirComptabilitat &&
                            facturaDoc &&
                            facturaDoc.estat_document === "ESBORRANY_PREFACTURA" && (
                              <Link
                                href={`/gestio/comptabilitat?tab=PREFACTURACIO&prefactura_id=${facturaDoc.id}`}
                                onClick={onClose}
                                className="w-full py-2 px-3 rounded-xl bg-amber-500 hover:bg-amber-400 text-slate-950 text-xs font-bold inline-flex items-center justify-center gap-1"
                              >
                                <Receipt className="w-3.5 h-3.5" /> Editar Pre-factura a Comptabilitat
                              </Link>
                            )}
                        </div>
                      )}
                    </div>
                  </section>
                </div>
              </div>
            </form>
          )}
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

      {/* Modal Consulta Comercial de Pre-factura / Factura */}
      <FacturaComercialModal facturaId={facturaModalId} onClose={() => setFacturaModalId(null)} />
    </>
  );
}
