"use client";

import React, { useState, useEffect } from "react";
import { X, Save, Building2, User, FileText, Calendar, MapPin, Map } from "lucide-react";
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

  // Form state
  const [formData, setFormData] = useState({
    codi: `OT-${Math.floor(Math.random() * 10000)}`,
    titol: "",
    descripcio: "",
    adreca: "",
    client_id: "",
    finca_id: "",
    cap_de_colla_id: "",
    data_planificacio: new Date().toISOString().split("T")[0],
    estat: "PENDENT"
  });

  useEffect(() => {
    // Load clients and operaris
    Promise.all([
      apiFetch("/api/v1/gestio/clients"),
      apiFetch("/api/v1/gestio/operaris")
    ]).then(([clientsRes, operarisRes]) => {
      if (clientsRes.ok) {
        clientsRes.json().then((data: any) => setClients(data.items || data || []));
      }
      if (operarisRes.ok) {
        operarisRes.json().then((data: any) => setOperaris(data || []));
      }
    }).catch(console.error);
  }, []);

  // When client changes, fetch fitxa360 to get finques
  useEffect(() => {
    if (formData.client_id) {
      apiFetch(`/api/v1/gestio/clients/${formData.client_id}/fitxa360`)
        .then(res => res.json())
        .then(data => {
          setFinques(data.finques || []);
          // Reset finca_id
          setFormData(prev => ({ ...prev, finca_id: "" }));
        })
        .catch(console.error);
    } else {
      setFinques([]);
      setFormData(prev => ({ ...prev, finca_id: "" }));
    }
  }, [formData.client_id]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      const payload = {
        ...formData,
        vehicle_id: null
      };

      const res = await apiFetch("/api/v1/gestio/feines", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      if (res.ok) {
        alert("Ordre de treball creada amb èxit!");
        if (onSuccess) onSuccess();
        onClose();
      } else {
        const errorData = await res.json();
        alert(`Error: ${errorData.detail || 'Error desconegut'}`);
      }
    } catch (err: any) {
      alert(`Error en crear la feina: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
      <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-xl w-full max-w-2xl overflow-hidden flex flex-col max-h-[90vh]">
        
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-slate-100 dark:border-slate-800">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-emerald-100 dark:bg-emerald-900/30 flex items-center justify-center">
              <FileText className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-slate-800 dark:text-slate-100">Nova Ordre de Treball</h2>
              <p className="text-sm text-slate-500">Crea una feina i assigna-la al calendari operatiu</p>
            </div>
          </div>
          <button onClick={onClose} className="p-2 rounded-full hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto p-6 space-y-6">
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Codi */}
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

            {/* Data Planificació */}
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

            {/* Títol */}
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

            {/* Client */}
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

            {/* Finca */}
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

            {/* Cap de colla */}
            <div className="space-y-2 md:col-span-2">
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

            {/* Adreça / Coordenades GIS (Per defecte) */}
            <div className="space-y-2 md:col-span-2">
              <label className="text-sm font-bold text-slate-700 dark:text-slate-300 flex items-center gap-2">
                <MapPin className="w-4 h-4 text-slate-400" /> Adreça / Coordenades (ex: 41.3851, 2.1734)
              </label>
              <input
                type="text"
                placeholder="Introduïu una adreça per al GIS..."
                value={formData.adreca}
                onChange={e => setFormData({ ...formData, adreca: e.target.value })}
                className="w-full px-4 py-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100 focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 outline-none transition-all"
              />
            </div>
          </div>

          <div className="flex items-center justify-end gap-3 pt-6 border-t border-slate-100 dark:border-slate-800">
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
              {loading ? "Creant..." : "Crear Intervenció"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
