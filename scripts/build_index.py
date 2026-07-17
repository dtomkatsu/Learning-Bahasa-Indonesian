#!/usr/bin/env python3
"""
Regenerate index.html — the landing page: links to every *-player.html in the
project root, the practice modes, and the progress export/import (sync) panel.
Run this after build_player.py adds a new conversation.

Usage:
    python3 build_index.py
"""
import json
import re
from pathlib import Path

from _srs_js import SRS_JS
from _sync_js import SYNC_JS
from build_flashcards import load_decks
from build_quiz import (
    load_vocab, load_conversations,
    build_quiz_items, build_sentence_items, build_listening_items,
)

ROOT = Path(__file__).resolve().parent.parent

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="manifest" href="manifest.json">
<meta name="theme-color" content="#D01228">
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
  a.card.study { border-color:var(--accent); }
  a.card.study .name { color:var(--accent); font-size:1.05rem; }
  .statsCard { padding:16px 18px; border-radius:10px; border:1px solid var(--line); background:var(--card);
    font-size:0.85rem; }
  .statsCard .line { margin-bottom:8px; }
  .statsCard .big { font-weight:700; }
  .heat { display:flex; gap:3px; margin:10px 0 4px; }
  .heat div { width:14px; height:14px; border-radius:3px; background:var(--accent); }
  .heat .h0 { background:var(--line); }
  .heat .h1 { opacity:0.3; } .heat .h2 { opacity:0.55; } .heat .h3 { opacity:0.8; } .heat .h4 { opacity:1; }
  .statsCard .sub { color:var(--muted); font-size:0.76rem; }
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
  .sync input[type="password"] { width:100%; margin-bottom:10px; font-size:0.85rem; border-radius:8px;
    border:1px solid var(--line); background:var(--bg); color:var(--fg); padding:9px 10px; }
  .sync a { color:var(--accent); }
  .sync .subhead { font-size:0.72rem; text-transform:uppercase; letter-spacing:0.04em; color:var(--muted);
    margin:0 0 10px; }
  .sync hr { border:0; border-top:1px solid var(--line); margin:16px 0 14px; }
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
  <a class="card practice study" href="study.html">
    <div class="name">&#9654; Study now</div>
    <div class="meta" id="studyMeta">one mixed session of everything due</div>
  </a>
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

  <h2 class="section">Stats</h2>
  <div class="statsCard" id="statsCard">No reviews yet — hit Study now to start the streak.</div>

  <h2 class="section">Sync progress</h2>
  <div class="sync">
    <div class="counts" id="syncCounts"></div>
    <div class="subhead">Auto-sync (GitHub gist)</div>
    <div id="remoteBox"></div>
    <hr>
    <div class="subhead">Manual export / import</div>
    <div class="row">
      <button id="exportBtn">Export progress</button>
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
__SRS_JS__
__SYNC_JS__
const STUDY_META = __STUDY_META__;

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

// ---- auto-sync panel ----
const remoteBox = document.getElementById('remoteBox');

function renderRemote() {
  if (syncRemoteConfigured()) {
    const last = parseInt(localStorage.getItem('bahasa:sync:lastSync') || '0', 10);
    const gid = localStorage.getItem('bahasa:sync:gistId');
    remoteBox.innerHTML = `
      <div class="row">
        <button class="primary" id="syncNowBtn">Sync now</button>
        <button id="disconnectBtn">Disconnect</button>
      </div>
      <div class="note">Auto-sync is <b>on</b> (private gist ${gid.slice(0,8)}…). Last synced:
      ${last ? new Date(last).toLocaleString() : 'never'}. Every page pulls on load; ratings push a few seconds
      after you answer. Connect the other device with the same token and it stays in step automatically.</div>`;
    document.getElementById('syncNowBtn').addEventListener('click', async () => {
      say('Syncing…');
      try {
        await syncRemotePush();
        renderCounts(); renderRemote();
        say('Synced.', 'ok');
      } catch (e) { say(e.message, 'err'); }
    });
    document.getElementById('disconnectBtn').addEventListener('click', () => {
      if (!confirm('Disconnect auto-sync on this device? Your progress here and the gist are both kept — this only stops syncing.')) return;
      syncRemoteDisconnect();
      renderRemote();
      say('Auto-sync disconnected on this device.', 'ok');
    });
  } else {
    remoteBox.innerHTML = `
      <input type="password" id="tokenInput" autocomplete="off"
        placeholder="GitHub classic token with only the gist scope">
      <div class="row"><button class="primary" id="connectBtn">Connect auto-sync</button></div>
      <div class="note">Stores progress in a <b>private gist</b> on your GitHub account — no server, nothing
      new to run. Create a token at
      <a href="https://github.com/settings/tokens/new?scopes=gist&description=Bahasa+Player+sync"
         target="_blank" rel="noopener">github.com/settings/tokens/new</a>
      (classic token, tick only <b>gist</b> — fine-grained tokens don't work with the gist API), paste it here,
      then do the same once on your other device. The token stays in this browser's local storage.</div>`;
    document.getElementById('connectBtn').addEventListener('click', async () => {
      const token = document.getElementById('tokenInput').value.trim();
      if (!token) { say('Paste a token first.', 'err'); return; }
      say('Connecting…');
      try {
        await syncRemoteSetup(token);
        const r = await syncRemotePull();
        renderCounts(); renderRemote();
        say('Connected. ' + (r.touched ? r.text : 'No remote progress to merge yet — this device is the starting point.'), 'ok');
      } catch (e) { say(e.message, 'err'); }
    });
  }
}
renderRemote();

