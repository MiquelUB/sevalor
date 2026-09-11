"use client";

import React, { useState, useMemo } from "react";
import {
  Layers,
  Folder,
  FolderPlus,
  FileText,
  UploadCloud,
  Search,
  Lock,
  Unlock,
  Eye,
  EyeOff,
  Compass,
  MapPin,
  Download,
  Printer,
  Share2,
  AlertTriangle,
  CheckCircle2,
  Sliders,
  ZoomIn,
  ZoomOut,
  Maximize2,
  FileCode,
  Shield,
  ShieldAlert,
  Info,
  X,
  Plus,
  PenTool,
  Move,
  Square,
  Slash,
  Maximize,
  Check,
  ChevronRight,
  ChevronDown,
  Activity,
  Calendar,
  User,
  Radio,
  Building,
  Sparkles,
} from "lucide-react";
import { useGestio } from "@/lib/gestio-context";

// Tipus de dades del domini Spec 010
interface CarpetaUI {
  id: string;
  nom: string;
  categoria: "CLIENTS" | "INFRAESTRUCTURA_COMUNITARIA" | "MUNICIPAL_TERRITORIAL";
  descripcio?: string;
  municipi?: string;
  num_planols: number;
}

interface CapaVectorialUI {
  id: string;
  nom: string;
  disciplina: "AIGUA_REG" | "ELECTRICITAT" | "OBRA_CIVIL" | "INCIDENCIA_PERICIAL";
  es_immutable: boolean;
  color_hex: string;
  gruix_linia: number;
  opacitat_percent: number;
  visible: boolean;
  version_id: number;
  ordre_treball_ref?: string;
}

interface PlanolUI {
  id: string;
  carpeta_id: string;
  titol: string;
  codi_referencia: string;
  tipus_fitxer: "DXF" | "GEOJSON" | "KML" | "PDF" | "TIFF" | "PNG";
  es_georeferenciat: boolean;
  fitxer_path: string;
  mida_mb: number;
  projeccio: string;
  client_nom?: string;
  data_actualitzacio: string;
  capes: CapaVectorialUI[];
}

