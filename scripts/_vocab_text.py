"""Locating a vocab term inside a sentence, affixes and all.

Shared by build_flashcards.py (which bolds the term in the example sentence
on the back of a card) and build_quiz.py (which blanks that same span out to
make a fill-the-blank item). Both need the answer to one question — *where in
this sentence is this word?* — and both get it wrong in the same ways if they
answer it with a substring test.

Indonesian affixation means the card's dictionary form is usually not the
surface form: "tangkap" shows up as *menangkap*, "kunjung" as *mengunjungi*.
Worse, the meN-/peN- prefixes absorb the root's initial k/s/t/p, so those
words don't contain their own root as a substring at all. Rather than pull in
a stemmer, we walk the sentence and ask of each word: could this be the card's
word wearing affixes? — stripping known prefixes and suffixes and restoring
the elided consonant where the prefix implies one.

Deliberately over-generates rather than under-generates: a spurious candidate
root almost never collides with a real card front, whereas a missed one shows
up immediately as an unbolded example or a skipped quiz item.
"""
import re

PREFIXES = [
    "memper", "member", "menge", "meng", "meny", "mem", "men", "me",
    "penge", "peng", "peny", "pem", "pen", "pe",
    "diper", "di", "ter", "ber", "be", "se", "ke",
]
# Which initial root consonant each nasal prefix absorbs (meng- + kirim -> mengirim)
ELIDED = {"meng": "k", "peng": "k", "meny": "s", "peny": "s",
          "men": "t", "pen": "t", "mem": "p", "pem": "p"}
SUFFIXES = ["kannya", "annya", "inya", "nya", "kan", "an", "lah", "i"]

WORD_RE = re.compile(r"[A-Za-zÀ-ÿ]+(?:-[A-Za-zÀ-ÿ]+)*")

# Clitics a multi-word front's final word can pick up in a running sentence
# ("kamar mandi" -> "kamar mandinya").
TRAILING_SUFFIX = r"(?:nya|ku|mu|kan|an|lah)?"


def possible_roots(word):
    """Every dictionary form the given surface word could be an inflection of."""
    w = word.lower()
    stems = {w}
    for pre in PREFIXES:
        if w.startswith(pre) and len(w) > len(pre) + 1:
            rest = w[len(pre):]
            stems.add(rest)
            if pre in ELIDED:
                stems.add(ELIDED[pre] + rest)
    roots = set(stems)
    for s in stems:
        for suf in SUFFIXES:
            if s.endswith(suf) and len(s) > len(suf) + 1:
                roots.add(s[: -len(suf)])
    return roots


def bounded(term):
    """Regex matching the term as a whole span in running text.

    Three wrinkles the naive \\b version gets wrong: fronts that end in
    punctuation ("Apa namanya?") — \\b can't sit after a "?"; fronts written
    with an ellipsis placeholder ("Di mana…?"); and multi-word fronts whose
    last word picks up a clitic in a real sentence ("kamar mandi" surfacing as
    "kamar mandinya").
    """
    core = re.sub(r"[…?!.]+\s*$", "", term.strip())
    words = core.split()
    if not words:
        return re.compile(r"(?!x)x")     # never matches
    body = r"\s+".join(re.escape(w) for w in words)
    lead = r"(?<!\w)" if re.match(r"\w", core) else ""
    trail = (TRAILING_SUFFIX + r"(?!\w)") if re.search(r"\w$", core) else ""
    return re.compile(lead + body + trail, re.IGNORECASE)


def find_term(term, sentence):
    """Where the card's term sits in the sentence, as (start, end).

    Tries the literal phrase first — which also covers multi-word fronts and
    the whole-phrase cards — then falls back to the affix-aware word match.
    Returns None when neither hits: the deck has a handful of fronts like
    "sama … dengan …" that span a gap no single run of text corresponds to.
    """
    variants = [v.strip() for v in term.split(" / ") if v.strip()]
    for v in variants:
        # A trailing "…" is just a placeholder for the rest of the sentence and
        # gets stripped; an interior one ("sama … dengan …") means the front
        # spans a gap, and no single run of text corresponds to it.
        if "…" in re.sub(r"[…?!.\s]+$", "", v):
            continue
        m = bounded(v).search(sentence)
        if m:
            return m.start(), m.end()
    targets = {v.lower() for v in variants if " " not in v}
    if targets:
        for m in WORD_RE.finditer(sentence):
            if possible_roots(m.group(0)) & targets:
                return m.start(), m.end()
    return None
