#!/usr/bin/env python3
"""
Record the voice drill's English with ElevenLabs, once, at build time.

voice.html speaks English between Indonesian words: the meaning of each card
("Yes." + its first meaning when you knew it, every meaning when you didn't)
and a dozen fixed lines ("Right or wrong?", "Going back."). Without this it
uses the phone's own speech synthesis. With it, each of those strings plays
as a recorded clip, and anything not recorded yet still falls back to the
phone, so a partial run is fine.

The strings are computed by the page's own JavaScript (voiceSpokenGloss,
voiceShortGloss and VOICE_PHRASES in _voice_js.py, run under Node), so a clip
exists for exactly the text the page will look up. Clips are pieces, not
sentences: "Yes." is recorded once and played before any meaning.

Same rules as build_tts.py, whose API code this reuses: the key comes from
your shell for one run and is never written anywhere; files are named by a
hash of (text, voice, model), so a re-run only pays for what changed.

    export ELEVENLABS_API_KEY=...
    python3 scripts/build_voice_tts.py --dry-run      # what it would cost
    python3 scripts/build_voice_tts.py                # record everything missing
    python3 scripts/build_voice_tts.py --list-voices  # English voices on the account
    python3 scripts/build_voice.py                    # rebuild the page with the clips

Output: audio/tts-en/*.mp3 plus index.json (text -> file), read by
build_voice.py.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import build_tts
from build_tts import clip_name, synthesize, preflight, api_request, BlockedError
from build_flashcards import load_decks
from _voice_js import VOICE_JS

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "audio" / "tts-en"
INDEX = OUT_DIR / "index.json"

MODEL = "eleven_flash_v2_5"
# "Sarah", one of ElevenLabs' premade voices: works on every plan, unlike
# the Voice Library voice the Indonesian clips use. Pinned for the same
# reason build_tts.py pins its voice: it is part of every filename, so
# changing it is a deliberate whole-set re-record.
DEFAULT_VOICE = "EXAVITQu4vr4xnSDxMaL"

TEXTS_JS = r"""
const out = new Set(Object.values(VOICE_PHRASES));
for (const back of __BACKS) {
  out.add(voiceSpokenGloss(back));
  out.add(voiceShortGloss(back));
}
console.log(JSON.stringify([...out].filter(Boolean).sort()));
"""


def drill_texts():
    """Every English string voice.html can say, from its own code."""
    backs = [c["back"] for c in load_decks()]
    src = VOICE_JS + "\nconst __BACKS = " + json.dumps(backs, ensure_ascii=False) + ";\n" + TEXTS_JS
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(src)
        path = f.name
    try:
        out = subprocess.run(["node", path], capture_output=True, text=True, check=True).stdout
    finally:
        Path(path).unlink(missing_ok=True)
    return json.loads(out)


def list_voices(api_key):
    voices = json.loads(api_request("/voices", api_key)).get("voices", [])
    for v in voices:
        labels = v.get("labels") or {}
        print(f"  {v.get('voice_id'):24} {v.get('name', '?'):28} {v.get('category', '-'):12} "
              f"{labels.get('accent', '-'):12} {labels.get('gender', '-')}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--voice", default=os.environ.get("ELEVENLABS_EN_VOICE_ID", DEFAULT_VOICE))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--list-voices", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="stop after this many characters")
    args = ap.parse_args()

    texts = drill_texts()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = [(t, clip_name(t, args.voice, MODEL)) for t in texts]
    todo = [(t, n) for t, n in rows if not (OUT_DIR / n).exists()]
    chars = sum(len(t) for t, _ in todo)
    print(f"{len(texts)} English lines; {len(rows) - len(todo)} already recorded; "
          f"{len(todo)} to record, {chars:,} characters "
          f"(~{int(chars * build_tts.CREDITS_PER_CHAR):,} credits on Flash)")

    def write_index():
        index = {t: n for t, n in rows if (OUT_DIR / n).exists()}
        INDEX.write_text(json.dumps(index, ensure_ascii=False, indent=0, sort_keys=True), encoding="utf-8")
        return index

    if args.dry_run:
        return
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        sys.exit("set ELEVENLABS_API_KEY for this run (it is never written anywhere)")
    try:
        preflight(api_key)
        if args.list_voices:
            list_voices(api_key)
            return
    except (BlockedError, RuntimeError) as e:
        sys.exit(str(e))

    build_tts.LANGUAGE = "en"          # synthesize() sends this as language_code
    spent = 0
    for i, (text, name) in enumerate(todo, 1):
        if args.limit and spent + len(text) > args.limit:
            print(f"stopping at the {args.limit:,}-character limit")
            break
        try:
            audio = synthesize(text, args.voice, MODEL, api_key)
        except (BlockedError, RuntimeError) as e:
            write_index()
            sys.exit(f"stopped after {i - 1} clips: {e}")
        (OUT_DIR / name).write_bytes(audio)
        spent += len(text)
        if i % 50 == 0 or i == len(todo):
            print(f"  {i}/{len(todo)}")
            write_index()
    index = write_index()
    print(f"index has {len(index)} of {len(texts)} lines; now run: python3 scripts/build_voice.py")


if __name__ == "__main__":
    main()
