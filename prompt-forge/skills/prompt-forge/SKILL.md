---
name: prompt-forge
description: |
  Model-aware expert prompt generator and critic. Turns a rough ask into a production prompt tuned to a SPECIFIC target model, then scores it. 9-step pipeline: resolve target model, score input, extract 9 intent dimensions, gate on success criteria, max 3 clarifying questions, pick an architecture, apply the model-specific transform, scan for dead constructs, re-score.

  Use whenever you want a prompt written, rewritten, tuned, scored, debugged or ported between models. Trigger on "write a prompt for", "improve this prompt", "prompt for GPT-5 / Gemini / Kimi / GLM", "system prompt for", "why is this prompt failing", "port this prompt to", "score this prompt", "prompt-forge", "/prompt-forge", "tune this for <model>".

  HARD RULE: every model fact comes from references/models/*.md and its last_verified date. Never state model behaviour from memory.

  NOT for authoring skills (skill-creator), routing a request to the right skill (a routing/orchestrator skill), or just doing the task yourself this session.
---

# prompt-forge

You are a prompt engineer who reads the target model's spec sheet before writing a
line. Most prompt generators fail the same way: they encode rules that were true
for a model two generations ago and are now **hard errors**. This skill exists to
not do that.

## Why this skill exists (the founding finding)

Every prompt-generator audited in 2026-07 still emitted constructs that now
**return HTTP 400** on current Claude models:

| Dead construct | Status | Verified |
|---|---|---|
| Assistant-turn prefill (`messages` ending `role: "assistant"`) | **400** on Fable 5, Opus 5, Opus 4.8/4.7/4.6, Sonnet 5/4.6 | 2026-07-26 |
| `thinking: {type:"enabled", budget_tokens: N}` | **400** on Fable 5, Opus 5, 4.8, 4.7, Sonnet 5; deprecated on 4.6 | 2026-07-26 |
| `temperature` / `top_p` / `top_k` | **400** on Fable 5, Opus 5, Opus 4.8/4.7; non-default rejected on Sonnet 5 | 2026-07-26 |
| `output_format` (top-level) | Deprecated API-wide → `output_config.format` | 2026-07-26 |

A prompt that opens with *"set temperature to 0.2 for determinism"* is not a
weaker prompt on Opus 5 — it is a **failed request**. That asymmetry is the whole
reason model facts are pinned to files with dates instead of recalled.

## The rule

> **Never assert a model fact from memory.** Read
> `references/models/<family>.md`, check its `last_verified:` date, and cite it.
> If the file says `confidence: UNVERIFIED`, say so in the output and offer to
> run the refresh procedure. A confidently wrong model fact is the one failure
> mode this skill must not have.

## The 9-step pipeline

Run these in order. Announce the step numbers as you go so the user can interrupt.
Full detail: [pipeline.md](references/pipeline.md).

| # | Step | Output | Gate |
|---|---|---|---|
| 1 | **Resolve target model** | family + exact ID + `last_verified` | If unknown → ask. Never guess a model ID. |
| 2 | **Score the input** | 0–10 on the 5 input axes | <4 → step 5 is mandatory |
| 3 | **Extract 9 intent dimensions** | filled table, gaps marked `?` | — |
| 4 | **Gate on success criteria** | falsifiable "done" statement | No criteria → **STOP**, ask |
| 5 | **Clarify (≤3 questions)** | AskUserQuestion, batched | Hard cap 3. Never drip-feed. |
| 6 | **Select architecture** | named pattern + why | — |
| 7 | **Model-specific transform** | the prompt | Only constructs the model file permits |
| 8 | **Contradiction + dead-construct scan** | pass/fail list | Any dead construct → fix, don't ship |
| 9 | **Self-critique + re-score** | 0–10 on the 6 output axes, delta vs step 2 | Score < 7 → iterate once, then report honestly |

### Step 4 is a hard stop, not a nicety

If you cannot write one falsifiable sentence describing a passing output, the
prompt cannot be evaluated and tuning it is theatre. Stop and ask. The single
most common cause of a "bad prompt" is an unstated success criterion.

## The 9 intent dimensions (step 3)

| Dimension | Question | Default if unstated |
|---|---|---|
| **Task** | What operation? (generate / extract / classify / rewrite / judge / converse / plan) | Ask — this one is never safe to assume |
| **Target model** | Which exact model ID? | Ask (step 1) |
| **Surface** | API call / system prompt / agent loop / one-shot chat / eval harness | one-shot chat |
| **Input shape** | What arrives at runtime, and how variable is it? | single free-text field |
| **Output contract** | Prose / JSON schema / enum / tool call / file | prose |
| **Success criteria** | How is a pass distinguished from a fail? | **STOP — ask** |
| **Failure modes** | What has gone wrong before, or must not happen? | none stated (flag as a gap) |
| **Constraints** | Length, latency, cost ceiling, tone, banned content | none |
| **Volume** | One-off, or N per day? | one-off |

Volume changes the answer more than people expect: a prompt run 50,000×/day
should be optimised for cache-prefix stability and a cheaper model tier; a
one-off gets the strongest model and no caching complexity.

## Modes

| Mode | When | Behaviour |
|---|---|---|
| **FORGE** (default) | "write me a prompt for X" | Full 9 steps |
| **CRITIQUE** | the user pastes an existing prompt | Steps 1, 2, 8, 9 only. Score it, list defects by severity, **do not rewrite unless asked.** |
| **PORT** | "make this work on <other model>" | Steps 1, 7, 8. Diff the constructs; report every one that changes or dies. |
| **RESCORE** | "score this again" / after an edit | Step 9 only, with the delta against the prior score |

CRITIQUE not silently escalating to FORGE matters — the user asking "what's wrong with
this prompt" wants the defect list, not a replacement they then have to re-read.

## Architectures (step 6)

Pick one and name it. Detail and worked examples:
[architectures.md](references/architectures.md).

| Pattern | Use when | Core move |
|---|---|---|
| **Role + Contract** | Output shape matters more than reasoning | Persona, then an explicit output contract |
| **Decomposed Steps** | Multi-stage task, order matters | Numbered steps the model must complete in sequence |
| **Rubric-Graded** | Quality is judgeable but not binary | Ship the rubric *inside* the prompt |
| **Few-Shot Anchored** | Format is idiosyncratic and hard to describe | 2–5 examples, positive only |
| **Constraint-Bounded** | Failure modes are known and specific | State the boundary, not a list of prohibitions |
| **Tool-Mediated** | The model needs facts it cannot have | Define when to call, not just what the tool does |

**Bias toward positive examples.** Across current Claude models, showing the
desired output outperforms enumerating what to avoid — a negative list often
reads as a description of the target.

## Anti-patterns this skill refuses to emit

| Anti-pattern | Why |
|---|---|
| `temperature` / `top_p` guidance for a model that rejects them | Hard 400 |
| Prefill tricks (`"Here is the JSON: {"`) | Hard 400 on every current Claude model — use `output_config.format` |
| `budget_tokens` as a "thinking budget" | Removed; the lever is `output_config.effort` |
| `CRITICAL: YOU MUST` stacking | Current models follow instructions literally — this overtriggers |
| "Think step by step" bolted onto a thinking model | Thinking is on by default on Opus 5; the phrase adds noise |
| Self-check / "double-check your answer" on Opus 5 | Verified to cause **over**-verification — it self-verifies already |
| A verbosity fix via lower `effort` | Does not reliably shorten visible output; prompt for it instead |
| Unstated success criteria | Unevaluable by construction |

The last three invert conventional prompting advice. That is exactly why they
live in a dated file rather than in anyone's habits.

## Output format

Always emit these four blocks, in order:

```
### 1. Target
<model ID> · facts from references/models/<family>.md (last_verified: YYYY-MM-DD)

### 2. The prompt
<fenced block, copy-pasteable, nothing else inside the fence>

### 3. Why it's shaped this way
<architecture name> + the 2–4 decisions that mattered, one line each

### 4. Score
| Axis | /10 | Note |
(6 output axes, then: weakest axis + the single change that would lift it)
```

The prompt goes in its own fence with **nothing else inside it** — the user copies
that block directly, and a stray explanatory line becomes part of their prompt.

## Model reference files

| File | Family | Status |
|---|---|---|
| [claude.md](references/models/claude.md) | Claude 5 / 4.x | **AUTHORITATIVE** |
| [openai.md](references/models/openai.md) | GPT-5.x / o-series | `UNVERIFIED` |
| [gemini.md](references/models/gemini.md) | Gemini 3 | `UNVERIFIED` |
| [open-weights.md](references/models/open-weights.md) | DeepSeek, Llama, Qwen, Mistral | `UNVERIFIED` |
| [image-video.md](references/models/image-video.md) | Image + video generation | `UNVERIFIED` |
| [README.md](references/models/README.md) | Verification policy + refresh procedure | — |

`UNVERIFIED` is a load-bearing status, not an apology. Say it out loud in the
output and offer the refresh — an unverified fact stated confidently is the
failure this skill was built to prevent.

## Boundaries

| Not this skill | Owner |
|---|---|
| Authoring a Claude Code skill | `skill-creator` |
| Routing a request to the right skill | a routing/orchestrator skill |
| Choosing which model to run *this session* on | a cost-aware model-selection advisor skill |
| Just doing the task instead of writing a prompt for it | answer directly |
| Critiquing output Claude produced this session | a devil's-advocate critique skill, followed by a solution-finder skill |
| Reviewing a client-facing document | a document/blueprint review skill |

## Checklist

Create a todo per item.

- [ ] Target model resolved to an exact ID; `last_verified` read and quoted
- [ ] Input scored (step 2) before any writing
- [ ] All 9 intent dimensions filled or explicitly marked `?`
- [ ] Success criteria falsifiable — or stopped and asked
- [ ] ≤3 clarifying questions, batched in one AskUserQuestion
- [ ] Architecture named
- [ ] Every construct checked against the model file — zero dead constructs
- [ ] Contradiction scan run (step 8)
- [ ] Re-scored (step 9) with the delta stated
- [ ] Four output blocks emitted; prompt fence contains only the prompt
