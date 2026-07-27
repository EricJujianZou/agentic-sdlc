"""Compare arm reports: per-position outcomes for Arm B vs Arm A (read-only)."""
import json

m = json.load(open("bench2/manifest.json"))
order = m["orderings"]["forward"]
diff = {i: v["difficulty"] for i, v in m["instances"].items()}

ra = json.load(open("bench2/results/bench2-armA-1.armA-1-local.json"))
rb = json.load(open("bench2/results/bench2-armB-1.armB-1-local.json"))
a_ok = set(ra["resolved_ids"])
b_ok = set(rb["resolved_ids"])
b_err = set(rb.get("error_ids", []))

print(f"{'pos':>3} {'instance':45s} {'diff':12s} {'armA':6s} {'armB':6s}")
for i, iid in enumerate(order, 1):
    a = "PASS" if iid in a_ok else "fail"
    b = "PASS" if iid in b_ok else ("ERROR" if iid in b_err else "fail")
    flag = "  <-- B-only failure" if a == "PASS" and b != "PASS" else ""
    print(f"{i:>3} {iid:45s} {diff[iid][:12]:12s} {a:6s} {b:6s}{flag}")

first = order[:10]
second = order[10:]
for name, half in [("positions 1-10", first), ("positions 11-20", second)]:
    a_n = sum(1 for i in half if i in a_ok)
    b_n = sum(1 for i in half if i in b_ok)
    print(f"{name}: armA {a_n}/10, armB {b_n}/10")
