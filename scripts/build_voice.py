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
    <label>Recognition <select id="engineSel">
      <option value="whisper">On this phone (no chime)</option>
      <option value="safari">Safari</option></select></label>
  </div>
  <div class="help">
    <p><b>How it works.</b> You hear an Indonesian word. Say what it means in English
    (&ldquo;friend&rdquo;, &ldquo;to eat&rdquo;) and it grades you. Or grade yourself instead:
    <b>good</b>, <b>easy</b>, <b>hard</b>, or <b>don&rsquo;t know</b>. Either way you hear the
    answer before the next word. If it can&rsquo;t tell, it reads the answer and asks
    <b>right or wrong?</b></p>
    <p>Any time: <b>repeat</b>, <b>skip</b>, <b>stop</b>, or <b>go back</b> to return to the word before (its grade is taken back so you can answer it again). Two silences in a row
    pause it; say <b>resume</b> to carry on.</p>
    <p><b>Recognition.</b> &ldquo;On this phone&rdquo; opens the mic once and understands you on the
    phone itself, so there&rsquo;s no chime between words. It downloads a ~40 MB speech model the first
    time (use Wi-Fi). &ldquo;Safari&rdquo; uses Apple&rsquo;s recognizer instead, which chimes every word.</p>
    <p><b>Keep the screen on.</b> Browsers stop listening when the phone locks, so this page
    keeps the screen awake. Use <b>Pocket lock</b> to black it out and ignore touches (hold the
    button on the black screen to unlock). Earbuds help: the mic won&rsquo;t hear the page
    talking, and iPhone plays louder through them while it&rsquo;s listening.</p>
    <p>Reviews here count as flashcard reviews &mdash; same schedule, same streak, same sync.</p>
    <p><a href="whisper-test.html">Speed test</a> (temporary: on-device recognition without the iPhone chime).</p>
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

const prefs = Object.assign({ tag: '', newPer: 5, waitMs: 8000, engine: '' }, srsLoad(PREFS_KEY));
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
$('engineSel').onchange = e => { prefs.engine = e.target.value; savePrefs(); };

function setSyncState() {}
syncRemoteAutoPull(() => { srs = srsLoad(SRS_KEY); DECK = computeDeck(); renderTagSel(); renderStats(); }, setSyncState);

// ---- Diagnostic log --------------------------------------------------------
// Temporary. "The first word works, the second doesn't" only happens on the
// iPhone, which can't be reproduced off the device, so the drill records each
// step (audio out, every recognizer event, what was decided) and uploads it to
// the progress-sync gist as its own file. The progress file is never touched.
const VLOG_KEY = 'bahasa:voice:log:v1';
const VLOG_FILE = 'voice-debug-log.json';
const VLOG_CAP = 600;
let vlogT0 = Date.now();
let vlogEntries = (() => { try { return JSON.parse(localStorage.getItem(VLOG_KEY)) || []; } catch (_) { return []; } })();
let vlogTimer = null;
function vlog(ev, d) {
  vlogEntries.push({ t: Date.now() - vlogT0, ev, d: d === undefined ? '' : d });
  if (vlogEntries.length > VLOG_CAP) vlogEntries = vlogEntries.slice(-VLOG_CAP);
  try { localStorage.setItem(VLOG_KEY, JSON.stringify(vlogEntries)); } catch (_) {}
  clearTimeout(vlogTimer);
  vlogTimer = setTimeout(vlogSend, 4000);
}
async function vlogSend() {
  const token = localStorage.getItem('bahasa:sync:token');
  const gist = localStorage.getItem('bahasa:sync:gistId');
  if (!token || !gist || !vlogEntries.length) return;
  try {
    await fetch('https://api.github.com/gists/' + gist, {
      method: 'PATCH',
      headers: { 'Authorization': 'Bearer ' + token, 'Accept': 'application/vnd.github+json' },
      body: JSON.stringify({ files: { [VLOG_FILE]: { content: JSON.stringify({
        sent: new Date().toISOString(), ua: navigator.userAgent,
        standalone: !!(navigator.standalone || matchMedia('(display-mode: standalone)').matches),
        log: vlogEntries }) } } }),
    });
  } catch (_) {}
}
// A log saved by an earlier session that couldn't get out (no sync token at
// the time) goes out as soon as the page opens, before a new session's log
// replaces it.
setTimeout(vlogSend, 1500);

