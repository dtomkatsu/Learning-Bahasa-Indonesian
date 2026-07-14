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
5. (Optional but recommended) Translate the Indonesian lines to English — see **Translations** below.
6. Build a synced player: `python3 scripts/build_player.py transcripts/<name>.clean.txt audio/<name>.<ext>
   <name>-player.html --title "Conversation N" --translations transcripts/<name>.translations.json`
   (drop `--translations` if you skipped step 5). See **Playing the audio** below.
7. Regenerate `flashcards.html` (`python3 scripts/build_flashcards.py`), `quiz.html`
   (`python3 scripts/build_quiz.py`), and `index.html` (`python3 scripts/build_index.py`) — flashcards/quiz pull
   from *all* vocab decks and transcripts automatically, so re-running them picks up the new conversation.
8. Run the four listening passes below against the audio + clean transcript.

## Translations

For a conversation's Indonesian lines to show English translations in the player (and to get sentence
translations in quiz reveals), build `transcripts/<name>.translations.json` — a JSON object mapping each
Indonesian-language entry's index (0-based over the full parsed transcript, string keys) to an English string.

There's no automated translation API wired up; Conversation 1's 473 lines were translated by splitting the list
into chunks and dispatching parallel research-agent calls (via the `Agent` tool), each given
`notes/conversation-1-notes.md` for context (particle glossary, speaker roles, cultural notes) and asked to
return strict JSON `[{"idx": N, "en": "..."}]`. The results were merged with a short Python snippet into the
single `.translations.json` file. Repeat that pattern for new conversations — it's the same shape of work every
time (extract Indonesian lines → chunk → translate with context → merge by idx → sanity-check no idx is missing).

## Playing the audio

`scripts/build_player.py` generates a self-contained HTML page (already built for Conversation 1 as
`conversation-1-player.html`) with the audio and full transcript side by side:

- Click any line and the audio jumps there and starts playing.
- Hover a line for a **loop** button — repeats just that line, for shadowing.
- Speed buttons (0.6x/0.75x/1x/1.25x) for slow listening on hard stretches.
- The transcript auto-highlights and scrolls to follow playback.
- A search box to jump straight to a phrase.
- **Show translations** toggle (top right) reveals an English gloss under every Indonesian line, if a
  `--translations` file was supplied at build time. Off by default — the point is to try comprehension first.
- **Flagging bad lines**: Soniox sometimes transcribes silence/noise as garbled text, or two lines round to the
  same timestamp so "play just this line" can't isolate one from the other. Hover a line for a **flag** button —
  flagging hides it from the transcript (there's a "Show flagged (N)" toggle to review/undo) and also excludes
  any quiz cards built from that same line, since flags are shared across pages via `localStorage`. This is a
  manual, ongoing curation step, not something the build scripts can detect on their own.

`scripts/build_index.py` regenerates `index.html`, a landing page linking to every `*-player.html` in the
project, plus the Flashcards/Quiz practice modes — run it after adding a new conversation's player so it shows
up there too.

## Comprehension exercises

Two practice modes, both self-contained HTML/JS with progress saved to the browser's `localStorage` (a simple
4-box mastery system: get it right, it shows up less often; get it wrong, it resets to box 0 and comes back
soon). Neither needs a server or an account.

- **`flashcards.html`** (`scripts/build_flashcards.py`) — flips through every `vocab/*.tsv` deck. Filter by tag
  (particle, food, family, etc.), rate "still learning" / "got it", `space` to flip, `1`/`2` to rate.
- **`quiz.html`** (`scripts/build_quiz.py`) — two modes, toggled at the top of the page:
  - **Word** — cross-references vocab terms against real transcript lines. A term used inside a longer sentence
    becomes a **cloze** card (blank it, guess from context, play the actual audio of that line, then reveal). A
    term that basically *is* the whole line (most of the "phrase" tag entries) becomes a **recall** card (listen
    first, then reveal). Terms with no match in any transcript are silently skipped.
  - **Sentence** — tests whether you followed the *whole* line, not just one word in it. Every Indonesian line
    with a translation and at least 4 words becomes a card: read (and optionally play) the real sentence, then
    reveal the full English translation and self-rate. Filter switches to conversation source instead of vocab
    tag in this mode.
  
  Both modes share the same 4-box mastery tracking (tracked separately per mode) and re-scan everything from
  scratch — re-run after adding a new conversation or vocab deck. Each card also has a **"Not real content"**
  button (same flagging system as the player) — use it if "Play line" is silent or the caption is ASR garbage;
  it's excluded immediately and won't be regenerated on the next build since flags live in the browser, not the
  transcript file. "Unflag lines (N)" clears everything if you flag something by mistake.

Both are linked from `index.html` under "Practice," so they're reachable from **Bahasa Player.app** like
everything else — no separate app needed.

### The app (no terminal needed)

**Bahasa Player.app** lives in `~/Applications` — double-click it (or find it in Spotlight/Launchpad) and it
opens `index.html` in a clean, tab-free Chrome window, like a real app. This is the everyday way to use this —
no commands required.

If it ever needs rebuilding (e.g. after moving the project folder), the source is a one-line AppleScript that
shells out to `open -na 'Google Chrome' --args --app=file://<path to index.html>`, compiled with:
```
osacompile -o ~/Applications/"Bahasa Player.app" bahasa-player.applescript
```

### Manual fallback

Opening the HTML directly also works, if you ever want it in a normal browser tab instead:
```
open ~/Learning-Bahasa-Indonesian/index.html
```

If seeking feels broken in a browser (some are picky about local-file media seeking), serve the folder over
HTTP instead, which is guaranteed to support seeking:
```
cd ~/Learning-Bahasa-Indonesian && npx --yes http-server -p 8770 --cors -c-1
```
then open `http://localhost:8770/index.html`. (Plain `python3 -m http.server` does *not* work for this — it
doesn't support the HTTP Range requests that audio seeking needs.)

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
