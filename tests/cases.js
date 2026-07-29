// Assertions over the shared browser logic. Assembled with the real
// _srs_js / _sync_js / _vocab_js sources and a localStorage shim by
// run_tests.py, then run under Node — see that file for how to run this.
//
// Scope on purpose: the pure math and data transforms, which is where every
// real bug in this project has actually been (an FSRS formula, a merge rule,
// a parser edge case). Rendering and audio stay with the browser checks.

// ---- FSRS ------------------------------------------------------------------

suite('FSRS initial state', () => {
  const now = 1_000_000;
  const grades = [1, 2, 3, 4].map(g => fsrsNextState(null, g, now));
  grades.forEach((s, i) => {
    ok(s.difficulty >= 1 && s.difficulty <= 10, `grade ${i + 1} difficulty in [1,10], got ${s.difficulty}`);
    ok(s.stability > 0, `grade ${i + 1} stability positive, got ${s.stability}`);
  });
  // Harder ratings must leave the card harder than easier ratings.
  ok(grades[0].difficulty > grades[3].difficulty,
    'Again leaves a higher difficulty than Easy');
  // Stability must be ordered by grade.
  for (let i = 1; i < 4; i++) {
    ok(grades[i].stability >= grades[i - 1].stability,
      `stability non-decreasing across grades at ${i}`);
  }
});

suite('FSRS intervals are ordered by grade', () => {
  const now = Date.now();
  const state = fsrsNextState(null, 3, now - 3 * 86400000);
  const due = [1, 2, 3, 4].map(g => fsrsNextState(state, g, now).due);
  for (let i = 1; i < 4; i++) {
    ok(due[i] > due[i - 1],
      `grade ${i + 1} schedules later than grade ${i} (${due[i]} vs ${due[i - 1]})`);
  }
  // "Again" must bring the card back very soon, not days out.
  ok(due[0] - now < 60 * 60 * 1000, 'Again reschedules within the hour');
});

suite('FSRS reps counter', () => {
  const now = Date.now();
  let s = fsrsNextState(null, 3, now);
  eq(s.reps, 1, 'first Good sets reps to 1');
  s = fsrsNextState(s, 3, now);
  eq(s.reps, 2, 'second Good increments reps');
  s = fsrsNextState(s, 1, now);
  eq(s.reps, 0, 'Again resets reps to 0');
});

suite('srsFmtInterval', () => {
  eq(srsFmtInterval(0), 'now', 'zero renders as now');
  eq(srsFmtInterval(10 * 60 * 1000), '10m', 'minutes');
  eq(srsFmtInterval(3 * 3600 * 1000), '3h', 'hours');
  eq(srsFmtInterval(5 * 86400000), '5d', 'days');
  eq(srsFmtInterval(60 * 86400000), '2mo', 'months');
  eq(srsFmtInterval(400 * 86400000), '1.1y', 'years');
});

suite('srsIsDue / srsIsMature', () => {
  ok(srsIsDue(null), 'a card with no state is due');
  ok(srsIsDue({ due: Date.now() - 1000 }), 'past due date is due');
  ok(!srsIsDue({ due: Date.now() + 60000 }), 'future due date is not due');
  ok(srsIsMature({ stability: 30 }), '30d stability is mature');
  ok(!srsIsMature({ stability: 5 }), '5d stability is not mature');
  ok(!srsIsMature(null), 'no state is not mature');
});

// ---- Review log ------------------------------------------------------------

suite('srsLogReview records grade, kind and item key', () => {
  localStorage.clear();
  const ts = srsLogReview('flash', 3, false, 'kira-kira');
  ok(typeof ts === 'number', 'returns the key it logged under');
  const log = srsLoad('bahasa:reviewLog:v1');
  eq(log[ts].g, 3, 'grade stored');
  eq(log[ts].k, 'flash', 'kind stored');
  eq(log[ts].i, 'kira-kira', 'item key stored, so stats can group by tag');
  eq(log[ts].n, 0, 'not-new flag stored');
});

suite('srsLogReview never overwrites a same-millisecond entry', () => {
  localStorage.clear();
  const a = srsLogReview('flash', 3, false, 'x');
  const b = srsLogReview('flash', 1, false, 'y');
  ok(a !== b, 'two reviews in the same tick get distinct keys');
  eq(Object.keys(srsLoad('bahasa:reviewLog:v1')).length, 2, 'both survive');
});

suite('srsUnlogReview removes exactly one entry', () => {
  localStorage.clear();
  const a = srsLogReview('flash', 3, false, 'x');
  srsLogReview('flash', 1, false, 'y');
  srsUnlogReview(a);
  const log = srsLoad('bahasa:reviewLog:v1');
  eq(Object.keys(log).length, 1, 'one entry left');
  ok(!(a in log), 'the undone entry is the one gone');
  srsUnlogReview(undefined);
  eq(Object.keys(srsLoad('bahasa:reviewLog:v1')).length, 1, 'undefined key is a no-op');
});

// ---- Undo ------------------------------------------------------------------

