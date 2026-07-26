---
name: entity-naming
description: >-
  Naming pipeline for Indian companies, LLPs, brands and outlets — brief intake,
  genre-diverse generation, authoritative RDAP domain clearance (.com/.in/.co.in/.net),
  a parallel MCA/trademark registry-proxy fan-out, a fixed scoring rubric, a ranked
  shortlist, and a shareable ranked finalist board. Use whenever
  someone needs to find, shortlist, clear, score or decide a name for a company,
  LLP, holding entity, brand, outlet, restaurant, cafe, gym or venture — including
  when they only say "I need a name for X", "help me name my company", "is this
  name available", "check if X.com is free", "shortlist some names", "our name is
  taken, find alternatives", "what should we call it", "MCA name availability",
  "is this trademark free", "brand name ideas", or paste candidate names asking
  which are clear. Also re-scores prior rounds. Do NOT use for
  naming code artifacts (variables, files, repos), for UK/Companies House naming,
  or for brand positioning with no name-selection component — that is emily.
---

# Entity naming (India)

You are running a naming round that has to end in a decision, not a list. The
output that matters is: a founder picks a name, buys the domains, and hands one
name to a CA. Everything in this skill exists to get to that point without the
two failure modes that actually kill naming rounds — falling in love with a name
whose .com is gone, and producing forty names in one style that the founder
rejects wholesale.

## The pipeline

```
1. Brief intake      → naming-brief.md
2. Generate          → candidates.txt   (40-50, spread across genres)
3. Clear domains     → clearance.json   (authoritative, RDAP)
4. Registry fan-out  → registry.json    (parallel agents, banded)
5. Score             → board.json + shortlist.md
6. Board             → index.html + firebase.json
7. Hand off          → founder buys domains, CA files RUN/SPICe+
```

Steps 3 and 4 are the only slow ones and they are independent — run them
concurrently rather than in sequence.

## Step 1 — Lock the brief

Read `references/brief-intake.md` and ask its eight questions **in one batched
round**, not one at a time. Write the answers to `naming-brief.md`.

The one question people skip and shouldn't: *"Is there a name you already love,
even if it's taken?"* A rejected favourite is the single best signal of taste you
will get, and it seeds the rescue lane in step 2.

Tell the founder up front that wave one is a probe. Naming rounds almost always
need two passes, and framing that as the process rather than a setback keeps the
second wave from feeling like failure.

## Step 2 — Generate across genres

Read `references/genre-playbook.md`. Generate **40-50 candidates spread over at
least four genres** — Sanskrit-adjacent coined, coined abstract, Anglo estate,
Sanskrit trio, blended founder. Concentrating in one genre means one taste
rejection kills the whole wave.

Two rules the playbook explains and that decide most rounds:

- **Never generate 4-5 character names.** Every short .com is registered. Those
  candidates are dead before you check them.
- **Aim for 7-8 characters.** Long enough to clear .com, short enough to work on
  signage and as a handle.

Always include a **rescue lane**: 3-5 names deliberately built to sit next to
whatever the founder said they loved but couldn't have. Those consistently
survive to the final round because they're anchored to demonstrated taste rather
than inference.

Write one candidate per line to `candidates.txt`.

Also write `meta.json` — genre, meaning, and your brief-fit rating 0-5 per name,
keyed by lowercase slug:

```json
{
  "ozarva":   {"display": "Ozarva", "genre": "Coined · abstract", "meaning": "Brisk, modern, abstract", "brief_fit": 4},
  "trisendra":{"display": "Trisendra", "genre": "Sanskrit · trio", "meaning": "Tri (3) + ascend — triple ascent", "brief_fit": 3}
}
```

Rate `brief_fit` honestly against `naming-brief.md`. It is capped at 15% of the
total score, so it can break a tie between cleared names but can never rescue one
whose .com is gone — which is the specific failure the old hand-scored board
allowed.

## Step 3 — Clear domains

```bash
scripts/clear_names.sh --json --file candidates.txt > clearance.json
```

