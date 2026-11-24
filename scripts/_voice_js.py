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
  if (w.length > 3 && w.endsWith('e')) return w.slice(0, -1);   // take/taking, make/making
  return w;
}

// The part of a back that is the meaning rather than the commentary.
function voiceHead(back) {
  return String(back || '').split(/\s[—–-]\s|\s[—–]|[—–]\s/)[0];
}

// Phrases that count as a correct answer for this card. Synonyms the back
// doesn't spell out (vocab/voice-answers.json) are passed separately as
// `extra` and matched more strictly, in voiceMatchesExtra.
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

// A synonym counts only when all its words are there ("take a break", not
// just "take"): one key word is enough for the back's own meanings, but a
// phrase like "when it comes to" would otherwise make "when" correct.
function voiceMatchesExtra(saidStems, extra) {
  for (const x of extra || []) {
    const words = voiceCanon(voiceNorm(x)).split(' ').filter(w => w && !VOICE_STOP.has(w));
    if (words.length && words.every(w => saidStems.has(voiceStem(w)))) return true;
  }
  return false;
}

// What the page reads aloud as the answer: the meaning, without the notes.
function voiceSpokenGloss(back) {
  const head = voiceHead(back).replace(/\([^)]*\)/g, ' ')
    .replace(/["“”]/g, '').replace(/\s*\/\s*/g, ', or ')
    .replace(/\s+/g, ' ').trim().replace(/[,;]$/, '');
  return head || String(back || '');
}

// Recognizers spell what they hear, not what you meant: "sea" comes back as
// "see", "soft" next to "weak" as "week". Each group is rewritten to its
// first spelling on both sides before matching. Only content words: to/two,
// for/four, no/know, I/eye and one/won are left alone because they collide
// with stopwords, grades or commands.
const VOICE_HOMOPHONES = [
  'sea see', 'week weak', 'here hear', 'son sun', 'meat meet', 'flower flour',
  'right write', 'eight ate', 'hair hare', 'tail tale', 'pear pair', 'night knight',
  'road rode', 'blue blew', 'red read', 'dear deer', 'bear bare', 'buy by bye',
  'sail sale', 'steal steel', 'wait weight', 'waist waste', 'plain plane',
  'male mail', 'whole hole', 'peace piece', 'wood would', 'threw through',
  'sent cent scent', 'sore soar', 'rain reign', 'break brake', 'fair fare',
  'great grate', 'flew flu', 'new knew', 'die dye', 'sole soul', 'toe tow',
  'wear where', 'witch which', 'weather whether wether', 'high hi', 'route root',
  'past passed', 'allowed aloud', 'morning mourning', 'rose rows', 'berry bury',
  'sell cell', 'heal heel', 'nose knows', 'way weigh', 'there their',
  'missed mist', 'guest guessed', 'pour poor', 'stair stare', 'tea tee',
  'board bored', 'ceiling sealing', 'chilly chili', 'minor miner', 'pray prey',
  'beat beet', 'due dew', 'heard herd', 'whale wail', 'wheel we\'ll',
];
const VOICE_SOUNDALIKE = new Map();
VOICE_HOMOPHONES.forEach(g => { const ws = g.split(' '); ws.forEach(w => VOICE_SOUNDALIKE.set(w, ws[0])); });
function voiceCanon(s) {
  return s.split(' ').map(w => VOICE_SOUNDALIKE.get(w) || w).join(' ');
}

// After a right answer only the first meaning is read ("Yes. clothes"), so
// the drill keeps moving; the full list is for when you missed it.
function voiceShortGloss(back) {
  return voiceSpokenGloss(back).split(/, or |[;,]/)[0].trim();
}

// Everything the drill says in English apart from the card meanings. Fixed
// strings, so scripts/build_voice_tts.py can have them recorded once.
const VOICE_PHRASES = {
  yes: 'Yes.',
  rightOrWrong: 'Right or wrong?',
  pausing: 'Pausing. Say resume when you\u2019re ready.',
  ok: 'OK.',
  goingBack: 'Going back.',
  firstWord: 'This is the first word.',
  stopped: 'Stopped.',
  caughtUp: 'All caught up.',
  nothingDue: 'Nothing due right now.',
  changedRight: 'Changed it to right.',
  changedWrong: 'Changed it to wrong.',
  nothingToChange: 'There\u2019s nothing to change yet.',
};

function voiceHas(said, phrase) {
  return (' ' + said + ' ').includes(' ' + phrase + ' ');
}

// One-letter slips on longer words ("wether" for weather) still count.
function voiceNear(a, b) {
  if (a === b) return true;
  if (a.length < 5 || b.length < 5 || Math.abs(a.length - b.length) > 1) return false;
  let i = 0;
  while (i < a.length && a[i] === b[i]) i++;
  if (a.length === b.length) return a.slice(i + 1) === b.slice(i + 1);
  return a.length > b.length ? a.slice(i + 1) === b.slice(i) : a.slice(i) === b.slice(i + 1);
}

// True when what you said contains the meaning: a whole accepted phrase, or
// any content word from one (stemmed), so "it means to eat something" and
// "eating" both count for "to eat".
function voiceMatches(said, back, extra) {
  const s = voiceCanon(voiceNorm(said));
  if (!s) return false;
  const saidStems = new Set(s.split(' ').map(voiceStem));
  if (voiceMatchesExtra(saidStems, extra)) return true;
  for (const phrase of voiceAccepted(back).map(voiceCanon)) {
    if (voiceHas(s, phrase)) return true;
    for (const w of phrase.split(' ')) {
      if (w.length < 3 || VOICE_STOP.has(w)) continue;
      const st = voiceStem(w);
      if (saidStems.has(st)) return true;
      for (const x of saidStems) if (voiceNear(x, st)) return true;
    }
  }
  return false;
}

// Control words, checked in this order. Each is a whole-phrase match on the
// normalized transcript, so "repeat" never fires on "repeatedly".
const VOICE_COMMANDS = [
  // "Actually right/wrong" changes the grade of the word before, when the
  // drill got it wrong. Checked first: "that was right" must not read as a
  // plain "right".
  ['override-right', ['actually right', 'actually i was right', 'that was right', 'mark it right',
    'mark that right', 'change it to right', 'i got that one', 'actually correct']],
  ['override-wrong', ['actually wrong', 'actually i was wrong', 'that was wrong', 'mark it wrong',
    'mark that wrong', 'change it to wrong', 'actually incorrect']],
  ['stop', ['stop', 'pause', 'stop listening', 'take a break']],
  ['undo', ['go back', 'back', 'undo', 'previous', 'previous word', 'last one', 'last word',
    'word before', 'one before', 'go back one']],
  ['repeat', ['repeat', 'again please', 'say again', 'say it again', 'one more time', 'what', 'huh', 'pardon', 'sorry']],
  ['skip', ['skip', 'next', 'next one', 'pass on this']],
];
const VOICE_GRADES = [
  // "don't know" before anything that could find "know" in a gloss.
  [1, ["don't know", 'dont know', 'do not know', 'no idea', 'not sure', 'no clue',
       "didn't know", "didn't get it", 'not right', 'not correct', 'incorrect', 'i was wrong',
       'again', 'again again', 'but again',
       'forgot', 'i forget', 'pass', 'bad', 'wrong', 'missed', 'miss', 'nope', 'nah', 'no']],
  [2, ['hard', 'heart', 'hart', 'difficult', 'almost', 'close', 'kind of', 'sort of']],
  // Plus what recognizers make of a lone one-word answer: "good" comes back
  // as "could" or "goods", "easy" as "ez" or "easey".
  [4, ['easy', 'too easy', 'super easy', 'obvious', 'ez', 'easey', 'eazy', 'easily']],
  [3, ['good', 'could', 'goods', 'gud', 'good good', 'very good', 'got it',
       'great', 'grate', 'perfect', 'nice', 'awesome', 'sure', 'exactly', 'yup', 'nailed it',
       "that's right", 'that is right', 'i got it', 'write', 'right', 'correct', 'yes', 'yeah', 'yep', 'knew it', 'i knew it', 'know it', 'i know it']],
];

// In the answer window, a grade only counts when that's all you said: "no
// problem" is an answer that happens to contain "no", and grading it Again
// was a real miss on the phone.
const VOICE_FILLER = new Set(('it its it\'s that that\'s was is i a very too so oh um uh ok okay '
  + 'well hmm the one this').split(' '));
let VOICE_GRADE_WORDS = null;
function voiceOnlyGradeWords(s) {
  if (!VOICE_GRADE_WORDS) {
    VOICE_GRADE_WORDS = new Set(VOICE_GRADES.flatMap(([, ps]) => ps.flatMap(p => p.split(' '))));
  }
  const words = s.split(' ');
  return words.length <= 4 && words.every(w => VOICE_GRADE_WORDS.has(w) || VOICE_FILLER.has(w));
}

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
// A self-grade that is also the meaning ("good" for bagus) counts as the
// meaning.
function voiceClassifyAnswer(said, back, extra) {
  const s = voiceNorm(said);
  if (!s) return { kind: 'silent' };
  const accepted = voiceAccepted(back).concat((extra || []).map(voiceNorm));
  const dontKnow = ["don't know", 'dont know', 'do not know', 'no idea', 'no clue'];
  if (dontKnow.some(p => voiceHas(s, p)) && !accepted.some(a => dontKnow.some(p => a.includes(p)))) {
    return { kind: 'grade', grade: 1 };
  }
  // A control word is a command, unless it is exactly this card's meaning:
  // "what" answers apa and "go back" answers kembali, but "go back" on pergi
  // ("to go") goes back.
  const cmd = voiceCommand(s);
  if (cmd && !accepted.includes(s)) return { kind: 'command', cmd };
  if (voiceMatches(s, back, extra)) return { kind: 'correct' };
  if (voiceOnlyGradeWords(s)) {
    const g = voiceFind(s, VOICE_GRADES);
    if (g) return { kind: 'grade', grade: g };
  }
  return { kind: 'unclear' };
}

// After the page reads the answer back and asks "right or wrong?".
// Returns {kind:'grade', grade} | {kind:'command', cmd} | {kind:'silent'} | {kind:'unclear'}.
// At "right or wrong?" only grades are expected, so common mishearings of
// them count here (not in the answer window, where "hot" could be a real
// answer).
const VOICE_CONFIRM_ALIKE = [
  [2, ['heart', 'hart', 'hearts', 'hot', 'had', 'hod', 'hide', 'hyde', 'harder', 'hard one', 'hold']],
  [3, ['god', 'alright', 'all right', 'rite', 'go ahead']],
];
function voiceClassifyConfirm(said) {
  const s = voiceNorm(said);
  if (!s) return { kind: 'silent' };
  const cmd = voiceCommand(s);
  // Here "that was right" answers the question being asked.
  if (cmd === 'override-right') return { kind: 'grade', grade: 3 };
  if (cmd === 'override-wrong') return { kind: 'grade', grade: 1 };
  if (cmd && cmd !== 'skip') return { kind: 'command', cmd };
  const g = voiceFind(s, VOICE_GRADES) || voiceFind(s, VOICE_CONFIRM_ALIKE);
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
