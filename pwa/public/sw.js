/**
 * Service Worker per a SEVALOR PWA — Offline-First (Spec 019)
 *
 * Estratègia: NetworkFirst per a dades fresques, CacheFirst per a assets estàtics.
 * Background Sync pendent d'integrar amb Workbox.
 */
const CACHE_NAME = "sevalor-pwa-v4";
const STATIC_ASSETS = [
  "/",
  "/operari/feines/",
  "/operari/login/",
  "/manifest.json",
  "/icons/icon-192x192.png",
  "/icons/icon-512x512.png",
];

// Instal·lació: pre-cache d'assets estàtics
self.addEventListener("install", (event: ExtendableEvent) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS);
    })
  );
  self.skipWaiting();
});

// Activació: neteja de caches antics
self.addEventListener("activate", (event: ExtendableEvent) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
      );
    })
  );
  self.clients.claim();
});

// Fetch: NetworkFirst amb fallback a cache
self.addEventListener("fetch", (event: FetchEvent) => {
  // Només interceptar peticions GET
  if (event.request.method !== "GET") return;

  event.respondWith(
    fetch(event.request)
      .then((response) => {
        // Clonar i guardar a cache si és resposta vàlida
        if (response.status === 200) {
          const cloned = response.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(event.request, cloned);
          });
        }
        return response;
      })
      .catch(() => {
        // Fallback a cache
        return caches.match(event.request) as Promise<Response>;
      })
  );
});

export {};