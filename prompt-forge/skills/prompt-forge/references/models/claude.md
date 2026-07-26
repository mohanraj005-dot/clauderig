---
family: Claude
last_verified: 2026-07-26
confidence: AUTHORITATIVE
source: bundled `claude-api` skill (Anthropic-maintained), read in full 2026-07-26
---

# Claude — prompt-forge model facts

**Refresh by invoking the `claude-api` skill and re-reading its Current Models,
Thinking & Effort, and model-migration sections.** Do not refresh this file from
memory or from a web search summary.

## Model IDs (use these exact strings — never append a date suffix)

| Model | ID | Context | Max output | $/1M in | $/1M out |
|---|---|---|---|---|---|
| Claude Fable 5 | `claude-fable-5` | 1M | 128K | 10.00 | 50.00 |
| Claude Mythos 5 | `claude-mythos-5` | 1M | 128K | 10.00 | 50.00 |
| **Claude Opus 5** | `claude-opus-5` | 1M | 128K | 5.00 | 25.00 |
| Claude Opus 4.8 | `claude-opus-4-8` | 1M | 128K | 5.00 | 25.00 |
| Claude Opus 4.7 | `claude-opus-4-7` | 1M | 128K | 5.00 | 25.00 |
| Claude Opus 4.6 | `claude-opus-4-6` | 1M | 128K | 5.00 | 25.00 |
| Claude Sonnet 5 | `claude-sonnet-5` | 1M | 128K | 3.00 | 15.00 |
| Claude Sonnet 4.6 | `claude-sonnet-4-6` | 1M | 128K | 3.00 | 15.00 |
| Claude Haiku 4.5 | `claude-haiku-4-5` | 200K | 64K | 1.00 | 5.00 |

- Sonnet 5 has an **introductory** rate of $2.00 / $10.00 through **2026-08-31**.
- Mythos 5 is Project Glasswing only — same capabilities and price as Fable 5.
- Default to `claude-opus-5` unless the user names another model.
- Bedrock IDs take an `anthropic.` prefix (`anthropic.claude-opus-5`). Claude
  Platform on AWS uses the **bare** first-party ID — no prefix.

## Dead constructs — these return HTTP 400

| Construct | Errors on | Replacement |
|---|---|---|
| Assistant-turn prefill | Fable 5, Opus 5, 4.8, 4.7, 4.6, Sonnet 5, Sonnet 4.6 | `output_config.format` (structured outputs), or a system-prompt instruction |
| `thinking: {type:"enabled", budget_tokens:N}` | Fable 5, Opus 5, 4.8, 4.7, Sonnet 5 (deprecated on 4.6) | `thinking: {type:"adaptive"}` + `output_config.effort` |
| `temperature` / `top_p` / `top_k` | Fable 5, Opus 5, Opus 4.8, Opus 4.7 (non-default rejected on Sonnet 5) | Prompt for the behaviour |
| `thinking: {type:"disabled"}` at effort `xhigh`/`max` | Opus 5 | Enable thinking, or drop effort to `high` or lower |
| Any explicit `thinking` config | Fable 5 (`disabled` **and** `enabled` both 400) | Omit the parameter entirely |
| `output_format` (top-level) | Deprecated API-wide | `output_config.format` |
| `text_editor_20250124` + `str_replace_editor` | Claude 4+ | `text_editor_20250728` + `str_replace_based_edit_tool` (**both** fields change) |

**Prompt-writing consequence:** never write prompt guidance that says "set
temperature to 0" or "prefill the response with `{`" for a current Claude model.
Both are request failures, not stylistic weaknesses.

## Thinking

| Model | Omitting `thinking` | Notes |
|---|---|---|
| Fable 5 / Mythos 5 | Runs adaptive — always on | Any explicit config 400s |
| **Opus 5** | Runs **adaptive** | Changed from 4.8/4.7. `disabled` allowed only at effort ≤ `high` |
| Opus 4.8 / 4.7 | Runs **without** thinking | Must set `{type:"adaptive"}` explicitly |
| Sonnet 5 | Runs adaptive | Changed from 4.6 (which ran thinking-off) |
| Opus 4.6 / Sonnet 4.6 | No thinking | Set `{type:"adaptive"}` explicitly |

- `display` defaults to `"omitted"` on Fable 5 / Mythos 5 / Opus 5 / 4.8 / 4.7 /
  Sonnet 5 — thinking blocks stream with **empty text**. Set
  `{type:"adaptive", display:"summarized"}` to surface reasoning to users.
- Raw chain of thought is **never** returned on Fable 5 / Mythos 5 / Opus 5.
- `max_tokens` caps thinking **plus** response text. A route that previously ran
  thinking-off and sized `max_tokens` tightly can now truncate mid-answer.

## Effort (`output_config.effort`, not top-level)

Levels: `low` · `medium` · `high` · `xhigh` · `max`. Default `high`.

| Model | Starting point |
|---|---|
| Opus 5 | `xhigh` for coding/agentic, `high` otherwise — **then sweep down**; `low`/`medium` are unusually strong here |
| Opus 4.8 | `high` default, sweep `medium`/`high`/`xhigh` per route |
| Opus 4.7 | `xhigh` for coding/agentic; minimum `high` for intelligence-sensitive |
| Sonnet 5 | `high` default; `xhigh` for the hardest coding/agentic |

At `xhigh`/`max`, set `max_tokens` ≥ 64K or output truncates.

**Effort is not a verbosity lever on Opus 5** — lowering it moves thinking volume
without reliably shortening visible output. Prompt for conciseness instead.

## Behavioural facts that change prompt wording

