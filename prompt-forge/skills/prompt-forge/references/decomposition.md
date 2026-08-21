# Decomposition & delegation (step 6.5)

A prompt that hands one agent five unrelated jobs is not a strong prompt run
serially — it is a **weaker** prompt. Each unrelated workstream dilutes the
context window, and every finding from workstream A becomes noise while the model
works on workstream E. Fan-out is a context-*reduction* move before it is a
speed move.

This file is the full spec for pipeline step 6.5. SKILL.md carries the summary.

---

## Part 1 — Decompose

### The independence test

Two candidate workstreams are independent when **all four** hold:

| # | Test | Fails when |
|---|---|---|
| 1 | **No shared mutable state** | Both edit the same file, table, or branch |
| 2 | **No output dependency** | B's prompt needs A's answer to be written |
| 3 | **No ordering requirement** | B must not run before A for correctness |
| 4 | **Separately verifiable** | You cannot state a pass/fail for one alone |

Fail any test → they are one workstream, not two. Test 1 has an escape hatch:
shared mutable state is survivable if each agent gets an isolated worktree, but
that costs setup time and disk, so only reach for it when the parallel win is
real.

### The fan-out rule

```
independent workstreams >= 2  ->  one agent per workstream,
                                  dispatched in a SINGLE message
independent workstreams  = 1  ->  single-thread, and STATE THE REASON
```

Escaping to single-thread silently is a defect. The forged prompt must name
which condition applied: *"single-thread — one file, read-only, no research."*

### Shape selection

| Shape | Use when | Cost of getting it wrong |
|---|---|---|
| **Single-thread** | One domain, read-only or <=2 tool calls, no sweep | Slow only if genuinely parallel work was serialised |
| **Flat fan-out** | N independent workstreams, results merged once at the end | Barrier latency: the merge waits on the slowest agent |
| **Pipeline** | Each item passes through the same stages, items are independent of one another | None — this is the default for multi-stage work over a list |
| **Fan-out then verify** | Findings must be adversarially checked before they are reported | Plausible-but-wrong findings ship unverified |
| **Judge panel** | The solution space is wide and one attempt will under-explore it | You get the first idea rather than the best one |

Default to **pipeline** over flat fan-out whenever stages exist. A barrier is
justified only when stage N genuinely needs *all* of stage N-1 — dedup across a
whole result set, an early exit on a zero count, or a prompt that compares
findings against each other. "I need to flatten the list first" is not a barrier.

### Sizing

| Signal | Agent count |
|---|---|
| "check X" / "find any bugs" | 2–4 |
| "review this properly" | 4–8 |
| "audit this" / "be comprehensive" | 8–15, plus a verify pass |
| Unknown-size discovery | loop until 2 consecutive rounds return nothing new |

Never price a subagent in dollars — no documented per-subagent overhead figure
exists (this rule is inherited from step 8.5). Recommend a **cap**, not a cost.

---

## Part 2 — Delegate

### The skill-selection rule

> A relevant installed skill is **not optional**. If a skill owns the workstream,
> the forged prompt names it. If no skill owns it, say so explicitly rather than
> leaving the row blank.

### Ground the inventory first — do not trust the session listing

The session's skill listing is **not** a reliable inventory. It is budget-capped
(~25k tokens) and the installed set exceeds it, so descriptions are truncated and
entries can be dropped entirely. Selecting from a truncated listing is how a
forged prompt ends up naming a near-miss of a real skill.

Read the inventory from disk before assigning any skill:

```bash
# user skills — one directory per skill
ls -1 ~/.claude/skills/

# plugin skills — emitted as plugin:skill, deduped across cached versions
find ~/.claude/plugins/cache -maxdepth 6 -name SKILL.md -path '*/skills/*' \
  | sed -E 's|.*/cache/[^/]+/([^/]+)/[^/]+/skills/([^/]+)/SKILL.md|\1:\2|' \
  | sort -u
```

To confirm one candidate name rather than list everything:

```bash
ls -d ~/.claude/skills/<name> >/dev/null 2>&1 \
  && echo "<name>: INSTALLED" || echo "<name>: NOT INSTALLED"
```

To read what a skill actually claims before assigning it — descriptions in the
session listing may be cut mid-sentence, and the boundary clauses ("Do NOT use
for…") are usually what got cut:

```bash
sed -n '1,20p' ~/.claude/skills/<name>/SKILL.md
```

The plugin `find` is deduped for a reason: a plugin can have several cached
version directories (`unknown`, plus content hashes) and an un-deduped list
reports the same skill three times as three candidates.

### Procedure

1. **List** the workstreams from Part 1.
2. **Ground** the inventory from disk using the commands above. Never assign from
   the session listing alone.
3. **Match** each workstream against that grounded inventory.
4. **Resolve conflicts** by specificity. A skill whose description names the
   exact system beats a general-purpose one. Two skills claiming the same
   workstream means the boundary is wrong — pick the narrower and note it. Read
   the boundary clauses before deciding; that is where the answer usually is.
5. **Verify the name exists**, exactly as written, against the grounded list. A
   forged prompt that invokes a skill which is not installed fails at runtime and
   is worse than one that invokes nothing.
6. **Record** the assignment in the Execution shape output block.

### Process skills come first

Where a process skill and an implementation skill both apply, the process skill
sets the approach and the implementation skill carries it out:

| Trigger | Order |
|---|---|
| "build X" | brainstorming → implementation skill |
| "fix this bug" | systematic-debugging → domain skill |
| "is it done?" | verification-before-completion → the claim |
| production write | the approval gate → the writing skill |

### When no skill owns it

Say `no skill — direct execution` in the Execution shape table. That is a valid
outcome and is more useful than a plausible-sounding wrong skill name.

---

## Worked example

**Raw ask:** *"Write me a prompt that audits our AWS bill, checks the Snowflake
credits, and tells me what to cut."*

**Step 6.5 output:**

```
[execution shape]

DECOMPOSITION: 3 independent workstreams -> flat fan-out, dispatched in one message

| # | Workstream                         | Independent? | Skill                |
|---|------------------------------------|--------------|----------------------|
| 1 | AWS account cost audit             | yes          | aws-cost-finops      |
| 2 | Snowflake credit + warehouse audit | yes          | snowflake-finops     |
| 3 | Code/config-layer cost regressions | yes          | cost-reducer         |

MERGE: one synthesis pass ranks all findings by annualised saving.
BARRIER: justified — the ranking compares findings across all three streams.
CAP: 3 agents. No verify pass; findings are read-only queries, not claims.
```

Note what the lens caught: three *different* skills own three parts of one
sentence. Forging this as a single prompt would have picked one of them and
silently dropped the other two thirds of the ask.

---

## Failure modes

| Failure | Looks like | Fix |
|---|---|---|
| **Over-fan-out** | 4 agents for one read-only file lookup | Apply the triviality escape; state the reason |
| **Phantom skill** | Prompt invokes `aws-cost-auditor` (does not exist) | Verify every name against the **disk** inventory, not the session listing |
| **Truncated-listing pick** | A near-miss name chosen because the real one was cut from the budget-capped listing | Ground from `~/.claude/skills/` before assigning |
| **Silent single-thread** | No Agents row at all | The row is mandatory even when the answer is "1" |
| **Unjustified barrier** | `parallel()` used where a pipeline would do | Barrier only for genuine cross-item dependency |
| **Shared-state collision** | Two agents editing the same file | Merge into one workstream, or isolate per agent |
| **Skill named, never invoked** | Table lists a skill the prompt body ignores | The prompt body must actually instruct the invocation |