// ---- Session state ---------------------------------------------------------
let running = false;
let runId = 0;              // bumped to cancel whatever the loop is awaiting
let current = null;
let newShown = 0;
let session = { done: 0, right: 0 };
let upNext = [];           // cards to show before drawing: "go back" puts them here
let history = [];          // cards finished this session, newest last: {card, rated}
const HISTORY_CAP = 30;

function pool() {
  return DECK.filter(d => !prefs.tag || d.tags.includes(prefs.tag));
}
function pickNext() {
  if (upNext.length) return upNext.shift();
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
  // cancel() immediately followed by speak() can drop the utterance on iOS,
  // so only cancel when something is actually speaking.
  if (speechSynthesis.speaking || speechSynthesis.pending) speechSynthesis.cancel();
  vlog('sayEn', text);
  return new Promise(resolve => {
    const u = new SpeechSynthesisUtterance(text);
    if (enVoice) { u.voice = enVoice; u.lang = enVoice.lang; } else u.lang = 'en-US';
    u.rate = 1.0;
    let done = false;
    const fin = (ok, why) => { if (!done) { done = true; vlog('sayEn.end', why); resolve(ok); } };
    u.onend = () => fin(true, 'end');
    u.onerror = e => fin(false, 'error:' + (e && e.error));
    // iOS occasionally never fires 'end'; don't let that stall the drill.
    setTimeout(() => fin(false, 'timeout'), 1500 + text.length * 120);
    speechSynthesis.speak(u);
  });
}

// If iOS won't play the clip after the mic has been in use (it can leave the
// <audio> element stuck with no 'ended' and no error), notice within
// STALL_MS that playback isn't moving and say the word with the device's
// Indonesian voice instead, rather than waiting forever on the second word.
const STALL_MS = 1500;
const CLIP_CAP_MS = 6000;
function playClipWatched(src) {
  return new Promise(resolve => {
    let done = false, lastPos = -1, lastMove = Date.now();
    const t0 = Date.now();
    const fin = why => { if (!done) { done = true; clearInterval(watch); resolve(why); } };
    const watch = setInterval(() => {
      const pos = ttsClipAudio ? ttsClipAudio.currentTime : 0;
      if (pos !== lastPos) { lastPos = pos; lastMove = Date.now(); }
      if (Date.now() - lastMove > STALL_MS) fin('stalled');
      else if (Date.now() - t0 > CLIP_CAP_MS) fin('timeout');
    }, 250);
    ttsPlayClip(src).then(ok => fin(ok ? 'end' : 'failed'));
  });
}

