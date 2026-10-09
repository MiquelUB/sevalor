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
  actiu?: boolean;
  es_lot_caducable?: boolean;
  estoc_real?: number;
}

export default function GestioMagatzemPage() {
  const { rolActiu } = useGestio();
  const [vertical, setVertical] = useState<string>("SEVALOR");
  const [customFamilies, setCustomFamilies] = useState<string[]>([]);
  const [articles, setArticles] = useState<Article[]>([]);
  const [eines, setEines] = useState<any[]>([]);
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
  });

  // Efecte per autocalcular el preu de venda
  useEffect(() => {
    if (nouArticle.tipus_creacio === "MATERIAL") {
      const costReal = nouArticle.preu_cost * (1 - (nouArticle.descompte_proveidor / 100));
      const preuVendaCalculat = costReal * (1 + (nouArticle.marge_guanys / 100));
      setNouArticle(prev => ({ ...prev, preu_venda: parseFloat(preuVendaCalculat.toFixed(2)) }));
    }
  }, [nouArticle.preu_cost, nouArticle.descompte_proveidor, nouArticle.marge_guanys, nouArticle.tipus_creacio]);

  const carregarArticles = async () => {
    setLoading(true);
    setError(null);
    try {
      const [articlesData, einesData, operarisData, configData] = await Promise.all([
        apiFetch<Article[]>("/gestio/magatzem/articles").catch(() => []),
        apiFetch<any[]>("/gestio/magatzem/eines").catch(() => []),
        apiFetch<any[]>("/gestio/operaris").catch(() => []),
        apiFetch<any>("/gestio/configuracio/empresa").catch(() => null)
      ]);
      setArticles(articlesData || []);
      setEines(einesData || []);
      setOperaris(operarisData || []);
      
      if (configData) {
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
          linies: resultatOcr.linies || [],
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
    if (!einaCheckout || !selectedOperari) return;
    try {
      await apiFetch(`/gestio/magatzem/eines/${einaCheckout.id}/checkout`, {
        method: "POST",
        body: JSON.stringify({ operari_id: selectedOperari })
      });
      setModalCheckout(false);
      setEinaCheckout(null);
      carregarArticles();
    } catch (err: any) {
      alert(err.message || "Error al fer checkout");
    }
  };

  const handleCheckin = async (einaId: string) => {
    if (!confirm("Confirmar devolució de l'eina al magatzem central?")) return;
    try {
      await apiFetch(`/gestio/magatzem/eines/${einaId}/checkin`, {
        method: "POST"
      });
      carregarArticles();
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
          <div className="relative">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
            <input
              type="text"
              value={filtreCerca}
              onChange={(e) => setFiltreCerca(e.target.value)}
              placeholder="Cercar referència o nom..."
              className="pl-9 pr-3 py-1.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-xs font-medium focus:outline-none focus:border-emerald-600 w-56"
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
            onClick={carregarArticles}
            disabled={loading}
            className="p-2 rounded-xl bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 text-slate-600 dark:text-slate-300 transition-colors"
            title="Refrescar llista"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
          </button>

          
          <button
            onClick={() => setModalOcr(true)}
            className="px-3 py-1.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold flex items-center gap-1 shadow transition-all"
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>Entrada Assistida IA</span>
          </button>

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
                          <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${eina.estat === "DISPONIBLE" ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400" : "bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400"}`}>
                            {eina.estat}
                          </span>
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
                          ) : eina.estat === "CUSTODIADA" ? (
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
          <div className="w-full max-w-lg bg-white dark:bg-slate-900 rounded-3xl shadow-2xl border border-slate-200 dark:border-slate-800 overflow-hidden">
            <div className="p-5 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
              <h3 className="font-bold text-sm text-slate-800 dark:text-slate-100 flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-indigo-600" />
                Entrada Assistida per IA (OCR)
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

            <div className="p-5 space-y-4">
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
                  <div className="p-4 bg-slate-50 dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 text-xs">
                    <p><strong>Proveïdor:</strong> {resultatOcr.proveidor?.nom || (typeof resultatOcr.proveidor === "string" ? resultatOcr.proveidor : "Pendent de revisió")}</p>
                    <p><strong>Número:</strong> {resultatOcr.numero_document || "Sense número"}</p>
                    <p><strong>Data:</strong> {resultatOcr.data_document || "Pendent"}</p>
                    <p className="mt-2 font-bold">Línies detectades: {resultatOcr.linies?.length || 0}</p>
                  </div>
                  <div className="flex justify-end gap-2">
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
                      className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold shadow disabled:opacity-50"
                    >
                      {processantOcr ? "Desant..." : "Confirmar i Desar"}
                    </button>
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
                    <select
                      value={nouArticle.familia}
                      onChange={(e) => setNouArticle({ ...nouArticle, familia: e.target.value })}
                      className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs font-semibold"
                    >
                      <option value="TUBERIA">Canonades i Tubs</option>
                      <option value="VALVULERIA">Valvuleria</option>
                      <option value="ACCESSORIS">Accessoris</option>
                      <option value="EINES">Eines de Custòdia</option>
                      <option value="GENERAL">General</option>
                    </select>
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
                    <div>
                      <label className="block text-xs font-bold text-slate-600 dark:text-slate-400 mb-1">Família</label>
                      <select
                        value={articleEditant.familia}
                        onChange={(e) => setArticleEditant({ ...articleEditant, familia: e.target.value })}
                        className="w-full p-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs"
                      >
                      {vertical === "ELECTRICPRO" ? (
                        <>
                          <option value="CABLES">Cables i Conducció</option>
                          <option value="QUADRES">Quadres i Proteccions</option>
                          <option value="ILLUMINACIO">Il·luminació</option>
                          <option value="MECANISMES">Mecanismes</option>
                        </>
                      ) : vertical === "HYDROPRO" ? (
                        <>
                          <option value="TUBERIA">Canonades i Tubs</option>
                          <option value="VALVULERIA">Valvuleria</option>
                          <option value="SANITARIS">Sanitaris</option>
                          <option value="AIXETES">Aixetes</option>
                        </>
                      ) : vertical === "BUILDINGPRO" ? (
                        <>
                          <option value="CIMENT">Ciment i Àrids</option>
                          <option value="FUSTA">Fusta i Fusteria</option>
                          <option value="PINTURA">Pintures i Acabats</option>
                          <option value="AILLAMENTS">Aïllaments</option>
                        </>
                      ) : (
                        <>
                          <option value="TUBERIA">Canonades i Tubs</option>
                          <option value="VALVULERIA">Valvuleria</option>
                          <option value="ACCESSORIS">Accessoris</option>
                          <option value="CABLES">Cables i Elèctric</option>
                        </>
                      )}
                      <option value="GENERAL">General</option>
                        {/* Preserve existing family if it was custom */}
                        {![
                          "TUBERIA", "VALVULERIA", "ACCESSORIS", "CABLES", "GENERAL",
                          "QUADRES", "ILLUMINACIO", "MECANISMES", "SANITARIS", "AIXETES",
                          "CIMENT", "FUSTA", "PINTURA", "AILLAMENTS"
                        ].includes(articleEditant.familia) && (
                          <option value={articleEditant.familia}>{articleEditant.familia}</option>
                        )}
                      </select>
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
              <div className="flex justify-end gap-2 pt-2">
                <button
                  onClick={() => { setModalCheckout(false); setEinaCheckout(null); }}
                  className="px-4 py-2 rounded-xl border border-slate-300 dark:border-slate-700 text-slate-600 dark:text-slate-300 text-xs font-medium hover:bg-slate-100"
                >
                  Cancel·lar
                </button>
                <button
                  onClick={handleCheckout}
                  disabled={!selectedOperari}
                  className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold shadow disabled:opacity-50"
                >
                  Confirmar Entrega
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
