"use client";

import React, { useState, useEffect, useRef } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  Layers,
  Plus,
  Lock,
  Eye,
  EyeOff,
  MapPin,
  Compass,
  RefreshCw,
  Flashlight,
  AlertTriangle,
  Check,
  X,
  Activity,
  MousePointer,
  RotateCcw,
  FileText,
  ChevronDown,
  ShieldCheck,
  Palette,
  Trash2,
  ExternalLink,
  Share2,
} from "lucide-react";
import { apiFetch, getApiBaseUrl } from "@/lib/api";
import { addToSyncQueue } from "@/lib/offline/sync";

// --- TIPUS I LLEGENDA DE COLORS I SÍMBOLS (SPEC 01, 02 & AS-BUILT) ---

interface SimbolLlegenda {
  id: string;
  nom: string;
  disciplina: "AIGUA_REG" | "BAIXA_TENSIO" | "SANEJAMENT" | "INCIDENCIA" | "OBRA_CIVIL";
  color_hex: string;
  categoria: string;
  icona: string;
  forma: "triangle" | "square" | "circle" | "diamond";
  descripcio: string;
}

const LLEGENDA_TECNICA: SimbolLlegenda[] = [
  // AIGUA I REG (BLAU #0284c7)
  {
    id: "valvula_tall",
    nom: "Vàlvula de tall",
    disciplina: "AIGUA_REG",
    color_hex: "#0284c7",
    categoria: "Hidràulica",
    icona: "💧",
    forma: "triangle",
    descripcio: "Vàlvula de comporta / papallona / pas d'aigua",
  },
  {
    id: "comptador_aigua",
    nom: "Comptador d'aigua",
    disciplina: "AIGUA_REG",
    color_hex: "#0284c7",
    categoria: "Hidràulica",
    icona: "⏱️",
    forma: "square",
    descripcio: "Comptador volumètric o electromagnètic",
  },
  {
    id: "escomesa_aigua",
    nom: "Escomesa d'aigua",
    disciplina: "AIGUA_REG",
    color_hex: "#0284c7",
    categoria: "Hidràulica",
    icona: "🚰",
    forma: "circle",
    descripcio: "Punt de connexió a xarxa general de reg / abastiment",
  },
  {
    id: "bomba_pressio",
    nom: "Grup de Bombeig",
    disciplina: "AIGUA_REG",
    color_hex: "#0284c7",
    categoria: "Hidràulica",
    icona: "⚡",
    forma: "circle",
    descripcio: "Estació de bombament o grup de pressió",
  },
  {
    id: "hidrant",
    nom: "Hidrant / Boqueta",
    disciplina: "AIGUA_REG",
    color_hex: "#0284c7",
    categoria: "Hidràulica",
    icona: "🚒",
    forma: "square",
    descripcio: "Hidrant d'incendis o presa de càrrega ràpida",
  },

  // BAIXA TENSIÓ REBT (GROC / TARONJA #eab308)
  {
    id: "quadre_cgp",
    nom: "Quadre / CGP Elèctric",
    disciplina: "BAIXA_TENSIO",
    color_hex: "#eab308",
    categoria: "Electricitat",
    icona: "⚡",
    forma: "square",
    descripcio: "Caixa General de Protecció o Quadre de Comandament",
  },
  {
    id: "caixa_derivacio",
    nom: "Caixa de Derivació",
    disciplina: "BAIXA_TENSIO",
    color_hex: "#eab308",
    categoria: "Electricitat",
    icona: "📦",
    forma: "square",
    descripcio: "Arqueta o caixa d'enllaç elèctric",
  },
  {
    id: "punt_llum",
    nom: "Punt de Llum / Farola",
    disciplina: "BAIXA_TENSIO",
    color_hex: "#eab308",
    categoria: "Electricitat",
    icona: "💡",
    forma: "circle",
    descripcio: "Llumenera o punt d'il·luminació",
  },
  {
    id: "escomesa_elec",
    nom: "Escomesa Elèctrica",
    disciplina: "BAIXA_TENSIO",
    color_hex: "#eab308",
    categoria: "Electricitat",
    icona: "🔌",
    forma: "diamond",
    descripcio: "Connexió a la línia de distribució elèctrica",
  },

  // SANEJAMENT I DRENATGE (VERD #10b981)
  {
    id: "arqueta_sanejament",
    nom: "Arqueta de Registre",
    disciplina: "SANEJAMENT",
    color_hex: "#10b981",
    categoria: "Sanejament",
    icona: "🕳️",
    forma: "circle",
    descripcio: "Pou o arqueta sifònica de sanejament",
  },
  {
    id: "boqueta_neteja",
    nom: "Boqueta de Neteja",
    disciplina: "SANEJAMENT",
    color_hex: "#10b981",
    categoria: "Sanejament",
    icona: "🌿",
    forma: "square",
    descripcio: "Terminal de desembussament i inspecció",
  },

  // INCIDÈNCIES I PUNTS CRÍTICS (VERMELL #ef4444)
  {
    id: "fuita_avaria",
    nom: "Fuita / Trencament",
    disciplina: "INCIDENCIA",
    color_hex: "#ef4444",
    categoria: "Incidència",
    icona: "🚨",
    forma: "diamond",
    descripcio: "Fuita d'aigua activa o cable seccionat",
  },
  {
    id: "incidencia_bloqueig",
    nom: "Obstacle Bloquejant",
    disciplina: "INCIDENCIA",
    color_hex: "#ef4444",
    categoria: "Incidència",
    icona: "⚠️",
    forma: "triangle",
    descripcio: "Punt conflictiu que requereix intervenció o aturada",
  },

  // OBRA CIVIL I RASES (PISSARRA #475569)
  {
    id: "rasa_creuament",
    nom: "Rasa / Creuament",
    disciplina: "OBRA_CIVIL",
    color_hex: "#475569",
    categoria: "Obra Civil",
    icona: "🚧",
    forma: "square",
    descripcio: "Travessera de calçada o rasa oberta",
  },
  {
    id: "fita_topografica",
    nom: "Fita / Vèrtex",
    disciplina: "OBRA_CIVIL",
    color_hex: "#475569",
    categoria: "Obra Civil",
    icona: "📐",
    forma: "diamond",
    descripcio: "Referència fixa de coordenades de camp",
  },
];

const PALETA_DISCIPLINES = [
  { id: "AIGUA_REG", nom: "Aigua i Reg", color: "#0284c7" },
  { id: "BAIXA_TENSIO", nom: "Electricitat REBT", color: "#eab308" },
  { id: "SANEJAMENT", nom: "Sanejament", color: "#10b981" },
  { id: "INCIDENCIA", nom: "Incidència", color: "#ef4444" },
  { id: "OBRA_CIVIL", nom: "Obra Civil", color: "#475569" },
];

interface FeatureGeoJSON {
  type: "Feature";
  geometry: {
    type: "Point" | "LineString";
    coordinates: any;
  };
  properties: {
    id?: string;
    nom?: string;
    etiqueta?: string;
    simbol_id?: string;
    icona?: string;
    color?: string;
    disciplina?: string;
  };
}

interface CapaVectorialUI {
  id: string;
  nom: string;
  disciplina: string;
  color_hex: string;
  gruix_linia: number;
  es_immutable: boolean;
  visible: boolean;
  geometries_geojson: {
    type: string;
    features: FeatureGeoJSON[];
  };
}

