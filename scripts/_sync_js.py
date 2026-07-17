"""
Shared progress sync JS, embedded verbatim into index.html, flashcards.html
and quiz.html by their build scripts. Not a standalone script.

FSRS state lives in localStorage, which is per-browser AND per-origin — so
the phone (https:// Pages) and the laptop app (file://) each keep their own
schedule. Two sync layers, both built on the same merge:

  1. Export/import — bundle every progress key into one JSON file and merge
     it back in on another device. Zero infrastructure, manual.
  2. Auto-sync via a private GitHub Gist — paste a gist-scoped token once per
     device; after that every page-load pulls+merges and every rating pushes
     (debounced, and it re-pulls right before pushing so a stale device can
     never clobber a fresh one). The gist is just the export payload, stored
     remotely. GitHub's API allows browser CORS, so this works from a static
     site with no server of our own.

Merge rules (shared by both layers):
  * FSRS items    — per item id, the entry with the later `lastReview` wins.
                    So reviewing on your phone all week and then importing an
                    older laptop export won't roll your phone back.
  * Flags         — union. A flag is a "this line is ASR junk" judgement, so
                    merging keeps flags from both sides. Consequence:
                    UNflagging does not propagate; if you unflag on one
                    device, unflag on the other too (or it comes back next
                    sync).
  * Removed cards — union, same reasoning/consequence as flags (it's the same
                    kind of deliberate, rarely-reversed judgement).
  * Custom cards  — per front, the entry with the later `updatedAt` wins
                    (same shape as the FSRS rule, applied to a card *edit*
                    instead of a *review*).
"""

