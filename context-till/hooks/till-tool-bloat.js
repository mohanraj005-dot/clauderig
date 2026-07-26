#!/usr/bin/env node
// till-tool-bloat.js — PostToolUse hook (context-till signals #17, #18)
//
// #17 — a single tool call returned enough bytes to matter.
// #18 — it did so when context-mode offered a sandboxed alternative that would
//       have kept those bytes out of the window entirely.
//
// SCOPE: this hook only ever measures the SIZE of a tool result. It never reads
// the content, never logs it, and never rewrites it.
//
// ─────────────────────────────────────────────────────────────────────────────
// DELIBERATELY NOT IMPLEMENTED: output truncation.
//
// PostToolUse can fully replace a tool result via
// hookSpecificOutput.updatedToolOutput. It is not used here, by decision.
// Two reasons:
//   1. Edit requires the file's exact bytes in context to match against.
//      Truncating a Read silently breaks the Edit that follows, and the model
//      gets no signal explaining why.
//   2. The tool has already executed by the time this hook fires. Truncation
//      changes only what the model sees — it saves no work and undoes no side
//      effect.
// The string "updatedToolOutput" must not appear in CODE below this block.
// Verify (comments stripped, so this block is not counted):
//   node -e 'const s=require("fs").readFileSync("till-tool-bloat.js","utf8")
//     .replace(/\/\*[\s\S]*?\*\//g,"").split("\n").filter(l=>!/^\s*\/\//.test(l)).join("\n");
//     console.log((s.match(/updatedToolOutput/g)||[]).length)'   → must print 0
// ─────────────────────────────────────────────────────────────────────────────
//
// Disable:   export TILL_CTX_DISABLE=1
// Threshold: export TILL_CTX_BLOAT_CHARS=20000   (default 20000, ASSUMED —
//            no documented per-tool-result size cap exists to derive it from)

if (process.env.TILL_CTX_DISABLE === '1') process.exit(0);

const fs   = require('fs');
const path = require('path');
const os   = require('os');

const HOME        = process.env.HOME || process.env.USERPROFILE || os.homedir();
const STATE_FILE  = path.join(HOME, '.claude', '.context-till-state.json');
const BLOAT_CHARS = parseInt(process.env.TILL_CTX_BLOAT_CHARS || '20000', 10);

// Raw tool → the context-mode tool that would have kept the bytes in the
// sandbox. Only tools with a real alternative can trigger #18.
const CTX_ALTERNATIVE = {
  Bash:     'ctx_batch_execute',
  Read:     'ctx_execute_file',
  Grep:     'ctx_batch_execute',
  Glob:     'ctx_batch_execute',
  WebFetch: 'ctx_fetch_and_index',
};

// Size a tool_response without ever inspecting its content.
function responseSize(resp) {
  if (resp == null) return 0;
  if (typeof resp === 'string') return resp.length;
  try { return JSON.stringify(resp).length; } catch (_) { return 0; }
}

// Read-before-Edit is mandatory, not waste: Edit needs the exact bytes.
// Track recent Read paths so a Read that is about to be edited is exempt. The
// exemption is applied on the Edit side: when an Edit/Write lands on a path
// that was just Read, that Read's earlier warning is not repeated.
function noteRead(state, p) {
  if (!p) return;
  state.recent_reads = (state.recent_reads || []).filter(r => r !== p).concat(p).slice(-12);
}
function wasRecentlyRead(state, p) {
  return !!p && (state.recent_reads || []).includes(p);
}

let raw = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', c => { raw += c; });
process.stdin.on('end', () => {
  try {
    let data = {};
    try { data = JSON.parse(raw) || {}; } catch (_) {}

    const tool = data.tool_name || '';
    if (!tool) process.exit(0);

    const sessionId = data.session_id || '';
    let state = {};
    try { state = JSON.parse(fs.readFileSync(STATE_FILE, 'utf8')) || {}; } catch (_) {}
    if (state.session_id !== sessionId) state = { session_id: sessionId };

    const target = data.tool_input?.file_path || data.tool_input?.path || '';

    // An Edit/Write on a recently-Read path retroactively justifies that Read.
    if (/^(Edit|Write|MultiEdit|NotebookEdit)$/.test(tool)) {
      if (wasRecentlyRead(state, target)) {
        state.read_justified = (state.read_justified || []).concat(target).slice(-12);
      }
      try { fs.writeFileSync(STATE_FILE, JSON.stringify(state)); } catch (_) {}
      process.exit(0);
    }

    const size = responseSize(data.tool_response);
    if (tool === 'Read') noteRead(state, target);
    try { fs.writeFileSync(STATE_FILE, JSON.stringify(state)); } catch (_) {}

    if (size < BLOAT_CHARS) process.exit(0);

    const alt   = CTX_ALTERNATIVE[tool];
    const kTok  = Math.round(size / 4 / 100) / 10;
    const where = target ? ` (${path.basename(target)})` : '';

    // #18 when a sandboxed alternative existed, #17 otherwise. Never both —
    // one line per offence is the contract.
    const line = alt
      ? `🪙 #18 — ${tool}${where} returned ~${kTok}k tok of raw bytes; ${alt} would have kept them in the sandbox`
      : `🪙 #17 — ${tool}${where} returned ~${kTok}k tok in one call; narrow the query or derive the answer in code`;

    process.stdout.write(JSON.stringify({
      hookSpecificOutput: {
        hookEventName: 'PostToolUse',
        additionalContext: `[Context Till]\n  ${line}\n`,
      },
    }));
  } catch (_) { /* fail open — a sizing hook must never break a tool call */ }
  process.exit(0);
});
