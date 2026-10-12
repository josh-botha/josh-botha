"""Counts commits per day and Claude Code messages per day into data/activity.json.

Counts only. No commit messages, file names, prompts or replies leave this
machine. Same rules as the site's scripts/build-activity.mjs, so the numbers
match joshbotha.com:

  commits  every git repo under ~/Developer, --all, each hash once, Josh's
           author addresses only, bucketed by Sydney date
  claude   every session log under ~/.claude/projects, one count per
           assistant message id (the logs repeat an id while a reply streams)

Run: python3 scripts/activity.py
"""

import json
import os
import re
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

HOME = Path.home()
TZ = ZoneInfo("Australia/Sydney")
AUTHORS = [re.compile(p, re.I) for p in (r"josh\.botha@outlook\.com", r"josh@nervehospitality\.com", r"^josh\.botha$")]
OUT = Path(__file__).resolve().parent.parent / "data" / "activity.json"


def day_key(iso: str) -> str:
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(TZ).strftime("%Y-%m-%d")


def find_repos(root: Path, depth: int = 3) -> list[Path]:
    out = []

    def walk(d: Path, left: int):
        try:
            entries = list(os.scandir(d))
        except OSError:
            return
        if any(e.name == ".git" and e.is_dir() for e in entries):
            out.append(d)
            return
        if left == 0:
            return
        for e in entries:
            if e.is_dir() and not e.name.startswith(".") and e.name != "node_modules":
                walk(Path(e.path), left - 1)

    walk(root, depth)
    return out


def commits():
    seen: dict[str, str] = {}
    repos = []
    for repo in find_repos(HOME / "Developer"):
        try:
            log = subprocess.run(["git", "-C", str(repo), "log", "--all", "--format=%H|%aI|%ae"],
                                 capture_output=True, text=True, check=True).stdout
        except subprocess.CalledProcessError:
            continue
        mine = 0
        for line in log.splitlines():
            parts = line.split("|")
            if len(parts) != 3 or not any(a.search(parts[2]) for a in AUTHORS):
                continue
            if parts[0] not in seen:
                seen[parts[0]] = day_key(parts[1])
                mine += 1
        if mine:
            repos.append(repo.name)
    days: dict[str, int] = {}
    for d in seen.values():
        days[d] = days.get(d, 0) + 1
    return {"repos": len(repos), "total": len(seen), "days": days}


def claude():
    ids = set()
    days: dict[str, int] = {}
    starts: dict[str, int] = {}  # sessions by the day they started
    sessions = 0
    for f in (HOME / ".claude" / "projects").rglob("*.jsonl"):
        if f.stat().st_size == 0:
            continue
        counted = None
        with open(f, encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                if '"assistant"' not in line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if row.get("type") != "assistant" or not row.get("timestamp") or not row.get("message"):
                    continue
                mid = row["message"].get("id") or row.get("uuid")
                if not mid or mid in ids:
                    continue
                ids.add(mid)
                k = day_key(row["timestamp"])
                counted = min(counted or k, k)
                days[k] = days.get(k, 0) + 1
        if counted:
            sessions += 1
            starts[counted] = starts.get(counted, 0) + 1
    return {"sessions": sessions, "messages": len(ids), "days": days, "starts": starts}


if __name__ == "__main__":
    data = {
        "generated": datetime.now(TZ).strftime("%Y-%m-%d"),
        "commits": commits(),
        "claude": claude(),
    }
    OUT.write_text(json.dumps(data, indent=1, sort_keys=True))
    c, a = data["commits"], data["claude"]
    print(f"{c['total']} commits in {c['repos']} repos; {a['sessions']} Claude sessions, {a['messages']} messages")
