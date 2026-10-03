"use client";

import React, { useState, useEffect } from "react";
import { useGestio } from "@/lib/gestio-context";
import { apiFetch } from "@/lib/api";
import GestioMap, { Feina, Operari } from "@/components/gestio/Map";

export default function GestioMapaPage() {
  const { rolActiu } = useGestio();
  const [modeVisor, setModeVisor] = useState<"SAT" | "TOPO">("SAT");
  const [feines, setFeines] = useState<Feina[]>([]);
  const [operaris, setOperaris] = useState<Operari[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [feinesData, operarisData] = await Promise.all([
        apiFetch<Feina[]>("/gestio/feines?limit=100"),
        apiFetch<Operari[]>("/gestio/operaris"),
      ]);
      setFeines(feinesData || []);
      setOperaris((operarisData || []).filter((o) => o.rol === "OPERARI" && o.estat === "ACTIU"));
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
            ? { ...f, cap_de_colla_id: operariId, estat: "ASSIGNADA", versio: f.versio + 1 }
            : f
        )
      );
    } catch (err: any) {
      alert("Error en l'assignació: " + err.message);
    }
  };

  return (
    <div className="flex-1 flex flex-col p-6 space-y-4 max-w-7xl mx-auto w-full">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-900 dark:text-white">
            Torre de Control & Mapa Cartogràfic
          </h1>
          <p className="text-xs text-slate-500">
            Assignació dinàmica Drop & Go de feines de camp als caps de colla actius.
          </p>
        </div>
      </div>

      {loading ? (
        <div className="flex-1 min-h-[400px] flex items-center justify-center bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800">
          <p className="text-xs text-slate-400 animate-pulse">Carregant mapa i quadrilles...</p>
        </div>
      ) : (
        <GestioMap
          feines={feines}
          operaris={operaris}
          onDropAssignment={handleDropAssignment}
          modeVisor={modeVisor}
          onModeVisorChange={setModeVisor}
        />
      )}
    </div>
  );
}
