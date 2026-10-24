"use client";

import React, { useState, useEffect } from "react";
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
} from "lucide-react";
import { apiFetch, getAuthToken, getApiBaseUrl, extractTenantId } from "@/lib/api";
import { useGestio } from "@/lib/gestio-context";

interface Article {
  id: string;
  referencia_inventari: string;
  nom: string;
  unitat_mesura: string;
  familia: string;
  estoc_optim: number;
  estoc_minim: number;
  preu_cost: number;
  descompte_proveidor: number;
  marge_guanys: number;
  preu_venda: number;
  proveidor_id?: string | null;
  proveidor_nom?: string | null;
  actiu?: boolean;
  es_lot_caducable?: boolean;
  estoc_real?: number;
}

interface MagatzemItem {
  id: string;
  nom: string;
  tipus: "NAU_CENTRAL" | "FURGONETA";
  vehicle_id?: string | null;
  vehicle_matricula?: string | null;
  actiu: boolean;
}

export default function GestioMagatzemPage() {
  const { rolActiu } = useGestio();
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
  const [activeTab, setActiveTab] = useState<"MATERIALS" | "EINES">("MATERIALS");
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
    nom: "",
    numero_serie: "",
    model_eina: "",
    data_fi_garantia: "",
    observacions: "",
    incidencies: "",
    unitat_mesura: "UNITAT",
    familia: "TUBERIA",
    estoc_optim: 10,
    estoc_minim: 2,
    preu_cost: 0,
    descompte_proveidor: 0,
    marge_guanys: 0,
    preu_venda: 0,
    es_lot_caducable: false,
    proveidor_id: "",
  });

  // Efecte per autocalcular el preu de venda
  useEffect(() => {
    if (nouArticle.tipus_creacio === "MATERIAL") {
      const costReal = nouArticle.preu_cost * (1 - (nouArticle.descompte_proveidor / 100));
      const preuVendaCalculat = costReal * (1 + (nouArticle.marge_guanys / 100));
      setNouArticle(prev => ({ ...prev, preu_venda: parseFloat(preuVendaCalculat.toFixed(2)) }));
    }
  }, [nouArticle.preu_cost, nouArticle.descompte_proveidor, nouArticle.marge_guanys, nouArticle.tipus_creacio]);

  const carregarArticles = async (magId?: string) => {
    setLoading(true);
    setError(null);
    const targetMagId = magId !== undefined ? magId : selectedMagatzemId;
    const articlesQuery = targetMagId && targetMagId !== "TOTS"
      ? `/gestio/magatzem/articles?magatzem_id=${targetMagId}`
      : "/gestio/magatzem/articles";
    const einesQuery = targetMagId && targetMagId !== "TOTS"
      ? `/gestio/magatzem/eines?magatzem_id=${targetMagId}`
      : "/gestio/magatzem/eines";

    try {
      const [articlesData, einesData, operarisData, configData, proveidorsData, magatzemsData] = await Promise.all([
        apiFetch<Article[]>(articlesQuery).catch(() => []),
        apiFetch<any[]>(einesQuery).catch(() => []),
        apiFetch<any[]>("/gestio/operaris").catch(() => []),
        apiFetch<any>("/gestio/configuracio/empresa").catch(() => null),
        apiFetch<any[]>("/gestio/proveidors").catch(() => []),
        apiFetch<MagatzemItem[]>("/gestio/magatzem/magatzems").catch(() => [])
      ]);
      setArticles(articlesData || []);
      setEines(einesData || []);
      setOperaris(operarisData || []);
      setProveidors(proveidorsData || []);
      if (Array.isArray(magatzemsData) && magatzemsData.length > 0) {
        setMagatzems(magatzemsData);
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
          nom: articleEditant.nom,
          unitat_mesura: articleEditant.unitat_mesura,
          familia: articleEditant.familia,
          estoc_optim: Number(articleEditant.estoc_optim),
          estoc_minim: Number(articleEditant.estoc_minim),
          preu_cost: Number(articleEditant.preu_cost),
          descompte_proveidor: Number(articleEditant.descompte_proveidor),
          marge_guanys: Number(articleEditant.marge_guanys),
          preu_venda: Number(articleEditant.preu_venda),
          es_lot_caducable: articleEditant.es_lot_caducable || false,
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
    setArticleEditant({ ...art });
    setModalEditarArticle(true);
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
            nom: nouArticle.nom,
            unitat_mesura: nouArticle.unitat_mesura,
            familia: nouArticle.familia,
            es_lot_caducable: nouArticle.es_lot_caducable,
            estoc_optim: Number(nouArticle.estoc_optim),
            estoc_minim: Number(nouArticle.estoc_minim),
            preu_cost: Number(nouArticle.preu_cost),
            descompte_proveidor: Number(nouArticle.descompte_proveidor),
            marge_guanys: Number(nouArticle.marge_guanys),
            preu_venda: Number(nouArticle.preu_venda),
            proveidor_id: nouArticle.proveidor_id || null,
          }),
        });
      }
      setModalNouArticle(false);
      setNouArticle({
        tipus_creacio: "MATERIAL",
        referencia_inventari: "",
        nom: "",
        numero_serie: "",
        model_eina: "",
        data_fi_garantia: "",
        observacions: "",
        incidencies: "",
        unitat_mesura: "UNITAT",
        familia: "TUBERIA",
        estoc_optim: 10,
        estoc_minim: 2,
        preu_cost: 0,
        descompte_proveidor: 0,
        marge_guanys: 0,
        preu_venda: 0,
        es_lot_caducable: false,
        proveidor_id: "",
      });
      await carregarArticles();
    } catch (err: any) {
      setError(err.message || "Error al crear l'article");
    } finally {
      setGuardant(false);
    }
  };

  const articlesFiltrats = articles.filter((a) => {
    const coincideixCerca =
      a.nom.toLowerCase().includes(filtreCerca.toLowerCase()) ||
      a.referencia_inventari.toLowerCase().includes(filtreCerca.toLowerCase());
    const coincideixFamilia = filtreFamilia === "TOTS" || a.familia === filtreFamilia;
    return coincideixCerca && coincideixFamilia;
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
              placeholder="Cercar referència o nom..."
              className="pl-9 pr-3 py-1.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-xs font-medium focus:outline-none focus:border-emerald-600 w-48"
            />
          </div>

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
              className="px-3 py-1.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold flex items-center gap-1 shadow transition-all"
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>Entrada Assistida IA</span>
            </button>
          )}

          <button
            onClick={() => setModalNouArticle(true)}
            className="px-3 py-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold flex items-center gap-1 shadow transition-all"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Nou Article</span>
          </button>
        </div>
      </div>

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
            <RefreshCw className="w-6 h-6 animate-spin text-emerald-600 mb-2" />
            <p className="text-xs text-slate-500">Carregant catàleg de magatzem...</p>
          </div>
        ) : articles.length === 0 ? (
          <div className="flex-1 flex flex-col items-center justify-center p-12 text-center bg-white dark:bg-slate-900 rounded-2xl border border-dashed border-slate-300 dark:border-slate-800 my-auto shadow-sm">
            <div className="w-14 h-14 rounded-full bg-emerald-50 dark:bg-emerald-950 text-emerald-600 dark:text-emerald-400 flex items-center justify-center mb-3">
              <Package className="w-7 h-7" />
            </div>
            <h3 className="text-base font-bold text-slate-800 dark:text-slate-100">
              Magatzem central sense articles
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 max-w-xs">
              Estat Dia-0: Registra el primer article o eina per començar a gestionar l'estoc i els moviments.
            </p>
            <button
              onClick={() => setModalNouArticle(true)}
              className="mt-4 px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold shadow"
            >
              + Donar d'Alta Article
            </button>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="flex space-x-2 border-b border-slate-200 dark:border-slate-800 pb-2">
              <button
                onClick={() => setActiveTab("MATERIALS")}
                className={`px-4 py-2 rounded-lg text-xs font-bold transition-colors ${
                  activeTab === "MATERIALS"
                    ? "bg-slate-800 text-white dark:bg-slate-100 dark:text-slate-900"
                    : "bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-400"
                }`}
              >
                Catàleg de Materials
              </button>
              <button
                onClick={() => setActiveTab("EINES")}
                className={`px-4 py-2 rounded-lg text-xs font-bold transition-colors flex items-center gap-2 ${
                  activeTab === "EINES"
                    ? "bg-blue-600 text-white"
                    : "bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-400"
                }`}
              >
                <Wrench className="w-3.5 h-3.5" /> Inventari d'Eines
              </button>
            </div>

            {/* Targetes de Resum */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm flex items-center justify-between">
                <div>
                  <p className="text-[10px] font-mono uppercase text-slate-400 font-bold">Total Articles Catàleg</p>
                  <h3 className="text-xl font-black text-slate-800 dark:text-slate-100 mt-0.5">
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
                  <h3 className="text-xl font-black text-emerald-600 dark:text-emerald-400 mt-0.5">
                    {new Set(articles.map((a) => a.familia)).size}
                  </h3>
                </div>
                <div className="w-10 h-10 rounded-xl bg-emerald-50 dark:bg-emerald-950/40 text-emerald-600 flex items-center justify-center">
                  <Layers className="w-5 h-5" />
                </div>
              </div>

              <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm flex items-center justify-between">
                <div>
                  <p className="text-[10px] font-mono uppercase text-slate-400 font-bold">Unitats de Mesura</p>
                  <h3 className="text-xl font-black text-blue-600 dark:text-blue-400 mt-0.5">
                    {new Set(articles.map((a) => a.unitat_mesura)).size}
                  </h3>
                </div>
                <div className="w-10 h-10 rounded-xl bg-blue-50 dark:bg-blue-950/40 text-blue-600 flex items-center justify-center">
                  <Wrench className="w-5 h-5" />
                </div>
              </div>
            </div>

            {/* Taula d'articles */}
              <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
              {activeTab === "MATERIALS" ? (
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="bg-slate-50 dark:bg-slate-800/60 border-b border-slate-200 dark:border-slate-800 font-bold text-slate-600 dark:text-slate-300">
                      <th className="p-3">Ref. Inventari</th>
                      <th className="p-3">Descripció Article</th>
                      <th className="p-3">Proveïdor</th>
                      <th className="p-3">Família</th>
                      <th className="p-3">Unitat</th>
                      <th className="p-3 text-right">Estoc Real</th>
                      <th className="p-3 text-right">Estoc Mínim</th>
                      <th className="p-3 text-right">Estoc Òptim</th>
                      <th className="p-3 text-right">Preu Cost</th>
                      <th className="p-3 text-right">Preu Venda</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                    {articlesFiltrats.map((art) => (
                      <tr key={art.id} onClick={() => obrirFitxa(art)} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/40 transition-colors cursor-pointer">
                        <td className="p-3 font-mono font-bold text-emerald-700 dark:text-emerald-400">
                          {art.referencia_inventari}
                        </td>
                        <td className="p-3 font-medium text-slate-900 dark:text-white">
                          {art.nom}
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
                        <td className="p-3 text-right font-mono">
                          <span
                            className={`px-2 py-1 rounded-lg font-bold ${
                              art.estoc_real && art.estoc_real <= art.estoc_minim
                                ? "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400"
                                : "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300"
                            }`}
                          >
                            {art.estoc_real ?? 0}
                          </span>
                        </td>
                        <td className="p-3 text-right font-mono text-slate-400">
                          {art.estoc_minim}
                        </td>
                        <td className="p-3 text-right font-mono text-slate-400">
                          {art.estoc_optim}
                        </td>
                        <td className="p-3 text-right font-mono text-slate-500">
                          {art.preu_cost?.toFixed(2)} €
                        </td>
                        <td className="p-3 text-right font-mono font-bold text-emerald-600 dark:text-emerald-400">
                          {art.preu_venda?.toFixed(2)} €
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="bg-blue-50 dark:bg-blue-900/20 border-b border-blue-100 dark:border-blue-900/40 font-bold text-blue-700 dark:text-blue-400">
                      <th className="p-3">Ref. Fabricant</th>
                      <th className="p-3">Nom Màquina / Model</th>
                      <th className="p-3 font-mono">Nº Sèrie</th>
                      <th className="p-3">Estat</th>
                      <th className="p-3">Fi Garantia</th>
                      <th className="p-3 text-right">Custòdia (Check-in/out)</th>
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
                          {eina.estat === "DISPONIBLE" ? (
                            <button
                              onClick={() => { setEinaCheckout(eina); setModalCheckout(true); }}
                              className="px-3 py-1 rounded-lg bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-400 text-[10px] font-bold hover:bg-blue-200 transition-colors"
                            >
                              Check-Out 📤
                            </button>
                          ) : (eina.estat === "CUSTODIADA" || eina.estat === "EN_VEHICLE") ? (
                            <button
                              onClick={() => handleCheckin(eina.id)}
                              className="px-3 py-1 rounded-lg bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-400 text-[10px] font-bold hover:bg-emerald-200 transition-colors"
                            >
                              Check-In 📥
                            </button>
                          ) : null}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
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
                <Sparkles className="w-4 h-4 text-indigo-600" />
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
                      className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold shadow disabled:opacity-50"
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
                        <Building className="w-4 h-4 text-indigo-600" />
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
                          className="w-full px-2.5 py-1.5 rounded-xl border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 text-xs font-mono font-bold text-indigo-700 dark:text-indigo-400"
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
                      <Layers className="w-3.5 h-3.5 text-indigo-600" />
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
                      className="px-3 py-1 rounded-xl bg-indigo-50 hover:bg-indigo-100 dark:bg-indigo-950/50 dark:hover:bg-indigo-900/60 text-indigo-700 dark:text-indigo-300 text-xs font-bold flex items-center gap-1 border border-indigo-200 dark:border-indigo-800 transition-colors"
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
                                {costNetUnitari.toFixed(2)} €
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

                    <div className="flex gap-2">
                      <button
                        onClick={() => setResultatOcr(null)}
                        className="px-4 py-2 rounded-xl border border-slate-300 dark:border-slate-700 text-slate-600 dark:text-slate-300 text-xs font-medium hover:bg-slate-100 dark:hover:bg-slate-800"
                        disabled={processantOcr}
                      >
                        Tornar
                      </button>
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
                  <div className="col-span-2">
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
                    <option value="UNITAT">Unitat (un)</option>
                    <option value="METRES_LINEALS">Metres Lineals (m)</option>
                    <option value="KG">Quilograms (kg)</option>
                    <option value="LITRES">Litres (l)</option>
                    <option value="M2">Metres Quadrats (m²)</option>
                    <option value="M3">Metres Cúbics (m³)</option>
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
              )}

              {nouArticle.tipus_creacio === "MATERIAL" && (
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
                    <div className="col-span-2">
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
                        value={articleEditant.unitat_mesura}
                        onChange={(e) => setArticleEditant({ ...articleEditant, unitat_mesura: e.target.value })}
                        className="w-full p-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs"
                      >
                        <option value="UNITAT">Unitats (u)</option>
                        <option value="METRE">Metres (m)</option>
                        <option value="LITRE">Litres (L)</option>
                        <option value="QUILO">Quilograms (kg)</option>
                        <option value="CAIXA">Caixes</option>
                      </select>
                    </div>
                  </div>
                </div>

                {/* Dades Econòmiques i Estoc */}
                <div className="grid grid-cols-2 gap-4">
                  <div className="p-4 bg-emerald-50/50 dark:bg-emerald-900/10 rounded-2xl border border-emerald-100 dark:border-emerald-900/30 space-y-4">
                    <h4 className="text-xs font-bold text-emerald-600 dark:text-emerald-500 uppercase tracking-wider mb-2">Control d'Estoc</h4>
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
                  </div>
                  
                  <div className="p-4 bg-indigo-50/50 dark:bg-indigo-900/10 rounded-2xl border border-indigo-100 dark:border-indigo-900/30 space-y-4">
                    <h4 className="text-xs font-bold text-indigo-600 dark:text-indigo-400 uppercase tracking-wider mb-2">Preus i Costos</h4>
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="block text-xs font-bold text-slate-600 dark:text-slate-400 mb-1">Preu Cost (€)</label>
                        <input
                          type="number"
                          step="0.01"
                          value={articleEditant.preu_cost}
                          onChange={(e) => {
                            const pc = Number(e.target.value) || 0;
                            const costReal = pc * (1 - (articleEditant.descompte_proveidor / 100));
                            const preuVendaCalculat = costReal * (1 + (articleEditant.marge_guanys / 100));
                            setArticleEditant({ ...articleEditant, preu_cost: pc, preu_venda: parseFloat(preuVendaCalculat.toFixed(2)) });
                          }}
                          className="w-full p-2 rounded-xl border border-indigo-200 dark:border-indigo-800 bg-white dark:bg-slate-900 text-xs"
                          required
                        />
                      </div>
                      <div>
                        <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">Desc. Proveïdor (%)</label>
                        <input
                          type="number"
                          step="0.01"
                          value={articleEditant.descompte_proveidor}
                          onChange={(e) => {
                            const desc = Number(e.target.value) || 0;
                            const costReal = articleEditant.preu_cost * (1 - (desc / 100));
                            const preuVendaCalculat = costReal * (1 + (articleEditant.marge_guanys / 100));
                            setArticleEditant({ ...articleEditant, descompte_proveidor: desc, preu_venda: parseFloat(preuVendaCalculat.toFixed(2)) });
                          }}
                          className="w-full p-2 rounded-xl border border-indigo-200 dark:border-indigo-800 bg-white dark:bg-slate-900 text-xs"
                        />
                      </div>
                      <div>
                        <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">Marge Guanys (%)</label>
                        <input
                          type="number"
                          step="0.01"
                          value={articleEditant.marge_guanys}
                          onChange={(e) => {
                            const marge = Number(e.target.value) || 0;
                            const costReal = articleEditant.preu_cost * (1 - (articleEditant.descompte_proveidor / 100));
                            const preuVendaCalculat = costReal * (1 + (marge / 100));
                            setArticleEditant({ ...articleEditant, marge_guanys: marge, preu_venda: parseFloat(preuVendaCalculat.toFixed(2)) });
                          }}
                          className="w-full p-2 rounded-xl border border-indigo-200 dark:border-indigo-800 bg-white dark:bg-slate-900 text-xs"
                        />
                      </div>
                      <div className="col-span-2">
                        <label className="block text-xs font-bold text-slate-600 dark:text-slate-400 mb-1">Preu Venda (€) (Càlcul P.V.P.)</label>
                        <input
                          type="number"
                          step="0.01"
                          value={articleEditant.preu_venda}
                          onChange={(e) => setArticleEditant({ ...articleEditant, preu_venda: Number(e.target.value) })}
                          className="w-full p-2 rounded-xl border border-indigo-300 dark:border-indigo-700 bg-indigo-50 dark:bg-indigo-900/40 font-bold text-indigo-700 dark:text-indigo-300 text-xs"
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
                      {art.referencia_inventari} - {art.nom} (Total: {art.estoc_real ?? 0} {art.unitat_mesura})
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

    </div>
  );
}
