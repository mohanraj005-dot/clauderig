#!/usr/bin/env python3
"""
score_names.py — turn raw clearance data into a consistently-scored shortlist.

WHY THIS EXISTS: the first time this pipeline ran, the finalist scores were typed
by hand. That is fine once, but it means two naming rounds are never comparable —
a 63 in round one and a 63 in round two measured different things, so you cannot
tell whether round two actually produced better candidates. This script applies
one fixed rubric so scores mean the same thing across every round and every
entity you ever name.

The rubric is deliberately transparent rather than clever. Every sub-score is
printable and arguable; if you disagree with a weight, change it here once and
every past round can be re-scored on the new basis.

Inputs:
  --clearance FILE   JSON from clear_names.sh --json  (required)
  --meta FILE        JSON: per-name genre, etymology, brief_fit 0-5   (optional)
  --registry FILE    JSON: per-name registry-proxy verdict            (optional)

Outputs:
  --out-json FILE    Scored board data, consumed by build_board.py
  --out-md FILE      Human-readable ranked shortlist

Usage:
  ./score_names.py --clearance clearance.json --meta meta.json \
                   --registry registry.json \
                   --out-json board.json --out-md shortlist.md
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone

VOWELS = set("aeiou")

# ---- Weights -----------------------------------------------------------------
# These sum to 100. Domain weight dominates because it is the only dimension that
# is both authoritative and irreversible: a taken .com cannot be negotiated, while
# a mediocre phonetic score can be lived with. Registry risk is second because an
# MCA collision kills the name at filing time, after you have already paid for
# domains. The craft dimensions matter but they are recoverable.
W_DOMAIN = 35
W_REGISTRY = 20
W_LENGTH = 15
W_PHONETIC = 15
W_BRIEF = 15

# Per-TLD share of the domain score. .com carries most of it because it is the
# default a customer types and the hardest to acquire; .in matters for an Indian
# entity but is far easier to secure, so it cannot carry equal weight.
TLD_WEIGHTS = {"com": 0.55, "in": 0.30, "co.in": 0.10, "net": 0.05}

REGISTRY_BANDS = {
    "clean": (100, "no exact match, few similar"),
    "watch": (65, "no exact match, several similar names"),
    "crowded": (30, "many similar names in register"),
    "blocked": (0, "exact or near-exact match exists"),
    "unchecked": (50, "registry proxy not run"),
}


def score_domains(domains: dict) -> tuple[float, str]:
    """Weighted availability across TLDs.

    A rate-limited or unknown lookup scores as half rather than zero: treating an
    unresolved lookup as a failure would silently bury good candidates behind a
    transient network problem, which is worse than flagging it for a re-run.
    """
    total = 0.0
    weight_seen = 0.0
    notes = []
    for tld, status in domains.items():
        w = TLD_WEIGHTS.get(tld, 0.05)
        weight_seen += w
        if status == "AVAILABLE":
            total += w
        elif status == "REGISTERED":
            notes.append(f".{tld} taken")
        else:
            total += w * 0.5
            notes.append(f".{tld} unresolved")
    if weight_seen == 0:
        return 0.0, "no domain data"
    return (total / weight_seen) * 100, ", ".join(notes) or "all clear"


def score_length(slug: str) -> tuple[float, str]:
    """Peak at 7-8 characters.

    This is an empirical finding, not an aesthetic preference: in the round that
    produced Ozarva, every 4-5 letter candidate failed .com (those are essentially
    all registered), while 7-8 letter coined words cleared reliably and still read
    as one word. Below 6 you are fighting the domain market; above 10 the name
    stops fitting signage and handles.
    """
    n = len(slug)
    if 7 <= n <= 8:
        return 100.0, "ideal length"
    if n in (6, 9):
        return 85.0, "good length"
    if n == 10:
        return 65.0, "slightly long"
    if n == 5:
        return 45.0, "short — .com likely taken"
    if n <= 4:
        return 20.0, "very short — .com almost certainly taken"
    return max(20.0, 100.0 - (n - 8) * 12), "long"


def score_phonetic(slug: str) -> tuple[float, str]:
    """Reward names that survive being said out loud over a phone line.

    The test that matters for a real business is whether a customer can hear the
    name once and then spell it into a search bar. Consonant pile-ups and doubled
    letters are where that breaks down, so those are penalised; clean
    consonant-vowel alternation is rewarded.
    """
    s = slug.lower()
    score = 100.0
    notes = []

    syllables = len(re.findall(r"[aeiou]+", s))
    if syllables == 0:
        return 10.0, "unpronounceable — no vowels"
    if syllables > 4:
        score -= (syllables - 4) * 12
        notes.append(f"{syllables} syllables")
    elif syllables < 2:
        score -= 15
        notes.append("single syllable")

    # Penalty scales with cluster length, not just cluster count: a six-consonant
    # pile-up is not merely "one problem", it is unsayable, and a flat per-cluster
    # penalty would score it the same as a mild three-consonant run.
    clusters = re.findall(r"[^aeiou]{3,}", s)
    for c in clusters:
        score -= 15 + (len(c) - 3) * 12
    if clusters:
        notes.append("consonant cluster: " + ",".join(clusters))

    if re.search(r"(.)\1", s):
        score -= 8
        notes.append("doubled letter")

    # Spelling traps: these are letter pairs an Indian English speaker can hear
    # correctly but still spell three different ways.
    for trap in ("ph", "gh", "kn", "wr", "ck"):
        if trap in s:
            score -= 6
            notes.append(f"ambiguous '{trap}'")

    # A vowel ending reads as a name rather than an abbreviation, and it is the
    # pattern the brief has consistently favoured.
    if s[-1] in VOWELS:
        score += 5
        notes.append("vowel ending")

    alternations = sum(
        1 for i in range(len(s) - 1)
        if (s[i] in VOWELS) != (s[i + 1] in VOWELS)
    )
    if len(s) > 1 and alternations / (len(s) - 1) > 0.7:
        score += 5
        notes.append("clean rhythm")

    return max(0.0, min(100.0, score)), "; ".join(notes) or "clean"


def score_registry(verdict: str) -> tuple[float, str]:
    band = (verdict or "unchecked").lower()
    val, note = REGISTRY_BANDS.get(band, REGISTRY_BANDS["unchecked"])
    return float(val), note


def score_brief(fit) -> tuple[float, str]:
    """Brief fit is the one human input, on a 0-5 scale.

    It is capped at 15% of the total on purpose. Taste should be able to break a
    tie between two cleared names, but it should never be able to promote a name
    whose .com is gone — that was the failure mode the hand-scored board allowed.
    """
    if fit is None:
        return 50.0, "not rated"
    try:
        f = max(0.0, min(5.0, float(fit)))
    except (TypeError, ValueError):
        return 50.0, "not rated"
    return (f / 5.0) * 100, f"brief fit {f}/5"


def band_for(total: float, domains: dict, registry: str) -> str:
    """Headline verdict, capped by the worst individual signal.

    The band is what people read off the board; the number is what they ignore. So
    the band must never be more optimistic than the weakest underlying check. A
    strong composite can hide a mediocre registry result — that is precisely how
    the previous round showed its winner as acceptable while its registry verdict
    was only 'watch' and never escalated. Here the registry verdict is a ceiling,
    not just another weighted input.
    """
    reg = (registry or "unchecked").lower()
    if reg == "blocked" or domains.get("com") == "REGISTERED":
        return "block"

    if total >= 78:
        band = "clean"
    elif total >= 60:
        band = "watch"
    else:
        band = "crowded"

    ceiling = {"clean": "clean", "watch": "watch", "crowded": "crowded",
               "unchecked": "watch"}.get(reg, "watch")
    order = ["block", "crowded", "watch", "clean"]
    return band if order.index(band) <= order.index(ceiling) else ceiling


def main() -> int:
    ap = argparse.ArgumentParser(description="Score naming candidates on a fixed rubric.")
    ap.add_argument("--clearance", required=True)
    ap.add_argument("--meta")
    ap.add_argument("--registry")
    ap.add_argument("--out-json")
    ap.add_argument("--out-md")
    ap.add_argument("--title", default="Entity Name Finalist Board")
    args = ap.parse_args()

    with open(args.clearance) as fh:
        clearance = json.load(fh)

    meta = {}
    if args.meta:
        with open(args.meta) as fh:
            meta = {k.lower(): v for k, v in json.load(fh).items()}

    registry = {}
    if args.registry:
        with open(args.registry) as fh:
            registry = {k.lower(): v for k, v in json.load(fh).items()}

    rows = []
    for cand in clearance.get("candidates", []):
        slug = cand["slug"]
        m = meta.get(slug, {})
        reg = registry.get(slug, {})
        reg_verdict = reg.get("verdict", "unchecked") if isinstance(reg, dict) else str(reg)

        d_score, d_note = score_domains(cand.get("domains", {}))
        l_score, l_note = score_length(slug)
        p_score, p_note = score_phonetic(slug)
        r_score, r_note = score_registry(reg_verdict)
        b_score, b_note = score_brief(m.get("brief_fit"))

        total = (
            d_score * W_DOMAIN
            + r_score * W_REGISTRY
            + l_score * W_LENGTH
            + p_score * W_PHONETIC
            + b_score * W_BRIEF
        ) / 100.0

        rows.append({
            "name": m.get("display") or cand["input"].title(),
            "slug": slug,
            "genre": m.get("genre", "—"),
            "meaning": m.get("meaning", ""),
            "score": round(total, 1),
            "band": band_for(total, cand.get("domains", {}), reg_verdict),
            "registry_verdict": reg_verdict,
            "registry_note": r_note,
            "domains": cand.get("domains", {}),
            "links": cand.get("manual_checks", {}),
            "subscores": {
                "domain": {"score": round(d_score, 1), "weight": W_DOMAIN, "note": d_note},
                "registry": {"score": round(r_score, 1), "weight": W_REGISTRY, "note": r_note},
                "length": {"score": round(l_score, 1), "weight": W_LENGTH, "note": l_note},
                "phonetic": {"score": round(p_score, 1), "weight": W_PHONETIC, "note": p_note},
                "brief": {"score": round(b_score, 1), "weight": W_BRIEF, "note": b_note},
            },
        })

    rows.sort(key=lambda r: r["score"], reverse=True)
    for i, r in enumerate(rows, 1):
        r["rank"] = i

    board = {
        "title": args.title,
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "clearance_checked_utc": clearance.get("checked_utc"),
        "rubric": {
            "domain": W_DOMAIN, "registry": W_REGISTRY, "length": W_LENGTH,
            "phonetic": W_PHONETIC, "brief_fit": W_BRIEF,
        },
        "rows": rows,
    }

    if args.out_json:
        with open(args.out_json, "w") as fh:
            json.dump(board, fh, indent=2)
        print(f"wrote {args.out_json}", file=sys.stderr)

    if args.out_md:
        with open(args.out_md, "w") as fh:
            fh.write(render_markdown(board))
        print(f"wrote {args.out_md}", file=sys.stderr)

    if not args.out_json and not args.out_md:
        print(json.dumps(board, indent=2))

    return 0


BAND_MARK = {"clean": "✅ clean", "watch": "⚠ watch", "crowded": "🟠 crowded", "block": "🔴 blocked"}


def render_markdown(board: dict) -> str:
    rows = board["rows"]
    live = [r for r in rows if r["band"] != "block"]
    dead = [r for r in rows if r["band"] == "block"]
    tlds = list(rows[0]["domains"].keys()) if rows else []

    out = [f"# {board['title']}", ""]
    top = ", ".join(f"**{r['name']}** ({r['score']})" for r in live[:3]) or "none cleared"
    out += [
        "> **At a glance:**",
        f"> - **{len(live)} of {len(rows)}** candidates survived clearance.",
        f"> - Leaders: {top}",
        "> - Domains are **authoritative**; MCA and trademark are **not** — a CA RUN/SPICe+ filing is the only binding name check.",
        "",
        f"Scored on a fixed rubric — domain {board['rubric']['domain']} · registry {board['rubric']['registry']} · "
        f"length {board['rubric']['length']} · phonetic {board['rubric']['phonetic']} · brief fit {board['rubric']['brief_fit']}. "
        f"Clearance run {board.get('clearance_checked_utc', 'n/a')}.",
        "",
        "## Cleared candidates",
        "",
    ]

    header = "| # | Name | Score | Verdict | " + " | ".join(f".{t}" for t in tlds) + " | Genre |"
    sep = "|---|---|---|---|" + "---|" * len(tlds) + "---|"
    out += [header, sep]
    for r in live:
        cells = "|".join(
            " ✅ " if r["domains"].get(t) == "AVAILABLE"
            else " ❌ " if r["domains"].get(t) == "REGISTERED" else " ? "
            for t in tlds
        )
        out.append(f"| {r['rank']} | **{r['name']}** | {r['score']} | {BAND_MARK[r['band']]} |{cells}| {r['genre']} |")

    if dead:
        out += ["", "## Eliminated", "", "| Name | Score | Why |", "|---|---|---|"]
        for r in dead:
            why = "exact registry match" if r["registry_verdict"] == "blocked" else ".com unavailable"
            out.append(f"| {r['name']} | {r['score']} | {why} |")

    out += ["", "## Score breakdown", "", "| Name | Domain | Registry | Length | Phonetic | Brief | Total |", "|---|---|---|---|---|---|---|"]
    for r in live:
        s = r["subscores"]
        out.append(
            f"| {r['name']} | {s['domain']['score']} | {s['registry']['score']} | {s['length']['score']} | "
            f"{s['phonetic']['score']} | {s['brief']['score']} | **{r['score']}** |"
        )

    out += [
        "", "## Still on you", "",
        "| Step | Why it cannot be automated |",
        "|---|---|",
        "| MCA RUN/SPICe+ filing | Register sits behind Akamai bot protection and a login — the filing itself is the only binding check |",
        "| IP India trademark search | CAPTCHA-gated; run Wordmark + Phonetic in the classes you will trade in |",
        "| Buy domains for the top 2-3 | Availability above is a snapshot, not a reservation |",
        "",
    ]
    return "\n".join(out)


if __name__ == "__main__":
    sys.exit(main())
