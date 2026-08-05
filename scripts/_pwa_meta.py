"""Shared PWA head tags, injected into every page's <head>.

Why this exists: manifest.json already declares `"display": "standalone"`,
which Android honors on its own. iOS Safari does not — "Add to Home Screen"
on iOS ignores the manifest's display mode entirely unless the page also
carries the legacy Apple meta tags below. Without them, tapping the home
screen icon just opens the page in ordinary Safari, URL bar and all, no
matter what the manifest says. This was missing from every page except
index.html until 2026-08-05, and even there the Apple-specific tags were
absent — only the manifest link and theme-color were present, which is
exactly the combination that works on Android and silently doesn't on iOS.

Present on every page, not just index.html: the manifest's `"scope": "./"`
already declares the whole site as one app, and a user can land on (or
bookmark, or share a link to) any page directly — flashcards.html, a
specific conversation player — not only index.html. Whichever page they
actually add to the home screen needs its own copy of these tags to launch
standalone.

apple-mobile-web-app-status-bar-style is deliberately "default" (opaque,
standard iOS chrome) rather than "black-translucent" (edge-to-edge,
transparent over content). The latter looks better but needs safe-area-inset
padding on every page's top-level layout to avoid content sitting under the
notch/status bar — a real CSS change, not a one-line addition. "default" gets
the actual ask (no Safari URL bar, launches like an app) without that.
"""

PWA_META_TAGS = """<link rel="manifest" href="manifest.json">
<meta name="theme-color" content="#D01228">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="default">
<meta name="apple-mobile-web-app-title" content="Bahasa">
<link rel="apple-touch-icon" href="icon-192.png">"""

# Was registered from index.html only, which left the service worker (and
# therefore offline support) dependent on which page happened to be the
# entry point. register() is idempotent — every page calling it with the
# same script URL is normal PWA practice, not redundant work — and matches
# manifest.json's own "scope": "./" already declaring the whole site as one
# app. No-ops over file:// (the desktop app), same as before.
PWA_SW_JS = """if ('serviceWorker' in navigator && location.protocol.startsWith('http')) {
  navigator.serviceWorker.register('sw.js').catch(() => {});
}"""
