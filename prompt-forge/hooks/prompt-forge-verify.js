#!/usr/bin/env node
/**
 * prompt-forge-verify.js — Stop hook
 *
 * Companion enforcement for prompt-forge-gate.js (UserPromptSubmit).
 *
 * The gate INJECTS the forge contract. Nothing verified that it was followed,
 * so the contract was advisory: on 2026-07-26 a turn opened by stating the skip
 * "would be wrong", then skipped anyway — superpowers:using-superpowers claims
 * "invoke skills BEFORE any response", which swallowed contract steps 3-4 into
 * brainstorming's question loop. This hook closes that hole.
 *
 * Compliance is detected from the `Skill` tool_use RECORD, never from prose.
 * Prose was the loophole: the previous failure announced its own violation in
 * fluent English and a text scan would have accepted the announcement.
 *
 * Passes (silent) when ANY hold:
 *   - stop_hook_active            (already blocked once — never loop)
 *   - this promptId was blocked before (cross-event guard)
 *   - prompt carries #noforge / !raw / #forged, or is a slash command
 *   - the turn is trivial: <= TRIVIAL_TOOL_MAX tool calls and no subagent dispatch
 *   - a Skill tool_use with skill matching /prompt-forge/ exists in the turn
 *
 * Fails OPEN on any error. A broken verifier must never block real work.
 */

const fs = require('fs');
const os = require('os');
const path = require('path');

const TRIVIAL_TOOL_MAX = 2;
const DISPATCH_TOOLS = /^(Agent|Task|Workflow)$/;
const BYPASS = /#noforge|!raw|#forged/i;
const SLASH_COMMAND = /^\s*\//;
const STATE_DIR = path.join(os.tmpdir(), 'prompt-forge-verify');

const pass = () => {
  process.stdout.write(JSON.stringify({ continue: true, suppressOutput: true }) + '\n');
  process.exit(0);
};

const block = (reason) => {
  process.stdout.write(JSON.stringify({ decision: 'block', reason }) + '\n');
  process.exit(0);
};

/** Pull plain text out of a message.content that may be string or block array. */
function textOf(content) {
  if (typeof content === 'string') return content;
  if (!Array.isArray(content)) return '';
  return content
    .filter((b) => b && b.type === 'text' && typeof b.text === 'string')
    .map((b) => b.text)
    .join('\n');
}

/**
 * A real, human-typed prompt — NOT a tool_result and NOT a skill-body injection.
 * Skill bodies arrive as type:"user" with text content and would otherwise match
 * the bypass patterns (they legitimately contain `#forged`, `last_verified:`).
 * `origin.kind === "human"` is the only field that separates them cleanly.
 */
function isHumanPrompt(o) {
  return (
    o &&
    o.type === 'user' &&
    !o.isSidechain &&
    o.origin &&
    o.origin.kind === 'human'
  );
}

let raw = '';
process.stdin.on('data', (c) => (raw += c));
process.stdin.on('end', () => {
  try {
    const input = JSON.parse(raw || '{}');

    if (input.stop_hook_active) pass();

    const transcriptPath = input.transcript_path;
    if (!transcriptPath || !fs.existsSync(transcriptPath)) pass();

    const lines = fs.readFileSync(transcriptPath, 'utf8').trim().split('\n');
    const entries = [];
    for (const l of lines) {
      try {
        const o = JSON.parse(l);
        if (!o.isSidechain) entries.push(o);
      } catch {
        /* skip malformed line */
      }
    }

    // Locate the turn: everything after the last human prompt.
    let turnStart = -1;
    for (let i = entries.length - 1; i >= 0; i--) {
      if (isHumanPrompt(entries[i])) {
        turnStart = i;
        break;
      }
    }
    if (turnStart === -1) pass();

    const promptEntry = entries[turnStart];
    const promptText = textOf(promptEntry.message && promptEntry.message.content);

    if (BYPASS.test(promptText) || SLASH_COMMAND.test(promptText)) pass();

    // Cross-event guard: never block the same prompt twice, even if
    // stop_hook_active is absent on a later Stop for the same prompt.
    const promptId = promptEntry.promptId || promptEntry.uuid || '';
    const marker = promptId
      ? path.join(STATE_DIR, promptId.replace(/[^\w.-]/g, '_'))
      : '';
    if (marker && fs.existsSync(marker)) pass();

    // Walk the turn, tallying tool use.
    let toolCount = 0;
    let dispatched = false;
    let forged = false;

    for (let i = turnStart + 1; i < entries.length; i++) {
      const o = entries[i];
      if (o.type !== 'assistant') continue;
      const content = o.message && o.message.content;
      if (!Array.isArray(content)) continue;
      for (const b of content) {
        if (!b || b.type !== 'tool_use') continue;
        toolCount++;
        if (DISPATCH_TOOLS.test(b.name)) dispatched = true;
        if (
          b.name === 'Skill' &&
          b.input &&
          /prompt-forge/i.test(String(b.input.skill || ''))
        ) {
          forged = true;
        }
      }
    }

    if (forged) pass();

    // Triviality escape, measured objectively rather than asserted in prose.
    if (toolCount <= TRIVIAL_TOOL_MAX && !dispatched) pass();

    if (marker) {
      try {
        fs.mkdirSync(STATE_DIR, { recursive: true });
        fs.writeFileSync(marker, String(Date.now()));
      } catch {
        /* marker is best-effort */
      }
    }

    block(
      [
        'Forge contract not satisfied on this turn.',
        '',
        `This turn ran ${toolCount} tool call${toolCount === 1 ? '' : 's'}` +
          `${dispatched ? ' and dispatched a subagent' : ''}, so it is not trivial,`,
        'and no `Skill(prompt-forge)` call appears in the transcript.',
        '',
        'Stating that the forge was skipped does not satisfy the contract — only',
        "the skill invocation does. Per this plugin's standing policy, prompt-forge runs",
        'before any other skill, including superpowers:brainstorming and',
        'superpowers:using-superpowers.',
        '',
        'Invoke prompt-forge now, show the forged prompt in its own fence, then',
        'continue the work you were doing. Do not restart the turn from scratch.',
        '',
        'If this turn genuinely did not warrant forging, say so in one line and stop —',
        'this check will not fire again for this prompt.',
      ].join('\n')
    );
  } catch {
    pass(); // fail open, always
  }
});
