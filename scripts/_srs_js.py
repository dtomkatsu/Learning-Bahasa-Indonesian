"""
Shared spaced-repetition JS snippet, embedded verbatim into flashcards.html
and quiz.html by their respective build scripts. Not a standalone script.

Implements FSRS-5 (Free Spaced Repetition Scheduler) — the algorithm Anki
itself switched to as its recommended default over the older SM-2 family,
because it predicts real recall probability more accurately and needs fewer
reviews for the same retention (per Anki's own docs/FAQ). Formulas and the
19 default (population-trained) weights below match the published FSRS-5
spec: https://github.com/open-spaced-repetition/fsrs4anki/wiki

Each card tracks difficulty (D, 1-10) and stability (S, days — defined as
the number of days for recall probability to fall to 90%). A review with
grade g in {1:Again, 2:Hard, 3:Good, 4:Easy} updates D and S; the next
interval is derived from S so that predicted recall at that point is
DESIRED_RETENTION (90%, matching Anki's default target).

Deliberately no server/account — state lives in localStorage, per-browser.
"""

SRS_JS = """
const DAY_MS = 24 * 60 * 60 * 1000;
const RELEARN_MS = 10 * 60 * 1000;
const MATURE_STABILITY_DAYS = 21;
const DESIRED_RETENTION = 0.9;

const FSRS_W = [
  0.40255, 1.18385, 3.173, 15.69105, 7.1949,
  0.5345, 1.4604, 0.0046, 1.54575, 0.1192,
  1.01925, 1.9395, 0.11, 0.29605, 2.2698,
  0.2315, 2.9898, 0.51655, 0.6621
];
const FSRS_F = 19 / 81;
const FSRS_C = -0.5;

function srsLoad(key) {
  try { return JSON.parse(localStorage.getItem(key)) || {}; } catch (e) { return {}; }
}
function srsSave(key, s) { localStorage.setItem(key, JSON.stringify(s)); }

function clamp(x, lo, hi) { return Math.max(lo, Math.min(hi, x)); }
function clampD(d) { return clamp(d, 1, 10); }

function fsrsRetrievability(elapsedDays, stability) {
  if (elapsedDays <= 0) return 1;
  return Math.pow(1 + FSRS_F * (elapsedDays / stability), FSRS_C);
}

// Days until retrievability decays to `desiredR` starting from `stability`.
function fsrsIntervalDays(desiredR, stability) {
  return (stability / FSRS_F) * (Math.pow(desiredR, 1 / FSRS_C) - 1);
}

function fsrsInitialDifficulty(g) {
  return clampD(FSRS_W[4] - Math.exp(FSRS_W[5] * (g - 1)) + 1);
}
function fsrsInitialStability(g) {
  return FSRS_W[g - 1]; // W[0..3] are literally the four initial-stability values
}

function fsrsUpdateDifficulty(D, g) {
  const deltaD = -FSRS_W[6] * (g - 3);
  const dPrime = D + deltaD * ((10 - D) / 9);
  const mixed = FSRS_W[7] * fsrsInitialDifficulty(4) + (1 - FSRS_W[7]) * dPrime;
  return clampD(mixed);
}

function fsrsUpdateStability(S, D, R, g) {
  if (g === 1) {
    // Lapse: new stability can't exceed the pre-lapse stability.
    const sMin = FSRS_W[11] * Math.pow(D, -FSRS_W[12]) *
      (Math.pow(S + 1, FSRS_W[13]) - 1) * Math.exp(FSRS_W[14] * (1 - R));
    return Math.min(sMin, S);
  }
  const hardPenalty = g === 2 ? FSRS_W[15] : 1;
  const easyBonus = g === 4 ? FSRS_W[16] : 1;
  const growth = 1 + hardPenalty * easyBonus * Math.exp(FSRS_W[8]) *
    (11 - D) * Math.pow(S, -FSRS_W[9]) * (Math.exp(FSRS_W[10] * (1 - R)) - 1);
  return S * growth;
}

function fsrsUpdateSameDayStability(S, g) {
  return S * Math.exp(FSRS_W[17] * (g - 3 + FSRS_W[18]));
}

// Pure: computes the resulting state for grade g without touching storage.
// state is null/undefined for a never-reviewed card.
function fsrsNextState(state, g, now) {
  if (!state || !state.stability) {
    const S = fsrsInitialStability(g);
    const D = fsrsInitialDifficulty(g);
    const due = g === 1 ? now + RELEARN_MS : now + fsrsIntervalDays(DESIRED_RETENTION, S) * DAY_MS;
    return { difficulty: D, stability: S, due, lastReview: now, reps: g === 1 ? 0 : 1 };
  }
  const elapsedDays = Math.max(0, (now - state.lastReview) / DAY_MS);
  const R = fsrsRetrievability(elapsedDays, state.stability);
  const D = fsrsUpdateDifficulty(state.difficulty, g);
  const S = elapsedDays < 1
    ? fsrsUpdateSameDayStability(state.stability, g)
    : fsrsUpdateStability(state.stability, state.difficulty, R, g);
  const due = g === 1 ? now + RELEARN_MS : now + fsrsIntervalDays(DESIRED_RETENTION, S) * DAY_MS;
  const reps = g === 1 ? 0 : (state.reps || 0) + 1;
  return { difficulty: D, stability: S, due, lastReview: now, reps };
}

// { 1: 'Again', 2: 'Hard', 3: 'Good', 4: 'Easy' } -> formatted next-interval string,
// for showing an Anki-style preview on each rating button.
function fsrsPreviewLabels(state, now) {
  const out = {};
  for (let g = 1; g <= 4; g++) {
    const next = fsrsNextState(state, g, now);
    out[g] = srsFmtInterval(next.due - now);
  }
  return out;
}

function srsIsDue(state) {
  return !state || !state.due || state.due <= Date.now();
}
function srsIsMature(state) {
  return !!(state && state.stability >= MATURE_STABILITY_DAYS);
}

// ---- Daily new-card cap ----------------------------------------------------
// Removed (2026-07-19) — new cards are no longer rationed. srsNewQuotaLeft()
// stays as a no-op returning Infinity so every caller (flashcards/quiz/study
// all do `.slice(0, srsNewQuotaLeft())` or `quota === 0` checks) keeps
// working unchanged without gating on it.
function srsNewQuotaLeft() {
  return Infinity;
}
function srsNoteNewIntroduced() {}

// ---- Review log (feeds streak/heatmap/retention stats) ---------------------
// Map keyed by ms-timestamp -> {g: grade 1-4, k: kind, n: 1 if first-ever
// review of that item}. Capped to the newest LOG_CAP entries; synced across
// devices as a union (see _sync_js.py) so streaks survive switching devices.
const REVIEWLOG_KEY = 'bahasa:reviewLog:v1';
const REVIEWLOG_CAP = 2000;

// Returns the key it logged under, so an undo can take the entry back out.
// `itemKey` (the item's SRS id) is recorded so stats can join a review back to
// the card it belongs to — that's what makes retention-by-tag possible.
// Entries written before this existed simply have no `i` and are skipped by
// those breakdowns rather than miscounted.
function srsLogReview(kind, grade, isNew, itemKey) {
  const log = srsLoad(REVIEWLOG_KEY);
  let t = Date.now();
  while (log[t]) t++;
  log[t] = { g: grade, k: kind, n: isNew ? 1 : 0 };
  if (itemKey) log[t].i = itemKey;
  const keys = Object.keys(log).map(Number).sort((a, b) => b - a);
  if (keys.length > REVIEWLOG_CAP) {
    for (const k of keys.slice(REVIEWLOG_CAP)) delete log[k];
  }
  srsSave(REVIEWLOG_KEY, log);
  return t;
}

// ---- Recent-item ring ------------------------------------------------------
// pickNext draws at random from whatever is due, so on its own nothing stops
// it handing straight back the card you just rated. The old guard — redraw
// once if you got the same card as `current` — was too weak twice over: it
// still repeats 1-in-n draws, and in practice-ahead it never fired at all,
// because the caught-up screen clears `current` between draws. So a two-card
// tag repeated itself half the time.
//
// Instead, remember the last few items shown and draw from the pool with
// those removed. The ring is trimmed to leave at least one candidate, so a
// tiny filtered deck alternates rather than stalling; on a two-card tag that
// means strict A-B-A-B, which is the best a two-card tag can do.
// Depth is a preference rather than a constant, because the right value
// depends on how you study: a wide unfiltered deck never notices it, while on
// a small tag it is the difference between a rotation and a shuffle. Kept
// device-local alongside sessionSize and autoCompare — it's a UI preference,
// not learning data, so it stays out of _sync_js.py's SYNC_KEYS. 0 means off,
// which restores plain random draws (and with them the odd back-to-back
// repeat); RECENT_CAP is only a sanity bound on hand-edited storage.
const RECENT_KEY = 'bahasa:recentRing:v1';
const RECENT_DEFAULT = 5;
const RECENT_CAP = 50;
// The ring is persisted per page (flashcards and quiz key their items
// differently). Held only in memory it was lost on every reload, so each page
// load could open on a card you'd just seen.
// v2: entries are word keys (see srsWordKeys), not item ids. v1 held ids.
const RECENT_RING_KEY = 'bahasa:recentItems:v2:' + ((typeof location !== 'undefined' && location.pathname) || '');
// A ring entry is one shown item: a key, or an array of keys.
function srsKeyList(x) {
  return (Array.isArray(x) ? x : [x]).filter(k => typeof k === 'string' && k);
}
function srsLoadRing() {
  const v = srsLoad(RECENT_RING_KEY);
  return Array.isArray(v) ? v.filter(e => srsKeyList(e).length) : [];
}
function srsSaveRing() { srsSave(RECENT_RING_KEY, srsRecent); }
let srsRecent = srsLoadRing();

function srsRecentMax() {
  const v = srsLoad(RECENT_KEY);
  return v && typeof v.n === 'number' ? clamp(Math.round(v.n), 0, RECENT_CAP) : RECENT_DEFAULT;
}
// Shrinking the ring has to drop the now-excess entries straight away,
// otherwise the change doesn't take effect until enough cards have scrolled
// through to trim it naturally.
function srsSetRecentMax(n) {
  srsSave(RECENT_KEY, { n: clamp(Math.round(n), 0, RECENT_CAP) });
  srsTrimRecent();
}
function srsTrimRecent() {
  const max = srsRecentMax();
  if (srsRecent.length > max) srsRecent = srsRecent.slice(srsRecent.length - max);
  srsSaveRing();
}

function srsNoteShown(key) {
  const keys = srsKeyList(key);
  if (!keys.length) return;
  const id = keys.join('|');
  srsRecent = srsRecent.filter(e => srsKeyList(e).join('|') !== id);
  srsRecent.push(keys.length === 1 ? keys[0] : keys);
  srsTrimRecent();
}

// What counts as "the same card again". Avoiding repeats by item id wasn't
// enough: many items share a word — Catch it has one clip per speaker,
// Minimal pairs reuse a word across pairs (adik/adil, adik/aduk), and the
// Study session mixes a word's flashcard, cloze and fill-the-blank with the
// Sentence and Listening cards for the same line. So an item's keys are its
// word(s), lowercased, plus the transcript line it came from.
function srsWordKeys(d) {
  const words = d.kind === 'pairs' ? (d.options || [])
    : [d.kind && d.kind !== 'flash' ? (d.term || d.answer) : d.front];
  const keys = [];
  words.forEach(w => String(w || '').toLowerCase().split('/').forEach(p => {
    p = p.trim();
    if (p) keys.push('w:' + p);
  }));
  if (d.lineId) keys.push('l:' + d.lineId);
  if (!keys.length) keys.push('i:' + (d.id || d.front));
  return keys;
}
function srsClearRecent() { srsRecent = []; srsSaveRing(); }
function srsRecentKeys() { return srsRecent.slice(); }

// Wires a button row (one `data-ring` button per offered depth) to the
// setting. Shared because flashcards and the quiz carry the same control in
// different chrome — they differ in where it sits, not in what it does. A
// stored value that matches no button (hand-edited storage) simply leaves the
// row unhighlighted rather than silently snapping to something else.
function srsWireRecentGroup(id) {
  const el = document.getElementById(id);
  if (!el) return;
  const btns = [...el.querySelectorAll('button[data-ring]')];
  const paint = () => btns.forEach(b =>
    b.classList.toggle('active', Number(b.dataset.ring) === srsRecentMax()));
  btns.forEach(b => b.addEventListener('click', () => {
    srsSetRecentMax(Number(b.dataset.ring));
    paint();
  }));
  paint();
}

// Draws uniformly from `items`, skipping any item that shares a key with
// something in the ring. `keyOf` maps an item to a key or an array of keys
// (usually srsWordKeys). When the pool is too small to avoid the whole ring,
// the oldest entries are let go first, so the most recent card is the last
// one allowed back. Returns null only for an empty list.
function srsPickAvoidingRecent(items, keyOf) {
  if (!items.length) return null;
  const keysOf = d => srsKeyList(keyOf(d));
  // Only ring entries that touch this pool count: stale keys from another
  // filter would otherwise eat the avoidance budget.
  const inPool = new Set(items.flatMap(keysOf));
  const recent = srsRecent.map(srsKeyList).filter(e => e.some(k => inPool.has(k)));
  for (let n = recent.length; n > 0; n--) {
    const avoid = new Set(recent.slice(-n).flat());
    const eligible = items.filter(d => !keysOf(d).some(k => avoid.has(k)));
    if (eligible.length) return eligible[Math.floor(Math.random() * eligible.length)];
  }
  return items[Math.floor(Math.random() * items.length)];
}

// ---- Undo ------------------------------------------------------------------
// Rating is the only destructive action in the study UIs: it overwrites an
// item's FSRS state and appends a review-log entry. "Go back" restores both,
// so a misclicked "Again" doesn't leave a wrecked schedule behind. The stack
// is in-memory on purpose — it's for the misclick you just made, not
// cross-session history.
const UNDO_CAP = 30;
let srsUndoStack = [];

function srsPushUndo(entry) {
  srsUndoStack.push(entry);
  if (srsUndoStack.length > UNDO_CAP) srsUndoStack.shift();
}
function srsPopUndo() { return srsUndoStack.pop() || null; }
function srsUndoDepth() { return srsUndoStack.length; }

// An undo rewrites an item to an *older* state, which would normally lose the
// sync merge to the rated copy this device may already have pushed (the merge
// keeps whichever side was reviewed later). `rev` marks "this was written
// locally at time T" without touching lastReview, which FSRS reads as when the
// item was genuinely last reviewed. See syncMergeFsrs in _sync_js.py.
// Returns null when the item had no prior state (it was brand new), which the
// caller turns into a delete rather than a write.
function srsRestoreState(prev) {
  return prev ? Object.assign({}, prev, { rev: Date.now() }) : null;
}

// ---- Forward stack ---------------------------------------------------------
// The card an undo pushed off the screen. Flashcards and the quiz draw the
// next item at random, so without this, going back and re-rating would hand
// you a *different* card than the one you were already looking at — the undo
// would quietly reshuffle your place in the deck.
//
// LIFO, so consecutive undos replay forwards in the right order: rate A (see
// B), rate B (see C), undo, undo — now re-rating A gives back B, and B gives
// back C.
let srsForwardStack = [];

function srsPushForward(item) {
  if (item) srsForwardStack.push(item);
}
function srsClearForward() { srsForwardStack = []; }
function srsForwardDepth() { return srsForwardStack.length; }

// `resolve` re-looks-up the queued item and returns it (or a falsy value if
// it's no longer eligible — filtered out, removed, or edited away). Skips past
// anything stale rather than showing a card that isn't in the current pool.
function srsTakeForward(resolve) {
  while (srsForwardStack.length) {
    const found = resolve(srsForwardStack.pop());
    if (found) return found;
  }
  return null;
}

// Removes a review-log entry by the key srsLogReview returned, so an undone
// rating doesn't keep inflating the streak/recall stats.
function srsUnlogReview(ts) {
  if (!ts) return;
  const log = srsLoad(REVIEWLOG_KEY);
  if (!(ts in log)) return;
  delete log[ts];
  srsSave(REVIEWLOG_KEY, log);
}

// ---- Daily goal ------------------------------------------------------------
// A target number of reviews per day. Deliberately a soft goal shown on the
// landing page, not a cap that stops you (the hard 15/day new-card cap was
// removed on purpose) — it exists to make "am I done for today?" answerable.
// Device-local: it's a display preference, not progress, so it stays out of
// SYNC_KEYS and each device can set its own.
const GOAL_KEY = 'bahasa:dailyGoal:v1';
const DEFAULT_GOAL = 30;

function srsDayKey(d) {
  return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
}
function srsGoal() {
  const g = srsLoad(GOAL_KEY);
  return g && g.n ? g.n : DEFAULT_GOAL;
}
function srsSetGoal(n) {
  srsSave(GOAL_KEY, { n: Math.max(1, Math.round(n)) });
}
function srsReviewsToday() {
  const today = srsDayKey(new Date());
  const log = srsLoad(REVIEWLOG_KEY);
  let n = 0;
  for (const ts of Object.keys(log)) {
    if (srsDayKey(new Date(Number(ts))) === today) n++;
  }
  return n;
}

// ---- Device ----------------------------------------------------------------
// Touch devices have no space bar and no "z" key, but they do have the swipe
// gestures — so the on-screen hints have to say different things. `hover:none`
// is the right signal (it means "no mouse"); screen width is not, since a
// narrow desktop window still has a keyboard.
function srsIsTouch() {
  return !!(window.matchMedia && window.matchMedia('(hover: none)').matches);
}

// Separate from srsIsTouch on purpose: whether a panel should start collapsed
// is a *layout* question (is there room?), while hint wording is an *input*
// question (is there a keyboard?). A narrow desktop window needs the collapse
// but still wants the keyboard hints.
function srsIsNarrow() {
  return window.innerWidth < 640;
}

function srsFmtDue(ts) {
  if (!isFinite(ts)) return 'later';
  return srsFmtInterval(ts - Date.now());
}
function srsFmtInterval(ms) {
  if (ms <= 0) return 'now';
  const mins = Math.round(ms / 60000);
  if (mins < 60) return mins + 'm';
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return hrs + 'h';
  const days = Math.round(hrs / 24);
  if (days < 30) return days + 'd';
  const months = Math.round(days / 30);
  if (months < 12) return months + 'mo';
  return (Math.round(months / 12 * 10) / 10) + 'y';
}

// One-time migration from the old simplified-SM2 state (ease/interval/reps,
// no difficulty/stability) into FSRS state, then removes the legacy key.
// Items with reps >= 1 are seeded as if their most recent rating was "Good"
// (grade 3), using their old interval as a stability floor, and are put up
// for immediate re-review under the new model rather than guessing a
// mapping that doesn't really exist between the two systems.
function srsMigrateLegacy(srsKey, legacyKeys) {
  let srs = srsLoad(srsKey);
  for (const legacyKey of legacyKeys) {
    const legacy = srsLoad(legacyKey);
    if (!Object.keys(legacy).length) continue;
    for (const [id, v] of Object.entries(legacy)) {
      if (srs[id]) continue;
      const hasProgress = v && ((v.reps || 0) >= 1 || (v.box || 0) >= 1);
      const S = hasProgress ? Math.max(fsrsInitialStability(3), v.interval || 0) : fsrsInitialStability(3);
      srs[id] = {
        difficulty: fsrsInitialDifficulty(3),
        stability: S,
        due: Date.now(),
        lastReview: Date.now(),
        reps: hasProgress ? 1 : 0,
      };
    }
    localStorage.removeItem(legacyKey);
  }
  srsSave(srsKey, srs);
  return srs;
}
"""
