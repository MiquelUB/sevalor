"use client";

import React, { useState, useEffect } from "react";
import { useGestio } from "@/lib/gestio-context";
import { apiFetch } from "@/lib/api";
import GestioMap, { Feina, Operari } from "@/components/gestio/Map";
import { QuadrillesTauler } from "@/components/gestio/QuadrillesTauler";

export default function GestioMapaPage() {
  const { rolActiu } = useGestio();
  const [modeVisor, setModeVisor] = useState<"SAT" | "TOPO">("SAT");
  const [feines, setFeines] = useState<Feina[]>([]);
  const [operaris, setOperaris] = useState<Operari[]>([]);
  const [selectedOperariId, setSelectedOperariId] = useState<string | null>(null);
  const [selectedFeinaId, setSelectedFeinaId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [isEmbed, setIsEmbed] = useState(false);
  const [initialOperariId, setInitialOperariId] = useState<string | null>(null);
  const [filtreEstat, setFiltreEstat] = useState<"TOTS" | "EN_CURS" | "EN_RUTA" | "PENDENT">("TOTS");

  useEffect(() => {
    fetchData();
    if (typeof window !== "undefined") {
      setIsEmbed(window.location.search.includes("embed=true"));
      const params = new URLSearchParams(window.location.search);
      const opId = params.get("operari_id");
      if (opId) {
        setInitialOperariId(opId);
        setSelectedOperariId(opId);
      }
    }
  }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [feinesData, operarisData] = await Promise.all([
        apiFetch<any>("/gestio/feines?limit=100").catch(() => []),
        apiFetch<any>("/gestio/operaris").catch(() => []),
      ]);
      const opsList = Array.isArray(operarisData) ? operarisData : operarisData?.operaris || [];
      setFeines(Array.isArray(feinesData) ? feinesData : feinesData?.feines || []);
      setOperaris(opsList.filter((o: any) => o.estat === "ACTIU"));
    } catch (e) {
      console.error("Error carregant dades del mapa:", e);
    } finally {
      setLoading(false);
    }
  };

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

  const operarisFiltrats = operaris.filter((op) => {
    if (filtreEstat === "TOTS") return true;
    const feinaOp = feines.find((f) => f.cap_de_colla_id === op.id);
    if (filtreEstat === "EN_CURS") {
      return (
        op.estat_operatiu === "EN_OBRA" ||
        op.estat_operatiu === "EN_SERVEI" ||
        feinaOp?.estat === "EN_CURS" ||
        feinaOp?.estat === "ASSIGNADA"
      );
    }
    if (filtreEstat === "EN_RUTA") {
      return op.estat_operatiu === "EN_RUTA" || feinaOp?.estat === "EN_RUTA";
    }
    return !feinaOp || feinaOp.estat === "PENDENT";
  });

  const feinesActivesCount = feines.filter((f) =>
    ["PENDENT", "ASSIGNADA", "PROGRAMADA", "EN_CURS", "EN_OBRA", "EN_RUTA"].includes(f.estat)
  ).length;

  return (
    <div className="flex-1 flex flex-col space-y-lg w-full">
      {/* Stitch Split Map Container (screen_48d6b881522c4ffb9aa2f02fa047c9f9) */}
      <div className="flex flex-col lg:flex-row h-[680px] rounded-xl overflow-hidden shadow-lg border border-outline-variant/30 bg-surface-container-lowest">
        {/* Left Panel: Operaris Actius & Filtres (Stitch w-80) */}
        <div className="w-full lg:w-80 bg-surface-container-low border-r border-outline-variant/40 flex flex-col z-10 shadow-sm shrink-0">
          <div className="p-md border-b border-outline-variant/30 bg-surface-container-lowest">
            <div className="flex items-center justify-between mb-sm">
              <h1 className="font-section-title text-lg text-primary">
                Operaris i Mapa GIS
              </h1>
              <button
                onClick={fetchData}
                className="p-1 rounded-lg hover:bg-surface-container-high text-on-surface-variant"
                title="Actualitzar posicions"
              >
                <span className="material-symbols-outlined text-[18px]">refresh</span>
              </button>
            </div>
            {/* Filter Pills */}
            <div className="flex gap-xs overflow-x-auto pb-1">
              {(
                [
                  { id: "TOTS", label: `Tots (${operaris.length})` },
                  { id: "EN_CURS", label: "En curs" },
                  { id: "EN_RUTA", label: "En ruta" },
                  { id: "PENDENT", label: "Disponibles" },
                ] as const
              ).map((pill) => (
                <button
                  key={pill.id}
                  onClick={() => setFiltreEstat(pill.id)}
                  className={`px-sm py-xs rounded-full text-xs font-body-strong whitespace-nowrap transition-colors ${
                    filtreEstat === pill.id
                      ? "bg-primary text-on-primary shadow-sm"
                      : "bg-surface-container-highest text-on-surface-variant hover:bg-surface-variant"
                  }`}
                >
                  {pill.label}
                </button>
              ))}
            </div>
          </div>

          {/* Scrollable List of Real Operaris */}
          <div className="flex-1 overflow-y-auto p-sm space-y-sm custom-scrollbar">
            {operarisFiltrats.length === 0 ? (
              <div className="p-lg text-center text-xs text-on-surface-variant">
                Cap operari actiu per a aquest filtre.
              </div>
            ) : (
              operarisFiltrats.map((op) => {
                const feinaAssignada = feines.find(
                  (f) =>
                    f.cap_de_colla_id === op.id &&
                    ["ASSIGNADA", "PROGRAMADA", "EN_CURS", "EN_OBRA", "EN_RUTA"].includes(f.estat)
                );
                const isSelected = selectedOperariId === op.id;

                return (
                  <div
                    key={op.id}
                    onClick={() => setSelectedOperariId(isSelected ? null : op.id)}
                    className={`p-md rounded-xl bg-surface-container-lowest shadow-sm transition-all cursor-pointer border-l-4 ${
                      isSelected
                        ? "border-secondary-container ring-2 ring-secondary-container/30"
                        : feinaAssignada
                        ? "border-green-600 hover:bg-surface-bright"
                        : "border-primary hover:bg-surface-bright"
                    }`}
                  >
                    <div className="flex items-start justify-between mb-xs">
                      <div className="flex items-center gap-sm min-w-0">
                        <div className="relative shrink-0">
                          <div className="w-10 h-10 rounded-full bg-primary text-white font-bold flex items-center justify-center text-sm">
                            {(op.nom || "O").charAt(0).toUpperCase()}
                          </div>
                          <span
                            className={`absolute bottom-0 right-0 w-3 h-3 border-2 border-white rounded-full ${
                              feinaAssignada ? "bg-green-500" : "bg-secondary-container"
                            }`}
                          ></span>
                        </div>
                        <div className="min-w-0">
                          <h3 className="font-body-strong text-on-surface text-sm truncate">
                            {op.nom} {op.cognoms || ""}
                          </h3>
                          <p className="text-[11px] text-on-surface-variant truncate">
                            {feinaAssignada
                              ? `En curs: ${feinaAssignada.client_nom || feinaAssignada.codi}`
                              : op.rol || "Operari de Camp"}
                          </p>
                        </div>
                      </div>
                      <span className="font-data-tabular text-[10px] bg-surface-container px-xs py-0.5 rounded text-on-surface-variant shrink-0">
                        {feinaAssignada ? feinaAssignada.codi : "BASE"}
                      </span>
                    </div>
                    <div className="flex items-center gap-xs text-xs text-on-surface-variant mt-sm pt-xs border-t border-surface-container">
                      <span className="material-symbols-outlined text-[14px] text-primary">
                        location_on
                      </span>
                      <span className="truncate">
                        {feinaAssignada?.adreca || "Disponible per assignació Drop & Go"}
                      </span>
                    </div>
                  </div>
                );
              })
            )}
          </div>

          {/* Bottom Stats Summary (100% Real Data) */}
          <div className="p-md bg-surface-container-highest/50 border-t border-outline-variant/40">
            <div className="grid grid-cols-3 gap-xs text-center">
              <div>
                <p className="text-[10px] font-label-caps text-on-surface-variant uppercase">
                  Actius
                </p>
                <p className="font-section-title text-primary text-lg">{operaris.length}</p>
              </div>
              <div>
                <p className="text-[10px] font-label-caps text-on-surface-variant uppercase">
                  OTs Avui
                </p>
                <p className="font-section-title text-primary text-lg">{feinesActivesCount}</p>
              </div>
              <div>
                <p className="text-[10px] font-label-caps text-on-surface-variant uppercase">
                  Pendents
                </p>
                <p className="font-section-title text-secondary text-lg">
                  {feines.filter((f) => f.estat === "PENDENT").length}
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Right Map Canvas (Real Leaflet Map + Stitch Overlays) */}
        <div className="flex-1 relative bg-slate-950 overflow-hidden flex flex-col">
          {loading ? (
            <div className="w-full h-full flex items-center justify-center bg-slate-950">
              <p className="text-xs text-slate-400 animate-pulse font-mono">
                Carregant cartografia GIS i quadrilles...
              </p>
            </div>
          ) : (
            <GestioMap
              feines={feines}
              operaris={operaris}
              onDropAssignment={handleDropAssignment}
              modeVisor={modeVisor}
              onModeVisorChange={setModeVisor}
              initialOperariId={initialOperariId}
              selectedOperariId={selectedOperariId}
              onSelectOperari={setSelectedOperariId}
              selectedFeinaId={selectedFeinaId}
              onSelectFeina={setSelectedFeinaId}
              showSidebar={true}
            />
          )}
        </div>
      </div>

      {/* Tauler de Quadrilles per a Drag & Drop */}
      {!loading && (
        <QuadrillesTauler
          operaris={operaris}
          feines={feines}
          selectedOperariId={selectedOperariId}
          onSelectOperari={(id) => setSelectedOperariId(id)}
          onSelectFeina={(id) => setSelectedFeinaId(id)}
          onDropAssignment={handleDropAssignment}
        />
      )}
    </div>
  );
}
