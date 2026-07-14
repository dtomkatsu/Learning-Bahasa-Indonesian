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
