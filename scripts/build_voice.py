#!/usr/bin/env python3
"""
Build voice.html — the hands-free flashcard drill.

Tap Start once and put the phone down: the page says an Indonesian word, listens
for you to say what it means, tells you the answer, and moves on, with no more
taps. Answer with the meaning and it grades you itself ("Yes — friend" counts
as Good); say a grade instead ("good", "hard", "easy", "don't know") and it
takes yours. Anything it can't place, it reads the answer and asks "right or
wrong?". "Repeat", "skip", "go back" and "stop" work at any point.

It schedules into the SAME FSRS store as flashcards.html (keyed by front) and
logs reviews as kind 'flash', so a word drilled by voice is a word reviewed:
streaks, stats and gist sync all see it.

Platform limits, stated on the page rather than discovered: browsers only
listen while the page is on screen, so the drill holds a screen wake lock and
offers a pocket lock (black screen that ignores touches) instead of letting
the phone sleep. Locking the phone pauses it.

Usage:
    python3 build_voice.py
"""
import json
from pathlib import Path

from _srs_js import SRS_JS
from _sync_js import SYNC_JS
from _tts_js import TTS_JS
from _voice_js import VOICE_JS
from _pwa_meta import PWA_META_TAGS, PWA_SW_JS
from build_flashcards import load_decks

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "voice.html"

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
__PWA_META__
<title>Voice drill — Learning Bahasa Indonesian</title>
<style>
  :root { color-scheme: light dark; --bg:#fff; --fg:#1a1a1a; --muted:#6b7280; --line:#e5e7eb;
    --accent:#2563eb; --card:#f9fafb; --again:#dc2626; --hard:#d97706; --good:#16a34a; --easy:#2563eb; }
  @media (prefers-color-scheme: dark) {
    :root { --bg:#111318; --fg:#e7e9ee; --muted:#9aa1ac; --line:#2a2e37; --accent:#5b9dff;
      --card:#1a1d24; --again:#f87171; --hard:#fbbf24; --good:#4ade80; --easy:#7cb0ff; }
  }
  * { box-sizing:border-box; }
  html, body { margin:0; background:var(--bg); color:var(--fg);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }
  .wrap { max-width:560px; margin:0 auto; padding:24px 16px 60px; }
  .top { display:flex; justify-content:space-between; align-items:baseline; gap:10px; margin-bottom:14px; }
  h1 { font-size:1.15rem; margin:0; }
  a.back { color:var(--muted); font-size:0.8rem; text-decoration:none; }
  #card { border:1px solid var(--line); border-radius:14px; background:var(--card);
    padding:22px 20px; min-height:230px; margin-bottom:14px; text-align:center; }
  .phase { font-size:0.75rem; text-transform:uppercase; letter-spacing:0.05em; color:var(--muted);
    min-height:1.2em; }
  .phase.listening { color:var(--good); }
  .phase.listening::before { content:''; display:inline-block; width:8px; height:8px; border-radius:50%;
    background:var(--good); margin-right:6px; vertical-align:1px; animation:pulse 1.2s infinite; }
  @keyframes pulse { 50% { opacity:0.25; } }
  .front { font-size:2rem; font-weight:600; margin:18px 0 6px; min-height:2.4rem; overflow-wrap:anywhere; }
  .answer { font-size:1.05rem; color:var(--muted); min-height:1.5rem; }
  .heard { margin-top:16px; font-size:0.9rem; color:var(--muted); min-height:1.3rem; font-style:italic; }
  .verdict { margin-top:8px; font-weight:600; min-height:1.4rem; }
  .verdict.g1 { color:var(--again); } .verdict.g2 { color:var(--hard); }
  .verdict.g3 { color:var(--good); } .verdict.g4 { color:var(--easy); }
  .controls { display:flex; gap:8px; flex-wrap:wrap; margin-bottom:14px; }
  button { font:inherit; font-size:0.9rem; padding:10px 14px; border-radius:10px;
    border:1px solid var(--line); background:transparent; color:var(--fg); cursor:pointer; }
  button:disabled { opacity:0.4; cursor:default; }
  button.primary { background:var(--accent); border-color:var(--accent); color:#fff; flex:1; font-weight:600; }
  .stats { color:var(--muted); font-size:0.82rem; margin-bottom:16px; }
  .settings { border:1px solid var(--line); border-radius:12px; padding:12px 14px; font-size:0.85rem; }
  .settings label { display:flex; justify-content:space-between; align-items:center; gap:10px; padding:6px 0; }
  .settings select { font-size:0.85rem; padding:4px 6px; border-radius:6px; border:1px solid var(--line);
    background:var(--bg); color:var(--fg); max-width:55%; }
  .help { color:var(--muted); font-size:0.82rem; line-height:1.5; margin-top:16px; }
  .help b { color:var(--fg); }
  .warn { border:1px solid var(--again); color:var(--fg); border-radius:10px; padding:10px 12px;
    font-size:0.85rem; margin-bottom:14px; line-height:1.45; }
  #lock { position:fixed; inset:0; background:#000; color:#555; z-index:10; display:flex;
    flex-direction:column; align-items:center; justify-content:center; gap:14px; text-align:center;
    touch-action:none; user-select:none; -webkit-user-select:none; padding:24px; }
  #lock[hidden] { display:none; }
  #lock .lockPhase { font-size:0.95rem; color:#666; }
  #lock .lockFront { font-size:1.6rem; color:#777; min-height:2rem; }
  #lock .hold { margin-top:40px; border:1px solid #333; border-radius:999px; padding:14px 22px;
    color:#666; font-size:0.85rem; }
  #lock .hold.holding { border-color:#888; color:#aaa; }
</style>
</head>
<body>
<div class="wrap">
  <div class="top">
    <h1>Voice drill</h1>
    <a class="back" href="index.html">&larr; Home</a>
  </div>
  <div class="warn" id="unsupported" hidden></div>
  <div id="card">
    <div class="phase" id="phase">Tap Start, then put the phone down</div>
    <div class="front" id="front"></div>
    <div class="answer" id="answer"></div>
    <div class="heard" id="heard"></div>
    <div class="verdict" id="verdict"></div>
  </div>
  <div class="controls">
    <button class="primary" id="startBtn">Start</button>
    <button id="skipBtn" disabled>Skip</button>
    <button id="undoBtn" disabled>&#8630; Go back</button>
    <button id="lockBtn" disabled>Pocket lock</button>
  </div>
  <div class="stats" id="stats"></div>
  <div class="settings">
    <label>Words <select id="tagSel"></select></label>
    <label>New words per session <select id="newSel">
      <option value="0">0 — reviews only</option><option value="5">5</option>
      <option value="10">10</option><option value="20">20</option></select></label>
    <label>Time to answer <select id="waitSel">
      <option value="5000">5 s</option><option value="8000">8 s</option>
      <option value="12000">12 s</option></select></label>
  </div>
  <div class="help">
    <p><b>How it works.</b> You hear an Indonesian word. Say what it means in English
    (&ldquo;friend&rdquo;, &ldquo;to eat&rdquo;) and it grades you. Or grade yourself instead:
    <b>good</b>, <b>easy</b>, <b>hard</b>, or <b>don&rsquo;t know</b>. Either way you hear the
    answer before the next word. If it can&rsquo;t tell, it reads the answer and asks
    <b>right or wrong?</b></p>
    <p>Any time: <b>repeat</b>, <b>skip</b>, <b>go back</b>, <b>stop</b>. Two silences in a row
    pause it; say <b>resume</b> to carry on.</p>
    <p><b>Keep the screen on.</b> Browsers stop listening when the phone locks, so this page
    keeps the screen awake. Use <b>Pocket lock</b> to black it out and ignore touches (hold the
    button on the black screen to unlock). Earbuds help: the mic won&rsquo;t hear the page
    talking, and iPhone plays louder through them while it&rsquo;s listening.</p>
    <p>Reviews here count as flashcard reviews &mdash; same schedule, same streak, same sync.</p>
  </div>
</div>
<div id="lock" hidden>
  <div class="lockPhase" id="lockPhase"></div>
  <div class="lockFront" id="lockFront"></div>
  <div class="hold" id="holdBtn">Hold to unlock</div>
</div>
<script>
__SRS_JS__
__SYNC_JS__
__TTS_JS__
__VOICE_JS__
__PWA_SW__
const BUILTIN_DECK = __DATA__;
const SRS_KEY = 'bahasa:flashcards:fsrs:v1';
const PREFS_KEY = 'bahasa:voice:prefs:v1';
const SR = window.SpeechRecognition || window.webkitSpeechRecognition;

let srs = srsLoad(SRS_KEY);
const $ = id => document.getElementById(id);

// Same deck as flashcards.html: built-ins minus removed, plus custom cards.
function computeDeck() {
  const removed = syncRead(REMOVED_CARDS_KEY);
  const custom = syncRead(CUSTOM_CARDS_KEY);
  const byFront = new Map();
  BUILTIN_DECK.forEach(d => { if (!removed[d.front]) byFront.set(d.front, d); });
  Object.values(custom).forEach(d => byFront.set(d.front, Object.assign({}, d, {
    tags: Array.isArray(d.tags) && d.tags.length ? d.tags : (d.tag ? [d.tag] : ['custom']),
  })));
  return [...byFront.values()];
}
let DECK = computeDeck();

const prefs = Object.assign({ tag: '', newPer: 5, waitMs: 8000 }, srsLoad(PREFS_KEY));
function savePrefs() { srsSave(PREFS_KEY, prefs); }

function renderTagSel() {
  const tags = [...new Set(DECK.flatMap(d => d.tags))].sort();
  if (prefs.tag && !tags.includes(prefs.tag)) prefs.tag = '';
  $('tagSel').innerHTML = '<option value="">All words</option>' +
    tags.map(t => `<option value="${t.replace(/"/g, '&quot;')}">${t}</option>`).join('');
  $('tagSel').value = prefs.tag;
}
renderTagSel();
$('newSel').value = String(prefs.newPer);
$('waitSel').value = String(prefs.waitMs);
$('tagSel').onchange = e => { prefs.tag = e.target.value; savePrefs(); renderStats(); };
$('newSel').onchange = e => { prefs.newPer = Number(e.target.value); savePrefs(); renderStats(); };
$('waitSel').onchange = e => { prefs.waitMs = Number(e.target.value); savePrefs(); };

function setSyncState() {}
syncRemoteAutoPull(() => { srs = srsLoad(SRS_KEY); DECK = computeDeck(); renderTagSel(); renderStats(); }, setSyncState);

// ---- Session state ---------------------------------------------------------
let running = false;
let runId = 0;              // bumped to cancel whatever the loop is awaiting
let current = null;
let newShown = 0;
let session = { done: 0, right: 0 };
let forcedNext = null;      // a card "go back" put back on top

function pool() {
  return DECK.filter(d => !prefs.tag || d.tags.includes(prefs.tag));
}
function pickNext() {
  if (forcedNext) { const c = forcedNext; forcedNext = null; return c; }
  const p = pool();
  const reviews = p.filter(d => srs[d.front] && srsIsDue(srs[d.front]));
  let due = reviews;
  if (!due.length && newShown < prefs.newPer) due = p.filter(d => !srs[d.front]);
  if (!due.length) return null;
  return srsPickAvoidingRecent(due, srsWordKeys);
}

function renderStats() {
  const p = pool();
  const due = p.filter(d => srs[d.front] && srsIsDue(srs[d.front])).length;
  const fresh = p.filter(d => !srs[d.front]).length;
  const s = session.done
    ? `This session: ${session.done} reviewed, ${session.right} right. `
    : '';
  $('stats').textContent = `${s}${due} due · ${fresh} new available`;
}
renderStats();

function show(phase, opts) {
  opts = opts || {};
  const ph = $('phase');
  ph.textContent = phase;
  ph.classList.toggle('listening', !!opts.listening);
  $('lockPhase').textContent = phase;
  if ('front' in opts) { $('front').textContent = opts.front; $('lockFront').textContent = opts.front; }
  if ('answer' in opts) $('answer').textContent = opts.answer;
  if ('heard' in opts) $('heard').textContent = opts.heard ? '“' + opts.heard + '”' : '';
  if ('verdict' in opts) {
    $('verdict').textContent = opts.verdict || '';
    $('verdict').className = 'verdict' + (opts.grade ? ' g' + opts.grade : '');
  }
}

// ---- Audio out -------------------------------------------------------------
let enVoice = null;
function pickEnVoice() {
  if (!ttsHasSupport) return;
  const vs = speechSynthesis.getVoices() || [];
  enVoice = vs.find(v => /^en[-_]US/i.test(v.lang) && v.localService)
    || vs.find(v => /^en[-_]US/i.test(v.lang)) || vs.find(v => /^en\b/i.test(v.lang)) || null;
}
pickEnVoice();
ttsOnVoicesChanged(pickEnVoice);

function sayEn(text) {
  if (!ttsHasSupport || !text) return Promise.resolve(false);
  speechSynthesis.cancel();
  return new Promise(resolve => {
    const u = new SpeechSynthesisUtterance(text);
    if (enVoice) { u.voice = enVoice; u.lang = enVoice.lang; } else u.lang = 'en-US';
    u.rate = 1.0;
    let done = false;
    const fin = ok => { if (!done) { done = true; resolve(ok); } };
    u.onend = () => fin(true);
    u.onerror = () => fin(false);
    // iOS occasionally never fires 'end'; don't let that stall the drill.
    setTimeout(() => fin(false), 1500 + text.length * 120);
    speechSynthesis.speak(u);
  });
}

function sayId(card) {
  const word = card.front.split(' / ')[0].trim();
  return ttsSay(word, card.llSrc || card.wordSrc, 0.9);
}

// iOS only lets a page make sound after a tap. The Start tap plays silence
// through the same <audio> element and speech engine the drill reuses, which
// unlocks both for the rest of the session.
const SILENCE = 'data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAIA+AAACABAAZGF0YQAAAAA=';
function unlockAudio() {
  if (ttsClipAudio) { ttsClipAudio.src = SILENCE; ttsClipAudio.play().catch(() => {}); }
  if (ttsHasSupport) speechSynthesis.speak(new SpeechSynthesisUtterance(' '));
}

const pause = ms => new Promise(r => setTimeout(r, ms));

// ---- Audio in --------------------------------------------------------------
// One short recognition per answer window rather than a single continuous
// session: continuous mode on iOS drops out after a while and hears the page's
// own voice. Listening only after the audio finishes keeps the page from
// grading itself. Resolves to the recognizer's alternatives, best first,
// or [] for silence.
let activeRec = null;
let fatalMic = null;

function listen(ms) {
  return new Promise(resolve => {
    if (!SR) { resolve([]); return; }
    const rec = new SR();
    activeRec = rec;
    rec.lang = 'en-US';
    rec.interimResults = true;
    rec.maxAlternatives = 3;
    rec.continuous = false;
    let alts = [];
    let settled = false;
    let deadline = Date.now() + ms;
    const finish = () => {
      if (settled) return;
      settled = true;
      clearInterval(tick);
      if (activeRec === rec) activeRec = null;
      resolve(alts.filter(Boolean));
    };
    rec.onresult = e => {
      const res = e.results[e.results.length - 1];
      const texts = [];
      for (let i = 0; i < res.length; i++) texts.push(res[i].transcript.trim());
      // Earlier final chunks (rare without continuous) are kept in front.
      const before = [];
      for (let i = 0; i < e.results.length - 1; i++) before.push(e.results[i][0].transcript.trim());
      const prefix = before.join(' ');
      alts = texts.map(t => (prefix ? prefix + ' ' + t : t));
      show('Heard', { listening: true, heard: alts[0] });
      // Still talking: don't cut the sentence off at the deadline.
      deadline = Math.max(deadline, Date.now() + 1200);
      if (res.isFinal) { try { rec.stop(); } catch (_) {} }
    };
    rec.onerror = e => {
      if (e.error === 'not-allowed' || e.error === 'service-not-allowed' || e.error === 'audio-capture') {
        fatalMic = e.error;
      }
    };
    rec.onend = finish;
    const tick = setInterval(() => {
      if (Date.now() > deadline) { try { rec.stop(); } catch (_) {} }
      if (Date.now() > deadline + 2500) { try { rec.abort(); } catch (_) {} finish(); }
    }, 200);
    try { rec.start(); } catch (_) { finish(); }
  });
}

function stopListening() {
  if (activeRec) { try { activeRec.abort(); } catch (_) {} activeRec = null; }
}

// ---- Rating ----------------------------------------------------------------
const GRADE_NAME = { 1: 'Again', 2: 'Hard', 3: 'Good', 4: 'Easy' };

function rate(card, grade) {
  const isNew = !srs[card.front];
  if (isNew) newShown++;
  const ts = srsLogReview('flash', grade, isNew, card.front);
  srsPushUndo({ card, front: card.front, prev: srs[card.front] || null, ts, isNew });
  srs[card.front] = fsrsNextState(srs[card.front], grade, Date.now());
  srsSave(SRS_KEY, srs);
  syncRemoteQueuePush(setSyncState);
  session.done++;
  if (grade >= 3) session.right++;
  $('undoBtn').disabled = false;
  renderStats();
}

function undoLast() {
  const u = srsPopUndo();
  if (!u) return null;
  const restored = srsRestoreState(u.prev);
  if (restored) srs[u.front] = restored; else delete srs[u.front];
  srsSave(SRS_KEY, srs);
  srsUnlogReview(u.ts);
  syncRemoteQueuePush(setSyncState);
  session.done = Math.max(0, session.done - 1);
  if (u.isNew) newShown = Math.max(0, newShown - 1);
  $('undoBtn').disabled = !srsUndoDepth();
  renderStats();
  return u.card;
}

// ---- The drill -------------------------------------------------------------
class Cancelled extends Error {}
function guard(id) { if (id !== runId || !running) throw new Cancelled(); }

// Plays the card, listens, and returns what the answer window decided:
// a grade, or a control word for the loop to act on.
async function drillCard(id, card) {
  let silences = 0;
  let repeats = 0;
  for (;;) {
    show('Listen', { front: card.front.split(' / ')[0], answer: '', heard: '', verdict: '' });
    await sayId(card);
    guard(id);
    await pause(250);
    guard(id);
    show('Listening — what does it mean?', { listening: true });
    const alts = await listen(prefs.waitMs);
    guard(id);
    if (fatalMic) return { cmd: 'mic' };
    const heard = alts[0] || '';
    const r = alts.some(a => voiceClassifyAnswer(a, card.back).kind === 'correct')
      ? { kind: 'correct' } : voiceClassifyAnswer(heard, card.back);
    show(r.kind === 'silent' ? '' : 'Heard', { heard });
    if (r.kind === 'silent') {
      if (++silences >= 2) return { cmd: 'idle' };
      continue;
    }
    if (r.kind === 'command') {
      if (r.cmd === 'repeat' && repeats++ < 3) continue;
      if (r.cmd === 'repeat') return { grade: 1 };
      return { cmd: r.cmd };
    }
    const gloss = voiceSpokenGloss(card.back);
    show('Answer', { answer: card.back });
    if (r.kind === 'correct') {
      show('Answer', { verdict: 'Right — Good', grade: 3 });
      await sayEn('Yes. ' + gloss);
      return { grade: 3 };
    }
    if (r.kind === 'grade') {
      show('Answer', { verdict: GRADE_NAME[r.grade], grade: r.grade });
      await sayEn(gloss);
      return { grade: r.grade };
    }
    // Said something that isn't the gloss, but could be a fine synonym.
    for (let ask = 0; ask < 2; ask++) {
      await sayEn(ask ? 'Right or wrong?' : gloss + '. Right or wrong?');
      guard(id);
      await pause(200);
      show('Right or wrong?', { listening: true });
      const c = voiceClassifyConfirm((await listen(5000))[0] || '');
      guard(id);
      if (fatalMic) return { cmd: 'mic' };
      if (c.kind === 'grade') {
        show('Answer', { verdict: GRADE_NAME[c.grade], grade: c.grade });
        return { grade: c.grade };
      }
      if (c.kind === 'command') return { cmd: c.cmd };
    }
    return { cmd: 'skip' };
  }
}

async function waitForResume(id) {
  show('Paused — say “resume”', { listening: true });
  await sayEn('Pausing. Say resume when you’re ready.');
  const until = Date.now() + 10 * 60 * 1000;
  while (Date.now() < until) {
    guard(id);
    const alts = await listen(10000);
    guard(id);
    if (fatalMic) return false;
    if (alts.some(voiceIsResume)) return true;
  }
  return false;
}

async function run() {
  const id = ++runId;
  try {
    while (true) {
      guard(id);
      const card = pickNext();
      if (!card) {
        show('All caught up', { front: '', answer: pool().length ? 'Nothing due right now.' : 'No words in this filter.', heard: '', verdict: '' });
        await sayEn(session.done ? `All caught up. ${session.right} of ${session.done} right.` : 'Nothing due right now.');
        stop();
        return;
      }
      current = card;
      srsNoteShown(srsWordKeys(card));
      const out = await drillCard(id, card);
      guard(id);
      if (out.grade) {
        rate(card, out.grade);
        current = null;
        await pause(600);
        continue;
      }
      if (out.cmd === 'mic') { micBlocked(); stop(); return; }
      if (out.cmd === 'stop') { await sayEn('Stopped.'); stop(); return; }
      if (out.cmd === 'skip') { show('Skipped', { verdict: '' }); continue; }
      if (out.cmd === 'undo') {
        const back = undoLast();
        if (back) { forcedNext = back; await sayEn('Going back.'); }
        else await sayEn('Nothing to undo.');
        continue;
      }
      if (out.cmd === 'idle') {
        forcedNext = card;
        if (!(await waitForResume(id))) {
          if (fatalMic) micBlocked();
          stop();
          return;
        }
        await sayEn('OK.');
      }
    }
  } catch (e) {
    if (!(e instanceof Cancelled)) { console.error(e); stop(); }
  }
}

// ---- Wake lock + pocket lock -----------------------------------------------
let wakeLock = null;
async function holdScreen() {
  try {
    if ('wakeLock' in navigator && !wakeLock) {
      wakeLock = await navigator.wakeLock.request('screen');
      wakeLock.addEventListener('release', () => { wakeLock = null; });
    }
  } catch (_) {}
}
function releaseScreen() {
  if (wakeLock) { wakeLock.release().catch(() => {}); wakeLock = null; }
}

function setLocked(on) {
  $('lock').hidden = !on;
}
(function wireHold() {
  const btn = $('holdBtn');
  let timer = null;
  const cancel = () => { clearTimeout(timer); timer = null; btn.classList.remove('holding'); };
  btn.addEventListener('pointerdown', e => {
    e.preventDefault();
    btn.classList.add('holding');
    timer = setTimeout(() => { cancel(); setLocked(false); }, 1500);
  });
  ['pointerup', 'pointercancel', 'pointerleave'].forEach(t => btn.addEventListener(t, cancel));
  $('lock').addEventListener('touchstart', e => { if (e.target !== btn) e.preventDefault(); }, { passive: false });
})();

// ---- Start / stop ----------------------------------------------------------
function start() {
  if (running) return;
  if (!SR) return;
  fatalMic = null;
  unlockAudio();
  running = true;
  holdScreen();
  $('startBtn').textContent = 'Stop';
  $('skipBtn').disabled = false;
  $('lockBtn').disabled = false;
  run();
}

function stop() {
  running = false;
  runId++;
  stopListening();
  ttsStop();
  releaseScreen();
  setLocked(false);
  $('startBtn').textContent = session.done ? 'Resume' : 'Start';
  $('skipBtn').disabled = true;
  $('lockBtn').disabled = true;
  show(session.done ? 'Stopped' : 'Tap Start, then put the phone down', { listening: false });
  if (current) forcedNext = forcedNext || current;
}

function micBlocked() {
  const w = $('unsupported');
  w.hidden = false;
  w.innerHTML = fatalMic === 'service-not-allowed'
    ? 'Speech recognition is turned off on this device. On iPhone: Settings &rarr; Siri &rarr; turn on <b>Siri</b> (or Settings &rarr; General &rarr; Keyboard &rarr; <b>Enable Dictation</b>), then reload.'
    : 'Microphone access was blocked. Allow the microphone for this site (on iPhone: Settings &rarr; Safari &rarr; Microphone), then reload.';
}

$('startBtn').onclick = () => (running ? stop() : start());
$('skipBtn').onclick = () => {
  if (!running) return;
  // Restart the loop on a fresh card; the skipped one stays unrated.
  runId++;
  stopListening();
  ttsStop();
  running = true;
  run();
};
$('undoBtn').onclick = () => {
  const back = undoLast();
  if (!back) return;
  forcedNext = back;
  if (running) { runId++; stopListening(); ttsStop(); run(); }
  else show('Went back', { front: back.front.split(' / ')[0], answer: '', heard: '', verdict: '' });
};
$('lockBtn').onclick = () => { if (running) setLocked(true); };

// Locking the phone or switching apps kills recognition; stop cleanly so the
// screen doesn't come back to a loop stuck mid-listen.
document.addEventListener('visibilitychange', () => {
  if (document.hidden && running) {
    stop();
    show('Paused — the phone locked. Tap Resume.');
  }
});

if (!SR) {
  const w = $('unsupported');
  w.hidden = false;
  const standalone = window.navigator.standalone || matchMedia('(display-mode: standalone)').matches;
  w.innerHTML = standalone
    ? 'This browser doesn&rsquo;t offer speech recognition inside the home-screen app. Open this page in <b>Safari</b> (or Chrome) instead.'
    : 'This browser doesn&rsquo;t offer speech recognition. Use Safari on iPhone, or Chrome.';
  $('startBtn').disabled = true;
}
</script>
</body>
</html>
"""

# Only what the drill reads; the flashcard page's example sentences and
# family-clip fields would triple the page for nothing.
FIELDS = ("front", "back", "tags", "llSrc", "wordSrc")


def main():
    deck = [{k: c[k] for k in FIELDS if k in c} for c in load_decks()]
    html = (
        PAGE.replace("__SRS_JS__", SRS_JS)
        .replace("__SYNC_JS__", SYNC_JS)
        .replace("__TTS_JS__", TTS_JS)
        .replace("__VOICE_JS__", VOICE_JS)
        .replace("__PWA_META__", PWA_META_TAGS)
        .replace("__PWA_SW__", PWA_SW_JS)
        .replace("__DATA__", json.dumps(deck, ensure_ascii=False))
    )
    OUT.write_text(html, encoding="utf-8")
    clips = sum(1 for c in deck if c.get("llSrc") or c.get("wordSrc"))
    print(f"wrote {OUT} with {len(deck)} cards; {clips} with a recorded word clip, "
          f"{len(deck) - clips} use the device's Indonesian voice")


if __name__ == "__main__":
    main()
