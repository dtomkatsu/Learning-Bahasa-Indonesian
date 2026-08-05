"""Shared microphone-recording JS for the say-it-yourself practice loop.

The research pass behind notes/pronunciation-training-scope.md landed on one
uncomfortable finding: learners reliably miss about half their own
pronunciation errors when asked to judge a recording freely. Hearing yourself
is necessary but not sufficient — what makes the difference is (a) hearing
your attempt *immediately adjacent* to the model rather than minutes apart,
and (b) being told what specifically to listen for.

So this module isn't just "record and play back". It gives the page an
alternating A/B compare — model, you, model, you — because differences that
are inaudible in isolation become obvious back-to-back, and the pages pair it
with a per-card attention prompt (see say_tip() in build_flashcards.py).

Deliberately no scoring. Nothing here rates the attempt, and the recording is
never uploaded anywhere — it lives in a blob URL that's revoked when you leave
the card. There is no honest way to grade Indonesian pronunciation in the
browser today (see notes/elevenlabs-pronunciation-scope.md §3), and a fake
score would be worse than none.

Everything is prefixed `rec` so it can sit alongside _srs_js / _sync_js /
_tts_js / _vocab_js in one page without colliding at the top level.

This file uses a raw string, so backslashes here are written exactly as they
appear in the emitted JavaScript.
"""

REC_JS = r"""
// getUserMedia is https-or-localhost only, so this is false on a plain file://
// or http:// origin — the pages check it and hide the whole feature rather
// than offering a button that can only fail.
const recSupported = !!(navigator.mediaDevices
  && typeof navigator.mediaDevices.getUserMedia === 'function'
  && typeof window.MediaRecorder !== 'undefined');

let recRecorder = null;
let recStream = null;
let recChunks = [];
let recUrl = null;
const recAudio = typeof Audio !== 'undefined' ? new Audio() : null;

function recHasClip() { return !!recUrl; }

// Dropping the clip and releasing the object URL. Called on every card change:
// a recording of the last word is worse than no recording, because it would
// silently compare you against the wrong model.
function recClear() {
  recStopPlayback();
  if (recUrl) { URL.revokeObjectURL(recUrl); recUrl = null; }
  recChunks = [];
}

function recStopPlayback() {
  if (recAudio) { recAudio.pause(); recAudio.currentTime = 0; }
}

// Resolves true once recording has actually started, false if the user denied
// the mic prompt or the device has none. Never throws at the call site.
async function recStart() {
  if (!recSupported) return false;
  try {
    recStream = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch (e) {
    return false;
  }
  recClear();
  try {
    recRecorder = new MediaRecorder(recStream);
  } catch (e) {
    recReleaseStream();
    return false;
  }
  recChunks = [];
  recRecorder.addEventListener('dataavailable', e => {
    if (e.data && e.data.size) recChunks.push(e.data);
  });
  recRecorder.start();
  return true;
}

// The mic indicator stays lit until every track is stopped, which looks like
// the page is still listening after you've finished.
function recReleaseStream() {
  if (recStream) {
    recStream.getTracks().forEach(t => t.stop());
    recStream = null;
  }
}

function recIsRecording() {
  return !!(recRecorder && recRecorder.state === 'recording');
}

// Resolves to the clip's object URL, or null if nothing was captured.
function recStop() {
  return new Promise(resolve => {
    if (!recIsRecording()) { recReleaseStream(); resolve(null); return; }
    recRecorder.addEventListener('stop', () => {
      recReleaseStream();
      if (!recChunks.length) { resolve(null); return; }
      const blob = new Blob(recChunks, { type: recChunks[0].type || 'audio/webm' });
      recUrl = URL.createObjectURL(blob);
      resolve(recUrl);
    }, { once: true });
    recRecorder.stop();
  });
}

// Resolves when playback finishes (or immediately if there's nothing to play),
// so the caller can sequence model-then-you without guessing at durations.
function recPlay() {
  return new Promise(resolve => {
    if (!recUrl || !recAudio) { resolve(); return; }
    recAudio.src = recUrl;
    const done = () => { recAudio.removeEventListener('ended', done); resolve(); };
    recAudio.addEventListener('ended', done);
    recAudio.play().catch(() => done());
  });
}

function recWait(ms) {
  return new Promise(r => setTimeout(r, ms));
}

// A compare runs for several seconds (model, you, model, you) and the learner
// must be able to cut it short — to re-record, or just to move on. Each run
// takes a token; bumping the token strands any older run, which then returns
// false at its next checkpoint instead of driving UI that has moved on.
//
// Why a token and not a flag the caller clears: a stranded run may be parked
// on `await playModel()` forever, because pausing an <audio> fires no 'ended'
// event and that promise simply never settles. So nothing may depend on a
// cancelled run reaching its own cleanup — the winner owns the state, and the
// loser is required only to stay silent.
let recCompareToken = 0;

function recAbortCompare() {
  recCompareToken++;
  recStopPlayback();
}

// The point of the whole module: model and attempt back to back, twice, with
// a beat between them. Differences that vanish when you compare across a gap
// of thirty seconds are obvious in this window. `playModel` is supplied by the
// page (a real recording clip on some cards, speech synthesis on others) and
// must return a promise that resolves when it has finished speaking.
//
// Resolves true if it ran to completion, false if it was superseded — callers
// should only apply end-of-compare UI on true.
async function recCompare(playModel, onStep) {
  const token = ++recCompareToken;
  const live = () => token === recCompareToken;
  for (let round = 0; round < 2; round++) {
    if (!live()) return false;
    if (onStep) onStep('model');
    await playModel();
    if (!live()) return false;
    await recWait(320);
    if (!live()) return false;
    if (onStep) onStep('you');
    await recPlay();
    if (!live()) return false;
    if (round === 0) await recWait(420);
  }
  if (!live()) return false;
  if (onStep) onStep('done');
  return true;
}
"""
