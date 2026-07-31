"""Objective difficulty ranking for bench5 (pre-registered rule, PLAN.md).

Primary signal: published frontier per-instance pass/fail from the official
SWE-bench_Pro-os repo's leaderboard-config runs (250-turn, no cost cap):
  traj/claude-45sonnet-10132025/eval_results.json  (n=730)
  traj/gpt-5-250-turns-10132025/eval_results.json  (n=729)
  traj/kimi-k2-instruct-10132025/eval_results.json (n=729)
(The "-paper" runs use a different config ($2 cost cap) and partial coverage,
so they are excluded.)

frontier_score = mean(pass) over the runs that cover the instance
  (lower = harder). Instances covered by zero runs would rank by proxy only
  (none exist at time of writing).

Tie-break / fallback proxy (higher = harder):
  proxy = z(patch_bytes) + z(files_touched) + z(n_f2p_tests + n_p2p_tests)

Sort: frontier_score ASC, proxy DESC, instance_id ASC (final determinism).
Top N=100 frozen into bench5/instances.json with SHA-256 hashes of each
instance's canonical record. Trim rule (if pilot timing gate fires): drop
from the END of this ordering down to a pre-registered N >= 60.
"""
import hashlib
import json
import os

import pandas as pd

REPO = r"C:\Users\zouju\Coding Projects\agentic-sdlc"
HARNESS = r"C:\Users\zouju\Coding Projects\SWE-bench_Pro-os"
PARQUET = os.path.join(REPO, "bench5", "data", "swebench_pro_test.parquet")
N = 100

FRONTIER_RUNS = [
    "claude-45sonnet-10132025",
    "gpt-5-250-turns-10132025",
    "kimi-k2-instruct-10132025",
]

df = pd.read_parquet(PARQUET)

runs = {}
for run in FRONTIER_RUNS:
    with open(os.path.join(HARNESS, "traj", run, "eval_results.json")) as f:
        runs[run] = json.load(f)

def frontier(iid):
    votes = [bool(r[iid]) for r in runs.values() if iid in r]
    return (sum(votes) / len(votes)) if votes else None, len(votes)

def n_files(patch):
    return patch.count("diff --git ")

df["frontier_score"], df["frontier_cov"] = zip(*df.instance_id.map(frontier))
df["patch_bytes"] = df.patch.str.len()
df["files_touched"] = df.patch.map(n_files)
df["n_tests"] = df.fail_to_pass.map(lambda s: len(eval(s))) + df.pass_to_pass.map(
    lambda s: len(eval(s))
)

for col in ["patch_bytes", "files_touched", "n_tests"]:
    df[f"z_{col}"] = (df[col] - df[col].mean()) / df[col].std()
df["proxy"] = df.z_patch_bytes + df.z_files_touched + df.z_n_tests

uncovered = df[df.frontier_score.isna()]
if len(uncovered):
    print(f"WARNING: {len(uncovered)} instances have zero frontier coverage; proxy-only")
    df.loc[df.frontier_score.isna(), "frontier_score"] = -1.0  # proxy-only sinks to hardest

ranked = df.sort_values(
    ["frontier_score", "proxy", "instance_id"], ascending=[True, False, True]
).reset_index(drop=True)

sel = ranked.head(N)

def canonical_record(row):
    return {
        "instance_id": row.instance_id,
        "repo": row.repo,
        "repo_language": row.repo_language,
        "base_commit": row.base_commit,
        "dockerhub_tag": row.dockerhub_tag,
        "problem_statement_sha256": hashlib.sha256(
            row.problem_statement.encode("utf-8")
        ).hexdigest(),
        "gold_patch_sha256": hashlib.sha256(row.patch.encode("utf-8")).hexdigest(),
        "test_patch_sha256": hashlib.sha256(row.test_patch.encode("utf-8")).hexdigest(),
    }

instances = []
for i, row in enumerate(sel.itertuples()):
    rec = canonical_record(row)
    rec["rank"] = i + 1
    rec["frontier_score"] = row.frontier_score
    rec["frontier_coverage"] = row.frontier_cov
    rec["proxy_score"] = round(row.proxy, 6)
    rec["record_sha256"] = hashlib.sha256(
        json.dumps(canonical_record(row), sort_keys=True).encode()
    ).hexdigest()
    instances.append(rec)

out = {
    "metadata": {
        "dataset": "ScaleAI/SWE-bench_Pro",
        "dataset_revision": "7ab5114912baf22bb098818e604c02fe7ad2c11f",
        "dataset_split": "test",
        "dataset_n_total": len(df),
        "parquet_sha256": hashlib.sha256(open(PARQUET, "rb").read()).hexdigest(),
        "ranking_rule": (
            "frontier_score ASC (mean pass over leaderboard-config runs "
            f"{FRONTIER_RUNS}), tie-break proxy DESC "
            "(z(patch_bytes)+z(files_touched)+z(n_tests)), then instance_id ASC; "
            "top 100; trim rule drops from the end of this ordering"
        ),
        "harness_repo": "https://github.com/scaleapi/SWE-bench_Pro-os",
        "selected_n": len(instances),
        "frozen_utc": "2026-07-31",
    },
    "instances": instances,
}

dst = os.path.join(REPO, "bench5", "instances.json")
with open(dst, "w", newline="\n") as f:
    json.dump(out, f, indent=1)
print(f"wrote {dst} with {len(instances)} instances")
print("\nselection summary:")
print(sel.repo_language.value_counts())
print(sel.repo.value_counts())
print("frontier_score distribution:", sel.frontier_score.value_counts().to_dict())
