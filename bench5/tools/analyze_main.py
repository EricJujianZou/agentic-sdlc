"""Pre-registered analysis for round 5 main run (bench5/PLAN.md).

Reads the raw per-instance harness outputs (armA_*/armB_* _output.json),
rebuilds the full 60x4 pass matrix, and reports:
  - per-cell pass rates
  - primary: within-model McNemar (arm A vs arm B), exact binomial
  - interaction: delta_sonnet - delta_opus with bootstrap CI over instances
  - probe-conditioned sensitivity (exclude high-probe instances)
  - integrity/process: meta.json timestamp + duration summaries
Writes bench5/results/main_matrix.json (the merged verdict matrix).
"""
import json
import math
import os
import glob
import random

import pandas as pd

REPO = r"C:\Users\zouju\Coding Projects\agentic-sdlc"
OUT_MAIN = r"C:\Users\zouju\Coding Projects\SWE-bench_Pro-os\bench5_eval\out_main"
CELLS = ["armA_sonnet5", "armA_opus5", "armB_sonnet5", "armB_opus5"]


def load_matrix():
    df = pd.read_parquet(os.path.join(REPO, "bench5", "data",
                                      "swebench_pro_test.parquet"))
    df = df.set_index("instance_id")
    frozen = json.load(open(os.path.join(REPO, "bench5", "instances.json")))
    by_iid = {r["instance_id"]: r["rank"] for r in frozen["instances"]
              if r["rank"] <= 60}
    matrix = {}  # rank -> {cell: bool}
    for p in glob.glob(os.path.join(OUT_MAIN, "*", "arm*_output.json")):
        prefix = os.path.basename(p).replace("_output.json", "")
        cell, rank = prefix.rsplit("_r", 1)
        rank = int(rank)
        iid = os.path.basename(os.path.dirname(p))
        if by_iid.get(iid) != rank or cell not in CELLS:
            continue
        out = json.load(open(p))
        passed = {t["name"] for t in out.get("tests", [])
                  if t["status"] == "PASSED"}
        needed = (set(eval(df.loc[iid, "fail_to_pass"]))
                  | set(eval(df.loc[iid, "pass_to_pass"])))
        matrix.setdefault(rank, {})[cell] = needed <= passed
    return matrix, {r["rank"]: r["instance_id"] for r in frozen["instances"]}


def mcnemar_exact(b, c):
    """Two-sided exact binomial p for discordant counts b, c."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    p = sum(math.comb(n, i) for i in range(0, k + 1)) / 2 ** n * 2
    return min(1.0, p)


def analyze(matrix, ranks, label):
    print(f"\n=== {label} (n={len(ranks)}) ===")
    res = {"label": label, "n": len(ranks)}
    for cell in CELLS:
        n_pass = sum(matrix[r][cell] for r in ranks)
        rate = n_pass / len(ranks)
        res[cell] = f"{n_pass}/{len(ranks)}"
        print(f"  {cell}: {n_pass}/{len(ranks)} ({rate:.1%})")
    for model in ["sonnet5", "opus5"]:
        b = sum(matrix[r][f"armA_{model}"] and not matrix[r][f"armB_{model}"]
                for r in ranks)  # A pass, B fail
        c = sum(not matrix[r][f"armA_{model}"] and matrix[r][f"armB_{model}"]
                for r in ranks)  # A fail, B pass
        p = mcnemar_exact(b, c)
        res[f"mcnemar_{model}"] = {"A_only": b, "B_only": c, "p": round(p, 4)}
        print(f"  McNemar {model}: A-only={b} B-only={c} exact p={p:.4f}")
    # interaction: (SA-SB) - (OA-OB), bootstrap over instances
    deltas = []
    for r in ranks:
        ds = int(matrix[r]["armA_sonnet5"]) - int(matrix[r]["armB_sonnet5"])
        do = int(matrix[r]["armA_opus5"]) - int(matrix[r]["armB_opus5"])
        deltas.append(ds - do)
    obs = sum(deltas) / len(deltas)
    rng = random.Random(20260803)
    boots = []
    for _ in range(10000):
        samp = [deltas[rng.randrange(len(deltas))] for _ in deltas]
        boots.append(sum(samp) / len(samp))
    boots.sort()
    lo, hi = boots[249], boots[9749]
    res["interaction"] = {"obs": round(obs, 4), "ci95": [round(lo, 4),
                                                         round(hi, 4)]}
    print(f"  interaction (dSonnet-dOpus): {obs:+.4f}  "
          f"bootstrap 95% CI [{lo:+.4f}, {hi:+.4f}]")
    return res


def main():
    matrix, rank_to_iid = load_matrix()
    all_ranks = sorted(r for r, cells in matrix.items()
                       if all(c in cells for c in CELLS))
    missing = [r for r in range(1, 61) if r not in all_ranks]
    if missing:
        print(f"WARNING: incomplete ranks (skipped): {missing}")
    results = [analyze(matrix, all_ranks, "primary (all instances)")]

    # probe-conditioned sensitivity
    probe = json.load(open(os.path.join(REPO, "bench5", "probe",
                                        "probe_results.json")))
    high = set()
    for key, rec in probe.items():
        iid = rec["instance_id"]
        scorable = rec.get("scorable_gold", [])
        if not scorable:
            continue
        hit = len(set(rec["predicted"]) & set(scorable)) / len(scorable)
        if hit >= 0.5:
            high.add(iid)
    low_ranks = [r for r in all_ranks if rank_to_iid[r] not in high]
    results.append(analyze(matrix, low_ranks, "low-probe sensitivity"))

    # process/integrity: durations from meta.json per cell
    print("\n=== process (self-reported wall-clock, minutes/instance) ===")
    import subprocess
    for arm, model, branch, prefix in [
            ("armA", "sonnet5", "bench5/armA-sonnet5", "bench5/results/armA/sonnet5"),
            ("armA", "opus5", "bench5/armA-opus5", "bench5/results/armA/opus5"),
            ("armB", "sonnet5", "bench5/armB-sonnet5", "bench5/results/armB/sonnet5"),
            ("armB", "opus5", "bench5/armB-opus5", "bench5/results/armB/opus5")]:
        durs, bad_meta = [], 0
        for r in all_ranks:
            try:
                raw = subprocess.run(
                    ["git", "show",
                     f"origin/{branch}:{prefix}/r{r:03d}/meta.json"],
                    capture_output=True, text=True, cwd=REPO, check=True).stdout
                m = json.loads(raw)
                t0 = pd.Timestamp(m["started_at"])
                t1 = pd.Timestamp(m["finished_at"])
                durs.append((t1 - t0).total_seconds() / 60)
            except Exception:
                bad_meta += 1
        if durs:
            s = pd.Series(durs)
            print(f"  {arm}_{model}: median {s.median():.1f}m  "
                  f"mean {s.mean():.1f}m  max {s.max():.0f}m  "
                  f"(missing/bad meta: {bad_meta})")

    out = {"matrix": {str(r): matrix[r] for r in all_ranks},
           "rank_to_instance": {str(r): rank_to_iid[r] for r in all_ranks},
           "analyses": results,
           "high_probe_instances": sorted(high)}
    with open(os.path.join(REPO, "bench5", "results", "main_matrix.json"),
              "w", newline="\n") as f:
        json.dump(out, f, indent=1)
    print("\nwrote bench5/results/main_matrix.json")


if __name__ == "__main__":
    main()
