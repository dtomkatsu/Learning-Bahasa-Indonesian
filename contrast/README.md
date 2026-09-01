# Discrimination foils

Real Indonesian words that exist in this project **only as the wrong option**
in the Minimal pairs quiz mode. They are never flashcards, never scheduled,
and never counted in the deck.

## Why they exist

`build_pair_items()` can only build a pair when both halves are words the
deck already contains *and* both have a real Lingua Libre recording. That
capped the drill at 31 pairs, 13 of them on a documented English-L1
contrast — not because the audio was missing, but because the deck is mined
from what one family happened to talk about. The contrast a learner most
needs to hear is frequently a common word paired against another common word
that never came up in the recordings: *sapi/sepi*, *taman/teman*,
*becak/becek*, *musik/musim*, *kakak/kakek*, *pandai/pantai*.

Adding those partners as flashcards would have worked, and would also have
added review obligations for words chosen by their spelling rather than by
whether they are worth knowing. A foil closes the gap without that cost.
Adding 38 of them took the drill to 74 pairs, 54 on a documented contrast.

## The rules

1. **A foil must be a real, standard Indonesian word.** Lingua Libre carries
   plenty of regional and nonstandard spellings — *aer*, *aje*, *bunge*,
   *banyek*, *saptu*, *telinge*, *apotik*. 96 partner words were available
   and 58 were rejected on this rule alone. A drill that shows a nonword next
   to a gloss teaches the learner that the nonword is a word.
2. **Never foil vs. foil.** Enforced in `build_pair_items()`. The drill earns
   its place when one option is a word you are actually learning; two
   unknowns test nothing but raw acoustics against two glosses read for the
   first time.
3. **Both halves need real audio.** Already enforced — the pool is
   intersected with `audio/ll/index.json`. `fetch_lingualibre.py` includes
   foils in `deck_fronts()` so their recordings are fetched; a foil with no
   clip silently drops the pair it was added for.
4. **A gloss, not a definition.** The hint is one short line, the same
   register as a card back.

## Adding more

327 further documented-contrast pairs are available in Lingua Libre where
*neither* half is currently a deck word, so the ceiling is far above 74.
They need judging word by word against rule 1 — that is the whole cost, and
it is the only real work here. There is no API and no spend involved:
Lingua Libre is CC BY-SA volunteer audio, attributed per file in
`audio/ll/CREDITS.json`.

Format: `word<TAB>gloss`, `#` for comments.
