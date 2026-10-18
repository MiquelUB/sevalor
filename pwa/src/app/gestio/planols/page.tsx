"use client";

import React, { useState, useEffect } from "react";
import {
  Folder,
  FolderPlus,
  FileText,
  MapPin,
  AlertTriangle,
  Plus,
  X,
  RefreshCw,
} from "lucide-react";
import { useGestio } from "@/lib/gestio-context";
import { apiFetch } from "@/lib/api";

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
  projeccio?: string;
  created_at?: string;
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
  const [capaValvules, setCapaValvules] = useState(true);
  const [capaPressio, setCapaPressio] = useState(false);

  // Modals
  const [modalNovaCarpeta, setModalNovaCarpeta] = useState(false);
  const [modalNouPlanol, setModalNouPlanol] = useState(false);
  const [guardant, setGuardant] = useState(false);

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

  const handleCrearPlanol = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!carpetaSeleccionada) return;
    setGuardant(true);
    setError(null);
    try {
      const creat = await apiFetch<Planol>("/gestio/planols", {
        method: "POST",
        body: JSON.stringify({
          ...nouPlanol,
          carpeta_id: carpetaSeleccionada.id,
        }),
      });
      setModalNouPlanol(false);
      setNouPlanol({
        titol: "",
        codi_referencia: "",
        tipus_fitxer: "DXF",
        es_georeferenciat: true,
        projeccio: "ETRS89 / UTM 31N",
      });
      await carregarDades();
      if (creat) setPlanolSeleccionat(creat);
    } catch (err: any) {
      setError(err.message || "Error al registrar el plànol");
    } finally {
      setGuardant(false);
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

            <div className="flex items-center gap-sm">
              <button
                onClick={() => setModalNouPlanol(true)}
                disabled={!carpetaSeleccionada}
                className="flex items-center gap-sm px-md py-sm bg-primary text-on-primary rounded-lg font-body-strong text-xs hover:bg-primary-container transition-all disabled:opacity-50 shadow-sm"
              >
                <span className="material-symbols-outlined text-[18px]">upload_file</span>
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
            <div className="flex-1 flex flex-col items-center justify-center p-12 text-center m-lg bg-surface-container-low/50 rounded-2xl border border-dashed border-outline-variant">
              <FileText className="w-10 h-10 text-outline mb-3" />
              <h3 className="text-base font-bold text-on-surface">La carpeta està buida</h3>
              <p className="text-xs text-on-surface-variant max-w-xs mt-1">
                Estat Dia-0: Puja el primer arxiu DXF, GeoJSON o PDF georeferenciat d&apos;aquesta zona.
              </p>
              <button
                onClick={() => setModalNouPlanol(true)}
                className="mt-3 px-4 py-2 rounded-lg bg-primary hover:bg-primary-container text-white text-xs font-bold shadow"
              >
                + Pujar Plànol
              </button>
            </div>
          ) : (
            <div className="flex-1 relative bg-surface-dim flex flex-col justify-between overflow-y-auto">
              {/* Top Interactive Blueprint Canvas + Floating Layer Controls */}
              <div
                className="relative flex-1 min-h-[280px] p-lg flex items-start justify-between"
                style={{ opacity: opacitatPlanimetria / 100 }}
              >
                {/* Blueprint Technical Grid Preview */}
                <div className="visor-pdf bg-surface-container-lowest/90 backdrop-blur-md p-lg rounded-xl shadow-md border border-outline-variant/40 max-w-md">
                  <span className="font-label-caps text-primary uppercase block mb-xs">
                    Fitxa Cartogràfica Activa
                  </span>
                  <h3 className="font-body-strong text-base text-on-surface">
                    {planolSeleccionat?.titol || planolsFiltrats[0]?.titol}
                  </h3>
                  <p className="text-xs font-data-tabular text-on-surface-variant mt-xs">
                    Ref: {planolSeleccionat?.codi_referencia || planolsFiltrats[0]?.codi_referencia}{" "}
                    · Format: {planolSeleccionat?.tipus_fitxer || planolsFiltrats[0]?.tipus_fitxer}
                  </p>
                </div>

                {/* Stitch Floating Layer Controls */}
                <div className="bg-surface/95 backdrop-blur-md p-md rounded-xl shadow-xl border border-outline-variant/30 w-64 space-y-md">
                  <div className="flex items-center justify-between">
                    <span className="font-label-caps text-label-caps text-on-surface-variant uppercase">
                      Capes d&apos;Informació
                    </span>
                    <span className="material-symbols-outlined text-primary text-[18px]">
                      layers
                    </span>
                  </div>
                  <div className="space-y-xs">
                    <div className="flex justify-between items-center text-data-tabular">
                      <span>Opacitat Planimetria</span>
                      <span>{opacitatPlanimetria}%</span>
                    </div>
                    <input
                      type="range"
                      min={20}
                      max={100}
                      value={opacitatPlanimetria}
                      onChange={(e) => setOpacitatPlanimetria(Number(e.target.value))}
                      className="w-full h-1.5 bg-surface-container-highest rounded-lg cursor-pointer accent-primary"
                    />
                  </div>
                  <div
                    onClick={() => setCapaValvules(!capaValvules)}
                    className="flex items-center justify-between cursor-pointer text-xs"
                  >
                    <span className="text-on-surface">Vàlvules i Escomeses</span>
                    <div
                      className={`w-8 h-4 rounded-full relative transition-colors ${
                        capaValvules ? "bg-primary" : "bg-outline"
                      }`}
                    >
                      <div
                        className={`absolute top-1 w-2 h-2 bg-white rounded-full transition-all ${
                          capaValvules ? "right-1" : "left-1"
                        }`}
                      ></div>
                    </div>
                  </div>
                  <div
                    onClick={() => setCapaPressio(!capaPressio)}
                    className="flex items-center justify-between cursor-pointer text-xs"
                  >
                    <span className="text-on-surface"> telemetria / Isòbares</span>
                    <div
                      className={`w-8 h-4 rounded-full relative transition-colors ${
                        capaPressio ? "bg-primary" : "bg-outline"
                      }`}
                    >
                      <div
                        className={`absolute top-1 w-2 h-2 bg-white rounded-full transition-all ${
                          capaPressio ? "right-1" : "left-1"
                        }`}
                      ></div>
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

            <form onSubmit={handleCrearPlanol} className="p-5 space-y-4">
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
    </div>
  );
}
