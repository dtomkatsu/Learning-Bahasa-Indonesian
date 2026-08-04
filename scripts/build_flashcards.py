#!/usr/bin/env python3
"""
Build flashcards.html — a self-contained flip-card vocab trainer over every
vocab/*.tsv deck (Indonesian / English+notes / tag / example sentence /
example translation columns, no header).

Every card carries a hand-written example sentence in columns 4 and 5, shown
on the back so the word is always revealed inside a real sentence rather than
as a bare gloss. Cards whose word also occurs in one of the transcripts get
that line too, under a separate "Heard in the recording" heading — authentic
but unedited family speech, kept clearly apart from the clean example.

Uses real spaced repetition — FSRS-5 (see scripts/_srs_js.py), the same
algorithm Anki itself recommends as its default over the older SM-2 family.
Rating is the familiar 4-button Again/Hard/Good/Easy, each showing a preview
of the resulting interval (Anki-style), and only cards that are actually due
get shown. If nothing's due, there's a "practice ahead" fallback rather than
a dead end.

The deck isn't fixed at build time: a "Remove this card" link on the back of
each card hides it (tombstoned in localStorage, restorable), "+ Add card"
lets you type in a single new vocab entry on the fly, and "+ Add list" takes
a pasted block of "front – back" lines (same format as the vocab/*.tsv
source files), optionally grouped into "(tag)"-headed blocks. All of these
are layered on top of the TSV-sourced deck rather than editing it, and all
are included in the sync payload (scripts/_sync_js.py) so deck edits
propagate to other devices the same way review progress does.

Usage:
    python3 build_flashcards.py
"""
import csv
import json
import re
from html import escape as html_escape
from pathlib import Path

from _boost_js import BOOST_JS
from _rhythm_tip import RHYTHM_TIP_TEXT
from _srs_js import SRS_JS
from _sync_js import SYNC_JS
from _record_js import REC_JS
from _tts_js import TTS_JS
from _vocab_js import VOCAB_JS
from _vocab_text import bounded, find_term

