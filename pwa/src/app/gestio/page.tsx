"use client";

import React, { useState, useEffect } from "react";
import {
  Users,
  Calendar,
  MapPin,
  FileText,
  Navigation,
} from "lucide-react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import { CrearOTModal } from "@/components/gestio/CrearOTModal";
import GestioMap, { Feina, Operari } from "@/components/gestio/Map";
import { QuadrillesTauler } from "@/components/gestio/QuadrillesTauler";

export default function GestioDashboardPage() {
  const [vistaActiva, setVistaActiva] = useState<"FEINA" | "RESULTATS">("FEINA");

  useEffect(() => {
    const syncVista = () => {
      if (typeof window !== "undefined") {
        setVistaActiva(
          window.location.search.includes("vista=resultats") ? "RESULTATS" : "FEINA"
        );
      }
    };
    syncVista();
    window.addEventListener("popstate", syncVista);
    window.addEventListener("sevalor-vista-change", syncVista);
    return () => {
      window.removeEventListener("popstate", syncVista);
      window.removeEventListener("sevalor-vista-change", syncVista);
    };
  }, []);

  const [showModalOT, setShowModalOT] = useState(false);
  const [hud, setHud] = useState({
    active_jobs: 0,
    completed_jobs: 0,
    open_incidents: 0,
    teams_on_field: 0,
    critical_stock: 0,
    vehicles_with_alerts: 0,
  });
  const [feines, setFeines] = useState<Feina[]>([]);
  const [operaris, setOperaris] = useState<Operari[]>([]);
  const [selectedOperariId, setSelectedOperariId] = useState<string | null>(null);
  const [selectedFeinaId, setSelectedFeinaId] = useState<string | null>(null);
  const [modeVisor, setModeVisor] = useState<"SAT" | "TOPO">("SAT");
  const [loading, setLoading] = useState(true);

  // Filtres per a la vista Treballs Finalitzats (Stitch screen_090f8e779aca498a8fc1dd0908d1e453)
  const [filtreClientResultats, setFiltreClientResultats] = useState<string>("TOTS");
  const [filtreEstatResultats, setFiltreEstatResultats] = useState<string>("TOTS");
  const [expandedRowId, setExpandedRowId] = useState<string | null>(null);

  const carregarDades = () => {
    setLoading(true);
    Promise.all([
      apiFetch<any>("/gestio/dashboard/hud").catch(() => null),
      apiFetch<any>("/gestio/feines?limit=100").catch(() => []),
      apiFetch<any>("/gestio/operaris").catch(() => []),
    ])
      .then(([hudData, feinesData, operarisData]) => {
        const fList = Array.isArray(feinesData) ? feinesData : feinesData?.feines || [];
        const oList = Array.isArray(operarisData) ? operarisData : operarisData?.operaris || [];
        setFeines(fList);
        setOperaris(oList.filter((o: any) => o.estat === "ACTIU"));

        if (hudData) {
          setHud(hudData);
        } else {
          const otsActives = fList.filter((f: any) =>
            ["PENDENT", "ASSIGNADA", "PROGRAMADA", "EN_CURS", "EN_OBRA", "EN_RUTA"].includes(f.estat)
          );
          const colles = new Set(
            otsActives
              .filter(
                (f: any) =>
                  f.cap_de_colla_id &&
                  ["ASSIGNADA", "PROGRAMADA", "EN_CURS", "EN_OBRA", "EN_RUTA"].includes(f.estat)
              )
              .map((f: any) => f.cap_de_colla_id)
          );
          setHud((prev) => ({
            ...prev,
            active_jobs: otsActives.length,
            teams_on_field: colles.size,
          }));
        }
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    carregarDades();
  }, []);

  const handleDropAssignment = async (feinaId: string, versio: number, operariId: string) => {
    try {
      await apiFetch(`/gestio/feines/${feinaId}/drop-and-go`, {
        method: "PATCH",
        body: JSON.stringify({
          versio: versio,
          cap_de_colla_id: operariId,
          data_programada: new Date().toISOString().split("T")[0],
        }),
      });
      setFeines((prev) =>
        prev.map((f) =>
          f.id === feinaId
            ? { ...f, cap_de_colla_id: operariId, estat: "ASSIGNADA", versio: (f.versio || 1) + 1 }
            : f
        )
      );
    } catch (err: any) {
      alert("Error en l'assignació: " + err.message);
    }
  };

  const handleFocusFeinaAlMapa = (feinaId: string) => {
    setSelectedFeinaId(feinaId);
    const mapaElement = document.getElementById("finestra-mapa-central");
    if (mapaElement) {
      mapaElement.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  };

  const handleFocusOperariAlMapa = (operariId: string) => {
    setSelectedOperariId(operariId);
    const mapaElement = document.getElementById("finestra-mapa-central");
    if (mapaElement) {
      mapaElement.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  };

  // Càlcul reactiu i coherent dels KPIs operatius en temps real (Zero Mock Data)
  const feinesActives = feines.filter((f) =>
    ["PENDENT", "ASSIGNADA", "PROGRAMADA", "EN_CURS", "EN_OBRA", "EN_RUTA"].includes(f.estat)
  );
  const feinesPendents = feines.filter((f) => f.estat === "PENDENT");
  const feinesCompletades = feines.filter((f) =>
    ["COMPLETADA", "FINALITZADA", "TANCADA", "FACTURADA"].includes(f.estat)
  );

  const feinesActivesAmbColla = new Set(
    feines
      .filter(
        (f) =>
          f.cap_de_colla_id &&
          ["ASSIGNADA", "PROGRAMADA", "EN_CURS", "EN_OBRA", "EN_RUTA"].includes(f.estat)
      )
      .map((f) => f.cap_de_colla_id)
  );

  const operarisEnServei = new Set(
    operaris
      .filter((o) => ["EN_SERVEI", "EN_RUTA", "EN_OBRA"].includes(o.estat_operatiu || ""))
      .map((o) => o.id)
  );

  const quadrillesActivesReals = Math.max(
    hud.teams_on_field,
    feinesActivesAmbColla.size,
    operarisEnServei.size
  );

  const feinesActivesReals = Math.max(hud.active_jobs, feinesActives.length);
  const feinesCompletadesReals = Math.max(hud.completed_jobs, feinesCompletades.length);
  const totalOperarisReals = Math.max(operaris.length, quadrillesActivesReals);
  const percentatgeOperarisRuta =
    totalOperarisReals > 0 ? Math.min(100, Math.round((quadrillesActivesReals / totalOperarisReals) * 100)) : 0;

  const clientsUnics = Array.from(
    new Set(feines.map((f) => f.client_nom).filter(Boolean))
  ) as string[];

  const feinesResultatsFiltrades = feines.filter((f) => {
    const matchClient = filtreClientResultats === "TOTS" || f.client_nom === filtreClientResultats;
    const matchEstat =
      filtreEstatResultats === "TOTS" ||
      (filtreEstatResultats === "FINALITZADES" &&
        ["COMPLETADA", "FINALITZADA", "TANCADA", "FACTURADA"].includes(f.estat)) ||
      f.estat === filtreEstatResultats;
    return matchClient && matchEstat;
  });

  return (
    <div className="flex flex-col w-full gap-lg">
      {/* Selector ràpid de vista FEINA / RESULTATS (sincronitzat amb la sub-barra Stitch) */}
      {vistaActiva === "RESULTATS" ? (
        /* ============================================================================
         * VISTA 2: TREBALLS FINALITZATS / RESULTATS (Stitch screen_090f8e779aca498a8fc1dd0908d1e453)
         * ============================================================================ */
        <div className="flex flex-col w-full gap-lg">
          <section className="grid grid-cols-12 gap-lg items-end">
            <div className="col-span-12 lg:col-span-5">
              <h1 className="font-display-lg text-display-lg text-primary mb-xs italic">
                Treballs Finalitzats i Historial d&apos;Ordres
              </h1>
              <p className="font-body-base text-on-surface-variant">
                Historial complet d&apos;intervencions, auditories tècniques i estat operatiu en temps real.
              </p>
            </div>
            <div className="col-span-12 lg:col-span-7 flex flex-wrap items-center justify-end gap-md">
              <div className="flex items-center gap-sm bg-surface-container-low p-xs rounded-lg shadow-sm border border-outline-variant/30">
                <div className="flex flex-col px-md py-xs border-r border-outline-variant/30">
                  <span className="font-label-caps text-[10px] text-on-surface-variant uppercase tracking-widest">
                    Client
                  </span>
                  <select
                    value={filtreClientResultats}
                    onChange={(e) => setFiltreClientResultats(e.target.value)}
                    className="bg-transparent font-body-strong text-sm outline-none cursor-pointer pr-lg text-on-surface"
                  >
                    <option value="TOTS">Tots els clients ({clientsUnics.length})</option>
                    {clientsUnics.map((nom) => (
                      <option key={nom} value={nom}>
                        {nom}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="flex flex-col px-md py-xs">
                  <span className="font-label-caps text-[10px] text-on-surface-variant uppercase tracking-widest">
                    Estat
                  </span>
                  <select
                    value={filtreEstatResultats}
                    onChange={(e) => setFiltreEstatResultats(e.target.value)}
                    className="bg-transparent font-body-strong text-sm outline-none cursor-pointer pr-lg text-on-surface"
                  >
                    <option value="TOTS">Tots els estats ({feines.length})</option>
                    <option value="FINALITZADES">Finalitzades ({feinesCompletades.length})</option>
                    <option value="EN_CURS">En Curs</option>
                    <option value="ASSIGNADA">Assignades</option>
                    <option value="PENDENT">Pendents ({feinesPendents.length})</option>
                  </select>
                </div>
              </div>
              <button
                onClick={() => setVistaActiva("FEINA")}
                className="flex items-center gap-sm bg-surface-container-high text-primary px-md py-md rounded-lg hover:bg-surface-container-highest transition-all font-body-strong text-sm"
              >
                <span className="material-symbols-outlined text-[18px]">dashboard</span>
                <span>Tornar al Dashboard</span>
              </button>
              <button
                onClick={() => setShowModalOT(true)}
                className="flex items-center gap-sm bg-primary text-on-primary px-xl py-md rounded-lg shadow-md hover:bg-primary-container transition-all group"
              >
                <span className="material-symbols-outlined">add_task</span>
                <span className="font-body-strong">Nova Feina</span>
              </button>
            </div>
          </section>

          {/* Taula d'Auditoria d'Ordres (Stitch style, 100% Zero Mock Data) */}
          <section className="bg-surface-container-lowest rounded-xl shadow-xl overflow-hidden border border-outline-variant/20">
            {feinesResultatsFiltrades.length === 0 ? (
              <div className="p-12 text-center">
                <span className="material-symbols-outlined text-4xl text-outline mb-2">
                  assignment_turned_in
                </span>
                <p className="font-body-strong text-on-surface">
                  No hi ha ordres de treball que coincideixin amb el filtre seleccionat.
                </p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="bg-surface-container-high/50 border-b border-outline-variant/30">
                      <th className="px-lg py-md font-label-caps text-on-surface-variant">CODI</th>
                      <th className="px-lg py-md font-label-caps text-on-surface-variant">CLIENT</th>
                      <th className="px-lg py-md font-label-caps text-on-surface-variant">TÍTOL / INTERVENCIÓ</th>
                      <th className="px-lg py-md font-label-caps text-on-surface-variant">CAP DE COLLA</th>
                      <th className="px-lg py-md font-label-caps text-on-surface-variant text-center">DATA</th>
                      <th className="px-lg py-md font-label-caps text-on-surface-variant">UBICACIÓ</th>
                      <th className="px-lg py-md font-label-caps text-on-surface-variant">ESTAT</th>
                      <th className="px-lg py-md font-label-caps text-on-surface-variant text-right">ACCIONS</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-outline-variant/10">
                    {feinesResultatsFiltrades.map((feina) => {
                      const isExpanded = expandedRowId === feina.id;
                      return (
                        <React.Fragment key={feina.id}>
                          <tr
                            onClick={() => setExpandedRowId(isExpanded ? null : feina.id)}
                            className="hover:bg-surface-container-low/50 transition-colors cursor-pointer group"
                          >
                            <td className="px-lg py-md font-data-tabular font-bold text-primary">
                              {feina.codi}
                            </td>
                            <td className="px-lg py-md font-body-strong text-on-surface">
                              {feina.client_nom || "—"}
                            </td>
                            <td className="px-lg py-md text-sm text-on-surface">
                              <div className="font-body-strong">{feina.titol}</div>
                              {feina.descripcio && (
                                <div className="text-xs text-on-surface-variant line-clamp-1">
                                  {feina.descripcio}
                                </div>
                              )}
                            </td>
                            <td className="px-lg py-md text-xs text-on-surface-variant">
                              {feina.cap_de_colla_nom || "Pendent d'assignar"}
                            </td>
                            <td className="px-lg py-md font-data-tabular text-center">
                              {feina.data_planificacio || "—"}
                            </td>
                            <td className="px-lg py-md text-xs text-on-surface-variant max-w-xs truncate">
                              {feina.adreca || "—"}
                            </td>
                            <td className="px-lg py-md">
                              <div
                                className={`flex items-center gap-xs ${
                                  ["COMPLETADA", "FINALITZADA", "TANCADA"].includes(feina.estat)
                                    ? "text-green-600"
                                    : feina.estat === "PENDENT"
                                    ? "text-secondary"
                                    : "text-primary"
                                }`}
                              >
                                <span className="material-symbols-outlined text-[14px]">
                                  {["COMPLETADA", "FINALITZADA", "TANCADA"].includes(feina.estat)
                                    ? "check_circle"
                                    : "schedule"}
                                </span>
                                <span className="font-label-caps">{feina.estat}</span>
                              </div>
                            </td>
                            <td className="px-lg py-md text-right">
                              <div className="flex items-center justify-end gap-sm">
                                <button
                                  type="button"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    setVistaActiva("FEINA");
                                    setTimeout(() => handleFocusFeinaAlMapa(feina.id), 100);
                                  }}
                                  className="p-xs hover:bg-surface-container-highest rounded text-on-surface-variant"
                                  title="Veure al Mapa"
                                >
                                  <span className="material-symbols-outlined text-[18px]">
                                    location_on
                                  </span>
                                </button>
                                <button
                                  type="button"
                                  className="p-xs hover:bg-surface-container-highest rounded text-on-surface-variant"
                                  title="Detalls"
                                >
                                  <span className="material-symbols-outlined text-[18px]">
                                    {isExpanded ? "expand_less" : "expand_more"}
                                  </span>
                                </button>
                              </div>
                            </td>
                          </tr>
                          {isExpanded && (
                            <tr className="bg-surface-container-low/40">
                              <td colSpan={8} className="px-xl py-lg">
                                <div className="grid grid-cols-1 md:grid-cols-3 gap-lg">
                                  <div className="bg-surface-container-lowest p-md rounded-xl border border-outline-variant/30">
                                    <span className="font-label-caps text-on-surface-variant uppercase block mb-xs">
                                      Descripció Tècnica
                                    </span>
                                    <p className="text-sm text-on-surface">
                                      {feina.descripcio || "Sense observacions addicionals registrades."}
                                    </p>
                                  </div>
                                  <div className="bg-surface-container-lowest p-md rounded-xl border border-outline-variant/30">
                                    <span className="font-label-caps text-on-surface-variant uppercase block mb-xs">
                                      Localització i Client
                                    </span>
                                    <p className="text-sm font-body-strong text-primary">
                                      {feina.client_nom || "Client no especificat"}
                                    </p>
                                    <p className="text-xs text-on-surface-variant mt-1">
                                      {feina.adreca || "Sense adreça"}
                                    </p>
                                  </div>
                                  <div className="bg-surface-container-lowest p-md rounded-xl border border-outline-variant/30 flex flex-col justify-between">
                                    <div>
                                      <span className="font-label-caps text-on-surface-variant uppercase block mb-xs">
                                        Assignació Operativa
                                      </span>
                                      <p className="text-sm font-body-strong text-on-surface">
                                        Responsable: {feina.cap_de_colla_nom || "Pendent d'assignar"}
                                      </p>
                                    </div>
                                    <div className="flex gap-sm mt-md">
                                      <Link
                                        href="/gestio/comptabilitat"
                                        className="flex-1 py-xs px-sm bg-surface-container-high hover:bg-surface-container-highest text-primary font-body-strong text-xs rounded-lg transition-colors text-center"
                                      >
                                        Facturació SIF
                                      </Link>
                                      <Link
                                        href="/gestio/planols"
                                        className="flex-1 py-xs px-sm bg-secondary-container/15 hover:bg-secondary-container/25 text-secondary font-body-strong text-xs rounded-lg transition-colors text-center"
                                      >
                                        Plànols GIS
                                      </Link>
                                    </div>
                                  </div>
                                </div>
                              </td>
                            </tr>
                          )}
                        </React.Fragment>
                      );
                    })}
                  </tbody>
                  <tfoot>
                    <tr className="bg-primary text-on-primary">
                      <td colSpan={4} className="px-lg py-md font-body-strong text-right">
                        Resum del Període Seleccionat
                      </td>
                      <td className="px-lg py-md font-data-tabular text-center font-bold">
                        {feinesResultatsFiltrades.length} OTs
                      </td>
                      <td className="px-lg py-md font-data-tabular font-bold text-primary-fixed">
                        {feinesActivesReals} Actives
                      </td>
                      <td colSpan={2} className="px-lg py-md font-data-tabular font-bold text-secondary-fixed">
                        {feinesCompletadesReals} Completades
                      </td>
                    </tr>
                  </tfoot>
                </table>
              </div>
            )}
          </section>
        </div>
      ) : (
        /* ============================================================================
         * VISTA 1: DASHBOARD PRINCIPAL / TORRE DE CONTROL (Stitch screen_c3390d6c13d8430ab549f29c1e18ac8d)
         * ============================================================================ */
        <>
          {/* 1. KPI ROW (4 + 1 Stitch Cards, 100% Real Data) */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-lg">
            {/* Feines d'avui */}
            <div
              onClick={() => {
                const el = document.getElementById("taula-ordres-sistema");
                el?.scrollIntoView({ behavior: "smooth" });
              }}
              className="bg-surface-container-lowest p-lg rounded-xl shadow-sm border-b-2 border-primary flex flex-col justify-between cursor-pointer hover:shadow-md transition-all"
            >
              <div className="flex justify-between items-start">
                <span className="font-label-caps text-on-surface-variant uppercase">
                  Feines d&apos;avui
                </span>
                <span className="material-symbols-outlined text-primary bg-primary/5 p-xs rounded-lg">
                  assignment
                </span>
              </div>
              <div className="mt-md">
                <div className="font-display-lg text-display-lg text-on-surface">
                  {feinesActivesReals}
                </div>
                <div className="flex gap-sm mt-xs text-xs">
                  <span className="text-green-600 font-body-strong">
                    {Math.max(0, feinesActivesReals - feinesPendents.length)} assignades
                  </span>
                  <span className="text-outline">•</span>
                  <span className="text-secondary font-body-strong">
                    {feinesPendents.length} pendents
                  </span>
                </div>
              </div>
            </div>

            {/* Operaris en ruta / Quadrilles Actives */}
            <Link
              href="/gestio/operaris"
              className="bg-surface-container-lowest p-lg rounded-xl shadow-sm border-b-2 border-green-500 flex flex-col justify-between hover:shadow-md transition-all"
            >
              <div className="flex justify-between items-start">
                <span className="font-label-caps text-on-surface-variant uppercase">
                  Operaris en ruta
                </span>
                <span className="material-symbols-outlined text-green-600 bg-green-50 p-xs rounded-lg">
                  engineering
                </span>
              </div>
              <div className="mt-md">
                <div className="font-display-lg text-display-lg text-on-surface">
                  {quadrillesActivesReals}
                  <span className="text-outline font-normal text-lg">/{totalOperarisReals}</span>
                </div>
                <div className="w-full bg-surface-container h-1.5 rounded-full mt-sm overflow-hidden">
                  <div
                    className="bg-green-500 h-full transition-all duration-300"
                    style={{ width: `${percentatgeOperarisRuta}%` }}
                  ></div>
                </div>
              </div>
            </Link>

            {/* Incidències obertes */}
            <Link
              href="/gestio/notificacions"
              className="bg-surface-container-lowest p-lg rounded-xl shadow-sm border-b-2 border-error flex flex-col justify-between hover:shadow-md transition-all"
            >
              <div className="flex justify-between items-start">
                <span className="font-label-caps text-on-surface-variant uppercase">
                  Incidències obertes
                </span>
                <span className="material-symbols-outlined text-error bg-error-container/30 p-xs rounded-lg">
                  warning
                </span>
              </div>
              <div className="mt-md">
                <div className="font-display-lg text-display-lg text-error">
                  {hud.open_incidents}
                </div>
                <p className="text-xs text-on-error-container mt-xs font-medium">
                  {hud.open_incidents > 0
                    ? "Requereixen atenció a Torre de Control"
                    : "Cap incidència crítica activa"}
                </p>
              </div>
            </Link>

            {/* Estat Flota */}
            <Link
              href="/gestio/flota"
              className="bg-surface-container-lowest p-lg rounded-xl shadow-sm border-b-2 border-primary-container flex flex-col justify-between hover:shadow-md transition-all"
            >
              <div className="flex justify-between items-start">
                <span className="font-label-caps text-on-surface-variant uppercase">
                  Estat Flota
                </span>
                <span className="material-symbols-outlined text-primary bg-primary/5 p-xs rounded-lg">
                  local_shipping
                </span>
              </div>
              <div className="mt-md">
                <div className="font-display-lg text-display-lg text-on-surface">
                  {hud.vehicles_with_alerts}
                </div>
                <p className="text-xs text-on-surface-variant mt-xs font-medium">
                  Vehicles amb alerta tècnica
                </p>
              </div>
            </Link>

            {/* Estoc Crític & Completades */}
            <Link
              href="/gestio/magatzem"
              className="bg-surface-container-lowest p-lg rounded-xl shadow-sm border-b-2 border-secondary-container flex flex-col justify-between hover:shadow-md transition-all"
            >
              <div className="flex justify-between items-start">
                <span className="font-label-caps text-on-surface-variant uppercase">
                  Alertes d&apos;Estoc
                </span>
                <span className="material-symbols-outlined text-secondary bg-secondary-container/10 p-xs rounded-lg">
                  inventory_2
                </span>
              </div>
              <div className="mt-md">
                <div className="font-display-lg text-display-lg text-on-surface font-data-tabular">
                  {hud.critical_stock}
                </div>
                <div className="flex items-center gap-xs text-secondary text-xs mt-xs font-body-strong">
                  <span className="material-symbols-outlined text-[14px]">trending_up</span>
                  <span>{feinesCompletadesReals} OTs completades</span>
                </div>
              </div>
            </Link>
          </div>

          {/* 2. BARRA D'ACCIONS RÀPIDES */}
          <div className="flex flex-wrap items-center justify-between gap-md">
            <div>
              <h1 className="font-section-title text-section-title text-primary">
                Ordres de Treball i Torre de Control GIS
              </h1>
              <p className="text-xs text-on-surface-variant">
                 Supervisió d&apos;operacions en temps real, assignació Drop &amp; Go i telemetria de quadrilles.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-sm">
              <button
                onClick={() => setShowModalOT(true)}
                className="px-lg py-sm rounded-lg bg-secondary-container hover:bg-secondary text-on-secondary-container hover:text-white text-sm font-body-strong shadow-md flex items-center gap-xs transition-all cursor-pointer"
              >
                <span className="material-symbols-outlined text-[18px]">add</span>
                <span>Nova Feina / Crear Ordre de Treball</span>
              </button>
              <Link
                href="/gestio/mapa"
                className="px-lg py-sm rounded-lg bg-primary hover:bg-primary-container text-on-primary text-sm font-body-strong shadow-sm flex items-center gap-xs transition-all"
              >
                <span className="material-symbols-outlined text-[18px]">map</span>
                <span>Obrir Mapa Interactiu Complet</span>
              </Link>
            </div>
          </div>

          {/* 3. CENTRAL SPLIT SECTION: MAPA EN TEMPS REAL (7 COLS) + PROPERES FEINES (5 COLS) */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-lg">
            {/* Map Widget (7 cols) */}
            <div
              id="finestra-mapa-central"
              className="lg:col-span-7 bg-surface-container-lowest rounded-xl shadow-sm overflow-hidden flex flex-col h-[540px] border border-outline-variant/30"
            >
              <div className="p-md border-b border-surface-container flex justify-between items-center bg-surface-container-lowest">
                <h2 className="font-section-title text-lg text-on-surface flex items-center gap-sm">
                  <span className="material-symbols-outlined text-primary">public</span>
                  Mapa d&apos;Operacions en Temps Real
                </h2>
                <div className="flex items-center gap-md">
                  <span className="flex items-center gap-xs text-xs font-label-caps text-green-600 bg-green-50 px-sm py-xs rounded-full">
                    <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></span>
                    ACTIU ARA
                  </span>
                </div>
              </div>
              <div className="flex-1 relative bg-slate-950 overflow-hidden">
                {loading ? (
                  <div className="w-full h-full flex items-center justify-center bg-slate-950">
                    <p className="text-xs text-slate-400 animate-pulse font-mono">
                      Carregant cartografia GIS i posicionament...
                    </p>
                  </div>
                ) : (
                  <GestioMap
                    feines={feines}
                    operaris={operaris}
                    onDropAssignment={handleDropAssignment}
                    modeVisor={modeVisor}
                    onModeVisorChange={setModeVisor}
                    selectedOperariId={selectedOperariId}
                    onSelectOperari={setSelectedOperariId}
                    selectedFeinaId={selectedFeinaId}
                    onSelectFeina={setSelectedFeinaId}
                    showSidebar={false}
                  />
                )}
              </div>
            </div>

            {/* Upcoming Jobs List (5 cols - Stitch style) */}
            <div className="lg:col-span-5 bg-surface-container-lowest rounded-xl shadow-sm flex flex-col h-[540px] border border-outline-variant/30">
              <div className="p-md border-b border-surface-container flex justify-between items-center">
                <h2 className="font-section-title text-lg text-on-surface">Properes Feines</h2>
                <button
                  onClick={() => setShowModalOT(true)}
                  className="bg-secondary-container text-on-secondary-container hover:opacity-90 px-md py-xs rounded-lg font-body-strong text-xs flex items-center gap-xs transition-all shadow-sm"
                >
                  <span className="material-symbols-outlined text-sm">add</span>
                  Nova Feina
                </button>
              </div>
              <div className="flex-1 overflow-y-auto p-md space-y-sm custom-scrollbar">
                {feines.length === 0 ? (
                  <div className="h-full flex flex-col items-center justify-center text-center p-lg text-on-surface-variant">
                    <span className="material-symbols-outlined text-4xl text-outline mb-sm">
                      event_busy
                    </span>
                    <p className="font-body-strong text-sm">Cap ordre de treball programada</p>
                    <p className="text-xs text-outline mt-xs">
                      Crea una nova intervenció per assignar-la a les quadrilles de camp.
                    </p>
                  </div>
                ) : (
                  feines.slice(0, 8).map((feina) => {
                    const statusColor =
                      feina.estat === "PENDENT"
                        ? "bg-secondary-container"
                        : feina.estat === "EN_CURS" || feina.estat === "EN_RUTA"
                        ? "bg-green-500"
                        : "bg-primary";

                    return (
                      <div
                        key={feina.id}
                        onClick={() => handleFocusFeinaAlMapa(feina.id)}
                        className="p-md rounded-lg bg-surface-container-low hover:bg-surface-container transition-colors flex items-center justify-between cursor-pointer group"
                      >
                        <div className="flex items-center gap-md min-w-0">
                          <div className={`w-1 h-10 ${statusColor} rounded-full shrink-0`}></div>
                          <div className="min-w-0">
                            <h4 className="font-body-strong text-on-surface truncate">
                              {feina.titol}
                            </h4>
                            <p className="text-xs text-on-surface-variant truncate">
                              Client: {feina.client_nom || "Sense especificar"} • {feina.codi}
                            </p>
                          </div>
                        </div>
                        <div className="text-right flex flex-col items-end shrink-0 ml-sm">
                          <span className="font-data-tabular font-semibold text-primary text-xs">
                            {feina.data_planificacio || "Avui"}
                          </span>
                          <span className="text-[10px] font-label-caps text-on-surface-variant mt-xs">
                            {feina.cap_de_colla_nom || feina.estat}
                          </span>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
              <div className="p-sm border-t border-surface-container text-center">
                <button
                  onClick={() => setVistaActiva("RESULTATS")}
                  className="text-xs font-body-strong text-primary hover:underline"
                >
                  Veure tot l&apos;historial d&apos;ordres ({feines.length}) &rarr;
                </button>
              </div>
            </div>
          </div>

          {/* 4. QUADRILLES D'OPERARIS ACTIVES (Drag & Drop) */}
          <QuadrillesTauler
            operaris={operaris}
            feines={feines}
            selectedOperariId={selectedOperariId}
            onSelectOperari={handleFocusOperariAlMapa}
            onSelectFeina={handleFocusFeinaAlMapa}
            onDropAssignment={handleDropAssignment}
          />

          {/* 5. ALERTES DEL SISTEMA (Stitch Bottom Section) */}
          <div className="bg-surface-container-lowest rounded-xl shadow-sm p-lg border border-outline-variant/30">
            <div className="flex items-center justify-between mb-md">
              <div className="flex items-center gap-sm">
                <span className="material-symbols-outlined text-error">notifications_active</span>
                <h2 className="font-section-title text-lg text-on-surface">
                  Alertes del Sistema i Telemetria Operativa
                </h2>
              </div>
              <span className="text-xs text-outline"> Temps real · Zero-Trust</span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-md">
              <Link
                href="/gestio/magatzem"
                className="flex items-start gap-md p-md rounded-lg bg-error-container/15 border border-error/20 hover:bg-error-container/25 transition-colors"
              >
                <span className="material-symbols-outlined text-error mt-0.5">inventory_2</span>
                <div>
                  <h4 className="font-body-strong text-on-error-container text-sm">
                    Estoc Crític: {hud.critical_stock} referències
                  </h4>
                  <p className="text-xs text-on-error-container/80 mt-xs">
                    Articles per sota del llindar mínim de seguretat al magatzem central.
                  </p>
                  <span className="mt-sm inline-block text-[11px] font-label-caps text-error underline uppercase">
                    Gestionar Magatzem
                  </span>
                </div>
              </Link>

              <Link
                href="/gestio/flota"
                className="flex items-start gap-md p-md rounded-lg bg-secondary-container/15 border border-secondary-container/30 hover:bg-secondary-container/25 transition-colors"
              >
                <span className="material-symbols-outlined text-secondary mt-0.5">
                  local_shipping
                </span>
                <div>
                  <h4 className="font-body-strong text-on-secondary-container text-sm">
                    Flota i Manteniment: {hud.vehicles_with_alerts} alertes
                  </h4>
                  <p className="text-xs text-on-secondary-container/80 mt-xs">
                    Control d&apos;ITV, revisions quilomètriques i odòmetres verificats per IA.
                  </p>
                  <span className="mt-sm inline-block text-[11px] font-label-caps text-secondary underline uppercase">
                    Revisar Vehicles
                  </span>
                </div>
              </Link>

              <Link
                href="/gestio/notificacions"
                className="flex items-start gap-md p-md rounded-lg bg-surface-container-high border border-outline-variant hover:bg-surface-container-highest transition-colors"
              >
                <span className="material-symbols-outlined text-primary mt-0.5">warning</span>
                <div>
                  <h4 className="font-body-strong text-on-surface text-sm">
                    Incidències de Camp: {hud.open_incidents} obertes
                  </h4>
                  <p className="text-xs text-on-surface-variant mt-xs">
                    Avisos d&apos;operaris en ruta, notes de veu i tiquets pendents de resolució.
                  </p>
                  <span className="mt-sm inline-block text-[11px] font-label-caps text-primary underline uppercase">
                    Obrir Centre d&apos;Incidències
                  </span>
                </div>
              </Link>
            </div>
          </div>

          {/* 6. LLISTAT COMPLET D'ORDRES DE TREBALL REGISTRADES */}
          <div
            id="taula-ordres-sistema"
            className="bg-surface-container-lowest rounded-xl border border-outline-variant/30 shadow-sm p-lg space-y-md"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-sm">
                <FileText className="w-5 h-5 text-primary" />
                <h2 className="font-section-title text-lg text-on-surface">
                  Ordres de Treball Registrades al Sistema
                </h2>
              </div>
              <Link
                href="/gestio/mapa"
                className="text-xs font-body-strong text-primary hover:underline flex items-center gap-1"
              >
                Veure totes al mapa complet &rarr;
              </Link>
            </div>

            {feines.length === 0 ? (
              <div className="p-8 text-center bg-surface-container-low rounded-xl border border-dashed border-outline-variant">
                <p className="text-sm font-medium text-on-surface-variant">
                  No hi ha ordres de treball registrades per a aquesta empresa.
                </p>
                <button
                  onClick={() => setShowModalOT(true)}
                  className="mt-3 px-4 py-2 rounded-lg bg-primary hover:bg-primary-container text-white text-xs font-bold transition-colors"
                >
                  + Crear la primera Ordre de Treball
                </button>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead>
                    <tr className="border-b border-surface-container-high text-[11px] font-label-caps text-on-surface-variant uppercase tracking-wider bg-surface-container-low/50">
                      <th className="py-3 px-4">Codi</th>
                      <th className="py-3 px-4">Títol / Descripció</th>
                      <th className="py-3 px-4">Client</th>
                      <th className="py-3 px-4">Cap de Colla</th>
                      <th className="py-3 px-4">Estat</th>
                      <th className="py-3 px-4">Data Planificada</th>
                      <th className="py-3 px-4">Ubicació</th>
                      <th className="py-3 px-4 text-right">Acció</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-surface-container">
                    {feines.slice(0, 15).map((feina) => (
                      <tr
                        key={feina.id}
                        draggable
                        onDragStart={(e) => {
                          e.dataTransfer.setData("feinaId", feina.id);
                          e.dataTransfer.setData("versio", (feina.versio || 1).toString());
                        }}
                        className="hover:bg-surface-container-low/60 transition-colors cursor-grab active:cursor-grabbing"
                        title="Arrossega cap a una quadrilla per reassignar"
                      >
                        <td className="py-3 px-4 font-data-tabular font-bold text-primary text-xs">
                          {feina.codi}
                        </td>
                        <td className="py-3 px-4 font-body-strong text-on-surface">
                          <div>{feina.titol}</div>
                          {feina.descripcio && (
                            <div className="text-xs text-on-surface-variant font-normal line-clamp-1">
                              {feina.descripcio}
                            </div>
                          )}
                        </td>
                        <td className="py-3 px-4 text-xs font-medium text-on-surface-variant">
                          {feina.client_nom || "-"}
                        </td>
                        <td className="py-3 px-4 text-xs">
                          {feina.cap_de_colla_nom ? (
                            <span className="font-body-strong text-on-surface flex items-center gap-1">
                              <Users className="w-3.5 h-3.5 text-primary" />
                              {feina.cap_de_colla_nom}
                            </span>
                          ) : (
                            <span className="text-secondary text-[11px] font-medium italic">
                              Pendent d&apos;assignar
                            </span>
                          )}
                        </td>
                        <td className="py-3 px-4">
                          <span
                            className={`text-[11px] font-label-caps px-2.5 py-0.5 rounded-full ${
                              feina.estat === "PENDENT"
                                ? "bg-secondary-container/20 text-on-secondary-container"
                                : feina.estat === "ASSIGNADA" || feina.estat === "PROGRAMADA"
                                ? "bg-primary/10 text-primary"
                                : "bg-green-100 text-green-700"
                            }`}
                          >
                            {feina.estat}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-xs text-on-surface-variant flex items-center gap-1.5">
                          <Calendar className="w-3.5 h-3.5 text-outline" />
                          {feina.data_planificacio || "-"}
                        </td>
                        <td className="py-3 px-4 text-xs text-on-surface-variant">
                          <div className="flex items-center gap-1 truncate max-w-xs">
                            <MapPin className="w-3.5 h-3.5 text-secondary shrink-0" />
                            <span className="truncate">{feina.adreca}</span>
                          </div>
                        </td>
                        <td className="py-3 px-4 text-right">
                          <button
                            type="button"
                            onClick={() => handleFocusFeinaAlMapa(feina.id)}
                            className="px-3 py-1.5 text-xs font-body-strong rounded-lg bg-primary/10 hover:bg-primary hover:text-white text-primary inline-flex items-center gap-1 transition-colors"
                          >
                            <Navigation className="w-3 h-3" />
                            <span>Veure al mapa</span>
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}

      {showModalOT && (
        <CrearOTModal
          onClose={() => setShowModalOT(false)}
          onSuccess={() => carregarDades()}
        />
      )}
    </div>
  );
}
