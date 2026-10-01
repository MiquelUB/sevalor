import { useState, useEffect, useCallback } from "react";
import { apiFetch } from "../api";
import { localDB } from "../db";
import { OrdreTreballLocal } from "../types/operari";

export function useAssignacions() {
  const [ordres, setOrdres] = useState<OrdreTreballLocal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchLocalAndRemote = useCallback(async () => {
    setLoading(true);
    try {
      // 1. Offline-First read from Dexie
      const localData = await localDB.ordres.toArray();
      if (localData.length > 0) {
        setOrdres(localData);
        setLoading(false); // Show local data immediately
      }

      // 2. Fetch from API to update cache
      try {
        const remoteData = await apiFetch<OrdreTreballLocal[]>("operari_pwa/feines");
        await localDB.ordres.clear();
        if (remoteData && remoteData.length > 0) {
          await localDB.ordres.bulkPut(remoteData);
        }
        const updatedLocalData = await localDB.ordres.toArray();
        setOrdres(updatedLocalData);
        setError(null);
      } catch (remoteErr: any) {
        console.warn("Could not fetch remote feines, using local cache.", remoteErr);
        if (localData.length === 0) {
          setError(remoteErr.message || "Error carregant feines remotament i cap caché local disponible.");
        }
      }
    } catch (err: any) {
      console.error("Failed to read from localDB:", err);
      setError("Error de la base de dades local.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchLocalAndRemote();
  }, [fetchLocalAndRemote]);

  return { ordres, loading, error, refetch: fetchLocalAndRemote };
}
