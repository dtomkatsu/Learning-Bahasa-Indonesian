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

// How recently a record was written. Normally that's its lastReview, but an
// undo deliberately restores an *older* state and stamps it with `rev` (see
// srsRestoreState in _srs_js.py) so it isn't instantly re-clobbered by the
// rated copy already sitting on the remote.
function syncStamp(r) {
  return Math.max((r && r.lastReview) || 0, (r && r.rev) || 0);
}

// Per item id, keep whichever side was written more recently.
function syncMergeFsrs(local, incoming) {
  const out = Object.assign({}, local);
  let added = 0, updated = 0, kept = 0;
  for (const [id, inc] of Object.entries(incoming || {})) {
    const cur = out[id];
    if (!cur) { out[id] = inc; added++; continue; }
    if (syncStamp(inc) > syncStamp(cur)) { out[id] = inc; updated++; }
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
// Set when GitHub rejects the saved token (401). Classic tokens default to a
// 30-day expiry, and when this one lapsed every push failed behind a small
// "sync failed" badge for two months. The flag lets every page say plainly
// that the token is dead and take a new one in place.
const SYNC_AUTH_FAIL_KEY = 'bahasa:sync:authFailedAt';
const SYNC_STALE_MS = 3 * 24 * 60 * 60 * 1000;
const SYNC_FILENAME = 'bahasa-progress.json';
const GH_API = 'https://api.github.com';

function syncRemoteConfigured() {
  return !!(localStorage.getItem(SYNC_TOKEN_KEY) && localStorage.getItem(SYNC_GIST_KEY));
}
function syncRemoteNeedsToken() {
  return syncRemoteConfigured() && !!localStorage.getItem(SYNC_AUTH_FAIL_KEY);
}
// Connected, but nothing has synced for a few days (and no known cause).
function syncRemoteStale() {
  const last = parseInt(localStorage.getItem(SYNC_LAST_KEY) || '0', 10);
  return syncRemoteConfigured() && (!last || Date.now() - last > SYNC_STALE_MS);
}
function syncNoteResponse(resp) {
  if (resp.status === 401) {
    if (!localStorage.getItem(SYNC_AUTH_FAIL_KEY)) localStorage.setItem(SYNC_AUTH_FAIL_KEY, String(Date.now()));
    throw new Error('GitHub rejected the saved token — it has expired or been revoked. Paste a new one to resume syncing.');
  }
  if (resp.ok) localStorage.removeItem(SYNC_AUTH_FAIL_KEY);
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
  syncNoteResponse(resp);
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

// ---- Writes ------------------------------------------------------------------
// Every write to the gist goes through one queue, one at a time. Two
// overlapping PATCHes to one gist (a progress push and the voice drill's
// debug log) can get one refused, and that showed up as a sync error.
// Other files (that debug log) ride along with the next progress push
// instead of making writes of their own: GitHub rate-limits content writes
// per account, and a long drill session was getting close.
const SYNC_ERR_KEY = 'bahasa:sync:lastError';
const _syncExtraFiles = {};
function syncAttachFile(name, content) { _syncExtraFiles[name] = content; }

let _syncChain = Promise.resolve();
function syncSerial(fn) {
  const p = _syncChain.then(fn, fn);
  _syncChain = p.catch(() => {});
  return p;
}

// Refusals worth waiting out rather than reporting: 409 (a write raced
// another), 403/429 (rate limits), 5xx, and no network. A 401 is not one of
// them; syncNoteResponse reports a dead token straight away.
let syncRetryDelays = [2000, 6000, 20000];
function syncTransient(status) { return status === 0 || status === 409 || status === 403 || status === 429 || status >= 500; }
const _syncSleep = ms => new Promise(r => setTimeout(r, ms));

// Pull-merge first so this device's push can never clobber another device's
// newer reviews, then upload the merged state.
function syncRemotePush() {
  return syncSerial(async () => {
    const id = localStorage.getItem(SYNC_GIST_KEY);
    for (let attempt = 0; ; attempt++) {
      try { await syncRemotePull(); } catch (e) { /* offline pull is fine; push may still work */ }
      const files = { [SYNC_FILENAME]: { content: JSON.stringify(syncBuildExport()) } };
      for (const [name, content] of Object.entries(_syncExtraFiles)) files[name] = { content };
      let resp = null;
      try {
        resp = await fetch(GH_API + '/gists/' + id, {
          method: 'PATCH', headers: syncGhHeaders(), body: JSON.stringify({ files }),
        });
      } catch (e) { /* network: retried below */ }
      if (resp) syncNoteResponse(resp);           // throws on a dead token
      if (resp && resp.ok) {
        for (const name of Object.keys(files)) {
          if (name !== SYNC_FILENAME && _syncExtraFiles[name] === files[name].content) delete _syncExtraFiles[name];
        }
        localStorage.setItem(SYNC_LAST_KEY, String(Date.now()));
        localStorage.removeItem(SYNC_ERR_KEY);
        return;
      }
      const status = resp ? resp.status : 0;
      if (syncTransient(status) && attempt < syncRetryDelays.length) {
        await _syncSleep(syncRetryDelays[attempt]);
        continue;
      }
      const msg = status ? 'Push failed (HTTP ' + status + ').' : 'Push failed: no connection.';
      localStorage.setItem(SYNC_ERR_KEY, JSON.stringify({ at: Date.now(), msg }));
      throw new Error(msg);
    }
  });
}

// Pushes wait for a pause in reviewing (SYNC_PUSH_IDLE_MS) so a run of quick
// ratings is one write, but never longer than SYNC_PUSH_MAX_MS from the first
// unsent rating, so steady reviewing still syncs.
const SYNC_PUSH_IDLE_MS = 8000;
const SYNC_PUSH_MAX_MS = 30000;
let _syncPushTimer = null;
let _syncFirstQueued = 0;
function syncRemoteQueuePush(statusCb) {
  if (!syncRemoteConfigured()) return;
  if (_syncPushTimer) clearTimeout(_syncPushTimer);
  if (!_syncFirstQueued) _syncFirstQueued = Date.now();
  statusCb && statusCb('pending');
  const wait = Math.max(0, Math.min(SYNC_PUSH_IDLE_MS, _syncFirstQueued + SYNC_PUSH_MAX_MS - Date.now()));
  _syncPushTimer = setTimeout(async () => {
    _syncPushTimer = null;
    _syncFirstQueued = 0;
    try { await syncRemotePush(); statusCb && statusCb('ok'); }
    // The specific reason (bad token, deleted gist, network) used to be
    // thrown away here — every page just showed "sync failed" with no way to
    // tell a revoked token from a network blip without re-triggering a
    // manual action on index.html. Pass it through instead.
    catch (e) { statusCb && statusCb('err', e.message); }
  }, 2500);
}

// Swap in a new token without disconnecting: same gist, so nothing is
// re-created and both devices keep pointing at one file. Then pull-merge and
// push, so everything studied while sync was down goes up straight away.
async function syncRemoteReplaceToken(token) {
  const id = localStorage.getItem(SYNC_GIST_KEY);
  const resp = id && await fetch(GH_API + '/gists/' + id, {
    headers: { 'Authorization': 'Bearer ' + token, 'Accept': 'application/vnd.github+json' },
  });
  if (resp && resp.status === 401) throw new Error('GitHub rejected that token too. Is it a classic token with the gist scope?');
  if (resp && resp.ok) localStorage.setItem(SYNC_TOKEN_KEY, token);
  else await syncRemoteSetup(token);   // gist gone or never set: find or create it
  localStorage.removeItem(SYNC_AUTH_FAIL_KEY);
  await syncRemotePush();
}

// Best-effort flush if the tab is backgrounded while a push is still queued.
// Skips the pre-pull; keepalive bodies are size-capped (~64KB) so this can
// silently no-op on very large state — the next normal push covers it.
// Leaving the page with ratings not yet pushed. A keepalive request would
// survive the page closing, but browsers refuse keepalive bodies over 64 KB
// and the progress file is ~200 KB, so this flush failed every time. A
// normal request goes out now; iOS finishes it when the app comes back if it
// suspends it first, and the next push covers it either way.
async function syncRemoteFlush() {
  const id = localStorage.getItem(SYNC_GIST_KEY);
  if (!id) return;
  const body = JSON.stringify({ files: { [SYNC_FILENAME]: { content: JSON.stringify(syncBuildExport()) } } });
  try {
    const resp = await fetch(GH_API + '/gists/' + id, {
      method: 'PATCH', headers: syncGhHeaders(), keepalive: body.length < 60000, body,
    });
    if (resp.ok) localStorage.setItem(SYNC_LAST_KEY, String(Date.now()));
  } catch (e) { /* best effort; the next push covers it */ }
}
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'hidden' && _syncPushTimer) {
    clearTimeout(_syncPushTimer);
    _syncPushTimer = null;
    _syncFirstQueued = 0;
    syncSerial(syncRemoteFlush);
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
  } catch (e) { statusCb && statusCb('err', e.message); }
}

// Shared by flashcards/quiz/study, which all show the same small "synced ✓ /
// syncing… / sync failed" badge next to their stats line. Centralized so the
// three pages can't drift the way the plain 'err'-with-no-detail version did
// — tap the failed state to see the actual reason (bad token, deleted gist,
// offline) instead of a dead end.
function syncStatusBadge(el, s, detail) {
  if (!el) return;
  if (!syncRemoteConfigured()) { el.textContent = ''; el.onclick = null; el.style.cursor = ''; return; }
  if (s === 'pending') { el.textContent = 'syncing…'; el.onclick = null; el.style.cursor = ''; return; }
  if (s === 'ok') { el.textContent = 'synced ✓'; el.onclick = null; el.style.cursor = ''; return; }
  if (syncRemoteNeedsToken()) {
    el.textContent = 'sync stopped: token expired (tap to fix)';
    el.style.cursor = 'pointer';
    el.onclick = async () => {
      const t = (prompt('GitHub rejected the saved sync token (expired or revoked). Your progress on this device is safe.' +
        '\\n\\nMake a new classic token with only the gist scope and Expiration set to No expiration ' +
        '(github.com/settings/tokens/new), then paste it here:') || '').trim();
      if (!t) return;
      syncStatusBadge(el, 'pending');
      try { await syncRemoteReplaceToken(t); syncStatusBadge(el, 'ok'); }
      catch (e) { syncStatusBadge(el, 'err', e.message); }
    };
    return;
  }
  el.textContent = 'sync failed (tap for why)';
  el.style.cursor = 'pointer';
  el.onclick = () => alert('Sync failed: ' + (detail || 'unknown error.') +
    '\\n\\nIf this keeps happening, the saved GitHub token may have been revoked or expired — ' +
    'go to the homepage sync panel, disconnect, and reconnect with a fresh token.');
}

function syncRemoteDisconnect() {
  localStorage.removeItem(SYNC_TOKEN_KEY);
  localStorage.removeItem(SYNC_GIST_KEY);
  localStorage.removeItem(SYNC_LAST_KEY);
  localStorage.removeItem(SYNC_AUTH_FAIL_KEY);
}
"""