ROOT = Path(__file__).resolve().parent.parent
VOCAB_DIR = ROOT / "vocab"
OUT = ROOT / "flashcards.html"

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Flashcards — Learning Bahasa Indonesian</title>
<style>
  :root { color-scheme: light dark; --bg:#fff; --fg:#1a1a1a; --muted:#6b7280; --line:#e5e7eb;
    --accent:#2563eb; --card:#f9fafb;
    --again:#dc2626; --hard:#d97706; --good:#16a34a; --easy:#2563eb; }
  @media (prefers-color-scheme: dark) {
    :root { --bg:#111318; --fg:#e7e9ee; --muted:#9aa1ac; --line:#2a2e37; --accent:#5b9dff;
      --card:#1a1d24; --again:#f87171; --hard:#fbbf24; --good:#4ade80; --easy:#7cb0ff; }
  }
  * { box-sizing:border-box; }
  html, body { margin:0; background:var(--bg); color:var(--fg); height:100%;
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }
  .wrap { max-width:560px; margin:0 auto; padding:28px 20px 60px; }
  .top { display:flex; justify-content:space-between; align-items:baseline; gap:10px; flex-wrap:wrap; margin-bottom:6px; }
  h1 { font-size:1.15rem; margin:0; }
  a.back { color:var(--muted); font-size:0.8rem; text-decoration:none; }
  .stats { color:var(--muted); font-size:0.8rem; margin-bottom:16px; }
  .controls { display:flex; flex-wrap:wrap; gap:8px; margin-bottom:14px; }
  .panel { border:1px solid var(--line); border-radius:10px; background:var(--card);
    padding:12px; margin-bottom:16px; }
  .panel[hidden] { display:none; }
  #searchBox { width:100%; font-size:0.85rem; border-radius:8px; border:1px solid var(--line);
    background:var(--bg); color:var(--fg); padding:8px 10px; margin-bottom:10px; }
  .chips { display:flex; flex-wrap:wrap; gap:6px; }
  button.chip { font-size:0.75rem; padding:5px 10px; border-radius:999px; border:1px solid var(--line);
    background:var(--bg); color:var(--muted); cursor:pointer; }
  button.chip.active { background:var(--accent); border-color:var(--accent); color:#fff; }
  button.chip:hover { border-color:var(--accent); }
  button.chip .n { opacity:0.65; font-size:0.68rem; margin-left:4px; }
  .panelFoot { margin-top:10px; display:flex; justify-content:space-between; align-items:center; gap:8px; }
  .panelFoot .count { color:var(--muted); font-size:0.75rem; }
  .browseList { max-height:58vh; overflow-y:auto; margin:-4px -4px 0; }
  .browseRow { display:flex; justify-content:space-between; gap:10px; align-items:baseline;
    padding:9px 6px; border-bottom:1px solid var(--line); cursor:pointer; }
  .browseRow:last-child { border-bottom:none; }
  .browseRow:hover { background:var(--bg); }
  .browseRow .bmain { min-width:0; }
  .browseRow .bf { font-weight:600; font-size:0.9rem; }
  .browseRow .bb { color:var(--muted); font-size:0.78rem; }
  .browseRow .bs { font-size:0.7rem; white-space:nowrap; flex:0 0 auto; }
  .bs.new { color:var(--accent); }
  .bs.learning { color:var(--hard); }
  .bs.mature { color:var(--good); }
  #card { border:1px solid var(--line); border-radius:14px; background:var(--card);
    min-height:220px; display:flex; align-items:center; justify-content:center; text-align:center;
    padding:28px 20px; cursor:pointer; margin:18px 0; user-select:none; }
  #card .front { font-size:1.5rem; font-weight:600; }
  #card .back { display:none; }
  #card.flipped .front { display:none; }
  #card.flipped .back { display:block; }
  /* The Indonesian is echoed above the answer: you're judging recall at the
     moment you rate, so the pair you're trying to associate has to be on
     screen together rather than the prompt vanishing on flip. */
  #card .back .q { color:var(--muted); font-size:0.95rem; margin-bottom:10px; }
  #card .back .en { font-size:1.25rem; font-weight:600; margin-bottom:6px; }
  #card .back .tag { color:var(--muted); font-size:0.78rem; }
  #card .back .ex, #card .back .heard { margin-top:14px; padding-top:12px;
    border-top:1px dashed var(--line); font-size:0.88rem; line-height:1.5; }
  #card .back .ex b, #card .back .heard b { color:var(--accent); }
  #card .back .ex .exEn, #card .back .heard .exEn { color:var(--muted); font-size:0.8rem; margin-top:3px; }
  #card .back .ex:empty, #card .back .heard:empty { display:none; }
  /* The recording is unedited family speech — often a fragment, sometimes
     mistranscribed. Labelled and dimmed so it reads as evidence, not as the
     model sentence sitting above it. */
  #card .back .heard { color:var(--muted); font-size:0.82rem; }
  #card .back .heard .heardLbl { font-size:0.66rem; letter-spacing:0.06em;
    text-transform:uppercase; opacity:0.75; margin-bottom:4px; }
  #card .back .heard .heardPlay { display:block; margin-top:8px; padding:4px 10px;
    font-size:0.74rem; color:var(--muted); background:none;
    border:1px solid var(--line); border-radius:8px; cursor:pointer; }
  #card .back .heard .heardPlay:hover { color:var(--fg); }
  .playRow { display:flex; align-items:center; gap:10px; justify-content:center;
    margin:-6px 0 14px; }
  button.playBtn { font-size:0.82rem; padding:7px 13px; border-radius:8px;
    border:1px solid var(--accent); background:transparent; color:var(--accent); cursor:pointer; }
  button.playBtn:hover { background:var(--accent); color:#fff; }
  button.playBtn:disabled { border-color:var(--line); color:var(--muted);
    background:transparent; cursor:default; }
  .playNote { color:var(--muted); font-size:0.72rem; }
  /* Say-it-yourself. Sits under the model's play row because the order of
     operations is the point: hear it, say it, then hear both back to back. */
  .sayRow { display:flex; align-items:center; gap:8px; justify-content:center;
    flex-wrap:wrap; margin:-6px 0 12px; }
  .sayRow[hidden] { display:none; }
  button.sayBtn { font-size:0.82rem; padding:7px 13px; border-radius:8px;
    border:1px solid var(--line); background:transparent; color:var(--fg); cursor:pointer; }
  button.sayBtn:hover { border-color:var(--accent); color:var(--accent); }
  button.sayBtn.recording { border-color:var(--again); color:var(--again); }
  button.sayBtn:disabled { opacity:0.45; cursor:default; }
  .sayNote { color:var(--muted); font-size:0.72rem; }
  .sayNote.model { color:var(--accent); }
  .sayNote.you { color:var(--good); }
  .sayTip { max-width:460px; margin:0 auto 16px; padding:9px 12px; border-radius:8px;
    background:var(--card); border:1px solid var(--line); color:var(--muted);
    font-size:0.78rem; line-height:1.5; text-align:left; }
  .sayTip[hidden] { display:none; }
  .sayTip b { color:var(--accent); }
  .sayTip .lbl { display:block; font-size:0.64rem; letter-spacing:0.06em;
    text-transform:uppercase; opacity:0.75; margin-bottom:3px; }
  .rhythmTip { max-width:460px; margin:0 auto 16px; padding:9px 12px; border-radius:8px;
    background:var(--card); border:1px solid var(--line); color:var(--muted);
    font-size:0.78rem; line-height:1.5; text-align:left; }
  .rhythmTip[hidden] { display:none; }
  .rhythmTip b { color:var(--accent); }
  .rhythmTip .lbl { display:block; font-size:0.64rem; letter-spacing:0.06em;
    text-transform:uppercase; opacity:0.75; margin-bottom:3px; }
  .hint { text-align:center; color:var(--muted); font-size:0.78rem; margin-top:-8px; margin-bottom:18px; }
  .rate { display:flex; gap:8px; }
  button.rate-btn { flex:1; padding:10px 4px; border-radius:10px; border:1px solid var(--line);
    background:var(--card); color:var(--fg); font-size:0.85rem; cursor:pointer; display:flex;
    flex-direction:column; align-items:center; gap:2px; }
  button.rate-btn:hover { filter:brightness(1.1); }
  button.rate-btn .prev { font-size:0.7rem; opacity:0.7; }
  button.rate-btn.again { border-color:var(--again); color:var(--again); }
  button.rate-btn.hard { border-color:var(--hard); color:var(--hard); }
  button.rate-btn.good { border-color:var(--good); color:var(--good); }
  button.rate-btn.easy { border-color:var(--easy); color:var(--easy); }
  .rate[hidden] { display:none; }
  /* Sits well clear of the rate buttons and right-aligned rather than centred
     under them — it used to be a full-width tap target directly beneath
     "Again", which is a thumb misfire waiting to happen on a phone. */
  .cardMeta { text-align:right; margin-top:22px; }
  .cardMeta[hidden] { display:none; }
  button.linkBtn { font-size:0.72rem; color:var(--muted); background:none; border:none;
    cursor:pointer; padding:4px; }
  button.linkBtn:hover { color:var(--again); text-decoration:underline; }
  .tools { display:flex; justify-content:space-between; align-items:center; margin-top:24px;
    flex-wrap:wrap; gap:8px; }
  .tools .row { display:flex; gap:8px; flex-wrap:wrap; }
  button.plain { font-size:0.78rem; padding:6px 10px; border-radius:6px; border:1px solid var(--line);
    background:var(--bg); color:var(--muted); cursor:pointer; }
  button.plain:disabled { opacity:0.4; cursor:default; }
  button.plain.active { border-color:var(--accent); color:var(--accent); }
  button.plain.danger:hover { border-color:var(--again); color:var(--again); }
  .empty { color:var(--muted); font-size:0.9rem; text-align:center; margin-top:20px; }
  .empty .sub { font-size:0.8rem; margin-top:6px; }
  .empty button.plain { margin-top:14px; }

  #addForm, #bulkForm { border:1px solid var(--line); border-radius:10px; background:var(--card);
    padding:14px; margin:0 0 16px; }
  #addForm[hidden], #bulkForm[hidden] { display:none; }
  #addForm input, #bulkForm textarea { width:100%; margin-bottom:8px; font-size:0.85rem; border-radius:8px;
    border:1px solid var(--line); background:var(--bg); color:var(--fg); padding:8px 10px; }
  #bulkForm textarea { font-family:ui-monospace,SFMono-Regular,Menlo,monospace; min-height:160px; resize:vertical; }
  #bulkForm .hint2 { font-size:0.75rem; color:var(--muted); margin:-4px 0 8px; }
  #addForm .row, #bulkForm .row { display:flex; gap:8px; }
</style>
</head>
<body>
<div class="wrap">
  <div class="top">
    <h1>Flashcards</h1>
    <a class="back" href="index.html">&larr; all conversations</a>
  </div>
  <div class="stats" id="stats"></div>
  <div class="controls">
    <button class="plain" id="filterToggleBtn">Filter</button>
    <button class="plain" id="browseToggleBtn">Browse</button>
    <button class="plain" id="addToggleBtn">+ Card</button>
    <button class="plain" id="bulkToggleBtn">+ List</button>
  </div>
  <div class="panel" id="filterPanel" hidden>
    <input id="searchBox" placeholder="Search Indonesian or English…">
    <div class="chips" id="tagChips"></div>
    <div class="panelFoot">
      <span class="count" id="filterCount"></span>
      <button class="plain" id="clearFilterBtn">Clear filters</button>
    </div>
  </div>
  <div class="panel" id="browsePanel" hidden>
    <div class="browseList" id="browseList"></div>
    <div class="panelFoot">
      <span class="count" id="browseCount"></span>
      <button class="plain" id="browseCloseBtn">Close</button>
    </div>
  </div>
  <div id="addForm" hidden>
    <input id="addFront" placeholder="Indonesian (e.g. kayaknya)">
    <input id="addBack" placeholder="English / notes">
    <input id="addTag" placeholder="tags, comma-separated (optional — defaults to “custom”)">
    <div class="row">
      <button class="plain" id="addSaveBtn">Save card</button>
      <button class="plain" id="addCancelBtn">Cancel</button>
    </div>
  </div>
  <div id="bulkForm" hidden>
    <div class="hint2">One per line: <code>front – back</code>. Start a block with <code>(tag)</code> to
      tag everything below it until the next blank line or <code>(tag)</code> — blocks without one default
      to “custom”. Words that already exist in the deck get the new tag added rather than duplicated.</div>
    <textarea id="bulkText" placeholder="(comparison)