// ---- Study-now due counts ----
function renderStudyMeta() {
  const srsF = syncRead('bahasa:flashcards:fsrs:v1');
  const srsQ = syncRead('bahasa:quiz:fsrs:v1');
  const removed = syncRead(REMOVED_CARDS_KEY);
  const custom = syncRead(CUSTOM_CARDS_KEY);
  const flags = syncRead(FLAG_KEY);
  const now = Date.now();
  const fronts = new Set(STUDY_META.flashFronts.filter(f => !removed[f]));
  Object.keys(custom).forEach(f => fronts.add(f));
  let reviews = 0, fresh = 0;
  fronts.forEach(f => { const s = srsF[f]; if (!s) fresh++; else if (s.due <= now) reviews++; });
  STUDY_META.quiz.forEach(q => {
    if (flags[q.lineId]) return;
    const s = srsQ[q.id];
    if (!s) fresh++; else if (s.due <= now) reviews++;
  });
  const newToday = Math.min(fresh, srsNewQuotaLeft());
  const el = document.getElementById('studyMeta');
  if (!reviews && !newToday) el.textContent = 'all caught up ✓';
  else el.textContent = `${reviews} to review · ${newToday} new today`;
}
renderStudyMeta();

// ---- Stats panel: streak, 28-day heatmap, recall rate ----
function dayKey(d) {
  return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
}
function renderStatsPanel() {
  const log = syncRead(SYNC_REVIEWLOG_KEY);
  const entries = Object.entries(log).map(([t, v]) => ({ t: +t, g: v.g, n: v.n }));
  if (!entries.length) return;
  const byDay = {};
  entries.forEach(e => { const k = dayKey(new Date(e.t)); byDay[k] = (byDay[k] || 0) + 1; });
  const DAY = 86400000;
  let streak = 0;
  for (let i = 0; ; i++) {
    const k = dayKey(new Date(Date.now() - i * DAY));
    if (byDay[k]) streak++;
    else if (i === 0) continue;   // an empty today doesn't break yesterday's streak
    else break;
  }
  let heat = '';
  for (let i = 27; i >= 0; i--) {
    const n = byDay[dayKey(new Date(Date.now() - i * DAY))] || 0;
    const lvl = n === 0 ? 'h0' : n < 5 ? 'h1' : n < 10 ? 'h2' : n < 20 ? 'h3' : 'h4';
    heat += `<div class="${lvl}" title="${n} reviews"></div>`;
  }
  const reviewsOnly = entries.filter(e => !e.n).sort((a, b) => b.t - a.t).slice(0, 200);
  const recall = reviewsOnly.length
    ? Math.round(100 * reviewsOnly.filter(e => e.g > 1).length / reviewsOnly.length) : null;
  const today = byDay[dayKey(new Date())] || 0;
  document.getElementById('statsCard').innerHTML = `
    <div class="line"><span class="big">${streak}</span>-day streak · <span class="big">${today}</span> reviews today · <span class="big">${entries.length}</span> logged</div>
    <div class="heat">${heat}</div>
    <div class="sub">last 28 days${recall !== null ? ` · recall rate ${recall}% (target 90% — much higher means you can afford more new cards)` : ''}</div>`;
}
renderStatsPanel();

// If already connected, do a background pull on load like the practice pages do.
syncRemoteAutoPull(() => { renderCounts(); renderRemote(); renderStudyMeta(); renderStatsPanel(); }, null);

// ---- PWA: offline caching + installability (no-op over file://) ----
if ('serviceWorker' in navigator && location.protocol.startsWith('http')) {
  navigator.serviceWorker.register('sw.js').catch(() => {});
}
</script>
</body>
</html>
"""

ITEM = """<a class="card" href="{href}">
    <div class="name">{name}</div>
    <div class="meta">{href}</div>
  </a>"""


def build_study_meta():
    flash = load_decks()
    vocab = load_vocab()
    convos = load_conversations()
    word_items = build_quiz_items(vocab, convos)
    sentence_items = build_sentence_items(convos)
    listening_items = build_listening_items(sentence_items)
    quiz = [{"id": i["id"], "lineId": i["lineId"]} for i in word_items + sentence_items + listening_items]
    return {"flashFronts": [d["front"] for d in flash], "quiz": quiz}


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
    html = (
        PAGE.replace("__SRS_JS__", SRS_JS)
        .replace("__SYNC_JS__", SYNC_JS)
        .replace("__STUDY_META__", json.dumps(build_study_meta(), ensure_ascii=False))
        .replace("__ITEMS__", items)
    )
    out = ROOT / "index.html"
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out} with {len(players)} conversation(s) + sync panel")


if __name__ == "__main__":
    main()
