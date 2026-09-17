"use client";

import React, { useState, useEffect } from "react";
import {
  Layers,
  Folder,
  FolderPlus,
  FileText,
  Search,
  Lock,
  Compass,
  MapPin,
  Download,
  AlertTriangle,
  CheckCircle2,
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
      setCarpetes(dataCarpetes || []);
      setPlanols(dataPlanols || []);
      if (dataCarpetes && dataCarpetes.length > 0) {
        setCarpetaSeleccionada(dataCarpetes[0]);
      } else {
        setCarpetaSeleccionada(null);
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

  return (
    <div className="flex-1 flex flex-col h-[calc(100vh-3.5rem)] overflow-hidden bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 transition-colors">
      {/* Barra superior de Plànols */}
      <div className="p-4 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between shadow-sm">
        <div>
          <h1 className="text-base font-bold text-slate-800 dark:text-slate-100 flex items-center gap-2">
            <Layers className="w-5 h-5 text-emerald-600" />
            Plànols & Xarxes Vectorials GIS (Spec 010)
          </h1>
          <p className="text-xs text-slate-500">
            Arxiu cartogràfic, capes vectorials d'aigua i georeferenciació ETRS89
          </p>
        </div>

        <div className="flex items-center gap-2">
          <div className="relative">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
            <input
              type="text"
              value={filtreCerca}
              onChange={(e) => setFiltreCerca(e.target.value)}
              placeholder="Cercar per títol o referència..."
              className="pl-9 pr-3 py-1.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-xs font-medium focus:outline-none focus:border-emerald-600 w-56"
            />
          </div>

          <button
            onClick={carregarDades}
            disabled={loading}
            className="p-2 rounded-xl bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 text-slate-600 dark:text-slate-300 transition-colors"
            title="Refrescar dades"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
          </button>

          <button
            onClick={() => setModalNovaCarpeta(true)}
            className="px-3 py-1.5 rounded-xl bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-800 dark:text-slate-200 text-xs font-bold flex items-center gap-1 transition-all"
          >
            <FolderPlus className="w-3.5 h-3.5" />
            <span>Nova Carpeta</span>
          </button>

          <button
            onClick={() => setModalNouPlanol(true)}
            disabled={!carpetaSeleccionada}
            className="px-3 py-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold flex items-center gap-1 shadow transition-all disabled:opacity-50"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Pujar Plànol</span>
          </button>
        </div>
      </div>

      {error && (
        <div className="mx-4 mt-3 p-3 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900 text-rose-700 dark:text-rose-300 text-xs flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-rose-600" />
            <span>{error}</span>
          </div>
          <button onClick={() => setError(null)} className="p-1 hover:text-rose-900">
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* Cos principal: Columna de Carpetes + Taula de Plànols */}
      <div className="flex-1 flex overflow-hidden">
        {/* Llista de Carpetes */}
        <div className="w-72 border-r border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 overflow-y-auto p-3 space-y-2">
          <p className="text-[10px] font-mono font-bold uppercase tracking-wider text-slate-400 px-2">
            Carpetes de Projecte
          </p>
          {loading && carpetes.length === 0 ? (
            <div className="p-6 text-center text-slate-400 text-xs flex flex-col items-center gap-2">
              <RefreshCw className="w-4 h-4 animate-spin text-emerald-600" />
              <span>Carregant carpetes...</span>
            </div>
          ) : carpetes.length === 0 ? (
            <div className="p-6 text-center text-slate-400 text-xs space-y-2">
              <Folder className="w-8 h-8 text-slate-300 dark:text-slate-700 mx-auto" />
              <p className="font-bold text-slate-600 dark:text-slate-300">Sense carpetes</p>
              <p className="text-[10px] text-slate-400">Estat Dia-0</p>
              <button
                onClick={() => setModalNovaCarpeta(true)}
                className="mt-1 px-3 py-1 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-bold"
              >
                + Crear Carpeta
              </button>
            </div>
          ) : (
            carpetes.map((c) => (
              <div
                key={c.id}
                onClick={() => setCarpetaSeleccionada(c)}
                className={`p-3 rounded-2xl border transition-all cursor-pointer ${
                  carpetaSeleccionada?.id === c.id
                    ? "bg-emerald-50 dark:bg-emerald-950/40 border-emerald-500 shadow-sm"
                    : "bg-slate-50 dark:bg-slate-850 border-slate-200 dark:border-slate-800 hover:border-slate-300"
                }`}
              >
                <div className="flex items-center gap-2">
                  <Folder className="w-4 h-4 text-emerald-600 shrink-0" />
                  <h4 className="text-xs font-bold text-slate-800 dark:text-slate-100 truncate">
                    {c.nom}
                  </h4>
                </div>
                {c.municipi && (
                  <p className="text-[10px] text-slate-500 mt-1 flex items-center gap-1">
                    <MapPin className="w-3 h-3 text-slate-400" />
                    {c.municipi}
                  </p>
                )}
              </div>
            ))
          )}
        </div>

        {/* Llista de Plànols de la carpeta */}
        <div className="flex-1 p-4 overflow-y-auto">
          {!carpetaSeleccionada ? (
            <div className="flex-1 flex flex-col items-center justify-center p-12 text-center text-slate-400">
              <Folder className="w-12 h-12 stroke-[1.5] text-slate-300 dark:text-slate-700 mb-2" />
              <p className="text-sm font-medium">Selecciona una carpeta de l'arbre lateral</p>
            </div>
          ) : planolsFiltrats.length === 0 ? (
            <div className="flex-1 flex flex-col items-center justify-center p-12 text-center bg-white dark:bg-slate-900 rounded-2xl border border-dashed border-slate-300 dark:border-slate-800 my-auto shadow-sm">
              <FileText className="w-10 h-10 text-slate-400 mb-3" />
              <h3 className="text-base font-bold text-slate-800 dark:text-slate-100">
                La carpeta està buida
              </h3>
              <p className="text-xs text-slate-500 max-w-xs mt-1">
                Estat Dia-0: Puja el primer arxiu DXF, GeoJSON o PDF georeferenciat d'aquesta zona.
              </p>
              <button
                onClick={() => setModalNouPlanol(true)}
                className="mt-3 px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold shadow"
              >
                + Pujar Plànol
              </button>
            </div>
          ) : (
            <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 overflow-hidden shadow-sm">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="bg-slate-50 dark:bg-slate-800/60 border-b border-slate-200 dark:border-slate-800 font-bold text-slate-600 dark:text-slate-300">
                    <th className="p-3">Ref. Plànol</th>
                    <th className="p-3">Títol del Document</th>
                    <th className="p-3">Format</th>
                    <th className="p-3">Georeferenciat</th>
                    <th className="p-3">Projecció Cartogràfica</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {planolsFiltrats.map((p) => (
                    <tr key={p.id} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/40 transition-colors">
                      <td className="p-3 font-mono font-bold text-emerald-700 dark:text-emerald-400">
                        {p.codi_referencia}
                      </td>
                      <td className="p-3 font-medium text-slate-900 dark:text-white">
                        {p.titol}
                      </td>
                      <td className="p-3 font-mono text-[10px] font-bold">
                        <span className="px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                          {p.tipus_fitxer}
                        </span>
                      </td>
                      <td className="p-3">
                        <span className={`px-2 py-0.5 rounded-full text-[9px] font-bold ${
                          p.es_georeferenciat
                            ? "bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300"
                            : "bg-slate-100 dark:bg-slate-800 text-slate-500"
                        }`}>
                          {p.es_georeferenciat ? "ETRS89 WGS84" : "Esquemàtic"}
                        </span>
                      </td>
                      <td className="p-3 font-mono text-slate-500 text-[11px]">
                        {p.projeccio || "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* Modal Nova Carpeta */}
      {modalNovaCarpeta && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-md bg-white dark:bg-slate-900 rounded-3xl shadow-2xl border border-slate-200 dark:border-slate-800 overflow-hidden">
            <div className="p-5 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
              <h3 className="font-bold text-sm text-slate-800 dark:text-slate-100 flex items-center gap-2">
                <FolderPlus className="w-4 h-4 text-emerald-600" />
                Nova Carpeta Cartogràfica
              </h3>
              <button
                onClick={() => setModalNovaCarpeta(false)}
                className="p-1 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleCrearCarpeta} className="p-5 space-y-4">
              <div>
                <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                  Nom de la Carpeta *
                </label>
                <input
                  type="text"
                  required
                  placeholder="Ex: Sector Nord Regants Garrigues"
                  value={novaCarpeta.nom}
                  onChange={(e) => setNovaCarpeta({ ...novaCarpeta, nom: e.target.value })}
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs font-medium"
                />
              </div>

              <div>
                <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                  Municipi / Terme
                </label>
                <input
                  type="text"
                  placeholder="Ex: Arbeca"
                  value={novaCarpeta.municipi}
                  onChange={(e) => setNovaCarpeta({ ...novaCarpeta, municipi: e.target.value })}
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs"
                />
              </div>

              <div className="pt-3 border-t border-slate-200 dark:border-slate-800 flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setModalNovaCarpeta(false)}
                  className="px-4 py-2 rounded-xl border border-slate-300 dark:border-slate-700 text-slate-600 dark:text-slate-300 text-xs font-medium"
                >
                  Cancel·lar
                </button>
                <button
                  type="submit"
                  disabled={guardant || !novaCarpeta.nom.trim()}
                  className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold shadow disabled:opacity-50"
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
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-md bg-white dark:bg-slate-900 rounded-3xl shadow-2xl border border-slate-200 dark:border-slate-800 overflow-hidden">
            <div className="p-5 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
              <h3 className="font-bold text-sm text-slate-800 dark:text-slate-100 flex items-center gap-2">
                <Plus className="w-4 h-4 text-emerald-600" />
                Alta de Plànol Tècnic
              </h3>
              <button
                onClick={() => setModalNouPlanol(false)}
                className="p-1 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleCrearPlanol} className="p-5 space-y-4">
              <div>
                <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                  Codi Referència *
                </label>
                <input
                  type="text"
                  required
                  placeholder="Ex: PLN-001"
                  value={nouPlanol.codi_referencia}
                  onChange={(e) => setNouPlanol({ ...nouPlanol, codi_referencia: e.target.value })}
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs font-mono"
                />
              </div>

              <div>
                <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                  Títol del Plànol *
                </label>
                <input
                  type="text"
                  required
                  placeholder="Ex: Xarxa Distribució PE-100 Polígon 3"
                  value={nouPlanol.titol}
                  onChange={(e) => setNouPlanol({ ...nouPlanol, titol: e.target.value })}
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs font-medium"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                    Format
                  </label>
                  <select
                    value={nouPlanol.tipus_fitxer}
                    onChange={(e) => setNouPlanol({ ...nouPlanol, tipus_fitxer: e.target.value })}
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs font-semibold"
                  >
                    <option value="DXF">AutoCAD DXF</option>
                    <option value="GEOJSON">GeoJSON</option>
                    <option value="KML">Google KML</option>
                    <option value="PDF">Plànol PDF</option>
                  </select>
                </div>

                <div>
                  <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                    Projecció
                  </label>
                  <input
                    type="text"
                    value={nouPlanol.projeccio}
                    onChange={(e) => setNouPlanol({ ...nouPlanol, projeccio: e.target.value })}
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs font-mono"
                  />
                </div>
              </div>

              <div className="pt-3 border-t border-slate-200 dark:border-slate-800 flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setModalNouPlanol(false)}
                  className="px-4 py-2 rounded-xl border border-slate-300 dark:border-slate-700 text-slate-600 dark:text-slate-300 text-xs font-medium"
                >
                  Cancel·lar
                </button>
                <button
                  type="submit"
                  disabled={guardant || !nouPlanol.titol.trim() || !nouPlanol.codi_referencia.trim()}
                  className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold shadow disabled:opacity-50"
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
