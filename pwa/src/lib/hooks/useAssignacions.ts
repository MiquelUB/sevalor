import { useState, useEffect, useCallback } from "react";
import { apiFetch } from "../api";
import { db } from "../offline/db";
import { encryptWithPin, decryptWithPin } from "../crypto";
import { OrdreTreballLocal } from "../types/operari";

export function useAssignacions() {
  const [ordres, setOrdres] = useState<OrdreTreballLocal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchLocalAndRemote = useCallback(async () => {
    setLoading(true);
    let cachedOrdres: OrdreTreballLocal[] = [];

    try {
      // 1. Offline-First: llegir registres xifrats des de db.ordres
      const sessionPin = typeof window !== "undefined" ? sessionStorage.getItem("sevalor_session_pin") : null;
      const saltStr = typeof window !== "undefined" ? localStorage.getItem("sevalor_sentinel_salt") : null;

      if (sessionPin && saltStr) {
        try {
          const saltBytes = new Uint8Array(saltStr.split(",").map(Number));
          const encryptedList = await db.ordres.toArray();
          for (const item of encryptedList) {
            try {
              const decryptedJson = await decryptWithPin(item.ciphertext, item.iv, sessionPin, saltBytes);
              const parsed = JSON.parse(decryptedJson);
              cachedOrdres.push(parsed);
            } catch (decErr) {
              console.warn("No s'ha pogut desxifrar l'ordre local:", item.id);
            }
          }
        } catch (e) {
          console.warn("Error en carregar ordres xifrades de IndexedDB:", e);
        }
      }

      if (cachedOrdres.length > 0) {
        setOrdres(cachedOrdres);
        setLoading(false);
      }

      // 2. Fetch remot des de l'API per actualitzar i xifrar a la memòria cau
      try {
        const remoteData = await apiFetch<OrdreTreballLocal[]>("/operari/feines");
        if (remoteData && Array.isArray(remoteData)) {
          setOrdres(remoteData);
          setError(null);

          // Si tenim la clau de sessió, persistim xifrat a IndexedDB
          if (sessionPin && saltStr) {
            const saltBytes = new Uint8Array(saltStr.split(",").map(Number));
            await db.ordres.clear();
            for (const item of remoteData) {
              const { cipherTextHex, ivHex } = await encryptWithPin(
                JSON.stringify(item),
                sessionPin,
                saltBytes
              );
              await db.ordres.put({
                id: item.id,
                ciphertext: cipherTextHex,
                iv: ivHex,
              });
            }
          }
        }
      } catch (remoteErr: any) {
        console.warn("Could not fetch remote feines, using local cache.", remoteErr);
        if (cachedOrdres.length === 0) {
          setError(remoteErr.message || "Error carregant feines remotament i cap memòria cau disponible.");
        }
      }
    } catch (err: any) {
      console.error("Failed to read from local encrypted DB:", err);
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
