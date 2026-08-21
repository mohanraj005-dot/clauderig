#!/usr/bin/env node
// till-precompact.js — PreCompact hook (feeds context-till signal #19)
//
// Counts how many times this session has been compacted, so #19 can tell the
// difference between "context is large" and "context has already been
// summarised twice and is now lossy".
//
// Why the count matters: after each compaction Claude Code re-injects skill
// bodies but caps them at 5,000 tokens per skill and 25,000 total, dropping
// the oldest first (documented 2026-07-26). A twice-compacted session has
// provably lost skill bodies it thinks it still has. That is the closest thing
// to a measurable quality signal available — no degradation curve is published.
//
// ─────────────────────────────────────────────────────────────────────────────
// THIS HOOK MUST NEVER BLOCK. Blocking a compaction that is recovering from an
// already-returned context-limit API error surfaces that error and FAILS THE
// REQUEST. PreCompact's only output surface is a block decision, so the correct
// design is to emit no JSON at all — ever. There is deliberately no code path
// here that writes to stdout.
//
// Verify (comments stripped, so the prohibition text above is not counted):
//   node -e 'const s=require("fs").readFileSync("till-precompact.js","utf8")
//     .replace(/\/\*[\s\S]*?\*\//g,"").split("\n").filter(l=>!/^\s*\/\//.test(l)).join("\n");
//     console.log((s.match(/stdout|decision/g)||[]).length)'   → must print 0
// ─────────────────────────────────────────────────────────────────────────────
//
// Disable: export TILL_CTX_DISABLE=1

if (process.env.TILL_CTX_DISABLE === '1') process.exit(0);

const fs   = require('fs');
const path = require('path');
const os   = require('os');

const HOME    = process.env.HOME || process.env.USERPROFILE || os.homedir();
const CTX_DIR = path.join(HOME, '.claude', '.context-till');

// Per-session state file — see till-overhead.js for why this is a directory
// keyed by session id rather than one shared file.
function sanitizeId(id) { return String(id || '').replace(/[^A-Za-z0-9_-]/g, '') || '_nosession'; }
function statePath(sessionId) { return path.join(CTX_DIR, sanitizeId(sessionId) + '.json'); }

let raw = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', c => { raw += c; });
process.stdin.on('end', () => {
  try {
    let data = {};
    try { data = JSON.parse(raw) || {}; } catch (_) {}
    const sessionId  = data.session_id || '';
    const STATE_FILE = statePath(sessionId);

    let state = {};
    try { state = JSON.parse(fs.readFileSync(STATE_FILE, 'utf8')) || {}; } catch (_) {}

    state.compactions = (typeof state.compactions === 'number' ? state.compactions : 0) + 1;
    state.last_compact_trigger = data.trigger === 'manual' ? 'manual' : 'auto';

    // The rate baseline is meaningless across a compaction boundary — context
    // drops discontinuously. Clear it so #16 rebuilds instead of reporting a
    // huge negative delta.
    delete state.used_prev;
    delete state.ema_delta;

    try {
      fs.mkdirSync(CTX_DIR, { recursive: true });
      fs.writeFileSync(STATE_FILE, JSON.stringify(state));
    } catch (_) {}
  } catch (_) { /* fail open */ }

  // Silent by construction. Nothing is written to stdout, so this hook cannot
  // alter, delay, or block the compaction it observes.
  process.exit(0);
});
