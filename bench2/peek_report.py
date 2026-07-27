"""Print resolved/unresolved from a local harness report (runs inside WSL)."""
import glob
import json
import sys

for path in sorted(glob.glob("/home/zouju/bench2/bench2-arm*.json")):
    r = json.load(open(path))
    print(path.rsplit("/", 1)[-1])
    print("  resolved:", r["resolved_instances"], "/", r["submitted_instances"],
          " completed:", r["completed_instances"], " errors:", r["error_instances"],
          " empty:", r.get("empty_patch_instances", 0))
    print("  unresolved:", sorted(r.get("unresolved_ids", [])))
    print("  error_ids:", sorted(r.get("error_ids", [])))
