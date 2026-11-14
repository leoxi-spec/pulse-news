/* Pulse service worker: app shell + offline reading of what you've opened. */
const VERSION = 'pulse-v44';
const SHELL_CACHE = `${VERSION}-shell`;
const API_CACHE = `${VERSION}-api`;
const IMG_CACHE = `${VERSION}-img`;

const SHELL = [
  '/',
  '/app.css',
  '/js/app.js',
  '/js/api.js',
  '/js/ui.js',
  '/js/store.js',
  '/js/router.js',
  '/js/components.js',
  '/js/views/home.js',
  '/js/views/article.js',
  '/js/views/discover.js',
  '/js/views/misc.js',
  '/js/views/videos.js',
  '/js/views/reels.js',
  '/js/views/founder.js',
  '/js/views/keyword.js',
  '/js/views/arcade.js',
  '/js/voice.js',
  '/js/weather.js',
  '/js/ambient.js',
  '/js/daily.js',
  '/js/views/sports.js',
  '/js/views/sources.js',
  '/manifest.webmanifest',
  '/icons/icon-v11.svg',
  '/icons/icon-192-v11.png',
  '/icons/icon-512-v11.png',
];

const CACHEABLE_API = [
  '/api/bootstrap',
  '/api/feed',
  '/api/discover',
  '/api/articles/',
  '/api/sports',
  '/api/search',
  '/api/saved',
  '/api/archive',
  '/api/topics',
  '/api/brief',
  '/api/weather',
];

self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') self.skipWaiting();
});

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(SHELL_CACHE)
      .then((cache) => cache.addAll(SHELL))
      .then(() => self.skipWaiting())
      .catch(() => self.skipWaiting()),
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((key) => !key.startsWith(VERSION)).map((key) => caches.delete(key))))
      .then(() => self.clients.claim()),
  );
});

async function networkFirst(request, cacheName) {
  const cache = await caches.open(cacheName);
  try {
    const response = await fetch(request);
    if (response.ok) cache.put(request, response.clone());
    return response;
  } catch (err) {
    const cached = await cache.match(request);
    if (cached) return cached;
    throw err;
  }
}

async function cacheFirst(request, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(request);
  if (cached) return cached;
  const response = await fetch(request);
  if (response.ok) cache.put(request, response.clone());
  return response;
}

self.addEventListener('fetch', (event) => {
  const { request } = event;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request).catch(async () => {
        const cache = await caches.open(SHELL_CACHE);
        return (await cache.match('/')) || Response.error();
      }),
    );
    return;
  }

  // App code must always be fresh when online; the cache is only an offline
  // fallback. This is what makes local upgrades show up immediately.
  if (url.pathname === '/app.css' || url.pathname.startsWith('/js/') || url.pathname === '/manifest.webmanifest') {
    event.respondWith(networkFirst(request, SHELL_CACHE));
    return;
  }

  if (url.pathname === '/api/img') {
    event.respondWith(cacheFirst(request, IMG_CACHE).catch(() => Response.error()));
    return;
  }

  if (url.pathname.startsWith('/api/')) {
    if (CACHEABLE_API.some((prefix) => url.pathname.startsWith(prefix))) {
      event.respondWith(networkFirst(request, API_CACHE));
    }
    return;
  }

  event.respondWith(cacheFirst(request, SHELL_CACHE).catch(() => Response.error()));
});
