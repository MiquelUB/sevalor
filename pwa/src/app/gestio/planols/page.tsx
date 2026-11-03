"use client";

import React, { useState, useEffect, useRef } from "react";
import {
  Folder,
  FolderPlus,
  FileText,
  MapPin,
  AlertTriangle,
  Plus,
  X,
  RefreshCw,
  UploadCloud,
  FileUp,
  Download,
  ExternalLink,
  CheckCircle2,
  Layers,
  Eye,
  EyeOff,
  Lock,
  Pencil,
  Trash2,
  MousePointer,
  Activity,
  RotateCcw,
  Save,
  FileDown,
  ShieldCheck,
  Palette,
  Check,
  ZoomIn,
  ZoomOut,
  Maximize2,
  Move,
} from "lucide-react";
import { useGestio } from "@/lib/gestio-context";
import { apiFetch, getAuthToken, extractTenantId, getApiBaseUrl } from "@/lib/api";

interface Carpeta {
  id: string;
  nom: string;
  categoria: string;
  descripcio?: string;
  municipi?: string;
  created_at?: string;
}

interface Planol {
  id: string;
  carpeta_id: string;
  titol: string;
  codi_referencia: string;
  tipus_fitxer: string;
  es_georeferenciat: boolean;
  fitxer_path?: string;
  mida_bytes?: number;
  carpeta_nom?: string;
  municipi?: string;
  projeccio?: string;
  created_at?: string;
}

interface FeatureGeoJSON {
  type: "Feature";
  geometry: {
    type: "LineString" | "Point";
    coordinates: any;
  };
  properties: {
    id: string;
    nom?: string;
    etiqueta?: string;
    color?: string;
    disciplina?: string;
  };
}

interface CapaVectorialUI {
  id: string;
  planol_base_id?: string;
  nom: string;
  disciplina: string;
  es_immutable: boolean;
  version_id: number;
  color_hex: string;
  gruix_linia: number;
  opacitat_percent: number;
  visible: boolean;
  geometries_geojson: {
    type?: string;
    features?: FeatureGeoJSON[];
    [key: string]: any;
  };
  ordre_treball_id?: string | null;
  created_at?: string;
}

const DISCIPLINES_DEFECTE = [
  { id: "CANONADA_REG", label: "Aigua i Reg", color: "#0284c7" },
  { id: "XARXA_ELECTRICA", label: "Baixa Tensió REBT", color: "#eab308" },
  { id: "OBRA_CIVIL", label: "Obra Civil i Rases", color: "#ea580c" },
  { id: "SANEJAMENT", label: "Sanejament i Drenatge", color: "#10b981" },
  { id: "INCIDENCIA", label: "Anotacions i Incidències", color: "#ef4444" },
];

interface DraggedItem {
  capaId: string;
  featureIndex: number;
  type: "point" | "vertex";
  vertexIndex?: number;
  startX: number;
  startY: number;
  currentX: number;
  currentY: number;
  hasMoved: boolean;
}

