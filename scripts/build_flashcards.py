#!/usr/bin/env python3
"""
Build flashcards.html — a self-contained flip-card vocab trainer over every
vocab/*.tsv deck (Indonesian / English+notes / tag columns, no header).

Uses real spaced repetition (simplified SM-2, see scripts/_srs_js.py): each
card has an interval/ease/due-date in localStorage, and only cards that are
actually due get shown. Correct answers grow the interval; misses reset it
with a short relearn step. If nothing's due, there's a "practice ahead"
fallback rather than a dead end.

Usage:
    python3 build_flashcards.py
"""
import csv
import json
from pathlib import Path

from _srs_js import SRS_JS

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
    --accent:#2563eb; --card:#f9fafb; --good:#16a34a; --bad:#dc2626; }
  @media (prefers-color-scheme: dark) {
    :root { --bg:#111318; --fg:#e7e9ee; --muted:#9aa1ac; --line:#2a2e37; --accent:#5b9dff;
      --card:#1a1d24; --good:#4ade80; --bad:#f87171; }
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
  .rate { display:flex; gap:10px; }
  button.rate-btn { flex:1; padding:12px; border-radius:10px; border:1px solid var(--line);
    background:var(--card); color:var(--fg); font-size:0.9rem; cursor:pointer; }
  button.rate-btn:hover { filter:brightness(1.08); }
  button.rate-btn.bad { border-color:var(--bad); color:var(--bad); }
  button.rate-btn.good { border-color:var(--good); color:var(--good); }
  .rate[hidden] { display:none; }
  .tools { display:flex; justify-content:space-between; align-items:center; margin-top:24px; }
  button.plain { font-size:0.78rem; padding:6px 10px; border-radius:6px; border:1px solid var(--line);
    background:var(--bg); color:var(--muted); cursor:pointer; }
  .empty { color:var(--muted); font-size:0.9rem; text-align:center; margin-top:20px; }
  .empty .sub { font-size:0.8rem; margin-top:6px; }
  .empty button.plain { margin-top:14px; }
</style>
</head>
<body>
<div class="wrap">
  <div class="top">
    <h1>Flashcards</h1>
    <a class="back" href="index.html">&larr; all conversations</a>
  </div>
  <div class="stats" id="stats"></div>
  <select id="tagFilter"></select>
  <div id="card"><div class="front"></div><div class="back"><div class="en"></div><div class="tag"></div></div></div>
  <div class="hint">Click the card (or press space) to flip</div>
  <div class="rate" id="rateRow" hidden>
    <button class="rate-btn bad" id="btnBad">Still learning</button>
    <button class="rate-btn good" id="btnGood">Got it</button>
  </div>
  <div class="tools">
    <button class="plain" id="resetBtn">Reset progress</button>
    <span class="stats" id="deckInfo"></span>
  </div>
</div>
<script>
__SRS_JS__
const DECK = __DATA__;
const SRS_KEY = 'bahasa:flashcards:srs:v1';
const LEGACY_KEY = 'bahasa:flashcards:v1';

let srs = srsMigrateFromBoxes(SRS_KEY, LEGACY_KEY);

let pool = DECK.slice();
let current = null;
let flipped = false;
let practiceAhead = false;

const cardEl = document.getElementById('card');
const rateRow = document.getElementById('rateRow');
const tagFilter = document.getElementById('tagFilter');

function uniqueTags() {
  return [...new Set(DECK.map(d => d.tag))].sort();
}
tagFilter.innerHTML = '<option value="">All tags</option>' +
  uniqueTags().map(t => `<option value="${t}">${t}</option>`).join('');
tagFilter.addEventListener('change', () => { practiceAhead = false; applyFilter(); pickNext(); });

function applyFilter() {
  const t = tagFilter.value;
  pool = t ? DECK.filter(d => d.tag === t) : DECK.slice();
}
applyFilter();

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

function flip() {
  if (!current) return;
  flipped = !flipped;
  cardEl.classList.toggle('flipped', flipped);
  rateRow.hidden = !flipped;
}

function rate(good) {
  if (!current) return;
  srs[current.front] = srsSchedule(srs[current.front], good);
  srsSave(SRS_KEY, srs);
  practiceAhead = false;
  pickNext();
}

cardEl.addEventListener('click', flip);
document.getElementById('btnBad').addEventListener('click', (e) => { e.stopPropagation(); rate(false); });
document.getElementById('btnGood').addEventListener('click', (e) => { e.stopPropagation(); rate(true); });
document.getElementById('resetBtn').addEventListener('click', () => {
  if (confirm('Reset all flashcard progress (review history and due dates)?')) { srs = {}; srsSave(SRS_KEY, srs); pickNext(); }
});
document.addEventListener('keydown', (e) => {
  if (e.key === ' ') { e.preventDefault(); flip(); }
  else if (flipped && e.key === '1') rate(false);
  else if (flipped && e.key === '2') rate(true);
});

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
        .replace("__DATA__", json.dumps(deck, ensure_ascii=False))
    )
    OUT.write_text(html, encoding="utf-8")
    print(f"wrote {OUT} with {len(deck)} cards from {len(list(VOCAB_DIR.glob('*.tsv')))} deck(s)")


if __name__ == "__main__":
    main()
