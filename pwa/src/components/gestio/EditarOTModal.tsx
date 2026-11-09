"use client";

import React, { useState, useEffect, useMemo, useRef } from "react";
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
  AlertCircle,
  RefreshCw,
  Layers,
  Package,
  Wrench,
  Plus,
  Trash2,
  CheckCircle2,
  Box,
  Clock,
  Search,
  Tag,
  ExternalLink,
} from "lucide-react";
import { apiFetch } from "@/lib/api";
import { geocodificarAdreca } from "@/lib/geocoding";

interface EditarOTModalProps {
  feinaId: string;
  onClose: () => void;
  onSuccess?: () => void;
}

interface LiniaPickingUI {
  id?: string;
  article_id: string;
  article_nom: string;
  referencia_inventari: string;
  quantitat_prevista: number;
  unitat_mesura: string;
  estoc_disponible: number;
}

interface EinaUI {
  id: string;
  nom: string;
  model?: string | null;
  numero_serie: string;
  estat: string;
}

interface PlanolUI {
  id: string;
  titol: string;
  codi_referencia: string;
  tipus_fitxer: string;
  carpeta_nom?: string | null;
  municipi?: string | null;
}

interface ArticleCataleg {
  id: string;
  nom: string;
  referencia_inventari: string;
  unitat_mesura: string;
  familia?: string;
  estoc_real?: number;
  actiu?: boolean;
}

