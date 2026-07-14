#!/usr/bin/env python3
"""
Build a synced HTML audio+transcript player from a cleaned transcript.

Usage:
    python3 build_player.py <clean_transcript.txt> <audio_relative_path> <output.html>
        [--title "Conversation N"] [--translations <translations.json>]

`audio_relative_path` should be relative to wherever output.html will be
opened/served from (e.g. "audio/conversation-1.m4a" if both live under the
project root and output.html sits at the project root too).

`--translations` points to a JSON object mapping entry index (as a string,
0-based, over the full parsed entry list including English lines) to an
English translation string. Only Indonesian-language entries look up a
translation; see scripts/merge_translations.py or the translate-with-agents
workflow described in STUDY-METHOD.md for how to generate one.
"""
import argparse
import json
import re
from html import escape
from pathlib import Path

ENTRY_RE = re.compile(
    r"\[(\d{1,2}:\d{2}(?::\d{2})?)\]\s*(Speaker \d+):\s*\n\[(\w+)\]\s*\"(.*)\"",
    re.MULTILINE,
)


def ts_to_seconds(ts):
    parts = [int(p) for p in ts.split(":")]
    if len(parts) == 2:
        m, s = parts
        return m * 60 + s
    h, m, s = parts
    return h * 3600 + m * 60 + s


def parse(raw, name):
    entries = []
    for i, m in enumerate(ENTRY_RE.finditer(raw)):
        ts, speaker, lang, text = m.groups()
        entries.append({
            "ts": ts,
            "sec": ts_to_seconds(ts),
            "speaker": speaker,
            "lang": lang,
            "text": text.strip(),
            "lineId": f"{name}::{i}",
        })
    return entries