export default function GestioPlanolsPage() {
  const { rolActiu } = useGestio();
  const esSecretaria = rolActiu === "SECRETARIA";

  // Estat del cercador i carpetes
  const [cercaText, setCercaText] = useState("");
  const [categoriaSeleccionada, setCategoriaSeleccionada] = useState<string>("TOTS");
  const [carpetaActivaId, setCarpetaActivaId] = useState<string>("c-1");

  // Estat de la llista de carpetes (Dia 0 / Dades inicials representatives)
  const [carpetes, setCarpetes] = useState<CarpetaUI[]>([
    {
      id: "c-1",
      nom: "Comunitat de Regants Segarra-Garrigues (Sector 4)",
      categoria: "INFRAESTRUCTURA_COMUNITARIA",
      municipi: "Arbeca",
      descripcio: "Canonades d'alta pressió PE-100 i xarxa d'hidrants comunitaris",
      num_planols: 2,
    },
    {
      id: "c-2",
      nom: "Finca Mas Salagros - Instal·lació Reg Goter",
      categoria: "CLIENTS",
      municipi: "Vallromanes",
      descripcio: "Distribució parcel·lària sectoritzada i bombes elèctriques",
      num_planols: 1,
    },
    {
      id: "c-3",
      nom: "Pla Municipal Xarxa Hídrica Rural",
      categoria: "MUNICIPAL_TERRITORIAL",
      municipi: "Sant Cugat Sesgarrigues",
      descripcio: "Connexions d'abastament rústic municipal i servituds de pas",
      num_planols: 1,
    },
  ]);

  // Estat de plànols base
  const [planols, setPlanols] = useState<PlanolUI[]>([
    {
      id: "pln-01",
      carpeta_id: "c-1",
      titol: "Traçat Xarxa Primària Polígon 14 (PE-100 Ø110)",
      codi_referencia: "PLN-2026-SG04",
      tipus_fitxer: "DXF",
      es_georeferenciat: true,
      fitxer_path: "/docs/empresa/planols/sg_pol14.dxf",
      mida_mb: 8.4,
      projeccio: "ETRS89 / UTM 31N (WGS84)",
      client_nom: "Comunitat Regants Segarra-Garrigues",
      data_actualitzacio: "08/09/2026",
      capes: [
        {
          id: "cap-1",
          nom: "Conducció Principal PE-100 Ø110",
          disciplina: "AIGUA_REG",
          es_immutable: false,
          color_hex: "#2563eb",
          gruix_linia: 3,
          opacitat_percent: 100,
          visible: true,
          version_id: 1,
        },
        {
          id: "cap-2",
          nom: "Hidrants i vàlvules de sectorització",
          disciplina: "AIGUA_REG",
          es_immutable: false,
          color_hex: "#0284c7",
          gruix_linia: 2,
          opacitat_percent: 100,
          visible: true,
          version_id: 1,
        },
        {
          id: "cap-3",
          nom: "Escomesa Masia Vella (OT-089 Tancada i Facturada)",
          disciplina: "OBRA_CIVIL",
          es_immutable: true, // Capa bloquejada pericialment (RF-12, EDGE-05)
          color_hex: "#dc2626",
          gruix_linia: 2,
          opacitat_percent: 75,
          visible: true,
          version_id: 2,
          ordre_treball_ref: "",
        },
      ],
    },
    {
      id: "pln-02",
      carpeta_id: "c-1",
      titol: "Esquema Unifilar Quadre Bombament QB-02",
      codi_referencia: "PLN-2026-QB02",
      tipus_fitxer: "PDF",
      es_georeferenciat: false,
      fitxer_path: "/docs/empresa/planols/unifilar_qb02.pdf",
      mida_mb: 2.1,
      projeccio: "Esquema No Georeferenciat (CAD 2D)",
      client_nom: "Comunitat Regants Segarra-Garrigues",
      data_actualitzacio: "05/09/2026",
      capes: [
        {
          id: "cap-4",
          nom: "Línia d'Escomesa 400V Trifàsica",
          disciplina: "ELECTRICITAT",
          es_immutable: true,
          color_hex: "#eab308",
          gruix_linia: 2,
          opacitat_percent: 100,
          visible: true,
          version_id: 1,
        },
      ],
    },
    {
      id: "pln-03",
      carpeta_id: "c-2",
      titol: "Delineació Sectors A i B Finca Mas Salagros",
      codi_referencia: "PLN-2026-MS01",
      tipus_fitxer: "GEOJSON",
      es_georeferenciat: true,
      fitxer_path: "/docs/empresa/planols/salagros_cad.geojson",
      mida_mb: 4.2,
      projeccio: "WGS84",
      client_nom: "Mas Salagros Ecoresort",
      data_actualitzacio: "02/09/2026",
      capes: [
        {
          id: "cap-5",
          nom: "Tub secundari reg goter Ø32",
          disciplina: "AIGUA_REG",
          es_immutable: false,
          color_hex: "#10b981",
          gruix_linia: 2,
          opacitat_percent: 90,
          visible: true,
          version_id: 1,
        },
      ],
    },
    {
      id: "pln-04",
      carpeta_id: "c-3",
      titol: "Plànol Topogràfic Cadastral Polígon 3",
      codi_referencia: "PLN-2026-MUN03",
      tipus_fitxer: "TIFF",
      es_georeferenciat: false,
      fitxer_path: "/docs/empresa/planols/topografic_p3.tiff",
      mida_mb: 14.8,
      projeccio: "Topogràfic 1:1000",
      client_nom: "Ajuntament Sant Cugat Sesgarrigues",
      data_actualitzacio: "28/08/2026",
      capes: [],
    },
  ]);

  const [planolActiuId, setPlanolActiuId] = useState<string>("pln-01");

  // Estat de l'eina activa de delineació
  const [einaActiva, setEinaActiva] = useState<"PAN" | "LINE" | "POLYGON" | "COTA" | "VALVULA" | "HIDRANT" | "PIN">("PAN");
  const [opacitatBaseMap, setOpacitatBaseMap] = useState<number>(100);
  const [zoomNivell, setZoomNivell] = useState<number>(100);
  const [mostrarSigpac, setMostrarSigpac] = useState<boolean>(true);

  // Modals
  const [modalCaixetiObert, setModalCaixetiObert] = useState<boolean>(false);
  const [modalPujarObert, setModalPujarObert] = useState<boolean>(false);
  const [modalNovaCarpetaObert, setModalNovaCarpetaObert] = useState<boolean>(false);
  const [alertaImmutabilitat, setAlertaImmutabilitat] = useState<string | null>(null);
  const [missatgeExit, setMissatgeExit] = useState<string | null>(null);

  // Formulari Caixetí Homologat
  const [caixetiConfig, setCaixetiConfig] = useState({
    escala: "1:500",
    autorTecnic: "Carles Vives Roca (Enginyer Col·legiat 4819)",
    observacionsLegals: "Projecte tècnic d'obra hidràulica i reg. Propietat de SEVALOR SL. Queda prohibida la reproducció sense autorització expressa.",
    incloureLlegenda: true,
  });

  // Plànol actualment seleccionat
  const planolActiu = useMemo(() => {
    return planols.find((p) => p.id === planolActiuId) || null;
  }, [planols, planolActiuId]);

  // Filtrar plànols de la carpeta activa
  const planolsFiltrats = useMemo(() => {
    return planols.filter((p) => {
      const perCarpeta = p.carpeta_id === carpetaActivaId;
      const perCerca =
        !cercaText ||
        p.titol.toLowerCase().includes(cercaText.toLowerCase()) ||
        p.codi_referencia.toLowerCase().includes(cercaText.toLowerCase());
      return perCarpeta && perCerca;
    });
  }, [planols, carpetaActivaId, cercaText]);

  // Carpeta activa
  const carpetaActiva = useMemo(() => {
    return carpetes.find((c) => c.id === carpetaActivaId) || null;
  }, [carpetes, carpetaActivaId]);

  // Manejador per commutar la visibilitat d'una capa
  const toggleVisibilitatCapa = (capaId: string) => {
    if (!planolActiu) return;
    setPlanols((prev) =>
      prev.map((p) => {
        if (p.id !== planolActiu.id) return p;
        return {
          ...p,
          capes: p.capes.map((c) => {
            if (c.id !== capaId) return c;
            return { ...c, visible: !c.visible };
          }),
        };
      })
    );
  };

  // Manejador d'intent d'edició sobre una capa (comprovació d'immutabilitat)
  const handleIntentEdicioCapa = (capa: CapaVectorialUI) => {
    if (capa.es_immutable) {
      setAlertaImmutabilitat(
        `Capa "${capa.nom}" bloquejada per traçabilitat pericial d'obra tancada (${capa.ordre_treball_ref || "OT Facturada"}). Segons la norma ISO i Spec 010 RF-12 / EDGE-05, no es permet cap modificació un cop segellat el tancament econòmic.`
      );
      return;
    }
    if (esSecretaria) {
      setAlertaImmutabilitat(
        "Veto de Secretaria: El vostre rol té accés exclusiu de consulta i descàrrega documental. La delineació de xarxes està reservada a Enginyeria i Direcció Tècnica."
      );
      return;
    }
    setMissatgeExit(`Capa "${capa.nom}" seleccionada per a delineació activa.`);
    setTimeout(() => setMissatgeExit(null), 3000);
  };

  // Acció d'exportació de PDF amb Caixetí Homologat
  const handleExportarPdfOficial = () => {
    setMissatgeExit("Dossier PDF oficial amb Caixetí Industrial generat correctament sota infraestructura sobirana Hetzner Alemanya. Sense codis QR d'eines.");
    setModalCaixetiObert(false);
    setTimeout(() => setMissatgeExit(null), 4000);
  };

  // Acció d'exportació CAD GeoJSON per a maquinària
  const handleExportarCad = () => {
    setMissatgeExit("Fitxer CAD GeoJSON (WGS84) exportat correctament per a maquinària de reg.");
    setTimeout(() => setMissatgeExit(null), 3500);
  };

  return (
    <div className="flex flex-col h-[calc(100vh-3.5rem)] bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 overflow-hidden font-sans">
      {/* 1. BARRA SUPERIOR DE CONTEXT & ACCIONS DE DELINEACIÓ */}
      <div className="h-14 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 px-4 flex items-center justify-between shrink-0 z-20">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-indigo-50 dark:bg-indigo-950/60 border border-indigo-200 dark:border-indigo-800 text-indigo-600 dark:text-indigo-400">
            <Layers className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-base font-bold text-slate-900 dark:text-slate-100 leading-none">
                Delineació de Plànols GIS & Caixetí Oficial
              </h1>
              <span className="text-[10px] font-black uppercase tracking-wider px-2 py-0.5 rounded bg-emerald-100 dark:bg-emerald-950/60 border border-emerald-300 dark:border-emerald-800 text-emerald-800 dark:text-emerald-400">
                WGS84 • ETRS89
              </span>
              <span className="text-[10px] font-black uppercase tracking-wider px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 border border-slate-300 dark:border-slate-700">
                Hetzner Alemanya
              </span>
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5 truncate max-w-xl">
              {carpetaActiva?.nom} &rsaquo; {planolActiu ? planolActiu.titol : "Seleccioneu un plànol"}
            </p>
          </div>
        </div>

        {/* Accions principals: Caixetí PDF, CAD, Pujada */}
        <div className="flex items-center gap-2">
          {esSecretaria && (
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-amber-50 dark:bg-amber-950/40 border border-amber-300 dark:border-amber-800 text-amber-800 dark:text-amber-400 text-xs font-medium">
              <ShieldAlert className="w-3.5 h-3.5" />
              <span>Mode Consulta (Veto Secretaria)</span>
            </div>
          )}

          <button
            onClick={handleExportarCad}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 hover:bg-slate-100 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 transition shadow-sm"
          >
            <FileCode className="w-4 h-4 text-sky-600 dark:text-sky-400" />
            <span>Exportar CAD (WGS84)</span>
          </button>

          <button
            onClick={() => setModalCaixetiObert(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white transition shadow-sm"
          >
            <Printer className="w-4 h-4" />
            <span>Caixetí Oficial PDF</span>
          </button>

          <button
            onClick={() => {
              if (esSecretaria) {
                setAlertaImmutabilitat("Veto de Secretaria: No teniu autorització per carregar fitxers tècnics o CAD.");
                return;
              }
              setModalPujarObert(true);
            }}
            disabled={esSecretaria}
            className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold rounded-lg transition shadow-sm ${
              esSecretaria
                ? "bg-slate-200 dark:bg-slate-800 text-slate-400 cursor-not-allowed border border-slate-300 dark:border-slate-700"
                : "bg-emerald-600 hover:bg-emerald-700 text-white"
            }`}
          >
            <UploadCloud className="w-4 h-4" />
            <span>Carregar Fitxer (&le; 50MB)</span>
          </button>
        </div>
      </div>

      {/* 2. ZONA DE TREBALL PRINCIPAL: ARBRE LATERAL + VISOR HÍBRID + PANELL DE CAPES */}
      <div className="flex-1 flex overflow-hidden">
        {/* BARRA LATERAL ESQUERRA: BIBLIOTECA DE PLÀNOLS & CARPETES */}
        <aside className="w-80 bg-white dark:bg-slate-900 border-r border-slate-200 dark:border-slate-800 flex flex-col shrink-0 z-10">
          {/* Cercador reactiu < 200 ms */}
          <div className="p-3 border-b border-slate-200 dark:border-slate-800">
            <div className="relative">
              <Search className="w-4 h-4 absolute left-2.5 top-2.5 text-slate-400" />
              <input
                type="text"
                value={cercaText}
                onChange={(e) => setCercaText(e.target.value)}
                placeholder="Cercar plànols o codis..."
                className="w-full pl-8 pr-3 py-1.5 text-xs rounded-md bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-800 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />
            </div>

            {/* Selector de Categoria de Carpeta */}
            <div className="flex items-center gap-1 mt-2">
              {[
                { id: "TOTS", label: "Tots" },
                { id: "CLIENTS", label: "Clients" },
                { id: "INFRAESTRUCTURA_COMUNITARIA", label: "Comunitats" },
                { id: "MUNICIPAL_TERRITORIAL", label: "Municipal" },
              ].map((cat) => (
                <button
                  key={cat.id}
                  onClick={() => setCategoriaSeleccionada(cat.id)}
                  className={`text-[11px] font-semibold px-2 py-0.5 rounded transition ${
                    categoriaSeleccionada === cat.id
                      ? "bg-indigo-100 dark:bg-indigo-950 text-indigo-700 dark:text-indigo-300 font-bold"
                      : "text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
                  }`}
                >
                  {cat.label}
                </button>
              ))}
            </div>
          </div>

          {/* Arbre de Carpetes */}
          <div className="flex-1 overflow-y-auto p-2 space-y-1">
            <div className="flex items-center justify-between px-2 py-1 text-[11px] font-bold text-slate-400 uppercase tracking-wider">
              <span>Carpetes de Projecte</span>
              <button
                onClick={() => {
                  if (esSecretaria) {
                    setAlertaImmutabilitat("Veto Secretaria: La creació de carpetes de projecte està restringida.");
                    return;
                  }
                  setModalNovaCarpetaObert(true);
                }}
                className="text-indigo-600 dark:text-indigo-400 hover:underline flex items-center gap-0.5 normal-case"
              >
                <FolderPlus className="w-3.5 h-3.5" />
                <span>Nova</span>
              </button>
            </div>

            {carpetes
              .filter((c) => categoriaSeleccionada === "TOTS" || c.categoria === categoriaSeleccionada)
              .map((c) => {
                const activa = c.id === carpetaActivaId;
                return (
                  <button
                    key={c.id}
                    onClick={() => setCarpetaActivaId(c.id)}
                    className={`w-full text-left p-2 rounded-lg transition flex items-start gap-2.5 ${
                      activa
                        ? "bg-indigo-50 dark:bg-indigo-950/60 border border-indigo-200 dark:border-indigo-800"
                        : "hover:bg-slate-100 dark:hover:bg-slate-800/60 text-slate-700 dark:text-slate-300"
                    }`}
                  >
                    <Folder
                      className={`w-4 h-4 shrink-0 mt-0.5 ${
                        activa ? "text-indigo-600 dark:text-indigo-400 fill-indigo-600/20" : "text-slate-400"
                      }`}
                    />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold truncate text-slate-800 dark:text-slate-100">
                          {c.nom}
                        </span>
                        <span className="text-[10px] px-1.5 py-0.2 rounded bg-slate-200 dark:bg-slate-800 text-slate-600 dark:text-slate-400 font-mono">
                          {c.num_planols}
                        </span>
                      </div>
                      <div className="text-[11px] text-slate-500 dark:text-slate-400 truncate">
                        {c.municipi ? `${c.municipi} • ` : ""}
                        {c.categoria === "INFRAESTRUCTURA_COMUNITARIA"
                          ? "Comunitat Reg"
                          : c.categoria === "CLIENTS"
                          ? "Finca Client"
                          : "Municipal"}
                      </div>
                    </div>
                  </button>
                );
              })}

            {/* Llistat de Plànols de la Carpeta Seleccionada */}
            <div className="pt-3">
              <div className="px-2 py-1 text-[11px] font-bold text-slate-400 uppercase tracking-wider flex items-center justify-between">
                <span>Plànols a la carpeta</span>
                <span className="text-[10px] font-mono">{planolsFiltrats.length} arxius</span>
              </div>

              {planolsFiltrats.length === 0 ? (
                <div className="p-4 text-center rounded-lg border border-dashed border-slate-200 dark:border-slate-800 mt-1">
                  <FileText className="w-8 h-8 text-slate-300 dark:text-slate-700 mx-auto mb-1.5" />
                  <p className="text-xs font-semibold text-slate-600 dark:text-slate-400">
                    No hi ha cap plànol registrat
                  </p>
                  <p className="text-[11px] text-slate-400 mt-0.5">
                    Carregueu un fitxer CAD/GIS o PDF per començar a delinear.
                  </p>
                </div>
              ) : (
                <div className="space-y-1 mt-1">
                  {planolsFiltrats.map((p) => {
                    const esSeleccionat = p.id === planolActiuId;
                    return (
                      <div
                        key={p.id}
                        onClick={() => setPlanolActiuId(p.id)}
                        className={`p-2 rounded-lg cursor-pointer transition border text-left ${
                          esSeleccionat
                            ? "bg-white dark:bg-slate-800 border-indigo-500 shadow-sm ring-1 ring-indigo-500/20"
                            : "bg-transparent border-transparent hover:bg-slate-100 dark:hover:bg-slate-800/40"
                        }`}
                      >
                        <div className="flex items-start justify-between gap-1">
                          <span className="text-xs font-bold text-slate-900 dark:text-slate-100 line-clamp-1">
                            {p.titol}
                          </span>
                          <span
                            className={`text-[9px] font-extrabold px-1 rounded uppercase tracking-wider ${
                              p.es_georeferenciat
                                ? "bg-emerald-100 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300"
                                : "bg-amber-100 dark:bg-amber-950 text-amber-700 dark:text-amber-300"
                            }`}
                          >
                            {p.tipus_fitxer}
                          </span>
                        </div>
                        <div className="flex items-center justify-between mt-1 text-[11px] text-slate-500 dark:text-slate-400">
                          <span className="font-mono text-[10px]">{p.codi_referencia}</span>
                          <span>{p.mida_mb} MB</span>
                        </div>
                        <div className="flex items-center gap-2 mt-1 text-[10px] text-slate-400">
                          <span>{p.capes.length} capes</span>
                          {p.capes.some((c) => c.es_immutable) && (
                            <span className="flex items-center gap-0.5 text-rose-500 font-bold">
                              <Lock className="w-2.5 h-2.5" /> Immutable
                            </span>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </aside>

        {/* VISOR HÍBRID CENTRAL: MAPA WGS84 O VISOR DOCUMENTAL */}
        <main className="flex-1 flex flex-col relative bg-slate-900 overflow-hidden">
          {/* BARRA D'EINES DE DELINEACIÓ VECTORIAL (TOOLBAR FLOTANT) */}
          <div className="absolute top-3 left-3 z-30 flex items-center bg-white/95 dark:bg-slate-900/95 backdrop-blur-md rounded-xl p-1.5 shadow-lg border border-slate-200 dark:border-slate-800 gap-1">
            <button
              onClick={() => setEinaActiva("PAN")}
              title="Moure / Desplaçar visor (Pan)"
              className={`p-2 rounded-lg transition ${
                einaActiva === "PAN"
                  ? "bg-indigo-600 text-white shadow"
                  : "text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800"
              }`}
            >
              <Move className="w-4 h-4" />
            </button>

            <div className="w-px h-5 bg-slate-200 dark:bg-slate-800 mx-0.5" />

            <button
              onClick={() => {
                if (esSecretaria) {
                  setAlertaImmutabilitat("Veto Secretaria: La delineació està reservada a Enginyeria.");
                  return;
                }
                setEinaActiva("LINE");
              }}
              title="Delinear Polilínia (Canonada PE-100)"
              className={`p-2 rounded-lg transition ${
                einaActiva === "LINE"
                  ? "bg-indigo-600 text-white shadow"
                  : esSecretaria
                  ? "text-slate-300 dark:text-slate-600 cursor-not-allowed"
                  : "text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800"
              }`}
            >
              <Slash className="w-4 h-4" />
            </button>

            <button
              onClick={() => {
                if (esSecretaria) {
                  setAlertaImmutabilitat("Veto Secretaria: La delineació està reservada a Enginyeria.");
                  return;
                }
                setEinaActiva("POLYGON");
              }}
              title="Delinear Polígon (Parcel·la SIGPAC / Sector Reg)"
              className={`p-2 rounded-lg transition ${
                einaActiva === "POLYGON"
                  ? "bg-indigo-600 text-white shadow"
                  : esSecretaria
                  ? "text-slate-300 dark:text-slate-600 cursor-not-allowed"
                  : "text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800"
              }`}
            >
              <Square className="w-4 h-4" />
            </button>

            <button
              onClick={() => {
                if (esSecretaria) {
                  setAlertaImmutabilitat("Veto Secretaria: La delineació està reservada a Enginyeria.");
                  return;
                }
                setEinaActiva("COTA");
              }}
              title="Afegir Cota Mètrica Ancorada (Longitud)"
              className={`p-2 rounded-lg transition ${
                einaActiva === "COTA"
                  ? "bg-indigo-600 text-white shadow"
                  : esSecretaria
                  ? "text-slate-300 dark:text-slate-600 cursor-not-allowed"
                  : "text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800"
              }`}
            >
              <Maximize className="w-4 h-4" />
            </button>

            <div className="w-px h-5 bg-slate-200 dark:bg-slate-800 mx-0.5" />

            {/* Simbologia Normalitzada */}
            <button
              onClick={() => {
                if (esSecretaria) {
                  setAlertaImmutabilitat("Veto Secretaria: La col·locació de símbols està reservada a Enginyeria.");
                  return;
                }
                setEinaActiva("VALVULA");
              }}
              title="Símbol: Vàlvula Reguladora / Ventosa"
              className={`p-2 rounded-lg transition ${
                einaActiva === "VALVULA"
                  ? "bg-indigo-600 text-white shadow"
                  : esSecretaria
                  ? "text-slate-300 dark:text-slate-600 cursor-not-allowed"
                  : "text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800"
              }`}
            >
              <Activity className="w-4 h-4 text-emerald-500" />
            </button>

            <button
              onClick={() => {
                if (esSecretaria) {
                  setAlertaImmutabilitat("Veto Secretaria: La col·locació de símbols està reservada a Enginyeria.");
                  return;
                }
                setEinaActiva("HIDRANT");
              }}
              title="Símbol: Hidrant d'Alta Pressió"
              className={`p-2 rounded-lg transition ${
                einaActiva === "HIDRANT"
                  ? "bg-indigo-600 text-white shadow"
                  : esSecretaria
                  ? "text-slate-300 dark:text-slate-600 cursor-not-allowed"
                  : "text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800"
              }`}
            >
              <Radio className="w-4 h-4 text-sky-500" />
            </button>

            <button
              onClick={() => {
                if (esSecretaria) {
                  setAlertaImmutabilitat("Veto Secretaria: El registre de PINs està reservat a personal tècnic.");
                  return;
                }
                setEinaActiva("PIN");
              }}
              title="PIN d'Incidència Georeferenciat"
              className={`p-2 rounded-lg transition ${
                einaActiva === "PIN"
                  ? "bg-rose-600 text-white shadow"
                  : esSecretaria
                  ? "text-slate-300 dark:text-slate-600 cursor-not-allowed"
                  : "text-rose-500 hover:bg-rose-50 dark:hover:bg-rose-950/40"
              }`}
            >
              <MapPin className="w-4 h-4" />
            </button>
          </div>

          {/* CONTROLS DE ZOOM & OPACITAT (DRETA SUPERIOR) */}
          <div className="absolute top-3 right-3 z-30 flex items-center bg-white/95 dark:bg-slate-900/95 backdrop-blur-md rounded-xl p-1.5 shadow-lg border border-slate-200 dark:border-slate-800 gap-2">
            <div className="flex items-center gap-1.5 px-2">
              <Sliders className="w-3.5 h-3.5 text-slate-400" />
              <span className="text-[11px] font-semibold text-slate-600 dark:text-slate-300">
                Ortofoto:
              </span>
              <input
                type="range"
                min="0"
                max="100"
                value={opacitatBaseMap}
                onChange={(e) => setOpacitatBaseMap(parseInt(e.target.value))}
                className="w-16 h-1 bg-slate-200 dark:bg-slate-700 rounded-lg accent-indigo-600 cursor-pointer"
              />
              <span className="text-[10px] font-mono text-slate-400 w-7">{opacitatBaseMap}%</span>
            </div>

            <div className="w-px h-5 bg-slate-200 dark:bg-slate-800" />

            <button
              onClick={() => setMostrarSigpac((prev) => !prev)}
              className={`px-2 py-1 text-xs font-semibold rounded-md border transition ${
                mostrarSigpac
                  ? "bg-amber-50 dark:bg-amber-950/60 border-amber-300 dark:border-amber-800 text-amber-800 dark:text-amber-300"
                  : "bg-slate-100 dark:bg-slate-800 border-slate-200 dark:border-slate-700 text-slate-500"
              }`}
            >
              SIGPAC {mostrarSigpac ? "ON" : "OFF"}
            </button>

            <div className="w-px h-5 bg-slate-200 dark:bg-slate-800" />

            <div className="flex items-center gap-1">
              <button
                onClick={() => setZoomNivell((prev) => Math.max(50, prev - 15))}
                className="p-1 rounded hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-300"
              >
                <ZoomOut className="w-4 h-4" />
              </button>
              <span className="text-xs font-mono text-slate-500 w-10 text-center">{zoomNivell}%</span>
              <button
                onClick={() => setZoomNivell((prev) => Math.min(250, prev + 15))}
                className="p-1 rounded hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-300"
              >
                <ZoomIn className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* CANVAS / SUPERFÍCIE VISUAL DEL PLÀNOL (WGS84 VS DOCUMENTAL) */}
          <div className="flex-1 w-full h-full relative overflow-hidden flex items-center justify-center select-none">
            {planolActiu?.es_georeferenciat ? (
              /* VISOR VECTORIAL WGS84 AMB CAPES DE REG */
              <div
                className="w-full h-full relative flex items-center justify-center transition-transform duration-100"
                style={{
                  transform: `scale(${zoomNivell / 100})`,
                }}
              >
                {/* 1. Base Ortofoto PNOA / Satèl·lit */}
                <div
                  className="absolute inset-0 bg-[#1e293b] opacity-100 flex items-center justify-center overflow-hidden"
                  style={{ opacity: opacitatBaseMap / 100 }}
                >
                  <svg className="w-full h-full opacity-30" xmlns="http://www.w3.org/2000/svg">
                    <defs>
                      <pattern id="grid" width="60" height="60" patternUnits="userSpaceOnUse">
                        <path d="M 60 0 L 0 0 0 60" fill="none" stroke="#475569" strokeWidth="0.5" />
                      </pattern>
                    </defs>
                    <rect width="100%" height="100%" fill="url(#grid)" />
                  </svg>
                </div>

                {/* 2. Parcel·les Cadastrals SIGPAC (Groc/Ambre discontinu) */}
                {mostrarSigpac && (
                  <svg className="absolute inset-0 w-full h-full pointer-events-none">
                    <polygon
                      points="180,120 620,90 740,380 410,480 140,320"
                      fill="rgba(245, 158, 11, 0.05)"
                      stroke="#f59e0b"
                      strokeWidth="1.5"
                      strokeDasharray="6,4"
                    />
                    <text x="380" y="270" fill="#f59e0b" fontSize="11" fontWeight="bold" opacity="0.8">
                      SIGPAC: Polígon 14 • Parcel·la 88 (Oliveres de Reg)
                    </text>
                  </svg>
                )}

                {/* 3. Render de Capes Vectorials (Canonades, Cotes, Simbologia) */}
                <svg className="absolute inset-0 w-full h-full pointer-events-auto">
                  {/* Capa 1: Canonada Principal PE-100 Ø110 (Blau) */}
                  {planolActiu.capes.find((c) => c.id === "cap-1")?.visible && (
                    <g
                      onClick={() =>
                        handleIntentEdicioCapa(planolActiu.capes.find((c) => c.id === "cap-1")!)
                      }
                      className="cursor-pointer hover:opacity-80 transition"
                    >
                      <polyline
                        points="160,340 320,310 510,270 690,190"
                        fill="none"
                        stroke="#2563eb"
                        strokeWidth="4"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                      {/* Cota ancorada inalterable */}
                      <text x="390" y="280" fill="#60a5fa" fontSize="10" fontWeight="bold" className="font-mono">
                        PE-100 Ø110 PN16 (Longitud: 342.5 m)
                      </text>
                    </g>
                  )}

                  {/* Capa 2: Hidrants i Vàlvules (Cian) */}
                  {planolActiu.capes.find((c) => c.id === "cap-2")?.visible && (
                    <g
                      onClick={() =>
                        handleIntentEdicioCapa(planolActiu.capes.find((c) => c.id === "cap-2")!)
                      }
                      className="cursor-pointer hover:opacity-80 transition"
                    >
                      {/* Vàlvula reguladora 1 */}
                      <circle cx="320" cy="310" r="7" fill="#0284c7" stroke="#ffffff" strokeWidth="2" />
                      <text x="332" y="314" fill="#38bdf8" fontSize="10" fontWeight="bold">
                        VR-01 (63mm)
                      </text>

                      {/* Hidrant d'alta pressió H-04 */}
                      <rect x="503" y="263" width="14" height="14" fill="#0284c7" stroke="#ffffff" strokeWidth="2" rx="2" />
                      <text x="522" y="274" fill="#38bdf8" fontSize="10" fontWeight="bold">
                        Hidrant H-04 (16 bar)
                      </text>
                    </g>
                  )}

                  {/* Capa 3: Escomesa Masia Vella (IMMUTABLE - Vermell) */}
                  {planolActiu.capes.find((c) => c.id === "cap-3")?.visible && (
                    <g
                      onClick={() =>
                        handleIntentEdicioCapa(planolActiu.capes.find((c) => c.id === "cap-3")!)
                      }
                      className="cursor-pointer hover:opacity-80 transition"
                    >
                      <polyline
                        points="510,270 540,360 620,410"
                        fill="none"
                        stroke="#dc2626"
                        strokeWidth="3"
                        strokeDasharray="4,3"
                      />
                      {/* Símbol de Bloqueig Pericial */}
                      <circle cx="540" cy="360" r="6" fill="#dc2626" stroke="#ffffff" strokeWidth="1.5" />
                      <text x="552" y="364" fill="#f87171" fontSize="10" fontWeight="bold">
                        [IMMUTABLE OT-089] Escomesa 63mm
                      </text>
                    </g>
                  )}

                  {/* Pin d'Incidència Geolocalitzada */}
                  <g className="cursor-pointer">
                    <circle cx="320" cy="310" r="14" fill="rgba(239, 68, 68, 0.25)" className="animate-ping" />
                    <circle cx="320" cy="310" r="4" fill="#ef4444" />
                  </g>
                </svg>

                {/* Rosa dels vents i escala gràfica a cantonada inferior dreta */}
                <div className="absolute bottom-4 right-4 bg-slate-900/90 border border-slate-700 p-2.5 rounded-lg text-white backdrop-blur-md shadow-xl flex items-center gap-3 select-none">
                  <div className="flex flex-col items-center">
                    <Compass className="w-5 h-5 text-indigo-400" />
                    <span className="text-[9px] font-black text-slate-300">N</span>
                  </div>
                  <div className="w-px h-6 bg-slate-700" />
                  <div>
                    <div className="w-24 h-1.5 bg-white border border-slate-900 flex">
                      <div className="w-1/2 h-full bg-slate-900" />
                      <div className="w-1/2 h-full bg-white" />
                    </div>
                    <div className="flex justify-between text-[9px] font-mono text-slate-300 mt-0.5">
                      <span>0m</span>
                      <span>25m</span>
                      <span>50m</span>
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              /* VISOR DOCUMENTAL NO GEOREFERENCIAT (UNIFILAR / TIFF / PDF) */
              <div className="w-full h-full flex flex-col items-center justify-center p-8 bg-slate-800">
                <div className="max-w-2xl w-full bg-white dark:bg-slate-900 rounded-xl p-6 shadow-2xl border border-slate-700 text-center">
                  <FileText className="w-16 h-16 text-indigo-500 mx-auto mb-3" />
                  <h3 className="text-base font-bold text-slate-900 dark:text-slate-100">
                    Visor Documental d&apos;Alta Resolució (Esquema Unifilar)
                  </h3>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 max-w-md mx-auto">
                    Aquest document tècnic no té projecció espacial WGS84 directa. Es processa en espai vectorial CAD 2D unifilar independent sota Hetzner sobirà.
                  </p>

                  <div className="mt-4 p-3 rounded-lg bg-slate-100 dark:bg-slate-800 text-left font-mono text-xs text-slate-700 dark:text-slate-300 space-y-1">
                    <div>Fitxer: {planolActiu?.fitxer_path}</div>
                    <div>Codi referència: {planolActiu?.codi_referencia}</div>
                    <div>Projecció: {planolActiu?.projeccio}</div>
                  </div>

                  <div className="mt-5 flex justify-center gap-3">
                    <button
                      onClick={() => setModalCaixetiObert(true)}
                      className="px-4 py-2 text-xs font-bold rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white transition flex items-center gap-2"
                    >
                      <Printer className="w-4 h-4" />
                      <span>Generar Caixetí Industrial</span>
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        </main>

        {/* PANELL FLOTANT DRET: GESTIÓ DE CAPES VECTORIALS & IMMUTABILITAT */}
        <aside className="w-72 bg-white dark:bg-slate-900 border-l border-slate-200 dark:border-slate-800 flex flex-col shrink-0 z-10">
          <div className="p-3 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Layers className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
              <span className="text-xs font-bold text-slate-900 dark:text-slate-100">
                Capes de l&apos;Obra
              </span>
            </div>
            <button
              onClick={() => {
                if (esSecretaria) {
                  setAlertaImmutabilitat("Veto Secretaria: La creació de capes està reservada a Enginyeria.");
                  return;
                }
                setMissatgeExit("Per afegir capes, seleccioneu el botó de delineació activa.");
                setTimeout(() => setMissatgeExit(null), 3000);
              }}
              disabled={esSecretaria}
              className={`p-1 rounded text-xs transition ${
                esSecretaria
                  ? "text-slate-400 cursor-not-allowed"
                  : "text-indigo-600 dark:text-indigo-400 hover:bg-indigo-50 dark:hover:bg-indigo-950"
              }`}
              title="Nova Capa Vectorial"
            >
              <Plus className="w-4 h-4" />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-2 space-y-1.5">
            {planolActiu && planolActiu.capes.length > 0 ? (
              planolActiu.capes.map((capa) => (
                <div
                  key={capa.id}
                  className={`p-2.5 rounded-lg border transition ${
                    capa.es_immutable
                      ? "bg-rose-50/50 dark:bg-rose-950/20 border-rose-200 dark:border-rose-900"
                      : "bg-slate-50 dark:bg-slate-800/60 border-slate-200 dark:border-slate-700"
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2 min-w-0">
                      <div
                        className="w-3 h-3 rounded-full shrink-0"
                        style={{ backgroundColor: capa.color_hex }}
                      />
                      <span className="text-xs font-bold text-slate-800 dark:text-slate-200 truncate">
                        {capa.nom}
                      </span>
                    </div>

                    <button
                      onClick={() => toggleVisibilitatCapa(capa.id)}
                      className="p-1 text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 rounded"
                    >
                      {capa.visible ? <Eye className="w-3.5 h-3.5" /> : <EyeOff className="w-3.5 h-3.5 text-slate-300" />}
                    </button>
                  </div>

                  <div className="flex items-center justify-between mt-2 pt-2 border-t border-slate-200 dark:border-slate-700/60 text-[10px]">
                    <span className="font-mono text-slate-500">{capa.disciplina}</span>

                    {capa.es_immutable ? (
                      <span
                        onClick={() => handleIntentEdicioCapa(capa)}
                        className="flex items-center gap-1 font-black text-rose-600 dark:text-rose-400 bg-rose-100 dark:bg-rose-950 px-1.5 py-0.5 rounded cursor-pointer"
                        title="Bloquejada per traçabilitat pericial d'obra tancada"
                      >
                        <Lock className="w-3 h-3" />
                        IMMUTABLE
                      </span>
                    ) : (
                      <span className="text-emerald-600 dark:text-emerald-400 font-semibold flex items-center gap-0.5">
                        <CheckCircle2 className="w-3 h-3" />
                        Editable (v{capa.version_id})
                      </span>
                    )}
                  </div>
                </div>
              ))
            ) : (
              <div className="p-4 text-center text-xs text-slate-400">
                Aquest plànol no conté capes vectorials actives.
              </div>
            )}
          </div>

          {/* Llegenda de Simbologia Tècnica Homologada */}
          <div className="p-3 bg-slate-50 dark:bg-slate-800/40 border-t border-slate-200 dark:border-slate-800 text-[11px] space-y-1.5">
            <span className="font-bold text-slate-700 dark:text-slate-300 text-xs block mb-1">
              Simbologia Normalitzada
            </span>
            <div className="flex items-center gap-2 text-slate-600 dark:text-slate-400">
              <div className="w-2.5 h-0.5 bg-blue-600 rounded" />
              <span>Canonada PE-100 Ø110</span>
            </div>
            <div className="flex items-center gap-2 text-slate-600 dark:text-slate-400">
              <div className="w-2 h-2 rounded-full bg-sky-600" />
              <span>Vàlvula reguladora pressió</span>
            </div>
            <div className="flex items-center gap-2 text-slate-600 dark:text-slate-400">
              <div className="w-2 h-2 rounded-sm bg-sky-600" />
              <span>Hidrant d&apos;alta pressió (16 bar)</span>
            </div>
            <div className="flex items-center gap-2 text-slate-600 dark:text-slate-400">
              <div className="w-2.5 h-0.5 border-b border-dashed border-amber-500" />
              <span>Límit Parcel·la SIGPAC</span>
            </div>
          </div>
        </aside>
      </div>

      {/* 3. MODALS & ALERTES D'IMMUTABILITAT */}

      {/* Banner / Toast d'Alerta d'Immutabilitat o Veto */}
      {alertaImmutabilitat && (
        <div className="fixed bottom-6 right-6 z-50 max-w-md bg-rose-900 text-white p-4 rounded-xl shadow-2xl border border-rose-700 flex items-start gap-3 animate-in fade-in slide-in-from-bottom-4 duration-200">
          <ShieldAlert className="w-5 h-5 text-rose-300 shrink-0 mt-0.5" />
          <div className="flex-1 text-xs">
            <p className="font-bold text-sm text-rose-100">Acció Bloquejada per Normativa</p>
            <p className="text-rose-200 mt-1">{alertaImmutabilitat}</p>
          </div>
          <button
            onClick={() => setAlertaImmutabilitat(null)}
            className="text-rose-300 hover:text-white p-1"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Banner de Missatge d'Èxit */}
      {missatgeExit && (
        <div className="fixed bottom-6 right-6 z-50 max-w-md bg-emerald-900 text-white p-4 rounded-xl shadow-2xl border border-emerald-700 flex items-start gap-3 animate-in fade-in slide-in-from-bottom-4 duration-200">
          <CheckCircle2 className="w-5 h-5 text-emerald-300 shrink-0 mt-0.5" />
          <div className="flex-1 text-xs">
            <p className="font-bold text-sm text-emerald-100">Operació Realitzada</p>
            <p className="text-emerald-200 mt-1">{missatgeExit}</p>
          </div>
          <button
            onClick={() => setMissatgeExit(null)}
            className="text-emerald-300 hover:text-white p-1"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* MODAL OFICIAL: CAIXETÍ INDUSTRIAL HOMOLOGAT PDF (RF-23, RF-25) */}
      {modalCaixetiObert && planolActiu && (
        <div className="fixed inset-0 z-50 bg-slate-900/80 backdrop-blur-sm flex items-center justify-center p-4 overflow-y-auto">
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl max-w-3xl w-full shadow-2xl overflow-hidden animate-in zoom-in-95 duration-150">
            <div className="p-4 bg-slate-900 text-white flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Printer className="w-5 h-5 text-indigo-400" />
                <h2 className="text-base font-bold">Generador de Caixetí Oficial & Dossier Tècnic PDF</h2>
              </div>
              <button
                onClick={() => setModalCaixetiObert(false)}
                className="text-slate-400 hover:text-white p-1"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6 space-y-6">
              {/* Previsualització en viu del Caixetí Industrial Homologat */}
              <div>
                <span className="text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider block mb-2">
                  Previsualització del Segell & Caixetí UNE-EN ISO 5457
                </span>

                <div className="border-2 border-slate-900 dark:border-slate-600 p-4 bg-slate-50 dark:bg-slate-950 font-sans text-xs">
                  <div className="grid grid-cols-4 border-b border-slate-400 dark:border-slate-700 pb-3 mb-3">
                    <div className="col-span-1 border-r border-slate-300 dark:border-slate-700 pr-3">
                      <div className="w-10 h-10 rounded-lg bg-emerald-600 flex items-center justify-center font-black text-white text-base tracking-wider shadow">
                        SE
                      </div>
                      <div className="font-extrabold text-sm text-slate-900 dark:text-slate-100 mt-1">SEVALOR</div>
                      <div className="text-[9px] text-slate-500">Enginyeria & Sistemes de Reg</div>
                    </div>
                    <div className="col-span-3 pl-3">
                      <div className="text-[10px] text-slate-400 uppercase font-mono">Títol del Projecte / Obra</div>
                      <div className="font-bold text-sm text-slate-900 dark:text-slate-100">{planolActiu.titol}</div>
                      <div className="text-[11px] text-slate-600 dark:text-slate-300 mt-1">
                        Client: <span className="font-semibold">{planolActiu.client_nom || "Comunitat General de Regants"}</span>
                      </div>
                    </div>
                  </div>

                  <div className="grid grid-cols-4 gap-2 text-[11px] border-b border-slate-400 dark:border-slate-700 pb-2 mb-2">
                    <div>
                      <span className="text-slate-400 text-[10px] block">Escala Gràfica:</span>
                      <span className="font-bold font-mono text-slate-800 dark:text-slate-200">{caixetiConfig.escala}</span>
                    </div>
                    <div>
                      <span className="text-slate-400 text-[10px] block">Projecció:</span>
                      <span className="font-bold font-mono text-slate-800 dark:text-slate-200">{planolActiu.projeccio}</span>
                    </div>
                    <div>
                      <span className="text-slate-400 text-[10px] block">Data d&apos;Emissió:</span>
                      <span className="font-bold font-mono text-slate-800 dark:text-slate-200">{new Date().toLocaleDateString("ca-ES")}</span>
                    </div>
                    <div>
                      <span className="text-slate-400 text-[10px] block">Ref. Arxiu:</span>
                      <span className="font-bold font-mono text-slate-800 dark:text-slate-200">{planolActiu.codi_referencia}</span>
                    </div>
                  </div>

                  <div className="text-[10px] text-slate-600 dark:text-slate-400 space-y-1">
                    <div><span className="font-bold">Autor Tècnic:</span> {caixetiConfig.autorTecnic}</div>
                    <div className="italic text-[9px] text-slate-500">{caixetiConfig.observacionsLegals}</div>
                  </div>

                  {/* Certificació de Constitució v4.0: EINES SENSE QR */}
                  <div className="mt-3 pt-2 border-t border-dashed border-slate-300 dark:border-slate-700 flex items-center justify-between text-[10px]">
                    <div className="flex items-center gap-1.5 text-emerald-700 dark:text-emerald-400 font-semibold">
                      <Shield className="w-3.5 h-3.5" />
                      <span>Conforme Constitució SEVALOR v4.0 (Sense codis QR d&apos;eines)</span>
                    </div>
                    <span className="text-slate-400 font-mono">ID: {planolActiu.id.slice(0, 8)}</span>
                  </div>
                </div>
              </div>

              {/* Configuració de l'exportació */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                    Escala Gràfica Normalitzada
                  </label>
                  <select
                    value={caixetiConfig.escala}
                    onChange={(e) => setCaixetiConfig({ ...caixetiConfig, escala: e.target.value })}
                    className="w-full text-xs p-2 rounded-lg bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 font-mono"
                  >
                    <option value="1:250">1:250 (Detall d&apos;arqueta / escomesa)</option>
                    <option value="1:500">1:500 (Instal·lació hidràulica de finca)</option>
                    <option value="1:1000">1:1000 (Xarxa general de polígon)</option>
                    <option value="1:2000">1:2000 (Pla general territorial)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                    Autor Tècnic Responsable
                  </label>
                  <input
                    type="text"
                    value={caixetiConfig.autorTecnic}
                    onChange={(e) => setCaixetiConfig({ ...caixetiConfig, autorTecnic: e.target.value })}
                    className="w-full text-xs p-2 rounded-lg bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700"
                  />
                </div>
              </div>
            </div>

            <div className="p-4 bg-slate-100 dark:bg-slate-800/80 border-t border-slate-200 dark:border-slate-800 flex items-center justify-between">
              <span className="text-xs text-slate-500 dark:text-slate-400">
                Destí d&apos;emmagatzematge: Hetzner Nuremberg (Alemanya)
              </span>

              <div className="flex gap-2">
                <button
                  onClick={() => setModalCaixetiObert(false)}
                  className="px-4 py-2 text-xs font-semibold rounded-lg text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700 transition"
                >
                  Cancel·lar
                </button>
                <button
                  onClick={handleExportarPdfOficial}
                  className="px-4 py-2 text-xs font-bold rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white transition flex items-center gap-2 shadow"
                >
                  <Download className="w-4 h-4" />
                  <span>Descarregar Dossier PDF Oficial</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* MODAL: CARREGAR NOU FITXER TÈCNIC / CAD */}
      {modalPujarObert && (
        <div className="fixed inset-0 z-50 bg-slate-900/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl max-w-lg w-full shadow-2xl p-6">
            <div className="flex items-center justify-between pb-4 border-b border-slate-200 dark:border-slate-800">
              <div className="flex items-center gap-2">
                <UploadCloud className="w-5 h-5 text-emerald-600" />
                <h3 className="text-base font-bold text-slate-900 dark:text-slate-100">
                  Pujar Plànol Tècnic CAD / GIS
                </h3>
              </div>
              <button onClick={() => setModalPujarObert(false)} className="text-slate-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="mt-4 space-y-4 text-xs">
              <div className="p-6 border-2 border-dashed border-slate-300 dark:border-slate-700 rounded-xl text-center hover:border-emerald-500 transition cursor-pointer">
                <FileCode className="w-10 h-10 text-slate-400 mx-auto mb-2" />
                <p className="font-bold text-slate-700 dark:text-slate-200">
                  Arrossegueu el fitxer o feu clic per explorar
                </p>
                <p className="text-slate-400 text-[11px] mt-1">
                  Formats admesos: .dxf, .dwg, .geojson, .kml, .pdf, .tiff (Màx: 50 MB)
                </p>
              </div>

              <div>
                <label className="block font-bold text-slate-700 dark:text-slate-300 mb-1">
                  Carpeta de Destí
                </label>
                <select className="w-full p-2 rounded-lg bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700">
                  {carpetes.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.nom} ({c.categoria})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block font-bold text-slate-700 dark:text-slate-300 mb-1">
                  Títol del Plànol
                </label>
                <input
                  type="text"
                  placeholder="Ex: Xarxa Secundària Sector 2"
                  className="w-full p-2 rounded-lg bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700"
                />
              </div>
            </div>

            <div className="mt-6 flex justify-end gap-2">
              <button
                onClick={() => setModalPujarObert(false)}
                className="px-4 py-2 text-xs font-semibold rounded-lg text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition"
              >
                Cancel·lar
              </button>
              <button
                onClick={() => {
                  setMissatgeExit("Plànol registrat correctament i allotjat sota sobirania Hetzner Alemanya.");
                  setModalPujarObert(false);
                  setTimeout(() => setMissatgeExit(null), 3000);
                }}
                className="px-4 py-2 text-xs font-bold rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white transition shadow"
              >
                Pujar i Processar
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL: NOVA CARPETA DE PROJECTE */}
      {modalNovaCarpetaObert && (
        <div className="fixed inset-0 z-50 bg-slate-900/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl max-w-md w-full shadow-2xl p-6">
            <div className="flex items-center justify-between pb-4 border-b border-slate-200 dark:border-slate-800">
              <div className="flex items-center gap-2">
                <FolderPlus className="w-5 h-5 text-indigo-600" />
                <h3 className="text-base font-bold text-slate-900 dark:text-slate-100">
                  Nova Carpeta de Projecte
                </h3>
              </div>
              <button onClick={() => setModalNovaCarpetaObert(false)} className="text-slate-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="mt-4 space-y-4 text-xs">
              <div>
                <label className="block font-bold text-slate-700 dark:text-slate-300 mb-1">
                  Categoria Obligatòria
                </label>
                <select className="w-full p-2 rounded-lg bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700">
                  <option value="CLIENTS">Clients (Finques i Explotacions Privades)</option>
                  <option value="INFRAESTRUCTURA_COMUNITARIA">Infraestructures Comunitàries (Comunitats de Regants)</option>
                  <option value="MUNICIPAL_TERRITORIAL">Municipal / Territorial (Ajuntaments i Ens Públics)</option>
                </select>
              </div>

              <div>
                <label className="block font-bold text-slate-700 dark:text-slate-300 mb-1">
                  Nom de la Carpeta
                </label>
                <input
                  type="text"
                  placeholder="Ex: Finca Can Puig - Xarxa Goter"
                  className="w-full p-2 rounded-lg bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700"
                />
              </div>

              <div>
                <label className="block font-bold text-slate-700 dark:text-slate-300 mb-1">
                  Municipi
                </label>
                <input
                  type="text"
                  placeholder="Ex: Vilafranca del Penedès"
                  className="w-full p-2 rounded-lg bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700"
                />
              </div>
            </div>

            <div className="mt-6 flex justify-end gap-2">
              <button
                onClick={() => setModalNovaCarpetaObert(false)}
                className="px-4 py-2 text-xs font-semibold rounded-lg text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition"
              >
                Cancel·lar
              </button>
              <button
                onClick={() => {
                  setMissatgeExit("Carpeta creada correctament.");
                  setModalNovaCarpetaObert(false);
                  setTimeout(() => setMissatgeExit(null), 3000);
                }}
                className="px-4 py-2 text-xs font-bold rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white transition shadow"
              >
                Crear Carpeta
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