Per-model, all verified 2026-07-26:

| Behaviour | Model | Prompt consequence |
|---|---|---|
| **Self-verifies unprompted** | Opus 5 | **Delete** "double-check your answer" / "verify before responding" — they cause over-verification. This inverts the usual self-check advice. |
| Longer visible responses | Opus 5 | Add an explicit conciseness instruction; a short one cut length ~20% in testing |
| Longer written files | Opus 5 | Calibrate deliverable length explicitly — separate from conversational verbosity |
| Expands task scope | Opus 5 | Add a scope-discipline instruction; include a finish-the-whole-task clause |
| Delegates to subagents **more** | Opus 5 | Cap spawn count. Note this **reverses** Opus 4.8, which under-delegated |
| Narrates self-corrections at length | Opus 5 | Scope corrections to ones that change the user's outcome |
| Under-reaches for tools / memory / subagents | Opus 4.8 | Put the trigger condition in each tool's own `description` |
| Narrates more between tool calls | Opus 4.8 | Remove "summarize every N tool calls" scaffolding; add a silence-default if too chatty |
| More literal instruction following | Opus 4.7, Sonnet 5 | Dial back `CRITICAL:` / `MUST` / `If in doubt` — they now overtrigger. State scope explicitly when a rule should apply broadly |
| Follows severity filters literally | 4.7, 4.8, Opus 5, Sonnet 5 | In review harnesses, "only high-severity" depresses measured recall — ask for everything + confidence, filter downstream |
| Reaches for tools **less** | Opus 4.7 | Add explicit when/how-to-call guidance |
| Default cream/serif design house style | Opus 4.7 | Give exact hex/typeface, or have it propose 4 directions and pick one |
| Verbose reasoning when thinking disabled | Opus 4.8, Opus 5 | Prefer thinking-on at low effort; else add a final-answer-only instruction |

## Thinking-disabled failure modes (Opus 5)

Only applies when `thinking: {type:"disabled"}` is set explicitly.

1. **Tool calls emitted as plain text** — the turn completes normally, the call
   never runs, no error. In an agentic loop the bogus text pollutes later turns.
   Mitigation: *"You may say a brief sentence before using a tool."*
2. **`<thinking>` tags leak into visible output.** Two counterintuitive rules:
   **delete** any "do not think / do not reason" instruction (it makes leakage
   worse), and write the fix **generically** — *"Do not include internal or
   system XML tags in your response"* beats naming thinking tags.

Primary recommendation for both: turn thinking back on and use `low`/`medium`
effort instead. It is cheaper in every sense.

## Structured output (the prefill replacement)

```python
output_config={"format": {"type": "json_schema", "schema": {...}}}
```

Unsupported in schemas: recursion, `minimum`/`maximum`/`multipleOf`,
`minLength`/`maxLength`, complex array constraints, `additionalProperties`
anything other than `false`. Incompatible with citations (400) and with
prefilling. Python/TS SDKs strip unsupported constraints and validate client-side.

For a fixed label set, prefer a tool with an `enum` field over prose instruction.

## Prompt caching (matters at volume)

- Prefix match. Any byte change anywhere in the prefix invalidates everything
  after it. Render order: `tools` → `system` → `messages`.
- Minimum cacheable prefix is **not monotonic**: 512 tokens on Opus 5 / Fable 5 /
  Mythos 5; 1024 on Opus 4.8 / Sonnet 5 / Sonnet 4.6 / 4.5-era; 2048 on Opus 4.7;
  **4096** on Opus 4.6 / Opus 4.5 / Haiku 4.5.
- Never interpolate a timestamp, UUID, or session ID into the system prompt —
  it invalidates the whole downstream prefix.
- Mid-conversation operator instructions: append `{"role":"system", ...}` to
  `messages` (Opus 5, Opus 4.8, Fable 5, Mythos 5 — **not** Sonnet 5). Preserves
  the cached prefix and is the injection-safe operator channel.
- Max 4 `cache_control` breakpoints per request.

## Refusals

Opus 5 and Fable 5 run elevated cybersecurity safeguards. A declined request is
**HTTP 200** with `stop_reason: "refusal"` and a `stop_details` category.

- Branch on `stop_reason`, never on `stop_details` (which can be `null` on a
  refusal). Code that reads `content[0]` unconditionally breaks.
- Opt into fallbacks by default: `fallbacks: "default"` with beta header
  `server-side-fallback-2026-07-01` (Claude API only). Cyber-category refusals
  route to Opus 4.8.

## Tokenizer

Opus 4.7 introduced a new tokenizer, shared by Opus 4.8, Fable 5, and Sonnet 5.

- From Opus 4.7/4.8 → Fable 5 / Opus 5: counts roughly unchanged.
- From Opus 4.6 / Sonnet 4.6 / Haiku / older: ~1×–1.35× as many tokens for the
  same text (Sonnet 4.6 → Sonnet 5 is ~+30%).
- Never apply a blanket multiplier. Re-run `count_tokens` against the target
  model. Never use `tiktoken` for Claude — it undercounts 15–20% on prose and
  far more on code.

## Vision

High-resolution tier (2576 px long edge, up to ~4784 visual tokens/image):
Opus 5, Opus 4.8, Opus 4.7, Sonnet 5. Coordinates map 1:1 to pixels — no
scale-factor math. Earlier models cap at 1568 px.

On Opus 5, **giving crop/analyze/verify tools beats raising thinking** for vision
accuracy, and is cheaper.

## Rate limits

Opus 5 draws on a **separate** bucket from the combined Opus 4.x pool. Shifting
traffic neither frees headroom on the old bucket nor inherits it.
