# clauderig

Five plugins for [Claude Code](https://claude.com/claude-code). Built for daily use first, generalised for release second.

## Install

**From your terminal:**

```bash
claude plugin marketplace add mohanraj005-dot/clauderig
claude plugin install promptcarta@clauderig
```

**Or from inside a Claude Code session** — these are slash commands, typed at the Claude prompt, not in a shell:

```
/plugin marketplace add mohanraj005-dot/clauderig
/plugin install promptcarta@clauderig
```

Every plugin is independent — swap `promptcarta` for any of `context-till`, `entity-naming`, `sketcher`, `risk-critic`, or install several. Check what you're getting before you commit to it:

```bash
claude plugin details promptcarta@clauderig
```

That prints the component inventory and the token cost.

To remove:

```bash
claude plugin uninstall promptcarta@clauderig
```

---

## promptcarta

**The problem it solves:** prompt advice goes stale silently.

*"Set temperature to 0 for determinism"* was reasonable in 2024. On several current models it returns **HTTP 400** — the parameter is rejected outright. That is not a weaker prompt. It is a failed request.

Most prompt tools encode model behaviour in their own logic, which means the tool is confidently wrong the moment a model ships. This one refuses to state a model fact from memory. Every claim reads from a reference file carrying a `last_verified:` date and a `confidence:` field. When a file is stale or unverified, it says so in the output rather than guessing.

That mechanism is where the name comes from: a *carta* is a formal, dated document.

It runs an 11-step pipeline: resolve the exact target model → score the input → extract intent → **stop** if there is no falsifiable success criterion → clarify (max 3 questions) → pick a named architecture → decompose the ask into parallel sub-agents → apply the model-specific transform → scan for dead constructs → apply a cost lens → re-score.

Two of those steps are worth calling out:

- **Decompose & delegate.** A prompt that hands one agent five unrelated jobs is not a strong prompt run serially — it is a weaker one, because every workstream dilutes the others' context. The pipeline runs an independence test and requires a stated *reason* when it stays single-threaded.
- **Cost lens.** A good prompt that costs 5× too much is not a good prompt. It rules on model tier vs task difficulty, effort level, cache-prefix stability against the model's minimum, and fan-out shape. It never prints a per-subagent dollar estimate, because no documented figure exists.

Ships with two hooks: one injects the contract on every prompt, one checks at end-of-turn whether the skill actually ran.

| | |
|---|---|
| Skill | `promptcarta` |
| Hooks | `UserPromptSubmit`, `Stop` |
| Model files | Claude (verified) · OpenAI, Gemini, open-weights, image/video (marked `UNVERIFIED` — they are stubs, and they say so) |

---

## context-till

**The problem it solves:** you cannot see what you are wasting.

Claude Code hooks receive no native token accounting. This works around that: hooks measure session overhead, oversized tool results, repeated reads of files the harness already had, and pre-compaction pressure — then emit a single line at the end of a turn.

The discipline that matters: **it only reports what was actually observed.** Signals it cannot measure are documented as dormant rather than estimated and presented as fact.

State is kept per session, so two Claude Code sessions running against the same project no longer overwrite each other's counters.

| | |
|---|---|
| Skill | `context-till` |
| Hooks | `SessionStart` ×2, `PostToolUse`, `Stop`, `PreCompact` |

---

## entity-naming

Company and brand name generation, then live RDAP domain clearance and India registry/trademark lookups, scored against a fixed rubric. All endpoints are public — no API key needed.

## sketcher

Room dimensions to a to-scale 2D SVG floor plan, with accessibility and egress clearance checks (ADA/IBC or India NBC 2016). Includes a linter that fails the plan, not just warns.

## risk-critic

Two skills that ship together and are deliberately split:

| Skill | What it does |
|---|---|
| **risk-critic** | Adversarially reviews work just produced in-session. Scores by severity and likelihood. **Is not permitted to propose fixes.** |
| **remediation-planner** | Takes what risk-critic found and answers each item with a quick fix, a structural fix, the trade-off, and a verification command. **Is not permitted to raise new risks.** |

Letting one skill both find and fix problems makes it soft on its own findings.

---

## Limitations

Stated plainly, because you should know before installing:

- **The `Stop` hook fails open.** `promptcarta-verify` blocks a turn when the skill should have run and didn't — but if it errors, it lets the turn through. Hook-based enforcement reliability is an open question upstream. Treat it as a nudge, not a guarantee.
- **Model reference files need manual refresh.** That is the design — a dated file that goes stale loudly beats logic that goes stale silently — but nothing refreshes them for you. Check the `last_verified:` date.
- **Only the Claude model file is verified.** The other four are honest stubs marked `UNVERIFIED`.
- **`context-till` has dormant signals.** Six of its documented signals were driven by a router hook that is not part of this release. They are marked dormant rather than removed, so the numbering stays stable.
- **Tested on Claude Code on macOS only.** Hooks invoke `node` from `PATH`.
- **These are opinionated.** They encode one person's working style. Fork and cut what doesn't fit.

## History

This repo was previously `claude-skills`, and `promptcarta` was previously `prompt-forge`. Both names were shared with a number of unrelated projects, so they were changed for clarity. GitHub redirects the old repository URL — but **the plugin name itself changed**, so if you installed `prompt-forge@claude-skills`, uninstall it and install `promptcarta@clauderig`.

The `toolkit` bundle was split into `entity-naming`, `sketcher` and `risk-critic`, which now install independently.

## Contributing

Issues and PRs welcome. If a skill misfires or a model fact is out of date, that is the most useful thing you can report.

## License

Apache-2.0. See [LICENSE](LICENSE).
