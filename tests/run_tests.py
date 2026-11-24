#!/usr/bin/env python3
"""Test runner for the browser-side logic. No dependencies beyond Node.

    python3 tests/run_tests.py

Two passes:

1. Unit tests. The real _srs_js / _sync_js / _vocab_js sources are concatenated
   with a small localStorage shim and tests/cases.js, then run under Node. This
   covers the FSRS math, the sync merge rules, the undo/rev logic, the review
   log and the bulk vocab parser — pure functions, no DOM.

2. Syntax check. Every generated *.html has its inline <script> extracted and
   passed through `node --check`. This has caught real breakage before (a
   duplicate top-level `const` between a shared module and a page). Note it
   only catches *syntax*: a call to a function that no longer exists is a
   runtime error and passes this check, so it is not a substitute for the
   browser pass.

Exits non-zero if anything fails, so it can gate a commit.
"""
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from _srs_js import SRS_JS          # noqa: E402
from _sync_js import SYNC_JS        # noqa: E402
from _vocab_js import VOCAB_JS      # noqa: E402
from _voice_js import VOICE_JS      # noqa: E402

# Minimal browser surface. Only what the modules touch at load time or inside
# the pure functions under test — anything network- or DOM-bound is out of
# scope for these tests and simply never called.
SHIM = r"""
const __store = {};
globalThis.localStorage = {
  getItem: k => (Object.prototype.hasOwnProperty.call(__store, k) ? __store[k] : null),
  setItem: (k, v) => { __store[k] = String(v); },
  removeItem: k => { delete __store[k]; },
  clear: () => { for (const k of Object.keys(__store)) delete __store[k]; },
};
globalThis.window = globalThis;
globalThis.matchMedia = () => ({ matches: false, addEventListener() {} });
globalThis.innerWidth = 1280;
globalThis.addEventListener = () => {};
globalThis.document = { addEventListener() {}, getElementById: () => null, hidden: false };

let __pass = 0, __fail = 0, __suite = '';
function suite(name, fn) {
  __suite = name;
  try {
    fn();
  } catch (e) {
    __fail++;
    console.log(`  ✗ ${name}: threw ${e && e.message ? e.message : e}`);
  }
}
function ok(cond, msg) {
  if (cond) { __pass++; }
  else { __fail++; console.log(`  ✗ ${__suite} — ${msg}`); }
}
function eq(actual, expected, msg) {
  ok(Object.is(actual, expected), `${msg} (expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)})`);
}
function deepEq(actual, expected, msg) {
  ok(JSON.stringify(actual) === JSON.stringify(expected),
     `${msg} (expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)})`);
}
// Async suites run one after another (they share localStorage and fetch),
// after all the synchronous ones; the footer waits for the chain.
let __asyncChain = Promise.resolve();
function asyncSuite(name, fn) {
  __asyncChain = __asyncChain.then(async () => {
    __suite = name;
    try { await fn(); }
    catch (e) { __fail++; console.log(`  ✗ ${name}: threw ${e && e.message ? e.message : e}`); }
  });
}
globalThis.__report = () => {
  console.log(`\n  ${__pass} passed, ${__fail} failed`);
  return __fail;
};
"""

FOOTER = "\n__asyncChain.then(() => process.exit(__report()));\n"


def run_unit_tests():
    cases = (ROOT / "tests" / "cases.js").read_text(encoding="utf-8")
    bundle = SHIM + SRS_JS + SYNC_JS + VOCAB_JS + VOICE_JS + cases + FOOTER
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(bundle)
        path = f.name
    print("unit tests")
    proc = subprocess.run(["node", path], capture_output=True, text=True)
    sys.stdout.write(proc.stdout)
    if proc.stderr.strip():
        sys.stderr.write(proc.stderr)
    Path(path).unlink(missing_ok=True)
    return proc.returncode == 0


