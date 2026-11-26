"use client";

import React, { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  ArrowLeft,
  Package,
  Wrench,
  CheckCircle2,
  AlertTriangle,
  Plus,
  Truck,
  Scissors,
  CheckSquare,
  Square,
  RefreshCw,
  Search,
  X,
  Loader2,
  ArrowDownLeft,
  ArrowUpRight,
} from "lucide-react";
import { apiFetch } from "@/lib/api";

interface MaterialItem {
  id: string;
  ordre_treball_id?: string | null;
  ordre_codi?: string | null;
  article_id?: string | null;
  nom: string;
  referencia: string;
  quantitat_programada: number;
  quantitat_carregada_pick_in?: number;
  unitat: string;
  es_eina: boolean;
  format_continu?: boolean;
  carregat_pick_in: boolean;
  confirmat_bd?: boolean;
  retornat_pick_out: number;
  quantitat_mermada: number;
  origen_estoc: "NAU" | "FURGONETA" | string;
  magatzem_nom?: string | null;
}

interface EstocFurgonetaItem {
  estoc_id: string;
  article_id: string;
  nom: string;
  referencia: string;
  codi_barres?: string | null;
  unitat: string;
  format_continu: boolean;
  quantitat_fisica: number;
  quantitat_disponible: number;
}

interface EstocFurgonetaResponse {
  magatzem_id: string | null;
  magatzem_nom: string | null;
  vehicle_id: string | null;
  vehicle_matricula: string | null;
  vehicle_model: string | null;
  items: EstocFurgonetaItem[];
}

interface FeinaResum {
  id: string;
  codi: string;
  titol: string;
  estat: string;
}

interface EinaPickingItem {
  id: string;
  nom: string;
  model?: string | null;
  numero_serie: string;
  referencia_fabricant?: string | null;
  estat: string;
  ordre_treball_id?: string | null;
  ordre_codi?: string | null;
  custodiat_per_operari_id?: string | null;
  magatzem_id?: string | null;
  magatzem_nom?: string | null;
  observacions?: string | null;
  incidencies?: string | null;
}

interface EinesPickingResponse {
  eines_assignades: EinaPickingItem[];
  eines_disponibles: EinaPickingItem[];
}

type FaseMaterial = "PICK_IN" | "OBRA" | "PICK_OUT" | "EINES";

function parseInitialFase(rawFase: string | null, rawTab: string | null): FaseMaterial {
  const val = (rawFase || rawTab || "").toUpperCase();
  if (val === "OBRA" || val === "FURGONETA") return "OBRA";
  if (val === "PICK_OUT" || val === "PICKOUT") return "PICK_OUT";
  if (val === "EINES" || val === "TOOLS") return "EINES";
  return "PICK_IN";
}