export function EditarOTModal({ feinaId, onClose, onSuccess }: EditarOTModalProps) {
  const [activeTab, setActiveTab] = useState<"GENERAL" | "PLANOL" | "PICKING" | "EINES">("GENERAL");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Auxiliar catalogs
  const [clients, setClients] = useState<any[]>([]);
  const [finques, setFinques] = useState<any[]>([]);
  const [operaris, setOperaris] = useState<any[]>([]);
  const [vehicles, setVehicles] = useState<any[]>([]);
  const [planols, setPlanols] = useState<PlanolUI[]>([]);
  const [articlesCatalog, setArticlesCatalog] = useState<ArticleCataleg[]>([]);
  const [einesCatalog, setEinesCatalog] = useState<EinaUI[]>([]);

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
    planol_id: "",
  });

  const [horaInici, setHoraInici] = useState("");
  const [horaFi, setHoraFi] = useState("");

  // Picking & Eines state
  const [liniesPicking, setLiniesPicking] = useState<LiniaPickingUI[]>([]);
  const [selectedEinaIds, setSelectedEinaIds] = useState<string[]>([]);

  // Autocomplete & Family state for Picking (Materials)
  const [filtreFamilia, setFiltreFamilia] = useState<string>("TOTES");
  const [cercaArticle, setCercaArticle] = useState<string>("");
  const [selectedArticle, setSelectedArticle] = useState<ArticleCataleg | null>(null);
  const [selectedArticleId, setSelectedArticleId] = useState("");
  const [quantitatPickingInput, setQuantitatPickingInput] = useState<number>(1);
  const [isArticleDropdownOpen, setIsArticleDropdownOpen] = useState(false);
  const articleComboboxRef = useRef<HTMLDivElement>(null);

  // Autocomplete state for Eines (Tools)
  const [cercaEina, setCercaEina] = useState<string>("");
  const [selectedEina, setSelectedEina] = useState<EinaUI | null>(null);
  const [selectedEinaInputId, setSelectedEinaInputId] = useState("");
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

  // Compute available families for articles
  const familiesDisponibles = useMemo(() => {
    const fams = new Set<string>();
    articlesCatalog.forEach((a) => {
      if (a.familia && a.familia.trim()) fams.add(a.familia.trim());
    });
    return Array.from(fams).sort();
  }, [articlesCatalog]);

  // Filtered articles for autocomplete (capped at 10 items for responsive UX)
  const filteredArticles = useMemo(() => {
    const q = cercaArticle.trim().toLowerCase();
    return articlesCatalog
      .filter((art) => {
        if (filtreFamilia !== "TOTES" && (art.familia || "").toUpperCase() !== filtreFamilia.toUpperCase()) {
          return false;
        }
        if (!q) return true;
        return (
          art.nom.toLowerCase().includes(q) ||
          art.referencia_inventari.toLowerCase().includes(q) ||
          (art.familia && art.familia.toLowerCase().includes(q))
        );
      })
      .slice(0, 10);
  }, [articlesCatalog, cercaArticle, filtreFamilia]);

  // Filtered tools for autocomplete (capped at 10 items)
  const filteredEines = useMemo(() => {
    const q = cercaEina.trim().toLowerCase();
    return einesCatalog
      .filter((e) => !selectedEinaIds.includes(e.id))
      .filter((e) => {
        if (!q) return true;
        return (
          e.nom.toLowerCase().includes(q) ||
          e.numero_serie.toLowerCase().includes(q) ||
          (e.model && e.model.toLowerCase().includes(q))
        );
      })
      .slice(0, 10);
  }, [einesCatalog, selectedEinaIds, cercaEina]);

  // Load feina and auxiliary catalogs
  useEffect(() => {
    setLoading(true);
    Promise.all([
      apiFetch<any>(`/gestio/feines/${feinaId}`),
      apiFetch<any>("/gestio/clients").catch(() => []),
      apiFetch<any>("/gestio/operaris").catch(() => []),
      apiFetch<any>("/gestio/flota").catch(() => []),
      apiFetch<PlanolUI[]>("/gestio/planols").catch(() => []),
      apiFetch<ArticleCataleg[]>("/gestio/magatzem/articles").catch(() => []),
      apiFetch<EinaUI[]>("/gestio/magatzem/eines").catch(() => []),
    ])
      .then(([feinaData, clientsData, operarisData, flotaData, planolsData, articlesData, einesData]) => {
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
          planol_id: feinaData.planol_id || "",
        });

        if (feinaData.hora_inici_prevista) {
          try {
            const d = new Date(feinaData.hora_inici_prevista);
            const hh = String(d.getHours()).padStart(2, "0");
            const mm = String(d.getMinutes()).padStart(2, "0");
            setHoraInici(`${hh}:${mm}`);
          } catch {}
        }
        if (feinaData.hora_fi_prevista) {
          try {
            const d = new Date(feinaData.hora_fi_prevista);
            const hh = String(d.getHours()).padStart(2, "0");
            const mm = String(d.getMinutes()).padStart(2, "0");
            setHoraFi(`${hh}:${mm}`);
          } catch {}
        }

        // Initialize picking lines
        if (Array.isArray(feinaData.linies_picking)) {
          setLiniesPicking(
            feinaData.linies_picking.map((lp: any) => ({
              id: lp.id,
              article_id: lp.article_id,
              article_nom: lp.article_nom || "Article sense nom",
              referencia_inventari: lp.referencia_inventari || "S/REF",
              quantitat_prevista: Number(lp.quantitat_prevista) || 1,
              unitat_mesura: lp.unitat_mesura || "UNITAT",
              estoc_disponible: Number(lp.estoc_disponible) || 0,
            }))
          );
        }

        // Initialize linked tools
        if (Array.isArray(feinaData.eina_ids)) {
          setSelectedEinaIds(feinaData.eina_ids);
        } else if (Array.isArray(feinaData.eines)) {
          setSelectedEinaIds(feinaData.eines.map((e: any) => e.id));
        }

        setClients(Array.isArray(clientsData) ? clientsData : clientsData?.items || []);
        setOperaris(
          (Array.isArray(operarisData) ? operarisData : operarisData?.operaris || []).filter(
            (o: any) => o.estat === "ACTIU"
          )
        );
        setVehicles(Array.isArray(flotaData) ? flotaData : flotaData?.vehicles || []);
        setPlanols(Array.isArray(planolsData) ? planolsData : []);
        setArticlesCatalog(Array.isArray(articlesData) ? articlesData : []);
        setEinesCatalog(Array.isArray(einesData) ? einesData : []);

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

  const handleFincaChange = (fincaId: string) => {
    setFormData((prev) => {
      const f = finques.find((x) => x.id === fincaId);
      return {
        ...prev,
        finca_id: fincaId,
        adreca: (!prev.adreca || prev.adreca.trim() === "") && f?.adreca ? f.adreca : prev.adreca,
        latitud: f?.latitud != null ? Number(f.latitud) : prev.latitud,
        longitud: f?.longitud != null ? Number(f.longitud) : prev.longitud,
      };
    });
  };

  // Picking functions
  const handleSelectArticle = (art: ArticleCataleg) => {
    setSelectedArticle(art);
    setSelectedArticleId(art.id);
    setCercaArticle(`[${art.referencia_inventari}] ${art.nom}`);
    setIsArticleDropdownOpen(false);
  };

  const handleClearArticle = () => {
    setSelectedArticle(null);
    setSelectedArticleId("");
    setCercaArticle("");
    setIsArticleDropdownOpen(false);
  };

  const handleAfegirMaterial = () => {
    const article = selectedArticle || articlesCatalog.find((a) => a.id === selectedArticleId);
    if (!article) return;

    if (quantitatPickingInput <= 0) {
      setErrorMsg("La quantitat del material ha de ser superior a zero.");
      return;
    }

    // Check if already in list
    const existentIndex = liniesPicking.findIndex((l) => l.article_id === article.id);
    if (existentIndex >= 0) {
      const noves = [...liniesPicking];
      noves[existentIndex].quantitat_prevista += quantitatPickingInput;
      setLiniesPicking(noves);
    } else {
      setLiniesPicking([
        ...liniesPicking,
        {
          article_id: article.id,
          article_nom: article.nom,
          referencia_inventari: article.referencia_inventari,
          quantitat_prevista: quantitatPickingInput,
          unitat_mesura: article.unitat_mesura || "UNITAT",
          estoc_disponible: article.estoc_real || 0,
        },
      ]);
    }

    handleClearArticle();
    setQuantitatPickingInput(1);
    setErrorMsg(null);
  };

  const handleEliminarLiniaPicking = (articleId: string) => {
    setLiniesPicking(liniesPicking.filter((l) => l.article_id !== articleId));
  };

  const handleCanviarQuantitatPicking = (articleId: string, novaQ: number) => {
    if (novaQ <= 0) return;
    setLiniesPicking(
      liniesPicking.map((l) => (l.article_id === articleId ? { ...l, quantitat_prevista: novaQ } : l))
    );
  };

  // Eines functions
  const handleSelectEina = (eina: EinaUI) => {
    setSelectedEina(eina);
    setSelectedEinaInputId(eina.id);
    setCercaEina(`${eina.nom} (${eina.model || eina.numero_serie})`);
    setIsEinaDropdownOpen(false);
  };

  const handleClearEina = () => {
    setSelectedEina(null);
    setSelectedEinaInputId("");
    setCercaEina("");
    setIsEinaDropdownOpen(false);
  };

  const handleVincularEina = () => {
    const einaId = selectedEina?.id || selectedEinaInputId;
    if (!einaId) return;
    if (selectedEinaIds.includes(einaId)) return;
    setSelectedEinaIds([...selectedEinaIds, einaId]);
    handleClearEina();
  };

  const handleDesvincularEina = (einaId: string) => {
    setSelectedEinaIds(selectedEinaIds.filter((id) => id !== einaId));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.titol.trim()) {
      setErrorMsg("El títol de la feina és obligatori.");
      setActiveTab("GENERAL");
      return;
    }
    if (!formData.adreca.trim()) {
      setErrorMsg("L'adreça d'obra és obligatòria.");
      setActiveTab("GENERAL");
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
        planol_id: formData.planol_id || null,
        adreca: formData.adreca.trim(),
        data_planificacio: formData.data_planificacio,
        hora_inici_prevista: horaInici ? `${formData.data_planificacio}T${horaInici}:00` : null,
        hora_fi_prevista: horaFi ? `${formData.data_planificacio}T${horaFi}:00` : null,
        estat: formData.estat,
        cap_de_colla_id: formData.cap_de_colla_id || null,
        vehicle_id: formData.vehicle_id || null,
        latitud: geo.lat,
        longitud: geo.lng,
        versio: formData.versio,
        eina_ids: selectedEinaIds,
        linies_picking: liniesPicking.map((l) => ({
          article_id: l.article_id,
          quantitat_prevista: Number(l.quantitat_prevista),
        })),
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

  // Helper for blueprint info
  const selectedPlanol = planols.find((p) => p.id === formData.planol_id);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-in fade-in duration-150">
      <div className="relative w-full max-w-3xl bg-white dark:bg-slate-900 rounded-2xl shadow-2xl border border-slate-200 dark:border-slate-800 flex flex-col max-h-[92vh] overflow-hidden">
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
                Gestió integral: assignació, plànols tècnics, picking de materials i eines en custòdia.
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            type="button"
            className="p-2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-xl transition-colors cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Pestanyes de Navegació */}
        <div className="flex items-center border-b border-slate-200 dark:border-slate-800 bg-slate-50/80 dark:bg-slate-800/20 px-6 gap-2">
          <button
            type="button"
            onClick={() => setActiveTab("GENERAL")}
            className={`py-3 px-3 text-xs font-bold flex items-center gap-1.5 border-b-2 transition-all cursor-pointer ${
              activeTab === "GENERAL"
                ? "border-primary text-primary"
                : "border-transparent text-slate-500 hover:text-slate-700 dark:hover:text-slate-300"
            }`}
          >
            <FileText className="w-3.5 h-3.5" />
            <span>General & Dades</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab("PLANOL")}
            className={`py-3 px-3 text-xs font-bold flex items-center gap-1.5 border-b-2 transition-all cursor-pointer ${
              activeTab === "PLANOL"
                ? "border-primary text-primary"
                : "border-transparent text-slate-500 hover:text-slate-700 dark:hover:text-slate-300"
            }`}
          >
            <Layers className="w-3.5 h-3.5" />
            <span>Plànol Tècnic</span>
            {formData.planol_id && (
              <span className="w-2 h-2 rounded-full bg-primary inline-block" />
            )}
          </button>

          <button
            type="button"
            onClick={() => setActiveTab("PICKING")}
            className={`py-3 px-3 text-xs font-bold flex items-center gap-1.5 border-b-2 transition-all cursor-pointer ${
              activeTab === "PICKING"
                ? "border-primary text-primary"
                : "border-transparent text-slate-500 hover:text-slate-700 dark:hover:text-slate-300"
            }`}
          >
            <Package className="w-3.5 h-3.5" />
            <span>Pickup Materials</span>
            {liniesPicking.length > 0 && (
              <span className="ml-1 px-1.5 py-0.2 rounded-full text-[10px] font-mono bg-primary/10 text-primary font-bold">
                {liniesPicking.length}
              </span>
            )}
          </button>

          <button
            type="button"
            onClick={() => setActiveTab("EINES")}
            className={`py-3 px-3 text-xs font-bold flex items-center gap-1.5 border-b-2 transition-all cursor-pointer ${
              activeTab === "EINES"
                ? "border-primary text-primary"
                : "border-transparent text-slate-500 hover:text-slate-700 dark:hover:text-slate-300"
            }`}
          >
            <Wrench className="w-3.5 h-3.5" />
            <span>Eines en Custòdia</span>
            {selectedEinaIds.length > 0 && (
              <span className="ml-1 px-1.5 py-0.2 rounded-full text-[10px] font-mono bg-primary/10 text-primary font-bold">
                {selectedEinaIds.length}
              </span>
            )}
          </button>
        </div>

        {/* Cos del Formulari */}
        {loading ? (
          <div className="p-16 flex flex-col items-center justify-center gap-3">
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

            {/* TAB 1: GENERAL */}
            {activeTab === "GENERAL" && (
              <div className="space-y-4 animate-in fade-in duration-100">
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
                      onChange={(e) => handleFincaChange(e.target.value)}
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
                      <Calendar className="w-3.5 h-3.5 text-slate-400" />
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

                {/* Franja Horària Prevista (Opcional) */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1 flex items-center gap-1.5">
                      <Clock className="w-3.5 h-3.5 text-slate-400" />
                      <span>Hora Inici Prevista (Opcional)</span>
                    </label>
                    <input
                      type="time"
                      value={horaInici}
                      onChange={(e) => setHoraInici(e.target.value)}
                      className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary font-mono"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1 flex items-center gap-1.5">
                      <Clock className="w-3.5 h-3.5 text-slate-400" />
                      <span>Hora Fi Prevista (Opcional)</span>
                    </label>
                    <input
                      type="time"
                      value={horaFi}
                      onChange={(e) => setHoraFi(e.target.value)}
                      className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary font-mono"
                    />
                  </div>
                </div>
              </div>
            )}

            {/* TAB 2: PLÀNOL TÈCNIC */}
            {activeTab === "PLANOL" && (
              <div className="space-y-4 animate-in fade-in duration-100">
                <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800 text-xs text-slate-600 dark:text-slate-300 flex items-start gap-2.5">
                  <Layers className="w-4 h-4 text-primary shrink-0 mt-0.5" />
                  <div>
                    <p className="font-semibold text-slate-800 dark:text-white">
                      Assignació de Plànol Tècnic d&apos;Obra
                    </p>
                    <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">
                      Vincula el croquis, esquema unifilar elèctric, plànol de reg o distribució tècnica. L&apos;operari podrà consultar-lo directament des de la PWA al terreny.
                    </p>
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1.5 flex items-center justify-between">
                    <span>Selecciona el Plànol Tècnic</span>
                    {formData.planol_id && (
                      <button
                        type="button"
                        onClick={() => setFormData({ ...formData, planol_id: "" })}
                        className="text-[11px] text-error hover:underline cursor-pointer"
                      >
                        Desvincular plànol
                      </button>
                    )}
                  </label>
                  <select
                    value={formData.planol_id}
                    onChange={(e) => setFormData({ ...formData, planol_id: e.target.value })}
                    className="w-full px-3 py-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary"
                  >
                    <option value="">Sense plànol vinculat</option>
                    {Object.entries(
                      planols.reduce((acc: Record<string, PlanolUI[]>, p: PlanolUI) => {
                        const carp = p.carpeta_nom ? `Carpeta: ${p.carpeta_nom}` : "Biblioteca General";
                        if (!acc[carp]) acc[carp] = [];
                        acc[carp].push(p);
                        return acc;
                      }, {})
                    ).map(([nomCarpeta, items]) => (
                      <optgroup key={nomCarpeta} label={nomCarpeta}>
                        {items.map((p) => (
                          <option key={p.id} value={p.id}>
                            [{p.codi_referencia}] {p.titol} ({p.tipus_fitxer})
                          </option>
                        ))}
                      </optgroup>
                    ))}
                  </select>
                </div>

                {selectedPlanol ? (
                  <div className="p-4 rounded-xl border border-primary/20 bg-primary/5 dark:bg-primary/10 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-lg bg-primary/20 flex items-center justify-center text-primary shrink-0">
                        <Layers className="w-5 h-5" />
                      </div>
                      <div>
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="font-mono text-xs font-bold text-primary">
                            {selectedPlanol.codi_referencia}
                          </span>
                          <span className="text-[10px] px-1.5 py-0.5 rounded font-mono uppercase bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-300">
                            {selectedPlanol.tipus_fitxer}
                          </span>
                          {selectedPlanol.carpeta_nom && (
                            <span className="text-[10px] px-2 py-0.5 rounded bg-surface-container-high text-on-surface-variant font-medium">
                              {selectedPlanol.carpeta_nom}
                            </span>
                          )}
                        </div>
                        <h4 className="text-xs font-bold text-slate-900 dark:text-white mt-0.5">
                          {selectedPlanol.titol}
                        </h4>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 self-end sm:self-center">
                      <a
                        href={`/api/v1/gestio/planols/${selectedPlanol.id}/fitxer`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="px-3 py-1.5 rounded-lg bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-700 text-xs font-medium text-slate-700 dark:text-slate-200 flex items-center gap-1.5 transition-colors cursor-pointer"
                      >
                        <ExternalLink className="w-3.5 h-3.5" />
                        <span>Veure Fitxer</span>
                      </a>
                      <span className="text-xs font-medium text-emerald-600 dark:text-emerald-400 flex items-center gap-1 bg-emerald-50 dark:bg-emerald-950/30 px-2 py-1 rounded-lg border border-emerald-500/20">
                        <CheckCircle2 className="w-4 h-4" />
                        Vinculat
                      </span>
                    </div>
                  </div>
                ) : (
                  <div className="p-8 text-center border border-dashed border-slate-200 dark:border-slate-800 rounded-xl">
                    <Layers className="w-8 h-8 text-slate-300 dark:text-slate-600 mx-auto mb-2" />
                    <p className="text-xs text-slate-500 dark:text-slate-400">
                      Aquesta ordre de treball no té cap plànol tècnic associat.
                    </p>
                  </div>
                )}
              </div>
            )}

            {/* TAB 3: PICKING DE MATERIALS */}
            {activeTab === "PICKING" && (
              <div className="space-y-4 animate-in fade-in duration-100">
                <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800 text-xs text-slate-600 dark:text-slate-300 flex items-start gap-2.5">
                  <Package className="w-4 h-4 text-primary shrink-0 mt-0.5" />
                  <div>
                    <p className="font-semibold text-slate-800 dark:text-white">
                      Fulla de Picking (Pickup de Materials & Control d&apos;Inventari)
                    </p>
                    <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">
                      Filtra per família i comença a escriure per autocompletar l&apos;article. La quantitat sol·licitada es reserva automàticament de l&apos;estoc de magatzem.
                    </p>
                  </div>
                </div>

                {/* Subformulari afegir article amb cerca autocompletable i selecció de família */}
                <div className="p-3.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 space-y-3">
                  {/* Fila 1: Filtre de Família & Cerca o Selecció Directa d'Article */}
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                    {/* Selector de Família */}
                    <div>
                      <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1 flex items-center gap-1">
                        <Tag className="w-3.5 h-3.5 text-primary" />
                        <span>Família de Material</span>
                      </label>
                      <select
                        value={filtreFamilia}
                        onChange={(e) => {
                          setFiltreFamilia(e.target.value);
                          setIsArticleDropdownOpen(true);
                        }}
                        className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary"
                      >
                        <option value="TOTES">Totes les famílies ({articlesCatalog.length})</option>
                        {familiesDisponibles.map((f) => (
                          <option key={f} value={f}>
                            {f}
                          </option>
                        ))}
                      </select>
                    </div>

                    {/* Cerca Autocompletable */}
                    <div className="md:col-span-2 relative" ref={articleComboboxRef}>
                      <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1 flex items-center justify-between">
                        <span className="flex items-center gap-1">
                          <Search className="w-3.5 h-3.5 text-primary" />
                          <span>Cerca d&apos;Article (Codi, Nom o Referència)</span>
                        </span>
                        {selectedArticle && (
                          <span className="text-[11px] font-mono font-bold text-emerald-600 dark:text-emerald-400">
                            Estoc: {selectedArticle.estoc_real ?? 0} {selectedArticle.unitat_mesura}
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
                            setSelectedArticleId("");
                            setIsArticleDropdownOpen(true);
                          }}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") {
                              e.preventDefault();
                              if (filteredArticles.length > 0) {
                                handleSelectArticle(filteredArticles[0]);
                              }
                            }
                          }}
                          placeholder="Escriu per cercar per referència, nom o família..."
                          className="w-full pl-9 pr-8 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary font-medium"
                        />
                        <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5 pointer-events-none" />
                        {cercaArticle && (
                          <button
                            type="button"
                            onClick={handleClearArticle}
                            className="absolute right-2.5 top-2.5 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 cursor-pointer"
                          >
                            <X className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </div>

                      {/* Dropdown d'autocompletat */}
                      {isArticleDropdownOpen && (
                        <div className="absolute top-full left-0 right-0 mt-1 z-50 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl shadow-2xl overflow-hidden max-h-52 overflow-y-auto">
                          {filteredArticles.length > 0 ? (
                            filteredArticles.map((art) => (
                              <button
                                key={art.id}
                                type="button"
                                onClick={() => handleSelectArticle(art)}
                                className="w-full text-left px-3 py-2 text-xs hover:bg-slate-50 dark:hover:bg-slate-800/70 border-b border-slate-100 dark:border-slate-800 last:border-b-0 flex items-center justify-between gap-2 transition-colors cursor-pointer"
                              >
                                <div className="min-w-0 flex-1">
                                  <div className="flex items-center gap-1.5 flex-wrap">
                                    <span className="font-mono text-[11px] font-bold text-primary">
                                      [{art.referencia_inventari}]
                                    </span>
                                    <span className="font-medium text-slate-800 dark:text-slate-200 truncate">
                                      {art.nom}
                                    </span>
                                  </div>
                                  {art.familia && (
                                    <span className="inline-block mt-0.5 text-[10px] px-1.5 py-0.2 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 font-mono">
                                      {art.familia}
                                    </span>
                                  )}
                                </div>
                                <div className="text-right shrink-0">
                                  <span
                                    className={`font-mono text-[11px] font-bold ${
                                      (art.estoc_real ?? 0) <= 0
                                        ? "text-error"
                                        : "text-slate-600 dark:text-slate-300"
                                    }`}
                                  >
                                    {art.estoc_real ?? 0} {art.unitat_mesura}
                                  </span>
                                </div>
                              </button>
                            ))
                          ) : (
                            <div className="p-3 text-center text-xs text-slate-400">
                              Cap article coincident amb la cerca.
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Selector Directe Alternatiu d'Articles per facilitar selecció ràpida */}
                  <div className="pt-2 border-t border-slate-100 dark:border-slate-800">
                    <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                      O selecciona directament del catàleg ({articlesCatalog.filter(a => filtreFamilia === "TOTES" || (a.familia || "").toUpperCase() === filtreFamilia.toUpperCase()).length} articles disponibles):
                    </label>
                    <select
                      value={selectedArticleId}
                      onChange={(e) => {
                        const art = articlesCatalog.find((a) => a.id === e.target.value);
                        if (art) handleSelectArticle(art);
                      }}
                      className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary"
                    >
                      <option value="">-- Tria un article per afegir a la fulla de picking --</option>
                      {articlesCatalog
                        .filter(
                          (a) =>
                            filtreFamilia === "TOTES" ||
                            (a.familia || "").toUpperCase() === filtreFamilia.toUpperCase()
                        )
                        .map((a) => (
                          <option key={a.id} value={a.id}>
                            [{a.referencia_inventari}] {a.nom} — {a.estoc_real ?? 0} {a.unitat_mesura} disp.
                          </option>
                        ))}
                    </select>
                  </div>

                  {/* Fila 2: Detalls de l'article seleccionat i assignació de quantitat */}
                  {selectedArticle && (
                    <div className="pt-3 border-t border-slate-100 dark:border-slate-800 flex flex-col sm:flex-row items-stretch sm:items-end gap-3 bg-slate-50/60 dark:bg-slate-800/30 p-3 rounded-xl border border-slate-200/60 dark:border-slate-700/60 animate-in fade-in duration-100">
                      <div className="flex-1 min-w-0">
                        <p className="text-[10px] text-slate-500 dark:text-slate-400 font-mono uppercase font-bold">
                          Article seleccionat:
                        </p>
                        <p className="text-xs font-bold text-slate-900 dark:text-white truncate">
                          [{selectedArticle.referencia_inventari}] {selectedArticle.nom}
                        </p>
                        <span className="inline-block mt-1 text-xs font-mono font-bold text-emerald-600 dark:text-emerald-400">
                          Estoc disponible: {selectedArticle.estoc_real ?? 0} {selectedArticle.unitat_mesura}
                        </span>
                      </div>

                      <div className="w-full sm:w-36 space-y-1">
                        <label className="block text-[11px] font-bold text-slate-700 dark:text-slate-300">
                          Quantitat ({selectedArticle.unitat_mesura})
                        </label>
                        <input
                          type="number"
                          step="any"
                          min="0.001"
                          value={quantitatPickingInput}
                          onChange={(e) => setQuantitatPickingInput(parseFloat(e.target.value) || 0)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") {
                              e.preventDefault();
                              handleAfegirMaterial();
                            }
                          }}
                          className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary font-mono font-bold text-center"
                        />
                      </div>

                      <button
                        type="button"
                        onClick={handleAfegirMaterial}
                        disabled={quantitatPickingInput <= 0}
                        className="w-full sm:w-auto px-4 py-2.5 rounded-xl bg-primary hover:bg-primary-container text-white text-xs font-bold transition-all flex items-center justify-center gap-1.5 cursor-pointer disabled:opacity-40 shrink-0 shadow-sm"
                      >
                        <Plus className="w-4 h-4" />
                        <span>Afegir a la Fulla</span>
                      </button>
                    </div>
                  )}
                </div>

                {/* Taula de materials reservats */}
                {liniesPicking.length > 0 ? (
                  <div className="border border-slate-200 dark:border-slate-800 rounded-xl overflow-x-auto shadow-xs">
                    <table className="w-full min-w-[540px] text-left text-xs">
                      <thead className="bg-slate-50 dark:bg-slate-800/60 text-slate-600 dark:text-slate-300 border-b border-slate-200 dark:border-slate-800">
                        <tr>
                          <th className="py-2.5 px-3 font-semibold">Ref / Article</th>
                          <th className="py-2.5 px-3 font-semibold text-center w-36">Quantitat Prevista</th>
                          <th className="py-2.5 px-3 font-semibold text-right w-36">Estoc Magatzem</th>
                          <th className="py-2.5 px-3 text-right w-16">Acció</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                        {liniesPicking.map((linia) => (
                          <tr key={linia.article_id} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/40">
                            <td className="py-2.5 px-3">
                              <div className="flex items-center gap-1.5 flex-wrap">
                                <span className="font-mono text-[11px] font-bold text-primary shrink-0">
                                  [{linia.referencia_inventari}]
                                </span>
                                <span className="text-slate-800 dark:text-slate-200 font-medium truncate max-w-xs block">
                                  {linia.article_nom}
                                </span>
                              </div>
                            </td>
                            <td className="py-2.5 px-3 text-center">
                              <div className="inline-flex items-center justify-center gap-1.5">
                                <input
                                  type="number"
                                  step="any"
                                  min="0.001"
                                  value={linia.quantitat_prevista}
                                  onChange={(e) =>
                                    handleCanviarQuantitatPicking(
                                      linia.article_id,
                                      parseFloat(e.target.value) || 0
                                    )
                                  }
                                  className="w-20 px-2 py-1 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs font-mono font-bold text-center focus:outline-none focus:ring-1 focus:ring-primary"
                                />
                                <span className="text-[11px] font-mono text-slate-500 shrink-0">
                                  {linia.unitat_mesura}
                                </span>
                              </div>
                            </td>
                            <td className="py-2.5 px-3 text-right">
                              <span
                                className={`text-[11px] font-mono px-2 py-0.5 rounded-full inline-block ${
                                  linia.estoc_disponible < linia.quantitat_prevista
                                    ? "bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300"
                                    : "bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300"
                                }`}
                              >
                                {linia.estoc_disponible} {linia.unitat_mesura} disp.
                              </span>
                            </td>
                            <td className="py-2.5 px-3 text-right">
                              <button
                                type="button"
                                onClick={() => handleEliminarLiniaPicking(linia.article_id)}
                                className="p-1.5 text-slate-400 hover:text-error hover:bg-error/10 rounded-lg transition-colors cursor-pointer"
                                title="Eliminar de la fulla de picking"
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="p-8 text-center border border-dashed border-slate-200 dark:border-slate-800 rounded-xl">
                    <Box className="w-8 h-8 text-slate-300 dark:text-slate-600 mx-auto mb-2" />
                    <p className="text-xs text-slate-500 dark:text-slate-400">
                      Cap material reservat a la fulla de picking d&apos;aquesta intervenció.
                    </p>
                  </div>
                )}
              </div>
            )}

            {/* TAB 4: EINES EN CUSTÒDIA */}
            {activeTab === "EINES" && (
              <div className="space-y-4 animate-in fade-in duration-100">
                <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800 text-xs text-slate-600 dark:text-slate-300 flex items-start gap-2.5">
                  <Wrench className="w-4 h-4 text-primary shrink-0 mt-0.5" />
                  <div>
                    <p className="font-semibold text-slate-800 dark:text-white">
                      Eines i Equips Tècnics en Custòdia
                    </p>
                    <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">
                      Comença a escriure per autocompletar l&apos;eina per nom, model o número de sèrie. Quedaran sota la custòdia directa del cap de colla mentre duri la feina.
                    </p>
                  </div>
                </div>

                {/* Subformulari vincular eina amb cerca autocompletable */}
                <div className="p-3.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 space-y-3">
                  <div className="flex flex-col sm:flex-row items-end gap-3">
                    {/* Input de Cerca Autocompletable */}
                    <div className="flex-1 w-full relative" ref={einaComboboxRef}>
                      <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1 flex items-center justify-between">
                        <span className="flex items-center gap-1">
                          <Search className="w-3.5 h-3.5 text-primary" />
                          <span>Cerca d&apos;Eina / Equip (Autocompletar)</span>
                        </span>
                        {selectedEina && (
                          <span className="text-[11px] font-mono font-bold text-primary">
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
                            setSelectedEinaInputId("");
                            setIsEinaDropdownOpen(true);
                          }}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") {
                              e.preventDefault();
                              if (filteredEines.length > 0) {
                                handleSelectEina(filteredEines[0]);
                              }
                            }
                          }}
                          placeholder="Escriu nom, model o número de sèrie per autocompletar..."
                          className="w-full pl-9 pr-8 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary font-medium"
                        />
                        <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5 pointer-events-none" />
                        {cercaEina && (
                          <button
                            type="button"
                            onClick={handleClearEina}
                            className="absolute right-2.5 top-2.5 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 cursor-pointer"
                          >
                            <X className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </div>

                      {/* Dropdown d'autocompletat d'eines */}
                      {isEinaDropdownOpen && (
                        <div className="absolute top-full left-0 right-0 mt-1 z-30 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl shadow-2xl overflow-hidden max-h-60 overflow-y-auto">
                          {filteredEines.length > 0 ? (
                            filteredEines.map((eina) => (
                              <button
                                key={eina.id}
                                type="button"
                                onClick={() => handleSelectEina(eina)}
                                className="w-full text-left px-3 py-2 text-xs hover:bg-slate-50 dark:hover:bg-slate-800/70 border-b border-slate-100 dark:border-slate-800 last:border-b-0 flex items-center justify-between gap-2 transition-colors cursor-pointer"
                              >
                                <div className="min-w-0 flex-1">
                                  <div className="flex items-center gap-1.5 flex-wrap">
                                    <span className="font-bold text-slate-800 dark:text-slate-200">
                                      {eina.nom}
                                    </span>
                                    {eina.model && (
                                      <span className="text-[11px] text-slate-500 dark:text-slate-400">
                                        ({eina.model})
                                      </span>
                                    )}
                                  </div>
                                  <span className="inline-block mt-0.5 text-[10px] text-slate-400 font-mono">
                                    SN: {eina.numero_serie}
                                  </span>
                                </div>
                                <span
                                  className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded-full shrink-0 ${
                                    eina.estat === "DISPONIBLE"
                                      ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300"
                                      : "bg-blue-100 text-blue-800 dark:bg-blue-950/60 dark:text-blue-300"
                                  }`}
                                >
                                  {eina.estat}
                                </span>
                              </button>
                            ))
                          ) : (
                            <div className="p-3 text-center text-xs text-slate-400">
                              Cap eina disponible coincident.
                            </div>
                          )}
                        </div>
                      )}
                    </div>

                    <button
                      type="button"
                      onClick={handleVincularEina}
                      disabled={!selectedEina && !selectedEinaInputId}
                      className="w-full sm:w-auto px-4 py-2 rounded-xl bg-primary hover:bg-primary-container text-white text-xs font-bold transition-all flex items-center justify-center gap-1 cursor-pointer disabled:opacity-40"
                    >
                      <Plus className="w-3.5 h-3.5" />
                      <span>Assignar Custòdia</span>
                    </button>
                  </div>
                </div>

                {/* Llistat d'eines assignades */}
                {selectedEinaIds.length > 0 ? (
                  <div className="border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden divide-y divide-slate-100 dark:divide-slate-800">
                    {selectedEinaIds.map((einaId) => {
                      const eina = einesCatalog.find((e) => e.id === einaId);
                      return (
                        <div
                          key={einaId}
                          className="p-3 flex items-center justify-between hover:bg-slate-50/50 dark:hover:bg-slate-800/40"
                        >
                          <div className="flex items-center gap-3">
                            <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center text-primary">
                              <Wrench className="w-4 h-4" />
                            </div>
                            <div>
                              <div className="flex items-center gap-2">
                                <h4 className="text-xs font-bold text-slate-900 dark:text-white">
                                  {eina ? eina.nom : "Eina assignada"}
                                </h4>
                                {eina?.model && (
                                  <span className="text-[11px] text-slate-500 dark:text-slate-400">
                                    {eina.model}
                                  </span>
                                )}
                              </div>
                              <p className="text-[11px] font-mono text-slate-400 mt-0.5">
                                SN: {eina ? eina.numero_serie : einaId}
                              </p>
                            </div>
                          </div>

                          <div className="flex items-center gap-3">
                            <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded-full bg-blue-100 text-blue-800 dark:bg-blue-950/60 dark:text-blue-300">
                              CUSTÒDIA
                            </span>
                            <button
                              type="button"
                              onClick={() => handleDesvincularEina(einaId)}
                              className="p-1.5 text-slate-400 hover:text-error hover:bg-error/10 rounded-lg transition-colors cursor-pointer"
                              title="Alliberar custòdia d'aquesta eina"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <div className="p-8 text-center border border-dashed border-slate-200 dark:border-slate-800 rounded-xl">
                    <Wrench className="w-8 h-8 text-slate-300 dark:text-slate-600 mx-auto mb-2" />
                    <p className="text-xs text-slate-500 dark:text-slate-400">
                      Cap eina ni equip tècnic en custòdia assignat a aquesta ordre de treball.
                    </p>
                  </div>
                )}
              </div>
            )}

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
                  className="px-4 py-2 rounded-xl text-xs font-bold text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors cursor-pointer"
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
