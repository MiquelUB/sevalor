"use client";

import React, { useState } from "react";
import { AlertTriangle, MapPin, Camera, Save, X } from "lucide-react";
import { addToSyncQueue } from "@/lib/offline/sync";

interface IncidenciaFormProps {
  onSuccess?: () => void;
  onCancel?: () => void;
}

export default function IncidenciaForm({ onSuccess, onCancel }: IncidenciaFormProps) {
  const [titol, setTitol] = useState("");
  const [descripcio, setDescripcio] = useState("");
  const [urgencia, setUrgencia] = useState("MITJANA");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const payload = {
        titol,
        descripcio,
        urgencia,
        data_report: new Date().toISOString(),
      };
      
      // Afegim a la cua de sincronització (Offline First)
      await addToSyncQueue("REPORTAR_INCIDENCIA", payload);
      
      // Netejem el formulari
      setTitol("");
      setDescripcio("");
      setUrgencia("MITJANA");
      
      if (onSuccess) onSuccess();
    } catch (err) {
      console.error(err);
      alert("Error en guardar l'incidència localment");
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4 bg-white dark:bg-slate-900 p-4 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
      <div>
        <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
          Títol de la Incidència
        </label>
        <input
          type="text"
          value={titol}
          onChange={(e) => setTitol(e.target.value)}
          required
          placeholder="Ex: Trencament de canonada"
          className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
        />
      </div>

      <div>
        <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
          Descripció
        </label>
        <textarea
          value={descripcio}
          onChange={(e) => setDescripcio(e.target.value)}
          required
          rows={3}
          placeholder="Descriu què ha passat..."
          className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
        />
      </div>

      <div>
        <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
          Nivell d'Urgència
        </label>
        <select
          value={urgencia}
          onChange={(e) => setUrgencia(e.target.value)}
          className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
        >
          <option value="BAIXA">Baixa - Pot esperar</option>
          <option value="MITJANA">Mitjana - Afecta el rendiment</option>
          <option value="ALTA">Alta - Bloqueja la feina</option>
          <option value="CRITICA">Crítica - Risc per a persones/equips</option>
        </select>
      </div>

      <div className="flex items-center gap-2 pt-2">
        <button
          type="button"
          onClick={onCancel}
          className="flex-1 py-2 px-4 rounded-lg border border-slate-200 dark:border-slate-700 text-sm font-bold text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
        >
          Cancel·lar
        </button>
        <button
          type="submit"
          disabled={loading || !titol.trim() || !descripcio.trim()}
          className="flex-1 py-2 px-4 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-bold shadow flex items-center justify-center gap-2 disabled:opacity-50 transition-colors"
        >
          <Save className="w-4 h-4" />
          Guardar Offline
        </button>
      </div>
    </form>
  );
}
