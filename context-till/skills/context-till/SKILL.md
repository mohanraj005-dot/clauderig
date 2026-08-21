---
name: context-till
description: Stingy end-of-turn cost and context controller. Audits every response for token waste and context-budget pressure, and nudges when avoidable spend or avoidable context growth happened. Invoked manually, or wired to end-of-turn via an orchestrator/router hook if you have one — silent when clean, vocal when waste detected. Trigger directly with "till check", "context-till audit", "what's the waste", "am I burning tokens", "till context", "how much budget is left", "why is context growing". The till is stingy and exact — it never adds prose where a tally will do.
---

# Context Till — Cost & Context Controller

Context Till is the household-finance-officer of the Claude session. It doesn't write essays. It doesn't celebrate clean turns. It shows up at the end, eyes the till, and either says nothing (good) or lists the leaks (bad).

It watches two tills:

| Till | Question | Signals |
|------|----------|---------|
| **Cost** | Are we paying for tokens we didn't need? | #2, #6, #9, #10, #13, #14 |
| **Context** | Is the window filling faster than the work justifies? | #5, #15, #16, #17, #18, #19, #20, #21 |

## When invoked

- Wired to end-of-turn via an orchestrator/router hook, if your setup has one (that piece is NOT part of this package — see "Package scope" below). Relay the hook-computed `[Context Till]` block **verbatim**.
- Manually when the user says "till check", "context-till audit", "what's the waste", "am I burning tokens", "cost check", "till context", "how much budget is left", or any phrasing about session spend or context growth.

## Package scope — what this package ships vs. what it assumes

This package ships five hooks: `till-overhead.js`, `till-tool-bloat.js`, `till-handoff-gate.js`, `till-handoff-resume.js`, and `till-precompact.js`. Between them they fully compute signals **#14** (time arm), **#17**, **#18**, **#20**, and **#21** — no other hook is required for those.

Signals **#2, #5, #13, #15, #16, #19**, and the **context arm of #14**, are computed in the reference design by a `UserPromptSubmit` router/orchestrator hook that is **NOT included in this package** (it lived alongside cache/cost logic specific to one setup). Concretely:

- `till-precompact.js` still increments a compaction counter in the shared state file on every `PreCompact` event — that bookkeeping is self-contained and harmless. But nothing in this package turns that counter into a spoken `#19` line; a `UserPromptSubmit` hook needs to read it and decide to speak.
- `till-handoff-gate.js`'s context arm reads `used_prev` / `ceiling` / `ema_delta` from the shared state file. Only `ceiling` is populated by a shipped hook (`till-overhead.js`); `used_prev` and `ema_delta` are never written without an external per-turn hook. Absent that data, `contextArm()` returns `null` and only the time arm of #14 can fire. This is by design — the hook fails open, it does not crash or guess.
- If you want #2/#5/#13/#15/#16/#19 to actually speak, you need to add your own `UserPromptSubmit` hook that reads/writes the same per-session state keys (`used_prev`, `ceiling`, `ema_delta`, `compactions`) that the shipped hooks already read and write — see "Shared state" below for the file layout. Until then, treat those six rows in the tables below as **documented but dormant**.

## The measurement rule

**Everything numeric is computed by a hook. Nothing numeric is guessed by the model.**

Six signals were retired for asking the model to observe data it cannot see, which produced false alarms and destroyed the till's credibility. That rule now extends to context: you cannot see your own context size, burn rate, or compaction count. Do not estimate them. If no hook line appeared, say nothing.

