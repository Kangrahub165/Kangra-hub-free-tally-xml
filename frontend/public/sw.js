// Kangra Hub PWA Service Worker
const CACHE_NAME = 'kh-cache-v1';
const STATIC_ASSETS = [
  '/',
  '/manifest.webmanifest',
  '/logo.webp',
  '/favicon.ico',
  '/favicon-32x32.png',
  '/favicon-16x16.png'
];

self.addEventListener('install', (event) => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS).catch((err) => {
        console.warn('PWA cache addAll warning:', err);
      });
    })
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
      );
    }).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  // Pass non-GET requests directly to network
  if (event.request.method !== 'GET') return;

  const url = new URL(event.request.url);

  // Never cache backend API calls or authentication paths
  if (url.pathname.startsWith('/api') || url.pathname.includes(':8000')) {
    return;
  }

  // Network-first strategy for pages and static assets
  event.respondWith(
    fetch(event.request)
      .then((networkResponse) => {
        if (networkResponse && networkResponse.status === 200) {
          const responseToCache = networkResponse.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(event.request, responseToCache).catch(() => {});
          });
        }
        return networkResponse;
      })
      .catch(() => caches.match(event.request))
  );
});
