# Scoping: real Indonesian audio, and whether pronunciation can be graded

Written 2026-08-01, against the deck as it stands at 997 cards / 984
fill-the-blank items.

**Read the last section first if you only read one.** The two halves of this
question have very different answers. Getting a good Indonesian voice to
*imitate* is a solved, cheap, one-afternoon problem. Getting a machine to
*grade your own Indonesian pronunciation* is not a thing you can currently
buy, and I'd rather say that up front than bury it.

A note on sourcing: the API mechanics, model IDs, and speech-to-text response
shape below are read from ElevenLabs' own generated SDK, so they're solid.
**The prices are not** — their pricing page and help centre were unreachable
from this environment, so every dollar figure here is triangulated from
third-party 2026 write-ups and should be confirmed on the pricing page before
you spend anything. Individual "could not confirm" items are flagged inline.

---

## 1. The actual problem

| | |
|---|---|
| Cards with a real recording of the family | 429 |
| Cards with no recording — device speech synthesis only | 568 |
| Fill-the-blank items, none of which can ever have a recording | 984 |

The 568 and the 984 are the gap. Those cards call `ttsSpeak()`, which uses
`window.speechSynthesis` with an `id-*` voice. That works acceptably on iOS
and on most Android devices, and **not at all on a typical desktop browser**,
where no Indonesian voice is installed and the button is disabled with *"no
Indonesian voice installed on this device"*. Where it does work, it's robotic
enough that it's a weak model to imitate.

This got worse, not better, with the everyday-vocabulary decks: those 444
cards are exactly the ones the family never said, so they're exactly the ones
with no audio.

---

## 2. What it would take to fix the listening half

### Volume — measured, not estimated

| | items | characters |
|---|---|---|
| Example sentences | 997 (996 unique) | 31,009 (avg 31.1) |
| Card fronts (the words themselves) | 997 | 6,700 (avg 6.7) |
| **Both** | **1,994 clips** | **37,709** |
| *(Indonesian transcript lines, if you ever wanted those voiced too)* | *1,425* | *32,270* |

### Cost — **unverified, confirm before spending**

ElevenLabs bills per character, and the cheaper models bill at half rate:

| Model | credits/char | 37,709 chars → credits | ≈ cost |
|---|---|---|---|
| `eleven_flash_v2_5` / `eleven_turbo_v2_5` | 0.5 | 18,855 | **~$1.90** |
| `eleven_multilingual_v2` / `eleven_v3` | 1.0 | 37,709 | ~$3.80 |

Reported plans: Free 10,000 credits/mo · Starter $6 / 30,000 · Creator $22 /
121,000 (some sources say 100,000 — could not confirm) · Pro $99 / 600,000.

Two consequences worth noticing:

- **The free tier does not work here**, and not mainly because of volume.
  Free-plan output carries a **mandatory "elevenlabs.io" attribution** and
  **cannot be used commercially**. This repo is public. Spend the $6.
- **On the full-price models the whole deck doesn't fit in one Starter
  month** — 37,709 credits against a 30,000 allowance. Flash at 18,855 fits
  with room to spare. That, plus the next point, decides the model.

### Which model — `eleven_flash_v2_5`, and for a deck-specific reason

All four current models list Indonesian: `eleven_v3`, `eleven_multilingual_v2`,
`eleven_flash_v2_5`, `eleven_turbo_v2_5`. But the request takes an optional
`language_code` that pins the language and its text normalisation, and the SDK
notes it **is not supported for `multilingual_v2`**.

That matters more for this deck than it would for most. 17 example sentences
carry an English or abbreviation token that a language-detecting synthesiser
will happily read with English phonics — *Dia alergi **seafood***, *__HP__ saya
**lowbat***, *Pesawatnya **delay** dua jam*, *__AC__-nya rusak dari kemarin*,
*Adik saya masih __SD__*. Those are real Indonesian sentences and the letters
`HP`, `AC`, `SD` must be read *ha-pe*, *a-se*, *es-de*. Being able to send
`language_code: "id"` is the difference between a card that teaches the right
thing and one that teaches an English pronunciation of a word Indonesians say
in Indonesian.