lebih – more
kurang – less / not enough
paling – most

(connector)
dan – and
atau – or"></textarea>
    <div class="row">
      <button class="plain" id="bulkSaveBtn">Import list</button>
      <button class="plain" id="bulkCancelBtn">Cancel</button>
    </div>
  </div>
  <div id="card"><div class="front"></div><div class="back"><div class="q"></div><div class="en"></div><div class="tag"></div><div class="ex"></div><div class="heard"></div></div></div>
  <div class="playRow">
    <button class="playBtn" id="playBtn">&#9654; Hear it</button>
    <span class="playNote" id="playNote"></span>
  </div>
  <div class="sayRow" id="sayRow" hidden>
    <button class="sayBtn" id="recBtn">&#127908; Say it</button>
    <button class="sayBtn" id="cmpBtn" disabled>&#8646; Compare</button>
    <span class="sayNote" id="sayNote"></span>
  </div>
  <div class="sayTip" id="sayTip" hidden></div>
  <div class="rhythmTip" id="rhythmTip" hidden><span class="lbl">Sentence rhythm</span>__RHYTHM_TIP__</div>
  <div class="hint" id="hint"></div>
  <div class="rate" id="rateRow" hidden>
    <button class="rate-btn again" id="btn1"><span class="lbl">Again</span><span class="prev" id="prev1"></span></button>
    <button class="rate-btn hard" id="btn2"><span class="lbl">Hard</span><span class="prev" id="prev2"></span></button>
    <button class="rate-btn good" id="btn3"><span class="lbl">Good</span><span class="prev" id="prev3"></span></button>
    <button class="rate-btn easy" id="btn4"><span class="lbl">Easy</span><span class="prev" id="prev4"></span></button>
  </div>
  <div class="cardMeta" id="cardMeta" hidden>
    <button class="linkBtn" id="removeBtn">Remove card</button>
  </div>
  <audio id="cardAudio" preload="none"></audio>
  <div class="tools">
    <div class="row">
      <button class="plain" id="undoBtn" disabled>&#8630; Go back</button>
      <button class="plain" id="restoreBtn">Restore removed (0)</button>
    </div>
    <div class="row">
      <span class="stats" id="syncState"></span>
      <span class="stats" id="deckInfo"></span>
      <button class="plain danger" id="resetBtn">Reset progress</button>
    </div>
  </div>
</div>
<script>
__SRS_JS__
__SYNC_JS__
__TTS_JS__
__REC_JS__
__BOOST_JS__
const BUILTIN_DECK = __DATA__;
const SRS_KEY = 'bahasa:flashcards:fsrs:v1';
const LEGACY_KEYS = ['bahasa:flashcards:v1', 'bahasa:flashcards:srs:v1'];

let srs = srsMigrateLegacy(SRS_KEY, LEGACY_KEYS);

// The deck isn't just BUILTIN_DECK: removed cards are tombstoned out and
// custom cards are layered in (a custom card with the same front as a
// built-in one edits it in place, since it wins the Map merge below).
function loadRemovedCards() { return syncRead(REMOVED_CARDS_KEY); }
function loadCustomCards() { return syncRead(CUSTOM_CARDS_KEY); }
// Cards carry a `tags` array; older custom cards (and imports from an older
// device) may still have a single `tag` string — normalize on read.
function normalizeCard(d) {
  if (Array.isArray(d.tags) && d.tags.length) return d;
  return Object.assign({}, d, { tags: d.tag ? [d.tag] : ['custom'] });
}
function computeDeck() {
  const removed = loadRemovedCards();
  const custom = loadCustomCards();
  const byFront = new Map();
  BUILTIN_DECK.forEach(d => { if (!removed[d.front]) byFront.set(d.front, d); });
  Object.values(custom).forEach(d => byFront.set(d.front, normalizeCard(d)));
  return [...byFront.values()];
}
let DECK = computeDeck();

let pool = DECK.slice();
let current = null;
let flipped = false;
let practiceAhead = false;

function setSyncState(s) {
  const el = document.getElementById('syncState');
  if (!syncRemoteConfigured()) { el.textContent = ''; return; }
  el.textContent = s === 'pending' ? 'syncing…' : s === 'err' ? 'sync failed' : 'synced ✓';
}

const cardEl = document.getElementById('card');
const rateRow = document.getElementById('rateRow');
const cardMeta = document.getElementById('cardMeta');
const chipsEl = document.getElementById('tagChips');

// Multi-select category chips. None selected = whole deck; any selected =
// union of those categories (a card matches if it carries ANY active tag,
// so cross-tagged cards let categories mix).
let activeTags = new Set();
let searchTerm = '';

function escapeHtml(s) {
  return String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
}

function uniqueTags() {
  return [...new Set(DECK.flatMap(d => d.tags))].sort();
}
function tagCount(t) {
  return DECK.filter(d => d.tags.includes(t)).length;
}
function renderChips() {
  const tags = uniqueTags();
  activeTags = new Set([...activeTags].filter(t => tags.includes(t)));
  chipsEl.innerHTML = tags.map(t =>
    `<button class="chip${activeTags.has(t) ? ' active' : ''}" data-tag="${escapeHtml(t)}">` +
    `${escapeHtml(t)}<span class="n">${tagCount(t)}</span></button>`).join('');
  chipsEl.querySelectorAll('.chip').forEach(b => {
    b.addEventListener('click', () => {
      const t = b.dataset.tag;
      if (activeTags.has(t)) activeTags.delete(t); else activeTags.add(t);
      b.classList.toggle('active');
      practiceAhead = false;
      afterFilterChange(true);
    });
  });
}
renderChips();

function matchesSearch(d) {
  if (!searchTerm) return true;
  return (d.front + ' ' + d.back).toLowerCase().includes(searchTerm);
}

function applyFilter() {
  pool = DECK.filter(d =>
    (!activeTags.size || d.tags.some(t => activeTags.has(t))) && matchesSearch(d));
  updateFilterChrome();
}

function activeFilterCount() { return activeTags.size + (searchTerm ? 1 : 0); }

function updateFilterChrome() {
  const n = activeFilterCount();
  const btn = document.getElementById('filterToggleBtn');
  btn.textContent = n ? 'Filter · ' + n : 'Filter';
  btn.classList.toggle('active', n > 0);
  document.getElementById('filterCount').textContent =
    pool.length + ' of ' + DECK.length + ' cards match';
}

// Chips are an explicit "show me this category" action, so they always draw a
// fresh card. Typing in the search box shouldn't yank the current card away
// mid-word, so it only re-picks once the card on screen stops matching.
function afterFilterChange(forcePick) {
  srsClearForward();
  applyFilter();
  if (!document.getElementById('browsePanel').hidden) renderBrowse();
  if (forcePick || !current || !pool.some(d => d.front === current.front)) pickNext();
  else renderStats();
}
applyFilter();

// Re-derive the deck after a local edit (add/remove) or a remote sync pull
// that may have brought in edits made on another device.
function refreshDeck() {
  srsClearForward();
  DECK = computeDeck();
  renderChips();
  updateRestoreCount();
  applyFilter();
  pickNext();
}