SYNC_JS = """
const SYNC_FORMAT = 1;
const SYNC_APP_ID = 'learning-bahasa-indonesian';
const FSRS_KEYS = ['bahasa:flashcards:fsrs:v1', 'bahasa:quiz:fsrs:v1'];
const FLAG_KEY = 'bahasa:flaggedLines:v1';
const REMOVED_CARDS_KEY = 'bahasa:flashcards:removed:v1';
const CUSTOM_CARDS_KEY = 'bahasa:flashcards:custom:v1';
// REVIEWLOG_KEY is declared in the SRS module, which is always embedded
// before this one on pages that have both; index.html embeds only this
// module, so declare a local fallback name instead of referencing it.
const SYNC_REVIEWLOG_KEY = 'bahasa:reviewLog:v1';
const SYNC_KEYS = [...FSRS_KEYS, FLAG_KEY, REMOVED_CARDS_KEY, CUSTOM_CARDS_KEY, SYNC_REVIEWLOG_KEY];

function syncRead(key) {
  try { return JSON.parse(localStorage.getItem(key)) || {}; } catch (e) { return {}; }
}
function syncWrite(key, v) { localStorage.setItem(key, JSON.stringify(v)); }

function syncBuildExport() {
  const data = {};
  SYNC_KEYS.forEach(k => { data[k] = syncRead(k); });
  return {
    app: SYNC_APP_ID,
    formatVersion: SYNC_FORMAT,
    exportedAt: Date.now(),
    exportedAtISO: new Date().toISOString(),
    data,
  };
}

// Per item id, keep whichever side was reviewed more recently.
function syncMergeFsrs(local, incoming) {
  const out = Object.assign({}, local);
  let added = 0, updated = 0, kept = 0;
  for (const [id, inc] of Object.entries(incoming || {})) {
    const cur = out[id];
    if (!cur) { out[id] = inc; added++; continue; }
    if ((inc.lastReview || 0) > (cur.lastReview || 0)) { out[id] = inc; updated++; }
    else kept++;
  }
  return { out, added, updated, kept };
}

function syncMergeFlags(local, incoming) {
  const out = Object.assign({}, local);
  let added = 0;
  for (const id of Object.keys(incoming || {})) {
    if (!out[id]) { out[id] = incoming[id]; added++; }
  }
  return { out, added };
}

// Generic version of syncMergeFsrs's rule (later `field` wins) for any
// id -> {..., [field]: timestamp} map — used for custom flashcards, keyed by
// `updatedAt` instead of `lastReview`.
function syncMergeByField(local, incoming, field) {
  const out = Object.assign({}, local);
  let added = 0, updated = 0, kept = 0;
  for (const [id, inc] of Object.entries(incoming || {})) {
    const cur = out[id];
    if (!cur) { out[id] = inc; added++; continue; }
    if ((inc[field] || 0) > (cur[field] || 0)) { out[id] = inc; updated++; }
    else kept++;
  }
  return { out, added, updated, kept };
}

// Returns a human-readable summary, or throws with a useful message.
function syncApplyImport(payload) {
  if (!payload || typeof payload !== 'object') throw new Error('That file isn\\'t valid JSON.');
  if (payload.app !== SYNC_APP_ID) {
    throw new Error('That file isn\\'t a Bahasa Player progress export.');
  }
  if ((payload.formatVersion || 0) > SYNC_FORMAT) {
    throw new Error('That export came from a newer version of the app than this one.');
  }
  const bits = [];
  let touched = 0;
  for (const key of FSRS_KEYS) {
    const r = syncMergeFsrs(syncRead(key), (payload.data || {})[key]);
    syncWrite(key, r.out);
    touched += r.added + r.updated;
    const label = key.includes('flashcards') ? 'flashcards' : 'quiz items';
    bits.push(`${label}: ${r.added} new, ${r.updated} updated, ${r.kept} already newer here`);
  }
  const f = syncMergeFlags(syncRead(FLAG_KEY), (payload.data || {})[FLAG_KEY]);
  syncWrite(FLAG_KEY, f.out);
  touched += f.added;
  bits.push(`flagged lines: ${f.added} new`);

  const rm = syncMergeFlags(syncRead(REMOVED_CARDS_KEY), (payload.data || {})[REMOVED_CARDS_KEY]);
  syncWrite(REMOVED_CARDS_KEY, rm.out);
  touched += rm.added;
  bits.push(`removed flashcards: ${rm.added} new`);

  const cc = syncMergeByField(syncRead(CUSTOM_CARDS_KEY), (payload.data || {})[CUSTOM_CARDS_KEY], 'updatedAt');
  syncWrite(CUSTOM_CARDS_KEY, cc.out);
  touched += cc.added + cc.updated;
  bits.push(`custom flashcards: ${cc.added} new, ${cc.updated} updated, ${cc.kept} already newer here`);

  // Review log: union by timestamp key, then trim to the newest 2000 so the
  // payload can't grow without bound.
  const lg = syncMergeFlags(syncRead(SYNC_REVIEWLOG_KEY), (payload.data || {})[SYNC_REVIEWLOG_KEY]);
  const lgKeys = Object.keys(lg.out).map(Number).sort((a, b) => b - a);
  for (const k of lgKeys.slice(2000)) delete lg.out[k];
  syncWrite(SYNC_REVIEWLOG_KEY, lg.out);
  touched += lg.added;

  const when = payload.exportedAtISO ? new Date(payload.exportedAtISO).toLocaleString() : 'unknown date';
  return { touched, text: `Merged export from ${when}.\\n` + bits.join('\\n') };
}

function syncCounts() {
  const fc = Object.keys(syncRead('bahasa:flashcards:fsrs:v1')).length;
  const qz = Object.keys(syncRead('bahasa:quiz:fsrs:v1')).length;
  const fl = Object.keys(syncRead(FLAG_KEY)).length;
  return { fc, qz, fl };
}

// ---- Remote auto-sync via a private GitHub Gist ----------------------------
// The gist holds exactly one file (SYNC_FILENAME) whose content is the same
// payload syncBuildExport() produces, so pull can reuse syncApplyImport().
// Token requirement: a CLASSIC personal-access token with only the `gist`
// scope (fine-grained tokens can't access the gist API). Stored in this
// browser's localStorage only.

const SYNC_TOKEN_KEY = 'bahasa:sync:token';
const SYNC_GIST_KEY = 'bahasa:sync:gistId';
const SYNC_LAST_KEY = 'bahasa:sync:lastSync';
const SYNC_FILENAME = 'bahasa-progress.json';
const GH_API = 'https://api.github.com';

function syncRemoteConfigured() {
  return !!(localStorage.getItem(SYNC_TOKEN_KEY) && localStorage.getItem(SYNC_GIST_KEY));
}
function syncGhHeaders() {
  return {
    'Authorization': 'Bearer ' + localStorage.getItem(SYNC_TOKEN_KEY),
    'Accept': 'application/vnd.github+json',
  };
}

// Find this browser's user's progress gist, or create it. Stores token+id.
async function syncRemoteSetup(token) {
  const headers = { 'Authorization': 'Bearer ' + token, 'Accept': 'application/vnd.github+json' };
  let resp = await fetch(GH_API + '/gists?per_page=100', { headers });
  if (resp.status === 401) throw new Error('GitHub rejected that token. Is it a classic token with the gist scope?');
  if (!resp.ok) throw new Error('GitHub error ' + resp.status + ' while listing gists.');
  const gists = await resp.json();
  let gist = gists.find(g => g.files && g.files[SYNC_FILENAME]);
  if (!gist) {
    resp = await fetch(GH_API + '/gists', {
      method: 'POST', headers,
      body: JSON.stringify({
        description: 'Bahasa Player progress sync (created automatically)',
        public: false,
        files: { [SYNC_FILENAME]: { content: JSON.stringify(syncBuildExport()) } },
      }),
    });
    if (!resp.ok) throw new Error('Could not create the sync gist (HTTP ' + resp.status + '). Does the token have the gist scope?');
    gist = await resp.json();
  }
  localStorage.setItem(SYNC_TOKEN_KEY, token);
  localStorage.setItem(SYNC_GIST_KEY, gist.id);
  return gist.id;
}

async function syncRemotePull() {
  const id = localStorage.getItem(SYNC_GIST_KEY);
  const resp = await fetch(GH_API + '/gists/' + id, { headers: syncGhHeaders() });
  if (resp.status === 404) throw new Error('Sync gist not found — it may have been deleted. Disconnect and reconnect.');
  if (!resp.ok) throw new Error('Pull failed (HTTP ' + resp.status + ').');
  const gist = await resp.json();
  const file = gist.files && gist.files[SYNC_FILENAME];
  if (!file) return { touched: 0, text: 'Remote gist has no progress file yet.' };
  let content = file.content;
  if (file.truncated) content = await (await fetch(file.raw_url)).text();
  let payload;
  try { payload = JSON.parse(content); } catch (e) { return { touched: 0, text: 'Remote progress file was unreadable; it will be overwritten on next push.' }; }
  const r = syncApplyImport(payload);
  localStorage.setItem(SYNC_LAST_KEY, String(Date.now()));
  return r;
}

// Pull-merge first so this device's push can never clobber another device's
// newer reviews, then upload the merged state.
async function syncRemotePush() {
  try { await syncRemotePull(); } catch (e) { /* offline pull is fine; push may still work */ }
  const id = localStorage.getItem(SYNC_GIST_KEY);
  const resp = await fetch(GH_API + '/gists/' + id, {
    method: 'PATCH', headers: syncGhHeaders(),
    body: JSON.stringify({ files: { [SYNC_FILENAME]: { content: JSON.stringify(syncBuildExport()) } } }),
  });
  if (!resp.ok) throw new Error('Push failed (HTTP ' + resp.status + ').');
  localStorage.setItem(SYNC_LAST_KEY, String(Date.now()));
}

let _syncPushTimer = null;
function syncRemoteQueuePush(statusCb) {
  if (!syncRemoteConfigured()) return;
  if (_syncPushTimer) clearTimeout(_syncPushTimer);
  statusCb && statusCb('pending');
  _syncPushTimer = setTimeout(async () => {
    _syncPushTimer = null;
    try { await syncRemotePush(); statusCb && statusCb('ok'); }
    catch (e) { statusCb && statusCb('err'); }
  }, 2500);
}

// Best-effort flush if the tab is backgrounded while a push is still queued.
// Skips the pre-pull; keepalive bodies are size-capped (~64KB) so this can
// silently no-op on very large state — the next normal push covers it.
async function syncRemoteFlush() {
  const id = localStorage.getItem(SYNC_GIST_KEY);
  if (!id) return;
  try {
    await fetch(GH_API + '/gists/' + id, {
      method: 'PATCH', headers: syncGhHeaders(), keepalive: true,
      body: JSON.stringify({ files: { [SYNC_FILENAME]: { content: JSON.stringify(syncBuildExport()) } } }),
    });
    localStorage.setItem(SYNC_LAST_KEY, String(Date.now()));
  } catch (e) { /* best effort */ }
}
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'hidden' && _syncPushTimer) {
    clearTimeout(_syncPushTimer);
    _syncPushTimer = null;
    syncRemoteFlush();
  }
});

// Page-load hook: pull, merge, and let the page refresh its UI if anything
// actually changed.
async function syncRemoteAutoPull(onMerged, statusCb) {
  if (!syncRemoteConfigured()) return;
  statusCb && statusCb('pending');
  try {
    const r = await syncRemotePull();
    statusCb && statusCb('ok');
    if (r.touched && onMerged) onMerged(r);
  } catch (e) { statusCb && statusCb('err'); }
}

function syncRemoteDisconnect() {
  localStorage.removeItem(SYNC_TOKEN_KEY);
  localStorage.removeItem(SYNC_GIST_KEY);
  localStorage.removeItem(SYNC_LAST_KEY);
}
"""