So: **`eleven_flash_v2_5` with `language_code: "id"`** — half price, supports
the language pin, fits one Starter month, and Flash's documented weakness is
emotional expressiveness rather than pronunciation accuracy, which is the
wrong axis to care about for single words and six-word example sentences.

### Architecture — pre-generate at build time. Not a runtime call.

Three options were on the table.

**A. Pre-generate at build time, commit the MP3s.** ✅ Recommended.
A `scripts/build_tts.py` walks `vocab/*.tsv`, POSTs each front and each
sentence, and writes `audio/tts/<sha1(text|voice|model)[:16]>.mp3`, skipping
files that already exist. The API key lives in the maintainer's environment
for the duration of one build and is never shipped.

**B. Call the API from the browser with a key the user pastes.** ❌
This is tempting because the project already has the pattern — `_sync_js.py`
asks for a gist-scoped GitHub token and keeps it in `localStorage`. The
analogy breaks on one point: a gist-scoped PAT can only touch its owner's own
gists, whereas an ElevenLabs key is a **billable credential**. It's also
against ElevenLabs' own guidance, which says the key must not be exposed in
client-side code; their sanctioned browser pattern is short-lived single-use
tokens minted server-side, and those exist for speech-to-text but **not for
text-to-speech**. There is no server here to mint them. (Browser calls do
appear to work technically — a static GitHub Pages app in the wild calls the
TTS endpoint with `fetch` and an `xi-api-key` header, which can't work without
permissive CORS — but "it works" and "the key is safe" are different claims,
and only the second one matters.)

**C. Hybrid** — ship A, and *optionally* allow B for cards the user adds via
"+ Add card", which a build-time pass can't know about. Worth doing later;
not worth doing first.

Option A also wins on things that have nothing to do with keys: everyone
hears the same voice, the audio is reviewable in a diff, a replay costs
nothing, and it works offline through the existing service worker with no
changes — `sw.js` already serves non-HTML same-origin GETs cache-first.
(It should **not** go in `PRECACHE`; 13 MB on install would be hostile.
Cache-on-first-play is the right behaviour and is already what happens.)

### Size

`mp3_22050_32` is in the output-format enum and isn't one of the gated
formats (only `mp3_192` needs Creator+, and PCM/WAV at 44.1 kHz needs Pro+).
At 32 kbps: roughly **9.7 MB** for the sentences and **3.1 MB** for the words,
so about **13 MB** added to a repo whose working tree is already 81 MB of
source audio. Fine. Don't take the `mp3_44100_128` default — that's 4× the
size for headphone-quality nobody needs on a 2-second clip.

### Code changes required — genuinely small

The refactor that landed with the Fill-the-blank mode already put the seams
in place:

1. `scripts/_tts_js.py` is now the **only** place in the project that turns
   Indonesian text into sound. `ttsSpeak(text)` grows a lookup: if a
   pre-generated clip exists for this text, play it; otherwise fall back to
   `speechSynthesis` exactly as today. Nothing else changes.
2. The builders already put the raw text in the payload (`card.example`,
   `item.sentence`), so hashing text → filename needs no schema change. Emit
   a `TTS_INDEX` of `{sha → path}` alongside the deck.
3. **A third provenance label.** This is the part not to skip. The README's
   claim is that a synthetic voice is never mistaken for the family, and a
   *better* synthetic voice makes that more important, not less. Today there
   are two states — `real recording` and `synthesized — not from the
   recording`. There would need to be three, with the new one saying plainly
   that it's a studio voice and not these people.

Estimate: the generation script is an afternoon. The playback change is
under an hour. The labelling is ten minutes and is the part with actual
consequences.

