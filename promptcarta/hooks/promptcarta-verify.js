#!/usr/bin/env node
/**
 * promptcarta-verify.js — Stop hook
 *
 * Companion enforcement for promptcarta-gate.js (UserPromptSubmit).
 *
 * The gate INJECTS the forge contract. Nothing verified that it was followed,
 * so the contract was advisory: a turn can open by stating a skip "would be
 * wrong", then skip anyway — superpowers:using-superpowers claims "invoke
 * skills BEFORE any response", which can swallow contract steps 3-4 into
 * brainstorming's question loop. This hook closes that hole.
 *
 * Compliance is detected from the `Skill` tool_use RECORD, never from prose.
 * Prose is the loophole: a failure can announce its own violation in fluent
 * English, and a text scan would accept the announcement.
 *
 * Passes (silent) when ANY hold:
 *   - stop_hook_active            (already blocked once — never loop)
 *   - this promptId was blocked before (cross-event guard)
 *   - prompt carries #noforge / !raw / #forged, or is a slash command
 *   - the turn is trivial: no subagent dispatch, <= TRIVIAL_MUTATION_MAX mutating
 *     calls, and <= READONLY_TOOL_MAX tool calls in total
 *   - a Skill tool_use with skill matching /promptcarta/ exists in the turn
 *
 * Triviality is measured in MUTATIONS, not raw tool count. The gate injects
 * "single domain · read-only OR <= 2 tool calls · no research and no
 * cross-file sweep". Counting every Read/Grep implements only the second half
 * of that disjunction, so a read-only multi-call investigation reads as
 * trivial by the contract the model was handed and non-trivial by the hook
 * grading it — the model follows the gate's prose and gets blocked by its
 * sibling anyway. Mutation-counting closes that gap: every subagent dispatch
 * and every >2-mutation turn still blocks, but a read-only sweep of a few
 * extra files no longer does.
 *
 * Known trade-off: a multi-domain READ-ONLY research turn of <= READONLY_TOOL_MAX
 * calls skips the forge silently. That is deliberate — the gate's own text
 * already classifies read-only work as trivial.
 *
 * Fails OPEN on any error. A broken verifier must never block real work.
 */

const fs = require('fs');
const os = require('os');
const path = require('path');

const TRIVIAL_MUTATION_MAX = 2;
const READONLY_TOOL_MAX = 8;
const DISPATCH_TOOLS = /^(Agent|Task|Workflow)$/;
const MUTATOR_TOOLS = /^(Edit|Write|MultiEdit|NotebookEdit)$/;
const BYPASS = /#noforge|!raw|#forged/i;
const SLASH_COMMAND = /^\s*\//;
const STATE_DIR = path.join(os.tmpdir(), 'promptcarta-verify');

const pass = () => {
  process.stdout.write(JSON.stringify({ continue: true, suppressOutput: true }) + '\n');
  process.exit(0);
};

const block = (reason) => {
  process.stdout.write(JSON.stringify({ decision: 'block', reason }) + '\n');
  process.exit(0);
};

/**
 * Local state change. The git branch matches `git` at a command position
 * followed by a mutating subcommand ANYWHERE later on the line, rather than
 * immediately after `git` — that is what admits `git -c credential.helper=... push`,
 * `git -C <path> commit` and `git --no-pager push`, none of which a simple
 * `\bgit\s+push\b` shape would catch.
 *
 * The scan deliberately is NOT bounded by `;` `|` `&`. A quoted argument can
 * itself contain those characters, so a segment-bounded scan can stop before
 * it ever reaches the mutating verb. The accepted cost is an occasional false
 * positive on shapes like `git status | grep push`; over-matching costs one
 * extra forge invocation, while under-matching is a silent hole — so this
 * regex is deliberately biased toward the former.
 *
 * Requiring whitespace before the verb keeps `--grep=push` and `--format=commit`
 * out. `pull`, `switch` and `restore` are included because they rewrite the
 * working tree — `git pull` is how a deploy lands on a remote host, and its
 * absence is why a bare `ssh host "git pull"` would otherwise score clean.
 *
 * The redirect alternative excludes `/dev/null` and fd dups (`2>&1`) by
 * requiring a non-`&`, non-`/`, non-space character after `>` — discarding
 * output is the opposite of writing state.
 */
