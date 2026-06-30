// ZEUS-IA Enterprise - Service Worker
// Versión: 1.3.0 — nunca cachear POST; API network-only; SPA network-first

const CACHE_NAME = 'zeus-enterprise-v4';
const RUNTIME_CACHE = 'zeus-runtime-v4';

const STATIC_ASSETS = ['/favicon.ico'];

const SPA_PATH_PREFIXES = [
  '/dashboard',
  '/admin',
  '/tpv',
  '/login',
  '/register',
  '/auth/',
  '/pricing',
  '/checkout',
];

function isSpaRoute(pathname) {
  return SPA_PATH_PREFIXES.some(
    (p) => pathname === p || pathname.startsWith(p)
  );
}

function isCacheableRequest(request) {
  return request.method === 'GET' || request.method === 'HEAD';
}

function isApiRequest(pathname) {
  return pathname.startsWith('/api/');
}

async function safeCachePut(cache, request, response) {
  if (!isCacheableRequest(request)) {
    return;
  }
  if (!response || !response.ok) {
    return;
  }
  try {
    await cache.put(request, response.clone());
  } catch (err) {
    console.log('[SW] Skip cache.put:', request.method, request.url, err);
  }
}

self.addEventListener('install', (event) => {
  console.log('[SW] Service Worker instalando v4...');
  event.waitUntil(
    caches
      .open(CACHE_NAME)
      .then((cache) => {
        return cache
          .addAll(STATIC_ASSETS.map((url) => new Request(url, { cache: 'reload' })))
          .catch((err) => {
            console.log('[SW] Error cacheando recursos (continuando):', err);
            return Promise.resolve();
          });
      })
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  console.log('[SW] Service Worker activando v4...');
  event.waitUntil(
    caches
      .keys()
      .then((cacheNames) =>
        Promise.all(
          cacheNames
            .filter((name) => name !== CACHE_NAME && name !== RUNTIME_CACHE)
            .map((name) => caches.delete(name))
        )
      )
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  if (!url.protocol.startsWith('http')) {
    return;
  }

  // POST/PUT/PATCH/DELETE: no interceptar (Cache API no soporta POST)
  if (!isCacheableRequest(request)) {
    return;
  }

  if (url.pathname.endsWith('service-worker.js')) {
    event.respondWith(networkOnlyStrategy(request));
    return;
  }

  if (isApiRequest(url.pathname)) {
    event.respondWith(networkOnlyStrategy(request));
    return;
  }

  if (url.pathname.startsWith('/assets/')) {
    event.respondWith(networkFirstStrategy(request, { allowCache: true }));
    return;
  }

  if (
    request.mode === 'navigate' ||
    url.pathname.endsWith('.html') ||
    url.pathname === '/' ||
    isSpaRoute(url.pathname)
  ) {
    event.respondWith(networkFirstStrategy(request, { allowCache: false, spaFallback: true }));
    return;
  }

  event.respondWith(cacheFirstStrategy(request));
});

async function cacheFirstStrategy(request) {
  try {
    const cachedResponse = await caches.match(request);
    if (cachedResponse) {
      return cachedResponse;
    }

    const networkResponse = await fetch(request);
    if (networkResponse && networkResponse.status === 200) {
      const cache = await caches.open(CACHE_NAME);
      await safeCachePut(cache, request, networkResponse);
    }
    return networkResponse;
  } catch (error) {
    if (request.mode === 'navigate' || isSpaRoute(new URL(request.url).pathname)) {
      const fallback = await caches.match('/index.html');
      if (fallback) {
        return fallback;
      }
    }
    throw error;
  }
}

async function networkOnlyStrategy(request) {
  return fetch(request);
}

async function networkFirstStrategy(request, options = {}) {
  const { allowCache = true, spaFallback = false } = options;

  try {
    const networkResponse = await fetch(request);
    if (allowCache && networkResponse && networkResponse.ok) {
      const cache = await caches.open(RUNTIME_CACHE);
      await safeCachePut(cache, request, networkResponse);
    }
    return networkResponse;
  } catch (error) {
    const cachedResponse = await caches.match(request);
    if (cachedResponse) {
      return cachedResponse;
    }
    if (spaFallback) {
      const index = await caches.match('/index.html');
      if (index) {
        return index;
      }
    }
    throw error;
  }
}

self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});

console.log('[SW] Service Worker cargado v4');