async function sayId(card) {
  const word = card.front.split(' / ')[0].trim();
  const src = card.llSrc || card.wordSrc;
  const t0 = Date.now();
  vlog('sayId', word + (src ? ' clip' : ' tts'));
  let why = src && ttsHasClip(src) ? await playClipWatched(src) : 'noclip';
  if (why !== 'end') {
    ttsStopClip();
    if (ttsVoice) {
      const spoke = await Promise.race([ttsSpeak(word, 0.9), pause(4000).then(() => false)]);
      why += spoke ? '+synth' : '+synthFailed';
    }
  }
  vlog('sayId.end', why + ' ' + (Date.now() - t0) + 'ms');
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
// One recognition session per answer window, not one for the whole drill:
// a long-lived session hears the page's own voice, and listening only after
// the audio finishes keeps the page from grading itself.
//
// Safari's recognizer ends on its own, often within a second and before a
// one-word answer like "good" is out, which read as silence and replayed the
// word. So the window is ours, not the recognizer's: if it ends early it is
// restarted until the window closes, and the window closes once you have
// stopped talking for SPEECH_GAP_MS rather than on the recognizer's verdict.
// Resolves to the alternatives heard, best first, or [] for silence.
const SPEECH_GAP_MS = 1100;
let activeRec = null;
let fatalMic = null;
let recSerial = 0;
let listenCancel = null;

// Safari can refuse a new recognizer while the last one is still shutting
// down, so a new session waits for the previous one's 'end' (or 1.5 s).
let recClosed = Promise.resolve();
function trackClose(r) {
  let done, t = null;
  const p = new Promise(res => { done = res; });
  r.__closed = () => { clearTimeout(t); done(); };
  // The 1.5 s grace starts when the session is told to stop, not when it
  // was created (a long answer window is not a stuck shutdown).
  r.__closing = () => { if (t === null) t = setTimeout(() => { vlog('rec.closeTimeout', r.__n); done(); }, 1500); };
  recClosed = p;
}
function recSettled() { return recClosed; }

function listen(ms) {
  if (useWhisper()) return whisperListen(ms);
  return new Promise(resolve => {
    if (!SR) { resolve([]); return; }
    let alts = [];
    let kept = '';             // text from sessions that already ended
    let settled = false;
    let deadline = Date.now() + ms;
    let lastSpeech = 0;
    let rec = null;
    const finish = why => {
      if (settled) return;
      settled = true;
      vlog('listen.done', (why || '') + ' ' + JSON.stringify(alts[0] || ''));
      clearInterval(tick);
      if (rec) { if (rec.__closing) rec.__closing(); try { rec.abort(); } catch (_) {} }
      activeRec = null;
      listenCancel = null;
      resolve(alts.filter(Boolean));
    };
    const open = async () => {
      if (settled) return;
      await recClosed;
      if (settled) return;
      const r = new SR();
      r.__n = ++recSerial;
      trackClose(r);
      rec = activeRec = r;
      vlog('rec.new', r.__n);
      r.onstart = () => vlog('rec.start', r.__n);
      r.onaudiostart = () => vlog('rec.audiostart', r.__n);
      r.onspeechstart = () => vlog('rec.speechstart', r.__n);
      r.lang = 'en-US';
      r.interimResults = true;
      r.maxAlternatives = 3;
      r.continuous = true;
      r.onresult = e => {
        if (r !== rec) { vlog('rec.staleResult', r.__n); return; }
        // Everything this session has heard, final or not; alternatives come
        // from its latest result.
        const parts = [];
        for (let i = 0; i < e.results.length - 1; i++) parts.push(e.results[i][0].transcript.trim());
        const last = e.results[e.results.length - 1];
        const head = [kept, parts.join(' ')].filter(Boolean).join(' ');
        const texts = [];
        for (let i = 0; i < last.length; i++) texts.push(last[i].transcript.trim());
        const next = texts.map(t => [head, t].filter(Boolean).join(' ').trim()).filter(Boolean);
        vlog('rec.result', r.__n + ' ' + (last.isFinal ? 'final ' : '') + JSON.stringify(next[0] || ''));
        if (!next.length) return;
        alts = next;
        lastSpeech = Date.now();
        deadline = Math.max(deadline, lastSpeech + SPEECH_GAP_MS);
        show('Heard', { listening: true, heard: alts[0] });
      };
      r.onerror = e => {
        vlog('rec.error', r.__n + ' ' + e.error);
        if (e.error === 'not-allowed' || e.error === 'service-not-allowed' || e.error === 'audio-capture') {
          fatalMic = e.error;
          finish('fatal');
        }
      };
      r.onend = () => {
        vlog('rec.end', r.__n);
        if (r.__closed) r.__closed();
        if (r !== rec || settled) return;
        kept = alts[0] || kept;
        // Ended on its own with time left: listen again.
        if (Date.now() < deadline - 300) setTimeout(open, 60);
        else finish('ended');
      };
      try { r.start(); } catch (e) { vlog('rec.startThrew', r.__n + ' ' + (e && e.message)); if (r.__closed) r.__closed(); setTimeout(finish, 0); }
    };
    const tick = setInterval(() => {
      const now = Date.now();
      if (lastSpeech && now - lastSpeech > SPEECH_GAP_MS) finish('gap');
      else if (now > deadline) finish('deadline');
    }, 100);
    vlog('listen', ms);
    listenCancel = () => finish('cancelled');
    open();
  });
}

// ---- On-device recognition (Whisper) ----------------------------------------
// Safari's recognizer is a fresh session per answer: iOS chimes on every one,
// and on the phone's log one of those sessions opened and then heard nothing
// for two whole windows. This engine opens the mic once per drill (no chime)
// and transcribes each answer on the phone with Whisper tiny.en, run on the
// graphics chip via WebGPU. The model (~40 MB) downloads once and is cached.
// Used when WebGPU is available; Safari's recognizer otherwise, or by choice.
const W_MODEL = 'onnx-community/whisper-tiny.en';
const W_LIB = 'https://cdn.jsdelivr.net/npm/@huggingface/transformers@3.8.1';
const W_HANG_MS = 700;        // quiet this long after speech = you're done
const W_MAX_SPEECH_MS = 7000;
const W = { asr: null, loading: null, ctx: null, stream: null, proc: null,
  floor: 0.004, armed: null, gpu: null, device: null };

// Loading on the graphics chip can take more memory than iOS allows a page,
// and then Safari kills the page outright ("A problem repeatedly occurred"):
// no error, no catch. So a marker is set before each load and cleared after
// it; a marker still there on the next page load means that way crashed, and
// it isn't tried again. Order: graphics chip, then CPU (smaller int8 model,
// far less memory), then Safari's recognizer.
const W_LOADING_KEY = 'bahasa:voice:whisperLoading:v1';
const W_BAD_KEY = 'bahasa:voice:whisperBad:v1';
function wBad() { try { return JSON.parse(localStorage.getItem(W_BAD_KEY)) || []; } catch (_) { return []; } }
(function noteCrashedLoad() {
  const m = localStorage.getItem(W_LOADING_KEY);
  if (!m) return;
  localStorage.removeItem(W_LOADING_KEY);
  const bad = wBad();
  if (!bad.includes(m)) bad.push(m);
  localStorage.setItem(W_BAD_KEY, JSON.stringify(bad));
  setTimeout(() => vlog('whisper.crashed', m), 0);
})();
function whisperDevice() {
  const bad = wBad();
  if (W.gpu && !bad.includes('webgpu')) return 'webgpu';
  if (!bad.includes('wasm')) return 'wasm';
  return null;
}

async function whisperHasGpu() {
  if (W.gpu !== null) return W.gpu;
  try { W.gpu = !!(navigator.gpu && await navigator.gpu.requestAdapter()); } catch (_) { W.gpu = false; }
  return W.gpu;
}

function whisperLoad() {
  if (W.asr) return Promise.resolve(W.asr);
  if (W.loading) return W.loading;
  W.loading = (async () => {
    const t0 = Date.now();
    const device = W.device = whisperDevice();
    if (!device) throw new Error('on-device recognition crashed this phone before');
    vlog('whisper.load', device);
    const { pipeline, env } = await import(W_LIB);
    env.allowLocalModels = false;
    let last = -1;
    localStorage.setItem(W_LOADING_KEY, device);
    const asr = await pipeline('automatic-speech-recognition', W_MODEL, {
      device,
      dtype: device === 'webgpu' ? { encoder_model: 'fp32', decoder_model_merged: 'q4' } : 'q8',
      progress_callback: p => {
        if (p.status !== 'progress' || !p.total) return;
        const pct = Math.round((p.loaded / p.total) * 100);
        if (pct !== last && running) { last = pct; show('Downloading speech model\u2026 ' + pct + '% (first time only)'); }
      },
    });
    await asr(new Float32Array(16000));      // compile once, before the first answer
    localStorage.removeItem(W_LOADING_KEY);
    vlog('whisper.ready', device + ' ' + (Date.now() - t0) + 'ms');
    W.asr = asr;
    return asr;
  })();
  W.loading.catch(e => {
    // A thrown error (not a crash): this way doesn't work here either.
    if (W.device) {
      const bad = wBad();
      if (!bad.includes(W.device)) bad.push(W.device);
      localStorage.setItem(W_BAD_KEY, JSON.stringify(bad));
    }
    localStorage.removeItem(W_LOADING_KEY);
    vlog('whisper.loadFailed', (W.device || '') + ' ' + String(e && e.message || e));
    W.loading = null;
  });
  return W.loading;
}

function wRms(a) { let s = 0; for (let i = 0; i < a.length; i++) s += a[i] * a[i]; return Math.sqrt(s / a.length); }

function wResample(chunks, rate) {
  const len = chunks.reduce((n, c) => n + c.length, 0);
  const all = new Float32Array(len);
  let o = 0; for (const c of chunks) { all.set(c, o); o += c.length; }
  if (rate === 16000) return all;
  const ratio = rate / 16000, out = new Float32Array(Math.floor(len / ratio));
  for (let i = 0; i < out.length; i++) {
    const x = i * ratio, j = Math.floor(x), f = x - j;
    out[i] = all[j] * (1 - f) + (all[j + 1] || 0) * f;
  }
  return out;
}

// Must run inside the Start tap: iOS only lets a tap start audio capture.
function whisperMicStart() {
  if (W.stream) return Promise.resolve();
  const AC = window.AudioContext || window.webkitAudioContext;
  W.ctx = W.ctx || new AC();
  const resumed = W.ctx.resume();
  return navigator.mediaDevices.getUserMedia({
    audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
  }).then(stream => resumed.then(() => {
    W.stream = stream;
    const src = W.ctx.createMediaStreamSource(stream);
    W.proc = W.ctx.createScriptProcessor(2048, 1, 1);
    const mute = W.ctx.createGain(); mute.gain.value = 0;
    src.connect(W.proc); W.proc.connect(mute); mute.connect(W.ctx.destination);
    W.proc.onaudioprocess = e => whisperFrame(new Float32Array(e.inputBuffer.getChannelData(0)));
    vlog('whisper.mic', W.ctx.sampleRate);
  }));
}

function whisperMicStop() {
  if (W.proc) W.proc.onaudioprocess = null;
  if (W.stream) W.stream.getTracks().forEach(t => t.stop());
  W.proc = W.stream = null;
}

// Audio is only examined while an answer window is open, so the page's own
// voice (which plays between windows) is never transcribed.
function whisperFrame(a) {
  const w = W.armed;
  if (!w) return;
  const now = Date.now();
  const level = wRms(a);
  const thr = Math.max(0.012, W.floor * 3);
  const loud = level > thr;
  if (!w.speaking) {
    if (!loud) W.floor = W.floor * 0.95 + level * 0.05;   // learn the room while waiting
    w.preroll.push(a); if (w.preroll.length > 6) w.preroll.shift();
    if (loud) {
      w.speaking = true; w.buf = w.preroll.slice(); w.lastLoud = now; w.started = now;
      vlog('whisper.speech', level.toFixed(3) + '>' + thr.toFixed(3));
      show('Hearing you\u2026', { listening: true });
    } else if (now > w.deadline) {
      w.end([]);
    }
    return;
  }
  w.buf.push(a);
  if (loud) w.lastLoud = now;
  if (now - w.lastLoud >= W_HANG_MS || now - w.started > W_MAX_SPEECH_MS) {
    const chunks = w.buf, spoke = w.lastLoud - w.started;
    W.armed = null;
    if (spoke < 150) { vlog('whisper.click', spoke + 'ms'); w.end([]); return; }   // a knock, not a word
    show('Heard', { listening: true });
    const t0 = Date.now();
    W.asr(wResample(chunks, W.ctx.sampleRate)).then(out => {
      let text = ((out && out.text) || '').trim();
      // Whisper's habit on noise: bracketed tags, or a stock "Thank you."
      if (/^[\\[(].*[\\])]$/.test(text) || /^(thank you|thanks for watching)[.!]?$/i.test(text)) text = '';
      vlog('whisper.text', JSON.stringify(text) + ' ' + (Date.now() - t0) + 'ms');
      if (text) show('Heard', { listening: true, heard: text });
      w.end(text ? [text] : []);
    }).catch(e => { vlog('whisper.error', String(e && e.message || e)); w.end([]); });
  }
}

function whisperListen(ms) {
  return new Promise(resolve => {
    vlog('listen.w', ms);
    let done = false;
    const end = alts => { if (done) return; done = true; if (W.armed === arm) W.armed = null; listenCancel = null; vlog('listen.done', JSON.stringify(alts[0] || '')); resolve(alts); };
    const arm = { deadline: Date.now() + ms, speaking: false, buf: [], preroll: [], lastLoud: 0, started: 0, end };
    W.armed = arm;
    listenCancel = () => end([]);
    // ScriptProcessor stops firing if the audio context is suspended (a call,
    // Siri); don't wait on it forever.
    setTimeout(() => { if (!arm.speaking) end([]); }, ms + 1500);
  });
}

function useWhisper() { return engine === 'whisper' && !!W.asr && !!W.stream; }
let engine = 'safari';

function stopListening() {
  if (listenCancel) listenCancel();
  if (activeRec) { try { activeRec.abort(); } catch (_) {} activeRec = null; }
}

// ---- Rating ----------------------------------------------------------------
const GRADE_NAME = { 1: 'Again', 2: 'Hard', 3: 'Good', 4: 'Easy' };

function rate(card, grade) {
  const isNew = !srs[card.front];
  if (isNew) newShown++;
  const ts = srsLogReview('flash', grade, isNew, card.front);
  srsPushUndo({ card, front: card.front, prev: srs[card.front] || null, ts, isNew, grade });
  srs[card.front] = fsrsNextState(srs[card.front], grade, Date.now());
  srsSave(SRS_KEY, srs);
  syncRemoteQueuePush(setSyncState);
  session.done++;
  if (grade >= 3) session.right++;
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
  if (u.grade >= 3) session.right = Math.max(0, session.right - 1);
  if (u.isNew) newShown = Math.max(0, newShown - 1);
  renderStats();
  return u.card;
}

// "Go back" returns to the word before, whether you graded it or skipped it.
// A graded one has its grade taken back first, so you answer it fresh; the
// word you were on comes straight after it.
function remember(card, rated) {
  history.push({ card, rated });
  if (history.length > HISTORY_CAP) history.shift();
  $('undoBtn').disabled = false;
}

function goBack(onScreen) {
  const h = history.pop();
  $('undoBtn').disabled = !history.length;
  if (!h) return false;
  if (h.rated) undoLast();
  upNext = upNext.filter(c => c !== h.card && c !== onScreen);
  upNext.unshift(h.card, ...(onScreen && onScreen !== h.card ? [onScreen] : []));
  return true;
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
    await pause(100);
    guard(id);
    show('Listening — what does it mean?', { listening: true });
    const alts = await listen(prefs.waitMs);
    // Talking over a mic that is still shutting down is the other thing iOS
    // handles badly; give it a moment to let go first.
    await Promise.race([recSettled(), pause(800)]);
    guard(id);
    if (fatalMic) return { cmd: 'mic' };
    const heard = alts[0] || '';
    const r = alts.some(a => voiceClassifyAnswer(a, card.back).kind === 'correct')
      ? { kind: 'correct' } : voiceClassifyAnswer(heard, card.back);
    vlog('decided', card.front + ' -> ' + r.kind + (r.grade ? ' ' + r.grade : '') + (r.cmd ? ' ' + r.cmd : ''));
    show(r.kind === 'silent' ? 'Didn\u2019t catch that' : 'Heard', { heard });
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
      await Promise.race([recSettled(), pause(800)]);
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
        remember(card, true);
        current = null;
        await pause(600);
        continue;
      }
      if (out.cmd === 'mic') { micBlocked(); stop(); return; }
      if (out.cmd === 'stop') { await sayEn('Stopped.'); stop(); return; }
      if (out.cmd === 'skip') { remember(card, false); show('Skipped', { verdict: '' }); continue; }
      if (out.cmd === 'undo') {
        if (goBack(card)) await sayEn('Going back.');
        else { upNext.unshift(card); await sayEn('This is the first word.'); }
        continue;
      }
      if (out.cmd === 'idle') {
        upNext.unshift(card);
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
  const wantWhisper = prefs.engine === 'whisper' && !!whisperDevice();
  if (!SR && !wantWhisper) return;
  fatalMic = null;
  vlogT0 = Date.now();
  vlogEntries = [];
  vlog('start', navigator.userAgent + ' engine=' + (wantWhisper ? 'whisper' : 'safari'));
  unlockAudio();
  running = true;
  holdScreen();
  $('startBtn').textContent = 'Stop';
  $('skipBtn').disabled = false;
  $('lockBtn').disabled = false;
  if (!wantWhisper) { engine = 'safari'; run(); return; }
  // Mic first, inside the tap; then the model (cached after the first time).
  const mic = whisperMicStart();
  show('Loading speech model\u2026');
  Promise.all([mic, whisperLoad()]).then(() => {
    if (!running) return;
    engine = 'whisper';
    run();
  }).catch(e => {
    vlog('whisper.fallback', String(e && e.message || e));
    whisperMicStop();
    if (!running) return;
    if (e && e.name === 'NotAllowedError') { fatalMic = 'not-allowed'; micBlocked(); stop(); return; }
    engine = 'safari';
    show('On-device recognition didn\u2019t load; using Safari this time');
    if (SR) run(); else stop();
  });
}

function stop() {
  if (running) { vlog('stop'); clearTimeout(vlogTimer); vlogSend(); }
  running = false;
  runId++;
  stopListening();
  whisperMicStop();
  ttsStop();
  releaseScreen();
  setLocked(false);
  $('startBtn').textContent = session.done ? 'Resume' : 'Start';
  $('skipBtn').disabled = true;
  $('lockBtn').disabled = true;
  show(session.done ? 'Stopped' : 'Tap Start, then put the phone down', { listening: false });
  if (current && upNext[0] !== current) upNext.unshift(current);
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
  if (current) remember(current, false);
  runId++;
  stopListening();
  ttsStop();
  running = true;
  run();
};
$('undoBtn').onclick = () => {
  const cur = running ? current : null;
  if (!running && current && upNext[0] === current) upNext.shift();
  if (!goBack(cur || (running ? null : current))) return;
  if (running) { runId++; stopListening(); ttsStop(); run(); }
  else show('Went back', { front: upNext[0].front.split(' / ')[0], answer: '', heard: '', verdict: '' });
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

whisperHasGpu().then(() => {
  const opt = $('engineSel').querySelector('option[value="whisper"]');
  const dev = whisperDevice();
  if (!dev) {
    opt.disabled = true;
    opt.textContent = 'On this phone (crashed here)';
    if (prefs.engine === 'whisper') prefs.engine = 'safari';
  }
  if (!prefs.engine) prefs.engine = dev ? 'whisper' : 'safari';
  $('engineSel').value = prefs.engine;
  if (dev && !SR) { $('unsupported').hidden = true; $('startBtn').disabled = false; }
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
