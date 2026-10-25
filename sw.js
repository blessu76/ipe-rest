// ipe() service worker — installable PWA + offline fallback
const CACHE = 'ipe-v41';
const CORE = [
  '/', '/index.html',
  '/manifest.webmanifest?v=23',
  '/icon-192.png?v=23', '/icon-512.png', '/icon-180.png?v=23',
  '/og-image.png',
  '/en/', '/journal/', '/journal/en/', '/journal/journal.css?v=8', '/journal/journal.js?v=7',
  '/about/', '/contact/', '/privacy/',
  '/fonts/inter-400.woff2?v=23', '/fonts/jbmono-400.woff2?v=23', '/fonts/jbmono-600.woff2?v=23'
];

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE).then((c) => c.addAll(CORE)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return;

  const isHTML = req.mode === 'navigate' ||
    (req.headers.get('accept') || '').includes('text/html');

  if (isHTML) {
    // network-first: 항상 최신 페이지, 오프라인이면 캐시
    // cache:'no-cache' — 브라우저 HTTP 캐시(Pages max-age=600)를 거치지 않고 서버에 재검증(변경 없으면 304)
    e.respondWith(
      fetch(req, { cache: 'no-cache' }).then((res) => {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(req, copy));
        return res;
      }).catch(() => caches.match(req).then((r) => r || caches.match('/index.html')))
    );
  } else {
    // 정적 자산: cache-first
    e.respondWith(
      caches.match(req).then((cached) => cached || fetch(req).then((res) => {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(req, copy));
        return res;
      }).catch(() => undefined))
    );
  }
});
