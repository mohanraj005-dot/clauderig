# Step 8.5 — the cost lens

Runs between the dead-construct scan (8) and the re-score (9). It needs the
finished prompt text, so it cannot precede step 8; its verdict is the evidence
for step 9's **Efficiency** axis, so it must precede step 9. Slotting it at 8.5
keeps the pipeline a 9-step pipeline everywhere else it is referenced.

## What it rules on

Four questions, in this order. Each is answerable from facts, not vibes.

| # | Question | Decided by |
|---|---|---|
| 1 | Is the **tier** warranted? | task attributes vs the capability/price table below |
| 2 | Is the **effort** level right, and is `max_tokens` legal for it? | `claude.md` §Effort |
| 3 | Is the prefix **cacheable**, and does the volume sustain a cache? | `claude.md` §Pricing levers |
| 4 | Is the **fan-out** shape defensible? | cap recommendation only — never a cost estimate |

## The hard gate

> If **volume**, **prefix size**, or **target model** is unknown, emit
> `VOLUME: unstated` and **skip the cache verdict entirely.**

A guessed volume produces a confidently wrong cache recommendation, which is
worse than no recommendation. This mirrors step 4's success-criteria stop.

## Tier selection

Every row below is grounded in a cited capability or price difference. Rows
marked **[J]** are judgement, not documentation — say so when you use one.

| Attribute | Verdict | Why |
|---|---|---|
| Context > 200K | **Not Haiku 4.5** | hard cap 200K; everything else is 1M |
| Output > 64K needed | **Not Haiku 4.5** | max output 64K vs 128K |
| Needs `output_config.effort` | **Not Haiku 4.5** | `effort` errors on Haiku 4.5 |
| Needs adaptive thinking | **Not Haiku 4.5** | no adaptive mode |
| Hard coding / agentic | **`claude-opus-5` @ `xhigh`** | documented starting point |
| High-volume, coding-shaped | **`claude-sonnet-5`** | near-Opus on coding; 40–60% cheaper |
| Classification / single-label, speed-critical | **`claude-haiku-4-5`** | 5× cheaper both directions |
| Deterministic schema extraction, no reasoning chain | Haiku 4.5 **[J]** | no source ranks tiers on extraction |
| Latency-critical but must stay Opus-tier | Opus 5 + `speed:"fast"` | 2.5× output rate at 2× price; Claude API only, not Batch |
| Deferrable ≤24h | **Any tier + Batch = 0.5×** | usually dominates a tier downgrade |
| Prefix 512–1023 tok, high volume | **Opus 5 / Fable 5 only** | they cache at 512; Sonnet needs 1024, Haiku 4096 |
| Migrating Sonnet 4.6 → Sonnet 5 | **re-baseline token counts** | new tokenizer, ~+30% tokens for the same text |

**The counter-intuitive one, and the reason this lens exists:** *the cheapest tier
is often the least cacheable.* An 800-token prefix caches on Opus 5 (min 512) and
silently does not on Haiku 4.5 (min 4096). At sufficient volume the 90% cache
discount can invert the tier ranking. **Always check the minimum before
recommending a downgrade.**

## Two constraints the lens must ENFORCE, not advise

1. At `xhigh`/`max`, `max_tokens ≥ 64K` — or output truncates.
2. On Opus 5, `thinking:{type:"disabled"}` at `xhigh`/`max` is a **400**. A lens
   that says "disable thinking to save tokens" without checking effort emits a
   broken prompt.

## Evaluate Batch first

A flat 0.5× on every token type is the only lever that is both large and free of
quality risk. Check eligibility *before* considering a tier downgrade.

## Output block

Emit alongside the step-9 score. Fixed format, ≤12 lines, nothing else.

