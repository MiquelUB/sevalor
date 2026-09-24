/**
 * Service Worker per a SEVALOR PWA — Offline-First (Spec 013, Spec 019)
 *
 * Estratègia:
 * - CacheFirst per a assets estàtics (shell de l'app)
 * - NetworkFirst per a peticions GET de dades (API)
 * - BackgroundSyncPlugin (Workbox) per a mètodes mutables (POST, PUT, DELETE, PATCH)
 *   amb cua "sync_queue" per a operacions offline diferides
 */

// Workbox CDN — Spec 013 RF-02
importScripts("https://storage.googleapis.com/workbox-cdn/releases/7.0.0/workbox-sw.js");

const CACHE_NAME = "sevalor-pwa-v4";
const STATIC_ASSETS = [
  "/",
  "/operari/feines/",
  "/operari/login/",
  "/manifest.json",
  "/icons/icon-192x192.png",
  "/icons/icon-512x512.png",
];

// ─── Pre-cache d'assets estàtics ───────────────────────────────────────
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS);
    })
  );
  self.skipWaiting();
});

// ─── Activació: neteja de caches antics ────────────────────────────────
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
      );
    })
  );
  self.clients.claim();
});

// ─── Workbox: Background Sync per a mètodes mutables ───────────────────
// Spec 013 RF-03: Cua "sync_queue" per a operacions offline
if (workbox) {
  const bgSyncPlugin = new workbox.backgroundSync.BackgroundSyncPlugin("sync_queue", {
    maxRetentionTime: 24 * 60, // Reintentar fins a 24 hores
    onSync: async ({ queue }) => {
      let entry;
      while ((entry = await queue.shiftRequest())) {
        try {
          await fetch(entry.request.clone());
        } catch (error) {
          // Tornar a posar a la cua si falla
          await queue.unshiftRequest(entry);
          throw error;
        }
      }
    },
  });

  // Interceptar POST a /api/v1/
  workbox.routing.registerRoute(
    ({ url, request }) =>
      url.pathname.startsWith("/api/v1/") && request.method === "POST",
    new workbox.strategies.NetworkOnly({
      plugins: [bgSyncPlugin],
    }),
    "POST"
  );

  // Interceptar PUT a /api/v1/
  workbox.routing.registerRoute(
    ({ url, request }) =>
      url.pathname.startsWith("/api/v1/") && request.method === "PUT",
    new workbox.strategies.NetworkOnly({
      plugins: [bgSyncPlugin],
    }),
    "PUT"
  );

  // Interceptar DELETE a /api/v1/
  workbox.routing.registerRoute(
    ({ url, request }) =>
      url.pathname.startsWith("/api/v1/") && request.method === "DELETE",
    new workbox.strategies.NetworkOnly({
      plugins: [bgSyncPlugin],
    }),
    "DELETE"
  );

  // Interceptar PATCH a /api/v1/
  workbox.routing.registerRoute(
    ({ url, request }) =>
      url.pathname.startsWith("/api/v1/") && request.method === "PATCH",
    new workbox.strategies.NetworkOnly({
      plugins: [bgSyncPlugin],
    }),
    "PATCH"
  );

  // GET a /api/v1/ → NetworkFirst amb fallback a cache
  workbox.routing.registerRoute(
    ({ url }) => url.pathname.startsWith("/api/v1/"),
    new workbox.strategies.NetworkFirst({
      cacheName: "sevalor-api-cache",
      plugins: [
        new workbox.expiration.ExpirationPlugin({
          maxEntries: 100,
          maxAgeSeconds: 60 * 60, // 1 hora
        }),
      ],
    })
  );

  // Assets estàtics → CacheFirst
  workbox.routing.registerRoute(
    ({ request }) =>
      request.destination === "style" ||
      request.destination === "script" ||
      request.destination === "image" ||
      request.destination === "font",
    new workbox.strategies.CacheFirst({
      cacheName: "sevalor-static-cache",
      plugins: [
        new workbox.expiration.ExpirationPlugin({
          maxEntries: 60,
          maxAgeSeconds: 30 * 24 * 60 * 60, // 30 dies
        }),
      ],
    })
  );
}

// ─── Fallback per a navegació offline ──────────────────────────────────
self.addEventListener("fetch", (event) => {
  // Workbox ja gestiona les rutes registrades; aquest listener
  // només actua com a fallback per a peticions GET no capturades per Workbox
  if (event.request.method !== "GET") return;

  // Ignorem les rutes ja gestionades per Workbox
  if (event.request.url.includes("/api/v1/")) return;

  event.respondWith(
    fetch(event.request)
      .then((response) => {
        if (response.status === 200) {
          const cloned = response.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(event.request, cloned);
          });
        }
        return response;
      })
      .catch(() => {
        return caches.match(event.request);
      })
  );
});