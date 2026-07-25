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
globalThis.__report = () => {
  console.log(`\n  ${__pass} passed, ${__fail} failed`);
  return __fail;
};
"""

FOOTER = "\nprocess.exit(__report());\n"


def run_unit_tests():
    cases = (ROOT / "tests" / "cases.js").read_text(encoding="utf-8")
    bundle = SHIM + SRS_JS + SYNC_JS + VOCAB_JS + cases + FOOTER
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
    syntax_ok = run_syntax_checks()
    if units_ok and syntax_ok:
        print("\nall green")
        return 0
    print("\nFAILED")
    return 1


if __name__ == "__main__":
    sys.exit(main())