This is the only authoritative check in the whole pipeline. RDAP returns 404 for
free and 200 for taken; the script retries on 429 because a rate-limit answer
misread as "available" is the most expensive mistake available here.

Run it in the background while step 4 runs — 50 names across 4 TLDs is 200
lookups.

## Step 4 — Registry-proxy fan-out (parallel)

The MCA register and IP India trademark register **cannot be queried by machine** —
Akamai bot protection, Cloudflare challenges, CAPTCHAs and logins. All of it was
attempted directly and blocked. Don't spend the session rediscovering that.

Instead, approximate it. Read `references/india-registries.md` for the exact
search set and banding rules, then **dispatch one agent per 5-8 candidates**, each
returning JSON only. Merge into `registry.json`.

Band as `clean` / `watch` / `crowded` / `blocked` using the table in that
reference, applied literally rather than by feel — consistent banding is what
makes two naming rounds comparable.

## Step 5 — Score

```bash
scripts/score_names.py --clearance clearance.json --meta meta.json \
    --registry registry.json --out-json board.json --out-md shortlist.md
```

Fixed rubric, weights in one place at the top of the script:

| Dimension | Weight | Why it carries that much |
|---|---|---|
| Domain availability | 35 | Authoritative and irreversible — a taken .com can't be negotiated |
| Registry collision | 20 | Kills the name at filing, after you've paid for domains |
| Length | 15 | Empirical: 7-8 chars clears .com and still reads as one word |
| Phonetic clarity | 15 | Can a customer hear it once and spell it into a search bar |
| Brief fit | 15 | Taste breaks ties; it must not override clearance |

A taken `.com` or a `blocked` registry verdict caps the band at `block` no matter
what the composite score is.

The reason this is a script and not a judgement call: the first time this pipeline
ran, the scores were typed by hand, so a 63 in one round and a 63 in another
measured different things. If you disagree with a weight, change it once in the
script and every past round can be re-scored on the new basis.

## Step 6 — Build the board

```bash
scripts/build_board.py --board board.json --out-dir ./name-board \
    --title "Holding Co — Finalist Board" --site my-entity-names
```

Produces a self-contained `index.html` — no external requests, no scripts — plus
a `firebase.json` ready for `firebase deploy --only hosting`.

The board exists because naming is usually a group decision among people who
won't read a terminal or a repo. They get one link and the same ranked view you
have, with the domain and registry evidence attached to each name so the
discussion argues about the right things. The markdown shortlist is for you; the
board is for them.

## Step 7 — Hand off honestly

Close every round with what is *not* settled. The order matters:

1. **Buy .com + .in for the top 2-3 — today.** Clearance is a snapshot, not a
   reservation. This takes minutes; the CA filing takes days. Do it first.
2. **Hand the #1 to the CA for RUN/SPICe+.** That filing is the only binding MCA
   check that exists.
3. **Run the IP India trademark search** on Wordmark + Phonetic in the trading
   classes (43 F&B · 35 retail · 41 fitness · 44 wellness).

State plainly which names came back `clean` and which came back `watch`. A `watch`
is not a pass. In the round that produced Ozarva the winning name was banded
`watch` and there's no record the binding check was ever done — surfacing that
gap is more useful than a board that looks decisive.

## Files

| Path | Purpose |
|---|---|
| `scripts/clear_names.sh` | RDAP domain clearance, human or `--json` output |
| `scripts/score_names.py` | Fixed-rubric scoring → `board.json` + `shortlist.md` |
| `scripts/build_board.py` | `board.json` → hosted ranked finalist board |
| `references/brief-intake.md` | The eight intake questions and why each one matters |
| `references/genre-playbook.md` | Genres, length economics, the rescue lane |
| `references/india-registries.md` | What's checkable, the fan-out spec, banding rules |
| `assets/board.css` | Board styling |

## Quick paths

**"Is this one name available?"** — skip the pipeline:

```bash
scripts/clear_names.sh ozarva
```

**"Re-score last round with a different weighting"** — edit the weights at the top
of `score_names.py` and re-run step 5 against the existing `clearance.json`. No
need to re-check domains unless the data is more than a few weeks old.
