const CACHE_NAME = 'painel-notas-v1';

self.addEventListener('install', (event) => {
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    event.waitUntil(clients.claim());
});

self.addEventListener('fetch', (event) => {
    // Permite que requisições passem diretamente pela rede
    event.respondWith(fetch(event.request).catch(() => caches.match(event.request)));
});