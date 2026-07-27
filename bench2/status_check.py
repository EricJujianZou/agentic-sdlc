"""Quick progress check on pushed bench2 run branches (read-only)."""
import json
import subprocess


def git(*a):
    return subprocess.run(["git"] + list(a), capture_output=True, text=True).stdout


m = json.load(open("bench2/manifest.json"))
order = m["orderings"]["forward"]

print("=== Arm A (one branch per instance) ===")
for iid in sorted(m["instances"]):
    br = f"origin/bench2/armA-1-{iid}"
    files = git("ls-tree", "-r", "--name-only", br, "bench2/results/armA-1/").splitlines()
    has_p = f"bench2/results/armA-1/{iid}.patch" in files
    size = len(git("show", f"{br}:bench2/results/armA-1/{iid}.patch")) if has_p else 0
    sa = ""
    if f"bench2/results/armA-1/{iid}.meta.json" in files:
        try:
            sa = json.loads(git("show", f"{br}:bench2/results/armA-1/{iid}.meta.json")).get("self_assessment", "?")
        except Exception:
            sa = "BAD META"
    p = "Y" if has_p else "MISSING"
    print(f"{iid:45s} patch={p:7s} bytes={size:6d} meta={sa}")

print()
print("=== Arm B (single session, forward order) ===")
files = git("ls-tree", "-r", "--name-only", "origin/bench2/armB-1", "bench2/results/armB-1/").splitlines()
done = {f.rsplit("/", 1)[-1][: -len(".patch")] for f in files if f.endswith(".patch")}
for i, iid in enumerate(order, 1):
    if iid in done:
        sz = len(git("show", f"origin/bench2/armB-1:bench2/results/armB-1/{iid}.patch"))
        try:
            sa = json.loads(git("show", f"origin/bench2/armB-1:bench2/results/armB-1/{iid}.meta.json")).get("self_assessment", "?")
        except Exception:
            sa = "no meta"
        print(f"{i:2d}. {iid:45s} DONE bytes={sz:6d} self={sa}")
    else:
        print(f"{i:2d}. {iid:45s} pending")

print()
print(git("log", "--oneline", "-3", "origin/bench2/armB-1"))