function OperariMaterialContent() {
  const searchParams = useSearchParams();
  const paramOrdreId = searchParams.get("ordre_id") || "";
  const paramFase = searchParams.get("fase");
  const paramTab = searchParams.get("tab");

  const [ordreActivaId, setOrdreActivaId] = useState<string>(paramOrdreId);
  const [feinesActives, setFeinesActives] = useState<FeinaResum[]>([]);
  const [fase, setFase] = useState<FaseMaterial>(() =>
    parseInitialFase(paramFase, paramTab)
  );

  useEffect(() => {
    if (paramFase || paramTab) {
      setFase(parseInitialFase(paramFase, paramTab));
    }
  }, [paramFase, paramTab]);

  const [materials, setMaterials] = useState<MaterialItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [desant, setDesant] = useState<boolean>(false);
  const [feedback, setFeedback] = useState<{ tipus: "ok" | "error"; text: string } | null>(null);

  // Eines en custòdia (Pick-In / Pick-Out d'eines)
  const [einesAssignades, setEinesAssignades] = useState<EinaPickingItem[]>([]);
  const [einesDisponibles, setEinesDisponibles] = useState<EinaPickingItem[]>([]);
  const [loadingEines, setLoadingEines] = useState<boolean>(false);
  const [einaProcessantId, setEinaProcessantId] = useState<string | null>(null);
  const [showEinesDispModal, setShowEinesDispModal] = useState<boolean>(false);
  const [cercaEinaDisp, setCercaEinaDisp] = useState<string>("");
  const [destiPickInEina, setDestiPickInEina] = useState<"CUSTODIADA" | "EN_VEHICLE">("CUSTODIADA");
  const [einaPickOutAvaria, setEinaPickOutAvaria] = useState<EinaPickingItem | null>(null);
  const [avariaEinaText, setAvariaEinaText] = useState<string>("");

  // Magatzem del vehicle (Furgoneta)
  const [vanStock, setVanStock] = useState<EstocFurgonetaResponse | null>(null);
  const [loadingVan, setLoadingVan] = useState<boolean>(false);
  const [showVanModal, setShowVanModal] = useState<boolean>(false);
  const [cercaVan, setCercaVan] = useState<string>("");
  const [vanItemSel, setVanItemSel] = useState<EstocFurgonetaItem | null>(null);
  const [vanQuantitat, setVanQuantitat] = useState<string>("1");
  const [vanMerma, setVanMerma] = useState<string>("0");
  const [vanNotes, setVanNotes] = useState<string>("");
  const [enviantVan, setEnviantVan] = useState<boolean>(false);

  // Incidència real de magatzem (desquadrament real a nau)
  const [showIncModal, setShowIncModal] = useState<boolean>(false);
  const [incText, setIncText] = useState<string>("");
  const [enviantInc, setEnviantInc] = useState<boolean>(false);

  const carregarFeines = useCallback(async () => {
    try {
      const data = await apiFetch<FeinaResum[]>("/operari/feines");
      const list = Array.isArray(data) ? data : [];
      setFeinesActives(list);
      if (!paramOrdreId && !ordreActivaId && list.length > 0) {
        const activa = list.find((f) =>
          ["EN_CURS", "EN_RUTA", "ASSIGNADA", "PROGRAMADA", "PENDENT", "PAUSADA"].includes(
            (f.estat || "").toUpperCase()
          )
        );
        setOrdreActivaId((activa || list[0]).id);
      }
    } catch {
      // mode offline silenciós
    }
  }, [paramOrdreId, ordreActivaId]);

  const carregarMaterials = useCallback(async (targetOrdreId?: string) => {
    setLoading(true);
    try {
      const otParam = targetOrdreId || ordreActivaId;
      const url = otParam
        ? `/operari/materials?ordre_treball_id=${encodeURIComponent(otParam)}`
        : "/operari/materials";
      const data = await apiFetch<MaterialItem[]>(url);
      const items = Array.isArray(data) ? data : [];
      setMaterials(
        items.map((m) => {
          const confirmatServidor = Boolean(m.carregat_pick_in);
          return {
            ...m,
            carregat_pick_in: confirmatServidor,
            confirmat_bd: confirmatServidor,
            retornat_pick_out: Number(m.retornat_pick_out ?? 0),
            quantitat_mermada: Number(m.quantitat_mermada ?? 0),
            origen_estoc: (m.origen_estoc || "NAU").toUpperCase(),
          };
        })
      );
    } catch {
      setMaterials([]);
    } finally {
      setLoading(false);
    }
  }, [ordreActivaId]);

  const carregarEstocFurgoneta = useCallback(async (targetOrdreId?: string) => {
    setLoadingVan(true);
    try {
      const otParam = targetOrdreId || ordreActivaId;
      const url = otParam
        ? `/operari/picking/vehicle-stock?ordre_treball_id=${encodeURIComponent(otParam)}`
        : "/operari/picking/vehicle-stock";
      const data = await apiFetch<EstocFurgonetaResponse>(url);
      setVanStock(data || null);
    } catch {
      setVanStock(null);
    } finally {
      setLoadingVan(false);
    }
  }, [ordreActivaId]);

  const carregarEines = useCallback(async (targetOrdreId?: string) => {
    setLoadingEines(true);
    try {
      const otParam = targetOrdreId || ordreActivaId;
      const url = otParam
        ? `/operari/picking/eines?ordre_treball_id=${encodeURIComponent(otParam)}&incloure_disponibles=true`
        : "/operari/picking/eines?incloure_disponibles=true";
      const data = await apiFetch<EinesPickingResponse>(url);
      setEinesAssignades(Array.isArray(data?.eines_assignades) ? data.eines_assignades : []);
      setEinesDisponibles(Array.isArray(data?.eines_disponibles) ? data.eines_disponibles : []);
    } catch {
      setEinesAssignades([]);
      setEinesDisponibles([]);
    } finally {
      setLoadingEines(false);
    }
  }, [ordreActivaId]);

  useEffect(() => {
    carregarFeines();
  }, [carregarFeines]);

  useEffect(() => {
    carregarMaterials(ordreActivaId);
    carregarEstocFurgoneta(ordreActivaId);
    carregarEines(ordreActivaId);
  }, [ordreActivaId, carregarMaterials, carregarEstocFurgoneta, carregarEines]);

  const handlePickInEina = async (
    eina: EinaPickingItem,
    desti: "CUSTODIADA" | "EN_VEHICLE" = destiPickInEina
  ) => {
    setEinaProcessantId(eina.id);
    setFeedback(null);
    try {
      await apiFetch(`/operari/picking/eines/${eina.id}/pick-in`, {
        method: "POST",
        body: JSON.stringify({
          ordre_treball_id: ordreActivaId || null,
          desti,
        }),
      });
      setFeedback({
        tipus: "ok",
        text:
          desti === "EN_VEHICLE"
            ? `Pick-In confirmat: ${eina.nom} carregada a la furgoneta.`
            : `Pick-In confirmat: ${eina.nom} assignada en custòdia.`,
      });
      setShowEinesDispModal(false);
      await carregarEines(ordreActivaId);
    } catch (err: unknown) {
      setFeedback({
        tipus: "error",
        text: err instanceof Error ? err.message : "Error en fer Pick-In de l'eina.",
      });
    } finally {
      setEinaProcessantId(null);
    }
  };

  const handlePickOutEina = async (
    eina: EinaPickingItem,
    estatRetorn: "DISPONIBLE" | "AVARIADA",
    incidencia?: string
  ) => {
    setEinaProcessantId(eina.id);
    setFeedback(null);
    try {
      await apiFetch(`/operari/picking/eines/${eina.id}/pick-out`, {
        method: "POST",
        body: JSON.stringify({
          ordre_treball_id: ordreActivaId || eina.ordre_treball_id || null,
          estat_retorn: estatRetorn,
          incidencia: incidencia?.trim() || undefined,
        }),
      });
      setFeedback({
        tipus: "ok",
        text:
          estatRetorn === "AVARIADA"
            ? `Pick-Out amb avaria registrat per a ${eina.nom}. Oficina avisada.`
            : `Pick-Out completat: ${eina.nom} retornada disponible al magatzem.`,
      });
      setEinaPickOutAvaria(null);
      setAvariaEinaText("");
      await carregarEines(ordreActivaId);
    } catch (err: unknown) {
      setFeedback({
        tipus: "error",
        text: err instanceof Error ? err.message : "Error en fer Pick-Out de l'eina.",
      });
    } finally {
      setEinaProcessantId(null);
    }
  };

  const einesDispFiltrades = useMemo(() => {
    const q = cercaEinaDisp.trim().toLowerCase();
    if (!q) return einesDisponibles;
    return einesDisponibles.filter(
      (e) =>
        e.nom.toLowerCase().includes(q) ||
        e.numero_serie.toLowerCase().includes(q) ||
        (e.model || "").toLowerCase().includes(q) ||
        (e.referencia_fabricant || "").toLowerCase().includes(q)
    );
  }, [einesDisponibles, cercaEinaDisp]);

  const materialsNau = useMemo(
    () => materials.filter((m) => m.origen_estoc !== "FURGONETA"),
    [materials]
  );
  const materialsFurgoneta = useMemo(
    () => materials.filter((m) => m.origen_estoc === "FURGONETA"),
    [materials]
  );

  const marcatsCount = materialsNau.filter((m) => m.carregat_pick_in).length;
  const confirmatsBdCount = materialsNau.filter((m) => m.confirmat_bd).length;
  const totalNauCount = materialsNau.length;
  const percentPickIn =
    totalNauCount > 0 ? Math.round((marcatsCount / totalNauCount) * 100) : 0;
  const totsMarcats = totalNauCount > 0 && marcatsCount === totalNauCount;
  const totsConfirmatsBd = totalNauCount > 0 && confirmatsBdCount === totalNauCount;

  const handleToggleCheck = (id: string) => {
    setMaterials((prev) =>
      prev.map((m) =>
        m.id === id ? { ...m, carregat_pick_in: !m.carregat_pick_in } : m
      )
    );
  };

  const handleMarcarTots = () => {
    setMaterials((prev) =>
      prev.map((m) =>
        m.origen_estoc !== "FURGONETA" ? { ...m, carregat_pick_in: true } : m
      )
    );
  };

  const handleConfirmarPickIn = async () => {
    const aConfirmar = materialsNau.filter((m) => m.carregat_pick_in);
    if (aConfirmar.length === 0) return;

    setDesant(true);
    setFeedback(null);
    try {
      await apiFetch("/operari/picking/linies/batch", {
        method: "PUT",
        body: JSON.stringify({
          items: aConfirmar.map((m) => ({
            linia_id: m.id,
            quantitat_carregada_pick_in: m.quantitat_programada,
          })),
        }),
      });
      await carregarMaterials(ordreActivaId);
      setFeedback({
        tipus: "ok",
        text: `Pick-In confirmat al magatzem (${aConfirmar.length} de ${totalNauCount} línies desades).`,
      });
      setFase("OBRA");
    } catch (err: unknown) {
      await carregarMaterials(ordreActivaId);
      setFeedback({
        tipus: "error",
        text: err instanceof Error ? err.message : "Error en confirmar el Pick-In. Cap canvi parcial no s'ha desat.",
      });
    } finally {
      setDesant(false);
    }
  };

  const handleRetornCanvi = (id: string, valor: number) => {
    setMaterials((prev) =>
      prev.map((m) => {
        if (m.id !== id) return m;
        const base = m.quantitat_carregada_pick_in || m.quantitat_programada;
        const maxRetorn = Math.max(0, base - (m.quantitat_mermada || 0));
        return {
          ...m,
          retornat_pick_out: Math.max(0, Math.min(maxRetorn, valor)),
        };
      })
    );
  };

  const handleMermaCanvi = (id: string, valor: number) => {
    setMaterials((prev) =>
      prev.map((m) => {
        if (m.id !== id) return m;
        const base = m.quantitat_carregada_pick_in || m.quantitat_programada;
        const maxMerma = Math.max(0, base - (m.retornat_pick_out || 0));
        return {
          ...m,
          quantitat_mermada: Math.max(0, Math.min(maxMerma, valor)),
        };
      })
    );
  };

  const handleConfirmarPickOut = async () => {
    if (materialsNau.length === 0) return;

    setDesant(true);
    setFeedback(null);
    try {
      await apiFetch("/operari/picking/linies/batch", {
        method: "PUT",
        body: JSON.stringify({
          items: materialsNau.map((m) => ({
            linia_id: m.id,
            quantitat_carregada_pick_in:
              m.quantitat_carregada_pick_in && m.quantitat_carregada_pick_in > 0
                ? m.quantitat_carregada_pick_in
                : m.quantitat_programada,
            quantitat_retornada_pick_out: m.retornat_pick_out ?? 0,
            quantitat_mermada: m.quantitat_mermada ?? 0,
          })),
        }),
      });
      await carregarMaterials(ordreActivaId);
      setFeedback({
        tipus: "ok",
        text: "Pick-Out consolidat. Estoc del magatzem i balanç de l'ordre actualitzats.",
      });
    } catch (err: unknown) {
      await carregarMaterials(ordreActivaId);
      setFeedback({
        tipus: "error",
        text: err instanceof Error ? err.message : "Error en consolidar el Pick-Out.",
      });
    } finally {
      setDesant(false);
    }
  };

  const handleConsumirDeFurgoneta = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!vanItemSel) return;
    const otTarget = ordreActivaId || materials[0]?.ordre_treball_id || "";
    if (!otTarget) {
      setFeedback({
        tipus: "error",
        text: "Selecciona primer una ordre de treball activa per imputar el material de la furgoneta.",
      });
      return;
    }

    const qty = parseFloat(vanQuantitat) || 0;
    const merma = parseFloat(vanMerma) || 0;
    if (qty <= 0 || qty > vanItemSel.quantitat_disponible) {
      setFeedback({
        tipus: "error",
        text: `Quantitat invàlida. Disponible a la furgoneta: ${vanItemSel.quantitat_disponible} ${vanItemSel.unitat}.`,
      });
      return;
    }
    if (merma < 0 || merma > qty) {
      setFeedback({
        tipus: "error",
        text: "La merma no pot superar la quantitat consumida.",
      });
      return;
    }

    setEnviantVan(true);
    setFeedback(null);
    try {
      if (typeof navigator !== "undefined" && navigator.onLine) {
        await apiFetch("/operari/picking/consum-vehicle", {
          method: "POST",
          body: JSON.stringify({
            ordre_treball_id: otTarget,
            article_id: vanItemSel.article_id,
            quantitat: qty,
            quantitat_mermada: merma,
            magatzem_id: vanStock?.magatzem_id || undefined,
            notes: vanNotes.trim() || undefined,
          }),
        });
        setFeedback({
          tipus: "ok",
          text: `Imputats ${qty} ${vanItemSel.unitat} de ${vanItemSel.nom} des de ${vanStock?.magatzem_nom || "furgoneta"}.`,
        });
        await Promise.all([
          carregarMaterials(otTarget),
          carregarEstocFurgoneta(otTarget),
        ]);
      } else {
        const { addToSyncQueue } = await import("@/lib/offline/sync");
        await addToSyncQueue("USE_MATERIAL_FROM_VAN", {
          ordre_treball_id: otTarget,
          article_id: vanItemSel.article_id,
          quantitat: qty,
          quantitat_mermada: merma,
          magatzem_id: vanStock?.magatzem_id || null,
          notes: vanNotes.trim() || null,
          timestamp: Date.now(),
        });
        setFeedback({
          tipus: "ok",
          text: `Registrat offline (${qty} ${vanItemSel.unitat} de ${vanItemSel.nom}). Es descomptarà de la furgoneta en recuperar connexió.`,
        });
      }
      setShowVanModal(false);
      setVanItemSel(null);
      setVanQuantitat("1");
      setVanMerma("0");
      setVanNotes("");
    } catch (err: unknown) {
      setFeedback({
        tipus: "error",
        text:
          err instanceof Error
            ? err.message
            : "Error registrant el material de la furgoneta.",
      });
    } finally {
      setEnviantVan(false);
    }
  };

  const handleReportarIncidenciaMagatzem = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!incText.trim()) return;
    setEnviantInc(true);
    setFeedback(null);
    try {
      await apiFetch("/operari/incidencies", {
        method: "POST",
        body: JSON.stringify({
          ordre_treball_id: ordreActivaId || null,
          ambit: "MAGATZEM",
          tipus: "DESQUADRAMENT_ESTOC",
          gravetat: "ALTA",
          estat: "VERMELL",
          text_observacions: incText.trim(),
        }),
      });
      setShowIncModal(false);
      setIncText("");
      setFeedback({
        tipus: "ok",
        text: "Incidència de magatzem enviada a l'oficina tècnica.",
      });
    } catch (err: unknown) {
      setFeedback({
        tipus: "error",
        text:
          err instanceof Error
            ? err.message
            : "Error enviant la incidència de magatzem.",
      });
    } finally {
      setEnviantInc(false);
    }
  };

  const vanItemsFiltrats = useMemo(() => {
    const items = vanStock?.items || [];
    const q = cercaVan.trim().toLowerCase();
    if (!q) return items;
    return items.filter(
      (it) =>
        it.nom.toLowerCase().includes(q) ||
        it.referencia.toLowerCase().includes(q) ||
        (it.codi_barres || "").toLowerCase().includes(q)
    );
  }, [vanStock, cercaVan]);

  return (
    <div className="flex-1 flex flex-col bg-surface dark:bg-slate-950 text-on-surface dark:text-slate-100 transition-colors">
      {/* Capçalera */}
      <header className="bg-surface-container-lowest dark:bg-slate-900 text-primary dark:text-white p-4 border-b border-outline-variant/25 dark:border-slate-800 flex items-center justify-between gap-2">
        <div className="flex items-center gap-3 min-w-0">
          <Link
            href={ordreActivaId ? `/operari/feines/${ordreActivaId}` : "/operari/feines"}
            className="w-9 h-9 rounded-lg bg-surface-container-low dark:bg-slate-800 hover:bg-surface-container flex items-center justify-center text-primary dark:text-white transition-colors shrink-0"
          >
            <ArrowLeft className="w-4 h-4" />
          </Link>
          <div className="min-w-0">
            <h1 className="text-base font-extrabold leading-tight text-primary dark:text-white truncate">
              Materials i magatzem
            </h1>
            <p className="text-xs text-on-surface-variant dark:text-slate-400 truncate">
              {fase === "PICK_IN"
                ? "Càrrega matinal (Nau)"
                : fase === "OBRA"
                ? "Execució a camp i furgoneta"
                : fase === "PICK_OUT"
                ? "Retorn a nau, mermes i balanç"
                : "Custòdia d'eines: Pick-In i Pick-Out"}
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={() => setShowIncModal(true)}
          className="px-2.5 py-1.5 rounded-lg text-xs font-bold bg-error-container/30 text-error border border-error/30 flex items-center gap-1 shrink-0 cursor-pointer"
          title="Notificar manca o desquadrament real d'estoc a nau"
        >
          <AlertTriangle className="w-3.5 h-3.5" />
          <span className="hidden xs:inline">Incidència</span>
        </button>
      </header>

      {/* Selector d'ordre de treball si l'operari en té diverses */}
      {feinesActives.length > 0 && (
        <div className="bg-surface-container-low/70 dark:bg-slate-900/70 px-4 py-2 border-b border-outline-variant/20 flex items-center justify-between gap-2">
          <label className="text-xs font-semibold text-on-surface-variant shrink-0">
            Ordre activa
          </label>
          <select
            value={ordreActivaId}
            onChange={(e) => setOrdreActivaId(e.target.value)}
            className="flex-1 max-w-xs px-2.5 py-1.5 rounded-lg bg-surface-container-lowest dark:bg-slate-800 border border-outline-variant/40 text-xs font-semibold text-primary dark:text-white"
          >
            {feinesActives.map((f) => (
              <option key={f.id} value={f.id}>
                {f.codi} — {f.titol}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Pestanyes de Fase */}
      <div className="bg-surface-container-lowest dark:bg-slate-900 border-b border-outline-variant/25 dark:border-slate-800 grid grid-cols-4 text-[11px] font-bold">
        {[
          { id: "PICK_IN" as const, label: "1. Pick In" },
          { id: "OBRA" as const, label: "2. Furgoneta" },
          { id: "PICK_OUT" as const, label: "3. Pick Out" },
          { id: "EINES" as const, label: `4. Eines (${einesAssignades.length})` },
        ].map((tab) => (
          <button
            key={tab.id}
            type="button"
            data-testid={`tab-material-${tab.id.toLowerCase()}`}
            onClick={() => setFase(tab.id)}
            className={`py-3 px-1 text-center border-b-2 transition-colors cursor-pointer truncate ${
              fase === tab.id
                ? "border-secondary-container text-secondary dark:text-emerald-400 bg-secondary-container/5"
                : "border-transparent text-on-surface-variant hover:text-primary dark:text-slate-400"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Missatge de feedback */}
      {feedback && (
        <div
          className={`mx-4 mt-3 px-3.5 py-2.5 rounded-xl text-xs font-semibold flex items-center justify-between gap-2 border ${
            feedback.tipus === "ok"
              ? "bg-secondary-container/15 border-secondary/30 text-secondary"
              : "bg-error-container/30 border-error/40 text-error"
          }`}
        >
          <span>{feedback.text}</span>
          <button
            type="button"
            onClick={() => setFeedback(null)}
            className="p-0.5 opacity-70 hover:opacity-100 cursor-pointer"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* Contingut principal */}
      <div className="flex-1 p-4 flex flex-col space-y-4 overflow-y-auto">
        {loading && materials.length === 0 && (
          <div className="flex-1 flex items-center justify-center text-on-surface-variant text-xs font-semibold">
            Carregant materials...
          </div>
        )}

        {/* Estat buit real + accés directe al magatzem de la furgoneta */}
        {!loading && materials.length === 0 && fase !== "OBRA" && fase !== "EINES" && (
          <div className="flex-1 flex flex-col items-center justify-center p-7 text-center bg-surface-container-lowest dark:bg-slate-900 rounded-2xl border-2 border-dashed border-outline-variant/40 dark:border-slate-800 my-auto shadow-sm space-y-3">
            <div className="w-14 h-14 rounded-2xl bg-secondary-container/10 text-secondary flex items-center justify-center">
              <Package className="w-7 h-7" />
            </div>
            <h3 className="text-base font-extrabold text-primary dark:text-slate-100">
              Aquesta tasca no té materials ni eines programades
            </h3>
            <p className="text-xs text-on-surface-variant dark:text-slate-400 max-w-xs">
              Si necessites peces a camp, pots imputar material directament des del magatzem de la furgoneta assignada.
            </p>
            <div className="flex flex-wrap items-center justify-center gap-2 pt-2">
              <button
                type="button"
                onClick={() => {
                  setFase("OBRA");
                  setShowVanModal(true);
                }}
                className="px-4 py-2.5 rounded-xl bg-primary hover:bg-primary-container text-white text-xs font-bold shadow-sm flex items-center gap-1.5 cursor-pointer"
              >
                <Truck className="w-4 h-4" />
                <span>Agafar de la furgoneta</span>
              </button>
              <button
                type="button"
                onClick={() => carregarMaterials(ordreActivaId)}
                disabled={loading}
                className="px-4 py-2.5 rounded-xl bg-surface-container-high text-on-surface text-xs font-bold flex items-center gap-1.5 cursor-pointer"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
                <span>Actualitzar</span>
              </button>
            </div>
          </div>
        )}

        {/* FASE 1: PICK IN */}
        {materialsNau.length > 0 && fase === "PICK_IN" && (
          <div className="space-y-4">
            <div className="bg-surface-container-low dark:bg-slate-900 rounded-xl p-4 border border-outline-variant/25 dark:border-slate-800 space-y-2.5">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <span className="text-xs text-on-surface-variant block">
                    {totsConfirmatsBd
                      ? "Càrrega a nau confirmada al magatzem"
                      : `Confirmats a magatzem: ${confirmatsBdCount} de ${totalNauCount}`}
                  </span>
                  <h2 className="text-lg font-extrabold text-primary dark:text-white">
                    {totsConfirmatsBd
                      ? `${confirmatsBdCount} de ${totalNauCount} ítems confirmats`
                      : `${marcatsCount} de ${totalNauCount} ítems seleccionats`}
                  </h2>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  {!totsMarcats && (
                    <button
                      type="button"
                      onClick={handleMarcarTots}
                      className="px-2.5 py-1 rounded-lg bg-surface-container-lowest dark:bg-slate-800 border border-outline-variant/40 text-[11px] font-bold text-primary dark:text-slate-200 hover:border-primary/50 transition-colors cursor-pointer"
                    >
                      Marcar tots
                    </button>
                  )}
                  <span className="text-sm font-mono font-extrabold text-secondary">
                    {percentPickIn}%
                  </span>
                </div>
              </div>
              <div className="w-full h-2 bg-surface-container-highest dark:bg-slate-800 rounded-full overflow-hidden">
                <div
                  className="h-full bg-secondary-container rounded-full transition-all duration-300"
                  style={{ width: `${percentPickIn}%` }}
                />
              </div>
              {!totsConfirmatsBd && marcatsCount > confirmatsBdCount && (
                <p className="text-[11px] text-amber-700 dark:text-amber-300 font-medium">
                  Els ítems marcats encara no s&apos;han desat. Prem el botó de confirmació inferior per registrar la càrrega.
                </p>
              )}
            </div>

            <div className="space-y-2.5">
              {materialsNau.map((m) => (
                <div
                  key={m.id}
                  onClick={() => handleToggleCheck(m.id)}
                  className={`p-3.5 rounded-xl border transition-all cursor-pointer flex items-center justify-between ${
                    m.confirmat_bd
                      ? "bg-secondary-container/12 border-secondary-container text-primary dark:text-emerald-200"
                      : m.carregat_pick_in
                      ? "bg-amber-500/8 border-amber-500/50 text-primary dark:text-amber-100"
                      : "bg-surface-container-lowest dark:bg-slate-900 border-outline-variant/30 dark:border-slate-800 hover:border-primary/40"
                  }`}
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <div className={m.confirmat_bd ? "text-secondary-container shrink-0" : "text-amber-600 dark:text-amber-400 shrink-0"}>
                      {m.carregat_pick_in ? (
                        <CheckSquare className="w-6 h-6" />
                      ) : (
                        <Square className="w-6 h-6 text-outline-variant dark:text-slate-600" />
                      )}
                    </div>
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-[11px] font-mono font-bold px-1.5 py-0.5 rounded bg-surface-container-low dark:bg-slate-800 text-primary dark:text-slate-300">
                          {m.referencia}
                        </span>
                        {m.magatzem_nom && (
                          <span className="text-[11px] text-on-surface-variant">
                            {m.magatzem_nom}
                          </span>
                        )}
                        {m.confirmat_bd ? (
                          <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-secondary-container/20 text-secondary">
                            Confirmat
                          </span>
                        ) : m.carregat_pick_in ? (
                          <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-700 dark:text-amber-300">
                            Pendent de desar
                          </span>
                        ) : null}
                        {m.es_eina && (
                          <span className="text-[11px] font-bold px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-700 dark:text-amber-300 inline-flex items-center gap-1">
                            <Wrench className="w-3 h-3" /> Eina
                          </span>
                        )}
                      </div>
                      <h4
                        className={`text-sm font-bold mt-1 truncate ${
                          m.confirmat_bd
                            ? "line-through opacity-75 text-on-surface-variant"
                            : "text-primary dark:text-slate-100"
                        }`}
                      >
                        {m.nom}
                      </h4>
                    </div>
                  </div>

                  <div className="text-right font-mono font-extrabold text-sm text-primary dark:text-white shrink-0 ml-2">
                    {m.quantitat_programada} {m.unitat}
                  </div>
                </div>
              ))}
            </div>

            <button
              type="button"
              data-testid="btn-confirmar-pick-in"
              onClick={handleConfirmarPickIn}
              disabled={!totsMarcats || desant}
              className={`w-full py-3.5 rounded-xl font-bold text-xs flex items-center justify-center gap-2 shadow-md transition-all cursor-pointer ${
                totsMarcats && !desant
                  ? "bg-secondary-container hover:brightness-110 text-white active:scale-[0.98]"
                  : "bg-surface-container-high dark:bg-slate-800 text-outline dark:text-slate-500 cursor-not-allowed"
              }`}
            >
              {desant ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <CheckCircle2 className="w-4 h-4" />
              )}
              <span>
                {desant
                  ? "Desant Pick-In al magatzem..."
                  : totsConfirmatsBd
                  ? "Pick-In confirmat · Reconfirmar i passar a Furgoneta"
                  : `Confirmar Pick In (${marcatsCount} de ${totalNauCount})`}
              </span>
            </button>
          </div>
        )}

        {/* FASE 2: EXECUCIÓ A CAMP I ESTOC DE FURGONETA */}
        {fase === "OBRA" && (
          <div className="space-y-4">
            <div className="p-4 rounded-xl bg-surface-container-lowest dark:bg-slate-900 border border-outline-variant/25 dark:border-slate-800 shadow-sm space-y-3">
              <div className="flex items-center justify-between gap-2">
                <div>
                  <h3 className="text-sm font-extrabold text-primary dark:text-white">
                    Magatzem del vehicle
                  </h3>
                  <p className="text-xs text-on-surface-variant">
                    {vanStock?.magatzem_nom
                      ? `${vanStock.magatzem_nom}${vanStock.vehicle_matricula ? ` (${vanStock.vehicle_matricula})` : ""} · ${vanStock.items.length} articles amb estoc`
                      : "Cap magatzem de furgoneta vinculat a aquesta ordre"}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => carregarEstocFurgoneta(ordreActivaId)}
                  disabled={loadingVan}
                  className="p-2 rounded-lg bg-surface-container-low text-primary hover:bg-surface-container cursor-pointer"
                  title="Actualitzar estoc de furgoneta"
                >
                  <RefreshCw className={`w-4 h-4 ${loadingVan ? "animate-spin" : ""}`} />
                </button>
              </div>

              <button
                type="button"
                data-testid="btn-obrir-magatzem-furgoneta"
                onClick={() => setShowVanModal(true)}
                className="w-full py-3 px-3.5 rounded-xl bg-primary hover:bg-primary-container text-white text-xs font-bold flex items-center justify-between shadow-sm transition-colors cursor-pointer"
              >
                <div className="flex items-center gap-2">
                  <Truck className="w-4 h-4" />
                  <span>Agafar peça del magatzem de la furgoneta</span>
                </div>
                <Plus className="w-4 h-4" />
              </button>

              <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/30 text-xs text-amber-900 dark:text-amber-200 flex items-start gap-2.5">
                <Scissors className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                <p className="leading-relaxed">
                  En materials continus (tubs, cables), esgota primer el retall de furgoneta abans de tallar bobina nova.
                </p>
              </div>
            </div>

            {/* Materials imputats des de la furgoneta a aquesta OT */}
            <div className="space-y-2">
              <h4 className="text-xs font-bold text-on-surface-variant px-1">
                Material agafat de furgoneta en aquesta ordre ({materialsFurgoneta.length})
              </h4>
              {materialsFurgoneta.length === 0 ? (
                <div className="p-4 rounded-xl bg-surface-container-lowest dark:bg-slate-900 border border-dashed border-outline-variant/40 text-center text-xs text-on-surface-variant">
                  Encara no s&apos;ha imputat cap peça de l&apos;estoc del vehicle en aquesta ordre.
                </div>
              ) : (
                materialsFurgoneta.map((m) => (
                  <div
                    key={m.id}
                    className="p-3.5 rounded-xl bg-surface-container-lowest dark:bg-slate-900 border border-secondary/30 flex items-center justify-between"
                  >
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-[11px] font-mono font-bold px-1.5 py-0.5 rounded bg-secondary-container/15 text-secondary">
                          Furgoneta
                        </span>
                        <span className="text-[11px] font-mono text-on-surface-variant">
                          {m.referencia}
                        </span>
                      </div>
                      <p className="text-sm font-bold text-primary dark:text-white mt-1 truncate">
                        {m.nom}
                      </p>
                      {m.quantitat_mermada > 0 && (
                        <p className="text-[11px] text-amber-700 dark:text-amber-300">
                          Merma declarada: {m.quantitat_mermada} {m.unitat}
                        </p>
                      )}
                    </div>
                    <div className="text-right font-mono font-extrabold text-sm text-secondary shrink-0 ml-2">
                      {m.quantitat_carregada_pick_in} {m.unitat}
                    </div>
                  </div>
                ))
              )}
            </div>

            {materialsNau.length > 0 && (
              <button
                type="button"
                onClick={() => setFase("PICK_OUT")}
                className="w-full py-3.5 rounded-xl bg-secondary-container hover:brightness-110 text-white text-xs font-bold flex items-center justify-center gap-2 shadow-md transition-all cursor-pointer"
              >
                <span>Arribada a nau: iniciar devolució Pick Out</span>
              </button>
            )}
          </div>
        )}

        {/* FASE 3: PICK OUT (DEVOLUCIÓ I MERMES) */}
        {materialsNau.length > 0 && fase === "PICK_OUT" && (
          <div className="space-y-4">
            <div className="p-4 rounded-xl bg-surface-container-lowest dark:bg-slate-900 border border-outline-variant/25 dark:border-slate-800 shadow-sm space-y-3">
              <div>
                <h3 className="text-sm font-extrabold text-primary dark:text-white">
                  Devolució de sobrants i mermes a nau
                </h3>
                <p className="text-xs text-on-surface-variant mt-0.5">
                  Indica el material intacte que torna al magatzem i la merma (retalls/trencaments). L&apos;estoc físic i la reserva s&apos;actualitzen automàticament.
                </p>
              </div>

              <div className="space-y-3 pt-1">
                {materialsNau.map((m) => {
                  const base = m.quantitat_carregada_pick_in || m.quantitat_programada;
                  const retornat = m.retornat_pick_out ?? 0;
                  const merma = m.quantitat_mermada ?? 0;
                  const consumInstallat = Math.max(0, +(base - retornat - merma).toFixed(3));

                  return (
                    <div
                      key={m.id}
                      className="p-3.5 rounded-xl bg-surface-container-low dark:bg-slate-800/70 border border-outline-variant/30 space-y-2.5"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <p className="text-sm font-bold text-primary dark:text-slate-100 truncate">
                            {m.nom}
                          </p>
                          <p className="text-xs font-mono text-on-surface-variant">
                            Carregat: {base} {m.unitat}
                          </p>
                        </div>
                        <div className="text-right shrink-0">
                          <span className="text-[11px] text-on-surface-variant block">
                            Consum net
                          </span>
                          <span className="text-sm font-mono font-extrabold text-secondary dark:text-emerald-400">
                            {consumInstallat} {m.unitat}
                          </span>
                        </div>
                      </div>

                      <div className="grid grid-cols-2 gap-2.5 pt-1 border-t border-outline-variant/20">
                        <div>
                          <label className="block text-[11px] font-semibold text-on-surface-variant mb-1">
                            Retorn intacte ({m.unitat})
                          </label>
                          <input
                            type="number"
                            min="0"
                            max={base}
                            step={m.format_continu ? "0.01" : "1"}
                            value={retornat}
                            onChange={(e) =>
                              handleRetornCanvi(m.id, parseFloat(e.target.value) || 0)
                            }
                            className="w-full p-2 rounded-lg border border-outline-variant dark:border-slate-700 bg-surface-container-lowest dark:bg-slate-900 text-center text-xs font-mono font-bold text-primary dark:text-white"
                          />
                        </div>
                        <div>
                          <label className="block text-[11px] font-semibold text-on-surface-variant mb-1">
                            Merma / residu ({m.unitat})
                          </label>
                          <input
                            type="number"
                            min="0"
                            max={Math.max(0, base - retornat)}
                            step={m.format_continu ? "0.01" : "1"}
                            value={merma}
                            onChange={(e) =>
                              handleMermaCanvi(m.id, parseFloat(e.target.value) || 0)
                            }
                            className="w-full p-2 rounded-lg border border-outline-variant dark:border-slate-700 bg-surface-container-lowest dark:bg-slate-900 text-center text-xs font-mono font-bold text-amber-700 dark:text-amber-300"
                          />
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            <button
              type="button"
              disabled={desant}
              onClick={handleConfirmarPickOut}
              className="w-full py-3.5 rounded-xl bg-secondary-container hover:brightness-110 text-white text-xs font-bold flex items-center justify-center gap-2 shadow-md transition-all disabled:opacity-50 cursor-pointer"
            >
              {desant ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <CheckCircle2 className="w-4 h-4" />
              )}
              <span>Confirmar devolució i actualitzar magatzem</span>
            </button>
          </div>
        )}

        {/* FASE 4: BOX EINES (PICK-IN I PICK-OUT D'EINES EN CUSTÒDIA) */}
        {fase === "EINES" && (
          <div data-testid="box-eines-picking" className="space-y-4">
            <div className="p-4 rounded-xl bg-surface-container-lowest dark:bg-slate-900 border border-outline-variant/25 dark:border-slate-800 shadow-sm space-y-3">
              <div className="flex items-center justify-between gap-2">
                <div>
                  <h3 className="text-sm font-extrabold text-primary dark:text-white flex items-center gap-1.5">
                    <Wrench className="w-4 h-4 text-amber-500" />
                    <span>Eines en custòdia (Pick-In / Pick-Out)</span>
                  </h3>
                  <p className="text-xs text-on-surface-variant">
                    {einesAssignades.length} eina(es) activa(es) · {einesDisponibles.length} disponible(s) a nau
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => carregarEines(ordreActivaId)}
                  disabled={loadingEines}
                  className="p-2 rounded-lg bg-surface-container-low text-primary hover:bg-surface-container cursor-pointer"
                  title="Actualitzar eines"
                >
                  <RefreshCw className={`w-4 h-4 ${loadingEines ? "animate-spin" : ""}`} />
                </button>
              </div>

              <button
                type="button"
                data-testid="btn-obrir-eines-disponibles"
                onClick={() => setShowEinesDispModal(true)}
                className="w-full py-3 px-3.5 rounded-xl bg-primary hover:bg-primary-container text-white text-xs font-bold flex items-center justify-between shadow-sm transition-colors cursor-pointer"
              >
                <span className="flex items-center gap-2">
                  <ArrowDownLeft className="w-4 h-4 text-secondary-container" />
                  <span>Fer Pick-In d&apos;una eina disponible de nau</span>
                </span>
                <Plus className="w-4 h-4" />
              </button>
            </div>

            {loadingEines && einesAssignades.length === 0 ? (
              <div className="p-6 text-center text-xs text-on-surface-variant">
                Carregant eines assignades...
              </div>
            ) : einesAssignades.length === 0 ? (
              <div className="p-7 text-center bg-surface-container-lowest dark:bg-slate-900 rounded-2xl border-2 border-dashed border-outline-variant/40 dark:border-slate-800 space-y-2.5">
                <div className="w-12 h-12 rounded-2xl bg-amber-500/10 text-amber-600 flex items-center justify-center mx-auto">
                  <Wrench className="w-6 h-6" />
                </div>
                <h4 className="text-sm font-extrabold text-primary dark:text-white">
                  Cap eina en custòdia per a aquesta ordre
                </h4>
                <p className="text-xs text-on-surface-variant dark:text-slate-400">
                  Selecciona una eina disponible a nau per registrar el seu Pick-In.
                </p>
              </div>
            ) : (
              <div className="space-y-2.5">
                {einesAssignades.map((eina) => {
                  const busy = einaProcessantId === eina.id;
                  const enFurgoneta = eina.estat === "EN_VEHICLE";
                  return (
                    <div
                      key={eina.id}
                      data-testid={`eina-card-${eina.id}`}
                      className="p-3.5 rounded-xl bg-surface-container-lowest dark:bg-slate-900 border border-outline-variant/30 dark:border-slate-800 shadow-sm space-y-3"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <div className="flex items-center gap-1.5 flex-wrap">
                            <span className="text-[11px] font-mono font-bold px-1.5 py-0.5 rounded bg-surface-container-low dark:bg-slate-800 text-primary dark:text-slate-200">
                              SN: {eina.numero_serie}
                            </span>
                            {eina.ordre_codi && (
                              <span className="text-[10px] font-mono font-bold text-secondary">
                                {eina.ordre_codi}
                              </span>
                            )}
                          </div>
                          <h4 className="text-sm font-bold text-primary dark:text-white mt-1">
                            {eina.nom}
                          </h4>
                          <p className="text-xs text-on-surface-variant dark:text-slate-400">
                            {eina.model || "Model estàndard"}
                            {eina.magatzem_nom ? ` · ${eina.magatzem_nom}` : ""}
                          </p>
                        </div>

                        <span
                          className={`text-[10px] font-extrabold px-2.5 py-1 rounded-full border shrink-0 ${
                            enFurgoneta
                              ? "bg-primary/10 text-primary dark:text-sky-300 border-primary/25"
                              : "bg-secondary-container/15 text-secondary border-secondary-container/30"
                          }`}
                        >
                          {enFurgoneta ? "En Furgoneta" : eina.estat}
                        </span>
                      </div>

                      <div className="grid grid-cols-3 gap-1.5 pt-2 border-t border-outline-variant/20">
                        <button
                          type="button"
                          disabled={busy}
                          data-testid={`btn-eina-pickin-${eina.id}`}
                          onClick={() =>
                            handlePickInEina(eina, enFurgoneta ? "CUSTODIADA" : "EN_VEHICLE")
                          }
                          className="py-2 px-2 rounded-lg bg-surface-container-low dark:bg-slate-800 hover:bg-surface-container text-primary dark:text-slate-200 text-[11px] font-bold flex items-center justify-center gap-1 disabled:opacity-50 cursor-pointer"
                        >
                          <Truck className="w-3.5 h-3.5 text-secondary shrink-0" />
                          <span>{enFurgoneta ? "A Operari" : "A Furgoneta"}</span>
                        </button>

                        <button
                          type="button"
                          disabled={busy}
                          data-testid={`btn-eina-pickout-${eina.id}`}
                          onClick={() => handlePickOutEina(eina, "DISPONIBLE")}
                          className="py-2 px-2 rounded-lg bg-secondary-container hover:brightness-110 text-white text-[11px] font-bold flex items-center justify-center gap-1 disabled:opacity-50 cursor-pointer"
                        >
                          {busy ? (
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          ) : (
                            <ArrowUpRight className="w-3.5 h-3.5 shrink-0" />
                          )}
                          <span>Pick-Out OK</span>
                        </button>

                        <button
                          type="button"
                          disabled={busy}
                          data-testid={`btn-eina-avaria-${eina.id}`}
                          onClick={() => {
                            setEinaPickOutAvaria(eina);
                            setAvariaEinaText("");
                          }}
                          className="py-2 px-2 rounded-lg bg-error-container/30 hover:bg-error-container/50 text-error border border-error/30 text-[11px] font-bold flex items-center justify-center gap-1 disabled:opacity-50 cursor-pointer"
                        >
                          <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
                          <span>Avaria</span>
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Modal Real: Pick-In d'Eines Disponibles de Nau */}
      {showEinesDispModal && (
        <div className="fixed inset-0 z-50 bg-slate-950/60 backdrop-blur-xs flex items-end sm:items-center justify-center p-3">
          <div className="w-full max-w-md bg-surface-container-lowest dark:bg-slate-900 rounded-2xl border border-outline-variant/30 shadow-2xl overflow-hidden flex flex-col max-h-[85vh]">
            <div className="p-4 border-b border-outline-variant/20 flex items-center justify-between">
              <div>
                <h3 className="text-sm font-extrabold text-primary dark:text-white flex items-center gap-2">
                  <Wrench className="w-4 h-4 text-amber-500" />
                  <span>Pick-In d&apos;eina disponible</span>
                </h3>
                <p className="text-xs text-on-surface-variant">
                  Selecciona el destí i l&apos;eina a retirar del magatzem
                </p>
              </div>
              <button
                type="button"
                onClick={() => setShowEinesDispModal(false)}
                className="p-1.5 rounded-lg hover:bg-surface-container text-on-surface-variant cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="p-4 space-y-3 overflow-y-auto flex-1">
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => setDestiPickInEina("CUSTODIADA")}
                  className={`py-2 px-3 rounded-xl text-xs font-bold border transition-colors cursor-pointer ${
                    destiPickInEina === "CUSTODIADA"
                      ? "bg-secondary-container text-white border-secondary-container"
                      : "bg-surface-container-low dark:bg-slate-800 text-on-surface border-outline-variant/40"
                  }`}
                >
                  Custòdia operari
                </button>
                <button
                  type="button"
                  onClick={() => setDestiPickInEina("EN_VEHICLE")}
                  className={`py-2 px-3 rounded-xl text-xs font-bold border transition-colors cursor-pointer ${
                    destiPickInEina === "EN_VEHICLE"
                      ? "bg-secondary-container text-white border-secondary-container"
                      : "bg-surface-container-low dark:bg-slate-800 text-on-surface border-outline-variant/40"
                  }`}
                >
                  Carregar a furgoneta
                </button>
              </div>

              <div className="relative">
                <Search className="w-4 h-4 text-on-surface-variant absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  value={cercaEinaDisp}
                  onChange={(e) => setCercaEinaDisp(e.target.value)}
                  placeholder="Cerca per nom, model o número de sèrie..."
                  className="w-full pl-9 pr-3 py-2 rounded-xl bg-surface-container-low dark:bg-slate-800 border border-outline-variant/40 text-xs"
                />
              </div>

              {einesDispFiltrades.length === 0 ? (
                <div className="p-6 text-center rounded-xl border border-dashed border-outline-variant/40 text-xs text-on-surface-variant">
                  No hi ha eines disponibles al magatzem que coincideixin amb la cerca.
                </div>
              ) : (
                <div className="space-y-2">
                  {einesDispFiltrades.map((eina) => (
                    <button
                      key={eina.id}
                      type="button"
                      disabled={einaProcessantId === eina.id}
                      onClick={() => handlePickInEina(eina, destiPickInEina)}
                      className="w-full text-left p-3 rounded-xl bg-surface-container-low dark:bg-slate-800/70 hover:border-primary border border-outline-variant/30 flex items-center justify-between gap-2 cursor-pointer disabled:opacity-50"
                    >
                      <div className="min-w-0">
                        <span className="text-[11px] font-mono text-secondary font-bold">
                          SN: {eina.numero_serie}
                        </span>
                        <p className="text-xs font-bold text-primary dark:text-white truncate">
                          {eina.nom}
                        </p>
                        {eina.model && (
                          <p className="text-[11px] text-on-surface-variant truncate">
                            {eina.model}
                          </p>
                        )}
                      </div>
                      <span className="px-2.5 py-1 rounded-lg bg-primary text-white text-[11px] font-bold shrink-0">
                        Pick-In
                      </span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Modal Real: Pick-Out d'Eina amb Avaria */}
      {einaPickOutAvaria && (
        <div className="fixed inset-0 z-50 bg-slate-950/60 backdrop-blur-xs flex items-end sm:items-center justify-center p-3">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handlePickOutEina(einaPickOutAvaria, "AVARIADA", avariaEinaText);
            }}
            className="w-full max-w-md bg-surface-container-lowest dark:bg-slate-900 rounded-2xl border border-outline-variant/30 shadow-2xl p-4 space-y-3"
          >
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-extrabold text-error flex items-center gap-1.5">
                <AlertTriangle className="w-4 h-4" />
                <span>Pick-Out amb avaria d&apos;eina</span>
              </h3>
              <button
                type="button"
                onClick={() => setEinaPickOutAvaria(null)}
                className="p-1 text-on-surface-variant cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <p className="text-xs text-on-surface-variant">
              <strong>{einaPickOutAvaria.nom}</strong> (SN: {einaPickOutAvaria.numero_serie}) quedarà bloquejada com a <strong>AVARIADA</strong> i s&apos;obrirà una incidència a oficina.
            </p>
            <textarea
              required
              rows={3}
              value={avariaEinaText}
              onChange={(e) => setAvariaEinaText(e.target.value)}
              placeholder="Descriu l'avaria o desperfecte detectat..."
              className="w-full p-2.5 rounded-xl bg-surface-container-low dark:bg-slate-800 border border-outline-variant/50 text-xs"
            />
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setEinaPickOutAvaria(null)}
                className="flex-1 py-2.5 rounded-xl bg-surface-container text-on-surface text-xs font-bold cursor-pointer"
              >
                Cancel·lar
              </button>
              <button
                type="submit"
                disabled={einaProcessantId === einaPickOutAvaria.id || !avariaEinaText.trim()}
                className="flex-1 py-2.5 rounded-xl bg-error text-white text-xs font-bold disabled:opacity-50 cursor-pointer"
              >
                {einaProcessantId === einaPickOutAvaria.id ? "Registrant..." : "Confirmar avaria"}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Modal Real: Agafar Material de la Furgoneta */}
      {showVanModal && (
        <div className="fixed inset-0 z-50 bg-slate-950/60 backdrop-blur-xs flex items-end sm:items-center justify-center p-3">
          <div className="w-full max-w-md bg-surface-container-lowest dark:bg-slate-900 rounded-2xl border border-outline-variant/30 shadow-2xl overflow-hidden flex flex-col max-h-[85vh]">
            <div className="p-4 border-b border-outline-variant/20 flex items-center justify-between">
              <div>
                <h3 className="text-sm font-extrabold text-primary dark:text-white flex items-center gap-2">
                  <Truck className="w-4 h-4 text-secondary" />
                  <span>Estoc de furgoneta</span>
                </h3>
                <p className="text-xs text-on-surface-variant">
                  {vanStock?.magatzem_nom || "Sense magatzem de vehicle assignat"}
                </p>
              </div>
              <button
                type="button"
                onClick={() => {
                  setShowVanModal(false);
                  setVanItemSel(null);
                }}
                className="p-1.5 rounded-lg hover:bg-surface-container text-on-surface-variant cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="p-4 space-y-3 overflow-y-auto flex-1">
              {!vanItemSel ? (
                <>
                  <div className="relative">
                    <Search className="w-4 h-4 text-on-surface-variant absolute left-3 top-1/2 -translate-y-1/2" />
                    <input
                      type="text"
                      value={cercaVan}
                      onChange={(e) => setCercaVan(e.target.value)}
                      placeholder="Cerca per nom o referència..."
                      className="w-full pl-9 pr-3 py-2 rounded-xl bg-surface-container-low dark:bg-slate-800 border border-outline-variant/40 text-xs"
                    />
                  </div>

                  {loadingVan ? (
                    <p className="text-center text-xs text-on-surface-variant py-6">
                      Consultant estoc real de la furgoneta...
                    </p>
                  ) : vanItemsFiltrats.length === 0 ? (
                    <div className="p-6 text-center rounded-xl border border-dashed border-outline-variant/40 text-xs text-on-surface-variant">
                      {vanStock?.magatzem_id
                        ? "No hi ha articles disponibles amb estoc positiu en aquesta furgoneta."
                        : "Aquesta ordre no té cap vehicle amb magatzem mòbil configurat."}
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {vanItemsFiltrats.map((item) => (
                        <button
                          key={item.estoc_id}
                          type="button"
                          onClick={() => {
                            setVanItemSel(item);
                            setVanQuantitat("1");
                            setVanMerma("0");
                          }}
                          className="w-full text-left p-3 rounded-xl bg-surface-container-low dark:bg-slate-800/70 hover:border-primary border border-outline-variant/30 flex items-center justify-between gap-2 cursor-pointer"
                        >
                          <div className="min-w-0">
                            <span className="text-[11px] font-mono text-secondary font-bold">
                              {item.referencia}
                            </span>
                            <p className="text-xs font-bold text-primary dark:text-white truncate">
                              {item.nom}
                            </p>
                          </div>
                          <span className="text-xs font-mono font-extrabold text-primary dark:text-emerald-400 shrink-0">
                            {item.quantitat_disponible} {item.unitat}
                          </span>
                        </button>
                      ))}
                    </div>
                  )}
                </>
              ) : (
                <form onSubmit={handleConsumirDeFurgoneta} className="space-y-3">
                  <div className="p-3 rounded-xl bg-surface-container-low dark:bg-slate-800 border border-outline-variant/30">
                    <span className="text-[11px] font-mono text-secondary font-bold">
                      {vanItemSel.referencia}
                    </span>
                    <p className="text-sm font-bold text-primary dark:text-white">
                      {vanItemSel.nom}
                    </p>
                    <p className="text-xs text-on-surface-variant mt-0.5">
                      Disponible al vehicle: <strong>{vanItemSel.quantitat_disponible} {vanItemSel.unitat}</strong>
                    </p>
                  </div>

                  <div className="grid grid-cols-2 gap-2.5">
                    <div>
                      <label className="block text-xs font-semibold text-on-surface-variant mb-1">
                        Quantitat usada ({vanItemSel.unitat})
                      </label>
                      <input
                        type="number"
                        required
                        min={vanItemSel.format_continu ? "0.01" : "1"}
                        max={vanItemSel.quantitat_disponible}
                        step={vanItemSel.format_continu ? "0.01" : "1"}
                        value={vanQuantitat}
                        onChange={(e) => setVanQuantitat(e.target.value)}
                        className="w-full p-2.5 rounded-xl bg-surface-container-low dark:bg-slate-800 border border-outline-variant/50 text-sm font-mono font-bold"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-on-surface-variant mb-1">
                        Merma ({vanItemSel.unitat})
                      </label>
                      <input
                        type="number"
                        min="0"
                        max={vanQuantitat || "0"}
                        step={vanItemSel.format_continu ? "0.01" : "1"}
                        value={vanMerma}
                        onChange={(e) => setVanMerma(e.target.value)}
                        className="w-full p-2.5 rounded-xl bg-surface-container-low dark:bg-slate-800 border border-outline-variant/50 text-sm font-mono font-bold"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-on-surface-variant mb-1">
                      Nota tècnica (opcional)
                    </label>
                    <input
                      type="text"
                      value={vanNotes}
                      onChange={(e) => setVanNotes(e.target.value)}
                      placeholder="Ex: substitució maneguet trencat a arqueta 2"
                      className="w-full p-2.5 rounded-xl bg-surface-container-low dark:bg-slate-800 border border-outline-variant/50 text-xs"
                    />
                  </div>

                  <div className="flex gap-2 pt-2">
                    <button
                      type="button"
                      onClick={() => setVanItemSel(null)}
                      className="flex-1 py-2.5 rounded-xl bg-surface-container text-on-surface text-xs font-bold cursor-pointer"
                    >
                      Tornar
                    </button>
                    <button
                      type="submit"
                      disabled={enviantVan}
                      className="flex-1 py-2.5 rounded-xl bg-secondary-container text-white text-xs font-bold flex items-center justify-center gap-1.5 disabled:opacity-50 cursor-pointer"
                    >
                      {enviantVan && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                      <span>Imputar a l&apos;ordre</span>
                    </button>
                  </div>
                </form>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Modal Real: Incidència de Magatzem */}
      {showIncModal && (
        <div className="fixed inset-0 z-50 bg-slate-950/60 backdrop-blur-xs flex items-end sm:items-center justify-center p-3">
          <form
            onSubmit={handleReportarIncidenciaMagatzem}
            className="w-full max-w-md bg-surface-container-lowest dark:bg-slate-900 rounded-2xl border border-outline-variant/30 shadow-2xl p-4 space-y-3"
          >
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-extrabold text-error flex items-center gap-1.5">
                <AlertTriangle className="w-4 h-4" />
                <span>Reportar desquadrament d&apos;estoc</span>
              </h3>
              <button
                type="button"
                onClick={() => setShowIncModal(false)}
                className="p-1 text-on-surface-variant cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <p className="text-xs text-on-surface-variant">
              Aquesta incidència queda registrada a l&apos;ordre activa i avisa l&apos;enginyer i magatzem.
            </p>
            <textarea
              required
              rows={3}
              value={incText}
              onChange={(e) => setIncText(e.target.value)}
              placeholder="Indica quin article falta o està danyat al magatzem..."
              className="w-full p-2.5 rounded-xl bg-surface-container-low dark:bg-slate-800 border border-outline-variant/50 text-xs"
            />
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setShowIncModal(false)}
                className="flex-1 py-2.5 rounded-xl bg-surface-container text-on-surface text-xs font-bold cursor-pointer"
              >
                Cancel·lar
              </button>
              <button
                type="submit"
                disabled={enviantInc || !incText.trim()}
                className="flex-1 py-2.5 rounded-xl bg-error text-white text-xs font-bold disabled:opacity-50 cursor-pointer"
              >
                {enviantInc ? "Enviant..." : "Enviar incidència"}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}

export default function OperariMaterialPage() {
  return (
    <Suspense
      fallback={
        <div className="flex-1 flex items-center justify-center text-xs text-on-surface-variant">
          Inicialitzant picking...
        </div>
      }
    >
      <OperariMaterialContent />
    </Suspense>
  );
}
