"use client";

import React, { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
  Package,
  Search,
  Plus,
  Sparkles,
  Truck,
  Wrench,
  AlertTriangle,
  Building,
  RefreshCw,
  X,
  CheckCircle2,
  Layers,
  Trash2,
  FileText,
  Edit3,
  ShoppingCart,
  SlidersHorizontal,
  Barcode,
  Mail,
  Send,
  ExternalLink,
  ClipboardCheck,
} from "lucide-react";
import { apiFetch, getAuthToken, getApiBaseUrl, extractTenantId } from "@/lib/api";
import { useGestio } from "@/lib/gestio-context";
import { BarcodeScanner } from "@/components/operari/BarcodeScanner";

const UNITATS_MESURA_CANONIQUES = [
  { value: "UNITAT", label: "Unitat (un)" },
  { value: "METRES_LINEALS", label: "Metres Lineals (m)" },
  { value: "KG", label: "Quilograms (kg)" },
  { value: "LITRES", label: "Litres (l)" },
  { value: "M2", label: "Metres Quadrats (m²)" },
  { value: "M3", label: "Metres Cúbics (m³)" },
  { value: "CAIXA", label: "Caixes" },
] as const;

function normalitzarUnitatMesura(unitat?: string | null): string {
  const u = (unitat || "UNITAT").toUpperCase();
  if (u === "METRE") return "METRES_LINEALS";
  if (u === "QUILO") return "KG";
  if (u === "LITRE") return "LITRES";
  return u;
}

interface Article {
  id: string;
  referencia_inventari: string;
  codi_barres?: string | null;
  nom: string;
  unitat_mesura: string;
  es_material_continu?: boolean;
  familia: string;
  estoc_optim: number;
  estoc_minim: number;
  preu_cost?: number | null;
  descompte_proveidor?: number | null;
  marge_guanys?: number | null;
  preu_venda: number;
  proveidor_id?: string | null;
  proveidor_nom?: string | null;
  actiu?: boolean;
  es_lot_caducable?: boolean;
  estoc_fisic?: number;
  estoc_reservat?: number;
  estoc_disponible?: number;
  estoc_real?: number;
  pmp_actual?: number | null;
  estoc_slot_residus?: number;
}

interface RecompraAlertaItem {
  id: string;
  tipus_alerta: string;
  article_id?: string | null;
  article_nom?: string | null;
  article_ref?: string | null;
  article_codi_barres?: string | null;
  proveidor_id?: string | null;
  proveidor_nom?: string | null;
  proveidor_email?: string | null;
  esborrany_email_assumpte?: string | null;
  esborrany_email_cos?: string | null;
  mailto_url?: string | null;
  missatge: string;
  estat: string;
  enviat_automaticament: boolean;
  created_at?: string | null;
  dades_comanda_proposta: {
    unitat_mesura?: string;
    estoc_disponible?: number;
    estoc_minim?: number;
    estoc_optim?: number;
    quantitat_proposada?: number;
    quantitat_aprovada?: number;
    proveidor_email?: string | null;
    esborrany_email_assumpte?: string | null;
    esborrany_email_cos?: string | null;
    mailto_url?: string | null;
    preu_unitari_estimat?: number | null;
    import_estimat?: number | null;
    estat_hitl?: string;
  };
}

interface RecompraGrupProveidor {
  grup_key: string;
  proveidor_id?: string | null;
  proveidor_nom: string;
  proveidor_email?: string | null;
  alerta_ids: string[];
  total_articles: number;
  items: Array<{
    alerta_id: string;
    article_id?: string | null;
    referencia?: string | null;
    codi_barres?: string | null;
    nom?: string | null;
    unitat_mesura: string;
    estoc_disponible: number;
    estoc_minim: number;
    quantitat_proposada: number;
    preu_unitari_estimat?: number | null;
    import_estimat?: number | null;
  }>;
  import_total_estimat?: number | null;
  esborrany_email_assumpte: string;
  esborrany_email_cos: string;
  mailto_url?: string | null;
}

interface AlbaraPendentItem {
  id: string;
  proveidor_id: string;
  proveidor_nom?: string | null;
  proveidor_nif?: string | null;
  numero_albara: string;
  data_albara?: string | null;
  estat: string;
  ja_te_stock_aplicat?: boolean;
  linies: Array<{
    referencia: string;
    nom: string;
    quantitat: number;
    preu?: number | null;
    descompte_percent?: number;
    tipus: string;
  }>;
  created_at?: string | null;
}

interface SuggerimentMerma {
  article_id: string;
  es_material_continu: boolean;
  merma_suggerida_pct: number;
  total_mermes_registrades: number;
  quantitat_total_mermada: number;
  recomanacio: string;
}

interface MermaItem {
  id: string;
  article_id: string;
  article_nom: string;
  article_ref: string;
  magatzem_id: string;
  ordre_treball_id?: string | null;
  ordre_treball_codi?: string | null;
  quantitat: number;
  pmp_aplicat: number;
  cost_total: number;
  motiu: string;
  subcompte_comptable: string;
  transferit_slot_residus: boolean;
  notes?: string | null;
  created_at?: string | null;
}

interface MagatzemItem {
  id: string;
  nom: string;
  tipus: "NAU_CENTRAL" | "FURGONETA";
  vehicle_id?: string | null;
  vehicle_matricula?: string | null;
  actiu: boolean;
}

