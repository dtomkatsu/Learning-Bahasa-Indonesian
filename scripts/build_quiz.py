#!/usr/bin/env python3
"""
Build quiz.html — comprehension exercises generated from real transcript
lines, with inline audio playback of the source line. Six modes:

- Word (cloze/recall): cross-references every vocab/*.tsv term against each
  conversation's Indonesian-language lines. A term that appears inside a
  longer sentence becomes a cloze card (blank the term, guess it from
  context); a term that IS basically the whole line becomes a "recall" card
  (listen, then reveal). Terms with no match in any transcript are skipped.
- Fill the blank: the same idea over each card's *written* example sentence
  rather than a transcript line, and with a typed answer instead of a
  self-rated reveal. Word mode can only reach the ~400 terms the family
  happened to say; this reaches the whole deck. No audio from the recording,
  by definition — these sentences were written for the deck — so the play
  button is speech synthesis only.
- Catch it: a real clip plays and you pick which of four similar-sounding
  words was in it, with immediate feedback. Built only from words at least
  two different family members say, so the same word is heard out of more
  than one mouth — the High Variability Phonetic Training protocol, which
  is the best-evidenced technique in the pronunciation literature and the
  reason this drill uses real speakers rather than synthesis.
- Minimal pairs: forced-choice discrimination between two real words that
  differ by exactly one documented or near-documented English->Indonesian
  trouble spot (schwa vs full vowel, voiced/voiceless stops, the final -k
  glottal stop, plus general vowel/consonant contrasts). Same HVPT protocol
  as Catch it, but isolated single words from scripts/fetch_lingualibre.py's
  real volunteer recordings rather than a whole transcript line, and scoped
  to a specific phonetic axis rather than general word recognition. See
  build_pair_items() for how the item pool and audio are chosen.
- Sentence: every Indonesian line with a translation and at least
  MIN_SENTENCE_WORDS words becomes a whole-sentence comprehension check —
  read/listen to the real line, then reveal the translation and self-rate.
  Tests whether you followed the whole thought, not just one word in it.

For each conversation (matched by transcripts/<name>.clean.txt +
audio/<name>.<ext> + an optional transcripts/<name>.translations.json).

Progress persists in the browser via localStorage using real spaced
repetition — FSRS-5 (see scripts/_srs_js.py), the algorithm Anki itself
recommends as its default. Rating is the familiar 4-button Again/Hard/
Good/Easy with an interval preview on each, and only cards that are
actually due get shown. Word and sentence modes are scheduled
independently (item ids are prefixed by kind so they never collide in
the one store).

Usage:
    python3 build_quiz.py
"""
import csv
import json
import re
from html import escape as html_escape
from pathlib import Path

from _srs_js import SRS_JS
from _sync_js import SYNC_JS
from _tts_js import TTS_JS
from _boost_js import BOOST_JS
from _rhythm_tip import RHYTHM_TIP_TEXT
from _mobile_ui import TIPS_CSS, TIPS_JS, STICKY_RATE_CSS, OFF_FILTER_CSS
from build_flashcards import load_tts_index, load_ll_index
from _vocab_text import bounded, find_term
from _pwa_meta import PWA_META_TAGS, PWA_SW_JS

ROOT = Path(__file__).resolve().parent.parent
VOCAB_DIR = ROOT / "vocab"
TRANSCRIPTS_DIR = ROOT / "transcripts"
AUDIO_DIR = ROOT / "audio"
OUT = ROOT / "quiz.html"

ENTRY_RE = re.compile(
    r"\[(\d{1,2}:\d{2}(?::\d{2})?)\]\s*(Speaker \d+):\s*\n\[(\w+)\]\s*\"(.*)\"",
    re.MULTILINE,
)

SKIP_TAGS = {"codeswitch"}

AUDIO_EXTS = [".m4a", ".mp3", ".wav", ".mp4"]

MIN_SENTENCE_WORDS = 4
MIN_CLIP_SECONDS = 2


def clamp_next_sec(sec, next_sec, max_dur):
    """Stop point for 'play just this line': at least MIN_CLIP_SECONDS long
    (many consecutive transcript lines share the same rounded timestamp, or
    sit under a second apart, which would otherwise produce an inaudible
    zero-duration clip), capped at max_dur so long silences don't play out."""
    return min(max(next_sec, sec + MIN_CLIP_SECONDS), sec + max_dur)


def ts_to_seconds(ts):
    parts = [int(p) for p in ts.split(":")]
    if len(parts) == 2:
        m, s = parts
        return m * 60 + s
    h, m, s = parts
    return h * 3600 + m * 60 + s


def parse_transcript(raw):
    entries = []
    for m in ENTRY_RE.finditer(raw):
        ts, speaker, lang, text = m.groups()
        entries.append({
            "ts": ts,
            "sec": ts_to_seconds(ts),
            "speaker": speaker,
            "lang": lang,
            "text": text.strip(),
        })
    return entries


def find_audio(name):
    for ext in AUDIO_EXTS:
        p = AUDIO_DIR / f"{name}{ext}"
        if p.exists():
            return f"audio/{name}{ext}"
    return None


def load_conversations():
    convos = []
    for clean in sorted(TRANSCRIPTS_DIR.glob("*.clean.txt")):
        name = clean.name[: -len(".clean.txt")]
        audio = find_audio(name)
        if not audio:
            continue
        entries = parse_transcript(clean.read_text(encoding="utf-8"))
        trans_path = TRANSCRIPTS_DIR / f"{name}.translations.json"
        translations = {}
        if trans_path.exists():
            translations = json.loads(trans_path.read_text(encoding="utf-8"))
        for i, e in enumerate(entries):
            if e["lang"] == "Indonesian":
                e["en"] = translations.get(str(i))
        convos.append({"name": name, "audio": audio, "entries": entries, "label": name.replace("-", " ").title()})
    return convos


def parse_tags(raw):
    """Tag column is a comma-separated list ("emotion,adjective"); a plain
    single tag is just the one-element case."""
    tags = [t.strip() for t in raw.split(",") if t.strip()]
    return tags or ["untagged"]


def load_vocab():
    rows = []
    seen = set()
    for tsv in sorted(VOCAB_DIR.glob("*.tsv")):
        with open(tsv, encoding="utf-8") as f:
            for row in csv.reader(f, delimiter="\t"):
                if len(row) < 3:
                    continue
                front, back, tags = row[0].strip(), row[1].strip(), parse_tags(row[2])
                if not front or front in seen or any(t in SKIP_TAGS for t in tags):
                    continue
                seen.add(front)
                rows.append({
                    "front": front, "back": back, "tags": tags, "deck": tsv.stem,
                    "example": row[3].strip() if len(row) > 3 else "",
                    "example_en": row[4].strip() if len(row) > 4 else "",
                })
    return rows


def build_blank_items(vocab, tts=None):
    """Fill-the-blank over the written example sentences, one item per card.

    Word mode can only ever cover terms the family happened to say — 407 of
    997. Every card has a written example sentence though, so blanking the
    term out of *that* covers the whole deck, including the reference decks
    that have no transcript behind them at all.

    The answer is the surface form actually in the sentence, not the card's
    dictionary form: for "tangkap" the sentence says *menangkap*, and asking
    for the affixed form is the harder and more useful exercise. The page
    accepts either (see the `accepts` list) and points out the difference
    when they don't match, because typing the root is a near miss worth
    naming rather than an error.

    Skipped: cards with no example, and the handful of fronts like
    "sama … dengan …" that span a gap find_term can't point at — there is no
    single span to blank, so there is no item to build.
    """
    tts = tts if tts is not None else load_tts_index()
    items = []
    for v in vocab:
        sentence = v["example"]
        if not sentence:
            continue
        span = find_term(v["front"], sentence)
        if span is None:
            continue
        a, b = span
        surface = sentence[a:b]
        # A one-word sentence blanked out leaves nothing to reason from.
        if len(sentence.split()) < 3:
            continue
        accepts = [surface]
        if surface.lower() != v["front"].lower():
            accepts.append(v["front"])
        items.append({
            "id": f"blank::{v['front']}",
            "kind": "blank",
            "term": v["front"],
            "answer": surface,
            "accepts": accepts,
            "hint": v["back"],
            "tags": v["tags"],
            "cloze": sentence[:a] + "_____" + sentence[b:],
            "sentenceHtml": (html_escape(sentence[:a]) + "<b>" + html_escape(surface)
                             + "</b>" + html_escape(sentence[b:])),
            "sentence": sentence,
            "translation": v["example_en"],
            "source": v["deck"].replace("-", " "),
        })
        if sentence in tts:
            items[-1]["sentenceSrc"] = f"audio/tts/{tts[sentence]}"
    return items


