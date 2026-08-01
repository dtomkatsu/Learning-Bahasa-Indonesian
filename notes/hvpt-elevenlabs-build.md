# Investigation: building the multi-talker HVPT drill with ElevenLabs

Written 2026-08-01, following up on §2 of `pronunciation-training-scope.md`.
That doc identified real family audio as the gold-standard source (38+ of
the first 250 cards already have the same word said by 2+ real speakers)
and explicitly deferred the question of filling in the rest with ElevenLabs
voices. This is that investigation.

**Read this before the mechanics section: the headline finding changes the
plan.** I went looking for evidence that synthetic-voice variability
produces the same effect real-talker variability does in HVPT. There's
essentially one study on point, and it found the opposite of what the
design assumed.

---

## The finding that matters most

Al-Shami & Cardoso (2025), *"Text-to-Speech in High-Variability Phonetic
Training: Focus on L2 Phonological Awareness"* — 30 adult ESL learners,
4 weeks, trained on an English phonological-awareness task. One group
trained on **multiple TTS voices**, the other on **a single TTS voice**.

**Both groups improved significantly. There was no significant difference
between them.**

That's the specific mechanism this drill was going to lean on — the classic
HVPT result that multi-talker training beats single-talker training —
tested with synthetic voices instead of real ones, and it didn't replicate.
Caveats worth naming: small sample (~15/group), a categorization task
rather than the discrimination-with-novel-talker-generalization paradigm
the real-talker HVPT studies use, and I couldn't get past Concordia's
repository 403 to read past the abstract, so I can't check what the
authors themselves make of the null result. But it's the only study that
asks this exact question, and it says "no."

I looked for a theoretical bridge too — do current neural voices sound
close enough to real speaker variation that the real-talker findings might
reasonably transfer anyway? Two adjacent papers (Calandruccio et al. 2025
on masked-speech recognition with human vs. cloned voices; Bakkouche et al.
2025 on naturalness ratings) suggest a *single* modern clone can
perceptually substitute for the *specific person it was cloned from*.
Neither says anything about whether a library of unrelated synthetic voices
spans between-speaker variability — vocal-tract-scale acoustic differences,
not just style — the way genuinely different humans do. That's inference on
my part, not a finding, and I'm flagging it as such rather than letting it
quietly become the justification.

One more relevant, narrower question: does ElevenLabs' same-voice
style/stability controls count as "variability" in the HVPT sense, or does
the effect need actually different voice IDs? No direct research either
way. HVPT's own theoretical account is that the mechanism is abstracting a
phonetic category away from between-*speaker* differences — different
vocal tracts — not different delivery of the same voice. By that logic,
turning up expressiveness on one ElevenLabs voice is closer to "the same
single-talker condition, performed more dramatically" than to genuine
multi-talker variability. If you build this at all, source it from
genuinely distinct voice IDs, not style knobs on one voice.

## What this changes

Don't build "generate the drill in 4-6 ElevenLabs voices, expect the
generalization boost real-talker HVPT gets." That's building on a
mechanism the one study that tested it didn't find.

**What's still supported**: TTS-based pronunciation practice in general.
The Al-Shami study's *both* groups improved — single-voice TTS training
produced real gains, just not more than that from adding voices. That's
consistent with finding #1 from the earlier research pass (explicit
instruction beats passive exposure) and with the plain build-time-TTS plan
from `elevenlabs-pronunciation-scope.md` — giving 568 silent flashcards and
984 blank items *a* voice is worth doing regardless of how many voices.

**Revised design**: keep the tiers separate rather than blurring them.

| Tier | Source | What it's evidenced for |
|---|---|---|
| 1 | Real family audio, 2+ speakers | The actual HVPT effect — this is genuine multi-talker data, no assumption needed |
| 2 | Real family audio, 1 speaker, or single-voice TTS | Ordinary listen-and-discriminate practice — supported, just not the "beats single-talker" claim |
| 3 | Multiple ElevenLabs voices, no real audio at all | Better than nothing, but the multi-voice-specifically-helps claim is unvalidated for synthetic sources — don't market it as HVPT's proven effect |