suite('undo stack', () => {
  srsUndoStack.length = 0;
  eq(srsUndoDepth(), 0, 'starts empty');
  eq(srsPopUndo(), null, 'popping empty gives null');
  srsPushUndo({ a: 1 });
  srsPushUndo({ a: 2 });
  eq(srsUndoDepth(), 2, 'depth tracks pushes');
  eq(srsPopUndo().a, 2, 'pops most recent first');
  eq(srsUndoDepth(), 1, 'depth drops after pop');
  srsUndoStack.length = 0;
});

suite('undo stack is capped', () => {
  srsUndoStack.length = 0;
  for (let i = 0; i < 40; i++) srsPushUndo({ i });
  eq(srsUndoDepth(), 30, 'capped at 30');
  eq(srsPopUndo().i, 39, 'newest kept');
  srsUndoStack.length = 0;
});

suite('srsRestoreState stamps rev without touching lastReview', () => {
  const prev = { difficulty: 5, stability: 3.17, due: 123, lastReview: 500, reps: 1 };
  const restored = srsRestoreState(prev);
  eq(restored.stability, 3.17, 'FSRS fields preserved');
  eq(restored.lastReview, 500, 'lastReview untouched — FSRS reads it as when it was really reviewed');
  ok(typeof restored.rev === 'number' && restored.rev > 0, 'rev stamped');
  eq(srsRestoreState(null), null, 'no previous state restores to null (caller deletes)');
});

// ---- Forward stack (what "Go back" should hand you next) -------------------

suite('forward stack replays in the order the undos happened', () => {
  // rate A (see B), rate B (see C), then undo twice. Re-rating A must give
  // back B, and re-rating B must give back C — not a fresh random draw.
  srsClearForward();
  const id = x => x;
  srsPushForward({ front: 'C' });   // first undo displaced C
  srsPushForward({ front: 'B' });   // second undo displaced B
  eq(srsForwardDepth(), 2, 'both queued');
  eq(srsTakeForward(id).front, 'B', 'most recent undo replays first');
  eq(srsTakeForward(id).front, 'C', 'then the one before it');
  eq(srsTakeForward(id), null, 'exhausted');
  eq(srsForwardDepth(), 0, 'drained');
});

suite('forward stack skips items that are no longer eligible', () => {
  srsClearForward();
  srsPushForward({ front: 'still-here' });
  srsPushForward({ front: 'filtered-out' });
  // resolve() stands in for "is it still in the current pool?"
  const resolve = c => (c.front === 'filtered-out' ? null : c);
  eq(srsTakeForward(resolve).front, 'still-here',
    'a queued card that left the pool is skipped, not shown');
  eq(srsForwardDepth(), 0, 'the stale entry was consumed too');
});

suite('forward stack: resolve may swap in a refreshed object', () => {
  // The pool holds the current version of a card; an edit between queueing and
  // replaying should not resurrect the stale copy.
  srsClearForward();
  srsPushForward({ front: 'x', back: 'old' });
  const refreshed = srsTakeForward(c => ({ front: c.front, back: 'new' }));
  eq(refreshed.back, 'new', 'the resolved object is what gets used');
});

suite('forward stack: push ignores nothing-on-screen, clear empties', () => {
  srsClearForward();
  srsPushForward(null);
  srsPushForward(undefined);
  eq(srsForwardDepth(), 0, 'null/undefined are not queued');
  srsPushForward({ front: 'a' });
  srsClearForward();
  eq(srsForwardDepth(), 0, 'clear empties the stack');
  eq(srsTakeForward(x => x), null, 'taking from an empty stack is null');
});

// ---- Sync merges -----------------------------------------------------------

suite('syncMergeFsrs keeps the more recently reviewed side', () => {
  const local = { a: { stability: 1, lastReview: 100 } };
  const incoming = { a: { stability: 9, lastReview: 200 }, b: { stability: 4, lastReview: 50 } };
  const { out, added, updated } = syncMergeFsrs(local, incoming);
  eq(out.a.stability, 9, 'newer incoming wins');
  eq(out.b.stability, 4, 'unseen item added');
  eq(added, 1, 'added counted');
  eq(updated, 1, 'updated counted');
});

suite('syncMergeFsrs: an undo beats an already-pushed rating', () => {
  // The regression this rev field exists for: the device rated a card, pushed
  // it, then the user hit "Go back". Local now holds the OLDER state.
  const ratedRemote = { x: { stability: 1.59, lastReview: 1000 } };
  const restoredLocal = { x: { stability: 3.17, lastReview: 500, rev: 1500 } };
  eq(syncMergeFsrs(restoredLocal, ratedRemote).out.x.stability, 3.17,
    'undo survives the merge');

  // A same-millisecond tie must also favour local, since the merge only
  // replaces on a strictly greater stamp.
  const tie = { x: { stability: 3.17, lastReview: 500, rev: 1000 } };
  eq(syncMergeFsrs(tie, ratedRemote).out.x.stability, 3.17, 'tie favours local');

  // Control: without the stamp the old state loses. If this ever starts
  // passing, the rev mechanism has stopped doing anything.
  const noRev = { x: { stability: 3.17, lastReview: 500 } };
  eq(syncMergeFsrs(noRev, ratedRemote).out.x.stability, 1.59,
    'control — without rev the rated copy wins');
});

