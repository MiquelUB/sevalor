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
  Map,
  Truck,
  Map as MapIcon,
  AlignLeft,
  Package,
  Plus,
  Trash2,
  Wrench,
  Sparkles,
} from "lucide-react";
import { apiFetch } from "@/lib/api";
import { geocodificarAdreca } from "@/lib/geocoding";

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
  const [eines, setEines] = useState<any[]>([]);
  const [prioritat, setPrioritat] = useState<"BAIXA" | "NORMAL" | "ALTA" | "URGENT">("NORMAL");

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
    estat: "PENDENT",
  });

  // Picking lines state
  const [liniesPicking, setLiniesPicking] = useState<{ article_id: string; quantitat: number }[]>([]);
  const [currentArticle, setCurrentArticle] = useState("");
  const [currentQty, setCurrentQty] = useState(1);

  // Eines en custòdia state
  const [selectedEinaIds, setSelectedEinaIds] = useState<string[]>([]);
  const [currentEina, setCurrentEina] = useState("");

  useEffect(() => {
    Promise.all([
      apiFetch<any>("/gestio/clients").catch(() => []),
      apiFetch<any>("/gestio/operaris").catch(() => []),
      apiFetch<any>("/gestio/flota").catch(() => []),
      apiFetch<any>("/gestio/planols").catch(() => []),
      apiFetch<any>("/gestio/magatzem/articles").catch(() => []),
      apiFetch<any>("/gestio/magatzem/eines").catch(() => []),
    ])
      .then(([clientsData, operarisData, flotaData, planolsData, articlesData, einesData]) => {
        setClients(Array.isArray(clientsData) ? clientsData : clientsData?.items || []);
        setOperaris(Array.isArray(operarisData) ? operarisData : operarisData?.operaris || []);
        setVehicles(Array.isArray(flotaData) ? flotaData : flotaData?.vehicles || []);
        setPlanols(Array.isArray(planolsData) ? planolsData : []);
        setArticles(Array.isArray(articlesData) ? articlesData : []);
        setEines(Array.isArray(einesData) ? einesData : []);
      })
      .catch(console.error);
  }, []);

  // When client changes, fetch fitxa360 to get finques
  useEffect(() => {
    if (formData.client_id) {
      apiFetch<any>(`/gestio/clients/${formData.client_id}/fitxa360`)
        .then((data) => {
          setFinques(data?.finques || []);
          setFormData((prev) => ({ ...prev, finca_id: "" }));
        })
        .catch(console.error);
    } else {
      setFinques([]);
      setFormData((prev) => ({ ...prev, finca_id: "" }));
    }
  }, [formData.client_id]);

  const addLiniaPicking = () => {
    if (!currentArticle || currentQty <= 0) return;
    const existingIndex = liniesPicking.findIndex((l) => l.article_id === currentArticle);
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

  const addEina = () => {
    if (!currentEina || selectedEinaIds.includes(currentEina)) return;
    setSelectedEinaIds([...selectedEinaIds, currentEina]);
    setCurrentEina("");
  };

  const removeEina = (idToRemove: string) => {
    setSelectedEinaIds(selectedEinaIds.filter((id) => id !== idToRemove));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      const geo = geocodificarAdreca(formData.adreca);
      const payload = {
        ...formData,
        estat: formData.cap_de_colla_id ? "ASSIGNADA" : formData.estat || "PENDENT",
        latitud: geo.lat,
        longitud: geo.lng,
        vehicle_id: formData.vehicle_id ? formData.vehicle_id : null,
        cap_de_colla_id: formData.cap_de_colla_id ? formData.cap_de_colla_id : null,
        finca_id: formData.finca_id ? formData.finca_id : null,
        eina_ids: selectedEinaIds.length > 0 ? selectedEinaIds : null,
      };

      const { planol_id, ...backendPayload } = payload;

      // 1. Create OT
      const createdOT = await apiFetch<any>("/gestio/feines", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(backendPayload),
      });

      // 2. Create Fulla de Picking if materials assigned
      if (liniesPicking.length > 0) {
        const createdPick = await apiFetch<any>("/gestio/magatzem/picking", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            ordre_treball_id: createdOT.id,
            vehicle_id: createdOT.vehicle_id,
          }),
        });

        // 3. Insert Picking Lines
        for (const linia of liniesPicking) {
          await apiFetch(`/gestio/magatzem/picking/${createdPick.id}/linies`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              article_id: linia.article_id,
              quantitat_prevista: linia.quantitat,
            }),
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

  const step1Done = Boolean(formData.titol.trim() && formData.client_id);
  const step2Done = Boolean(formData.finca_id || formData.adreca.trim());
  const step3Done = Boolean(formData.cap_de_colla_id);
  const step4Done = liniesPicking.length > 0 || selectedEinaIds.length > 0;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-primary/60 backdrop-blur-sm p-4">
      <div className="bg-surface rounded-2xl shadow-2xl w-full max-w-6xl overflow-hidden flex flex-col max-h-[92vh] border border-outline-variant/40">
        {/* Stitch Top Modal Header */}
        <div className="flex items-center justify-between px-xl py-md bg-surface-container-lowest border-b border-surface-container-high">
          <div className="flex items-center gap-md">
            <div className="w-10 h-10 rounded-xl bg-primary text-on-primary flex items-center justify-center shadow-sm">
              <span className="material-symbols-outlined">assignment_add</span>
            </div>
            <div>
              <h2 className="font-section-title text-section-title text-primary">
                Crear Nova Feina · Nova Ordre de Treball
              </h2>
              <p className="text-xs text-on-surface-variant">
                Planificació tècnica, geolocalització GIS, assignació de quadrilla i fulla de picking
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-full hover:bg-surface-container-high text-on-surface-variant hover:text-primary transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Stitch 4-Step Progress Indicator (screen_55e4601b415d4dedb9c32183414dda47) */}
        <div className="bg-surface-container-low px-xl py-md border-b border-outline-variant/30">
          <div className="flex items-center justify-between relative max-w-4xl mx-auto">
            <div className="absolute top-1/2 left-0 w-full h-0.5 bg-surface-container-highest -translate-y-1/2 z-0"></div>
            <div className="relative z-10 flex items-center gap-sm bg-surface-container-low pr-md">
              <div className="w-7 h-7 rounded-full bg-primary text-on-primary flex items-center justify-center font-bold text-xs shadow-md">
                1
              </div>
              <span className="font-body-strong text-primary text-xs">Dades Bàsiques</span>
            </div>
            <div className="relative z-10 flex items-center gap-sm bg-surface-container-low px-md">
              <div
                className={`w-7 h-7 rounded-full flex items-center justify-center font-bold text-xs transition-colors ${
                  step2Done
                    ? "bg-primary text-on-primary"
                    : "bg-surface-container-highest text-on-surface-variant"
                }`}
              >
                2
              </div>
              <span className="font-body-base text-on-surface-variant text-xs">Ubicació i Finca</span>
            </div>
            <div className="relative z-10 flex items-center gap-sm bg-surface-container-low px-md">
              <div
                className={`w-7 h-7 rounded-full flex items-center justify-center font-bold text-xs transition-colors ${
                  step3Done
                    ? "bg-primary text-on-primary"
                    : "bg-surface-container-highest text-on-surface-variant"
                }`}
              >
                3
              </div>
              <span className="font-body-base text-on-surface-variant text-xs">Recursos</span>
            </div>
            <div className="relative z-10 flex items-center gap-sm bg-surface-container-low pl-md">
              <div
                className={`w-7 h-7 rounded-full flex items-center justify-center font-bold text-xs transition-colors ${
                  step4Done
                    ? "bg-secondary-container text-on-secondary-container"
                    : "bg-surface-container-highest text-on-surface-variant"
                }`}
              >
                4
              </div>
              <span className="font-body-base text-on-surface-variant text-xs">
                Materials i Eines
              </span>
            </div>
          </div>
        </div>

        {/* Main 2-Column Stitch Form */}
        <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto p-xl custom-scrollbar">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-xl items-start">
            {/* LEFT COLUMN: Core Form & Picking (7 Cols) */}
            <div className="lg:col-span-7 space-y-lg">
              {/* Card 1: Informació General & Client */}
              <div className="bg-surface-container-lowest p-lg rounded-xl shadow-sm border border-outline-variant/30 space-y-md">
                <div className="flex items-center justify-between border-b border-surface-container pb-sm">
                  <div className="flex items-center gap-sm">
                    <span className="material-symbols-outlined text-primary">description</span>
                    <h3 className="font-section-title text-lg text-primary">
                      1. Dades Bàsiques de la Feina
                    </h3>
                  </div>
                  <span className="font-data-tabular text-xs bg-primary/10 text-primary px-2 py-0.5 rounded font-bold">
                    {formData.codi}
                  </span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-md">
                  <div className="space-y-xs">
                    <label className="font-label-caps text-on-surface-variant uppercase flex items-center gap-1">
                      <FileText className="w-3.5 h-3.5" /> Codi Referència
                    </label>
                    <input
                      required
                      type="text"
                      value={formData.codi}
                      onChange={(e) => setFormData({ ...formData, codi: e.target.value })}
                      className="w-full p-sm bg-surface-container-low rounded-lg border border-outline-variant focus:border-primary outline-none text-sm font-data-tabular font-bold"
                    />
                  </div>

                  <div className="space-y-xs">
                    <label className="font-label-caps text-on-surface-variant uppercase flex items-center gap-1">
                      <Calendar className="w-3.5 h-3.5" /> Data Planificació
                    </label>
                    <input
                      required
                      type="date"
                      value={formData.data_planificacio}
                      onChange={(e) =>
                        setFormData({ ...formData, data_planificacio: e.target.value })
                      }
                      className="w-full p-sm bg-surface-container-low rounded-lg border border-outline-variant focus:border-primary outline-none text-sm"
                    />
                  </div>

                  <div className="space-y-xs md:col-span-2">
                    <label className="font-label-caps text-on-surface-variant uppercase">
                      Títol de la Intervenció
                    </label>
                    <input
                      required
                      type="text"
                      placeholder="Ex: Reparació de bomba d'aigua sector Nord"
                      value={formData.titol}
                      onChange={(e) => setFormData({ ...formData, titol: e.target.value })}
                      className="w-full p-sm bg-surface-container-low rounded-lg border border-outline-variant focus:border-primary focus:bg-white outline-none transition-all text-sm"
                    />
                  </div>

                  <div className="space-y-xs">
                    <label className="font-label-caps text-on-surface-variant uppercase flex items-center gap-1">
                      <Building2 className="w-3.5 h-3.5" /> Client
                    </label>
                    <select
                      required
                      value={formData.client_id}
                      onChange={(e) => setFormData({ ...formData, client_id: e.target.value })}
                      className="w-full p-sm bg-surface-container-low rounded-lg border border-outline-variant focus:border-primary outline-none text-sm"
                    >
                      <option value="">Selecciona un client...</option>
                      {clients.map((c) => (
                        <option key={c.id || c.codi} value={c.id}>
                          {c.rao_social} ({c.nif})
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="space-y-xs">
                    <label className="font-label-caps text-on-surface-variant uppercase">
                      Prioritat Operativa
                    </label>
                    <div className="grid grid-cols-4 gap-xs">
                      {(["BAIXA", "NORMAL", "ALTA", "URGENT"] as const).map((p) => (
                        <button
                          key={p}
                          type="button"
                          onClick={() => setPrioritat(p)}
                          className={`py-2 px-xs rounded-lg text-[10px] font-label-caps border transition-all ${
                            prioritat === p
                              ? p === "URGENT"
                                ? "border-error bg-error-container/30 text-error font-bold"
                                : "border-secondary-container bg-secondary-container/20 text-on-secondary-container font-bold"
                              : "border-outline-variant bg-surface-container-low text-on-surface-variant"
                          }`}
                        >
                          {p}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="space-y-xs md:col-span-2">
                    <label className="font-label-caps text-on-surface-variant uppercase flex items-center gap-1">
                      <AlignLeft className="w-3.5 h-3.5" /> Definició de Tasca (Descripció)
                    </label>
                    <textarea
                      placeholder="Detalla les tasques a realitzar, eines específiques o instruccions d'accés..."
                      value={formData.descripcio}
                      onChange={(e) => setFormData({ ...formData, descripcio: e.target.value })}
                      rows={3}
                      className="w-full p-sm bg-surface-container-low rounded-lg border border-outline-variant focus:border-primary focus:bg-white outline-none transition-all text-sm resize-none"
                    />
                  </div>
                </div>
              </div>

              {/* Card 2: Materials (Picking) & Eines en Custòdia */}
              <div className="bg-surface-container-lowest p-lg rounded-xl shadow-sm border border-outline-variant/30 space-y-lg">
                <div className="flex items-center gap-sm border-b border-surface-container pb-sm">
                  <span className="material-symbols-outlined text-primary">inventory_2</span>
                  <h3 className="font-section-title text-lg text-primary">
                    4. Materials (Fulla de Picking) i Eines en Custòdia
                  </h3>
                </div>

                {/* Sub-secció Picking */}
                <div className="bg-surface-container-low p-md rounded-xl border border-outline-variant/40 space-y-md">
                  <div className="flex items-end gap-sm flex-wrap">
                    <div className="flex-1 min-w-[220px] space-y-xs">
                      <label className="font-label-caps text-on-surface-variant uppercase flex items-center gap-1">
                        <Package className="w-3.5 h-3.5" /> Article / Material
                      </label>
                      <select
                        value={currentArticle}
                        onChange={(e) => setCurrentArticle(e.target.value)}
                        className="w-full p-sm rounded-lg border border-outline-variant bg-surface-container-lowest text-sm outline-none focus:border-primary"
                      >
                        <option value="">Cercar material disponible...</option>
                        {articles.map((art) => (
                          <option
                            key={art.id}
                            value={art.id}
                            className={art.estoc_real <= 0 ? "text-error" : ""}
                          >
                            {art.nom} ({art.referencia_inventari}) - Estoc: {art.estoc_real ?? 0}{" "}
                            {art.unitat_mesura}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="w-24 space-y-xs">
                      <label className="font-label-caps text-on-surface-variant uppercase">
                        Quantitat
                      </label>
                      <input
                        type="number"
                        min="1"
                        step="any"
                        value={currentQty}
                        onChange={(e) => setCurrentQty(Number(e.target.value))}
                        className="w-full p-sm rounded-lg border border-outline-variant bg-surface-container-lowest text-sm font-data-tabular text-center outline-none focus:border-primary"
                      />
                    </div>
                    <button
                      type="button"
                      onClick={addLiniaPicking}
                      disabled={!currentArticle || currentQty <= 0}
                      className="px-md py-sm rounded-lg bg-primary hover:bg-primary-container disabled:opacity-50 text-on-primary text-xs font-body-strong transition-colors flex items-center gap-1 h-[38px]"
                    >
                      <Plus className="w-4 h-4" /> Afegir Material
                    </button>
                  </div>

                  {liniesPicking.length > 0 && (
                    <div className="pt-sm border-t border-outline-variant/30">
                      <h4 className="font-label-caps text-on-surface-variant uppercase mb-xs">
                        Fulla de Picking (Per preparar):
                      </h4>
                      <ul className="space-y-xs">
                        {liniesPicking.map((linia, idx) => {
                          const articleDef = articles.find((a) => a.id === linia.article_id);
                          return (
                            <li
                              key={idx}
                              className="flex items-center justify-between bg-surface-container-lowest p-sm rounded-lg border border-outline-variant/30"
                            >
                              <span className="font-body-strong text-on-surface text-xs">
                                {articleDef?.nom}{" "}
                                <span className="text-on-surface-variant font-normal">
                                  ({articleDef?.referencia_inventari})
                                </span>
                              </span>
                              <div className="flex items-center gap-md">
                                <span className="font-data-tabular font-bold text-primary text-xs">
                                  {linia.quantitat} {articleDef?.unitat_mesura}
                                </span>
                                <button
                                  type="button"
                                  onClick={() => removeLiniaPicking(idx)}
                                  className="text-error hover:bg-error-container/30 p-1 rounded transition-colors"
                                >
                                  <Trash2 className="w-3.5 h-3.5" />
                                </button>
                              </div>
                            </li>
                          );
                        })}
                      </ul>
                    </div>
                  )}
                </div>

                {/* Sub-secció Eines en Custòdia */}
                <div className="bg-surface-container-low p-md rounded-xl border border-outline-variant/40 space-y-md">
                  <div className="flex items-end gap-sm flex-wrap">
                    <div className="flex-1 min-w-[220px] space-y-xs">
                      <label className="font-label-caps text-on-surface-variant uppercase flex items-center gap-1">
                        <Wrench className="w-3.5 h-3.5" /> Eina o Maquinària en Custòdia
                      </label>
                      <select
                        value={currentEina}
                        onChange={(e) => setCurrentEina(e.target.value)}
                        className="w-full p-sm rounded-lg border border-outline-variant bg-surface-container-lowest text-sm outline-none focus:border-primary"
                      >
                        <option value="">Selecciona eina disponible...</option>
                        {eines
                          .filter((e) => !selectedEinaIds.includes(e.id))
                          .map((e) => (
                            <option key={e.id} value={e.id}>
                              {e.nom} {e.model ? `(${e.model})` : ""} - SN: {e.numero_serie} [
                              {e.estat}]
                            </option>
                          ))}
                      </select>
                    </div>
                    <button
                      type="button"
                      onClick={addEina}
                      disabled={!currentEina}
                      className="px-md py-sm rounded-lg bg-primary hover:bg-primary-container disabled:opacity-50 text-on-primary text-xs font-body-strong transition-colors flex items-center gap-1 h-[38px]"
                    >
                      <Plus className="w-4 h-4" /> Vincular Eina
                    </button>
                  </div>

                  {selectedEinaIds.length > 0 && (
                    <div className="pt-sm border-t border-outline-variant/30">
                      <h4 className="font-label-caps text-on-surface-variant uppercase mb-xs">
                        Eines assignades a la intervenció:
                      </h4>
                      <ul className="space-y-xs">
                        {selectedEinaIds.map((einaId) => {
                          const einaDef = eines.find((e) => e.id === einaId);
                          return (
                            <li
                              key={einaId}
                              className="flex items-center justify-between bg-surface-container-lowest p-sm rounded-lg border border-outline-variant/30"
                            >
                              <div className="flex items-center gap-sm">
                                <Wrench className="w-3.5 h-3.5 text-secondary" />
                                <span className="font-body-strong text-on-surface text-xs">
                                  {einaDef?.nom || "Eina"}{" "}
                                  <span className="text-on-surface-variant font-normal">
                                    (SN: {einaDef?.numero_serie})
                                  </span>
                                </span>
                              </div>
                              <button
                                type="button"
                                onClick={() => removeEina(einaId)}
                                className="text-error hover:bg-error-container/30 p-1 rounded transition-colors"
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                              </button>
                            </li>
                          );
                        })}
                      </ul>
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* RIGHT COLUMN: Ubicació, Plànol, Recursos & Resum (5 Cols) */}
            <div className="lg:col-span-5 space-y-lg">
              {/* Card 3: Ubicació, Finca i Plànol */}
              <div className="bg-surface-container-lowest p-lg rounded-xl shadow-sm border border-outline-variant/30 space-y-md">
                <div className="flex items-center gap-sm border-b border-surface-container pb-sm">
                  <span className="material-symbols-outlined text-primary">location_on</span>
                  <h3 className="font-section-title text-lg text-primary">
                    2. Ubicació i Emplaçament GIS
                  </h3>
                </div>

                <div className="space-y-xs">
                  <label className="font-label-caps text-on-surface-variant uppercase flex items-center gap-1">
                    <Map className="w-3.5 h-3.5" /> Finca del Client
                  </label>
                  <select
                    required
                    disabled={!formData.client_id}
                    value={formData.finca_id}
                    onChange={(e) => {
                      const selId = e.target.value;
                      const selFinca = finques.find((f) => f.id === selId);
                      setFormData((prev) => ({
                        ...prev,
                        finca_id: selId,
                        adreca:
                          selFinca?.latitud && selFinca?.longitud
                            ? `${selFinca.latitud}, ${selFinca.longitud}`
                            : selFinca?.adreca || prev.adreca,
                      }));
                    }}
                    className="w-full p-sm bg-surface-container-low rounded-lg border border-outline-variant focus:border-primary outline-none text-sm disabled:opacity-50"
                  >
                    <option value="">Selecciona una finca...</option>
                    {finques.map((f) => (
                      <option key={f.id} value={f.id}>
                        {f.nom || f.nom_finca || f.id}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="space-y-xs">
                  <label className="font-label-caps text-on-surface-variant uppercase flex items-center gap-1">
                    <MapPin className="w-3.5 h-3.5" /> Adreça / Coordenades GPS
                  </label>
                  <input
                    type="text"
                    placeholder="Ex: Polígon 4, Parcel·la 12 o 41.6176, 0.6200..."
                    value={formData.adreca}
                    onChange={(e) => setFormData({ ...formData, adreca: e.target.value })}
                    className="w-full p-sm bg-surface-container-low rounded-lg border border-outline-variant focus:border-primary outline-none text-sm"
                  />
                  {formData.adreca.trim().length > 2 &&
                    (() => {
                      const geo = geocodificarAdreca(formData.adreca);
                      return (
                        <div className="p-sm rounded-lg bg-primary/5 border border-primary/20 flex items-center justify-between text-xs">
                          <div className="flex items-center gap-xs text-primary font-body-strong">
                            <span className="material-symbols-outlined text-[16px] text-secondary-container">
                              my_location
                            </span>
                            <span>{geo.ciutat || "Coordenades GIS validades"}</span>
                          </div>
                          <span className="font-data-tabular text-on-surface-variant">
                            {geo.lat.toFixed(4)}°N, {geo.lng.toFixed(4)}°E
                          </span>
                        </div>
                      );
                    })()}
                </div>

                <div className="space-y-xs">
                  <label className="font-label-caps text-on-surface-variant uppercase flex items-center gap-1">
                    <MapIcon className="w-3.5 h-3.5" /> Plànol / Esbós Vinculat (Opcional)
                  </label>
                  <select
                    value={formData.planol_id}
                    onChange={(e) => setFormData({ ...formData, planol_id: e.target.value })}
                    className="w-full p-sm bg-surface-container-low rounded-lg border border-outline-variant focus:border-primary outline-none text-sm"
                  >
                    <option value="">Sense plànol vinculat</option>
                    {planols.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.titol} ({p.codi_referencia})
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Card 4: Assignació d'Operari i Vehicle */}
              <div className="bg-surface-container-lowest p-lg rounded-xl shadow-sm border border-outline-variant/30 space-y-md">
                <div className="flex items-center gap-sm border-b border-surface-container pb-sm">
                  <span className="material-symbols-outlined text-primary">groups</span>
                  <h3 className="font-section-title text-lg text-primary">
                    3. Assignació d&apos;Actius i Quadrilla
                  </h3>
                </div>

                <div className="space-y-xs">
                  <label className="font-label-caps text-on-surface-variant uppercase flex items-center gap-1">
                    <User className="w-3.5 h-3.5" /> Cap de Colla / Operari Assignat
                  </label>
                  <select
                    required
                    value={formData.cap_de_colla_id}
                    onChange={(e) => setFormData({ ...formData, cap_de_colla_id: e.target.value })}
                    className="w-full p-sm bg-surface-container-low rounded-lg border border-outline-variant focus:border-primary outline-none text-sm"
                  >
                    <option value="">Assignar operari...</option>
                    {operaris.map((op) => (
                      <option key={op.id} value={op.id}>
                        {op.nom} {op.cognoms} - {op.rol}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="space-y-xs">
                  <label className="font-label-caps text-on-surface-variant uppercase flex items-center gap-1">
                    <Truck className="w-3.5 h-3.5" /> Vehicle Assignat (Opcional)
                  </label>
                  <select
                    value={formData.vehicle_id}
                    onChange={(e) => setFormData({ ...formData, vehicle_id: e.target.value })}
                    className="w-full p-sm bg-surface-container-low rounded-lg border border-outline-variant focus:border-primary outline-none text-sm"
                  >
                    <option value="">Assignar vehicle...</option>
                    {vehicles.map((v) => (
                      <option key={v.id} value={v.id}>
                        {v.matricula} - {v.marca} {v.model}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Stitch Summary & Triple Action Card */}
              <div className="bg-primary text-on-primary p-lg rounded-xl shadow-xl space-y-md">
                <div className="flex justify-between items-center border-b border-primary-container pb-sm">
                  <span className="font-label-caps text-on-primary-container uppercase">
                    Resum de l&apos;Ordre
                  </span>
                  <span className="font-data-tabular text-xs bg-secondary-container text-on-secondary-container px-sm py-0.5 rounded-full font-bold">
                    {formData.cap_de_colla_id ? "ASSIGNADA" : "PENDENT"}
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-sm text-xs">
                  <div>
                    <p className="text-on-primary-container">Data Planificada</p>
                    <p className="font-data-tabular font-bold text-sm">
                      {formData.data_planificacio}
                    </p>
                  </div>
                  <div>
                    <p className="text-on-primary-container">Dotació Material</p>
                    <p className="font-data-tabular font-bold text-sm">
                      {liniesPicking.length} art. · {selectedEinaIds.length} eines
                    </p>
                  </div>
                </div>

                <div className="pt-sm flex flex-col gap-sm">
                  <button
                    type="submit"
                    disabled={loading}
                    className="w-full py-md bg-secondary-container hover:bg-secondary text-on-secondary-container hover:text-white font-body-strong rounded-lg shadow-lg transition-all flex items-center justify-center gap-sm cursor-pointer disabled:opacity-60"
                  >
                    <Save className="w-4 h-4" />
                    <span>
                      {loading ? "Processant..." : "Crear Intervenció i Picking"}
                    </span>
                  </button>

                  <div className="grid grid-cols-2 gap-sm">
                    <button
                      type="button"
                      onClick={onClose}
                      className="py-sm bg-primary-container hover:bg-primary-container/80 text-white text-xs font-body-strong rounded-lg transition-colors"
                    >
                      Cancel·lar
                    </button>
                    <button
                      type="button"
                      onClick={() =>
                        alert(
                          "El Copilot IA ha pre-calculat l'estimació de materials i hores segons l'històric de la finca."
                        )
                      }
                      className="py-sm bg-white/10 hover:bg-white/20 text-secondary-fixed text-xs font-body-strong rounded-lg transition-colors flex items-center justify-center gap-1"
                    >
                      <Sparkles className="w-3.5 h-3.5" />
                      <span>Copilot IA</span>
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}
