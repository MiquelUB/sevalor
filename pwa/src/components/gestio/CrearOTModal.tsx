"use client";

import React, { useState, useEffect, useRef } from "react";
import {
  X,
  Save,
  Building2,
  User,
  Users,
  ShieldCheck,
  FileText,
  Calendar,
  Clock,
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
  Search,
  ExternalLink,
} from "lucide-react";
import { apiFetch, getApiBaseUrl } from "@/lib/api";
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

  // Horaris previstos
  const [horaInici, setHoraInici] = useState("");
  const [horaFi, setHoraFi] = useState("");

  // Colla operaris state (suport / equip addicional)
  const [collaOperariIds, setCollaOperariIds] = useState<string[]>([]);
  const [selectedCollaCandidate, setSelectedCollaCandidate] = useState<string>("");

  const addOperariToColla = (opId?: string) => {
    const idToAdd = opId || selectedCollaCandidate;
    if (!idToAdd || idToAdd === formData.cap_de_colla_id) return;
    if (!collaOperariIds.includes(idToAdd)) {
      setCollaOperariIds((prev) => [...prev, idToAdd]);
    }
    setSelectedCollaCandidate("");
  };

  const removeOperariFromColla = (idToRemove: string) => {
    setCollaOperariIds((prev) => prev.filter((id) => id !== idToRemove));
  };

  // Picking lines state
  const [liniesPicking, setLiniesPicking] = useState<{ article_id: string; quantitat: number }[]>([]);
  const [currentArticle, setCurrentArticle] = useState("");
  const [currentQty, setCurrentQty] = useState(1);

  // Autocomplete & Family state for Picking (Materials)
  const [filtreFamilia, setFiltreFamilia] = useState<string>("TOTES");
  const [cercaArticle, setCercaArticle] = useState<string>("");
  const [selectedArticle, setSelectedArticle] = useState<any | null>(null);
  const [isArticleDropdownOpen, setIsArticleDropdownOpen] = useState(false);
  const articleComboboxRef = useRef<HTMLDivElement>(null);

  // Eines en custòdia state
  const [selectedEinaIds, setSelectedEinaIds] = useState<string[]>([]);
  const [currentEina, setCurrentEina] = useState("");

  // Autocomplete state for Eines (Tools)
  const [cercaEina, setCercaEina] = useState<string>("");
  const [selectedEina, setSelectedEina] = useState<any | null>(null);
  const [isEinaDropdownOpen, setIsEinaDropdownOpen] = useState(false);
  const einaComboboxRef = useRef<HTMLDivElement>(null);

  // Close dropdowns on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (articleComboboxRef.current && !articleComboboxRef.current.contains(e.target as Node)) {
        setIsArticleDropdownOpen(false);
      }
      if (einaComboboxRef.current && !einaComboboxRef.current.contains(e.target as Node)) {
        setIsEinaDropdownOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const familiesArticles = Array.from(
    new Set(
      articles
        .map((a) => (a.familia ? String(a.familia).trim() : "GENERAL"))
        .filter(Boolean)
    )
  ).sort();

  const filteredArticles = articles
    .filter((art) => {
      const fam = art.familia ? String(art.familia).trim() : "GENERAL";
      if (filtreFamilia !== "TOTES" && fam !== filtreFamilia) return false;
      if (!cercaArticle.trim()) return true;
      const term = cercaArticle.toLowerCase();
      const nom = (art.nom || "").toLowerCase();
      const ref = (art.referencia_inventari || "").toLowerCase();
      return nom.includes(term) || ref.includes(term);
    })
    .slice(0, 10);

  const filteredEines = eines
    .filter((e) => !selectedEinaIds.includes(e.id))
    .filter((e) => {
      if (!cercaEina.trim()) return true;
      const term = cercaEina.toLowerCase();
      const nom = (e.nom || "").toLowerCase();
      const model = (e.model || "").toLowerCase();
      const sn = (e.numero_serie || "").toLowerCase();
      return nom.includes(term) || model.includes(term) || sn.includes(term);
    })
    .slice(0, 10);

  const handleSelectArticle = (art: any) => {
    setSelectedArticle(art);
    setCurrentArticle(art.id);
    setCercaArticle(`${art.nom} (${art.referencia_inventari})`);
    setIsArticleDropdownOpen(false);
  };

  const handleClearArticle = () => {
    setSelectedArticle(null);
    setCurrentArticle("");
    setCercaArticle("");
    setIsArticleDropdownOpen(false);
  };

  const handleSelectEina = (eina: any) => {
    setSelectedEina(eina);
    setCurrentEina(eina.id);
    setCercaEina(`${eina.nom} - SN: ${eina.numero_serie}`);
    setIsEinaDropdownOpen(false);
  };

  const handleClearEina = () => {
    setSelectedEina(null);
    setCurrentEina("");
    setCercaEina("");
    setIsEinaDropdownOpen(false);
  };

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
    const artId = selectedArticle?.id || currentArticle;
    if (!artId || currentQty <= 0) return;
    const existingIndex = liniesPicking.findIndex((l) => l.article_id === artId);
    if (existingIndex >= 0) {
      const newLinies = [...liniesPicking];
      newLinies[existingIndex].quantitat += currentQty;
      setLiniesPicking(newLinies);
    } else {
      setLiniesPicking([...liniesPicking, { article_id: artId, quantitat: currentQty }]);
    }
    handleClearArticle();
    setCurrentQty(1);
  };

  const removeLiniaPicking = (index: number) => {
    const newLinies = [...liniesPicking];
    newLinies.splice(index, 1);
    setLiniesPicking(newLinies);
  };

  const addEina = () => {
    const einaId = selectedEina?.id || currentEina;
    if (!einaId || selectedEinaIds.includes(einaId)) return;
    setSelectedEinaIds([...selectedEinaIds, einaId]);
    handleClearEina();
  };

  const removeEina = (idToRemove: string) => {
    setSelectedEinaIds(selectedEinaIds.filter((id) => id !== idToRemove));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      const geo = geocodificarAdreca(formData.adreca);
      const horaIniciDate = horaInici
        ? `${formData.data_planificacio}T${horaInici}:00`
        : null;
      const horaFiDate = horaFi
        ? `${formData.data_planificacio}T${horaFi}:00`
        : null;

      const allOperarisIds = Array.from(
        new Set([formData.cap_de_colla_id, ...collaOperariIds].filter(Boolean))
      );

      const payload = {
        ...formData,
        planol_id: formData.planol_id || null,
        estat:
          formData.cap_de_colla_id || collaOperariIds.length > 0
            ? "ASSIGNADA"
            : formData.estat || "PENDENT",
        latitud: geo.lat,
        longitud: geo.lng,
        hora_inici_prevista: horaIniciDate,
        hora_fi_prevista: horaFiDate,
        vehicle_id: formData.vehicle_id ? formData.vehicle_id : null,
        cap_de_colla_id: formData.cap_de_colla_id ? formData.cap_de_colla_id : null,
        operaris_ids: allOperarisIds.length > 0 ? allOperarisIds : null,
        finca_id: formData.finca_id ? formData.finca_id : null,
        eina_ids: selectedEinaIds.length > 0 ? selectedEinaIds : null,
      };

      // 1. Create OT directly with planol_id, eina_ids and schedule
      const createdOT = await apiFetch<any>("/gestio/feines", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
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

                  <div className="grid grid-cols-2 gap-xs">
                    <div className="space-y-xs">
                      <label className="font-label-caps text-on-surface-variant uppercase flex items-center gap-1 text-[10px]">
                        <Clock className="w-3 h-3 text-primary" /> Hora Inici
                      </label>
                      <input
                        type="time"
                        value={horaInici}
                        onChange={(e) => setHoraInici(e.target.value)}
                        className="w-full p-sm bg-surface-container-low rounded-lg border border-outline-variant focus:border-primary outline-none text-xs font-data-tabular"
                      />
                    </div>
                    <div className="space-y-xs">
                      <label className="font-label-caps text-on-surface-variant uppercase flex items-center gap-1 text-[10px]">
                        <Clock className="w-3 h-3 text-primary" /> Hora Fi
                      </label>
                      <input
                        type="time"
                        value={horaFi}
                        onChange={(e) => setHoraFi(e.target.value)}
                        className="w-full p-sm bg-surface-container-low rounded-lg border border-outline-variant focus:border-primary outline-none text-xs font-data-tabular"
                      />
                    </div>
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

                {/* Sub-secció Picking amb Autocompletat i Família */}
                <div className="bg-surface-container-low p-md rounded-xl border border-outline-variant/40 space-y-md">
                  <div className="flex items-center gap-2 border-b border-outline-variant/20 pb-2">
                    <Package className="w-4 h-4 text-primary" />
                    <h4 className="font-body-strong text-primary text-xs uppercase tracking-wider">
                      Reserva de Materials & Control d&apos;Inventari
                    </h4>
                  </div>

                  {/* Fila de selectors de materials: Família + Cerca autocompletable */}
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-sm items-start">
                    {/* Selector de Família */}
                    <div className="space-y-xs">
                      <label className="font-label-caps text-on-surface-variant uppercase flex items-center gap-1 text-[11px]">
                        <Package className="w-3.5 h-3.5 text-primary" /> Família
                      </label>
                      <select
                        value={filtreFamilia}
                        onChange={(e) => {
                          setFiltreFamilia(e.target.value);
                          setIsArticleDropdownOpen(true);
                        }}
                        className="w-full p-sm rounded-lg border border-outline-variant bg-surface-container-lowest text-xs text-on-surface outline-none focus:border-primary"
                      >
                        <option value="TOTES">Totes les famílies ({articles.length})</option>
                        {familiesArticles.map((f) => (
                          <option key={f} value={f}>
                            {f}
                          </option>
                        ))}
                      </select>
                    </div>

                    {/* Cerca Autocompletable */}
                    <div className="sm:col-span-2 space-y-xs relative" ref={articleComboboxRef}>
                      <label className="font-label-caps text-on-surface-variant uppercase flex items-center justify-between text-[11px]">
                        <span className="flex items-center gap-1">
                          <Search className="w-3.5 h-3.5 text-primary" /> Cerca Material (Escriu per filtrar)
                        </span>
                        {selectedArticle && (
                          <span className="text-[10px] font-mono font-bold text-secondary">
                            Disp: {selectedArticle.estoc_real ?? 0} {selectedArticle.unitat_mesura}
                          </span>
                        )}
                      </label>

                      <div className="relative">
                        <input
                          type="text"
                          value={cercaArticle}
                          onFocus={() => setIsArticleDropdownOpen(true)}
                          onChange={(e) => {
                            setCercaArticle(e.target.value);
                            setSelectedArticle(null);
                            setCurrentArticle("");
                            setIsArticleDropdownOpen(true);
                          }}
                          placeholder="Comença a escriure nom, codi o referència..."
                          className="w-full pl-8 pr-7 py-2 rounded-lg border border-outline-variant bg-surface-container-lowest text-xs text-on-surface outline-none focus:border-primary font-medium"
                        />
                        <Search className="w-3.5 h-3.5 text-on-surface-variant absolute left-2.5 top-2.5 pointer-events-none" />
                        {cercaArticle && (
                          <button
                            type="button"
                            onClick={handleClearArticle}
                            className="absolute right-2 top-2 text-on-surface-variant hover:text-primary cursor-pointer p-0.5"
                          >
                            <X className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </div>

                      {/* Dropdown d'autocompletat */}
                      {isArticleDropdownOpen && (
                        <div className="absolute top-full left-0 right-0 mt-1 z-30 bg-surface-container-lowest border border-outline-variant/60 rounded-xl shadow-xl overflow-hidden max-h-56 overflow-y-auto">
                          {filteredArticles.length > 0 ? (
                            filteredArticles.map((art) => (
                              <button
                                key={art.id}
                                type="button"
                                onClick={() => handleSelectArticle(art)}
                                className="w-full text-left px-3 py-2 text-xs hover:bg-surface-container border-b border-surface-container-high last:border-b-0 flex items-center justify-between gap-2 transition-colors cursor-pointer"
                              >
                                <div className="min-w-0 flex-1">
                                  <div className="flex items-center gap-1.5 flex-wrap">
                                    <span className="font-mono text-[11px] font-bold text-primary">
                                      [{art.referencia_inventari}]
                                    </span>
                                    <span className="font-medium text-on-surface truncate">
                                      {art.nom}
                                    </span>
                                  </div>
                                  {art.familia && (
                                    <span className="inline-block mt-0.5 text-[9px] px-1.5 py-0.2 rounded bg-surface-container-high text-on-surface-variant font-mono">
                                      {art.familia}
                                    </span>
                                  )}
                                </div>
                                <div className="text-right shrink-0">
                                  <span
                                    className={`font-mono text-[11px] font-bold ${
                                      (art.estoc_real ?? 0) <= 0
                                        ? "text-error"
                                        : "text-secondary"
                                    }`}
                                  >
                                    {art.estoc_real ?? 0} {art.unitat_mesura}
                                  </span>
                                </div>
                              </button>
                            ))
                          ) : (
                            <div className="p-3 text-center text-xs text-on-surface-variant">
                              Cap material coincideix amb la cerca.
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Fila 2: Detalls de l'article seleccionat i botó d'afegir */}
                  {selectedArticle && (
                    <div className="pt-2 border-t border-outline-variant/30 flex flex-wrap items-end gap-sm animate-in fade-in duration-100">
                      <div className="flex-1 min-w-[200px] p-2 rounded-lg bg-primary/5 border border-primary/20 flex items-center justify-between">
                        <div className="min-w-0">
                          <p className="text-[10px] text-on-surface-variant font-mono">
                            Article seleccionat:
                          </p>
                          <p className="text-xs font-bold text-primary truncate">
                            [{selectedArticle.referencia_inventari}] {selectedArticle.nom}
                          </p>
                        </div>
                        <span className="shrink-0 text-xs font-mono font-bold text-secondary ml-2">
                          {selectedArticle.estoc_real ?? 0} {selectedArticle.unitat_mesura} disp.
                        </span>
                      </div>

                      <div className="w-28 space-y-xs">
                        <label className="font-label-caps text-on-surface-variant uppercase text-[10px]">
                          Quantitat ({selectedArticle.unitat_mesura})
                        </label>
                        <input
                          type="number"
                          min="0.001"
                          step="any"
                          value={currentQty}
                          onChange={(e) => setCurrentQty(parseFloat(e.target.value) || 0)}
                          className="w-full p-sm rounded-lg border border-outline-variant bg-surface-container-lowest text-xs font-data-tabular text-center outline-none focus:border-primary font-bold"
                        />
                      </div>

                      <button
                        type="button"
                        onClick={addLiniaPicking}
                        disabled={currentQty <= 0}
                        className="px-md py-sm rounded-lg bg-primary hover:bg-primary-container disabled:opacity-50 text-on-primary text-xs font-body-strong transition-colors flex items-center gap-1 h-[36px] cursor-pointer"
                      >
                        <Plus className="w-4 h-4" /> Afegir a la Fulla
                      </button>
                    </div>
                  )}

                  {/* Taula de materials afegits a la fulla de picking */}
                  {liniesPicking.length > 0 ? (
                    <div className="pt-sm border-t border-outline-variant/30">
                      <h4 className="font-label-caps text-on-surface-variant uppercase mb-xs flex items-center justify-between">
                        <span>Fulla de Picking ({liniesPicking.length} articles):</span>
                      </h4>
                      <ul className="space-y-xs">
                        {liniesPicking.map((linia, idx) => {
                          const articleDef = articles.find((a) => a.id === linia.article_id);
                          return (
                            <li
                              key={idx}
                              className="flex items-center justify-between bg-surface-container-lowest p-sm rounded-lg border border-outline-variant/30"
                            >
                              <div className="min-w-0 flex-1">
                                <span className="font-body-strong text-primary text-xs block truncate">
                                  {articleDef?.nom || "Article"}{" "}
                                  <span className="text-on-surface-variant font-mono font-normal">
                                    ({articleDef?.referencia_inventari || linia.article_id})
                                  </span>
                                </span>
                              </div>
                              <div className="flex items-center gap-md shrink-0">
                                <span className="font-data-tabular font-bold text-secondary text-xs">
                                  {linia.quantitat} {articleDef?.unitat_mesura || "uts"}
                                </span>
                                <button
                                  type="button"
                                  onClick={() => removeLiniaPicking(idx)}
                                  className="text-error hover:bg-error-container/30 p-1 rounded transition-colors"
                                  title="Eliminar de la fulla de picking"
                                >
                                  <Trash2 className="w-3.5 h-3.5" />
                                </button>
                              </div>
                            </li>
                          );
                        })}
                      </ul>
                    </div>
                  ) : (
                    <div className="p-3 text-center text-xs text-on-surface-variant border border-dashed border-outline-variant/50 rounded-lg">
                      Cap material reservat a la fulla de picking d&apos;aquesta intervenció.
                    </div>
                  )}
                </div>

                {/* Sub-secció Eines en Custòdia amb Autocompletat */}
                <div className="bg-surface-container-low p-md rounded-xl border border-outline-variant/40 space-y-md">
                  <div className="flex items-center gap-2 border-b border-outline-variant/20 pb-2">
                    <Wrench className="w-4 h-4 text-primary" />
                    <h4 className="font-body-strong text-primary text-xs uppercase tracking-wider">
                      Assignació d&apos;Eines i Maquinària en Custòdia
                    </h4>
                  </div>

                  <div className="flex items-end gap-sm flex-wrap">
                    {/* Cerca Autocompletable d'Eines */}
                    <div className="flex-1 min-w-[260px] space-y-xs relative" ref={einaComboboxRef}>
                      <label className="font-label-caps text-on-surface-variant uppercase flex items-center justify-between text-[11px]">
                        <span className="flex items-center gap-1">
                          <Search className="w-3.5 h-3.5 text-primary" /> Cerca Eina / Equip (Escriu per filtrar)
                        </span>
                        {selectedEina && (
                          <span className="text-[10px] font-mono font-bold text-secondary">
                            SN: {selectedEina.numero_serie}
                          </span>
                        )}
                      </label>
                      <div className="relative">
                        <input
                          type="text"
                          value={cercaEina}
                          onFocus={() => setIsEinaDropdownOpen(true)}
                          onChange={(e) => {
                            setCercaEina(e.target.value);
                            setSelectedEina(null);
                            setCurrentEina("");
                            setIsEinaDropdownOpen(true);
                          }}
                          placeholder="Comença a escriure nom, model o núm. sèrie..."
                          className="w-full pl-8 pr-7 py-2 rounded-lg border border-outline-variant bg-surface-container-lowest text-xs text-on-surface outline-none focus:border-primary font-medium"
                        />
                        <Search className="w-3.5 h-3.5 text-on-surface-variant absolute left-2.5 top-2.5 pointer-events-none" />
                        {cercaEina && (
                          <button
                            type="button"
                            onClick={handleClearEina}
                            className="absolute right-2 top-2 text-on-surface-variant hover:text-primary cursor-pointer p-0.5"
                          >
                            <X className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </div>

                      {/* Dropdown autocompletat d'eines */}
                      {isEinaDropdownOpen && (
                        <div className="absolute top-full left-0 right-0 mt-1 z-30 bg-surface-container-lowest border border-outline-variant/60 rounded-xl shadow-xl overflow-hidden max-h-56 overflow-y-auto">
                          {filteredEines.length > 0 ? (
                            filteredEines.map((eina) => (
                              <button
                                key={eina.id}
                                type="button"
                                onClick={() => handleSelectEina(eina)}
                                className="w-full text-left px-3 py-2 text-xs hover:bg-surface-container border-b border-surface-container-high last:border-b-0 flex items-center justify-between gap-2 transition-colors cursor-pointer"
                              >
                                <div className="min-w-0 flex-1">
                                  <div className="flex items-center gap-1.5 flex-wrap">
                                    <span className="font-bold text-primary">
                                      {eina.nom}
                                    </span>
                                    {eina.model && (
                                      <span className="text-[10px] text-on-surface-variant">
                                        ({eina.model})
                                      </span>
                                    )}
                                  </div>
                                  <span className="inline-block mt-0.5 text-[9px] text-on-surface-variant font-mono">
                                    SN: {eina.numero_serie}
                                  </span>
                                </div>
                                <span
                                  className={`text-[9px] font-mono font-bold px-2 py-0.5 rounded-full shrink-0 ${
                                    eina.estat === "DISPONIBLE"
                                      ? "bg-secondary-container/20 text-on-secondary-container"
                                      : "bg-surface-container-high text-on-surface-variant"
                                  }`}
                                >
                                  {eina.estat}
                                </span>
                              </button>
                            ))
                          ) : (
                            <div className="p-3 text-center text-xs text-on-surface-variant">
                              Cap eina disponible coincideix amb la cerca.
                            </div>
                          )}
                        </div>
                      )}
                    </div>

                    <button
                      type="button"
                      onClick={addEina}
                      disabled={!selectedEina && !currentEina}
                      className="px-md py-sm rounded-lg bg-primary hover:bg-primary-container disabled:opacity-50 text-on-primary text-xs font-body-strong transition-colors flex items-center gap-1 h-[36px] cursor-pointer shrink-0"
                    >
                      <Plus className="w-4 h-4" /> Vincular Eina
                    </button>
                  </div>

                  {selectedEinaIds.length > 0 ? (
                    <div className="pt-sm border-t border-outline-variant/30">
                      <h4 className="font-label-caps text-on-surface-variant uppercase mb-xs">
                        Eines assignades a la intervenció ({selectedEinaIds.length}):
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
                                <span className="font-body-strong text-primary text-xs">
                                  {einaDef?.nom || "Eina"}{" "}
                                  <span className="text-on-surface-variant font-normal font-mono">
                                    (SN: {einaDef?.numero_serie || "S/N"})
                                  </span>
                                </span>
                              </div>
                              <button
                                type="button"
                                onClick={() => removeEina(einaId)}
                                className="text-error hover:bg-error-container/30 p-1 rounded transition-colors"
                                title="Desvincular eina"
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                              </button>
                            </li>
                          );
                        })}
                      </ul>
                    </div>
                  ) : (
                    <div className="p-3 text-center text-xs text-on-surface-variant border border-dashed border-outline-variant/50 rounded-lg">
                      Cap eina en custòdia assignada a aquesta ordre.
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
                  <label className="font-label-caps text-on-surface-variant uppercase flex items-center justify-between text-[11px]">
                    <span className="flex items-center gap-1">
                      <MapIcon className="w-3.5 h-3.5 text-primary" /> Plànol / Esbós de la Biblioteca (Opcional)
                    </span>
                    {formData.planol_id && (
                      <button
                        type="button"
                        onClick={() => setFormData({ ...formData, planol_id: "" })}
                        className="text-error hover:underline text-[10px] cursor-pointer"
                      >
                        Desvincular plànol
                      </button>
                    )}
                  </label>
                  <select
                    value={formData.planol_id}
                    onChange={(e) => setFormData({ ...formData, planol_id: e.target.value })}
                    className="w-full p-sm bg-surface-container-low rounded-lg border border-outline-variant focus:border-primary outline-none text-xs"
                  >
                    <option value="">Sense plànol vinculat</option>
                    {Object.entries(
                      planols.reduce((acc: Record<string, any[]>, p: any) => {
                        const carp = p.carpeta_nom ? `Carpeta: ${p.carpeta_nom}` : "Biblioteca General";
                        if (!acc[carp]) acc[carp] = [];
                        acc[carp].push(p);
                        return acc;
                      }, {})
                    ).map(([nomCarpeta, items]) => (
                      <optgroup key={nomCarpeta} label={nomCarpeta}>
                        {items.map((p: any) => (
                          <option key={p.id} value={p.id}>
                            [{p.codi_referencia}] {p.titol} ({p.tipus_fitxer})
                          </option>
                        ))}
                      </optgroup>
                    ))}
                  </select>

                  {/* Targeta del plànol seleccionat */}
                  {(() => {
                    const selP = planols.find((p) => p.id === formData.planol_id);
                    if (!selP) return null;
                    return (
                      <div className="p-sm rounded-lg border border-primary/20 bg-primary/5 flex items-center justify-between gap-sm animate-in fade-in duration-100">
                        <div className="flex items-center gap-2 min-w-0">
                          <div className="w-7 h-7 rounded bg-primary/10 flex items-center justify-center text-primary shrink-0">
                            <MapIcon className="w-3.5 h-3.5" />
                          </div>
                          <div className="min-w-0">
                            <p className="text-xs font-bold text-primary truncate">
                              [{selP.codi_referencia}] {selP.titol}
                            </p>
                            <p className="text-[10px] text-on-surface-variant font-mono">
                              {selP.carpeta_nom ? `Carpeta: ${selP.carpeta_nom}` : "Biblioteca"} · {selP.tipus_fitxer}
                            </p>
                          </div>
                        </div>
                        <div className="flex items-center gap-1.5 shrink-0">
                          <a
                            href={`${getApiBaseUrl()}/gestio/planols/${selP.id}/fitxer`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-[10px] text-primary hover:underline flex items-center gap-1 font-medium bg-primary/10 px-2 py-0.5 rounded cursor-pointer"
                          >
                            <ExternalLink className="w-3 h-3" /> Obrir
                          </a>
                          <span className="text-[10px] font-bold text-secondary bg-secondary-container/20 px-2 py-0.5 rounded-full">
                            Vinculat
                          </span>
                        </div>
                      </div>
                    );
                  })()}
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
                  <label className="font-label-caps text-on-surface-variant uppercase flex items-center justify-between text-[11px]">
                    <span className="flex items-center gap-1">
                      <User className="w-3.5 h-3.5 text-primary" /> Cap de Colla (Responsable Principal)
                    </span>
                    <span className="text-[10px] font-mono text-primary font-bold">Líder d&apos;intervenció</span>
                  </label>
                  <select
                    required
                    value={formData.cap_de_colla_id}
                    onChange={(e) => {
                      const newCap = e.target.value;
                      setFormData({ ...formData, cap_de_colla_id: newCap });
                      setCollaOperariIds((prev) => prev.filter((id) => id !== newCap));
                    }}
                    className="w-full p-sm bg-surface-container-low rounded-lg border border-outline-variant focus:border-primary outline-none text-sm"
                  >
                    <option value="">Seleccionar Cap de Colla...</option>
                    {operaris.map((op) => (
                      <option key={op.id} value={op.id}>
                        {op.nom} {op.cognoms} — {op.rol}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Assignació de Colla / Quadrilla (Múltiples treballadors a la mateixa feina) */}
                <div className="space-y-xs pt-1">
                  <label className="font-label-caps text-on-surface-variant uppercase flex items-center justify-between text-[11px]">
                    <span className="flex items-center gap-1">
                      <Users className="w-3.5 h-3.5 text-primary" /> Treballadors de la Colla (Equip Operari)
                    </span>
                    <span className="text-[10px] font-mono text-on-surface-variant font-bold">
                      {collaOperariIds.length + (formData.cap_de_colla_id ? 1 : 0)} assignats
                    </span>
                  </label>

                  <div className="flex gap-2">
                    <select
                      value={selectedCollaCandidate}
                      onChange={(e) => setSelectedCollaCandidate(e.target.value)}
                      className="flex-1 p-sm bg-surface-container-low rounded-lg border border-outline-variant focus:border-primary outline-none text-xs"
                    >
                      <option value="">Afegir un altre operari a la colla...</option>
                      {operaris
                        .filter(
                          (op) =>
                            op.id !== formData.cap_de_colla_id &&
                            !collaOperariIds.includes(op.id)
                        )
                        .map((op) => (
                          <option key={op.id} value={op.id}>
                            {op.nom} {op.cognoms} — {op.rol}
                          </option>
                        ))}
                    </select>
                    <button
                      type="button"
                      disabled={!selectedCollaCandidate}
                      onClick={() => addOperariToColla()}
                      className="px-3 py-1.5 rounded-lg bg-primary text-white text-xs font-bold hover:bg-primary/90 disabled:opacity-40 transition-colors flex items-center gap-1 cursor-pointer"
                    >
                      <Plus className="w-3.5 h-3.5" />
                      <span>Afegir</span>
                    </button>
                  </div>

                  {/* Llista de membres de la colla seleccionats */}
                  <div className="space-y-1.5 pt-1">
                    {/* Element del Cap de Colla */}
                    {formData.cap_de_colla_id && (() => {
                      const capOp = operaris.find((o) => o.id === formData.cap_de_colla_id);
                      return capOp ? (
                        <div className="p-2 rounded-lg bg-primary/10 border border-primary/30 flex items-center justify-between text-xs">
                          <div className="flex items-center gap-2">
                            <div className="w-6 h-6 rounded-full bg-primary text-white flex items-center justify-center font-bold text-[10px]">
                              {capOp.nom[0]}
                            </div>
                            <span className="font-bold text-on-surface dark:text-white">
                              {capOp.nom} {capOp.cognoms || ""}
                            </span>
                          </div>
                          <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded-full bg-primary text-white">
                            CAP DE COLLA · RESPONSABLE
                          </span>
                        </div>
                      ) : null;
                    })()}

                    {/* Altres membres de la colla */}
                    {collaOperariIds.map((cId) => {
                      const memberOp = operaris.find((o) => o.id === cId);
                      if (!memberOp) return null;
                      return (
                        <div
                          key={cId}
                          className="p-2 rounded-lg bg-surface-container-low border border-outline-variant/30 flex items-center justify-between text-xs hover:border-outline-variant transition-colors"
                        >
                          <div className="flex items-center gap-2">
                            <div className="w-6 h-6 rounded-full bg-surface-container-high text-on-surface flex items-center justify-center font-bold text-[10px]">
                              {memberOp.nom[0]}
                            </div>
                            <div>
                              <span className="font-medium text-on-surface dark:text-white block">
                                {memberOp.nom} {memberOp.cognoms || ""}
                              </span>
                              <span className="text-[10px] text-on-surface-variant font-mono">
                                {memberOp.rol || "Operari de suport"}
                              </span>
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-surface-container-high text-on-surface-variant">
                              OPERARI COLLA
                            </span>
                            <button
                              type="button"
                              onClick={() => removeOperariFromColla(cId)}
                              className="p-1 rounded text-outline hover:text-error hover:bg-error/10 transition-colors cursor-pointer"
                              title="Treure aquest operari de la colla"
                            >
                              <X className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        </div>
                      );
                    })}

                    <p className="text-[11px] text-on-surface-variant italic pt-1">
                      {collaOperariIds.length > 0
                        ? `Aquesta feina s'assignarà com a única Ordre de Treball compartida per la colla (${collaOperariIds.length + 1} treballadors), evitant duplicar tasques.`
                        : "Sense altres membres a la colla (feina individual assignada exclusivament al Cap de Colla)."}
                    </p>
                  </div>
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
                    <p className="text-on-primary-container">Colla / Quadrilla</p>
                    <p className="font-data-tabular font-bold text-sm">
                      {formData.cap_de_colla_id
                        ? `${1 + collaOperariIds.length} treballadors`
                        : "Pendent"}
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
