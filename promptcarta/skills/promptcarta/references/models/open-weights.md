---
family: Open-weights (DeepSeek, Llama, Qwen, Mistral)
last_verified: never
confidence: UNVERIFIED
source: none — no first-party source reachable at file creation (2026-07-26)
---

# Open-weights models — UNVERIFIED

**Do not state facts from this file as verified.**

## Why this family is different

Open-weights models are the case where "which model" is not enough information.
The same weights behave differently depending on:

| Variable | Why it matters to the prompt |
|---|---|
| **Serving stack** | vLLM / Ollama / llama.cpp / a hosted API differ in defaults and in which sampling params they accept |
| **Quantisation** | Aggressive quant degrades instruction-following before it degrades fluency — a prompt that works at fp16 can fail at q4 |
| **Chat template** | Wrong template = silently worse output, no error. This is the single most common failure |
| **Context length as served** | Often configured well below the model's advertised maximum |
| **Sampling defaults** | Unlike current Claude, these models *do* take `temperature`/`top_p`, and the serving default is frequently not what the model card recommends |

So step 1 must resolve **model + serving stack + quantisation**, not just a name.
If the user names only the model, ask — this is a legitimate use of a step 5 question.

## What promptcarta must do when targeting this family

1. Say plainly: *"I don't have verified facts on file for this family."*
2. Ask for the serving stack and quantisation if not stated.
3. Write with **model-agnostic structure only**.
4. Flag the chat-template risk explicitly — it is the highest-probability cause
   of "the prompt doesn't work" and it produces no error message.

## Refresh

Per model, fetch the **official model card** (Hugging Face repo card or the
provider's own docs) and extract:

- [ ] Exact chat template, verbatim
- [ ] Recommended sampling parameters from the model card (not the serving default)
- [ ] Advertised context length, and whether long-context is a separate variant
- [ ] Whether a reasoning/thinking mode exists and how it is invoked
- [ ] Structured-output support (usually grammar/JSON-mode at the serving layer, not the model)
- [ ] System-prompt handling — several families handle it non-obviously
- [ ] Known instruction-following degradation at common quant levels

Then set `confidence: AUTHORITATIVE`, `last_verified:` to today, `source:` to the
URL fetched, and update `README.md` + `SKILL.md`.

Because this file spans several families, a partial refresh should record which
models are covered — a blanket `AUTHORITATIVE` on a file that only verified
DeepSeek would be misleading for Llama.
