"""Summarize per-instance timing from collected meta files (read-only)."""
import json
from datetime import datetime

for run in ["armA-1", "armB-1"]:
    s = json.load(open(f"bench2/results/{run}/summary.json"))
    spans = []
    for iid, m in s["meta"].items():
        try:
            a = datetime.fromisoformat(m["started_at"].replace("Z", "+00:00"))
            b = datetime.fromisoformat(m["finished_at"].replace("Z", "+00:00"))
            spans.append((a, b, iid, (b - a).total_seconds() / 60))
        except Exception as e:
            print(run, iid, "bad meta:", e)
    if not spans:
        continue
    spans.sort()
    first = spans[0][0]
    last = max(x[1] for x in spans)
    per = sorted(x[3] for x in spans)
    print(f"{run}: n={len(spans)} wall {(last - first).total_seconds() / 60:.0f} min, "
          f"per-instance min/med/max = {per[0]:.1f}/{per[len(per) // 2]:.1f}/{per[-1]:.1f} min")
    if run == "armB-1":
        for a, b, iid, mins in spans:
            print(f"   {a.strftime('%H:%M')}-{b.strftime('%H:%M')} {mins:5.1f}m {iid}")