Concretely: build the `discriminate` item type against tier 1 first, exactly
as §2 originally specified — that's the part with real evidence behind it.
Where a card has no real multi-speaker audio, fall back to a **single**
well-chosen ElevenLabs voice for ordinary practice (tier 2), not a
synthesized multi-voice set dressed up as HVPT. If you still want tier 3
later, build it, but the UI copy should say what it is — more exposure, not
a proven-equivalent substitute for tier 1 — the same "don't let a synthetic
voice pass as more than it is" discipline this whole project already holds
itself to elsewhere.

---

## The mechanics, for whichever tier you end up using ElevenLabs on

Confirmed directly from the SDK source (`elevenlabs-python` on GitHub,
which loads fine — only `elevenlabs.io` itself and the help centre 403
from this environment), not from docs prose:

**Searching the Voice Library**: `GET v1/shared-voices`
(`client.voices.get_shared(...)`). Confirmed filter params include
`language`, `accent`, `gender`, `age`, `search`, `featured`, `sort`, `page`,
`page_size` (max 100) — so you genuinely can search "Indonesian, filtered by
accent" in one call, not just "multilingual voice, hope it sounds right."
Could not confirm the expected value format for `language` (`"id"` vs.
`"Indonesian"`) — test both.

**Adding a found voice to your account**: `POST v1/voices/add/{public_user_id}/{voice_id}`
(`client.voices.share(...)`). Then generate against it exactly like any
other voice — same `POST v1/text-to-speech/{voice_id}` endpoint the earlier
scoping doc already specified.

**One real complication the earlier doc didn't know to check for**:
third-party reporting (unconfirmed against a primary source — blocked)
says the Voice Library search API specifically may require a paid plan, and
separately reports voice-slot caps — **Free: 3, Starter: 10**. If that's
right, it's a second, different constraint from the credit-volume math in
`elevenlabs-pronunciation-scope.md`: that doc found the free tier's 10,000
credits/month covers this deck's audio in two months on pure volume. A
3-voice cap wouldn't block *that* plan (it only ever used one voice), but
it would block sourcing 4-6 genuinely distinct voices for a discrimination
drill. If tier 3 gets built, this is worth confirming before assuming free
tier still covers it — verify at signup rather than assuming the earlier
doc's free-tier recommendation automatically extends to a multi-voice
feature it didn't originally scope.

**One thing I looked into and am recommending against outright**: Instant
Voice Cloning (`POST v1/voices/add` with `files`) could technically clone a
real person's voice from a short recording — including, mechanically
speaking, a family member's from the existing conversation audio. The SDK's
raw API call has **no consent parameter at all** — `name` and `files` are
the only required fields, which means any consent verification ElevenLabs
does happens in their web dashboard UI, not as something the API itself
enforces. That gap is exactly why I'm flagging this rather than treating it
as a routine feature: cloning a real, identifiable family member's voice
without their explicit informed consent for that specific use isn't
something to build regardless of what the API allows, and it would cut
directly against the one thing this whole project is careful to protect —
that a synthetic voice never gets to pass as one of these actual people. If
real people's voices are ever wanted for this deck, that's a conversation
to have with them directly, not an API call.

---

## Where this leaves the build order

`pronunciation-training-scope.md`'s order still holds — directed A/B
self-recording, then the discrimination drill, then the contrastive-pairs
deck. What changes is the discrimination drill's scope: build it against
real multi-speaker audio (tier 1) as originally specified, and treat
ElevenLabs multi-voice coverage as a separate, lower-confidence extension
to revisit later rather than folding it into the same feature now. Nothing
here is built yet — this was the "should we, and how would we" pass.