// Pull any progress made on another device, then refresh what's on screen.
syncRemoteAutoPull(() => {
  srs = srsLoad(SRS_KEY);
  refreshDeck();
}, setSyncState);

function dueIn(items) { return items.filter(d => srsIsDue(srs[d.front])); }

function pickNext() {
  if (!pool.length) { renderEmpty('No cards for this tag.'); return; }
  // If an undo displaced a card, give that one back rather than drawing a
  // fresh random one — otherwise "Go back" loses your place in the deck.
  const queued = srsTakeForward(c => pool.find(d => d.front === c.front));
  if (queued) { showCard(queued); return; }
  // Reviews first, then any brand-new card; practice-ahead ignores the
  // schedule entirely once even that pool is exhausted.
  const reviews = pool.filter(d => srs[d.front] && srsIsDue(srs[d.front]));
  const freshAll = pool.filter(d => !srs[d.front]);
  let due = reviews.length ? reviews : freshAll;
  if (practiceAhead && !due.length) due = pool;
  if (!due.length) { renderAllCaughtUp(); return; }
  let next = due[Math.floor(Math.random() * due.length)];
  if (due.length > 1 && current && next.front === current.front) next = due[Math.floor(Math.random() * due.length)];
  showCard(next);
}

// Split out of pickNext so undo can put a specific card back on screen
// instead of drawing a fresh random one.
function showCard(card) {
  current = card;
  flipped = false;
  cardEl.className = '';
  cardEl.innerHTML = '<div class="front"></div><div class="back"><div class="q"></div>' +
    '<div class="en"></div><div class="tag"></div><div class="ex"></div><div class="heard"></div></div>';
  cardEl.querySelector('.front').textContent = current.front;
  cardEl.querySelector('.q').textContent = current.front;
  cardEl.querySelector('.en').textContent = current.back;
  cardEl.querySelector('.tag').textContent = current.tags.join(' · ');
  // Both the written example and the real line are back-only, so neither can
  // give the answer away before you've committed to one.
  if (current.exampleHtml) {
    cardEl.querySelector('.ex').innerHTML = current.exampleHtml +
      (current.exampleEn ? `<div class="exEn">${escapeHtml(current.exampleEn)}</div>` : '');
  }
  if (current.sentenceHtml) {
    // The quote keeps its own play control: when a clearer clip owns the main
    // button, this is where the family's actual voice stays one tap away.
    cardEl.querySelector('.heard').innerHTML = '<div class="heardLbl">Heard in the recording</div>' +
      current.sentenceHtml +
      (current.exTranslation ? `<div class="exEn">${escapeHtml(current.exTranslation)}</div>` : '') +
      (current.audio && modelSrc()
        ? '<button type="button" class="heardPlay">&#9654; play the family clip</button>' : '');
    const hp = cardEl.querySelector('.heardPlay');
    if (hp) hp.addEventListener('click', e => {
      e.stopPropagation();                    // the card itself flips on click
      if (!cardAudio.paused) { cardAudio.pause(); stopAt = null; return; }
      playFamilyClip();
    });
  }
  rateRow.hidden = true;
  cardMeta.hidden = true;
  stopAudio();
  resetSay();
  updatePlayRow();
  renderStats();
}

function renderEmpty(msg) {
  current = null;
  stopAudio();
  updatePlayRow();
  cardEl.innerHTML = `<div class="empty">${msg}</div>`;
  rateRow.hidden = true;
}

function renderAllCaughtUp() {
  current = null;
  stopAudio();
  updatePlayRow();
  const now = Date.now();
  const dues = pool.map(d => (srs[d.front] && srs[d.front].due) || Infinity);
  const nextDue = Math.min(...dues);
  const in24h = pool.filter(d => srs[d.front] && srs[d.front].due > now && srs[d.front].due <= now + 86400000).length;
  cardEl.innerHTML = `<div class="empty">🎉 All caught up!<div class="sub">Next review in ${srsFmtDue(nextDue)}${in24h ? ` · ${in24h} due within 24h` : ''}.</div>` +
    `<button class="plain" id="aheadBtn">Practice ahead anyway</button></div>`;
  rateRow.hidden = true;
  cardMeta.hidden = true;
  document.getElementById('aheadBtn').addEventListener('click', () => { practiceAhead = true; pickNext(); });
  renderStats();
}

function renderStats() {
  // Deliberately whole-deck, ignoring the tag filter (matches quiz.html's
  // pattern) — deckInfo below is where the filtered count lives, so these
  // numbers stay internally consistent regardless of what's selected.
  const dueReviews = DECK.filter(d => srs[d.front] && srsIsDue(srs[d.front])).length;
  const fresh = DECK.filter(d => !srs[d.front]).length;
  const mature = DECK.filter(d => srsIsMature(srs[d.front])).length;
  document.getElementById('stats').textContent =
    `${DECK.length} cards — ${dueReviews} to review, ${fresh} new, ${mature} mastered (21d+)`;
  document.getElementById('deckInfo').textContent = pool.length + ' in current filter';
}

function updatePreviews() {
  if (!current) return;
  const labels = fsrsPreviewLabels(srs[current.front], Date.now());
  for (let g = 1; g <= 4; g++) document.getElementById('prev' + g).textContent = labels[g];
}

function flip() {
  if (!current) return;
  flipped = !flipped;
  cardEl.classList.toggle('flipped', flipped);
  rateRow.hidden = !flipped;
  cardMeta.hidden = !flipped;
  updatePlayRow();          // what "Hear it" says changes once the sentence is visible
  updateSayRow();
  if (flipped) updatePreviews();
}

function rate(grade) {
  if (!current) return;
  const isNew = !srs[current.front];
  const ts = srsLogReview('flash', grade, isNew, current.front);
  srsPushUndo({ card: current, front: current.front, prev: srs[current.front] || null, ts });
  srs[current.front] = fsrsNextState(srs[current.front], grade, Date.now());
  srsSave(SRS_KEY, srs);
  syncRemoteQueuePush(setSyncState);
  practiceAhead = false;
  updateUndoBtn();
  pickNext();
}

// Undo puts the card back exactly as it was: its previous schedule (or no
// schedule at all, if that rating was its first) and no review-log entry.
function undoLast() {
  const u = srsPopUndo();
  if (!u) return;
  // Remember what was on screen, so re-rating the restored card returns you
  // to it instead of a random draw.
  srsPushForward(current);
  const restored = srsRestoreState(u.prev);
  if (restored) srs[u.front] = restored; else delete srs[u.front];
  srsSave(SRS_KEY, srs);
  srsUnlogReview(u.ts);
  syncRemoteQueuePush(setSyncState);
  practiceAhead = false;
  updateUndoBtn();
  showCard(u.card);
}

function updateUndoBtn() {
  document.getElementById('undoBtn').disabled = !srsUndoDepth();
}

// ---- Browse ---------------------------------------------------------------
// A list view over the current filter, so a 274-card deck is something you can
// actually look at rather than only meeting one card at a time. Rows show
// scheduling state; clicking one jumps straight to studying that card.
function cardStateLabel(front) {
  const s = srs[front];
  if (!s) return { txt: 'new', cls: 'new' };
  if (srsIsMature(s)) return { txt: 'mastered · ' + srsFmtDue(s.due), cls: 'mature' };
  return { txt: srsIsDue(s) ? 'due now' : 'in ' + srsFmtDue(s.due), cls: 'learning' };
}

