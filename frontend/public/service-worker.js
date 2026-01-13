// ZEUS-IA Enterprise - Service Worker
// Versión: 1.0.0
// Estrategia: Cache-first para máxima velocidad

const CACHE_NAME = 'zeus-enterprise-v1';
const RUNTIME_CACHE = 'zeus-runtime-v1';

// Recursos estáticos para cachear en la instalación
const STATIC_ASSETS = [
  '/',
  '/dashboard',
  '/admin',
  '/tpv',
  '/index.html',
  '/favicon.ico'
];

// Instalación del Service Worker
self.addEventListener('install', (event) => {
  console.log('[SW] Service Worker instalando...');
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => {
        console.log('[SW] Cacheando recursos estáticos');
        return cache.addAll(STATIC_ASSETS.map(url => new Request(url, { cache: 'reload' })))
          .catch((err) => {
            console.log('[SW] Error cacheando algunos recursos (continuando):', err);
            return Promise.resolve(); // Continuar aunque falle algunos recursos
          });
      })
      .then(() => {
        console.log('[SW] Service Worker instalado correctamente');
        return self.skipWaiting(); // Activar inmediatamente
      })
  );
});

// Activación del Service Worker
self.addEventListener('activate', (event) => {
  console.log('[SW] Service Worker activando...');
  event.waitUntil(
    caches.keys()
      .then((cacheNames) => {
        return Promise.all(
          cacheNames
            .filter((cacheName) => {
              // Eliminar caches antiguos
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
        return self.clients.claim(); // Tomar control inmediato
      })
  );
});

// Estrategia: Cache-first con fallback a red
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Solo manejar requests HTTP/HTTPS (no chrome-extension, etc.)
  if (!url.protocol.startsWith('http')) {
    return;
  }

  // Para requests de API, usar network-first
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(networkFirstStrategy(request));
    return;
  }

  // Para recursos estáticos, usar cache-first
  event.respondWith(cacheFirstStrategy(request));
});

// Estrategia Cache-First: Buscar en cache primero, luego en red
async function cacheFirstStrategy(request) {
  try {
    const cachedResponse = await caches.match(request);
    
    if (cachedResponse) {
      console.log('[SW] Cache hit:', request.url);
      return cachedResponse;
    }

    console.log('[SW] Cache miss, fetch desde red:', request.url);
    const networkResponse = await fetch(request);

    // Cachear respuesta exitosa
    if (networkResponse && networkResponse.status === 200) {
      const cache = await caches.open(CACHE_NAME);
      cache.put(request, networkResponse.clone());
    }

    return networkResponse;
  } catch (error) {
    console.log('[SW] Error en cache-first:', error);
    
    // Fallback: Si es una página, devolver página offline
    if (request.mode === 'navigate') {
      return caches.match('/index.html');
    }
    
    throw error;
  }
}

// Estrategia Network-First: Intentar red primero, luego cache
async function networkFirstStrategy(request) {
  try {
    const networkResponse = await fetch(request);
    
    // Cachear respuesta exitosa
    if (networkResponse && networkResponse.status === 200) {
      const cache = await caches.open(RUNTIME_CACHE);
      cache.put(request, networkResponse.clone());
    }
    
    return networkResponse;
  } catch (error) {
    console.log('[SW] Network falló, buscando en cache:', request.url);
    
    const cachedResponse = await caches.match(request);
    if (cachedResponse) {
      return cachedResponse;
    }
    
    throw error;
  }
}

// Manejar mensajes desde la app
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
