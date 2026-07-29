"""Pooled cross-replicate analysis: discordance, McNemar sign test, position."""
import json
from math import comb

v = json.load(open("bench2/results/final_verdicts.json"))
m = json.load(open("bench2/manifest.json"))
fwd = m["orderings"]["forward"]
rev = m["orderings"]["reverse"]
iids = sorted(m["instances"])

print("=== per-instance across replicates (A1 A2 A3 | B1 B2 B3) ===")
a_only, b_only = 0, 0
for iid in iids:
    a = [v[f"armA-{i}"][iid] for i in (1, 2, 3)]
    b = [v[f"armB-{i}"][iid] for i in (1, 2, 3)]
    for x, y in zip(a, b):
        if x and not y:
            a_only += 1
        elif y and not x:
            b_only += 1
    mark = ""
    if sum(a) > sum(b):
        mark = "  <-- A better"
    elif sum(b) > sum(a):
        mark = "  <-- B better"
    fmt = lambda xs: " ".join("P" if x else "f" for x in xs)
    print(f"{iid:45s} {fmt(a)} | {fmt(b)}{mark}")

n = a_only + b_only
p = sum(comb(n, k) for k in range(min(a_only, b_only) + 1)) / 2 ** n * 2
print(f"\ndiscordant pairs (paired by replicate): A-only {a_only}, "
      f"B-only {b_only}; two-sided exact McNemar p = {min(p, 1):.4f}")

print("\n=== Arm B position analysis ===")
for run, order in [("armB-1", fwd), ("armB-2", rev), ("armB-3", fwd)]:
    fails = [i + 1 for i, iid in enumerate(order) if not v[run][iid]]
    fh = sum(1 for i, iid in enumerate(order[:10]) if v[run][iid])
    sh = sum(1 for iid in order[10:] if v[run][iid])
    print(f"{run}: fail positions {fails}; first half {fh}/10, second half {sh}/10")
