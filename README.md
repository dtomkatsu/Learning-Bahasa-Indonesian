# Learning Bahasa Indonesian

A self-contained toolkit for building **listening comprehension of real, unscripted Indonesian** — the fast,
code-switched, particle-heavy way a family actually talks at home, rather than the clean sentences you get from
a textbook.

It's built around one 68-minute recording of my partner's family in Indonesia, made while they were testing a
live-translation app (Soniox) over an ordinary evening: errands, food, picking a movie, family history, ordering
pizza. Everything here — the player, the flashcards, the quiz — is generated from that transcript and audio by a
handful of Python scripts, and runs as plain HTML/JS with no server, no build step, and no account.

**▶ [Try it live](https://dtomkatsu.github.io/Learning-Bahasa-Indonesian/)**

## What's in it

| | |
|---|---|
| **Synced player** | Full transcript beside the audio. Click any line to jump there; hover for a **loop** button to repeat one line while shadowing; 0.6x–1.25x speed; toggle an English gloss under every Indonesian line. |
| **Flashcards** | ~84 vocab cards mined from the conversation, filterable by tag. |
| **Quiz** | **Word** mode blanks a vocab term out of a real sentence (cloze) and plays that exact moment of audio. **Sentence** mode checks you followed a whole line, not just one word in it. |
| **Spaced repetition** | Real **FSRS-5** — the algorithm Anki itself now recommends over SM-2 — with Again/Hard/Good/Easy and live interval previews on each button. Progress lives in `localStorage`. |
| **Progress sync** | Export/import progress as a JSON file to move schedules between devices. Merges rather than overwrites: per card, the more recent review wins, so an older export can't roll back newer progress. |

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
# 1. Drop in transcripts/<name>.raw.txt (Soniox export) and audio/<name>.<ext>

# 2. Strip ASR hallucination loops (Soniox got stuck repeating "I'm sorry" for
#    ~22 minutes of quiet audio in this recording; the script collapses those
#    runs while keeping every genuine line)
python3 scripts/clean_transcript.py transcripts/<name>.raw.txt transcripts/<name>.clean.txt

# 3. Build the pages (all of these re-scan everything from scratch)
python3 scripts/build_player.py transcripts/<name>.clean.txt audio/<name>.<ext> \
    <name>-player.html --title "Conversation N" --translations transcripts/<name>.translations.json
python3 scripts/build_flashcards.py
python3 scripts/build_quiz.py
python3 scripts/build_index.py
```

Translations are optional (drop `--translations`). There's no translation API wired up — the ones here were
produced by fanning out parallel LLM calls over chunks of the Indonesian lines, each given the particle glossary
for context, then merged by line index. See [`STUDY-METHOD.md`](STUDY-METHOD.md).

Requirements: Python 3 (standard library only). `scripts/build_icon.sh` additionally uses headless Chrome and
macOS's `iconutil`, but that's only for the optional desktop-app wrapper.

## Layout

```
scripts/          build scripts (all stdlib Python) + FSRS engine + icon art
transcripts/      raw Soniox export, cleaned transcript, translations
audio/            source recording
vocab/            TSV decks (Indonesian / English+notes / tag) — Anki-importable as-is
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
