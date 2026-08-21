---
family: Claude
last_verified: 2026-07-26
confidence: AUTHORITATIVE
source: bundled `claude-api` skill (Anthropic-maintained), read in full 2026-07-26
---

# Claude — promptcarta model facts

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

## Pricing levers — caching, batch, fast mode

`levers_verified: 2026-07-31` · source: bundled `claude-api` skill
(`shared/prompt-caching.md`, `python/claude-api/batches.md`, its SKILL.md
§Fast Mode), read in full. **Refresh by invoking the `claude-api` skill** — its
path is version-hashed and must never be hardcoded.

This section exists because the cost lens (step 8.5) needs numbers, and the
skill's HARD RULE forbids sourcing them from memory. Before this section, no
`references/models/*.md` file carried a cache multiplier at all.

| Lever | Multiplier vs base input | Source |
|---|---|---|
| Cache **write**, 5-minute TTL | **1.25×** | `prompt-caching.md:141` |
| Cache **write**, 1-hour TTL | **2×** | `prompt-caching.md:141` |
| Cache **read** | **0.1×** | `prompt-caching.md:141,152` |
| Batch API (all token types) | **0.5×** | `batches.md:3,10` |
| Fast mode, Opus 5 (`speed:"fast"`) | **2×** in and out ($10/$50) | `claude-api` SKILL.md §Fast Mode |

**Minimum cacheable prefix — non-monotonic, so check the model, don't interpolate:**

| Tokens | Models |
|---|---|
| **512** | Opus 5, Fable 5, Mythos 5 |
| **1024** | Opus 4.8, Sonnet 5, Sonnet 4.6 |
| **2048** | Opus 4.7, Haiku 3.5 |
| **4096** | Opus 4.6, **Haiku 4.5** |

Below the minimum the cache **silently no-ops** — `cache_creation_input_tokens: 0`,
no error (`prompt-caching.md:128`). Max **4** breakpoints (`:125`).

**Break-even.** Write premium ÷ saving-per-read, where saving = 1.0 − 0.1:

| TTL | Write | Reads to break even | Requests to profit |
|---|---|---|---|
| 5m | 1.25× | 0.25 / 0.9 = **0.28 → 1** | **2** |
| 1h | 2.00× | 1.00 / 0.9 = **1.11 → 2** | **3** |

Asymptote: **0.1× base input on the cached span — a 90% discount.**

**The gate everyone forgets:** requests must arrive *within* the TTL of each other.
`requests_per_window = daily_volume × (TTL_minutes / 1440)`. Evenly-spread traffic
under **288/day cannot sustain a 5-minute cache** — every request becomes a cold
write at 1.25×, so caching makes it *worse*. Ask for burst shape, not just volume.

**Does the TTL refresh on read?** **UNVERIFIED.** `prompt-caching.md:216` implies it
("requests more often than every 5 minutes keep the cache warm") but never asserts
it. Do not encode as fact.

**Invalidators** (render order is `tools` → `system` → `messages`; a change at
position N kills every breakpoint at ≥ N): any byte change in the prefix; tool
add/remove/**reorder**; **model switch** (caches are model-scoped, no escape hatch);
`datetime.now()`/`uuid4()` in the prefix; `json.dumps()` without `sort_keys=True`;
session/user id in the system prompt; conditional system sections. Does **not**
invalidate: `tool_choice`, images, thinking on/off, `speed`, message content.

Two structural rules the lens can check mechanically: the breakpoint goes on the
**last block of the shared portion**, not the end of the prompt (`:56-58`); and a
breakpoint walks back at most **20 content blocks**, so long agentic turns need an
intermediate breakpoint every ~15 (`:191-193`).

**Subagent cost: UNVERIFIED.** No documented per-subagent overhead figure exists in
`claude-api` or here. Grepping for `7x`, `Agent Teams`, `per subagent` returns zero
hits. The lens may recommend a **cap**; it must never print a subagent dollar figure.
What *is* documented: a subagent on a cheaper model preserves the main loop's cache
(`agent-design.md:94`), run subagents at `low` effort, and Opus 5 over-delegates
(see the behavioural table below).

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
