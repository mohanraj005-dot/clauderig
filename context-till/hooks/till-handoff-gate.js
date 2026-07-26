#!/usr/bin/env node
// till-handoff-gate.js — Stop hook (context-till Signal #14)
//
// When a single task runs longer than the threshold (default 3 min), this hook
// blocks the stop ONCE and instructs Claude to OFFER the user a handoff-vs-resume
// choice via AskUserQuestion — it does NOT auto-generate the snapshot. The user
// picks: emit a session-handoff-style snapshot now, or keep the session open.
//
// Turn-start time comes from ~/.claude/.last_turn_ts. That file is OPTIONAL and
// EXTERNAL to this plugin: some setups have a UserPromptSubmit router hook that
// writes it at the start of every turn (elapsed = now - last_turn_ts = full task
// duration). This plugin does not ship that router. If the file is absent, the
// time arm below simply never fires — see the graceful-degradation note at
// isNaN(startTs) — it does not error or crash.
//
// The context arm (below) similarly reads .context-till-state.json fields
// (used_prev, ceiling, ema_delta) that, on this plugin alone, are only ever
// populated by till-overhead.js (ceiling) and cleared by till-precompact.js.
// A fuller router hook could populate used_prev/ema_delta every turn for a
// richer signal; without one, contextArm() simply has less to work with and
// returns null — again, absent state means "skip this arm", never a crash.
//
// Disable:   export TILL_HANDOFF_DISABLE=1
// Threshold: export TILL_HANDOFF_THRESHOLD_SEC=300   (default 180)

if (process.env.TILL_HANDOFF_DISABLE === '1') process.exit(0);

const fs   = require('fs');
const path = require('path');
const os   = require('os');

const HOME       = process.env.HOME || process.env.USERPROFILE || os.homedir();
const TS_FILE    = path.join(HOME, '.claude', '.last_turn_ts');              // turn START (optional; written by an external router hook if present)
const MARK_FILE  = path.join(HOME, '.claude', '.context-till-handoff-fired'); // dedupe: turn-start ts already offered
const STATE_FILE = path.join(HOME, '.claude', '.context-till-state.json');    // shared with till-overhead.js / till-tool-bloat.js / till-precompact.js
const THRESHOLD  = parseInt(process.env.TILL_HANDOFF_THRESHOLD_SEC || '180', 10);

// Second arm: context budget nearly spent. Fires when the burn rate leaves
// fewer than this many turns before auto-compact. Deliberately tighter than
// an advisory-level #16 (default 8) some setups compute elsewhere — by the
// time we are blocking a stop, an earlier advisory has already been ignored
// for several turns.
const TURNS_BLOCK = parseInt(process.env.TILL_CTX_TURNS_BLOCK || '3', 10);

// Returns a reason string when the context budget warrants offering a handoff,
// else null. Reads only shared state — no transcript parsing, no second
// opinion on the numbers. If used_prev/ema_delta were never populated (no
// external hook wrote them this session), this simply returns null.
function contextArm() {
  if (process.env.TILL_CTX_DISABLE === '1') return null;
  try {
    const s = JSON.parse(fs.readFileSync(STATE_FILE, 'utf8')) || {};
    const used = s.used_prev, ceiling = s.ceiling, ema = s.ema_delta;
    if (typeof used !== 'number' || typeof ceiling !== 'number' || ceiling <= 0) return null;

    const pct = Math.round((used / ceiling) * 100);

    if (typeof ema === 'number' && ema > 0) {
      const turnsLeft = Math.floor((ceiling - used) / ema);
      if (turnsLeft >= 0 && turnsLeft <= TURNS_BLOCK) {
        return `context budget ${pct}% used, ~${turnsLeft} turns before auto-compact at this burn rate`;
      }
    }
    if (pct >= 85) return `context budget ${pct}% used`;
  } catch (_) {}
  return null;
}

let raw = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', c => { raw += c; });
process.stdin.on('end', () => {
  let data = {};
  try { data = JSON.parse(raw); } catch (_) {}

  // Anti-loop guard #1: already inside a hook-induced continuation (the
  // AskUserQuestion + answer + reply cycle this hook itself triggered).
  if (data.stop_hook_active) process.exit(0);

  // Need a turn-start timestamp to measure elapsed wall-clock for this task.
  // Absent file (no external router hook writing it) → skip the time arm.
  let startTs = NaN;
  try { startTs = parseInt(fs.readFileSync(TS_FILE, 'utf8').trim(), 10); } catch (_) {}
  if (isNaN(startTs)) process.exit(0);

  // Two independent arms; either one is enough to offer a handoff.
  const elapsedSec = (Date.now() - startTs) / 1000;
  const timeArm   = elapsedSec >= THRESHOLD;
  const ctxReason = contextArm();
  if (!timeArm && !ctxReason) process.exit(0);

  // Anti-loop guard #2: marker keyed to this turn's start — only offer once per task.
  try {
    if (fs.existsSync(MARK_FILE)) {
      const fired = parseInt(fs.readFileSync(MARK_FILE, 'utf8').trim(), 10);
      if (fired === startTs) process.exit(0);
    }
  } catch (_) {}
  try { fs.writeFileSync(MARK_FILE, String(startTs)); } catch (_) {}

  const mins   = Math.max(1, Math.round(elapsedSec / 60));
  const thrMin = Math.round(THRESHOLD / 60);

  // Whichever arm fired decides the wording. When both fire, context leads —
  // it is the one with a hard ceiling behind it.
  const trigger = ctxReason
    ? `[Context Till · Signal #16/#5] ${ctxReason}.`
    : `[Context Till · Signal #14] This task ran ~${mins} min (over the ${thrMin}-min handoff threshold).`;
  const prompt = ctxReason
    ? `${ctxReason.charAt(0).toUpperCase()}${ctxReason.slice(1)}. Session handoff now, or keep working?`
    : `Task ran ~${mins}m. Session handoff now, or keep working?`;

  const reason = [
    trigger,
    `Do NOT auto-generate a handoff. Give the user the choice instead:`,
    `call the AskUserQuestion tool with ONE question — "${prompt}"`,
    `— and exactly these options:`,
    `(1) "Handoff & clear" → if a session-handoff-style skill is installed, invoke it: it writes a snapshot to ~/.claude/handoffs/<project>/LATEST.md AND prints it, then tells the user to run /clear (a new session auto-resumes from that file via the till-handoff-resume SessionStart hook — no paste needed). If no such skill is installed, summarize progress manually instead;`,
    `(2) "Keep working" → reply with a single line acknowledging, then stop.`,
    `Emit nothing besides the AskUserQuestion (and the handoff snapshot if chosen): no routing block, no summary, no context-till ledger.`
  ].join(' ');

  process.stdout.write(JSON.stringify({ decision: 'block', reason }));
  process.exit(0);
});
