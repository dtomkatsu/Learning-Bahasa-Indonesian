#!/usr/bin/env python3
"""
Clean Soniox-style transcript exports.

Format expected (repeating blocks):
    [MM:SS] Speaker N:
    [Language] "text"

ASR models (Soniox included) sometimes get stuck in a loop on quiet/noisy
audio and emit the same short phrase hundreds of times in a row (e.g.
"I'm sorry." / "Uh, quiet."). This collapses those runs into a single
marker line while preserving any genuine dialogue that appears in between,
and reports the real speaking-time span it covers.

Usage:
    python3 clean_transcript.py <input.txt> <output.txt>
"""
import re
import sys

ENTRY_RE = re.compile(
    r"\[(\d{1,2}:\d{2}(?::\d{2})?)\]\s*(Speaker \d+):\s*\n\[(\w+)\]\s*\"(.*)\"",
    re.MULTILINE,
)

# Stock filler phrases ASR models loop on when audio is quiet/noisy.
# Extend this set if a future recording loops on something else.
LOOP_CLAUSES = {"im sorry", "thank you", "quiet"}

WINDOW = 6            # look at runs within this many consecutive entries
RUN_THRESHOLD = 4      # collapse when >= this many of the last WINDOW are loop-dominated


def normalize(text):
    return re.sub(r"[^\w\s]", "", text.lower()).strip()


def normalize_clause(s):
    s = s.lower()
    s = re.sub(r"[^\w\s]", "", s)
    s = re.sub(r"\buh\b", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def split_sentences(text):
    return [s for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def classify(entry):
    """Return (is_loop_dominated, salvaged_genuine_text_or_None)."""
    sentences = split_sentences(entry["text"])
    if not sentences:
        return False, None
    norm = [normalize_clause(s) for s in sentences]
    loop_flags = [n in LOOP_CLAUSES or n == "" for n in norm]
    loop_count = sum(loop_flags)
    genuine = [s for s, is_loop in zip(sentences, loop_flags) if not is_loop]
    dominated = loop_count > 0 and (loop_count / len(sentences)) >= 0.5
    salvage = " ".join(genuine).strip() if (dominated and genuine) else None
    return dominated, salvage


def parse(raw):
    entries = []
    for m in ENTRY_RE.finditer(raw):
        ts, speaker, lang, text = m.groups()
        entries.append({"ts": ts, "speaker": speaker, "lang": lang, "text": text.strip()})
    return entries


def clean(entries):
    flags = []
    for e in entries:
        dominated, salvage = classify(e)
        flags.append((dominated, salvage))

    out = []
    i = 0
    n = len(entries)
    removed_total = 0
    while i < n:
        window_flags = [flags[k][0] for k in range(i, min(i + WINDOW, n))]
        matches = sum(window_flags)
        if matches >= RUN_THRESHOLD:
            j = i
            last_match = i
            while j < n:
                if flags[j][0]:
                    last_match = j
                    j += 1
                elif j - last_match <= 2:
                    j += 1
                else:
                    break
            run_entries = entries[i:j]
            run_flags = flags[i:j]
            genuine_entries = []
            for e, (dominated, salvage) in zip(run_entries, run_flags):
                if not dominated:
                    genuine_entries.append(e)
                elif salvage:
                    genuine_entries.append({**e, "text": salvage})
            removed_total += len(run_entries) - len(genuine_entries)
            out.append({
                "marker": True,
                "start": run_entries[0]["ts"],
                "end": run_entries[-1]["ts"],
                "count": len(run_entries) - len(genuine_entries),
            })
            out.extend(genuine_entries)
            i = j
        else:
            out.append(entries[i])
            i += 1
    return out, removed_total


def render(cleaned):
    lines = []
    for e in cleaned:
        if e.get("marker"):
            lines.append(
                f"[{e['start']}–{e['end']}] (ASR artifact: {e['count']} repeated/garbled lines removed — likely quiet/noisy audio)"
            )
            lines.append("")
        else:
            lines.append(f"[{e['ts']}] {e['speaker']}:")
            lines.append(f"[{e['lang']}] \"{e['text']}\"")
            lines.append("")
    return "\n".join(lines)


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    src, dst = sys.argv[1], sys.argv[2]
    with open(src, encoding="utf-8") as f:
        raw = f.read()
    entries = parse(raw)
    cleaned, removed = clean(entries)
    with open(dst, "w", encoding="utf-8") as f:
        f.write(render(cleaned))
    print(f"parsed {len(entries)} entries, removed {removed} loop/garbled lines")
    print(f"wrote {dst}")


if __name__ == "__main__":
    main()
