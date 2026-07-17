#!/usr/bin/env python3
"""
Build quiz.html — comprehension exercises generated from real transcript
lines, with inline audio playback of the source line. Two modes:

- Word (cloze/recall): cross-references every vocab/*.tsv term against each
  conversation's Indonesian-language lines. A term that appears inside a
  longer sentence becomes a cloze card (blank the term, guess it from
  context); a term that IS basically the whole line becomes a "recall" card
  (listen, then reveal). Terms with no match in any transcript are skipped.
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
                rows.append({"front": front, "back": back, "tags": tags})
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
<meta name="viewport" content="width=device-width, initial-scale=1">
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
  button.flagLineBtn { font-size:0.78rem; padding:8px 14px; border-radius:8px; border:1px solid var(--line);
    background:var(--bg); color:var(--muted); cursor:pointer; margin-left:8px; }
  button.flagLineBtn:hover { border-color:var(--bad); color:var(--bad); }
  .rate { display:flex; gap:8px; margin-top:14px; }
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
    <button class="modeBtn" data-mode="sentence">Sentence</button>
    <button class="modeBtn" data-mode="listening">Listening</button>
  </div>
  <div class="modeHint" id="modeHint"></div>
  <div class="stats" id="stats"></div>
  <select id="tagFilter"></select>
  <div id="card"></div>
  <div class="tools">
    <button class="plain" id="resetBtn">Reset progress</button>
    <button class="plain" id="unflagBtn">Unflag lines (0)</button>
    <span class="stats" id="syncState"></span>
    <span class="stats" id="deckInfo"></span>
  </div>
</div>
<audio id="qaudio" preload="none"></audio>
<script>
__SRS_JS__
__SYNC_JS__
const ITEMS = __DATA__;
const SRS_KEY = 'bahasa:quiz:fsrs:v1';
const LEGACY_KEYS = ['bahasa:quiz:v1', 'bahasa:quiz:srs:v1'];
// FLAG_KEY comes from the shared sync module above.
const audio = document.getElementById('qaudio');

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
  rebuildTagFilter();
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
const tagFilter = document.getElementById('tagFilter');
const modeHintEl = document.getElementById('modeHint');

const MODE_HINTS = {
  word: 'One word blanked out of a real sentence — recall it from context.',
  sentence: 'A whole real line — read or listen, then reveal the translation and rate yourself on the whole thing, not just one word.',
  listening: 'Ears only: the clip plays with the text hidden. Understand it by ear, then reveal and rate. This is the actual target skill.',
};

function itemsForMode(m) { return ITEMS.filter(d => d.kind === m && !flags[d.lineId]); }

function rebuildTagFilter() {
  const modeItems = itemsForMode(mode);
  const label = mode === 'word' ? 'All tags' : 'All conversations';
  const tags = [...new Set(modeItems.flatMap(d => d.tags))].sort();
  tagFilter.innerHTML = `<option value="">${label}</option>` +
    tags.map(t => `<option value="${t}">${t}</option>`).join('');
}

tagFilter.addEventListener('change', () => { practiceAhead = false; applyFilter(); pickNext(); });

function applyFilter() {
  const modeItems = itemsForMode(mode);
  const t = tagFilter.value;
  pool = t ? modeItems.filter(d => d.tags.includes(t)) : modeItems;
}

document.querySelectorAll('.modeBtn').forEach(b => {
  b.addEventListener('click', () => {
    mode = b.dataset.mode;
    practiceAhead = false;
    document.querySelectorAll('.modeBtn').forEach(x => x.classList.toggle('active', x === b));
    modeHintEl.textContent = MODE_HINTS[mode];
    rebuildTagFilter();
    applyFilter();
    pickNext();
  });
});

modeHintEl.textContent = MODE_HINTS[mode];
rebuildTagFilter();
applyFilter();

function escapeHtml(s) {
  return s.replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
}

function renderEmpty(msg) {
  current = null;
  cardEl.innerHTML = `<div class="empty">${msg}</div>`;
}

function renderAllCaughtUp(capReached) {
  current = null;
  const now = Date.now();
  const dues = pool.map(d => (srs[d.id] && srs[d.id].due) || Infinity);
  const nextDue = Math.min(...dues);
  const in24h = pool.filter(d => srs[d.id] && srs[d.id].due > now && srs[d.id].due <= now + 86400000).length;
  const head = capReached ? `Daily new-card limit (${NEW_PER_DAY}) reached — good stopping point!` : '🎉 All caught up!';
  cardEl.innerHTML = `<div class="empty">${head}<div class="sub">Next review in ${srsFmtDue(nextDue)}${in24h ? ` · ${in24h} due within 24h` : ''}.</div>` +
    `<button class="plain" id="aheadBtn">Practice ahead anyway</button></div>`;
  document.getElementById('aheadBtn').addEventListener('click', () => { practiceAhead = true; pickNext(); });
}

function renderCard() {
  let promptText, hintLine, revealInner;
  if (current.kind === 'listening') {
    promptText = '🎧 Listen — no peeking. Press play (or "p") and try to catch the whole line.';
    hintLine = '';
    revealInner = `
      <div class="id">${current.sentenceHtml}</div>
      <div class="en">${escapeHtml(current.translation)}</div>
    `;
  } else if (current.kind === 'sentence') {
    promptText = current.sentenceHtml;
    hintLine = '';
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
  if (!btn) return;
  btn.innerHTML = (!audio.paused && isWithinCurrentClip()) ? '&#10073;&#10073; Pause' : '&#9654; Play line';
}

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
  if (isNew) srsNoteNewIntroduced();
  srsLogReview(current.kind, grade, isNew);
  srs[current.id] = fsrsNextState(srs[current.id], grade, Date.now());
  srsSave(SRS_KEY, srs);
  syncRemoteQueuePush(setSyncState);
  practiceAhead = false;
  pickNext();
}

function pickNext() {
  audio.pause();
  stopAt = null;
  if (!pool.length) { renderEmpty('No quiz items for this tag.'); renderStats(); return; }
  // Reviews first; brand-new items only while today's shared new-card quota
  // lasts (practice-ahead ignores both the schedule and the quota).
  const reviews = pool.filter(d => srs[d.id] && srsIsDue(srs[d.id]));
  const freshAll = pool.filter(d => !srs[d.id]);
  const quota = srsNewQuotaLeft();
  let due = reviews.length ? reviews : (practiceAhead ? freshAll : freshAll.slice(0, quota));
  if (practiceAhead && !due.length) due = pool;
  if (!due.length) { renderAllCaughtUp(freshAll.length > 0 && quota === 0); renderStats(); return; }
  let next = due[Math.floor(Math.random() * due.length)];
  if (due.length > 1 && current && next.id === current.id) next = due[Math.floor(Math.random() * due.length)];
  current = next;
  revealed = false;
  renderCard();
  renderStats();
  if (current.kind === 'listening' && userInteracted) playLine();
}

function renderStats() {
  const modeItems = itemsForMode(mode);
  const dueReviews = modeItems.filter(d => srs[d.id] && srsIsDue(srs[d.id])).length;
  const fresh = modeItems.filter(d => !srs[d.id]).length;
  const newToday = Math.min(fresh, srsNewQuotaLeft());
  const mature = modeItems.filter(d => srsIsMature(srs[d.id])).length;
  const label = { word: 'word items', sentence: 'sentences', listening: 'listening clips' }[mode];
  document.getElementById('stats').textContent =
    `${modeItems.length} ${label} — ${dueReviews} to review, ${newToday} new today, ${mature} mastered (21d+)`;
  document.getElementById('deckInfo').textContent = pool.length + ' in current filter';
}

document.getElementById('resetBtn').addEventListener('click', () => {
  if (confirm('Reset all quiz progress (review history and due dates)?')) { srs = {}; srsSave(SRS_KEY, srs); pickNext(); }
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
  if (revealed && ['1','2','3','4'].includes(e.key)) rate(parseInt(e.key, 10));
});

updateUnflagCount();
pickNext();
</script>
</body>
</html>
"""


def main():
    vocab = load_vocab()
    convos = load_conversations()
    word_items = build_quiz_items(vocab, convos)
    sentence_items = build_sentence_items(convos)
    listening_items = build_listening_items(sentence_items)
    items = word_items + sentence_items + listening_items
    html = (
        PAGE.replace("__SRS_JS__", SRS_JS)
        .replace("__SYNC_JS__", SYNC_JS)
        .replace("__DATA__", json.dumps(items, ensure_ascii=False))
    )
    OUT.write_text(html, encoding="utf-8")
    cloze_n = sum(1 for i in word_items if i["mode"] == "cloze")
    print(f"wrote {OUT}: {len(word_items)} word items ({cloze_n} cloze, {len(word_items)-cloze_n} recall) "
          f"from {len(vocab)} vocab terms, {len(sentence_items)} sentence items, "
          f"{len(listening_items)} listening items, across {len(convos)} conversation(s)")


if __name__ == "__main__":
    main()
