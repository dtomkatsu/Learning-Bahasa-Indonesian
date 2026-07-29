#!/usr/bin/env python3
"""
Import a *translated* Soniox export — one where each utterance is followed by
its machine translation:

    [00:00] Speaker 1:
    [Indonesian] "Mungkin banjir nih."
    [English] "Maybe it's a flood."

That differs from an untranslated export (Conversation 1), where every block
holds exactly one line and an [English] block means somebody actually spoke
English. Running the normal pipeline on a translated export would silently
throw the translations away — the shared ENTRY_RE only ever matches the first
line of a block — so this script splits them out first.

It produces the three files the rest of the pipeline expects:

    transcripts/<name>.raw.txt            source utterances only, one per block
    transcripts/<name>.clean.txt          the above with ASR loops collapsed
    transcripts/<name>.translations.json  index -> English, for Indonesian lines

Translations are keyed by position in the *cleaned* transcript, and are matched
back onto it by (timestamp, speaker, text) after cleaning, so entries dropped
as ASR artifacts can't shift the mapping.

Only Indonesian utterances get a translation entry: the gloss in the player and
the Sentence/Listening quiz modes exist to explain Indonesian, and a translated
export also "translates" English into Indonesian, which we don't want.

Usage:
    python3 import_soniox_translated.py <soniox-export.txt> <name>
    # e.g.  python3 import_soniox_translated.py ~/Downloads/Recording2.txt conversation-2
"""
import json
import re
import sys
from pathlib import Path

from clean_transcript import clean, parse, render

ROOT = Path(__file__).resolve().parent.parent
TRANSCRIPTS = ROOT / "transcripts"

BLOCK_RE = re.compile(
    r"\[(\d{1,2}:\d{2}(?::\d{2})?)\]\s*(Speaker \d+):\s*\n((?:\[\w+\]\s*\"[^\n]*\"\s*\n?)+)"
)
LINE_RE = re.compile(r"\[(\w+)\]\s*\"([^\n]*)\"")


def split_export(raw):
    """-> (blocks, source_only_text). Each block is
    {ts, speaker, lang, text, translation}."""
    blocks = []
    for m in BLOCK_RE.finditer(raw):
        ts, speaker, body = m.groups()
        lines = LINE_RE.findall(body)
        if not lines:
            continue
        lang, text = lines[0]
        # Anything after the utterance is Soniox's translation of it. The tag on
        # that line is unreliable (it sometimes repeats the source language), so
        # position is what identifies it, not the label.
        translation = lines[1][1].strip() if len(lines) > 1 else None
        blocks.append({
            "ts": ts,
            "speaker": speaker,
            "lang": lang,
            "text": text.strip(),
            "translation": translation,
        })

    rendered = []
    for b in blocks:
        rendered.append(f"[{b['ts']}] {b['speaker']}:")
        rendered.append(f"[{b['lang']}] \"{b['text']}\"")
        rendered.append("")
    return blocks, "\n".join(rendered)


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    src, name = Path(sys.argv[1]).expanduser(), sys.argv[2]
    raw_export = src.read_text(encoding="utf-8")

    blocks, source_only = split_export(raw_export)
    langs = {}
    for b in blocks:
        langs[b["lang"]] = langs.get(b["lang"], 0) + 1
    translated = sum(1 for b in blocks if b["translation"])
    print(f"parsed {len(blocks)} blocks — " + ", ".join(f"{k} {v}" for k, v in sorted(langs.items())))
    print(f"  {translated} carry a translation line")

    raw_path = TRANSCRIPTS / f"{name}.raw.txt"
    raw_path.write_text(source_only, encoding="utf-8")
    print(f"wrote {raw_path.relative_to(ROOT)}")

    entries = parse(source_only)
    cleaned, removed = clean(entries)
    clean_path = TRANSCRIPTS / f"{name}.clean.txt"
    clean_path.write_text(render(cleaned), encoding="utf-8")
    kept = [e for e in cleaned if not e.get("marker")]
    print(f"wrote {clean_path.relative_to(ROOT)} — {len(kept)} entries, "
          f"{removed} collapsed as ASR artifacts")

    # Match translations back on by content, so anything the cleaner dropped
    # cannot shift the index mapping.
    by_key = {}
    for b in blocks:
        if b["lang"] == "Indonesian" and b["translation"]:
            by_key[(b["ts"], b["speaker"], b["text"])] = b["translation"]

    translations, missing = {}, 0
    for i, e in enumerate(kept):
        if e["lang"] != "Indonesian":
            continue
        hit = by_key.get((e["ts"], e["speaker"], e["text"]))
        if hit:
            translations[str(i)] = hit
        else:
            missing += 1

    trans_path = TRANSCRIPTS / f"{name}.translations.json"
    trans_path.write_text(json.dumps(translations, ensure_ascii=False, indent=1), encoding="utf-8")
    idn = sum(1 for e in kept if e["lang"] == "Indonesian")
    print(f"wrote {trans_path.relative_to(ROOT)} — {len(translations)}/{idn} Indonesian lines "
          f"translated ({missing} without)")


if __name__ == "__main__":
    main()
