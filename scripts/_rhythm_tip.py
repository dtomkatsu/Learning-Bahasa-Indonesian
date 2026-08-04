"""Shared sentence-level rhythm/stress prompt, shown wherever a whole
Indonesian sentence is practiced aloud: flashcards' say-it-yourself compare,
quiz's Sentence and Listening modes, and the player's Shadow mode.

Why this exists: notes/sentence-pronunciation-scope.md found that
pronunciation training's biggest comprehensibility gains come from
prosody-focused instruction specifically, not segmental instruction alone —
and every sentence-level exercise here trained rhythm only implicitly, via
real audio, with no directed-attention prompt the way SAY_TIPS already
gives individual words (see notes/pronunciation-training-scope.md finding
#1: explicit instruction beats passive exposure).

Deliberately ONE constant message, not per-sentence content like SAY_TIPS:
the underlying claim — Indonesian is syllable-timed, English is
stress-timed — is a typological fact about the language, not a property of
any one sentence, so there is nothing to vary per item. Also deliberately
narrower than it could be: pronunciation-training-scope.md §3 explicitly
warns that Indonesian word-stress placement itself is unsettled in the
literature, so this names only the well-documented rhythm pattern and stops
there rather than inventing stress-placement rules for individual words.
"""

RHYTHM_TIP_TEXT = (
    "Indonesian is <b>syllable-timed</b>: every syllable gets roughly equal "
    "length and weight. English is stress-timed and compresses unstressed "
    "syllables toward “duh” to keep a beat — that instinct will "
    "speed up and swallow parts of this sentence that Indonesian keeps full."
)
