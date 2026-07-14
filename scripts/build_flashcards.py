#!/usr/bin/env python3
"""
Build flashcards.html — a self-contained flip-card vocab trainer over every
vocab/*.tsv deck (Indonesian / English+notes / tag columns, no header).

Progress persists in the browser's localStorage (per-browser, not synced),
using a simple 4-box mastery system: wrong answers or "still learning"
resets a card to box 0; "got it" advances it up to box 3. Lower-box cards
are shown more often.

Usage:
    python3 build_flashcards.py
"""
import csv
import json
from pathlib import Path

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
  .empty { color:var(--muted); font-size:0.9rem; text-align:center; margin-top:60px; }
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
const DECK = __DATA__;
const STORE_KEY = 'bahasa:flashcards:v1';

function loadProgress() {
  try { return JSON.parse(localStorage.getItem(STORE_KEY)) || {}; } catch (e) { return {}; }
}
function saveProgress(p) { localStorage.setItem(STORE_KEY, JSON.stringify(p)); }
let progress = loadProgress();

function boxOf(front) { return (progress[front] && progress[front].box) || 0; }

let pool = DECK.slice();
let current = null;
let flipped = false;

const cardEl = document.getElementById('card');
const frontEl = cardEl.querySelector('.front');
const enEl = cardEl.querySelector('.en');
const tagEl = cardEl.querySelector('.tag');
const rateRow = document.getElementById('rateRow');
const tagFilter = document.getElementById('tagFilter');

function uniqueTags() {
  return [...new Set(DECK.map(d => d.tag))].sort();
}
tagFilter.innerHTML = '<option value="">All tags</option>' +
  uniqueTags().map(t => `<option value="${t}">${t}</option>`).join('');
tagFilter.addEventListener('change', () => { applyFilter(); pickNext(); });

function applyFilter() {
  const t = tagFilter.value;
  pool = t ? DECK.filter(d => d.tag === t) : DECK.slice();
}
applyFilter();

function weightedPick(items) {
  const weights = items.map(d => Math.max(1, 4 - boxOf(d.front)));
  const total = weights.reduce((a, b) => a + b, 0);
  let r = Math.random() * total;
  for (let i = 0; i < items.length; i++) {
    r -= weights[i];
    if (r <= 0) return items[i];
  }
  return items[items.length - 1];
}

function pickNext() {
  if (!pool.length) { renderEmpty(); return; }
  let next = weightedPick(pool);
  if (pool.length > 1 && current && next.front === current.front) next = weightedPick(pool);
  current = next;
  flipped = false;
  cardEl.classList.remove('flipped');
  frontEl.textContent = current.front;
  enEl.textContent = current.back;
  tagEl.textContent = current.tag;
  rateRow.hidden = true;
  renderStats();
}

function renderEmpty() {
  cardEl.innerHTML = '<div class="empty">No cards for this tag.</div>';
  rateRow.hidden = true;
}

function renderStats() {
  const boxes = [0,0,0,0];
  DECK.forEach(d => boxes[boxOf(d.front)]++);
  document.getElementById('stats').textContent =
    `${DECK.length} cards — new ${boxes[0]}, learning ${boxes[1]+boxes[2]}, mastered ${boxes[3]}`;
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
  const front = current.front;
  const box = boxOf(front);
  progress[front] = { box: good ? Math.min(3, box + 1) : 0 };
  saveProgress(progress);
  pickNext();
}

cardEl.addEventListener('click', flip);
document.getElementById('btnBad').addEventListener('click', (e) => { e.stopPropagation(); rate(false); });
document.getElementById('btnGood').addEventListener('click', (e) => { e.stopPropagation(); rate(true); });
document.getElementById('resetBtn').addEventListener('click', () => {
  if (confirm('Reset all flashcard progress?')) { progress = {}; saveProgress(progress); pickNext(); }
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
    html = PAGE.replace("__DATA__", json.dumps(deck, ensure_ascii=False))
    OUT.write_text(html, encoding="utf-8")
    print(f"wrote {OUT} with {len(deck)} cards from {len(list(VOCAB_DIR.glob('*.tsv')))} deck(s)")


if __name__ == "__main__":
    main()
