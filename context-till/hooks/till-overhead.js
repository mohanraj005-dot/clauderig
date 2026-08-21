#!/usr/bin/env node
// till-overhead.js — SessionStart hook (context-till signals #20, #21)
//
// Measures the FIXED context cost paid on every single turn before the user
// types anything: the skill listing, CLAUDE.md, and memory files.
//
// Why this exists: Claude Code budgets the skill listing at ~1% of the context
// window (skillListingBudgetFraction) and caps each entry at 1536 chars
// (skillListingMaxDescChars). On overflow it DROPS descriptions starting with
// the skills you invoke least — silently. A dropped description means that
// skill can never trigger. Nothing else in this setup measures that.
//
// SCOPE HONESTY: this hook can see skills, CLAUDE.md and memory files on disk.
// It CANNOT see MCP tool schemas (they live in the API request, not on disk),
// so #21 reports a measured FLOOR, never a total. It says so in its output.
//
// Fires once per session (deduped via a per-session file under .context-till/).
//
// STATE PARTITION: state lives at ~/.claude/.context-till/<session-id>.json —
// one file per session, never a single shared file. An earlier single-global-
// file design let two concurrent sessions clobber each other's counters (last
// writer wins), which is exactly the failure mode a per-session partition
// rules out by construction. Stale files are pruned after 7 days, here, since
// SessionStart is the only hot-path-free place any of these hooks run.
//
// Disable:    export TILL_CTX_DISABLE=1
// Threshold:  export TILL_CTX_OVERHEAD_PCT=8      (default 8, ASSUMED)

if (process.env.TILL_CTX_DISABLE === '1') process.exit(0);

const fs   = require('fs');
const path = require('path');
const os   = require('os');

const HOME       = process.env.HOME || process.env.USERPROFILE || os.homedir();
const CLAUDE_DIR = path.join(HOME, '.claude');
const CTX_DIR    = path.join(CLAUDE_DIR, '.context-till');
const OVERHEAD_PCT = parseInt(process.env.TILL_CTX_OVERHEAD_PCT || '8', 10);
const PRUNE_MAX_AGE_MS = 7 * 86400000;

function sanitizeId(id) { return String(id || '').replace(/[^A-Za-z0-9_-]/g, '') || '_nosession'; }
function statePath(sessionId) { return path.join(CTX_DIR, sanitizeId(sessionId) + '.json'); }

// SessionStart only — never called from a hot path.
function pruneStaleStateFiles() {
  const now = Date.now();
  try {
    for (const f of fs.readdirSync(CTX_DIR)) {
      if (!f.endsWith('.json')) continue;
      const p = path.join(CTX_DIR, f);
      try { if (now - fs.statSync(p).mtimeMs > PRUNE_MAX_AGE_MS) fs.unlinkSync(p); } catch (_) {}
    }
  } catch (_) {}
}

// Rough chars→tokens. Deliberately crude and always rendered with "~".
// Never use a precise-looking number for an estimate.
const CHARS_PER_TOKEN = 4;

// ── Ceiling: the auto-compact trigger, not the raw window ────────────────────
// Documented (2026-07-26): ~967,000 for 1M-context sessions; 200,000 when 1M
// is off. Overridable via CLAUDE_CODE_AUTO_COMPACT_WINDOW.
// A bridge file written by a statusline command is preferred when present, but
// it does NOT exist under the desktop entrypoint (no statusline runs there),
// so the settings.json model marker is the working fallback: "opus[1m]" → 1M.
function resolveCeiling(sessionId) {
  const env = parseInt(process.env.CLAUDE_CODE_AUTO_COMPACT_WINDOW || '0', 10);
  if (env > 0) return { ceiling: env, src: 'env' };

  try {
    if (sessionId) {
      const bridge = path.join(os.tmpdir(), `claude-ctx-${sessionId}.json`);
      if (fs.existsSync(bridge)) {
        const total = JSON.parse(fs.readFileSync(bridge, 'utf8'))?.context_window?.total_tokens;
        if (typeof total === 'number' && total > 0) {
          return { ceiling: Math.round(total * 0.967), src: 'bridge' };
        }
      }
    }
  } catch (_) {}

  try {
    const model = String(JSON.parse(fs.readFileSync(path.join(CLAUDE_DIR, 'settings.json'), 'utf8')).model || '');
    if (/\[1m\]/i.test(model)) return { ceiling: 967000, src: 'model-marker' };
  } catch (_) {}

  return { ceiling: 200000, src: 'default' };
}

// ── Skill listing measurement ───────────────────────────────────────────────
// Only name + description enter the listing. The body does not (progressive
// disclosure), so measuring whole files would overstate the cost by ~50x.
// Parsed line-by-line, not by regex. Descriptions are routinely multi-line
// (folded or indented continuations), and a lookahead-terminated regex silently
// keeps only the first line — which can meaningfully undercount a real listing.
// Walk until the next top-level `key:` instead.
function frontmatterNameDesc(file) {
  let txt;
  try { txt = fs.readFileSync(file, 'utf8'); } catch (_) { return null; }
  const m = /^---\s*\n([\s\S]*?)\n---\s*\n/.exec(txt);
  if (!m) return null;

  const lines = m[1].split('\n');
  let name = '', desc = '', inDesc = false;

  for (const line of lines) {
    const key = /^([A-Za-z_][A-Za-z0-9_-]*):[ \t]*(.*)$/.exec(line);
    if (key) {
      inDesc = false;
      if (key[1] === 'name') name = key[2].trim();
      else if (key[1] === 'description') { desc = key[2]; inDesc = true; }
    } else if (inDesc) {
      desc += '\n' + line;           // continuation of a multi-line description
    }
  }

  if (!name) name = path.basename(path.dirname(file));
  return { name: name.trim(), chars: name.trim().length + desc.trim().length };
}

