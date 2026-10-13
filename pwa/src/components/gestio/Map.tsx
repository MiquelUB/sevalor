"use client";

import React, { useState, useEffect } from "react";
import {
  MapPin,
  Clock,
  CheckCircle2,
  AlertTriangle,
  Briefcase,
  Users,
  Search,
  Check,
  Plus,
  Minus,
  Truck,
  Layers,
  Crosshair,
  ChevronUp,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  RotateCcw,
  Phone,
  ExternalLink,
  X,
  Filter,
  Eye,
  UserCheck,
  Navigation,
} from "lucide-react";

export interface Feina {
  id: string;
  codi: string;
  titol: string;
  estat: string;
  adreca: string;
  versio: number;
  latitud?: number | null;
  longitud?: number | null;
  cap_de_colla_id?: string | null;
  cap_de_colla_nom?: string | null;
  client_nom?: string | null;
  descripcio?: string | null;
}

export interface Operari {
  id: string;
  nom: string;
  cognoms: string;
  rol: string;
  estat: string;
  telefon?: string | null;
  latitud?: number | null;
  longitud?: number | null;
  vehicle_nom?: string | null;
}

interface MapProps {
  feines: Feina[];
  operaris: Operari[];
  onDropAssignment: (feinaId: string, versio: number, operariId: string) => Promise<void>;
  modeVisor?: "SAT" | "TOPO";
  onModeVisorChange?: (mode: "SAT" | "TOPO") => void;
  initialOperariId?: string | null;
}

// Funció matemàtica de conversió lat/lng a rajoles Web Mercator (EPSG:3857)
function latLngToTile(lat: number, lng: number, zoom: number) {
  const n = Math.pow(2, zoom);
  const tileX = Math.floor(((lng + 180) / 360) * n);
  const latRad = (lat * Math.PI) / 180;
  const tileY = Math.floor(
    ((1 - Math.log(Math.tan(latRad) + 1 / Math.cos(latRad)) / Math.PI) / 2) * n
  );
  return { x: tileX, y: tileY };
}

