"use client";

import React, { Suspense, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
  Activity,
  AlertTriangle,
  Banknote,
  Building2,
  CheckCircle2,
  Download,
  Edit3,
  FileCheck2,
  FileText,
  Lock,
  Package,
  Plus,
  QrCode,
  Receipt,
  RefreshCw,
  Scale,
  Search,
  Send,
  ShieldCheck,
  Trash2,
  TrendingUp,
  Users,
  X,
} from "lucide-react";
import { useGestio } from "@/lib/gestio-context";
import { apiFetch, getApiBaseUrl } from "@/lib/api";
import {
  AgingBarChart,
  Evolucio12MChart,
  MargesVerticalChart,
  TresoreriaProjeccioChart,
  WaterfallChart,
} from "@/components/comptabilitat/EconomicCharts";

interface FacturaLinia {
  id?: string;
  obra_id?: string | null;
  centre_de_cost_id?: string;
  article_id?: string | null;
  concepte: string;
  descripcio_detall?: string | null;
  compte_pgc: string;
  quantitat: number;
  quantitat_merma?: number;
  preu_venda_unitari: number;
  descompte_aplicat_pct: number;
  tipus_iva: number;
  tipus_recarrec_equivalencia?: number;
  subtotal?: number;
}

interface Factura {
  id: string;
  exercici?: number;
  numero_factura: number;
  serie: string;
  num_serie_verifactu?: string | null;
  tipus_factura?: string;
  tipus_rectificacio?: string | null;
  client_id: string;
  client_nom?: string | null;
  estat_document?: string;
  estat_anulacio?: string;
  data_emissio?: string | null;
  data_operacio?: string | null;
  data_venciment?: string | null;
  metode_pagament?: string;
  referencia_client?: string | null;
  es_inversio_subjecte_passiu?: boolean;
  notes_factura?: string | null;
  base_imposable: number;
  quota_iva: number;
  quota_recarrec_equivalencia?: number;
  import_total_verifactu?: number;
  import_retencio: number;
  import_retencio_garantia_4308?: number;
  import_suplits: number;
  liquid_exigible: number;
  hash_sha256: string;
  hash_anterior?: string;
  hash_anulacio_sha256?: string | null;
  motiu_anulacio?: string | null;
  estat_cobrament: string;
  import_cobrat?: number;
  data_cobrament_real?: string | null;
  estat_enviament: string;
  estat_aeat?: string;
  csv_aeat?: string | null;
  codi_error_aeat?: string | null;
  descripcio_error_aeat?: string | null;
  darrer_error_aeat?: string | null;
  linies?: FacturaLinia[];
  ordres_treball_codis?: string[];
}

interface ClientOption {
  id: string;
  rao_social: string;
  nif: string;
}

interface ArticleMagatzemOption {
  id: string;
  referencia_inventari: string;
  nom: string;
  unitat_mesura?: string;
  preu_venda: number;
  estoc_disponible?: number;
}

interface DashboardEconomic {
  facturacio_neta: number;
  cost_directe_obra: number;
  marge_brut_eur: number;
  marge_brut_pct: number;
  despeses_fixes_estructura: number;
  ebitda_operatiu_eur: number;
  ebitda_operatiu_pct: number;
  break_even_facturacio_necessaria: number;
  break_even_assolit: boolean;
  alertes_erosio_marge: Array<{
    article_id: string;
    referencia: string;
    nom: string;
    preu_cost_mitja: number;
    preu_cost_ultim: number;
    preu_venda_tarifa: number;
    marge_actual_pct: number;
    llindar_minim_pct: number;
  }>;
  capital_immobilitzat_90d_eur: number;
  cash_flow_operatiu_real: number;
  burn_rate_mes_seguent: number;
  guardacaixa_fiscal_iva_303: number;
  projeccio_tresoreria_30d: number;
  projeccio_tresoreria_60d: number;
  projeccio_tresoreria_90d: number;
  dso_dies_mitjana_cobrament: number;
  aging_impagats: Record<string, number>;
  total_retencions_garantia_4308_excloses_aging: number;
  cost_flota_eur_km_mitja: number;
  mrr_mensual_actiu: number;
  cobertura_estructura_mrr_pct: number;
  alerta_concentracio_pareto_25pct: boolean;
  waterfall_mensual: Record<string, number>;
  evolucio_12m: Array<{
    mes: string;
    ingressos: number;
    despeses: number;
    ebitda_pct: number;
  }>;
  marges_per_vertical: Array<{ vertical: string; marge_eur: number }>;
}

interface WIPControl {
  total_wip_valorat_pvp: number;
  total_cost_wip_avancat: number;
  nombre_ots_en_wip: number;
  nombre_ots_envellides_critiques: number;
  items: Array<{
    ordre_treball_id: string;
    codi_ot: string;
    titol_ot?: string | null;
    client_id: string;
    client_nom?: string | null;
    estat_ot?: string | null;
    hores_imputades?: number;
    preu_hora_aplicat?: number;
    pvp_materials?: number;
    dies_en_wip: number;
    valor_wip_pvp: number;
    cost_wip_avancat: number;
    es_wip_envellit_alerta: boolean;
  }>;
}

interface RetencioGarantia {
  id: string;
  tipus: string;
  factura_client_id?: string;
  import_retingut: number;
  data_retencio: string;
  data_venciment_garantia: string;
  dies_fins_venciment: number;
  estat: string;
  alerta_venciment_proper: boolean;
}

interface Art80Item {
  factura_id: string;
  numero_factura: number;
  serie: string;
  data_emissio: string;
  data_limit_art80: string;
  base_imposable: number;
  quota_iva: number;
  dies_impagada: number;
  estat_art80: string;
}

interface OperariCost {
  usuari_id: string;
  nom_complet: string;
  cost_hora_referencia: number;
  salari_brut_i_ss_visible: string | null;
  hores_fitxades_mes: number;
  hores_imputades_ot_mes: number;
  ratio_eficiencia_pct: number;
  cost_hora_efectiu_mensual: number | null;
  alerta_improductivitat: boolean;
}

interface ContracteMRR {
  contracte_id: string;
  codi_contracte: string;
  quota_mensual_mrr: number;
  cost_real_ots_periode: number;
  marge_net_contracte: number;
  sinistralitat_pct: number;
  semafor: string;
}

interface TiquetDespesa {
  id: string;
  categoria: string;
  data_tiquet: string;
  nif_emissor?: string;
  nif_comprador?: string;
  rao_social?: string;
  base_imposable: number;
  quota_iva: number;
  import_total: number;
  subcompte_pgc?: string;
  estat_aprovacio: string;
  estat_fiscal: string;
  requereix_aprovacio_boss: boolean;
  custodia_paper_confirmada: boolean;
  nom_fitxer_visible?: string;
}

interface OTCostMarge {
  ordre_treball_id: string;
  codi?: string;
  titol?: string;
  ingressos_nets_eur: number;
  desglossament_costos: {
    materials_picking_pmp_eur: number;
    mermes_imputades_eur: number;
    tiquets_camp_ocr_eur: number;
    ma_obra_real_eur: number;
    flota_real_eur: number;
  };
  cost_total_real_eur: number;
  marge_brut_eur: number;
  marge_brut_pct: number;
  alerta_desviacio_marge: boolean;
}

interface DespesaComptableItem {
  id: string;
  ordre_treball_id?: string | null;
  tiquet_id?: string | null;
  merma_id?: string | null;
  concepte: string;
  subcompte: string;
  base_imposable: number;
  quota_iva: number;
  import_total: number;
  estat: string;
  origen: string;
  created_at: string;
}

interface DespesaFixaItem {
  id: string;
  concepte: string;
  categoria: "LLOGUER" | "SUBMINISTRAMENTS" | "ASSEGURANCES" | "GESTORIA" | "SOFTWARE" | "ALTRES";
  import_base: number;
  quota_iva: number;
  periodicitat: "MENSUAL" | "TRIMESTRAL" | "ANUAL";
  import_mensual_normalitzat: number;
  iva_mensual_normalitzat: number;
  dia_carrec: number;
  actiu: boolean;
  created_at: string;
}

interface Norma43Moviment {
  data_operacio: string;
  concepte: string;
  import_moviment: number;
  saldo_resultant: number;
  huella_sha256: string;
  duplicat_rebutjat: boolean;
  factura_suggerida_id?: string;
}

type TabKey =
  | "DASHBOARD"
  | "DESPESES_FIXES"
  | "WIP_CONTROL"
  | "PREFACTURACIO"
  | "VERIFACTU"
  | "MARGES_OT"
  | "OPERARIS_MRR"
  | "TIQUETS"
  | "NORMA43";

function round2(val: number): number {
  return Math.round((val + Number.EPSILON) * 100) / 100;
}

