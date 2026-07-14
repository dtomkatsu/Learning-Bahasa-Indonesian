#!/usr/bin/env python3
"""
Regenerate index.html — a landing page linking to every *-player.html in the
project root. Run this after build_player.py adds a new conversation.

Usage:
    python3 build_index.py
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Learning Bahasa Indonesian</title>
<style>
  :root { color-scheme: light dark; --bg:#fff; --fg:#1a1a1a; --muted:#6b7280; --line:#e5e7eb; --accent:#2563eb; --card:#f9fafb; }
  @media (prefers-color-scheme: dark) {
    :root { --bg:#111318; --fg:#e7e9ee; --muted:#9aa1ac; --line:#2a2e37; --accent:#5b9dff; --card:#1a1d24; }
  }
  * { box-sizing:border-box; }
  html, body { margin:0; background:var(--bg); color:var(--fg);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }
  .wrap { max-width:640px; margin:0 auto; padding:48px 20px; }
  h1 { font-size:1.4rem; margin:0 0 4px; }
  p.sub { color:var(--muted); margin:0 0 28px; font-size:0.9rem; }
  a.card { display:block; padding:16px 18px; margin-bottom:12px; border-radius:10px;
    border:1px solid var(--line); background:var(--card); text-decoration:none; color:var(--fg); }
  a.card:hover { border-color:var(--accent); }
  a.card .name { font-weight:600; font-size:1rem; }
  a.card .meta { color:var(--muted); font-size:0.8rem; margin-top:3px; }
  .empty { color:var(--muted); font-size:0.9rem; }
</style>
</head>
<body>
<div class="wrap">
  <h1>Learning Bahasa Indonesian</h1>
  <p class="sub">Pick a conversation to listen and read along.</p>
  __ITEMS__
</div>
</body>
</html>
"""

ITEM = """<a class="card" href="{href}">
    <div class="name">{name}</div>
    <div class="meta">{href}</div>
  </a>"""


def main():
    players = sorted(ROOT.glob("*-player.html"))
    if players:
        items = "\n  ".join(
            ITEM.format(
                href=p.name,
                name=re.sub(r"-player\.html$", "", p.name).replace("-", " ").title(),
            )
            for p in players
        )
    else:
        items = '<p class="empty">No conversations yet — run build_player.py first.</p>'
    html = PAGE.replace("__ITEMS__", items)
    out = ROOT / "index.html"
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out} with {len(players)} conversation(s)")


if __name__ == "__main__":
    main()
