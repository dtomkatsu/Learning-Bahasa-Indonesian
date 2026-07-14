#!/usr/bin/env python3
"""
Build quiz.html — cloze (fill-in-the-blank) comprehension exercises generated
from real transcript lines that contain a vocab-deck term, with inline audio
playback of the source line.

For each conversation (matched by transcripts/<name>.clean.txt +
audio/<name>.<ext> + an optional transcripts/<name>.translations.json),
cross-references every vocab/*.tsv term against that conversation's
Indonesian-language lines. A term that appears inside a longer sentence
becomes a cloze card (blank the term, guess it from context); a term that
IS basically the whole line becomes a "recall" card (listen, then reveal).
Terms with no match in any transcript are skipped — not every vocab word
needs to have been said with extra context.

Progress persists in the browser via localStorage, using the same 4-box
mastery system as flashcards.html.

Usage:
    python3 build_quiz.py
"""
import csv
import json
import re
from html import escape as html_escape
from pathlib import Path

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


def load_vocab():
    rows = []
    seen = set()
    for tsv in sorted(VOCAB_DIR.glob("*.tsv")):
        with open(tsv, encoding="utf-8") as f:
            for row in csv.reader(f, delimiter="\t"):
                if len(row) < 3:
                    continue
                front, back, tag = row[0].strip(), row[1].strip(), row[2].strip()
                if not front or front in seen or tag in SKIP_TAGS:
                    continue
                seen.add(front)
                rows.append({"front": front, "back": back, "tag": tag})
    return rows


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
            "term": v["front"],
            "hint": v["back"],
            "tag": v["tag"],
            "mode": mode,
            "sentence": e["text"],
            "sentenceHtml": sentence_html,
            "cloze": cloze_sentence,
            "translation": e.get("en"),
            "sec": e["sec"],
            "nextSec": min(next_sec, e["sec"] + 8),
            "audio": convo["audio"],
            "source": convo["label"],
        })
    return items


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Quiz — Learning Bahasa Indonesian</title>
<style>
  :root { color-scheme: light dark; --bg:#fff; --fg:#1a1a1a; --muted:#6b7280; --line:#e5e7eb;
    --accent:#2563eb; --card:#f9fafb; --good:#16a34a; --bad:#dc2626; --blank:#f59e0b; }
  @media (prefers-color-scheme: dark) {
    :root { --bg:#111318; --fg:#e7e9ee; --muted:#9aa1ac; --line:#2a2e37; --accent:#5b9dff;
      --card:#1a1d24; --good:#4ade80; --bad:#f87171; --blank:#fbbf24; }
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
  #card { border:1px solid var(--line); border-radius:14px; background:var(--card);
    min-height:200px; padding:24px 22px; margin:18px 0; }
  .source { font-size:0.72rem; color:var(--muted); margin-bottom:10px; }
  .prompt { font-size:1.15rem; line-height:1.5; margin-bottom:6px; }
  .prompt .blank { color:var(--blank); font-weight:700; letter-spacing:1px; }
  .hint { color:var(--muted); font-size:0.82rem; margin-bottom:16px; }
  .playrow { margin-bottom:14px; }
  button.play { font-size:0.85rem; padding:8px 14px; border-radius:8px; border:1px solid var(--accent);
    background:transparent; color:var(--accent); cursor:pointer; }
  button.play:hover { background:var(--accent); color:#fff; }
  .reveal { display:none; border-top:1px dashed var(--line); margin-top:14px; padding-top:14px; }
  .reveal.shown { display:block; }
  .reveal .id { font-size:1.05rem; margin-bottom:4px; }
  .reveal .id b { color:var(--accent); }
  .reveal .en { color:var(--muted); font-size:0.9rem; }
  button.revealBtn { font-size:0.85rem; padding:8px 14px; border-radius:8px; border:1px solid var(--line);
    background:var(--bg); color:var(--fg); cursor:pointer; }
  .rate { display:flex; gap:10px; margin-top:14px; }
  .rate[hidden] { display:none; }
  button.rate-btn { flex:1; padding:12px; border-radius:10px; border:1px solid var(--line);
    background:var(--card); color:var(--fg); font-size:0.9rem; cursor:pointer; }
  button.rate-btn.bad { border-color:var(--bad); color:var(--bad); }
  button.rate-btn.good { border-color:var(--good); color:var(--good); }
  .tools { display:flex; justify-content:space-between; align-items:center; margin-top:24px; }
  button.plain { font-size:0.78rem; padding:6px 10px; border-radius:6px; border:1px solid var(--line);
    background:var(--bg); color:var(--muted); cursor:pointer; }
  .empty { color:var(--muted); font-size:0.9rem; text-align:center; margin-top:60px; }
</style>
</head>
<body>
<div class="wrap">
  <div class="top">
    <h1>Quiz</h1>
    <a class="back" href="index.html">&larr; all conversations</a>
  </div>
  <div class="stats" id="stats"></div>
  <select id="tagFilter"></select>
  <div id="card"></div>
  <div class="tools">
    <button class="plain" id="resetBtn">Reset progress</button>
    <span class="stats" id="deckInfo"></span>
  </div>
</div>
<audio id="qaudio" preload="none"></audio>
<script>
const ITEMS = __DATA__;
const STORE_KEY = 'bahasa:quiz:v1';
const audio = document.getElementById('qaudio');

function loadProgress() {
  try { return JSON.parse(localStorage.getItem(STORE_KEY)) || {}; } catch (e) { return {}; }
}
function saveProgress(p) { localStorage.setItem(STORE_KEY, JSON.stringify(p)); }
let progress = loadProgress();
function keyOf(item) { return item.source + '::' + item.term; }
function boxOf(item) { const k = keyOf(item); return (progress[k] && progress[k].box) || 0; }

let pool = ITEMS.slice();
let current = null;
let revealed = false;
let stopAt = null;

const cardEl = document.getElementById('card');
const tagFilter = document.getElementById('tagFilter');

function uniqueTags() { return [...new Set(ITEMS.map(d => d.tag))].sort(); }
tagFilter.innerHTML = '<option value="">All tags</option>' +
  uniqueTags().map(t => `<option value="${t}">${t}</option>`).join('');
tagFilter.addEventListener('change', () => { applyFilter(); pickNext(); });

function applyFilter() {
  const t = tagFilter.value;
  pool = t ? ITEMS.filter(d => d.tag === t) : ITEMS.slice();
}
applyFilter();

function weightedPick(items) {
  const weights = items.map(d => Math.max(1, 4 - boxOf(d)));
  const total = weights.reduce((a, b) => a + b, 0);
  let r = Math.random() * total;
  for (let i = 0; i < items.length; i++) {
    r -= weights[i];
    if (r <= 0) return items[i];
  }
  return items[items.length - 1];
}

function escapeHtml(s) {
  return s.replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
}

function renderCard() {
  if (!current) { cardEl.innerHTML = '<div class="empty">No quiz items for this tag.</div>'; return; }
  const promptText = current.mode === 'cloze'
    ? escapeHtml(current.cloze).replace('_____', '<span class="blank">_____</span>')
    : '🔊 Listen first, then reveal.';
  cardEl.innerHTML = `
    <div class="source">${current.source} · ${current.tag}</div>
    <div class="prompt">${promptText}</div>
    <div class="hint">clue: ${escapeHtml(current.hint)}</div>
    <div class="playrow"><button class="play" id="playBtn">&#9654; Play line</button></div>
    <button class="revealBtn" id="revealBtn">Reveal answer</button>
    <div class="reveal" id="revealBox">
      <div class="id">${current.sentenceHtml}</div>
      <div class="en">${current.translation ? escapeHtml(current.translation) : ''}</div>
    </div>
    <div class="rate" id="rateRow" hidden>
      <button class="rate-btn bad" id="btnBad">Missed it</button>
      <button class="rate-btn good" id="btnGood">Got it</button>
    </div>
  `;
  document.getElementById('playBtn').addEventListener('click', playLine);
  document.getElementById('revealBtn').addEventListener('click', reveal);
  document.getElementById('btnBad').addEventListener('click', () => rate(false));
  document.getElementById('btnGood').addEventListener('click', () => rate(true));
}

function playLine() {
  if (!current) return;
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

audio.addEventListener('timeupdate', () => {
  if (stopAt !== null && audio.currentTime >= stopAt) { audio.pause(); stopAt = null; }
});

function reveal() {
  revealed = true;
  document.getElementById('revealBox').classList.add('shown');
  document.getElementById('rateRow').hidden = false;
}

function rate(good) {
  if (!current) return;
  const k = keyOf(current);
  const box = boxOf(current);
  progress[k] = { box: good ? Math.min(3, box + 1) : 0 };
  saveProgress(progress);
  pickNext();
}

function pickNext() {
  if (!pool.length) { current = null; renderCard(); renderStats(); return; }
  let next = weightedPick(pool);
  if (pool.length > 1 && current && next.term === current.term && next.source === current.source) next = weightedPick(pool);
  current = next;
  revealed = false;
  stopAt = null;
  renderCard();
  renderStats();
}

function renderStats() {
  const boxes = [0,0,0,0];
  ITEMS.forEach(d => boxes[boxOf(d)]++);
  document.getElementById('stats').textContent =
    `${ITEMS.length} quiz items — new ${boxes[0]}, learning ${boxes[1]+boxes[2]}, mastered ${boxes[3]}`;
  document.getElementById('deckInfo').textContent = pool.length + ' in current filter';
}

document.getElementById('resetBtn').addEventListener('click', () => {
  if (confirm('Reset all quiz progress?')) { progress = {}; saveProgress(progress); pickNext(); }
});

pickNext();
</script>
</body>
</html>
"""


def main():
    vocab = load_vocab()
    convos = load_conversations()
    items = build_quiz_items(vocab, convos)
    html = PAGE.replace("__DATA__", json.dumps(items, ensure_ascii=False))
    OUT.write_text(html, encoding="utf-8")
    cloze_n = sum(1 for i in items if i["mode"] == "cloze")
    print(f"wrote {OUT}: {len(items)} quiz items ({cloze_n} cloze, {len(items)-cloze_n} recall) "
          f"from {len(vocab)} vocab terms across {len(convos)} conversation(s)")


if __name__ == "__main__":
    main()
