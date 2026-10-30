// Service worker: makes the site installable and usable offline.
// - HTML: network-first (deploys show up immediately), cache fallback offline.
// - Everything else same-origin (icons, manifest, audio): cache-first.
//
// Two caches, invalidated independently:
// - SHELL, versioned: the pages, the manifest and the icons. Bumping VERSION
//   drops it, which is the whole point of a bump.
// - MEDIA, effectively permanent: the clips under audio/. That's ~104MB the
//   device has already paid to download, and it has nothing to do with a code
//   change — so a shell bump must not evict it. Bump MEDIA_VERSION only when
//   the audio files themselves are re-cut.
// Reads go to the specific cache rather than caches.match(), which searches
// every cache in the origin and would happily serve a stale copy of something
// the shell bump was meant to replace.
const VERSION = 'v8';
const MEDIA_VERSION = 'v1';
const SHELL = `bahasa-shell-${VERSION}`;
const MEDIA = `bahasa-media-${MEDIA_VERSION}`;

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

// The single-cache layout this replaced (bahasa-v1, bahasa-v2).
const LEGACY = /^bahasa-v\d+$/;

function isAudio(url) {
  return url.pathname.includes('/audio/');
}

// Carry already-downloaded clips out of the old single cache before it's
// dropped, so introducing the split doesn't itself cost the 104MB of
// re-downloading it exists to prevent. Only audio/ moves across: the manifest
// and icons are precached into SHELL on every install, and a second copy
// hanging around in MEDIA is exactly the staleness this split avoids.
async function adoptLegacyAudio() {
  const media = await caches.open(MEDIA);
  for (const key of await caches.keys()) {
    if (!LEGACY.test(key)) continue;
    const old = await caches.open(key);
    for (const req of await old.keys()) {
      if (!isAudio(new URL(req.url))) continue;
      if (await media.match(req)) continue;
      const res = await old.match(req);
      if (res) await media.put(req, res);
    }
  }
}

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(SHELL).then((c) => c.addAll(PRECACHE)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    adoptLegacyAudio()
      .catch(() => {})
      .then(() => caches.keys())
      .then((keys) => Promise.all(
        keys.filter((k) => k !== SHELL && k !== MEDIA).map((k) => caches.delete(k))
      ))
      .then(() => self.clients.claim())
  );
});

// Cache-first against one named cache. Range requests pass through to the
// network and are never stored, so offline audio seeking is best-effort —
// text features are the guaranteed-offline part.
function cacheFirst(request, cacheName) {
  return caches.open(cacheName).then((cache) =>
    cache.match(request).then(
      (hit) =>
        hit ||
        fetch(request).then((r) => {
          if (r.ok && r.status === 200 && !request.headers.get('range')) {
            cache.put(request, r.clone());
          }
          return r;
        })
    )
  );
}

self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET' || url.origin !== location.origin) return;

  if (e.request.mode === 'navigate' || url.pathname.endsWith('.html')) {
    e.respondWith(
      fetch(e.request)
        .then((r) => {
          const copy = r.clone();
          caches.open(SHELL).then((c) => c.put(e.request, copy));
          return r;
        })
        .catch(() => caches.open(SHELL).then((c) => c.match(e.request)))
    );
    return;
  }

  e.respondWith(cacheFirst(e.request, isAudio(url) ? MEDIA : SHELL));
});
