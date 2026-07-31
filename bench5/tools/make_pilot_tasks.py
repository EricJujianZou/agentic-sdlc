"""Generate pilot task files for the 10 pre-specified decile instances.

Each bench5/pilot/tasks/r<rank>.md contains exactly the SWE-bench Pro
task-visible fields (problem_statement, requirements, interface) plus repo
+ base_commit. Gold patch / test patch / test lists are NOT included.
"""
import json
import os

import pandas as pd

REPO = r"C:\Users\zouju\Coding Projects\agentic-sdlc"
PARQUET = os.path.join(REPO, "bench5", "data", "swebench_pro_test.parquet")
INSTANCES = os.path.join(REPO, "bench5", "instances.json")
PILOT_RANKS = [5, 15, 25, 35, 45, 55, 65, 75, 85, 95]

df = pd.read_parquet(PARQUET).set_index("instance_id")
frozen = json.load(open(INSTANCES))
by_rank = {r["rank"]: r for r in frozen["instances"]}

outdir = os.path.join(REPO, "bench5", "pilot", "tasks")
os.makedirs(outdir, exist_ok=True)

for rank in PILOT_RANKS:
    rec = by_rank[rank]
    row = df.loc[rec["instance_id"]]
    body = f"""# Pilot task r{rank:03d}

- instance_id: `{rec["instance_id"]}`
- repo: `{row.repo}` (public GitHub)
- base_commit: `{row.base_commit}`
- language: {row.repo_language}

## Problem statement

{row.problem_statement}

## Requirements

{row.requirements}

## Interface

{row.interface}
"""
    with open(os.path.join(outdir, f"r{rank:03d}.md"), "w", newline="\n",
              encoding="utf-8") as f:
        f.write(body)
    print(f"r{rank:03d}", rec["instance_id"][:70], row.repo)
