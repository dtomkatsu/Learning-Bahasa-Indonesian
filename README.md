# Learning Bahasa Indonesian

A self-contained toolkit for building **listening comprehension of real, unscripted Indonesian** — the fast,
code-switched, particle-heavy way a family actually talks at home, rather than the clean sentences you get from
a textbook.

It's built around real recordings of my partner's family in Indonesia, made while they were testing a
live-translation app (Soniox) over ordinary evenings: errands, food, picking a movie, family history,
ordering pizza, arisan admin, a zombie film. Two conversations so far — 68 and 113 minutes, ~1,400
Indonesian lines between them. Everything here — the players, the flashcards, the quiz — is generated from
those transcripts and audio by a handful of Python scripts, and runs as plain HTML/JS with no server, no build step, and no account.

**▶ [Try it live](https://dtomkatsu.github.io/Learning-Bahasa-Indonesian/)**

## What's in it

| | |
|---|---|
| **Synced player** | Full transcript beside the audio. Click any line to jump there; hover for **loop** (repeat one line), **+ card** (capture that line's vocab straight into the flashcard deck); **Shadow mode** auto-pauses after every line so you can repeat it aloud; 0.6x–1.25x speed; toggle an English gloss under every Indonesian line. |
| **Flashcards** | ~1,000 cards (conversation-mined vocab + reference decks for adjectives, comparisons, connectors, a 176-verb deck tagged by function, and everyday-conversation decks: greetings, numbers, days/months, food, house, body/health, places/transport, shopping, weather, work/school, clothing, small talk). **Every card's back shows the word inside a written example sentence** with its translation, so you never learn a word as a bare gloss. Every card can also be **heard**: words that occur in the recording play the family actually saying them, with that line quoted separately under *"Heard in the recording"*; the rest fall back to Indonesian speech synthesis, clearly labelled so a synthetic voice is never mistaken for the real thing. Search, category chips with counts, and a **Browse** list of every card's scheduling state. Add cards one at a time, or paste a whole `front – back` list with an optional `(tag)` header per block. |
| **Quiz** | **Word** mode blanks a vocab term out of a real sentence (cloze) and plays that exact moment of audio. **Fill the blank** does the same over each card's written example sentence and asks you to *type* the missing word — which covers all ~980 cards rather than only the ~400 the family happened to say, and grades objectively (it accepts the dictionary form when the sentence inflects it, and tells you so). **Catch it** plays a real clip and asks which of four similar-sounding words was in it — built only from words two or more family members actually say, so you hear each one out of more than one mouth (the [HVPT](notes/hvpt-elevenlabs-build.md) protocol). **Sentence** mode checks you followed a whole line. **Listening** mode is ears-only: the clip plays with text hidden — the actual target skill. |
| **Pronunciation** | Every flashcard back has a **Say it** button: record yourself, and the page immediately plays the model and your attempt back to back, twice. Above it sits one “listen for” prompt keyed to that word's known trouble spot for English speakers — word-initial *ng-*/*ny-*, final *-k* as a glottal stop, unaspirated *p/t/k*. No score and nothing leaves the browser; see [`notes/pronunciation-training-scope.md`](notes/pronunciation-training-scope.md) for why a fake number would be worse than none. |
| **Spaced repetition** | Real **FSRS-5** — the algorithm Anki itself now recommends over SM-2 — with Again/Hard/Good/Easy and live interval previews on each button. Misclicked? **Go back** (`z`) restores that card's previous schedule and un-logs the review. A **Study now** mixed session interleaves everything due, sized to 10/20/50/all so a sitting is always finishable. Installable as a **PWA** on the phone. |
| **Stats** | Streak, 28-day heatmap, and overall recall rate, plus an editable **daily goal** and **recall by category, weakest first** — so it's obvious that connectors are at 40% while adjectives are at 90%, and what to drill next. |
| **Progress sync** | Auto-sync between devices via a **private GitHub gist** (paste a gist-scoped token once per device; pages pull on load, ratings push automatically) — plus manual JSON export/import as a fallback. Either way it merges rather than overwrites: per card, the more recent review wins. |

## The idea

Most courses teach you to parse careful, complete sentences. Real family speech is nothing like that, and the
thing that actually blocks comprehension isn't nouns — it's the **colloquial particles** (*kan, sih, dong, loh,
kok, banget, mah, atuh*) that carry tone rather than dictionary meaning, plus the constant English
code-switching. So the vocab decks deliberately weight particles over nouns, and
[`STUDY-METHOD.md`](STUDY-METHOD.md) treats *what the speakers switch to English for* as a diagnostic — those
switches are a gap list the conversation hand-picked for you.

The method itself is a four-pass loop per recording: blind listen → read-along shadow → mine vocab → cold
re-listen a week later. Details, including the particle glossary, are in
[`STUDY-METHOD.md`](STUDY-METHOD.md) and [`notes/`](notes/).

## Using it with your own recordings

Nothing here is specific to this conversation — point the scripts at your own transcript and audio:

```bash
# 1. Drop the audio in audio/<name>.<ext>, then import the transcript.
#    If your Soniox export has TWO lines per block (utterance + its machine
#    translation), use this — it writes the raw, cleaned and translation files
#    in one go, and would otherwise be silently discarded:
python3 scripts/import_soniox_translated.py ~/Downloads/<export>.txt <name>

#    If it has ONE line per block, drop it in transcripts/<name>.raw.txt and
#    strip ASR hallucination loops instead (Soniox got stuck repeating
#    "I'm sorry" for ~22 minutes of quiet audio in Conversation 1):
python3 scripts/clean_transcript.py transcripts/<name>.raw.txt transcripts/<name>.clean.txt

# 3. Build the pages (all of these re-scan everything from scratch)
python3 scripts/build_player.py transcripts/<name>.clean.txt audio/<name>.<ext> \
    <name>-player.html --title "Conversation N" --translations transcripts/<name>.translations.json
# (optional) fetch real volunteer recordings of the words themselves — free,
#    CC BY-SA, from Lingua Libre via Wikimedia Commons; covers ~58% of fronts
#    with real human voices (attribution lands in audio/ll/CREDITS.json)
python3 scripts/fetch_lingualibre.py --dry-run
python3 scripts/fetch_lingualibre.py

# (optional) give the remaining cards and every example sentence a studio
#    Indonesian voice, generated once at build time so no API key ever
#    reaches a browser. Voice Library voices need a paid ElevenLabs plan
#    (the free tier 402s on them); see notes/audio-retool.md for the full
#    model-audio source hierarchy.
export ELEVENLABS_API_KEY=...      # never committed; used only during this run
python3 scripts/build_tts.py --list-voices
python3 scripts/build_tts.py --voice <id> --dry-run
python3 scripts/build_tts.py --voice <id> --limit 20000

python3 scripts/build_flashcards.py
python3 scripts/build_quiz.py
python3 scripts/build_study.py
python3 scripts/build_index.py
```

Translations are optional (drop `--translations`). Conversation 2's came free with the Soniox export;
Conversation 1's were produced by fanning out parallel LLM calls over chunks of the Indonesian lines, each
given the particle glossary for context, then merged by line index. See [`STUDY-METHOD.md`](STUDY-METHOD.md).

Requirements: Python 3 (standard library only). `scripts/build_icon.sh` additionally uses headless Chrome and
macOS's `iconutil`, but that's only for the optional desktop-app wrapper.

## Tests

```bash
python3 tests/run_tests.py
```

Runs the browser-side logic — FSRS scheduling, the gist sync merge rules, undo, the review log, the bulk vocab
parser — under Node with a `localStorage` shim, then syntax-checks the inline script of every generated page.
No dependencies beyond Node itself.

The suite is deliberately scoped to pure functions, because that's where the real bugs in this project have
been: an FSRS formula, a merge rule, a parser edge case. It is verified by mutation — breaking the `rev`
tiebreaker, the parser's separator rule, the goal clamp, the item-key logging, or "Again" scheduling each makes
it go red. Note that `node --check` only catches *syntax*, so a call to a function that no longer exists still
passes; the browser is still the place to check rendering and audio.

## Layout

```
scripts/          build scripts (all stdlib Python) + FSRS engine + icon art
transcripts/      raw Soniox exports, cleaned transcripts, translations
audio/            source recordings
vocab/            TSV decks (Indonesian / English+notes / tag) — Anki-importable as-is; not all decks need to
                  come from a conversation (common-adjectives.tsv, comparisons.tsv, connectors.tsv, verbs.tsv
                  are standalone reference decks)
notes/            speaker map, timestamped topic index, particle glossary, cultural notes
*.html            generated: player, flashcards, quiz, landing page
```

The generated HTML is committed so the site works straight from GitHub Pages.

## A note on the recording

The audio is a real family conversation, published with their knowledge. It's included because the whole point
of the project is that *authentic* speech — with its overlaps, mumbles, dialect, and mis-transcriptions — is the
thing worth training on. If you're reusing this repo, please bring your own recording rather than
redistributing theirs.

## Desktop app (macOS, optional)

`scripts/bahasa-player.applescript` compiles to a double-clickable **Bahasa Player.app** that opens the local
copy in a chromeless Chrome window:

```bash
osacompile -o ~/Applications/"Bahasa Player.app" scripts/bahasa-player.applescript
./scripts/build_icon.sh   # re-apply the icon; osacompile resets it
```
