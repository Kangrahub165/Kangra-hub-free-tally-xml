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
  // Only handle GET requests
  if (event.request.method !== 'GET') return;

  let url;
  try {
    url = new URL(event.request.url);
  } catch {
    return;
  }

  // Only intercept same-origin requests to prevent interference with backend APIs & CDNs
  if (url.origin !== self.location.origin) {
    return;
  }

  // Never cache backend API calls, dev sockets, or non-static routes
  if (
    url.pathname.startsWith('/api') ||
    url.pathname.startsWith('/_next/webpack-hmr') ||
    url.pathname.includes(':8000')
  ) {
    return;
  }

  // Network-first strategy for same-origin pages and static assets
  event.respondWith(
    fetch(event.request)
      .then((networkResponse) => {
        if (networkResponse && networkResponse.status === 200 && networkResponse.type === 'basic') {
          const responseToCache = networkResponse.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(event.request, responseToCache).catch(() => {});
          });
        }
        return networkResponse;
      })
      .catch(async () => {
        try {
          const cached = await caches.match(event.request);
          if (cached) {
            return cached;
          }
          if (event.request.mode === 'navigate') {
            const rootCached = await caches.match('/');
            if (rootCached) {
              return rootCached;
            }
          }
        } catch {}
        // Fallback valid Response object prevents "Failed to convert value to 'Response'"
        return new Response('The requested offline resource is currently unavailable.', {
          status: 503,
          statusText: 'Service Unavailable',
          headers: { 'Content-Type': 'text/plain; charset=utf-8' },
        });
      })
  );
});
