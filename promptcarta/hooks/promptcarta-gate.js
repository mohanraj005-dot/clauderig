#!/usr/bin/env node
/**
 * promptcarta-gate.js — UserPromptSubmit hook
 *
 * Injects the standing "forge before you execute" contract on every prompt.
 * May run alongside other UserPromptSubmit hooks; emits its own <system-reminder>
 * block and does not modify or suppress theirs.
 *
 * Bypass: put `#noforge` or `!raw` anywhere in the prompt.
 * Skipped automatically when the prompt is already an explicit /promptcarta call.
 *
 * Target model facts live in this skill's references/models/claude.md (bundled
 * with this plugin) — AUTHORITATIVE, last_verified 2026-07-26. This hook states
 * no model facts itself.
 */

const BYPASS = /#noforge|!raw/i;
const ALREADY_FORGING = /^\s*\/promptcarta\b/i;

/**
 * Recursion guard, layer 1 — inbound.
 * Fires when the submitted text is itself promptcarta output: the user pasting
 * a forged prompt back in, or a forged prompt arriving through a scheduled task
 * or /loop. Forging a forged prompt degrades it — the second pass re-reads
 * already-resolved constraints as fresh ambiguity and re-asks settled questions.
 */
const ALREADY_FORGED = [
  /#forged\b/i, // explicit marker the user can paste
  /^\s*###\s*\d\.\s*(Target|The prompt)\b/im, // promptcarta output block headers
  /\blast_verified:\s*\d{4}-\d{2}-\d{2}/i, // a cited model-file stamp
];

let raw = '';
process.stdin.on('data', (c) => (raw += c));
process.stdin.on('end', () => {
  let prompt = '';
  try {
    prompt = (JSON.parse(raw || '{}').prompt || '').toString();
  } catch {
    prompt = '';
  }

  const isForged = ALREADY_FORGED.some((re) => re.test(prompt));

  if (BYPASS.test(prompt) || ALREADY_FORGING.test(prompt) || isForged) {
    process.stdout.write(
      JSON.stringify({ continue: true, suppressOutput: true }) + '\n'
    );
    process.exit(0);
  }

  process.stdout.write(`<system-reminder>

═══ PROMPTCARTA GATE — standing, every session ═══

Before executing this request, run it through the \`promptcarta\` skill and act on
the forged version, not the raw text.

| Step | Action |
|---|---|
| 1 | Invoke \`promptcarta\` (FORGE mode) on the user's message. |
| 2 | If the task, the output contract, or the success criteria are not falsifiable from the message, ask up to 3 questions in ONE AskUserQuestion call, then forge. |
| 3 | Show the forged prompt in its own fenced block — nothing else inside the fence. |
| 4 | Execute the forged prompt in the same turn. Do not wait for approval. |
| 5 | If the forged reading differs materially from the literal request, say so in one line before executing. |

ONE PASS ONLY. Forge exactly once per user message. The forged prompt is executed,
never re-forged, and \`promptcarta\` is not invoked on any text \`promptcarta\` produced —
including in a later step of this same turn, inside a subagent, or when the forged
prompt is pasted back in. A second pass re-reads settled constraints as fresh
ambiguity and re-asks answered questions. If you are about to forge forged text, stop
and execute it instead.

Defaults when the user names no model: target \`claude-opus-5\`, \`output_config.effort: high\`
(\`xhigh\` for coding or agentic work, per the model file). Read the model file — never
assert a model fact from memory.

SKIP the forge pass, and say in one line that you skipped it, when ALL hold:
single domain · read-only or ≤2 tool calls · no research and no cross-file sweep.
Same triviality escape the Pal contract uses. A greeting, a status check, or a
one-line factual question does not get forged.

Scope discipline: the forged prompt covers what was asked. It does not widen the
task, add deliverables, or spawn subagents the raw request did not warrant.

Bypass for one turn with \`#noforge\`.
</system-reminder>
`);
  process.exit(0);
});
