"""
Shared spaced-repetition JS snippet, embedded verbatim into flashcards.html
and quiz.html by their respective build scripts. Not a standalone script.

Simplified SM-2 (the same family Anki uses): each item gets an ease factor,
an interval (days), a rep count, and a due timestamp. Correct answers grow
the interval (interval *= ease, with fixed first two steps of 1 and 3 days);
misses reset reps/interval to 0 and drop ease, with a short 10-minute
"relearn" step so a missed card can resurface the same session rather than
vanishing for a day. Deliberately no server/account — state lives in
localStorage, per-browser.
"""

SRS_JS = """
const DAY_MS = 24 * 60 * 60 * 1000;
const RELEARN_MS = 10 * 60 * 1000;
const MATURE_INTERVAL_DAYS = 21;

function srsLoad(key) {
  try { return JSON.parse(localStorage.getItem(key)) || {}; } catch (e) { return {}; }
}
function srsSave(key, s) { localStorage.setItem(key, JSON.stringify(s)); }

// One-time migration from the old session-only "box" system (no due dates)
// into real SRS state, then removes the legacy key so it isn't re-applied.
function srsMigrateFromBoxes(srsKey, legacyKey) {
  let srs = srsLoad(srsKey);
  const legacy = srsLoad(legacyKey);
  if (!Object.keys(legacy).length) return srs;
  const stepIntervals = [0, 1, 3, 6];
  for (const [id, v] of Object.entries(legacy)) {
    if (srs[id]) continue;
    const box = (v && v.box) || 0;
    srs[id] = { ease: 2.3, interval: stepIntervals[Math.min(box, 3)], reps: box, due: Date.now() };
  }
  srsSave(srsKey, srs);
  localStorage.removeItem(legacyKey);
  return srs;
}

function srsIsDue(state) {
  return !state || !state.due || state.due <= Date.now();
}

function srsIsMature(state) {
  return !!(state && state.interval >= MATURE_INTERVAL_DAYS);
}

function srsSchedule(state, good) {
  const s = state ? Object.assign({}, state) : { ease: 2.3, interval: 0, reps: 0, due: 0 };
  if (good) {
    s.reps = (s.reps || 0) + 1;
    if (s.reps === 1) s.interval = 1;
    else if (s.reps === 2) s.interval = 3;
    else s.interval = Math.max(1, Math.round(s.interval * s.ease));
    s.ease = Math.min(3.0, s.ease + 0.1);
    s.due = Date.now() + s.interval * DAY_MS;
  } else {
    s.reps = 0;
    s.interval = 0;
    s.ease = Math.max(1.3, s.ease - 0.2);
    s.due = Date.now() + RELEARN_MS;
  }
  return s;
}

function srsFmtDue(ts) {
  if (!isFinite(ts)) return 'later';
  const diff = ts - Date.now();
  if (diff <= 0) return 'now';
  const mins = Math.round(diff / 60000);
  if (mins < 60) return mins + 'm';
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return hrs + 'h';
  const days = Math.round(hrs / 24);
  return days + 'd';
}
"""
