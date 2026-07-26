---
family: Google Gemini 3
last_verified: never
confidence: UNVERIFIED
source: none — no first-party source reachable at file creation (2026-07-26)
---

# Gemini — UNVERIFIED

**Do not state facts from this file as verified.** No model data, because none
could be verified from a first-party source when it was created.

## What prompt-forge must do when targeting this family

1. Say plainly: *"I don't have verified Gemini 3 facts on file — model-specific
   claims here are unverified."*
2. Offer the refresh procedure below.
3. Write with **model-agnostic structure only** (see `openai.md` →
   Known-transferable).
4. Emit no parameter-level guidance: no thinking-config syntax, no safety-setting
   values, no token limits, no prices.

## Refresh

Fetch `ai.google.dev` / Vertex AI Gemini API reference directly and extract:

- [ ] Exact model ID strings (and the Vertex vs AI Studio ID difference)
- [ ] Context window + max output tokens
- [ ] Pricing per 1M input / output
- [ ] Thinking / reasoning parameter name and accepted values
- [ ] Which older parameters now error
- [ ] Structured-output mechanism and schema limitations
- [ ] System-instruction handling (differs from Claude's `system` field)
- [ ] Multimodal input limits, if relevant to the prompt
- [ ] Documented behavioural quirks affecting prompt wording

Then set `confidence: AUTHORITATIVE`, `last_verified:` to today, `source:` to the
URL fetched, and update `README.md` + `SKILL.md`.

Note: Gemini is served via both AI Studio and Vertex AI with differing IDs and
feature availability. A refresh that covers only one is incomplete — say which.