def _edit_distance(a, b):
    """Plain Levenshtein — used only to rank how confusable two words look."""
    if a == b:
        return 0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _confusable(target, pool, line_text, n=3):
    """The n words most likely to be misheard *as* the target.

    Ranked by edit distance, tie-broken by length similarity, because the
    point of the drill is discriminating sounds rather than recognising
    vocabulary — "tahu" against "tahun" and "tuju" is phonetic training,
    "tahu" against "kulkas" is a free point.

    Anything that also occurs in the very line being played is excluded, or
    the trial would have two defensible answers and mark one of them wrong.
    """
    tl = target.lower()
    ranked = []
    for w in pool:
        wl = w.lower()
        if wl == tl or " " in w:
            continue
        if bounded(w).search(line_text):
            continue
        d = _edit_distance(tl, wl)
        if d == 0 or d > max(2, len(tl) // 2):
            continue
        ranked.append((d, abs(len(wl) - len(tl)), w))
    ranked.sort(key=lambda r: (r[0], r[1], r[2]))
    return [w for _, _, w in ranked[:n]]


def build_hear_items(vocab, convos, per_term=2):
    """Catch-the-word: a real clip plays, you pick which word was in it.

    This is the one drill in the project with High Variability Phonetic
    Training behind it (see notes/hvpt-elevenlabs-build.md). HVPT's evidenced
    effect comes from training across *several real talkers* so the learner
    abstracts the sound away from any one voice — which is why this is built
    only from the family's own audio and not from synthesised voices: the one
    study that tested TTS as the variability source found no multi-talker
    benefit.

    So an item is only generated for a term at least two different people
    actually say, and the clips kept for that term are deliberately spread
    across those speakers. Long lines are skipped — the task is catching one
    word, and a 25-word ramble tests patience instead.

    Line-level timestamps are all the transcripts have, so the trial plays a
    whole line rather than an isolated token. That makes it identification in
    running speech, which is closer to the real target skill than isolated
    tokens would be anyway.
    """
    fronts = [v["front"] for v in vocab]
    by_term = {}
    for v in vocab:
        pattern = bounded(v["front"])
        hits = []
        for convo in convos:
            entries = convo["entries"]
            for i, e in enumerate(entries):
                if e["lang"] != "Indonesian" or not e.get("en"):
                    continue
                words = e["text"].split()
                if not (3 <= len(words) <= 12):
                    continue
                m = pattern.search(e["text"])
                if not m:
                    continue
                nxt = entries[i + 1]["sec"] if i + 1 < len(entries) else e["sec"] + 6
                hits.append({
                    "convo": convo, "i": i, "e": e, "m": m,
                    "speaker": f"{convo['name']}::{e['speaker']}",
                    "nextSec": clamp_next_sec(e["sec"], nxt, 8),
                })
        speakers = {h["speaker"] for h in hits}
        if len(speakers) >= 2:
            by_term[v["front"]] = (v, hits)

    items = []
    for front, (v, hits) in by_term.items():
        # One clip per speaker before a second from anyone: the whole point is
        # hearing the same word out of different mouths.
        chosen, seen = [], set()
        for h in sorted(hits, key=lambda h: h["speaker"]):
            if h["speaker"] not in seen:
                seen.add(h["speaker"])
                chosen.append(h)
            if len(chosen) == per_term:
                break
        for h in chosen:
            e, m, convo = h["e"], h["m"], h["convo"]
            distractors = _confusable(front, fronts, e["text"])
            if len(distractors) < 2:
                continue          # nothing confusable enough to make it a real choice
            items.append({
                "id": f"hear::{convo['name']}::{h['i']}::{front}",
                "lineId": f"{convo['name']}::{h['i']}",
                "kind": "hear",
                "answer": front,
                "options": sorted([front] + distractors),
                "hint": v["back"],
                "tags": v["tags"],
                "sentence": e["text"],
                "sentenceHtml": (html_escape(e["text"][: m.start()])
                                 + "<b>" + html_escape(e["text"][m.start(): m.end()]) + "</b>"
                                 + html_escape(e["text"][m.end():])),
                "translation": e.get("en"),
                "sec": e["sec"],
                "nextSec": h["nextSec"],
                "audio": convo["audio"],
                "source": convo["label"],
            })
    return items


def _classify_pair(a, b):
    """What one-letter substitution separates two same-length words, if any.

    Same-length-only is deliberate: a substitution isolates one phonetic
    difference cleanly, where an insertion/deletion (mata/matang) changes
    syllable count too and confounds the thing being tested. Labelled with
    whether notes/pronunciation-training-scope.md §3 documents this specific
    contrast for English->Indonesian (pepet/taling, stop voicing, final -k)
    versus a general vowel/consonant contrast with no specific citation —
    same "don't oversell an inferred finding" discipline as SAY_TIPS.
    """
    if len(a) != len(b):
        return None
    diff = [i for i in range(len(a)) if a[i] != b[i]]
    if len(diff) != 1:
        return None
    i = diff[0]
    s = frozenset((a[i], b[i]))
    if s in ({"e", "a"}, {"e", "i"}, {"e", "u"}):
        return ("pepet/taling — schwa vs. full vowel", True)
    if s in ({"p", "b"}, {"t", "d"}, {"k", "g"}):
        return ("voiced vs. voiceless stop", True)
    if i == len(a) - 1 and "k" in s:
        return ("final -k glottal stop", True)
    if s <= set("aiueo"):
        return ("vowel contrast", False)
    # Deliberately no general consonant-swap catch-all: an arbitrary single-
    # letter substitution (ada/aja, agak/anak) isn't a documented or even a
    # plausible English-L1 confusion just because it's one edit away — it's
    # noise that would dilute the pool with pairs nobody actually mishears.
    # Only the vowel-identity case above is kept as "general" without a
    # specific citation; every consonant contrast in the item pool traces to
    # a named finding in notes/pronunciation-training-scope.md §3.
    return None


def build_pair_items(vocab, ll_index):
    """Minimal-pair discrimination from real Lingua Libre recordings.

    HVPT's evidenced effect is training a phonetic *contrast* across real
    talkers, same as Catch it — the difference here is the contrast is
    chosen deliberately (one substituted sound) rather than "these two
    words happen to sound similar", and the audio is a clean isolated word
    rather than a whole transcript line, so nothing except the target sound
    varies within a single clip.

    Both halves of a pair must have a real volunteer recording — this never
    falls back to a generated or device voice, same reasoning as Catch it:
    the one study that tested synthetic-voice variability as an HVPT source
    found no multi-talker benefit (notes/hvpt-elevenlabs-build.md).

    Voice-confound note, not hidden from future maintainers: a single trial
    is one clip judged against two options, so within that trial there is no
    "compare two voices" leak. Across a pair's full trial set the risk is a
    learner keying on voice identity rather than the sound if one word's
    speakers and the other's never overlap — checked directly (2026-08-03):
    16 of 34 voiced pairs share at least one speaker who said both words, the
    strongest trials for this reason. The rest still draw from each word's
    own 1-3 real speakers rather than a single fixed voice, which is a
    partial mitigation, not a fix — flagged here rather than asserted clean.
    """
    fronts = {v["front"].split(" / ")[0].strip().lower(): v for v in vocab}
    words = sorted(w for w in fronts if w.isalpha() and len(w) >= 3 and w in ll_index)

    def clips(word):
        e = ll_index[word]
        out = [{"speaker": e["author"], "file": e["file"]}]
        out += [{"speaker": a["author"], "file": a["file"]} for a in e.get("alts", [])]
        return out

    items = []
    for i, a in enumerate(words):
        for b in words[i + 1:]:
            result = _classify_pair(a, b)
            if not result:
                continue
            contrast, documented = result
            clips_a, clips_b = clips(a), clips(b)
            shared = {c["speaker"] for c in clips_a} & {c["speaker"] for c in clips_b}
            trials = (
                [{"answer": a, "src": f"audio/ll/{c['file']}", "speaker": c["speaker"]}
                 for c in clips_a]
                + [{"answer": b, "src": f"audio/ll/{c['file']}", "speaker": c["speaker"]}
                   for c in clips_b]
            )
            va, vb = fronts[a], fronts[b]
            items.append({
                "id": f"pairs::{a}::{b}",
                "kind": "pairs",
                "options": [a, b],
                "hints": {a: va["back"], b: vb["back"]},
                "contrast": contrast,
                "documented": documented,
                "sharedSpeaker": bool(shared),
                "tags": sorted(set(va["tags"]) | set(vb["tags"])),
                "trials": trials,
            })
    return items


def build_quiz_items(vocab, convos):
    items = []
    for v in vocab:
        pattern = re.compile(r"(?<!\w)" + re.escape(v["front"]) + r"(?!\w)", re.IGNORECASE)
        found = None
        for convo in convos:
            entries = convo["entries"]
            for i, e in enumerate(entries):
                if e["lang"] != "Indonesian":
                    continue
                m = pattern.search(e["text"])
                if not m:
                    continue
                found = (convo, i, e, m)
                break
            if found:
                break
        if not found:
            continue
        convo, i, e, m = found
        entries = convo["entries"]
        next_sec = entries[i + 1]["sec"] if i + 1 < len(entries) else e["sec"] + 6
        term_words = len(v["front"].split())
        sentence_words = len(e["text"].split())
        if sentence_words > term_words:
            cloze_sentence = e["text"][: m.start()] + "_____" + e["text"][m.end():]
            mode = "cloze"
        else:
            cloze_sentence = None
            mode = "recall"
        sentence_html = (
            html_escape(e["text"][: m.start()])
            + "<b>" + html_escape(e["text"][m.start(): m.end()]) + "</b>"
            + html_escape(e["text"][m.end():])
        )
        items.append({
            "id": f"word::{convo['name']}::{i}::{v['front']}",
            "lineId": f"{convo['name']}::{i}",
            "kind": "word",
            "term": v["front"],
            "hint": v["back"],
            "tags": v["tags"],
            "mode": mode,
            "sentence": e["text"],
            "sentenceHtml": sentence_html,
            "cloze": cloze_sentence,
            "translation": e.get("en"),
            "sec": e["sec"],
            "nextSec": clamp_next_sec(e["sec"], next_sec, 8),
            "audio": convo["audio"],
            "source": convo["label"],
        })
    return items


def build_sentence_items(convos, min_words=MIN_SENTENCE_WORDS):
    """Whole-sentence comprehension items: every real Indonesian line with a
    translation, tests whether the whole thought was understood, not just
    one word in it. Filtered to a minimum length so trivial one-word
    utterances ("Iya.", "Hah?") don't dilute the exercise."""
    items = []
    for convo in convos:
        entries = convo["entries"]
        for i, e in enumerate(entries):
            if e["lang"] != "Indonesian":
                continue
            en = e.get("en")
            if not en or len(e["text"].split()) < min_words:
                continue
            next_sec = entries[i + 1]["sec"] if i + 1 < len(entries) else e["sec"] + 6
            items.append({
                "id": f"sentence::{convo['name']}::{i}",
                "lineId": f"{convo['name']}::{i}",
                "kind": "sentence",
                "tags": [convo["label"]],
                "sentence": e["text"],
                "sentenceHtml": html_escape(e["text"]),
                "translation": en,
                "sec": e["sec"],
                "nextSec": clamp_next_sec(e["sec"], next_sec, 14),
                "audio": convo["audio"],
                "source": convo["label"],
            })
    return items


def build_listening_items(sentence_items):
    """Audio-first comprehension over the same source lines as sentence mode:
    the prompt is the CLIP with the text hidden — understand by ear, then
    reveal transcript + translation. Separate FSRS ids (listening::) because
    recognizing a line by ear is a different skill, and a different memory,
    than reading it."""
    return [
        {**s, "id": s["id"].replace("sentence::", "listening::", 1), "kind": "listening"}
        for s in sentence_items
    ]


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
__PWA_META__
<title>Quiz — Learning Bahasa Indonesian</title>
<style>
  :root { color-scheme: light dark; --bg:#fff; --fg:#1a1a1a; --muted:#6b7280; --line:#e5e7eb;
    --accent:#2563eb; --card:#f9fafb; --blank:#f59e0b; --bad:#dc2626;
    --again:#dc2626; --hard:#d97706; --good:#16a34a; --easy:#2563eb; }
  @media (prefers-color-scheme: dark) {
    :root { --bg:#111318; --fg:#e7e9ee; --muted:#9aa1ac; --line:#2a2e37; --accent:#5b9dff;
      --card:#1a1d24; --blank:#fbbf24; --bad:#f87171;
      --again:#f87171; --hard:#fbbf24; --good:#4ade80; --easy:#7cb0ff; }
  }
  * { box-sizing:border-box; }
  html, body { margin:0; background:var(--bg); color:var(--fg);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }
  .wrap { max-width:600px; margin:0 auto; padding:28px 20px 60px; }
  .top { display:flex; justify-content:space-between; align-items:baseline; gap:10px; flex-wrap:wrap; margin-bottom:6px; }
  h1 { font-size:1.15rem; margin:0; }
  a.back { color:var(--muted); font-size:0.8rem; text-decoration:none; }
  .stats { color:var(--muted); font-size:0.8rem; margin-bottom:16px; }
  select { font-size:0.8rem; padding:5px 7px; border-radius:6px; border:1px solid var(--line);
    background:var(--bg); color:var(--fg); }
  .modes { display:flex; gap:6px; margin-bottom:10px; }
  button.modeBtn { font-size:0.82rem; padding:6px 12px; border-radius:7px; border:1px solid var(--line);
    background:var(--bg); color:var(--fg); cursor:pointer; }
  button.modeBtn.active { background:var(--accent); color:#fff; border-color:var(--accent); }
  .modeHint { color:var(--muted); font-size:0.78rem; margin:-2px 0 14px; }
  #card { border:1px solid var(--line); border-radius:14px; background:var(--card);
    min-height:200px; padding:24px 22px; margin:18px 0; }
  .source { font-size:0.72rem; color:var(--muted); margin-bottom:10px; }
  .prompt { font-size:1.15rem; line-height:1.5; margin-bottom:6px; }
  .prompt .blank { color:var(--blank); font-weight:700; letter-spacing:1px; }
  .hint { color:var(--muted); font-size:0.82rem; margin-bottom:16px; }
__TIPS_CSS__
__OFF_FILTER_CSS__
  .playrow { margin-bottom:14px; }
  button.play { font-size:0.85rem; padding:8px 14px; border-radius:8px; border:1px solid var(--accent);
    background:transparent; color:var(--accent); cursor:pointer; }
  button.play:hover { background:var(--accent); color:#fff; }
  /* Fill-the-blank: typed answer, so the verdict is objective rather than
     self-assessed. The input sits where the blank is being asked about. */
  .answerRow { display:flex; gap:8px; margin-bottom:12px; }
  input.answerBox { flex:1; min-width:0; font-size:1rem; border-radius:8px;
    border:1px solid var(--line); background:var(--bg); color:var(--fg); padding:9px 11px; }
  input.answerBox:focus { outline:none; border-color:var(--accent); }
  input.answerBox:disabled { opacity:0.7; }
  button.checkBtn { font-size:0.85rem; padding:8px 14px; border-radius:8px;
    border:1px solid var(--accent); background:var(--accent); color:#fff; cursor:pointer; }
  button.checkBtn:disabled { background:transparent; border-color:var(--line);
    color:var(--muted); cursor:default; }
  .verdict { font-size:0.9rem; margin-bottom:12px; font-weight:600; }
  .verdict.right { color:var(--good); }
  .verdict.wrong { color:var(--again); }
  .verdict .sub { display:block; font-weight:400; font-size:0.8rem;
    color:var(--muted); margin-top:3px; }
  /* Catch-it: forced choice, big enough targets to answer by ear on a phone
     without hunting. Correct/incorrect colouring stays on after the answer so
     the contrast you just failed is still on screen while you re-listen. */
  .opts { display:grid; grid-template-columns:repeat(2, 1fr); gap:8px; margin-bottom:12px; }
  button.opt { font-size:0.95rem; padding:11px 8px; border-radius:10px;
    border:1px solid var(--line); background:var(--bg); color:var(--fg); cursor:pointer; }
  button.opt:hover:not(:disabled) { border-color:var(--accent); }
  button.opt:disabled { cursor:default; }
  button.opt.right { border-color:var(--good); color:var(--good); font-weight:600; }
  button.opt.wrong { border-color:var(--again); color:var(--again); text-decoration:line-through; }
  button.opt.dim:disabled { opacity:0.45; }
  .reveal { display:none; border-top:1px dashed var(--line); margin-top:14px; padding-top:14px; }
  .reveal.shown { display:block; }
  .reveal .id { font-size:1.05rem; margin-bottom:4px; }
  .reveal .id b { color:var(--accent); }
  .reveal .en { color:var(--muted); font-size:0.9rem; }
  button.revealBtn { font-size:0.85rem; padding:8px 14px; border-radius:8px; border:1px solid var(--line);
    background:var(--bg); color:var(--fg); cursor:pointer; }
  button.flagLineBtn { font-size:0.78rem; padding:8px 14px; border-radius:8px; border:1px solid var(--line);
    background:var(--bg); color:var(--muted); cursor:pointer; margin-left:8px; }
  button.flagLineBtn:hover { border-color:var(--bad); color:var(--bad); }
  .rate { display:flex; gap:8px; margin-top:14px; }
__STICKY_RATE_CSS__
  .rate[hidden] { display:none; }
  button.rate-btn { flex:1; padding:10px 4px; border-radius:10px; border:1px solid var(--line);
    background:var(--card); color:var(--fg); font-size:0.85rem; cursor:pointer; display:flex;
    flex-direction:column; align-items:center; gap:2px; }
  button.rate-btn:hover { filter:brightness(1.1); }
  button.rate-btn .prev { font-size:0.7rem; opacity:0.7; }
  button.rate-btn.again { border-color:var(--again); color:var(--again); }
  button.rate-btn.hard { border-color:var(--hard); color:var(--hard); }
  button.rate-btn.good { border-color:var(--good); color:var(--good); }
  button.rate-btn.easy { border-color:var(--easy); color:var(--easy); }
  .tools { display:flex; justify-content:space-between; align-items:center; margin-top:24px; }
  button.plain { font-size:0.78rem; padding:6px 10px; border-radius:6px; border:1px solid var(--line);
    background:var(--bg); color:var(--muted); cursor:pointer; }
  button.plain:disabled { opacity:0.4; cursor:default; }
  button.plain.active { border-color:var(--accent); color:var(--accent); }
  button.plain.danger:hover { border-color:var(--again); color:var(--again); }
  .speedGroup { display:inline-flex; gap:4px; }
  .speedGroup button { padding:6px 8px; }
  .controls { display:flex; flex-wrap:wrap; gap:8px; margin-bottom:14px; }
  .panel { border:1px solid var(--line); border-radius:10px; background:var(--card);
    padding:12px; margin-bottom:16px; }
  .panel[hidden] { display:none; }
  .chips { display:flex; flex-wrap:wrap; gap:6px; }
  button.chip { font-size:0.75rem; padding:5px 10px; border-radius:999px; border:1px solid var(--line);
    background:var(--bg); color:var(--muted); cursor:pointer; }
  button.chip.active { background:var(--accent); border-color:var(--accent); color:#fff; }
  button.chip:hover { border-color:var(--accent); }
  button.chip .n { opacity:0.65; font-size:0.68rem; margin-left:4px; }
  .panelFoot { margin-top:10px; display:flex; justify-content:space-between; align-items:center; gap:8px; }
  .panelFoot .count { color:var(--muted); font-size:0.75rem; }
  .empty { color:var(--muted); font-size:0.9rem; text-align:center; margin-top:40px; }
  .empty .sub { font-size:0.8rem; margin-top:6px; }
  .empty button.plain { margin-top:14px; }
</style>
</head>
<body>
<div class="wrap">
  <div class="top">
    <h1>Quiz</h1>
    <a class="back" href="index.html">&larr; all conversations</a>
  </div>
  <div class="modes">
    <button class="modeBtn active" data-mode="word">Word</button>
    <button class="modeBtn" data-mode="blank">Fill the blank</button>
    <button class="modeBtn" data-mode="hear">Catch it</button>
    <button class="modeBtn" data-mode="pairs">Minimal pairs</button>
    <button class="modeBtn" data-mode="sentence">Sentence</button>
    <button class="modeBtn" data-mode="listening">Listening</button>
  </div>
  <span class="speedGroup" id="speedGroup" title="Speed of generated/volunteer clips — real family audio is unaffected">
    <button class="plain" data-rate="0.75">0.75x</button>
    <button class="plain active" data-rate="0.9">0.9x</button>
    <button class="plain" data-rate="1">1x</button>
    <button class="plain" data-rate="1.25">1.25x</button>
  </span>
  <div class="modeHint" id="modeHint"></div>
  <div class="stats" id="stats"></div>
  <div class="controls">
    <button class="plain" id="filterToggleBtn">Filter</button>
  </div>
  <div class="panel" id="filterPanel" hidden>
    <div class="chips" id="tagChips"></div>
    <div class="panelFoot">
      <span class="count" id="filterCount"></span>
      <button class="plain" id="clearFilterBtn">Clear filters</button>
    </div>
  </div>
  <div class="offFilter" id="offFilter" hidden></div>
  <div id="card"></div>
  <div class="tools">
    <button class="plain" id="undoBtn" disabled>&#8630; Go back</button>
    <button class="plain danger" id="resetBtn">Reset progress</button>
    <button class="plain" id="unflagBtn">Unflag lines (0)</button>
    <span class="stats" id="syncState"></span>
    <span class="stats" id="deckInfo"></span>
  </div>
</div>
<audio id="qaudio" preload="none"></audio>
<script>
__SRS_JS__
__SYNC_JS__
__TIPS_JS__
__TTS_JS__
__BOOST_JS__
const ITEMS = __DATA__;
const RHYTHM_TIP_HTML = '<details class="tip" data-tip="rhythm">'
  + '<summary>Sentence rhythm</summary><div class="tipBody">__RHYTHM_TIP__</div></details>';
const SRS_KEY = 'bahasa:quiz:fsrs:v1';
const LEGACY_KEYS = ['bahasa:quiz:v1', 'bahasa:quiz:srs:v1'];
// FLAG_KEY comes from the shared sync module above.
const audio = document.getElementById('qaudio');
boostAttach(audio);   // family phone audio only — TTS clips are already at studio level

let srs = srsMigrateLegacy(SRS_KEY, LEGACY_KEYS);
let practiceAhead = false;

function setSyncState(s) {
  const el = document.getElementById('syncState');
  if (!syncRemoteConfigured()) { el.textContent = ''; return; }
  el.textContent = s === 'pending' ? 'syncing…' : s === 'err' ? 'sync failed' : 'synced ✓';
}
// Pull any progress made on another device, then refresh what's on screen.
// (Deferred a tick so it runs after the initial render below.)
setTimeout(() => syncRemoteAutoPull(() => {
  srs = srsLoad(SRS_KEY);
  flags = loadFlags();
  updateUnflagCount();
  renderChips();
  applyFilter();
  pickNext();
}, setSyncState), 0);

function loadFlags() {
  try { return JSON.parse(localStorage.getItem(FLAG_KEY)) || {}; } catch (e) { return {}; }
}
function saveFlags(f) { localStorage.setItem(FLAG_KEY, JSON.stringify(f)); }
let flags = loadFlags();
const unflagBtn = document.getElementById('unflagBtn');
function updateUnflagCount() {
  unflagBtn.textContent = `Unflag lines (${Object.keys(flags).length})`;
}

let mode = 'word';
let pool = [];
let current = null;
let revealed = false;
let stopAt = null;

const cardEl = document.getElementById('card');
const chipsEl = document.getElementById('tagChips');
const modeHintEl = document.getElementById('modeHint');

const MODE_HINTS = {
  word: 'One word blanked out of a real sentence — recall it from context.',
  blank: 'Type the missing word into the example sentence. Covers the whole deck, not just words the family happened to say — so no audio from the recording, only synthesis.',
  hear: 'A real clip plays — pick which word was in it. Every word here is one at least two different people in the recordings say, so you hear it out of more than one mouth.',
  pairs: 'A real volunteer says one of two similar words — which one? Each pair differs by exactly one sound, often the specific thing English speakers mishear in Indonesian.',
  sentence: 'A whole real line — read or listen, then reveal the translation and rate yourself on the whole thing, not just one word.',
  listening: 'Ears only: the clip plays with the text hidden. Understand it by ear, then reveal and rate. This is the actual target skill.',
};

function itemsForMode(m) { return ITEMS.filter(d => d.kind === m && !flags[d.lineId]); }

// Same multi-select chip filter as flashcards (several chips = union of those
// categories). Tags are mode-dependent — Word items carry vocab categories,
// Sentence/Listening carry conversations — so the chips rebuild on mode switch
// and any now-invalid selection is dropped.
let activeTags = new Set();

function renderChips() {
  const modeItems = itemsForMode(mode);
  const tags = [...new Set(modeItems.flatMap(d => d.tags))].sort();
  activeTags = new Set([...activeTags].filter(t => tags.includes(t)));
  chipsEl.innerHTML = tags.map(t =>
    `<button class="chip${activeTags.has(t) ? ' active' : ''}" data-tag="${escapeHtml(t)}">` +
    `${escapeHtml(t)}<span class="n">${modeItems.filter(d => d.tags.includes(t)).length}</span></button>`).join('');
  chipsEl.querySelectorAll('.chip').forEach(b => {
    b.addEventListener('click', () => {
      const t = b.dataset.tag;
      if (activeTags.has(t)) activeTags.delete(t); else activeTags.add(t);
      b.classList.toggle('active');
      practiceAhead = false;
      applyFilter();
      pickNext();
    });
  });
}

function applyFilter() {
  srsClearForward();
  const modeItems = itemsForMode(mode);
  pool = activeTags.size
    ? modeItems.filter(d => d.tags.some(t => activeTags.has(t)))
    : modeItems;
  const btn = document.getElementById('filterToggleBtn');
  btn.textContent = activeTags.size ? 'Filter · ' + activeTags.size : 'Filter';
  btn.classList.toggle('active', activeTags.size > 0);
  document.getElementById('filterCount').textContent =
    pool.length + ' of ' + modeItems.length + ' match';
}

document.getElementById('filterToggleBtn').addEventListener('click', () => {
  const el = document.getElementById('filterPanel');
  el.hidden = !el.hidden;
});
document.getElementById('clearFilterBtn').addEventListener('click', () => {
  activeTags.clear();
  practiceAhead = false;
  renderChips();
  applyFilter();
  pickNext();
});

// Split out of the click handler so undo can switch back to whichever mode a
// rating was made in (it stops short of pickNext, since undo picks the card).
function setMode(m) {
  mode = m;
  practiceAhead = false;
  document.querySelectorAll('.modeBtn').forEach(x => x.classList.toggle('active', x.dataset.mode === m));
  modeHintEl.textContent = MODE_HINTS[mode];
  renderChips();
  applyFilter();
}

document.querySelectorAll('.modeBtn').forEach(b => {
  b.addEventListener('click', () => { setMode(b.dataset.mode); pickNext(); });
});

// Speed applies to generated and volunteer clips only (see _tts_js.py) — real
// family recordings (Catch it, Sentence, Listening) play at their own pace.
document.querySelectorAll('#speedGroup button').forEach(b => {
  b.addEventListener('click', () => {
    document.querySelectorAll('#speedGroup button').forEach(x => x.classList.remove('active'));
    b.classList.add('active');
    ttsSetRate(parseFloat(b.dataset.rate));
  });
});

modeHintEl.textContent = MODE_HINTS[mode];
renderChips();
applyFilter();
if (!srsIsTouch() && !srsIsNarrow()) document.getElementById('filterPanel').hidden = false;

function escapeHtml(s) {
  return s.replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
}

function renderEmpty(msg) {
  current = null;
  cardEl.innerHTML = `<div class="empty">${msg}</div>`;
}

function renderAllCaughtUp() {
  current = null;
  const now = Date.now();
  const dues = pool.map(d => (srs[d.id] && srs[d.id].due) || Infinity);
  const nextDue = Math.min(...dues);
  const in24h = pool.filter(d => srs[d.id] && srs[d.id].due > now && srs[d.id].due <= now + 86400000).length;
  cardEl.innerHTML = `<div class="empty">🎉 All caught up!<div class="sub">Next review in ${srsFmtDue(nextDue)}${in24h ? ` · ${in24h} due within 24h` : ''}.</div>` +
    `<button class="plain" id="aheadBtn">Practice ahead anyway</button></div>`;
  document.getElementById('aheadBtn').addEventListener('click', () => { practiceAhead = true; pickNext(); });
}

// Indonesian spelling is regular enough that a typed answer can be graded
// honestly, but not so regular that a stray accent or trailing period should
// count against you. Everything here is about stripping the things that aren't
// the answer.
function normalizeAnswer(s) {
  return (s || '')
    .toLowerCase()
    .replace(/[^a-z0-9\\s-]/g, '')
    .replace(/\\s+/g, ' ')
    .trim();
}

// One-edit distance, capped — enough to tell "typo" from "different word".
function withinOneEdit(a, b) {
  if (Math.abs(a.length - b.length) > 1) return false;
  let i = 0, j = 0, edits = 0;
  while (i < a.length && j < b.length) {
    if (a[i] === b[j]) { i++; j++; continue; }
    if (++edits > 1) return false;
    if (a.length > b.length) i++;
    else if (a.length < b.length) j++;
    else { i++; j++; }
  }
  return edits + (a.length - i) + (b.length - j) <= 1;
}

// Returns how the typed answer relates to what the sentence wanted, so the
// verdict can say something more useful than right/wrong: typing the
// dictionary form when the sentence inflects it is a near miss worth naming.
function gradeAnswer(item, typed) {
  const got = normalizeAnswer(typed);
  if (!got) return { ok: false, kind: 'empty' };
  const wanted = normalizeAnswer(item.answer);
  if (got === wanted) return { ok: true, kind: 'exact' };
  for (const alt of item.accepts || []) {
    if (got === normalizeAnswer(alt)) return { ok: true, kind: 'dictionary' };
  }
  if (got.length >= 4 && withinOneEdit(got, wanted)) return { ok: true, kind: 'typo' };
  return { ok: false, kind: 'wrong' };
}

// Fill-the-blank gets its own renderer because it has a step the other modes
// don't: you commit to an answer before anything is revealed. The rate row
// still appears afterwards — the grader knows whether you were right, but only
// you know whether it was effortless.
function renderBlankCard(promptText, hintLine, revealInner) {
  const canHear = !!ttsVoice || !!current.sentenceSrc;
  cardEl.innerHTML = `
    <div class="source">${escapeHtml(current.source)} · ${escapeHtml(current.tags.join(' · '))}</div>
    <div class="prompt">${promptText}</div>
    ${hintLine}
    <div class="answerRow">
      <input class="answerBox" id="answerBox" type="text" autocomplete="off"
             autocapitalize="off" autocorrect="off" spellcheck="false"
             placeholder="type the missing word">
      <button class="checkBtn" id="checkBtn">Check</button>
    </div>
    <div class="verdict" id="verdict" hidden></div>
    <div class="playrow"><button class="play" id="playBtn"${canHear ? '' : ' disabled'}>&#128266; Hear the sentence</button></div>
    <button class="revealBtn" id="revealBtn">I don't know &mdash; show it</button>
    <div class="reveal" id="revealBox">${revealInner}</div>
    <div class="rate" id="rateRow" hidden>
      <button class="rate-btn again" id="btn1"><span class="lbl">Again</span><span class="prev" id="prev1"></span></button>
      <button class="rate-btn hard" id="btn2"><span class="lbl">Hard</span><span class="prev" id="prev2"></span></button>
      <button class="rate-btn good" id="btn3"><span class="lbl">Good</span><span class="prev" id="prev3"></span></button>
      <button class="rate-btn easy" id="btn4"><span class="lbl">Easy</span><span class="prev" id="prev4"></span></button>
    </div>
  `;
  const box = document.getElementById('answerBox');
  document.getElementById('checkBtn').addEventListener('click', checkAnswer);
  box.addEventListener('keydown', e => {
    if (e.key !== 'Enter') return;
    e.preventDefault();
    if (revealed) rate(3); else checkAnswer();
  });
  // Typing goes to the box, so the global 1/2/3/4 and "p" shortcuts must not
  // also fire while it has focus.
  box.addEventListener('keydown', e => e.stopPropagation());
  document.getElementById('revealBtn').addEventListener('click', () => showBlankAnswer(null));
  document.getElementById('playBtn').addEventListener('click', () => ttsSay(current.sentence, current.sentenceSrc));
  [1, 2, 3, 4].forEach(g => {
    document.getElementById('btn' + g).addEventListener('click', () => rate(g));
  });
  if (!srsIsTouch()) box.focus();
}

function checkAnswer() {
  if (!current || revealed) return;
  showBlankAnswer(gradeAnswer(current, document.getElementById('answerBox').value));
}

// `result` is null when the answer was skipped rather than attempted — the
// sentence still gets revealed, but claiming a verdict would be a lie.
function showBlankAnswer(result) {
  const box = document.getElementById('answerBox');
  const el = document.getElementById('verdict');
  box.disabled = true;
  document.getElementById('checkBtn').disabled = true;
  if (result && result.kind !== 'empty') {
    el.hidden = false;
    el.className = 'verdict ' + (result.ok ? 'right' : 'wrong');
    if (result.kind === 'exact') el.textContent = '✓ Correct.';
    else if (result.kind === 'typo') el.innerHTML = '✓ Close enough — the spelling is ' +
      `<b>${escapeHtml(current.answer)}</b>.`;
    else if (result.kind === 'dictionary') el.innerHTML = '✓ Right word — ' +
      `but in this sentence it takes affixes: <b>${escapeHtml(current.answer)}</b>.` +
      '<span class="sub">Rate yourself on whether you\\'d have produced that form.</span>';
    else el.innerHTML = `✗ The answer was <b>${escapeHtml(current.answer)}</b>.`;
  }
  document.getElementById('revealBtn').hidden = true;
  reveal();
}

// Catch-it. Forced-choice identification with immediate feedback, which is the
// protocol the HVPT literature actually tested — feedback-free discrimination
// shows much weaker effects, so answering has to resolve right away rather
// than waiting for a self-rated reveal.
function renderHearCard() {
  // Reshuffled every showing: fixed positions turn into "the answer is the
  // third button" surprisingly fast.
  const opts = current.options.slice();
  for (let i = opts.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [opts[i], opts[j]] = [opts[j], opts[i]];
  }
  cardEl.innerHTML = `
    <div class="source">${escapeHtml(current.source)} · ${escapeHtml(current.tags.join(' · '))}</div>
    <div class="prompt">🎧 Which word is in this clip?</div>
    <div class="playrow"><button class="play" id="playBtn">&#9654; Play line</button></div>
    <div class="opts" id="opts">
      ${opts.map(o => `<button class="opt" data-opt="${escapeHtml(o)}">${escapeHtml(o)}</button>`).join('')}
    </div>
    <div class="verdict" id="verdict" hidden></div>
    <button class="flagLineBtn" id="flagLineBtn" title="Hide this line everywhere — silent clip or ASR junk">&#128681; Not real content</button>
    <div class="reveal" id="revealBox">
      <div class="id">${current.sentenceHtml}</div>
      <div class="en">${escapeHtml(current.translation || '')}</div>
    </div>
    <div class="rate" id="rateRow" hidden>
      <button class="rate-btn again" id="btn1"><span class="lbl">Again</span><span class="prev" id="prev1"></span></button>
      <button class="rate-btn hard" id="btn2"><span class="lbl">Hard</span><span class="prev" id="prev2"></span></button>
      <button class="rate-btn good" id="btn3"><span class="lbl">Good</span><span class="prev" id="prev3"></span></button>
      <button class="rate-btn easy" id="btn4"><span class="lbl">Easy</span><span class="prev" id="prev4"></span></button>
    </div>
  `;
  document.getElementById('playBtn').addEventListener('click', playLine);
  document.getElementById('flagLineBtn').addEventListener('click', flagCurrentLine);
  cardEl.querySelectorAll('.opt').forEach(b => {
    b.addEventListener('click', () => answerHear(b.dataset.opt));
  });
  [1, 2, 3, 4].forEach(g => {
    document.getElementById('btn' + g).addEventListener('click', () => rate(g));
  });
  updatePlayBtnLabel();
}

function answerHear(picked) {
  if (revealed) return;
  const ok = picked === current.answer;
  cardEl.querySelectorAll('.opt').forEach(b => {
    b.disabled = true;
    const o = b.dataset.opt;
    if (o === current.answer) b.classList.add('right');
    else if (o === picked) b.classList.add('wrong');
    else b.classList.add('dim');
  });
  const el = document.getElementById('verdict');
  el.hidden = false;
  el.className = 'verdict ' + (ok ? 'right' : 'wrong');
  el.innerHTML = ok
    ? `✓ <b>${escapeHtml(current.answer)}</b> — ${escapeHtml(current.hint)}`
    : `✗ It was <b>${escapeHtml(current.answer)}</b> — ${escapeHtml(current.hint)}` +
      '<span class="sub">Play it once more now you know which word to hear.</span>';
  reveal();
}

// Minimal pairs. A random trial (one specific word x speaker recording) is
// drawn fresh every time this pair comes up for review, not fixed at build
// time — so which of the two words is "the answer" and whose voice you hear
// both vary across repeat exposures of the same pair.
let currentTrial = null;

function renderPairsCard() {
  currentTrial = current.trials[Math.floor(Math.random() * current.trials.length)];
  const opts = current.options.slice();
  for (let i = opts.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [opts[i], opts[j]] = [opts[j], opts[i]];
  }
  cardEl.innerHTML = `
    <div class="source">${escapeHtml(current.contrast)}${current.documented ? '' : ' · general practice'}</div>
    <div class="prompt">🎧 Listen for it — which word is this?</div>
    <div class="playrow"><button class="play" id="playBtn">&#9654; Play word</button></div>
    <div class="opts" id="opts">
      ${opts.map(o => `<button class="opt" data-opt="${escapeHtml(o)}">${escapeHtml(o)}</button>`).join('')}
    </div>
    <div class="verdict" id="verdict" hidden></div>
    <div class="reveal" id="revealBox">
      <div class="id">${current.options.map(o =>
        (o === currentTrial.answer ? '<b>' : '') + escapeHtml(o) + ' — ' + escapeHtml(current.hints[o])
        + (o === currentTrial.answer ? '</b>' : '')).join('<br>')}</div>
    </div>
    <div class="rate" id="rateRow" hidden>
      <button class="rate-btn again" id="btn1"><span class="lbl">Again</span><span class="prev" id="prev1"></span></button>
      <button class="rate-btn hard" id="btn2"><span class="lbl">Hard</span><span class="prev" id="prev2"></span></button>
      <button class="rate-btn good" id="btn3"><span class="lbl">Good</span><span class="prev" id="prev3"></span></button>
      <button class="rate-btn easy" id="btn4"><span class="lbl">Easy</span><span class="prev" id="prev4"></span></button>
    </div>
  `;
  document.getElementById('playBtn').addEventListener('click', playPairTrial);
  cardEl.querySelectorAll('.opt').forEach(b => {
    b.addEventListener('click', () => answerPair(b.dataset.opt));
  });
  [1, 2, 3, 4].forEach(g => {
    document.getElementById('btn' + g).addEventListener('click', () => rate(g));
  });
}

function playPairTrial() {
  if (!currentTrial) return;
  ttsStop();
  ttsPlayClip(currentTrial.src);
}

function answerPair(picked) {
  if (revealed) return;
  const ok = picked === currentTrial.answer;
  cardEl.querySelectorAll('.opt').forEach(b => {
    b.disabled = true;
    const o = b.dataset.opt;
    if (o === currentTrial.answer) b.classList.add('right');
    else if (o === picked) b.classList.add('wrong');
    else b.classList.add('dim');
  });
  const el = document.getElementById('verdict');
  el.hidden = false;
  el.className = 'verdict ' + (ok ? 'right' : 'wrong');
  el.innerHTML = ok
    ? `✓ <b>${escapeHtml(currentTrial.answer)}</b> — ${escapeHtml(current.hints[currentTrial.answer])}`
    : `✗ It was <b>${escapeHtml(currentTrial.answer)}</b> — ${escapeHtml(current.hints[currentTrial.answer])}` +
      '<span class="sub">Play it once more now you know which word to hear.</span>';
  reveal();
}

function renderCard() {
  let promptText, hintLine, revealInner;
  if (current.kind === 'hear') { renderHearCard(); return; }
  if (current.kind === 'pairs') { renderPairsCard(); return; }
  if (current.kind === 'blank') {
    promptText = escapeHtml(current.cloze).replace('_____', '<span class="blank">_____</span>');
    hintLine = `<div class="hint">${escapeHtml(current.translation || '')}` +
      `${current.translation ? ' · ' : ''}clue: ${escapeHtml(current.hint)}</div>`;
    revealInner = `
      <div class="id">${current.sentenceHtml}</div>
      <div class="en">${escapeHtml(current.translation || '')}</div>
    `;
    renderBlankCard(promptText, hintLine, revealInner);
    return;
  }
  if (current.kind === 'listening') {
    promptText = srsIsTouch()
      ? '🎧 Listen — no peeking. Tap play and try to catch the whole line.'
      : '🎧 Listen — no peeking. Press play (or "p") and try to catch the whole line.';
    // A standing reminder about Indonesian's rhythm, not per-line content —
    // it's the same for every item, so it gives nothing about this specific
    // line away and doesn't compromise "no peeking".
    hintLine = RHYTHM_TIP_HTML;
    revealInner = `
      <div class="id">${current.sentenceHtml}</div>
      <div class="en">${escapeHtml(current.translation)}</div>
    `;
  } else if (current.kind === 'sentence') {
    promptText = current.sentenceHtml;
    hintLine = RHYTHM_TIP_HTML;
    revealInner = `<div class="en">${escapeHtml(current.translation)}</div>`;
  } else {
    promptText = current.mode === 'cloze'
      ? escapeHtml(current.cloze).replace('_____', '<span class="blank">_____</span>')
      : '🔊 Listen first, then reveal.';
    hintLine = `<div class="hint">clue: ${escapeHtml(current.hint)}</div>`;
    revealInner = `
      <div class="id">${current.sentenceHtml}</div>
      <div class="en">${current.translation ? escapeHtml(current.translation) : ''}</div>
    `;
  }

  const sourceLine = current.kind === 'word' ? `${current.source} · ${current.tags.join(' · ')}` : current.source;
  cardEl.innerHTML = `
    <div class="source">${sourceLine}</div>
    <div class="prompt">${promptText}</div>
    ${hintLine}
    <div class="playrow"><button class="play" id="playBtn">&#9654; Play line</button></div>
    <button class="revealBtn" id="revealBtn">Reveal ${current.kind === 'word' ? 'answer' : 'transcript + translation'}</button>
    <button class="flagLineBtn" id="flagLineBtn" title="Hide this line everywhere — silent clip or ASR junk">&#128681; Not real content</button>
    <div class="reveal" id="revealBox">${revealInner}</div>
    <div class="rate" id="rateRow" hidden>
      <button class="rate-btn again" id="btn1"><span class="lbl">Again</span><span class="prev" id="prev1"></span></button>
      <button class="rate-btn hard" id="btn2"><span class="lbl">Hard</span><span class="prev" id="prev2"></span></button>
      <button class="rate-btn good" id="btn3"><span class="lbl">Good</span><span class="prev" id="prev3"></span></button>
      <button class="rate-btn easy" id="btn4"><span class="lbl">Easy</span><span class="prev" id="prev4"></span></button>
    </div>
  `;
  document.getElementById('playBtn').addEventListener('click', playLine);
  document.getElementById('revealBtn').addEventListener('click', reveal);
  document.getElementById('flagLineBtn').addEventListener('click', flagCurrentLine);
  [1, 2, 3, 4].forEach(g => {
    document.getElementById('btn' + g).addEventListener('click', () => rate(g));
  });
  updatePlayBtnLabel();
  wireTips();          // the rhythm tip is re-injected with every card
}

function updatePreviews() {
  if (!current) return;
  const labels = fsrsPreviewLabels(srs[current.id], Date.now());
  for (let g = 1; g <= 4; g++) document.getElementById('prev' + g).textContent = labels[g];
}

function flagCurrentLine() {
  if (!current) return;
  flags[current.lineId] = true;
  saveFlags(flags);
  syncRemoteQueuePush(setSyncState);
  updateUnflagCount();
  applyFilter();
  pickNext();
}

function isWithinCurrentClip() {
  return current && audio.src.endsWith(current.audio) && audio.readyState >= 1 &&
    audio.currentTime >= current.sec - 0.25 && audio.currentTime < current.nextSec;
}

function playLine() {
  if (!current) return;
  if (current.kind === 'pairs') { playPairTrial(); return; }
  // Fill-the-blank sentences were written for the deck, not spoken by anyone,
  // so there is no clip to seek to — synthesis is the only option.
  if (!current.audio) { ttsSay(current.sentence, current.sentenceSrc); return; }
  if (isWithinCurrentClip()) {
    if (audio.paused) { stopAt = current.nextSec; audio.play(); } else { audio.pause(); }
    return;
  }
  stopAt = current.nextSec;
  const start = () => { audio.currentTime = current.sec; audio.play(); };
  if (audio.src.endsWith(current.audio) && audio.readyState >= 1) {
    start();
  } else {
    audio.src = current.audio;
    audio.addEventListener('loadedmetadata', start, {once:true});
    audio.load();
  }
}

function updatePlayBtnLabel() {
  const btn = document.getElementById('playBtn');
  if (!btn || !current || !current.audio) return;   // blank items keep their own label
  btn.innerHTML = (!audio.paused && isWithinCurrentClip()) ? '&#10073;&#10073; Pause' : '&#9654; Play line';
}

// Voices arrive asynchronously; a blank card rendered before they load would
// otherwise be stuck with a permanently disabled play button.
ttsOnVoicesChanged(() => {
  const btn = document.getElementById('playBtn');
  if (btn && current && !current.audio) btn.disabled = !ttsVoice && !current.sentenceSrc;
});

audio.addEventListener('play', updatePlayBtnLabel);
audio.addEventListener('pause', updatePlayBtnLabel);
audio.addEventListener('timeupdate', () => {
  if (stopAt !== null && audio.currentTime >= stopAt) { audio.pause(); stopAt = null; }
  updatePlayBtnLabel();
});

function reveal() {
  revealed = true;
  document.getElementById('revealBox').classList.add('shown');
  document.getElementById('rateRow').hidden = false;
  updatePreviews();
}

function rate(grade) {
  if (!current) return;
  const isNew = !srs[current.id];
  const ts = srsLogReview(current.kind, grade, isNew);
  srsPushUndo({ item: current, id: current.id, prev: srs[current.id] || null, ts, mode });
  srs[current.id] = fsrsNextState(srs[current.id], grade, Date.now());
  srsSave(SRS_KEY, srs);
  syncRemoteQueuePush(setSyncState);
  practiceAhead = false;
  updateUndoBtn();
  pickNext();
}

// Undo restores the item's previous schedule (or removes it entirely if that
// rating was its first) and drops the review-log entry.
function undoLast() {
  const u = srsPopUndo();
  if (!u) return;
  // Remember what was on screen, so re-rating the restored item returns you
  // to it instead of a random draw.
  srsPushForward(current);
  const restored = srsRestoreState(u.prev);
  if (restored) srs[u.id] = restored; else delete srs[u.id];
  srsSave(SRS_KEY, srs);
  srsUnlogReview(u.ts);
  syncRemoteQueuePush(setSyncState);
  practiceAhead = false;
  updateUndoBtn();
  // The rating may have happened in another mode; go back to it so the
  // restored item is the one actually on screen.
  if (u.mode !== mode) setMode(u.mode);
  audio.pause();
  stopAt = null;
  current = u.item;
  revealed = false;
  renderCard();
  renderStats();
}

function updateUndoBtn() {
  document.getElementById('undoBtn').disabled = !srsUndoDepth();
}

function pickNext() {
  audio.pause();
  stopAt = null;
  if (!pool.length) { renderEmpty('No quiz items for this tag.'); renderStats(); return; }
  // If an undo displaced an item, give that one back rather than drawing a
  // fresh random one — otherwise "Go back" loses your place.
  const queued = srsTakeForward(c => pool.find(d => d.id === c.id));
  if (queued) {
    current = queued;
    revealed = false;
    renderCard();
    renderStats();
    if (['listening', 'hear', 'pairs'].includes(current.kind) && userInteracted) playLine();
    return;
  }
  // Reviews first, then any brand-new item; practice-ahead ignores the
  // schedule entirely once even that pool is exhausted.
  const reviews = pool.filter(d => srs[d.id] && srsIsDue(srs[d.id]));
  const freshAll = pool.filter(d => !srs[d.id]);
  let due = reviews.length ? reviews : freshAll;
  if (practiceAhead && !due.length) due = pool;
  if (!due.length) { renderAllCaughtUp(); renderStats(); return; }
  let next = due[Math.floor(Math.random() * due.length)];
  if (due.length > 1 && current && next.id === current.id) next = due[Math.floor(Math.random() * due.length)];
  current = next;
  revealed = false;
  renderCard();
  renderStats();
  if (['listening', 'hear', 'pairs'].includes(current.kind) && userInteracted) playLine();
}

// Undo can legitimately land on an item the active filter excludes (the mode
// is restored automatically, the tag chips are not). Say so.
function updateOffFilterNote() {
  const el = document.getElementById('offFilter');
  if (!el) return;
  if (!current || !pool.length || pool.some(d => d.id === current.id)) {
    el.hidden = true;
    return;
  }
  el.innerHTML = "This item isn't in your current filter — it's tagged <b>"
    + escapeHtml((current.tags || []).join(' · ')) + "</b>. Rate it to go back to your filter.";
  el.hidden = false;
}

function renderStats() {
  updateOffFilterNote();
  const modeItems = itemsForMode(mode);
  const dueReviews = modeItems.filter(d => srs[d.id] && srsIsDue(srs[d.id])).length;
  const fresh = modeItems.filter(d => !srs[d.id]).length;
  const mature = modeItems.filter(d => srsIsMature(srs[d.id])).length;
  const label = { word: 'word items', blank: 'blanks to fill', hear: 'clips to catch', pairs: 'minimal pairs', sentence: 'sentences', listening: 'listening clips' }[mode];
  document.getElementById('stats').textContent =
    `${modeItems.length} ${label} — ${dueReviews} to review, ${fresh} new, ${mature} mastered (21d+)`;
  document.getElementById('deckInfo').textContent = pool.length + ' in current filter';
}

document.getElementById('resetBtn').addEventListener('click', () => {
  if (confirm('Reset all quiz progress (review history and due dates)?')) { srs = {}; srsSave(SRS_KEY, srs); srsClearForward(); pickNext(); }
});

unflagBtn.addEventListener('click', () => {
  if (!Object.keys(flags).length) return;
  if (confirm(`Unflag all ${Object.keys(flags).length} lines? They'll reappear in the player and quiz.`)) {
    flags = {};
    saveFlags(flags);
    updateUnflagCount();
    applyFilter();
    pickNext();
  }
});

let userInteracted = false;
document.addEventListener('pointerdown', () => { userInteracted = true; }, { capture: true });
document.addEventListener('keydown', (e) => {
  userInteracted = true;
  if (e.key === 'p') { playLine(); return; }
  if (e.key === 'z') { undoLast(); return; }
  if (revealed && ['1','2','3','4'].includes(e.key)) rate(parseInt(e.key, 10));
});

document.getElementById('undoBtn').addEventListener('click', undoLast);

updateUnflagCount();
pickNext();
__PWA_SW__
</script>
</body>
</html>
"""


def main():
    vocab = load_vocab()
    convos = load_conversations()
    ll_index = load_ll_index()
    word_items = build_quiz_items(vocab, convos)
    blank_items = build_blank_items(vocab)
    hear_items = build_hear_items(vocab, convos)
    pair_items = build_pair_items(vocab, ll_index)
    sentence_items = build_sentence_items(convos)
    listening_items = build_listening_items(sentence_items)
    items = word_items + blank_items + hear_items + pair_items + sentence_items + listening_items
    html = (
        PAGE.replace("__SRS_JS__", SRS_JS)
        .replace("__SYNC_JS__", SYNC_JS)
        .replace("__TTS_JS__", TTS_JS)
        .replace("__BOOST_JS__", BOOST_JS)
        .replace("__PWA_META__", PWA_META_TAGS)
        .replace("__PWA_SW__", PWA_SW_JS)
        .replace("__TIPS_CSS__", TIPS_CSS)
        .replace("__OFF_FILTER_CSS__", OFF_FILTER_CSS)
        .replace("__STICKY_RATE_CSS__", STICKY_RATE_CSS)
        .replace("__TIPS_JS__", TIPS_JS)
        .replace("__RHYTHM_TIP__", RHYTHM_TIP_TEXT)
        .replace("__DATA__", json.dumps(items, ensure_ascii=False))
    )
    OUT.write_text(html, encoding="utf-8")
    cloze_n = sum(1 for i in word_items if i["mode"] == "cloze")
    affixed = sum(1 for i in blank_items if len(i["accepts"]) > 1)
    documented = sum(1 for i in pair_items if i["documented"])
    print(f"wrote {OUT}: {len(word_items)} word items ({cloze_n} cloze, {len(word_items)-cloze_n} recall) "
          f"from {len(vocab)} vocab terms, {len(blank_items)} fill-the-blank items "
          f"({affixed} where the sentence uses an affixed form), {len(hear_items)} catch-it clips "
          f"over {len({i[chr(39)+chr(39)] if False else i['answer'] for i in hear_items})} multi-speaker words, "
          f"{len(pair_items)} minimal pairs ({documented} on a documented contrast, "
          f"{sum(len(i['trials']) for i in pair_items)} trials), {len(sentence_items)} sentence items, "
          f"{len(listening_items)} listening items, across {len(convos)} conversation(s)")


if __name__ == "__main__":
    main()
