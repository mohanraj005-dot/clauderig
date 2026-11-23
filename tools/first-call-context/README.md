# first-call-context

Shows how much context Claude Code loads at the start of each session, from your own logs.

It reads `~/.claude/projects/**/*.jsonl` and takes the first API call of each session:
input + cache write + cache read tokens.

- Read-only, standard library only, no network calls.
- Prints dates, counts and token totals. It does not print prompts, file contents or project names.
- Subagent logs are left out unless you pass `--include-subagents`.

## Run it

```bash
python3 first_call_context.py
```

Compare two periods on one model and Claude Code version:

```bash
python3 first_call_context.py --before 2026-10-08:2026-10-11 --after 2026-10-13:2026-10-21 --model haiku --version 2.1.293
```

Limit it to one project or repeated job with `--path-contains TEXT`.

## Reading the result

Compare like with like. A median across mixed work can move because the work changed,
so filter to one model, one version and, where you can, one kind of job.

## Test

```bash
python3 -m unittest test_first_call_context
```