suite('syncMergeFlags is a union', () => {
  const { out } = syncMergeFlags({ a: true }, { b: true });
  ok(out.a && out.b, 'both sides kept');
  // Unflagging deliberately does not propagate.
  eq(syncMergeFlags({}, { a: true }).out.a, true, 'incoming flag re-added');
});

suite('syncMergeByField', () => {
  const local = { c1: { front: 'x', updatedAt: 10 } };
  const incoming = { c1: { front: 'y', updatedAt: 20 }, c2: { front: 'z', updatedAt: 1 } };
  const { out } = syncMergeByField(local, incoming, 'updatedAt');
  eq(out.c1.front, 'y', 'newer updatedAt wins');
  eq(out.c2.front, 'z', 'new key added');
});

// ---- Daily goal ------------------------------------------------------------

suite('daily goal', () => {
  localStorage.clear();
  eq(srsGoal(), 30, 'defaults to 30');
  srsSetGoal(12);
  eq(srsGoal(), 12, 'set value is read back');
  srsSetGoal(0);
  eq(srsGoal(), 1, 'clamped to at least 1');
});

suite('srsReviewsToday counts only today', () => {
  localStorage.clear();
  const now = Date.now();
  const log = {};
  log[now - 1000] = { g: 3, k: 'flash' };
  log[now - 2000] = { g: 1, k: 'word' };
  log[now - 3 * 86400000] = { g: 3, k: 'flash' };   // three days ago
  localStorage.setItem('bahasa:reviewLog:v1', JSON.stringify(log));
  eq(srsReviewsToday(), 2, 'older entries excluded');
});

// ---- Bulk vocab parser -----------------------------------------------------

suite('parseBulkVocab: tag blocks', () => {
  const out = parseBulkVocab(
    '(comparison)\nlebih – more\nkurang – less / not enough\n\n(connector)\ndan – and');
  eq(out.length, 3, 'three entries across two blocks');
  eq(out[0].front, 'lebih', 'front parsed');
  eq(out[0].back, 'more', 'back parsed');
  deepEq(out[0].tags, ['comparison'], 'block tag applied');
  deepEq(out[2].tags, ['connector'], 'second block gets its own tag');
  eq(out[1].back, 'less / not enough', 'slashes in the gloss survive');
});

suite('parseBulkVocab: untagged blocks default to custom', () => {
  const out = parseBulkVocab('nyala – on / lit');
  deepEq(out[0].tags, ['custom'], 'defaults to custom');
});

suite('parseBulkVocab: multi-tag headers', () => {
  const out = parseBulkVocab('(emotion, adjective)\nsedih – sad');
  deepEq(out[0].tags, ['emotion', 'adjective'], 'comma-separated header split and trimmed');
});

suite('parseBulkVocab: separator forms', () => {
  eq(parseBulkVocab('a – b')[0].back, 'b', 'en dash');
  eq(parseBulkVocab('a — b')[0].back, 'b', 'em dash');
  eq(parseBulkVocab('a - b')[0].back, 'b', 'plain hyphen');
});

suite('parseBulkVocab: hyphenated Indonesian words stay intact', () => {
  // The separator must be space-padded, or "kira-kira" would split itself.
  const out = parseBulkVocab('kira-kira – about / roughly');
  eq(out[0].front, 'kira-kira', 'reduplicated word kept whole');
  eq(out[0].back, 'about / roughly', 'gloss intact');
});

suite('parseBulkVocab: ellipsis pattern entries', () => {
  const out = parseBulkVocab('(comparison)\nlebih … daripada … – more … than …');
  eq(out[0].front, 'lebih … daripada …', 'placeholder front preserved');
  eq(out[0].back, 'more … than …', 'placeholder back preserved');
});

suite('parseBulkVocab: junk lines are skipped, not guessed at', () => {
  const out = parseBulkVocab('(x)\ngood – line\nno separator here\nanother – ok\n   \n');
  eq(out.length, 2, 'only well-formed lines become entries');
  deepEq(out.map(e => e.front), ['good', 'another'], 'the right two');
  eq(parseBulkVocab('').length, 0, 'empty input yields nothing');
  eq(parseBulkVocab('   \n\n  ').length, 0, 'whitespace-only yields nothing');
});

suite('parseBulkVocab: extra blank lines and stray indentation', () => {
  const out = parseBulkVocab('\n\n(tag)\n   lebih – more   \n\n\n\n(other)\n  dan – and\n\n');
  eq(out.length, 2, 'blank runs do not create phantom blocks');
  deepEq(out[0].tags, ['tag'], 'first block tag');
  eq(out[0].front, 'lebih', 'indentation trimmed from front');
  deepEq(out[1].tags, ['other'], 'second block tag');
});
