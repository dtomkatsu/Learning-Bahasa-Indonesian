#!/usr/bin/env python3
"""
Build flashcards.html — a self-contained flip-card vocab trainer over every
vocab/*.tsv deck (Indonesian / English+notes / tag columns, no header).

Uses real spaced repetition — FSRS-5 (see scripts/_srs_js.py), the same
algorithm Anki itself recommends as its default over the older SM-2 family.
Rating is the familiar 4-button Again/Hard/Good/Easy, each showing a preview
of the resulting interval (Anki-style), and only cards that are actually due
get shown. If nothing's due, there's a "practice ahead" fallback rather than
a dead end.

The deck isn't fixed at build time: a "Remove this card" link on the back of
each card hides it (tombstoned in localStorage, restorable), and "+ Add card"
lets you type in new vocab on the fly. Both are layered on top of the
TSV-sourced deck rather than editing it, and both are included in the sync
payload (scripts/_sync_js.py) so deck edits propagate to other devices the
same way review progress does.

Usage:
    python3 build_flashcards.py
"""
import csv
import json
from pathlib import Path

from _srs_js import SRS_JS
from _sync_js import SYNC_JS

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
  select { font-size:0.8rem; padding:5px 7px; border-radius:6px; border:1px solid var(--line);
    background:var(--bg); color:var(--fg); }
  .topRow { display:flex; gap:8px; align-items:center; margin-bottom:16px; }
  .topRow select { flex:1 1 auto; margin-bottom:0; }
  #card { border:1px solid var(--line); border-radius:14px; background:var(--card);
    min-height:220px; display:flex; align-items:center; justify-content:center; text-align:center;
    padding:28px 20px; cursor:pointer; margin:18px 0; user-select:none; }
  #card .front { font-size:1.5rem; font-weight:600; }
  #card .back { display:none; }
  #card.flipped .front { display:none; }
  #card.flipped .back { display:block; }
  #card .back .en { font-size:1.25rem; font-weight:600; margin-bottom:6px; }
  #card .back .tag { color:var(--muted); font-size:0.78rem; }
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
  .cardMeta { text-align:center; margin-top:10px; }
  .cardMeta[hidden] { display:none; }
  button.linkBtn { font-size:0.75rem; color:var(--muted); background:none; border:none;
    text-decoration:underline; cursor:pointer; padding:4px; }
  button.linkBtn:hover { color:var(--again); }
  .tools { display:flex; justify-content:space-between; align-items:center; margin-top:24px;
    flex-wrap:wrap; gap:8px; }
  .tools .row { display:flex; gap:8px; flex-wrap:wrap; }
  button.plain { font-size:0.78rem; padding:6px 10px; border-radius:6px; border:1px solid var(--line);
    background:var(--bg); color:var(--muted); cursor:pointer; }
  .empty { color:var(--muted); font-size:0.9rem; text-align:center; margin-top:20px; }
  .empty .sub { font-size:0.8rem; margin-top:6px; }
  .empty button.plain { margin-top:14px; }

  #addForm { border:1px solid var(--line); border-radius:10px; background:var(--card);
    padding:14px; margin:0 0 16px; }
  #addForm[hidden] { display:none; }
  #addForm input { width:100%; margin-bottom:8px; font-size:0.85rem; border-radius:8px;
    border:1px solid var(--line); background:var(--bg); color:var(--fg); padding:8px 10px; }
  #addForm .row { display:flex; gap:8px; }
