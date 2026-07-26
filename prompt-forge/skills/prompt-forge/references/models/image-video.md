---
family: Image + video generation
last_verified: never
confidence: UNVERIFIED
source: none — no first-party source reachable at file creation (2026-07-26)
---

# Image + video generation — UNVERIFIED

**Do not state facts from this file as verified.**

## Why this family needs its own pipeline treatment

Image and video prompts break several assumptions the text pipeline makes:

| Text prompts | Image/video prompts |
|---|---|
| Instructions are followed | Prompt is a **description**, not a command — "don't include a cat" often produces a cat |
| Negatives work as prohibitions | Negatives usually need a **separate negative-prompt field**, not inline prose |
| Success criteria can be checked mechanically | Success is visual; the criterion has to be describable in advance |
| Length helps precision | Beyond a model-specific limit, later tokens are simply ignored |
| One output | Batch + seed control matters; reproducibility depends on the seed |

**Step 4's success-criteria gate still applies** and is harder to satisfy here.
Push for it: subject, composition, lighting, style, aspect ratio, and what would
count as a failed render.

## What prompt-forge must do when targeting this family

1. Say plainly: *"I don't have verified facts on file for this generator."*
2. Ask which generator **and which version** — behaviour shifts sharply between
   versions of the same product.
3. Write the prompt as a **layered description**, not instructions:
   `subject → action/pose → environment → composition/framing → lighting → style/medium → technical (aspect ratio, quality)`
4. Put negatives in a clearly separated block so they can be moved into a
   negative-prompt field.
5. Do not invent parameter syntax (weights, `--flags`, seeds, aspect-ratio
   notation). Syntax is product-specific and changes between versions.

## Refresh

Per generator, fetch the provider's own prompting guide and API reference:

- [ ] Exact model/version identifiers
- [ ] Prompt length limit (in tokens or characters) and truncation behaviour
- [ ] Negative-prompt mechanism — separate field, inline syntax, or unsupported
- [ ] Weighting / emphasis syntax, if any
- [ ] Aspect-ratio and resolution parameters
- [ ] Seed / reproducibility controls
- [ ] Image-to-image and reference-image inputs, if supported
- [ ] Documented style keywords the model actually responds to
- [ ] Content-policy boundaries that cause silent rewrites or refusals

Then set `confidence: AUTHORITATIVE`, `last_verified:` to today, `source:` to the
URL fetched, and update `README.md` + `SKILL.md`.

Record the **version** in `family:` when refreshing — "Midjourney" without a
version is not a verified target.
