"""Compare Arm B self-reported meta times against actual git commit times."""
import json
import subprocess
import sys
from datetime import datetime


def git(*a):
    return subprocess.run(["git"] + list(a), capture_output=True, text=True).stdout


run = sys.argv[1]
s = json.load(open(f"bench3/results/{run}/summary.json"))

commits = {}
branches = ([f"origin/bench3/{run}"] if run.startswith("armB")
            else [f"origin/bench3/{run}-{iid}" for iid in s["meta"]])
for branch in branches:
    out = git("log", "--format=%aI|%s", branch)
    for line in out.splitlines():
        if "|" not in line:
            continue
        when, subj = line.split("|", 1)
        if subj.startswith(f"{run}: "):
            commits[subj.split(": ", 1)[1]] = datetime.fromisoformat(when)
bad = 0
for iid, m in sorted(s["meta"].items()):
    try:
        st = datetime.fromisoformat(m["started_at"].replace("Z", "+00:00"))
        fi = datetime.fromisoformat(m["finished_at"].replace("Z", "+00:00"))
    except Exception:
        print(f"{iid}: unparseable meta")
        bad += 1
        continue
    c = commits.get(iid)
    issues = []
    if fi < st:
        issues.append("finished<started")
    if c and abs((fi - c).total_seconds()) > 600:
        issues.append(f"finished_at {fi:%H:%M} vs commit {c:%H:%M}")
    if issues:
        bad += 1
        print(f"{iid}: {', '.join(issues)}")
print(f"{run}: {bad} suspicious of {len(s['meta'])} "
      f"({len(commits)} matching commits found)")
