#!/usr/bin/env node
// till-handoff-resume.js — SessionStart hook (context-till handoff auto-resume)
//
// On a fresh session, if an unconsumed handoff snapshot exists for the CURRENT
// project, inject it as additionalContext and CONSUME it (archive) so it never
// re-injects into an unrelated future session.
//
// Pairs with:
//   - a session-handoff-style skill (if installed) → WRITES ~/.claude/handoffs/<slug>/LATEST.md
//   - till-handoff-gate.js (Stop) → offers "Handoff & clear" on long tasks
//
// slug = cwd with every non-alphanumeric char replaced by '-'
//        (e.g. a path like "home/example/my-project" becomes
//        "-home-example-my-project"), matching how Claude Code namespaces
//        ~/.claude/projects/.
//
// Disable: export TILL_RESUME_DISABLE=1
// Fail-open in every branch — a SessionStart hook must never break session start.

if (process.env.TILL_RESUME_DISABLE === '1') process.exit(0);

const fs   = require('fs');
const path = require('path');
const os   = require('os');

const HOME       = process.env.HOME || process.env.USERPROFILE || os.homedir();
const MAX_AGE_MS  = 1000 * 60 * 60 * 24 * 30; // 30 days — ignore stale handoffs

function slug(cwd) {
  return String(cwd || '').replace(/[^a-zA-Z0-9]/g, '-');
}

// --- banner summary extraction (project-agnostic) -------------------------
// Pull a short one-liner from the handoff so the user sees WHAT resumed,
// not just THAT something did. Fail-soft: any missing section → skipped.
function truncate(s, n) {
  s = String(s || '').replace(/\s+/g, ' ').trim();
  if (s.length <= n) return s;
  const cut = s.slice(0, n);
  const sp  = cut.lastIndexOf(' ');
  return (sp > n * 0.6 ? cut.slice(0, sp) : cut).trim() + '…';
}
function firstMeaningfulLine(lines) {
  for (const l of lines) {
    const t = l.trim();
    if (t && !/^#{1,6}\s/.test(t) && !/^[>*_-]+$/.test(t)) {
      return t.replace(/^[>*\-\s]+/, '');
    }
  }
  return '';
}
function section(lines, name) {
  const re = new RegExp('^#{1,6}\\s*' + name, 'i');
  const i  = lines.findIndex(l => re.test(l.trim()));
  if (i < 0) return '';
  const out = [];
  for (let j = i + 1; j < lines.length; j++) {
    const t = lines[j].trim();
    if (/^#{1,6}\s/.test(t)) break;                 // next heading ends the section
    if (!t) { if (out.length) break; else continue; } // blank after content ends it
    out.push(t.replace(/^[>*\-\s]+/, ''));
  }
  return out.join(' ').trim();
}

let raw = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', c => { raw += c; });
process.stdin.on('end', () => {
 try {
  let data = {};
  try { data = JSON.parse(raw); } catch (_) {}

  const cwd    = data.cwd || process.cwd();
  const dir    = path.join(HOME, '.claude', 'handoffs', slug(cwd));
  const latest = path.join(dir, 'LATEST.md');

  if (!fs.existsSync(latest)) process.exit(0);

  const stat    = fs.statSync(latest);
  const content = fs.readFileSync(latest, 'utf8').trim();

  // Consume-on-inject: archive FIRST so any failure below can never re-inject
  // the same handoff on every future session start.
  try {
    const consumedDir = path.join(dir, 'consumed');
    fs.mkdirSync(consumedDir, { recursive: true });
    fs.renameSync(latest, path.join(consumedDir, `LATEST-${Date.now()}.md`));
  } catch (_) {
    try { fs.unlinkSync(latest); } catch (_) {}
  }

  // Stale or empty → consumed above, but not injected.
  if (Date.now() - stat.mtimeMs > MAX_AGE_MS) process.exit(0);
  if (!content) process.exit(0);

  // --- derive the short summary for the visible banner --------------------
  const lines = content.split('\n');
  const goal  = truncate(section(lines, 'Session goal') || firstMeaningfulLine(lines), 120);
  const next  = truncate(section(lines, 'Next step')    || section(lines, 'Next steps'), 120);

  // (a) VISIBLE channel — systemMessage renders the instant the screen clears,
  //     before the user types anything.
  const bannerLines = ['📋 Handoff loaded from your last /clear.'];
  if (goal) bannerLines.push('   Goal: ' + goal);
  if (next) bannerLines.push('   Next: ' + next);
  bannerLines.push('   (Full context is already in memory — just continue.)');
  const banner = bannerLines.join('\n');

  // (b) CONTEXT channel — full handoff + a directive so I re-state the banner
  //     atop my first reply (belt-and-suspenders: shows even if the CLI
  //     version renders systemMessage differently).
  const directive = [
    '<resume-banner-directive>',
    'A prior-session handoff was just auto-loaded (full text below). In your FIRST reply of',
    'this session, open with ONE line before anything else:',
    '  📋 Resumed from handoff — ' + (goal || 'prior session'),
    'then address the user normally. Do not repeat the full handoff back to them.',
    '</resume-banner-directive>',
    ''
  ].join('\n');

  const injected = [
    directive,
    '━━━ SESSION HANDOFF — auto-resumed by context-till ━━━',
    'A handoff snapshot was written before the last /clear. Resume from it:',
    '',
    content,
    '',
    '(This handoff has now been consumed — it will not appear again.)'
  ].join('\n');

  process.stdout.write(JSON.stringify({
    systemMessage: banner,
    hookSpecificOutput: {
      hookEventName: 'SessionStart',
      additionalContext: injected
    }
  }));
 } catch (_) { /* never break session start */ }
  process.exit(0);
});