function walkSkills() {
  const files = [];
  const roots = [path.join(CLAUDE_DIR, 'skills'), path.join(CLAUDE_DIR, 'plugins')];
  const seen = new Set();

  function rec(dir, depth) {
    if (depth > 6) return;
    let entries;
    try { entries = fs.readdirSync(dir, { withFileTypes: true }); } catch (_) { return; }
    for (const e of entries) {
      const p = path.join(dir, e.name);
      if (e.isDirectory()) rec(p, depth + 1);
      else if (e.isFile() && e.name === 'SKILL.md' && !seen.has(p)) { seen.add(p); files.push(p); }
    }
  }
  for (const r of roots) rec(r, 0);
  return files;
}

function fileChars(p) {
  try { return fs.statSync(p).size; } catch (_) { return 0; }
}

// ── Main ────────────────────────────────────────────────────────────────────

let raw = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', c => { raw += c; });
process.stdin.on('end', () => {
  try {
    let data = {};
    try { data = JSON.parse(raw) || {}; } catch (_) {}
    const sessionId  = data.session_id || '';
    const STATE_FILE = statePath(sessionId);
    pruneStaleStateFiles();

    // Dedupe: report once per session. Per-session file — nothing to clobber.
    let state = {};
    try { state = JSON.parse(fs.readFileSync(STATE_FILE, 'utf8')) || {}; } catch (_) {}
    if (state.overhead_reported) process.exit(0);

    const { ceiling, src } = resolveCeiling(sessionId);

    const skillFiles = walkSkills();
    let listingChars = 0, count = 0, overCap = [];
    for (const f of skillFiles) {
      const r = frontmatterNameDesc(f);
      if (!r) continue;
      count++;
      listingChars += r.chars;
      if (r.chars > 1536) overCap.push(r.name);
    }

    const listingTok = Math.round(listingChars / CHARS_PER_TOKEN);
    const budgetTok  = Math.round(ceiling * 0.01);

    // CLAUDE.md files + auto-memory, insofar as they are on disk.
    let memChars = 0;
    for (const p of [
      path.join(CLAUDE_DIR, 'CLAUDE.md'),
      path.join(CLAUDE_DIR, 'MEMORY.md'),
      path.join(process.cwd(), 'CLAUDE.md'),
    ]) memChars += fileChars(p);
    const memTok = Math.round(memChars / CHARS_PER_TOKEN);

    const floorTok = listingTok + memTok;
    const floorPct = ceiling > 0 ? (floorTok / ceiling) * 100 : 0;

    // Render tokens as "22.7k" / "9.7k". Estimates only — always prefixed "~".
    const k = n => `${Math.round(n / 100) / 10}k`;

    const lines = [];

    // #20 — skill listing overflow
    if (count > 0 && listingTok > budgetTok) {
      const overBy = (listingTok / Math.max(1, budgetTok)).toFixed(1);
      lines.push(
        `🪙 #20 — Skill listing ~${k(listingTok)} tok across ${count} skills vs ~${k(budgetTok)} budget ` +
        `(${overBy}x over). Claude Code is dropping descriptions of least-invoked skills — those skills cannot trigger.`
      );
    }
    if (overCap.length) {
      lines.push(
        `🪙 #20 — ${overCap.length} entr${overCap.length === 1 ? 'y' : 'ies'} over the 1536-char cap, truncated: ` +
        `${overCap.slice(0, 3).join(', ')}${overCap.length > 3 ? '…' : ''}`
      );
    }

    // #21 — measured floor of fixed per-turn overhead
    if (floorPct >= OVERHEAD_PCT) {
      lines.push(
        `🪙 #21 — ~${Math.round(floorPct)}% of the ${Math.round(ceiling / 1000)}k budget is spent before you type ` +
        `(~${k(listingTok)} skills + ~${k(memTok)} memory). ` +
        `Floor only — MCP tool schemas are not measurable from disk. Ceiling src: ${src}.`
      );
    }

    state.overhead_reported = true;
    state.ceiling = ceiling;
    state.ceiling_src = src;
    try {
      fs.mkdirSync(CTX_DIR, { recursive: true });
      fs.writeFileSync(STATE_FILE, JSON.stringify(state));
    } catch (_) {}

    if (!lines.length) process.exit(0);

    process.stdout.write(JSON.stringify({
      hookSpecificOutput: {
        hookEventName: 'SessionStart',
        additionalContext: `\n[Context Till — fixed overhead]\n${lines.map(l => `  ${l}`).join('\n')}\n`,
      },
    }));
  } catch (_) { /* fail open — never break a session start */ }
  process.exit(0);
});
