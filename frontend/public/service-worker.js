// ZEUS-IA Enterprise - Service Worker
// Versión: 1.4.0 — SPA offline-safe; nunca cachear POST; API network-only

const CACHE_NAME = 'zeus-enterprise-v5';
const RUNTIME_CACHE = 'zeus-runtime-v5';

const PRECACHE = ['/favicon.ico', '/index.html'];

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
  return SPA_PATH_PREFIXES.some((p) => pathname === p || pathname.startsWith(p));
}

function isCacheableRequest(request) {
  return request.method === 'GET' || request.method === 'HEAD';
}

function isApiRequest(pathname) {
  return pathname.startsWith('/api/');
}

function isNavigation(request) {
  return request.mode === 'navigate';
}

async function safeCachePut(cache, request, response) {
  if (!isCacheableRequest(request)) return;
  if (!response || !response.ok) return;
  try {
    await cache.put(request, response.clone());
  } catch (err) {
    console.log('[SW] Skip cache.put:', request.method, request.url, err);
  }
}

async function matchIndexHtml() {
  return (await caches.match('/index.html')) || (await caches.match('/'));
}

async function offlineHtmlResponse() {
  const cached = await matchIndexHtml();
  if (cached) return cached;
  return new Response(
    '<!DOCTYPE html><html><head><meta charset="utf-8"><title>ZEUS</title></head>' +
      '<body><p>ZEUS — sin conexión. Compruebe la red y recargue.</p></body></html>',
    { status: 200, headers: { 'Content-Type': 'text/html; charset=utf-8' } }
  );
}

self.addEventListener('install', (event) => {
  console.log('[SW] Service Worker instalando v5...');
  event.waitUntil(
    caches
      .open(CACHE_NAME)
      .then(async (cache) => {
        for (const url of PRECACHE) {
          try {
            const res = await fetch(url, { cache: 'reload' });
            if (res.ok) await safeCachePut(cache, new Request(url), res);
          } catch (err) {
            console.log('[SW] Precache skip:', url, err);
          }
        }
      })
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  console.log('[SW] Service Worker activando v5...');
  event.waitUntil(
    caches
      .keys()
      .then((names) =>
        Promise.all(names.filter((n) => n !== CACHE_NAME && n !== RUNTIME_CACHE).map((n) => caches.delete(n)))
      )
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  if (!url.protocol.startsWith('http')) return;
  if (!isCacheableRequest(request)) return;

  if (url.pathname.endsWith('service-worker.js')) {
    event.respondWith(networkOnlyStrategy(request));
    return;
  }

  if (isApiRequest(url.pathname)) {
    event.respondWith(networkOnlyStrategy(request));
    return;
  }

  if (isNavigation(request) || isSpaRoute(url.pathname) || url.pathname === '/') {
    event.respondWith(spaNavigationStrategy(request));
    return;
  }

  if (url.pathname.startsWith('/assets/')) {
    event.respondWith(networkFirstStrategy(request, { allowCache: true }));
    return;
  }

  if (url.pathname.endsWith('.html')) {
    event.respondWith(networkFirstStrategy(request, { allowCache: true, spaFallback: true }));
    return;
  }

  event.respondWith(cacheFirstStrategy(request));
});

/** SPA: network → index.html cache → offline shell (nunca reject). */
async function spaNavigationStrategy(request) {
  try {
    const networkResponse = await fetch(request);
    if (networkResponse && networkResponse.ok) {
      if (request.url.endsWith('/index.html') || new URL(request.url).pathname === '/') {
        const cache = await caches.open(CACHE_NAME);
        await safeCachePut(cache, new Request('/index.html'), networkResponse);
      }
      return networkResponse;
    }
  } catch (err) {
    console.log('[SW] SPA network fail:', request.url, err);
  }

  const cachedRoute = await caches.match(request);
  if (cachedRoute) return cachedRoute;

  const index = await matchIndexHtml();
  if (index) return index;

  try {
    const idx = await fetch('/index.html');
    if (idx.ok) {
      const cache = await caches.open(CACHE_NAME);
      await safeCachePut(cache, new Request('/index.html'), idx);
      return idx;
    }
  } catch (err) {
    console.log('[SW] index.html fetch fail:', err);
  }

  return offlineHtmlResponse();
}

async function cacheFirstStrategy(request) {
  try {
    const cachedResponse = await caches.match(request);
    if (cachedResponse) return cachedResponse;

    const networkResponse = await fetch(request);
    if (networkResponse && networkResponse.ok) {
      const cache = await caches.open(CACHE_NAME);
      await safeCachePut(cache, request, networkResponse);
    }
    return networkResponse;
  } catch (error) {
    console.log('[SW] cache-first fail:', request.url, error);
    if (isNavigation(request) || isSpaRoute(new URL(request.url).pathname)) {
      return offlineHtmlResponse();
    }
    return new Response('', { status: 503, statusText: 'Offline' });
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
    console.log('[SW] network-first fail:', request.url, error);
    const cachedResponse = await caches.match(request);
    if (cachedResponse) return cachedResponse;
    if (spaFallback) return offlineHtmlResponse();
    return new Response('', { status: 503, statusText: 'Offline' });
  }
}

self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});

console.log('[SW] Service Worker cargado v5');
