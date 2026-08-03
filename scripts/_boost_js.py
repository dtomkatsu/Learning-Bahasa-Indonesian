"""Shared loudness boost for the *family* audio, injected wherever it plays
(player, flashcards, quiz).

Why this exists: the recordings are phone audio captured mid-life — people
talk across the room, the TV is on, nobody is addressing the microphone. As
comprehension material that's the whole point, but at native element volume
much of it is simply too quiet to work with, and `HTMLMediaElement.volume`
caps at 1.0 so it can't help. A WebAudio gain stage can: element -> gain
(x2.4) -> compressor (as a limiter, so boosted peaks don't clip) -> out.

Two deliberate scope limits:

- Only the family <audio> elements are wrapped. Generated TTS clips and the
  learner's own mic recordings are already at studio level; boosting them
  would just be loud.
- Skipped entirely on file:// (the desktop Bahasa Player.app). Chrome treats
  file:// media as CORS-opaque, and opaque media routed through WebAudio
  plays SILENCE — the boost would break the desktop app's audio outright.
  There the OS volume is the remedy; the boost serves the localhost and
  GitHub Pages origins, which is where the phone lives anyway.

A MediaElementSource can be created only once per element, and once created
the element plays through the graph alone — so attachment is guarded by a
WeakSet, and any construction failure leaves the element on its native path.

Everything is prefixed `boost` so it can sit alongside the other _*_js
modules in one page without top-level collisions.

This file uses a raw string, so backslashes here are written exactly as they
appear in the emitted JavaScript.
"""

BOOST_JS = r"""
const boostSupported = (location.protocol === 'http:' || location.protocol === 'https:')
  && !!(window.AudioContext || window.webkitAudioContext);
let boostCtx = null;
const boostWrapped = (typeof WeakSet !== 'undefined') ? new WeakSet() : null;

function boostAttach(el) {
  if (!boostSupported || !el || !boostWrapped || boostWrapped.has(el)) return;
  try {
    boostCtx = boostCtx || new (window.AudioContext || window.webkitAudioContext)();
    const src = boostCtx.createMediaElementSource(el);
    const gain = boostCtx.createGain();
    const comp = boostCtx.createDynamicsCompressor();
    gain.gain.value = 2.4;
    // Limiter-flavoured settings: high ratio, fast attack — the compressor's
    // job here is only to stop the boosted signal from clipping, not to
    // flatten the dynamics of the conversation.
    comp.threshold.value = -24;
    comp.knee.value = 12;
    comp.ratio.value = 12;
    comp.attack.value = 0.003;
    comp.release.value = 0.25;
    src.connect(gain);
    gain.connect(comp);
    comp.connect(boostCtx.destination);
    boostWrapped.add(el);
    // Autoplay policy starts the context suspended until a user gesture;
    // resuming on 'play' covers both direct clicks and the programmatic
    // replays that follow them.
    el.addEventListener('play', () => {
      if (boostCtx && boostCtx.state === 'suspended') boostCtx.resume();
    });
  } catch (e) {
    /* element keeps its native, un-boosted path */
  }
}
"""
