"use client";

import { useEffect, useCallback } from "react";
import { db } from "@/lib/offline/db";

export function useSyncQueue() {
  const processQueue = useCallback(async () => {
    if (!navigator.onLine) return;

    try {
      const items = await db.syncQueue.orderBy("timestamp").toArray();
      if (items.length === 0) return;

      console.log(`Iniciant sincronització de ${items.length} elements encuats...`);

      for (const item of items) {
        try {
          const response = await fetch(item.url, {
            method: item.method,
            body: item.body,
            // Afegir els headers d'auth des del localStorage si s'escau
            headers: {
              "Authorization": `Bearer ${localStorage.getItem("token") || ""}`,
            }
          });

          if (response.ok) {
            // Eliminar de la cua si s'ha enviat amb èxit
            if (item.id) {
              await db.syncQueue.delete(item.id);
            }
          } else {
            console.error(`Fallada enviant l'element ${item.id}: ${response.status}`);
            // Es deixa a la cua per al següent intent
          }
        } catch (error) {
          console.error(`Error de xarxa en element ${item.id}:`, error);
          break; // Sortim del bucle si no hi ha connexió real
        }
      }
    } catch (err) {
      console.error("Error processant la cua de sincronització", err);
    }
  }, []);

  useEffect(() => {
    // Intentar sincronitzar en carregar l'aplicació
    processQueue();

    // Escoltar quan recuperem la connexió
    window.addEventListener("online", processQueue);

    // Intentar periòdicament per si ha fallat algun enviament esporàdic
    const interval = setInterval(processQueue, 60000); // Cada minut

    return () => {
      window.removeEventListener("online", processQueue);
      clearInterval(interval);
    };
  }, [processQueue]);

  return { processQueue };
}
