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
import { apiFetch } from "@/lib/api";
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
  preu_venda: number;
  actiu?: boolean;
}

export default function GestioMagatzemPage() {
  const { rolActiu } = useGestio();
  const [articles, setArticles] = useState<Article[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filtreCerca, setFiltreCerca] = useState("");
  const [filtreFamilia, setFiltreFamilia] = useState<string>("TOTS");
  const [modalNouArticle, setModalNouArticle] = useState(false);
  const [guardant, setGuardant] = useState(false);
  const [modalOcr, setModalOcr] = useState(false);
  const [fitxerOcr, setFitxerOcr] = useState<File | null>(null);
  const [processantOcr, setProcessantOcr] = useState(false);
  const [resultatOcr, setResultatOcr] = useState<any>(null);


  // Formulari nou article
  const [nouArticle, setNouArticle] = useState({
    referencia_inventari: "",
    nom: "",
    unitat_mesura: "UNITAT",
    familia: "TUBERIA",
    estoc_optim: 10,
    estoc_minim: 2,
    preu_cost: 0,
    preu_venda: 0,
    es_lot_caducable: false,
  });

  const carregarArticles = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiFetch<Article[]>("/gestio/magatzem/articles");
      setArticles(data || []);
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
      
      const token = localStorage.getItem("token");
      const urlBase = typeof window !== 'undefined' ? (window as any).API_BASE_URL || "/api/v1" : "/api/v1";
      const res = await fetch(`${urlBase}/gestio/magatzem/albara/ocr`, {
        method: "POST",
        headers: { "Authorization": `Bearer ${token}` },
        body: formData
      });
      
      if (!res.ok) throw new Error("Error processant l'albarà");
      const data = await res.json();
      setResultatOcr(data);
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
      await apiFetch("/gestio/magatzem/albara/confirmar", {
        method: "POST",
        body: JSON.stringify({
          proveidor: resultatOcr.proveidor,
          numero_document: resultatOcr.numero_document,
          tipus_document: resultatOcr.tipus_document,
          data_document: resultatOcr.data_document,
          numero_albarans_vinculats: resultatOcr.numero_albarans_vinculats || [],
          linies: resultatOcr.linies
        })
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

  const handleCrearArticle = async (e: React.FormEvent) => {
    e.preventDefault();
    setGuardant(true);
    setError(null);
    try {
      await apiFetch<Article>("/gestio/magatzem/articles", {
        method: "POST",
        body: JSON.stringify({
          ...nouArticle,
          estoc_optim: Number(nouArticle.estoc_optim),
          estoc_minim: Number(nouArticle.estoc_minim),
          preu_cost: Number(nouArticle.preu_cost),
          preu_venda: Number(nouArticle.preu_venda),
        }),
      });
      setModalNouArticle(false);
      setNouArticle({
        referencia_inventari: "",
        nom: "",
        unitat_mesura: "UNITAT",
        familia: "TUBERIA",
        estoc_optim: 10,
        estoc_minim: 2,
        preu_cost: 0,
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
            className="p-1.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-xs font-semibold"
          >
            <option value="TOTS">Totes les Famílies</option>
            <option value="TUBERIA">Canonades i Tubs</option>
            <option value="VALVULERIA">Valvuleria</option>
            <option value="ACCESSORIS">Accessoris</option>
            <option value="EINES">Eines de Custòdia</option>
            <option value="GENERAL">General</option>
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
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="bg-slate-50 dark:bg-slate-800/60 border-b border-slate-200 dark:border-slate-800 font-bold text-slate-600 dark:text-slate-300">
                    <th className="p-3">Ref. Inventari</th>
                    <th className="p-3">Descripció Article</th>
                    <th className="p-3">Família</th>
                    <th className="p-3">Unitat</th>
                    <th className="p-3 text-right">Estoc Mínim</th>
                    <th className="p-3 text-right">Estoc Òptim</th>
                    <th className="p-3 text-right">Preu Cost</th>
                    <th className="p-3 text-right">Preu Venda</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {articlesFiltrats.map((art) => (
                    <tr key={art.id} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/40 transition-colors">
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
                      <td className="p-3 text-right font-mono text-slate-700 dark:text-slate-300">
                        {art.estoc_minim}
                      </td>
                      <td className="p-3 text-right font-mono font-bold text-slate-900 dark:text-white">
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
                    <p><strong>Proveïdor:</strong> {resultatOcr.proveidor}</p>
                    <p><strong>Número:</strong> {resultatOcr.numero_document}</p>
                    <p><strong>Data:</strong> {resultatOcr.data_document}</p>
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
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                    Referència *
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="#ART-1001"
                    value={nouArticle.referencia_inventari}
                    onChange={(e) => setNouArticle({ ...nouArticle, referencia_inventari: e.target.value })}
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs font-mono"
                  />
                </div>
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
              </div>

              <div>
                <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                  Nom / Descripció de l'Article *
                </label>
                <input
                  type="text"
                  required
                  placeholder="Ex: Colze Electrosoldable PE-100 90º Ø90"
                  value={nouArticle.nom}
                  onChange={(e) => setNouArticle({ ...nouArticle, nom: e.target.value })}
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs font-medium"
                />
              </div>

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

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                    Preu Cost (€)
                  </label>
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={nouArticle.preu_cost}
                    onChange={(e) => setNouArticle({ ...nouArticle, preu_cost: Number(e.target.value) })}
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs font-mono"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                    Preu Venda (€)
                  </label>
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={nouArticle.preu_venda}
                    onChange={(e) => setNouArticle({ ...nouArticle, preu_venda: Number(e.target.value) })}
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs font-mono"
                  />
                </div>
              </div>

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
    </div>
  );
}
