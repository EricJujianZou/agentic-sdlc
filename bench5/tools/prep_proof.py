"""Prepare grading-proof inputs: 2 sample instances, gold + empty patches.

Writes (LF-only, into the SWE-bench_Pro-os harness checkout):
  bench5_eval/raw_samples.jsonl   - the 2 instances' rows
  bench5_eval/gold_patches.json   - gold patches (expect PASS)
  bench5_eval/empty_patches.json  - whitespace no-op patches (expect FAIL)
"""
import json
import os

import pandas as pd

HARNESS = r"C:\Users\zouju\Coding Projects\SWE-bench_Pro-os"
PARQUET = r"C:\Users\zouju\Coding Projects\agentic-sdlc\bench5\data\swebench_pro_test.parquet"

df = pd.read_parquet(PARQUET)

# Two proof instances, one python one go, chosen for small patch + few test files.
cands = df[df.repo_language.isin(["python", "go"])].copy()
cands["patch_len"] = cands.patch.str.len()
cands["n_test_files"] = cands.selected_test_files_to_run.map(lambda s: len(eval(s)))
cands = cands.sort_values(["n_test_files", "patch_len"])
pick = pd.concat([
    cands[cands.repo_language == "python"].head(1),
    cands[cands.repo_language == "go"].head(1),
])

outdir = os.path.join(HARNESS, "bench5_eval")
os.makedirs(outdir, exist_ok=True)

cols = list(df.columns)
with open(os.path.join(outdir, "raw_samples.jsonl"), "w", newline="\n") as f:
    for _, row in pick.iterrows():
        f.write(json.dumps({c: row[c] for c in cols}) + "\n")

gold = [{"instance_id": r.instance_id, "patch": r.patch, "prefix": "gold"} for r in pick.itertuples()]
with open(os.path.join(outdir, "gold_patches.json"), "w", newline="\n") as f:
    json.dump(gold, f)

empty = [{"instance_id": r.instance_id, "patch": "", "prefix": "empty"} for r in pick.itertuples()]
with open(os.path.join(outdir, "empty_patches.json"), "w", newline="\n") as f:
    json.dump(empty, f)

for r in pick.itertuples():
    print(r.instance_id, "|", r.repo, "|", r.repo_language,
          "| patch_len", len(r.patch), "| test_files", len(eval(r.selected_test_files_to_run)),
          "| image tag:", r.dockerhub_tag)