function renderBrowse() {
  const listEl = document.getElementById('browseList');
  if (!pool.length) {
    listEl.innerHTML = '<div class="empty">Nothing matches.</div>';
  } else {
    listEl.innerHTML = pool.map((d, i) => {
      const st = cardStateLabel(d.front);
      return `<div class="browseRow" data-i="${i}">` +
        `<div class="bmain"><div class="bf">${escapeHtml(d.front)}</div>` +
        `<div class="bb">${escapeHtml(d.back)}</div></div>` +
        `<div class="bs ${st.cls}">${escapeHtml(st.txt)}</div></div>`;
    }).join('');
    listEl.querySelectorAll('.browseRow').forEach(r => {
      r.addEventListener('click', () => {
        const card = pool[Number(r.dataset.i)];
        closePanels();
        showCard(card);
      });
    });
  }
  document.getElementById('browseCount').textContent =
    pool.length + (pool.length === 1 ? ' card' : ' cards');
}

// ---- Panels ---------------------------------------------------------------
// Filter / Browse / Add card / Add list are mutually exclusive so they never
// stack up and push the card off screen.
const PANEL_IDS = ['filterPanel', 'browsePanel', 'addForm', 'bulkForm'];

function closePanels(except) {
  PANEL_IDS.forEach(id => {
    if (id !== except) document.getElementById(id).hidden = true;
  });
  document.getElementById('browseToggleBtn')
    .classList.toggle('active', except === 'browsePanel');
}

function togglePanel(id) {
  const el = document.getElementById(id);
  const willOpen = el.hidden;
  closePanels(willOpen ? id : null);
  el.hidden = !willOpen;
  if (id === 'browsePanel' && willOpen) renderBrowse();
  document.getElementById('browseToggleBtn')
    .classList.toggle('active', id === 'browsePanel' && willOpen);
  return willOpen;
}

// ---- Audio -----------------------------------------------------------------
// Up to four sources per card, deliberately distinguishable — and since the
// 2026-08 retool, ordered by how good a *model* they are rather than by
// authenticity. The family recordings are phone audio captured across rooms:
// unbeatable as comprehension material, but often too faint to imitate. So
// "Hear it" now prefers a clear clip (a real Lingua Libre volunteer where one
// exists, else the generated studio voice), and the family line is kept as a
// separately-played quote under "Heard in the recording" — demoted, never
// hidden, and each source still says plainly what it is.
const cardAudio = document.getElementById('cardAudio');
const playBtn = document.getElementById('playBtn');
const playNote = document.getElementById('playNote');
let stopAt = null;
boostAttach(cardAudio);

cardAudio.addEventListener('timeupdate', () => {
  if (stopAt !== null && cardAudio.currentTime >= stopAt) { cardAudio.pause(); stopAt = null; }
});

ttsOnVoicesChanged(updatePlayRow);

// Before the flip you're recalling the word, so the word is the useful
// prompt; after it, the sentence is what's worth modelling. Returns the
// clearest clip for whichever that is — a volunteer's real voice beats the
// studio voice for a single word — or '' when there isn't one.
function modelSrc() {
  if (!current) return '';
  if (flipped && current.exampleSrc) return current.exampleSrc;
  if (!flipped && (current.llSrc || current.wordSrc)) return current.llSrc || current.wordSrc;
  return (current.llSrc || current.wordSrc || current.exampleSrc || '');
}

function updatePlayRow() {
  if (!current) { playBtn.disabled = true; playNote.textContent = ''; return; }
  const src = modelSrc();
  if (src) {
    // A clear clip is the model to imitate, but it is still not these people —
    // one label per source, so none can be mistaken for another.
    playBtn.disabled = false;
    playBtn.innerHTML = '&#128266; Hear it';
    if (!flipped && current.llSrc) {
      playNote.textContent = 'real voice — a volunteer, not the family';
    } else {
      playNote.textContent = flipped && current.exampleSrc
        ? 'example sentence · studio voice, not the family'
        : 'studio voice — not the family';
    }
  } else if (current.audio) {
    playBtn.disabled = false;
    playBtn.innerHTML = '&#9654; Hear it';
    playNote.textContent = 'real recording — may be faint';
  } else if (ttsVoice) {
    playBtn.disabled = false;
    playBtn.innerHTML = '&#128266; Hear it';
    // Once flipped there's a whole sentence worth hearing, not just the word.
    playNote.textContent = flipped && current.example
      ? 'example sentence · synthesized'
      : 'synthesized — not from the recording';
  } else {
    playBtn.disabled = true;
    playBtn.innerHTML = '&#128266; Hear it';
    playNote.textContent = ttsUnavailableNote();
  }
}

function stopAudio() {
  cardAudio.pause();
  stopAt = null;
  ttsStop();
}

function playCurrent() {
  if (!current) return;
  if (modelSrc()) {
    cardAudio.pause();
    stopAt = null;
    ttsSay(flipped && current.example ? current.example : current.front, modelSrc());
    return;
  }
  if (current.audio) {
    ttsStop();
    if (!cardAudio.paused) { cardAudio.pause(); stopAt = null; return; }
    playFamilyClip();
    return;
  }
  cardAudio.pause();
  ttsSay(flipped && current.example ? current.example : current.front, '');
}

// Same audio as "Hear it", but always plays from the start and resolves when
// it's done — the compare loop has to know when the model has stopped talking
// before it plays your attempt back.
function playModel() {
  if (!current) return Promise.resolve();
  if (modelSrc() || !current.audio) {
    cardAudio.pause();
    return ttsSay(flipped && current.example ? current.example : current.front, modelSrc());
  }
  return playFamilyClip();
}

// The family's own line, played as a clip: from this card's timestamp to the
// next line's. Kept even where a clearer model exists — hearing how the word
// sounds inside this family's real speech is the project's whole point; it's
// just no longer the audio you're asked to imitate.
function playFamilyClip() {
  if (!current || !current.audio) return Promise.resolve();
  ttsStop();
  return new Promise(resolve => {
    let settled = false;
    const finish = () => {
      if (settled) return;
      settled = true;
      cardAudio.removeEventListener('pause', finish);
      cardAudio.removeEventListener('ended', finish);
      resolve();
    };
    // The timeupdate handler above pauses at nextSec, which fires 'pause' —
    // so clip-end and user-interruption settle through the same path.
    cardAudio.addEventListener('pause', finish);
    cardAudio.addEventListener('ended', finish);
    stopAt = current.nextSec;
    const start = () => {
      cardAudio.currentTime = current.sec;
      cardAudio.play().catch(finish);
    };
    if (cardAudio.src.endsWith(current.audio) && cardAudio.readyState >= 1) {
      start();
    } else {
      cardAudio.src = current.audio;
      cardAudio.addEventListener('loadedmetadata', start, { once: true });
      cardAudio.load();
    }
  });
}