</style>
</head>
<body>
<div class="wrap">
  <div class="top">
    <h1>Flashcards</h1>
    <a class="back" href="index.html">&larr; all conversations</a>
  </div>
  <div class="stats" id="stats"></div>
  <div class="topRow">
    <select id="tagFilter"></select>
    <button class="plain" id="addToggleBtn">+ Add card</button>
  </div>
  <div id="addForm" hidden>
    <input id="addFront" placeholder="Indonesian (e.g. kayaknya)">
    <input id="addBack" placeholder="English / notes">
    <input id="addTag" placeholder="tag (optional — defaults to “custom”)">
    <div class="row">
      <button class="plain" id="addSaveBtn">Save card</button>
      <button class="plain" id="addCancelBtn">Cancel</button>
    </div>
  </div>
  <div id="card"><div class="front"></div><div class="back"><div class="en"></div><div class="tag"></div></div></div>
  <div class="hint">Click the card (or press space) to flip</div>
  <div class="rate" id="rateRow" hidden>
    <button class="rate-btn again" id="btn1"><span class="lbl">Again</span><span class="prev" id="prev1"></span></button>
    <button class="rate-btn hard" id="btn2"><span class="lbl">Hard</span><span class="prev" id="prev2"></span></button>
    <button class="rate-btn good" id="btn3"><span class="lbl">Good</span><span class="prev" id="prev3"></span></button>
    <button class="rate-btn easy" id="btn4"><span class="lbl">Easy</span><span class="prev" id="prev4"></span></button>
  </div>
  <div class="cardMeta" id="cardMeta" hidden>
    <button class="linkBtn" id="removeBtn">Remove this card from my deck</button>
  </div>
  <div class="tools">
    <div class="row">
      <button class="plain" id="resetBtn">Reset progress</button>
      <button class="plain" id="restoreBtn">Restore removed (0)</button>
    </div>
    <span class="stats" id="syncState"></span>
    <span class="stats" id="deckInfo"></span>
  </div>
</div>
<script>
__SRS_JS__
__SYNC_JS__
const BUILTIN_DECK = __DATA__;
const SRS_KEY = 'bahasa:flashcards:fsrs:v1';
const LEGACY_KEYS = ['bahasa:flashcards:v1', 'bahasa:flashcards:srs:v1'];

let srs = srsMigrateLegacy(SRS_KEY, LEGACY_KEYS);