export default function GestioMap({
  feines,
  operaris,
  onDropAssignment,
  modeVisor = "SAT",
  onModeVisorChange,
  initialOperariId = null,
}: MapProps) {
  const [draggingId, setDraggingId] = useState<string | null>(null);
  
  // Pestanyes del panell lateral: "FEINES" o "OPERARIS"
  const [sidebarMode, setSidebarMode] = useState<"FEINES" | "OPERARIS">("FEINES");
  const [tabSidebarFeines, setTabSidebarFeines] = useState<"PENDENTS" | "TOTES" | "ASSIGNADES">("PENDENTS");
  const [filtreOperariId, setFiltreOperariId] = useState<string | null>(null);

  // Seleccions actives
  const [selectedFeinaId, setSelectedFeinaId] = useState<string | null>(null);
  const [selectedOperariId, setSelectedOperariId] = useState<string | null>(null);

  // Centre del visor dinàmic (per defecte Seu Central a Lleida / Segrià: 41.6176, 0.6200)
  const [centerCoord, setCenterCoord] = useState<{ lat: number; lng: number }>({
    lat: 41.6176,
    lng: 0.6200,
  });

  // Zoom & Pan
  const [zoom, setZoom] = useState<number>(13);
  const [panX, setPanX] = useState<number>(0);
  const [panY, setPanY] = useState<number>(0);

  // Capes GIS del mapa
  const [showMenuCapes, setShowMenuCapes] = useState<boolean>(false);
  const [capes, setCapes] = useState({
    feines: true,
    operaris: true,
    rutes: true,
    cobertura: false,
  });

  // Càlcul de rajola central a partir de les coordenades reals
  const baseTile = latLngToTile(centerCoord.lat, centerCoord.lng, zoom);
  const centerTileX = baseTile.x + panX;
  const centerTileY = baseTile.y + panY;

  // Càlcul de coordenades del centre actual del visor (HUD)
  const n = Math.pow(2, zoom);
  const currentCenterLng = ((centerTileX + 0.5) / n) * 360 - 180;
  const currentCenterLatRad = Math.atan(Math.sinh(Math.PI * (1 - 2 * ((centerTileY + 0.5) / n))));
  const currentCenterLat = (currentCenterLatRad * 180) / Math.PI;

  // Projecció de coordenades (lat, lng) al grid 3x3 (viewBox 768x768)
  const projectCoords = (lat: number, lng: number) => {
    const tileX = ((lng + 180) / 360) * n;
    const latRad = (lat * Math.PI) / 180;
    const tileY =
      ((1 - Math.log(Math.tan(latRad) + 1 / Math.cos(latRad)) / Math.PI) / 2) * n;

    // Viewport comença a centerTileX - 1 i centerTileY - 1, cobrint 3 rajoles (768px)
    const leftPercent = ((tileX - (centerTileX - 1)) / 3) * 100;
    const topPercent = ((tileY - (centerTileY - 1)) / 3) * 100;

    const xPx = (leftPercent / 100) * 768;
    const yPx = (topPercent / 100) * 768;

    return {
      top: `${topPercent.toFixed(2)}%`,
      left: `${leftPercent.toFixed(2)}%`,
      topPercent,
      leftPercent,
      xPx,
      yPx,
    };
  };

  const getFeinaCoords = (f: Feina, idx: number) => {
    let lat = f.latitud ?? null;
    let lng = f.longitud ?? null;

    if ((lat === null || lng === null) && f.adreca && f.adreca.includes(",")) {
      try {
        const parts = f.adreca.split(",").map((p) => parseFloat(p.trim()));
        if (parts.length >= 2 && !isNaN(parts[0]) && !isNaN(parts[1])) {
          lat = parts[0];
          lng = parts[1];
        }
      } catch {}
    }

    if (lat === null || lng === null) {
      const charCode = (f.id ? f.id.charCodeAt(0) : idx * 7) % 15;
      const charCode2 = (f.codi ? f.codi.charCodeAt(f.codi.length - 1) : idx * 11) % 15;
      lat = 41.6176 + (charCode - 7) * 0.007;
      lng = 0.6200 + (charCode2 - 7) * 0.007;
    }

    return { lat, lng };
  };

  const getStatusColor = (estat: string) => {
    switch (estat) {
      case "PENDENT":
        return "bg-amber-500 border-amber-300";
      case "ASSIGNADA":
      case "PROGRAMADA":
        return "bg-blue-500 border-blue-300";
      case "EN_CURS":
      case "EN_OBRA":
      case "EN_RUTA":
        return "bg-emerald-500 border-emerald-300";
      case "BLOQUEJADA":
      case "INCIDENCIA":
        return "bg-red-500 border-red-300";
      default:
        return "bg-slate-600 border-slate-400";
    }
  };

  // Pins de les feines amb dades i coordenades completes
  const pinsFeines = feines.map((f, idx) => {
    const coords = getFeinaCoords(f, idx);
    const pos = projectCoords(coords.lat, coords.lng);
    const assignedOp = operaris.find((op) => op.id === f.cap_de_colla_id);
    const isSelected = selectedFeinaId === f.id;
    const isLinkedToSelectedOperari =
      selectedOperariId && f.cap_de_colla_id === selectedOperariId;

    return {
      feina: f,
      id: f.id,
      codi: f.codi,
      titol: f.titol,
      adreca: f.adreca,
      estat: f.estat,
      cap_de_colla_id: f.cap_de_colla_id,
      cap_de_colla_nom: assignedOp ? `${assignedOp.nom} ${assignedOp.cognoms || ""}`.trim() : f.cap_de_colla_nom,
      lat: coords.lat,
      lng: coords.lng,
      pos,
      color: getStatusColor(f.estat),
      isSelected,
      isLinkedToSelectedOperari,
    };
  });

  // Pins de les quadrilles d'operaris actius amb posició garantida
  const pinsQuadrilles = operaris
    .filter((o) => o.estat === "ACTIU")
    .map((op, idx) => {
      const assignedJobs = feines.filter((f) => f.cap_de_colla_id === op.id);
      let lat = op.latitud ?? null;
      let lng = op.longitud ?? null;

      if (lat === null || lng === null) {
        if (assignedJobs.length > 0) {
          const c = getFeinaCoords(assignedJobs[0], idx);
          lat = c.lat + 0.0025;
          lng = c.lng + 0.0025;
        } else {
          lat = 41.6176 + ((idx % 7) - 3) * 0.004;
          lng = 0.6200 + ((idx % 7) - 3) * 0.004;
        }
      }

      const pos = projectCoords(lat, lng);
      const isSelected = selectedOperariId === op.id;

      return {
        operari: op,
        id: op.id,
        nom: `${op.nom} ${op.cognoms || ""}`.trim(),
        telefon: op.telefon,
        assignedJobs,
        lat,
        lng,
        pos,
        isSelected,
      };
    });

  // Funció clau: Centrar el mapa i enfocar un operari immediatament
  const focusOperari = (operariId: string) => {
    setSelectedOperariId(operariId);
    setSelectedFeinaId(null);
    const opPin = pinsQuadrilles.find((p) => p.id === operariId);
    if (opPin) {
      setCenterCoord({ lat: opPin.lat, lng: opPin.lng });
      setPanX(0);
      setPanY(0);
    }
  };

  // Funció clau: Centrar el mapa i enfocar una feina
  const focusFeina = (feinaId: string) => {
    setSelectedFeinaId(feinaId);
    const fPin = pinsFeines.find((p) => p.id === feinaId);
    if (fPin) {
      setCenterCoord({ lat: fPin.lat, lng: fPin.lng });
      setPanX(0);
      setPanY(0);
      if (fPin.cap_de_colla_id) {
        setSelectedOperariId(fPin.cap_de_colla_id);
      }
    }
  };

  // Suport per carregar un operari inicial per paràmetre URL
  useEffect(() => {
    if (initialOperariId) {
      focusOperari(initialOperariId);
    }
  }, [initialOperariId, operaris.length]);

  const handleDragStart = (e: React.DragEvent, feina: Feina) => {
    e.dataTransfer.setData("feinaId", feina.id);
    e.dataTransfer.setData("versio", feina.versio.toString());
    setDraggingId(feina.id);
  };

  const handleDragEnd = () => {
    setDraggingId(null);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };

  const handleDrop = async (e: React.DragEvent, operariId: string) => {
    e.preventDefault();
    const feinaId = e.dataTransfer.getData("feinaId");
    const versioStr = e.dataTransfer.getData("versio");
    if (!feinaId || !versioStr) return;
    await onDropAssignment(feinaId, parseInt(versioStr, 10), operariId);
    focusOperari(operariId);
  };

  const handleZoomIn = () => {
    if (zoom < 14) setZoom((z) => z + 1);
  };

  const handleZoomOut = () => {
    if (zoom > 12) setZoom((z) => z - 1);
  };

  const handleRecenter = () => {
    setCenterCoord({ lat: 41.6176, lng: 0.6200 });
    setPanX(0);
    setPanY(0);
    setZoom(13);
    setSelectedFeinaId(null);
    setSelectedOperariId(null);
  };

  // Llistat filtrat de feines
  const feinesFiltrades = feines.filter((f) => {
    if (filtreOperariId && f.cap_de_colla_id !== filtreOperariId) {
      return false;
    }
    if (tabSidebarFeines === "PENDENTS") return !f.cap_de_colla_id;
    if (tabSidebarFeines === "ASSIGNADES") return !!f.cap_de_colla_id;
    return true; // "TOTES"
  });

  const selectedFeina = feines.find((f) => f.id === selectedFeinaId);
  const selectedOperari = operaris.find((o) => o.id === selectedOperariId);

  return (
    <div className="flex-1 flex flex-col md:flex-row gap-4 relative">
      {/* 1. Panell Lateral de Navegació (Feines i Operaris) */}
      <div className="w-full md:w-80 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4 flex flex-col shadow-sm">
        
        {/* Selector de Mode Lateral: FEINES vs OPERARIS */}
        <div className="grid grid-cols-2 gap-1.5 bg-slate-100 dark:bg-slate-800 p-1 rounded-xl mb-3">
          <button
            type="button"
            onClick={() => setSidebarMode("FEINES")}
            className={`py-1.5 text-xs font-bold rounded-lg flex items-center justify-center gap-1.5 transition-all ${
              sidebarMode === "FEINES"
                ? "bg-white dark:bg-slate-900 text-emerald-600 dark:text-emerald-400 shadow-sm"
                : "text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
            }`}
          >
            <Briefcase className="w-3.5 h-3.5" />
            <span>Feines ({feines.length})</span>
          </button>
          <button
            type="button"
            onClick={() => setSidebarMode("OPERARIS")}
            className={`py-1.5 text-xs font-bold rounded-lg flex items-center justify-center gap-1.5 transition-all ${
              sidebarMode === "OPERARIS"
                ? "bg-white dark:bg-slate-900 text-blue-600 dark:text-blue-400 shadow-sm"
                : "text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
            }`}
          >
            <Users className="w-3.5 h-3.5" />
            <span>Operaris ({operaris.length})</span>
          </button>
        </div>

        {/* CONTINGUT: MODE OPERARIS */}
        {sidebarMode === "OPERARIS" && (
          <div className="flex-1 flex flex-col overflow-hidden">
            <div className="flex items-center justify-between mb-2">
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
                Quadrilles Actives de Camp
              </span>
              <span className="text-xs text-blue-500 font-mono font-bold">
                {pinsQuadrilles.length} al mapa
              </span>
            </div>

            <div className="flex-1 overflow-y-auto space-y-2 max-h-[520px] pr-1">
              {operaris.map((op) => {
                const assigned = feines.filter((f) => f.cap_de_colla_id === op.id);
                const isSelected = selectedOperariId === op.id;

                return (
                  <div
                    key={op.id}
                    onClick={() => focusOperari(op.id)}
                    className={`p-3 rounded-xl border transition-all cursor-pointer ${
                      isSelected
                        ? "border-blue-500 bg-blue-50/60 dark:bg-blue-950/30 ring-2 ring-blue-500/20"
                        : "border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/60 hover:border-blue-400"
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1.5">
                      <div className="flex items-center gap-2">
                        <div className="w-7 h-7 rounded-full bg-blue-500/20 text-blue-500 font-bold text-xs flex items-center justify-center border border-blue-500/30">
                          {op.nom[0]}
                          {op.cognoms ? op.cognoms[0] : ""}
                        </div>
                        <div>
                          <h4 className="text-xs font-bold text-slate-900 dark:text-white leading-tight">
                            {op.nom} {op.cognoms || ""}
                          </h4>
                          <span className="text-[10px] text-slate-500 font-mono">
                            {op.rol} • {op.estat}
                          </span>
                        </div>
                      </div>
                      <span className="px-1.5 py-0.5 rounded text-[10px] font-mono font-bold bg-blue-100 dark:bg-blue-900/50 text-blue-600 dark:text-blue-300">
                        {assigned.length} OT
                      </span>
                    </div>

                    <div className="flex items-center justify-between pt-1 border-t border-slate-200 dark:border-slate-700/60 text-[10px]">
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          focusOperari(op.id);
                        }}
                        className="text-blue-600 dark:text-blue-400 font-bold hover:underline flex items-center gap-1"
                      >
                        <Navigation className="w-3 h-3" />
                        <span>Centrar al mapa</span>
                      </button>

                      {op.telefon && (
                        <a
                          href={`tel:${op.telefon}`}
                          onClick={(e) => e.stopPropagation()}
                          className="text-slate-500 hover:text-emerald-500 flex items-center gap-1"
                        >
                          <Phone className="w-3 h-3" />
                          <span>{op.telefon}</span>
                        </a>
                      )}
                    </div>
                  </div>
                );
              })}
              {operaris.length === 0 && (
                <div className="p-6 text-center text-slate-400 text-xs">
                  No hi ha operaris registrats en aquest tenant.
                </div>
              )}
            </div>
          </div>
        )}

        {/* CONTINGUT: MODE FEINES */}
        {sidebarMode === "FEINES" && (
          <div className="flex-1 flex flex-col overflow-hidden">
            {/* Filtre per Cap de Colla / Operari */}
            <div className="mb-3">
              <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block mb-1 flex items-center gap-1">
                <Filter className="w-3 h-3 text-slate-400" />
                Filtrar per Operari / Colla
              </label>
              <select
                value={filtreOperariId || ""}
                onChange={(e) => {
                  const val = e.target.value || null;
                  setFiltreOperariId(val);
                  if (val) focusOperari(val);
                }}
                className="w-full text-xs bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg px-2.5 py-1.5 text-slate-800 dark:text-slate-200 font-medium focus:ring-2 focus:ring-emerald-500 outline-none transition-all cursor-pointer"
              >
                <option value="">Tots els operaris ({operaris.length})</option>
                {operaris.map((op) => {
                  const count = feines.filter((f) => f.cap_de_colla_id === op.id).length;
                  return (
                    <option key={op.id} value={op.id}>
                      {op.nom} {op.cognoms || ""} — {count} feines
                    </option>
                  );
                })}
              </select>
            </div>

            {/* Pestanyes d'Estat */}
            <div className="grid grid-cols-3 gap-1 bg-slate-100 dark:bg-slate-800/80 p-1 rounded-lg mb-3">
              <button
                type="button"
                onClick={() => setTabSidebarFeines("PENDENTS")}
                className={`py-1 text-[11px] font-bold rounded-md transition-colors ${
                  tabSidebarFeines === "PENDENTS"
                    ? "bg-white dark:bg-slate-900 text-emerald-600 dark:text-emerald-400 shadow-sm"
                    : "text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
                }`}
              >
                Pendents ({feines.filter((f) => !f.cap_de_colla_id).length})
              </button>
              <button
                type="button"
                onClick={() => setTabSidebarFeines("ASSIGNADES")}
                className={`py-1 text-[11px] font-bold rounded-md transition-colors ${
                  tabSidebarFeines === "ASSIGNADES"
                    ? "bg-white dark:bg-slate-900 text-emerald-600 dark:text-emerald-400 shadow-sm"
                    : "text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
                }`}
              >
                Assignades ({feines.filter((f) => !!f.cap_de_colla_id).length})
              </button>
              <button
                type="button"
                onClick={() => setTabSidebarFeines("TOTES")}
                className={`py-1 text-[11px] font-bold rounded-md transition-colors ${
                  tabSidebarFeines === "TOTES"
                    ? "bg-white dark:bg-slate-900 text-emerald-600 dark:text-emerald-400 shadow-sm"
                    : "text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
                }`}
              >
                Totes ({feines.length})
              </button>
            </div>

            {/* Llistat Arrossegable (Drop & Go) */}
            <div className="flex-1 overflow-y-auto space-y-2 max-h-[520px] pr-1">
              {feinesFiltrades.map((feina) => {
                const isSelected = selectedFeinaId === feina.id;
                const assignedOp = operaris.find((o) => o.id === feina.cap_de_colla_id);

                return (
                  <div
                    key={feina.id}
                    draggable
                    onDragStart={(e) => handleDragStart(e, feina)}
                    onDragEnd={handleDragEnd}
                    onClick={() => focusFeina(feina.id)}
                    className={`p-3 bg-slate-50 dark:bg-slate-800/60 border rounded-lg cursor-grab active:cursor-grabbing hover:border-emerald-500 transition-all shadow-sm ${
                      isSelected
                        ? "border-emerald-500 ring-2 ring-emerald-500/20 bg-emerald-50/40 dark:bg-emerald-950/20"
                        : "border-slate-200 dark:border-slate-700/60"
                    } ${draggingId === feina.id ? "opacity-50 border-emerald-500 ring-2 ring-emerald-500/20" : ""}`}
                  >
                    <div className="flex justify-between items-start mb-1">
                      <span className="text-xs font-bold text-slate-800 dark:text-slate-100 font-mono">
                        {feina.codi}
                      </span>
                      <span
                        className={`text-[10px] px-1.5 py-0.5 rounded font-medium border ${
                          feina.estat === "PENDENT"
                            ? "bg-amber-500/10 text-amber-600 border-amber-500/20"
                            : feina.estat === "ASSIGNADA" || feina.estat === "PROGRAMADA"
                            ? "bg-blue-500/10 text-blue-600 border-blue-500/20"
                            : "bg-emerald-500/10 text-emerald-600 border-emerald-500/20"
                        }`}
                      >
                        {feina.estat}
                      </span>
                    </div>
                    <p className="text-xs font-medium text-slate-600 dark:text-slate-300 line-clamp-1">
                      {feina.titol}
                    </p>

                    {assignedOp ? (
                      <div
                        onClick={(e) => {
                          e.stopPropagation();
                          focusOperari(assignedOp.id);
                        }}
                        className="mt-1 flex items-center gap-1.5 text-[10px] text-blue-600 dark:text-blue-400 font-medium hover:underline cursor-pointer"
                        title="Centrar en aquest operari al mapa"
                      >
                        <Truck className="w-3 h-3 shrink-0" />
                        <span>Colla: {assignedOp.nom} {assignedOp.cognoms || ""}</span>
                      </div>
                    ) : (
                      <div className="mt-1 flex items-center gap-1 text-[10px] text-amber-600 dark:text-amber-400">
                        <Clock className="w-3 h-3 shrink-0" />
                        <span>Pendent d'assignar</span>
                      </div>
                    )}

                    <div className="flex items-center gap-1 mt-1 text-[10px] text-slate-400 truncate">
                      <MapPin className="w-3 h-3 text-emerald-500 shrink-0" />
                      <span className="truncate">{feina.adreca}</span>
                    </div>
                  </div>
                );
              })}
              {feinesFiltrades.length === 0 && (
                <div className="p-6 text-center text-slate-400 text-xs">
                  No hi ha feines amb els filtres seleccionats.
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* 2. Visor Cartogràfic GIS Principal */}
      <div className="flex-1 bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-xl relative overflow-hidden flex flex-col min-h-[580px] shadow-sm select-none">
        
        {/* Barra superior esquerra: Selector de Base & Capes */}
        <div className="absolute top-4 left-4 z-30 flex items-center gap-2">
          {/* Selector de Cartografia Base */}
          <div className="flex bg-white/95 dark:bg-slate-900/95 backdrop-blur rounded-lg border border-slate-200 dark:border-slate-800 p-0.5 shadow-md">
            <button
              type="button"
              onClick={() => onModeVisorChange && onModeVisorChange("SAT")}
              className={`px-3 py-1.5 text-xs font-bold rounded-md transition-all flex items-center gap-1.5 ${
                modeVisor === "SAT"
                  ? "bg-emerald-600 text-white shadow-sm"
                  : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
              }`}
            >
              <span>🛰️ Ortofoto ESRI</span>
            </button>
            <button
              type="button"
              onClick={() => onModeVisorChange && onModeVisorChange("TOPO")}
              className={`px-3 py-1.5 text-xs font-bold rounded-md transition-all flex items-center gap-1.5 ${
                modeVisor === "TOPO"
                  ? "bg-emerald-600 text-white shadow-sm"
                  : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
              }`}
            >
              <span>🗺️ Carrers Topo</span>
            </button>
          </div>

          {/* Menú Desplegable de Capes de Dades */}
          <div className="relative">
            <button
              type="button"
              onClick={() => setShowMenuCapes((prev) => !prev)}
              className={`px-3 py-1.5 text-xs font-bold rounded-lg border shadow-md backdrop-blur flex items-center gap-1.5 transition-colors ${
                showMenuCapes
                  ? "bg-slate-800 text-white border-emerald-500 ring-2 ring-emerald-500/20"
                  : "bg-white/95 dark:bg-slate-900/95 text-slate-700 dark:text-slate-300 border-slate-200 dark:border-slate-800 hover:border-slate-400"
              }`}
            >
              <Layers className="w-3.5 h-3.5 text-emerald-500" />
              <span>Capes ({Object.values(capes).filter(Boolean).length})</span>
            </button>

            {showMenuCapes && (
              <div className="absolute top-full left-0 mt-2 w-56 bg-slate-900/95 backdrop-blur border border-slate-700 rounded-xl p-3 shadow-2xl z-40 space-y-2.5 text-xs">
                <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400 pb-1 border-b border-slate-800">
                  Visibilitat de Capes GIS
                </div>
                
                <label className="flex items-center gap-2 text-slate-200 cursor-pointer hover:text-white">
                  <input
                    type="checkbox"
                    checked={capes.feines}
                    onChange={(e) => setCapes({ ...capes, feines: e.target.checked })}
                    className="rounded border-slate-700 text-emerald-500 focus:ring-emerald-500"
                  />
                  <span>📍 Feines / Ordres ({pinsFeines.length})</span>
                </label>

                <label className="flex items-center gap-2 text-slate-200 cursor-pointer hover:text-white">
                  <input
                    type="checkbox"
                    checked={capes.operaris}
                    onChange={(e) => setCapes({ ...capes, operaris: e.target.checked })}
                    className="rounded border-slate-700 text-emerald-500 focus:ring-emerald-500"
                  />
                  <span>👷 Operaris / Colles ({pinsQuadrilles.length})</span>
                </label>

                <label className="flex items-center gap-2 text-slate-200 cursor-pointer hover:text-white">
                  <input
                    type="checkbox"
                    checked={capes.rutes}
                    onChange={(e) => setCapes({ ...capes, rutes: e.target.checked })}
                    className="rounded border-slate-700 text-emerald-500 focus:ring-emerald-500"
                  />
                  <span>↔️ Rutes d'Assignació</span>
                </label>

                <label className="flex items-center gap-2 text-slate-200 cursor-pointer hover:text-white">
                  <input
                    type="checkbox"
                    checked={capes.cobertura}
                    onChange={(e) => setCapes({ ...capes, cobertura: e.target.checked })}
                    className="rounded border-slate-700 text-emerald-500 focus:ring-emerald-500"
                  />
                  <span>⭕ Radi de Cobertura</span>
                </label>
              </div>
            )}
          </div>
        </div>

        {/* Barra superior dreta: HUD Coordenades, Recentrar i Zoom */}
        <div className="absolute top-4 right-4 z-30 flex items-center gap-2">
          {/* Indicador de Coordenades Reals */}
          <div className="bg-slate-900/90 text-white px-2.5 py-1.5 rounded-lg border border-slate-700 text-[11px] font-mono shadow-md backdrop-blur flex items-center gap-1.5">
            <Crosshair className="w-3.5 h-3.5 text-emerald-400" />
            <span>{currentCenterLat.toFixed(4)}°N, {currentCenterLng.toFixed(4)}°E</span>
          </div>

          {/* Botó de Recentrar a la Seu Central */}
          <button
            type="button"
            onClick={handleRecenter}
            className="p-1.5 bg-white/95 dark:bg-slate-900/95 rounded-lg border border-slate-200 dark:border-slate-800 shadow-md backdrop-blur text-slate-700 dark:text-slate-300 hover:text-emerald-500 transition-colors"
            title="Recentrar a la Seu Central (Lleida)"
          >
            <RotateCcw className="w-4 h-4" />
          </button>

          {/* Controls de Zoom */}
          <div className="flex flex-col bg-white/95 dark:bg-slate-900/95 rounded-lg border border-slate-200 dark:border-slate-800 shadow-md backdrop-blur overflow-hidden">
            <button
              type="button"
              onClick={handleZoomIn}
              disabled={zoom >= 14}
              className="p-1.5 hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300 disabled:opacity-30 border-b border-slate-200 dark:border-slate-800"
              title="Apropar mapa"
            >
              <Plus className="w-4 h-4" />
            </button>
            <button
              type="button"
              onClick={handleZoomOut}
              disabled={zoom <= 12}
              className="p-1.5 hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300 disabled:opacity-30"
              title="Allunyar mapa"
            >
              <Minus className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Controls de Desplaçament (Pan N, S, E, O) */}
        <div className="absolute bottom-24 right-4 z-30 flex flex-col items-center bg-slate-900/90 border border-slate-700 rounded-xl p-1 shadow-xl backdrop-blur">
          <button
            type="button"
            onClick={() => setPanY((y) => y - 1)}
            className="p-1 text-slate-300 hover:text-emerald-400 hover:bg-slate-800 rounded transition-colors"
            title="Desplaçar al Nord"
          >
            <ChevronUp className="w-4 h-4" />
          </button>
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => setPanX((x) => x - 1)}
              className="p-1 text-slate-300 hover:text-emerald-400 hover:bg-slate-800 rounded transition-colors"
              title="Desplaçar a l'Oest"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <button
              type="button"
              onClick={handleRecenter}
              className="w-4 h-4 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center text-[9px] font-bold hover:bg-emerald-500/40"
              title="Centre"
            >
              •
            </button>
            <button
              type="button"
              onClick={() => setPanX((x) => x + 1)}
              className="p-1 text-slate-300 hover:text-emerald-400 hover:bg-slate-800 rounded transition-colors"
              title="Desplaçar a l'Est"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
          <button
            type="button"
            onClick={() => setPanY((y) => y + 1)}
            className="p-1 text-slate-300 hover:text-emerald-400 hover:bg-slate-800 rounded transition-colors"
            title="Desplaçar al Sud"
          >
            <ChevronDown className="w-4 h-4" />
          </button>
        </div>

        {/* CONTENIDOR DEL MAPA (GRID 3x3 DE RAJOLES REALS + CAPA SVG + PINS) */}
        <div className="absolute inset-0 overflow-hidden flex items-center justify-center bg-slate-950">
          <div className="relative w-[768px] h-[768px] shrink-0 select-none">
            {/* 1. Rajoles Cartogràfiques Reals */}
            <div className="grid grid-cols-3 grid-rows-3 w-[768px] h-[768px] absolute inset-0">
              {[-1, 0, 1].map((dy) =>
                [-1, 0, 1].map((dx) => {
                  const tx = centerTileX + dx;
                  const ty = centerTileY + dy;
                  const tileUrl =
                    modeVisor === "SAT"
                      ? `https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/${zoom}/${ty}/${tx}`
                      : `https://tile.openstreetmap.org/${zoom}/${tx}/${ty}.png`;

                  return (
                    <img
                      key={`${zoom}-${tx}-${ty}-${modeVisor}`}
                      src={tileUrl}
                      alt="Cartografia"
                      className="w-[256px] h-[256px] block border border-slate-800/10 object-cover"
                      loading="lazy"
                    />
                  );
                })
              )}
            </div>

            {/* 2. Capa Vectorial SVG (Rutes d'assignació i Radi de Cobertura) */}
            <svg
              viewBox="0 0 768 768"
              className="absolute inset-0 w-full h-full pointer-events-none z-10"
            >
              {/* Radi de Cobertura */}
              {capes.cobertura &&
                pinsQuadrilles.map((op) => (
                  <circle
                    key={`cobertura-${op.id}`}
                    cx={op.pos.xPx}
                    cy={op.pos.yPx}
                    r={90}
                    fill="rgba(16, 185, 129, 0.08)"
                    stroke="rgba(16, 185, 129, 0.35)"
                    strokeWidth="1.5"
                    strokeDasharray="4 4"
                  />
                ))}

              {/* Línies de Ruta Connectant Operari -> Feina */}
              {capes.rutes &&
                pinsQuadrilles.map((op) =>
                  op.assignedJobs.map((f) => {
                    const fPin = pinsFeines.find((p) => p.id === f.id);
                    if (!fPin) return null;

                    const isHighlight =
                      op.isSelected ||
                      selectedFeinaId === f.id ||
                      filtreOperariId === op.id;

                    const midX = (op.pos.xPx + fPin.pos.xPx) / 2;
                    const midY = (op.pos.yPx + fPin.pos.yPx) / 2 - 20;

                    return (
                      <g key={`route-${op.id}-${f.id}`}>
                        <path
                          d={`M ${op.pos.xPx} ${op.pos.yPx} Q ${midX} ${midY} ${fPin.pos.xPx} ${fPin.pos.yPx}`}
                          stroke={isHighlight ? "#10b981" : "#38bdf8"}
                          strokeWidth={isHighlight ? "3.5" : "2"}
                          strokeDasharray={isHighlight ? "6 3" : "4 4"}
                          fill="none"
                          opacity={isHighlight ? "0.95" : "0.55"}
                        />
                        <circle
                          cx={midX}
                          cy={midY}
                          r={isHighlight ? "3.5" : "2"}
                          fill={isHighlight ? "#10b981" : "#38bdf8"}
                        />
                      </g>
                    );
                  })
                )}
            </svg>

            {/* 3. Pins de Feines Georeferenciades */}
            {capes.feines &&
              pinsFeines.map((pin) => {
                const isSelected = pin.isSelected;
                const isLinked = pin.isLinkedToSelectedOperari;

                return (
                  <div
                    key={pin.id}
                    style={{ top: pin.pos.top, left: pin.pos.left }}
                    onClick={(e) => {
                      e.stopPropagation();
                      focusFeina(pin.id);
                    }}
                    className={`absolute z-20 -translate-x-1/2 -translate-y-1/2 pointer-events-auto cursor-pointer group transition-transform ${
                      isSelected ? "scale-125 z-30" : "hover:scale-110"
                    }`}
                  >
                    <div className="relative flex items-center justify-center">
                      {(isSelected || isLinked) && (
                        <span className="animate-ping absolute inline-flex h-8 w-8 rounded-full bg-emerald-400 opacity-60" />
                      )}
                      <div
                        className={`w-7 h-7 rounded-full ${pin.color} text-white flex items-center justify-center shadow-lg border-2 ${
                          isSelected
                            ? "border-emerald-300 ring-2 ring-emerald-400"
                            : isLinked
                            ? "border-yellow-300 ring-2 ring-yellow-400/50"
                            : "border-white dark:border-slate-900"
                        }`}
                      >
                        <MapPin className="w-4 h-4" />
                      </div>
                    </div>

                    {/* Etiqueta compacta */}
                    <div
                      className={`mt-1 rounded-md px-2 py-0.5 text-[10px] shadow-xl whitespace-nowrap backdrop-blur border ${
                        isSelected
                          ? "bg-emerald-950/90 text-white border-emerald-500 font-bold"
                          : "bg-slate-900/90 text-slate-200 border-slate-700"
                      }`}
                    >
                      <span className="font-mono text-emerald-400">{pin.codi}</span>
                      {pin.cap_de_colla_nom && (
                        <span className="ml-1 text-slate-300 text-[9px]">
                          • {pin.cap_de_colla_nom.split(" ")[0]}
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}

            {/* 4. Pins de Vehicles / Operaris de Camp (Visible, Il·luminat i Interactiu) */}
            {capes.operaris &&
              pinsQuadrilles.map((v) => {
                const isSelected = v.isSelected || filtreOperariId === v.id;

                return (
                  <div
                    key={v.id}
                    style={{ top: v.pos.top, left: v.pos.left }}
                    onClick={(e) => {
                      e.stopPropagation();
                      focusOperari(v.id);
                    }}
                    className={`absolute z-30 -translate-x-1/2 -translate-y-1/2 pointer-events-auto cursor-pointer transition-transform ${
                      isSelected ? "scale-125 z-40" : "hover:scale-110"
                    }`}
                  >
                    <div className="relative flex items-center justify-center">
                      {isSelected && (
                        <span className="animate-ping absolute inline-flex h-12 w-12 rounded-full bg-blue-400 opacity-60" />
                      )}
                      <div
                        className={`flex items-center gap-1.5 backdrop-blur border text-white rounded-full px-2.5 py-1 text-[11px] shadow-2xl transition-all ${
                          isSelected
                            ? "bg-blue-600 border-white ring-4 ring-blue-500/50 font-bold shadow-blue-500/30"
                            : "bg-slate-900/95 border-blue-500/50 hover:border-blue-400"
                        }`}
                      >
                        <div className="w-5 h-5 rounded-full bg-blue-400 text-slate-900 font-bold text-[10px] flex items-center justify-center">
                          {v.nom[0]}
                        </div>
                        <Truck className="w-3.5 h-3.5 text-blue-300 shrink-0" />
                        <span className="truncate max-w-[120px] font-medium">{v.nom}</span>
                        {v.assignedJobs.length > 0 && (
                          <span className="bg-emerald-500 text-white text-[9px] px-1.5 py-0.2 rounded-full font-mono font-bold">
                            {v.assignedJobs.length}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
          </div>
        </div>

        {/* 3. Popover Flotant de Detall de Feina Seleccionada */}
        {selectedFeina && (
          <div className="absolute top-16 right-4 z-40 w-80 bg-slate-900/95 backdrop-blur border border-slate-700 rounded-xl p-4 shadow-2xl text-white">
            <div className="flex items-start justify-between pb-2 mb-2 border-b border-slate-800">
              <div>
                <span className="text-xs font-mono font-bold text-emerald-400">
                  {selectedFeina.codi}
                </span>
                <h3 className="text-sm font-bold leading-tight mt-0.5">
                  {selectedFeina.titol}
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setSelectedFeinaId(null)}
                className="p-1 text-slate-400 hover:text-white rounded"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-2 text-xs">
              <div className="flex items-center gap-1.5 text-slate-300">
                <MapPin className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                <span className="truncate">{selectedFeina.adreca}</span>
              </div>

              <div className="flex items-center justify-between pt-1">
                <span className="text-slate-400">Estat actual:</span>
                <span
                  className={`px-2 py-0.5 rounded text-[10px] font-bold border ${getStatusColor(
                    selectedFeina.estat
                  )}`}
                >
                  {selectedFeina.estat}
                </span>
              </div>

              {/* Informació de l'operari assignat */}
              <div className="p-2.5 bg-slate-800/80 rounded-lg border border-slate-700 mt-2">
                <div className="text-[10px] text-slate-400 uppercase font-bold mb-1">
                  Cap de Colla Assignat
                </div>
                {selectedFeina.cap_de_colla_id ? (
                  (() => {
                    const op = operaris.find((o) => o.id === selectedFeina.cap_de_colla_id);
                    return op ? (
                      <div className="flex items-center justify-between">
                        <div
                          onClick={() => focusOperari(op.id)}
                          className="flex items-center gap-2 cursor-pointer group"
                        >
                          <div className="w-6 h-6 rounded-full bg-blue-500/20 text-blue-400 flex items-center justify-center font-bold text-xs group-hover:bg-blue-500 group-hover:text-white transition-colors">
                            {op.nom[0]}
                          </div>
                          <div>
                            <div className="font-bold text-xs group-hover:text-blue-400 transition-colors">
                              {op.nom} {op.cognoms || ""}
                            </div>
                            <div className="text-[10px] text-slate-400">{op.rol}</div>
                          </div>
                        </div>
                        <div className="flex items-center gap-1">
                          <button
                            type="button"
                            onClick={() => focusOperari(op.id)}
                            className="p-1 text-blue-400 hover:text-blue-300"
                            title="Centrar en l'operari al mapa"
                          >
                            <Navigation className="w-3.5 h-3.5" />
                          </button>
                          {op.telefon && (
                            <a
                              href={`tel:${op.telefon}`}
                              className="p-1 text-emerald-400 hover:text-emerald-300"
                              title="Trucar"
                            >
                              <Phone className="w-3.5 h-3.5" />
                            </a>
                          )}
                        </div>
                      </div>
                    ) : (
                      <span className="text-slate-400 text-xs">ID: {selectedFeina.cap_de_colla_id}</span>
                    );
                  })()
                ) : (
                  <div className="text-amber-400 text-xs flex items-center gap-1">
                    <AlertTriangle className="w-3.5 h-3.5" />
                    <span>Sense assignar (Pendent d'adjudicar)</span>
                  </div>
                )}
              </div>

              {/* Reassignació Ràpida Drop & Go des del Popover */}
              <div className="pt-2">
                <label className="text-[10px] text-slate-400 uppercase font-bold block mb-1">
                  Reassignar Feina a un altre Operari:
                </label>
                <select
                  defaultValue=""
                  onChange={async (e) => {
                    const newOpId = e.target.value;
                    if (newOpId) {
                      await onDropAssignment(selectedFeina.id, selectedFeina.versio, newOpId);
                      focusOperari(newOpId);
                    }
                  }}
                  className="w-full text-xs bg-slate-800 border border-slate-700 rounded-lg px-2 py-1.5 text-white font-medium focus:ring-2 focus:ring-emerald-500 outline-none cursor-pointer"
                >
                  <option value="" disabled>
                    Tria una colla d'operaris...
                  </option>
                  {operaris.map((op) => (
                    <option key={op.id} value={op.id}>
                      {op.nom} {op.cognoms || ""} ({op.rol})
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </div>
        )}

        {/* 4. Popover Flotant d'Operari Seleccionat */}
        {selectedOperari && !selectedFeina && (
          <div className="absolute top-16 right-4 z-40 w-72 bg-slate-900/95 backdrop-blur border border-slate-700 rounded-xl p-4 shadow-2xl text-white">
            <div className="flex items-start justify-between pb-2 mb-2 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-full bg-blue-500/20 text-blue-400 font-bold text-sm flex items-center justify-center border border-blue-500/30">
                  {selectedOperari.nom[0]}
                  {selectedOperari.cognoms ? selectedOperari.cognoms[0] : ""}
                </div>
                <div>
                  <h3 className="text-xs font-bold leading-tight">
                    {selectedOperari.nom} {selectedOperari.cognoms}
                  </h3>
                  <span className="text-[10px] text-blue-400 font-mono">
                    {selectedOperari.rol} • {selectedOperari.estat}
                  </span>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setSelectedOperariId(null)}
                className="p-1 text-slate-400 hover:text-white rounded"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-2 text-xs">
              {selectedOperari.telefon && (
                <div className="flex items-center gap-2 text-slate-300">
                  <Phone className="w-3.5 h-3.5 text-emerald-400" />
                  <a href={`tel:${selectedOperari.telefon}`} className="hover:underline">
                    {selectedOperari.telefon}
                  </a>
                </div>
              )}

              <div className="pt-2 border-t border-slate-800">
                <div className="flex items-center justify-between text-[11px] mb-1">
                  <span className="text-slate-400 font-bold">Feines Actives Assignades:</span>
                  <span className="font-mono text-emerald-400 font-bold">
                    {feines.filter((f) => f.cap_de_colla_id === selectedOperari.id).length}
                  </span>
                </div>
                <div className="max-h-32 overflow-y-auto space-y-1 pr-1">
                  {feines
                    .filter((f) => f.cap_de_colla_id === selectedOperari.id)
                    .map((af) => (
                      <div
                        key={af.id}
                        onClick={() => focusFeina(af.id)}
                        className="p-1.5 bg-slate-800/80 hover:bg-slate-700/80 border border-slate-700 rounded text-[11px] flex items-center justify-between cursor-pointer transition-colors"
                      >
                        <span className="font-mono text-emerald-400 font-bold">{af.codi}</span>
                        <span className="truncate max-w-[140px] text-slate-300">{af.titol}</span>
                      </div>
                    ))}
                  {feines.filter((f) => f.cap_de_colla_id === selectedOperari.id).length === 0 && (
                    <div className="text-[10px] text-slate-500 py-1 text-center">
                      Cap feina assignada actualment.
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* 5. Tauler Flotant Drop & Go de Quadrilles al Peu del Mapa */}
        <div className="mt-auto z-20 p-4 bg-gradient-to-t from-slate-950 via-slate-950/90 to-transparent pt-8">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
              <Users className="w-4 h-4 text-emerald-400" />
              Quadrilles Actives (Clica per centrar • Arrossega feines per assignar)
            </span>
            <span className="text-[10px] text-slate-400">
              {modeVisor === "SAT"
                ? "© ESRI World Imagery • Cartografia d'Alta Resolució"
                : "© OpenStreetMap contributors • Visualitzador Carrers"}
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {operaris.map((operari) => {
              const assignedFeines = feines.filter((f) => f.cap_de_colla_id === operari.id);
              const isSelected = selectedOperariId === operari.id;

              return (
                <div
                  key={operari.id}
                  onDragOver={handleDragOver}
                  onDrop={(e) => handleDrop(e, operari.id)}
                  onClick={() => focusOperari(operari.id)}
                  className={`bg-slate-900/90 backdrop-blur border-2 border-dashed rounded-xl p-3 transition-all flex flex-col min-h-[120px] shadow-lg cursor-pointer ${
                    isSelected
                      ? "border-blue-500 ring-2 ring-blue-500/30 bg-slate-900"
                      : "border-slate-700 hover:border-blue-400"
                  }`}
                  title="Clica per centrar i veure al mapa"
                >
                  <div className="flex items-center gap-2 mb-2 pb-2 border-b border-slate-800">
                    <div className="w-7 h-7 rounded-full bg-blue-500/20 text-blue-400 font-bold text-xs flex items-center justify-center border border-blue-500/30">
                      {operari.nom[0]}
                      {operari.cognoms ? operari.cognoms[0] : ""}
                    </div>
                    <div className="flex-1 truncate">
                      <h3 className="text-xs font-bold text-white leading-tight truncate">
                        {operari.nom} {operari.cognoms}
                      </h3>
                      <span className="text-[10px] text-blue-400 font-mono">
                        En Servei ({operari.rol})
                      </span>
                    </div>
                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-800 text-slate-300">
                      {assignedFeines.length} OT
                    </span>
                  </div>

                  <div className="flex-1 space-y-1 overflow-y-auto max-h-[80px]">
                    {assignedFeines.length === 0 ? (
                      <div className="h-full flex flex-col items-center justify-center text-center p-1 text-slate-500 text-[11px]">
                        <span>Clica per centrar o arrossega una feina</span>
                      </div>
                    ) : (
                      assignedFeines.map((af) => (
                        <div
                          key={af.id}
                          onClick={(e) => {
                            e.stopPropagation();
                            focusFeina(af.id);
                          }}
                          className="bg-slate-800/80 hover:bg-slate-700/80 border border-slate-700 rounded px-2 py-1 text-xs flex items-center justify-between text-slate-200 transition-colors"
                        >
                          <span className="font-bold text-[10px] text-emerald-400 font-mono">
                            {af.codi}
                          </span>
                          <span className="text-[10px] truncate max-w-[140px] text-slate-300">
                            {af.titol}
                          </span>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
