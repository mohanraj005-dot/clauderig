# clauderig

A [Claude Code](https://claude.com/claude-code) plugin marketplace with five independent plugins: a model-aware prompt generator, an end-of-turn token-waste auditor, an adversarial review pair, a naming pipeline and a floor-plan tool. Built for daily use first, generalised for release second.

## The five plugins

| Plugin | What it does | Try it |
|---|---|---|
| `promptcarta` | Writes and scores prompts for a specific target model. Reads model behaviour from dated reference files, never from memory, and flags constructs that now return HTTP 400. | `/promptcarta write a prompt for Claude that classifies support tickets` |
| `context-till` | Hooks measure session overhead, oversized tool results and compaction pressure, then print one line at end of turn. Reports only what was observed. | `till check` |
| `risk-critic` | Two skills: `risk-critic` lists risks in work just produced (no fixes allowed); `remediation-planner` answers each with a fix, trade-off and verification command (no new risks allowed). | `poke holes in this` |
| `entity-naming` | Brief intake, name generation, live RDAP domain checks, India MCA and trademark lookup links, scored against a fixed rubric. Public endpoints only, no API key. | `I need a name for my LLP` |
| `sketcher` | Room dimensions to a to-scale 2D SVG floor plan, with a linter that fails on clearance and egress errors (ADA/IBC or India NBC 2016). | `lay out a 30-cover cafe in a 12 m x 8 m unit` |

The commands in the last column are example prompts; skills trigger on the phrases listed in each `SKILL.md` description.

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

## How it's built

```
.claude-plugin/marketplace.json     marketplace manifest: lists the five plugins
<plugin>/.claude-plugin/plugin.json plugin manifest: name, version, description
<plugin>/skills/<skill>/SKILL.md    skill: frontmatter trigger description + instructions
<plugin>/hooks/hooks.json           hook wiring (promptcarta, context-till only)
<plugin>/hooks/*.js                 hook scripts, plain Node.js, no dependencies
scripts/validate.py                 repo validator (see Testing)
```

| Plugin | Skills | Hooks | Bundled scripts and data |
|---|---|---|---|
| `promptcarta` | `promptcarta` | `UserPromptSubmit` (`promptcarta-gate.js`), `Stop` (`promptcarta-verify.js`) | `references/`: pipeline, architectures, cost lens, decomposition, and one file per model family under `references/models/` |
| `context-till` | `context-till` | `SessionStart` (`till-handoff-resume.js`, `till-overhead.js`), `PostToolUse` (`till-tool-bloat.js`), `Stop` (`till-handoff-gate.js`), `PreCompact` (`till-precompact.js`) | per-session state files under `~/.claude/.context-till/` |
| `entity-naming` | `entity-naming` | none | `clear_names.sh` (RDAP clearance), `score_names.py`, `build_board.py`, India registry and genre references |
| `sketcher` | `sketcher` | none | `lint_plan.py`, `render_2d.py`, a JSON plan schema, standards reference, an example cafe plan, `evals/evals.json` (three prompts with expected outputs) |
| `risk-critic` | `risk-critic`, `remediation-planner` | none | none; `risk-critic` disallows `Write`, `Edit` and `NotebookEdit` in its frontmatter |

Design choices that run through the repo:

- **Dated facts, not remembered facts.** `promptcarta` refuses to state a model behaviour unless a reference file carries a `last_verified:` date and a `confidence:` field.
- **Fail open.** Every hook exits cleanly on error; a broken hook must not block a session.
- **Split roles on purpose.** The critic cannot fix and the planner cannot find new risks, so neither grades its own work.
- **No agents or MCP servers.** The repo ships skills and hooks only.

## Testing

There is no unit-test suite. What exists is a structural validator and one lint check, both run in CI (`.github/workflows/validate.yml`):

```bash
python3 scripts/validate.py
python3 sketcher/skills/sketcher/scripts/lint_plan.py sketcher/skills/sketcher/assets/presets/example-cafe.json
claude plugin validate .
```

`scripts/validate.py` (standard library only) checks that every manifest parses and matches its marketplace entry, every hook command points at a file that exists and passes `node --check`, every `SKILL.md` has name and description frontmatter, every Python script compiles, and every repo path mentioned in this README exists. `claude plugin validate` is the Claude Code CLI's own manifest check and is not run in CI. Skill behaviour itself is not tested automatically; `sketcher` carries example prompts in `evals/evals.json` for manual runs.

---

## promptcarta

**The problem it solves:** prompt advice goes stale silently.

*"Set temperature to 0 for determinism"* was reasonable in 2024. On several current models it returns **HTTP 400** — the parameter is rejected outright. That is not a weaker prompt. It is a failed request.

Most prompt tools encode model behaviour in their own logic, which means the tool is confidently wrong the moment a model ships. This one refuses to state a model fact from memory. Every claim reads from a reference file carrying a `last_verified:` date and a `confidence:` field. When a file is stale or unverified, it says so in the output rather than guessing.

That mechanism is where the name comes from: a *carta* is a formal, dated document.

It runs a 9-step pipeline, plus two sub-steps: resolve the exact target model → score the input → extract intent → **stop** if there is no falsifiable success criterion → clarify (max 3 questions) → pick a named architecture → *(6.5)* decompose the ask into parallel sub-agents → apply the model-specific transform → scan for dead constructs → *(8.5)* apply a cost lens → re-score.

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

Until v0.3.1 the marketplace manifest still identified itself as `claude-skills`, so it registered locally under that name even after the repo rename. If you added this marketplace before v0.3.1, run `/plugin marketplace remove claude-skills` and add it again to re-key it as `clauderig`.

## Contributing

Issues and PRs welcome. If a skill misfires or a model fact is out of date, that is the most useful thing you can report.

## License

Apache-2.0. See [LICENSE](LICENSE).
