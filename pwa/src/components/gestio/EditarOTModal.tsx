"use client";

import React, { useState, useEffect } from "react";
import {
  X,
  Save,
  Building2,
  User,
  FileText,
  Calendar,
  MapPin,
  Truck,
  AlignLeft,
  Check,
  Clock,
  AlertCircle,
  RefreshCw,
} from "lucide-react";
import { apiFetch } from "@/lib/api";
import { geocodificarAdreca } from "@/lib/geocoding";

interface EditarOTModalProps {
  feinaId: string;
  onClose: () => void;
  onSuccess?: () => void;
}

export function EditarOTModal({ feinaId, onClose, onSuccess }: EditarOTModalProps) {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Auxiliar catalogs
  const [clients, setClients] = useState<any[]>([]);
  const [finques, setFinques] = useState<any[]>([]);
  const [operaris, setOperaris] = useState<any[]>([]);
  const [vehicles, setVehicles] = useState<any[]>([]);

  // Form state
  const [formData, setFormData] = useState({
    codi: "",
    versio: 1,
    titol: "",
    descripcio: "",
    adreca: "",
    client_id: "",
    finca_id: "",
    cap_de_colla_id: "",
    vehicle_id: "",
    data_planificacio: new Date().toISOString().split("T")[0],
    estat: "PENDENT",
    latitud: null as number | null,
    longitud: null as number | null,
  });

  // Load feina and auxiliary catalogs
  useEffect(() => {
    setLoading(true);
    Promise.all([
      apiFetch<any>(`/gestio/feines/${feinaId}`),
      apiFetch<any>("/gestio/clients").catch(() => []),
      apiFetch<any>("/gestio/operaris").catch(() => []),
      apiFetch<any>("/gestio/flota").catch(() => []),
    ])
      .then(([feinaData, clientsData, operarisData, flotaData]) => {
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
          data_planificacio: feinaData.data_planificacio || new Date().toISOString().split("T")[0],
          estat: feinaData.estat || "PENDENT",
          latitud: feinaData.latitud ?? null,
          longitud: feinaData.longitud ?? null,
        });

        setClients(Array.isArray(clientsData) ? clientsData : clientsData?.items || []);
        setOperaris(
          (Array.isArray(operarisData) ? operarisData : operarisData?.operaris || []).filter(
            (o: any) => o.estat === "ACTIU"
          )
        );
        setVehicles(Array.isArray(flotaData) ? flotaData : flotaData?.vehicles || []);

        if (feinaData.client_id) {
          apiFetch<any>(`/gestio/clients/${feinaData.client_id}/fitxa360`)
            .then((res) => setFinques(res?.finques || []))
            .catch(() => setFinques([]));
        }
      })
      .catch((err) => {
        setErrorMsg("No s'ha pogut carregar l'ordre de treball: " + (err.message || err));
      })
      .finally(() => setLoading(false));
  }, [feinaId]);

  // When client changes, fetch finques
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

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.titol.trim()) {
      setErrorMsg("El títol de la feina és obligatori.");
      return;
    }
    if (!formData.adreca.trim()) {
      setErrorMsg("L'adreça d'obra és obligatòria.");
      return;
    }

    setSaving(true);
    setErrorMsg(null);

    try {
      const geo = geocodificarAdreca(formData.adreca, formData.latitud ?? undefined, formData.longitud ?? undefined);

      const payload = {
        titol: formData.titol.trim(),
        descripcio: formData.descripcio.trim() || null,
        client_id: formData.client_id || null,
        finca_id: formData.finca_id || null,
        adreca: formData.adreca.trim(),
        data_planificacio: formData.data_planificacio,
        estat: formData.estat,
        cap_de_colla_id: formData.cap_de_colla_id || null,
        vehicle_id: formData.vehicle_id || null,
        latitud: geo.lat,
        longitud: geo.lng,
        versio: formData.versio,
      };

      await apiFetch(`/gestio/feines/${feinaId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (onSuccess) onSuccess();
      onClose();
    } catch (err: any) {
      setErrorMsg(err.message || "Error desant els canvis de la feina.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-in fade-in duration-150">
      <div className="relative w-full max-w-2xl bg-white dark:bg-slate-900 rounded-2xl shadow-2xl border border-slate-200 dark:border-slate-800 flex flex-col max-h-[90vh] overflow-hidden">
        {/* Capçalera Modal */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/40">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center text-primary">
              <FileText className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-bold text-slate-900 dark:text-white">
                  Editar Ordre de Treball
                </h2>
                {formData.codi && (
                  <span className="font-mono text-xs font-bold px-2.5 py-0.5 rounded-full bg-primary text-white">
                    {formData.codi}
                  </span>
                )}
                <span
                  className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded-full ${
                    formData.estat === "PENDENT"
                      ? "bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300"
                      : formData.estat === "ASSIGNADA" || formData.estat === "PROGRAMADA"
                      ? "bg-blue-100 text-blue-800 dark:bg-blue-950/60 dark:text-blue-300"
                      : ["EN_CURS", "EN_OBRA", "EN_RUTA"].includes(formData.estat)
                      ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300"
                      : "bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-300"
                  }`}
                >
                  {formData.estat}
                </span>
              </div>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                Modifica l&apos;assignació, la planificació o les dades tècniques d&apos;aquesta intervenció.
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            type="button"
            className="p-2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-xl transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Cos del Formulari */}
        {loading ? (
          <div className="p-12 flex flex-col items-center justify-center gap-3">
            <RefreshCw className="w-8 h-8 text-primary animate-spin" />
            <p className="text-xs text-slate-500 font-mono">Carregant dades de l&apos;ordre de treball...</p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto p-6 space-y-4">
            {errorMsg && (
              <div className="p-3 rounded-xl bg-error/10 border border-error/20 flex items-center gap-2 text-error text-xs">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>{errorMsg}</span>
              </div>
            )}

            {/* Títol de la feina */}
            <div>
              <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1 flex items-center gap-1.5">
                <FileText className="w-3.5 h-3.5 text-primary" />
                <span>Títol de la Feina / Intervenció *</span>
              </label>
              <input
                type="text"
                required
                value={formData.titol}
                onChange={(e) => setFormData({ ...formData, titol: e.target.value })}
                placeholder="Ex: Reparació electrobomba sector Nord"
                className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary font-medium"
              />
            </div>

            {/* Descripció tècnica */}
            <div>
              <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1 flex items-center gap-1.5">
                <AlignLeft className="w-3.5 h-3.5 text-slate-400" />
                <span>Instruccions Tècniques per a l&apos;Operari</span>
              </label>
              <textarea
                rows={2}
                value={formData.descripcio}
                onChange={(e) => setFormData({ ...formData, descripcio: e.target.value })}
                placeholder="Observacions, accessos o tasques específiques a realitzar sobre el terreny..."
                className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary resize-none"
              />
            </div>

            {/* Client i Finca */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1 flex items-center gap-1.5">
                  <Building2 className="w-3.5 h-3.5 text-slate-400" />
                  <span>Client Associat</span>
                </label>
                <select
                  value={formData.client_id}
                  onChange={(e) => handleClientChange(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary"
                >
                  <option value="">Selecciona un client...</option>
                  {clients.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.rao_social} ({c.nif || c.codi})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1 flex items-center gap-1.5">
                  <MapPin className="w-3.5 h-3.5 text-slate-400" />
                  <span>Finca / Emplaçament</span>
                </label>
                <select
                  value={formData.finca_id}
                  onChange={(e) => setFormData({ ...formData, finca_id: e.target.value })}
                  disabled={!formData.client_id || finques.length === 0}
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary disabled:opacity-50"
                >
                  <option value="">
                    {finques.length === 0
                      ? formData.client_id
                        ? "Aquest client no té finques"
                        : "Selecciona client primer"
                      : "Selecciona una finca..."}
                  </option>
                  {finques.map((f) => (
                    <option key={f.id} value={f.id}>
                      {f.nom || f.adreca || "Finca sense nom"}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Adreça física d'obra */}
            <div>
              <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1 flex items-center gap-1.5">
                <MapPin className="w-3.5 h-3.5 text-secondary" />
                <span>Adreça / Coordenades d&apos;Obra *</span>
              </label>
              <input
                type="text"
                required
                value={formData.adreca}
                onChange={(e) => setFormData({ ...formData, adreca: e.target.value })}
                placeholder="Carrer, municipi o coordenades lat, lng"
                className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary font-mono"
              />
            </div>

            {/* Assignació Operativa (Cap de Colla) i Vehicle */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1 flex items-center gap-1.5">
                  <User className="w-3.5 h-3.5 text-primary" />
                  <span>Cap de Colla / Operari Assignat</span>
                </label>
                <select
                  value={formData.cap_de_colla_id}
                  onChange={(e) => {
                    const newOp = e.target.value;
                    setFormData({
                      ...formData,
                      cap_de_colla_id: newOp,
                      estat: newOp && formData.estat === "PENDENT" ? "ASSIGNADA" : formData.estat,
                    });
                  }}
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary"
                >
                  <option value="">Pendent d&apos;assignar (Sense colla)</option>
                  {operaris.map((op) => (
                    <option key={op.id} value={op.id}>
                      {op.nom} {op.cognoms || ""} ({op.nif || "Operari"})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1 flex items-center gap-1.5">
                  <Truck className="w-3.5 h-3.5 text-slate-400" />
                  <span>Vehicle Assignat (Flota)</span>
                </label>
                <select
                  value={formData.vehicle_id}
                  onChange={(e) => setFormData({ ...formData, vehicle_id: e.target.value })}
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary"
                >
                  <option value="">Sense vehicle assignat</option>
                  {vehicles.map((v) => (
                    <option key={v.id} value={v.id}>
                      {v.matricula} — {v.marca || ""} {v.model || ""}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Data Planificada i Estat */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1 flex items-center gap-1.5">
                  <Calendar className="w-3.5 h-3.5 text-slate-400" />
                  <span>Data Planificada</span>
                </label>
                <input
                  type="date"
                  required
                  value={formData.data_planificacio}
                  onChange={(e) => setFormData({ ...formData, data_planificacio: e.target.value })}
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary font-mono"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1 flex items-center gap-1.5">
                  <Clock className="w-3.5 h-3.5 text-slate-400" />
                  <span>Estat Operatiu</span>
                </label>
                <select
                  value={formData.estat}
                  onChange={(e) => setFormData({ ...formData, estat: e.target.value })}
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary font-medium"
                >
                  <option value="PENDENT">PENDENT</option>
                  <option value="ASSIGNADA">ASSIGNADA</option>
                  <option value="PROGRAMADA">PROGRAMADA</option>
                  <option value="EN_RUTA">EN RUTA</option>
                  <option value="EN_OBRA">EN OBRA</option>
                  <option value="EN_CURS">EN CURS</option>
                  <option value="COMPLETADA">COMPLETADA</option>
                  <option value="BLOQUEJADA">BLOQUEJADA</option>
                </select>
              </div>
            </div>

            {/* Peu Modal */}
            <div className="flex items-center justify-between pt-4 border-t border-slate-100 dark:border-slate-800">
              <span className="text-[11px] font-mono text-slate-400">
                Versió de bloqueig optimista: v{formData.versio}
              </span>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={onClose}
                  disabled={saving}
                  className="px-4 py-2 rounded-xl text-xs font-bold text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                >
                  Cancel·lar
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="px-5 py-2 rounded-xl bg-primary hover:bg-primary-container text-white text-xs font-bold shadow-sm transition-all flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
                >
                  {saving ? (
                    <>
                      <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                      <span>Desant...</span>
                    </>
                  ) : (
                    <>
                      <Save className="w-3.5 h-3.5" />
                      <span>Desar Canvis</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
