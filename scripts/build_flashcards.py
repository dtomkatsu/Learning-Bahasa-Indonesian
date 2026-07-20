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
  .topRow { display:flex; gap:8px; align-items:flex-start; margin-bottom:16px; }
  .topRow #addToggleBtn { flex:0 0 auto; white-space:nowrap; }
  .chips { flex:1 1 auto; display:flex; flex-wrap:wrap; gap:6px; }
  button.chip { font-size:0.75rem; padding:5px 10px; border-radius:999px; border:1px solid var(--line);
    background:var(--bg); color:var(--muted); cursor:pointer; }
  button.chip.active { background:var(--accent); border-color:var(--accent); color:#fff; }
  button.chip:hover { border-color:var(--accent); }
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
  <div class="topRow">
    <div class="chips" id="tagChips"></div>
    <button class="plain" id="addToggleBtn">+ Add card</button>
    <button class="plain" id="bulkToggleBtn">+ Add list</button>
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

function uniqueTags() {
  return [...new Set(DECK.flatMap(d => d.tags))].sort();
}
function renderChips() {
  const tags = uniqueTags();
  activeTags = new Set([...activeTags].filter(t => tags.includes(t)));
  chipsEl.innerHTML = tags.map(t =>
    `<button class="chip${activeTags.has(t) ? ' active' : ''}" data-tag="${t}">${t}</button>`).join('');
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
renderChips();

function applyFilter() {
  pool = activeTags.size
    ? DECK.filter(d => d.tags.some(t => activeTags.has(t)))
    : DECK.slice();
}
applyFilter();

// Re-derive the deck after a local edit (add/remove) or a remote sync pull
// that may have brought in edits made on another device.
function refreshDeck() {
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
  // Reviews first, then any brand-new card; practice-ahead ignores the
  // schedule entirely once even that pool is exhausted.
  const reviews = pool.filter(d => srs[d.front] && srsIsDue(srs[d.front]));
  const freshAll = pool.filter(d => !srs[d.front]);
  let due = reviews.length ? reviews : freshAll;
  if (practiceAhead && !due.length) due = pool;
  if (!due.length) { renderAllCaughtUp(); return; }
  let next = due[Math.floor(Math.random() * due.length)];
  if (due.length > 1 && current && next.front === current.front) next = due[Math.floor(Math.random() * due.length)];
  current = next;
  flipped = false;
  cardEl.className = '';
  cardEl.innerHTML = '<div class="front"></div><div class="back"><div class="en"></div><div class="tag"></div></div>';
  cardEl.querySelector('.front').textContent = current.front;
  cardEl.querySelector('.en').textContent = current.back;
  cardEl.querySelector('.tag').textContent = current.tags.join(' · ');
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
  if (flipped) updatePreviews();
}

function rate(grade) {
  if (!current) return;
  const isNew = !srs[current.front];
  if (isNew) srsNoteNewIntroduced();
  srsLogReview('flash', grade, isNew);
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

// Parses the same "front – back" paste format used to build the vocab/*.tsv
// decks: blank-line-separated blocks, each optionally starting with a
// "(tag[,tag2])" line that applies to every entry in that block. Accepts
// en dash / em dash / hyphen as the separator, as long as it's space-padded
// (so hyphenated words like "kira-kira" inside a term are left alone).
function parseBulkVocab(text) {
  const entries = [];
  const blocks = text.split(/\\n\\s*\\n/);
  for (const block of blocks) {
    const lines = block.split('\\n').map(l => l.trim()).filter(Boolean);
    if (!lines.length) continue;
    let tags = ['custom'];
    let start = 0;
    const tagMatch = lines[0].match(/^\\(([^)]+)\\)$/);
    if (tagMatch) {
      tags = tagMatch[1].split(',').map(t => t.trim()).filter(Boolean);
      if (!tags.length) tags = ['custom'];
      start = 1;
    }
    for (let i = start; i < lines.length; i++) {
      const sep = lines[i].match(/\\s[–—-]\\s/);
      if (!sep) continue;
      const front = lines[i].slice(0, sep.index).trim();
      const back = lines[i].slice(sep.index + sep[0].length).trim();
      if (front && back) entries.push({ front, back, tags });
    }
  }
  return entries;
}

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
  bulkForm.hidden = true;
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

const bulkForm = document.getElementById('bulkForm');
document.getElementById('bulkToggleBtn').addEventListener('click', () => {
  addForm.hidden = true;
  bulkForm.hidden = !bulkForm.hidden;
  if (!bulkForm.hidden) document.getElementById('bulkText').focus();
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


def load_decks():
    rows = []
    for tsv in sorted(VOCAB_DIR.glob("*.tsv")):
        with open(tsv, encoding="utf-8") as f:
            reader = csv.reader(f, delimiter="\t")
            for row in reader:
                if len(row) < 3:
                    continue
                front, back, tags = row[0].strip(), row[1].strip(), parse_tags(row[2])
                if front:
                    rows.append({"front": front, "back": back, "tags": tags, "deck": tsv.stem})
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
