#!/usr/bin/env python3
"""Measure how much context Claude Code loads at the start of each session.

Reads Claude Code's local session logs and reports the tokens on the first API
call of each session: input + cache write + cache read.

Read-only. Standard library only. Makes no network calls. Prints dates, counts
and token totals, never prompts, file contents or project names.

Examples:
  python3 first_call_context.py
  python3 first_call_context.py --model haiku --days 30
  python3 first_call_context.py --before 2026-10-08:2026-10-11 \\
      --after 2026-10-13:2026-10-21 --model haiku --version 2.1.293
"""
import argparse
import datetime as dt
import glob
import json
import os
import statistics
import sys
from collections import defaultdict


def first_call(path):
    """Return the first assistant record with usage data, or None."""
    with open(path, errors="replace") as handle:
        for line in handle:
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if not isinstance(row, dict) or row.get("type") != "assistant":
                continue
            message = row.get("message") or {}
            usage = message.get("usage")
            if not usage:
                continue
            return {
                "day": str(row.get("timestamp", ""))[:10],
                "version": row.get("version") or "",
                "model": message.get("model") or "",
                "tokens": int(usage.get("input_tokens") or 0)
                + int(usage.get("cache_creation_input_tokens") or 0)
                + int(usage.get("cache_read_input_tokens") or 0),
            }
    return None


def load_sessions(root, model="", version="", path_contains="", include_subagents=False):
    """Collect one first-call record per session log that passes the filters."""
    sessions = []
    for path in glob.glob(os.path.join(root, "**", "*.jsonl"), recursive=True):
        if not include_subagents and f"{os.sep}subagents{os.sep}" in path:
            continue
        if path_contains and path_contains.lower() not in path.lower():
            continue
        try:
            call = first_call(path)
        except OSError:
            continue
        if not call or not call["day"] or call["model"] == "<synthetic>":
            continue
        if model and model.lower() not in call["model"].lower():
            continue
        if version and call["version"] != version:
            continue
        sessions.append(call)
    return sessions


def date_range(text):
    """Parse YYYY-MM-DD:YYYY-MM-DD."""
    try:
        start, end = text.split(":")
        first, last = dt.date.fromisoformat(start), dt.date.fromisoformat(end)
    except ValueError as error:
        raise argparse.ArgumentTypeError("use YYYY-MM-DD:YYYY-MM-DD") from error
    if first > last:
        raise argparse.ArgumentTypeError("start date is after end date")
    return start, end


def summary(values):
    return {
        "sessions": len(values),
        "median": int(statistics.median(values)),
        "min": min(values),
        "max": max(values),
    }


def print_row(label, stats):
    print(f"{label:<25}{stats['sessions']:>9,}{stats['median']:>11,}"
          f"{stats['min']:>11,}{stats['max']:>11,}")


def print_header():
    print(f"{'':<25}{'sessions':>9}{'median':>11}{'min':>11}{'max':>11}")


def compare(sessions, before, after):
    """Print a before/after comparison. Return 0, or 1 if a window is empty."""
    picks = {}
    for name, (start, end) in (("before", before), ("after", after)):
        picks[name] = [s["tokens"] for s in sessions if start <= s["day"] <= end]
        if not picks[name]:
            print(f"No sessions matched the {name} window ({start} to {end}).")
            return 1
    first, second = summary(picks["before"]), summary(picks["after"])
    print_header()
    print_row(f"before {before[0][5:]}..{before[1][5:]}", first)
    print_row(f"after  {after[0][5:]}..{after[1][5:]}", second)
    change = second["median"] - first["median"]
    print(f"\nMedian change: {change:+,} tokens ({change / first['median']:+.1%})")
    print("Compare like with like: filter to one model and version, and to one "
          "kind of work if you can.")
    return 0


def daily(sessions, days):
    """Print one row per day for the most recent days that have sessions."""
    by_day = defaultdict(list)
    for session in sessions:
        by_day[session["day"]].append(session["tokens"])
    print_header()
    for day in sorted(by_day)[-days:]:
        print_row(day, summary(by_day[day]))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Report context tokens on the first API call of each Claude Code session.")
    parser.add_argument("--root", default=os.path.expanduser("~/.claude/projects"),
                        help="session log folder (default: ~/.claude/projects)")
    parser.add_argument("--model", default="", help="keep models containing this text, e.g. haiku")
    parser.add_argument("--version", default="", help="keep one Claude Code version, e.g. 2.1.293")
    parser.add_argument("--path-contains", default="",
                        help="keep logs whose path contains this text (one project or job)")
    parser.add_argument("--include-subagents", action="store_true",
                        help="count subagent logs too (off by default)")
    parser.add_argument("--days", type=int, default=14, help="days to show without windows")
    parser.add_argument("--before", type=date_range, help="YYYY-MM-DD:YYYY-MM-DD")
    parser.add_argument("--after", type=date_range, help="YYYY-MM-DD:YYYY-MM-DD")
    args = parser.parse_args(argv)

    if bool(args.before) != bool(args.after):
        parser.error("--before and --after must be used together")
    if args.days < 1:
        parser.error("--days must be at least 1")
    if not os.path.isdir(args.root):
        print(f"Log folder not found: {args.root}", file=sys.stderr)
        return 2

    sessions = load_sessions(args.root, args.model, args.version,
                             args.path_contains, args.include_subagents)
    if not sessions:
        print("No sessions matched those filters.")
        return 1
    if args.before:
        return compare(sessions, args.before, args.after)
    return daily(sessions, args.days)


if __name__ == "__main__":
    sys.exit(main())