function MagatzemContent() {
  const { rolActiu } = useGestio();
  const esEnginyer = (rolActiu || "").toUpperCase() === "ENGINYER";
  const searchParams = useSearchParams();
  const filtreParam = (searchParams.get("filtre") || "").toLowerCase();
  const tabParam = (searchParams.get("tab") || "").toUpperCase();
  const [nomesTrencamentEstoc, setNomesTrencamentEstoc] = useState(
    filtreParam === "trencament" || filtreParam === "critics"
  );
  const [mostrarLectorBarres, setMostrarLectorBarres] = useState(false);
  const [vertical, setVertical] = useState<string>("SEVALOR");
  const [customFamilies, setCustomFamilies] = useState<string[]>([]);
  const [articles, setArticles] = useState<Article[]>([]);
  const [eines, setEines] = useState<any[]>([]);
  const [proveidors, setProveidors] = useState<any[]>([]);
  const [magatzems, setMagatzems] = useState<MagatzemItem[]>([]);
  const [selectedMagatzemId, setSelectedMagatzemId] = useState<string>("TOTS");
  const [modalTraspas, setModalTraspas] = useState(false);
  const [traspasArticleId, setTraspasArticleId] = useState<string>("");
  const [traspasOrigenId, setTraspasOrigenId] = useState<string>("");
  const [traspasDestiId, setTraspasDestiId] = useState<string>("");
  const [traspasQuantitat, setTraspasQuantitat] = useState<number>(1);
  const [traspasant, setTraspasant] = useState(false);
  const [checkoutTargetTipus, setCheckoutTargetTipus] = useState<"OPERARI" | "VEHICLE">("OPERARI");
  const [selectedVehicleMagatzemId, setSelectedVehicleMagatzemId] = useState("");
  const [activeTab, setActiveTab] = useState<"MATERIALS" | "EINES" | "MERMES" | "RECOMPRA_STOCK" | "ALBARANS">(
    tabParam === "RECOMPRA_STOCK" || tabParam === "ALBARANS" || tabParam === "MERMES" || tabParam === "EINES"
      ? tabParam
      : "MATERIALS"
  );
  const [mermes, setMermes] = useState<MermaItem[]>([]);
  const [recompraAlertes, setRecompraAlertes] = useState<RecompraAlertaItem[]>([]);
  const [recompraGrups, setRecompraGrups] = useState<RecompraGrupProveidor[]>([]);
  const [albaransPendents, setAlbaransPendents] = useState<AlbaraPendentItem[]>([]);
  const [consolidantAlbaraId, setConsolidantAlbaraId] = useState<string | null>(null);
  const [suggerimentMerma, setSuggerimentMerma] = useState<SuggerimentMerma | null>(null);
  const [modalEmailRecompra, setModalEmailRecompra] = useState<{
    alertaIds: string[];
    titol: string;
    proveidorId: string;
    destinatariEmail: string;
    assumpte: string;
    cosMissatge: string;
    mailtoUrl: string;
    quantitats: Record<string, number>;
  } | null>(null);
  const [enviantEmail, setEnviantEmail] = useState(false);

  useEffect(() => {
    setNomesTrencamentEstoc(filtreParam === "trencament" || filtreParam === "critics");
    if (tabParam === "RECOMPRA_STOCK" || tabParam === "ALBARANS" || tabParam === "MERMES" || tabParam === "EINES" || tabParam === "MATERIALS") {
      setActiveTab(tabParam);
    }
  }, [filtreParam, tabParam]);
  const [escanejantRecompra, setEscanejantRecompra] = useState(false);
  const [resolentAlertaId, setResolentAlertaId] = useState<string | null>(null);
  const [quantitatsRecompraEdit, setQuantitatsRecompraEdit] = useState<Record<string, number>>({});
  const [ordresTreball, setOrdresTreball] = useState<Array<{ id: string; codi: string; titol: string }>>([]);
  const [mermaArticleId, setMermaArticleId] = useState<string>("");
  const [mermaMagatzemId, setMermaMagatzemId] = useState<string>("");
  const [mermaQuantitat, setMermaQuantitat] = useState<string>("1");
  const [mermaMotiu, setMermaMotiu] = useState<string>("OBRA_TALL_INUTIL");
  const [mermaOtId, setMermaOtId] = useState<string>("");
  const [mermaNotes, setMermaNotes] = useState<string>("");
  const [registrantMerma, setRegistrantMerma] = useState<boolean>(false);
  const [modalAjustEstoc, setModalAjustEstoc] = useState(false);
  const [ajustArticle, setAjustArticle] = useState<Article | null>(null);
  const [ajustMagatzemId, setAjustMagatzemId] = useState<string>("");
  const [ajustTipus, setAjustTipus] = useState<"ENTRADA" | "SORTIDA" | "RESERVA">("ENTRADA");
  const [ajustQuantitat, setAjustQuantitat] = useState<number>(1);
  const [ajustUbicacio, setAjustUbicacio] = useState<string>("");
  const [ajustNotes, setAjustNotes] = useState<string>("");
  const [ajustantEstoc, setAjustantEstoc] = useState<boolean>(false);
  const [modalEditarEina, setModalEditarEina] = useState(false);
  const [einaEditant, setEinaEditant] = useState<any>(null);
  const [guardantEina, setGuardantEina] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filtreCerca, setFiltreCerca] = useState("");
  const [filtreFamilia, setFiltreFamilia] = useState<string>("TOTS");
  const [modalNouArticle, setModalNouArticle] = useState(false);
  const [guardant, setGuardant] = useState(false);
  const [modalOcr, setModalOcr] = useState(false);
  const [modalEditarArticle, setModalEditarArticle] = useState(false);
  const [articleEditant, setArticleEditant] = useState<Article | null>(null);
  const [operaris, setOperaris] = useState<any[]>([]);
  const [modalCheckout, setModalCheckout] = useState(false);
  const [einaCheckout, setEinaCheckout] = useState<any>(null);
  const [selectedOperari, setSelectedOperari] = useState("");
  const [fitxerOcr, setFitxerOcr] = useState<File | null>(null);
  const [processantOcr, setProcessantOcr] = useState(false);
  const [resultatOcr, setResultatOcr] = useState<any>(null);
  const [hasCopilotIa, setHasCopilotIa] = useState<boolean>(true);
  const [creantNovaFamiliaNou, setCreantNovaFamiliaNou] = useState<boolean>(false);
  const [novaFamiliaTextNou, setNovaFamiliaTextNou] = useState<string>("");
  const [creantNovaFamiliaEdit, setCreantNovaFamiliaEdit] = useState<boolean>(false);
  const [novaFamiliaTextEdit, setNovaFamiliaTextEdit] = useState<string>("");


  // Formulari nou article
  const [nouArticle, setNouArticle] = useState({
    tipus_creacio: "MATERIAL", // MATERIAL o EINA
    referencia_inventari: "",
    codi_barres: "",
    nom: "",
    numero_serie: "",
    model_eina: "",
    data_fi_garantia: "",
    observacions: "",
    incidencies: "",
    unitat_mesura: "UNITAT",
    familia: "TUBERIA",
    estoc_inicial: 0,
    magatzem_id: "",
    estoc_optim: 10,
    estoc_minim: 2,
    preu_cost: 0,
    descompte_proveidor: 0,
    marge_guanys: 0,
    preu_venda: 0,
    es_lot_caducable: false,
    es_material_continu: false,
    proveidor_id: "",
  });

  // Efecte per autocalcular el preu de venda
  useEffect(() => {
    if (nouArticle.tipus_creacio === "MATERIAL" && !esEnginyer) {
      const costReal = nouArticle.preu_cost * (1 - (nouArticle.descompte_proveidor / 100));
      const preuVendaCalculat = costReal * (1 + (nouArticle.marge_guanys / 100));
      setNouArticle(prev => ({ ...prev, preu_venda: parseFloat(preuVendaCalculat.toFixed(2)) }));
    }
  }, [nouArticle.preu_cost, nouArticle.descompte_proveidor, nouArticle.marge_guanys, nouArticle.tipus_creacio, esEnginyer]);

  const carregarArticles = async (magId?: string) => {
    setLoading(true);
    setError(null);
    const targetMagId = magId !== undefined ? magId : selectedMagatzemId;
    const articlesQuery = targetMagId && targetMagId !== "TOTS"
      ? `/gestio/magatzem/articles?limit=200&magatzem_id=${targetMagId}`
      : "/gestio/magatzem/articles?limit=200";
    const einesQuery = targetMagId && targetMagId !== "TOTS"
      ? `/gestio/magatzem/eines?magatzem_id=${targetMagId}`
      : "/gestio/magatzem/eines";

    try {
      const [articlesData, einesData, operarisData, configData, proveidorsData, magatzemsData, mermesData, otsData, recompraData, grupsData, albaransData] = await Promise.all([
        apiFetch<Article[]>(articlesQuery).catch(() => []),
        apiFetch<any[]>(einesQuery).catch(() => []),
        apiFetch<any[]>("/gestio/operaris").catch(() => []),
        apiFetch<any>("/gestio/configuracio/empresa").catch(() => null),
        apiFetch<any[]>("/gestio/proveidors").catch(() => []),
        apiFetch<MagatzemItem[]>("/gestio/magatzem/magatzems").catch(() => []),
        apiFetch<MermaItem[]>("/gestio/magatzem/mermes").catch(() => []),
        apiFetch<Array<{ id: string; codi: string; titol: string }>>("/gestio/feines").catch(() => []),
        apiFetch<RecompraAlertaItem[]>("/gestio/magatzem/recompra").catch(() => []),
        apiFetch<RecompraGrupProveidor[]>("/gestio/magatzem/recompra/agrupades-proveidor").catch(() => []),
        apiFetch<AlbaraPendentItem[]>("/gestio/magatzem/albarans").catch(() => [])
      ]);
      setArticles(articlesData || []);
      setEines(einesData || []);
      setOperaris(operarisData || []);
      setProveidors(proveidorsData || []);
      setMermes(mermesData || []);
      setOrdresTreball(otsData || []);
      setRecompraAlertes(recompraData || []);
      setRecompraGrups(grupsData || []);
      setAlbaransPendents(albaransData || []);
      if (Array.isArray(magatzemsData) && magatzemsData.length > 0) {
        setMagatzems(magatzemsData);
        const nauCentral = magatzemsData.find(m => m.tipus === "NAU_CENTRAL") || magatzemsData[0];
        if (nauCentral) {
          setNouArticle(prev => prev.magatzem_id ? prev : { ...prev, magatzem_id: nauCentral.id });
        }
      }
      
      if (configData) {
        if (configData.feature_copilot_ia !== undefined) {
          setHasCopilotIa(Boolean(configData.feature_copilot_ia));
        }
        if (configData.vertical) setVertical(configData.vertical);
        if (configData.magatzem_families_default) {
          setCustomFamilies(configData.magatzem_families_default.split(',').map((s: string) => s.trim()).filter(Boolean));
        } else {
          setCustomFamilies([]);
        }
      }
    } catch (err: any) {
      setError(err.message || "Error al carregar l'inventari");
      setArticles([]);
    } finally {
      setLoading(false);
    }
  };

  const handleCanviMagatzem = (nouMagId: string) => {
    setSelectedMagatzemId(nouMagId);
    carregarArticles(nouMagId);
  };

  const handleRegistrarMerma = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!mermaArticleId || !mermaMagatzemId) {
      setError("Cal seleccionar article i magatzem per registrar la merma");
      return;
    }
    setRegistrantMerma(true);
    setError(null);
    try {
      await apiFetch("/gestio/magatzem/mermes", {
        method: "POST",
        body: JSON.stringify({
          article_id: mermaArticleId,
          magatzem_id: mermaMagatzemId,
          quantitat_mermada: Number(mermaQuantitat || 0),
          motiu: mermaMotiu,
          ordre_treball_id: mermaOtId || null,
          notes: mermaNotes || null,
        }),
      });
      setMermaQuantitat("1");
      setMermaNotes("");
      await carregarArticles();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error registrant merma d'inventari");
    } finally {
      setRegistrantMerma(false);
    }
  };

  const handleExecutarTraspas = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!traspasArticleId || !traspasOrigenId || !traspasDestiId) {
      setError("Cal seleccionar article, magatzem d'origen i magatzem de destí");
      return;
    }
    if (traspasOrigenId === traspasDestiId) {
      setError("L'origen i el destí del traspàs han de ser diferents");
      return;
    }
    if (traspasQuantitat <= 0) {
      setError("La quantitat a traspassar ha de ser superior a 0");
      return;
    }

    setTraspasant(true);
    setError(null);
    try {
      await apiFetch("/gestio/magatzem/traspas-furgoneta", {
        method: "POST",
        body: JSON.stringify({
          article_id: traspasArticleId,
          origen_magatzem_id: traspasOrigenId,
          desti_magatzem_id: traspasDestiId,
          quantitat: Number(traspasQuantitat),
        }),
      });
      setModalTraspas(false);
      await carregarArticles();
    } catch (err: any) {
      setError(err.message || "Error en realitzar el traspàs d'estoc");
    } finally {
      setTraspasant(false);
    }
  };

  useEffect(() => {
    carregarArticles();
  }, []);

  useEffect(() => {
    if (!mermaArticleId) {
      setSuggerimentMerma(null);
      return;
    }
    let cancelat = false;
    apiFetch<SuggerimentMerma>(`/gestio/magatzem/articles/${mermaArticleId}/suggeriment-merma`)
      .then((res) => {
        if (!cancelat) setSuggerimentMerma(res);
      })
      .catch(() => {
        if (!cancelat) setSuggerimentMerma(null);
      });
    return () => {
      cancelat = true;
    };
  }, [mermaArticleId]);

  
  const handlePujarOcr = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!fitxerOcr) return;
    
    setProcessantOcr(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append("fitxer", fitxerOcr);
      
      const token = getAuthToken();
      const urlBase = getApiBaseUrl();
      const tenantId = extractTenantId();
      
      const headers: any = { "Authorization": `Bearer ${token}` };
      if (tenantId) headers["X-Empresa-ID"] = tenantId;
      
      const res = await fetch(`${urlBase}/gestio/magatzem/albara/ocr`, {
        method: "POST",
        headers,
        body: formData
      });
      
      if (!res.ok) throw new Error("Error processant l'albarà");
      const data = await res.json();
      const ocrNormalitzat = {
        proveidor: data.proveidor || {
          nif: data.ocr_data?.proveidor_nif || "",
          nom: data.ocr_data?.proveidor_nom || "Proveïdor per revisar",
        },
        numero_document: data.numero_document || data.ocr_data?.numero_albara || "",
        tipus_document: data.tipus_document || "ALBARA",
        data_document: data.data_document || data.ocr_data?.data_albara || new Date().toISOString().split("T")[0],
        linies: data.linies || data.ocr_data?.linies || [],
        numero_albarans_vinculats: data.numero_albarans_vinculats || [],
      };
      setResultatOcr(ocrNormalitzat);
    } catch (err: any) {
      setError(err.message || "Error al processar l'albarà OCR");
    } finally {
      setProcessantOcr(false);
    }
  };

  const handleConfirmarOcr = async () => {
    if (!resultatOcr) return;
    setProcessantOcr(true);
    setError(null);
    try {
      const provNom = resultatOcr.proveidor?.nom || (typeof resultatOcr.proveidor === "string" ? resultatOcr.proveidor : "Proveïdor General");
      const provNif = resultatOcr.proveidor?.nif || "B00000000";
      await apiFetch("/gestio/magatzem/albara/confirmar", {
        method: "POST",
        body: JSON.stringify({
          ...(resultatOcr.albara_id ? { albara_id: resultatOcr.albara_id } : {}),
          proveidor: {
            nif: provNif,
            nom: provNom,
            adreca: resultatOcr.proveidor?.adreca || "",
            telefon: resultatOcr.proveidor?.telefon || "",
            email: resultatOcr.proveidor?.email || "",
          },
          numero_document: resultatOcr.numero_document || `ALB-${Date.now()}`,
          tipus_document: resultatOcr.tipus_document || "ALBARA",
          data_document: resultatOcr.data_document || new Date().toISOString().split("T")[0],
          numero_albarans_vinculats: resultatOcr.numero_albarans_vinculats || [],
          linies: (resultatOcr.linies || []).map((l: any) => ({
            referencia: l.referencia,
            nom: l.nom,
            quantitat: Number(l.quantitat) || 1,
            preu: Number(l.preu) || 0,
            descompte_percent: Number(l.descompte_percent) || 0,
            tipus: l.tipus || "MATERIAL",
          })),
        }),
      });
      setModalOcr(false);
      setResultatOcr(null);
      setFitxerOcr(null);
      await carregarArticles();
    } catch (err: any) {
      setError(err.message || "Error al confirmar l'albarà");
    } finally {
      setProcessantOcr(false);
    }
  };

  const handleRevisarAlbaraPendent = (alb: AlbaraPendentItem) => {
    setError(null);
    setResultatOcr({
      albara_id: alb.id,
      proveidor: {
        nif: alb.proveidor_nif || "B00000000",
        nom: alb.proveidor_nom || "Proveïdor per revisar",
      },
      numero_document: alb.numero_albara,
      tipus_document: "ALBARA",
      data_document: alb.data_albara || new Date().toISOString().split("T")[0],
      linies: (alb.linies || []).map((l) => ({
        referencia: l.referencia || "",
        nom: l.nom || "",
        quantitat: Number(l.quantitat) || 1,
        preu: Number(l.preu || 0),
        descompte_percent: Number(l.descompte_percent || 0),
        tipus: l.tipus || "MATERIAL",
      })),
      numero_albarans_vinculats: [],
    });
    setModalOcr(true);
  };

  const handleDesarAlbaraPendent = async () => {
    if (!resultatOcr) return;
    setProcessantOcr(true);
    setError(null);
    try {
      const provNom = resultatOcr.proveidor?.nom || (typeof resultatOcr.proveidor === "string" ? resultatOcr.proveidor : "Proveïdor General");
      const provNif = resultatOcr.proveidor?.nif || "B00000000";
      await apiFetch("/gestio/magatzem/albarans/desar-pendent", {
        method: "POST",
        body: JSON.stringify({
          proveidor: {
            nif: provNif,
            nom: provNom,
            adreca: resultatOcr.proveidor?.adreca || "",
            telefon: resultatOcr.proveidor?.telefon || "",
            email: resultatOcr.proveidor?.email || "",
          },
          numero_document: resultatOcr.numero_document || `ALB-${Date.now()}`,
          tipus_document: resultatOcr.tipus_document || "ALBARA",
          data_document: resultatOcr.data_document || new Date().toISOString().split("T")[0],
          numero_albarans_vinculats: resultatOcr.numero_albarans_vinculats || [],
          linies: (resultatOcr.linies || []).map((l: any) => ({
            referencia: l.referencia,
            nom: l.nom,
            quantitat: Number(l.quantitat) || 1,
            preu: Number(l.preu) || 0,
            descompte_percent: Number(l.descompte_percent) || 0,
            tipus: l.tipus || "MATERIAL",
          })),
        }),
      });
      setModalOcr(false);
      setResultatOcr(null);
      setFitxerOcr(null);
      setActiveTab("ALBARANS");
      await carregarArticles();
    } catch (err: any) {
      setError(err.message || "Error al desar l'albarà pendent d'auditoria");
    } finally {
      setProcessantOcr(false);
    }
  };

  const handleConsolidarAlbara = async (albaraId: string) => {
    setConsolidantAlbaraId(albaraId);
    setError(null);
    try {
      await apiFetch(`/gestio/magatzem/albarans/${albaraId}/consolidar`, {
        method: "POST",
      });
      setAlbaransPendents((prev) =>
        prev.map((a) => (a.id === albaraId ? { ...a, estat: "CONSOLIDAT" } : a))
      );
      await carregarArticles();
    } catch (err: any) {
      setError(err.message || "Error consolidant l'albarà a estoc");
    } finally {
      setConsolidantAlbaraId(null);
    }
  };


  const handleDesarEdicio = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!articleEditant) return;
    setGuardant(true);
    setError(null);
    try {
      await apiFetch(`/gestio/magatzem/articles/${articleEditant.id}`, {
        method: "PUT",
        body: JSON.stringify({
          referencia_inventari: articleEditant.referencia_inventari,
          codi_barres: articleEditant.codi_barres?.trim() || null,
          nom: articleEditant.nom,
          unitat_mesura: normalitzarUnitatMesura(articleEditant.unitat_mesura),
          familia: articleEditant.familia,
          estoc_optim: Number(articleEditant.estoc_optim),
          estoc_minim: Number(articleEditant.estoc_minim),
          preu_cost: esEnginyer ? 0 : Number(articleEditant.preu_cost ?? 0),
          descompte_proveidor: esEnginyer ? 0 : Number(articleEditant.descompte_proveidor ?? 0),
          marge_guanys: esEnginyer ? 0 : Number(articleEditant.marge_guanys ?? 0),
          preu_venda: Number(articleEditant.preu_venda),
          es_lot_caducable: articleEditant.es_lot_caducable || false,
          es_material_continu: articleEditant.es_material_continu || false,
          proveidor_id: articleEditant.proveidor_id || null,
        }),
      });
      setModalEditarArticle(false);
      setArticleEditant(null);
      await carregarArticles();
    } catch (err: any) {
      setError(err.message || "Error al modificar l'article");
    } finally {
      setGuardant(false);
    }
  };

  const obrirFitxa = (art: Article) => {
    setArticleEditant({
      ...art,
      unitat_mesura: normalitzarUnitatMesura(art.unitat_mesura),
    });
    setModalEditarArticle(true);
  };

  const obrirAjustEstoc = (art: Article) => {
    setAjustArticle(art);
    const nauCentral = magatzems.find((m) => m.tipus === "NAU_CENTRAL") || magatzems[0];
    setAjustMagatzemId(
      selectedMagatzemId !== "TOTS" ? selectedMagatzemId : (nauCentral?.id || "")
    );
    setAjustTipus("ENTRADA");
    setAjustQuantitat(1);
    setAjustUbicacio("");
    setAjustNotes("");
    setModalAjustEstoc(true);
  };

  const handleExecutarAjustEstoc = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!ajustArticle || !ajustMagatzemId) {
      setError("Cal seleccionar un magatzem per ajustar l'estoc.");
      return;
    }
    if (ajustQuantitat <= 0) {
      setError("La quantitat de moviment ha de ser superior a zero.");
      return;
    }
    setAjustantEstoc(true);
    setError(null);
    try {
      await apiFetch(`/gestio/magatzem/magatzems/${ajustMagatzemId}/moviment`, {
        method: "POST",
        body: JSON.stringify({
          article_id: ajustArticle.id,
          tipus: ajustTipus,
          quantitat: Number(ajustQuantitat),
          ubicacio_passadis: ajustUbicacio.trim() || null,
          notes: ajustNotes.trim() || null,
        }),
      });
      setModalAjustEstoc(false);
      setAjustArticle(null);
      await carregarArticles();
    } catch (err: any) {
      setError(err.message || "Error en registrar el moviment d'estoc");
    } finally {
      setAjustantEstoc(false);
    }
  };

  const obrirEditarEina = (eina: any) => {
    setEinaEditant({
      ...eina,
      data_fi_garantia: eina.data_fi_garantia ? String(eina.data_fi_garantia).slice(0, 10) : "",
    });
    setModalEditarEina(true);
  };

  const handleDesarEina = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!einaEditant) return;
    setGuardantEina(true);
    setError(null);
    try {
      await apiFetch(`/gestio/magatzem/eines/${einaEditant.id}`, {
        method: "PUT",
        body: JSON.stringify({
          referencia_fabricant: einaEditant.referencia_fabricant || null,
          nom: einaEditant.nom,
          model: einaEditant.model || null,
          numero_serie: einaEditant.numero_serie,
          data_fi_garantia: einaEditant.data_fi_garantia || null,
          observacions: einaEditant.observacions || null,
          incidencies: einaEditant.incidencies || null,
        }),
      });
      setModalEditarEina(false);
      setEinaEditant(null);
      await carregarArticles();
    } catch (err: any) {
      setError(err.message || "Error en actualitzar la fitxa de l'eina");
    } finally {
      setGuardantEina(false);
    }
  };

  const handleEscanejarRecompra = async () => {
    setEscanejantRecompra(true);
    setError(null);
    try {
      await apiFetch("/gestio/magatzem/recompra/escanejar", { method: "POST" });
      await carregarArticles();
    } catch (err: any) {
      setError(err.message || "Error escanejant trencaments d'estoc");
    } finally {
      setEscanejantRecompra(false);
    }
  };

  const handleAccioRecompra = async (alerta: RecompraAlertaItem, accio: "APROVAR" | "DESCARTAR") => {
    setResolentAlertaId(alerta.id);
    setError(null);
    try {
      const qtyOverride = quantitatsRecompraEdit[alerta.id];
      await apiFetch(`/gestio/magatzem/recompra/${alerta.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          accio,
          quantitat_aprovada:
            accio === "APROVAR" && qtyOverride && qtyOverride > 0
              ? Number(qtyOverride)
              : undefined,
        }),
      });
      await carregarArticles();
    } catch (err: any) {
      setError(err.message || "Error resolent la proposta HITL de recompra");
    } finally {
      setResolentAlertaId(null);
    }
  };

  const obrirModalEmailAlerta = (alerta: RecompraAlertaItem) => {
    const prop = alerta.dades_comanda_proposta || {};
    const qty = Number(quantitatsRecompraEdit[alerta.id] || prop.quantitat_aprovada || prop.quantitat_proposada || 1);
    const refTxt = alerta.article_ref || "N/A";
    const unitatTxt = prop.unitat_mesura || "UNITAT";
    setModalEmailRecompra({
      alertaIds: [alerta.id],
      titol: `Comanda de recompra · ${alerta.article_nom || refTxt}`,
      proveidorId: alerta.proveidor_id || "",
      destinatariEmail: alerta.proveidor_email || prop.proveidor_email || "",
      assumpte:
        alerta.esborrany_email_assumpte ||
        prop.esborrany_email_assumpte ||
        `Comanda de reposició: ${alerta.article_nom || ""} (${refTxt})`,
      cosMissatge:
        alerta.esborrany_email_cos ||
        prop.esborrany_email_cos ||
        `Bon dia,\n\nSol·licitem pressupost i termini d'entrega per a:\n- ${refTxt} | ${alerta.article_nom || ""}: ${qty} ${unitatTxt}\n\nGràcies.`,
      mailtoUrl: alerta.mailto_url || prop.mailto_url || "",
      quantitats: { [alerta.id]: qty },
    });
  };

  const obrirModalEmailGrup = (grup: RecompraGrupProveidor) => {
    const quantitatsInicials: Record<string, number> = {};
    for (const item of grup.items) {
      const override = quantitatsRecompraEdit[item.alerta_id];
      quantitatsInicials[item.alerta_id] = Number(override || item.quantitat_proposada || 1);
    }
    setModalEmailRecompra({
      alertaIds: grup.alerta_ids,
      titol: `Comanda agrupada (${grup.total_articles} articles) · ${grup.proveidor_nom}`,
      proveidorId: grup.proveidor_id || "",
      destinatariEmail: grup.proveidor_email || "",
      assumpte: grup.esborrany_email_assumpte,
      cosMissatge: grup.esborrany_email_cos,
      mailtoUrl: grup.mailto_url || "",
      quantitats: quantitatsInicials,
    });
  };

  const obrirModalEmailArticle = async (art: Article) => {
    const existent = recompraAlertes.find(
      (a) => a.article_id === art.id && (a.estat === "ACTIVA" || a.estat === "PENDENT")
    );
    if (existent) {
      obrirModalEmailAlerta(existent);
      return;
    }
    setError(null);
    try {
      await apiFetch("/gestio/magatzem/recompra/escanejar", { method: "POST" });
      const [freshAlertes, freshGrups] = await Promise.all([
        apiFetch<RecompraAlertaItem[]>("/gestio/magatzem/recompra").catch(() => []),
        apiFetch<RecompraGrupProveidor[]>("/gestio/magatzem/recompra/agrupades-proveidor").catch(() => []),
      ]);
      setRecompraAlertes(freshAlertes || []);
      setRecompraGrups(freshGrups || []);
      const trobada = (freshAlertes || []).find(
        (a) => a.article_id === art.id && (a.estat === "ACTIVA" || a.estat === "PENDENT")
      );
      if (trobada) {
        obrirModalEmailAlerta(trobada);
      } else {
        setError("L'article no compleix els requisits de trencament d'estoc per generar alerta.");
      }
    } catch (err: any) {
      setError(err.message || "Error preparant l'esborrany d'email de recompra");
    }
  };

  const handleEnviarEmailRecompra = async (canal: "SMTP" | "MAILTO") => {
    if (!modalEmailRecompra) return;
    if (!modalEmailRecompra.destinatariEmail.trim()) {
      setError("Cal indicar una adreça d'email del proveïdor abans d'enviar.");
      return;
    }
    setEnviantEmail(true);
    setError(null);
    try {
      const resposta = await apiFetch<{
        estat: string;
        email_enviat: boolean;
        email_error?: string | null;
        mailto_url: string;
      }>("/gestio/magatzem/recompra/enviar-email", {
        method: "POST",
        body: JSON.stringify({
          alerta_ids: modalEmailRecompra.alertaIds,
          proveidor_id: modalEmailRecompra.proveidorId || null,
          destinatari_email: modalEmailRecompra.destinatariEmail.trim(),
          assumpte: modalEmailRecompra.assumpte,
          cos_missatge: modalEmailRecompra.cosMissatge,
          quantitats: modalEmailRecompra.quantitats,
          canal,
        }),
      });
      if (canal === "MAILTO" && resposta?.mailto_url) {
        window.open(resposta.mailto_url, "_blank", "noopener,noreferrer");
      } else if (canal === "SMTP" && !resposta?.email_enviat) {
        setError(
          resposta?.email_error
            ? `Esborrany aprovat, però SMTP no configurat o ha fallat (${resposta.email_error}). Pots usar l'opció mailto.`
            : "Esborrany aprovat, però no s'ha pogut enviar via SMTP. Utilitza el client de correu (mailto)."
        );
      }
      if (canal === "MAILTO" || resposta?.email_enviat) {
        setModalEmailRecompra(null);
      }
      await carregarArticles();
    } catch (err: any) {
      setError(err.message || "Error enviant la comanda de recompra");
    } finally {
      setEnviantEmail(false);
    }
  };

  const handleCheckout = async () => {
    if (!einaCheckout) return;
    if (checkoutTargetTipus === "OPERARI" && !selectedOperari) {
      alert("Cal seleccionar un operari");
      return;
    }
    if (checkoutTargetTipus === "VEHICLE" && !selectedVehicleMagatzemId) {
      alert("Cal seleccionar una furgoneta o vehicle");
      return;
    }

    try {
      const payload = checkoutTargetTipus === "OPERARI"
        ? { operari_id: selectedOperari }
        : { magatzem_id: selectedVehicleMagatzemId };

      await apiFetch(`/gestio/magatzem/eines/${einaCheckout.id}/checkout`, {
        method: "POST",
        body: JSON.stringify(payload)
      });
      setModalCheckout(false);
      setEinaCheckout(null);
      setSelectedOperari("");
      setSelectedVehicleMagatzemId("");
      await carregarArticles();
    } catch (err: any) {
      alert(err.message || "Error al fer checkout");
    }
  };

  const handleCheckin = async (einaId: string) => {
    if (!confirm("Confirmar retorn de l'eina a la base (DISPONIBLE)?")) return;
    try {
      await apiFetch(`/gestio/magatzem/eines/${einaId}/checkin`, {
        method: "POST"
      });
      await carregarArticles();
    } catch (err: any) {
      alert(err.message || "Error al fer check-in");
    }
  };
  const handleCrearArticle = async (e: React.FormEvent) => {
    e.preventDefault();
    setGuardant(true);
    setError(null);
    try {
      if (nouArticle.tipus_creacio === "EINA") {
        await apiFetch("/gestio/magatzem/eines", {
          method: "POST",
          body: JSON.stringify({
            referencia_fabricant: nouArticle.referencia_inventari,
            nom: nouArticle.nom,
            numero_serie: nouArticle.numero_serie,
            model: nouArticle.model_eina,
            data_fi_garantia: nouArticle.data_fi_garantia || null,
            observacions: nouArticle.observacions || null,
            incidencies: nouArticle.incidencies || null,
          }),
        });
      } else {
        await apiFetch<Article>("/gestio/magatzem/articles", {
          method: "POST",
          body: JSON.stringify({
            referencia_inventari: nouArticle.referencia_inventari,
            codi_barres: nouArticle.codi_barres.trim() || null,
            nom: nouArticle.nom,
            unitat_mesura: normalitzarUnitatMesura(nouArticle.unitat_mesura),
            familia: nouArticle.familia,
            es_lot_caducable: nouArticle.es_lot_caducable,
            es_material_continu: nouArticle.es_material_continu,
            estoc_inicial: Number(nouArticle.estoc_inicial || 0),
            magatzem_id: nouArticle.magatzem_id || null,
            estoc_optim: Number(nouArticle.estoc_optim),
            estoc_minim: Number(nouArticle.estoc_minim),
            preu_cost: esEnginyer ? 0 : Number(nouArticle.preu_cost),
            descompte_proveidor: esEnginyer ? 0 : Number(nouArticle.descompte_proveidor),
            marge_guanys: esEnginyer ? 0 : Number(nouArticle.marge_guanys),
            preu_venda: Number(nouArticle.preu_venda),
            proveidor_id: nouArticle.proveidor_id || null,
          }),
        });
      }
      setModalNouArticle(false);
      const nauCentral = magatzems.find((m) => m.tipus === "NAU_CENTRAL") || magatzems[0];
      setNouArticle({
        tipus_creacio: "MATERIAL",
        referencia_inventari: "",
        codi_barres: "",
        nom: "",
        numero_serie: "",
        model_eina: "",
        data_fi_garantia: "",
        observacions: "",
        incidencies: "",
        unitat_mesura: "UNITAT",
        familia: "TUBERIA",
        estoc_inicial: 0,
        magatzem_id: nauCentral?.id || "",
        estoc_optim: 10,
        estoc_minim: 2,
        preu_cost: 0,
        descompte_proveidor: 0,
        marge_guanys: 0,
        preu_venda: 0,
        es_lot_caducable: false,
        es_material_continu: false,
        proveidor_id: "",
      });
      await carregarArticles();
    } catch (err: any) {
      setError(err.message || "Error al crear l'article");
    } finally {
      setGuardant(false);
    }
  };

  const articlesEnTrencament = articles.filter(
    (a) => Number(a.estoc_minim ?? 0) > 0 && Number(a.estoc_disponible ?? a.estoc_real ?? 0) <= Number(a.estoc_minim ?? 0)
  );

  const articlesFiltrats = articles.filter((a) => {
    const q = filtreCerca.toLowerCase();
    const coincideixCerca =
      a.nom.toLowerCase().includes(q) ||
      a.referencia_inventari.toLowerCase().includes(q) ||
      (a.codi_barres || "").toLowerCase().includes(q);
    const coincideixFamilia = filtreFamilia === "TOTS" || a.familia === filtreFamilia;
    const estocDisp = Number(a.estoc_disponible ?? a.estoc_real ?? 0);
    const enTrencament = Number(a.estoc_minim ?? 0) > 0 && estocDisp <= Number(a.estoc_minim ?? 0);
    const coincideixTrencament = !nomesTrencamentEstoc || enTrencament;
    return coincideixCerca && coincideixFamilia && coincideixTrencament;
  });

  const totesLesFamilies = Array.from(
    new Set([
      ...customFamilies,
      ...articles.map((a) => a.familia).filter(Boolean),
      "TUBERIA",
      "VALVULERIA",
      "ACCESSORIS",
      "CABLES",
      "QUADRES",
      "ILLUMINACIO",
      "SANITARIS",
      "AIXETES",
      "CLIMATITZACIO",
      "EINES",
      "GENERAL",
    ])
  ).sort();


  const renderFamilyOptions = () => {
    if (customFamilies.length > 0) {
      return customFamilies.map(fam => <option key={fam} value={fam}>{fam}</option>);
    }
    if (vertical === "ELECTRICPRO") {
      return (
        <>
          <option value="CABLES">Cables i Conducció</option>
          <option value="QUADRES">Quadres i Proteccions</option>
          <option value="ILLUMINACIO">Il·luminació</option>
          <option value="MECANISMES">Mecanismes</option>
        </>
      );
    }
    if (vertical === "HYDROPRO") {
      return (
        <>
          <option value="TUBERIA">Canonades i Tubs</option>
          <option value="VALVULERIA">Valvuleria</option>
          <option value="SANITARIS">Sanitaris</option>
          <option value="AIXETES">Aixetes</option>
        </>
      );
    }
    if (vertical === "BUILDINGPRO") {
      return (
        <>
          <option value="CIMENT">Ciment i Àrids</option>
          <option value="FUSTA">Fusta i Fusteria</option>
          <option value="PINTURA">Pintures i Acabats</option>
          <option value="AILLAMENTS">Aïllaments</option>
        </>
      );
    }
    return (
      <>
        <option value="TUBERIA">Canonades i Tubs</option>
        <option value="VALVULERIA">Valvuleria</option>
        <option value="ACCESSORIS">Accessoris</option>
        <option value="CABLES">Cables i Elèctric</option>
      </>
    );
  };

  return (
    <div className="flex-1 flex flex-col h-[calc(100vh-3.5rem)] overflow-hidden bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 transition-colors">
      {/* Capçalera del Magatzem */}
      <div className="p-4 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between shadow-sm">
        <div>
          <h1 className="text-base font-bold text-slate-800 dark:text-slate-100 flex items-center gap-2">
            <Package className="w-5 h-5 text-emerald-600" />
            Magatzem Central & Inventari Industrial (Spec 004)
          </h1>
          <p className="text-xs text-slate-500">
            Control d'estoc, famílies de material i picking per a ordres de treball
          </p>
        </div>

        <div className="flex items-center gap-2">
          {/* Selector de Magatzem Mòbil vs Central (Spec 004 / Spec 01 / Spec 015) */}
          <div className="flex items-center gap-1.5 bg-slate-100 dark:bg-slate-800 p-1 rounded-xl border border-slate-200 dark:border-slate-700">
            <span className="text-[11px] font-bold text-slate-500 px-1.5 flex items-center gap-1">
              <Building className="w-3.5 h-3.5 text-emerald-600" />
              Magatzem:
            </span>
            <select
              value={selectedMagatzemId}
              onChange={(e) => handleCanviMagatzem(e.target.value)}
              className="bg-white dark:bg-slate-900 text-xs font-bold py-1 px-2 rounded-lg border border-slate-300 dark:border-slate-700 text-slate-800 dark:text-slate-100 focus:outline-none focus:ring-1 focus:ring-emerald-500"
            >
              <option value="TOTS">🏢 Tots els Magatzems (Consolidat)</option>
              {magatzems.map((mag) => (
                <option key={mag.id} value={mag.id}>
                  {mag.tipus === "NAU_CENTRAL" ? "🏭 " : "🚐 "}
                  {mag.nom} {mag.vehicle_matricula ? `[${mag.vehicle_matricula}]` : ""}
                </option>
              ))}
            </select>
          </div>

          <div className="relative">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
            <input
              type="text"
              value={filtreCerca}
              onChange={(e) => setFiltreCerca(e.target.value)}
              placeholder="Cercar ref., nom o codi barres..."
              className="pl-9 pr-3 py-1.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-xs font-medium focus:outline-none focus:border-primary w-52"
            />
          </div>

          <button
            type="button"
            onClick={() => {
              setActiveTab("MATERIALS");
              setMostrarLectorBarres((prev) => !prev);
            }}
            className={`px-3 py-1.5 rounded-xl border text-xs font-bold flex items-center gap-1.5 transition-colors ${
              mostrarLectorBarres
                ? "bg-primary/10 border-primary text-primary"
                : "border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-700"
            }`}
            title="Escanejar codi de barres de material (EAN / Code128)"
          >
            <Barcode className="w-3.5 h-3.5" />
            <span>Lector Barres</span>
          </button>

          <button
            type="button"
            onClick={() => {
              setActiveTab("MATERIALS");
              setNomesTrencamentEstoc((prev) => !prev);
            }}
            className={`px-3 py-1.5 rounded-xl border text-xs font-bold flex items-center gap-1.5 transition-colors ${
              nomesTrencamentEstoc
                ? "bg-rose-600 border-rose-600 text-white shadow"
                : articlesEnTrencament.length > 0
                ? "bg-amber-50 dark:bg-amber-950/40 border-amber-300 dark:border-amber-800 text-amber-800 dark:text-amber-300 hover:bg-amber-100"
                : "border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-100"
            }`}
            title="Filtrar exclusivament articles per sota de l'estoc mínim"
          >
            <AlertTriangle className="w-3.5 h-3.5" />
            <span>Trencaments ({articlesEnTrencament.length})</span>
          </button>

          <select
            value={filtreFamilia}
            onChange={(e) => setFiltreFamilia(e.target.value)}
            className="p-1.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-xs font-semibold uppercase"
          >
            <option value="TOTS">TOTES LES FAMÍLIES</option>
            {Array.from(new Set(articles.map(a => a.familia))).sort().map(fam => (
              <option key={fam} value={fam}>{fam}</option>
            ))}
          </select>

          <button
            onClick={() => carregarArticles()}
            disabled={loading}
            className="p-2 rounded-xl bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 text-slate-600 dark:text-slate-300 transition-colors"
            title="Refrescar llista"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
          </button>

          <button
            onClick={() => {
              if (articles.length > 0) {
                setTraspasArticleId(articles[0].id);
              }
              const nau = magatzems.find(m => m.tipus === "NAU_CENTRAL");
              const furg = magatzems.find(m => m.tipus === "FURGONETA");
              if (nau) setTraspasOrigenId(nau.id);
              if (furg) setTraspasDestiId(furg.id);
              setModalTraspas(true);
            }}
            className="px-3 py-1.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold flex items-center gap-1.5 shadow transition-all"
            title="Traspàs d'estoc entre magatzem central i furgonetes (T026)"
          >
            <Truck className="w-3.5 h-3.5" />
            <span>Traspàs / Dotar</span>
          </button>
          
          {hasCopilotIa && (
            <button
              onClick={() => setModalOcr(true)}
              className="px-3 py-1.5 rounded-xl bg-primary/90 hover:bg-primary text-white text-xs font-bold flex items-center gap-1 shadow transition-all"
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>Entrada Assistida IA</span>
            </button>
          )}

          <button
            onClick={() => setModalNouArticle(true)}
            className="px-3 py-1.5 rounded-xl bg-primary hover:opacity-90 text-white text-xs font-bold flex items-center gap-1 shadow transition-all"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Nou Article</span>
          </button>
        </div>
      </div>

      {mostrarLectorBarres && (
        <div className="mx-4 mt-3 p-3 rounded-2xl bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 flex flex-col sm:flex-row sm:items-center gap-3">
          <div className="text-xs font-semibold text-slate-700 dark:text-slate-200 shrink-0 flex items-center gap-1.5">
            <Barcode className="w-4 h-4 text-primary" />
            <span>Escaneig de Material (EAN / Code128):</span>
          </div>
          <div className="flex-1">
            <BarcodeScanner
              placeholder="Escaneja o introdueix el codi de barres per cercar un material..."
              onScan={(code) => {
                setFiltreCerca(code);
                setActiveTab("MATERIALS");
                setMostrarLectorBarres(false);
              }}
            />
          </div>
        </div>
      )}

      {error && (
        <div className="mx-4 mt-3 p-3 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900 text-rose-700 dark:text-rose-300 text-xs flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-rose-600" />
            <span>{error}</span>
          </div>
          <button onClick={() => setError(null)} className="p-1 hover:text-rose-900">
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* Contingut: Taula d'Inventari */}
      <div className="flex-1 p-4 overflow-y-auto">
        {loading && articles.length === 0 ? (
          <div className="flex-1 flex flex-col items-center justify-center p-12 text-center">
            <RefreshCw className="w-6 h-6 animate-spin text-primary mb-2" />
            <p className="text-xs text-slate-500">Carregant catàleg de magatzem...</p>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="flex flex-wrap gap-2 border-b border-slate-200 dark:border-slate-800 pb-2">
              <button
                onClick={() => setActiveTab("MATERIALS")}
                className={`px-4 py-2 rounded-lg text-xs font-bold transition-colors ${
                  activeTab === "MATERIALS"
                    ? "bg-primary text-white"
                    : "bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-400"
                }`}
              >
                Catàleg de Materials ({articles.length})
              </button>
              <button
                onClick={() => setActiveTab("EINES")}
                className={`px-4 py-2 rounded-lg text-xs font-bold transition-colors flex items-center gap-2 ${
                  activeTab === "EINES"
                    ? "bg-primary text-white"
                    : "bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-400"
                }`}
              >
                <Wrench className="w-3.5 h-3.5" /> Inventari d&apos;Eines ({eines.length})
              </button>
              <button
                onClick={() => setActiveTab("MERMES")}
                className={`px-4 py-2 rounded-lg text-xs font-bold transition-colors flex items-center gap-2 ${
                  activeTab === "MERMES"
                    ? "bg-primary text-white"
                    : "bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-400"
                }`}
              >
                <Trash2 className="w-3.5 h-3.5" /> Mermes &amp; Residus ({mermes.length})
              </button>
              <button
                onClick={() => setActiveTab("RECOMPRA_STOCK")}
                className={`px-4 py-2 rounded-lg text-xs font-bold transition-colors flex items-center gap-2 ${
                  activeTab === "RECOMPRA_STOCK"
                    ? "bg-primary text-white"
                    : "bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-400"
                }`}
              >
                <ShoppingCart className="w-3.5 h-3.5" />
                <span>Recompra d&apos;Estoc</span>
                {recompraAlertes.filter((a) => a.estat === "ACTIVA").length > 0 && (
                  <span className="px-1.5 py-0.5 rounded-full text-[10px] font-mono font-black bg-amber-400 text-slate-950">
                    {recompraAlertes.filter((a) => a.estat === "ACTIVA").length}
                  </span>
                )}
              </button>
              <button
                onClick={() => setActiveTab("ALBARANS")}
                className={`px-4 py-2 rounded-lg text-xs font-bold transition-colors flex items-center gap-2 ${
                  activeTab === "ALBARANS"
                    ? "bg-primary text-white"
                    : "bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-400"
                }`}
              >
                <ClipboardCheck className="w-3.5 h-3.5" />
                <span>Albarans OCR</span>
                {albaransPendents.filter((a) => a.estat === "PENDENT_AUDITORIA").length > 0 && (
                  <span className="px-1.5 py-0.5 rounded-full text-[10px] font-mono font-black bg-rose-500 text-white">
                    {albaransPendents.filter((a) => a.estat === "PENDENT_AUDITORIA").length}
                  </span>
                )}
              </button>
            </div>

            {/* Targetes de Resum */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm flex items-center justify-between">
                <div>
                  <p className="text-[10px] font-mono uppercase text-slate-400 font-bold">Total Articles Catàleg</p>
                  <h3 className="text-xl font-black text-slate-800 dark:text-slate-100 mt-0.5 tabular-nums">
                    {articles.length} <span className="text-xs text-slate-400 font-normal">referències</span>
                  </h3>
                </div>
                <div className="w-10 h-10 rounded-xl bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 flex items-center justify-center">
                  <Building className="w-5 h-5" />
                </div>
              </div>

              <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm flex items-center justify-between">
                <div>
                  <p className="text-[10px] font-mono uppercase text-slate-400 font-bold">Famílies Actives</p>
                  <h3 className="text-xl font-black text-emerald-600 dark:text-emerald-400 mt-0.5 tabular-nums">
                    {new Set(articles.map((a) => a.familia)).size}
                  </h3>
                </div>
                <div className="w-10 h-10 rounded-xl bg-emerald-50 dark:bg-emerald-950/40 text-emerald-600 flex items-center justify-center">
                  <Layers className="w-5 h-5" />
                </div>
              </div>

              <button
                type="button"
                onClick={() => {
                  setActiveTab("MATERIALS");
                  setNomesTrencamentEstoc((prev) => !prev);
                }}
                className={`p-4 rounded-2xl border shadow-sm flex items-center justify-between text-left transition-all ${
                  nomesTrencamentEstoc
                    ? "bg-amber-50 dark:bg-amber-950/40 border-amber-400 dark:border-amber-700"
                    : "bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800 hover:border-amber-300"
                }`}
              >
                <div>
                  <p className="text-[10px] font-mono uppercase text-slate-400 font-bold">
                    Articles en Trencament {nomesTrencamentEstoc ? "(Filtre Actiu)" : ""}
                  </p>
                  <h3 className="text-xl font-black text-amber-600 dark:text-amber-400 mt-0.5 tabular-nums">
                    {articlesEnTrencament.length}{" "}
                    <span className="text-[11px] font-normal text-slate-500">
                      · {recompraAlertes.filter((a) => a.estat === "ACTIVA").length} esborranys HITL
                    </span>
                  </h3>
                </div>
                <div className="w-10 h-10 rounded-xl bg-amber-50 dark:bg-amber-950/40 text-amber-600 flex items-center justify-center">
                  <ShoppingCart className="w-5 h-5" />
                </div>
              </button>
            </div>

            {/* Taula d'articles */}
              <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-x-auto">
              {activeTab === "MATERIALS" ? (
                articles.length === 0 ? (
                  <div className="flex flex-col items-center justify-center p-12 text-center">
                    <div className="w-14 h-14 rounded-full bg-primary/10 text-primary flex items-center justify-center mb-3">
                      <Package className="w-7 h-7" />
                    </div>
                    <h3 className="text-base font-bold text-slate-800 dark:text-slate-100">
                      Magatzem central sense articles
                    </h3>
                    <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 max-w-xs">
                      Estat Dia-0: Registra el primer article o eina per començar a gestionar l&apos;estoc i els moviments.
                    </p>
                    <button
                      onClick={() => setModalNouArticle(true)}
                      className="mt-4 px-4 py-2 rounded-xl bg-primary hover:opacity-90 text-white text-xs font-bold shadow"
                    >
                      + Donar d&apos;Alta Article
                    </button>
                  </div>
                ) : (
                <>
                  {nomesTrencamentEstoc && (
                    <div className="px-4 py-3 bg-amber-50 dark:bg-amber-950/40 border-b border-amber-200 dark:border-amber-900/50 flex flex-wrap items-center justify-between gap-3">
                      <div className="flex items-center gap-2 text-xs font-semibold text-amber-900 dark:text-amber-200">
                        <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
                        <span>
                          Mostrant només articles amb trencament d&apos;estoc ({articlesFiltrats.length} de {articles.length})
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          onClick={() => setActiveTab("RECOMPRA_STOCK")}
                          className="px-3 py-1 rounded-lg bg-primary hover:opacity-90 text-white text-[11px] font-bold inline-flex items-center gap-1"
                        >
                          <Mail className="w-3 h-3" />
                          <span>Preparar Emails Proveïdors</span>
                        </button>
                        <button
                          type="button"
                          onClick={() => setNomesTrencamentEstoc(false)}
                          className="px-3 py-1 rounded-lg border border-amber-300 dark:border-amber-700 text-amber-800 dark:text-amber-200 text-[11px] font-bold hover:bg-amber-100 dark:hover:bg-amber-900/40"
                        >
                          Veure tots els articles
                        </button>
                      </div>
                    </div>
                  )}
                  {articlesFiltrats.length === 0 ? (
                    <div className="flex flex-col items-center justify-center p-12 text-center">
                      <div className="w-12 h-12 rounded-full bg-emerald-50 dark:bg-emerald-950/40 text-emerald-600 flex items-center justify-center mb-3">
                        <CheckCircle2 className="w-6 h-6" />
                      </div>
                      <h3 className="text-sm font-bold text-slate-800 dark:text-slate-100">
                        {nomesTrencamentEstoc
                          ? "Cap article en trencament d'estoc"
                          : "Cap article coincideix amb el filtre"}
                      </h3>
                      <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 max-w-sm">
                        {nomesTrencamentEstoc
                          ? "Tots els materials superen el llindar d'estoc mínim configurat."
                          : "Prova de netejar la cerca o canviar de família."}
                      </p>
                      <button
                        type="button"
                        onClick={() => {
                          setNomesTrencamentEstoc(false);
                          setFiltreCerca("");
                          setFiltreFamilia("TOTS");
                        }}
                        className="mt-4 px-4 py-2 rounded-xl bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 text-slate-700 dark:text-slate-200 text-xs font-bold"
                      >
                        Mostrar tot el catàleg
                      </button>
                    </div>
                  ) : (
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="bg-slate-50 dark:bg-slate-800/60 border-b border-slate-200 dark:border-slate-800 font-bold text-slate-600 dark:text-slate-300">
                      <th className="p-3">Ref. / Barres</th>
                      <th className="p-3">Descripció Article</th>
                      <th className="p-3">Proveïdor</th>
                      <th className="p-3">Família</th>
                      <th className="p-3">Unitat</th>
                      <th className="p-3 text-right">Estoc Disponible</th>
                      <th className="p-3 text-right">Slot Residus</th>
                      <th className="p-3 text-right">Mín. / Òpt.</th>
                      {!esEnginyer && <th className="p-3 text-right">PMP / Cost</th>}
                      <th className="p-3 text-right">Preu Venda</th>
                      <th className="p-3 text-right">Accions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                    {articlesFiltrats.map((art) => {
                      const estocDisp = Number(art.estoc_disponible ?? art.estoc_real ?? 0);
                      const estocFis = Number(art.estoc_fisic ?? estocDisp);
                      const estocRes = Number(art.estoc_reservat ?? 0);
                      return (
                      <tr key={art.id} onClick={() => obrirFitxa(art)} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/40 transition-colors cursor-pointer">
                        <td className="p-3 font-mono">
                          <span className="font-bold text-primary block">{art.referencia_inventari}</span>
                          {art.codi_barres && (
                            <span className="inline-flex items-center gap-1 text-[10px] text-slate-500 mt-0.5">
                              <Barcode className="w-3 h-3" /> {art.codi_barres}
                            </span>
                          )}
                        </td>
                        <td className="p-3 font-medium text-slate-900 dark:text-white">
                          <span>{art.nom}</span>
                          {art.es_material_continu && (
                            <span className="ml-2 px-1.5 py-0.5 rounded bg-sky-100 text-sky-700 dark:bg-sky-900/40 dark:text-sky-300 text-[10px] font-bold">
                              Continu
                            </span>
                          )}
                        </td>
                        <td className="p-3">
                          <span className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                            {art.proveidor_nom || "—"}
                          </span>
                        </td>
                        <td className="p-3">
                          <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                            {art.familia}
                          </span>
                        </td>
                        <td className="p-3 font-mono text-slate-500">
                          {art.unitat_mesura}
                        </td>
                        <td className="p-3 text-right font-mono tabular-nums">
                          <span
                            className={`px-2 py-1 rounded-lg font-bold inline-block ${
                              art.estoc_minim > 0 && estocDisp <= art.estoc_minim
                                ? "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400"
                                : "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300"
                            }`}
                          >
                            {estocDisp}
                          </span>
                          {estocRes > 0 && (
                            <span className="block text-[10px] text-slate-400 mt-0.5">
                              Físic {estocFis} · Res. {estocRes}
                            </span>
                          )}
                        </td>
                        <td className="p-3 text-right font-mono tabular-nums text-amber-600 dark:text-amber-400">
                          {(art.estoc_slot_residus ?? 0).toFixed(2)}
                        </td>
                        <td className="p-3 text-right font-mono tabular-nums text-slate-400">
                          {art.estoc_minim} / {art.estoc_optim}
                        </td>
                        {!esEnginyer && (
                          <td className="p-3 text-right font-mono tabular-nums text-slate-600 dark:text-slate-300">
                            {Number(art.pmp_actual && art.pmp_actual > 0 ? art.pmp_actual : (art.preu_cost ?? 0)).toFixed(2)} €
                          </td>
                        )}
                        <td className="p-3 text-right font-mono tabular-nums font-bold text-emerald-600 dark:text-emerald-400">
                          {Number(art.preu_venda ?? 0).toFixed(2)} €
                        </td>
                        <td className="p-3 text-right">
                          <div className="inline-flex items-center justify-end gap-1.5">
                            {!esEnginyer && art.estoc_minim > 0 && estocDisp <= art.estoc_minim && (
                              <button
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  obrirModalEmailArticle(art);
                                }}
                                className="px-2.5 py-1 rounded-lg bg-amber-100 hover:bg-amber-200 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300 text-[11px] font-bold inline-flex items-center gap-1 transition-colors"
                                title="Preparar esborrany d'email al proveïdor"
                              >
                                <Mail className="w-3 h-3" />
                                <span>Demanar</span>
                              </button>
                            )}
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                obrirAjustEstoc(art);
                              }}
                              className="px-2.5 py-1 rounded-lg bg-primary/10 hover:bg-primary/20 text-primary text-[11px] font-bold inline-flex items-center gap-1 transition-colors"
                              title="Registrar entrada, sortida o reserva manual"
                            >
                              <SlidersHorizontal className="w-3 h-3" />
                              <span>Ajustar Estoc</span>
                            </button>
                          </div>
                        </td>
                      </tr>
                    );})}
                  </tbody>
                </table>
                  )}
                </>
                )
              ) : activeTab === "EINES" ? (
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="bg-blue-50 dark:bg-blue-900/20 border-b border-blue-100 dark:border-blue-900/40 font-bold text-blue-700 dark:text-blue-400">
                      <th className="p-3">Ref. Fabricant</th>
                      <th className="p-3">Nom Màquina / Model</th>
                      <th className="p-3 font-mono">Nº Sèrie</th>
                      <th className="p-3">Estat</th>
                      <th className="p-3">Fi Garantia</th>
                      <th className="p-3 text-right">Accions i Custòdia</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                    {eines.filter(e => e.nom.toLowerCase().includes(filtreCerca.toLowerCase()) || e.numero_serie.toLowerCase().includes(filtreCerca.toLowerCase())).map((eina) => (
                      <tr key={eina.id} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/40 transition-colors">
                        <td className="p-3 font-mono text-slate-500">
                          {eina.referencia_fabricant || "-"}
                        </td>
                        <td className="p-3 font-medium text-slate-900 dark:text-white">
                          {eina.nom} <span className="text-slate-400 ml-1 font-normal">{eina.model}</span>
                        </td>
                        <td className="p-3 font-mono font-bold text-blue-600 dark:text-blue-400">
                          {eina.numero_serie}
                        </td>
                        <td className="p-3">
                          <span
                            className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                              eina.estat === "DISPONIBLE"
                                ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400"
                                : eina.estat === "EN_VEHICLE"
                                ? "bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400"
                                : "bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400"
                            }`}
                          >
                            {eina.estat === "EN_VEHICLE" ? "A VEHICLE" : eina.estat}
                          </span>
                          {eina.custodia_nom && (
                            <p className="text-[10px] text-slate-500 font-medium mt-0.5">
                              {eina.custodia_nom}
                            </p>
                          )}
                        </td>
                        <td className="p-3 text-slate-500 font-mono">
                          {eina.data_fi_garantia ? new Date(eina.data_fi_garantia).toLocaleDateString('ca-ES') : "-"}
                        </td>
                        <td className="p-3 text-right">
                          <div className="inline-flex items-center gap-1.5">
                            <button
                              type="button"
                              onClick={() => obrirEditarEina(eina)}
                              className="px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 text-[10px] font-bold hover:bg-slate-200 dark:hover:bg-slate-700 inline-flex items-center gap-1 transition-colors"
                            >
                              <Edit3 className="w-3 h-3" /> Editar
                            </button>
                            {eina.estat === "DISPONIBLE" ? (
                              <button
                                onClick={() => { setEinaCheckout(eina); setModalCheckout(true); }}
                                className="px-3 py-1 rounded-lg bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-400 text-[10px] font-bold hover:bg-blue-200 transition-colors"
                              >
                                Check-Out
                              </button>
                            ) : (eina.estat === "CUSTODIADA" || eina.estat === "EN_VEHICLE") ? (
                              <button
                                onClick={() => handleCheckin(eina.id)}
                                className="px-3 py-1 rounded-lg bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-400 text-[10px] font-bold hover:bg-emerald-200 transition-colors"
                              >
                                Check-In
                              </button>
                            ) : null}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : activeTab === "RECOMPRA_STOCK" ? (
                <div className="p-5 space-y-4">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-200 dark:border-slate-800">
                    <div>
                      <h3 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2">
                        <ShoppingCart className="w-4 h-4 text-primary" />
                        Safata HITL de Recompra d&apos;Estoc Mínim (FR-010)
                      </h3>
                      <p className="text-xs text-slate-500 mt-0.5">
                        Esborranys pendents de validació humana. Cap comanda ni correu electrònic s&apos;envia sense aprovació explícita.
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={handleEscanejarRecompra}
                      disabled={escanejantRecompra}
                      className="px-3.5 py-2 rounded-xl bg-primary hover:opacity-90 text-white text-xs font-bold flex items-center gap-1.5 shadow disabled:opacity-50"
                    >
                      <RefreshCw className={`w-3.5 h-3.5 ${escanejantRecompra ? "animate-spin" : ""}`} />
                      <span>{escanejantRecompra ? "Escanejant..." : "Escanejar Trencaments d'Estoc"}</span>
                    </button>
                  </div>

                  {recompraGrups.length > 0 && (
                    <div className="space-y-2.5">
                      <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 flex items-center gap-1.5">
                        <Mail className="w-3.5 h-3.5 text-primary" />
                        Esborranys de Comanda Agrupats per Proveïdor
                      </h4>
                      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
                        {recompraGrups.map((grup) => (
                          <div
                            key={grup.grup_key}
                            className="p-4 rounded-2xl border border-primary/20 bg-primary/5 flex flex-col justify-between gap-3"
                          >
                            <div className="space-y-1.5">
                              <div className="flex items-center justify-between gap-2">
                                <span className="text-xs font-bold text-slate-900 dark:text-white">
                                  {grup.proveidor_nom}
                                </span>
                                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300">
                                  {grup.total_articles} {grup.total_articles === 1 ? "article" : "articles"}
                                </span>
                              </div>
                              <p className="text-[11px] font-mono text-slate-500">
                                Email: {grup.proveidor_email || "Sense email configurat (editable al revisar)"}
                              </p>
                              <ul className="text-[11px] text-slate-700 dark:text-slate-300 space-y-0.5 pt-1">
                                {grup.items.map((it) => (
                                  <li key={it.alerta_id} className="flex justify-between gap-2 font-mono">
                                    <span className="truncate">
                                      • {it.referencia || "N/A"} · {it.nom}
                                    </span>
                                    <span className="font-bold shrink-0">
                                      {it.quantitat_proposada} {it.unitat_mesura}
                                    </span>
                                  </li>
                                ))}
                              </ul>
                              {!esEnginyer && grup.import_total_estimat != null && (
                                <p className="text-[11px] font-mono text-slate-700 dark:text-slate-200 pt-1">
                                  Import estimat conjunt: <strong>{Number(grup.import_total_estimat).toFixed(2)} €</strong>
                                </p>
                              )}
                            </div>
                            <div className="flex items-center justify-between gap-2 pt-2 border-t border-primary/15">
                              <span className="text-[10px] font-semibold text-emerald-700 dark:text-emerald-400">
                                HITL: Pendent d&apos;aprovació humana
                              </span>
                              {!esEnginyer ? (
                                <button
                                  type="button"
                                  onClick={() => obrirModalEmailGrup(grup)}
                                  className="px-3 py-1.5 rounded-xl bg-primary hover:opacity-90 text-white text-xs font-bold inline-flex items-center gap-1.5 shadow-sm"
                                >
                                  <Mail className="w-3.5 h-3.5" />
                                  <span>Revisar i Enviar Email</span>
                                </button>
                              ) : (
                                <span className="text-[11px] text-slate-500 font-semibold">Només Direcció / Admin</span>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {recompraAlertes.length === 0 ? (
                    <div className="rounded-xl border border-dashed border-slate-200 dark:border-slate-800 py-10 text-center text-xs text-slate-500">
                      Cap alerta activa de trencament d&apos;estoc. Tots els articles superen l&apos;estoc mínim configurat.
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {recompraAlertes.map((alerta) => {
                        const prop = alerta.dades_comanda_proposta || {};
                        const qtyProp = Number(prop.quantitat_aprovada ?? prop.quantitat_proposada ?? 0);
                        const qtyInputVal = quantitatsRecompraEdit[alerta.id] ?? qtyProp;
                        const isPendent = alerta.estat === "ACTIVA";
                        return (
                          <div
                            key={alerta.id}
                            className="p-4 rounded-2xl border border-slate-200 dark:border-slate-800 bg-slate-50/70 dark:bg-slate-800/30 flex flex-col lg:flex-row lg:items-center justify-between gap-4"
                          >
                            <div className="space-y-1 flex-1 min-w-0">
                              <div className="flex flex-wrap items-center gap-2">
                                <span
                                  className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${
                                    isPendent
                                      ? "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300"
                                      : alerta.estat === "APROVADA"
                                      ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300"
                                      : "bg-slate-200 text-slate-600 dark:bg-slate-700 dark:text-slate-300"
                                  }`}
                                >
                                  {isPendent ? "ESBORRANY HITL PENDENT" : alerta.estat}
                                </span>
                                <span className="font-mono text-xs font-bold text-primary">
                                  {alerta.article_ref || "N/A"}
                                </span>
                                <span className="text-xs font-bold text-slate-900 dark:text-white truncate">
                                  {alerta.article_nom}
                                </span>
                              </div>
                              <p className="text-xs text-slate-600 dark:text-slate-300">{alerta.missatge}</p>
                              <div className="flex flex-wrap gap-4 text-[11px] font-mono text-slate-500 pt-1">
                                <span>Disponible: <strong className="text-rose-600">{prop.estoc_disponible ?? 0}</strong> / Mínim: <strong>{prop.estoc_minim ?? 0}</strong></span>
                                <span>Proveïdor: <strong>{alerta.proveidor_nom || "Sense assignar"}</strong></span>
                                {!esEnginyer && prop.import_estimat != null && (
                                  <span>Import estimat: <strong className="text-slate-800 dark:text-slate-200">{Number(prop.import_estimat).toFixed(2)} €</strong></span>
                                )}
                                <span className="text-emerald-700 dark:text-emerald-400">Sense enviament automàtic</span>
                              </div>
                            </div>

                            {isPendent && (
                              <div className="flex items-center gap-2 shrink-0">
                                {!esEnginyer ? (
                                  <>
                                    <input
                                      type="number"
                                      min="1"
                                      step="any"
                                      value={qtyInputVal}
                                      onChange={(e) =>
                                        setQuantitatsRecompraEdit((prev) => ({
                                          ...prev,
                                          [alerta.id]: parseFloat(e.target.value) || 0,
                                        }))
                                      }
                                      className="w-24 px-2.5 py-1.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs font-mono font-bold text-center"
                                    />
                                    <button
                                      type="button"
                                      onClick={() => obrirModalEmailAlerta(alerta)}
                                      className="px-3 py-1.5 rounded-xl bg-amber-100 hover:bg-amber-200 text-amber-900 dark:bg-amber-900/40 dark:text-amber-200 text-xs font-bold inline-flex items-center gap-1"
                                    >
                                      <Mail className="w-3.5 h-3.5" />
                                      <span>Revisar Email</span>
                                    </button>
                                    <button
                                      type="button"
                                      disabled={resolentAlertaId === alerta.id}
                                      onClick={() => handleAccioRecompra(alerta, "APROVAR")}
                                      className="px-3 py-1.5 rounded-xl bg-primary hover:opacity-90 text-white text-xs font-bold disabled:opacity-50"
                                    >
                                      Aprovar Esborrany
                                    </button>
                                    <button
                                      type="button"
                                      disabled={resolentAlertaId === alerta.id}
                                      onClick={() => handleAccioRecompra(alerta, "DESCARTAR")}
                                      className="px-3 py-1.5 rounded-xl border border-slate-300 dark:border-slate-700 text-slate-600 dark:text-slate-300 text-xs font-bold hover:bg-slate-100 dark:hover:bg-slate-800 disabled:opacity-50"
                                    >
                                      Descartar
                                    </button>
                                  </>
                                ) : (
                                  <span className="text-[11px] font-semibold text-slate-500 bg-slate-100 dark:bg-slate-800 px-3 py-1.5 rounded-xl">
                                    Aprovació reservada a Direcció / Administració
                                  </span>
                                )}
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              ) : activeTab === "ALBARANS" ? (
                <div className="p-5 space-y-4">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-200 dark:border-slate-800">
                    <div>
                      <h3 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2">
                        <ClipboardCheck className="w-4 h-4 text-primary" />
                        Albarans d&apos;Entrada Pendents d&apos;Auditoria i Consolidats (FR-009)
                      </h3>
                      <p className="text-xs text-slate-500 mt-0.5">
                        Els albarans desats en pendent no incrementen l&apos;estoc ni recalculen el PMP fins a la consolidació humana.
                      </p>
                    </div>
                  </div>
                  {albaransPendents.length === 0 ? (
                    <div className="rounded-xl border border-dashed border-slate-200 dark:border-slate-800 py-10 text-center text-xs text-slate-500">
                      Cap albarà enregistrat. Puja un albarà des d&apos;Entrada Assistida IA per auditar-lo abans de consolidar.
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {albaransPendents.map((alb) => (
                        <div
                          key={alb.id}
                          className="p-4 rounded-2xl border border-slate-200 dark:border-slate-800 bg-slate-50/60 dark:bg-slate-800/30 space-y-2"
                        >
                          <div className="flex flex-wrap items-center justify-between gap-3">
                            <div className="flex flex-wrap items-center gap-2">
                              <span
                                className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${
                                  alb.estat === "PENDENT_AUDITORIA"
                                    ? "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300"
                                    : "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300"
                                }`}
                              >
                                {alb.estat}
                              </span>
                              <span className="font-mono text-xs font-bold text-primary">
                                {alb.numero_albara}
                              </span>
                              <span className="text-xs font-bold text-slate-800 dark:text-white">
                                {alb.proveidor_nom || "Proveïdor"}
                              </span>
                              {alb.data_albara && (
                                <span className="text-[11px] font-mono text-slate-400">
                                  {alb.data_albara}
                                </span>
                              )}
                              {alb.estat === "PENDENT_AUDITORIA" && alb.ja_te_stock_aplicat && (
                                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-sky-100 text-sky-800 dark:bg-sky-900/40 dark:text-sky-300">
                                  Estoc ja aplicat (no es duplicarà)
                                </span>
                              )}
                            </div>
                            {alb.estat === "PENDENT_AUDITORIA" && (
                              <div className="flex flex-wrap items-center gap-2">
                                <button
                                  type="button"
                                  disabled={consolidantAlbaraId === alb.id}
                                  onClick={() => handleRevisarAlbaraPendent(alb)}
                                  className="px-3 py-1.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-200 text-xs font-bold inline-flex items-center gap-1.5 disabled:opacity-50"
                                >
                                  <Edit3 className="w-3.5 h-3.5" />
                                  <span>Revisar / Auditar</span>
                                </button>
                                <button
                                  type="button"
                                  disabled={consolidantAlbaraId === alb.id}
                                  onClick={() => handleConsolidarAlbara(alb.id)}
                                  className="px-3 py-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold inline-flex items-center gap-1.5 disabled:opacity-50"
                                >
                                  <CheckCircle2 className="w-3.5 h-3.5" />
                                  <span>
                                    {consolidantAlbaraId === alb.id
                                      ? "Consolidant..."
                                      : alb.ja_te_stock_aplicat
                                        ? "Marcar Consolidat (sense duplicar estoc)"
                                        : "Consolidar i Augmentar Estoc"}
                                  </span>
                                </button>
                              </div>
                            )}
                          </div>
                          {alb.linies && alb.linies.length > 0 && (
                            <div className="text-[11px] text-slate-600 dark:text-slate-300 grid grid-cols-1 md:grid-cols-2 gap-1 pt-1">
                              {alb.linies.map((lin, idx) => (
                                <div key={`${alb.id}-${idx}`} className="font-mono flex justify-between gap-2 bg-white dark:bg-slate-900 px-2.5 py-1 rounded-lg border border-slate-100 dark:border-slate-800">
                                  <span className="truncate">{lin.referencia} · {lin.nom}</span>
                                  <span className="font-bold shrink-0">
                                    x{lin.quantitat}{!esEnginyer && lin.preu != null ? ` · ${Number(lin.preu).toFixed(2)}€` : ""}
                                  </span>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ) : (
                <div className="p-5 space-y-6">
                  <form onSubmit={handleRegistrarMerma} className="grid grid-cols-1 md:grid-cols-6 gap-3 rounded-xl border border-slate-200 dark:border-slate-800 p-4 bg-slate-50/70 dark:bg-slate-800/30">
                    <div className="md:col-span-2">
                      <label className="block text-[11px] font-semibold text-slate-600 dark:text-slate-300 mb-1">Article</label>
                      <select
                        value={mermaArticleId}
                        onChange={(e) => setMermaArticleId(e.target.value)}
                        className="w-full rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-2 text-xs"
                      >
                        <option value="">Selecciona article...</option>
                        {articles.map((a) => (
                          <option key={a.id} value={a.id}>
                            {a.referencia_inventari} · {a.nom}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="block text-[11px] font-semibold text-slate-600 dark:text-slate-300 mb-1">Magatzem</label>
                      <select
                        value={mermaMagatzemId}
                        onChange={(e) => setMermaMagatzemId(e.target.value)}
                        className="w-full rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-2 text-xs"
                      >
                        <option value="">Selecciona nau...</option>
                        {magatzems.map((m) => (
                          <option key={m.id} value={m.id}>{m.nom}</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="block text-[11px] font-semibold text-slate-600 dark:text-slate-300 mb-1">Motiu comptable</label>
                      <select
                        value={mermaMotiu}
                        onChange={(e) => setMermaMotiu(e.target.value)}
                        className="w-full rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-2 text-xs"
                      >
                        <option value="OBRA_TALL_INUTIL">Tall inútil / Obra (600)</option>
                        <option value="ENVAS_DESPRECINTAT_CAMP">Envàs desprecintat camp (600)</option>
                        <option value="FIANCA_PALET_TRENCAT">Fiança palet trencat (600)</option>
                        <option value="CADUCITAT_FEFO">Caducitat FEFO nau (659)</option>
                        <option value="TRENCAMENT_NAU">Trencament a nau (659)</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-[11px] font-semibold text-slate-600 dark:text-slate-300 mb-1">Quantitat &amp; OT</label>
                      <div className="flex gap-2">
                        <input
                          type="number"
                          step="0.01"
                          min="0.01"
                          value={mermaQuantitat}
                          onChange={(e) => setMermaQuantitat(e.target.value)}
                          className="w-20 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-2 py-2 text-xs tabular-nums"
                        />
                        <select
                          value={mermaOtId}
                          onChange={(e) => setMermaOtId(e.target.value)}
                          className="flex-1 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-2 py-2 text-xs"
                        >
                          <option value="">Sense OT (Nau)</option>
                          {ordresTreball.map((ot) => (
                            <option key={ot.id} value={ot.id}>{ot.codi}</option>
                          ))}
                        </select>
                      </div>
                    </div>
                    <div className="flex items-end">
                      <button
                        type="submit"
                        disabled={registrantMerma}
                        className="w-full rounded-lg bg-primary px-4 py-2 text-xs font-bold text-white disabled:opacity-50"
                      >
                        {registrantMerma ? "Registrant..." : "Registrar merma"}
                      </button>
                    </div>
                  </form>

                  {suggerimentMerma && (
                    <div className="rounded-xl border border-sky-200 dark:border-sky-900 bg-sky-50/70 dark:bg-sky-950/30 p-3 flex flex-wrap items-center justify-between gap-2 text-xs">
                      <div className="flex items-center gap-2 text-sky-900 dark:text-sky-200">
                        <AlertTriangle className="w-4 h-4 text-sky-600 shrink-0" />
                        <span>{suggerimentMerma.recomanacio}</span>
                      </div>
                      <span className="px-2.5 py-0.5 rounded-full bg-sky-100 dark:bg-sky-900/60 text-sky-800 dark:text-sky-200 font-mono font-bold text-[11px]">
                        Merma suggerida: {Number(suggerimentMerma.merma_suggerida_pct || 0).toFixed(1)}%
                        {suggerimentMerma.es_material_continu ? " · Material continu" : ""}
                      </span>
                    </div>
                  )}

                  {mermes.length === 0 ? (
                    <div className="rounded-xl border border-dashed border-slate-200 dark:border-slate-800 py-10 text-center text-xs text-slate-500">
                      Cap merma d&apos;inventari registrada. Qualsevol baixa s&apos;imputarà automàticament al PMP vigent i a Comptabilitat.
                    </div>
                  ) : (
                    <table className="w-full text-left text-xs border-collapse">
                      <thead>
                        <tr className="border-b border-slate-200 dark:border-slate-800 text-slate-500 font-bold">
                          <th className="p-3">Article</th>
                          <th className="p-3">Motiu</th>
                          <th className="p-3">Subcompte</th>
                          <th className="p-3">OT Imputada</th>
                          <th className="p-3 text-right">Quantitat</th>
                          {!esEnginyer && <th className="p-3 text-right">PMP Aplicat</th>}
                          {!esEnginyer && <th className="p-3 text-right">Cost Imputat</th>}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                        {mermes.map((m) => (
                          <tr key={m.id}>
                            <td className="p-3 font-medium">
                              <span className="font-mono text-primary mr-1.5">{m.article_ref}</span>
                              {m.article_nom}
                            </td>
                            <td className="p-3 text-slate-600 dark:text-slate-300">{m.motiu}</td>
                            <td className="p-3 font-mono font-semibold text-primary">{m.subcompte_comptable}</td>
                            <td className="p-3 font-mono text-slate-500">{m.ordre_treball_codi || "Nau (General)"}</td>
                            <td className="p-3 text-right font-mono tabular-nums">{Number(m.quantitat).toFixed(2)}</td>
                            {!esEnginyer && (
                              <td className="p-3 text-right font-mono tabular-nums">{Number(m.pmp_aplicat).toFixed(2)} €</td>
                            )}
                            {!esEnginyer && (
                              <td className="p-3 text-right font-mono font-bold tabular-nums text-rose-600">
                                {Number(m.cost_total).toFixed(2)} €
                              </td>
                            )}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Modal Entrada OCR */}
      {modalOcr && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className={`w-full ${resultatOcr ? "max-w-5xl max-h-[90vh]" : "max-w-lg"} bg-white dark:bg-slate-900 rounded-3xl shadow-2xl border border-slate-200 dark:border-slate-800 overflow-hidden flex flex-col`}>
            <div className="p-5 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between shrink-0">
              <h3 className="font-bold text-sm text-slate-800 dark:text-slate-100 flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-primary" />
                Entrada Assistida per IA (OCR Albarà / Factura)
              </h3>
              <button
                onClick={() => {
                  setModalOcr(false);
                  setFitxerOcr(null);
                  setResultatOcr(null);
                }}
                className="p-1 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="p-5 space-y-4 overflow-y-auto flex-1">
              {!resultatOcr ? (
                <form onSubmit={handlePujarOcr} className="space-y-4">
                  <div>
                    <label className="block text-xs font-bold text-slate-600 dark:text-slate-400 mb-2">
                      Puja l'albarà o factura (PDF / Imatge)
                    </label>
                    <input
                      type="file"
                      accept=".pdf,image/*"
                      onChange={(e) => setFitxerOcr(e.target.files?.[0] || null)}
                      className="w-full text-xs"
                      disabled={processantOcr}
                    />
                  </div>
                  <div className="flex justify-end">
                    <button
                      type="submit"
                      disabled={!fitxerOcr || processantOcr}
                      className="px-4 py-2 rounded-xl bg-primary hover:opacity-90 text-white text-xs font-bold shadow disabled:opacity-50"
                    >
                      {processantOcr ? "Processant amb IA..." : "Processar Document"}
                    </button>
                  </div>
                </form>
              ) : (
                <div className="space-y-4">
                  {/* Dades de la capçalera detectada amb selecció i edició */}
                  <div className="p-4 bg-slate-50 dark:bg-slate-800/60 rounded-2xl border border-slate-200 dark:border-slate-700 space-y-3">
                    <div className="flex flex-col md:flex-row md:items-center justify-between gap-2 pb-2 border-b border-slate-200 dark:border-slate-700/60">
                      <span className="text-xs font-bold text-slate-700 dark:text-slate-200 flex items-center gap-1.5">
                        <Building className="w-4 h-4 text-primary" />
                        Capçalera del Document & Proveïdor
                      </span>
                      <div className="flex items-center gap-2">
                        <label className="text-[11px] font-medium text-slate-500">Vincular Proveïdor:</label>
                        <select
                          onChange={(e) => {
                            const val = e.target.value;
                            if (!val) return;
                            const trobat = proveidors.find((p) => p.id === val);
                            if (trobat) {
                              setResultatOcr({
                                ...resultatOcr,
                                proveidor: {
                                  ...resultatOcr.proveidor,
                                  nom: trobat.rao_social,
                                  nif: trobat.nif,
                                  telefon: trobat.telefon || "",
                                  email: trobat.email || "",
                                },
                              });
                            }
                          }}
                          className="px-2.5 py-1 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 text-xs font-medium"
                        >
                          <option value="">-- Seleccionar proveïdor registrat --</option>
                          {proveidors.map((p) => (
                            <option key={p.id} value={p.id}>
                              {p.rao_social} ({p.nif})
                            </option>
                          ))}
                        </select>
                      </div>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
                      <div>
                        <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">
                          Nom Proveïdor (Raó Social) *
                        </label>
                        <input
                          type="text"
                          required
                          value={resultatOcr.proveidor?.nom || ""}
                          onChange={(e) =>
                            setResultatOcr({
                              ...resultatOcr,
                              proveidor: { ...resultatOcr.proveidor, nom: e.target.value },
                            })
                          }
                          className="w-full px-2.5 py-1.5 rounded-xl border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 text-xs font-bold text-slate-800 dark:text-slate-100"
                        />
                      </div>
                      <div>
                        <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">
                          NIF / CIF Proveïdor *
                        </label>
                        <input
                          type="text"
                          required
                          value={resultatOcr.proveidor?.nif || ""}
                          onChange={(e) =>
                            setResultatOcr({
                              ...resultatOcr,
                              proveidor: { ...resultatOcr.proveidor, nif: e.target.value },
                            })
                          }
                          className="w-full px-2.5 py-1.5 rounded-xl border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 text-xs font-mono font-bold text-slate-800 dark:text-slate-100 uppercase"
                        />
                      </div>
                      <div>
                        <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">
                          Nº Document (Albarà) *
                        </label>
                        <input
                          type="text"
                          required
                          value={resultatOcr.numero_document || ""}
                          onChange={(e) =>
                            setResultatOcr({ ...resultatOcr, numero_document: e.target.value })
                          }
                          className="w-full px-2.5 py-1.5 rounded-xl border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 text-xs font-mono font-bold text-primary"
                        />
                      </div>
                      <div>
                        <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">
                          Data Document *
                        </label>
                        <input
                          type="date"
                          required
                          value={resultatOcr.data_document || ""}
                          onChange={(e) =>
                            setResultatOcr({ ...resultatOcr, data_document: e.target.value })
                          }
                          className="w-full px-2.5 py-1.5 rounded-xl border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 text-xs font-medium text-slate-800 dark:text-slate-100"
                        />
                      </div>
                    </div>
                  </div>

                  {/* Capçalera de secció de línies amb botó d'afegir */}
                  <div className="flex items-center justify-between pt-1">
                    <span className="text-xs font-bold text-slate-700 dark:text-slate-300 flex items-center gap-1.5">
                      <Layers className="w-3.5 h-3.5 text-primary" />
                      Línies d'Articles Detectades ({resultatOcr.linies?.length || 0})
                    </span>
                    <button
                      type="button"
                      onClick={() => {
                        const novaLinia = {
                          tipus: "MATERIAL",
                          referencia: `ART-${(resultatOcr.linies?.length || 0) + 1}`,
                          nom: "",
                          quantitat: 1,
                          preu: 0,
                          descompte_percent: 0,
                        };
                        setResultatOcr({
                          ...resultatOcr,
                          linies: [...(resultatOcr.linies || []), novaLinia],
                        });
                      }}
                      className="px-3 py-1 rounded-xl bg-primary/10 hover:bg-primary/20 text-primary text-xs font-bold flex items-center gap-1 border border-primary/30 transition-colors"
                    >
                      <Plus className="w-3.5 h-3.5" />
                      <span>Afegir Línia</span>
                    </button>
                  </div>

                  {/* Taula de línies de l'albarà amb edició */}
                  <div className="border border-slate-200 dark:border-slate-700 rounded-2xl overflow-hidden shadow-sm">
                    <table className="w-full text-left text-xs border-collapse">
                      <thead>
                        <tr className="bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 font-bold border-b border-slate-200 dark:border-slate-700">
                          <th className="p-2.5">Tipus</th>
                          <th className="p-2.5">Ref. Article (Codi)</th>
                          <th className="p-2.5">Descripció del Producte</th>
                          <th className="p-2.5 text-right">Quantitat</th>
                          <th className="p-2.5 text-right">Preu Tarifa (€)</th>
                          <th className="p-2.5 text-right">Dte (%)</th>
                          <th className="p-2.5 text-right">Cost Net (€)</th>
                          <th className="p-2.5 text-right">Total Net</th>
                          <th className="p-2.5 text-center w-10"></th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100 dark:divide-slate-800 bg-white dark:bg-slate-900">
                        {resultatOcr.linies?.map((lin: any, idx: number) => {
                          const costNetUnitari = Number(lin.preu || 0) * (1 - (Number(lin.descompte_percent || 0) / 100));
                          const netTotal = Number(lin.quantitat || 0) * costNetUnitari;
                          const ocrNif = String(resultatOcr.proveidor?.nif || "").trim().toUpperCase();
                          const ocrNom = String(resultatOcr.proveidor?.nom || "").trim().toLowerCase();
                          const provMatch = proveidors.find(
                            (p) =>
                              (ocrNif && ocrNif !== "B00000000" && String(p.nif || "").trim().toUpperCase() === ocrNif) ||
                              (ocrNom && String(p.rao_social || "").trim().toLowerCase() === ocrNom)
                          );
                          const refTrim = String(lin.referencia || "").trim();
                          const artMatch =
                            !esEnginyer && provMatch && refTrim && lin.tipus !== "EINA"
                              ? articles.find(
                                  (a) =>
                                    a.referencia_inventari === refTrim &&
                                    a.proveidor_id === provMatch.id &&
                                    Number(a.marge_guanys || 0) > 0
                                )
                              : undefined;
                          return (
                            <tr key={idx} className="hover:bg-slate-50/60 dark:hover:bg-slate-800/40">
                              <td className="p-2">
                                <button
                                  type="button"
                                  onClick={() => {
                                    const updated = [...resultatOcr.linies];
                                    updated[idx].tipus = lin.tipus === "EINA" ? "MATERIAL" : "EINA";
                                    setResultatOcr({ ...resultatOcr, linies: updated });
                                  }}
                                  className={`px-2 py-0.5 rounded-full text-[10px] font-bold cursor-pointer transition-colors ${lin.tipus === "EINA" ? "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300 hover:bg-blue-200" : "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300 hover:bg-emerald-200"}`}
                                  title="Fes clic per commutar entre MATERIAL i EINA"
                                >
                                  {lin.tipus} ⟲
                                </button>
                              </td>
                              <td className="p-2">
                                <input
                                  type="text"
                                  value={lin.referencia}
                                  onChange={(e) => {
                                    const updated = [...resultatOcr.linies];
                                    updated[idx].referencia = e.target.value;
                                    setResultatOcr({ ...resultatOcr, linies: updated });
                                  }}
                                  placeholder="Ref. Codi"
                                  className="w-28 font-mono font-bold text-emerald-700 dark:text-emerald-400 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded px-1.5 py-0.5 text-xs"
                                />
                              </td>
                              <td className="p-2">
                                <input
                                  type="text"
                                  value={lin.nom}
                                  onChange={(e) => {
                                    const updated = [...resultatOcr.linies];
                                    updated[idx].nom = e.target.value;
                                    setResultatOcr({ ...resultatOcr, linies: updated });
                                  }}
                                  placeholder="Descripció de l'article"
                                  className="w-full min-w-[180px] bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded px-1.5 py-0.5 text-xs text-slate-800 dark:text-slate-100"
                                />
                              </td>
                              <td className="p-2 text-right">
                                <input
                                  type="number"
                                  step="0.01"
                                  value={lin.quantitat}
                                  onChange={(e) => {
                                    const updated = [...resultatOcr.linies];
                                    updated[idx].quantitat = Number(e.target.value);
                                    setResultatOcr({ ...resultatOcr, linies: updated });
                                  }}
                                  className="w-16 text-right font-mono font-bold bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded px-1 py-0.5 text-xs"
                                />
                              </td>
                              <td className="p-2 text-right">
                                <input
                                  type="number"
                                  step="0.01"
                                  value={lin.preu}
                                  onChange={(e) => {
                                    const updated = [...resultatOcr.linies];
                                    updated[idx].preu = Number(e.target.value);
                                    setResultatOcr({ ...resultatOcr, linies: updated });
                                  }}
                                  className="w-16 text-right font-mono bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded px-1 py-0.5 text-xs"
                                />
                              </td>
                              <td className="p-2 text-right">
                                <input
                                  type="number"
                                  step="0.01"
                                  value={lin.descompte_percent}
                                  onChange={(e) => {
                                    const updated = [...resultatOcr.linies];
                                    updated[idx].descompte_percent = Number(e.target.value);
                                    setResultatOcr({ ...resultatOcr, linies: updated });
                                  }}
                                  className="w-14 text-right font-mono bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded px-1 py-0.5 text-xs"
                                />
                              </td>
                              <td className="p-2 text-right font-mono text-slate-500">
                                <div>{costNetUnitari.toFixed(2)} €</div>
                                {artMatch && (
                                  <div className="text-[10px] font-sans font-bold text-emerald-600 dark:text-emerald-400">
                                    Marge +{Number(artMatch.marge_guanys)}% auto
                                  </div>
                                )}
                              </td>
                              <td className="p-2 text-right font-mono font-bold text-slate-800 dark:text-slate-200">
                                {netTotal.toFixed(2)} €
                              </td>
                              <td className="p-2 text-center">
                                <button
                                  type="button"
                                  onClick={() => {
                                    const updated = resultatOcr.linies.filter((_: any, i: number) => i !== idx);
                                    setResultatOcr({ ...resultatOcr, linies: updated });
                                  }}
                                  className="p-1 text-slate-400 hover:text-rose-600 rounded transition-colors"
                                  title="Eliminar línia"
                                >
                                  <Trash2 className="w-3.5 h-3.5" />
                                </button>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>

                  {/* Peu de la revisió */}
                  <div className="flex items-center justify-between pt-2">
                    <div className="text-xs text-slate-500">
                      Total net de l'albarà:{" "}
                      <strong className="text-slate-800 dark:text-slate-200 font-mono text-sm ml-1">
                        {resultatOcr.linies
                          ?.reduce((acc: number, l: any) => {
                            const costNet = Number(l.preu || 0) * (1 - (Number(l.descompte_percent || 0) / 100));
                            return acc + (Number(l.quantitat || 0) * costNet);
                          }, 0)
                          .toFixed(2)}{" "}
                        €
                      </strong>
                    </div>

                    <div className="flex flex-wrap gap-2">
                      <button
                        onClick={() => setResultatOcr(null)}
                        className="px-4 py-2 rounded-xl border border-slate-300 dark:border-slate-700 text-slate-600 dark:text-slate-300 text-xs font-medium hover:bg-slate-100 dark:hover:bg-slate-800"
                        disabled={processantOcr}
                      >
                        Tornar
                      </button>
                      {!resultatOcr.albara_id && (
                        <button
                          type="button"
                          onClick={handleDesarAlbaraPendent}
                          disabled={processantOcr}
                          className="px-4 py-2 rounded-xl bg-amber-500 hover:bg-amber-600 text-white text-xs font-bold shadow flex items-center gap-1.5 disabled:opacity-50"
                        >
                          <ClipboardCheck className="w-3.5 h-3.5" />
                          <span>Desar Pendent d&apos;Auditoria</span>
                        </button>
                      )}
                      <button
                        onClick={handleConfirmarOcr}
                        disabled={processantOcr}
                        className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold shadow flex items-center gap-1.5 disabled:opacity-50"
                      >
                        {processantOcr ? (
                          <>
                            <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                            <span>Desant...</span>
                          </>
                        ) : (
                          <>
                            <CheckCircle2 className="w-3.5 h-3.5" />
                            <span>Confirmar i Desar a l'Inventari</span>
                          </>
                        )}
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Modal Alta Nou Article */}
      {modalNouArticle && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-lg bg-white dark:bg-slate-900 rounded-3xl shadow-2xl border border-slate-200 dark:border-slate-800 overflow-hidden">
            <div className="p-5 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
              <h3 className="font-bold text-sm text-slate-800 dark:text-slate-100 flex items-center gap-2">
                <Plus className="w-4 h-4 text-emerald-600" />
                Alta d'Article al Catàleg (Spec 004)
              </h3>
              <button
                onClick={() => setModalNouArticle(false)}
                className="p-1 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleCrearArticle} className="p-5 space-y-4">
              <div className="flex gap-4 p-3 bg-slate-50 dark:bg-slate-800 rounded-xl mb-4 border border-slate-200 dark:border-slate-700">
                <label className="flex items-center gap-2 cursor-pointer text-xs font-bold text-slate-700 dark:text-slate-300">
                  <input 
                    type="radio" 
                    name="tipus" 
                    value="MATERIAL" 
                    checked={nouArticle.tipus_creacio === "MATERIAL"}
                    onChange={(e) => setNouArticle({...nouArticle, tipus_creacio: "MATERIAL"})}
                    className="w-4 h-4 text-emerald-600"
                  />
                  Consumible (Material)
                </label>
                <label className="flex items-center gap-2 cursor-pointer text-xs font-bold text-slate-700 dark:text-slate-300">
                  <input 
                    type="radio" 
                    name="tipus" 
                    value="EINA" 
                    checked={nouArticle.tipus_creacio === "EINA"}
                    onChange={(e) => setNouArticle({...nouArticle, tipus_creacio: "EINA"})}
                    className="w-4 h-4 text-emerald-600"
                  />
                  Eina de Custòdia (Màquina)
                </label>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                    {nouArticle.tipus_creacio === "MATERIAL" ? "Referència *" : "Ref. Fabricant"}
                  </label>
                  <input
                    type="text"
                    required={nouArticle.tipus_creacio === "MATERIAL"}
                    placeholder={nouArticle.tipus_creacio === "MATERIAL" ? "#ART-1001" : "Ex: BOSCH-234"}
                    value={nouArticle.referencia_inventari}
                    onChange={(e) => setNouArticle({ ...nouArticle, referencia_inventari: e.target.value })}
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs font-mono"
                  />
                </div>
                {nouArticle.tipus_creacio === "MATERIAL" && (
                  <div>
                    <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                      Família *
                    </label>
                    {!creantNovaFamiliaNou ? (
                      <div className="flex items-center gap-1.5">
                        <select
                          value={nouArticle.familia}
                          onChange={(e) => {
                            if (e.target.value === "+_CREAR_NOVA_") {
                              setCreantNovaFamiliaNou(true);
                              setNovaFamiliaTextNou("");
                            } else {
                              setNouArticle({ ...nouArticle, familia: e.target.value });
                            }
                          }}
                          className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs font-semibold"
                        >
                          {totesLesFamilies.map((fam) => (
                            <option key={fam} value={fam}>
                              {fam}
                            </option>
                          ))}
                          <option value="+_CREAR_NOVA_">➕ + Crear nova família...</option>
                        </select>
                      </div>
                    ) : (
                      <div className="flex items-center gap-1.5">
                        <input
                          type="text"
                          autoFocus
                          placeholder="Escriu el nom de la nova família..."
                          value={novaFamiliaTextNou}
                          onChange={(e) => {
                            setNovaFamiliaTextNou(e.target.value);
                            setNouArticle({ ...nouArticle, familia: e.target.value.toUpperCase() });
                          }}
                          className="w-full px-3 py-2 rounded-xl border border-emerald-500 bg-emerald-50/40 dark:bg-emerald-950/40 text-xs font-bold uppercase"
                        />
                        <button
                          type="button"
                          onClick={() => {
                            setCreantNovaFamiliaNou(false);
                            if (!nouArticle.familia) {
                              setNouArticle({ ...nouArticle, familia: "GENERAL" });
                            }
                          }}
                          className="px-2.5 py-2 rounded-xl bg-slate-200 dark:bg-slate-700 text-xs font-semibold text-slate-700 dark:text-slate-200 shrink-0"
                        >
                          Llista
                        </button>
                      </div>
                    )}
                  </div>
                )}
                {nouArticle.tipus_creacio === "EINA" && (
                  <div>
                    <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                      Número de Sèrie *
                    </label>
                    <input
                      type="text"
                      required
                      placeholder="Ex: SN-9283749823"
                      value={nouArticle.numero_serie}
                      onChange={(e) => setNouArticle({ ...nouArticle, numero_serie: e.target.value })}
                      className="w-full px-3 py-2 rounded-xl border border-blue-300 dark:border-blue-700 bg-blue-50 dark:bg-blue-900/30 text-xs font-mono font-bold"
                    />
                  </div>
                )}
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className={nouArticle.tipus_creacio === "MATERIAL" ? "col-span-2" : ""}>
                  <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                    {nouArticle.tipus_creacio === "MATERIAL" ? "Nom / Descripció de l'Article *" : "Nom de la Màquina/Eina *"}
                  </label>
                  <input
                    type="text"
                    required
                    placeholder={nouArticle.tipus_creacio === "MATERIAL" ? "Ex: Colze Electrosoldable PE-100 90º Ø90" : "Ex: Martell Demolidor BOSCH"}
                    value={nouArticle.nom}
                    onChange={(e) => setNouArticle({ ...nouArticle, nom: e.target.value })}
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs font-medium"
                  />
                </div>
                {nouArticle.tipus_creacio === "MATERIAL" && (
                  <>
                    <div className="col-span-2 grid grid-cols-1 sm:grid-cols-2 gap-3">
                      <div>
                        <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                          Codi de Barres (EAN / Code128, sense QR)
                        </label>
                        <input
                          type="text"
                          placeholder="Ex: 8412345000012"
                          value={nouArticle.codi_barres}
                          onChange={(e) => setNouArticle({ ...nouArticle, codi_barres: e.target.value })}
                          className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs font-mono"
                        />
                      </div>
                      <div>
                        <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                          Proveïdor Habitual (Comandes / Mínim Estoc)
                        </label>
                        <select
                          value={nouArticle.proveidor_id}
                          onChange={(e) => setNouArticle({ ...nouArticle, proveidor_id: e.target.value })}
                          className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs font-medium"
                        >
                          <option value="">Sense proveïdor assignat</option>
                          {proveidors.map((p) => (
                            <option key={p.id} value={p.id}>
                              {p.rao_social} ({p.nif})
                            </option>
                          ))}
                        </select>
                      </div>
                    </div>
                  </>
                )}
                {nouArticle.tipus_creacio === "EINA" && (
                  <div>
                    <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                      Model
                    </label>
                    <input
                      type="text"
                      placeholder="Ex: GBH 5-40 DCE"
                      value={nouArticle.model_eina}
                      onChange={(e) => setNouArticle({ ...nouArticle, model_eina: e.target.value })}
                      className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs font-medium"
                    />
                  </div>
                )}
              </div>

              {nouArticle.tipus_creacio === "EINA" && (
                <div className="grid grid-cols-1 gap-3 border-t border-slate-200 dark:border-slate-800 pt-3">
                  <div>
                    <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                      Data Fi Garantia Fabricant
                    </label>
                    <input
                      type="date"
                      value={nouArticle.data_fi_garantia}
                      onChange={(e) => setNouArticle({ ...nouArticle, data_fi_garantia: e.target.value })}
                      className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs font-medium"
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                      Observacions (Ex: Reparacions realitzades)
                    </label>
                    <textarea
                      rows={2}
                      placeholder="Historial de reparacions, canvis de filtre, etc."
                      value={nouArticle.observacions}
                      onChange={(e) => setNouArticle({ ...nouArticle, observacions: e.target.value })}
                      className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs font-medium"
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                      Incidències Especials
                    </label>
                    <textarea
                      rows={2}
                      placeholder="Peces que fallen sovint, cops, etc."
                      value={nouArticle.incidencies}
                      onChange={(e) => setNouArticle({ ...nouArticle, incidencies: e.target.value })}
                      className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs font-medium"
                    />
                  </div>
                </div>
              )}

              {nouArticle.tipus_creacio === "MATERIAL" && (
                <>
                  <div className="grid grid-cols-3 gap-3">
                    <div>
                      <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                        Unitat Mesura *
                      </label>
                      <select
                        value={nouArticle.unitat_mesura}
                        onChange={(e) => setNouArticle({ ...nouArticle, unitat_mesura: e.target.value })}
                        className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs font-semibold"
                      >
                        {UNITATS_MESURA_CANONIQUES.map((u) => (
                          <option key={u.value} value={u.value}>
                            {u.label}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                        Estoc Mínim
                      </label>
                      <input
                        type="number"
                        min="0"
                        step="0.1"
                        value={nouArticle.estoc_minim}
                        onChange={(e) => setNouArticle({ ...nouArticle, estoc_minim: Number(e.target.value) })}
                        className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs font-mono"
                      />
                    </div>
                    <div>
                      <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                        Estoc Òptim
                      </label>
                      <input
                        type="number"
                        min="0"
                        step="0.1"
                        value={nouArticle.estoc_optim}
                        onChange={(e) => setNouArticle({ ...nouArticle, estoc_optim: Number(e.target.value) })}
                        className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs font-mono"
                      />
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-3 p-3 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-700">
                    <div>
                      <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                        Estoc Inicial
                      </label>
                      <input
                        type="number"
                        min="0"
                        step="any"
                        value={nouArticle.estoc_inicial}
                        onChange={(e) => setNouArticle({ ...nouArticle, estoc_inicial: parseFloat(e.target.value) || 0 })}
                        className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs font-mono font-bold"
                      />
                    </div>
                    <div>
                      <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                        Magatzem Destí Inicial
                      </label>
                      <select
                        value={nouArticle.magatzem_id}
                        onChange={(e) => setNouArticle({ ...nouArticle, magatzem_id: e.target.value })}
                        className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs font-semibold"
                      >
                        <option value="">Nau Central per defecte</option>
                        {magatzems.map((m) => (
                          <option key={m.id} value={m.id}>
                            {m.tipus === "NAU_CENTRAL" ? "🏭 " : "🚐 "}
                            {m.nom}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>
                  <label className="flex items-center gap-2.5 p-2.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50/70 dark:bg-slate-800/40 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={nouArticle.es_material_continu}
                      onChange={(e) => setNouArticle({ ...nouArticle, es_material_continu: e.target.checked })}
                      className="rounded border-slate-300 text-primary focus:ring-primary"
                    />
                    <span className="text-xs font-semibold text-slate-700 dark:text-slate-200">
                      Material continu / a tall (cable, tub, mànega — calcula % merma històric)
                    </span>
                  </label>
                </>
              )}

              {nouArticle.tipus_creacio === "MATERIAL" && (
                esEnginyer ? (
                  <div className="bg-slate-100 dark:bg-slate-800/60 p-3 rounded-xl border border-slate-200 dark:border-slate-700 flex items-center justify-between gap-4">
                    <div>
                      <span className="text-xs font-bold text-slate-700 dark:text-slate-200 block">
                        Preu Venda (€)
                      </span>
                      <span className="text-[11px] text-slate-500">
                        Els costos interns i marges estan reservats a Direcció / Administració.
                      </span>
                    </div>
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      value={nouArticle.preu_venda}
                      onChange={(e) => setNouArticle({ ...nouArticle, preu_venda: parseFloat(e.target.value) || 0 })}
                      className="w-32 px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs font-mono font-bold text-right"
                    />
                  </div>
                ) : (
                <>
                  <div className="grid grid-cols-3 gap-3">
                    <div>
                      <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                        Preu Tarifa (€)
                      </label>
                      <input
                        type="number"
                        step="0.01"
                        required
                        value={nouArticle.preu_cost}
                        onChange={(e) => setNouArticle({ ...nouArticle, preu_cost: parseFloat(e.target.value) || 0 })}
                        className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs font-mono"
                      />
                    </div>
                    <div>
                      <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                        Descompte Prov. (%)
                      </label>
                      <input
                        type="number"
                        step="0.01"
                        value={nouArticle.descompte_proveidor}
                        onChange={(e) => setNouArticle({ ...nouArticle, descompte_proveidor: parseFloat(e.target.value) || 0 })}
                        className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs font-mono"
                      />
                    </div>
                    <div>
                      <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                        Marge Guany (%)
                      </label>
                      <input
                        type="number"
                        step="0.01"
                        value={nouArticle.marge_guanys}
                        onChange={(e) => setNouArticle({ ...nouArticle, marge_guanys: parseFloat(e.target.value) || 0 })}
                        className="w-full px-3 py-2 rounded-xl border border-emerald-300 bg-emerald-50 text-xs font-bold font-mono"
                      />
                    </div>
                  </div>
                  <div className="bg-slate-100 dark:bg-slate-800/60 p-3 rounded-xl border border-slate-200 dark:border-slate-700 flex justify-between items-center">
                    <span className="text-xs font-bold text-slate-600 dark:text-slate-400">Preu Venda (Autocalculat)</span>
                    <span className="text-lg font-black text-emerald-600 font-mono">{nouArticle.preu_venda} €</span>
                  </div>
                </>
                )
              )}

              <div className="pt-3 border-t border-slate-200 dark:border-slate-800 flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setModalNouArticle(false)}
                  className="px-4 py-2 rounded-xl border border-slate-300 dark:border-slate-700 text-slate-600 dark:text-slate-300 text-xs font-medium hover:bg-slate-100 dark:hover:bg-slate-800"
                >
                  Cancel·lar
                </button>
                <button
                  type="submit"
                  disabled={guardant}
                  className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold shadow disabled:opacity-50"
                >
                  {guardant ? "Desant..." : "Desar Article"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
      {/* Modal Editar Article (Fitxa de Producte) */}
      {modalEditarArticle && articleEditant && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-2xl bg-white dark:bg-slate-900 rounded-3xl shadow-2xl border border-slate-200 dark:border-slate-800 overflow-hidden flex flex-col max-h-[90vh]">
            <div className="p-5 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between bg-slate-50 dark:bg-slate-800/50">
              <h3 className="font-bold text-sm text-slate-800 dark:text-slate-100 flex items-center gap-2">
                <Package className="w-4 h-4 text-emerald-600" />
                Fitxa de Producte: {articleEditant.referencia_inventari}
              </h3>
              <button
                onClick={() => setModalEditarArticle(false)}
                className="p-1 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 transition-colors bg-white dark:bg-slate-800 shadow-sm"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            
            <div className="flex-1 overflow-y-auto p-5">
              <form id="form-editar-article" onSubmit={handleDesarEdicio} className="space-y-4">
                {/* Dades Principals */}
                <div className="p-4 bg-slate-50 dark:bg-slate-800/50 rounded-2xl border border-slate-100 dark:border-slate-800 space-y-4">
                  <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Informació General</h4>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-xs font-bold text-slate-600 dark:text-slate-400 mb-1">Referència Inventari</label>
                      <input
                        type="text"
                        value={articleEditant.referencia_inventari}
                        onChange={(e) => setArticleEditant({ ...articleEditant, referencia_inventari: e.target.value })}
                        className="w-full p-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs"
                        required
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-bold text-slate-600 dark:text-slate-400 mb-1">Descripció del Producte</label>
                      <input
                        type="text"
                        value={articleEditant.nom}
                        onChange={(e) => setArticleEditant({ ...articleEditant, nom: e.target.value })}
                        className="w-full p-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs"
                        required
                      />
                    </div>
                    <div className="col-span-2 grid grid-cols-1 sm:grid-cols-2 gap-4">
                      <div>
                        <label className="block text-xs font-bold text-slate-600 dark:text-slate-400 mb-1">
                          Codi de Barres (EAN / Code128, sense QR)
                        </label>
                        <input
                          type="text"
                          placeholder="Ex: 8412345000012"
                          value={articleEditant.codi_barres || ""}
                          onChange={(e) => setArticleEditant({ ...articleEditant, codi_barres: e.target.value })}
                          className="w-full p-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs font-mono"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-bold text-slate-600 dark:text-slate-400 mb-1">
                          Proveïdor Habitual (Comandes / Mínim Estoc)
                        </label>
                        <select
                          value={articleEditant.proveidor_id || ""}
                          onChange={(e) => {
                            const provId = e.target.value || null;
                            const p = proveidors.find((x) => x.id === provId);
                            setArticleEditant({
                              ...articleEditant,
                              proveidor_id: provId,
                              proveidor_nom: p ? p.rao_social : null,
                            });
                          }}
                          className="w-full p-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs font-medium"
                        >
                          <option value="">Sense proveïdor assignat</option>
                          {proveidors.map((p) => (
                            <option key={p.id} value={p.id}>
                              {p.rao_social} ({p.nif})
                            </option>
                          ))}
                        </select>
                        {articleEditant.proveidor_nom && (
                          <p className="text-[11px] text-emerald-600 dark:text-emerald-400 mt-1 font-medium">
                            Proveïdor vinculat: <strong>{articleEditant.proveidor_nom}</strong>
                          </p>
                        )}
                      </div>
                    </div>
                    <div>
                      <label className="block text-xs font-bold text-slate-600 dark:text-slate-400 mb-1">
                        Família del Producte
                      </label>
                      {!creantNovaFamiliaEdit ? (
                        <select
                          value={articleEditant.familia}
                          onChange={(e) => {
                            if (e.target.value === "+_CREAR_NOVA_") {
                              setCreantNovaFamiliaEdit(true);
                              setNovaFamiliaTextEdit("");
                            } else {
                              setArticleEditant({ ...articleEditant, familia: e.target.value });
                            }
                          }}
                          className="w-full p-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs font-semibold"
                        >
                          {totesLesFamilies.map((fam) => (
                            <option key={fam} value={fam}>
                              {fam}
                            </option>
                          ))}
                          {articleEditant.familia && !totesLesFamilies.includes(articleEditant.familia) && (
                            <option value={articleEditant.familia}>{articleEditant.familia}</option>
                          )}
                          <option value="+_CREAR_NOVA_">➕ + Crear nova família...</option>
                        </select>
                      ) : (
                        <div className="flex items-center gap-1.5">
                          <input
                            type="text"
                            autoFocus
                            placeholder="Escriu el nom de la nova família..."
                            value={novaFamiliaTextEdit}
                            onChange={(e) => {
                              setNovaFamiliaTextEdit(e.target.value);
                              setArticleEditant({ ...articleEditant, familia: e.target.value.toUpperCase() });
                            }}
                            className="w-full p-2 rounded-xl border border-emerald-500 bg-emerald-50/40 dark:bg-emerald-950/40 text-xs font-bold uppercase"
                          />
                          <button
                            type="button"
                            onClick={() => {
                              setCreantNovaFamiliaEdit(false);
                            }}
                            className="px-2.5 py-2 rounded-xl bg-slate-200 dark:bg-slate-700 text-xs font-semibold text-slate-700 dark:text-slate-200 shrink-0"
                          >
                            Llista
                          </button>
                        </div>
                      )}
                    </div>
                    <div>
                      <label className="block text-xs font-bold text-slate-600 dark:text-slate-400 mb-1">Unitat de Mesura</label>
                      <select
                        value={normalitzarUnitatMesura(articleEditant.unitat_mesura)}
                        onChange={(e) => setArticleEditant({ ...articleEditant, unitat_mesura: e.target.value })}
                        className="w-full p-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs"
                      >
                        {UNITATS_MESURA_CANONIQUES.map((u) => (
                          <option key={u.value} value={u.value}>
                            {u.label}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>
                </div>

                {/* Dades Econòmiques i Estoc */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="p-4 bg-emerald-50/50 dark:bg-emerald-900/10 rounded-2xl border border-emerald-100 dark:border-emerald-900/30 space-y-4">
                    <h4 className="text-xs font-bold text-emerald-600 dark:text-emerald-500 uppercase tracking-wider mb-2">Control d&apos;Estoc</h4>
                    <div className="grid grid-cols-3 gap-2 text-center p-2 rounded-xl bg-white dark:bg-slate-900 border border-emerald-100 dark:border-emerald-900/40 font-mono">
                      <div>
                        <span className="block text-[10px] text-slate-400">Físic</span>
                        <span className="text-xs font-bold">{articleEditant.estoc_fisic ?? articleEditant.estoc_real ?? 0}</span>
                      </div>
                      <div>
                        <span className="block text-[10px] text-slate-400">Reservat</span>
                        <span className="text-xs font-bold text-amber-600">{articleEditant.estoc_reservat ?? 0}</span>
                      </div>
                      <div>
                        <span className="block text-[10px] text-slate-400">Disponible</span>
                        <span className="text-xs font-black text-emerald-600">{articleEditant.estoc_disponible ?? articleEditant.estoc_real ?? 0}</span>
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="block text-xs font-bold text-slate-600 dark:text-slate-400 mb-1">Mínim</label>
                        <input
                          type="number"
                          step="0.01"
                          value={articleEditant.estoc_minim}
                          onChange={(e) => setArticleEditant({ ...articleEditant, estoc_minim: Number(e.target.value) })}
                          className="w-full p-2 rounded-xl border border-emerald-200 dark:border-emerald-800 bg-white dark:bg-slate-900 text-xs"
                          required
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-bold text-slate-600 dark:text-slate-400 mb-1">Òptim</label>
                        <input
                          type="number"
                          step="0.01"
                          value={articleEditant.estoc_optim}
                          onChange={(e) => setArticleEditant({ ...articleEditant, estoc_optim: Number(e.target.value) })}
                          className="w-full p-2 rounded-xl border border-emerald-200 dark:border-emerald-800 bg-white dark:bg-slate-900 text-xs"
                          required
                        />
                      </div>
                    </div>
                    <label className="flex items-center gap-2 p-2 rounded-xl bg-white dark:bg-slate-900 border border-emerald-100 dark:border-emerald-900/40 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={Boolean(articleEditant.es_material_continu)}
                        onChange={(e) => setArticleEditant({ ...articleEditant, es_material_continu: e.target.checked })}
                        className="rounded border-slate-300 text-primary focus:ring-primary"
                      />
                      <span className="text-[11px] font-semibold text-slate-700 dark:text-slate-200">
                        Material continu / a tall (aplica suggeriment de merma històric FR-008)
                      </span>
                    </label>
                  </div>
                  
                  <div className="p-4 bg-primary/5 rounded-2xl border border-primary/20 space-y-4">
                    <h4 className="text-xs font-bold text-primary uppercase tracking-wider mb-2">
                      {esEnginyer ? "Tarifa PVP (Accés Tècnic)" : "Preus i Costos"}
                    </h4>
                    <div className="grid grid-cols-2 gap-3">
                      {!esEnginyer && (
                        <>
                          <div>
                            <label className="block text-xs font-bold text-slate-600 dark:text-slate-400 mb-1">Preu Cost (€)</label>
                            <input
                              type="number"
                              step="0.01"
                              value={articleEditant.preu_cost ?? 0}
                              onChange={(e) => {
                                const pc = Number(e.target.value) || 0;
                                const costReal = pc * (1 - (Number(articleEditant.descompte_proveidor ?? 0) / 100));
                                const preuVendaCalculat = costReal * (1 + (Number(articleEditant.marge_guanys ?? 0) / 100));
                                setArticleEditant({ ...articleEditant, preu_cost: pc, preu_venda: parseFloat(preuVendaCalculat.toFixed(2)) });
                              }}
                              className="w-full p-2 rounded-xl border border-primary/30 bg-white dark:bg-slate-900 text-xs"
                              required
                            />
                          </div>
                          <div>
                            <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">Desc. Proveïdor (%)</label>
                            <input
                              type="number"
                              step="0.01"
                              value={articleEditant.descompte_proveidor ?? 0}
                              onChange={(e) => {
                                const desc = Number(e.target.value) || 0;
                                const costReal = Number(articleEditant.preu_cost ?? 0) * (1 - (desc / 100));
                                const preuVendaCalculat = costReal * (1 + (Number(articleEditant.marge_guanys ?? 0) / 100));
                                setArticleEditant({ ...articleEditant, descompte_proveidor: desc, preu_venda: parseFloat(preuVendaCalculat.toFixed(2)) });
                              }}
                              className="w-full p-2 rounded-xl border border-primary/30 bg-white dark:bg-slate-900 text-xs"
                            />
                          </div>
                          <div>
                            <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">Marge Guanys (%)</label>
                            <input
                              type="number"
                              step="0.01"
                              value={articleEditant.marge_guanys ?? 0}
                              onChange={(e) => {
                                const marge = Number(e.target.value) || 0;
                                const costReal = Number(articleEditant.preu_cost ?? 0) * (1 - (Number(articleEditant.descompte_proveidor ?? 0) / 100));
                                const preuVendaCalculat = costReal * (1 + (marge / 100));
                                setArticleEditant({ ...articleEditant, marge_guanys: marge, preu_venda: parseFloat(preuVendaCalculat.toFixed(2)) });
                              }}
                              className="w-full p-2 rounded-xl border border-primary/30 bg-white dark:bg-slate-900 text-xs"
                            />
                          </div>
                        </>
                      )}
                      <div className="col-span-2">
                        <label className="block text-xs font-bold text-slate-600 dark:text-slate-400 mb-1">Preu Venda (€) (Càlcul P.V.P.)</label>
                        <input
                          type="number"
                          step="0.01"
                          value={articleEditant.preu_venda}
                          onChange={(e) => setArticleEditant({ ...articleEditant, preu_venda: Number(e.target.value) })}
                          className="w-full p-2 rounded-xl border border-primary/40 bg-primary/10 font-bold text-primary text-xs"
                          required
                        />
                      </div>
                    </div>
                  </div>
                </div>
              </form>
            </div>
            
            <div className="p-5 border-t border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900 flex justify-end gap-3">
              <button
                type="button"
                onClick={() => setModalEditarArticle(false)}
                className="px-4 py-2 rounded-xl border border-slate-300 dark:border-slate-700 text-slate-700 dark:text-slate-300 text-xs font-bold hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                disabled={guardant}
              >
                Cancel·lar
              </button>
              <button
                type="submit"
                form="form-editar-article"
                disabled={guardant}
                className="px-6 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold shadow-md shadow-emerald-500/20 disabled:opacity-50 flex items-center gap-2 transition-all"
              >
                {guardant ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    <span>Desant...</span>
                  </>
                ) : (
                  <>
                    <CheckCircle2 className="w-4 h-4" />
                    <span>Desar Canvis</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}


      {/* Modal Checkout Eina */}
      {modalCheckout && einaCheckout && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-sm bg-white dark:bg-slate-900 rounded-3xl shadow-2xl border border-slate-200 dark:border-slate-800 overflow-hidden">
            <div className="px-5 py-4 border-b border-slate-200 dark:border-slate-800 flex justify-between items-center bg-blue-50 dark:bg-blue-900/20">
              <h2 className="text-sm font-bold text-blue-900 dark:text-blue-100">Check-Out d'Eina (Assignació)</h2>
              <button onClick={() => { setModalCheckout(false); setEinaCheckout(null); }} className="text-slate-400 hover:text-slate-600">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-5 space-y-4">
              <div className="p-3 bg-slate-50 dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700">
                <p className="text-xs font-bold text-slate-700 dark:text-slate-300">{einaCheckout.nom}</p>
                <p className="text-[10px] font-mono text-slate-500 mt-1">SN: {einaCheckout.numero_serie}</p>
              </div>

              {/* Selector Tipus de Custòdia: Treballador o Vehicle */}
              <div className="flex bg-slate-100 dark:bg-slate-800 p-1 rounded-xl">
                <button
                  type="button"
                  onClick={() => setCheckoutTargetTipus("OPERARI")}
                  className={`flex-1 py-1.5 text-xs font-bold rounded-lg transition-colors ${
                    checkoutTargetTipus === "OPERARI"
                      ? "bg-white dark:bg-slate-900 text-blue-600 dark:text-blue-400 shadow-sm"
                      : "text-slate-500 hover:text-slate-800"
                  }`}
                >
                  👤 Treballador
                </button>
                <button
                  type="button"
                  onClick={() => setCheckoutTargetTipus("VEHICLE")}
                  className={`flex-1 py-1.5 text-xs font-bold rounded-lg transition-colors ${
                    checkoutTargetTipus === "VEHICLE"
                      ? "bg-white dark:bg-slate-900 text-purple-600 dark:text-purple-400 shadow-sm"
                      : "text-slate-500 hover:text-slate-800"
                  }`}
                >
                  🚐 Vehicle / Flota
                </button>
              </div>

              {checkoutTargetTipus === "OPERARI" ? (
                <div>
                  <label className="block text-xs font-bold text-slate-600 dark:text-slate-400 mb-1">
                    Assignar a l'Operari / Cap de Colla *
                  </label>
                  <select
                    value={selectedOperari}
                    onChange={(e) => setSelectedOperari(e.target.value)}
                    className="w-full p-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-xs font-semibold"
                  >
                    <option value="">-- Selecciona un operari --</option>
                    {operaris.map(op => (
                      <option key={op.id} value={op.id}>{op.nom} {op.cognoms}</option>
                    ))}
                  </select>
                </div>
              ) : (
                <div>
                  <label className="block text-xs font-bold text-slate-600 dark:text-slate-400 mb-1">
                    Assignar al Vehicle / Furgoneta (Dotació) *
                  </label>
                  <select
                    value={selectedVehicleMagatzemId}
                    onChange={(e) => setSelectedVehicleMagatzemId(e.target.value)}
                    className="w-full p-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-xs font-semibold"
                  >
                    <option value="">-- Selecciona un vehicle --</option>
                    {magatzems.filter(m => m.tipus === "FURGONETA").map(m => (
                      <option key={m.id} value={m.id}>
                        {m.nom} {m.vehicle_matricula ? `[${m.vehicle_matricula}]` : ""}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              <div className="flex justify-end gap-2 pt-2">
                <button
                  onClick={() => { setModalCheckout(false); setEinaCheckout(null); }}
                  className="px-4 py-2 rounded-xl border border-slate-300 dark:border-slate-700 text-slate-600 dark:text-slate-300 text-xs font-medium hover:bg-slate-100"
                >
                  Cancel·lar
                </button>
                <button
                  onClick={handleCheckout}
                  disabled={checkoutTargetTipus === "OPERARI" ? !selectedOperari : !selectedVehicleMagatzemId}
                  className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold shadow disabled:opacity-50"
                >
                  Confirmar Entrega
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Modal Traspàs d'Estoc Nau Central <-> Vehicles (T026) */}
      {modalTraspas && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-md bg-white dark:bg-slate-900 rounded-3xl shadow-2xl border border-slate-200 dark:border-slate-800 overflow-hidden">
            <div className="px-5 py-4 border-b border-slate-200 dark:border-slate-800 flex justify-between items-center bg-blue-50 dark:bg-blue-900/20">
              <div className="flex items-center gap-2">
                <Truck className="w-5 h-5 text-blue-600 dark:text-blue-400" />
                <div>
                  <h2 className="text-sm font-bold text-slate-900 dark:text-white">
                    Traspàs d'Estoc (Nau Central ⇄ Vehicles)
                  </h2>
                  <p className="text-[10px] text-slate-500">Spec 004 & Spec 01 (T026)</p>
                </div>
              </div>
              <button
                onClick={() => setModalTraspas(false)}
                className="text-slate-400 hover:text-slate-600"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleExecutarTraspas} className="p-5 space-y-4">
              <div>
                <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                  Article o Material *
                </label>
                <select
                  value={traspasArticleId}
                  onChange={(e) => setTraspasArticleId(e.target.value)}
                  className="w-full p-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-xs font-semibold"
                  required
                >
                  <option value="">-- Selecciona un article --</option>
                  {articles.map((art) => (
                    <option key={art.id} value={art.id}>
                      {art.referencia_inventari} - {art.nom} (Disp.: {art.estoc_disponible ?? art.estoc_real ?? 0} {art.unitat_mesura})
                    </option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                    Origen (De) *
                  </label>
                  <select
                    value={traspasOrigenId}
                    onChange={(e) => setTraspasOrigenId(e.target.value)}
                    className="w-full p-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-xs font-semibold"
                    required
                  >
                    <option value="">-- Origen --</option>
                    {magatzems.map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.tipus === "NAU_CENTRAL" ? "🏭 " : "🚐 "}
                        {m.nom}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                    Destí (A) *
                  </label>
                  <select
                    value={traspasDestiId}
                    onChange={(e) => setTraspasDestiId(e.target.value)}
                    className="w-full p-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-xs font-semibold"
                    required
                  >
                    <option value="">-- Destí --</option>
                    {magatzems.map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.tipus === "NAU_CENTRAL" ? "🏭 " : "🚐 "}
                        {m.nom}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                  Quantitat a Moure *
                </label>
                <input
                  type="number"
                  min="0.01"
                  step="any"
                  value={traspasQuantitat}
                  onChange={(e) => setTraspasQuantitat(parseFloat(e.target.value) || 0)}
                  className="w-full p-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-xs font-mono font-bold"
                  required
                />
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-slate-100 dark:border-slate-800">
                <button
                  type="button"
                  onClick={() => setModalTraspas(false)}
                  className="px-4 py-2 rounded-xl border border-slate-300 dark:border-slate-700 text-slate-600 dark:text-slate-300 text-xs font-medium hover:bg-slate-100"
                >
                  Cancel·lar
                </button>
                <button
                  type="submit"
                  disabled={traspasant || !traspasArticleId || !traspasOrigenId || !traspasDestiId || traspasOrigenId === traspasDestiId}
                  className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold shadow flex items-center gap-1.5 disabled:opacity-50"
                >
                  {traspasant ? (
                    <>
                      <RefreshCw className="w-4 h-4 animate-spin" />
                      <span>Processant Traspàs...</span>
                    </>
                  ) : (
                    <>
                      <CheckCircle2 className="w-4 h-4" />
                      <span>Confirmar Traspàs</span>
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal Ajust Manual d'Estoc */}
      {modalAjustEstoc && ajustArticle && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-md bg-white dark:bg-slate-900 rounded-3xl shadow-2xl border border-slate-200 dark:border-slate-800 overflow-hidden">
            <div className="px-5 py-4 border-b border-slate-200 dark:border-slate-800 flex justify-between items-center bg-slate-50 dark:bg-slate-800/50">
              <h2 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2">
                <SlidersHorizontal className="w-4 h-4 text-primary" />
                <span>Ajustar Estoc: {ajustArticle.referencia_inventari}</span>
              </h2>
              <button
                type="button"
                onClick={() => {
                  setModalAjustEstoc(false);
                  setAjustArticle(null);
                }}
                className="text-slate-400 hover:text-slate-600"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleExecutarAjustEstoc} className="p-5 space-y-4">
              <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 text-xs">
                <p className="font-bold text-slate-900 dark:text-white">{ajustArticle.nom}</p>
                <p className="font-mono text-[11px] text-slate-500 mt-0.5">
                  Disponible actual: <strong>{ajustArticle.estoc_disponible ?? ajustArticle.estoc_real ?? 0}</strong> {ajustArticle.unitat_mesura}
                </p>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                    Magatzem *
                  </label>
                  <select
                    value={ajustMagatzemId}
                    onChange={(e) => setAjustMagatzemId(e.target.value)}
                    required
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs font-semibold"
                  >
                    <option value="">Selecciona nau o furgoneta...</option>
                    {magatzems.map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.tipus === "NAU_CENTRAL" ? "🏭 " : "🚐 "}
                        {m.nom}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                    Tipus Moviment *
                  </label>
                  <select
                    value={ajustTipus}
                    onChange={(e) => setAjustTipus(e.target.value as "ENTRADA" | "SORTIDA" | "RESERVA")}
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs font-semibold"
                  >
                    <option value="ENTRADA">ENTRADA (+ Físic)</option>
                    <option value="SORTIDA">SORTIDA (- Físic)</option>
                    <option value="RESERVA">RESERVA (+ Reservat)</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                    Quantitat ({ajustArticle.unitat_mesura}) *
                  </label>
                  <input
                    type="number"
                    min="0.01"
                    step="any"
                    required
                    value={ajustQuantitat}
                    onChange={(e) => setAjustQuantitat(parseFloat(e.target.value) || 0)}
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs font-mono font-bold"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                    Ubicació Passadís
                  </label>
                  <input
                    type="text"
                    placeholder="Ex: P2-R4"
                    value={ajustUbicacio}
                    onChange={(e) => setAjustUbicacio(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs font-mono"
                  />
                </div>
              </div>

              <div>
                <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                  Notes del Moviment
                </label>
                <input
                  type="text"
                  placeholder="Motiu regularització o inventari..."
                  value={ajustNotes}
                  onChange={(e) => setAjustNotes(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-slate-100 dark:border-slate-800">
                <button
                  type="button"
                  onClick={() => {
                    setModalAjustEstoc(false);
                    setAjustArticle(null);
                  }}
                  className="px-4 py-2 rounded-xl border border-slate-300 dark:border-slate-700 text-xs font-medium text-slate-600 dark:text-slate-300"
                >
                  Cancel·lar
                </button>
                <button
                  type="submit"
                  disabled={ajustantEstoc || !ajustMagatzemId || ajustQuantitat <= 0}
                  className="px-4 py-2 rounded-xl bg-primary hover:opacity-90 text-white text-xs font-bold shadow disabled:opacity-50"
                >
                  {ajustantEstoc ? "Desant..." : "Confirmar Moviment"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal Editar Eina de Custòdia */}
      {modalEditarEina && einaEditant && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-lg bg-white dark:bg-slate-900 rounded-3xl shadow-2xl border border-slate-200 dark:border-slate-800 overflow-hidden">
            <div className="px-5 py-4 border-b border-slate-200 dark:border-slate-800 flex justify-between items-center bg-slate-50 dark:bg-slate-800/50">
              <h2 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2">
                <Wrench className="w-4 h-4 text-primary" />
                <span>Editar Fitxa d&apos;Eina ({einaEditant.numero_serie})</span>
              </h2>
              <button
                type="button"
                onClick={() => {
                  setModalEditarEina(false);
                  setEinaEditant(null);
                }}
                className="text-slate-400 hover:text-slate-600"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleDesarEina} className="p-5 space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                    Ref. Fabricant
                  </label>
                  <input
                    type="text"
                    value={einaEditant.referencia_fabricant || ""}
                    onChange={(e) => setEinaEditant({ ...einaEditant, referencia_fabricant: e.target.value })}
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs font-mono"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                    Número de Sèrie *
                  </label>
                  <input
                    type="text"
                    required
                    value={einaEditant.numero_serie || ""}
                    onChange={(e) => setEinaEditant({ ...einaEditant, numero_serie: e.target.value })}
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs font-mono font-bold"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                    Nom Màquina / Eina *
                  </label>
                  <input
                    type="text"
                    required
                    value={einaEditant.nom || ""}
                    onChange={(e) => setEinaEditant({ ...einaEditant, nom: e.target.value })}
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs font-medium"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                    Model
                  </label>
                  <input
                    type="text"
                    value={einaEditant.model || ""}
                    onChange={(e) => setEinaEditant({ ...einaEditant, model: e.target.value })}
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs"
                  />
                </div>
              </div>

              <div>
                <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                  Data Fi Garantia
                </label>
                <input
                  type="date"
                  value={einaEditant.data_fi_garantia || ""}
                  onChange={(e) => setEinaEditant({ ...einaEditant, data_fi_garantia: e.target.value })}
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs"
                />
              </div>

              <div>
                <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                  Observacions / Manteniment
                </label>
                <textarea
                  rows={2}
                  value={einaEditant.observacions || ""}
                  onChange={(e) => setEinaEditant({ ...einaEditant, observacions: e.target.value })}
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs"
                />
              </div>

              <div>
                <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                  Incidències
                </label>
                <textarea
                  rows={2}
                  value={einaEditant.incidencies || ""}
                  onChange={(e) => setEinaEditant({ ...einaEditant, incidencies: e.target.value })}
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-slate-100 dark:border-slate-800">
                <button
                  type="button"
                  onClick={() => {
                    setModalEditarEina(false);
                    setEinaEditant(null);
                  }}
                  className="px-4 py-2 rounded-xl border border-slate-300 dark:border-slate-700 text-xs font-medium text-slate-600 dark:text-slate-300"
                >
                  Cancel·lar
                </button>
                <button
                  type="submit"
                  disabled={guardantEina}
                  className="px-4 py-2 rounded-xl bg-primary hover:opacity-90 text-white text-xs font-bold shadow disabled:opacity-50"
                >
                  {guardantEina ? "Desant..." : "Desar Eina"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal Esborrany d'Email de Recompra al Proveïdor (HITL FR-010) */}
      {modalEmailRecompra && !esEnginyer && (
        <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl w-full max-w-2xl shadow-2xl overflow-hidden">
            <div className="p-4 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between bg-slate-50 dark:bg-slate-800/50">
              <div className="flex items-center gap-2">
                <Mail className="w-4 h-4 text-primary" />
                <div>
                  <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                    {modalEmailRecompra.titol}
                  </h3>
                  <p className="text-[11px] text-slate-500">
                    Revisió humana obligatòria (HITL): edita el correu abans d&apos;aprovar l&apos;enviament al proveïdor.
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setModalEmailRecompra(null)}
                className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 dark:hover:text-slate-200"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="p-5 space-y-4 max-h-[75vh] overflow-y-auto">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                    Proveïdor
                  </label>
                  <select
                    value={modalEmailRecompra.proveidorId}
                    onChange={(e) => {
                      const provId = e.target.value;
                      const prov = proveidors.find((p: any) => p.id === provId);
                      setModalEmailRecompra({
                        ...modalEmailRecompra,
                        proveidorId: provId,
                        destinatariEmail: prov?.email || modalEmailRecompra.destinatariEmail,
                      });
                    }}
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs"
                  >
                    <option value="">Selecciona proveïdor...</option>
                    {proveidors.map((p: any) => (
                      <option key={p.id} value={p.id}>
                        {p.nom} {p.email ? `(${p.email})` : ""}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                    Email destinatari *
                  </label>
                  <input
                    type="email"
                    required
                    placeholder="comandes@proveidor.cat"
                    value={modalEmailRecompra.destinatariEmail}
                    onChange={(e) =>
                      setModalEmailRecompra({ ...modalEmailRecompra, destinatariEmail: e.target.value })
                    }
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs font-mono"
                  />
                </div>
              </div>

              <div>
                <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                  Assumpte
                </label>
                <input
                  type="text"
                  value={modalEmailRecompra.assumpte}
                  onChange={(e) =>
                    setModalEmailRecompra({ ...modalEmailRecompra, assumpte: e.target.value })
                  }
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs font-semibold"
                />
              </div>

              <div>
                <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                  Cos del missatge
                </label>
                <textarea
                  rows={8}
                  value={modalEmailRecompra.cosMissatge}
                  onChange={(e) =>
                    setModalEmailRecompra({ ...modalEmailRecompra, cosMissatge: e.target.value })
                  }
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs font-mono leading-relaxed"
                />
              </div>
            </div>

            <div className="p-4 border-t border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900 flex flex-wrap items-center justify-between gap-2">
              <button
                type="button"
                onClick={() => setModalEmailRecompra(null)}
                disabled={enviantEmail}
                className="px-4 py-2 rounded-xl border border-slate-300 dark:border-slate-700 text-xs font-medium text-slate-600 dark:text-slate-300"
              >
                Cancel·lar
              </button>
              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  disabled={enviantEmail}
                  onClick={() => handleEnviarEmailRecompra("MAILTO")}
                  className="px-4 py-2 rounded-xl border border-primary/40 bg-primary/10 hover:bg-primary/20 text-primary text-xs font-bold inline-flex items-center gap-1.5 disabled:opacity-50"
                >
                  <ExternalLink className="w-3.5 h-3.5" />
                  <span>Aprovar i Obrir Correu (mailto:)</span>
                </button>
                <button
                  type="button"
                  disabled={enviantEmail}
                  onClick={() => handleEnviarEmailRecompra("SMTP")}
                  className="px-4 py-2 rounded-xl bg-primary hover:opacity-90 text-white text-xs font-bold shadow inline-flex items-center gap-1.5 disabled:opacity-50"
                >
                  <Send className="w-3.5 h-3.5" />
                  <span>{enviantEmail ? "Enviant..." : "Aprovar i Enviar per SMTP"}</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}

export default function GestioMagatzemPage() {
  return (
    <Suspense
      fallback={
        <div className="flex-1 flex flex-col items-center justify-center p-12 text-center text-xs text-slate-500">
          Carregant magatzem i alertes d&apos;estoc...
        </div>
      }
    >
      <MagatzemContent />
    </Suspense>
  );
}
