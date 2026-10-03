"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Briefcase, ArrowLeft, Save, User, FileText, Calendar, DollarSign, Repeat, MapPin } from "lucide-react";
import { getAuthHeader } from "@/lib/auth";

export default function NouContractePage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [clients, setClients] = useState<any[]>([]);
  const [finques, setFinques] = useState<any[]>([]);
  
  const [formData, setFormData] = useState({
    client_id: "",
    numero_contracte: "",
    data_inici: new Date().toISOString().split('T')[0],
    data_fi: "",
    import_anual: 0.0,
    periodicitat: "ANUAL",
    observacions: "",
    finques_ids: [] as string[]
  });

  useEffect(() => {
    const fetchClients = async () => {
      try {
        const res = await fetch("http://localhost:8000/api/v1/gestio/clients", {
          headers: getAuthHeader(),
        });
        if (res.ok) {
          const data = await res.json();
          setClients(data);
        }
      } catch (e) { console.error(e) }
    };
    fetchClients();
  }, []);

  useEffect(() => {
    if (formData.client_id) {
      // Fetch finques for this client
      const fetchFinques = async () => {
        try {
          const res = await fetch(`http://localhost:8000/api/v1/gestio/clients/${formData.client_id}`, {
            headers: getAuthHeader(),
          });
          if (res.ok) {
            const data = await res.json();
            // Assumint que el detall del client retorna "adreces" o "finques"
            if (data.adreces) {
              setFinques(data.adreces);
            }
          }
        } catch (e) { console.error(e) }
      };
      fetchFinques();
    } else {
      setFinques([]);
    }
  }, [formData.client_id]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const payload = {
        ...formData,
        data_fi: formData.data_fi || null,
        import_anual: Number(formData.import_anual)
      };
      
      const res = await fetch("http://localhost:8000/api/v1/gestio/contractes", {
        method: "POST",
        headers: {
          ...getAuthHeader(),
          "Content-Type": "application/json"
        },
        body: JSON.stringify(payload)
      });
      
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Error desant contracte");
      }
      
      router.push("/gestio/contractes");
    } catch (e: any) {
      alert(e.message);
      setLoading(false);
    }
  };

  const toggleFinca = (fincaId: string) => {
    setFormData(prev => ({
      ...prev,
      finques_ids: prev.finques_ids.includes(fincaId) 
        ? prev.finques_ids.filter(id => id !== fincaId)
        : [...prev.finques_ids, fincaId]
    }));
  };

  return (
    <div className="p-4 md:p-8 max-w-4xl mx-auto space-y-6">
      <Link href="/gestio/contractes" className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-900 dark:hover:text-white mb-2 transition-colors">
        <ArrowLeft className="w-4 h-4" />
        Tornar a Contractes
      </Link>

      <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white flex items-center gap-2">
            <Briefcase className="w-6 h-6 text-primary-600" />
            Nou Contracte
          </h1>
          <p className="text-sm text-slate-500 mt-1">Donar d'alta un nou acord de manteniment preventiu</p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-6 rounded-xl shadow-sm space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            
            {/* Client */}
            <div className="md:col-span-2">
              <label className="block text-sm font-bold text-slate-700 dark:text-slate-300 mb-1.5 flex items-center gap-2">
                <User className="w-4 h-4 text-slate-400" /> Client
              </label>
              <select
                required
                value={formData.client_id}
                onChange={e => setFormData({...formData, client_id: e.target.value})}
                className="w-full bg-slate-50 border border-slate-300 text-slate-900 text-sm rounded-lg focus:ring-primary-500 focus:border-primary-500 block p-2.5 dark:bg-slate-800 dark:border-slate-600 dark:text-white"
              >
                <option value="" disabled>Selecciona un client...</option>
                {clients.map(c => (
                  <option key={c.id} value={c.id}>{c.nom || c.rao_social}</option>
                ))}
              </select>
            </div>

            {/* Número Contracte */}
            <div>
              <label className="block text-sm font-bold text-slate-700 dark:text-slate-300 mb-1.5 flex items-center gap-2">
                <FileText className="w-4 h-4 text-slate-400" /> Núm. de Contracte
              </label>
              <input
                type="text"
                required
                value={formData.numero_contracte}
                onChange={e => setFormData({...formData, numero_contracte: e.target.value})}
                placeholder="Ex: MANT-2024-001"
                className="w-full bg-slate-50 border border-slate-300 text-slate-900 text-sm rounded-lg focus:ring-primary-500 focus:border-primary-500 block p-2.5 dark:bg-slate-800 dark:border-slate-600 dark:text-white"
              />
            </div>

            {/* Periodicitat */}
            <div>
              <label className="block text-sm font-bold text-slate-700 dark:text-slate-300 mb-1.5 flex items-center gap-2">
                <Repeat className="w-4 h-4 text-slate-400" /> Periodicitat
              </label>
              <select
                required
                value={formData.periodicitat}
                onChange={e => setFormData({...formData, periodicitat: e.target.value})}
                className="w-full bg-slate-50 border border-slate-300 text-slate-900 text-sm rounded-lg focus:ring-primary-500 focus:border-primary-500 block p-2.5 dark:bg-slate-800 dark:border-slate-600 dark:text-white"
              >
                <option value="MENSUAL">Mensual</option>
                <option value="TRIMESTRAL">Trimestral</option>
                <option value="SEMESTRAL">Semestral</option>
                <option value="ANUAL">Anual</option>
              </select>
            </div>

            {/* Data Inici */}
            <div>
              <label className="block text-sm font-bold text-slate-700 dark:text-slate-300 mb-1.5 flex items-center gap-2">
                <Calendar className="w-4 h-4 text-slate-400" /> Data Inici
              </label>
              <input
                type="date"
                required
                value={formData.data_inici}
                onChange={e => setFormData({...formData, data_inici: e.target.value})}
                className="w-full bg-slate-50 border border-slate-300 text-slate-900 text-sm rounded-lg focus:ring-primary-500 focus:border-primary-500 block p-2.5 dark:bg-slate-800 dark:border-slate-600 dark:text-white"
              />
            </div>

            {/* Data Fi */}
            <div>
              <label className="block text-sm font-bold text-slate-700 dark:text-slate-300 mb-1.5 flex items-center gap-2">
                <Calendar className="w-4 h-4 text-slate-400" /> Data Fi (Opcional)
              </label>
              <input
                type="date"
                value={formData.data_fi}
                onChange={e => setFormData({...formData, data_fi: e.target.value})}
                className="w-full bg-slate-50 border border-slate-300 text-slate-900 text-sm rounded-lg focus:ring-primary-500 focus:border-primary-500 block p-2.5 dark:bg-slate-800 dark:border-slate-600 dark:text-white"
              />
            </div>

            {/* Import Anual */}
            <div>
              <label className="block text-sm font-bold text-slate-700 dark:text-slate-300 mb-1.5 flex items-center gap-2">
                <DollarSign className="w-4 h-4 text-slate-400" /> Import Anual Base (€)
              </label>
              <input
                type="number"
                step="0.01"
                min="0"
                required
                value={formData.import_anual}
                onChange={e => setFormData({...formData, import_anual: parseFloat(e.target.value) || 0})}
                className="w-full bg-slate-50 border border-slate-300 text-slate-900 text-sm rounded-lg focus:ring-primary-500 focus:border-primary-500 block p-2.5 dark:bg-slate-800 dark:border-slate-600 dark:text-white font-mono"
              />
            </div>

          </div>

          {/* Finques */}
          {formData.client_id && finques.length > 0 && (
            <div className="pt-4 border-t border-slate-200 dark:border-slate-800">
              <label className="block text-sm font-bold text-slate-700 dark:text-slate-300 mb-3 flex items-center gap-2">
                <MapPin className="w-4 h-4 text-slate-400" /> Adreces / Finques a Cobrir
              </label>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {finques.map(f => (
                  <label key={f.id} className="flex items-start gap-3 p-3 border border-slate-200 dark:border-slate-700 rounded-lg cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors">
                    <input 
                      type="checkbox"
                      checked={formData.finques_ids.includes(f.id)}
                      onChange={() => toggleFinca(f.id)}
                      className="mt-0.5 w-4 h-4 text-primary-600 rounded focus:ring-primary-500 dark:focus:ring-primary-600 dark:bg-slate-700 dark:border-slate-600"
                    />
                    <div className="flex flex-col">
                      <span className="text-sm font-medium text-slate-900 dark:text-white leading-tight">{f.nom_via} {f.numero}</span>
                      <span className="text-xs text-slate-500">{f.municipi} ({f.provincia})</span>
                    </div>
                  </label>
                ))}
              </div>
            </div>
          )}

          {/* Observacions */}
          <div className="pt-4 border-t border-slate-200 dark:border-slate-800">
            <label className="block text-sm font-bold text-slate-700 dark:text-slate-300 mb-1.5">
              Observacions
            </label>
            <textarea
              rows={3}
              value={formData.observacions}
              onChange={e => setFormData({...formData, observacions: e.target.value})}
              className="w-full bg-slate-50 border border-slate-300 text-slate-900 text-sm rounded-lg focus:ring-primary-500 focus:border-primary-500 block p-2.5 dark:bg-slate-800 dark:border-slate-600 dark:text-white"
              placeholder="Notes addicionals sobre el contracte..."
            />
          </div>

        </div>

        <div className="flex justify-end pt-4">
          <button
            type="submit"
            disabled={loading}
            className="bg-primary-600 hover:bg-primary-700 text-white px-6 py-2.5 rounded-lg font-bold flex items-center gap-2 transition-colors disabled:opacity-50"
          >
            <Save className="w-5 h-5" />
            {loading ? "Desant..." : "Crear Contracte"}
          </button>
        </div>
      </form>
    </div>
  );
}
