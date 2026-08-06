"""Shared mobile-height measures, used by every page that shows cards.

Both pieces here exist for the same measured reason: on a 375x812 phone the
rate buttons were unreachable without scrolling on every flashcard sampled
(0/60), and the card itself was never the problem — a few hundred pixels of
explanatory text sat between it and the buttons.

TIPS_CSS / TIPS_JS
    Static explainers collapse to a single line, expanded state remembered as
    a preference across cards and sessions. Built on <details>/<summary> so
    keyboard and screen-reader behaviour come for free. Any page can opt in by
    marking an element `<details class="tip" data-tip="<key>">`; the key is
    what the open/closed state is stored under, so the same tip stays in sync
    across pages.

STICKY_RATE_CSS
    Pins the rating row to the bottom of the viewport on narrow screens. The
    collapsing alone left a median flashcard at ~927px against an 812px
    viewport, and any future addition would have pushed it over again — this
    decouples "can I rate this" from "how long is this card".

Raw strings, so regex/CSS backslashes are written once rather than doubled for
the non-raw page templates.
"""

TIPS_CSS = r"""
  details.tip { max-width:460px; margin:0 auto 16px; border-radius:8px;
    background:var(--card); border:1px solid var(--line); color:var(--muted);
    font-size:0.78rem; line-height:1.5; text-align:left; }
  details.tip[hidden] { display:none; }
  details.tip > summary { list-style:none; cursor:pointer; padding:7px 12px;
    font-size:0.64rem; letter-spacing:0.06em; text-transform:uppercase; opacity:0.75;
    display:flex; justify-content:space-between; align-items:center; gap:8px; }
  details.tip > summary::-webkit-details-marker { display:none; }
  details.tip > summary::after { content:'\25BE'; font-size:0.7rem; }
  details.tip[open] > summary::after { content:'\25B4'; }
  details.tip > summary:hover { opacity:1; }
  details.tip .tipBody { padding:0 12px 10px; }
  details.tip b { color:var(--accent); }
"""

STICKY_RATE_CSS = r"""
  @media (max-width: 640px) {
    .rate { position:sticky; bottom:0; z-index:5; background:var(--bg);
      padding:8px 0 calc(8px + env(safe-area-inset-bottom, 0px)); margin-bottom:-8px; }
    .rate::before { content:''; position:absolute; left:0; right:0; top:-12px;
      height:12px; pointer-events:none;
      background:linear-gradient(to top, var(--bg), transparent); }
  }
"""

TIPS_JS = r"""
// Expanded state is a preference, not per-card: open a tip once and it stays
// open as you move through the deck, and across pages that use the same key.
//
// Deliberately self-contained rather than reusing srsLoad/srsSave — the
// conversation players embed the sync module but not the SRS one, and a tip
// that only works on pages carrying the whole scheduler would be a trap.
const TIPS_KEY = 'bahasa:tipsOpen:v1';
function tipsLoad() {
  try { return JSON.parse(localStorage.getItem(TIPS_KEY)) || {}; } catch (e) { return {}; }
}
function tipsSave(state) {
  try { localStorage.setItem(TIPS_KEY, JSON.stringify(state)); } catch (e) {}
}
function wireTips(root) {
  (root || document).querySelectorAll('details.tip[data-tip]').forEach(d => {
    if (d.dataset.tipWired) return;
    d.dataset.tipWired = '1';
    const key = d.dataset.tip;
    d.open = !!tipsLoad()[key];
    d.addEventListener('toggle', () => {
      const state = tipsLoad();
      state[key] = d.open;
      tipsSave(state);
    });
  });
}
wireTips();
"""
