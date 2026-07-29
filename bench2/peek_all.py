"""Summarize all local harness reports incl. error ids (read-only)."""
import glob
import json

for path in sorted(glob.glob("bench2/results/bench2-arm*.json")):
    r = json.load(open(path))
    name = path.rsplit("bench2-", 1)[-1].split(".")[0]
    print(f"{name}: resolved {r['resolved_instances']}/20, "
          f"unresolved {sorted(r.get('unresolved_ids', []))}, "
          f"errors {sorted(r.get('error_ids', []))}")
