"""Shared vocab-parsing JS, injected into flashcards.html and exercised
directly by tests/run_tests.py.

Lives in its own module for two reasons: the page templates are non-raw
Python strings, so every regex backslash inside them has to be doubled (an
easy thing to get wrong silently), and pure functions kept out of the page
body can be unit-tested under Node without a browser.

This file uses a raw string, so backslashes here are written exactly as they
appear in the emitted JavaScript.
"""

VOCAB_JS = r"""
// Parses the same "front – back" paste format used to build the vocab/*.tsv
// decks: blank-line-separated blocks, each optionally starting with a
// "(tag[,tag2])" line that applies to every entry in that block. Accepts
// en dash / em dash / hyphen as the separator, as long as it's space-padded
// (so hyphenated words like "kira-kira" inside a term are left alone).
function parseBulkVocab(text) {
  const entries = [];
  const blocks = text.split(/\n\s*\n/);
  for (const block of blocks) {
    const lines = block.split('\n').map(l => l.trim()).filter(Boolean);
    if (!lines.length) continue;
    let tags = ['custom'];
    let start = 0;
    const tagMatch = lines[0].match(/^\(([^)]+)\)$/);
    if (tagMatch) {
      tags = tagMatch[1].split(',').map(t => t.trim()).filter(Boolean);
      if (!tags.length) tags = ['custom'];
      start = 1;
    }
    for (let i = start; i < lines.length; i++) {
      const sep = lines[i].match(/\s[–—-]\s/);
      if (!sep) continue;
      const front = lines[i].slice(0, sep.index).trim();
      const back = lines[i].slice(sep.index + sep[0].length).trim();
      if (front && back) entries.push({ front, back, tags });
    }
  }
  return entries;
}
"""
