# Scoping: what the SLA/phonetics research says, and what to build

Written 2026-08-01, follow-up to `elevenlabs-pronunciation-scope.md`. That
doc concluded the highest-value pronunciation feature needed no vendor at
all — record yourself, play it back against the reference clip. This doc
checks that conclusion against the actual research literature rather than
intuition, and turns the result into a concrete build order.

Sourcing note: the findings below come from a literature search (meta-
analyses preferred over single studies, flagged where it's the latter) —
not primary reading of every paper. Confidence markers are inline. Where a
finding is well-replicated I say so; where it's a single study or my own
inference from typology, I say that too, because the previous doc's
"could not confirm" discipline is worth keeping here.

---

## The one-paragraph version

Plain record-and-compare is **necessary but not sufficient** — the research
on self-assessment says learners reliably miss about half their own errors
without something structuring what to listen for. Two additions are strongly
evidenced and cheap: **directed A/B comparison** instead of open self-rating,
and a **multi-talker discrimination drill** (this is the single best-evidenced
technique in the whole literature — meta-analytic g ≈ 0.67–0.92 — and this
repo already has the raw material for it in the transcripts, unused). Both
are described below with build specs. A few tempting things are explicitly
**not** recommended yet, with the reason why.

---

## What the evidence says, condensed

| # | Finding | Strength | What it means here |
|---|---|---|---|
| 1 | Explicit instruction beats passive exposure (d≈0.80, meta-analytic) | Strong | Every drill needs to *tell* the learner what to listen for, not just play audio at them |
| 2 | High Variability Phonetic Training — multi-talker discrimination + immediate feedback — generalizes to new talkers (g≈0.67–0.92) | Strong, meta-analytic | Best single technique to add. See §2 below |
| 3 | Intelligibility > nativeness; high-functional-load errors hurt comprehension more than cosmetic ones | Strong theory, 1 key study on cumulative effect | Curriculum should front-load contrasts that distinguish many word pairs, not just "sounds foreign" ones |
| 4 | Shadowing (near-simultaneous repeat) improves prosody, comprehensibility, fluency | Moderate, growing (2025 review, 44 studies); exact dosage unresolved | Already built (player's Shadow mode) — validated, not a new feature |
| 5 | Self-recording works via the noticing hypothesis, **but** unaided self-assessment misses ~half of real errors | Noticing theory strong; self-assessment-accuracy finding also strong | Don't ship a bare record button — see §1 below |
| 6 | Segmental (isolated-sound) accuracy doesn't reliably transfer to connected speech; interleaved practice beats blocked practice | Real, documented gap; interleaving moderately supported from motor-learning literature | Drill word → phrase → sentence, and never drill one contrast in a long unbroken block |
| 7 | Suprasegmentals (rhythm/stress) often outweigh segmentals for comprehensibility | Strong for Mandarin/Slavic→English; **not measured for English→Indonesian** | Can't assume the same weighting here — flagged as an open question, not applied blindly |
| 8 | Spacing helps motor-skill learning too (d≈0.96), but the mechanism (sleep-dependent motor consolidation) differs from vocabulary forgetting curves; no validated spacing *algorithm* exists for phonetics | Strong for "space it," unresolved for "how" | Don't force pronunciation drills through FSRS's interval math unmodified — see §4 |
| 9 | Indonesian-specific English-L1 trouble spots: pepet/taling-e schwa, ng-/ny- in word-initial position, final "k" as unreleased glottal stop, syllable-timed rhythm | 4 of 6 directly documented; vowel-reduction transfer and stop aspiration are typological inference, not directly cited | Basis for the contrastive-pairs deck in §3 |

---

## §1. Fix the self-recording plan from the ElevenLabs doc

The earlier recommendation was "record yourself, play it back next to the
reference clip." The self-assessment literature says that alone
underperforms because learners don't reliably notice their own errors —
noticing requires either external feedback or a task that forces a
judgement rather than an open "does this sound right?"

**Revised spec:**
1. Record the learner saying the target (word or example sentence).
2. **Forced-choice A/B, randomized order**: play the learner's clip and the
   reference clip in random order, ask "which one was you?" This is a task
   learners can actually do reliably (per the research), unlike open rating.
3. **Directed attention**, tied to the specific card's known trouble spot
   where one exists (see §3's tagging) — e.g. "listen for the final sound"
   on a card ending in orthographic *k*, "listen for the first sound" on an
   *ng-*/*ny-*-initial card. Generic cards get no prompt rather than a
   made-up one.
4. No vendor, no server. `MediaRecorder` + `<audio>` playback, entirely
   client-side, consistent with the rest of the site.

This slots onto the flashcard back and the fill-the-blank reveal — both
already show the example sentence with the target bolded, which is exactly
what step 3 needs to point at.

---

## §2. Multi-talker discrimination drill (the best-evidenced addition)

HVPT is the strongest result in the whole literature search — and this repo
already has unused raw material for a real-audio version of it, which is
more authentic than the synthetic-voice version most apps would default to.

**Checked against this repo, not assumed:** Conversation 1 has 4 distinct
transcribed speakers, Conversation 2 has 3. Scanning just the first 250
cards, **38 already have the same word said by two or more different
speakers** in the existing transcripts — `banyak` by five separate
speaker-turns across both recordings, `tangan`, `kaki`, `besar`, `baju`,
`hamil`, `rumah sakit` by two or three. Nobody is currently listening to
more than one of them: `attach_context` picks a single best-scored line and
discards the rest.

**Protocol** (from the Logan/Lively/Pisoni line and the recent meta-analysis):
short forced-choice trials, multiple talkers, **immediate correctness
feedback on every trial** — feedback-free discrimination shows much weaker
effects, so this part is not optional. Meta-analytic effects show up after
as little as three 20-minute sessions.

**Build**: a new item type, `discriminate`, generated at build time from
cards with ≥2 distinct real speaker clips (real audio only — don't fall back
to a single synthetic voice standing in for "multiple talkers," that isn't
what the research tested). Play clip A and clip B of the *same* word from
two different speakers, or a minimal-pair contrast from two different words,
and ask which. Where the repo doesn't have 2+ real speakers for a target
contrast (most cards, still — 38 of 250 is real but not most), skip it
rather than fake variety with one synthetic voice standing in for several,
until/unless the ElevenLabs multi-voice option from the other scoping doc is
in place.

Session size: 20–40 trials, matching the studied protocol — small enough to
fit before or after a normal Study session rather than replacing it.

---

## §3. A curriculum, not just a mechanism — contrastive minimal pairs

HVPT needs *contrasts* to train on. The literature review surfaced four
documented English→Indonesian trouble spots and two typologically-inferred
ones (flagged as such, not oversold):

| Contrast | Status | Example pair to author |
|---|---|---|
| pepet (schwa /ə/) vs. taling (clear /e/), both spelled *e* | Documented | `teh` (tea, clear e) vs `enam` (six, schwa) |
| *ng-*/*ny-* in word-initial position (not a legal English onset) | Documented | `ngomong` / `nyaman` vs. any vowel-initial word |
| Final orthographic *k* as unreleased glottal stop, not released /k/ | Documented | `tidak`, `enak` — English instinct is to release it like "back" |
| Syllable-timed rhythm vs. English stress-timing | Documented (though Indonesian word-stress itself is unsettled in the literature — don't over-engineer a "correct stress" drill) | Any multi-syllable word said at even timing |
| No vowel reduction under stress (Indonesian vowels stay full) | **Inferred from rhythm typology, not directly cited** | Any word where English instinct would reduce an unstressed syllable to schwa |
| Under-aspirated instinct on p/t/k (mirror of the well-documented Indonesian→English direction) | **Inferred from general L1-transfer phonetics, not directly cited for this direction** | `pasar`, `tahu`, `kita` |

This is a new small reference deck — `vocab/pronunciation-contrasts.tsv` or
similar — hand-authored the same way the example sentences were, not
generated. It needs a linguist's or a fluent speaker's ear on the pairs
before shipping, same as any example sentence here; I can draft candidates
but they need the same "sourced from real usage, grammatically checked"
bar the rest of the deck holds itself to.

---

## §4. What NOT to change

**Don't retrofit FSRS's interval math onto pronunciation drills.** The
spacing effect is real for motor skills too, but the mechanism (sleep-
dependent motor consolidation) differs from the forgetting-curve math FSRS
implements for vocabulary, and no study has validated a specific spacing
*algorithm* for phonetic drills. Concretely: keep pronunciation practice as
short, frequent, unscheduled sessions (available whenever, not "due" on a
calculated date), and lean on interleaving multiple contrasts within a
session rather than trying to compute an optimal review interval per
phoneme.

**Interleaving is already correct, for free.** §6 of the research flags that
blocked drilling (20 straight trials of one contrast) is worse than
interleaved practice, even though blocked drilling *feels* more successful
in the moment. `pickNext()` across flashcards/quiz already draws randomly
from the due pool rather than grouping by tag — the existing scheduler
already does the right thing here. Nothing to build, just worth knowing why
it's right as-is when designing the new item types above.

**Don't assume suprasegmentals matter more than segmentals here.** That
result is specific to Mandarin/Slavic-background learners of *English* and
hasn't been measured for English speakers learning Indonesian. Build both;
don't deprioritize the segmental contrasts in §3 on the strength of a
finding from the opposite language pair.

**ASR-based corrective feedback — real evidence (g≈0.69), explicitly
flagged as a later stretch, not now.** The meta-analysis found *explicit
corrective* ASR feedback works; passive transcription doesn't. Two paths:
the browser's free `Web Speech API` (no vendor, works today, English-biased
accuracy for Indonesian is unverified) or ElevenLabs Scribe v2 (confirmed
Indonesian support, ~$0.22/hr, per the other scoping doc). Worth a
follow-up once §1–§3 are built and it's clear where the ceiling of
self/peer-comparison actually is — building an ASR grader before that is
solving a problem you haven't confirmed you still have.

---

## Suggested build order

1. **§1 — directed A/B self-recording.** Cheapest, no vendor, fixes the
   weakest link in the existing plan.
2. **§2 — multi-talker discrimination drill from real audio.** Strongest
   evidence in the review, and the raw material already exists unused in
   the transcripts.
3. **§3 — contrastive-pairs deck**, feeding §2 with authored minimal pairs
   beyond what's already in the corpus, and tagging existing cards so §1's
   directed-attention prompts have something to point at.
4. **ASR corrective feedback** — only after 1–3 are in and it's clear
   self/peer comparison isn't enough on its own.

Nothing here is built yet. This is the design pass; say the word on any of
1–3 and I'll spec the exact code changes the way the Fill-the-blank mode
was built.
