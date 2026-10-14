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
      const opsList = Array.isArray(operarisData) ? operarisData : (operarisData?.operaris || []);
      setFeines(Array.isArray(feinesData) ? feinesData : (feinesData?.feines || []));
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
      // Actualitzar l'estat local
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

  return (
    <div className="flex-1 flex flex-col p-4 md:p-6 space-y-6 max-w-7xl mx-auto w-full">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
        <div>
          <h1 className="text-xl font-bold text-slate-900 dark:text-white">
            Torre de Control & Mapa Cartogràfic
          </h1>
          <p className="text-xs text-slate-500">
            Visualització cartogràfica d'alta resolució i assignació dinàmica Drop & Go de feines de camp.
          </p>
        </div>
      </div>

      {loading ? (
        <div className="h-[600px] flex items-center justify-center bg-slate-950 rounded-2xl border border-slate-800">
          <p className="text-xs text-slate-400 animate-pulse font-mono">
            Carregant cartografia GIS i quadrilles...
          </p>
        </div>
      ) : (
        <>
          {/* 1. FINESTRA ÚNICA DEL MAPA (Gran, Espaiosa i Neta) */}
          <div className="h-[620px] md:h-[680px] rounded-2xl md:rounded-3xl overflow-hidden border border-slate-200 dark:border-slate-800 shadow-sm relative w-full bg-slate-950 flex flex-col">
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
          </div>

          {/* 2. QUADRILLES D'OPERARIS (FORA DE LA FINESTRA DEL MAPA) */}
          <QuadrillesTauler
            operaris={operaris}
            feines={feines}
            selectedOperariId={selectedOperariId}
            onSelectOperari={(id) => setSelectedOperariId(id)}
            onSelectFeina={(id) => setSelectedFeinaId(id)}
            onDropAssignment={handleDropAssignment}
          />
        </>
      )}
    </div>
  );
}
