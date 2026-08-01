"""Shared browser speech-synthesis JS, injected into flashcards.html and
quiz.html.

Both pages need to say an Indonesian word or sentence out loud when there is
no real recording behind it, and both need to be honest about the fact that
a synthetic voice is not how this family talks. Keeping one copy means the
labelling stays consistent and there is a single seam to swap out if the
project ever moves to a proper Indonesian TTS voice (see
notes/elevenlabs-pronunciation-scope.md).

Everything is prefixed `tts` so it can be concatenated alongside _srs_js /
_sync_js / _vocab_js in one page without colliding at the top level — the
test runner's syntax pass catches that class of mistake, but only after it
has already broken a page.

This file uses a raw string, so backslashes here are written exactly as they
appear in the emitted JavaScript.
"""

TTS_JS = r"""
const ttsHasSupport = typeof window.speechSynthesis !== 'undefined'
  && typeof window.SpeechSynthesisUtterance !== 'undefined';
let ttsVoice = null;

// A pre-generated clip (scripts/build_tts.py) beats the device's own voice
// wherever one exists: it's a real Indonesian voice rather than whatever the
// OS happens to ship, it sounds the same on every device, and on desktop
// browsers with no Indonesian voice installed it's the difference between
// audio and a disabled button. Falls back to synthesis when a card has no clip
// — a partial run is a valid state, since the free tier's monthly allowance
// only covers about half the deck at a time.
const ttsClipAudio = typeof Audio !== 'undefined' ? new Audio() : null;

function ttsHasClip(src) { return !!(src && ttsClipAudio); }

// Same contract as ttsSpeak: resolves when the audio finishes, so callers can
// sequence against it without caring which of the two sources played.
function ttsPlayClip(src) {
  if (!ttsHasClip(src)) return Promise.resolve(false);
  ttsStop();
  return new Promise(resolve => {
    let settled = false;
    const done = ok => {
      if (settled) return;
      settled = true;
      ttsClipAudio.removeEventListener('ended', onEnd);
      ttsClipAudio.removeEventListener('error', onErr);
      resolve(ok);
    };
    const onEnd = () => done(true);
    const onErr = () => done(false);
    ttsClipAudio.addEventListener('ended', onEnd);
    ttsClipAudio.addEventListener('error', onErr);
    ttsClipAudio.src = src;
    ttsClipAudio.currentTime = 0;
    ttsClipAudio.play().catch(() => done(false));
  });
}

function ttsStopClip() {
  if (ttsClipAudio) { ttsClipAudio.pause(); ttsClipAudio.currentTime = 0; }
}

// The one call sites should use: prefer the generated clip, fall back to the
// device voice, so no page has to branch on which source it got.
function ttsSay(text, src, rate) {
  if (ttsHasClip(src)) return ttsPlayClip(src);
  return ttsSpeak(text, rate);
}

// Voices load asynchronously in most browsers, and an Indonesian voice may
// simply not be installed — in which case the default voice would read
// Indonesian with English phonics and teach the wrong pronunciation. Callers
// are expected to disable their play button and say so, rather than fall back
// to an English voice.
function ttsPickVoice() {
  if (!ttsHasSupport) return null;
  const vs = window.speechSynthesis.getVoices() || [];
  ttsVoice = vs.find(v => /^id\b|^id[-_]/i.test(v.lang)) || null;
  return ttsVoice;
}

// Re-picks on the browser's async voice load, then hands control back so the
// page can refresh whatever UI depends on voice availability.
function ttsOnVoicesChanged(cb) {
  if (!ttsHasSupport) return;
  ttsPickVoice();
  window.speechSynthesis.addEventListener('voiceschanged', () => { ttsPickVoice(); cb(); });
}

function ttsStop() {
  if (ttsHasSupport) window.speechSynthesis.cancel();
  if (typeof ttsStopClip === 'function') ttsStopClip();
}

// Slightly under normal speed: fast enough to sound like speech, slow enough
// that the syllable boundaries are still audible to a learner.
//
// Returns a promise that resolves when the voice has finished, so callers that
// need to sequence something after it (the say-it-yourself compare in
// _record_js.py plays the model, then your attempt) don't have to guess at a
// duration. Callers that just want noise can ignore the return value.
function ttsSpeak(text, rate) {
  if (!ttsVoice || !text) return Promise.resolve(false);
  window.speechSynthesis.cancel();
  return new Promise(resolve => {
    const u = new SpeechSynthesisUtterance(text);
    u.voice = ttsVoice;
    u.lang = ttsVoice.lang;
    u.rate = rate || 0.9;
    // 'end' fires on cancel() too, so an interrupted utterance still settles
    // rather than leaving the caller's await hanging forever.
    u.addEventListener('end', () => resolve(true));
    u.addEventListener('error', () => resolve(false));
    window.speechSynthesis.speak(u);
  });
}

// One place that decides what to tell the user about a synthetic voice, so
// flashcards and quiz can never drift into describing it differently.
function ttsUnavailableNote() {
  return ttsHasSupport
    ? 'no Indonesian voice installed on this device'
    : 'speech synthesis unavailable';
}
"""