const MUT_LOCAL =
  /(^|[\s;&|("'`])(rm|rmdir|mv|cp|mkdir|touch|tee|chmod|chown|ln|dd|truncate)\b|\bsed\s+-i\b|\bperl\s+-i\b|(^|[\s;&|("'`])git\b[^\n]*\s(add|commit|push|pull|rebase|reset|checkout|switch|restore|revert|cherry-pick|stash|merge|tag|apply|clean|submodule|worktree)\b|\bnpm\s+(i|install|publish|link)\b|\bpip\s+install\b|\bcurl\b[^|]*\s-[a-zA-Z]*o\b|>>?\s*(?!\/dev\/null\b)[^&\s]/;

/**
 * Reaches another machine or a remote service. Always a mutation regardless of
 * what else the command does: `scp` and `rsync` exist to move bytes, and a
 * push, a PR, a release or a non-GET HTTP call is outward-facing by definition.
 *
 * `ssh` is NOT here on purpose — see bashMutates below.
 */
const OUTWARD =
  /(^|[\s;&|("'`])(scp|rsync)\b|(^|[\s;&|("'`])git\b[^\n]*\spush\b|(^|[\s;&|("'`])gh\s+(pr|release|api|repo\s+(create|delete))\b|\bcurl\b[^|]*-X\s*(POST|PUT|PATCH|DELETE)\b/i;

/**
 * Does this shell command change state locally or remotely?
 *
 * `ssh` is handled by inspecting what it was asked to run rather than by
 * matching the word itself. Treating every `ssh` as a mutation would flag
 * read-only remote checks like `ssh host 'git status'` or `ssh host date` —
 * so instead it recurses into the remote command with the same rules.
 */
function bashMutates(cmd) {
  const s = String(cmd || '');
  if (OUTWARD.test(s) || MUT_LOCAL.test(s)) return true;
  const m = s.match(/(^|[\s;&|("'`])ssh\s+/);
  if (m) {
    const remote = s.slice(m.index + m[0].length);
    return OUTWARD.test(remote) || MUT_LOCAL.test(remote);
  }
  return false;
}

/** Does this tool_use block change state on disk or in a remote system? */
function isMutation(b) {
  if (!b || !b.name) return false;
  if (MUTATOR_TOOLS.test(b.name)) return true;
  if (b.name === 'Bash') return bashMutates(b.input && b.input.command);
  return false;
}

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
    let mutations = 0;
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
        if (isMutation(b)) mutations++;
        if (
          b.name === 'Skill' &&
          b.input &&
          /promptcarta/i.test(String(b.input.skill || ''))
        ) {
          forged = true;
        }
      }
    }

    if (forged) pass();

    // Triviality escape, measured objectively rather than asserted in prose.
    // Mirrors the gate's own clause: single domain · read-only OR <= 2 calls ·
    // no research (dispatch) and no cross-file sweep (READONLY_TOOL_MAX).
    if (!dispatched && mutations <= TRIVIAL_MUTATION_MAX && toolCount <= READONLY_TOOL_MAX) {
      pass();
    }

    if (marker) {
      try {
        fs.mkdirSync(STATE_DIR, { recursive: true });
        fs.writeFileSync(marker, String(Date.now()));
      } catch {
        /* marker is best-effort */
      }
    }

    const why = dispatched
      ? 'it dispatched a subagent'
      : mutations > TRIVIAL_MUTATION_MAX
        ? `it made ${mutations} mutating calls (limit ${TRIVIAL_MUTATION_MAX})`
        : `it ran ${toolCount} tool calls (limit ${READONLY_TOOL_MAX})`;

    block(
      [
        'Forge contract not satisfied on this turn.',
        '',
        `This turn is not trivial — ${why},`,
        'and no `Skill(promptcarta)` call appears in the transcript.',
        '',
        'Stating that the forge was skipped does not satisfy the contract — only',
        "the skill invocation does. Per this plugin's standing policy, promptcarta runs",
        'before any other skill, including superpowers:brainstorming and',
        'superpowers:using-superpowers.',
        '',
        'Invoke promptcarta now, show the forged prompt in its own fence, then',
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