def derive_name(transcript_path):
    base = Path(transcript_path).name
    if base.endswith(".clean.txt"):
        return base[: -len(".clean.txt")]
    return Path(transcript_path).stem


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__ — synced player</title>
<style>
  :root {
    color-scheme: light dark;
    --bg: #ffffff; --fg: #1a1a1a; --muted: #6b7280; --line: #e5e7eb;
    --accent: #2563eb; --accent-bg: #eff6ff; --id-tag: #b45309; --en-tag: #1d4ed8;
    --btn-bg: #f3f4f6; --btn-fg: #1a1a1a; --bad: #dc2626;
  }
  @media (prefers-color-scheme: dark) {
    :root { --bg:#111318; --fg:#e7e9ee; --muted:#9aa1ac; --line:#2a2e37;
      --accent:#5b9dff; --accent-bg:#152238; --id-tag:#e0a458; --en-tag:#7cb0ff;
      --btn-bg:#1d2129; --btn-fg:#e7e9ee; --bad:#f87171; }
  }
  * { box-sizing: border-box; }
  html, body { margin:0; padding:0; background:var(--bg); color:var(--fg);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }
  #topbar { position: sticky; top:0; z-index:10; background:var(--bg);
    border-bottom:1px solid var(--line); padding:10px 14px; display:flex;
    flex-wrap:wrap; gap:10px; align-items:center; }
  h1 { font-size:0.95rem; font-weight:600; margin:0 12px 0 0; white-space:nowrap; }
  audio { flex:1 1 320px; min-width:260px; height:36px; }
  .speeds, .tools { display:flex; gap:4px; align-items:center; }
  button { font-size:0.8rem; padding:5px 9px; border-radius:6px; border:1px solid var(--line);
    background:var(--btn-bg); color:var(--btn-fg); cursor:pointer; }
  button.active { background:var(--accent); color:#fff; border-color:var(--accent); }
  button:hover { filter:brightness(1.08); }
  #search { font-size:0.85rem; padding:6px 8px; border-radius:6px; border:1px solid var(--line);
    background:var(--bg); color:var(--fg); width:150px; }
  #list { padding:10px 14px 80px; max-width:900px; margin:0 auto; }
  .row { display:flex; gap:10px; padding:7px 8px; border-radius:8px; cursor:pointer; align-items:baseline; }
  .row:hover { background:var(--btn-bg); }
  .row.active { background:var(--accent-bg); }
  .ts { flex:0 0 auto; font-variant-numeric:tabular-nums; color:var(--muted); font-size:0.78rem;
    padding-top:2px; width:52px; }
  .row.active .ts { color:var(--accent); font-weight:600; }
  .body { flex:1 1 auto; min-width:0; }
  .meta { font-size:0.72rem; color:var(--muted); margin-bottom:1px; }
  .meta .spk { font-weight:600; }
  .tag-Indonesian { color:var(--id-tag); }
  .tag-English { color:var(--en-tag); }
  .text { font-size:0.95rem; line-height:1.4; }
  .en { font-size:0.85rem; line-height:1.35; color:var(--muted); margin-top:2px; display:none; }
  body.show-en .en { display:block; }
  .rowbtns { flex:0 0 auto; display:flex; gap:4px; opacity:0; }
  .row:hover .rowbtns, .loopbtn.active { opacity:1; }
  .loopbtn, .flagbtn { font-size:0.7rem; padding:3px 6px; }
  .loopbtn.active { background:var(--accent); color:#fff; border-color:var(--accent); }
  .flagbtn:hover { border-color:var(--bad); color:var(--bad); }
  .row.flagged { display:none; }
  body.show-flagged .row.flagged { display:flex; opacity:0.55; }
  body.show-flagged .row.flagged .rowbtns { opacity:1; }
  .row.flagged .flagbtn { background:var(--bad); color:#fff; border-color:var(--bad); }
  #hint { max-width:900px; margin:10px auto 0; padding:0 14px; font-size:0.78rem; color:var(--muted); }
</style>
</head>
<body>
<div id="topbar">
  <a class="back" href="index.html" style="color:var(--muted);font-size:0.78rem;text-decoration:none;">&larr;</a>
  <h1>__TITLE__</h1>
  <audio id="audio" controls preload="metadata" src="__AUDIO__"></audio>
  <div class="speeds">
    <button data-rate="0.6">0.6x</button>
    <button data-rate="0.75">0.75x</button>
    <button data-rate="1" class="active">1x</button>
    <button data-rate="1.25">1.25x</button>
  </div>
  <div class="tools">
    <button id="toggleEn">Show translations</button>
    <button id="toggleFlagged">Show flagged (0)</button>
    <input id="search" placeholder="jump to phrase…">
  </div>
</div>
<div id="hint">Click any line to jump the audio there. Hover a line for a "loop" button to repeat just that line (great for shadowing), or a "flag" button to hide a line that's silent/mis-transcribed junk. Speed buttons apply immediately. "Show translations" reveals an English gloss under each Indonesian line.</div>
<div id="list"></div>
<script>
const DATA = __DATA__;
const audio = document.getElementById('audio');
const list = document.getElementById('list');
let loopIdx = null;

function fmt(sec) {
  sec = Math.floor(sec);
  const h = Math.floor(sec/3600), m = Math.floor((sec%3600)/60), s = sec%60;
  const mm = h ? String(m).padStart(2,'0') : m;
  const ss = String(s).padStart(2,'0');
  return h ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
}

const FLAG_KEY = 'bahasa:flaggedLines:v1';
const MIN_CLIP_SECONDS = 2;
function loadFlags() {
  try { return JSON.parse(localStorage.getItem(FLAG_KEY)) || {}; } catch (e) { return {}; }
}
function saveFlags(f) { localStorage.setItem(FLAG_KEY, JSON.stringify(f)); }
let flags = loadFlags();

DATA.forEach((e, i) => {
  const row = document.createElement('div');
  row.className = 'row' + (flags[e.lineId] ? ' flagged' : '');
  row.dataset.idx = i;
  row.dataset.lineId = e.lineId;
  row.innerHTML = `
    <div class="ts">${fmt(e.sec)}</div>
    <div class="body">
      <div class="meta"><span class="spk">${e.speaker}</span> · <span class="tag-${e.lang}">${e.lang}</span></div>
      <div class="text"></div>
      <div class="en"></div>
    </div>
    <div class="rowbtns">
      <button class="loopbtn">loop</button>
      <button class="flagbtn" title="Flag this line as silent/mis-transcribed junk">flag</button>
    </div>
  `;
  row.querySelector('.text').textContent = e.text;
  row.querySelector('.en').textContent = e.en || '';
  row.addEventListener('click', (ev) => {
    if (ev.target.closest('.rowbtns')) return;
    loopIdx = null;
    document.querySelectorAll('.loopbtn.active').forEach(b => b.classList.remove('active'));
    audio.currentTime = e.sec;
    audio.play();
  });
  row.querySelector('.loopbtn').addEventListener('click', (ev) => {
    ev.stopPropagation();
    document.querySelectorAll('.loopbtn.active').forEach(b => b.classList.remove('active'));
    if (loopIdx === i) {
      loopIdx = null;
    } else {
      loopIdx = i;
      ev.target.classList.add('active');
      audio.currentTime = e.sec;
      audio.play();
    }
  });
  row.querySelector('.flagbtn').addEventListener('click', (ev) => {
    ev.stopPropagation();
    const nowFlagged = !flags[e.lineId];
    if (nowFlagged) flags[e.lineId] = true; else delete flags[e.lineId];
    saveFlags(flags);
    row.classList.toggle('flagged', nowFlagged);
    updateFlagCount();
  });
  list.appendChild(row);
});

const rows = [...list.children];

function updateFlagCount() {
  const n = rows.filter(r => r.classList.contains('flagged')).length;
  toggleFlaggedBtn.textContent = (showFlagged ? 'Hide flagged' : 'Show flagged') + ` (${n})`;
}

audio.addEventListener('timeupdate', () => {
  const t = audio.currentTime;
  if (loopIdx !== null) {
    const start = DATA[loopIdx].sec;
    const rawEnd = DATA[loopIdx+1] ? DATA[loopIdx+1].sec : start + 6;
    const end = Math.max(rawEnd, start + MIN_CLIP_SECONDS);
    if (t >= end || t < start) audio.currentTime = start;
  }
  let cur = -1;
  for (let i = 0; i < DATA.length; i++) {
    if (DATA[i].sec <= t) cur = i; else break;
  }
  rows.forEach(r => r.classList.remove('active'));
  if (cur >= 0) {
    const r = rows[cur];
    r.classList.add('active');
    const rect = r.getBoundingClientRect();
    if (rect.top < 60 || rect.bottom > window.innerHeight - 20) {
      r.scrollIntoView({block:'center', behavior:'smooth'});
    }
  }
});

document.querySelectorAll('.speeds button').forEach(b => {
  b.addEventListener('click', () => {
    document.querySelectorAll('.speeds button').forEach(x => x.classList.remove('active'));
    b.classList.add('active');
    audio.playbackRate = parseFloat(b.dataset.rate);
  });
});

const EN_KEY = 'bahasa:showTranslations';
const toggleEnBtn = document.getElementById('toggleEn');
function setShowEn(on) {
  document.body.classList.toggle('show-en', on);
  toggleEnBtn.classList.toggle('active', on);
  toggleEnBtn.textContent = on ? 'Hide translations' : 'Show translations';
  localStorage.setItem(EN_KEY, on ? '1' : '0');
}
toggleEnBtn.addEventListener('click', () => setShowEn(!document.body.classList.contains('show-en')));
setShowEn(localStorage.getItem(EN_KEY) === '1');

const toggleFlaggedBtn = document.getElementById('toggleFlagged');
let showFlagged = false;
toggleFlaggedBtn.addEventListener('click', () => {
  showFlagged = !showFlagged;
  document.body.classList.toggle('show-flagged', showFlagged);
  updateFlagCount();
});
updateFlagCount();

document.getElementById('search').addEventListener('keydown', (ev) => {
  if (ev.key !== 'Enter') return;
  const q = ev.target.value.trim().toLowerCase();
  if (!q) return;
  const hit = DATA.findIndex(e => e.text.toLowerCase().includes(q));
  if (hit >= 0) {
    rows[hit].scrollIntoView({block:'center', behavior:'smooth'});
    rows[hit].style.outline = '2px solid var(--accent)';
    setTimeout(() => rows[hit].style.outline = '', 1200);
  }
});
</script>
</body>
</html>
"""


def main():
    p = argparse.ArgumentParser()
    p.add_argument("transcript")
    p.add_argument("audio_path")
    p.add_argument("output")
    p.add_argument("--title", default="Conversation")
    p.add_argument("--translations", default=None, help="JSON file mapping entry idx -> English translation")
    p.add_argument("--name", default=None, help="Conversation slug used for flag/quiz line IDs (default: derived from transcript filename)")
    args = p.parse_args()

    name = args.name or derive_name(args.transcript)
    with open(args.transcript, encoding="utf-8") as f:
        raw = f.read()
    entries = parse(raw, name)

    if args.translations:
        with open(args.translations, encoding="utf-8") as f:
            translations = json.load(f)
        n_applied = 0
        for i, e in enumerate(entries):
            en = translations.get(str(i))
            if en:
                e["en"] = en
                n_applied += 1
        print(f"applied {n_applied} translations ({len(entries)} total entries)")

    html = (
        PAGE.replace("__TITLE__", escape(args.title))
        .replace("__AUDIO__", escape(args.audio_path))
        .replace("__DATA__", json.dumps(entries, ensure_ascii=False))
    )
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"wrote {args.output}: {len(entries)} lines, audio={args.audio_path}")


if __name__ == "__main__":
    main()
