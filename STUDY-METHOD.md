# Study method — Bahasa Indonesia comprehension from real family audio

The core asset here isn't a textbook, it's real, unscripted speech from Dila's family: fast, code-switched,
particle-heavy, and specific to the people and places in your actual life. The goal isn't "pass a test," it's
"understand this family in real time." The method below is built around that.

## Pipeline for each new recording

1. Drop the raw Soniox export in `transcripts/<name>.raw.txt` and the audio in `audio/<name>.<ext>`.
2. Clean it: `python3 scripts/clean_transcript.py transcripts/<name>.raw.txt transcripts/<name>.clean.txt`
   This strips ASR hallucination loops (it got stuck on "I'm sorry" / "quiet" for ~22 minutes in Conversation 1)
   while preserving every genuine line. Always eyeball the diff in size — if it removes almost nothing or almost
   everything, the audio quality/heuristic needs a look.
3. Skim the clean transcript once and write a `notes/<name>-notes.md` like the one for Conversation 1: speaker
   map, topic timeline with timestamps, anything culturally/grammatically notable.
4. Mine vocab into `vocab/<name>-vocab.tsv` (three columns: Indonesian, English/notes, tag) — only add things you
   didn't already know cold. Don't re-log particles you've already logged once; cross-check against
   `vocab/conversation-1-vocab.tsv` first.
5. Run the four listening passes below against the audio + clean transcript.

## The four passes (per recording, or per meaty chunk of one)

**Pass 1 — Blind listen.** Audio only, no transcript, no subtitles. Just try to follow: who's talking, what's the
topic, catch whatever words you can. This is the actual skill you're training — everything else is scaffolding
for this. Don't rewind. Let yourself miss things.

**Pass 2 — Read-along shadow.** Open `transcripts/<name>.clean.txt` next to the audio. Play a stretch, pause,
repeat the Indonesian lines out loud matching rhythm and intonation, not just words — particles like *kan/sih/dong*
carry tone, not dictionary meaning, so shadow the music of the line, not just the text. This is where you fix
pronunciation and internalize sentence rhythm.

**Pass 3 — Mine and drill.** Anything you had to look up or guess at goes into the vocab TSV, then into Anki
(see below). Prioritize particles and connective phrases over nouns — you already know what "tofu" and "gas
station" mean conceptually, you just need the label; particles are actually new grammar.

**Pass 4 — Re-listen cold, one week later.** No transcript. This is the actual measurement: did comprehension
improve, or did you just memorize this one transcript? If a stretch is still opaque a week out, that's a signal
to re-shadow it, not to move on.

## Spaced repetition (Anki)

Import `vocab/conversation-1-vocab.tsv` as a TSV note type (Indonesian / English+notes / Tags — 3 fields map
directly to Anki's Basic note type: Front / Back / Tags). In Anki: **File → Import**, select the `.tsv`, map
column 1→Front, column 2→Back, column 3→Tags.

Two card directions matter here, and they're not equally useful:
- **Indonesian → English** is recognition — this is what you need for listening comprehension. Weight it heavier.
- **English → Indonesian** is production — useful but secondary right now since the immediate goal is
  understanding the family, not speaking flawlessly back.

If your Anki setup supports it, enable both card types but keep recognition reviews more frequent early on.

## Code-switching as a diagnostic, not noise

Dila and family switch to English constantly — and *what* they switch for is informative. Watch for:
- **Technical/legal/abstract terms** ("reprimanded," "C1/C2," "royalty") — these get switched because the
  Indonesian equivalent is less automatic for a bilingual speaker, not because there isn't one. When you notice
  a switch, look up the Indonesian term deliberately — that's a targeted gap in your vocabulary, hand-picked by
  the conversation itself.
- **Emotional/relationship language** ("I'm going to miss you," "sarcastic," "narcissistic") often stays in
  English — that's a register gap worth closing if you want to have those conversations in Indonesian too.
- When *you* (Devin) get replied to in English after speaking Indonesian, that's not necessarily correction —
  check the note in Conversation 1 around 48:37–48:59 where Dila explicitly says she avoids English so she can
  practice. Pay attention to who's optimizing for whose practice in any given exchange.

## Particles: treat them as their own syllabus

`notes/conversation-1-notes.md` has a running particle table. Every new recording, check off which ones show up
again (reinforcement) vs. which are new. Once you can identify a dozen of these by ear and roughly place their
function (agreement-seeking vs. surprise vs. softening vs. intensifying), you'll notice comprehension jump more
than any amount of noun vocabulary will get you — particles are what make fast native speech parseable.

## Cadence

Something sustainable beats something intense and abandoned:
- 15–20 min/day: one pass (rotate through the four) on whatever's the current recording.
- Weekly: Pass 4 (cold re-listen) on the previous week's material — this is the only real signal of progress.
- As new recordings come in: run the pipeline (clean → notes → vocab → passes) same as Conversation 1.

## Known limitation

`scripts/clean_transcript.py` only knows about the loop phrases seen so far ("i'm sorry", "thank you", "quiet").
If a future recording loops on something else, add the new phrase to `LOOP_CLAUSES` in the script rather than
hand-editing the transcript.
