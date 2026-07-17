"""
Shared progress export/import JS, embedded verbatim into index.html by
build_index.py. Not a standalone script.

FSRS state lives in localStorage, which is per-browser — so the phone and the
laptop each keep their own schedule. This bundles every progress key into one
JSON file you can move between devices (AirDrop, email, Files, whatever) and
merges it back in without either side clobbering the other.

Merge rules:
  * FSRS items  — per item id, the entry with the later `lastReview` wins. So
                  reviewing on your phone all week and then importing an older
                  laptop export won't roll your phone back.
  * Flags       — union. A flag is a "this line is ASR junk" judgement, so
                  merging keeps flags from both sides. Consequence: UNflagging
                  does not propagate; if you unflag on one device, unflag on
                  the other too (or it'll come back on the next import).
"""

SYNC_JS = """
const SYNC_FORMAT = 1;
const SYNC_APP_ID = 'learning-bahasa-indonesian';
const FSRS_KEYS = ['bahasa:flashcards:fsrs:v1', 'bahasa:quiz:fsrs:v1'];
const FLAG_KEY = 'bahasa:flaggedLines:v1';
const SYNC_KEYS = [...FSRS_KEYS, FLAG_KEY];

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

  const when = payload.exportedAtISO ? new Date(payload.exportedAtISO).toLocaleString() : 'unknown date';
  return { touched, text: `Merged export from ${when}.\\n` + bits.join('\\n') };
}

function syncCounts() {
  const fc = Object.keys(syncRead('bahasa:flashcards:fsrs:v1')).length;
  const qz = Object.keys(syncRead('bahasa:quiz:fsrs:v1')).length;
  const fl = Object.keys(syncRead(FLAG_KEY)).length;
  return { fc, qz, fl };
}
"""
