---
family: OpenAI (GPT-5.x, o-series)
last_verified: never
confidence: UNVERIFIED
source: none — no first-party source reachable at file creation (2026-07-26)
---

# OpenAI — UNVERIFIED

**Do not state facts from this file as verified.** It contains no model data
because none could be verified from a first-party source when it was created.

## What promptcarta must do when targeting this family

1. Say plainly: *"I don't have verified GPT-5.x facts on file — model-specific
   claims here are unverified."*
2. Offer the refresh procedure below.
3. Write the prompt using **only model-agnostic structure** — architecture,
   contract, success criteria, examples. These transfer.
4. Do **not** emit parameter-level guidance (reasoning-effort values, sampling
   params, structured-output syntax, token limits, prices). Those are exactly the
   fields that go stale silently.

## Known-transferable (architecture, not parameters)

These hold across model families and are safe to apply:

- A falsifiable success criterion beats an adjective
- Positive examples beat prohibition lists
- Explicit output contracts beat implied format
- 2–5 few-shot examples spanning real variance
- Trigger conditions belong in a tool's own description
- Contradictory instructions produce unpredictable resolution

## Refresh

Fetch `platform.openai.com` API reference directly and extract, per model:

- [ ] Exact model ID strings
- [ ] Context window + max output tokens
- [ ] Pricing per 1M input / output
- [ ] Reasoning-control parameter name and accepted values
- [ ] Which older parameters now error, and on which models
- [ ] Structured-output mechanism and schema limitations
- [ ] Documented behavioural quirks affecting prompt wording

Then set `confidence: AUTHORITATIVE`, `last_verified:` to today, `source:` to the
URL fetched, and update the inventory in `README.md` and `SKILL.md`.

A secondary source (blog, aggregator, model card summary) does **not** upgrade
this file's status.