Only three signals are yours (#6, #9, #10), and only when directly observed in the current turn.

## Signals

Hook-measured unless marked otherwise. ASSUMED thresholds have no published source and are labelled as such — Anthropic documents no context-degradation curve, so those numbers are provisional and env-overridable. Rows marked **(dormant without an external router hook)** are documented in full per "Package scope" above.

### Cost till

| # | Tag | Signal | Threshold | Correction to emit |
|---|-----|--------|-----------|--------------------|
| 2 | [MEASURED] **(dormant without router hook)** | Idle gap past the applicable cache TTL edge — regime detected from `cache_creation.ephemeral_*` (subscription = 1-hour; API key = 5-min) | 270s / 3300s by regime | "Idle ~Xm — near the \<regime\> TTL edge; next turn may pay a cold-start write." |
| 13 | [MEASURED] **(dormant without router hook)** | Cache hit rate below target last turn | <70%, gated on >3k input | "Hit rate <70% — model flip, prefix edit, or idle gap busted the cache." |
| 14 | [HOOK-ENFORCED] | Task ran long, **or** context budget nearly spent — `till-handoff-gate.js` blocks Stop once and offers a handoff | 180s wall-clock (`TILL_HANDOFF_THRESHOLD_SEC`), or ≤3 turns of headroom (`TILL_CTX_TURNS_BLOCK`) | Handled by the Stop hook. Don't pre-empt it. Only the time arm fires without a router hook — see "Package scope". |
| 6 | [BEST-EFFORT] | A file Read the same turn it was just Edited/Written | — | "Re-Read after Edit on \<file\>. Harness already has it." |
| 9 | [BEST-EFFORT] | Excessive subagent fan-out in THIS turn | >12 (platform default cap is 20) | "Fan-out of \<N\>. Consider sequencing." |
| 10 | [BEST-EFFORT] | Opus subagent where Sonnet/Haiku would suffice | — | "Opus on subagent for \<task\>. Sonnet would do — ~60% saved." |

Subagent delegation is a context *reduction* technique — a subagent explores tens of thousands of tokens and returns a 1–2k summary in an isolated window. A low fan-out threshold penalises the single most effective context move available, and it would contradict the documented platform default of 20 concurrent. (A "~7x cost per subagent" figure circulates in some corners — it belongs to an experimental multi-agent-teams feature, not to Task-tool subagents, and should not be cited against #9.)

### Context till

| # | Tag | Signal | Threshold | Correction to emit |
|---|-----|--------|-----------|--------------------|
| 5 | [MEASURED] **(dormant without router hook)** | Context level as a share of the auto-compact ceiling | 60% warn / 75% alert of ceiling (`TILL_HANDOFF_WARN_TOKENS` / `_ALERT_TOKENS` override as absolutes) | "Context ~Xk of ~Yk (Z%); plan a handoff / a handoff + /clear resets the meter." |
| 15 | [MEASURED] **(dormant without router hook)** | Budget level, informational | Emitted **only** when another context signal already fired | "Budget Z% used (~Xk / ~Yk, ceiling src: \<src\>)." |
| 16 | [MEASURED] **(dormant without router hook)** | Burn rate → turns until auto-compact. EMA over the per-turn delta | ≤8 turns remaining (`TILL_CTX_TURNS_WARN`, **ASSUMED**) | "Burning ~Xk/turn; ~N turns to auto-compact. Handing off now costs less than compacting later." |
| 17 | [MEASURED] | A single tool call returned a large result, with no sandboxed alternative | >20,000 chars (`TILL_CTX_BLOAT_CHARS`, **ASSUMED** — no documented per-result cap exists) | "\<tool\> returned ~Xk tok in one call; narrow the query or derive the answer in code." |
| 18 | [MEASURED] | Same, but a sandboxed-execution tool offered an alternative that was bypassed | same | "\<tool\> returned ~Xk tok of raw bytes; \<ctx_tool\> would have kept them in the sandbox." |
| 19 | [MEASURED count / **ASSUMED** threshold] **(dormant without router hook)** | Compactions already survived this session | ≥2 (`TILL_CTX_COMPACTIONS_WARN`) | "N compactions this session; skill bodies are being dropped (5k/skill, 25k cap). /clear + handoff beats another summary." |
| 20 | [MEASURED] | Skill listing exceeds its budget, so Claude Code is dropping descriptions of least-invoked skills | listing tokens > 1% of ceiling; or any entry >1536 chars | "Skill listing ~Xk tok across N skills vs ~Yk budget (Zx over). Those skills cannot trigger." |
| 21 | [MEASURED floor] | Fixed per-turn overhead before the user types | ≥8% of ceiling (`TILL_CTX_OVERHEAD_PCT`, **ASSUMED**) | "~Z% of the budget is spent before you type. Floor only — MCP schemas aren't measurable from disk." |

**Hard cap: at most 2 context lines per turn**, highest severity first (#19 > #16/#5 > #15). The context window already carries other standing instructions, memory, and more. A stingy shopkeeper does not send a seven-line invoice.

### Retired

Several early signals were retired outright — they asked the model to guess data it cannot observe: prior-turn model flip, cross-turn serial dispatch, re-explained memory, compact-vs-handoff choice, repeated reads across turns, wide-read-vs-grep choice.

**One signal was removed outright as a MYTH.** Editing CLAUDE.md / settings.json / hooks mid-session does NOT invalidate the cache; it simply doesn't apply until the next `/clear`.

## The remediation ladder

When a context signal fires, this is what to actually do — cheapest rung first. The hook can only recommend; no hook can trigger `/compact`, `/clear`, or a handoff.

| Rung | Fired | Action | Why this one |
|------|-------|--------|--------------|
| 1 | #18 | Route the next equivalent call through a sandboxed execution tool | Prevents the bytes rather than compressing them after the fact |
| 2 | #17 on a wide Read | `Grep`/`Glob` to locate first, then `Read` with `limit`/`offset` | Just-in-time retrieval — Claude Code's own documented pattern |
| 3 | #17 before a big exploration | Delegate to a subagent | Isolated window; returns 1–2k tokens after exploring tens of thousands. Highest-leverage move available |
| 4 | #16, and the next task is a **new topic** | A session-handoff-style snapshot, then `/clear` | Stale context is re-paid on every subsequent message |
| 5 | #16, and the work is **mid-thread** | `/compact <focus>` with an explicit focus string | Steering beats the automatic guess |
| 6 | #19 (≥2 compactions) | `/clear` + handoff — **not** a third compaction | Each compaction re-injects skill bodies capped at 5k/skill, 25k total, oldest dropped. The session is already lossy |
| 7 | #20 | Audit skill descriptions; prune, or raise `skillListingMaxDescChars` | Truncated descriptions mean skills that silently never trigger |

Rung 3 deserves emphasis: fan-out is the cheapest context move, not an extravagance. Prefer it over reading widely in the main thread.

### `/clear` does not kill background work — quitting the app does

Verified against the Claude Code 2.1.219/2.1.220 binaries (`clearConversation`), not inferred. Tasks with `isBackgrounded: true` are copied into the new conversation and their completion notifications are re-armed; only foreground tasks are aborted, and those block the turn so `/clear` cannot reach them anyway. Behaviour changed in **2.1.72**. **Never warn that `/clear` orphans agents.**

The real hazard is one step later, and it is silent:

> handoff → `/clear` (safe) → **quit the app** → the session PID dies and takes its children with it. Next launch: *"background agent(s) orphaned by previous process exit."* The snapshot said nothing, so nothing prompted a check.

`till-handoff-gate.js` guards against this: before it offers a handoff it instructs a `TaskList` call, and if anything is still running it adds a third option — *"Wait for background work"* — instead of only "handoff" or "keep working". If a handoff is chosen anyway, the snapshot is told to record each running task's id, purpose, output path, and agent id under a **Live work at handoff** heading. If your session-handoff-style skill doesn't already carry that heading, add it — a fresh session cannot message an agent id it was never told.

Recovery paths if it happens anyway:

| Artifact | Path |
|---|---|
| Background bash stdout | `/private/tmp/claude-<pid>/<project>/<SESSION-UUID>/tasks/<id>.output` |
| Background agent transcript | `~/.claude/projects/<project>/<SESSION-UUID>/subagents/agent-<id>.jsonl` |
| Pre-clear conversation | `/resume`, or `/rewind` (gained pre-`/clear` recovery in 2.1.191) |

## Manual commands (don't auto-fire)

Explicit user commands. Context Till does NOT run these at end-of-turn — they cost tokens or processes that defeat the purpose if always-on.

### `till context`

Report the live context position from the hook state file. State lives at `~/.claude/.context-till/<session-id>.json` — one file per session (the session id has non-alphanumeric characters stripped for the filename). Read the file for the current session:

```
[Context Till — context]
  Budget:     <used>k / <ceiling>k  (<pct>%)   ceiling src: <src>
  Burn:       ~<ema>k/turn → ~<N> turns to auto-compact
  Compactions:<N> this session
  Overhead:   ~<X>k fixed (skills + memory), floor only
```

`Budget` and `Burn` require `used_prev`/`ema_delta` to be present — see "Package scope" above; without a router hook writing them, report only `Compactions` and `Overhead` and say the rest is unavailable. If the file is missing or its `session_id` doesn't match, say so and stop. Do not reconstruct the numbers.

### `till stats`

```bash
npx ccusage@latest blocks --active --json
```

NOTE: `--since` takes `YYYYMMDD`, NOT a duration like `"1h"` — passing a duration silently returns lifetime totals. Use `blocks --active` for the current ~5h billing window.

Parse `blocks[0]`: `costUSD`, `projection.totalCost`, `models`, and `tokenCounts.{inputTokens,cacheReadInputTokens}` for the hit rate (`cacheRead / (cacheRead + input)`).

```
[Context Till — ccusage]
  Active block: $<x.xx>  (current ~5h window; projected $<y.yy> if it runs full)
  Cache hits:   <pct>%   (target: >70%)
  Top model:    <model>
```

ccusage tracks spend by **model/day, not by tool/skill** — per-skill "top spender" and a turn count are NOT derivable from it. Don't fabricate them.

If not installed: `ccusage not installed — npm i -g ccusage or skip stats`.

### `till countdown`

Read the most recent assistant turn's usage block (when visible):

```
[Context Till — TTL]
  5m cache:  expires in ~<MM:SS>  (ephemeral_5m_input_tokens: <N>)
  1h cache:  expires in ~<HH:MM>  (ephemeral_1h_input_tokens: <N>)
```

If the usage block isn't accessible, stay silent — don't guess.

## Output format

When ANY signal fires, emit exactly this. Nothing more:

```
[Context Till]
  🪙 <signal #N> — <correction text from the hook>
  🪙 <signal #N> — <correction text from the hook>
```

When the turn is clean: **emit nothing at all.** Context Till is stingy with its own bytes.

## The hooks (shipped in this package)

| Hook | Event | Signals | Disable |
|------|-------|---------|---------|
| `till-tool-bloat.js` | PostToolUse | #17, #18 | `TILL_CTX_DISABLE=1` |
| `till-overhead.js` | SessionStart | #20, #21 | `TILL_CTX_DISABLE=1` |
| `till-precompact.js` | PreCompact | feeds #19's counter (see "Package scope") | `TILL_CTX_DISABLE=1` |
| `till-handoff-gate.js` | Stop | #14 (time arm always; context arm needs an external router hook) | `TILL_HANDOFF_DISABLE=1` |
| `till-handoff-resume.js` | SessionStart | auto-resumes a handoff snapshot on the next session | `TILL_RESUME_DISABLE=1` |

Not shipped: a `UserPromptSubmit` router/orchestrator hook computing #2, #5, #13, #15, #16, and the spoken form of #19. See "Package scope" above if you want to add one.

**State: `~/.claude/.context-till/<session-id>.json` — one file per session, never a single shared file.** An earlier design used one global `.context-till-state.json` keyed on `session_id`, resetting every field on a mismatch. Two concurrent sessions writing that file is a real failure mode, not a theoretical one: last writer wins, silently wiping the other session's `compactions`, `used_prev`, and `ema_delta`. The per-session partition rules that out by construction — each session only ever touches its own file. `till-overhead.js` prunes files older than 7 days on every `SessionStart`. Gitignore the whole `.context-till/` directory in your project.

**Design constraints, deliberate:**

- **No output truncation.** `PostToolUse` can replace a tool result via `updatedToolOutput`. It is not used. Truncating a `Read` breaks the `Edit` that follows, because Edit matches against exact bytes and the model gets no signal explaining the failure. The tool has also already run, so truncation saves no work.
- **`till-precompact.js` can never block.** Blocking a compaction that is recovering from a context-limit error surfaces that error and fails the request. The hook writes nothing to stdout, by construction.
- **Every hook fails open.** Missing telemetry, unparseable payload, absent state file → exit 0, emit nothing. Never fabricate a number when its input is absent.

### The ceiling

`ceiling` = the auto-compact trigger, not the raw window. Resolution order:

1. `CLAUDE_CODE_AUTO_COMPACT_WINDOW` if set
2. A bridge file at `/tmp/claude-ctx-{session_id}.json` → `context_window.total_tokens` × 0.967, if present
3. `settings.json` model marker — `opus[1m]` → 967,000
4. Default 200,000

**The bridge file (step 2) is written by a statusline command, and statusline commands only run in the terminal TUI** — it will not exist under a desktop-app entrypoint. Context Till therefore owns the level signal there by default, not by preference.

## What Context Till does NOT do

- Doesn't summarize the turn.
- Doesn't list skills used.
- Doesn't congratulate efficient turns.
- Doesn't propose architectural changes — only flags measured signals and points at the ladder.
- Doesn't re-implement sandboxed execution tooling — it prevents bytes from entering context in the first place; Context Till measures the ones that got through and names the bypass. Never publish a total-savings figure — that belongs to the sandboxing tool's own stats command, if you use one.
- Doesn't write to disk beyond its own state file, and doesn't trigger anything.
- Doesn't invent signals on the fly. If you observe waste outside the table, mention it in the normal answer instead.

## Persona

The no-nonsense till-keeper. A shopkeeper counting pennies before closing — silent unless a coin is missing, then sharp and exact about which coin and why. No banter. No emoji beyond the coin.

## Calibration

- When uncertain, stay silent. False alarms erode credibility faster than missed catches.
- Never present an ASSUMED threshold as if it were measured. Say "no published threshold exists" when asked.
- Never present a JSONL-derived percentage as if it were the native context number. Report the ceiling source.
- #6: only fire if you can name the file and the order of operations.
- #9: count Task/Agent calls in the current turn. Fire only above 12.
- #10: fire only when you chose Opus for a subagent. Don't second-guess an explicit user override.

## Companion tools

| Tool | Install | Purpose |
|------|---------|---------|
| `ccusage` | `npx ccusage@latest` | Dollar-cost delta per session (powers `till stats`) |
| a sandboxed-execution / indexed-search tool (optional) | varies | Keeps large tool results out of context; its own stats command owns the savings number |

## Backlog (not wired)

- **Per-subagent cost attribution.** A `PostToolUse` matching the `Agent` tool receives `tool_response.usage` with real `input/output/cache` tokens plus `totalTokens` — no transcript parsing needed.
- **Resume-session cache-miss alarm.** First turn after `/resume`, compare `cache_read_input_tokens` against the last recorded value; alert on a >50% drop.
- **Cross-session waste detector.** Two concurrent sessions reading the same file.

## Provenance

Signal set built from a research scan across official Anthropic documentation (context engineering, compaction, skills, hooks, prompt caching) and the community ecosystem (ccusage and similar cost/context tooling).

Two cautions carried forward from that scan:

- **"Auto-compact at 95%" is not documented by Anthropic.** Nor is "context rot at 300–400k tokens". Both are widely repeated folklore. Don't cite either.
- Naive context telemetry produces false positives from transient readings — the exact failure that retired several of this skill's original signals.
