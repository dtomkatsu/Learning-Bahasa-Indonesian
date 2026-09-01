#!/usr/bin/env python3
"""
Pre-generate spoken audio for every card's example sentence, using
ElevenLabs, at build time — so the shipped site is static files and no API
key ever reaches a browser.

Why this exists: the example sentences were written for this deck, so no
recording of them exists or ever could — not in the family audio, not in any
corpus of real speech. They currently fall back to the device's own speech
synthesis, which on a typical desktop browser means no Indonesian voice at
all and a disabled button. That covers the ~570 flashcard backs and all 984
fill-the-blank items whose only audio is their sentence.

Sentences only, deliberately — see load_texts() for why the bare card words
are not generated, and notes/audio-retool.md for the source hierarchy that
already gives 577 of those words a real volunteer recording instead.

Generated at the model's natural speaking rate on purpose. Slower audio does
help L2 listening, but the evidence favours giving the *learner* the control
(Zhao 1997) over baking one fixed rate in, and artificially slowing synthesis
risks flattening exactly the syllable-timed rhythm that scripts/_rhythm_tip.py
teaches — so speed is a playback-side control, not a generation-side one.

Why build-time and not a call from the page: an ElevenLabs key is a billable
credential. Calling the API from the browser would work, but the key would sit
readable in the page source of a public site, and ElevenLabs' own guidance is
that it must not be exposed client-side. Here the key lives in your shell for
the length of one run and is never written anywhere.

    export ELEVENLABS_API_KEY=...
    python3 scripts/build_tts.py --list-voices     # find an Indonesian voice
    export ELEVENLABS_VOICE_ID=...
    python3 scripts/build_tts.py --dry-run         # what it would cost
    python3 scripts/build_tts.py --limit 9000      # stay inside a free month
    python3 scripts/build_tts.py --prune           # drop orphaned clips

Output lands in audio/tts/ as content-hashed mp3s plus an index.json that
build_flashcards.py and build_quiz.py read to attach a clip to each card.
Because the filename is a hash of (text, voice, model), editing one example
sentence regenerates exactly one file and every other clip is skipped — so
re-running after a deck edit is cheap, and so is spreading a first full run
across two free months.

Standard library only, like the rest of this project.
"""
import argparse
import csv
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VOCAB_DIR = ROOT / "vocab"
OUT_DIR = ROOT / "audio" / "tts"
INDEX = OUT_DIR / "index.json"
LL_INDEX = ROOT / "audio" / "ll" / "index.json"

API_ROOT = "https://api.elevenlabs.io/v1"

# Flash rather than multilingual_v2 for a reason specific to this deck, not
# just its half-price billing: `language_code` is not supported on
# multilingual_v2, and 17 example sentences contain tokens like "HP", "AC",
# "SD" and "seafood" that a language-guessing synthesiser reads with English
# phonics. Those have to come out ha-pe, a-se, es-de.
DEFAULT_MODEL = "eleven_flash_v2_5"
LANGUAGE = "id"

# The lowest-bitrate mp3 in the API's format enum. A 2-second clip at the
# default 128kbps would be four times the size for headphone fidelity nobody
# needs; at 32kbps the whole deck is ~13 MB.
OUTPUT_FORMAT = "mp3_22050_32"

# Measured, not quoted: the 414-word run on 2026-08-31 moved this account's
# character_count by 844 for 3,349 characters — 0.252 credits/char on Flash,
# half the 0.5 the pricing write-ups reported and this constant used to
# assume. Only affects the estimate printed below, so an overestimate was
# harmless; it did make the budget look twice as tight as it is. Note the
# subscription counter is eventually consistent and climbs for a minute or
# two after a run, so re-read it before trusting a delta.
CREDITS_PER_CHAR = 0.25


# One card front is English on purpose — a code-switch card recording that
# Dila asked her question in English mid-Indonesian-sentence. An Indonesian
# voice pinned to language_code="id" would read it with Indonesian phonics,
# teaching the opposite of what the card exists to show.
SKIP_WORDS = {"Can I ask a question?"}


