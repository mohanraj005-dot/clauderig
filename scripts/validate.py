#!/usr/bin/env python3
"""Validate the clauderig marketplace: manifests, hooks, skills and README paths.

Standard library only. Run from anywhere:  python3 scripts/validate.py
Exit code 0 = all checks passed, 1 = at least one failure.

Checks
  1. .claude-plugin/marketplace.json parses; every plugin has a source dir
     containing .claude-plugin/plugin.json whose name and version match.
  2. Every hooks.json parses and every ${CLAUDE_PLUGIN_ROOT}/... path in a
     hook command exists; each referenced .js file passes `node --check`
     (skipped with a notice if node is not installed).
  3. Every SKILL.md has YAML frontmatter with name and description.
  4. Every Python script compiles.
  5. Every repo-relative file path or link mentioned in README.md exists.
"""
import json
import py_compile
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
failures = []
passes = 0


def ok(msg):
    global passes
    passes += 1
    print(f"  ok    {msg}")


def fail(msg):
    failures.append(msg)
    print(f"  FAIL  {msg}")


def load_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"{path.relative_to(ROOT)}: {exc}")
        return None


def check_marketplace():
    print("marketplace and plugin manifests")
    mp_path = ROOT / ".claude-plugin" / "marketplace.json"
    mp = load_json(mp_path)
    if mp is None:
        return []
    ok(".claude-plugin/marketplace.json parses")
    dirs = []
    for entry in mp.get("plugins", []):
        name = entry.get("name", "<unnamed>")
        src = ROOT / entry.get("source", "")
        manifest = src / ".claude-plugin" / "plugin.json"
        if not manifest.is_file():
            fail(f"{name}: missing {manifest.relative_to(ROOT)}")
            continue
        pj = load_json(manifest)
        if pj is None:
            continue
        problems = [k for k in ("name", "description", "version") if not pj.get(k)]
        if problems:
            fail(f"{name}: plugin.json missing {problems}")
        elif pj["name"] != name:
            fail(f"{name}: plugin.json name is {pj['name']!r}")
        elif pj["version"] != entry.get("version"):
            fail(f"{name}: version {pj['version']} (plugin.json) != {entry.get('version')} (marketplace)")
        else:
            ok(f"{name} {pj['version']}: manifest matches marketplace entry")
        dirs.append(src)
    return dirs


def check_hooks(plugin_dirs):
    print("hooks")
    node = shutil.which("node")
    if node is None:
        print("  note  node not found; skipping syntax check of hook scripts")
    for d in plugin_dirs:
        hooks_json = d / "hooks" / "hooks.json"
        if not hooks_json.is_file():
            continue
        data = load_json(hooks_json)
        if data is None:
            continue
        events = data.get("hooks", {})
        commands = [
            h.get("command", "")
            for groups in events.values()
            for group in groups
            for h in group.get("hooks", [])
        ]
        for cmd in commands:
            for rel in re.findall(r"\$\{CLAUDE_PLUGIN_ROOT\}/([^\"\s]+)", cmd):
                target = d / rel
                if not target.is_file():
                    fail(f"{d.name}: hook references missing file {rel}")
                    continue
                if node and target.suffix == ".js":
                    r = subprocess.run([node, "--check", str(target)], capture_output=True, text=True)
                    if r.returncode != 0:
                        fail(f"{d.name}: {rel} fails node --check: {r.stderr.strip()[:200]}")
                        continue
                ok(f"{d.name}: hook script {rel} exists" + (" and parses" if node else ""))


def frontmatter(text):
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    return m.group(1) if m else None


def check_skills():
    print("skills")
    for skill in sorted(ROOT.glob("*/skills/*/SKILL.md")):
        rel = skill.relative_to(ROOT)
        fm = frontmatter(skill.read_text(encoding="utf-8"))
        if fm is None:
            fail(f"{rel}: no YAML frontmatter")
        elif not re.search(r"^name:\s*\S", fm, re.M) or not re.search(r"^description:", fm, re.M):
            fail(f"{rel}: frontmatter lacks name or description")
        else:
            ok(f"{rel}: frontmatter has name and description")


def check_python():
    print("python scripts")
    with tempfile.TemporaryDirectory() as tmp:
        for py in sorted(ROOT.glob("**/*.py")):
            if ".git" in py.parts or py.parent == ROOT / "scripts":
                continue
            try:
                py_compile.compile(str(py), cfile=str(Path(tmp) / (py.name + "c")), doraise=True)
                ok(f"{py.relative_to(ROOT)} compiles")
            except py_compile.PyCompileError as exc:
                fail(f"{py.relative_to(ROOT)}: {exc.msg.strip()[:200]}")


def check_readme_paths():
    print("README paths")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    candidates = set(re.findall(r"`([A-Za-z0-9_.][A-Za-z0-9_./-]*/[A-Za-z0-9_.-]+|[A-Za-z0-9_.-]+\.(?:md|json|py|sh|js|yml))`", readme))
    candidates |= set(re.findall(r"\]\((?!https?:|#)([^)#\s]+)\)", readme))
    checked = 0
    for c in sorted(candidates):
        if c.startswith(("mohanraj005-dot/", "~/", "/")) or "*" in c or "<" in c:
            continue
        # Only treat strings whose first path segment is a real top-level entry as repo paths.
        if not (ROOT / c.split("/")[0]).exists():
            continue
        checked += 1
        if (ROOT / c).exists():
            ok(f"README mentions {c}: exists")
        else:
            fail(f"README mentions {c}: not found")
    if checked == 0:
        fail("README path check matched nothing; pattern is probably broken")


def main():
    dirs = check_marketplace()
    check_hooks(dirs)
    check_skills()
    check_python()
    check_readme_paths()
    print()
    if failures:
        print(f"{len(failures)} failure(s), {passes} passed")
        return 1
    print(f"all checks passed ({passes})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
