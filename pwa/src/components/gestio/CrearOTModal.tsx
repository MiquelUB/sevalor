"use client";

import React, { useState, useEffect } from "react";
import { X, Save, Building2, User, FileText, Calendar, MapPin, Map, Truck, Map as MapIcon, AlignLeft, Package, Plus, Trash2 } from "lucide-react";
import { apiFetch } from "@/lib/api";

interface CrearOTModalProps {
  onClose: () => void;
  onSuccess?: () => void;
}

export function CrearOTModal({ onClose, onSuccess }: CrearOTModalProps) {
  const [loading, setLoading] = useState(false);
  const [clients, setClients] = useState<any[]>([]);
  const [finques, setFinques] = useState<any[]>([]);
  const [operaris, setOperaris] = useState<any[]>([]);
  const [vehicles, setVehicles] = useState<any[]>([]);
  const [planols, setPlanols] = useState<any[]>([]);
  const [articles, setArticles] = useState<any[]>([]);

  // Form state
  const [formData, setFormData] = useState({
    codi: `OT-${Math.floor(Math.random() * 10000)}`,
    titol: "",
    descripcio: "",
    adreca: "",
    client_id: "",
    finca_id: "",
    cap_de_colla_id: "",
    vehicle_id: "",
    planol_id: "",
    data_planificacio: new Date().toISOString().split("T")[0],
    estat: "PENDENT"
  });

  // Picking lines state
  const [liniesPicking, setLiniesPicking] = useState<{ article_id: string; quantitat: number }[]>([]);
  const [currentArticle, setCurrentArticle] = useState("");
  const [currentQty, setCurrentQty] = useState(1);

  useEffect(() => {
    // Load external data
    Promise.all([
      apiFetch("/gestio/clients"),
      apiFetch("/gestio/operaris"),
      apiFetch("/gestio/flota"),
      apiFetch("/gestio/planols"),
      apiFetch("/gestio/magatzem/articles")
    ]).then(([clientsRes, operarisRes, flotaRes, planolsRes, articlesRes]) => {
      if (clientsRes.ok) clientsRes.json().then((data: any) => setClients(data.items || data || []));
      if (operarisRes.ok) operarisRes.json().then((data: any) => setOperaris(data || []));
      if (flotaRes.ok) flotaRes.json().then((data: any) => setVehicles(data || []));
      if (planolsRes.ok) planolsRes.json().then((data: any) => setPlanols(data || []));
      if (articlesRes.ok) articlesRes.json().then((data: any) => setArticles(data || []));
    }).catch(console.error);
  }, []);

  // When client changes, fetch fitxa360 to get finques
  useEffect(() => {
    if (formData.client_id) {
      apiFetch(`/gestio/clients/${formData.client_id}/fitxa360`)
        .then(res => res.json())
        .then(data => {
          setFinques(data.finques || []);
          setFormData(prev => ({ ...prev, finca_id: "" }));
        })
        .catch(console.error);
    } else {
      setFinques([]);
      setFormData(prev => ({ ...prev, finca_id: "" }));
    }
  }, [formData.client_id]);

  const addLiniaPicking = () => {
    if (!currentArticle || currentQty <= 0) return;
    const existingIndex = liniesPicking.findIndex(l => l.article_id === currentArticle);
    if (existingIndex >= 0) {
      const newLinies = [...liniesPicking];
      newLinies[existingIndex].quantitat += currentQty;
      setLiniesPicking(newLinies);
    } else {
      setLiniesPicking([...liniesPicking, { article_id: currentArticle, quantitat: currentQty }]);
    }
    setCurrentArticle("");
    setCurrentQty(1);
  };

  const removeLiniaPicking = (index: number) => {
    const newLinies = [...liniesPicking];
    newLinies.splice(index, 1);
    setLiniesPicking(newLinies);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      const payload = {
        ...formData,
        vehicle_id: formData.vehicle_id ? formData.vehicle_id : null,
      };
      
      const { planol_id, ...backendPayload } = payload;

      // 1. Create OT
      const res = await apiFetch("/api/v1/gestio/feines", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(backendPayload)
      });

      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(`Error creant OT: ${errorData.detail || 'Desconegut'}`);
      }

      const createdOT = await res.json();

      // 2. Create Fulla de Picking if materials assigned
      if (liniesPicking.length > 0) {
        const pickRes = await apiFetch("/api/v1/gestio/magatzem/picking", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            ordre_treball_id: createdOT.id,
            vehicle_id: createdOT.vehicle_id
          })
        });

        if (!pickRes.ok) {
          throw new Error("S'ha creat l'OT però hi ha hagut un error en inicialitzar el picking.");
        }

        const createdPick = await pickRes.json();

        // 3. Insert Picking Lines
        for (const linia of liniesPicking) {
          await apiFetch(`/api/v1/gestio/magatzem/picking/${createdPick.id}/linies`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              article_id: linia.article_id,
              quantitat_prevista: linia.quantitat
            })
          });
        }
      }

      alert("Ordre de treball i recursos assignats amb èxit!");
      if (onSuccess) onSuccess();
      onClose();
    } catch (err: any) {
      alert(`Error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
      <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-xl w-full max-w-4xl overflow-hidden flex flex-col max-h-[90vh]">
        
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-slate-100 dark:border-slate-800">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-emerald-100 dark:bg-emerald-900/30 flex items-center justify-center">
              <FileText className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-slate-800 dark:text-slate-100">Nova Ordre de Treball</h2>
              <p className="text-sm text-slate-500">Completa els detalls tècnics i logístics de la intervenció</p>
            </div>
          </div>
          <button onClick={onClose} className="p-2 rounded-full hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto p-6 space-y-8">
          
          {/* Secció 1: Informació General */}
          <div>
            <h3 className="text-sm font-bold text-emerald-600 dark:text-emerald-500 uppercase tracking-wider mb-4 border-b border-slate-100 dark:border-slate-800 pb-2">1. Informació General</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-2">
                <label className="text-sm font-bold text-slate-700 dark:text-slate-300 flex items-center gap-2">
                  <FileText className="w-4 h-4 text-slate-400" /> Codi Referència
                </label>
                <input
                  required
                  type="text"
                  value={formData.codi}
                  onChange={e => setFormData({ ...formData, codi: e.target.value })}
                  className="w-full px-4 py-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 text-slate-800 dark:text-slate-100 focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 outline-none transition-all"
                />
              </div>

              <div className="space-y-2">
                <label className="text-sm font-bold text-slate-700 dark:text-slate-300 flex items-center gap-2">
                  <Calendar className="w-4 h-4 text-slate-400" /> Data Planificació
                </label>
                <input
                  required
                  type="date"
                  value={formData.data_planificacio}
                  onChange={e => setFormData({ ...formData, data_planificacio: e.target.value })}
                  className="w-full px-4 py-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 text-slate-800 dark:text-slate-100 focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 outline-none transition-all"
                />
              </div>

              <div className="space-y-2 md:col-span-2">
                <label className="text-sm font-bold text-slate-700 dark:text-slate-300">Títol de la Intervenció</label>
                <input
                  required
                  type="text"
                  placeholder="Ex: Reparació fuita al quadre d'aigua..."
                  value={formData.titol}
                  onChange={e => setFormData({ ...formData, titol: e.target.value })}
                  className="w-full px-4 py-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100 focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 outline-none transition-all"
                />
              </div>

              <div className="space-y-2 md:col-span-2">
                <label className="text-sm font-bold text-slate-700 dark:text-slate-300 flex items-center gap-2">
                  <AlignLeft className="w-4 h-4 text-slate-400" /> Definició de Tasca (Descripció)
                </label>
                <textarea
                  placeholder="Detalla les accions a realitzar, material necessari, etc..."
                  value={formData.descripcio}
                  onChange={e => setFormData({ ...formData, descripcio: e.target.value })}
                  rows={3}
                  className="w-full px-4 py-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100 focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 outline-none transition-all resize-none"
                />
              </div>
            </div>
          </div>

          {/* Secció 2: Ubicació i Client */}
          <div>
            <h3 className="text-sm font-bold text-emerald-600 dark:text-emerald-500 uppercase tracking-wider mb-4 border-b border-slate-100 dark:border-slate-800 pb-2">2. Client i Emplaçament</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-2">
                <label className="text-sm font-bold text-slate-700 dark:text-slate-300 flex items-center gap-2">
                  <Building2 className="w-4 h-4 text-slate-400" /> Client
                </label>
                <select
                  required
                  value={formData.client_id}
                  onChange={e => setFormData({ ...formData, client_id: e.target.value })}
                  className="w-full px-4 py-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100 focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 outline-none transition-all"
                >
                  <option value="">Selecciona un client...</option>
                  {clients.map(c => (
                    <option key={c.id || c.codi} value={c.id}>
                      {c.rao_social} ({c.nif})
                    </option>
                  ))}
                </select>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-bold text-slate-700 dark:text-slate-300 flex items-center gap-2">
                  <Map className="w-4 h-4 text-slate-400" /> Finca
                </label>
                <select
                  required
                  disabled={!formData.client_id}
                  value={formData.finca_id}
                  onChange={e => setFormData({ ...formData, finca_id: e.target.value })}
                  className="w-full px-4 py-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100 focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 outline-none transition-all disabled:opacity-50"
                >
                  <option value="">Selecciona una finca...</option>
                  {finques.map(f => (
                    <option key={f.id} value={f.id}>
                      {f.nom_finca || f.id}
                    </option>
                  ))}
                </select>
              </div>

              <div className="space-y-2 md:col-span-2">
                <label className="text-sm font-bold text-slate-700 dark:text-slate-300 flex items-center gap-2">
                  <MapPin className="w-4 h-4 text-slate-400" /> Adreça / Direcció / Coordenades (ex: 41.3851, 2.1734)
                </label>
                <input
                  type="text"
                  placeholder="Introduïu una adreça o coordenades per al GIS..."
                  value={formData.adreca}
                  onChange={e => setFormData({ ...formData, adreca: e.target.value })}
                  className="w-full px-4 py-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100 focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 outline-none transition-all"
                />
              </div>

              <div className="space-y-2 md:col-span-2">
                <label className="text-sm font-bold text-slate-700 dark:text-slate-300 flex items-center gap-2">
                  <MapIcon className="w-4 h-4 text-slate-400" /> Plànol / Esboç Vinculat (Opcional)
                </label>
                <select
                  value={formData.planol_id}
                  onChange={e => setFormData({ ...formData, planol_id: e.target.value })}
                  className="w-full px-4 py-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100 focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 outline-none transition-all"
                >
                  <option value="">Sense plànol vinculat</option>
                  {planols.map(p => (
                    <option key={p.id} value={p.id}>
                      {p.titol} ({p.codi_referencia})
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          {/* Secció 3: Assignació d'Actius i Vehicles */}
          <div>
            <h3 className="text-sm font-bold text-emerald-600 dark:text-emerald-500 uppercase tracking-wider mb-4 border-b border-slate-100 dark:border-slate-800 pb-2">3. Assignació d'Actius i Vehicles</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-2">
                <label className="text-sm font-bold text-slate-700 dark:text-slate-300 flex items-center gap-2">
                  <User className="w-4 h-4 text-slate-400" /> Cap de Colla / Operari Assignat
                </label>
                <select
                  required
                  value={formData.cap_de_colla_id}
                  onChange={e => setFormData({ ...formData, cap_de_colla_id: e.target.value })}
                  className="w-full px-4 py-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100 focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 outline-none transition-all"
                >
                  <option value="">Assignar operari...</option>
                  {operaris.map(op => (
                    <option key={op.id} value={op.id}>
                      {op.nom} {op.cognoms} - {op.rol}
                    </option>
                  ))}
                </select>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-bold text-slate-700 dark:text-slate-300 flex items-center gap-2">
                  <Truck className="w-4 h-4 text-slate-400" /> Vehicle Assignat (Opcional)
                </label>
                <select
                  value={formData.vehicle_id}
                  onChange={e => setFormData({ ...formData, vehicle_id: e.target.value })}
                  className="w-full px-4 py-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100 focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 outline-none transition-all"
                >
                  <option value="">Assignar vehicle...</option>
                  {vehicles.map(v => (
                    <option key={v.id} value={v.id}>
                      {v.matricula} - {v.marca} {v.model}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          {/* Secció 4: Assignació de Materials i Eines */}
          <div>
            <h3 className="text-sm font-bold text-emerald-600 dark:text-emerald-500 uppercase tracking-wider mb-4 border-b border-slate-100 dark:border-slate-800 pb-2">4. Assignació de Material i Eines (Picking)</h3>
            <div className="bg-slate-50 dark:bg-slate-800/30 p-4 rounded-xl border border-slate-200 dark:border-slate-800 space-y-4">
              <div className="flex items-end gap-4 flex-wrap">
                <div className="flex-1 space-y-2 min-w-[250px]">
                  <label className="text-sm font-bold text-slate-700 dark:text-slate-300 flex items-center gap-2">
                    <Package className="w-4 h-4 text-slate-400" /> Article / Eina
                  </label>
                  <select
                    value={currentArticle}
                    onChange={e => setCurrentArticle(e.target.value)}
                    className="w-full px-4 py-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100 focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 outline-none transition-all"
                  >
                    <option value="">Cercar material disponible...</option>
                    {articles.map(art => (
                      <option key={art.id} value={art.id} className={art.estoc_real <= 0 ? "text-red-500" : ""}>
                        {art.nom} ({art.referencia_inventari}) - Estoc: {art.estoc_real} {art.unitat_mesura}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="w-24 space-y-2">
                  <label className="text-sm font-bold text-slate-700 dark:text-slate-300">Quantitat</label>
                  <input
                    type="number"
                    min="1"
                    step="any"
                    value={currentQty}
                    onChange={e => setCurrentQty(Number(e.target.value))}
                    className="w-full px-4 py-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100 focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 outline-none transition-all"
                  />
                </div>
                <button
                  type="button"
                  onClick={addLiniaPicking}
                  disabled={!currentArticle || currentQty <= 0}
                  className="px-4 py-2.5 rounded-xl bg-slate-800 dark:bg-slate-700 hover:bg-slate-900 dark:hover:bg-slate-600 disabled:opacity-50 text-white font-bold transition-colors flex items-center gap-2"
                >
                  <Plus className="w-4 h-4" /> Afegir
                </button>
              </div>

              {/* Llista de Picking Seleccionada */}
              {liniesPicking.length > 0 && (
                <div className="mt-4 pt-4 border-t border-slate-200 dark:border-slate-700">
                  <h4 className="text-xs font-bold text-slate-500 mb-3 uppercase tracking-wider">Fulla de Picking (Per preparar):</h4>
                  <ul className="space-y-2">
                    {liniesPicking.map((linia, idx) => {
                      const articleDef = articles.find(a => a.id === linia.article_id);
                      return (
                        <li key={idx} className="flex items-center justify-between bg-white dark:bg-slate-900 p-3 rounded-lg border border-slate-100 dark:border-slate-800 shadow-sm">
                          <span className="font-medium text-slate-800 dark:text-slate-200 text-sm">
                            {articleDef?.nom} <span className="text-slate-400">({articleDef?.referencia_inventari})</span>
                          </span>
                          <div className="flex items-center gap-4">
                            <span className="font-bold text-emerald-600 dark:text-emerald-400">
                              {linia.quantitat} {articleDef?.unitat_mesura}
                            </span>
                            <button
                              type="button"
                              onClick={() => removeLiniaPicking(idx)}
                              className="text-red-500 hover:text-red-700 p-1 rounded-md hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </div>
                        </li>
                      );
                    })}
                  </ul>
                </div>
              )}
            </div>
          </div>

          {/* Footer Botons */}
          <div className="flex items-center justify-end gap-3 pt-6 border-t border-slate-100 dark:border-slate-800 mt-8">
            <button
              type="button"
              onClick={onClose}
              className="px-5 py-2.5 rounded-xl font-bold text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            >
              Cancel·lar
            </button>
            <button
              type="submit"
              disabled={loading}
              className="px-6 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 disabled:opacity-70 text-white font-bold shadow-sm flex items-center gap-2 transition-colors"
            >
              <Save className="w-4 h-4" />
              {loading ? "Processant..." : "Crear Intervenció i Picking"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
