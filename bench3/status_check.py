"""Quick progress check on pushed bench3 run branches (read-only)."""
import json
import subprocess
import sys


def git(*a):
    return subprocess.run(["git"] + list(a), capture_output=True, text=True).stdout


rep = sys.argv[1] if len(sys.argv) > 1 else "1"
m = json.load(open("bench3/manifest.json"))
order = m["orderings"]["forward" if rep != "2" else "reverse"]

print(f"=== Arm A rep {rep} ===")
done_a = 0
for iid in sorted(m["instances"]):
    br = f"origin/bench3/armA-{rep}-{iid}"
    files = git("ls-tree", "-r", "--name-only", br,
                f"bench3/results/armA-{rep}/").splitlines()
    has_p = f"bench3/results/armA-{rep}/{iid}.patch" in files
    done_a += has_p
    if not has_p:
        print(f"  pending: {iid}")
print(f"armA-{rep}: {done_a}/20 patches pushed")

print(f"=== Arm B rep {rep} ===")
files = git("ls-tree", "-r", "--name-only", f"origin/bench3/armB-{rep}",
            f"bench3/results/armB-{rep}/").splitlines()
done = {f.rsplit("/", 1)[-1][:-len(".patch")] for f in files if f.endswith(".patch")}
for i, iid in enumerate(order, 1):
    if iid not in done:
        print(f"  pending: pos {i} {iid}")
print(f"armB-{rep}: {len(done)}/20 patches pushed")
print(git("log", "--format=%aI %s", "-3", f"origin/bench3/armB-{rep}"))