```
[cost lens]
MODEL     <id> · $<in>/$<out> per 1M · ctx <N> · max_out <N>   (claude.md, verified <date>)
TIER      OK | OVERSPEC → <cheaper id>, saves ~<N>% | UNDERSPEC → <id>, reason: <row>
EFFORT    <level> · max_tokens <N> <OK | MUST BE ≥64K at xhigh/max>
PREFIX    <N> tok stable / <N> tok variable · model min <512|1024|2048|4096> · <CACHEABLE|BELOW MIN>
VOLUME    <N>/day · <N> req per 5m window / <N> per 1h window
CACHE     <NO CACHE|ttl:5m|ttl:1h> · break-even <2|3> req/window · projected input saving ~<N>%
BREAKPTS  <N>/4 · placement <last stable block | END-OF-PROMPT ✗>
RISKS     <invalidator rules that fail, or "none">
FANOUT    <N> subagents · <cap advised: N | n/a> · per-subagent cost UNVERIFIED
BATCH     <eligible → 0.5× | not eligible: latency-bound>
VERDICT   <SHIP | RETUNE: the one change with the largest $ delta>
```

Show the arithmetic under the block, or it is vibes.

## Worked example — 200×/day, structured extraction from a 2k-token document, no tools

Stated assumptions (the lens must never hide these): stable system prompt +
schema ≈ 800 tok; the 2k document is different every call, so it is *variable*,
not prefix; output ≈ 300 tok; evenly spread; not latency-critical.

```
[cost lens]
MODEL     claude-haiku-4-5 · $1.00/$5.00 per 1M · ctx 200K · max_out 64K   (claude.md, verified 2026-07-26)
TIER      OK — no reasoning chain, 2.3K in / 0.3K out, 0 tool calls, well inside caps
EFFORT    n/a — `effort` errors on Haiku 4.5; adaptive thinking unsupported
PREFIX    800 tok stable / 2,300 tok variable · model min 4096 · BELOW MIN
VOLUME    200/day · 0.69 req per 5m window / 8.3 per 1h window
CACHE     NO CACHE — prefix 800 < 4096 min; cache_control would silently no-op
BREAKPTS  0/4 · placement n/a
RISKS     none — nothing cacheable to invalidate
FANOUT    0 subagents · n/a · per-subagent cost UNVERIFIED
BATCH     eligible (no latency constraint) → 0.5×: $0.92/day → $0.46/day
VERDICT   SHIP on haiku-4-5 + Batch API. Do not add cache_control at this tier/prefix.
```

| Tier | in | out | $/req | $/day @200 | + Batch |
|---|---|---|---|---|---|
| `claude-haiku-4-5` | 3,100 | 300 | **$0.00460** | $0.92 | **$0.46** |
| `claude-sonnet-5` (intro) | 3,100 | 300 | $0.00920 | $1.84 | $0.92 |
| `claude-opus-5` | 3,100 | 300 | $0.02300 | $4.60 | $2.30 |

Note what this surfaces: **Batch beats every tier downgrade here**, and the cache
verdict flipped on a model *minimum*, not on price.

## Boundary — do not duplicate neighbouring skills

| Skill | Owns | The line |
|---|---|---|
| **this lens** | design-time economics of a **prompt artifact** | emits **projections**; never reads live usage |
| a runtime cost/context auditor skill, if you have one | runtime audit of **this session's measured** spend | emits **measurements**; never predicts |
| a model-selection advisor skill | switching the **active session** model | never scores a prompt, and explicitly refuses to quote cost multiples |
| a cloud-cost/FinOps skill | infra line items in code/config | not LLM tokens at all |

If the lens ever prints a measured value it has crossed into the runtime
auditor's lane. If that auditor ever prints a projection, it has crossed back.

**Known conflict, decide explicitly:** a keyword-routed model-advisor tends to
route on prompt-opening phrasing (`write a…` → Sonnet); this lens routes on task
attributes (context size, output length, effort support, cacheable prefix). They
*will* disagree — a prompt opening "write a…" that needs 300K context. **The
lens wins on tier for the artifact; the advisor wins on the session model.**
They are answering different questions.

## Shelf life

`claude-sonnet-5`'s introductory rate ($2/$10) expires **2026-08-31**. Any
volume-driven recommendation resting on it must print both rates.
