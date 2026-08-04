# Scoping: what the evidence says about pronouncing whole sentences

Written 2026-08-03, follow-up to `pronunciation-training-scope.md`. That doc
scoped word- and phoneme-level training (self-recording, HVPT minimal pairs,
the contrastive-pairs deck) and flagged one open question rather than
answering it: does suprasegmental (rhythm/stress/intonation) accuracy matter
more than segmental (individual sound) accuracy for this project, or was
that an assumption imported from research on a different language pair? This
is the follow-up literature pass that question asked for, scoped specifically
to sentence- and connected-speech-level pronunciation rather than isolated
words.

Sourcing note: OpenAlex (keyless, no CAPTCHA gate) rather than Perplexity —
the usual browser path hit a Cloudflare human-check this session, not
something to click through. Search precision was noticeably worse than a
literature-aware search engine for narrow phrases ("connected speech
features training", "TTS pronunciation imitation", "chunking phrase length")
— those queries returned noise, not silence, and are reported as such below
rather than quietly dropped. What follows is what a keyword search over a
real bibliographic index actually surfaced, cross-checked by reading full
abstracts, not titles alone.

---

## The one-paragraph version

Three meta-analyses, read in full, converge on a specific and actionable
split: **pronunciation instruction works overall (this is settled, large
effect), and when the goal is comprehensibility specifically — being
understood, not sounding native — prosody-focused instruction outperforms
segmental instruction disproportionately.** Nativelike accent is a different
goal with a different, harder answer: it ties to segmental accuracy, which
resists instruction more. This project has real audio that trains prosody
*implicitly* (shadowing, already built) but nothing that trains it
*explicitly* — and finding #1 from the original scoping pass (explicit
instruction beats passive exposure) applies exactly as much here as it does
to segmentals.

---

## What the evidence says

| # | Finding | Strength | What it means here |
|---|---|---|---|
| 1 | Pronunciation instruction overall has a large effect: d≈0.80–0.89 (Lee, Jang & Plonsky 2015, meta-analysis of 86 studies) | Strong, meta-analytic, 426 citations | Baseline confidence that any well-built drill is worth building, not just the specific ones below |
| 2 | Effect size moderators: **longer interventions**, **treatments providing feedback**, and **controlled (not spontaneous) outcome measures** all show larger gains (same source) | Strong | Argues for *sustained*, *graded* practice with feedback — matches this project's FSRS-scheduled, immediate-feedback design already; argues against one-off drills |
| 3 | Instruction is most effective when it targets **monitored production of specific segmental or suprasegmental features** — picking one concrete target, not vague global practice (Saito et al. 2019, 77 studies) | Strong | Same "narrow attention to one feature" principle already used by `SAY_TIPS` — extends it to prosody, where nothing narrow currently exists |
| 4 | Instruction produces **larger comprehensibility gains than nativelikeness gains**, and this gap is **largest specifically when training targets prosody** (Saito 2021 meta-analysis: 37 listener studies + 17 training studies) | Strong, dual meta-analysis, direct citation | The actionable finding — see below |
| 5 | Nativelikeness/accentedness judgements tie strongly to **segmental** (consonant/vowel) accuracy, which is "resistant to the influence of instruction" (same source) | Strong | Sets expectations: the minimal-pairs/say-tip work already done targets the harder-to-move goal; that's fine, but don't expect it to move comprehensibility as much as prosody work would |
| 6 | Comprehensibility itself is genuinely multi-factorial — segmental, prosodic, *and* temporal (pacing/pausing) features all predict listener judgements (same source, Study 1) | Strong | Rhythm/stress isn't the *only* lever; pacing and pausing are a distinct, separately-evidenced factor this project doesn't address at all |
| 7 | Targeted, specific searches on connected-speech features (linking, reduction), TTS-as-imitation-model, and chunking/phrase-length effects returned **no relevant results** through this index | **Absence of evidence, not evidence of absence** | Don't cite a finding for these — flagging the gap instead of filling it with the general prosody findings above, which is a different claim |

---

## The actionable gap

Cross-referencing against what's actually built: every current exercise that
touches whole sentences trains prosody **implicitly at best**.

- **Shadowing** (player) — real connected speech, but no directed attention;
  finding #3 above says explicit-target training beats this alone, the same
  logic `pronunciation-training-scope.md` already applied to segmentals.
- **Say-it-yourself on a sentence** — compares your attempt to a model, but
  the only directed-attention prompt (`say_tip()`) is segmental, keyed to
  the target *word*, and says nothing about the sentence's rhythm or stress.
- **Fill-the-blank's "Hear the sentence"** — audio exists (once the
  ElevenLabs sentences are generated) but the exercise itself tests typed
  lexical recall, not pronunciation, production, or prosody at all.

Nothing currently says, in effect, "listen for where the stress falls" or
"listen for how these words run together" the way `SAY_TIPS` already says
"listen for the glottal stop." That's a real, specific, buildable gap — not
a vague "could be better."

**What I'm not recommending**: importing finding #4's exact ranking (prosody
> segmentals for comprehensibility) as settled fact for English→Indonesian
specifically. That result comes from general L2-English-acquisition research
across many L1 backgrounds and English as the target, not this language
pair. `pronunciation-training-scope.md` finding #7 already flagged this
exact caution for a different, narrower claim (Mandarin/Slavic rhythm
findings), and it applies here too: the *general* case for explicit prosody
instruction is now well-evidenced; the claim that it's the *specific*
priority over segmentals for English speakers learning Indonesian is not
established by anything found this session.

---

## If this gets built

Sketched, not specified — this is a research pass, matching the discipline
of the doc it follows ("nothing here is built yet").

1. **A prosody-directed attention prompt for sentences**, parallel to
   `say_tip()` but keyed to the sentence rather than the word — e.g. flagging
   Indonesian's syllable-timed rhythm against English stress-timing (already
   named as a documented contrast in `pronunciation-training-scope.md` §3),
   shown before shadowing or the say-it-yourself compare on a sentence.
2. **Pacing/pausing as a distinct, separate axis** (finding #6) — worth its
   own prompt rather than folding into "prosody" generically, since the
   evidence treats it as a separate predictor of comprehensibility.
3. Both would need the same "hand-authored, native-speaker-checked" bar
   `pronunciation-training-scope.md` §3 already holds contrastive pairs to —
   a general rhythm-typology claim being *true* doesn't mean a specific
   authored prompt about it is *correct* for a specific sentence without
   someone who speaks the language checking it.
