#!/usr/bin/env python3
"""
Regenerate index.html — the landing page: links to every *-player.html in the
project root, the practice modes, and the progress export/import (sync) panel.
Run this after build_player.py adds a new conversation.

Usage:
    python3 build_index.py
"""
import re
from pathlib import Path

from _sync_js import SYNC_JS

ROOT = Path(__file__).resolve().parent.parent

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Learning Bahasa Indonesian</title>
<style>
  :root { color-scheme: light dark; --bg:#fff; --fg:#1a1a1a; --muted:#6b7280; --line:#e5e7eb; --accent:#2563eb; --card:#f9fafb;
    --good:#16a34a; --bad:#dc2626; }
  @media (prefers-color-scheme: dark) {
    :root { --bg:#111318; --fg:#e7e9ee; --muted:#9aa1ac; --line:#2a2e37; --accent:#5b9dff; --card:#1a1d24;
      --good:#4ade80; --bad:#f87171; }
  }
  * { box-sizing:border-box; }
  html, body { margin:0; background:var(--bg); color:var(--fg);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }
  .wrap { max-width:640px; margin:0 auto; padding:48px 20px 64px; }
  h1 { font-size:1.4rem; margin:0 0 4px; }
  p.sub { color:var(--muted); margin:0 0 28px; font-size:0.9rem; }
  a.card { display:block; padding:16px 18px; margin-bottom:12px; border-radius:10px;
    border:1px solid var(--line); background:var(--card); text-decoration:none; color:var(--fg); }
  a.card:hover { border-color:var(--accent); }
  a.card .name { font-weight:600; font-size:1rem; }
  a.card .meta { color:var(--muted); font-size:0.8rem; margin-top:3px; }
  a.card.practice { display:flex; justify-content:space-between; align-items:center; }
  a.card.practice .name { display:flex; align-items:center; gap:8px; }
  h2.section { font-size:0.78rem; text-transform:uppercase; letter-spacing:0.04em; color:var(--muted);
    margin:28px 0 10px; }
  h2.section:first-of-type { margin-top:0; }
  .empty { color:var(--muted); font-size:0.9rem; }

  .sync { padding:16px 18px; border-radius:10px; border:1px solid var(--line); background:var(--card); }
  .sync .counts { color:var(--muted); font-size:0.8rem; margin-bottom:12px; }
  .sync .row { display:flex; gap:8px; flex-wrap:wrap; }
  .sync button { font-size:0.85rem; padding:9px 14px; border-radius:8px; border:1px solid var(--line);
    background:var(--bg); color:var(--fg); cursor:pointer; }
  .sync button.primary { border-color:var(--accent); color:var(--accent); }
  .sync button.primary:hover { background:var(--accent); color:#fff; }
  .sync .note { color:var(--muted); font-size:0.76rem; margin-top:12px; line-height:1.45; }
  .sync textarea { width:100%; margin-top:10px; min-height:90px; font-family:ui-monospace,Menlo,monospace;
    font-size:0.72rem; border-radius:8px; border:1px solid var(--line); background:var(--bg); color:var(--fg);
    padding:8px; }
  #syncMsg { margin-top:10px; font-size:0.8rem; white-space:pre-line; line-height:1.5; }
  #syncMsg.ok { color:var(--good); }
  #syncMsg.err { color:var(--bad); }
  .hidden { display:none; }
</style>
</head>
<body>
<div class="wrap">
  <h1>Learning Bahasa Indonesian</h1>
  <p class="sub">Listen and read along, then practice what stuck.</p>
  <h2 class="section">Practice</h2>
  <a class="card practice" href="flashcards.html">
    <div class="name">Flashcards</div>
    <div class="meta">vocab drill</div>
  </a>
  <a class="card practice" href="quiz.html">
    <div class="name">Quiz</div>
    <div class="meta">fill-in-the-blank from real lines</div>
  </a>
  <h2 class="section">Conversations</h2>
  __ITEMS__

  <h2 class="section">Sync progress</h2>
  <div class="sync">
    <div class="counts" id="syncCounts"></div>
    <div class="row">
      <button class="primary" id="exportBtn">Export progress</button>
      <button id="importBtn">Import progress…</button>
      <button id="pasteToggle">Paste instead</button>
    </div>
    <input type="file" id="fileInput" accept="application/json,.json" class="hidden">
    <div id="pasteBox" class="hidden">
      <textarea id="pasteArea" placeholder="Paste the contents of a progress export here, then press Merge."></textarea>
      <div class="row"><button id="pasteMerge">Merge pasted progress</button></div>
    </div>
    <div id="syncMsg"></div>
    <div class="note">
      Review schedules live in this browser, so your phone and laptop track separately. Export here, move the
      file across (AirDrop works well), then Import on the other device. Merging is safe both ways: for each
      card the more recent review wins, so an older export can't roll back newer progress. Flags merge as a
      union — unflagging doesn't propagate, so unflag on both devices if you change your mind.
    </div>
  </div>
</div>
<script>
__SYNC_JS__

const msg = document.getElementById('syncMsg');
function say(text, cls) { msg.textContent = text; msg.className = cls || ''; }

function renderCounts() {
  const c = syncCounts();
  document.getElementById('syncCounts').textContent =
    `${c.fc} flashcards, ${c.qz} quiz items, ${c.fl} flagged lines tracked in this browser`;
}
renderCounts();

document.getElementById('exportBtn').addEventListener('click', () => {
  const payload = syncBuildExport();
  const c = syncCounts();
  if (!c.fc && !c.qz && !c.fl) {
    say('Nothing to export yet — no reviews recorded in this browser.', 'err');
    return;
  }
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  const stamp = new Date().toISOString().slice(0, 10);
  a.href = url;
  a.download = `bahasa-progress-${stamp}.json`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  say(`Exported ${c.fc} flashcards, ${c.qz} quiz items, ${c.fl} flags.`, 'ok');
});

function doImport(text) {
  let payload;
  try { payload = JSON.parse(text); }
  catch (e) { say("That doesn't look like valid JSON.", 'err'); return; }
  try {
    const r = syncApplyImport(payload);
    renderCounts();
    say(r.text + (r.touched ? '' : '\\n(Nothing changed — this device was already up to date.)'), 'ok');
  } catch (e) {
    say(e.message, 'err');
  }
}

document.getElementById('importBtn').addEventListener('click', () => document.getElementById('fileInput').click());
document.getElementById('fileInput').addEventListener('change', (e) => {
  const file = e.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => doImport(reader.result);
  reader.onerror = () => say("Couldn't read that file.", 'err');
  reader.readAsText(file);
  e.target.value = '';
});

document.getElementById('pasteToggle').addEventListener('click', () => {
  document.getElementById('pasteBox').classList.toggle('hidden');
});
document.getElementById('pasteMerge').addEventListener('click', () => {
  const t = document.getElementById('pasteArea').value.trim();
  if (!t) { say('Paste an export first.', 'err'); return; }
  doImport(t);
});
</script>
</body>
</html>
"""

ITEM = """<a class="card" href="{href}">
    <div class="name">{name}</div>
    <div class="meta">{href}</div>
  </a>"""


def main():
    players = sorted(ROOT.glob("*-player.html"))
    if players:
        items = "\n  ".join(
            ITEM.format(
                href=p.name,
                name=re.sub(r"-player\.html$", "", p.name).replace("-", " ").title(),
            )
            for p in players
        )
    else:
        items = '<p class="empty">No conversations yet — run build_player.py first.</p>'
    html = PAGE.replace("__SYNC_JS__", SYNC_JS).replace("__ITEMS__", items)
    out = ROOT / "index.html"
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out} with {len(players)} conversation(s) + sync panel")


if __name__ == "__main__":
    main()
