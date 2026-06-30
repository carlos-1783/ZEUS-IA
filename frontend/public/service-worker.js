// ZEUS-IA Enterprise - Service Worker
// Versión: 1.2.0 — no cachear POST/API; SPA network-first

const CACHE_NAME = 'zeus-enterprise-v3';
const RUNTIME_CACHE = 'zeus-runtime-v3';

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
  return request.method === 'GET';
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

// Instalación del Service Worker
self.addEventListener('install', (event) => {
  console.log('[SW] Service Worker instalando...');
  event.waitUntil(
    caches
      .open(CACHE_NAME)
      .then((cache) => {
        console.log('[SW] Cacheando recursos estáticos');
        return cache
          .addAll(STATIC_ASSETS.map((url) => new Request(url, { cache: 'reload' })))
          .catch((err) => {
            console.log('[SW] Error cacheando algunos recursos (continuando):', err);
            return Promise.resolve();
          });
      })
      .then(() => {
        console.log('[SW] Service Worker instalado correctamente');
        return self.skipWaiting();
      })
  );
});

// Activación del Service Worker
self.addEventListener('activate', (event) => {
  console.log('[SW] Service Worker activando...');
  event.waitUntil(
    caches
      .keys()
      .then((cacheNames) => {
        return Promise.all(
          cacheNames
            .filter((cacheName) => {
              return cacheName !== CACHE_NAME && cacheName !== RUNTIME_CACHE;
            })
            .map((cacheName) => {
              console.log('[SW] Eliminando cache antiguo:', cacheName);
              return caches.delete(cacheName);
            })
        );
      })
      .then(() => {
        console.log('[SW] Service Worker activado');
        return self.clients.claim();
      })
  );
});

self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  if (!url.protocol.startsWith('http')) {
    return;
  }

  // POST/PUT/PATCH/DELETE: pasar directo al navegador (Cache API no soporta POST)
  if (!isCacheableRequest(request)) {
    return;
  }

  if (url.pathname.endsWith('service-worker.js')) {
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

  if (isApiRequest(url.pathname)) {
    event.respondWith(networkOnlyStrategy(request));
    return;
  }

  event.respondWith(cacheFirstStrategy(request));
});

async function cacheFirstStrategy(request) {
  try {
    const cachedResponse = await caches.match(request);

    if (cachedResponse) {
      console.log('[SW] Cache hit:', request.url);
      return cachedResponse;
    }

    console.log('[SW] Cache miss, fetch desde red:', request.url);
    const networkResponse = await fetch(request);

    if (networkResponse && networkResponse.status === 200) {
      const cache = await caches.open(CACHE_NAME);
      await safeCachePut(cache, request, networkResponse);
    }

    return networkResponse;
  } catch (error) {
    console.log('[SW] Error en cache-first:', error);

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

    if (allowCache && networkResponse && networkResponse.status === 200) {
      const cache = await caches.open(RUNTIME_CACHE);
      await safeCachePut(cache, request, networkResponse);
    }

    return networkResponse;
  } catch (error) {
    console.log('[SW] Network falló, buscando en cache:', request.url);

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

  if (event.data && event.data.type === 'CACHE_URLS') {
    event.waitUntil(
      caches.open(CACHE_NAME).then((cache) => {
        return cache.addAll(event.data.urls);
      })
    );
  }
});

console.log('[SW] Service Worker cargado');
