# Conversation 2 — Notes

Recording: `Recording-2026-07-02-21-49`, ~113 minutes, transcribed with Soniox.
Cleaned transcript: [`transcripts/conversation-2.clean.txt`](../transcripts/conversation-2.clean.txt)

Nearly twice the length of Conversation 1, and a very different mix: **952 Indonesian lines to
Conversation 1's 473**, with far less English around them. Devin is much less present in this one — it's
mostly the family talking to each other, which makes it harder listening and better material.

## What's different about this export

Soniox was run **with translation switched on**, so every utterance in the raw export is followed by its
machine translation:

```
[00:00] Speaker 1:
[Indonesian] "Mungkin banjir nih."
[English] "Maybe it's a flood."
```

Conversation 1's export had one line per block, where an `[English]` block meant somebody actually *spoke*
English. Running the normal pipeline on this file would have silently discarded every translation, so the
import goes through [`scripts/import_soniox_translated.py`](../scripts/import_soniox_translated.py) first —
see **Pipeline** in [`STUDY-METHOD.md`](../STUDY-METHOD.md).

Practical upshot: **948 of the 952 Indonesian lines came pre-translated**, so no translation pass was needed.
These are machine translations and they show it in places (see *Caveats*).

## Who's talking

Inferred from context only — treat as provisional, correct it as you listen:

- **Speaker 1** (585 lines) and **Speaker 2** (578 lines) carry the conversation almost equally. Both are
  fluent native speakers, switching between household logistics, money admin and teasing.
- **Speaker 3** (56 lines) drops in occasionally — from context, likely a child or younger family member
  (the zombie/monster exchanges around 48–64 min read that way).
- Referenced by name: **Bu/Mbak Uti**, **Kelvin (KVN)**, **Indri**, **Rani**, **Yusri**, **Iwan**, and a
  **nenek** (grandmother) who is talked about in the third person.

## Timeline (topic index)

| Time | Topic |
|---|---|
| 00:00–08:00 | Rain and a possible flood; cutting/preparing food alongside it |
| 08:00–16:00 | Food talk — crackers, *pisang goreng* (fried bananas); someone messaging back and forth |
| 16:00–32:00 | **Bank account admin.** Account numbers read aloud digit by digit, which bank, old vs new number, "*titik*" for the full stop. Dense with numbers — good listening drill |
| 32:00–40:00 | **Arisan logistics**: transfers, dates ("Monday, July 6th"), who pays whom, the *bendahara* (treasurer), notification for August |
| 40:00–48:00 | **In the car** — directions, which road is faster, traffic |
| 48:00–64:00 | **Watching a zombie/horror show.** Kids reacting, "how do zombies walk like that?", being scared of monsters |
| 64:00–80:00 | Garden and outdoor chores; health of an older relative; grandma being left alone |
| 80:00–96:00 | **Cleaning and cooking** — clearing things out, throwing things away, starting to cook, cake |
| 96:00–1:43 | Packing and a trip; books; assorted household back-and-forth |
| *1:43:27–1:53:14* | **Japanese TV in the background** (44 lines, a drama/anime). Not family speech — it produces no flashcards or quiz items, but it does show in the player transcript |

## Vocabulary mined

[`vocab/conversation-2-vocab.tsv`](../vocab/conversation-2-vocab.tsv) — 103 entries, chosen by frequency
against everything already in the decks rather than by skimming, so it fills genuine gaps.

The striking finding: after 450 cards of particles, adjectives, comparisons, connectors and verbs, the decks
still had **no pronouns, demonstratives, question words or core function words**. `ini`, `itu`, `yang`, `dia`,
`nggak`, `apa`, `saya`, `aku` are among the most frequent words in this recording and none of them were
covered. Those are now tagged `pronoun`, `demonstrative`, `question`, `time` and `grammar`.

Also worth its own mention: **`arisan`** — a rotating savings club where members pay in regularly and take
turns receiving the pot. It's as much a social obligation as a financial one, and it drives a solid 15 minutes
of this recording. There's no clean English equivalent.

## Caveats

- **The translations are machine-generated and unreviewed.** Most are fine; some are visibly wrong where the
  ASR mis-heard. "My car is already drunk" (~40 min) is a mistranscription, not an idiom, and "The cracker
  just brought fried bananas" has mangled a name into "cracker". Treat a confusing translation as suspect
  before assuming you misunderstood the Indonesian.
- Because Sentence and Listening quiz modes rate you against these translations, use the **"Not real content"**
  flag on any line where the translation is clearly broken — it removes that line everywhere at once.
- No ASR hallucination loop in this recording (the cleaner collapsed **0** lines), unlike Conversation 1's
  ~22-minute "I'm sorry" run.
