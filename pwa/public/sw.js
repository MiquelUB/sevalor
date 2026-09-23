/**
 * Service Worker per a SEVALOR PWA — Offline-First (Spec 019 & Spec 013)
 *
 * Estratègia: NetworkFirst per a dades fresques, CacheFirst per a assets estàtics.
 * Background Sync integrat amb Workbox per interceptar crides mutables a l'API.
 */

importScripts('https://storage.googleapis.com/workbox-cdn/releases/6.5.4/workbox-sw.js');

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
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS);
    })
  );
  self.skipWaiting();
});

// Activació: neteja de caches antics
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

if (workbox) {
  // Configurar Background Sync (Tasques 4.2 / RF-36)
  const bgSyncPlugin = new workbox.backgroundSync.BackgroundSyncPlugin('sync_queue', {
    maxRetentionTime: 24 * 60, // Retenim les crides fallides fins a 24h
  });

  // Interceptar trucades a l'API mutables (POST, PUT, DELETE, PATCH)
  workbox.routing.registerRoute(
    ({ url }) => url.pathname.startsWith('/api/v1/'),
    new workbox.strategies.NetworkOnly({
      plugins: [bgSyncPlugin],
    }),
    'POST'
  );
  workbox.routing.registerRoute(
    ({ url }) => url.pathname.startsWith('/api/v1/'),
    new workbox.strategies.NetworkOnly({
      plugins: [bgSyncPlugin],
    }),
    'PUT'
  );
  workbox.routing.registerRoute(
    ({ url }) => url.pathname.startsWith('/api/v1/'),
    new workbox.strategies.NetworkOnly({
      plugins: [bgSyncPlugin],
    }),
    'PATCH'
  );
  workbox.routing.registerRoute(
    ({ url }) => url.pathname.startsWith('/api/v1/'),
    new workbox.strategies.NetworkOnly({
      plugins: [bgSyncPlugin],
    }),
    'DELETE'
  );

  // Fetch API GET: NetworkFirst amb fallback a cache (només dades, assets ja estan a CACHE_NAME)
  workbox.routing.registerRoute(
    ({ url, request }) => request.method === 'GET' && url.pathname.startsWith('/api/v1/'),
    new workbox.strategies.NetworkFirst({
      cacheName: 'api-get-cache',
      plugins: [
        new workbox.expiration.ExpirationPlugin({
          maxEntries: 50,
          maxAgeSeconds: 12 * 60 * 60, // 12h
        }),
      ],
    })
  );
} else {
  console.error("Workbox no ha carregat.");
}

// Fallback per defecte per a GET de la PWA que no siguin API (Estratègia original)
self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;
  if (event.request.url.includes("/api/v1/")) return; // Deixat a Workbox

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

export {};