export default function GestioPlanolsPage() {
  const { rolActiu } = useGestio();
  const [carpetes, setCarpetes] = useState<Carpeta[]>([]);
  const [planols, setPlanols] = useState<Planol[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [carpetaSeleccionada, setCarpetaSeleccionada] = useState<Carpeta | null>(null);
  const [planolSeleccionat, setPlanolSeleccionat] = useState<Planol | null>(null);
  const [filtreCerca, setFiltreCerca] = useState("");
  const [opacitatPlanimetria, setOpacitatPlanimetria] = useState(85);

  // Zoom & Pan & Arrossegament de punts/icones (FR-015)
  const [zoom, setZoom] = useState<number>(1);
  const [pan, setPan] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [isPanning, setIsPanning] = useState(false);
  const [panStart, setPanStart] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [draggedItem, setDraggedItem] = useState<DraggedItem | null>(null);
  const draggedItemRef = useRef<DraggedItem | null>(null);
  const [justDragged, setJustDragged] = useState(false);
  const innerCanvasRef = useRef<HTMLDivElement>(null);

  // Capes vectorials del plànol seleccionat
  const [capes, setCapes] = useState<CapaVectorialUI[]>([]);
  const [capaActivaId, setCapaActivaId] = useState<string | null>(null);
  const [carregantCapes, setCarregantCapes] = useState(false);
  const [desantCapa, setDesantCapa] = useState(false);
  const [exportantPdf, setExportantPdf] = useState(false);

  // Eines d'edició
  const [einaDibuix, setEinaDibuix] = useState<"punter" | "canonada" | "punt">("punter");
  const [puntsLiniaEnCurs, setPuntsLiniaEnCurs] = useState<Array<{ x: number; y: number }>>([]);
  const canvasRef = useRef<HTMLDivElement>(null);

  // Modals de capes i elements
  const [modalNovaCapa, setModalNovaCapa] = useState(false);
  const [modalNouElement, setModalNouElement] = useState<{ x: number; y: number } | null>(null);
  const [etiquetaElement, setEtiquetaElement] = useState("Vàlvula");
  const [guardantNovaCapa, setGuardantNovaCapa] = useState(false);

  const [novaCapaForm, setNovaCapaForm] = useState({
    nom: "",
    disciplina: "CANONADA_REG",
    color_hex: "#0284c7",
    gruix_linia: 3,
    opacitat_percent: 100,
  });

  // Modals
  const [modalNovaCarpeta, setModalNovaCarpeta] = useState(false);
  const [modalNouPlanol, setModalNouPlanol] = useState(false);
  const [guardant, setGuardant] = useState(false);

  // Fitxers i carpeta d'origen
  const [fitxerPujada, setFitxerPujada] = useState<File | null>(null);
  const [importantDirectori, setImportantDirectori] = useState(false);
  const [missatgeExit, setMissatgeExit] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const multipleFileInputRef = useRef<HTMLInputElement>(null);

  // Formularis
  const [novaCarpeta, setNovaCarpeta] = useState({
    nom: "",
    categoria: "INFRAESTRUCTURA_COMUNITARIA",
    descripcio: "",
    municipi: "",
  });

  const [nouPlanol, setNouPlanol] = useState({
    titol: "",
    codi_referencia: "",
    tipus_fitxer: "DXF",
    es_georeferenciat: true,
    projeccio: "ETRS89 / UTM 31N",
  });

  const capaActiva = capes.find((c) => c.id === capaActivaId);

  const carregarCapesPlanol = async (planolId: string) => {
    setCarregantCapes(true);
    try {
      const data = await apiFetch<CapaVectorialUI[]>(`/gestio/planols/${planolId}/capes`);
      const list = Array.isArray(data) ? data : [];
      setCapes(list);
      if (list.length > 0) {
        setCapaActivaId(list[0].id);
      } else {
        setCapaActivaId(null);
      }
    } catch {
      setCapes([]);
      setCapaActivaId(null);
    } finally {
      setCarregantCapes(false);
    }
  };

  useEffect(() => {
    if (planolSeleccionat?.id) {
      carregarCapesPlanol(planolSeleccionat.id);
    } else {
      setCapes([]);
      setCapaActivaId(null);
    }
    setPuntsLiniaEnCurs([]);
    setZoom(1);
    setPan({ x: 0, y: 0 });
    draggedItemRef.current = null;
    setDraggedItem(null);
    setIsPanning(false);
  }, [planolSeleccionat?.id]);

  const toggleVisibilitatCapa = async (capaId: string) => {
    const target = capes.find((c) => c.id === capaId);
    if (!target || !planolSeleccionat) return;
    const novaVisibilitat = !target.visible;
    setCapes((prev) =>
      prev.map((c) => (c.id === capaId ? { ...c, visible: novaVisibilitat } : c))
    );
    try {
      await apiFetch(`/gestio/planols/${planolSeleccionat.id}/capes/${capaId}`, {
        method: "PUT",
        body: JSON.stringify({ visible: novaVisibilitat }),
      });
    } catch (err: any) {
      console.error("Error canviant visibilitat de la capa:", err);
    }
  };

  const desarCanvisCapa = async (capa: CapaVectorialUI) => {
    if (!planolSeleccionat) return;
    setDesantCapa(true);
    try {
      await apiFetch(`/gestio/planols/${planolSeleccionat.id}/capes/${capa.id}`, {
        method: "PUT",
        body: JSON.stringify({
          nom: capa.nom,
          color_hex: capa.color_hex,
          gruix_linia: capa.gruix_linia,
          opacitat_percent: capa.opacitat_percent,
          visible: capa.visible,
          geometries_geojson: capa.geometries_geojson,
        }),
      });
      setMissatgeExit(`Capa "${capa.nom}" desada. El plànol original roman intacte.`);
      setTimeout(() => setMissatgeExit(null), 3500);
    } catch (err: any) {
      setError("Error desant canvis a la capa: " + (err.message || err));
    } finally {
      setDesantCapa(false);
    }
  };

  const handleCrearCapa = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!planolSeleccionat || !novaCapaForm.nom.trim()) return;
    setGuardantNovaCapa(true);
    setError(null);
    try {
      const creada = await apiFetch<CapaVectorialUI>(
        `/gestio/planols/${planolSeleccionat.id}/capes`,
        {
          method: "POST",
          body: JSON.stringify({
            planol_base_id: planolSeleccionat.id,
            nom: novaCapaForm.nom.trim(),
            disciplina: novaCapaForm.disciplina,
            color_hex: novaCapaForm.color_hex,
            gruix_linia: Number(novaCapaForm.gruix_linia) || 3,
            opacitat_percent: Number(novaCapaForm.opacitat_percent) || 100,
            visible: true,
            geometries_geojson: {
              type: "FeatureCollection",
              features: [],
            },
          }),
        }
      );
      setCapes((prev) => [...prev, creada]);
      setCapaActivaId(creada.id);
      setModalNovaCapa(false);
      setNovaCapaForm({
        nom: "",
        disciplina: "CANONADA_REG",
        color_hex: "#0284c7",
        gruix_linia: 3,
        opacitat_percent: 100,
      });
      setMissatgeExit(`Capa "${creada.nom}" creada! El plànol original roman intacte.`);
      setTimeout(() => setMissatgeExit(null), 4000);
    } catch (err: any) {
      setError("Error creant la capa: " + (err.message || err));
    } finally {
      setGuardantNovaCapa(false);
    }
  };

  const handleEliminarCapa = async (capaId: string) => {
    if (!planolSeleccionat) return;
    const capa = capes.find((c) => c.id === capaId);
    if (!capa) return;
    if (capa.es_immutable) {
      alert("Aquesta capa és immutable i no es pot eliminar.");
      return;
    }
    if (!confirm(`Segur que vols eliminar la capa "${capa.nom}"?`)) return;

    try {
      await apiFetch(`/gestio/planols/${planolSeleccionat.id}/capes/${capaId}`, {
        method: "DELETE",
      });
      const remaining = capes.filter((c) => c.id !== capaId);
      setCapes(remaining);
      if (capaActivaId === capaId) {
        setCapaActivaId(remaining.length > 0 ? remaining[0].id : null);
      }
      setMissatgeExit(`Capa "${capa.nom}" eliminada.`);
      setTimeout(() => setMissatgeExit(null), 3000);
    } catch (err: any) {
      setError("Error eliminant la capa: " + (err.message || err));
    }
  };

  const startDrag = (
    e: React.MouseEvent,
    capaId: string,
    featureIndex: number,
    type: "point" | "vertex",
    initX: number,
    initY: number,
    vertexIndex?: number
  ) => {
    if (einaDibuix !== "punter") return;
    e.stopPropagation();
    e.preventDefault();

    const capa = capes.find((c) => c.id === capaId);
    if (capa?.es_immutable) {
      setError("Aquesta capa és immutable i els seus punts no es poden moure.");
      setTimeout(() => setError(null), 3500);
      return;
    }

    // Cancel·lar qualsevol desplaçament de càmera actiu
    setIsPanning(false);

    // Activar aquesta capa
    setCapaActivaId(capaId);

    const newItem: DraggedItem = {
      capaId,
      featureIndex,
      type,
      vertexIndex,
      startX: initX,
      startY: initY,
      currentX: initX,
      currentY: initY,
      hasMoved: false,
    };
    draggedItemRef.current = newItem;
    setDraggedItem(newItem);
  };

  useEffect(() => {
    const isDragging = !!draggedItem;
    if (!isDragging && !isPanning) return;

    const handleMouseMove = (e: MouseEvent) => {
      const activeDrag = draggedItemRef.current;
      if (activeDrag) {
        if (!innerCanvasRef.current) return;
        const rect = innerCanvasRef.current.getBoundingClientRect();
        const rawX = ((e.clientX - rect.left) / rect.width) * 100;
        const rawY = ((e.clientY - rect.top) / rect.height) * 100;
        const clampedX = Math.round(Math.max(0, Math.min(100, rawX)) * 10) / 10;
        const clampedY = Math.round(Math.max(0, Math.min(100, rawY)) * 10) / 10;

        activeDrag.currentX = clampedX;
        activeDrag.currentY = clampedY;
        activeDrag.hasMoved = true;

        setDraggedItem({ ...activeDrag });

        // Actualització optimista en temps real
        setCapes((prevCapes) =>
          prevCapes.map((c) => {
            if (c.id !== activeDrag.capaId) return c;
            const feats = [...(c.geometries_geojson?.features || [])];
            const targetFeat = feats[activeDrag.featureIndex];
            if (!targetFeat) return c;

            const updatedFeat = { ...targetFeat };
            if (activeDrag.type === "point") {
              updatedFeat.geometry = {
                ...updatedFeat.geometry,
                type: "Point",
                coordinates: [clampedX, clampedY],
              };
            } else if (
              activeDrag.type === "vertex" &&
              typeof activeDrag.vertexIndex === "number"
            ) {
              const coords = [...(updatedFeat.geometry?.coordinates || [])];
              coords[activeDrag.vertexIndex] = [clampedX, clampedY];
              updatedFeat.geometry = {
                ...updatedFeat.geometry,
                type: "LineString",
                coordinates: coords,
              };
            }
            feats[activeDrag.featureIndex] = updatedFeat;
            return {
              ...c,
              geometries_geojson: {
                ...c.geometries_geojson,
                features: feats,
              },
            };
          })
        );
      } else if (isPanning) {
        setPan({
          x: e.clientX - panStart.x,
          y: e.clientY - panStart.y,
        });
      }
    };

    const handleMouseUp = () => {
      const activeDrag = draggedItemRef.current;
      if (activeDrag) {
        if (activeDrag.hasMoved) {
          setJustDragged(true);
          setTimeout(() => setJustDragged(false), 200);

          setCapes((currentCapes) => {
            const updatedCapa = currentCapes.find((c) => c.id === activeDrag.capaId);
            if (updatedCapa) {
              desarCanvisCapa(updatedCapa);
              setMissatgeExit(
                `${activeDrag.type === "vertex" ? "Vèrtex de traçat" : "Element"} mogut a [X: ${activeDrag.currentX}%, Y: ${activeDrag.currentY}%]`
              );
              setTimeout(() => setMissatgeExit(null), 3000);
            }
            return currentCapes;
          });
        }
        draggedItemRef.current = null;
        setDraggedItem(null);
      }
      if (isPanning) {
        setIsPanning(false);
        setJustDragged(true);
        setTimeout(() => setJustDragged(false), 200);
      }
    };

    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);

    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };
  }, [draggedItem !== null, isPanning, panStart]);

  const handleZoomIn = () => {
    setZoom((z) => Math.min(3.5, Math.round((z + 0.25) * 100) / 100));
  };

  const handleZoomOut = () => {
    setZoom((z) => Math.max(0.5, Math.round((z - 0.25) * 100) / 100));
  };

  const handleResetZoom = () => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  };

  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? -0.15 : 0.15;
    setZoom((prev) => Math.max(0.5, Math.min(3.5, Math.round((prev + delta) * 100) / 100)));
  };

  const handleCanvasClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (einaDibuix === "punter" || justDragged || isPanning) return;
    if (!innerCanvasRef.current) return;

    const rect = innerCanvasRef.current.getBoundingClientRect();
    const rawX = ((e.clientX - rect.left) / rect.width) * 100;
    const rawY = ((e.clientY - rect.top) / rect.height) * 100;
    const x = Math.round(Math.max(0, Math.min(100, rawX)) * 10) / 10;
    const y = Math.round(Math.max(0, Math.min(100, rawY)) * 10) / 10;

    const act = capes.find((c) => c.id === capaActivaId);
    if (!act) {
      alert("Crea o selecciona una capa abans de dibuixar.");
      return;
    }
    if (act.es_immutable) {
      alert("Aquesta capa és immutable i no es pot modificar. Crea una nova capa per afegir anotacions.");
      return;
    }

    if (einaDibuix === "canonada") {
      setPuntsLiniaEnCurs((prev) => [...prev, { x, y }]);
    } else if (einaDibuix === "punt") {
      setModalNouElement({ x, y });
      setEtiquetaElement("Vàlvula");
    }
  };

  const finalitzarLinia = async () => {
    if (puntsLiniaEnCurs.length < 2) {
      setPuntsLiniaEnCurs([]);
      return;
    }
    const act = capes.find((c) => c.id === capaActivaId);
    if (!act || !planolSeleccionat) return;

    const novaFeature: FeatureGeoJSON = {
      type: "Feature",
      geometry: {
        type: "LineString",
        coordinates: puntsLiniaEnCurs.map((p) => [p.x, p.y]),
      },
      properties: {
        id: `line-${Date.now()}`,
        nom: `Traçat ${act.disciplina.toLowerCase()}`,
        color: act.color_hex,
      },
    };

    const featuresActuals = act.geometries_geojson?.features || [];
    const novesFeatures = [...featuresActuals, novaFeature];
    const novaCapaActualitzada = {
      ...act,
      geometries_geojson: {
        ...act.geometries_geojson,
        type: "FeatureCollection",
        features: novesFeatures,
      },
    };

    setCapes((prev) => prev.map((c) => (c.id === act.id ? novaCapaActualitzada : c)));
    setPuntsLiniaEnCurs([]);

    await desarCanvisCapa(novaCapaActualitzada);
  };

  const confirmarNouElement = async () => {
    if (!modalNouElement) return;
    const act = capes.find((c) => c.id === capaActivaId);
    if (!act || !planolSeleccionat) return;

    const novaFeature: FeatureGeoJSON = {
      type: "Feature",
      geometry: {
        type: "Point",
        coordinates: [modalNouElement.x, modalNouElement.y],
      },
      properties: {
        id: `point-${Date.now()}`,
        nom: etiquetaElement.trim() || "Element",
        etiqueta: etiquetaElement.trim() || "Element",
        color: act.color_hex,
      },
    };

    const featuresActuals = act.geometries_geojson?.features || [];
    const novesFeatures = [...featuresActuals, novaFeature];
    const novaCapaActualitzada = {
      ...act,
      geometries_geojson: {
        ...act.geometries_geojson,
        type: "FeatureCollection",
        features: novesFeatures,
      },
    };

    setCapes((prev) => prev.map((c) => (c.id === act.id ? novaCapaActualitzada : c)));
    setModalNouElement(null);
    setEtiquetaElement("");

    await desarCanvisCapa(novaCapaActualitzada);
  };

  const buidarElementsCapaActiva = async () => {
    const act = capes.find((c) => c.id === capaActivaId);
    if (!act || !planolSeleccionat) return;
    if (
      !confirm(
        `Segur que vols buidar tots els traçats de la capa "${act.nom}"? El plànol original romandrà 100% intacte.`
      )
    )
      return;

    const novaCapaActualitzada = {
      ...act,
      geometries_geojson: {
        type: "FeatureCollection",
        features: [],
      },
    };
    setCapes((prev) => prev.map((c) => (c.id === act.id ? novaCapaActualitzada : c)));
    setPuntsLiniaEnCurs([]);
    await desarCanvisCapa(novaCapaActualitzada);
  };

  const handleExportarPdf = async () => {
    if (!planolSeleccionat) return;
    setExportantPdf(true);
    try {
      await apiFetch(`/gestio/planols/${planolSeleccionat.id}/exportar-pdf`, {
        method: "POST",
      });
      setMissatgeExit("Sol·licitud d'exportació PDF amb capes enviada al servei de documents.");
      setTimeout(() => setMissatgeExit(null), 4000);
    } catch (err: any) {
      setError("Error exportant plànol a PDF: " + (err.message || err));
    } finally {
      setExportantPdf(false);
    }
  };

  const carregarDades = async () => {
    setLoading(true);
    setError(null);
    try {
      const [dataCarpetes, dataPlanols] = await Promise.all([
        apiFetch<Carpeta[]>("/gestio/planols/carpetes").catch(() => []),
        apiFetch<Planol[]>("/gestio/planols").catch(() => []),
      ]);
      const cList = dataCarpetes || [];
      const pList = dataPlanols || [];
      setCarpetes(cList);
      setPlanols(pList);
      if (cList.length > 0 && !carpetaSeleccionada) {
        setCarpetaSeleccionada(cList[0]);
        const firstPlan = pList.find((p) => p.carpeta_id === cList[0].id);
        if (firstPlan) setPlanolSeleccionat(firstPlan);
      }
    } catch (err: any) {
      setError(err.message || "Error al carregar els plànols");
      setCarpetes([]);
      setPlanols([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    carregarDades();
  }, []);

  const handleFitxerCanviat = (file: File) => {
    setFitxerPujada(file);
    const lastDot = file.name.lastIndexOf(".");
    const baseName = lastDot > 0 ? file.name.substring(0, lastDot) : file.name;
    const ext = (file.name.split(".").pop() || "").toUpperCase();
    let format = "DXF";
    if (ext === "PDF") format = "PDF";
    else if (ext === "GEOJSON" || ext === "JSON") format = "GEOJSON";
    else if (ext === "KML") format = "KML";
    else if (ext === "DWG") format = "DWG";

    setNouPlanol((prev) => ({
      ...prev,
      titol: prev.titol || baseName.replace(/[_-]/g, " ").trim(),
      codi_referencia: prev.codi_referencia || `PLN-${baseName.substring(0, 10).toUpperCase()}`,
      tipus_fitxer: format,
    }));
  };

  const handleCrearCarpeta = async (e: React.FormEvent) => {
    e.preventDefault();
    setGuardant(true);
    setError(null);
    try {
      const creada = await apiFetch<Carpeta>("/gestio/planols/carpetes", {
        method: "POST",
        body: JSON.stringify(novaCarpeta),
      });
      setModalNovaCarpeta(false);
      setNovaCarpeta({
        nom: "",
        categoria: "INFRAESTRUCTURA_COMUNITARIA",
        descripcio: "",
        municipi: "",
      });
      await carregarDades();
      if (creada) setCarpetaSeleccionada(creada);
    } catch (err: any) {
      setError(err.message || "Error al crear la carpeta");
    } finally {
      setGuardant(false);
    }
  };

  const handlePujarFitxerPlanol = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!carpetaSeleccionada) return;
    setGuardant(true);
    setError(null);
    try {
      if (fitxerPujada) {
        const formData = new FormData();
        formData.append("carpeta_id", carpetaSeleccionada.id);
        formData.append("fitxer", fitxerPujada);
        if (nouPlanol.titol) formData.append("titol", nouPlanol.titol);
        if (nouPlanol.codi_referencia) formData.append("codi_referencia", nouPlanol.codi_referencia);
        if (nouPlanol.tipus_fitxer) formData.append("tipus_fitxer", nouPlanol.tipus_fitxer);
        if (nouPlanol.projeccio) formData.append("projeccio", nouPlanol.projeccio);
        formData.append("es_georeferenciat", String(nouPlanol.es_georeferenciat));

        const baseUrl = getApiBaseUrl();
        const token = getAuthToken();
        const tenantId = extractTenantId();

        const res = await fetch(`${baseUrl}/gestio/planols/upload`, {
          method: "POST",
          headers: {
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
            ...(tenantId ? { "X-Empresa-ID": tenantId } : {}),
          },
          body: formData,
        });

        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail || "Error en pujar el fitxer");
        }
        const creat = await res.json();
        setMissatgeExit(`Plànol "${creat.titol}" carregat correctament!`);
        setTimeout(() => setMissatgeExit(null), 4000);
        await carregarDades();
        if (creat) setPlanolSeleccionat(creat);
      } else {
        const creat = await apiFetch<Planol>("/gestio/planols", {
          method: "POST",
          body: JSON.stringify({
            ...nouPlanol,
            carpeta_id: carpetaSeleccionada.id,
          }),
        });
        await carregarDades();
        if (creat) setPlanolSeleccionat(creat);
      }

      setModalNouPlanol(false);
      setFitxerPujada(null);
      setNouPlanol({
        titol: "",
        codi_referencia: "",
        tipus_fitxer: "DXF",
        es_georeferenciat: true,
        projeccio: "ETRS89 / UTM 31N",
      });
    } catch (err: any) {
      setError(err.message || "Error al registrar el plànol");
    } finally {
      setGuardant(false);
    }
  };

  const handleImportarDirectori = async () => {
    if (!carpetaSeleccionada) return;
    setImportantDirectori(true);
    setError(null);
    try {
      const importats = await apiFetch<Planol[]>("/gestio/planols/importar-directori", {
        method: "POST",
        body: JSON.stringify({
          carpeta_id: carpetaSeleccionada.id,
        }),
      });
      await carregarDades();
      const count = Array.isArray(importats) ? importats.length : 0;
      setMissatgeExit(
        count > 0
          ? `S'han carregat ${count} plànols des de la carpeta d'origen correctament!`
          : "S'ha escanejat la carpeta d'origen (cap plànol nou trobat o ja estaven registrats)."
      );
      setTimeout(() => setMissatgeExit(null), 5000);
    } catch (err: any) {
      setError(err.message || "Error important plànols des de la carpeta d'origen");
    } finally {
      setImportantDirectori(false);
    }
  };

  const handleSeleccioMultipleFitxers = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0 || !carpetaSeleccionada) return;
    setGuardant(true);
    setError(null);
    const baseUrl = getApiBaseUrl();
    const token = getAuthToken();
    const tenantId = extractTenantId();
    let count = 0;
    try {
      for (let i = 0; i < files.length; i++) {
        const file = files[i];
        const formData = new FormData();
        formData.append("carpeta_id", carpetaSeleccionada.id);
        formData.append("fitxer", file);
        const res = await fetch(`${baseUrl}/gestio/planols/upload`, {
          method: "POST",
          headers: {
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
            ...(tenantId ? { "X-Empresa-ID": tenantId } : {}),
          },
          body: formData,
        });
        if (res.ok) count++;
      }
      await carregarDades();
      setMissatgeExit(`S'han pujat ${count} plànols des de la carpeta d'origen!`);
      setTimeout(() => setMissatgeExit(null), 4000);
    } catch (err: any) {
      setError("Error carregant fitxers: " + err.message);
    } finally {
      setGuardant(false);
      if (multipleFileInputRef.current) multipleFileInputRef.current.value = "";
    }
  };

  const planolsFiltrats = planols.filter((p) => {
    const coincideixCarpeta = carpetaSeleccionada ? p.carpeta_id === carpetaSeleccionada.id : true;
    const coincideixCerca =
      p.titol.toLowerCase().includes(filtreCerca.toLowerCase()) ||
      p.codi_referencia.toLowerCase().includes(filtreCerca.toLowerCase());
    return coincideixCarpeta && coincideixCerca;
  });

  const municipisUnics = Array.from(
    new Set(carpetes.map((c) => c.municipi).filter(Boolean))
  ) as string[];

  return (
    <div className="flex flex-col w-full space-y-md">
      {missatgeExit && (
        <div className="p-md rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-800 dark:text-emerald-300 text-xs flex items-center justify-between animate-in fade-in">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
            <span className="font-bold">{missatgeExit}</span>
          </div>
          <button onClick={() => setMissatgeExit(null)} className="p-1 hover:opacity-80">
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {error && (
        <div className="p-md rounded-xl bg-error-container/40 border border-error/30 text-on-error-container text-xs flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-error" />
            <span>{error}</span>
          </div>
          <button onClick={() => setError(null)} className="p-1 hover:opacity-80">
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* Stitch Biblioteca de Plànols Main Workspace (screen_2c6aff2cd6d044e39d0f2e419d9c9011) */}
      <div className="flex flex-col lg:flex-row h-[calc(100vh-170px)] min-h-[620px] gap-lg overflow-hidden">
        {/* Left Sidebar: Tree Navigation & Search (w-[380px]) */}
        <div className="w-full lg:w-[380px] flex flex-col bg-surface-container-low rounded-xl shadow-sm border border-outline-variant/30 overflow-hidden shrink-0">
          <div className="p-md space-y-md border-b border-outline-variant/30 bg-surface-container-highest/20">
            <div className="flex items-center justify-between">
              <h1 className="font-section-title text-section-title text-primary">
                Biblioteca de Plànols
              </h1>
              <div className="flex items-center gap-xs">
                <button
                  onClick={carregarDades}
                  disabled={loading}
                  className="p-xs hover:bg-surface-container-high rounded-lg text-on-surface-variant transition-colors"
                  title="Refrescar"
                >
                  <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
                </button>
                <button
                  onClick={() => setModalNovaCarpeta(true)}
                  className="px-sm py-xs bg-primary text-on-primary rounded-lg text-xs font-body-strong flex items-center gap-1 hover:bg-primary-container transition-colors"
                >
                  <FolderPlus className="w-3.5 h-3.5" />
                  <span>Nova Carpeta</span>
                </button>
              </div>
            </div>

            <div className="flex items-center bg-surface-container-lowest px-md py-sm rounded-lg border border-outline-variant focus-within:border-primary transition-all group shadow-sm">
              <span className="material-symbols-outlined text-outline group-focus-within:text-primary text-[20px]">
                search
              </span>
              <input
                type="text"
                value={filtreCerca}
                onChange={(e) => setFiltreCerca(e.target.value)}
                placeholder="Cerca per nom, client o codi..."
                className="bg-transparent border-none outline-none ml-sm w-full text-body-base text-on-surface"
              />
            </div>
          </div>

          <div className="flex-1 overflow-y-auto p-md space-y-lg custom-scrollbar">
            {/* Project / Folder Tree */}
            <section>
              <div className="flex items-center gap-sm mb-sm text-primary">
                <span className="material-symbols-outlined text-[20px]">folder_Special</span>
                <span className="font-label-caps text-label-caps tracking-widest uppercase">
                  PER CARPETA DE PROJECTE
                </span>
              </div>

              {loading && carpetes.length === 0 ? (
                <div className="p-6 text-center text-outline text-xs flex flex-col items-center gap-2">
                  <RefreshCw className="w-4 h-4 animate-spin text-primary" />
                  <span>Carregant carpetes...</span>
                </div>
              ) : carpetes.length === 0 ? (
                <div className="p-6 text-center text-outline text-xs space-y-2 bg-surface-container-lowest rounded-xl border border-dashed border-outline-variant">
                  <Folder className="w-8 h-8 text-outline mx-auto" />
                  <p className="font-body-strong text-on-surface">Sense carpetes</p>
                  <p className="text-[10px] text-on-surface-variant">Estat Dia-0</p>
                  <button
                    onClick={() => setModalNovaCarpeta(true)}
                    className="mt-1 px-3 py-1.5 bg-primary hover:bg-primary-container text-white rounded-lg text-xs font-bold"
                  >
                    + Crear Carpeta
                  </button>
                </div>
              ) : (
                <div className="space-y-1">
                  {carpetes.map((c) => {
                    const isSelected = carpetaSeleccionada?.id === c.id;
                    const planolsCarpeta = planols.filter((p) => p.carpeta_id === c.id);
                    return (
                      <div key={c.id} className="rounded-lg overflow-hidden">
                        <div
                          onClick={() => {
                            setCarpetaSeleccionada(c);
                            if (planolsCarpeta.length > 0) {
                              setPlanolSeleccionat(planolsCarpeta[0]);
                            } else {
                              setPlanolSeleccionat(null);
                            }
                          }}
                          className={`flex items-center justify-between p-sm rounded-lg cursor-pointer transition-colors ${
                            isSelected
                              ? "bg-primary-container/15 text-primary font-body-strong"
                              : "hover:bg-surface-container-high text-on-surface"
                          }`}
                        >
                          <div className="flex items-center gap-sm min-w-0">
                            <span
                              className={`material-symbols-outlined text-[18px] transition-transform ${
                                isSelected ? "rotate-90 text-primary" : "text-outline"
                              }`}
                            >
                              chevron_right
                            </span>
                            <span className="truncate text-sm">{c.nom}</span>
                          </div>
                          <span className="text-data-tabular bg-surface-container-highest px-2 py-0.5 rounded-full text-xs">
                            {planolsCarpeta.length}
                          </span>
                        </div>

                        {isSelected && planolsCarpeta.length > 0 && (
                          <div className="ml-xl mt-1 space-y-1 border-l border-outline-variant/60 pl-3 py-1">
                            {planolsCarpeta.map((pl) => (
                              <div
                                key={pl.id}
                                onClick={() => setPlanolSeleccionat(pl)}
                                className={`p-xs text-xs rounded cursor-pointer transition-colors truncate ${
                                  planolSeleccionat?.id === pl.id
                                    ? "text-primary font-body-strong bg-primary/10 border-l-2 border-primary pl-2"
                                    : "text-on-surface-variant hover:text-on-surface"
                                }`}
                              >
                                {pl.titol} ({pl.codi_referencia})
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </section>

            {/* Municipality Tree (Dynamic from real carpetes) */}
            {municipisUnics.length > 0 && (
              <section>
                <div className="flex items-center gap-sm mb-sm text-outline">
                  <span className="material-symbols-outlined text-[20px]">map</span>
                  <span className="font-label-caps text-label-caps tracking-widest uppercase">
                    PER MUNICIPI
                  </span>
                </div>
                <div className="space-y-1">
                  {municipisUnics.map((mun) => (
                    <div
                      key={mun}
                      onClick={() => {
                        const found = carpetes.find((c) => c.municipi === mun);
                        if (found) setCarpetaSeleccionada(found);
                      }}
                      className="flex items-center justify-between p-sm hover:bg-surface-container-high rounded-lg cursor-pointer text-on-surface-variant transition-colors"
                    >
                      <div className="flex items-center gap-sm">
                        <span className="material-symbols-outlined text-outline text-[18px]">
                          location_city
                        </span>
                        <span className="font-body-base text-sm">{mun}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            )}
          </div>
        </div>

        {/* Right Panel: Selected Plan Viewer & Table */}
        <div className="flex-1 flex flex-col bg-surface-container-lowest rounded-xl shadow-xl border border-outline-variant/30 relative overflow-hidden">
          {/* Top Bar */}
          <div className="p-md flex flex-wrap items-center justify-between gap-md border-b border-outline-variant/20">
            <div className="flex flex-col">
              <div className="flex items-center gap-sm">
                <span className="material-symbols-outlined text-primary">description</span>
                <h2 className="font-section-title text-section-title text-primary">
                  {planolSeleccionat?.titol ||
                    carpetaSeleccionada?.nom ||
                    "Plànols & Xarxes Vectorials GIS"}
                </h2>
              </div>
              <div className="flex items-center gap-md mt-xs">
                {planolSeleccionat && (
                  <span className="text-data-tabular bg-secondary-container/20 text-on-secondary-container px-2 py-0.5 rounded font-body-strong">
                    {planolSeleccionat.tipus_fitxer} · {planolSeleccionat.codi_referencia}
                  </span>
                )}
                <span className="text-data-tabular text-on-surface-variant">
                  {planolSeleccionat?.projeccio ||
                    (carpetaSeleccionada?.municipi
                      ? `Municipi: ${carpetaSeleccionada.municipi}`
                      : "Projecció ETRS89 / UTM 31N")}
                </span>
              </div>
            </div>

            <div className="flex items-center gap-sm flex-wrap">
              {/* Input amagat per a selecció múltiple de fitxers d'origen */}
              <input
                type="file"
                ref={multipleFileInputRef}
                onChange={handleSeleccioMultipleFitxers}
                multiple
                accept=".pdf,.dxf,.dwg,.geojson,.json,.kml,.png,.jpg,.jpeg"
                className="hidden"
              />

              {planolSeleccionat?.id && (
                <a
                  href={`${getApiBaseUrl()}/gestio/planols/${planolSeleccionat.id}/fitxer`}
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-outline-variant bg-surface-container-low text-on-surface hover:bg-surface-container text-xs font-semibold transition-colors"
                  title="Obrir fitxer de plànol en pestanya nova"
                >
                  <ExternalLink className="w-3.5 h-3.5 text-primary" />
                  <span>Obrir Fitxer</span>
                </a>
              )}

              {/* Botó Carregar de Carpeta d'Origen */}
              <button
                type="button"
                onClick={() => multipleFileInputRef.current?.click()}
                disabled={!carpetaSeleccionada || guardant}
                className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-primary/30 bg-primary/5 hover:bg-primary/10 text-primary text-xs font-bold transition-all disabled:opacity-50"
                title="Selecciona fitxers de la teva carpeta d'origen per carregar-los"
              >
                <UploadCloud className="w-3.5 h-3.5" />
                <span>Carregar Carpeta d&apos;Origen</span>
              </button>

              {/* Botó Escaneig de documents de Sevalor */}
              <button
                type="button"
                onClick={handleImportarDirectori}
                disabled={!carpetaSeleccionada || importantDirectori}
                className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-outline-variant bg-surface-container-low hover:bg-surface-container text-on-surface-variant hover:text-on-surface text-xs font-medium transition-all disabled:opacity-50"
                title="Sincronitza els documents locals del disc de Sevalor"
              >
                <RefreshCw
                  className={`w-3.5 h-3.5 ${importantDirectori ? "animate-spin text-primary" : ""}`}
                />
                <span>{importantDirectori ? "Escanejant..." : "Sincronitzar Disc"}</span>
              </button>

              <button
                onClick={() => {
                  setFitxerPujada(null);
                  setModalNouPlanol(true);
                }}
                disabled={!carpetaSeleccionada}
                className="flex items-center gap-sm px-md py-sm bg-primary text-on-primary rounded-lg font-body-strong text-xs hover:bg-primary-container transition-all disabled:opacity-50 shadow-sm"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Pujar Plànol</span>
              </button>
            </div>
          </div>

          {/* Main Workspace Area */}
          {!carpetaSeleccionada ? (
            <div className="flex-1 flex flex-col items-center justify-center p-12 text-center text-outline">
              <Folder className="w-12 h-12 stroke-[1.5] text-outline/50 mb-2" />
              <p className="text-sm font-medium">Selecciona una carpeta de l&apos;arbre lateral</p>
            </div>
          ) : planolsFiltrats.length === 0 ? (
            <div className="flex-1 flex flex-col items-center justify-center p-12 text-center m-lg bg-surface-container-low/50 rounded-2xl border border-dashed border-outline-variant space-y-3">
              <FileText className="w-10 h-10 text-outline mb-1" />
              <div>
                <h3 className="text-base font-bold text-on-surface">La carpeta està buida</h3>
                <p className="text-xs text-on-surface-variant max-w-sm mt-1">
                  Carrega els plànols des de la teva carpeta d&apos;origen (.pdf, .dxf, .dwg, .geojson) per associar-los a aquest projecte.
                </p>
              </div>
              <div className="flex items-center gap-2 flex-wrap justify-center pt-2">
                <button
                  type="button"
                  onClick={() => multipleFileInputRef.current?.click()}
                  className="px-4 py-2 rounded-lg bg-primary hover:bg-primary-container text-white text-xs font-bold shadow flex items-center gap-1.5"
                >
                  <UploadCloud className="w-4 h-4" />
                  <span>Carregar des de Carpeta d&apos;Origen</span>
                </button>
                <button
                  type="button"
                  onClick={handleImportarDirectori}
                  disabled={importantDirectori}
                  className="px-4 py-2 rounded-lg border border-outline-variant bg-surface-container-lowest hover:bg-surface-container text-on-surface text-xs font-semibold flex items-center gap-1.5"
                >
                  <RefreshCw
                    className={`w-3.5 h-3.5 ${importantDirectori ? "animate-spin text-primary" : ""}`}
                  />
                  <span>Sincronitzar Documents Locals</span>
                </button>
                <button
                  onClick={() => {
                    setFitxerPujada(null);
                    setModalNouPlanol(true);
                  }}
                  className="px-4 py-2 rounded-lg border border-outline-variant hover:bg-surface-container text-on-surface-variant text-xs font-medium"
                >
                  + Formulari Manual
                </button>
              </div>
            </div>
          ) : (
            <div className="flex-1 relative bg-surface-dim flex flex-col justify-between overflow-y-auto">
              {/* Top Interactive Blueprint Canvas + Floating Technical Layer Studio (FR-015) */}
              <div className="p-md flex flex-col xl:flex-row gap-md min-h-[560px]">
                {/* Left Side: Drawing Tools Toolbar + Canvas Viewport */}
                <div className="flex-1 flex flex-col space-y-sm min-w-0">
                  {/* Toolbar Bar */}
                  <div className="p-sm bg-surface-container-lowest rounded-xl border border-outline-variant/30 flex flex-wrap items-center justify-between gap-2 shadow-sm">
                    {/* Plan Reference & Non-Destructive Shield */}
                    <div className="flex items-center gap-2">
                      <span className="font-body-strong text-xs text-on-surface truncate max-w-[200px]">
                        {planolSeleccionat?.titol || "Plànol Actiu"}
                      </span>
                      <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-surface-container-high text-on-surface-variant">
                        {planolSeleccionat?.codi_referencia}
                      </span>
                      <div className="flex items-center gap-1 text-[11px] font-bold text-emerald-700 dark:text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-500/20">
                        <ShieldCheck className="w-3.5 h-3.5" />
                        <span>Base Immutable (No Destructiu)</span>
                      </div>
                    </div>

                    {/* Tools Selector */}
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <div className="flex items-center bg-surface-container-low p-1 rounded-lg border border-outline-variant/30">
                        <button
                          type="button"
                          onClick={() => {
                            setEinaDibuix("punter");
                            setPuntsLiniaEnCurs([]);
                          }}
                          className={`flex items-center gap-1 px-2.5 py-1 rounded text-xs font-semibold transition-all ${
                            einaDibuix === "punter"
                              ? "bg-primary text-white shadow-xs"
                              : "text-on-surface-variant hover:text-on-surface"
                          }`}
                          title="Mode Navegació i Inspecció"
                        >
                          <MousePointer className="w-3.5 h-3.5" />
                          <span>Punter</span>
                        </button>

                        <button
                          type="button"
                          onClick={() => {
                            if (!capaActiva) {
                              alert("Crea o selecciona una capa abans de començar a traçar.");
                              return;
                            }
                            setEinaDibuix("canonada");
                          }}
                          className={`flex items-center gap-1 px-2.5 py-1 rounded text-xs font-semibold transition-all ${
                            einaDibuix === "canonada"
                              ? "bg-primary text-white shadow-xs"
                              : "text-on-surface-variant hover:text-on-surface"
                          }`}
                          title="Dibuixar Canonada o Cablejat (Polilínia)"
                        >
                          <Activity className="w-3.5 h-3.5" />
                          <span>Traçar Xarxa</span>
                        </button>

                        <button
                          type="button"
                          onClick={() => {
                            if (!capaActiva) {
                              alert("Crea o selecciona una capa abans d'afegir elements.");
                              return;
                            }
                            setEinaDibuix("punt");
                            setPuntsLiniaEnCurs([]);
                          }}
                          className={`flex items-center gap-1 px-2.5 py-1 rounded text-xs font-semibold transition-all ${
                            einaDibuix === "punt"
                              ? "bg-primary text-white shadow-xs"
                              : "text-on-surface-variant hover:text-on-surface"
                          }`}
                          title="Afegir Vàlvula, Escomesa o Element Puntual"
                        >
                          <MapPin className="w-3.5 h-3.5" />
                          <span>Afegir Element</span>
                        </button>
                      </div>

                      {/* Controls while drawing a polyline */}
                      {puntsLiniaEnCurs.length > 0 && (
                        <div className="flex items-center gap-1">
                          <span className="text-[11px] font-mono px-2 py-1 rounded bg-amber-500/10 text-amber-700 dark:text-amber-400 font-bold border border-amber-500/20">
                            {puntsLiniaEnCurs.length} vèrtexs
                          </span>
                          <button
                            type="button"
                            onClick={finalitzarLinia}
                            disabled={puntsLiniaEnCurs.length < 2}
                            className="flex items-center gap-1 px-2.5 py-1 rounded bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold transition-all disabled:opacity-50"
                          >
                            <Check className="w-3.5 h-3.5" />
                            <span>Desar Traçat</span>
                          </button>
                          <button
                            type="button"
                            onClick={() => setPuntsLiniaEnCurs([])}
                            className="p-1 rounded hover:bg-surface-container text-outline hover:text-on-surface"
                            title="Cancel·lar traçat en curs"
                          >
                            <X className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      )}

                      {/* Clean active layer */}
                      {capaActiva &&
                        (capaActiva.geometries_geojson?.features?.length || 0) > 0 &&
                        !capaActiva.es_immutable && (
                          <button
                            type="button"
                            onClick={buidarElementsCapaActiva}
                            className="flex items-center gap-1 px-2 py-1 rounded text-[11px] font-medium text-error hover:bg-error-container/20 border border-error/20 transition-all"
                            title="Buidar traçats d'aquesta capa"
                          >
                            <RotateCcw className="w-3 h-3" />
                            <span>Buidar Capa</span>
                          </button>
                        )}

                      {/* Status saving layer */}
                      {desantCapa && (
                        <div className="flex items-center gap-1 text-[11px] text-primary font-bold animate-pulse">
                          <RefreshCw className="w-3 h-3 animate-spin" />
                          <span>Desant...</span>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Canvas Viewport */}
                  <div
                    ref={canvasRef}
                    onWheel={handleWheel}
                    onMouseDown={(e) => {
                      if (einaDibuix === "punter" && e.button === 0 && !draggedItemRef.current) {
                        setIsPanning(true);
                        setPanStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
                      }
                    }}
                    onClick={handleCanvasClick}
                    className={`relative flex-1 min-h-[460px] rounded-xl overflow-hidden border border-outline-variant/40 bg-[#09131d] shadow-inner select-none ${
                      isPanning
                        ? "cursor-grabbing"
                        : einaDibuix === "punter"
                        ? "cursor-grab"
                        : "cursor-crosshair"
                    }`}
                  >
                    {/* Floating Zoom & Pan Controls (FR-015) */}
                    <div className="absolute top-3 right-3 z-30 flex items-center gap-1 p-1 rounded-xl bg-surface-container-lowest/90 backdrop-blur-md border border-outline-variant/40 shadow-xl pointer-events-auto">
                      <button
                        type="button"
                        onClick={handleZoomOut}
                        className="w-7 h-7 rounded-lg hover:bg-surface-container text-on-surface flex items-center justify-center font-bold text-xs transition-colors"
                        title="Reduir Zoom (-)"
                      >
                        <ZoomOut className="w-3.5 h-3.5" />
                      </button>
                      <button
                        type="button"
                        onClick={handleResetZoom}
                        className="px-2 py-0.5 rounded-lg hover:bg-surface-container text-primary font-mono text-xs font-bold transition-colors"
                        title="Restablir Zoom (100%)"
                      >
                        {Math.round(zoom * 100)}%
                      </button>
                      <button
                        type="button"
                        onClick={handleZoomIn}
                        className="w-7 h-7 rounded-lg hover:bg-surface-container text-on-surface flex items-center justify-center font-bold text-xs transition-colors"
                        title="Augmentar Zoom (+)"
                      >
                        <ZoomIn className="w-3.5 h-3.5" />
                      </button>
                      <div className="w-px h-3.5 bg-outline-variant/40 mx-0.5" />
                      <button
                        type="button"
                        onClick={handleResetZoom}
                        className="w-7 h-7 rounded-lg hover:bg-surface-container text-on-surface-variant hover:text-on-surface flex items-center justify-center transition-colors"
                        title="Centrar i ajustar plànol (Fit)"
                      >
                        <Maximize2 className="w-3.5 h-3.5" />
                      </button>
                    </div>

                    {/* Floating Pan & Scale Badge */}
                    {(zoom !== 1 || pan.x !== 0 || pan.y !== 0) && (
                      <div className="absolute top-3 left-3 z-30 flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-surface-container-lowest/90 backdrop-blur-md border border-outline-variant/40 text-[10px] font-mono text-primary shadow pointer-events-auto">
                        <Move className="w-3 h-3 text-secondary" />
                        <span>
                          Zoom {Math.round(zoom * 100)}% · Pan [{Math.round(pan.x)}, {Math.round(pan.y)}px]
                        </span>
                        <button
                          type="button"
                          onClick={handleResetZoom}
                          className="ml-1 text-on-surface-variant hover:text-primary underline font-bold"
                        >
                          Centrar
                        </button>
                      </div>
                    )}

                    {/* Scaled and Panned Container */}
                    <div
                      ref={innerCanvasRef}
                      style={{
                        transform: `scale(${zoom}) translate(${pan.x / zoom}px, ${pan.y / zoom}px)`,
                        transformOrigin: "center center",
                        transition: isPanning || draggedItem ? "none" : "transform 0.15s ease-out",
                      }}
                      className="w-full h-full relative"
                    >
                      {/* Immutable Base Blueprint Layer */}
                      <div
                        className="absolute inset-0 w-full h-full pointer-events-none transition-opacity duration-200"
                        style={{ opacity: opacitatPlanimetria / 100 }}
                      >
                        {/* Technical CAD Grid Background */}
                        <div
                          className="absolute inset-0 w-full h-full opacity-25"
                          style={{
                            backgroundImage:
                              "radial-gradient(circle, #38bdf8 1px, transparent 1px), linear-gradient(to right, #0369a1 1px, transparent 1px), linear-gradient(to bottom, #0369a1 1px, transparent 1px)",
                            backgroundSize: "20px 20px, 100px 100px, 100px 100px",
                          }}
                        />

                        {planolSeleccionat && (
                          <div className="w-full h-full flex items-center justify-center">
                            {planolSeleccionat.tipus_fitxer === "PDF" ? (
                              <object
                                data={`${getApiBaseUrl()}/gestio/planols/${planolSeleccionat.id}/fitxer#toolbar=0&navpanes=0`}
                                type="application/pdf"
                                className="w-full h-full pointer-events-none opacity-90"
                              >
                                <div className="flex flex-col items-center justify-center h-full text-slate-400 text-xs">
                                  <FileText className="w-12 h-12 text-primary/50 mb-2" />
                                  <span>{planolSeleccionat.titol}</span>
                                </div>
                              </object>
                            ) : ["PNG", "JPG", "JPEG", "WEBP"].includes(
                                planolSeleccionat.tipus_fitxer
                              ) ? (
                              <img
                                src={`${getApiBaseUrl()}/gestio/planols/${planolSeleccionat.id}/fitxer`}
                                alt={planolSeleccionat.titol}
                                className="max-w-full max-h-full object-contain pointer-events-none"
                              />
                            ) : (
                              <div className="flex flex-col items-center justify-center p-8 text-center text-slate-300">
                                <div className="p-4 rounded-2xl bg-primary/10 border border-primary/30 mb-3">
                                  <Activity className="w-10 h-10 text-primary animate-pulse" />
                                </div>
                                <h4 className="text-sm font-bold text-white mb-1">
                                  Planimetria Vectorial CAD: {planolSeleccionat.titol}
                                </h4>
                                <p className="text-xs text-slate-400 font-mono">
                                  Ref: {planolSeleccionat.codi_referencia} · Format:{" "}
                                  {planolSeleccionat.tipus_fitxer} · Projecció:{" "}
                                  {planolSeleccionat.projeccio || "ETRS89 UTM 31N"}
                                </p>
                                <p className="text-[11px] text-emerald-400 mt-2 font-mono flex items-center gap-1">
                                  <ShieldCheck className="w-3.5 h-3.5" /> Fitxer base original preservat
                                  intacte (No destructiu)
                                </p>
                              </div>
                            )}
                          </div>
                        )}
                      </div>

                      {/* Vector Layers SVG Overlay */}
                      <svg
                        className="absolute inset-0 w-full h-full pointer-events-none select-none"
                        viewBox="0 0 100 100"
                        preserveAspectRatio="none"
                      >
                        {/* Capes visibles */}
                        {capes
                          .filter((c) => c.visible)
                          .map((capa) => {
                            const features = capa.geometries_geojson?.features || [];
                            return (
                              <g
                                key={capa.id}
                                opacity={(capa.opacitat_percent || 100) / 100}
                              >
                                {features.map((feat, fIdx) => {
                                  if (feat.geometry?.type === "LineString") {
                                    const pts = (feat.geometry.coordinates || [])
                                      .map((coord: number[]) => `${coord[0]},${coord[1]}`)
                                      .join(" ");
                                    return (
                                      <g key={feat.properties?.id || `feat-line-${fIdx}`}>
                                        <polyline
                                          points={pts}
                                          fill="none"
                                          stroke={capa.color_hex}
                                          strokeWidth={
                                            capa.gruix_linia ? capa.gruix_linia * 0.35 : 1.2
                                          }
                                          strokeLinecap="round"
                                          strokeLinejoin="round"
                                        />
                                        {(feat.geometry.coordinates || []).map(
                                          (c: number[], cIdx: number) => {
                                            const isVertexDragged =
                                              draggedItem?.capaId === capa.id &&
                                              draggedItem?.featureIndex === fIdx &&
                                              draggedItem?.type === "vertex" &&
                                              draggedItem?.vertexIndex === cIdx;

                                            return (
                                              <g key={`feat-line-${fIdx}-v-${cIdx}`}>
                                                {/* Anell d'arrossegament actiu en temps real */}
                                                {isVertexDragged && (
                                                  <circle
                                                    cx={c[0]}
                                                    cy={c[1]}
                                                    r={3.8}
                                                    fill="none"
                                                    stroke="#38bdf8"
                                                    strokeWidth="0.8"
                                                    strokeDasharray="1,1"
                                                    className="pointer-events-none animate-pulse"
                                                  />
                                                )}

                                                {/* Cercle visual del vèrtex */}
                                                <circle
                                                  cx={c[0]}
                                                  cy={c[1]}
                                                  r={isVertexDragged ? 2.4 : 1.4}
                                                  fill={isVertexDragged ? "#38bdf8" : "#ffffff"}
                                                  stroke={capa.color_hex}
                                                  strokeWidth={isVertexDragged ? 0.9 : 0.5}
                                                  className="pointer-events-none"
                                                />
                                                <circle
                                                  cx={c[0]}
                                                  cy={c[1]}
                                                  r={0.5}
                                                  fill={isVertexDragged ? "#ffffff" : capa.color_hex}
                                                  className="pointer-events-none"
                                                />

                                                {/* Àrea d'interacció ampliada (Halo invisible per agafar fàcilment) */}
                                                <circle
                                                  cx={c[0]}
                                                  cy={c[1]}
                                                  r={3.8}
                                                  fill="transparent"
                                                  stroke="transparent"
                                                  onMouseDown={(e) => {
                                                    if (einaDibuix === "punter") {
                                                      startDrag(
                                                        e,
                                                        capa.id,
                                                        fIdx,
                                                        "vertex",
                                                        c[0],
                                                        c[1],
                                                        cIdx
                                                      );
                                                    }
                                                  }}
                                                  className={
                                                    einaDibuix === "punter" && !capa.es_immutable
                                                      ? "pointer-events-auto cursor-grab active:cursor-grabbing hover:opacity-100"
                                                      : "pointer-events-none"
                                                  }
                                                />
                                              </g>
                                            );
                                          }
                                        )}
                                      </g>
                                    );
                                  }
                                  if (feat.geometry?.type === "Point") {
                                    const [px, py] = feat.geometry.coordinates || [0, 0];
                                    const nomElement =
                                      feat.properties?.nom ||
                                      feat.properties?.etiqueta ||
                                      "Element";
                                    const isPointDragged =
                                      draggedItem?.capaId === capa.id &&
                                      draggedItem?.featureIndex === fIdx &&
                                      draggedItem?.type === "point";

                                    return (
                                      <g
                                        key={feat.properties?.id || `feat-pt-${fIdx}`}
                                        onMouseDown={(e) => {
                                          if (einaDibuix === "punter") {
                                            startDrag(e, capa.id, fIdx, "point", px, py);
                                          }
                                        }}
                                        className={
                                          einaDibuix === "punter" && !capa.es_immutable
                                            ? "pointer-events-auto cursor-grab hover:opacity-95 active:cursor-grabbing"
                                            : "pointer-events-none"
                                        }
                                      >
                                        {/* Anell d'arrossegament actiu */}
                                        {isPointDragged && (
                                          <circle
                                            cx={px}
                                            cy={py}
                                            r={3.8}
                                            fill="none"
                                            stroke="#38bdf8"
                                            strokeWidth="0.8"
                                            strokeDasharray="1,1"
                                          />
                                        )}
                                        <circle
                                          cx={px}
                                          cy={py}
                                          r={isPointDragged ? 2.6 : 1.9}
                                          fill={capa.color_hex}
                                          stroke="#ffffff"
                                          strokeWidth={isPointDragged ? 0.9 : 0.5}
                                        />
                                        <circle cx={px} cy={py} r={0.6} fill="#ffffff" />
                                        <text
                                          x={px + 2.2}
                                          y={py - 1.2}
                                          fill="#ffffff"
                                          fontSize="2.4"
                                          fontWeight="bold"
                                          filter="drop-shadow(0px 1px 2px rgba(0,0,0,0.95))"
                                          className="select-none pointer-events-none"
                                        >
                                          {nomElement}
                                        </text>
                                      </g>
                                    );
                                  }
                                  return null;
                                })}
                              </g>
                            );
                          })}

                        {/* Dibuix en curs */}
                        {puntsLiniaEnCurs.length > 0 && (
                          <g>
                            <polyline
                              points={puntsLiniaEnCurs.map((p) => `${p.x},${p.y}`).join(" ")}
                              fill="none"
                              stroke={capaActiva?.color_hex || "#38bdf8"}
                              strokeWidth="1.2"
                              strokeDasharray="2,2"
                            />
                            {puntsLiniaEnCurs.map((p, idx) => (
                              <circle
                                key={idx}
                                cx={p.x}
                                cy={p.y}
                                r={1.2}
                                fill="#ffffff"
                                stroke={capaActiva?.color_hex || "#38bdf8"}
                                strokeWidth="0.5"
                              />
                            ))}
                          </g>
                        )}
                      </svg>
                    </div>

                    {/* Canvas Bottom Instruction Banner */}
                    <div className="absolute bottom-2 left-2 right-2 flex items-center justify-between pointer-events-none text-[11px] font-mono">
                      <div className="px-2.5 py-1 rounded-lg bg-black/70 backdrop-blur-md text-white border border-white/10 flex items-center gap-2">
                        {draggedItem ? (
                          <span className="text-sky-300 font-bold flex items-center gap-1.5">
                            <Move className="w-3.5 h-3.5 animate-spin" />
                            <span>
                              Movent {draggedItem.type === "point" ? "icona" : "vèrtex"} a X:{" "}
                              {draggedItem.currentX}% · Y: {draggedItem.currentY}% (Deixa anar per fixar)
                            </span>
                          </span>
                        ) : isPanning ? (
                          <span className="text-sky-300">🖐️ Desplaçant plànol...</span>
                        ) : einaDibuix === "punter" ? (
                          <span>
                            ✋ <b>Punter:</b> Arrossega les icones o vèrtexs per moure&apos;ls. Arrossega el fons per desplaçar el plànol. Roda del ratolí per fer zoom.
                          </span>
                        ) : einaDibuix === "canonada" ? (
                          <span>
                            ✏️ Fes clic per afegir vèrtexs. Clica &quot;Desar Traçat&quot; en acabar.
                          </span>
                        ) : einaDibuix === "punt" ? (
                          <span>📍 Clica al punt exacte per posicionar l&apos;element.</span>
                        ) : null}
                      </div>

                      {capaActiva ? (
                        <div className="px-2.5 py-1 rounded-lg bg-black/70 backdrop-blur-md text-white border border-white/10 flex items-center gap-1.5">
                          <span
                            className="w-2.5 h-2.5 rounded-full inline-block"
                            style={{ backgroundColor: capaActiva.color_hex }}
                          />
                          <span className="font-bold">{capaActiva.nom}</span>
                        </div>
                      ) : (
                        <div className="px-2.5 py-1 rounded-lg bg-black/70 backdrop-blur-md text-amber-300 border border-white/10">
                          Sense capa activa seleccionada
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                {/* Right Side: Technical Layer Studio Panel */}
                <div className="w-full xl:w-80 bg-surface-container-lowest rounded-xl border border-outline-variant/30 p-md flex flex-col space-y-md shadow-sm">
                  {/* Layer Studio Header */}
                  <div className="flex items-center justify-between border-b border-outline-variant/20 pb-sm">
                    <div className="flex items-center gap-1.5">
                      <Layers className="w-4 h-4 text-primary" />
                      <h3 className="font-section-title text-sm text-primary">
                        Estudi de Capes ({capes.length})
                      </h3>
                    </div>
                    <button
                      type="button"
                      onClick={() => setModalNovaCapa(true)}
                      disabled={!planolSeleccionat}
                      className="px-2 py-1 bg-primary text-white rounded-lg text-xs font-bold flex items-center gap-1 hover:bg-primary-container transition-all disabled:opacity-50"
                    >
                      <Plus className="w-3.5 h-3.5" />
                      <span>Nova Capa</span>
                    </button>
                  </div>

                  {/* Opacity Control for Base Blueprint */}
                  <div className="p-sm rounded-lg bg-surface-container-low/60 border border-outline-variant/30 space-y-1">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-semibold text-on-surface">Opacitat Plànol Base</span>
                      <span className="font-mono text-[11px] text-primary font-bold">
                        {opacitatPlanimetria}%
                      </span>
                    </div>
                    <input
                      type="range"
                      min={15}
                      max={100}
                      value={opacitatPlanimetria}
                      onChange={(e) => setOpacitatPlanimetria(Number(e.target.value))}
                      className="w-full h-1.5 bg-surface-container-highest rounded-lg cursor-pointer accent-primary"
                    />
                  </div>

                  {/* Layers List */}
                  <div className="flex-1 overflow-y-auto space-y-2 max-h-[340px] pr-1 custom-scrollbar">
                    {carregantCapes ? (
                      <div className="p-6 text-center text-xs text-outline flex flex-col items-center gap-2">
                        <RefreshCw className="w-4 h-4 animate-spin text-primary" />
                        <span>Carregant capes vectorials...</span>
                      </div>
                    ) : capes.length === 0 ? (
                      <div className="p-5 text-center text-xs text-outline space-y-2 bg-surface-container-low/40 rounded-xl border border-dashed border-outline-variant/60">
                        <Layers className="w-7 h-7 text-outline/60 mx-auto" />
                        <p className="font-bold text-on-surface">Sense capes vectorials</p>
                        <p className="text-[11px] text-on-surface-variant">
                          Crea la primera capa per afegir xarxes o anotacions sense modificar el fitxer base.
                        </p>
                        <button
                          type="button"
                          onClick={() => setModalNovaCapa(true)}
                          disabled={!planolSeleccionat}
                          className="mt-1 px-3 py-1.5 rounded-lg bg-primary text-white text-xs font-bold shadow hover:bg-primary-container disabled:opacity-50"
                        >
                          + Crear Primera Capa
                        </button>
                      </div>
                    ) : (
                      capes.map((capa) => {
                        const isActiva = capa.id === capaActivaId;
                        const numFeatures = capa.geometries_geojson?.features?.length || 0;
                        return (
                          <div
                            key={capa.id}
                            onClick={() => setCapaActivaId(capa.id)}
                            className={`p-2.5 rounded-xl border transition-all cursor-pointer flex items-center justify-between gap-2 ${
                              isActiva
                                ? "bg-primary/5 border-primary shadow-xs ring-1 ring-primary/20"
                                : "bg-surface-container-low/50 hover:bg-surface-container-low border-outline-variant/30"
                            }`}
                          >
                            <div className="flex items-center gap-2 min-w-0">
                              <span
                                className="w-3 h-3 rounded-full shrink-0 shadow-xs"
                                style={{ backgroundColor: capa.color_hex }}
                              />
                              <div className="min-w-0">
                                <div className="flex items-center gap-1.5">
                                  <span className="font-body-strong text-xs text-on-surface truncate">
                                    {capa.nom}
                                  </span>
                                  {capa.es_immutable && (
                                    <span title="Capa tancada / immutable">
                                      <Lock className="w-3 h-3 text-outline shrink-0" />
                                    </span>
                                  )}
                                </div>
                                <div className="flex items-center gap-1.5 text-[10px] text-on-surface-variant">
                                  <span className="uppercase font-semibold text-primary">
                                    {capa.disciplina.replace("_", " ")}
                                  </span>
                                  <span>·</span>
                                  <span>{numFeatures} elements</span>
                                </div>
                              </div>
                            </div>

                            <div
                              className="flex items-center gap-1 shrink-0"
                              onClick={(e) => e.stopPropagation()}
                            >
                              <button
                                type="button"
                                onClick={() => toggleVisibilitatCapa(capa.id)}
                                className="p-1 rounded hover:bg-surface-container text-on-surface-variant hover:text-on-surface transition-colors"
                                title={capa.visible ? "Ocultar capa" : "Mostrar capa"}
                              >
                                {capa.visible ? (
                                  <Eye className="w-3.5 h-3.5 text-primary" />
                                ) : (
                                  <EyeOff className="w-3.5 h-3.5 text-outline" />
                                )}
                              </button>

                              {!capa.es_immutable && (
                                <button
                                  type="button"
                                  onClick={() => handleEliminarCapa(capa.id)}
                                  className="p-1 rounded hover:bg-error-container/30 text-outline hover:text-error transition-colors"
                                  title="Eliminar capa"
                                >
                                  <Trash2 className="w-3.5 h-3.5" />
                                </button>
                              )}
                            </div>
                          </div>
                        );
                      })
                    )}
                  </div>

                  {/* Actions & Non-destructive Spec 015 Guarantee */}
                  <div className="pt-sm border-t border-outline-variant/20 space-y-2">
                    <button
                      type="button"
                      onClick={handleExportarPdf}
                      disabled={exportantPdf || !planolSeleccionat}
                      className="w-full py-2 px-3 rounded-lg bg-surface-container-high hover:bg-surface-container-highest border border-outline-variant text-on-surface text-xs font-bold flex items-center justify-center gap-1.5 transition-all disabled:opacity-50"
                    >
                      {exportantPdf ? (
                        <>
                          <RefreshCw className="w-3.5 h-3.5 animate-spin text-primary" />
                          <span>Exportant PDF...</span>
                        </>
                      ) : (
                        <>
                          <FileDown className="w-3.5 h-3.5 text-primary" />
                          <span>Exportar PDF amb Capes</span>
                        </>
                      )}
                    </button>

                    <div className="p-2.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-[11px] text-emerald-800 dark:text-emerald-300 flex items-start gap-2">
                      <ShieldCheck className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                      <div className="leading-tight">
                        <span className="font-bold block">Garantia No Destructiva (FR-015)</span>
                        <span className="text-[10px] text-emerald-700 dark:text-emerald-400">
                          El fitxer original es manté inalterat. Les edicions es desen en capes
                          vectorials independents.
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Bottom Drawer: Taula de Plànols de la Carpeta */}
              <div className="m-md bg-surface/95 backdrop-blur-md p-md rounded-xl shadow-2xl border border-outline-variant/30">
                <div className="flex items-center justify-between mb-sm">
                  <span className="font-label-caps text-on-surface-variant uppercase">
                    Documents i Capes Registrades a la Carpeta ({planolsFiltrats.length})
                  </span>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs border-collapse">
                    <thead>
                      <tr className="bg-surface-container-high/60 border-b border-outline-variant/30 font-label-caps text-on-surface-variant uppercase">
                        <th className="p-2.5">Ref. Plànol</th>
                        <th className="p-2.5">Títol del Document</th>
                        <th className="p-2.5">Format</th>
                        <th className="p-2.5">Georeferenciat</th>
                        <th className="p-2.5">Projecció Cartogràfica</th>
                        <th className="p-2.5 text-right">Accions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-outline-variant/20">
                      {planolsFiltrats.map((p) => (
                        <tr
                          key={p.id}
                          onClick={() => setPlanolSeleccionat(p)}
                          className={`hover:bg-surface-container-low cursor-pointer transition-colors ${
                            planolSeleccionat?.id === p.id ? "bg-primary/5" : ""
                          }`}
                        >
                          <td className="p-2.5 font-data-tabular font-bold text-primary">
                            {p.codi_referencia}
                          </td>
                          <td className="p-2.5 font-body-strong text-on-surface">{p.titol}</td>
                          <td className="p-2.5 font-data-tabular text-[10px] font-bold">
                            <span className="px-1.5 py-0.5 rounded bg-surface-container-high text-on-surface">
                              {p.tipus_fitxer}
                            </span>
                          </td>
                          <td className="p-2.5">
                            <span
                              className={`px-2 py-0.5 rounded-full text-[9px] font-bold ${
                                p.es_georeferenciat
                                    ? "bg-green-100 text-green-800"
                                  : "bg-surface-container text-on-surface-variant"
                              }`}
                            >
                              {p.es_georeferenciat ? "ETRS89 WGS84" : "Esquemàtic"}
                            </span>
                          </td>
                          <td className="p-2.5 font-data-tabular text-on-surface-variant text-[11px]">
                            {p.projeccio || "—"}
                          </td>
                          <td className="p-2.5 text-right">
                            <a
                              href={`${getApiBaseUrl()}/gestio/planols/${p.id}/fitxer`}
                              target="_blank"
                              rel="noreferrer"
                              onClick={(e) => e.stopPropagation()}
                              className="inline-flex items-center gap-1 text-[11px] font-bold text-primary hover:underline"
                            >
                              <ExternalLink className="w-3 h-3" />
                              <span>Obrir</span>
                            </a>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Modal Nova Carpeta */}
      {modalNovaCarpeta && (
        <div className="fixed inset-0 z-50 bg-primary/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-md bg-surface-container-lowest rounded-2xl shadow-2xl border border-outline-variant/40 overflow-hidden">
            <div className="p-5 border-b border-surface-container flex items-center justify-between">
              <h3 className="font-section-title text-base text-primary flex items-center gap-2">
                <FolderPlus className="w-4 h-4 text-secondary" />
                Nova Carpeta Cartogràfica
              </h3>
              <button
                onClick={() => setModalNovaCarpeta(false)}
                className="p-1 rounded-lg text-outline hover:text-on-surface"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleCrearCarpeta} className="p-5 space-y-4">
              <div>
                <label className="block font-label-caps text-on-surface-variant uppercase mb-1">
                  Nom de la Carpeta *
                </label>
                <input
                  type="text"
                  required
                  placeholder="Nom de la carpeta"
                  value={novaCarpeta.nom}
                  onChange={(e) => setNovaCarpeta({ ...novaCarpeta, nom: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg border border-outline-variant bg-surface-container-low text-xs font-medium focus:border-primary outline-none"
                />
              </div>

              <div>
                <label className="block font-label-caps text-on-surface-variant uppercase mb-1">
                  Municipi / Terme
                </label>
                <input
                  type="text"
                  placeholder="Ex: Arbeca"
                  value={novaCarpeta.municipi}
                  onChange={(e) => setNovaCarpeta({ ...novaCarpeta, municipi: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg border border-outline-variant bg-surface-container-low text-xs focus:border-primary outline-none"
                />
              </div>

              <div className="pt-3 border-t border-surface-container flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setModalNovaCarpeta(false)}
                  className="px-4 py-2 rounded-lg border border-outline-variant text-on-surface-variant text-xs font-medium"
                >
                  Cancel·lar
                </button>
                <button
                  type="submit"
                  disabled={guardant || !novaCarpeta.nom.trim()}
                  className="px-4 py-2 rounded-lg bg-primary hover:bg-primary-container text-white text-xs font-bold shadow disabled:opacity-50"
                >
                  {guardant ? "Desant..." : "Crear Carpeta"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal Nou Plànol */}
      {modalNouPlanol && (
        <div className="fixed inset-0 z-50 bg-primary/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-md bg-surface-container-lowest rounded-2xl shadow-2xl border border-outline-variant/40 overflow-hidden">
            <div className="p-5 border-b border-surface-container flex items-center justify-between">
              <h3 className="font-section-title text-base text-primary flex items-center gap-2">
                <Plus className="w-4 h-4 text-secondary" />
                Alta de Plànol Tècnic
              </h3>
              <button
                onClick={() => setModalNouPlanol(false)}
                className="p-1 rounded-lg text-outline hover:text-on-surface"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handlePujarFitxerPlanol} className="p-5 space-y-4">
              {/* Dropzone Selector de Fitxer de la Carpeta d'Origen */}
              <div>
                <label className="block font-label-caps text-on-surface-variant uppercase mb-1">
                  Fitxer Cartogràfic (Des de Carpeta d&apos;Origen)
                </label>
                <div
                  onClick={() => fileInputRef.current?.click()}
                  className={`p-4 rounded-xl border-2 border-dashed transition-all cursor-pointer text-center ${
                    fitxerPujada
                      ? "border-emerald-500/60 bg-emerald-500/5 text-emerald-800 dark:text-emerald-300"
                      : "border-outline-variant hover:border-primary/60 bg-surface-container-low"
                  }`}
                >
                  <input
                    type="file"
                    ref={fileInputRef}
                    onChange={(e) => {
                      const f = e.target.files?.[0];
                      if (f) handleFitxerCanviat(f);
                    }}
                    accept=".pdf,.dxf,.dwg,.geojson,.json,.kml,.png,.jpg,.jpeg"
                    className="hidden"
                  />
                  {fitxerPujada ? (
                    <div className="space-y-1">
                      <CheckCircle2 className="w-6 h-6 text-emerald-600 mx-auto" />
                      <p className="text-xs font-bold truncate">{fitxerPujada.name}</p>
                      <p className="text-[10px] text-on-surface-variant font-mono">
                        {(fitxerPujada.size / 1024).toFixed(1)} KB · Fes clic per canviar fitxer
                      </p>
                    </div>
                  ) : (
                    <div className="space-y-1">
                      <UploadCloud className="w-6 h-6 text-primary mx-auto" />
                      <p className="text-xs font-bold text-on-surface">
                        Selecciona o arrossega el fitxer des de la teva carpeta local
                      </p>
                      <p className="text-[10px] text-on-surface-variant">
                        Formats admesos: PDF, DXF, DWG, GeoJSON, KML
                      </p>
                    </div>
                  )}
                </div>
              </div>

              <div>
                <label className="block font-label-caps text-on-surface-variant uppercase mb-1">
                  Codi Referència *
                </label>
                <input
                  type="text"
                  required
                  placeholder="Ex: PLN-001"
                  value={nouPlanol.codi_referencia}
                  onChange={(e) =>
                    setNouPlanol({ ...nouPlanol, codi_referencia: e.target.value })
                  }
                  className="w-full px-3 py-2 rounded-lg border border-outline-variant bg-surface-container-low text-xs font-data-tabular focus:border-primary outline-none"
                />
              </div>

              <div>
                <label className="block font-label-caps text-on-surface-variant uppercase mb-1">
                  Títol del Plànol *
                </label>
                <input
                  type="text"
                  required
                  placeholder="Ex: Xarxa Distribució PE-100 Polígon 3"
                  value={nouPlanol.titol}
                  onChange={(e) => setNouPlanol({ ...nouPlanol, titol: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg border border-outline-variant bg-surface-container-low text-xs font-medium focus:border-primary outline-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-label-caps text-on-surface-variant uppercase mb-1">
                    Format
                  </label>
                  <select
                    value={nouPlanol.tipus_fitxer}
                    onChange={(e) => setNouPlanol({ ...nouPlanol, tipus_fitxer: e.target.value })}
                    className="w-full px-3 py-2 rounded-lg border border-outline-variant bg-surface-container-low text-xs font-semibold"
                  >
                    <option value="DXF">AutoCAD DXF</option>
                    <option value="GEOJSON">GeoJSON</option>
                    <option value="KML">Google KML</option>
                    <option value="PDF">Plànol PDF</option>
                  </select>
                </div>

                <div>
                  <label className="block font-label-caps text-on-surface-variant uppercase mb-1">
                    Projecció
                  </label>
                  <input
                    type="text"
                    value={nouPlanol.projeccio}
                    onChange={(e) => setNouPlanol({ ...nouPlanol, projeccio: e.target.value })}
                    className="w-full px-3 py-2 rounded-lg border border-outline-variant bg-surface-container-low text-xs font-data-tabular"
                  />
                </div>
              </div>

              <div className="pt-3 border-t border-surface-container flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setModalNouPlanol(false)}
                  className="px-4 py-2 rounded-lg border border-outline-variant text-on-surface-variant text-xs font-medium"
                >
                  Cancel·lar
                </button>
                <button
                  type="submit"
                  disabled={
                    guardant || !nouPlanol.titol.trim() || !nouPlanol.codi_referencia.trim()
                  }
                  className="px-4 py-2 rounded-lg bg-primary hover:bg-primary-container text-white text-xs font-bold shadow disabled:opacity-50"
                >
                  {guardant ? "Desant..." : "Pujar Plànol"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal Nova Capa Vectorial (FR-015) */}
      {modalNovaCapa && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-md bg-surface-container-lowest rounded-2xl shadow-2xl border border-outline-variant/40 overflow-hidden">
            <div className="p-5 border-b border-surface-container flex items-center justify-between">
              <h3 className="font-section-title text-base text-primary flex items-center gap-2">
                <Layers className="w-4 h-4 text-secondary" />
                Nova Capa Vectorial GIS
              </h3>
              <button
                onClick={() => setModalNovaCapa(false)}
                className="p-1 rounded-lg text-outline hover:text-on-surface"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleCrearCapa} className="p-5 space-y-4">
              <div>
                <label className="block font-label-caps text-on-surface-variant uppercase mb-1">
                  Nom de la Capa *
                </label>
                <input
                  type="text"
                  required
                  placeholder="Ex: Canonada PE-100 Ø90mm Polígon Nord"
                  value={novaCapaForm.nom}
                  onChange={(e) => setNovaCapaForm({ ...novaCapaForm, nom: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg border border-outline-variant bg-surface-container-low text-xs font-medium focus:border-primary outline-none"
                />
              </div>

              <div>
                <label className="block font-label-caps text-on-surface-variant uppercase mb-1">
                  Disciplina Tècnica
                </label>
                <select
                  value={novaCapaForm.disciplina}
                  onChange={(e) => {
                    const disc = DISCIPLINES_DEFECTE.find((d) => d.id === e.target.value);
                    setNovaCapaForm({
                      ...novaCapaForm,
                      disciplina: e.target.value,
                      color_hex: disc ? disc.color : novaCapaForm.color_hex,
                    });
                  }}
                  className="w-full px-3 py-2 rounded-lg border border-outline-variant bg-surface-container-low text-xs font-semibold focus:border-primary outline-none"
                >
                  {DISCIPLINES_DEFECTE.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.label}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block font-label-caps text-on-surface-variant uppercase mb-1">
                  Color del Traçat
                </label>
                <div className="flex items-center gap-2">
                  <input
                    type="color"
                    value={novaCapaForm.color_hex}
                    onChange={(e) =>
                      setNovaCapaForm({ ...novaCapaForm, color_hex: e.target.value })
                    }
                    className="w-9 h-9 rounded-lg border border-outline-variant cursor-pointer p-0.5 bg-surface-container-low"
                  />
                  <input
                    type="text"
                    value={novaCapaForm.color_hex}
                    onChange={(e) =>
                      setNovaCapaForm({ ...novaCapaForm, color_hex: e.target.value })
                    }
                    className="w-28 px-2.5 py-1.5 rounded-lg border border-outline-variant bg-surface-container-low text-xs font-mono"
                  />
                  <div className="flex items-center gap-1.5 ml-auto">
                    {DISCIPLINES_DEFECTE.map((d) => (
                      <button
                        key={d.id}
                        type="button"
                        onClick={() =>
                          setNovaCapaForm({ ...novaCapaForm, color_hex: d.color })
                        }
                        className="w-5 h-5 rounded-full border border-black/20 transition-transform hover:scale-110"
                        style={{ backgroundColor: d.color }}
                        title={d.label}
                      />
                    ))}
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-label-caps text-on-surface-variant uppercase mb-1">
                    Gruix de Traç: {novaCapaForm.gruix_linia}px
                  </label>
                  <input
                    type="range"
                    min={1}
                    max={8}
                    value={novaCapaForm.gruix_linia}
                    onChange={(e) =>
                      setNovaCapaForm({ ...novaCapaForm, gruix_linia: Number(e.target.value) })
                    }
                    className="w-full h-1.5 bg-surface-container-highest rounded-lg cursor-pointer accent-primary"
                  />
                </div>

                <div>
                  <label className="block font-label-caps text-on-surface-variant uppercase mb-1">
                    Opacitat: {novaCapaForm.opacitat_percent}%
                  </label>
                  <input
                    type="range"
                    min={20}
                    max={100}
                    value={novaCapaForm.opacitat_percent}
                    onChange={(e) =>
                      setNovaCapaForm({
                        ...novaCapaForm,
                        opacitat_percent: Number(e.target.value),
                      })
                    }
                    className="w-full h-1.5 bg-surface-container-highest rounded-lg cursor-pointer accent-primary"
                  />
                </div>
              </div>

              <div className="p-2.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-[11px] text-emerald-800 dark:text-emerald-300 flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-emerald-600 shrink-0" />
                <span>El document original romandrà 100% inalterat.</span>
              </div>

              <div className="pt-3 border-t border-surface-container flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setModalNovaCapa(false)}
                  className="px-4 py-2 rounded-lg border border-outline-variant text-on-surface-variant text-xs font-medium"
                >
                  Cancel·lar
                </button>
                <button
                  type="submit"
                  disabled={guardantNovaCapa || !novaCapaForm.nom.trim()}
                  className="px-4 py-2 rounded-lg bg-primary hover:bg-primary-container text-white text-xs font-bold shadow disabled:opacity-50 flex items-center gap-1.5"
                >
                  {guardantNovaCapa ? (
                    <>
                      <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                      <span>Creant...</span>
                    </>
                  ) : (
                    <span>Crear Capa</span>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal Afegir Element Puntual */}
      {modalNouElement && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-sm bg-surface-container-lowest rounded-2xl shadow-2xl border border-outline-variant/40 overflow-hidden">
            <div className="p-4 border-b border-surface-container flex items-center justify-between">
              <h3 className="font-section-title text-sm text-primary flex items-center gap-2">
                <MapPin className="w-4 h-4 text-secondary" />
                Afegir Element a la Capa
              </h3>
              <button
                onClick={() => setModalNouElement(null)}
                className="p-1 rounded-lg text-outline hover:text-on-surface"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="p-4 space-y-3">
              <div>
                <label className="block font-label-caps text-on-surface-variant uppercase mb-1">
                  Nom / Etiqueta de l&apos;Element *
                </label>
                <input
                  type="text"
                  required
                  placeholder="Ex: Vàlvula DN50"
                  value={etiquetaElement}
                  onChange={(e) => setEtiquetaElement(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-outline-variant bg-surface-container-low text-xs font-medium focus:border-primary outline-none"
                  autoFocus
                />
              </div>

              <div>
                <label className="block font-label-caps text-on-surface-variant uppercase mb-1 text-[10px]">
                  Opcions ràpides
                </label>
                <div className="flex flex-wrap gap-1">
                  {[
                    "Vàlvula de tall",
                    "Comptador",
                    "Escomesa",
                    "Bomba",
                    "Hidrant",
                    "Arqueta",
                    "Caixa REBT",
                    "Sensor Pressió",
                  ].map((tipus) => (
                    <button
                      key={tipus}
                      type="button"
                      onClick={() => setEtiquetaElement(tipus)}
                      className={`px-2 py-1 rounded text-[10px] font-semibold border transition-all ${
                        etiquetaElement === tipus
                          ? "bg-primary text-white border-primary"
                          : "bg-surface-container-low border-outline-variant/40 hover:bg-surface-container"
                      }`}
                    >
                      {tipus}
                    </button>
                  ))}
                </div>
              </div>

              <div className="text-[10px] text-on-surface-variant font-mono bg-surface-container-low/50 p-2 rounded-lg">
                Posició relativa: X: {modalNouElement.x}% · Y: {modalNouElement.y}%
              </div>

              <div className="pt-2 border-t border-surface-container flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setModalNouElement(null)}
                  className="px-3 py-1.5 rounded-lg border border-outline-variant text-on-surface-variant text-xs font-medium"
                >
                  Cancel·lar
                </button>
                <button
                  type="button"
                  onClick={confirmarNouElement}
                  disabled={!etiquetaElement.trim()}
                  className="px-3 py-1.5 rounded-lg bg-primary hover:bg-primary-container text-white text-xs font-bold shadow disabled:opacity-50"
                >
                  Confirmar Element
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
