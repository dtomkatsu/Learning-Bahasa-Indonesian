# Retool: model audio vs. comprehension audio are different jobs

Written 2026-08-01, after real use surfaced the problem the earlier scoping
docs didn't weigh enough: **the family recordings are often too faint to
serve as model audio.** They're phone captures of people talking across
rooms with the TV on — exactly what makes them irreplaceable as
comprehension material, and exactly what makes them a poor "listen and
imitate this" reference. The original design used authenticity as the
priority order for every audio surface; this retool splits the two jobs.

## The new source hierarchy

**For model audio** (flashcards "Hear it", the say-it comparison model):

| Priority | Source | Label shown | Coverage |
|---|---|---|---|
| 1 | Lingua Libre volunteer recording (real human, isolated word, CC BY-SA) | "real voice — a volunteer, not the family" | 578 of 994 fronts (58%); fetched by `scripts/fetch_lingualibre.py` into `audio/ll/` |
| 2 | Generated studio voice (`scripts/build_tts.py`) | "studio voice — not the family" | all fronts + all 996 example sentences, once generated |
| 3 | Family clip | "real recording — may be faint" | 429 cards (used as the model only when neither clip exists) |
| 4 | Device speech synthesis | "synthesized — not from the recording" | last resort |

**For comprehension audio** (player, Sentence/Listening modes, Catch-it,
word-mode cloze): still the family recordings, unchanged — the entire point
of those exercises is *this family's* speech. What changed there is
loudness: `scripts/_boost_js.py` routes the family `<audio>` elements
through a WebAudio gain (×2.4) + limiter chain on http/https origins.
It deliberately skips `file://` (the desktop app): Chrome treats `file://`
media as CORS-opaque, and opaque media through WebAudio plays silence —
the boost would have broken the desktop app's audio entirely.

The family line on a flashcard back keeps its own "▶ play the family clip"
button under *Heard in the recording* — demoted from the main button, never
removed.

## Why Lingua Libre, specifically

Probed Wikimedia Commons directly (2026-08-01): **6,989** Lingua Libre
Indonesian word recordings exist (`LL-Q9240 (ind)-<speaker>-<word>.wav`),
**578 of our 994 fronts** are covered by at least one, **281 by two or more
distinct speakers**, across **79 volunteers**. That last number is the
important one: `notes/hvpt-elevenlabs-build.md` found synthetic multi-voice
has no evidence of reproducing the multi-talker HVPT effect, which left
word-level HVPT stuck on however many words the family said twice. Real
volunteer recordings are actual between-speaker variability — the fetcher
keeps up to 2 alternate speakers per word (in the index's `alts`) so a
word-level discrimination drill can draw on them later.

License: CC BY-SA 4.0, attribution required — `audio/ll/CREDITS.json` maps
every clip to its author and Commons source page. Keep that file shipping
alongside the audio.

## What this means for the ElevenLabs plan

Unchanged in mechanics, narrower in role: the studio voice now primarily
serves the **996 example sentences** (which no corpus of real recordings
will ever contain — they're authored for this deck) and the ~416 fronts
Lingua Libre doesn't cover. Still blocked on the Starter upgrade
(free tier 402s on any Voice Library voice — see the confirmed-2026-08-01
note in `hvpt-elevenlabs-build.md`). Voice choice stands: Andi
(`wvv6DzcHyOVTDgDY7SMW`). The 115 Alice-voice clips in `audio/tts/` are a
pipeline-validation batch, to be regenerated with Andi after the upgrade.

## Open threads

- **Catch-it at word level**: rebuild option using Lingua Libre multi-speaker
  words (281 candidates vs. the current 209 family multi-speaker words) —
  or better, both sources mixed. The current line-based Catch-it stays; boost
  makes it more usable meanwhile.
- **Say-it forced-choice A/B** (from `pronunciation-training-scope.md` §1):
  still pending — the shipped compare loop plays model/you in fixed labeled
  order; the researched design asks "which one was you?" on shuffled order.
- **Volunteer-voice consistency**: the fetcher picks each word's primary clip
  from the most prolific speaker so the default experience isn't voice
  whiplash; if a specific volunteer's audio quality disappoints, blocklist
  them in `fetch_lingualibre.py` and re-run.
