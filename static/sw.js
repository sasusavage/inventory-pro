/**
 * InventoryPro Service Worker
 * Strategy:
 *  - App shell (HTML pages, CSS, JS): Network-first with cache fallback
 *  - Static assets (images, fonts): Cache-first
 *  - API calls: Network-only (no stale data), but queue failed POSTs for sync
 */

const CACHE_VERSION  = 'invpro-v1';
const SHELL_CACHE    = `${CACHE_VERSION}-shell`;
const ASSET_CACHE    = `${CACHE_VERSION}-assets`;
const OFFLINE_QUEUE  = 'invpro-offline-queue';

const SHELL_URLS = [
    '/',
    '/pos-page',
    '/sales-page',
    '/products-page',
    '/customers-page',
    '/static/css/style.css',
    '/static/manifest.json',
];

// ── Install ──────────────────────────────────────────────────────────────────
self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(SHELL_CACHE)
            .then(cache => cache.addAll(SHELL_URLS))
            .then(() => self.skipWaiting())
    );
});

// ── Activate ─────────────────────────────────────────────────────────────────
self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(keys =>
            Promise.all(
                keys.filter(k => k.startsWith('invpro-') && k !== SHELL_CACHE && k !== ASSET_CACHE)
                    .map(k => caches.delete(k))
            )
        ).then(() => self.clients.claim())
    );
});

// ── Fetch ─────────────────────────────────────────────────────────────────────
self.addEventListener('fetch', event => {
    const { request } = event;
    const url = new URL(request.url);

    // Skip non-GET API calls — let background sync handle those
    if (request.method !== 'GET') return;

    // Skip external requests
    if (url.origin !== self.location.origin) return;

    // API routes — network-first, no cache
    if (url.pathname.startsWith('/api/') || isApiRoute(url.pathname)) {
        event.respondWith(networkOnly(request));
        return;
    }

    // Static assets — cache-first
    if (url.pathname.startsWith('/static/')) {
        event.respondWith(cacheFirst(request, ASSET_CACHE));
        return;
    }

    // App shell pages — network-first with cache fallback
    event.respondWith(networkFirst(request, SHELL_CACHE));
});

function isApiRoute(path) {
    return ['/sales', '/products', '/customers', '/suppliers', '/purchase-orders',
            '/dashboard', '/reports', '/expenses', '/activity'].some(p => path.startsWith(p) && !path.endsWith('-page'));
}

async function networkFirst(request, cacheName) {
    try {
        const response = await fetch(request);
        if (response.ok) {
            const cache = await caches.open(cacheName);
            cache.put(request, response.clone());
        }
        return response;
    } catch {
        const cached = await caches.match(request);
        return cached || offlineFallback();
    }
}

async function cacheFirst(request, cacheName) {
    const cached = await caches.match(request);
    if (cached) return cached;
    try {
        const response = await fetch(request);
        if (response.ok) {
            const cache = await caches.open(cacheName);
            cache.put(request, response.clone());
        }
        return response;
    } catch {
        return offlineFallback();
    }
}

async function networkOnly(request) {
    try { return await fetch(request); }
    catch { return new Response(JSON.stringify({ error: 'You are offline' }), {
        status: 503,
        headers: { 'Content-Type': 'application/json' },
    }); }
}

function offlineFallback() {
    return new Response(
        `<!DOCTYPE html><html><body style="font-family:sans-serif;text-align:center;padding:4rem;">
         <h2>You're offline</h2><p>Please check your connection and try again.</p>
         <button onclick="location.reload()">Retry</button></body></html>`,
        { headers: { 'Content-Type': 'text/html' } }
    );
}

// ── Background Sync — flush queued offline sales ──────────────────────────────
self.addEventListener('sync', event => {
    if (event.tag === 'sync-offline-sales') {
        event.waitUntil(flushOfflineSales());
    }
});

async function flushOfflineSales() {
    const db  = await openQueue();
    const tx  = db.transaction(OFFLINE_QUEUE, 'readwrite');
    const store = tx.objectStore(OFFLINE_QUEUE);
    const all = await idbAll(store);

    for (const item of all) {
        try {
            const res = await fetch('/sales', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ...item.payload, is_offline_sync: true }),
            });
            if (res.ok) {
                store.delete(item.id);
            }
        } catch {
            // Will retry on next sync event
        }
    }
}

// ── Minimal IndexedDB helpers ─────────────────────────────────────────────────
function openQueue() {
    return new Promise((resolve, reject) => {
        const req = indexedDB.open('invpro-offline', 1);
        req.onupgradeneeded = e => e.target.result.createObjectStore(OFFLINE_QUEUE, { autoIncrement: true, keyPath: 'id' });
        req.onsuccess = e => resolve(e.target.result);
        req.onerror   = e => reject(e.target.error);
    });
}

function idbAll(store) {
    return new Promise((resolve, reject) => {
        const req = store.getAll();
        req.onsuccess = () => resolve(req.result);
        req.onerror   = () => reject(req.error);
    });
}
