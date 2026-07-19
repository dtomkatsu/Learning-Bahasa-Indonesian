#!/usr/bin/env python3
"""
Build study.html — the one-tap daily session: everything due across
flashcards AND all three quiz modes (word/sentence/listening), interleaved
into a single run with an end-of-session summary.

Why one page: interleaving item types measurably beats studying them in
blocks, and a single "Study now" button removes the decision overhead that
kills daily habits. The page reads/writes the SAME two SRS stores as
flashcards.html and quiz.html (flash cards keyed by front, quiz items keyed
by id), so progress is one pool no matter which page you review on.

New cards respect the shared daily cap (see _srs_js.py); reviews always run
in full. Item data is imported from the flashcards/quiz builders, so this
stays in lockstep with them by construction.

Usage:
    python3 build_study.py
"""
import json
from pathlib import Path

from _srs_js import SRS_JS
from _sync_js import SYNC_JS
from build_flashcards import load_decks
from build_quiz import (
    load_vocab, load_conversations,
    build_quiz_items, build_sentence_items, build_listening_items,
)

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "study.html"

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Study — Learning Bahasa Indonesian</title>
<style>
  :root { color-scheme: light dark; --bg:#fff; --fg:#1a1a1a; --muted:#6b7280; --line:#e5e7eb;
    --accent:#2563eb; --card:#f9fafb; --blank:#f59e0b;
    --again:#dc2626; --hard:#d97706; --good:#16a34a; --easy:#2563eb; }
  @media (prefers-color-scheme: dark) {
    :root { --bg:#111318; --fg:#e7e9ee; --muted:#9aa1ac; --line:#2a2e37; --accent:#5b9dff;
      --card:#1a1d24; --blank:#fbbf24; --again:#f87171; --hard:#fbbf24; --good:#4ade80; --easy:#7cb0ff; }
  }
  * { box-sizing:border-box; }
  html, body { margin:0; background:var(--bg); color:var(--fg);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }
  .wrap { max-width:600px; margin:0 auto; padding:28px 20px 60px; }
  .top { display:flex; justify-content:space-between; align-items:baseline; gap:10px; flex-wrap:wrap; margin-bottom:6px; }
  h1 { font-size:1.15rem; margin:0; }
  a.back { color:var(--muted); font-size:0.8rem; text-decoration:none; }
  .progress { color:var(--muted); font-size:0.8rem; margin-bottom:14px; }
  .bar { height:4px; background:var(--line); border-radius:2px; margin-bottom:18px; overflow:hidden; }
  .bar span { display:block; height:100%; background:var(--accent); width:0; transition:width 0.25s; }
  #card { border:1px solid var(--line); border-radius:14px; background:var(--card);
    min-height:220px; padding:24px 22px; margin:0 0 14px; }
  .kind { font-size:0.72rem; color:var(--muted); text-transform:uppercase; letter-spacing:0.04em; margin-bottom:10px; }
  .prompt { font-size:1.2rem; line-height:1.5; margin-bottom:8px; }
  .prompt .blank { color:var(--blank); font-weight:700; letter-spacing:1px; }
  .hintline { color:var(--muted); font-size:0.82rem; margin-bottom:14px; }
  .playrow { margin-bottom:12px; }
  button.play { font-size:0.85rem; padding:8px 14px; border-radius:8px; border:1px solid var(--accent);
    background:transparent; color:var(--accent); cursor:pointer; }
  button.play:hover { background:var(--accent); color:#fff; }
  .reveal { display:none; border-top:1px dashed var(--line); margin-top:12px; padding-top:12px; }
  .reveal.shown { display:block; }
  .reveal .id { font-size:1.05rem; margin-bottom:4px; }
  .reveal .id b { color:var(--accent); }
  .reveal .en { color:var(--muted); font-size:0.9rem; }
  button.revealBtn { font-size:0.85rem; padding:8px 14px; border-radius:8px; border:1px solid var(--line);
    background:var(--bg); color:var(--fg); cursor:pointer; }
  .rate { display:flex; gap:8px; margin-top:4px; }
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
  .tools { display:flex; justify-content:space-between; align-items:center; margin-top:20px; }
  .stats { color:var(--muted); font-size:0.8rem; }
  .summary { text-align:center; padding:30px 10px; }
  .summary h2 { font-size:1.3rem; margin:0 0 8px; }
  .summary p { color:var(--muted); font-size:0.9rem; margin:6px 0; }
  .summary .tallies { display:flex; justify-content:center; gap:14px; margin:18px 0; }
  .summary .tallies div { text-align:center; }
  .summary .tallies .n { font-size:1.3rem; font-weight:700; }
  .summary .tallies .l { font-size:0.72rem; color:var(--muted); }
  .summary .t1 .n { color:var(--again); } .summary .t2 .n { color:var(--hard); }
  .summary .t3 .n { color:var(--good); } .summary .t4 .n { color:var(--easy); }
  .summary a, .summary button { font-size:0.85rem; padding:9px 14px; border-radius:8px;
    border:1px solid var(--line); background:var(--bg); color:var(--fg); cursor:pointer;
    text-decoration:none; display:inline-block; margin:4px; }
</style>
</head>
<body>
<div class="wrap">
  <div class="top">
    <h1>Study session</h1>
    <a class="back" href="index.html">&larr; home</a>
  </div>
  <div class="progress" id="progress"></div>
  <div class="bar"><span id="barFill"></span></div>
  <div id="card"></div>
  <div class="rate" id="rateRow" hidden>
    <button class="rate-btn again" id="btn1"><span class="lbl">Again</span><span class="prev" id="prev1"></span></button>
    <button class="rate-btn hard" id="btn2"><span class="lbl">Hard</span><span class="prev" id="prev2"></span></button>
    <button class="rate-btn good" id="btn3"><span class="lbl">Good</span><span class="prev" id="prev3"></span></button>
    <button class="rate-btn easy" id="btn4"><span class="lbl">Easy</span><span class="prev" id="prev4"></span></button>
  </div>
  <div class="tools">
    <span class="stats" id="syncState"></span>
    <span class="stats" id="sessionInfo"></span>
  </div>
</div>
<audio id="qaudio" preload="none"></audio>
<script>
__SRS_JS__
__SYNC_JS__
const FLASH_DECK = __FLASH__;
const QUIZ_ITEMS = __QUIZ__;
const FLASH_SRS_KEY = 'bahasa:flashcards:fsrs:v1';
const QUIZ_SRS_KEY = 'bahasa:quiz:fsrs:v1';
const audio = document.getElementById('qaudio');

let srsF = srsLoad(FLASH_SRS_KEY);
let srsQ = srsLoad(QUIZ_SRS_KEY);

function setSyncState(s) {
  const el = document.getElementById('syncState');
  if (!syncRemoteConfigured()) { el.textContent = ''; return; }
  el.textContent = s === 'pending' ? 'syncing…' : s === 'err' ? 'sync failed' : 'synced ✓';
}

// Same deck-layering as flashcards.html: tombstones out, custom cards in.
function normalizeCard(d) {
  if (Array.isArray(d.tags) && d.tags.length) return d;
  return Object.assign({}, d, { tags: d.tag ? [d.tag] : ['custom'] });
}
function computeFlashItems() {
  const removed = syncRead(REMOVED_CARDS_KEY);
  const custom = syncRead(CUSTOM_CARDS_KEY);
  const byFront = new Map();
  FLASH_DECK.forEach(d => { if (!removed[d.front]) byFront.set(d.front, d); });
  Object.values(custom).forEach(d => byFront.set(d.front, normalizeCard(d)));
  return [...byFront.values()].map(d => Object.assign({ kind: 'flash' }, d));
}
function computeQuizItems() {
  const flags = syncRead(FLAG_KEY);
  return QUIZ_ITEMS.filter(d => !flags[d.lineId]);
}

function stateFor(item) { return item.kind === 'flash' ? srsF[item.front] : srsQ[item.id]; }
function setState(item, s) {
  if (item.kind === 'flash') { srsF[item.front] = s; srsSave(FLASH_SRS_KEY, srsF); }
  else { srsQ[item.id] = s; srsSave(QUIZ_SRS_KEY, srsQ); }
}

function shuffle(a) {
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

// Session = every due review (shuffled, so kinds interleave naturally) with
// every not-yet-studied item sprinkled in one per few reviews. No daily cap,
// so on a big vocab dump (or a first-ever session) this can be large — that's
// intentional per-request, but worth knowing before hitting "Study now".
let session = [], idx = 0, tallies = { 1: 0, 2: 0, 3: 0, 4: 0 }, startedAt = null;
let practiceRun = false;

function buildSession(practice) {
  practiceRun = !!practice;
  const all = [...computeFlashItems(), ...computeQuizItems()];
  if (practice) {
    session = shuffle(all.filter(i => stateFor(i))).slice(0, 20);
  } else {
    const reviews = shuffle(all.filter(i => stateFor(i) && srsIsDue(stateFor(i))));
    const fresh = shuffle(all.filter(i => !stateFor(i))).slice(0, srsNewQuotaLeft());
    session = [];
    let f = 0;
    for (let r = 0; r < reviews.length; r++) {
      session.push(reviews[r]);
      if ((r + 1) % 3 === 0 && f < fresh.length) session.push(fresh[f++]);
    }
    while (f < fresh.length) session.push(fresh[f++]);
  }
  idx = 0;
  tallies = { 1: 0, 2: 0, 3: 0, 4: 0 };
  startedAt = Date.now();
}

const cardEl = document.getElementById('card');
const rateRow = document.getElementById('rateRow');
let current = null, revealed = false, stopAt = null;
let userInteracted = false;

function escapeHtml(s) {
  return String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
}

const KIND_LABEL = { flash: 'Flashcard', word: 'Fill the blank', sentence: 'Whole sentence', listening: 'By ear' };

function renderCard() {
  const item = current;
  let promptHtml, hintLine = '', revealInner, playRow = '';
  if (item.kind === 'flash') {
    promptHtml = escapeHtml(item.front);
    revealInner = `<div class="id">${escapeHtml(item.back)}</div><div class="en">${escapeHtml(item.tags.join(' · '))}</div>`;
  } else if (item.kind === 'word') {
    promptHtml = item.mode === 'cloze'
      ? escapeHtml(item.cloze).replace('_____', '<span class="blank">_____</span>')
      : '🔊 Listen first, then reveal.';
    hintLine = `<div class="hintline">clue: ${escapeHtml(item.hint)}</div>`;
    revealInner = `<div class="id">${item.sentenceHtml}</div><div class="en">${item.translation ? escapeHtml(item.translation) : ''}</div>`;
    playRow = '<div class="playrow"><button class="play" id="playBtn">&#9654; Play line</button></div>';
  } else if (item.kind === 'sentence') {
    promptHtml = item.sentenceHtml;
    revealInner = `<div class="en">${escapeHtml(item.translation)}</div>`;
    playRow = '<div class="playrow"><button class="play" id="playBtn">&#9654; Play line</button></div>';
  } else { // listening
    promptHtml = '🎧 Listen — no peeking. Press play (or "p") and try to catch the whole line.';
    revealInner = `<div class="id">${item.sentenceHtml}</div><div class="en">${escapeHtml(item.translation)}</div>`;
    playRow = '<div class="playrow"><button class="play" id="playBtn">&#9654; Play line</button></div>';
  }
  cardEl.innerHTML = `
    <div class="kind">${KIND_LABEL[item.kind]}${stateFor(item) ? '' : ' · new'}</div>
    <div class="prompt">${promptHtml}</div>
    ${hintLine}
    ${playRow}
    <button class="revealBtn" id="revealBtn">Reveal</button>
    <div class="reveal" id="revealBox">${revealInner}</div>
  `;
  rateRow.hidden = true;
  const pb = document.getElementById('playBtn');
  if (pb) pb.addEventListener('click', playLine);
  document.getElementById('revealBtn').addEventListener('click', reveal);
  updatePlayBtnLabel();
  renderProgress();
  if (item.kind === 'listening' && userInteracted) playLine();
}

function renderProgress() {
  document.getElementById('progress').textContent =
    `${Math.min(idx + 1, session.length)} of ${session.length}` + (practiceRun ? ' · practice (ignores schedule)' : '');
  document.getElementById('barFill').style.width = (session.length ? (idx / session.length) * 100 : 0) + '%';
  document.getElementById('sessionInfo').textContent =
    `${tallies[1] + tallies[2] + tallies[3] + tallies[4]} answered`;
}

function reveal() {
  revealed = true;
  document.getElementById('revealBox').classList.add('shown');
  rateRow.hidden = false;
  const labels = fsrsPreviewLabels(stateFor(current), Date.now());
  for (let g = 1; g <= 4; g++) document.getElementById('prev' + g).textContent = labels[g];
}

function rate(grade) {
  if (!current || !revealed) return;
  const isNew = !stateFor(current);
  if (isNew) srsNoteNewIntroduced();
  srsLogReview(current.kind, grade, isNew);
  setState(current, fsrsNextState(stateFor(current), grade, Date.now()));
  syncRemoteQueuePush(setSyncState);
  tallies[grade]++;
  idx++;
  next();
}

function next() {
  audio.pause();
  stopAt = null;
  revealed = false;
  if (idx >= session.length) { renderSummary(); return; }
  current = session[idx];
  renderCard();
}

function renderSummary() {
  current = null;
  rateRow.hidden = true;
  const total = tallies[1] + tallies[2] + tallies[3] + tallies[4];
  const mins = Math.max(1, Math.round((Date.now() - startedAt) / 60000));
  const all = [...computeFlashItems(), ...computeQuizItems()];
  const now = Date.now();
  const dues = all.map(i => (stateFor(i) && stateFor(i).due) || Infinity);
  const nextDue = Math.min(...dues);
  const in24h = all.filter(i => stateFor(i) && stateFor(i).due > now && stateFor(i).due <= now + 86400000).length;
  document.getElementById('progress').textContent = '';
  document.getElementById('barFill').style.width = '100%';
  cardEl.innerHTML = `
    <div class="summary">
      <h2>${total ? '🎉 Session done!' : 'Nothing due right now'}</h2>
      ${total ? `<div class="tallies">
        <div class="t1"><div class="n">${tallies[1]}</div><div class="l">Again</div></div>
        <div class="t2"><div class="n">${tallies[2]}</div><div class="l">Hard</div></div>
        <div class="t3"><div class="n">${tallies[3]}</div><div class="l">Good</div></div>
        <div class="t4"><div class="n">${tallies[4]}</div><div class="l">Easy</div></div>
      </div>
      <p>${total} answered in ~${mins} min.</p>` : ''}
      <p>Next review ${srsFmtDue(nextDue)}${in24h ? ` · ${in24h} due within 24h` : ''}.</p>
      <div>
        <button id="moreBtn">Practice 20 more</button>
        <a href="index.html">Done for now</a>
      </div>
    </div>`;
  document.getElementById('moreBtn').addEventListener('click', () => { buildSession(true); next(); });
}

// ---- audio (same clip logic as quiz.html) ----
function isWithinCurrentClip() {
  return current && current.audio && audio.src.endsWith(current.audio) && audio.readyState >= 1 &&
    audio.currentTime >= current.sec - 0.25 && audio.currentTime < current.nextSec;
}
function playLine() {
  if (!current || !current.audio) return;
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
    audio.addEventListener('loadedmetadata', start, { once: true });
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

// ---- input wiring ----
[1, 2, 3, 4].forEach(g => {
  document.getElementById('btn' + g).addEventListener('click', () => rate(g));
});
document.addEventListener('pointerdown', () => { userInteracted = true; }, { capture: true });
document.addEventListener('keydown', (e) => {
  userInteracted = true;
  if (e.key === 'p') { playLine(); return; }
  if (e.key === ' ' && current && !revealed) { e.preventDefault(); reveal(); return; }
  if (revealed && ['1', '2', '3', '4'].includes(e.key)) rate(parseInt(e.key, 10));
});

// Swipe-to-rate once revealed: right = Good, left = Again.
let touchX = null, touchY = null;
cardEl.addEventListener('touchstart', (e) => {
  touchX = e.touches[0].clientX; touchY = e.touches[0].clientY;
}, { passive: true });
cardEl.addEventListener('touchend', (e) => {
  if (touchX === null || !revealed || !current) { touchX = null; return; }
  const dx = e.changedTouches[0].clientX - touchX;
  const dy = e.changedTouches[0].clientY - touchY;
  touchX = null;
  if (Math.abs(dx) > 60 && Math.abs(dy) < 40) rate(dx > 0 ? 3 : 1);
});

// ---- go ----
buildSession(false);
next();
syncRemoteAutoPull(() => {
  srsF = srsLoad(FLASH_SRS_KEY);
  srsQ = srsLoad(QUIZ_SRS_KEY);
  // Only rebuild if the user hasn't started answering yet — never yank a
  // half-finished session out from under them.
  if (tallies[1] + tallies[2] + tallies[3] + tallies[4] === 0) { buildSession(false); next(); }
}, setSyncState);
</script>
</body>
</html>
"""


def main():
    flash = load_decks()
    vocab = load_vocab()
    convos = load_conversations()
    word_items = build_quiz_items(vocab, convos)
    sentence_items = build_sentence_items(convos)
    listening_items = build_listening_items(sentence_items)
    quiz_items = word_items + sentence_items + listening_items
    html = (
        PAGE.replace("__SRS_JS__", SRS_JS)
        .replace("__SYNC_JS__", SYNC_JS)
        .replace("__FLASH__", json.dumps(flash, ensure_ascii=False))
        .replace("__QUIZ__", json.dumps(quiz_items, ensure_ascii=False))
    )
    OUT.write_text(html, encoding="utf-8")
    print(f"wrote {OUT}: {len(flash)} flashcards + {len(quiz_items)} quiz items in the mixed pool")


if __name__ == "__main__":
    main()