def load_ll_index():
    """Lowercased word -> volunteer recording, or {} if none were ever fetched.

    Re-read rather than imported, same reason as the vocab read below: this
    script has to stay runnable even if the rest of the build is mid-edit.
    """
    if not LL_INDEX.exists():
        return {}
    try:
        return json.loads(LL_INDEX.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def load_texts():
    """Every example sentence, plus the card fronts no volunteer ever recorded.

    Sentences are unconditional. Words come back marked kind="word" and are
    only *generated* under --words — but they are always planned and always
    indexed, so a later plain run can neither drop them from index.json nor
    --prune the clips a --words run paid for.

    Which words: only fronts with no Lingua Libre recording. The original call
    here (2026-08-03) was to voice no words at all, because `wordSrc` reaches
    exactly one control — the front-of-card "Hear it" button — and volunteer
    recordings already covered the fronts. That second half is what changed:
    415 fronts have no volunteer recording, and on a desktop browser with no
    Indonesian speechSynthesis voice their button is disabled outright. This
    is that uncovered remainder, not the duplicate set rejected then; where a
    volunteer recording exists it still outranks the studio voice in
    build_flashcards.load_decks and nothing is generated for it.
    """
    ll = load_ll_index()
    seen = {}
    for tsv in sorted(VOCAB_DIR.glob("*.tsv")):
        with open(tsv, encoding="utf-8") as f:
            for row in csv.reader(f, delimiter="\t"):
                if len(row) < 3 or not row[0].strip():
                    continue
                if len(row) > 3 and row[3].strip():
                    seen.setdefault(row[3].strip(), "sentence")
                # build_flashcards speaks only the first spelling of a slash
                # front and looks the clip up under exactly that string, so
                # the key here has to be that same substring.
                spoken = row[0].split(" / ")[0].strip()
                if spoken and spoken not in SKIP_WORDS and spoken.lower() not in ll:
                    seen.setdefault(spoken, "word")
    return seen


def clip_name(text, voice, model):
    """Content-addressed filename: same text, voice and model -> same file.

    Means an unchanged sentence is never paid for twice, a changed one
    regenerates only itself, and a voice or model switch is a clean reset
    rather than a silent mix of old and new audio.
    """
    key = f"{text}|{voice}|{model}".encode("utf-8")
    return hashlib.sha1(key).hexdigest()[:16] + ".mp3"


def api_request(path, api_key, data=None, params=None, timeout=60):
    """One place that talks to ElevenLabs. Returns raw response bytes."""
    url = f"{API_ROOT}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body, method="POST" if body else "GET")
    req.add_header("xi-api-key", api_key)
    req.add_header("accept", "*/*")
    if body:
        req.add_header("content-type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


class BlockedError(RuntimeError):
    """An egress proxy refused to open a tunnel to the API.

    Distinct from a network blip because it is not transient: retrying a
    policy denial just sleeps through the backoff and fails identically, and
    the fix is never in this script.
    """


def _policy_denial(reason):
    """Whether a URLError reason is a proxy refusing the CONNECT.

    A corporate or sandboxed egress proxy answers CONNECT with 403 (host not
    on the allowlist) or 407 (credentials required). urllib surfaces both as
    'Tunnel connection failed: <code> ...' rather than as an HTTPError, since
    the failure happened before any HTTP request reached the origin.
    """
    text = str(reason)
    return "tunnel connection failed" in text.lower() and ("403" in text or "407" in text)


def synthesize(text, voice, model, api_key, retries=4):
    """Speak one string, with backoff on rate limits and transient failures.

    Raises on a 4xx that isn't 429 — a bad key or an unknown voice should stop
    the run immediately rather than burn through the whole deck failing — and
    likewise on a proxy policy denial, which no amount of waiting fixes.
    """
    payload = {"text": text, "model_id": model, "language_code": LANGUAGE}
    delay = 2
    for attempt in range(retries + 1):
        try:
            return api_request(
                f"/text-to-speech/{voice}", api_key,
                data=payload, params={"output_format": OUTPUT_FORMAT},
            )
        except urllib.error.HTTPError as e:
            transient = e.code == 429 or e.code >= 500
            if not transient or attempt == retries:
                detail = ""
                try:
                    detail = e.read().decode("utf-8", "replace")[:400]
                except Exception:
                    pass
                raise RuntimeError(f"HTTP {e.code} for {text!r}: {detail}") from None
            time.sleep(delay)
            delay *= 2
        except urllib.error.URLError as e:
            if _policy_denial(e.reason):
                raise BlockedError(
                    f"the egress proxy refused a tunnel to {API_ROOT} "
                    f"({e.reason}).\n"
                    "  This is a network policy decision, not a problem with your key\n"
                    "  or this script — the host is not on the allowlist for this\n"
                    "  environment. Run it from a machine that can reach\n"
                    "  api.elevenlabs.io, or have the host allowlisted."
                ) from None
            if attempt == retries:
                raise RuntimeError(f"network error for {text!r}: {e.reason}") from None
            time.sleep(delay)
            delay *= 2
    raise RuntimeError("unreachable")


def preflight(api_key):
    """Fail fast and legibly if the API isn't reachable at all.

    Without this, a blocked host shows up as a failure on the first clip after
    the run has already printed a plan and looked like it was starting — and
    with retries, several seconds of pointless backoff first.
    """
    try:
        api_request("/models", api_key, timeout=20)
        return
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise RuntimeError(
                "the API rejected the key (HTTP %d). Check ELEVENLABS_API_KEY." % e.code
            ) from None
        return          # any other response still proves the host is reachable
    except urllib.error.URLError as e:
        if _policy_denial(e.reason):
            raise BlockedError(
                f"cannot reach {API_ROOT} — the egress proxy refused the tunnel "
                f"({e.reason}).\n"
                "  This is a network policy decision, not a problem with your key\n"
                "  or this script. Run it from a machine that can reach\n"
                "  api.elevenlabs.io, or have the host allowlisted."
            ) from None
        raise RuntimeError(f"cannot reach {API_ROOT}: {e.reason}") from None


def list_voices(api_key, query_language="id"):
    """Print Indonesian voices from the shared library, to pick one from.

    The library search takes an explicit `language` filter, so this is a real
    search rather than "any multilingual voice, hope it sounds Indonesian" —
    which matters, since a multilingual voice reading Indonesian can carry an
    English accent into it.
    """
    for value in (query_language, "Indonesian"):
        try:
            raw = api_request("/shared-voices", api_key,
                              params={"language": value, "page_size": 30})
        except urllib.error.URLError as e:
            if _policy_denial(getattr(e, "reason", "")):
                sys.exit(f"\ncannot reach {API_ROOT} — the egress proxy refused the "
                         f"tunnel ({e.reason}).\n  Run this from a machine that can "
                         f"reach api.elevenlabs.io.")
            print(f"  query language={value!r} failed: {e}")
            continue
        except Exception as e:
            print(f"  query language={value!r} failed: {e}")
            continue
        voices = json.loads(raw).get("voices", [])
        if not voices:
            print(f"  query language={value!r}: no results")
            continue
        print(f"\n  {len(voices)} voice(s) for language={value!r}:\n")
        for v in voices:
            print(f"    {v.get('voice_id', '?'):24} {v.get('name', '?'):22} "
                  f"{v.get('accent') or '-':14} {v.get('gender') or '-':8} "
                  f"{v.get('age') or '-'}")
        print("\n  Listen to a candidate before committing to it — a whole deck "
              "in the wrong voice is a whole deck to regenerate.")
        return
    print("  No Indonesian voices returned. Note the library search is reported "
          "to require a paid plan; could not verify that from here.")


def plan(texts, voice, model):
    """What each string maps to on disk, and whether it's already there."""
    rows = []
    for text, kind in texts.items():
        name = clip_name(text, voice, model)
        rows.append({
            "text": text, "kind": kind, "name": name,
            "path": OUT_DIR / name,
            "exists": (OUT_DIR / name).exists(),
        })
    return rows


def write_index(rows):
    """text -> filename, for the page builders to attach clips to cards.

    Only clips actually on disk go in, so a partial run (a free month's worth)
    produces a valid index that covers what exists and silently falls back to
    speech synthesis for the rest.
    """
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    index = {r["text"]: r["name"] for r in rows if r["path"].exists()}
    INDEX.write_text(json.dumps(index, ensure_ascii=False, indent=0, sort_keys=True),
                     encoding="utf-8")
    return index


def prune(rows):
    """Delete clips no longer referenced — voice changes and edited sentences
    orphan their old audio, and nothing else will ever clean it up."""
    keep = {r["name"] for r in rows} | {INDEX.name}
    removed = 0
    freed = 0
    for f in OUT_DIR.glob("*.mp3"):
        if f.name not in keep:
            freed += f.stat().st_size
            f.unlink()
            removed += 1
    return removed, freed


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--voice", default=os.environ.get("ELEVENLABS_VOICE_ID"),
                    help="voice id (or set ELEVENLABS_VOICE_ID)")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--limit", type=int, default=0,
                    help="stop after this many characters — free tier is 10,000 "
                         "credits/month, i.e. 20,000 characters on a half-rate model")
    ap.add_argument("--dry-run", action="store_true",
                    help="report what's missing and what it would cost, generate nothing")
    ap.add_argument("--words", action="store_true",
                    help="also voice the card fronts that have no Lingua Libre "
                         "volunteer recording — without this they are planned "
                         "and indexed but never generated")
    ap.add_argument("--prune", action="store_true",
                    help="also delete clips no card refers to any more")
    ap.add_argument("--list-voices", action="store_true",
                    help="search the shared voice library for Indonesian voices and exit")
    args = ap.parse_args()

    api_key = os.environ.get("ELEVENLABS_API_KEY")

    if args.list_voices:
        if not api_key:
            sys.exit("ELEVENLABS_API_KEY is not set.")
        list_voices(api_key)
        return

    texts = load_texts()
    if not texts:
        sys.exit(f"No vocab found in {VOCAB_DIR}.")

    # The voice is part of the content hash, so a dry run without one would
    # report against filenames the real run would never produce.
    voice = args.voice or "VOICE_UNSET"
    rows = plan(texts, voice, args.model)

    def report(kind, label):
        group = [r for r in rows if r["kind"] == kind]
        gone = [r for r in group if not r["exists"]]
        chars = sum(len(r["text"]) for r in gone)
        print(f"{len(group)} {label} wanted; {len(group) - len(gone)} already "
              f"generated, {len(gone)} missing ({chars:,} characters -> "
              f"~{chars * CREDITS_PER_CHAR:,.0f} credits on {args.model})")

    report("sentence", "example sentences")
    report("word", "unrecorded card fronts")

    # Words are planned and indexed unconditionally so that a plain run never
    # drops or prunes them, but they are only paid for when asked for.
    missing = [r for r in rows if not r["exists"]
               and (args.words or r["kind"] != "word")]
    chars = sum(len(r["text"]) for r in missing)
    if not args.words and any(r["kind"] == "word" and not r["exists"] for r in rows):
        print("--words not set, so the card fronts above will be skipped.")
    print(f"this run would generate {len(missing)} clip(s), {chars:,} characters "
          f"(~{chars * CREDITS_PER_CHAR:,.0f} credits)")

    if args.dry_run:
        if not args.voice:
            print("\nNote: no voice set, so these filenames are placeholders. "
                  "Set --voice/ELEVENLABS_VOICE_ID for real ones.")
        budget = args.limit or None
        if budget:
            n = 0
            spent = 0
            for r in missing:
                if spent + len(r["text"]) > budget:
                    break
                spent += len(r["text"])
                n += 1
            print(f"--limit {budget:,} would generate {n} of {len(missing)} "
                  f"this run ({spent:,} characters)")
        return

    if not args.voice:
        sys.exit("No voice set. Use --voice or ELEVENLABS_VOICE_ID "
                 "(--list-voices finds one).")
    if not api_key:
        sys.exit("ELEVENLABS_API_KEY is not set.")

    try:
        preflight(api_key)
    except RuntimeError as e:
        sys.exit(f"\n{e}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    done = 0
    spent = 0
    try:
        for r in missing:
            if args.limit and spent + len(r["text"]) > args.limit:
                print(f"\nStopping at the {args.limit:,}-character limit. "
                      f"Re-run to continue — finished clips are skipped.")
                break
            audio = synthesize(r["text"], args.voice, args.model, api_key)
            # Written via a temp name so an interrupted run can't leave a
            # truncated mp3 that the next run would treat as already done.
            tmp = r["path"].with_suffix(".part")
            tmp.write_bytes(audio)
            tmp.rename(r["path"])
            spent += len(r["text"])
            done += 1
            print(f"  [{done}/{len(missing)}] {r['kind']:8} {r['text'][:52]}")
    except KeyboardInterrupt:
        print("\nInterrupted — clips already written are kept.")
    except BlockedError as e:
        print(f"\nStopped: {e}", file=sys.stderr)
    except RuntimeError as e:
        print(f"\nStopped: {e}", file=sys.stderr)
    finally:
        index = write_index(rows)
        if args.prune:
            removed, freed = prune(rows)
            print(f"pruned {removed} orphaned clip(s), {freed / 1e6:.1f} MB")
        total = sum(f.stat().st_size for f in OUT_DIR.glob("*.mp3"))
        try:
            where = INDEX.relative_to(ROOT)
        except ValueError:      # OUT_DIR pointed somewhere outside the repo
            where = INDEX
        print(f"\nwrote {done} clip(s) this run, {spent:,} characters "
              f"(~{spent * CREDITS_PER_CHAR:,.0f} credits)")
        print(f"{where} now covers {len(index)} of {len(rows)} "
              f"clips, {total / 1e6:.1f} MB on disk")
        if len(index) < len(rows):
            print("Re-run to fill the rest; cards with no clip fall back to "
                  "the device's speech synthesis.")


if __name__ == "__main__":
    main()
