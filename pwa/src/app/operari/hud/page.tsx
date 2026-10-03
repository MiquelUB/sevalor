"use client";

import { useEffect, useState } from "react";
import { db } from "@/lib/offline/db";
import { apiFetch } from "@/lib/api";

export default function HUDPage() {
  const [isOnline, setIsOnline] = useState(true);
  const [localOrdresCount, setLocalOrdresCount] = useState<number | null>(null);
  const [localIncidenciesCount, setLocalIncidenciesCount] = useState<number | null>(null);

  useEffect(() => {
    setIsOnline(navigator.onLine);
    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);

    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);
    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, []);

  useEffect(() => {
    // Carrega offline (Zero Mock, des de la BD xifrada de l'operari)
    const loadLocal = async () => {
      try {
        const p = await db.ordres.count();
        setLocalOrdresCount(p);

        const inc = await db.incidencies.count();
        setLocalIncidenciesCount(inc);
      } catch (err) {
        console.error("Error loading local stats:", err);
      }
    };

    loadLocal();
  }, []);

  return (
    <div className="p-4 space-y-4">
      <h1 className="text-xl font-bold">HUD Operari</h1>
      <div className="bg-slate-100 dark:bg-slate-800 p-4 rounded-lg shadow-sm">
        <p>Connexió: {isOnline ? "Online" : "Offline"}</p>
        <p>Ordres pendents (Local): {localOrdresCount ?? 0}</p>
        <p>Incidències pendents: {localIncidenciesCount ?? 0}</p>
      </div>
    </div>
  );
}
