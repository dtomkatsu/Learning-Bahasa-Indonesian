#!/usr/bin/env python3
"""
Fetch real Indonesian word recordings from Lingua Libre (via Wikimedia
Commons) for every vocab front that has one.

Why: the family recordings are phone audio captured across rooms — the right
material for comprehension, but often too faint to serve as the *model* you
imitate. Lingua Libre volunteers record isolated words cleanly, one word per
file, under CC BY-SA — real human Indonesian, free, and (unlike any TTS
voice) with genuine between-speaker variety: at last count 577 of this
deck's 994 fronts have at least one recording and 281 have two or more
distinct speakers, which is exactly the raw material word-level HVPT needs.

Files upload to Commons under the fixed pattern
    LL-Q9240 (ind)-<speaker>-<word>.wav        (Q9240 = Indonesian)
so matching against the deck is a filename suffix check, no search API.

For each covered front this downloads a primary clip — from the most
prolific matched speaker, so consecutive cards mostly share one coherent
voice — plus up to ALT_LIMIT alternates from *other* speakers for the
multi-speaker words. Everything is transcoded to ~32kbps mono m4a (a word
clip is 1–2s; the source WAVs would be ~100x the size), written to
audio/ll/, and indexed:

    audio/ll/index.json    {front: {file, author, alts: [{file, author}]}}
    audio/ll/CREDITS.json  {file: {author, license, source}}   (CC BY-SA
                           requires attribution — this is it, per file)

Re-runs are cheap: existing files are skipped, and the index is rewritten
from whatever is on disk, so an interrupted run is a valid partial state —
same philosophy as build_tts.py. Standard library only; transcoding uses
ffmpeg if present, else macOS's afconvert.

    python3 scripts/fetch_lingualibre.py --dry-run
    python3 scripts/fetch_lingualibre.py
"""
import argparse
import csv
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VOCAB_DIR = ROOT / "vocab"
OUT_DIR = ROOT / "audio" / "ll"
INDEX = OUT_DIR / "index.json"
CREDITS = OUT_DIR / "CREDITS.json"

API = "https://commons.wikimedia.org/w/api.php"
PREFIX = "LL-Q9240_(ind)-"
UA = ("bahasa-study-fetch/1.0 "
      "(https://github.com/dtomkatsu/Learning-Bahasa-Indonesian; dtomkatsu@gmail.com)")
ALT_LIMIT = 2          # extra speakers kept per word, beyond the primary
PAUSE = 0.7            # seconds between downloads — Commons asks for restraint


def fetch_json(params, retries=6):
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    delay = 3
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries - 1:
                time.sleep(delay)
                delay = min(delay * 2, 30)
                continue
            raise


def list_recordings():
    """Every Lingua Libre Indonesian file on Commons."""
    names, cont = [], None
    while True:
        params = {"action": "query", "list": "allimages",
                  "aiprefix": "LL-Q9240 (ind)-", "ailimit": "500", "format": "json"}
        if cont:
            params["aicontinue"] = cont
        d = fetch_json(params)
        names.extend(i["name"] for i in d.get("query", {}).get("allimages", []))
        cont = d.get("continue", {}).get("aicontinue")
        if not cont:
            return names
        time.sleep(1.0)


def load_foils():
    """Discrimination foils — real words that are never flashcards.

    They still need a recording, because a minimal pair is only usable if
    BOTH halves have real audio; a foil with no clip silently drops the pair
    it was added for. Shared reader with build_quiz.load_foils by convention
    rather than import, same standalone-runnability rule as everywhere else
    in scripts/.
    """
    path = ROOT / "contrast" / "foils.tsv"
    if not path.exists():
        return {}
    out = {}
    with open(path, encoding="utf-8") as f:
        for row in csv.reader(f, delimiter="\t"):
            if row and row[0].strip() and not row[0].startswith("#"):
                out[row[0].strip().lower()] = row[1].strip() if len(row) > 1 else ""
    return out


def deck_fronts():
    fronts = set(load_foils())
    for tsv in sorted(VOCAB_DIR.glob("*.tsv")):
        with open(tsv, encoding="utf-8") as f:
            for row in csv.reader(f, delimiter="\t"):
                if len(row) >= 3 and row[0].strip():
                    # Same first-spelling rule as build_tts.py
                    fronts.add(row[0].split(" / ")[0].strip().lower())
    return fronts


def match(names, fronts):
    """front -> [(speaker, commons_filename)], via filename suffix."""
    hits = {}
    for n in names:
        if not n.startswith(PREFIX):
            continue
        base = n[len(PREFIX):]
        low = base.replace("_", " ").lower()
        for f in fronts:
            if low.endswith("-" + f + ".wav"):
                speaker = base[: len(base) - len(f) - 5].rstrip("-").replace("_", " ")
                hits.setdefault(f, []).append((speaker, n))
                break
    return hits


def pick(hits):
    """Primary + alternates per word.

    Primary = the most prolific speaker among that word's matches, so the
    default voice stays consistent across as much of the deck as possible;
    alternates = other distinct speakers, most-prolific first, for the
    multi-speaker words a discrimination drill can draw on.
    """
    freq = Counter(s for pairs in hits.values() for s, _ in pairs)
    plan = {}
    for word, pairs in hits.items():
        by_speaker = {}
        for s, n in sorted(pairs):
            by_speaker.setdefault(s, n)          # one file per speaker
        order = sorted(by_speaker, key=lambda s: (-freq[s], s))
        plan[word] = [(s, by_speaker[s]) for s in order[: 1 + ALT_LIMIT]]
    return plan