# Replays every answer the voice drill logged on the phone (see
# scripts/voice_log_fixture.py) through the current matcher, against the
# card's current back. Fails on a false accept (an answer the learner said
# was wrong, now marked correct) or a lost accept (one the drill accepted
# before, now not); otherwise just reports how the mix moved.
REPLAY = r"""
let skipped = 0;
const out = { total: 0, correct: 0, ask: 0, grade: 0, command: 0, rescued: [], falseAccept: [], lost: [], changed: [] };
for (const c of __CASES) {
  const back = __BACK[c.front];
  if (!back) { skipped++; continue; }
  const r = voiceClassifyAnswer(c.heard, back, __ALT[c.front]);
  const now = r.kind === 'unclear' ? 'unclear' : r.kind + (r.grade ? ' ' + r.grade : '') + (r.cmd ? ' ' + r.cmd : '');
  out.total++;
  if (r.kind === 'correct') out.correct++;
  else if (r.kind === 'unclear') out.ask++;
  else if (r.kind === 'grade') out.grade++;
  else out.command++;
  const tag = `${c.front}: "${c.heard}"`;
  if (c.truth === 'wrong' && r.kind === 'correct') out.falseAccept.push(tag);
  if (c.then === 'correct' && r.kind !== 'correct') out.lost.push(tag + ' -> ' + now);
  if (c.then === 'unclear' && r.kind === 'correct' && (c.truth === 'right' || c.truth === 'hard')) out.rescued.push(tag);
  if (now !== c.then) out.changed.push(`${tag}  ${c.then} -> ${now}`);
}
let replies = 0, understood = 0;
const missed = [];
for (const c of __CASES) for (const reply of (c.confirm || [])) {
  if (!reply) continue;
  replies++;
  const k = voiceClassifyConfirm(reply).kind;
  if (k === 'grade' || k === 'command') understood++; else missed.push(reply);
}
const pct = n => Math.round(100 * n / Math.max(1, out.total)) + '%';
console.log(`  ${out.total} answers from the phone (${skipped} for cards no longer in the deck)`);
console.log(`  now: ${out.correct} accepted (${pct(out.correct)}), ${out.ask} asked right-or-wrong (${pct(out.ask)}), ` +
  `${out.grade} self-graded, ${out.command} commands`);
console.log(`  rescued (learner said right/hard, now accepted without asking): ${out.rescued.length}`);
out.rescued.forEach(t => console.log('    + ' + t));
console.log(`  right-or-wrong replies understood: ${understood}/${replies}` + (missed.length ? `  (not: ${missed.map(m => JSON.stringify(m)).join(', ')})` : ''));
if (out.changed.length) { console.log('  changed since logged:'); out.changed.forEach(t => console.log('    ' + t)); }
out.falseAccept.forEach(t => console.log('  ✗ false accept (learner said wrong): ' + t));
out.lost.forEach(t => console.log('  ✗ no longer accepted: ' + t));
process.exit(out.falseAccept.length || out.lost.length ? 1 : 0);
"""


def run_phone_replay():
    import json
    fixture = ROOT / "tests" / "voice-phone-answers.json"
    print("\nvoice drill: replay of answers logged on the phone")
    if not fixture.exists():
        print("  (no tests/voice-phone-answers.json yet: run scripts/voice_log_fixture.py)")
        return True
    from build_flashcards import load_decks   # noqa: E402
    backs = {c["front"]: c["back"] for c in load_decks()}
    answers = ROOT / "vocab" / "voice-answers.json"
    alts = json.loads(answers.read_text(encoding="utf-8")) if answers.exists() else {}
    cases = json.loads(fixture.read_text(encoding="utf-8"))
    bundle = (VOICE_JS + "\nconst __CASES = " + json.dumps(cases, ensure_ascii=False)
              + ";\nconst __BACK = " + json.dumps(backs, ensure_ascii=False)
              + ";\nconst __ALT = " + json.dumps(alts, ensure_ascii=False) + ";\n" + REPLAY)
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(bundle)
        path = f.name
    proc = subprocess.run(["node", path], capture_output=True, text=True)
    Path(path).unlink(missing_ok=True)
    sys.stdout.write(proc.stdout)
    if proc.stderr.strip():
        sys.stderr.write(proc.stderr)
    return proc.returncode == 0


def run_syntax_checks():
    print("\nsyntax check of generated pages")
    pages = sorted(ROOT.glob("*.html"))
    if not pages:
        print("  ! no generated pages found — run the build scripts first")
        return False
    all_ok = True
    for page in pages:
        html = page.read_text(encoding="utf-8")
        scripts = re.findall(r"<script>(.*?)</script>", html, re.S)
        if not scripts:
            continue
        for i, src in enumerate(scripts):
            with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
                f.write(src)
                path = f.name
            proc = subprocess.run(["node", "--check", path], capture_output=True, text=True)
            Path(path).unlink(missing_ok=True)
            if proc.returncode != 0:
                all_ok = False
                print(f"  ✗ {page.name} script {i}")
                print("    " + proc.stderr.strip().splitlines()[0])
        if all_ok:
            print(f"  ✓ {page.name}")
    return all_ok


def main():
    units_ok = run_unit_tests()
    replay_ok = run_phone_replay()
    syntax_ok = run_syntax_checks()
    if units_ok and replay_ok and syntax_ok:
        print("\nall green")
        return 0
    print("\nFAILED")
    return 1


if __name__ == "__main__":
    sys.exit(main())