// ---- Say it yourself -------------------------------------------------------
// Record, then hear the model and your attempt back to back. No score: there
// is no honest way to grade Indonesian pronunciation in a browser today (see
// notes/elevenlabs-pronunciation-scope.md), and the research this is built on
// says what actually helps is adjacency plus being told what to listen for —
// which is what sayTip carries. The clip never leaves the page.
const sayRow = document.getElementById('sayRow');
const sayTipEl = document.getElementById('sayTip');
const rhythmTipEl = document.getElementById('rhythmTip');
const sayNote = document.getElementById('sayNote');
const recBtn = document.getElementById('recBtn');
const cmpBtn = document.getElementById('cmpBtn');
let comparing = false;

function updateSayRow() {
  // Back of the card only: on the front you're still trying to recall the
  // word, and a microphone button there would just give the answer away.
  const show = recSupported && flipped && !!current;
  sayRow.hidden = !show;
  sayTipEl.hidden = !(show && current && current.sayTip);
  if (show && current && current.sayTip) {
    sayTipEl.innerHTML = '<span class="lbl">Listen for</span>' + current.sayTip;
  }
  cmpBtn.disabled = !recHasClip() || comparing;
  recBtn.disabled = comparing;
  // Independent of mic support — useful whether or not you can record, since
  // it applies to reading/listening/shadowing the sentence too, not just the
  // compare loop.
  rhythmTipEl.hidden = !(flipped && current && current.example);
}

function resetSay() {
  comparing = false;
  recClear();
  recBtn.classList.remove('recording');
  recBtn.innerHTML = '&#127908; Say it';
  sayNote.textContent = '';
  sayNote.className = 'sayNote';
  updateSayRow();
}

async function toggleRecord() {
  if (comparing) return;
  if (recIsRecording()) {
    recBtn.disabled = true;
    const url = await recStop();
    recBtn.disabled = false;
    recBtn.classList.remove('recording');
    recBtn.innerHTML = '&#127908; Again';
    sayNote.textContent = url ? 'recorded — now compare' : 'nothing recorded';
    sayNote.className = 'sayNote';
    updateSayRow();
    if (url) compareSay();
    return;
  }
  stopAudio();
  const ok = await recStart();
  if (!ok) {
    sayNote.textContent = 'microphone unavailable';
    sayNote.className = 'sayNote';
    return;
  }
  recBtn.classList.add('recording');
  recBtn.innerHTML = '&#9209; Stop';
  sayNote.textContent = 'listening…';
  sayNote.className = 'sayNote';
  updateSayRow();
}

async function compareSay() {
  if (!recHasClip() || comparing) return;
  comparing = true;
  updateSayRow();
  await recCompare(playModel, step => {
    if (step === 'model') { sayNote.textContent = 'the model'; sayNote.className = 'sayNote model'; }
    else if (step === 'you') { sayNote.textContent = 'you'; sayNote.className = 'sayNote you'; }
    else { sayNote.textContent = 'again?'; sayNote.className = 'sayNote'; }
  });
  comparing = false;
  updateSayRow();
}

recBtn.addEventListener('click', toggleRecord);
cmpBtn.addEventListener('click', compareSay);

function renderHint() {
  document.getElementById('hint').textContent = srsIsTouch()
    ? 'Tap the card to flip · swipe right = Good, left = Again'
    : 'Click the card (or press space) to flip · “p” to hear it · “z” to go back';
}

function updateRestoreCount() {
  document.getElementById('restoreBtn').textContent =
    `Restore removed (${Object.keys(loadRemovedCards()).length})`;
}

function removeCurrentCard() {
  if (!current) return;
  const front = current.front;
  const custom = loadCustomCards();
  const isCustom = !!custom[front];
  const msg = isCustom
    ? `Delete your custom card "${front}"? This can't be undone.`
    : `Remove "${front}" from your deck? You can bring it back later with "Restore removed".`;
  if (!confirm(msg)) return;
  if (isCustom) {
    delete custom[front];
    syncWrite(CUSTOM_CARDS_KEY, custom);
  } else {
    const removed = loadRemovedCards();
    removed[front] = true;
    syncWrite(REMOVED_CARDS_KEY, removed);
  }
  delete srs[front];
  srsSave(SRS_KEY, srs);
  syncRemoteQueuePush(setSyncState);
  refreshDeck();
}

function addCustomCard(front, back, tagsRaw) {
  front = front.trim(); back = back.trim();
  const tags = (tagsRaw || '').split(',').map(t => t.trim()).filter(Boolean);
  if (!tags.length) tags.push('custom');
  if (!front || !back) return false;
  const custom = loadCustomCards();
  custom[front] = { front, back, tags, updatedAt: Date.now() };
  syncWrite(CUSTOM_CARDS_KEY, custom);
  // If this front was previously removed (a built-in card), un-tombstone it —
  // saving a card with that name is an explicit signal to bring it back.
  const removed = loadRemovedCards();
  if (removed[front]) { delete removed[front]; syncWrite(REMOVED_CARDS_KEY, removed); }
  syncRemoteQueuePush(setSyncState);
  return true;
}

__VOCAB_JS__

// Same collision rule as manual TSV edits: a front that already exists
// anywhere in the deck (built-in or custom) gets the new tag(s) merged onto
// its existing row instead of being duplicated or having its back overwritten.
function addBulkCards(entries) {
  if (!entries.length) return { added: 0, retagged: 0 };
  const custom = loadCustomCards();
  const removed = loadRemovedCards();
  let added = 0, retagged = 0;
  for (const e of entries) {
    const existing = DECK.find(d => d.front === e.front);
    if (existing) {
      const mergedTags = [...new Set([...existing.tags, ...e.tags])];
      custom[e.front] = { front: e.front, back: existing.back, tags: mergedTags, updatedAt: Date.now() };
      retagged++;
    } else {
      custom[e.front] = { front: e.front, back: e.back, tags: e.tags, updatedAt: Date.now() };
      added++;
    }
    if (removed[e.front]) delete removed[e.front];
  }
  syncWrite(CUSTOM_CARDS_KEY, custom);
  syncWrite(REMOVED_CARDS_KEY, removed);
  syncRemoteQueuePush(setSyncState);
  return { added, retagged };
}

cardEl.addEventListener('click', flip);
[1, 2, 3, 4].forEach(g => {
  document.getElementById('btn' + g).addEventListener('click', (e) => { e.stopPropagation(); rate(g); });
});
document.getElementById('removeBtn').addEventListener('click', removeCurrentCard);
document.getElementById('undoBtn').addEventListener('click', undoLast);
playBtn.addEventListener('click', (e) => { e.stopPropagation(); playCurrent(); });
document.getElementById('resetBtn').addEventListener('click', () => {
  if (confirm('Reset all flashcard progress (review history and due dates)?')) { srs = {}; srsSave(SRS_KEY, srs); srsClearForward(); pickNext(); }
});
document.getElementById('restoreBtn').addEventListener('click', () => {
  const n = Object.keys(loadRemovedCards()).length;
  if (!n) return;
  if (!confirm(`Restore ${n} removed card(s)?`)) return;
  syncWrite(REMOVED_CARDS_KEY, {});
  syncRemoteQueuePush(setSyncState);
  refreshDeck();
});