def slug(word, speaker):
    w = re.sub(r"[^a-z0-9]+", "_", word.lower()).strip("_")
    s = re.sub(r"[^A-Za-z0-9]+", "", speaker)[:12] or "anon"
    return f"{w}-{s}.m4a"


TRANSCODER = None


def transcode(src, dst):
    """WAV -> mono ~32kbps m4a via ffmpeg or afconvert, whichever exists."""
    global TRANSCODER
    if TRANSCODER is None:
        TRANSCODER = "ffmpeg" if shutil.which("ffmpeg") else "afconvert"
    if TRANSCODER == "ffmpeg":
        cmd = ["ffmpeg", "-loglevel", "error", "-y", "-i", str(src),
               "-ac", "1", "-c:a", "aac", "-b:a", "32k", str(dst)]
    else:
        cmd = ["afconvert", "-f", "m4af", "-d", "aac", "-b", "32000",
               "-c", "1", str(src), str(dst)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 and TRANSCODER == "afconvert":
        # Some afconvert builds reject -c; retry letting it keep channels.
        r = subprocess.run(["afconvert", "-f", "m4af", "-d", "aac", "-b", "32000",
                            str(src), str(dst)], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"transcode failed for {src.name}: {r.stderr.strip()[:200]}")


def download(commons_name, dst_wav):
    url = ("https://commons.wikimedia.org/wiki/Special:FilePath/"
           + urllib.parse.quote(commons_name))
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    delay = 3
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                dst_wav.write_bytes(r.read())
                return
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 4:
                time.sleep(delay)
                delay = min(delay * 2, 30)
                continue
            raise


def write_indexes(plan):
    """Index + credits rebuilt from the plan, restricted to files on disk."""
    index, credits = {}, {}
    for word, entries in sorted(plan.items()):
        rows = []
        for speaker, commons_name in entries:
            f = slug(word, speaker)
            if not (OUT_DIR / f).exists():
                continue
            rows.append({"file": f, "author": speaker})
            credits[f] = {
                "author": speaker,
                "license": "CC BY-SA 4.0",
                "source": "https://commons.wikimedia.org/wiki/File:" + commons_name,
            }
        if rows:
            index[word] = {"file": rows[0]["file"], "author": rows[0]["author"],
                           "alts": rows[1:]}
    INDEX.write_text(json.dumps(index, ensure_ascii=False, indent=0, sort_keys=True),
                     encoding="utf-8")
    CREDITS.write_text(json.dumps(credits, ensure_ascii=False, indent=1, sort_keys=True),
                       encoding="utf-8")
    return index


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true",
                    help="report coverage and what would be fetched, download nothing")
    ap.add_argument("--limit", type=int, default=0,
                    help="stop after this many downloads (0 = no limit)")
    args = ap.parse_args()

    fronts = deck_fronts()
    print(f"deck fronts: {len(fronts)}")
    names = list_recordings()
    print(f"Lingua Libre Indonesian files on Commons: {len(names)}")
    hits = match(names, fronts)
    plan = pick(hits)
    multi = sum(1 for e in plan.values() if len(e) > 1)
    wanted = [(w, s, n) for w, entries in sorted(plan.items()) for s, n in entries]
    missing = [(w, s, n) for w, s, n in wanted if not (OUT_DIR / slug(w, s)).exists()]
    print(f"covered fronts: {len(plan)} ({len(plan) * 100 // len(fronts)}%), "
          f"{multi} with 2+ speakers")
    print(f"clips wanted: {len(wanted)}, already on disk: {len(wanted) - len(missing)}, "
          f"to fetch: {len(missing)}")

    if args.dry_run:
        return

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    done = failed = 0
    try:
        with tempfile.TemporaryDirectory() as td:
            for i, (word, speaker, commons_name) in enumerate(missing):
                if args.limit and done >= args.limit:
                    print(f"\nStopping at --limit {args.limit}.")
                    break
                wav = Path(td) / "clip.wav"
                try:
                    download(commons_name, wav)
                    transcode(wav, OUT_DIR / slug(word, speaker))
                    done += 1
                except Exception as e:      # one bad file must not sink the run
                    failed += 1
                    print(f"  ! {word} ({speaker}): {e}", file=sys.stderr)
                if done and done % 50 == 0:
                    print(f"  [{done}/{len(missing)}] …{word}")
                    write_indexes(plan)     # keep the partial state valid
                time.sleep(PAUSE)
    except KeyboardInterrupt:
        print("\nInterrupted — clips already fetched are kept.")
    finally:
        index = write_indexes(plan)
        size = sum(f.stat().st_size for f in OUT_DIR.glob("*.m4a"))
        print(f"\nfetched {done} clip(s) this run, {failed} failed")
        print(f"{INDEX.relative_to(ROOT)} covers {len(index)} words, "
              f"{size / 1e6:.1f} MB on disk")
        print("Re-run build_flashcards.py to attach the clips to cards.")


if __name__ == "__main__":
    main()