interface PlanolBaseUI {
  id: string;
  titol: string;
  codi_referencia: string;
  tipus_fitxer: string;
}

export default function OperariPlanolsPage() {
  const [capes, setCapes] = useState<CapaVectorialUI[]>([]);
  const [planolsDisponibles, setPlanolsDisponibles] = useState<PlanolBaseUI[]>([]);
  const [planolActiuId, setPlanolActiuId] = useState<string | null>(null);
  const [planolActiuInfo, setPlanolActiuInfo] = useState<PlanolBaseUI | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [zoom, setZoom] = useState<number>(1);
  const [opacitatFons, setOpacitatFons] = useState<number>(85);

  // Eines d'edició
  const [einaActiva, setEinaActiva] = useState<"punter" | "canonada" | "simbol">("punter");
  const [simbolSeleccionat, setSimbolSeleccionat] = useState<SimbolLlegenda>(LLEGENDA_TECNICA[0]);
  const [disciplinaFiltre, setDisciplinaFiltre] = useState<string>("TOTS");
  const [capaActivaId, setCapaActivaId] = useState<string>("");
  const [puntsLiniaEnCurs, setPuntsLiniaEnCurs] = useState<Array<{ x: number; y: number }>>([]);

  // Modals i calaixos
  const [mostrarLlegenda, setMostrarLlegenda] = useState<boolean>(false);
  const [mostrarDialegCapaTancada, setMostrarDialegCapaTancada] = useState<boolean>(false);
  const [pendentClickCoords, setPendentClickCoords] = useState<{ x: number; y: number } | null>(null);
  const [modalNovaCapa, setModalNovaCapa] = useState<boolean>(false);
  const [nomNovaCapa, setNomNovaCapa] = useState<string>("");
  const [disciplinaNovaCapa, setDisciplinaNovaCapa] = useState<string>("AIGUA_REG");
  const [desantCapa, setDesantCapa] = useState<boolean>(false);
  const [missatgeNotificacio, setMissatgeNotificacio] = useState<string | null>(null);

  // Element seleccionat per a inspecció
  const [elementInspeccio, setElementInspeccio] = useState<{
    capaId: string;
    feature: FeatureGeoJSON;
    index: number;
  } | null>(null);

  // Llanterna Integrada (FR-011)
  const [llanternaActiva, setLlanternaActiva] = useState<boolean>(false);
  const streamLlanternaRef = useRef<MediaStream | null>(null);

  // Connexió i arxiu extern
  const [errorConnexio, setErrorConnexio] = useState<{ code?: string; message: string } | null>(null);
  const [refArxiuExtern, setRefArxiuExtern] = useState<string>("");
  const [consultantArxiu, setConsultantArxiu] = useState<boolean>(false);

  const canvasRef = useRef<HTMLDivElement>(null);

  // Notificació visual temporal
  const mostrarNotificacio = (msg: string) => {
    setMissatgeNotificacio(msg);
    setTimeout(() => setMissatgeNotificacio(null), 3500);
  };

  // Carregar plànols disponibles i capes reals
  const carregarDades = async () => {
    setLoading(true);
    setErrorConnexio(null);
    try {
      const urlParams = typeof window !== "undefined" ? new URLSearchParams(window.location.search) : null;
      let targetPlanolId = urlParams?.get("planol");

      // Consultar plànols base disponibles de l'empresa
      const plansList = await apiFetch<PlanolBaseUI[]>("/operari/planols/disponibles").catch(() => []);
      setPlanolsDisponibles(plansList || []);

      if (!targetPlanolId && plansList && plansList.length > 0) {
        targetPlanolId = plansList[0].id;
      }

      setPlanolActiuId(targetPlanolId || null);

      if (targetPlanolId) {
        const found = plansList?.find((p) => p.id === targetPlanolId);
        if (found) setPlanolActiuInfo(found);

        // Carregar capes vectorials d'aquest plànol
        const dataCapes = await apiFetch<any[]>(`/operari/planols/${targetPlanolId}/capes`).catch(() => []);
        const capesNormalitzades: CapaVectorialUI[] = (dataCapes || []).map((c) => {
          let features: FeatureGeoJSON[] = [];
          if (c.geometries_geojson?.features && Array.isArray(c.geometries_geojson.features)) {
            features = c.geometries_geojson.features;
          } else if (c.dades_geojson?.features && Array.isArray(c.dades_geojson.features)) {
            features = c.dades_geojson.features;
          } else if (c.pins && Array.isArray(c.pins)) {
            // Conversió de pins clàssics a GeoJSON
            features = c.pins.map((p: any, idx: number) => ({
              type: "Feature",
              geometry: {
                type: "Point",
                coordinates: [p.x, p.y],
              },
              properties: {
                id: `pin-${idx}`,
                nom: p.etiqueta || "Anotació",
                color: c.color_hex || "#0284c7",
              },
            }));
          }

          return {
            id: c.id,
            nom: c.nom || c.nom_capa || "Capa As-Built",
            disciplina: c.disciplina || "AIGUA_REG",
            color_hex: c.color_hex || "#0284c7",
            gruix_linia: c.gruix_linia || 3,
            es_immutable: Boolean(c.es_immutable || c.es_tancada),
            visible: c.visible ?? true,
            geometries_geojson: {
              type: "FeatureCollection",
              features,
            },
          };
        });

        setCapes(capesNormalitzades);
        if (capesNormalitzades.length > 0) {
          setCapaActivaId(capesNormalitzades[0].id);
        } else {
          setCapaActivaId("");
        }
      } else {
        setCapes([]);
      }
    } catch (err: any) {
      setCapes([]);
      if (
        err?.code === "SENSE_COBERTURA_MOBIL" ||
        err?.code === "NODE_EMPRESA_OFFLINE" ||
        err?.code === "DB_UNAVAILABLE"
      ) {
        setErrorConnexio({
          code: err.code,
          message: err.message,
        });
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    carregarDades();
  }, []);

  // Cleanup de la llanterna quan es tanca la vista
  useEffect(() => {
    return () => {
      if (streamLlanternaRef.current) {
        streamLlanternaRef.current.getTracks().forEach((track) => track.stop());
      }
    };
  }, []);

  // Llanterna Integrada (FR-011)
  const toggleLlanterna = async () => {
    try {
      if (llanternaActiva) {
        if (streamLlanternaRef.current) {
          streamLlanternaRef.current.getTracks().forEach((t) => t.stop());
          streamLlanternaRef.current = null;
        }
        setLlanternaActiva(false);
        mostrarNotificacio("Llanterna apagada");
      } else {
        if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
          const stream = await navigator.mediaDevices.getUserMedia({
            video: { facingMode: "environment" },
          });
          streamLlanternaRef.current = stream;
          const track = stream.getVideoTracks()[0];
          const trackAny = track as any;
          if (trackAny.applyConstraints) {
            await trackAny.applyConstraints({ advanced: [{ torch: true }] });
          }
          setLlanternaActiva(true);
          mostrarNotificacio("🔦 Llanterna de camp activada");
        } else {
          alert("El navegador no té suport per a la llanterna en aquest dispositiu.");
        }
      }
    } catch {
      setLlanternaActiva(!llanternaActiva);
    }
  };

  // Canvi de plànol actiu
  const handleCanviarPlanol = (nouId: string) => {
    setPlanolActiuId(nouId);
    const found = planolsDisponibles.find((p) => p.id === nouId);
    setPlanolActiuInfo(found || null);
    setPuntsLiniaEnCurs([]);
    setElementInspeccio(null);

    // Carregar capes del nou plànol
    apiFetch<any[]>(`/operari/planols/${nouId}/capes`)
      .then((data) => {
        const list = (data || []).map((c) => ({
          id: c.id,
          nom: c.nom || "Capa",
          disciplina: c.disciplina || "AIGUA_REG",
          color_hex: c.color_hex || "#0284c7",
          gruix_linia: c.gruix_linia || 3,
          es_immutable: Boolean(c.es_immutable || c.es_tancada),
          visible: c.visible ?? true,
          geometries_geojson: c.geometries_geojson || { type: "FeatureCollection", features: [] },
        }));
        setCapes(list);
        setCapaActivaId(list.length > 0 ? list[0].id : "");
      })
      .catch(() => {
        setCapes([]);
        setCapaActivaId("");
      });
  };

  // Commutar visibilitat de la capa (Spec 017 RF-11)
  const toggleVisibilitat = async (id: string) => {
    const target = capes.find((c) => c.id === id);
    if (!target) return;
    const novaVis = !target.visible;
    setCapes((prev) => prev.map((c) => (c.id === id ? { ...c, visible: novaVis } : c)));

    if (planolActiuId) {
      try {
        await apiFetch(`/operari/planols/${planolActiuId}/capes/${id}`, {
          method: "PUT",
          body: JSON.stringify({ visible: novaVis }),
        });
      } catch {
        // En cas d'estar offline s'ignora silenciadament
      }
    }
  };

  // Persistir capa al servidor o a la cua offline
  const desarCanvisCapa = async (capa: CapaVectorialUI) => {
    if (!planolActiuId) return;
    setDesantCapa(true);
    try {
      await apiFetch(`/operari/planols/${planolActiuId}/capes/${capa.id}`, {
        method: "PUT",
        body: JSON.stringify({
          nom: capa.nom,
          geometries_geojson: capa.geometries_geojson,
          visible: capa.visible,
        }),
      });
      mostrarNotificacio(`Capa "${capa.nom}" sincronitzada. Plànol base intacte.`);
    } catch {
      // Si falla per connexió, s'encua a la sync queue (FR-002)
      await addToSyncQueue("POST_PLANOL_CAPA", {
        planol_id: planolActiuId,
        capa: {
          id: capa.id,
          nom: capa.nom,
          geometries_geojson: capa.geometries_geojson,
        },
      }).catch(console.error);
      mostrarNotificacio(`Guardat localment (Mode Fora de Línia).`);
    } finally {
      setDesantCapa(false);
    }
  };

  // Clic al canvas del plànol
  const handlePlanolClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (einaActiva === "punter") return;
    if (!canvasRef.current) return;

    const rect = canvasRef.current.getBoundingClientRect();
    const x = Math.round(((e.clientX - rect.left) / rect.width) * 1000) / 10;
    const y = Math.round(((e.clientY - rect.top) / rect.height) * 1000) / 10;

    const capaActual = capes.find((c) => c.id === capaActivaId);

    // Si no hi ha capa o és buida, oferir creació
    if (!capaActual) {
      setPendentClickCoords({ x, y });
      setModalNovaCapa(true);
      return;
    }

    // Spec 017 RF-13.1: Si la capa és tancada/immutable, bloquejar i oferir addenda
    if (capaActual.es_immutable) {
      setPendentClickCoords({ x, y });
      setMostrarDialegCapaTancada(true);
      return;
    }

    if (einaActiva === "canonada") {
      setPuntsLiniaEnCurs((prev) => [...prev, { x, y }]);
    } else if (einaActiva === "simbol") {
      afegirSimbolACapa(capaActual, x, y);
    }
  };

  // Afegir element puntual / símbol de la llegenda a la capa activa
  const afegirSimbolACapa = async (capa: CapaVectorialUI, x: number, y: number) => {
    const novaFeature: FeatureGeoJSON = {
      type: "Feature",
      geometry: {
        type: "Point",
        coordinates: [x, y],
      },
      properties: {
        id: `simbol-${Date.now()}`,
        nom: simbolSeleccionat.nom,
        etiqueta: simbolSeleccionat.nom,
        simbol_id: simbolSeleccionat.id,
        icona: simbolSeleccionat.icona,
        color: simbolSeleccionat.color_hex,
        disciplina: simbolSeleccionat.disciplina,
      },
    };

    const actuals = capa.geometries_geojson?.features || [];
    const actualitzada = {
      ...capa,
      geometries_geojson: {
        ...capa.geometries_geojson,
        features: [...actuals, novaFeature],
      },
    };

    setCapes((prev) => prev.map((c) => (c.id === capa.id ? actualitzada : c)));
    await desarCanvisCapa(actualitzada);
  };

  // Finalitzar traçat de canonada / línia
  const finalitzarLinia = async () => {
    if (puntsLiniaEnCurs.length < 2) {
      setPuntsLiniaEnCurs([]);
      return;
    }
    const capaActual = capes.find((c) => c.id === capaActivaId);
    if (!capaActual) return;

    const discColor =
      PALETA_DISCIPLINES.find((d) => d.id === capaActual.disciplina)?.color || capaActual.color_hex;

    const novaFeature: FeatureGeoJSON = {
      type: "Feature",
      geometry: {
        type: "LineString",
        coordinates: puntsLiniaEnCurs.map((p) => [p.x, p.y]),
      },
      properties: {
        id: `linia-${Date.now()}`,
        nom: `Traçat ${capaActual.nom}`,
        color: discColor,
        disciplina: capaActual.disciplina,
      },
    };

    const actuals = capaActual.geometries_geojson?.features || [];
    const actualitzada = {
      ...capaActual,
      geometries_geojson: {
        ...capaActual.geometries_geojson,
        features: [...actuals, novaFeature],
      },
    };

    setCapes((prev) => prev.map((c) => (c.id === capaActual.id ? actualitzada : c)));
    setPuntsLiniaEnCurs([]);
    await desarCanvisCapa(actualitzada);
  };

  // Crear nova capa des del mòbil (Spec 017 RF-13.1 / FR-010)
  const handleCrearCapa = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!planolActiuId) return;

    const disc = PALETA_DISCIPLINES.find((d) => d.id === disciplinaNovaCapa);
    const nomFinal =
      nomNovaCapa.trim() || `Addenda As-Built (${new Date().toLocaleDateString("ca-ES")})`;

    const initialFeatures: FeatureGeoJSON[] = pendentClickCoords
      ? [
          {
            type: "Feature",
            geometry: {
              type: "Point",
              coordinates: [pendentClickCoords.x, pendentClickCoords.y],
            },
            properties: {
              id: `simbol-${Date.now()}`,
              nom: simbolSeleccionat.nom,
              color: disc?.color || "#0284c7",
              icona: simbolSeleccionat.icona,
            },
          },
        ]
      : [];

    const payload = {
      nom: nomFinal,
      disciplina: disciplinaNovaCapa,
      color_hex: disc?.color || "#0284c7",
      gruix_linia: 3,
      es_tancada: false,
      visible: true,
      dades_geojson: {
        type: "FeatureCollection",
        features: initialFeatures,
      },
    };

    try {
      const res = await apiFetch<any>(`/operari/planols/${planolActiuId}/capes`, {
        method: "POST",
        body: JSON.stringify(payload),
      });

      const novaCapa: CapaVectorialUI = {
        id: res.id,
        nom: res.nom,
        disciplina: res.disciplina || disciplinaNovaCapa,
        color_hex: res.color_hex || disc?.color || "#0284c7",
        gruix_linia: res.gruix_linia || 3,
        es_immutable: false,
        visible: true,
        geometries_geojson: res.dades_geojson || { type: "FeatureCollection", features: initialFeatures },
      };

      setCapes((prev) => [...prev, novaCapa]);
      setCapaActivaId(novaCapa.id);
      mostrarNotificacio(`Capa "${novaCapa.nom}" creada.`);
    } catch {
      // Offline fallback
      const localId = `local-capa-${Date.now()}`;
      const novaCapaLocal: CapaVectorialUI = {
        id: localId,
        nom: nomFinal,
        disciplina: disciplinaNovaCapa,
        color_hex: disc?.color || "#0284c7",
        gruix_linia: 3,
        es_immutable: false,
        visible: true,
        geometries_geojson: { type: "FeatureCollection", features: initialFeatures },
      };
      setCapes((prev) => [...prev, novaCapaLocal]);
      setCapaActivaId(localId);

      await addToSyncQueue("POST_PLANOL_CAPA", {
        planol_id: planolActiuId,
        capa: novaCapaLocal,
      }).catch(console.error);
      mostrarNotificacio(`Capa creada localment (Mode Fora de Línia).`);
    } finally {
      setModalNovaCapa(false);
      setMostrarDialegCapaTancada(false);
      setPendentClickCoords(null);
      setNomNovaCapa("");
    }
  };

  // Eliminar un element seleccionat
  const handleEliminarElement = async () => {
    if (!elementInspeccio) return;
    const { capaId, index } = elementInspeccio;
    const capaTarget = capes.find((c) => c.id === capaId);
    if (!capaTarget || capaTarget.es_immutable) return;

    const novesFeatures = [...capaTarget.geometries_geojson.features];
    novesFeatures.splice(index, 1);

    const actualitzada = {
      ...capaTarget,
      geometries_geojson: {
        ...capaTarget.geometries_geojson,
        features: novesFeatures,
      },
    };

    setCapes((prev) => prev.map((c) => (c.id === capaId ? actualitzada : c)));
    setElementInspeccio(null);
    await desarCanvisCapa(actualitzada);
  };

  // Exportar plànol a incidència (FR-014 / User Story 6)
  const handleExportarAIncidencia = () => {
    if (!planolActiuId) return;
    mostrarNotificacio("Plànol As-Built vinculat a la incidència de camp.");
    if (typeof window !== "undefined") {
      window.location.href = `/operari/incidencies?nou=1&origen=planol&planol_id=${planolActiuId}`;
    }
  };

  // Consulta arxiu extern
  const handleConsultarArxiuExtern = async () => {
    if (!refArxiuExtern.trim()) return;
    setConsultantArxiu(true);
    setErrorConnexio(null);
    try {
      await apiFetch(
        `/operari/planols/arxiu-extern?referencia=${encodeURIComponent(refArxiuExtern.trim())}`
      );
    } catch (err: any) {
      setErrorConnexio({
        code: err?.code || "NODE_EMPRESA_OFFLINE",
        message:
          err?.message ||
          "🖥️ Ordinador central de l'empresa apagat: Aquest plànol extra viu al disc dur de l'oficina i ara mateix està apagat o sense internet.",
      });
    } finally {
      setConsultantArxiu(false);
    }
  };

  const capaActiva = capes.find((c) => c.id === capaActivaId);

  const simbolsFiltrats =
    disciplinaFiltre === "TOTS"
      ? LLEGENDA_TECNICA
      : LLEGENDA_TECNICA.filter((s) => s.disciplina === disciplinaFiltre);

  return (
    <div className="flex-1 flex flex-col bg-[#0b131e] text-slate-100 select-none overflow-hidden h-screen">
      {/* 1. Header Tècnic de Camp (Stitch Screen & Mobile Ergonomics) */}
      <header className="bg-[#0f1d2d] border-b border-slate-800 p-3 flex items-center justify-between shrink-0 shadow-md">
        <div className="flex items-center gap-2 min-w-0">
          <Link
            href="/operari/feines"
            className="flex items-center gap-1 text-xs font-bold text-slate-300 hover:text-white p-1 rounded-lg hover:bg-slate-800 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            <span className="hidden sm:inline">Feines</span>
          </Link>
          <div className="w-px h-4 bg-slate-700" />
          <div className="min-w-0">
            <h1 className="text-xs font-black tracking-wider uppercase text-white truncate flex items-center gap-1.5">
              <span>{planolActiuInfo?.titol || "Visor As-Built"}</span>
              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-sky-500/20 text-sky-300 font-bold border border-sky-500/30">
                {planolActiuInfo?.codi_referencia || "GIS"}
              </span>
            </h1>
          </div>
        </div>

        {/* Botons d'acció ràpida a la capçalera */}
        <div className="flex items-center gap-1.5 shrink-0">
          {/* Botó Llanterna Integrada (FR-011) */}
          <button
            type="button"
            onClick={toggleLlanterna}
            className={`px-2.5 py-1.5 rounded-xl text-xs font-bold flex items-center gap-1 transition-all shadow-sm ${
              llanternaActiva
                ? "bg-amber-400 text-slate-950 ring-2 ring-amber-300 animate-pulse"
                : "bg-slate-800 text-slate-300 hover:bg-slate-700 border border-slate-700"
            }`}
            title="Activa la llanterna per a treballs en rases i entorns foscos (FR-011)"
          >
            <Flashlight className="w-3.5 h-3.5" />
            <span className="hidden xs:inline">Llanterna</span>
          </button>

          {/* Botó Exportar a Incidència (FR-014) */}
          <button
            type="button"
            onClick={handleExportarAIncidencia}
            className="px-2.5 py-1.5 rounded-xl bg-rose-600/80 hover:bg-rose-600 text-white text-xs font-bold flex items-center gap-1 transition-all border border-rose-500/40 shadow-sm"
            title="Adjunta la vista del plànol amb anotacions a una incidència oberta"
          >
            <AlertTriangle className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Incidència</span>
          </button>

          {/* Botó Refrescar */}
          <button
            type="button"
            onClick={carregarDades}
            disabled={loading}
            className="p-1.5 rounded-xl bg-slate-800 text-slate-300 hover:text-white border border-slate-700 disabled:opacity-50"
            title="Sincronitzar plànols"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </header>

      {/* Notificació Toast Flotant */}
      {missatgeNotificacio && (
        <div className="absolute top-14 left-1/2 -translate-x-1/2 z-50 px-4 py-2 bg-emerald-500 text-slate-950 font-bold text-xs rounded-full shadow-2xl flex items-center gap-2 animate-in fade-in slide-in-from-top-2 border border-emerald-300">
          <ShieldCheck className="w-4 h-4" />
          <span>{missatgeNotificacio}</span>
        </div>
      )}

      {/* Avís de connexió si escau */}
      {errorConnexio && (
        <div className="mx-3 mt-2 p-2.5 rounded-xl bg-amber-950/80 border border-amber-600/40 text-amber-200 text-xs flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
            <span className="text-[11px] leading-tight">{errorConnexio.message}</span>
          </div>
          <button onClick={() => setErrorConnexio(null)} className="p-1 text-amber-400">
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* 2. Barra d'Eines Superior: Selector de Plànol & Gestió de Capes */}
      <div className="bg-[#0f1d2d]/90 border-b border-slate-800/80 px-3 py-2 flex items-center justify-between gap-2 overflow-x-auto custom-scrollbar shrink-0">
        {/* Selector de Plànols de la Jornada */}
        {planolsDisponibles.length > 1 && (
          <div className="flex items-center gap-1.5 shrink-0 bg-slate-800/70 px-2 py-1 rounded-lg border border-slate-700">
            <FileText className="w-3.5 h-3.5 text-sky-400" />
            <select
              value={planolActiuId || ""}
              onChange={(e) => handleCanviarPlanol(e.target.value)}
              className="bg-transparent text-xs font-bold text-white outline-none cursor-pointer"
            >
              {planolsDisponibles.map((p) => (
                <option key={p.id} value={p.id} className="bg-slate-900 text-white">
                  {p.codi_referencia} - {p.titol}
                </option>
              ))}
            </select>
          </div>
        )}

        {/* Llistat Horitzontal de Capes */}
        <div className="flex items-center gap-1.5 overflow-x-auto py-0.5 custom-scrollbar min-w-0 flex-1">
          <span className="text-[10px] font-mono text-slate-400 uppercase tracking-wider shrink-0 flex items-center gap-1">
            <Layers className="w-3 h-3 text-sky-400" />
            <span>Capes:</span>
          </span>

          {capes.map((capa) => {
            const isActiva = capa.id === capaActivaId;
            return (
              <div
                key={capa.id}
                onClick={() => setCapaActivaId(capa.id)}
                className={`px-2.5 py-1 rounded-lg flex items-center gap-1.5 cursor-pointer text-xs shrink-0 transition-all ${
                  isActiva
                    ? "bg-sky-600 text-white font-bold shadow ring-1 ring-sky-400"
                    : "bg-slate-800 text-slate-300 hover:bg-slate-700 border border-slate-700/60"
                }`}
              >
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    toggleVisibilitat(capa.id);
                  }}
                  className="hover:opacity-80 p-0.5"
                  title={capa.visible ? "Ocultar capa" : "Mostrar capa"}
                >
                  {capa.visible ? (
                    <Eye className="w-3 h-3 text-white" />
                  ) : (
                    <EyeOff className="w-3 h-3 opacity-40 text-slate-400" />
                  )}
                </button>
                <span
                  className="w-2 h-2 rounded-full shrink-0"
                  style={{ backgroundColor: capa.color_hex }}
                />
                <span className="truncate max-w-[120px]">{capa.nom}</span>
                {capa.es_immutable && (
                  <span title="Capa tancada / immutable">
                    <Lock className="w-2.5 h-2.5 text-amber-300 shrink-0" />
                  </span>
                )}
              </div>
            );
          })}

          {/* Botó Nova Capa */}
          <button
            type="button"
            onClick={() => setModalNovaCapa(true)}
            className="px-2 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-sky-400 border border-dashed border-sky-500/40 text-xs font-bold flex items-center gap-1 shrink-0 transition-all"
          >
            <Plus className="w-3 h-3" />
            <span>Nova</span>
          </button>
        </div>
      </div>

      {/* 3. Àrea Principal del Plànol Interactiu (Canvas SVG amb zoom i fons CAD) */}
      <div className="flex-1 relative flex items-center justify-center overflow-hidden bg-[#070e17]">
        {/* Floating Top Controls (GPS Status, Zoom, Opacitat) */}
        <div className="absolute top-3 left-3 z-30 flex items-center gap-2 pointer-events-auto">
          <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-slate-900/90 backdrop-blur-md border border-slate-700 text-[10px] font-mono text-emerald-400 shadow">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-ping" />
            <span>GPS AS-BUILT ACTIU</span>
          </div>

          <div className="hidden sm:flex items-center gap-1 px-2 py-0.5 rounded-full bg-slate-900/90 backdrop-blur-md border border-slate-700 text-[10px] font-mono text-slate-300 shadow">
            <span>Fons:</span>
            <input
              type="range"
              min={10}
              max={100}
              value={opacitatFons}
              onChange={(e) => setOpacitatFons(Number(e.target.value))}
              className="w-16 h-1 accent-sky-400 cursor-pointer"
            />
          </div>
        </div>

        {/* Floating Right Controls (Zoom +/-) */}
        <div className="absolute right-3 top-3 z-30 flex flex-col gap-1.5 pointer-events-auto">
          <button
            type="button"
            onClick={() => setZoom((z) => Math.min(2.5, +(z + 0.25).toFixed(2)))}
            className="w-9 h-9 rounded-xl bg-slate-900/90 backdrop-blur-md border border-slate-700 text-white flex items-center justify-center font-bold text-sm shadow hover:bg-slate-800 active:scale-95 transition-all"
          >
            +
          </button>
          <button
            type="button"
            onClick={() => setZoom((z) => Math.max(0.7, +(z - 0.25).toFixed(2)))}
            className="w-9 h-9 rounded-xl bg-slate-900/90 backdrop-blur-md border border-slate-700 text-white flex items-center justify-center font-bold text-sm shadow hover:bg-slate-800 active:scale-95 transition-all"
          >
            -
          </button>
          <button
            type="button"
            onClick={() => setZoom(1)}
            className="w-9 h-9 rounded-xl bg-slate-900/90 backdrop-blur-md border border-slate-700 text-sky-400 flex items-center justify-center font-mono text-[10px] font-bold shadow hover:bg-slate-800"
            title="Reset Zoom"
          >
            1x
          </button>
        </div>

        {/* Viewport del Plànol */}
        <div
          ref={canvasRef}
          onClick={handlePlanolClick}
          style={{ transform: `scale(${zoom})` }}
          className={`relative w-full max-w-lg aspect-[4/5] bg-slate-900 rounded-2xl border-2 border-slate-700 shadow-2xl overflow-hidden transition-transform duration-100 ${
            einaActiva === "punter" ? "cursor-default" : "cursor-crosshair"
          }`}
        >
          {/* Fons del Plànol Base Original Immutable */}
          <div
            className="absolute inset-0 w-full h-full pointer-events-none transition-opacity duration-150"
            style={{ opacity: opacitatFons / 100 }}
          >
            {/* Grid CAD de Precisió Tècnica */}
            <div
              className="absolute inset-0 w-full h-full opacity-20"
              style={{
                backgroundImage:
                  "radial-gradient(circle, #38bdf8 1px, transparent 1px), linear-gradient(to right, #0284c7 1px, transparent 1px), linear-gradient(to bottom, #0284c7 1px, transparent 1px)",
                backgroundSize: "20px 20px, 80px 80px, 80px 80px",
              }}
            />

            {/* Document Real / Plànol Base */}
            {planolActiuId ? (
              <div className="w-full h-full flex items-center justify-center">
                {planolActiuInfo?.tipus_fitxer === "PDF" ? (
                  <object
                    data={`${getApiBaseUrl()}/operari/planols/${planolActiuId}/fitxer#toolbar=0&navpanes=0`}
                    type="application/pdf"
                    className="w-full h-full pointer-events-none opacity-90"
                  >
                    <div className="flex flex-col items-center justify-center h-full text-slate-400 text-xs">
                      <FileText className="w-10 h-10 text-sky-400/50 mb-2" />
                      <span>{planolActiuInfo.titol}</span>
                    </div>
                  </object>
                ) : (
                  <img
                    src={`${getApiBaseUrl()}/operari/planols/${planolActiuId}/fitxer`}
                    alt={planolActiuInfo?.titol || "Plànol"}
                    onError={(e) => {
                      // Fallback si no és raster directe
                      (e.currentTarget as any).style.display = "none";
                    }}
                    className="max-w-full max-h-full object-contain pointer-events-none"
                  />
                )}
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center h-full text-center p-6 text-slate-400">
                <Compass className="w-10 h-10 text-sky-400/50 mb-2 animate-pulse" />
                <p className="text-xs font-mono">Finca / Emplaçament d&apos;Obra</p>
                <p className="text-[10px] text-slate-500">Base Inalterable SIF</p>
              </div>
            )}
          </div>

          {/* Renderització de Capes Vectorials SVG */}
          <svg
            className="absolute inset-0 w-full h-full pointer-events-none select-none"
            viewBox="0 0 100 100"
            preserveAspectRatio="none"
          >
            {capes
              .filter((c) => c.visible)
              .map((capa) => {
                const features = capa.geometries_geojson?.features || [];
                return (
                  <g key={capa.id}>
                    {features.map((feat, fIdx) => {
                      // Renderitzat de Línies / Canonades
                      if (feat.geometry?.type === "LineString") {
                        const pts = (feat.geometry.coordinates || [])
                          .map((coord: number[]) => `${coord[0]},${coord[1]}`)
                          .join(" ");
                        const strokeColor = feat.properties?.color || capa.color_hex;
                        return (
                          <g
                            key={feat.properties?.id || `line-${fIdx}`}
                            onClick={(e) => {
                              e.stopPropagation();
                              setElementInspeccio({ capaId: capa.id, feature: feat, index: fIdx });
                            }}
                            className="pointer-events-auto cursor-pointer"
                          >
                            <polyline
                              points={pts}
                              fill="none"
                              stroke={strokeColor}
                              strokeWidth={capa.gruix_linia ? capa.gruix_linia * 0.4 : 1.4}
                              strokeLinecap="round"
                              strokeLinejoin="round"
                            />
                            {feat.geometry.coordinates.map((c: number[], cIdx: number) => (
                              <circle
                                key={cIdx}
                                cx={c[0]}
                                cy={c[1]}
                                r={1.0}
                                fill="#ffffff"
                                stroke={strokeColor}
                                strokeWidth="0.4"
                              />
                            ))}
                          </g>
                        );
                      }

                      // Renderitzat de Símbols Puntuals de la Llegenda
                      if (feat.geometry?.type === "Point") {
                        const [px, py] = feat.geometry.coordinates || [0, 0];
                        const simbolId = feat.properties?.simbol_id;
                        const simbolDef = LLEGENDA_TECNICA.find((s) => s.id === simbolId);
                        const forma = simbolDef?.forma || "circle";
                        const color = feat.properties?.color || simbolDef?.color_hex || capa.color_hex;
                        const nom = feat.properties?.nom || feat.properties?.etiqueta || "Element";

                        return (
                          <g
                            key={feat.properties?.id || `pt-${fIdx}`}
                            onClick={(e) => {
                              e.stopPropagation();
                              setElementInspeccio({ capaId: capa.id, feature: feat, index: fIdx });
                            }}
                            className="pointer-events-auto cursor-pointer"
                          >
                            {/* Formes geomètriques segons la llegenda tècnica */}
                            {forma === "triangle" ? (
                              <polygon
                                points={`${px},${py - 2.2} ${px - 2.0},${py + 1.8} ${px + 2.0},${py + 1.8}`}
                                fill={color}
                                stroke="#ffffff"
                                strokeWidth="0.6"
                              />
                            ) : forma === "square" ? (
                              <rect
                                x={px - 1.8}
                                y={py - 1.8}
                                width={3.6}
                                height={3.6}
                                rx={0.4}
                                fill={color}
                                stroke="#ffffff"
                                strokeWidth="0.6"
                              />
                            ) : forma === "diamond" ? (
                              <polygon
                                points={`${px},${py - 2.2} ${px + 2.0},${py} ${px},${py + 2.2} ${px - 2.0},${py}`}
                                fill={color}
                                stroke="#ffffff"
                                strokeWidth="0.6"
                              />
                            ) : (
                              // Default Circle
                              <>
                                <circle
                                  cx={px}
                                  cy={py}
                                  r={2.0}
                                  fill={color}
                                  stroke="#ffffff"
                                  strokeWidth="0.6"
                                />
                                <circle cx={px} cy={py} r={0.7} fill="#ffffff" />
                              </>
                            )}

                            {/* Etiqueta flotant de l'element */}
                            <text
                              x={px + 2.4}
                              y={py - 1.4}
                              fill="#ffffff"
                              fontSize="2.4"
                              fontWeight="bold"
                              filter="drop-shadow(0px 1px 2px rgba(0,0,0,0.95))"
                            >
                              {nom}
                            </text>
                          </g>
                        );
                      }
                      return null;
                    })}
                  </g>
                );
              })}

            {/* Dibuix de línia en curs (Draft Polyline) */}
            {puntsLiniaEnCurs.length > 0 && (
              <g>
                <polyline
                  points={puntsLiniaEnCurs.map((p) => `${p.x},${p.y}`).join(" ")}
                  fill="none"
                  stroke={capaActiva?.color_hex || "#38bdf8"}
                  strokeWidth="1.5"
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

          {/* Cartell d'estat a la cantonada inferior del canvas */}
          <div className="absolute bottom-2 left-2 right-2 flex items-center justify-between pointer-events-none text-[10px] font-mono">
            <div className="px-2 py-1 rounded bg-black/80 backdrop-blur-md text-white border border-white/10 flex items-center gap-1.5">
              {einaActiva === "punter" && <span>🔍 Inspecció: Toca un element per veure detalls</span>}
              {einaActiva === "canonada" && (
                <span>✏️ Toca per afegir vèrtexs a la xarxa</span>
              )}
              {einaActiva === "simbol" && (
                <span>📍 Toca al plànol per col·locar: {simbolSeleccionat.nom}</span>
              )}
            </div>

            {desantCapa && (
              <div className="px-2 py-1 rounded bg-sky-600/90 text-white font-bold animate-pulse flex items-center gap-1">
                <RefreshCw className="w-3 h-3 animate-spin" />
                <span>Desant...</span>
              </div>
            )}
          </div>
        </div>

        {/* Modal / Popover d'Inspecció d'Element existent */}
        {elementInspeccio && (
          <div className="absolute top-16 left-1/2 -translate-x-1/2 z-40 bg-slate-900 border border-slate-700 p-3 rounded-2xl shadow-2xl max-w-xs w-11/12 text-xs space-y-2 animate-in fade-in">
            <div className="flex items-center justify-between border-b border-slate-800 pb-1.5">
              <div className="flex items-center gap-1.5 font-bold text-white">
                <MapPin className="w-4 h-4 text-sky-400" />
                <span>{elementInspeccio.feature.properties?.nom || "Element"}</span>
              </div>
              <button
                type="button"
                onClick={() => setElementInspeccio(null)}
                className="p-1 rounded text-slate-400 hover:text-white"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
            <div className="text-[11px] font-mono text-slate-300 space-y-1">
              <p>
                Tipus:{" "}
                <span className="text-sky-300 font-bold">
                  {elementInspeccio.feature.geometry.type === "LineString"
                    ? "Canonada / Cablejat"
                    : "Element Puntual"}
                </span>
              </p>
              <p>
                Coordenades: X:{" "}
                {elementInspeccio.feature.geometry.type === "Point"
                  ? elementInspeccio.feature.geometry.coordinates[0]
                  : "Múltiple"}{" "}
                · Y:{" "}
                {elementInspeccio.feature.geometry.type === "Point"
                  ? elementInspeccio.feature.geometry.coordinates[1]
                  : "Múltiple"}
              </p>
            </div>
            <div className="pt-2 flex justify-end gap-2">
              <button
                type="button"
                onClick={handleEliminarElement}
                className="px-2.5 py-1 rounded-lg bg-rose-500/20 text-rose-300 hover:bg-rose-500/30 border border-rose-500/40 text-[11px] font-bold flex items-center gap-1"
              >
                <Trash2 className="w-3 h-3" />
                <span>Eliminar</span>
              </button>
            </div>
          </div>
        )}
      </div>

      {/* 4. Controls d'Acció Inferiors (Toolbar Tècnica de Dibuix) */}
      <div className="bg-[#0f1d2d] border-t border-slate-800 p-2.5 flex flex-col gap-2 shrink-0">
        {/* Barra de Selecció d'Eina Principal */}
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center bg-slate-800 p-1 rounded-xl border border-slate-700/80 gap-1 flex-1">
            <button
              type="button"
              onClick={() => {
                setEinaActiva("punter");
                setPuntsLiniaEnCurs([]);
              }}
              className={`flex-1 py-2 px-2 rounded-lg text-xs font-bold flex items-center justify-center gap-1.5 transition-all ${
                einaActiva === "punter"
                  ? "bg-sky-600 text-white shadow-sm"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              <MousePointer className="w-3.5 h-3.5" />
              <span>Punter</span>
            </button>

            <button
              type="button"
              onClick={() => {
                if (capaActiva?.es_immutable) {
                  setMostrarDialegCapaTancada(true);
                  return;
                }
                setEinaActiva("canonada");
              }}
              className={`flex-1 py-2 px-2 rounded-lg text-xs font-bold flex items-center justify-center gap-1.5 transition-all ${
                einaActiva === "canonada"
                  ? "bg-sky-600 text-white shadow-sm"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              <Activity className="w-3.5 h-3.5" />
              <span>Traçar Xarxa</span>
            </button>

            <button
              type="button"
              onClick={() => {
                if (capaActiva?.es_immutable) {
                  setMostrarDialegCapaTancada(true);
                  return;
                }
                setEinaActiva("simbol");
                setPuntsLiniaEnCurs([]);
              }}
              className={`flex-1 py-2 px-2 rounded-lg text-xs font-bold flex items-center justify-center gap-1.5 transition-all ${
                einaActiva === "simbol"
                  ? "bg-sky-600 text-white shadow-sm"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              <MapPin className="w-3.5 h-3.5" />
              <span>Afegir Símbol</span>
            </button>
          </div>

          {/* Botó Obrir Llegenda Completa */}
          <button
            type="button"
            onClick={() => setMostrarLlegenda(!mostrarLlegenda)}
            className={`px-3 py-2 rounded-xl border text-xs font-bold flex items-center gap-1.5 transition-all shadow-sm ${
              mostrarLlegenda
                ? "bg-sky-500 text-slate-950 border-sky-400 font-black"
                : "bg-slate-800 text-slate-200 border-slate-700 hover:bg-slate-750"
            }`}
          >
            <Palette className="w-4 h-4" />
            <span className="hidden xs:inline">Llegenda</span>
          </button>
        </div>

        {/* Panell d'Estat quan s'està traçant una línia */}
        {puntsLiniaEnCurs.length > 0 && (
          <div className="p-2 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-between text-xs animate-in fade-in">
            <span className="font-mono text-amber-300 font-bold">
              {puntsLiniaEnCurs.length} vèrtexs marcats
            </span>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={finalitzarLinia}
                disabled={puntsLiniaEnCurs.length < 2}
                className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-bold flex items-center gap-1 disabled:opacity-50"
              >
                <Check className="w-3.5 h-3.5" />
                <span>Desar Traçat</span>
              </button>
              <button
                type="button"
                onClick={() => setPuntsLiniaEnCurs([])}
                className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}

        {/* Selector Ràpid de Símbols Actius (Quick Symbols Bar) */}
        {einaActiva === "simbol" && (
          <div className="flex items-center gap-1.5 overflow-x-auto py-1 custom-scrollbar">
            {LLEGENDA_TECNICA.slice(0, 8).map((simbol) => {
              const isSelected = simbolSeleccionat.id === simbol.id;
              return (
                <button
                  key={simbol.id}
                  type="button"
                  onClick={() => setSimbolSeleccionat(simbol)}
                  className={`px-2.5 py-1.5 rounded-xl border flex items-center gap-1.5 text-xs font-semibold shrink-0 transition-all ${
                    isSelected
                      ? "bg-slate-700 border-sky-400 text-white shadow-sm ring-1 ring-sky-400"
                      : "bg-slate-800/80 border-slate-700 text-slate-300 hover:bg-slate-700"
                  }`}
                >
                  <span
                    className="w-2.5 h-2.5 rounded-full"
                    style={{ backgroundColor: simbol.color_hex }}
                  />
                  <span>{simbol.icona}</span>
                  <span className="truncate max-w-[100px]">{simbol.nom}</span>
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* 5. Calatix Inferior: Llegenda Completa de Colors i Símbols (Spec 01 & 02) */}
      {mostrarLlegenda && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-xs flex flex-col justify-end animate-in fade-in">
          <div className="bg-[#0f1d2d] border-t-2 border-slate-700 rounded-t-3xl p-4 max-h-[80vh] flex flex-col shadow-2xl space-y-3">
            {/* Header Llegenda */}
            <div className="flex items-center justify-between border-b border-slate-800 pb-2">
              <div className="flex items-center gap-2">
                <Palette className="w-5 h-5 text-sky-400" />
                <h3 className="font-black text-sm text-white uppercase tracking-wider">
                  Llegenda Tècnica de Colors i Símbols
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setMostrarLlegenda(false)}
                className="p-1 rounded-lg text-slate-400 hover:text-white"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Filtre per Disciplina */}
            <div className="flex items-center gap-1 overflow-x-auto py-1 custom-scrollbar text-xs">
              <button
                type="button"
                onClick={() => setDisciplinaFiltre("TOTS")}
                className={`px-3 py-1 rounded-lg font-bold shrink-0 transition-all ${
                  disciplinaFiltre === "TOTS"
                    ? "bg-sky-500 text-slate-950 font-black"
                    : "bg-slate-800 text-slate-300 hover:bg-slate-700"
                }`}
              >
                Tots
              </button>
              {PALETA_DISCIPLINES.map((d) => (
                <button
                  key={d.id}
                  type="button"
                  onClick={() => setDisciplinaFiltre(d.id)}
                  className={`px-2.5 py-1 rounded-lg font-bold shrink-0 flex items-center gap-1.5 transition-all ${
                    disciplinaFiltre === d.id
                      ? "bg-sky-500 text-slate-950 font-black"
                      : "bg-slate-800 text-slate-300 hover:bg-slate-700"
                  }`}
                >
                  <span className="w-2 h-2 rounded-full" style={{ backgroundColor: d.color }} />
                  <span>{d.nom}</span>
                </button>
              ))}
            </div>

            {/* Graella de Símbols de la Llegenda */}
            <div className="overflow-y-auto space-y-2 flex-1 pr-1 custom-scrollbar">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {simbolsFiltrats.map((simbol) => {
                  const isSelected = simbolSeleccionat.id === simbol.id;
                  return (
                    <div
                      key={simbol.id}
                      onClick={() => {
                        setSimbolSeleccionat(simbol);
                        setEinaActiva("simbol");
                        setMostrarLlegenda(false);
                        mostrarNotificacio(`Símbol seleccionat: ${simbol.nom}`);
                      }}
                      className={`p-2.5 rounded-xl border flex items-center justify-between gap-3 cursor-pointer transition-all ${
                        isSelected
                          ? "bg-sky-950/60 border-sky-400 ring-1 ring-sky-400"
                          : "bg-slate-850 hover:bg-slate-800 border-slate-750"
                      }`}
                    >
                      <div className="flex items-center gap-2.5 min-w-0">
                        <div
                          className="w-8 h-8 rounded-lg flex items-center justify-center font-bold text-sm shrink-0 border border-white/20 shadow-sm"
                          style={{ backgroundColor: `${simbol.color_hex}30` }}
                        >
                          <span>{simbol.icona}</span>
                        </div>
                        <div className="min-w-0">
                          <p className="font-bold text-xs text-white truncate">{simbol.nom}</p>
                          <p className="text-[10px] text-slate-400 truncate">{simbol.descripcio}</p>
                        </div>
                      </div>
                      <span
                        className="w-3.5 h-3.5 rounded-full shrink-0 shadow-sm border border-white/30"
                        style={{ backgroundColor: simbol.color_hex }}
                      />
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Peu de la Llegenda amb garantia de traçabilitat no destructiva */}
            <div className="pt-2 border-t border-slate-800 flex items-center justify-between text-[11px] text-slate-400">
              <div className="flex items-center gap-1.5 text-emerald-400 font-semibold">
                <ShieldCheck className="w-4 h-4 shrink-0" />
                <span>Base inalterable (FR-010): El plànol font no es modifica mai.</span>
              </div>
              <button
                type="button"
                onClick={() => setMostrarLlegenda(false)}
                className="px-4 py-1.5 rounded-lg bg-sky-600 text-white font-bold text-xs"
              >
                Tancar
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 6. Modal Creació Nova Capa As-Built */}
      {modalNovaCapa && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-xs flex items-center justify-center p-4 animate-in fade-in">
          <div className="bg-[#0f1d2d] border border-slate-700 rounded-2xl max-w-sm w-full p-5 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-800 pb-2">
              <h3 className="font-black text-sm text-white flex items-center gap-1.5">
                <Layers className="w-4 h-4 text-sky-400" />
                <span>Nova Capa As-Built (FR-010)</span>
              </h3>
              <button
                type="button"
                onClick={() => setModalNovaCapa(false)}
                className="p-1 rounded text-slate-400 hover:text-white"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleCrearCapa} className="space-y-3">
              <div>
                <label className="block text-[11px] font-bold text-slate-300 uppercase tracking-wider mb-1">
                  Nom de la Capa
                </label>
                <input
                  type="text"
                  required
                  placeholder="Ex: Connexió PE-100 Polígon 4"
                  value={nomNovaCapa}
                  onChange={(e) => setNomNovaCapa(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-slate-800 border border-slate-700 text-white text-xs outline-none focus:border-sky-400 font-medium"
                />
              </div>

              <div>
                <label className="block text-[11px] font-bold text-slate-300 uppercase tracking-wider mb-1">
                  Disciplina Tècnica (Llegenda Oficial)
                </label>
                <select
                  value={disciplinaNovaCapa}
                  onChange={(e) => setDisciplinaNovaCapa(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-slate-800 border border-slate-700 text-white text-xs outline-none font-bold"
                >
                  {PALETA_DISCIPLINES.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.nom}
                    </option>
                  ))}
                </select>
              </div>

              <div className="p-2.5 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-[10px] text-emerald-300 flex items-center gap-1.5">
                <ShieldCheck className="w-4 h-4 shrink-0" />
                <span>Traçabilitat estricta: No sobreescriu el fitxer base original.</span>
              </div>

              <div className="pt-2 flex justify-end gap-2 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setModalNovaCapa(false)}
                  className="px-3 py-2 rounded-xl bg-slate-800 text-slate-300 text-xs font-semibold hover:bg-slate-750"
                >
                  Cancel·lar
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 rounded-xl bg-sky-600 hover:bg-sky-500 text-white text-xs font-bold shadow-md"
                >
                  Crear Capa
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* 7. Diàleg davant d'obra o capa tancada (Spec 017 RF-13.1) */}
      {mostrarDialegCapaTancada && (
        <div className="fixed inset-0 bg-black/75 backdrop-blur-xs flex items-center justify-center p-4 z-50 animate-in fade-in">
          <div className="bg-[#0f1d2d] border border-amber-500/40 p-5 rounded-2xl max-w-xs w-full text-center shadow-2xl space-y-4">
            <div className="w-12 h-12 rounded-full bg-amber-500/20 text-amber-400 flex items-center justify-center mx-auto border border-amber-500/40">
              <Lock className="w-6 h-6" />
            </div>
            <h3 className="text-sm font-black text-white">
              Capa tancada, vols crear una capa nova?
            </h3>
            <p className="text-xs text-slate-300 leading-relaxed">
              Aquesta ordre de treball o capa està tancada i facturada. Per a respectar la inalterabilitat del SIF, cal crear una capa d&apos;addenda activa.
            </p>
            <div className="flex gap-2 pt-2">
              <button
                type="button"
                onClick={() => {
                  setMostrarDialegCapaTancada(false);
                  setModalNovaCapa(true);
                }}
                className="flex-1 py-2.5 bg-sky-600 hover:bg-sky-500 text-white text-xs font-bold rounded-xl flex items-center justify-center gap-1 shadow-md"
              >
                <Plus className="w-4 h-4" />
                <span>Crear Capa Nova</span>
              </button>
              <button
                type="button"
                onClick={() => {
                  setMostrarDialegCapaTancada(false);
                  setPendentClickCoords(null);
                }}
                className="px-3 py-2.5 bg-slate-800 text-slate-300 text-xs font-semibold rounded-xl"
              >
                Cancel·lar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