// The deck isn't just BUILTIN_DECK: removed cards are tombstoned out and
// custom cards are layered in (a custom card with the same front as a
// built-in one edits it in place, since it wins the Map merge below).
function loadRemovedCards() { return syncRead(REMOVED_CARDS_KEY); }
function loadCustomCards() { return syncRead(CUSTOM_CARDS_KEY); }
function computeDeck() {
  const removed = loadRemovedCards();
  const custom = loadCustomCards();
  const byFront = new Map();
  BUILTIN_DECK.forEach(d => { if (!removed[d.front]) byFront.set(d.front, d); });
  Object.values(custom).forEach(d => byFront.set(d.front, d));
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
const tagFilter = document.getElementById('tagFilter');

function uniqueTags() {
  return [...new Set(DECK.map(d => d.tag))].sort();
}
function rebuildTagFilter() {
  const prev = tagFilter.value;
  tagFilter.innerHTML = '<option value="">All tags</option>' +
    uniqueTags().map(t => `<option value="${t}">${t}</option>`).join('');
  if ([...tagFilter.options].some(o => o.value === prev)) tagFilter.value = prev;
}
rebuildTagFilter();
tagFilter.addEventListener('change', () => { practiceAhead = false; applyFilter(); pickNext(); });

function applyFilter() {
  const t = tagFilter.value;
  pool = t ? DECK.filter(d => d.tag === t) : DECK.slice();
}
applyFilter();

// Re-derive the deck after a local edit (add/remove) or a remote sync pull
// that may have brought in edits made on another device.
function refreshDeck() {
  DECK = computeDeck();
  rebuildTagFilter();
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
  const due = practiceAhead ? pool : dueIn(pool);
  if (!due.length) { renderAllCaughtUp(); return; }
  let next = due[Math.floor(Math.random() * due.length)];
  if (due.length > 1 && current && next.front === current.front) next = due[Math.floor(Math.random() * due.length)];
  current = next;
  flipped = false;
  cardEl.className = '';
  cardEl.innerHTML = '<div class="front"></div><div class="back"><div class="en"></div><div class="tag"></div></div>';
  cardEl.querySelector('.front').textContent = current.front;
  cardEl.querySelector('.en').textContent = current.back;
  cardEl.querySelector('.tag').textContent = current.tag;
  rateRow.hidden = true;
  renderStats();
}

function renderEmpty(msg) {
  current = null;
  cardEl.innerHTML = `<div class="empty">${msg}</div>`;
  rateRow.hidden = true;
}

function renderAllCaughtUp() {
  current = null;
  const dues = pool.map(d => (srs[d.front] && srs[d.front].due) || Infinity);
  const nextDue = Math.min(...dues);
  cardEl.innerHTML = `<div class="empty">🎉 All caught up!<div class="sub">Next review in ${srsFmtDue(nextDue)}.</div>` +
    `<button class="plain" id="aheadBtn">Practice ahead anyway</button></div>`;
  rateRow.hidden = true;
  document.getElementById('aheadBtn').addEventListener('click', () => { practiceAhead = true; pickNext(); });
  renderStats();
}

function renderStats() {
  const due = dueIn(pool).length;
  const mature = pool.filter(d => srsIsMature(srs[d.front])).length;
  document.getElementById('stats').textContent =
    `${DECK.length} cards — ${due} due now, ${mature} mastered (21d+)`;
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
  if (flipped) updatePreviews();
}

function rate(grade) {
  if (!current) return;
  srs[current.front] = fsrsNextState(srs[current.front], grade, Date.now());
  srsSave(SRS_KEY, srs);
  syncRemoteQueuePush(setSyncState);
  practiceAhead = false;
  pickNext();
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

function addCustomCard(front, back, tag) {
  front = front.trim(); back = back.trim(); tag = (tag || '').trim() || 'custom';
  if (!front || !back) return false;
  const custom = loadCustomCards();
  custom[front] = { front, back, tag, updatedAt: Date.now() };
  syncWrite(CUSTOM_CARDS_KEY, custom);
  // If this front was previously removed (a built-in card), un-tombstone it —
  // saving a card with that name is an explicit signal to bring it back.
  const removed = loadRemovedCards();
  if (removed[front]) { delete removed[front]; syncWrite(REMOVED_CARDS_KEY, removed); }
  syncRemoteQueuePush(setSyncState);
  return true;
}

cardEl.addEventListener('click', flip);
[1, 2, 3, 4].forEach(g => {
  document.getElementById('btn' + g).addEventListener('click', (e) => { e.stopPropagation(); rate(g); });
});
document.getElementById('removeBtn').addEventListener('click', removeCurrentCard);
document.getElementById('resetBtn').addEventListener('click', () => {
  if (confirm('Reset all flashcard progress (review history and due dates)?')) { srs = {}; srsSave(SRS_KEY, srs); pickNext(); }
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
  addForm.hidden = !addForm.hidden;
  if (!addForm.hidden) document.getElementById('addFront').focus();
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

document.addEventListener('keydown', (e) => {
  if (document.activeElement && document.activeElement.tagName === 'INPUT') return;
  if (e.key === ' ') { e.preventDefault(); flip(); }
  else if (flipped && ['1','2','3','4'].includes(e.key)) rate(parseInt(e.key, 10));
});

updateRestoreCount();
pickNext();
</script>
</body>
</html>
"""


def load_decks():
    rows = []
    for tsv in sorted(VOCAB_DIR.glob("*.tsv")):
        with open(tsv, encoding="utf-8") as f:
            reader = csv.reader(f, delimiter="\t")
            for row in reader:
                if len(row) < 3:
                    continue
                front, back, tag = row[0].strip(), row[1].strip(), row[2].strip()
                if front:
                    rows.append({"front": front, "back": back, "tag": tag, "deck": tsv.stem})
    # dedupe by front, first occurrence wins
    seen = set()
    deduped = []
    for r in rows:
        if r["front"] in seen:
            continue
        seen.add(r["front"])
        deduped.append(r)
    return deduped


def main():
    deck = load_decks()
    html = (
        PAGE.replace("__SRS_JS__", SRS_JS)
        .replace("__SYNC_JS__", SYNC_JS)
        .replace("__DATA__", json.dumps(deck, ensure_ascii=False))
    )
    OUT.write_text(html, encoding="utf-8")
    print(f"wrote {OUT} with {len(deck)} cards from {len(list(VOCAB_DIR.glob('*.tsv')))} deck(s)")


if __name__ == "__main__":
    main()
