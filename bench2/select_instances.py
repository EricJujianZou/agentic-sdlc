"""Select the round-2 instance set from SWE-bench Verified.

Stdlib-only. Downloads all 500 rows of princeton-nlp/SWE-bench_Verified
(test split) via the HuggingFace datasets-server API, then takes a seeded,
repo-stratified sample of N instances, excluding the ">4 hours" difficulty
tier. Writes:

  bench2/manifest.json            instance metadata + the two run orderings
  bench2/instances/<id>.md        one spec file per instance (problem statement)

Deterministic: same seed => same selection. Run once by the maintainer before
pre-registration; solvers never run this.

    uv run python bench2/select_instances.py
"""

import json
import os
import random
import urllib.request

BENCH2 = os.path.dirname(os.path.abspath(__file__))
DATASET = "princeton-nlp/SWE-bench_Verified"
API = ("https://datasets-server.huggingface.co/rows"
       f"?dataset={DATASET.replace('/', '%2F')}&config=default&split=test")
SEED = 20260726
N = 20
EXCLUDE_DIFFICULTY = {">4 hours"}


def fetch_all_rows():
    rows, offset = [], 0
    while True:
        with urllib.request.urlopen(f"{API}&offset={offset}&length=100") as r:
            batch = json.load(r)["rows"]
        if not batch:
            break
        rows.extend(b["row"] for b in batch)
        offset += len(batch)
        if len(batch) < 100:
            break
    return rows


def stratified_sample(rows, n, seed):
    """Round-robin over repos (largest first), seeded shuffle within each."""
    rng = random.Random(seed)
    pool = [r for r in rows if r["difficulty"] not in EXCLUDE_DIFFICULTY]
    by_repo = {}
    for r in pool:
        by_repo.setdefault(r["repo"], []).append(r)
    for lst in by_repo.values():
        lst.sort(key=lambda r: r["instance_id"])
        rng.shuffle(lst)
    repos = sorted(by_repo, key=lambda k: (-len(by_repo[k]), k))
    picked = []
    while len(picked) < n:
        for repo in repos:
            if by_repo[repo] and len(picked) < n:
                picked.append(by_repo[repo].pop(0))
    return picked


def main():
    rows = fetch_all_rows()
    assert len(rows) == 500, f"expected 500 rows, got {len(rows)}"
    picked = stratified_sample(rows, N, SEED)

    order_fwd = sorted(r["instance_id"] for r in picked)
    rng = random.Random(SEED + 1)
    order_fwd = list(order_fwd)
    rng.shuffle(order_fwd)          # ordering A: seeded shuffle
    order_rev = list(reversed(order_fwd))  # ordering B: exact reverse

    inst_dir = os.path.join(BENCH2, "instances")
    os.makedirs(inst_dir, exist_ok=True)
    manifest = {"dataset": DATASET, "split": "test", "seed": SEED,
                "excluded_difficulty": sorted(EXCLUDE_DIFFICULTY),
                "orderings": {"forward": order_fwd, "reverse": order_rev},
                "instances": {}}
    for r in picked:
        iid = r["instance_id"]
        manifest["instances"][iid] = {
            "repo": r["repo"],
            "base_commit": r["base_commit"],
            "difficulty": r["difficulty"],
        }
        spec = (f"# {iid}\n\n"
                f"- **Repository:** https://github.com/{r['repo']}\n"
                f"- **Base commit:** `{r['base_commit']}`\n\n"
                "## Problem statement\n\n"
                f"{r['problem_statement'].strip()}\n")
        with open(os.path.join(inst_dir, f"{iid}.md"), "w",
                  encoding="utf-8", newline="\n") as f:
            f.write(spec)

    with open(os.path.join(BENCH2, "manifest.json"), "w",
              encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")

    diffs = {}
    for r in picked:
        diffs[r["difficulty"]] = diffs.get(r["difficulty"], 0) + 1
    print(f"selected {len(picked)} instances from {len(rows)}")
    print("difficulty mix:", diffs)
    print("repos:", sorted({r['repo'] for r in picked}))


if __name__ == "__main__":
    main()
