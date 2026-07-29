"""Final tally from per-instance report.json files (run inside WSL).

Reads logs/run_evaluation/<run>-local/bench2-<run>/<iid>/report.json for all
six runs and writes bench2/results/final_verdicts.json in the repo.
"""
import glob
import json
import os

LOGS = os.path.expanduser("~/bench2/logs/run_evaluation")
OUT = ("/mnt/c/Users/zouju/Coding Projects/agentic-sdlc/"
       "bench2/results/final_verdicts.json")
RUNS = ["armA-1", "armA-2", "armA-3", "armB-1", "armB-2", "armB-3"]

verdicts = {}
for run in RUNS:
    verdicts[run] = {}
    for path in glob.glob(f"{LOGS}/{run}-local/bench2-{run}/*/report.json"):
        iid = path.rsplit("/", 2)[-2]
        r = json.load(open(path))
        verdicts[run][iid] = bool(r.get(iid, {}).get("resolved", False))

with open(OUT, "w", encoding="utf-8", newline="\n") as f:
    json.dump(verdicts, f, indent=2, sort_keys=True)
    f.write("\n")

for run in RUNS:
    v = verdicts[run]
    print(f"{run}: {sum(v.values())}/{len(v)} resolved")