const addForm = document.getElementById('addForm');
document.getElementById('addToggleBtn').addEventListener('click', () => {
  if (togglePanel('addForm')) document.getElementById('addFront').focus();
});
document.getElementById('addCancelBtn').addEventListener('click', () => { addForm.hidden = true; });
document.getElementById('addSaveBtn').addEventListener('click', () => {
  const front = document.getElementById('addFront').value;
  const back = document.getElementById('addBack').value;
  const tag = document.getElementById('addTag').value;
  if (!addCustomCard(front, back, tag)) {
    alert('Enter both the Indonesian term and an English gloss.');
    return;
  }
  document.getElementById('addFront').value = '';
  document.getElementById('addBack').value = '';
  document.getElementById('addTag').value = '';
  addForm.hidden = true;
  refreshDeck();
});

const bulkForm = document.getElementById('bulkForm');
document.getElementById('bulkToggleBtn').addEventListener('click', () => {
  if (togglePanel('bulkForm')) document.getElementById('bulkText').focus();
});

document.getElementById('filterToggleBtn').addEventListener('click', () => togglePanel('filterPanel'));
document.getElementById('browseToggleBtn').addEventListener('click', () => togglePanel('browsePanel'));
document.getElementById('browseCloseBtn').addEventListener('click', () => closePanels());

const searchBox = document.getElementById('searchBox');
searchBox.addEventListener('input', () => {
  searchTerm = searchBox.value.trim().toLowerCase();
  practiceAhead = false;
  afterFilterChange(false);
});
document.getElementById('clearFilterBtn').addEventListener('click', () => {
  activeTags.clear();
  searchTerm = '';
  searchBox.value = '';
  practiceAhead = false;
  renderChips();
  afterFilterChange(true);
});
document.getElementById('bulkCancelBtn').addEventListener('click', () => { bulkForm.hidden = true; });
document.getElementById('bulkSaveBtn').addEventListener('click', () => {
  const entries = parseBulkVocab(document.getElementById('bulkText').value);
  if (!entries.length) {
    alert('No valid lines found. Use the format:\\n\\nfront – back\\n\\noptionally starting a block with (tag).');
    return;
  }
  const { added, retagged } = addBulkCards(entries);
  document.getElementById('bulkText').value = '';
  bulkForm.hidden = true;
  refreshDeck();
  alert(`Added ${added} new card(s)` + (retagged ? `, retagged ${retagged} existing word(s).` : '.'));
});

document.addEventListener('keydown', (e) => {
  if (document.activeElement && document.activeElement.tagName === 'INPUT') return;
  if (e.key === ' ') { e.preventDefault(); flip(); }
  else if (e.key === 'p') playCurrent();
  else if (e.key === 'z') undoLast();
  else if (flipped && ['1','2','3','4'].includes(e.key)) rate(parseInt(e.key, 10));
});

// Swipe-to-rate on touch devices: once flipped, swipe the card right for
// Good, left for Again (the two ratings that cover ~95% of real answers).
let touchX = null, touchY = null;
cardEl.addEventListener('touchstart', (e) => {
  touchX = e.touches[0].clientX; touchY = e.touches[0].clientY;
}, { passive: true });
cardEl.addEventListener('touchend', (e) => {
  if (touchX === null || !flipped || !current) { touchX = null; return; }
  const dx = e.changedTouches[0].clientX - touchX;
  const dy = e.changedTouches[0].clientY - touchY;
  touchX = null;
  if (Math.abs(dx) > 60 && Math.abs(dy) < 40) rate(dx > 0 ? 3 : 1);
});

