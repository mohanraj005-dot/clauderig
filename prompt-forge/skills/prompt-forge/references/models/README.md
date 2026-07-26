---
last_verified: 2026-07-26
---

# Model reference files — verification policy

## The contract

Every file in this directory carries frontmatter:

```yaml
family: <name>
last_verified: YYYY-MM-DD
confidence: AUTHORITATIVE | STALE | UNVERIFIED
source: <how it was verified — a named tool, skill, or doc URL>
```

`prompt-forge` reads these before writing a prompt and **quotes the date in its
output**. A file with no `last_verified` is treated as `UNVERIFIED`.

## Why this exists

Model APIs move faster than prompt-engineering habits. As of 2026-07-26, four
constructs that were standard advice now return **HTTP 400** on current Claude
models (prefill, `budget_tokens`, sampling params, top-level `output_format`).
Every prompt generator audited still emitted at least one of them.

A model fact recalled from memory is not a fact. It is a fact-shaped guess with
an unknown expiry date, and the failure is silent until a request 400s or a
prompt quietly underperforms.

## Status meanings

| Status | Means | prompt-forge behaviour |
|---|---|---|
| `AUTHORITATIVE` | Verified from a first-party source on `last_verified` | Use freely; quote the date |
| `STALE` | Was authoritative; date is old enough to distrust | Use, but flag the date and offer a refresh |
| `UNVERIFIED` | Not verified from a first-party source | **Say so in the output.** Offer the refresh. Never present as fact |

There is no "probably fine" tier. Either it was checked against a source, or it
was not.

## Current inventory

| File | Family | Status | Verified |
|---|---|---|---|
| `claude.md` | Claude 5 / 4.x | `AUTHORITATIVE` | 2026-07-26 |
| `openai.md` | GPT-5.x / o-series | `UNVERIFIED` | — |
| `gemini.md` | Gemini 3 | `UNVERIFIED` | — |
| `open-weights.md` | DeepSeek, Llama, Qwen, Mistral | `UNVERIFIED` | — |
| `image-video.md` | Image + video generation | `UNVERIFIED` | — |

Only Claude is authoritative because only Claude has a first-party,
locally-available source (the bundled `claude-api` skill). The rest are honestly
marked rather than plausibly filled — a fabricated GPT-5 parameter table would
reproduce the exact defect this skill was built to eliminate.

## Refresh procedure

### Claude

```
Invoke the `claude-api` skill. Read its Current Models table, the
Thinking & Effort quick reference, and shared/model-migration.md for the
target version. Rewrite claude.md from that; set last_verified to today.
```

Do **not** refresh `claude.md` from a web search summary or from memory. The
bundled skill is Anthropic-maintained and is the source of record here.

### Everything else

Requires live web access — `WebSearch` / `WebFetch`, or `ctx_fetch_and_index`.
For each family, fetch the **provider's own** API reference (not a blog post, not
an aggregator) and extract:

1. Exact model ID strings, context windows, max output
2. Current pricing per 1M input / output tokens
3. Reasoning-control parameters and their accepted values
4. **Which older parameters now error, and on which models** — this is the
   highest-value section and the one aggregators consistently get wrong
5. Structured-output mechanism
6. Documented behavioural quirks that change prompt wording

Then set `confidence: AUTHORITATIVE`, `last_verified:` to today, and `source:` to
the URL actually fetched.

**A refresh that cannot reach the provider's docs is not a refresh.** Leave the
file `UNVERIFIED` rather than upgrading its status from a secondary source.

## Adding a family

Copy the frontmatter block, start at `confidence: UNVERIFIED`, add a row to the
inventory above and to the table in `SKILL.md`, then run the refresh.
