"use client";

import { useEffect } from "react";

const SW_CACHE_VERSION = "sevalor-pwa-v5";
const SW_STORAGE_KEY = "sevalor_sw_version";

export function ServiceWorkerRegistrar() {
  useEffect(() => {
    if (typeof window === "undefined" || !("serviceWorker" in navigator)) {
      return;
    }

    const bustObsoleteCaches = async () => {
      if ("caches" in window) {
        const keys = await window.caches.keys();
        const obsolete = keys.filter(
          (key) => !key.endsWith("-v5") && key !== SW_CACHE_VERSION
        );
        await Promise.all(obsolete.map((key) => window.caches.delete(key)));
      }
      window.localStorage.setItem(SW_STORAGE_KEY, SW_CACHE_VERSION);
    };

    const registerAndCheck = async () => {
      try {
        const previousVersion = window.localStorage.getItem(SW_STORAGE_KEY);
        if (previousVersion && previousVersion !== SW_CACHE_VERSION) {
          await bustObsoleteCaches();
        } else if (!previousVersion) {
          await bustObsoleteCaches();
        }

        const registration = await navigator.serviceWorker.register("/sw.js", {
          scope: "/",
          updateViaCache: "none",
        });

        if (registration.waiting) {
          registration.waiting.postMessage({ type: "SKIP_WAITING" });
        }
        if (registration.active) {
          registration.active.postMessage({ type: "CACHE_BUST" });
        }

        await registration.update();
      } catch {
        // Ignorar errors si el context no suporta Service Workers (p. ex. HTTP no segur)
      }
    };

    void registerAndCheck();
  }, []);

  return null;
}