// On a phone the chip row is the single biggest thing between you and a card
// (15 categories wrap to ~7 rows), so it starts collapsed on any narrow
// screen. Wide windows have the room, so leave it open there.
if (!srsIsTouch() && !srsIsNarrow()) document.getElementById('filterPanel').hidden = false;
renderHint();
updatePlayRow();
updateRestoreCount();
pickNext();
</script>
</body>
</html>
"""


def parse_tags(raw):
    """Tag column is a comma-separated list ("emotion,adjective"); a plain
    single tag is just the one-element case."""
    tags = [t.strip() for t in raw.split(",") if t.strip()]
    return tags or ["untagged"]


# --- directed-attention prompts for the say-it-yourself loop ----------------
#
# Free-form "does that sound right?" is the thing the self-assessment research
# says learners are bad at; being told which single feature to listen for is
# what makes the comparison work. These cover the trouble spots documented for
# English speakers learning Indonesian (see notes/pronunciation-training-scope.md
# §3) and are matched off spelling, most-specific first.
#
# Deliberately absent: the pepet/taling <e> split (schwa vs clear e), which is
# the biggest single difficulty and the one thing spelling *cannot* tell you —
# both are written <e> with no diacritic. Guessing would teach the wrong vowel
# half the time, so those cards get no tip until the contrast deck exists to
# mark them by hand.
SAY_TIPS = [
    (re.compile(r"^ng", re.I),
     "Starts with <b>ng-</b>. English only has this sound at the <i>end</i> of a word "
     "(“sing”) — here it opens the word, with no hard g after it."),
    (re.compile(r"^ny", re.I),
     "Starts with <b>ny-</b>. Like the middle of “canyon”, but at the front — "
     "one sound, not n + y."),
    (re.compile(r"k$", re.I),
     "Ends in <b>-k</b>, which is a glottal stop: the sound is cut off in the throat, "
     "not released the way English releases the k in “back”."),
    (re.compile(r"^[ptk]", re.I),
     "Starts with <b>p/t/k</b> — no puff of air. English aspirates these "
     "(“pot”, “top”, “cat”); Indonesian doesn't."),
    # The single most-documented English-L1 trouble spot in this project's own
    # research (notes/pronunciation-training-scope.md §3) had no rule here at
    # all until 2026-08-03 — found by checking coverage, not assumed present.
    # Placed above the generic final-vowel rule (which is inferred, not cited)
    # since this is the specific, documented case; below ng-/ny-/final-k/
    # initial-ptk since those are more locally salient when they also apply.
    # Can't detect the sound from spelling — Indonesian orthography doesn't
    # mark pepet vs. taling, both are just "e" — so the tip names the
    # ambiguity itself rather than claiming a sound the text can't confirm.
    (re.compile(r"e", re.I),
     "Contains <b>e</b>, which hides two different sounds: pepet (a schwa, "
     "like the ‘a’ in “sofa”) and taling (a clear <i>é</i>, like “day”). "
     "Spelling doesn't tell you which — listen for the one this word actually "
     "uses rather than guessing."),
    (re.compile(r"[aiueo]$", re.I),
     "Ends in a vowel — keep it full and clean. English would weaken a final "
     "unstressed vowel toward “uh”; Indonesian vowels stay the same everywhere."),
]


def say_tip(front):
    """The one thing to listen for when comparing your attempt to the model.

    Only the first match applies — stacking three prompts on a card defeats
    the purpose, which is to narrow attention to a single feature.
    """
    word = front.split(" / ")[0].strip().lower()
    if " " in word or not word.isalpha():
        return None          # phrases and punctuation-bearing fronts: no single target
    for pattern, tip in SAY_TIPS:
        if pattern.search(word):
            return tip
    return None


def highlight(term, sentence):
    """Bold the card's term inside its example sentence, as HTML.

    Falls back to the plain escaped sentence when the term has no single span
    to point at (see _vocab_text.find_term) rather than mangling it.
    """
    span = find_term(term, sentence)
    if span is None:
        return html_escape(sentence)
    a, b = span
    return (html_escape(sentence[:a])
            + "<b>" + html_escape(sentence[a:b]) + "</b>"
            + html_escape(sentence[b:]))


TTS_INDEX_PATH = ROOT / "audio" / "tts" / "index.json"
LL_INDEX_PATH = ROOT / "audio" / "ll" / "index.json"


def load_tts_index():
    """text -> generated clip filename, empty when build_tts.py hasn't run.

    A partial index is normal and fine: the free tier covers roughly half the
    deck a month, so cards without a clip simply fall back to the device voice
    until a later run fills them in.
    """
    if not TTS_INDEX_PATH.exists():
        return {}
    try:
        return json.loads(TTS_INDEX_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def load_ll_index():
    """front -> Lingua Libre clip info, empty until fetch_lingualibre.py runs.

    Same partial-index philosophy as the TTS index: whatever volunteer
    recordings exist get used, everything else falls through the chain.
    """
    if not LL_INDEX_PATH.exists():
        return {}
    try:
        return json.loads(LL_INDEX_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def load_decks():
    tts = load_tts_index()
    ll = load_ll_index()
    rows = []
    for tsv in sorted(VOCAB_DIR.glob("*.tsv")):
        with open(tsv, encoding="utf-8") as f:
            reader = csv.reader(f, delimiter="\t")
            for row in reader:
                if len(row) < 3:
                    continue
                front, back, tags = row[0].strip(), row[1].strip(), parse_tags(row[2])
                if not front:
                    continue
                card = {"front": front, "back": back, "tags": tags, "deck": tsv.stem}
                # build_tts speaks only the first spelling of a slash front
                spoken = front.split(" / ")[0].strip()
                if spoken in tts:
                    card["wordSrc"] = f"audio/tts/{tts[spoken]}"
                # A real volunteer's voice outranks the studio voice for the
                # word itself; the page prefers llSrc when both exist.
                if spoken.lower() in ll:
                    card["llSrc"] = f"audio/ll/{ll[spoken.lower()]['file']}"
                tip = say_tip(front)
                if tip:
                    card["sayTip"] = tip
                example = row[3].strip() if len(row) > 3 else ""
                if example:
                    card["example"] = example        # raw, for speech synthesis
                    if example in tts:
                        card["exampleSrc"] = f"audio/tts/{tts[example]}"
                    card["exampleHtml"] = highlight(front, example)
                    if len(row) > 4 and row[4].strip():
                        card["exampleEn"] = row[4].strip()
                rows.append(card)
    # dedupe by front, first occurrence wins
    seen = set()
    deduped = []
    for r in rows:
        if r["front"] in seen:
            continue
        seen.add(r["front"])
        deduped.append(r)
    return deduped


MIN_HEARD_SCORE = 0     # below this, no transcript line is worth quoting


def _heard_score(term, text, match, has_en):
    """How good a transcript line is as the "heard in the recording" quote.

    The old rule — take the first line containing the word — pulled in some
    genuinely misleading quotes: "malu" matched the place name *Malu*, "tua"
    matched *orang tua* (parents) buried in a 20-word ramble. Scoring every
    occurrence and keeping the best one costs one extra pass and fixes both.
    """
    words = len(text.split())
    score = 0
    if has_en:
        score += 40          # a line with no translation is half a quote
    if 3 <= words <= 12:
        score += 30          # short enough to read on the back of a card
    elif words <= 18:
        score += 15
    elif words <= 25:
        score += 5
    else:
        score -= 10
    surface = text[match.start(): match.end()]
    if term[:1].islower() and surface[:1].isupper() and match.start() > 0:
        score -= 60          # capitalised mid-sentence: a name, not the word
    if text.rstrip().endswith((".", "?", "!")):
        score += 5
    return score


def attach_context(deck):
    """Give each card the family actually saying its word, where they do.

    Scores every real Indonesian transcript line containing the term and keeps
    the best one (see _heard_score), attaching the clip bounds plus the
    sentence so the card can play authentic audio alongside its written
    example. Roughly half the deck matches — the standalone reference decks
    (adjectives, comparisons, connectors, and the everyday-vocabulary decks)
    mostly aren't drawn from the conversation. Those get no audio fields and
    the page falls back to speech synthesis for them.

    Imported lazily so build_flashcards stays usable (minus context) even if
    the transcript/audio side of the project isn't set up.
    """
    try:
        from build_quiz import load_conversations, clamp_next_sec
    except Exception:
        return deck, 0
    convos = load_conversations()
    if not convos:
        return deck, 0
    matched = 0
    for card in deck:
        pattern = bounded(card["front"])
        best = None
        for convo in convos:
            for i, e in enumerate(convo["entries"]):
                if e["lang"] != "Indonesian":
                    continue
                m = pattern.search(e["text"])
                if not m:
                    continue
                score = _heard_score(card["front"], e["text"], m, bool(e.get("en")))
                if best is None or score > best[0]:
                    best = (score, convo, i, e, m)
        if best is None or best[0] < MIN_HEARD_SCORE:
            # Every occurrence was a bad quote — an untranslated ramble, or the
            # word only showing up as part of a name. Better no recording than
            # one that teaches the wrong sense; the card falls back to TTS.
            continue
        _, convo, i, e, m = best
        entries = convo["entries"]
        next_sec = entries[i + 1]["sec"] if i + 1 < len(entries) else e["sec"] + 6
        card["audio"] = convo["audio"]
        card["sec"] = e["sec"]
        card["nextSec"] = clamp_next_sec(e["sec"], next_sec, 8)
        card["sentenceHtml"] = (
            html_escape(e["text"][: m.start()])
            + "<b>" + html_escape(e["text"][m.start(): m.end()]) + "</b>"
            + html_escape(e["text"][m.end():])
        )
        if e.get("en"):
            card["exTranslation"] = e["en"]
        matched += 1
    return deck, matched


def main():
    deck = load_decks()
    deck, matched = attach_context(deck)
    html = (
        PAGE.replace("__SRS_JS__", SRS_JS)
        .replace("__SYNC_JS__", SYNC_JS)
        .replace("__TTS_JS__", TTS_JS)
        .replace("__REC_JS__", REC_JS)
        .replace("__BOOST_JS__", BOOST_JS)
        .replace("__RHYTHM_TIP__", RHYTHM_TIP_TEXT)
        .replace("__VOCAB_JS__", VOCAB_JS)
        .replace("__DATA__", json.dumps(deck, ensure_ascii=False))
    )
    OUT.write_text(html, encoding="utf-8")
    volunteer = sum(1 for c in deck if c.get("llSrc"))
    clip = sum(1 for c in deck
               if c.get("llSrc") or c.get("wordSrc") or c.get("exampleSrc"))
    fallback = sum(1 for c in deck
                   if not (c.get("llSrc") or c.get("wordSrc") or c.get("exampleSrc")
                           or c.get("audio")))
    print(f"wrote {OUT} with {len(deck)} cards from {len(list(VOCAB_DIR.glob('*.tsv')))} deck(s); "
          f"{clip} with a clear clip ({volunteer} volunteer-recorded), "
          f"{matched} with family audio, {fallback} rely on the device's speech synthesis")


if __name__ == "__main__":
    main()
