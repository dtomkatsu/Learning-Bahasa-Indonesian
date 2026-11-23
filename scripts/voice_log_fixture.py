#!/usr/bin/env python3
"""
Turn the voice drill's phone logs into regression cases.

voice.html records each step of a session and uploads it to the progress-sync
gist as voice-debug-log.json (see build_voice.py). This pulls that file (or
reads saved copies), extracts every answer window, and merges the answers
into tests/voice-phone-answers.json, which tests/run_tests.py replays through
the current matching logic. That way a change to the matcher is measured
against what was actually said on the phone, not invented examples.

Each case is one answer to one card:
    {"session": ..., "t": ..., "front": "laut", "heard": "See",
     "then": "unclear", "confirm": ["Great", "Right"], "truth": "right"}

`then` is what the drill decided at the time. `truth` is what the learner
said it was, taken from the right-or-wrong reply when the drill asked:
"right", "hard", "wrong", or "unknown" when it wasn't asked (an answer the
drill accepted, or a self-grade).

The log holds only the newest 600 steps and restarts with every session, so
run this after a session to keep its answers.

Usage:
    python3 scripts/voice_log_fixture.py              # fetch from the sync gist (needs gh)
    python3 scripts/voice_log_fixture.py log.json ... # merge saved log files
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "tests" / "voice-phone-answers.json"
LOG_FILE = "voice-debug-log.json"
PROGRESS_FILE = "bahasa-progress.json"

QUOTED = re.compile(r'"((?:[^"\\]|\\.)*)"\s*$')


def heard_of(d):
    """listen.done carries the transcript as a JSON string, after an optional
    reason ("gap", "deadline") in the Safari-engine logs."""
    m = QUOTED.search(str(d))
    return json.loads('"' + m.group(1) + '"') if m else ""


RIGHT = re.compile(r"\b(right|correct|yes|yeah|yep|good|great|perfect|got it)\b", re.I)
WRONG = re.compile(r"\b(wrong|again|no|nope|nah|don'?t know|incorrect|missed)\b", re.I)
HARD = re.compile(r"\b(hard|almost|close)\b", re.I)


def truth_of(confirm):
    """The learner's own verdict, from the first reply that gives one.
    Wrong is checked first so "not right" reads as wrong."""
    for c in confirm:
        if WRONG.search(c):
            return "wrong"
        if HARD.search(c):
            return "hard"
        if RIGHT.search(c):
            return "right"
    return "unknown"


def extract(payload):
    log = payload.get("log", [])
    session = payload.get("sent", "")
    start = next((e for e in log if e["ev"] == "start"), None)
    if start:
        session = f"{session}#{start['t']}"
    cases = []
    heard = None
    case = None
    for e in log:
        ev, d = e["ev"], e["d"]
        if ev == "listen.done":
            heard = heard_of(d)
            if case is not None:            # a right-or-wrong reply
                case["confirm"].append(heard)
        elif ev == "decided":
            front, _, then = str(d).rpartition(" -> ")
            case = None
            if heard is None or not front:
                continue
            kind = then.split()[0]
            if kind == "silent":
                continue                    # nothing was said; nothing to replay
            c = {"session": session, "t": e["t"], "front": front, "heard": heard,
                 "then": then, "confirm": []}
            cases.append(c)
            if kind == "unclear":
                case = c                    # collect its right-or-wrong replies
        elif ev == "sayId":
            case = None
    for c in cases:
        c["truth"] = truth_of(c["confirm"]) if c["then"] == "unclear" else "unknown"
        if not c["confirm"]:
            del c["confirm"]
    return cases


def fetch_from_gist():
    """The sync gist is the one holding the progress file; find it the way
    the pages do, then read the log file out of it."""
    out = subprocess.run(
        ["gh", "api", "gists", "--paginate", "--jq",
         f'.[] | select(.files["{PROGRESS_FILE}"]) | .id'],
        capture_output=True, text=True, check=True).stdout.split()
    if not out:
        sys.exit("no gist with " + PROGRESS_FILE)
    content = subprocess.run(
        ["gh", "api", f"gists/{out[0]}", "--jq", f'.files["{LOG_FILE}"].content'],
        capture_output=True, text=True, check=True).stdout.strip()
    if not content or content == "null":
        sys.exit("the sync gist has no " + LOG_FILE + " yet")
    return [json.loads(content)]


def main():
    payloads = ([json.loads(Path(p).read_text(encoding="utf-8")) for p in sys.argv[1:]]
                if len(sys.argv) > 1 else fetch_from_gist())
    existing = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else []
    seen = {(c["session"], c["t"]) for c in existing}
    added = 0
    for payload in payloads:
        for c in extract(payload):
            if (c["session"], c["t"]) in seen:
                continue
            seen.add((c["session"], c["t"]))
            existing.append(c)
            added += 1
    existing.sort(key=lambda c: (c["session"], c["t"]))
    OUT.write_text(json.dumps(existing, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    truths = {}
    for c in existing:
        truths[c["truth"]] = truths.get(c["truth"], 0) + 1
    print(f"{OUT.name}: {len(existing)} answers ({added} new); learner verdicts: {truths}")


if __name__ == "__main__":
    main()