---

## 3. The pronunciation half — the honest answer

**ElevenLabs cannot grade pronunciation.** Not "doesn't do it well" — there is
no such endpoint. Every API group in their SDK was enumerated; every single
occurrence of the word "pronunciation" is either `PronunciationDictionaries`
or `pronunciation_dictionary_locators`, and both of those are **inputs to the
synthesiser** — a lexicon telling it how *it* should say a word. They have
nothing to do with assessing how *you* said one.

What ElevenLabs does have that's adjacent:

- **Scribe v2** speech-to-text supports Indonesian, and its per-word response
  carries `start`, `end`, and a `logprob` confidence. Batch pricing reported
  around **$0.22/hour** of audio.
- A **forced-alignment** API that aligns known text to audio.

You could build a crude loop from those: record yourself reading the example
sentence, transcribe it, and check whether the target word came back and how
confident the model was. That tells you *"a speech recogniser could or
couldn't understand you"* — a real signal, and not nothing. It is **not**
phoneme-level accuracy scoring, it won't tell you your `ng` is wrong or your
final `k` is missing its glottal stop, and low confidence has many causes
that aren't your mouth (background noise, mic, speaking rate).

### And the vendors who *do* score pronunciation don't cover Indonesian

This is the genuinely blocking finding:

- **Azure AI Speech Pronunciation Assessment** is the strongest product in
  this space — real phoneme-level accuracy, fluency, completeness and prosody
  scores, +$0.30/hour on top of standard STT. Its supported-locale list runs
  to 33 entries and **`id-ID` is not among them.** (Verified against
  Microsoft's own docs source, so this one is solid.) Malay `ms-MY` *is*
  supported and is linguistically adjacent, but scoring Indonesian against a
  Malay model is a hack of unknown validity and I wouldn't ship it to a
  learner without testing it against known-good and known-bad recordings.
- **Google Cloud** has no pronunciation-assessment product at all.
- **Speechace** and **SpeechSuper** both sell genuine phoneme-level scoring.
  Neither could be confirmed to support Indonesian — Speechace's locale table
  was unreachable, and SpeechSuper's public samples cover eight languages that
  don't appear to include it. **This is the one worth a direct email** before
  concluding the door is shut.

### So what would actually help pronunciation, today

Ranked by value per unit of effort:

1. **Shadowing against the real recordings.** Already built — the player's
   Shadow mode auto-pauses after every line. 429 cards have the family saying
   the word. This is the best pronunciation tool in the project and it
   already exists.
2. **Record-and-compare, with no scoring.** Add a mic button that records you
   saying the sentence and plays it back **immediately after** the reference
   clip, A/B. No API, no cost, no vendor — `MediaRecorder` is a browser
   built-in. Self-comparison against a native model is how shadowing works
   offline anyway, and hearing yourself next to the reference catches more
   than a numeric score would. **This is the highest-value thing on this whole
   page and it needs no vendor at all.**
3. **Scribe v2 as a recognisability check.** Worth it only after (2), framed
   honestly as "a recogniser understood you / didn't", never as a score.
4. **Real phoneme scoring.** Blocked on vendor discovery. Don't scope it as
   an integration; scope it as a question to ask Speechace.

---

## 4. Recommendation

Do this, in order:

1. **Build-time TTS with `eleven_flash_v2_5` + `language_code: "id"`, one
   $6 Starter month, ~$2 of credits, ~13 MB committed.** Closes the real gap:
   568 flashcards and 984 blank items that currently have no usable audio on
   desktop. Confirm the pricing page first.
2. **Record-and-playback against the reference clip.** No vendor, no cost,
   and it's the part that actually touches *your* pronunciation.
3. **Ask Speechace whether they support Indonesian.** Everything past step 2
   depends on the answer, and nobody else in the market has one.

And keep the three-way audio labelling honest at every step. The reason this
project is worth anything is that it never pretends a machine is the family.