function ComptabilitatContent() {
  const searchParams = useSearchParams();
  const { rolActiu } = useGestio();
  const [tabActiva, setTabActiva] = useState<TabKey>("DASHBOARD");
  const [criteriCaixa, setCriteriCaixa] = useState(false);
  const [periode, setPeriode] = useState("MES_ACTUAL");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const [dashboard, setDashboard] = useState<DashboardEconomic | null>(null);
  const [factures, setFactures] = useState<Factura[]>([]);
  const [wip, setWip] = useState<WIPControl | null>(null);
  const [retencions, setRetencions] = useState<RetencioGarantia[]>([]);
  const [art80, setArt80] = useState<Art80Item[]>([]);
  const [operarisCost, setOperarisCost] = useState<OperariCost[]>([]);
  const [contractesMrr, setContractesMrr] = useState<ContracteMRR[]>([]);
  const [tiquets, setTiquets] = useState<TiquetDespesa[]>([]);
  const [margesOt, setMargesOt] = useState<OTCostMarge[]>([]);
  const [despesesAnalitiques, setDespesesAnalitiques] = useState<DespesaComptableItem[]>([]);
  const [despesesFixes, setDespesesFixes] = useState<DespesaFixaItem[]>([]);
  const [desgloseMap, setDesgloseMap] = useState<Record<string, { carb: string; adbl: string }>>({});

  // Modal Registre de Cobrament Manual
  const [facturaCobrament, setFacturaCobrament] = useState<Factura | null>(null);
  const [cobramentEstat, setCobramentEstat] = useState<"COBRADA" | "PARCIAL" | "PENDENT" | "IMPAGADA">("COBRADA");
  const [cobramentImport, setCobramentImport] = useState<string>("");
  const [cobramentData, setCobramentData] = useState<string>("");
  const [cobramentNotes, setCobramentNotes] = useState<string>("");
  const [savingCobrament, setSavingCobrament] = useState(false);

  // Modal / Formulari Despeses Fixes
  const [modalDespesaFixa, setModalDespesaFixa] = useState(false);
  const [editingDespesaFixa, setEditingDespesaFixa] = useState<DespesaFixaItem | null>(null);
  const [dfConcepte, setDfConcepte] = useState("");
  const [dfCategoria, setDfCategoria] = useState<DespesaFixaItem["categoria"]>("LLOGUER");
  const [dfImportBase, setDfImportBase] = useState("");
  const [dfQuotaIva, setDfQuotaIva] = useState("0");
  const [dfPeriodicitat, setDfPeriodicitat] = useState<DespesaFixaItem["periodicitat"]>("MENSUAL");
  const [dfDiaCarrec, setDfDiaCarrec] = useState("5");
  const [savingDespesaFixa, setSavingDespesaFixa] = useState(false);
  const [clientsList, setClientsList] = useState<ClientOption[]>([]);
  const [articlesMagatzem, setArticlesMagatzem] = useState<ArticleMagatzemOption[]>([]);

  // Estat Norma 43
  const [textC43, setTextC43] = useState("");
  const [movimentsC43, setMovimentsC43] = useState<Norma43Moviment[]>([]);

  // Modal Emissió Factura Veri*factu, Rectificativa Sèrie R, Anul·lació i Declaració Responsable SIF
  const [modalFactura, setModalFactura] = useState(false);
  const [clientIdInput, setClientIdInput] = useState("");
  const [concepteInput, setConcepteInput] = useState("");
  const [preuInput, setPreuInput] = useState("0");
  const [esIsp, setEsIsp] = useState(false);
  const [retGarantiaPct, setRetGarantiaPct] = useState("0");
  const [facturaRectificar, setFacturaRectificar] = useState<Factura | null>(null);
  const [motiuRectificar, setMotiuRectificar] = useState("");
  const [tipusRectificar, setTipusRectificar] = useState<"R1" | "R2" | "R3" | "R4">("R1");
  const [modalitatRectificar, setModalitatRectificar] = useState<"S" | "I">("S");
  const [facturaAnular, setFacturaAnular] = useState<Factura | null>(null);
  const [motiuAnular, setMotiuAnular] = useState("");
  const [reenviantAeatId, setReenviantAeatId] = useState<string | null>(null);
  const [modalDeclaracioSif, setModalDeclaracioSif] = useState(false);
  const [declaracioSif, setDeclaracioSif] = useState<Record<string, any> | null>(null);
  const [convertintWipId, setConvertintWipId] = useState<string | null>(null);

  // Editor de Pre-factures (ESBORRANY_PREFACTURA)
  const [editingPrefactura, setEditingPrefactura] = useState<Factura | null>(null);
  const [creatingPrefactura, setCreatingPrefactura] = useState(false);
  const [prefClientId, setPrefClientId] = useState("");
  const [prefTipusFactura, setPrefTipusFactura] = useState("F1");
  const [prefDataEmissio, setPrefDataEmissio] = useState("");
  const [prefDataOperacio, setPrefDataOperacio] = useState("");
  const [prefDataVenciment, setPrefDataVenciment] = useState("");
  const [prefMetodePagament, setPrefMetodePagament] = useState("TRANSFERENCIA");
  const [prefReferenciaClient, setPrefReferenciaClient] = useState("");
  const [prefNotesFactura, setPrefNotesFactura] = useState("");
  const [prefEsIsp, setPrefEsIsp] = useState(false);
  const [prefRetIrpfPct, setPrefRetIrpfPct] = useState("0");
  const [prefRetGarantiaPct, setPrefRetGarantiaPct] = useState("0");
  const [prefLinies, setPrefLinies] = useState<FacturaLinia[]>([]);
  const [cercaMaterialPref, setCercaMaterialPref] = useState("");
  const [materialPrefDropdownOpen, setMaterialPrefDropdownOpen] = useState(false);
  const [materialPrefQt, setMaterialPrefQt] = useState("1");
  const [savingPrefactura, setSavingPrefactura] = useState(false);
  const [emittingPrefId, setEmittingPrefId] = useState<string | null>(null);
  const [handledParamPrefId, setHandledParamPrefId] = useState<string | null>(null);

  const obrirNovaPrefactura = () => {
    const avui = new Date().toISOString().slice(0, 10);
    setEditingPrefactura(null);
    setCreatingPrefactura(true);
    setPrefClientId("");
    setPrefTipusFactura("F1");
    setPrefDataEmissio(avui);
    setPrefDataOperacio("");
    setPrefDataVenciment(avui);
    setPrefMetodePagament("TRANSFERENCIA");
    setPrefReferenciaClient("");
    setPrefNotesFactura("");
    setPrefEsIsp(false);
    setPrefRetIrpfPct("0");
    setPrefRetGarantiaPct("0");
    setCercaMaterialPref("");
    setMaterialPrefQt("1");
    setMaterialPrefDropdownOpen(false);
    setPrefLinies([
      {
        concepte: "",
        compte_pgc: "705000",
        quantitat: 1,
        preu_venda_unitari: 0,
        descompte_aplicat_pct: 0,
        tipus_iva: 21,
      },
    ]);
  };

  const tancarModalPrefactura = () => {
    setEditingPrefactura(null);
    setCreatingPrefactura(false);
    setMaterialPrefDropdownOpen(false);
  };

  const obrirEditorPrefactura = (f: Factura) => {
    const baseImp = Number(f.base_imposable || 0);
    const pctIrpf =
      baseImp > 0 && Number(f.import_retencio || 0) > 0
        ? round2((Number(f.import_retencio) / baseImp) * 100)
        : 0;
    const pctGar =
      baseImp > 0 && Number(f.import_retencio_garantia_4308 || 0) > 0
        ? round2((Number(f.import_retencio_garantia_4308 || 0) / baseImp) * 100)
        : 0;
    setCreatingPrefactura(false);
    setEditingPrefactura(f);
    setPrefClientId(f.client_id);
    setPrefTipusFactura(f.tipus_factura || "F1");
    setCercaMaterialPref("");
    setMaterialPrefQt("1");
    setMaterialPrefDropdownOpen(false);
    setPrefDataEmissio(
      f.data_emissio ? String(f.data_emissio).slice(0, 10) : new Date().toISOString().slice(0, 10)
    );
    setPrefDataOperacio(f.data_operacio ? String(f.data_operacio).slice(0, 10) : "");
    setPrefDataVenciment(
      f.data_venciment
        ? String(f.data_venciment).slice(0, 10)
        : new Date().toISOString().slice(0, 10)
    );
    setPrefMetodePagament(f.metode_pagament || "TRANSFERENCIA");
    setPrefReferenciaClient(f.referencia_client || "");
    setPrefNotesFactura(f.notes_factura || "");
    setPrefEsIsp(Boolean(f.es_inversio_subjecte_passiu));
    setPrefRetIrpfPct(String(pctIrpf));
    setPrefRetGarantiaPct(String(pctGar));
    setPrefLinies(
      f.linies && f.linies.length > 0
        ? f.linies.map((l) => ({ ...l }))
        : [
            {
              concepte: "Serveis tècnics executats",
              compte_pgc: "700000",
              quantitat: 1,
              preu_venda_unitari: Number(f.base_imposable || 0),
              descompte_aplicat_pct: 0,
              tipus_iva: 21,
            },
          ]
    );
  };

  const prefacturesEsborrany = useMemo(
    () => factures.filter((f) => f.estat_document === "ESBORRANY_PREFACTURA"),
    [factures]
  );

  const facturesEmeses = useMemo(
    () => factures.filter((f) => f.estat_document !== "ESBORRANY_PREFACTURA"),
    [factures]
  );

  const editorTotals = useMemo(() => {
    const basesPerIva: Record<string, number> = {};
    let suplerts = 0;
    for (const lin of prefLinies) {
      const dtoFactor = 1 - Number(lin.descompte_aplicat_pct || 0) / 100;
      const sub = round2(Number(lin.quantitat || 0) * Number(lin.preu_venda_unitari || 0) * dtoFactor);
      if ((lin.compte_pgc || "700000").startsWith("554")) {
        suplerts += sub;
      } else {
        const ivaPct = prefEsIsp ? 0 : Number(lin.tipus_iva ?? 21);
        const key = String(ivaPct);
        basesPerIva[key] = (basesPerIva[key] || 0) + sub;
      }
    }
    const baseTotal = round2(Object.values(basesPerIva).reduce((acc, v) => acc + v, 0));
    let ivaTotal = 0;
    if (!prefEsIsp) {
      for (const [pctStr, base] of Object.entries(basesPerIva)) {
        ivaTotal += round2(base * (Number(pctStr) / 100));
      }
    }
    ivaTotal = round2(ivaTotal);
    const retIrpf = round2(baseTotal * (Number(prefRetIrpfPct || 0) / 100));
    const retGar = round2(baseTotal * (Number(prefRetGarantiaPct || 0) / 100));
    const liquid = round2(baseTotal + ivaTotal + suplerts - retIrpf - retGar);
    return { baseTotal, ivaTotal, suplerts: round2(suplerts), retIrpf, retGar, liquid };
  }, [prefLinies, prefEsIsp, prefRetIrpfPct, prefRetGarantiaPct]);

  const articlesPrefFiltrats = useMemo(() => {
    const q = cercaMaterialPref.trim().toLowerCase();
    const list = q
      ? articlesMagatzem.filter(
          (a) =>
            (a.nom || "").toLowerCase().includes(q) ||
            (a.referencia_inventari || "").toLowerCase().includes(q)
        )
      : articlesMagatzem;
    return list.slice(0, 12);
  }, [articlesMagatzem, cercaMaterialPref]);

  const carregarDades = async () => {
    setLoading(true);
    setError(null);
    try {
      const [
        dashRes,
        factRes,
        wipRes,
        retRes,
        art80Res,
        opRes,
        mrrRes,
        tiqRes,
        margesRes,
        despRes,
        fixesRes,
        cliRes,
        artsRes,
      ] = await Promise.all([
        apiFetch<DashboardEconomic>(
          `/gestio/comptabilitat/dashboard-economic?criteri_caixa=${criteriCaixa}&periode=${encodeURIComponent(periode)}`
        ),
        apiFetch<Factura[]>("/gestio/comptabilitat/factures"),
        apiFetch<WIPControl>("/gestio/comptabilitat/wip-control"),
        apiFetch<RetencioGarantia[]>("/gestio/comptabilitat/retencions-garantia"),
        apiFetch<Art80Item[]>("/gestio/comptabilitat/art80-incobrables"),
        apiFetch<OperariCost[]>("/gestio/comptabilitat/operaris-cost-efectiu"),
        apiFetch<ContracteMRR[]>("/gestio/comptabilitat/contractes-mrr-auditoria"),
        apiFetch<TiquetDespesa[]>("/gestio/comptabilitat/tiquets"),
        apiFetch<OTCostMarge[]>("/gestio/comptabilitat/ordres-treball-marges").catch(() => []),
        apiFetch<DespesaComptableItem[]>("/gestio/comptabilitat/despeses-analitiques").catch(
          () => []
        ),
        apiFetch<DespesaFixaItem[]>("/gestio/comptabilitat/despeses-fixes").catch(() => []),
        apiFetch<ClientOption[]>("/gestio/clients?limit=200").catch(() => []),
        apiFetch<ArticleMagatzemOption[]>("/gestio/magatzem/articles?limit=200").catch(() => []),
      ]);

      setDashboard(dashRes);
      setFactures(factRes || []);
      setWip(wipRes);
      setRetencions(retRes || []);
      setArt80(art80Res || []);
      setOperarisCost(opRes || []);
      setContractesMrr(mrrRes || []);
      setTiquets(tiqRes || []);
      setMargesOt(margesRes || []);
      setDespesesAnalitiques(despRes || []);
      setDespesesFixes(Array.isArray(fixesRes) ? fixesRes : []);
      setClientsList(Array.isArray(cliRes) ? cliRes : []);
      setArticlesMagatzem(Array.isArray(artsRes) ? artsRes : []);
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Error carregant la suite econòmica";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const tabParam = searchParams.get("tab") as TabKey | null;
    if (
      tabParam &&
      [
        "DASHBOARD",
        "DESPESES_FIXES",
        "WIP_CONTROL",
        "PREFACTURACIO",
        "VERIFACTU",
        "MARGES_OT",
        "OPERARIS_MRR",
        "TIQUETS",
        "NORMA43",
      ].includes(tabParam)
    ) {
      setTabActiva(tabParam);
    }
  }, [searchParams]);

  useEffect(() => {
    const prefId = searchParams.get("prefactura_id");
    if (prefId && prefId !== handledParamPrefId && factures.length > 0) {
      const match = factures.find(
        (f) => f.id === prefId && f.estat_document === "ESBORRANY_PREFACTURA"
      );
      if (match) {
        setTabActiva("PREFACTURACIO");
        obrirEditorPrefactura(match);
        setHandledParamPrefId(prefId);
      }
    }
  }, [searchParams, factures, handledParamPrefId]);

  useEffect(() => {
    if (rolActiu !== "ENGINYER") {
      carregarDades();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rolActiu, criteriCaixa, periode]);

  if (rolActiu === "ENGINYER") {
    return (
      <div className="flex min-h-[70vh] items-center justify-center p-6">
        <div className="max-w-md rounded-2xl border border-rose-200 bg-rose-50/70 p-8 text-center">
          <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-rose-100 text-rose-700">
            <Lock className="h-7 w-7" />
          </div>
          <h1 className="text-xl font-bold text-slate-900">
            Veto d&apos;Enginyer (HTTP 403 Forbidden)
          </h1>
          <p className="mt-2 text-sm text-slate-600">
            Per mandat constitucional (Zero-Trust C-05), el rol{" "}
            <strong>ENGINYER</strong> té bloquejat l&apos;accés a comptabilitat,
            EBITDA, IBANs i salaris reals.
          </p>
        </div>
      </div>
    );
  }

  const handleEmetreFactura = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const avui = new Date().toISOString().slice(0, 10);
      await apiFetch("/gestio/comptabilitat/factures/emetre", {
        method: "POST",
        body: JSON.stringify({
          client_id: clientIdInput,
          serie: "F",
          data_emissio: avui,
          data_venciment: avui,
          es_inversio_subjecte_passiu: esIsp,
          retencio_garantia_pct: Number(retGarantiaPct || 0),
          linies: [
            {
              concepte: concepteInput,
              quantitat: 1,
              preu_venda_unitari: Number(preuInput || 0),
              tipus_iva_pct: esIsp ? 0 : 21,
            },
          ],
        }),
      });
      setModalFactura(false);
      await carregarDades();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error en emetre factura");
    }
  };

  const handleConvertirWipPrefactura = async (ordreTreballId: string) => {
    setConvertintWipId(ordreTreballId);
    setError(null);
    setSuccessMsg(null);
    try {
      const created = await apiFetch<{ id: string }>(
        `/gestio/comptabilitat/wip-control/${ordreTreballId}/prefacturar`,
        { method: "POST" }
      );
      const factList = await apiFetch<Factura[]>("/gestio/comptabilitat/factures");
      setFactures(factList || []);
      const wipRes = await apiFetch<WIPControl>("/gestio/comptabilitat/wip-control");
      setWip(wipRes);
      setTabActiva("PREFACTURACIO");
      const novaPref = (factList || []).find((f) => f.id === created.id);
      if (novaPref) {
        obrirEditorPrefactura(novaPref);
      }
      setSuccessMsg("Pre-factura generada en esborrany. Pots editar-ne línies i preus abans d'emetre-la.");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error en convertir OT a Pre-factura");
    } finally {
      setConvertintWipId(null);
    }
  };

  const afegirMaterialAPrefactura = (art: ArticleMagatzemOption) => {
    const qt = Math.max(0.01, Number(materialPrefQt || 1));
    const novaLinia: FacturaLinia = {
      article_id: art.id,
      concepte: `[${art.referencia_inventari}] ${art.nom}`,
      compte_pgc: "700000",
      quantitat: qt,
      preu_venda_unitari: Number(art.preu_venda || 0),
      descompte_aplicat_pct: 0,
      tipus_iva: prefEsIsp ? 0 : 21,
    };
    setPrefLinies((prev) => {
      if (
        prev.length === 1 &&
        !prev[0].concepte.trim() &&
        Number(prev[0].preu_venda_unitari || 0) === 0
      ) {
        return [novaLinia];
      }
      return [...prev, novaLinia];
    });
    setCercaMaterialPref("");
    setMaterialPrefQt("1");
    setMaterialPrefDropdownOpen(false);
  };

  const handleDesarPrefactura = async (emetreDespres: boolean) => {
    if (!editingPrefactura && !creatingPrefactura) return;
    if (creatingPrefactura && !prefClientId) {
      setError("Selecciona un client per crear la pre-factura.");
      return;
    }
    const liniesNetes = prefLinies.filter((l) => l.concepte.trim().length > 0);
    if (liniesNetes.length === 0) {
      setError("La pre-factura ha de tenir com a mínim una línia amb concepte.");
      return;
    }
    setSavingPrefactura(true);
    setError(null);
    setSuccessMsg(null);
    try {
      const avui = new Date().toISOString().slice(0, 10);
      const liniesPayload = liniesNetes.map((l) => {
        const compte = l.compte_pgc || "700000";
        const esSuplert = compte.startsWith("554");
        return {
          obra_id: l.obra_id || null,
          centre_de_cost_id: l.centre_de_cost_id || "CC-GENERAL",
          article_id: l.article_id || null,
          concepte: l.concepte.trim(),
          compte_pgc: compte,
          quantitat: Math.max(0.001, Number(l.quantitat || 0)),
          quantitat_merma: Number(l.quantitat_merma || 0),
          preu_venda_unitari: Math.max(0, Number(l.preu_venda_unitari || 0)),
          descompte_aplicat_pct: Math.min(100, Math.max(0, Number(l.descompte_aplicat_pct || 0))),
          tipus_iva_pct: prefEsIsp || esSuplert ? 0 : Number(l.tipus_iva ?? 21),
        };
      });

      let targetFacturaId = editingPrefactura?.id || "";
      if (creatingPrefactura) {
        const created = await apiFetch<Factura>("/gestio/comptabilitat/prefactures", {
          method: "POST",
          body: JSON.stringify({
            client_id: prefClientId,
            serie: "PRE",
            tipus_factura: prefTipusFactura,
            data_emissio: prefDataEmissio || avui,
            data_operacio: prefDataOperacio || null,
            data_venciment: prefDataVenciment || prefDataEmissio || avui,
            metode_pagament: prefMetodePagament,
            referencia_client: prefReferenciaClient || null,
            notes_factura: prefNotesFactura || null,
            es_inversio_subjecte_passiu: prefEsIsp,
            retencio_irpf_pct: Number(prefRetIrpfPct || 0),
            retencio_garantia_pct: Number(prefRetGarantiaPct || 0),
            linies: liniesPayload,
          }),
        });
        targetFacturaId = created.id;
      } else if (editingPrefactura) {
        await apiFetch(`/gestio/comptabilitat/prefactures/${editingPrefactura.id}`, {
          method: "PUT",
          body: JSON.stringify({
            tipus_factura: prefTipusFactura,
            data_emissio: prefDataEmissio || null,
            data_operacio: prefDataOperacio || null,
            data_venciment: prefDataVenciment || null,
            metode_pagament: prefMetodePagament,
            referencia_client: prefReferenciaClient || null,
            notes_factura: prefNotesFactura || null,
            es_inversio_subjecte_passiu: prefEsIsp,
            retencio_irpf_pct: Number(prefRetIrpfPct || 0),
            retencio_garantia_pct: Number(prefRetGarantiaPct || 0),
            linies: liniesPayload,
          }),
        });
      }

      if (emetreDespres && targetFacturaId) {
        const emesa = await apiFetch<Factura>(
          `/gestio/comptabilitat/prefactures/${targetFacturaId}/emetre`,
          {
            method: "POST",
            body: JSON.stringify({
              serie: "F",
              data_emissio: prefDataEmissio || null,
              data_venciment: prefDataVenciment || null,
              confirmacio_humana_hitl: true,
            }),
          }
        );
        tancarModalPrefactura();
        await carregarDades();
        setTabActiva("VERIFACTU");
        setSuccessMsg(
          `Factura definitiva ${emesa.serie}-${emesa.numero_factura} emesa i encadenada a Veri*factu.`
        );
      } else {
        tancarModalPrefactura();
        await carregarDades();
        setSuccessMsg(
          creatingPrefactura
            ? "Nova pre-factura en esborrany creada correctament."
            : "Canvis de la pre-factura desats correctament."
        );
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error en desar la pre-factura");
    } finally {
      setSavingPrefactura(false);
    }
  };

  const handleEmetrePrefacturaDirecte = async (f: Factura) => {
    setEmittingPrefId(f.id);
    setError(null);
    setSuccessMsg(null);
    try {
      const emesa = await apiFetch<Factura>(`/gestio/comptabilitat/prefactures/${f.id}/emetre`, {
        method: "POST",
        body: JSON.stringify({ serie: "F", confirmacio_humana_hitl: true }),
      });
      await carregarDades();
      setTabActiva("VERIFACTU");
      setSuccessMsg(
        `Factura definitiva ${emesa.serie}-${emesa.numero_factura} emesa a Veri*factu.`
      );
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error en emetre la factura definitiva");
    } finally {
      setEmittingPrefId(null);
    }
  };

  const handleDescartarPrefactura = async (f: Factura) => {
    setError(null);
    setSuccessMsg(null);
    try {
      await apiFetch(`/gestio/comptabilitat/prefactures/${f.id}`, {
        method: "DELETE",
      });
      await carregarDades();
      setSuccessMsg("Pre-factura descartada. L'ordre de treball torna a estar disponible a WIP.");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error en descartar la pre-factura");
    }
  };

  const handleEmetreRectificativa = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!facturaRectificar) return;
    try {
      await apiFetch(`/gestio/comptabilitat/factures/${facturaRectificar.id}/rectificar`, {
        method: "POST",
        body: JSON.stringify({
          motiu: motiuRectificar.trim(),
          tipus_factura: tipusRectificar,
          tipus_rectificacio: modalitatRectificar,
        }),
      });
      setFacturaRectificar(null);
      setMotiuRectificar("");
      setSuccessMsg("Factura rectificativa Sèrie R emesa i encadenada a Veri*factu.");
      await carregarDades();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error en emetre rectificativa Sèrie R");
    }
  };

  const handleAnularFactura = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!facturaAnular) return;
    try {
      await apiFetch(`/gestio/comptabilitat/factures/${facturaAnular.id}/anular`, {
        method: "POST",
        body: JSON.stringify({
          motiu: motiuAnular.trim(),
          confirmacio_humana_hitl: true,
        }),
      });
      setFacturaAnular(null);
      setMotiuAnular("");
      setSuccessMsg("Registre d'Anul·lació (RegistroAnulacion) emès i encadenat a Veri*factu.");
      await carregarDades();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error en anul·lar factura a Veri*factu");
    }
  };

  const handleReenviarAeat = async (facturaId: string) => {
    setReenviantAeatId(facturaId);
    setError(null);
    setSuccessMsg(null);
    try {
      const resp = await apiFetch<any>(
        `/gestio/comptabilitat/factures/${facturaId}/reenviar-aeat`,
        { method: "POST" }
      );
      await carregarDades();
      setSuccessMsg(
        `Enviament AEAT processat (${resp.num_serie_verifactu || facturaId}): estat ${resp.estat_aeat || resp.estat_enviament}${
          resp.csv_aeat ? ` · CSV: ${resp.csv_aeat}` : ""
        }`
      );
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error en reenviar factura a l'AEAT");
    } finally {
      setReenviantAeatId(null);
    }
  };

  const obrirDeclaracioResponsableSif = async () => {
    setModalDeclaracioSif(true);
    try {
      const data = await apiFetch<any>("/gestio/comptabilitat/verifactu/declaracio-responsable");
      setDeclaracioSif(data);
    } catch {
      setDeclaracioSif(null);
    }
  };

  const handleAuditarTiquet = async (id: string, accio: "APROVAT" | "REBUTJAT") => {
    try {
      const split = desgloseMap[id];
      const payload: Record<string, unknown> = {
        accio,
        custodia_paper_confirmada: true,
        desblocatge_targeta_vehicle: true,
      };
      if (split) {
        if (split.carb) payload.desglose_carburant_eur = Number(split.carb);
        if (split.adbl) payload.desglose_adblue_eur = Number(split.adbl);
      }
      await apiFetch(`/gestio/comptabilitat/tiquets/${id}/auditar`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
      await carregarDades();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error auditant tiquet");
    }
  };

  const handleReclamarGarantia = async (id: string) => {
    try {
      await apiFetch(`/gestio/comptabilitat/retencions-garantia/${id}/reclamar`, {
        method: "POST",
      });
      await carregarDades();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error reclamant garantia");
    }
  };

  const handleConciliarNorma43 = async (confirmarHitl: boolean) => {
    if (!textC43.trim()) return;
    try {
      const res = await apiFetch<Norma43Moviment[]>(
        "/gestio/comptabilitat/norma43/conciliar",
        {
          method: "POST",
          body: JSON.stringify({
            contingut_c43: textC43,
            confirmar_conciliacio_hitl: confirmarHitl,
          }),
        }
      );
      setMovimentsC43(res || []);
      if (confirmarHitl) await carregarDades();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error conciliant CSB 43");
    }
  };

  const obrirModalCobrament = (f: Factura) => {
    const avui = new Date().toISOString().slice(0, 10);
    setFacturaCobrament(f);
    const estatActual = (f.estat_cobrament || "PENDENT").toUpperCase();
    if (estatActual === "COBRADA" || estatActual === "PARCIAL" || estatActual === "IMPAGADA") {
      setCobramentEstat(estatActual as "COBRADA" | "PARCIAL" | "IMPAGADA");
    } else {
      setCobramentEstat("COBRADA");
    }
    const importInicial =
      f.import_cobrat && Number(f.import_cobrat) > 0
        ? Number(f.import_cobrat).toFixed(2)
        : Number(f.liquid_exigible || 0).toFixed(2);
    setCobramentImport(importInicial);
    setCobramentData(f.data_cobrament_real || avui);
    setCobramentNotes("");
  };

  const handleRegistrarCobrament = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!facturaCobrament) return;
    setSavingCobrament(true);
    setError(null);
    setSuccessMsg(null);
    try {
      const payload: Record<string, unknown> = {
        estat_cobrament: cobramentEstat,
        data_cobrament_real: cobramentData || null,
        notes: cobramentNotes.trim() || null,
      };
      if (cobramentEstat === "PARCIAL") {
        payload.import_cobrat = Number(cobramentImport || 0);
      } else if (cobramentEstat === "COBRADA") {
        payload.import_cobrat = Number(facturaCobrament.liquid_exigible || 0);
      } else {
        payload.import_cobrat = Number(cobramentImport || 0);
      }
      await apiFetch(`/gestio/comptabilitat/factures/${facturaCobrament.id}/cobrament`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
      setFacturaCobrament(null);
      setSuccessMsg("Cobrament registrat. El Cash-Flow, el DSO i el criteri de caixa s'han actualitzat.");
      await carregarDades();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error registrant el cobrament");
    } finally {
      setSavingCobrament(false);
    }
  };

  const obrirNovaDespesaFixa = () => {
    setEditingDespesaFixa(null);
    setDfConcepte("");
    setDfCategoria("LLOGUER");
    setDfImportBase("");
    setDfQuotaIva("0");
    setDfPeriodicitat("MENSUAL");
    setDfDiaCarrec("5");
    setModalDespesaFixa(true);
  };

  const obrirEditarDespesaFixa = (df: DespesaFixaItem) => {
    setEditingDespesaFixa(df);
    setDfConcepte(df.concepte);
    setDfCategoria(df.categoria);
    setDfImportBase(String(Number(df.import_base).toFixed(2)));
    setDfQuotaIva(String(Number(df.quota_iva).toFixed(2)));
    setDfPeriodicitat(df.periodicitat);
    setDfDiaCarrec(String(df.dia_carrec || 5));
    setModalDespesaFixa(true);
  };

  const handleDesarDespesaFixa = async (e: React.FormEvent) => {
    e.preventDefault();
    setSavingDespesaFixa(true);
    setError(null);
    setSuccessMsg(null);
    try {
      const payload = {
        concepte: dfConcepte.trim(),
        categoria: dfCategoria,
        import_base: Number(dfImportBase || 0),
        quota_iva: Number(dfQuotaIva || 0),
        periodicitat: dfPeriodicitat,
        dia_carrec: Number(dfDiaCarrec || 5),
      };
      if (editingDespesaFixa) {
        await apiFetch(`/gestio/comptabilitat/despeses-fixes/${editingDespesaFixa.id}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
        setSuccessMsg("Despesa fixa actualitzada.");
      } else {
        await apiFetch("/gestio/comptabilitat/despeses-fixes", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        setSuccessMsg("Despesa fixa enregistrada. El Break-Even i el Burn Rate s'han recalculat.");
      }
      setModalDespesaFixa(false);
      await carregarDades();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error desant la despesa fixa");
    } finally {
      setSavingDespesaFixa(false);
    }
  };

  const handleToggleDespesaFixa = async (df: DespesaFixaItem) => {
    setError(null);
    setSuccessMsg(null);
    try {
      if (df.actiu) {
        await apiFetch(`/gestio/comptabilitat/despeses-fixes/${df.id}`, { method: "DELETE" });
        setSuccessMsg(`Despesa fixa «${df.concepte}» desactivada.`);
      } else {
        await apiFetch(`/gestio/comptabilitat/despeses-fixes/${df.id}`, {
          method: "PUT",
          body: JSON.stringify({ actiu: true }),
        });
        setSuccessMsg(`Despesa fixa «${df.concepte}» reactivada.`);
      }
      await carregarDades();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error actualitzant l'estat de la despesa fixa");
    }
  };

  const despesesFixesActivesCount = despesesFixes.filter((d) => d.actiu).length;
  const totalMensualFixes = round2(
    despesesFixes
      .filter((d) => d.actiu)
      .reduce((acc, d) => acc + Number(d.import_mensual_normalitzat || 0), 0)
  );

  const tabs: Array<{ key: TabKey; label: string; icon: React.ReactNode; badge?: number }> = [
    { key: "DASHBOARD", label: "Suite Econòmica & KPIs", icon: <TrendingUp className="h-4 w-4" /> },
    {
      key: "DESPESES_FIXES",
      label: "Despeses Fixes",
      icon: <Building2 className="h-4 w-4" />,
      badge: despesesFixesActivesCount,
    },
    {
      key: "WIP_CONTROL",
      label: "Pendents de Prefacturar",
      icon: <Activity className="h-4 w-4" />,
      badge: wip?.nombre_ots_en_wip || 0,
    },
    {
      key: "PREFACTURACIO",
      label: "Prefactures Editables",
      icon: <Edit3 className="h-4 w-4" />,
      badge: prefacturesEsborrany.length,
    },
    { key: "VERIFACTU", label: "Veri*factu, Art.80 & 4308", icon: <QrCode className="h-4 w-4" /> },
    { key: "MARGES_OT", label: "Costos & Marges OT", icon: <Scale className="h-4 w-4" /> },
    { key: "OPERARIS_MRR", label: "Operaris & MRR", icon: <Users className="h-4 w-4" /> },
    { key: "TIQUETS", label: "Tiquets OCR Camp", icon: <Receipt className="h-4 w-4" /> },
    { key: "NORMA43", label: "Banc Norma 43", icon: <Banknote className="h-4 w-4" /> },
  ];

  return (
    <div className="space-y-6 p-6">
      {/* Capçalera Executiva amb Selector Global (RF-01, RF-02) */}
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            Suite de Control Financer i Comptabilitat (Spec 007 v5.0)
          </h1>
          <p className="text-sm text-slate-500">
            P&amp;L en temps real, Veri*factu RD 1007/2023, Tresoreria 30/60/90d i Auditoria Zero-Mock
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <select
            value={periode}
            onChange={(e) => setPeriode(e.target.value)}
            className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-700"
          >
            <option value="MES_ACTUAL">Mes Actual</option>
            <option value="TRIMESTRE_ACTUAL">Trimestre Actual</option>
            <option value="YTD">Acumulat Any (YTD)</option>
            <option value="EXERCICI_FISCAL">Exercici Fiscal Complet</option>
          </select>

          <button
            type="button"
            onClick={() => setCriteriCaixa((prev) => !prev)}
            className={`rounded-lg border px-3 py-2 text-xs font-medium transition ${
              criteriCaixa
                ? "border-primary bg-primary/10 text-primary"
                : "border-slate-200 bg-white text-slate-700"
            }`}
          >
            Criteri: {criteriCaixa ? "Caixa Analític" : "Meritació (Devengo)"}
          </button>

          <button
            type="button"
            onClick={carregarDades}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-700 hover:bg-slate-50"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
            Actualitzar
          </button>

          <button
            type="button"
            onClick={() => setModalFactura(true)}
            className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3.5 py-2 text-xs font-semibold text-white hover:opacity-90"
          >
            <Plus className="h-4 w-4" />
            Emetre Factura Veri*factu
          </button>
        </div>
      </div>

      {error && (
        <div className="flex items-center justify-between rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">
          <span className="flex items-center gap-2">
            <AlertTriangle className="h-4 w-4" />
            {error}
          </span>
          <button onClick={() => setError(null)}>
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {successMsg && (
        <div className="flex items-center justify-between rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
          <span className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4" />
            {successMsg}
          </span>
          <button onClick={() => setSuccessMsg(null)}>
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* Navegació per Pestanyes */}
      <div className="flex flex-wrap gap-2 border-b border-slate-200 pb-2">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setTabActiva(t.key)}
            className={`inline-flex items-center gap-2 rounded-lg px-3.5 py-2 text-xs font-semibold transition ${
              tabActiva === t.key
                ? "bg-primary text-white"
                : "bg-slate-100 text-slate-600 hover:bg-slate-200"
            }`}
          >
            {t.icon}
            <span>{t.label}</span>
            {typeof t.badge === "number" && t.badge > 0 && (
              <span
                className={`rounded-full px-1.5 py-0.5 text-[10px] font-bold leading-none ${
                  tabActiva === t.key
                    ? "bg-white/25 text-white"
                    : "bg-primary/15 text-primary"
                }`}
              >
                {t.badge}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* TAB 1: DASHBOARD ECONÒMIC & 5 GRÀFIQUES */}
      {tabActiva === "DASHBOARD" && dashboard && (
        <div className="space-y-6">
          {/* KPIs Principals */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <div className="rounded-xl border border-slate-200 bg-white p-5">
              <p className="text-xs font-medium text-slate-500">Facturació Neta &amp; Marge Brut</p>
              <p className="mt-1 text-2xl font-bold tabular-nums text-slate-900">
                {Number(dashboard.facturacio_neta).toFixed(2)} €
              </p>
              <p className="mt-1 text-xs text-slate-600">
                Marge Brut:{" "}
                <span className="font-semibold text-emerald-700">
                  {Number(dashboard.marge_brut_eur).toFixed(2)} € ({Number(dashboard.marge_brut_pct).toFixed(1)}%)
                </span>
              </p>
            </div>

            <div className="rounded-xl border border-slate-200 bg-white p-5">
              <p className="text-xs font-medium text-slate-500">EBITDA Operatiu &amp; Break-Even</p>
              <p
                className={`mt-1 text-2xl font-bold tabular-nums ${
                  Number(dashboard.ebitda_operatiu_eur) >= 0 ? "text-emerald-700" : "text-rose-700"
                }`}
              >
                {Number(dashboard.ebitda_operatiu_eur).toFixed(2)} €
              </p>
              <p className="mt-1 text-xs text-slate-600">
                Break-Even: {Number(dashboard.break_even_facturacio_necessaria).toFixed(2)} €{" "}
                {dashboard.break_even_assolit ? "✅ Assolit" : "⏳ Pendent"}
              </p>
            </div>

            <div className="rounded-xl border border-slate-200 bg-white p-5">
              <p className="text-xs font-medium text-slate-500">Burn Rate &amp; Guardacaixa IVA 303</p>
              <p className="mt-1 text-2xl font-bold tabular-nums text-slate-900">
                {Number(dashboard.burn_rate_mes_seguent).toFixed(2)} €
              </p>
              <p className="mt-1 text-xs text-amber-700 font-medium">
                Reserva AEAT IVA: {Number(dashboard.guardacaixa_fiscal_iva_303).toFixed(2)} €
              </p>
            </div>

            <div className="rounded-xl border border-slate-200 bg-white p-5">
              <p className="text-xs font-medium text-slate-500">MRR Actiu &amp; DSO Cobrament</p>
              <p className="mt-1 text-2xl font-bold tabular-nums text-primary">
                {Number(dashboard.mrr_mensual_actiu).toFixed(2)} €/mes
              </p>
              <p className="mt-1 text-xs text-slate-600">
                Cobertura Fixes: {Number(dashboard.cobertura_estructura_mrr_pct).toFixed(1)}% · DSO:{" "}
                {Number(dashboard.dso_dies_mitjana_cobrament).toFixed(0)}d
              </p>
            </div>
          </div>

          {/* KPIs Operatius d'Estructura, Flota i Cash-Flow Real */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div className="rounded-xl border border-slate-200 bg-white px-5 py-4 flex items-center justify-between gap-3">
              <div>
                <p className="text-xs font-medium text-slate-500">Despeses Fixes d&apos;Estructura</p>
                <p className="mt-1 text-xl font-bold tabular-nums text-slate-900">
                  {Number(dashboard.despeses_fixes_estructura).toFixed(2)} €
                </p>
                <p className="mt-0.5 text-xs text-slate-500">
                  {despesesFixesActivesCount} partides actives ({totalMensualFixes.toFixed(2)} €/mes base)
                </p>
              </div>
              <button
                type="button"
                onClick={() => setTabActiva("DESPESES_FIXES")}
                className="shrink-0 rounded-lg border border-primary/30 bg-primary/10 px-3 py-1.5 text-xs font-semibold text-primary hover:bg-primary/20 transition"
              >
                Gestionar
              </button>
            </div>

            <div className="rounded-xl border border-slate-200 bg-white px-5 py-4">
              <p className="text-xs font-medium text-slate-500">Cost Real de Flota per Km</p>
              <p className="mt-1 text-xl font-bold tabular-nums text-slate-900">
                {Number(dashboard.cost_flota_eur_km_mitja).toFixed(2)} €/km
              </p>
              <p className="mt-0.5 text-xs text-slate-500">
                Quotes mensuals + manteniments de taller i km imputats
              </p>
            </div>

            <div className="rounded-xl border border-slate-200 bg-white px-5 py-4">
              <p className="text-xs font-medium text-slate-500">Cash-Flow Operatiu Real</p>
              <p
                className={`mt-1 text-xl font-bold tabular-nums ${
                  Number(dashboard.cash_flow_operatiu_real) >= 0 ? "text-emerald-700" : "text-rose-700"
                }`}
              >
                {Number(dashboard.cash_flow_operatiu_real).toFixed(2)} €
              </p>
              <p className="mt-0.5 text-xs text-slate-500">
                Cobraments reals menys pagaments a proveïdors i tiquets
              </p>
            </div>
          </div>

          {/* Alertes Estratègiques (Pareto + Erosió Marge + Capital Immobilitzat) */}
          {(dashboard.alerta_concentracio_pareto_25pct ||
            dashboard.alertes_erosio_marge.length > 0 ||
            Number(dashboard.capital_immobilitzat_90d_eur) > 0) && (
            <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
              {dashboard.alerta_concentracio_pareto_25pct && (
                <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-xs text-amber-900">
                  <strong>Risc Concentració Pareto (&gt;25%):</strong> Un sol client supera el 25% de la facturació.
                </div>
              )}
              {dashboard.alertes_erosio_marge.length > 0 && (
                <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-xs text-rose-900">
                  <strong>Erosió de Marge ({dashboard.alertes_erosio_marge.length} articles):</strong> Puja de cost de proveïdor detectada.
                </div>
              )}
              <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-xs text-slate-700">
                <strong>Capital Immobilitzat (&gt;90d):</strong>{" "}
                {Number(dashboard.capital_immobilitzat_90d_eur).toFixed(2)} € en estoc sense rotació.
              </div>
            </div>
          )}

          {/* Les 5 Gràfiques Interactives */}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <Evolucio12MChart data={dashboard.evolucio_12m || []} />
            <WaterfallChart waterfall={dashboard.waterfall_mensual || {}} />
            <TresoreriaProjeccioChart
              cashFlowReal={Number(dashboard.cash_flow_operatiu_real || 0)}
              p30={Number(dashboard.projeccio_tresoreria_30d || 0)}
              p60={Number(dashboard.projeccio_tresoreria_60d || 0)}
              p90={Number(dashboard.projeccio_tresoreria_90d || 0)}
              guardacaixaIva={Number(dashboard.guardacaixa_fiscal_iva_303 || 0)}
            />
            <AgingBarChart
              aging={dashboard.aging_impagats || {}}
              retencionsExcloses={Number(dashboard.total_retencions_garantia_4308_excloses_aging || 0)}
            />
          </div>

          <MargesVerticalChart verticals={dashboard.marges_per_vertical || []} />
        </div>
      )}

      {/* TAB: DESPESES FIXES D'ESTRUCTURA (CRUD REAL) */}
      {tabActiva === "DESPESES_FIXES" && (
        <div className="space-y-5">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between rounded-xl border border-slate-200 bg-white p-5">
            <div>
              <h2 className="text-base font-bold text-slate-900">
                Despeses Fixes d&apos;Estructura
              </h2>
              <p className="mt-0.5 text-xs text-slate-500">
                Lloguers, subministraments, assegurances, gestoria i software que alimenten el Break-Even, el Burn Rate i el Guardacaixa IVA 303.
              </p>
            </div>
            <div className="flex items-center gap-4">
              <div className="text-right">
                <p className="text-xs text-slate-500">Total mensual normalitzat</p>
                <p className="text-lg font-bold tabular-nums text-primary">
                  {totalMensualFixes.toFixed(2)} €/mes
                </p>
              </div>
              <button
                type="button"
                onClick={obrirNovaDespesaFixa}
                className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-4 py-2 text-xs font-semibold text-white hover:opacity-90 transition"
              >
                <Plus className="h-4 w-4" /> Afegir Despesa Fixa
              </button>
            </div>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white overflow-hidden">
            {despesesFixes.length === 0 ? (
              <div className="p-10 text-center space-y-3">
                <p className="text-sm font-medium text-slate-700">
                  Encara no hi ha cap despesa fixa d&apos;estructura registrada.
                </p>
                <p className="text-xs text-slate-500 max-w-md mx-auto">
                  Afegeix les partides recurrents de l&apos;empresa (lloguer de nau, llum, assegurances, gestoria) perquè el Dashboard calculi el llindar de rendibilitat (Break-Even) i el Burn Rate reals.
                </p>
                <button
                  type="button"
                  onClick={obrirNovaDespesaFixa}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-4 py-2 text-xs font-semibold text-white hover:opacity-90"
                >
                  <Plus className="h-4 w-4" /> Enregistrar primera despesa fixa
                </button>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50 text-slate-600">
                    <tr>
                      <th className="px-4 py-3">Concepte</th>
                      <th className="px-4 py-3">Categoria</th>
                      <th className="px-4 py-3">Periodicitat</th>
                      <th className="px-4 py-3 text-right">Base + IVA</th>
                      <th className="px-4 py-3 text-right">Cost Mensual</th>
                      <th className="px-4 py-3 text-center">Dia càrrec</th>
                      <th className="px-4 py-3">Estat</th>
                      <th className="px-4 py-3 text-right">Accions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {despesesFixes.map((df) => (
                      <tr key={df.id} className={`hover:bg-slate-50 ${!df.actiu ? "opacity-60 bg-slate-50/60" : ""}`}>
                        <td className="px-4 py-3 font-medium text-slate-900">{df.concepte}</td>
                        <td className="px-4 py-3">
                          <span className="rounded-md bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-700">
                            {df.categoria}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-slate-600">{df.periodicitat}</td>
                        <td className="px-4 py-3 text-right tabular-nums text-slate-700">
                          {Number(df.import_base).toFixed(2)} €
                          {Number(df.quota_iva) > 0 && (
                            <span className="block text-[10px] text-slate-500">
                              + {Number(df.quota_iva).toFixed(2)} € IVA
                            </span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-right tabular-nums font-semibold text-slate-900">
                          {Number(df.import_mensual_normalitzat).toFixed(2)} €/mes
                        </td>
                        <td className="px-4 py-3 text-center tabular-nums text-slate-600">
                          Dia {df.dia_carrec}
                        </td>
                        <td className="px-4 py-3">
                          <span
                            className={`inline-block rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                              df.actiu
                                ? "bg-emerald-100 text-emerald-800"
                                : "bg-slate-200 text-slate-600"
                            }`}
                          >
                            {df.actiu ? "Activa" : "Desactivada"}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-right whitespace-nowrap space-x-2">
                          <button
                            type="button"
                            onClick={() => obrirEditarDespesaFixa(df)}
                            className="rounded-md border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-medium text-slate-700 hover:bg-slate-50"
                          >
                            Editar
                          </button>
                          <button
                            type="button"
                            onClick={() => handleToggleDespesaFixa(df)}
                            className={`rounded-md border px-2.5 py-1 text-[11px] font-medium ${
                              df.actiu
                                ? "border-rose-200 bg-rose-50 text-rose-700 hover:bg-rose-100"
                                : "border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100"
                            }`}
                          >
                            {df.actiu ? "Desactivar" : "Reactivar"}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 2: VERIFACTU, ART. 80 LIVA I RETENCIONS 5% */}
      {tabActiva === "VERIFACTU" && (
        <div className="space-y-6">
          <div className="rounded-xl border border-slate-200 bg-white overflow-hidden">
            <div className="border-b border-slate-100 px-5 py-3 flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-sm font-semibold text-slate-900">
                Factures Emeses (Encadenament SHA-256 Veri*factu · Ordre HAC/1177/2024)
              </h2>
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={obrirDeclaracioResponsableSif}
                  className="inline-flex items-center gap-1 rounded-lg border border-primary/30 bg-primary/10 px-2.5 py-1 text-xs font-semibold text-primary hover:bg-primary/20 cursor-pointer"
                >
                  <ShieldCheck className="h-3.5 w-3.5" /> Declaració Responsable SIF (Art. 15)
                </button>
                <span className="inline-flex items-center gap-1 text-xs text-emerald-700 font-medium">
                  <ShieldCheck className="h-4 w-4" /> SIF Inalterable
                </span>
              </div>
            </div>
            {facturesEmeses.length === 0 ? (
              <div className="p-8 text-center text-sm text-slate-500">
                Estat Dia 0 real: Encara no s&apos;ha emès cap factura definitiva en aquest tenant.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50 text-slate-600">
                    <tr>
                      <th className="px-4 py-3">Núm. Veri*factu</th>
                      <th className="px-4 py-3">Client / OTs</th>
                      <th className="px-4 py-3">Base</th>
                      <th className="px-4 py-3">IVA</th>
                      <th className="px-4 py-3">Total AEAT / Líquid</th>
                      <th className="px-4 py-3">Estat &amp; AEAT</th>
                      <th className="px-4 py-3">Empremta SHA-256</th>
                      <th className="px-4 py-3 text-right">Accions i Descàrregues</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {facturesEmeses.map((f) => {
                      const numCanonic = f.num_serie_verifactu || `${f.serie}-${f.exercici || 2026}-${String(f.numero_factura).padStart(4, "0")}`;
                      const esAnulada = f.estat_anulacio === "ANULADA_VERIFACTU";
                      const estatAeat = f.estat_aeat || f.estat_enviament || "PENDENT";
                      return (
                        <tr key={f.id} className={`hover:bg-slate-50 ${esAnulada ? "bg-rose-50/40" : ""}`}>
                          <td className="px-4 py-3">
                            <span className="font-mono font-bold text-slate-900">{numCanonic}</span>
                            <span className="ml-1.5 rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[10px] font-semibold text-slate-600">
                              {f.tipus_factura || "F1"}
                              {f.tipus_rectificacio ? `·${f.tipus_rectificacio}` : ""}
                            </span>
                            {esAnulada && (
                              <span className="mt-1 block rounded bg-rose-100 px-1.5 py-0.5 text-[10px] font-bold text-rose-800 w-fit">
                                ANUL·LADA VERI*FACTU
                              </span>
                            )}
                          </td>
                          <td className="px-4 py-3">
                            <p className="font-medium text-slate-800">{f.client_nom || "—"}</p>
                            {f.ordres_treball_codis && f.ordres_treball_codis.length > 0 && (
                              <p className="font-mono text-[10px] text-primary">
                                {f.ordres_treball_codis.join(", ")}
                              </p>
                            )}
                          </td>
                          <td className="px-4 py-3 tabular-nums">{Number(f.base_imposable).toFixed(2)} €</td>
                          <td className="px-4 py-3 tabular-nums">{Number(f.quota_iva).toFixed(2)} €</td>
                          <td className="px-4 py-3 tabular-nums">
                            <span className="font-semibold text-slate-900">
                              {Number(f.liquid_exigible).toFixed(2)} €
                            </span>
                            {f.import_total_verifactu !== undefined &&
                              Number(f.import_total_verifactu) !== Number(f.liquid_exigible) && (
                                <span className="block text-[10px] text-slate-500">
                                  AEAT: {Number(f.import_total_verifactu).toFixed(2)} €
                                </span>
                              )}
                          </td>
                          <td className="px-4 py-3 space-y-1">
                            <span
                              className={`inline-block rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                                f.estat_cobrament === "COBRADA"
                                  ? "bg-emerald-100 text-emerald-800"
                                  : f.estat_cobrament === "PARCIAL"
                                  ? "bg-amber-100 text-amber-800"
                                  : f.estat_cobrament === "IMPAGADA"
                                  ? "bg-rose-100 text-rose-800"
                                  : "bg-slate-100 text-slate-700"
                              }`}
                            >
                              {f.estat_cobrament}
                            </span>
                            {Number(f.import_cobrat || 0) > 0 && (
                              <span className="block text-[10px] tabular-nums text-emerald-700 font-medium">
                                Cobrat: {Number(f.import_cobrat).toFixed(2)} €
                                {f.data_cobrament_real ? ` (${f.data_cobrament_real})` : ""}
                              </span>
                            )}
                            <div>
                              <span
                                className={`inline-block rounded-full px-2 py-0.5 text-[10px] font-bold ${
                                  estatAeat === "ACCEPTADA_AEAT"
                                    ? "bg-emerald-100 text-emerald-800"
                                    : estatAeat === "ACCEPTADA_AMB_ERRORS"
                                    ? "bg-amber-100 text-amber-800"
                                    : estatAeat === "REBUTJADA_AEAT" || estatAeat === "ERROR_PERMANENT"
                                    ? "bg-rose-100 text-rose-800"
                                    : "bg-slate-100 text-slate-700"
                                }`}
                                title={f.darrer_error_aeat || estatAeat}
                              >
                                AEAT: {estatAeat}
                              </span>
                              {f.csv_aeat && (
                                <span className="block font-mono text-[10px] text-emerald-700 font-semibold">
                                  CSV: {f.csv_aeat}
                                </span>
                              )}
                              {f.darrer_error_aeat && (
                                <span className="block text-[10px] text-rose-700 max-w-[200px] truncate" title={f.darrer_error_aeat}>
                                  {f.darrer_error_aeat}
                                </span>
                              )}
                            </div>
                          </td>
                          <td className="px-4 py-3 font-mono text-[11px] text-slate-500">
                            {f.hash_sha256.slice(0, 14)}...
                            {f.hash_anulacio_sha256 && (
                              <span className="block text-[10px] text-rose-700">
                                Anul: {f.hash_anulacio_sha256.slice(0, 10)}...
                              </span>
                            )}
                          </td>
                          <td className="px-4 py-3 text-right whitespace-nowrap space-x-1.5">
                            <a
                              href={`${getApiBaseUrl()}/gestio/comptabilitat/factures/${f.id}/pdf`}
                              target="_blank"
                              rel="noreferrer"
                              className="inline-flex items-center gap-1 text-primary hover:underline font-semibold"
                            >
                              <Download className="h-3.5 w-3.5" /> PDF
                            </a>
                            <a
                              href={`${getApiBaseUrl()}/gestio/comptabilitat/factures/${f.id}/xml`}
                              target="_blank"
                              rel="noreferrer"
                              className="inline-flex items-center gap-1 text-slate-600 hover:underline"
                            >
                              <FileText className="h-3.5 w-3.5" /> XML
                            </a>
                            <button
                              type="button"
                              disabled={reenviantAeatId === f.id}
                              onClick={() => handleReenviarAeat(f.id)}
                              className="inline-flex items-center gap-1 rounded-md border border-slate-200 bg-white px-2 py-0.5 text-[10px] font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                              title="Enviar o reintentar enviament SOAP a l'AEAT"
                            >
                              <RefreshCw className={`h-3 w-3 ${reenviantAeatId === f.id ? "animate-spin" : ""}`} />
                              AEAT
                            </button>
                            {!esAnulada && (
                              <button
                                type="button"
                                onClick={() => obrirModalCobrament(f)}
                                className="inline-flex items-center gap-1 rounded-md border border-emerald-300 bg-emerald-50 px-2 py-0.5 text-[11px] font-semibold text-emerald-800 hover:bg-emerald-100"
                                title="Registrar cobrament total, parcial o impagament"
                              >
                                <Banknote className="h-3 w-3" />
                                {f.estat_cobrament === "COBRADA" ? "Cobrament" : "Registrar Cobrament"}
                              </button>
                            )}
                            {!f.serie.toUpperCase().startsWith("R") && !esAnulada && (
                              <button
                                type="button"
                                onClick={() => {
                                  setFacturaRectificar(f);
                                  setMotiuRectificar("");
                                  setTipusRectificar("R1");
                                  setModalitatRectificar("S");
                                }}
                                className="inline-flex items-center gap-1 rounded-md border border-amber-300 bg-amber-50 px-2 py-0.5 text-[11px] font-semibold text-amber-800 hover:bg-amber-100"
                              >
                                Rectificativa R
                              </button>
                            )}
                            {!esAnulada && (
                              <button
                                type="button"
                                onClick={() => {
                                  setFacturaAnular(f);
                                  setMotiuAnular("");
                                }}
                                className="inline-flex items-center gap-1 rounded-md border border-rose-200 bg-rose-50 px-2 py-0.5 text-[11px] font-semibold text-rose-700 hover:bg-rose-100"
                                title="Emetre Registre d'Anul·lació (RegistroAnulacion)"
                              >
                                Anul·lar
                              </button>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Retencions Garantia 5% i Art. 80 */}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <div className="rounded-xl border border-slate-200 bg-white p-5">
              <h3 className="text-sm font-semibold text-slate-900 mb-3">
                Retencions per Garantia d&apos;Obra 5% (Compte 4308)
              </h3>
              {retencions.length === 0 ? (
                <p className="text-xs text-slate-500">Sense retencions de garantia registrades.</p>
              ) : (
                <div className="space-y-2 text-xs">
                  {retencions.map((r) => (
                    <div
                      key={r.id}
                      className="flex items-center justify-between rounded-lg border border-slate-100 p-3"
                    >
                      <div>
                        <p className="font-semibold text-slate-900">
                          {Number(r.import_retingut).toFixed(2)} € ({r.estat})
                        </p>
                        <p className="text-slate-500">
                          Venciment: {r.data_venciment_garantia} ({r.dies_fins_venciment}d)
                        </p>
                      </div>
                      {r.alerta_venciment_proper && r.estat !== "RECLAMADA" && (
                        <button
                          onClick={() => handleReclamarGarantia(r.id)}
                          className="rounded-lg bg-primary px-2.5 py-1.5 font-semibold text-white"
                        >
                          Reclamar Alliberament
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="rounded-xl border border-slate-200 bg-white p-5">
              <h3 className="text-sm font-semibold text-slate-900 mb-3">
                Recuperació IVA Incobrables (Art. 80 LIVA · 180-270d)
              </h3>
              {art80.length === 0 ? (
                <p className="text-xs text-slate-500">
                  Cap factura en finestra legal d&apos;incobrables Art. 80 LIVA.
                </p>
              ) : (
                <div className="space-y-2 text-xs">
                  {art80.map((a) => (
                    <div
                      key={a.factura_id}
                      className="flex items-center justify-between rounded-lg border border-amber-200 bg-amber-50 p-3"
                    >
                      <div>
                        <p className="font-semibold text-slate-900">
                          {a.serie}-{a.numero_factura} · IVA recuperable: {Number(a.quota_iva).toFixed(2)} €
                        </p>
                        <p className="text-amber-800">
                          {a.dies_impagada} dies impagada · Límit: {a.data_limit_art80} ({a.estat_art80})
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* TAB: PREFACTURES EDITABLES (HITL ABANS DE VERI*FACTU) */}
      {tabActiva === "PREFACTURACIO" && (
        <div className="space-y-4">
          <div className="rounded-xl border border-amber-200 bg-amber-50/60 px-4 py-3 text-xs text-amber-900">
            Revisa i edita línies, hores, tarifes, materials, IVA o retencions de cada pre-factura abans de validar i emetre la factura definitiva a Veri*factu.
          </div>

          <div className="rounded-xl border border-slate-200 bg-white overflow-hidden">
            <div className="border-b border-slate-100 px-5 py-3 flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-sm font-semibold text-slate-900">
                Prefactures en Esborrany ({prefacturesEsborrany.length})
              </h2>
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={() => setTabActiva("WIP_CONTROL")}
                  className="text-xs font-semibold text-primary hover:underline cursor-pointer"
                >
                  + Veure feines acabades pendents de prefacturar
                </button>
                <button
                  type="button"
                  onClick={obrirNovaPrefactura}
                  className="inline-flex items-center gap-1 rounded-lg bg-primary px-3 py-1.5 text-xs font-semibold text-white hover:opacity-90 cursor-pointer"
                >
                  <Plus className="h-3.5 w-3.5" />
                  Nova Pre-factura
                </button>
              </div>
            </div>

            {prefacturesEsborrany.length === 0 ? (
              <div className="p-8 text-center space-y-2">
                <p className="text-sm text-slate-500">
                  No hi ha cap pre-factura en esborrany pendent de revisió.
                </p>
                {wip && wip.nombre_ots_en_wip > 0 && (
                  <button
                    type="button"
                    onClick={() => setTabActiva("WIP_CONTROL")}
                    className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3.5 py-2 text-xs font-semibold text-white"
                  >
                    Tens {wip.nombre_ots_en_wip} feines acabades pendents de prefacturar
                  </button>
                )}
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50 text-slate-600">
                    <tr>
                      <th className="px-4 py-3">Pre-factura</th>
                      <th className="px-4 py-3">Client &amp; Ordre de Treball</th>
                      <th className="px-4 py-3">Línies</th>
                      <th className="px-4 py-3 text-right">Base</th>
                      <th className="px-4 py-3 text-right">IVA</th>
                      <th className="px-4 py-3 text-right">Líquid Exigible</th>
                      <th className="px-4 py-3 text-right">Accions HITL</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {prefacturesEsborrany.map((f) => (
                      <tr key={f.id} className="hover:bg-slate-50">
                        <td className="px-4 py-3">
                          <span className="font-mono font-bold text-amber-800">
                            {f.serie}-{f.numero_factura}
                          </span>
                          <span className="block text-[10px] text-slate-500">
                            {f.data_emissio ? String(f.data_emissio).slice(0, 10) : "—"}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <p className="font-semibold text-slate-900">{f.client_nom || "Client"}</p>
                          {f.ordres_treball_codis && f.ordres_treball_codis.length > 0 && (
                            <p className="font-mono text-[11px] text-primary">
                              OT: {f.ordres_treball_codis.join(", ")}
                            </p>
                          )}
                        </td>
                        <td className="px-4 py-3 text-slate-600">
                          {f.linies?.length || 0} línies
                        </td>
                        <td className="px-4 py-3 text-right tabular-nums">
                          {Number(f.base_imposable).toFixed(2)} €
                        </td>
                        <td className="px-4 py-3 text-right tabular-nums">
                          {Number(f.quota_iva).toFixed(2)} €
                        </td>
                        <td className="px-4 py-3 text-right font-bold tabular-nums text-slate-900">
                          {Number(f.liquid_exigible).toFixed(2)} €
                        </td>
                        <td className="px-4 py-3 text-right whitespace-nowrap space-x-1.5">
                          <button
                            type="button"
                            onClick={() => obrirEditorPrefactura(f)}
                            className="inline-flex items-center gap-1 rounded-lg border border-primary/30 bg-primary/10 px-2.5 py-1.5 text-[11px] font-semibold text-primary hover:bg-primary/20"
                          >
                            <Edit3 className="h-3.5 w-3.5" /> Editar
                          </button>
                          <a
                            href={`${getApiBaseUrl()}/gestio/comptabilitat/factures/${f.id}/pdf`}
                            target="_blank"
                            rel="noreferrer"
                            className="inline-flex items-center gap-1 rounded-lg border border-slate-200 px-2.5 py-1.5 text-[11px] font-medium text-slate-700 hover:bg-slate-100"
                          >
                            <Download className="h-3.5 w-3.5" /> PDF
                          </a>
                          <button
                            type="button"
                            disabled={emittingPrefId === f.id}
                            onClick={() => handleEmetrePrefacturaDirecte(f)}
                            className="inline-flex items-center gap-1 rounded-lg bg-primary px-2.5 py-1.5 text-[11px] font-semibold text-white hover:opacity-90 disabled:opacity-50"
                          >
                            <Send className="h-3.5 w-3.5" />
                            {emittingPrefId === f.id ? "Emetent..." : "Emetre Veri*factu"}
                          </button>
                          <button
                            type="button"
                            onClick={() => handleDescartarPrefactura(f)}
                            className="inline-flex items-center gap-1 rounded-lg border border-rose-200 bg-rose-50 px-2 py-1.5 text-[11px] font-medium text-rose-700 hover:bg-rose-100"
                            title="Descartar esborrany i retornar OT a pendents"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 3: WIP OBRA EN CURS NO FACTURADA */}
      {tabActiva === "WIP_CONTROL" && wip && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <p className="text-xs text-slate-500">Valor WIP Pendent de Prefacturar (PVP)</p>
              <p className="text-xl font-bold text-slate-900">{Number(wip.total_wip_valorat_pvp).toFixed(2)} €</p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <p className="text-xs text-slate-500">Cost Avançat per l&apos;Empresa</p>
              <p className="text-xl font-bold text-slate-900">{Number(wip.total_cost_wip_avancat).toFixed(2)} €</p>
            </div>
            <div className="rounded-xl border border-rose-200 bg-rose-50 p-4">
              <p className="text-xs text-rose-700">OTs Envellides Crítiques (&gt;7 dies)</p>
              <p className="text-xl font-bold text-rose-800">{wip.nombre_ots_envellides_critiques}</p>
            </div>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-5 overflow-x-auto">
            {wip.items.length === 0 ? (
              <p className="text-sm text-slate-500 text-center py-6">
                Cap ordre de treball acabada pendent de prefacturar (WIP = 0).
              </p>
            ) : (
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 text-slate-600">
                  <tr>
                    <th className="px-3 py-2">OT &amp; Client</th>
                    <th className="px-3 py-2">Estat OT</th>
                    <th className="px-3 py-2">Hores × Tarifa</th>
                    <th className="px-3 py-2">Dies en WIP</th>
                    <th className="px-3 py-2">Valor PVP</th>
                    <th className="px-3 py-2">Cost Avançat</th>
                    <th className="px-3 py-2">Alerta</th>
                    <th className="px-3 py-2 text-right">Acció</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {wip.items.map((item) => (
                    <tr key={item.ordre_treball_id}>
                      <td className="px-3 py-2">
                        <span className="font-mono font-semibold text-primary">{item.codi_ot}</span>
                        {item.titol_ot && (
                          <span className="block text-slate-800 font-medium">{item.titol_ot}</span>
                        )}
                        {item.client_nom && (
                          <span className="block text-[11px] text-slate-500">{item.client_nom}</span>
                        )}
                      </td>
                      <td className="px-3 py-2">
                        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-700">
                          {item.estat_ot || "FINALITZADA"}
                        </span>
                      </td>
                      <td className="px-3 py-2 tabular-nums text-slate-700">
                        {Number(item.hores_imputades || 0).toFixed(2)} h ×{" "}
                        {Number(item.preu_hora_aplicat || 0).toFixed(2)} €/h
                        {Number(item.pvp_materials || 0) > 0 && (
                          <span className="block text-[10px] text-slate-500">
                            + Mat: {Number(item.pvp_materials).toFixed(2)} €
                          </span>
                        )}
                      </td>
                      <td className="px-3 py-2">{item.dies_en_wip} dies</td>
                      <td className="px-3 py-2 tabular-nums font-semibold">
                        {Number(item.valor_wip_pvp).toFixed(2)} €
                      </td>
                      <td className="px-3 py-2 tabular-nums">{Number(item.cost_wip_avancat).toFixed(2)} €</td>
                      <td className="px-3 py-2">
                        {item.es_wip_envellit_alerta ? (
                          <span className="rounded-full bg-rose-100 px-2 py-0.5 text-rose-800 font-semibold">
                            WIP Envellit &gt;7d
                          </span>
                        ) : (
                          <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-emerald-800">
                            Normal
                          </span>
                        )}
                      </td>
                      <td className="px-3 py-2 text-right">
                        <button
                          type="button"
                          disabled={convertintWipId === item.ordre_treball_id}
                          onClick={() => handleConvertirWipPrefactura(item.ordre_treball_id)}
                          className="rounded-lg bg-primary px-2.5 py-1.5 text-[11px] font-semibold text-primary-foreground hover:opacity-90 disabled:opacity-50"
                        >
                          {convertintWipId === item.ordre_treball_id
                            ? "Creant pre-factura..."
                            : "Passar a Prefacturació"}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}

      {/* TAB 4: OPERARIS COST HORA EFECTIU & SINISTRALITAT MRR */}
      {tabActiva === "OPERARIS_MRR" && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <h3 className="text-sm font-semibold text-slate-900 mb-3">
              Cost Hora Efectiu Dinàmic d&apos;Operaris
            </h3>
            {operarisCost.length === 0 ? (
              <p className="text-xs text-slate-500">Sense operaris actius registrats.</p>
            ) : (
              <div className="space-y-2 text-xs">
                {operarisCost.map((op) => (
                  <div key={op.usuari_id} className="rounded-lg border border-slate-100 p-3 flex justify-between items-center">
                    <div>
                      <p className="font-semibold text-slate-900">{op.nom_complet}</p>
                      <p className="text-slate-500">
                        Salari+SS: {op.salari_brut_i_ss_visible} · Eficiència: {Number(op.ratio_eficiencia_pct).toFixed(1)}%
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="font-bold text-slate-900">
                        {op.cost_hora_efectiu_mensual !== null
                          ? `${Number(op.cost_hora_efectiu_mensual).toFixed(2)} €/h`
                          : "100% Improductiu / Baixa"}
                      </p>
                      <p className="text-[11px] text-slate-500">
                        Ref: {Number(op.cost_hora_referencia).toFixed(2)} €/h
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <h3 className="text-sm font-semibold text-slate-900 mb-3">
              Auditoria de Sinistralitat de Contractes MRR
            </h3>
            {contractesMrr.length === 0 ? (
              <p className="text-xs text-slate-500">Cap contracte MRR actiu.</p>
            ) : (
              <div className="space-y-2 text-xs">
                {contractesMrr.map((c) => (
                  <div key={c.contracte_id} className="rounded-lg border border-slate-100 p-3 flex justify-between items-center">
                    <div>
                      <p className="font-semibold text-slate-900">{c.codi_contracte}</p>
                      <p className="text-slate-500">
                        Quota: {Number(c.quota_mensual_mrr).toFixed(2)} € · Cost OTs: {Number(c.cost_real_ots_periode).toFixed(2)} €
                      </p>
                    </div>
                    <span
                      className={`rounded-full px-2.5 py-1 font-semibold ${
                        c.semafor === "RENDIBLE"
                          ? "bg-emerald-100 text-emerald-800"
                          : c.semafor === "ALERTA_EROSIO"
                          ? "bg-amber-100 text-amber-800"
                          : "bg-rose-100 text-rose-800"
                      }`}
                    >
                      {Number(c.sinistralitat_pct).toFixed(1)}% · {c.semafor}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB: COSTOS REALS & MARGES OT (PONT MAGATZEM -> COMPTABILITAT) */}
      {tabActiva === "MARGES_OT" && (
        <div className="space-y-6">
          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
              <div>
                <h2 className="text-sm font-semibold text-slate-900">
                  Rendibilitat Real per Ordre de Treball (PMP + Mermes + Tiquets OCR + Mà d&apos;Obra + Flota)
                </h2>
                <p className="text-xs text-slate-500">
                  Consolidació determinista del consum net de magatzem valorat a Preu Mitjà Ponderat i costos de camp
                </p>
              </div>
              <span className="rounded-lg bg-primary/10 px-2.5 py-1 text-xs font-semibold text-primary">
                Llindar alerta: &lt; 15% Marge Brut
              </span>
            </div>

            {margesOt.length === 0 ? (
              <div className="rounded-xl border border-dashed border-slate-200 py-10 text-center text-sm text-slate-500">
                Encara no hi ha ordres de treball registrades per analitzar costos i marges.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-slate-200 text-slate-500">
                      <th className="px-3 py-2">Ordre de Treball</th>
                      <th className="px-3 py-2 text-right">Ingressos Nets</th>
                      <th className="px-3 py-2 text-right">Picking PMP</th>
                      <th className="px-3 py-2 text-right">Mermes (600)</th>
                      <th className="px-3 py-2 text-right">Tiquets OCR</th>
                      <th className="px-3 py-2 text-right">Mà d&apos;Obra &amp; Flota</th>
                      <th className="px-3 py-2 text-right">Cost Real</th>
                      <th className="px-3 py-2 text-right">Marge Brut</th>
                    </tr>
                  </thead>
                  <tbody>
                    {margesOt.map((m) => (
                      <tr key={m.ordre_treball_id} className="border-b border-slate-100">
                        <td className="px-3 py-2.5">
                          <span className="font-mono font-semibold text-primary">{m.codi || m.ordre_treball_id.slice(0, 8)}</span>
                          {m.titol && <span className="ml-2 text-slate-700">{m.titol}</span>}
                        </td>
                        <td className="px-3 py-2.5 text-right tabular-nums font-medium">
                          {Number(m.ingressos_nets_eur).toFixed(2)} €
                        </td>
                        <td className="px-3 py-2.5 text-right tabular-nums">
                          {Number(m.desglossament_costos.materials_picking_pmp_eur).toFixed(2)} €
                        </td>
                        <td className="px-3 py-2.5 text-right tabular-nums">
                          {Number(m.desglossament_costos.mermes_imputades_eur).toFixed(2)} €
                        </td>
                        <td className="px-3 py-2.5 text-right tabular-nums">
                          {Number(m.desglossament_costos.tiquets_camp_ocr_eur).toFixed(2)} €
                        </td>
                        <td className="px-3 py-2.5 text-right tabular-nums">
                          {(
                            Number(m.desglossament_costos.ma_obra_real_eur) +
                            Number(m.desglossament_costos.flota_real_eur)
                          ).toFixed(2)} €
                        </td>
                        <td className="px-3 py-2.5 text-right tabular-nums font-semibold">
                          {Number(m.cost_total_real_eur).toFixed(2)} €
                        </td>
                        <td className="px-3 py-2.5 text-right tabular-nums">
                          <span
                            className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 font-semibold ${
                              m.alerta_desviacio_marge
                                ? "bg-rose-100 text-rose-800"
                                : "bg-emerald-100 text-emerald-800"
                            }`}
                          >
                            {Number(m.marge_brut_eur).toFixed(2)} € ({Number(m.marge_brut_pct).toFixed(1)}%)
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <h3 className="mb-3 text-sm font-semibold text-slate-900">
              Assentaments Analítics Consolidats (Mermes 600/659 i Tiquets OCR 602/629/62X)
            </h3>
            {despesesAnalitiques.length === 0 ? (
              <div className="rounded-xl border border-dashed border-slate-200 py-8 text-center text-xs text-slate-500">
                Cap assentament analític generat des de Magatzem o OCR de Tiquets encara.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-slate-200 text-slate-500">
                      <th className="px-3 py-2">Subcompte</th>
                      <th className="px-3 py-2">Concepte</th>
                      <th className="px-3 py-2">Origen</th>
                      <th className="px-3 py-2 text-right">Base</th>
                      <th className="px-3 py-2 text-right">IVA</th>
                      <th className="px-3 py-2 text-right">Total</th>
                      <th className="px-3 py-2">Estat</th>
                    </tr>
                  </thead>
                  <tbody>
                    {despesesAnalitiques.map((d) => (
                      <tr key={d.id} className="border-b border-slate-100">
                        <td className="px-3 py-2 font-mono font-semibold text-primary">{d.subcompte}</td>
                        <td className="px-3 py-2 text-slate-800">{d.concepte}</td>
                        <td className="px-3 py-2 font-mono text-slate-500">{d.origen}</td>
                        <td className="px-3 py-2 text-right tabular-nums">{Number(d.base_imposable).toFixed(2)} €</td>
                        <td className="px-3 py-2 text-right tabular-nums">{Number(d.quota_iva).toFixed(2)} €</td>
                        <td className="px-3 py-2 text-right tabular-nums font-semibold">
                          {Number(d.import_total).toFixed(2)} €
                        </td>
                        <td className="px-3 py-2">
                          <span className="rounded bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-700">
                            {d.estat}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 5: TIQUETS DE DESPESA DE CAMP */}
      {tabActiva === "TIQUETS" && (
        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <h2 className="text-sm font-semibold text-slate-900 mb-4">
            Bústia d&apos;Auditoria OCR de Tiquets (Control &gt;100 €, AdBlue mixt i NIF Art. 97 LIVA)
          </h2>
          {tiquets.length === 0 ? (
            <p className="text-sm text-slate-500 text-center py-6">
              Cap tiquet de despesa pendent ni registrat al sistema.
            </p>
          ) : (
            <div className="space-y-3 text-xs">
              {tiquets.map((t) => {
                const editableStates = [
                  "PENDENT_AUDITORIA",
                  "INCIDENCIA_COMPROVACIO_MANUAL",
                  "PENDENT_DESGLOSE_MANUAL",
                  "BLOQUEJAT_EXCEDENCIA_100EUR",
                  "PENDENT_DE_CANJE",
                  "ARXIVAT_GESTIO",
                ];
                const canAudit = editableStates.includes(t.estat_aprovacio);
                const splitState = desgloseMap[t.id] || { carb: "", adbl: "" };
                return (
                  <div
                    key={t.id}
                    className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-slate-100 p-3"
                  >
                    <div className="space-y-0.5">
                      <p className="font-semibold text-slate-900">
                        {t.categoria} · {t.rao_social || "Proveïdor per validar"} ·{" "}
                        <span className="tabular-nums">{Number(t.import_total).toFixed(2)} €</span>{" "}
                        <span className="text-slate-500 font-normal">
                          (IVA: {Number(t.quota_iva).toFixed(2)} € · PGC {t.subcompte_pgc || "629000"})
                        </span>
                      </p>
                      <p className="text-slate-500">
                        {t.data_tiquet} · Emissor: {t.nif_emissor || "N/D"} · Comprador:{" "}
                        {t.nif_comprador || "SENSE NIF (62X / Canje)"} ·{" "}
                        <span className="font-semibold text-slate-700">{t.estat_aprovacio}</span>
                        {t.nom_fitxer_visible && (
                          <span className="ml-2 font-mono text-[11px] text-primary">
                            {t.nom_fitxer_visible}
                          </span>
                        )}
                      </p>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      {(t.requereix_aprovacio_boss ||
                        t.estat_aprovacio === "BLOQUEJAT_EXCEDENCIA_100EUR") && (
                        <span className="rounded bg-rose-100 px-2 py-0.5 font-semibold text-rose-900">
                          &gt;100€ Targeta bloquejada · Només BOSS
                        </span>
                      )}
                      {t.estat_aprovacio === "PENDENT_DESGLOSE_MANUAL" && (
                        <div className="flex items-center gap-1.5">
                          <input
                            type="number"
                            step="0.01"
                            placeholder="Dièsel €"
                            value={splitState.carb}
                            onChange={(e) =>
                              setDesgloseMap((prev) => ({
                                ...prev,
                                [t.id]: { ...splitState, carb: e.target.value },
                              }))
                            }
                            className="w-20 rounded border border-slate-300 px-2 py-1 text-xs tabular-nums"
                          />
                          <input
                            type="number"
                            step="0.01"
                            placeholder="AdBlue €"
                            value={splitState.adbl}
                            onChange={(e) =>
                              setDesgloseMap((prev) => ({
                                ...prev,
                                [t.id]: { ...splitState, adbl: e.target.value },
                              }))
                            }
                            className="w-20 rounded border border-slate-300 px-2 py-1 text-xs tabular-nums"
                          />
                        </div>
                      )}
                      {canAudit && (
                        <>
                          <button
                            onClick={() => handleAuditarTiquet(t.id, "APROVAT")}
                            className="rounded-lg bg-primary px-2.5 py-1 text-white font-semibold"
                          >
                            {t.estat_aprovacio === "BLOQUEJAT_EXCEDENCIA_100EUR"
                              ? "Aprovar i desbloquejar targeta"
                              : "Aprovar"}
                          </button>
                          <button
                            onClick={() => handleAuditarTiquet(t.id, "REBUTJAT")}
                            className="rounded-lg bg-rose-600 px-2.5 py-1 text-white font-semibold"
                          >
                            Rebutjar
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* TAB 6: CONCILIACIÓ BANCÀRIA CSB 43 */}
      {tabActiva === "NORMA43" && (
        <div className="rounded-xl border border-slate-200 bg-white p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-sm font-semibold text-slate-900">
                Conciliació Bancària Idempotent (AEB Norma 43 / CSB 43)
              </h2>
              <p className="text-xs text-slate-500">
                Enganxa el contingut d&apos;un fitxer .c43 / .n43 o línies YYYY-MM-DD|Concepte|Import|Saldo
              </p>
            </div>
            <Building2 className="h-5 w-5 text-slate-400" />
          </div>

          <textarea
            rows={5}
            value={textC43}
            onChange={(e) => setTextC43(e.target.value)}
            placeholder="2026-11-12|Transferència Client ABC|1210.00|15420.50"
            className="w-full rounded-lg border border-slate-200 p-3 font-mono text-xs"
          />

          <div className="flex gap-2">
            <button
              onClick={() => handleConciliarNorma43(false)}
              className="rounded-lg border border-slate-300 bg-white px-3.5 py-2 text-xs font-semibold text-slate-700"
            >
              Previsualitzar Creuament
            </button>
            <button
              onClick={() => handleConciliarNorma43(true)}
              className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3.5 py-2 text-xs font-semibold text-white"
            >
              <FileCheck2 className="h-4 w-4" />
              Confirmar Conciliació HITL
            </button>
          </div>

          {movimentsC43.length > 0 && (
            <div className="space-y-1.5 text-xs pt-2">
              {movimentsC43.map((m) => (
                <div
                  key={m.huella_sha256}
                  className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2"
                >
                  <span>
                    {m.data_operacio} · {m.concepte} ({Number(m.import_moviment).toFixed(2)} €)
                  </span>
                  <span className="font-semibold">
                    {m.duplicat_rebutjat
                      ? "Duplicat Rebutjat (Idempotent)"
                      : m.factura_suggerida_id
                      ? "Conciliat amb Factura"
                      : "Sense coincidència"}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* MODAL EMISSIÓ FACTURA VERI*FACTU */}
      {modalFactura && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-base font-bold text-slate-900">
                Nova Factura Veri*factu (Sèrie F)
              </h3>
              <button onClick={() => setModalFactura(false)}>
                <X className="h-5 w-5 text-slate-400" />
              </button>
            </div>
            <form onSubmit={handleEmetreFactura} className="space-y-3 text-xs">
              <div>
                <label className="block font-medium text-slate-700 mb-1">
                  Client de la Factura
                </label>
                <select
                  required
                  value={clientIdInput}
                  onChange={(e) => setClientIdInput(e.target.value)}
                  className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-slate-900"
                >
                  <option value="">
                    {clientsList.length === 0
                      ? "Sense clients donats d'alta al tenant..."
                      : "Selecciona un client..."}
                  </option>
                  {clientsList.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.rao_social} ({c.nif})
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block font-medium text-slate-700 mb-1">
                  Concepte de la línia
                </label>
                <input
                  required
                  value={concepteInput}
                  onChange={(e) => setConcepteInput(e.target.value)}
                  placeholder="Servei tècnic / Instal·lació"
                  className="w-full rounded-lg border border-slate-200 px-3 py-2"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-medium text-slate-700 mb-1">
                    Import Base (€)
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    required
                    value={preuInput}
                    onChange={(e) => setPreuInput(e.target.value)}
                    className="w-full rounded-lg border border-slate-200 px-3 py-2"
                  />
                </div>
                <div>
                  <label className="block font-medium text-slate-700 mb-1">
                    Retenció Garantia 4308 (%)
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    value={retGarantiaPct}
                    onChange={(e) => setRetGarantiaPct(e.target.value)}
                    className="w-full rounded-lg border border-slate-200 px-3 py-2"
                  />
                </div>
              </div>
              <label className="flex items-center gap-2 pt-1">
                <input
                  type="checkbox"
                  checked={esIsp}
                  onChange={(e) => setEsIsp(e.target.checked)}
                />
                <span>Inversió del Subjecte Passiu (ISP 0% IVA Art. 84)</span>
              </label>
              <div className="flex justify-end gap-2 pt-3">
                <button
                  type="button"
                  onClick={() => setModalFactura(false)}
                  className="rounded-lg border border-slate-200 px-4 py-2 font-medium"
                >
                  Cancel·lar
                </button>
                <button
                  type="submit"
                  className="rounded-lg bg-primary px-4 py-2 font-semibold text-white"
                >
                  Emetre i Encadenar SHA-256
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL EDITOR / CREADOR DE PRE-FACTURA (EDITAR ABANS D'EMETRE A VERI*FACTU) */}
      {(editingPrefactura || creatingPrefactura) && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4 overflow-y-auto">
          <div className="w-full max-w-5xl rounded-2xl bg-white p-6 shadow-2xl space-y-5 my-8">
            <div className="flex items-start justify-between border-b border-slate-100 pb-3">
              <div>
                <span className="inline-block rounded-full bg-amber-100 px-2.5 py-0.5 text-[11px] font-bold text-amber-800">
                  ESBORRANY EDITABLE · HITL
                </span>
                <h3 className="text-lg font-bold text-slate-900 mt-1">
                  {creatingPrefactura
                    ? "Nova Pre-factura Editable (Sèrie PRE)"
                    : `Editar Pre-factura ${editingPrefactura?.serie}-${editingPrefactura?.numero_factura}${
                        editingPrefactura?.client_nom ? ` · ${editingPrefactura.client_nom}` : ""
                      }`}
                </h3>
                {editingPrefactura?.ordres_treball_codis &&
                  editingPrefactura.ordres_treball_codis.length > 0 && (
                    <p className="text-xs font-mono text-primary mt-0.5">
                      Ordres de Treball vinculades: {editingPrefactura.ordres_treball_codis.join(", ")}
                    </p>
                  )}
              </div>
              <button
                type="button"
                onClick={tancarModalPrefactura}
                className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600 cursor-pointer"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {error && (
              <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-2.5 text-xs text-rose-800">
                {error}
              </div>
            )}

            {/* Capçalera Fiscal */}
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-6 text-xs">
              {creatingPrefactura && (
                <div className="sm:col-span-2 lg:col-span-2">
                  <label className="block font-medium text-slate-700 mb-1">Client *</label>
                  <select
                    required
                    value={prefClientId}
                    onChange={(e) => setPrefClientId(e.target.value)}
                    className="w-full rounded-lg border border-slate-200 bg-white px-2.5 py-2"
                  >
                    <option value="">Selecciona client...</option>
                    {clientsList.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.rao_social} ({c.nif})
                      </option>
                    ))}
                  </select>
                </div>
              )}
              <div>
                <label className="block font-medium text-slate-700 mb-1">Data Emissió</label>
                <input
                  type="date"
                  value={prefDataEmissio}
                  onChange={(e) => setPrefDataEmissio(e.target.value)}
                  className="w-full rounded-lg border border-slate-200 px-2.5 py-2"
                />
              </div>
              <div>
                <label className="block font-medium text-slate-700 mb-1">Data Venciment</label>
                <input
                  type="date"
                  value={prefDataVenciment}
                  onChange={(e) => setPrefDataVenciment(e.target.value)}
                  className="w-full rounded-lg border border-slate-200 px-2.5 py-2"
                />
              </div>
              <div>
                <label className="block font-medium text-slate-700 mb-1">Mètode Pagament</label>
                <select
                  value={prefMetodePagament}
                  onChange={(e) => setPrefMetodePagament(e.target.value)}
                  className="w-full rounded-lg border border-slate-200 bg-white px-2.5 py-2"
                >
                  <option value="TRANSFERENCIA">Transferència</option>
                  <option value="REBUT_DOMICILIAT">Rebut Domiciliat SEPA</option>
                  <option value="TARGETA">Targeta</option>
                  <option value="EFECTIU">Efectiu</option>
                  <option value="CONFIRMING">Confirming</option>
                </select>
              </div>
              <div>
                <label className="block font-medium text-slate-700 mb-1">Retenció IRPF (%)</label>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  max="30"
                  value={prefRetIrpfPct}
                  onChange={(e) => setPrefRetIrpfPct(e.target.value)}
                  className="w-full rounded-lg border border-slate-200 px-2.5 py-2 tabular-nums"
                />
              </div>
              {!creatingPrefactura && (
                <div>
                  <label className="block font-medium text-slate-700 mb-1">
                    Retenció Garantia 4308 (%)
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    max="20"
                    value={prefRetGarantiaPct}
                    onChange={(e) => setPrefRetGarantiaPct(e.target.value)}
                    className="w-full rounded-lg border border-slate-200 px-2.5 py-2 tabular-nums"
                  />
                </div>
              )}
            </div>

            <div className="flex flex-wrap items-center justify-between gap-3">
              <label className="inline-flex items-center gap-2 text-xs text-slate-700">
                <input
                  type="checkbox"
                  checked={prefEsIsp}
                  onChange={(e) => setPrefEsIsp(e.target.checked)}
                />
                <span>Inversió del Subjecte Passiu (ISP · 0% IVA Art. 84 LIVA)</span>
              </label>

              {creatingPrefactura && (
                <div className="flex items-center gap-2 text-xs">
                  <span className="font-medium text-slate-700">Garantia 4308 (%):</span>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    max="20"
                    value={prefRetGarantiaPct}
                    onChange={(e) => setPrefRetGarantiaPct(e.target.value)}
                    className="w-20 rounded-lg border border-slate-200 px-2 py-1 tabular-nums"
                  />
                </div>
              )}
            </div>

            {/* Selector Ràpid de Materials del Magatzem + Conceptes de Facturació */}
            <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-3 space-y-2.5 text-xs">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h4 className="font-bold uppercase tracking-wider text-slate-600 flex items-center gap-1.5">
                  <Package className="h-3.5 w-3.5 text-primary" />
                  Afegir Materials del Magatzem o Conceptes ({prefLinies.length} línies)
                </h4>
                <div className="flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    onClick={() =>
                      setPrefLinies((prev) => [
                        ...prev,
                        {
                          concepte: "",
                          compte_pgc: "705000",
                          quantitat: 1,
                          preu_venda_unitari: 0,
                          descompte_aplicat_pct: 0,
                          tipus_iva: prefEsIsp ? 0 : 21,
                        },
                      ])
                    }
                    className="inline-flex items-center gap-1 rounded-lg border border-primary/30 bg-primary/10 px-2.5 py-1.5 font-semibold text-primary hover:bg-primary/20 cursor-pointer"
                  >
                    <Plus className="h-3.5 w-3.5" /> Afegir Concepte / Servei
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      setPrefLinies((prev) => [
                        ...prev,
                        {
                          concepte: "",
                          compte_pgc: "700000",
                          quantitat: 1,
                          preu_venda_unitari: 0,
                          descompte_aplicat_pct: 0,
                          tipus_iva: prefEsIsp ? 0 : 21,
                        },
                      ])
                    }
                    className="inline-flex items-center gap-1 rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 font-semibold text-slate-700 hover:bg-slate-100 cursor-pointer"
                  >
                    <Plus className="h-3.5 w-3.5" /> Afegir Material Lliure
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      setPrefLinies((prev) => [
                        ...prev,
                        {
                          concepte: "",
                          compte_pgc: "554000",
                          quantitat: 1,
                          preu_venda_unitari: 0,
                          descompte_aplicat_pct: 0,
                          tipus_iva: 0,
                        },
                      ])
                    }
                    className="inline-flex items-center gap-1 rounded-lg border border-amber-300 bg-amber-50 px-2.5 py-1.5 font-semibold text-amber-800 hover:bg-amber-100 cursor-pointer"
                  >
                    <Plus className="h-3.5 w-3.5" /> Afegir Suplert (554)
                  </button>
                </div>
              </div>

              {articlesMagatzem.length > 0 && (
                <div className="flex flex-col sm:flex-row gap-2">
                  <div className="relative flex-1">
                    <Search className="h-3.5 w-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
                    <input
                      type="text"
                      value={cercaMaterialPref}
                      onFocus={() => setMaterialPrefDropdownOpen(true)}
                      onChange={(e) => {
                        setCercaMaterialPref(e.target.value);
                        setMaterialPrefDropdownOpen(true);
                      }}
                      placeholder="Cercar material del magatzem per referència o nom per afegir-lo a la factura..."
                      className="w-full pl-8 pr-3 py-2 rounded-lg border border-slate-200 bg-white"
                    />
                    {materialPrefDropdownOpen && articlesPrefFiltrats.length > 0 && (
                      <div className="absolute left-0 right-0 top-full mt-1 z-30 max-h-52 overflow-y-auto rounded-xl border border-slate-200 bg-white shadow-xl divide-y divide-slate-100">
                        {articlesPrefFiltrats.map((art) => (
                          <button
                            key={art.id}
                            type="button"
                            onClick={() => afegirMaterialAPrefactura(art)}
                            className="w-full px-3 py-2 text-left hover:bg-slate-50 flex items-center justify-between gap-2 cursor-pointer"
                          >
                            <div className="min-w-0">
                              <span className="font-mono text-[10px] font-bold text-primary mr-1.5">
                                [{art.referencia_inventari}]
                              </span>
                              <span className="font-medium text-slate-900">{art.nom}</span>
                              {art.estoc_disponible !== undefined && (
                                <span className="ml-2 text-[10px] text-slate-500">
                                  Estoc: {Number(art.estoc_disponible).toFixed(2)}{" "}
                                  {art.unitat_mesura || "uts"}
                                </span>
                              )}
                            </div>
                            <span className="font-semibold tabular-nums text-primary shrink-0">
                              {Number(art.preu_venda || 0).toFixed(2)} €
                            </span>
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="text-[11px] text-slate-500">Qt:</span>
                    <input
                      type="number"
                      step="0.01"
                      min="0.01"
                      value={materialPrefQt}
                      onChange={(e) => setMaterialPrefQt(e.target.value)}
                      className="w-20 rounded-lg border border-slate-200 bg-white px-2.5 py-2 tabular-nums"
                    />
                  </div>
                </div>
              )}
            </div>

            {/* Taula Editable de Línies */}
            <div className="space-y-2">
              <div className="overflow-x-auto rounded-xl border border-slate-200">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50 text-slate-600">
                    <tr>
                      <th className="px-2 py-2 w-36">Tipus / PGC</th>
                      <th className="px-2.5 py-2 min-w-[220px]">Concepte</th>
                      <th className="px-2 py-2 w-20">Qt.</th>
                      <th className="px-2 py-2 w-24">Preu u. (€)</th>
                      <th className="px-2 py-2 w-20">Dto %</th>
                      <th className="px-2 py-2 w-20">IVA %</th>
                      <th className="px-2 py-2 w-24 text-right">Subtotal</th>
                      <th className="px-2 py-2 w-10"></th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {prefLinies.map((lin, idx) => {
                      const esSuplertLinia = (lin.compte_pgc || "700000").startsWith("554");
                      const sub = round2(
                        Number(lin.quantitat || 0) *
                          Number(lin.preu_venda_unitari || 0) *
                          (1 - Number(lin.descompte_aplicat_pct || 0) / 100)
                      );
                      return (
                        <tr key={lin.id || `new-${idx}`}>
                          <td className="px-2 py-2">
                            <select
                              value={
                                esSuplertLinia
                                  ? "554000"
                                  : lin.compte_pgc === "705000"
                                    ? "705000"
                                    : "700000"
                              }
                              onChange={(e) => {
                                const nouCompte = e.target.value;
                                setPrefLinies((prev) =>
                                  prev.map((item, i) =>
                                    i === idx
                                      ? {
                                          ...item,
                                          compte_pgc: nouCompte,
                                          tipus_iva: nouCompte.startsWith("554")
                                            ? 0
                                            : item.tipus_iva || 21,
                                        }
                                      : item
                                  )
                                );
                              }}
                              className="w-full rounded border border-slate-200 bg-white px-1.5 py-1 text-[11px]"
                            >
                              <option value="700000">Material (700)</option>
                              <option value="705000">Servei / M.O. (705)</option>
                              <option value="554000">Suplert (554)</option>
                            </select>
                          </td>
                          <td className="px-2.5 py-2">
                            <div className="flex items-center gap-1.5">
                              <input
                                type="text"
                                value={lin.concepte}
                                onChange={(e) =>
                                  setPrefLinies((prev) =>
                                    prev.map((item, i) =>
                                      i === idx ? { ...item, concepte: e.target.value } : item
                                    )
                                  )
                                }
                                placeholder="Descripció del treball, concepte o material"
                                className="w-full rounded border border-slate-200 px-2 py-1"
                              />
                              {lin.article_id && (
                                <span className="shrink-0 rounded bg-primary/10 px-1.5 py-0.5 text-[9px] font-bold text-primary">
                                  MAG
                                </span>
                              )}
                            </div>
                          </td>
                          <td className="px-2 py-2">
                            <input
                              type="number"
                              step="any"
                              min="0.001"
                              value={lin.quantitat}
                              onChange={(e) =>
                                setPrefLinies((prev) =>
                                  prev.map((item, i) =>
                                    i === idx
                                      ? { ...item, quantitat: Number(e.target.value) }
                                      : item
                                  )
                                )
                              }
                              className="w-full rounded border border-slate-200 px-2 py-1 tabular-nums"
                            />
                          </td>
                          <td className="px-2 py-2">
                            <input
                              type="number"
                              step="any"
                              min="0"
                              value={lin.preu_venda_unitari}
                              onChange={(e) =>
                                setPrefLinies((prev) =>
                                  prev.map((item, i) =>
                                    i === idx
                                      ? { ...item, preu_venda_unitari: Number(e.target.value) }
                                      : item
                                  )
                                )
                              }
                              className="w-full rounded border border-slate-200 px-2 py-1 tabular-nums"
                            />
                          </td>
                          <td className="px-2 py-2">
                            <input
                              type="number"
                              step="0.1"
                              min="0"
                              max="100"
                              value={lin.descompte_aplicat_pct}
                              onChange={(e) =>
                                setPrefLinies((prev) =>
                                  prev.map((item, i) =>
                                    i === idx
                                      ? { ...item, descompte_aplicat_pct: Number(e.target.value) }
                                      : item
                                  )
                                )
                              }
                              className="w-full rounded border border-slate-200 px-2 py-1 tabular-nums"
                            />
                          </td>
                          <td className="px-2 py-2">
                            <select
                              disabled={prefEsIsp || esSuplertLinia}
                              value={prefEsIsp || esSuplertLinia ? 0 : lin.tipus_iva}
                              onChange={(e) =>
                                setPrefLinies((prev) =>
                                  prev.map((item, i) =>
                                    i === idx
                                      ? { ...item, tipus_iva: Number(e.target.value) }
                                      : item
                                  )
                                )
                              }
                              className="w-full rounded border border-slate-200 bg-white px-1.5 py-1 tabular-nums disabled:opacity-50"
                            >
                              <option value={21}>21%</option>
                              <option value={10}>10%</option>
                              <option value={4}>4%</option>
                              <option value={0}>0%</option>
                            </select>
                          </td>
                          <td className="px-2 py-2 text-right font-semibold tabular-nums">
                            {sub.toFixed(2)} €
                          </td>
                          <td className="px-2 py-2 text-center">
                            <button
                              type="button"
                              disabled={prefLinies.length <= 1}
                              onClick={() =>
                                setPrefLinies((prev) => prev.filter((_, i) => i !== idx))
                              }
                              className="rounded p-1 text-rose-600 hover:bg-rose-50 disabled:opacity-30 cursor-pointer"
                              title="Eliminar línia"
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Resum de Totals en Viu */}
            <div className="rounded-xl bg-slate-50 border border-slate-200 p-4 flex flex-wrap items-center justify-between gap-4 text-xs">
              <div className="flex flex-wrap gap-5">
                <div>
                  <span className="text-slate-500 block">Base Imposable</span>
                  <span className="font-bold tabular-nums text-slate-900">
                    {editorTotals.baseTotal.toFixed(2)} €
                  </span>
                </div>
                <div>
                  <span className="text-slate-500 block">Quota IVA</span>
                  <span className="font-bold tabular-nums text-slate-900">
                    {editorTotals.ivaTotal.toFixed(2)} €
                  </span>
                </div>
                {editorTotals.suplerts > 0 && (
                  <div>
                    <span className="text-slate-500 block">Suplerts (554)</span>
                    <span className="font-bold tabular-nums text-amber-700">
                      {editorTotals.suplerts.toFixed(2)} €
                    </span>
                  </div>
                )}
                {editorTotals.retIrpf > 0 && (
                  <div>
                    <span className="text-slate-500 block">Retenció IRPF</span>
                    <span className="font-bold tabular-nums text-rose-700">
                      -{editorTotals.retIrpf.toFixed(2)} €
                    </span>
                  </div>
                )}
                {editorTotals.retGar > 0 && (
                  <div>
                    <span className="text-slate-500 block">Garantia 4308</span>
                    <span className="font-bold tabular-nums text-rose-700">
                      -{editorTotals.retGar.toFixed(2)} €
                    </span>
                  </div>
                )}
              </div>
              <div className="text-right">
                <span className="text-slate-500 block">TOTAL LÍQUID EXIGIBLE</span>
                <span className="text-xl font-black tabular-nums text-primary">
                  {editorTotals.liquid.toFixed(2)} €
                </span>
              </div>
            </div>

            <div className="flex flex-wrap items-center justify-end gap-2 pt-2 border-t border-slate-100">
              <button
                type="button"
                onClick={tancarModalPrefactura}
                className="rounded-lg border border-slate-200 px-4 py-2 text-xs font-medium text-slate-700 cursor-pointer"
              >
                Cancel·lar
              </button>
              <button
                type="button"
                disabled={savingPrefactura}
                onClick={() => handleDesarPrefactura(false)}
                className="rounded-lg border border-primary bg-primary/10 px-4 py-2 text-xs font-semibold text-primary hover:bg-primary/20 disabled:opacity-50 cursor-pointer"
              >
                {savingPrefactura ? "Desant..." : "Desar Canvis (Esborrany)"}
              </button>
              <button
                type="button"
                disabled={savingPrefactura}
                onClick={() => handleDesarPrefactura(true)}
                className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-4 py-2 text-xs font-semibold text-white hover:opacity-90 disabled:opacity-50 cursor-pointer"
              >
                <Send className="h-3.5 w-3.5" />
                {savingPrefactura ? "Processant..." : "Desar i Emetre Factura Veri*factu"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL RECTIFICATIVA SÈRIE R (Spec 007 RF-14 i Ordre HAC/1177/2024) */}
      {facturaRectificar && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-base font-bold text-slate-900">
                Emetre Rectificativa Sèrie R ({facturaRectificar.num_serie_verifactu || `${facturaRectificar.serie}-${facturaRectificar.numero_factura}`})
              </h3>
              <button onClick={() => setFacturaRectificar(null)}>
                <X className="h-5 w-5 text-slate-400" />
              </button>
            </div>
            <form onSubmit={handleEmetreRectificativa} className="space-y-3 text-xs">
              <p className="text-slate-600">
                Es generarà una factura rectificativa Sèrie R encadenada a Veri*factu per a la factura original de{" "}
                <strong>{Number(facturaRectificar.liquid_exigible).toFixed(2)} €</strong>.
              </p>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-medium text-slate-700 mb-1">
                    Tipus Rectificativa AEAT
                  </label>
                  <select
                    value={tipusRectificar}
                    onChange={(e) => setTipusRectificar(e.target.value as any)}
                    className="w-full rounded-lg border border-slate-200 bg-white px-2.5 py-2"
                  >
                    <option value="R1">R1 · Error fonamentat en dret / Art. 80.1, 80.2 i 80.6</option>
                    <option value="R2">R2 · Concurs de creditors (Art. 80.3 LIVA)</option>
                    <option value="R3">R3 · Crèdit incobrable (Art. 80.4 LIVA)</option>
                    <option value="R4">R4 · Resta de causes de rectificació</option>
                  </select>
                </div>
                <div>
                  <label className="block font-medium text-slate-700 mb-1">
                    Modalitat (Art. 15 RD 1619/2012)
                  </label>
                  <select
                    value={modalitatRectificar}
                    onChange={(e) => setModalitatRectificar(e.target.value as "S" | "I")}
                    className="w-full rounded-lg border border-slate-200 bg-white px-2.5 py-2"
                  >
                    <option value="S">S · Per Substitució</option>
                    <option value="I">I · Per Diferències (abono negatiu)</option>
                  </select>
                </div>
              </div>
              <div>
                <label className="block font-medium text-slate-700 mb-1">
                  Motiu legal de rectificació
                </label>
                <input
                  required
                  minLength={3}
                  value={motiuRectificar}
                  onChange={(e) => setMotiuRectificar(e.target.value)}
                  placeholder="Ex: Error en base imposable o devolució parcial de partida"
                  className="w-full rounded-lg border border-slate-200 px-3 py-2"
                />
              </div>
              <div className="flex justify-end gap-2 pt-3">
                <button
                  type="button"
                  onClick={() => setFacturaRectificar(null)}
                  className="rounded-lg border border-slate-200 px-4 py-2 font-medium"
                >
                  Cancel·lar
                </button>
                <button
                  type="submit"
                  className="rounded-lg bg-amber-600 px-4 py-2 font-semibold text-white hover:bg-amber-500"
                >
                  Emetre Sèrie R
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL ANUL·LACIÓ DE FACTURA (RegistroAnulacion Art. 13.2 Ordre HAC/1177/2024) */}
      {facturaAnular && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-base font-bold text-rose-800">
                Anul·lar Factura a Veri*factu ({facturaAnular.num_serie_verifactu || `${facturaAnular.serie}-${facturaAnular.numero_factura}`})
              </h3>
              <button onClick={() => setFacturaAnular(null)}>
                <X className="h-5 w-5 text-slate-400" />
              </button>
            </div>
            <form onSubmit={handleAnularFactura} className="space-y-3 text-xs">
              <p className="text-slate-600">
                S&apos;emetrà un <strong>Registre d&apos;Anul·lació (RegistroAnulacion)</strong> encadenat criptogràficament amb SHA-256 a la cadena del SIF segons l&apos;Art. 13.2 de l&apos;Ordre HAC/1177/2024. La factura original es conservarà marcada com anul·lada.
              </p>
              <div>
                <label className="block font-medium text-slate-700 mb-1">
                  Motiu de l&apos;anul·lació
                </label>
                <input
                  required
                  minLength={3}
                  value={motiuAnular}
                  onChange={(e) => setMotiuAnular(e.target.value)}
                  placeholder="Ex: Factura emesa per error abans de lliurament al destinatari"
                  className="w-full rounded-lg border border-slate-200 px-3 py-2"
                />
              </div>
              <div className="flex justify-end gap-2 pt-3">
                <button
                  type="button"
                  onClick={() => setFacturaAnular(null)}
                  className="rounded-lg border border-slate-200 px-4 py-2 font-medium"
                >
                  Cancel·lar
                </button>
                <button
                  type="submit"
                  className="rounded-lg bg-rose-600 px-4 py-2 font-semibold text-white hover:bg-rose-500"
                >
                  Confirmar RegistroAnulacion
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL REGISTRAR COBRAMENT MANUAL */}
      {facturaCobrament && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                <Banknote className="h-5 w-5 text-emerald-600" />
                Registrar Cobrament —{" "}
                {facturaCobrament.num_serie_verifactu ||
                  `${facturaCobrament.serie}-${facturaCobrament.numero_factura}`}
              </h3>
              <button type="button" onClick={() => setFacturaCobrament(null)}>
                <X className="h-5 w-5 text-slate-400" />
              </button>
            </div>
            <p className="text-xs text-slate-600 mb-4">
              Líquid exigible:{" "}
              <strong className="tabular-nums text-slate-900">
                {Number(facturaCobrament.liquid_exigible).toFixed(2)} €
              </strong>
              {" · "}Client: <strong>{facturaCobrament.client_nom || "—"}</strong>
            </p>
            <form onSubmit={handleRegistrarCobrament} className="space-y-3 text-xs">
              <div>
                <label className="block font-medium text-slate-700 mb-1">Estat de cobrament</label>
                <select
                  value={cobramentEstat}
                  onChange={(e) => {
                    const nou = e.target.value as "COBRADA" | "PARCIAL" | "PENDENT" | "IMPAGADA";
                    setCobramentEstat(nou);
                    if (nou === "COBRADA") {
                      setCobramentImport(Number(facturaCobrament.liquid_exigible || 0).toFixed(2));
                    } else if (nou === "PENDENT" || nou === "IMPAGADA") {
                      setCobramentImport("0.00");
                    }
                  }}
                  className="w-full rounded-lg border border-slate-200 px-3 py-2"
                >
                  <option value="COBRADA">COBRADA (Totalitat del líquid exigible)</option>
                  <option value="PARCIAL">PARCIAL (Cobrament a compte)</option>
                  <option value="PENDENT">PENDENT</option>
                  <option value="IMPAGADA">IMPAGADA</option>
                </select>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-medium text-slate-700 mb-1">Import cobrat (€)</label>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    max={Number(facturaCobrament.liquid_exigible || 0)}
                    disabled={cobramentEstat === "COBRADA"}
                    required
                    value={cobramentImport}
                    onChange={(e) => setCobramentImport(e.target.value)}
                    className="w-full rounded-lg border border-slate-200 px-3 py-2 tabular-nums disabled:bg-slate-50"
                  />
                </div>
                <div>
                  <label className="block font-medium text-slate-700 mb-1">Data cobrament real</label>
                  <input
                    type="date"
                    value={cobramentData}
                    onChange={(e) => setCobramentData(e.target.value)}
                    className="w-full rounded-lg border border-slate-200 px-3 py-2"
                  />
                </div>
              </div>
              <div>
                <label className="block font-medium text-slate-700 mb-1">Notes / Referència bancària (opcional)</label>
                <input
                  type="text"
                  maxLength={500}
                  value={cobramentNotes}
                  onChange={(e) => setCobramentNotes(e.target.value)}
                  placeholder="Ex: Transferència CaixaBank 23/11"
                  className="w-full rounded-lg border border-slate-200 px-3 py-2"
                />
              </div>
              <div className="flex justify-end gap-2 pt-3">
                <button
                  type="button"
                  onClick={() => setFacturaCobrament(null)}
                  className="rounded-lg border border-slate-200 px-4 py-2 font-medium"
                >
                  Cancel·lar
                </button>
                <button
                  type="submit"
                  disabled={savingCobrament}
                  className="rounded-lg bg-primary px-4 py-2 font-semibold text-white hover:opacity-90 disabled:opacity-50"
                >
                  {savingCobrament ? "Desant..." : "Confirmar Cobrament"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL ALTA / EDICIÓ DESPESA FIXA D'ESTRUCTURA */}
      {modalDespesaFixa && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-base font-bold text-slate-900">
                {editingDespesaFixa ? "Editar Despesa Fixa" : "Nova Despesa Fixa d'Estructura"}
              </h3>
              <button type="button" onClick={() => setModalDespesaFixa(false)}>
                <X className="h-5 w-5 text-slate-400" />
              </button>
            </div>
            <form onSubmit={handleDesarDespesaFixa} className="space-y-3 text-xs">
              <div>
                <label className="block font-medium text-slate-700 mb-1">Concepte</label>
                <input
                  type="text"
                  required
                  minLength={2}
                  maxLength={255}
                  value={dfConcepte}
                  onChange={(e) => setDfConcepte(e.target.value)}
                  placeholder="Ex: Lloguer nau industrial, Gestoria fiscal..."
                  className="w-full rounded-lg border border-slate-200 px-3 py-2"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-medium text-slate-700 mb-1">Categoria</label>
                  <select
                    value={dfCategoria}
                    onChange={(e) => setDfCategoria(e.target.value as DespesaFixaItem["categoria"])}
                    className="w-full rounded-lg border border-slate-200 px-3 py-2"
                  >
                    <option value="LLOGUER">Lloguer</option>
                    <option value="SUBMINISTRAMENTS">Subministraments</option>
                    <option value="ASSEGURANCES">Assegurances</option>
                    <option value="GESTORIA">Gestoria</option>
                    <option value="SOFTWARE">Software</option>
                    <option value="ALTRES">Altres</option>
                  </select>
                </div>
                <div>
                  <label className="block font-medium text-slate-700 mb-1">Periodicitat</label>
                  <select
                    value={dfPeriodicitat}
                    onChange={(e) => setDfPeriodicitat(e.target.value as DespesaFixaItem["periodicitat"])}
                    className="w-full rounded-lg border border-slate-200 px-3 py-2"
                  >
                    <option value="MENSUAL">Mensual (×1)</option>
                    <option value="TRIMESTRAL">Trimestral (÷3/mes)</option>
                    <option value="ANUAL">Anual (÷12/mes)</option>
                  </select>
                </div>
              </div>
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="block font-medium text-slate-700 mb-1">Base (€)</label>
                  <input
                    type="number"
                    step="0.01"
                    min="0.01"
                    required
                    value={dfImportBase}
                    onChange={(e) => setDfImportBase(e.target.value)}
                    className="w-full rounded-lg border border-slate-200 px-3 py-2 tabular-nums"
                  />
                </div>
                <div>
                  <label className="block font-medium text-slate-700 mb-1">Quota IVA (€)</label>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    value={dfQuotaIva}
                    onChange={(e) => setDfQuotaIva(e.target.value)}
                    className="w-full rounded-lg border border-slate-200 px-3 py-2 tabular-nums"
                  />
                </div>
                <div>
                  <label className="block font-medium text-slate-700 mb-1">Dia càrrec</label>
                  <input
                    type="number"
                    min="1"
                    max="28"
                    required
                    value={dfDiaCarrec}
                    onChange={(e) => setDfDiaCarrec(e.target.value)}
                    className="w-full rounded-lg border border-slate-200 px-3 py-2 tabular-nums"
                  />
                </div>
              </div>
              <div className="flex justify-end gap-2 pt-3">
                <button
                  type="button"
                  onClick={() => setModalDespesaFixa(false)}
                  className="rounded-lg border border-slate-200 px-4 py-2 font-medium"
                >
                  Cancel·lar
                </button>
                <button
                  type="submit"
                  disabled={savingDespesaFixa}
                  className="rounded-lg bg-primary px-4 py-2 font-semibold text-white hover:opacity-90 disabled:opacity-50"
                >
                  {savingDespesaFixa ? "Desant..." : editingDespesaFixa ? "Desar canvis" : "Enregistrar despesa"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL DECLARACIÓ RESPONSABLE DEL SIF (Art. 15 Ordre HAC/1177/2024) */}
      {modalDeclaracioSif && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4">
          <div className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-xl space-y-4 text-xs">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                <ShieldCheck className="h-5 w-5 text-primary" />
                Declaració Responsable del Sistema Informàtic de Facturació
              </h3>
              <button onClick={() => setModalDeclaracioSif(false)}>
                <X className="h-5 w-5 text-slate-400" />
              </button>
            </div>
            <div className="space-y-2 text-slate-700">
              <p>
                <strong>Normativa aplicable:</strong>{" "}
                {declaracioSif?.normativa || "Reial Decret 1007/2023 i Ordre Ministerial HAC/1177/2024"}
              </p>
              <p>
                <strong>Nom del Sistema Informàtic (SIF):</strong>{" "}
                <span className="font-mono">{declaracioSif?.nom_sistema || "SEVALOR_SUITE_SIF"}</span> (ID:{" "}
                <span className="font-mono">{declaracioSif?.id_sistema || "SV"}</span> · Versió:{" "}
                <span className="font-mono">{declaracioSif?.versio || "2.5.0"}</span>)
              </p>
              <p>
                <strong>Productor del Sistema:</strong>{" "}
                {declaracioSif?.productor_nom || "Sevalor Technologies SL"} (NIF:{" "}
                <span className="font-mono">{declaracioSif?.productor_nif || "B00000000"}</span>)
              </p>
              <p>
                <strong>Modalitat d&apos;operació:</strong>{" "}
                <span className="rounded bg-emerald-100 px-2 py-0.5 font-mono font-bold text-emerald-800">
                  {declaracioSif?.modalitat || "VERI*FACTU"}
                </span>{" "}
                · Entorn: <span className="font-mono font-bold">{declaracioSif?.entorn_actiu || "PREPRODUCCIO"}</span>
              </p>
              <p>
                <strong>Algoritme d&apos;encadenament i empremta:</strong>{" "}
                {declaracioSif?.algoritme_empremta || "SHA-256 (TipoHuella 01 - Art. 13 Ordre HAC/1177/2024)"}
              </p>
              <p>
                <strong>Especificació del codi QR tributari:</strong>{" "}
                {declaracioSif?.especificacio_qr || "ISO/IEC 18004 Nivell M (35x35 mm - Art. 20-21 Ordre HAC/1177/2024)"}
              </p>
            </div>
            <div className="flex justify-end pt-2 border-t border-slate-100">
              <button
                type="button"
                onClick={() => setModalDeclaracioSif(false)}
                className="rounded-lg bg-primary px-4 py-2 font-semibold text-white"
              >
                Tancar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function GestioComptabilitatPage() {
  return (
    <Suspense
      fallback={
        <div className="p-8 text-center text-xs font-mono text-slate-500 animate-pulse">
          Carregant Suite de Control Financer i Prefacturació...
        </div>
      }
    >
      <ComptabilitatContent />
    </Suspense>
  );
}
