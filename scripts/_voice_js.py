"""Answer matching for the hands-free voice drill (voice.html).

The page hears the Indonesian word, then hears *you* through the browser's
speech recognizer, and has to decide what you meant without a tap: the
English meaning, a self-grade ("good", "hard", "don't know"), or a control
word ("repeat", "skip", "go back", "stop"). That decision is pure string work
on the recognizer's transcript and the card's back, so it lives here, apart
from the audio plumbing, where tests/cases.js can pin it down.

Card backs are written for reading, not for a recognizer: "clothes / a shirt
or top", "at / in / on — place, not motion", `tag question / seeking
agreement — "right?"`. voiceAccepted() turns one into the phrases that count
as a correct answer: the alternatives before the dash, plus anything quoted.
The explanation after the dash is never accepted, or "motion" would mark
"di" correct.

Everything is prefixed `voice` so it can sit beside the other shared modules
in one page.
"""

VOICE_JS = r"""
// Words that carry no meaning on their own. A gloss made only of these
// ("I / me", "you") still matches as a whole phrase; they just can't match
// as single words inside a longer answer.
const VOICE_STOP = new Set(('a an the to of in on at for and or is are be '
  + 'it its this that with as by from so not no do does also very some '
  + 'something someone thing one').split(' '));

const VOICE_NUM = ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven',
  'eight', 'nine', 'ten', 'eleven', 'twelve', 'thirteen', 'fourteen', 'fifteen',
  'sixteen', 'seventeen', 'eighteen', 'nineteen'];
const VOICE_TENS = ['', '', 'twenty', 'thirty', 'forty', 'fifty', 'sixty',
  'seventy', 'eighty', 'ninety'];

// Recognizers write numbers as digits ("2", "1000"); number cards are written
// in words. Spell digits out so the two meet.
function voiceNumWords(n) {
  if (n < 20) return VOICE_NUM[n];
  if (n < 100) return VOICE_TENS[Math.floor(n / 10)] + (n % 10 ? ' ' + VOICE_NUM[n % 10] : '');
  if (n < 1000) return VOICE_NUM[Math.floor(n / 100)] + ' hundred' + (n % 100 ? ' ' + voiceNumWords(n % 100) : '');
  if (n < 1000000) return voiceNumWords(Math.floor(n / 1000)) + ' thousand' + (n % 1000 ? ' ' + voiceNumWords(n % 1000) : '');
  if (n < 1000000000) return voiceNumWords(Math.floor(n / 1000000)) + ' million' + (n % 1000000 ? ' ' + voiceNumWords(n % 1000000) : '');
  return String(n);
}

function voiceNorm(s) {
  return String(s || '').toLowerCase()
    .replace(/[‘’]/g, "'")
    .replace(/(\d),(\d{3})/g, '$1$2')
    .replace(/\d+/g, d => ' ' + voiceNumWords(Number(d)) + ' ')
    .replace(/[^a-z' ]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

// Close enough for "eat"/"eats"/"eating"/"eaten", "tired"/"tiring". Applied
// to both sides, so it only has to be consistent, not linguistically right.
function voiceStem(w) {
  w = w.replace(/'s$/, '');
  if (w.length > 5 && w.endsWith('ing')) return w.slice(0, -3);
  if (w.length > 4 && w.endsWith('ed')) return w.slice(0, -2);
  if (w.length > 4 && w.endsWith('es')) return w.slice(0, -2);
  if (w.length > 3 && w.endsWith('s') && !w.endsWith('ss')) return w.slice(0, -1);
  if (w.length > 4 && w.endsWith('e')) return w.slice(0, -1);
  return w;
}

// The part of a back that is the meaning rather than the commentary.
function voiceHead(back) {
  return String(back || '').split(/\s[—–-]\s|\s[—–]|[—–]\s/)[0];
}

// Phrases that count as a correct answer for this card.
function voiceAccepted(back) {
  const quoted = [...String(back || '').matchAll(/["“]([^"”]+)["”]/g)].map(m => m[1]);
  const head = voiceHead(back).replace(/\([^)]*\)/g, ' ').replace(/["“”]/g, ' ');
  const parts = head.split(/[\/;,]/).concat(quoted);
  const out = [];
  for (let p of parts) {
    p = voiceNorm(p).replace(/^(also|or|esp|e g|i e) /, '');
    if (!p) continue;
    out.push(p);
    // "to eat" is answered by "eat"; "a shirt" by "shirt".
    const bare = p.replace(/^(to|a|an|the|be) /, '');
    if (bare !== p && bare) out.push(bare);
  }
  return [...new Set(out)];
}

// What the page reads aloud as the answer: the meaning, without the notes.
function voiceSpokenGloss(back) {
  const head = voiceHead(back).replace(/\([^)]*\)/g, ' ')
    .replace(/["“”]/g, '').replace(/\s*\/\s*/g, ', or ')
    .replace(/\s+/g, ' ').trim().replace(/[,;]$/, '');
  return head || String(back || '');
}

function voiceHas(said, phrase) {
  return (' ' + said + ' ').includes(' ' + phrase + ' ');
}

// True when what you said contains the meaning: a whole accepted phrase, or
// any content word from one (stemmed), so "it means to eat something" and
// "eating" both count for "to eat".
function voiceMatches(said, back) {
  const s = voiceNorm(said);
  if (!s) return false;
  const saidStems = new Set(s.split(' ').map(voiceStem));
  for (const phrase of voiceAccepted(back)) {
    if (voiceHas(s, phrase)) return true;
    for (const w of phrase.split(' ')) {
      if (w.length < 3 || VOICE_STOP.has(w)) continue;
      if (saidStems.has(voiceStem(w))) return true;
    }
  }
  return false;
}

// Control words, checked in this order. Each is a whole-phrase match on the
// normalized transcript, so "repeat" never fires on "repeatedly".
const VOICE_COMMANDS = [
  ['stop', ['stop', 'pause', 'stop listening', 'take a break']],
  ['undo', ['go back', 'undo', 'previous', 'last one']],
  ['repeat', ['repeat', 'again please', 'say again', 'say it again', 'one more time', 'what', 'huh', 'pardon', 'sorry']],
  ['skip', ['skip', 'next', 'next one', 'pass on this']],
];
const VOICE_GRADES = [
  // "don't know" before anything that could find "know" in a gloss.
  [1, ["don't know", 'dont know', 'do not know', 'no idea', 'not sure', 'no clue',
       'forgot', 'i forget', 'pass', 'bad', 'wrong', 'missed', 'miss', 'nope', 'no']],
  [2, ['hard', 'heart', 'hart', 'difficult', 'almost', 'close', 'kind of', 'sort of']],
  // Plus what recognizers make of a lone one-word answer: "good" comes back
  // as "could" or "goods", "easy" as "ez" or "easey".
  [4, ['easy', 'too easy', 'super easy', 'obvious', 'ez', 'easey', 'eazy', 'easily']],
  [3, ['good', 'could', 'goods', 'gud', 'good good', 'very good', 'got it', 'right', 'correct', 'yes', 'yeah', 'yep', 'knew it', 'i knew it', 'know it', 'i know it']],
];

function voiceFind(s, table) {
  for (const [value, phrases] of table) {
    if (phrases.some(p => voiceHas(s, p))) return value;
  }
  return null;
}

// Whole-utterance control: only when the utterance is short, so "stop" in
// "it means to stop" is an answer, not a pause.
function voiceCommand(said) {
  const s = voiceNorm(said);
  if (!s || s.split(' ').length > 4) return null;
  return voiceFind(s, VOICE_COMMANDS);
}

// What one utterance in the answer window means. Returns one of:
//   {kind:'silent'}              nothing heard
//   {kind:'command', cmd}        stop / undo / repeat / skip
//   {kind:'correct'}             said the meaning           -> Good
//   {kind:'grade', grade}        graded yourself instead     -> that grade
//   {kind:'unclear'}             said something else         -> ask right/wrong
// A self-grade or command that is also the meaning ("good" for bagus, "what"
// for apa) counts as the meaning.
function voiceClassifyAnswer(said, back) {
  const s = voiceNorm(said);
  if (!s) return { kind: 'silent' };
  const accepted = voiceAccepted(back);
  const dontKnow = ["don't know", 'dont know', 'do not know', 'no idea', 'no clue'];
  if (dontKnow.some(p => voiceHas(s, p)) && !accepted.some(a => dontKnow.some(p => a.includes(p)))) {
    return { kind: 'grade', grade: 1 };
  }
  // The meaning wins over a control word: "what" is the answer for apa, and
  // "go back" for kembali, not a request to repeat or undo.
  if (voiceMatches(s, back)) return { kind: 'correct' };
  const cmd = voiceCommand(s);
  if (cmd) return { kind: 'command', cmd };
  if (s.split(' ').length <= 3) {
    const g = voiceFind(s, VOICE_GRADES);
    if (g) return { kind: 'grade', grade: g };
  }
  return { kind: 'unclear' };
}

// After the page reads the answer back and asks "right or wrong?".
// Returns {kind:'grade', grade} | {kind:'command', cmd} | {kind:'silent'} | {kind:'unclear'}.
function voiceClassifyConfirm(said) {
  const s = voiceNorm(said);
  if (!s) return { kind: 'silent' };
  const cmd = voiceCommand(s);
  if (cmd && cmd !== 'skip') return { kind: 'command', cmd };
  const g = voiceFind(s, VOICE_GRADES);
  if (g) return { kind: 'grade', grade: g };
  if (cmd) return { kind: 'command', cmd };
  return { kind: 'unclear' };
}

// While paused by silence, only "resume" (or its friends) restarts the drill.
function voiceIsResume(said) {
  const s = voiceNorm(said);
  return ['resume', 'continue', 'start', 'go', "let's go", 'keep going', "i'm back", 'ready']
    .some(p => voiceHas(s, p));
}
"""
