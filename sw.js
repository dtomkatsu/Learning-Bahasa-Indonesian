// Service worker: makes the site installable and usable offline.
// - HTML: network-first (deploys show up immediately), cache fallback offline.
// - Everything else same-origin (JS-less pages, icons, audio): cache-first.
// Audio note: full responses are cached on first non-range fetch; range
// requests pass through to the network, so offline audio seeking is
// best-effort — text features are the guaranteed-offline part.
// Bump VERSION to invalidate all caches on deploy of breaking changes.
const VERSION = 'bahasa-v1';
const PRECACHE = [
  './',
  'index.html',
  'flashcards.html',
  'quiz.html',
  'study.html',
  'conversation-1-player.html',
  'manifest.json',
  'icon-192.png',
  'icon-512.png',
];

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(VERSION).then((c) => c.addAll(PRECACHE)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== VERSION).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET' || url.origin !== location.origin) return;

  if (e.request.mode === 'navigate' || url.pathname.endsWith('.html')) {
    e.respondWith(
      fetch(e.request)
        .then((r) => {
          const copy = r.clone();
          caches.open(VERSION).then((c) => c.put(e.request, copy));
          return r;
        })
        .catch(() => caches.match(e.request))
    );
    return;
  }

  e.respondWith(
    caches.match(e.request).then(
      (hit) =>
        hit ||
        fetch(e.request).then((r) => {
          if (r.ok && r.status === 200 && !e.request.headers.get('range')) {
            const copy = r.clone();
            caches.open(VERSION).then((c) => c.put(e.request, copy));
          }
          return r;
        })
    )
  );
});
