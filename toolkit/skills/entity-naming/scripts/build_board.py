#!/usr/bin/env python3
"""
build_board.py — render a scored board into a shareable finalist page.

WHY A PAGE AND NOT JUST THE MARKDOWN: picking an entity name is usually a group
decision among people who are not going to read a terminal or a repo. The board
gives them one link and the same ranked view you have, with the domain and
registry evidence attached to each name so the discussion argues about the right
things. The markdown shortlist is for you; this is for them.

Reads board.json from score_names.py and writes a self-contained index.html
(no external assets, no scripts, no network calls) plus a firebase.json ready
to deploy.

Usage:
  ./build_board.py --board board.json --out-dir ./name-board \
      --title "Holding Co — Finalist Board"

Then:  firebase deploy --only hosting
"""

import argparse
import html
import json
import os
import sys

BAND_LABEL = {
    "clean": "MCA clean",
    "watch": "MCA watch",
    "crowded": "MCA crowded",
    "block": "blocked",
}


def esc(s) -> str:
    return html.escape(str(s if s is not None else ""), quote=True)


def render_row(r: dict) -> str:
    band = r.get("band", "watch")
    pct = max(0, min(100, int(round(float(r.get("score", 0))))))
    dom = r.get("domains", {})
    dom_bits = " ".join(
        f'<span class="tick">.{esc(t)} {"✓" if v == "AVAILABLE" else "✗" if v == "REGISTERED" else "?"}</span>'
        for t, v in dom.items()
    )
    return f"""    <div class="row"><div class="rk">{esc(r.get('rank',''))}</div>
      <div class="nmwrap"><div class="n">{esc(r.get('name',''))}</div><div class="m">{esc(r.get('meaning',''))}</div>
        <div class="clist">{dom_bits}</div></div>
      <span class="genre">{esc(r.get('genre','—'))}</span>
      <div class="bandcol"><div class="meter"><div class="bar"><span style="width:{pct}%"></span></div><span class="score">{esc(r.get('score',''))}</span></div>
        <span class="band {esc(band)}"><span class="dot"></span>{esc(BAND_LABEL.get(band, band))}</span><div class="bandnote">{esc(r.get('registry_note',''))}</div></div></div>"""


EXTRA_CSS = """
  .board{margin-top:18px;border-top:1px solid var(--line)}
  .clist{margin-top:4px;display:flex;gap:6px;flex-wrap:wrap}
  .tick{font-family:var(--mono);font-size:11px;color:var(--muted);
        border:1px solid var(--line);border-radius:4px;padding:1px 5px}
  .band.crowded{background:var(--crowd-bg);color:var(--crowd)}
  .band.crowded .dot{background:var(--crowd)}
  .band.block{background:var(--block-bg);color:var(--block)}
  .band.block .dot{background:var(--block)}
  .rubric{font-family:var(--mono);font-size:11px;color:var(--faint);margin-top:26px;
          border-top:1px solid var(--line);padding-top:12px;line-height:1.7}
"""


def main() -> int:
    ap = argparse.ArgumentParser(description="Render a scored naming board to HTML.")
    ap.add_argument("--board", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--title")
    ap.add_argument("--site", default="entity-names", help="Firebase hosting site id")
    ap.add_argument("--css", help="Path to board.css (defaults to skill assets)")
    args = ap.parse_args()

    with open(args.board) as fh:
        board = json.load(fh)

    css_path = args.css or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "board.css"
    )
    try:
        with open(css_path) as fh:
            css = fh.read()
    except FileNotFoundError:
        print(f"warn: {css_path} not found, using minimal styling", file=sys.stderr)
        css = ":root{--ink:#1e2733;--muted:#5c6470}body{font-family:system-ui;margin:40px auto;max-width:860px}"

    rows = board.get("rows", [])
    title = args.title or board.get("title", "Entity Name Finalist Board")
    live = [r for r in rows if r.get("band") != "block"]
    rub = board.get("rubric", {})

    out_dir = args.out_dir
    pub = os.path.join(out_dir, "public")
    os.makedirs(pub, exist_ok=True)

    doc = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<style>{css}{EXTRA_CSS}</style>
</head><body><div class="wrap">
  <p class="section-label">Name clearance · {esc(board.get('generated_utc',''))}</p>
  <h1>{esc(title)}</h1>
  <p class="lead">{len(live)} of {len(rows)} candidates cleared. Ranked on a fixed rubric —
  domains are authoritative (RDAP); the registry band is a research signal, not a filing.</p>

  <div class="board">
{chr(10).join(render_row(r) for r in rows)}
  </div>

  <div class="legend">
    <span class="band clean"><span class="dot"></span>MCA clean</span> <span>— no exact match, few similar</span>
    <span class="band watch"><span class="dot"></span>MCA watch</span> <span>— no exact match, several similar names</span>
    <span class="band block"><span class="dot"></span>blocked</span> <span>— .com gone or exact register match</span>
  </div>

  <p class="rubric">Rubric weights — domain {rub.get('domain','?')} · registry {rub.get('registry','?')} ·
  length {rub.get('length','?')} · phonetic {rub.get('phonetic','?')} · brief fit {rub.get('brief_fit','?')}.
  Domain data checked {esc(board.get('clearance_checked_utc','n/a'))} and is a snapshot, not a reservation.
  The MCA register and IP India trademark register cannot be checked by machine — a CA RUN/SPICe+ filing
  is the only binding name check.</p>
</div></body></html>
"""

    with open(os.path.join(pub, "index.html"), "w") as fh:
        fh.write(doc)

    fb = {
        "hosting": {
            "site": args.site,
            "public": "public",
            "ignore": ["firebase.json", "**/.*", "**/node_modules/**"],
            "headers": [{
                "source": "**/*.@(js|css|html)",
                "headers": [{"key": "Cache-Control", "value": "no-cache, max-age=0, must-revalidate"}],
            }],
        }
    }
    with open(os.path.join(out_dir, "firebase.json"), "w") as fh:
        json.dump(fb, fh, indent=2)

    print(f"wrote {pub}/index.html ({len(rows)} rows, {len(live)} cleared)")
    print(f"wrote {out_dir}/firebase.json (site: {args.site})")
    print(f"preview: open {pub}/index.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
