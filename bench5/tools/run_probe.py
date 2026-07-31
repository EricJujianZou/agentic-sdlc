"""Memorization probe runner (see bench5/probe/README.md for method).

Usage:
  uv run --with pandas --with pyarrow python bench5/tools/run_probe.py [--models m1,m2] [--limit N]

Queries each model via `claude -p --model <m>` run from an empty scratch dir
(no repo context). Resumable: skips (instance, model) pairs already in
probe_results.json.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile

import pandas as pd

REPO = r"C:\Users\zouju\Coding Projects\agentic-sdlc"
PARQUET = os.path.join(REPO, "bench5", "data", "swebench_pro_test.parquet")
INSTANCES = os.path.join(REPO, "bench5", "instances.json")
OUT = os.path.join(REPO, "bench5", "probe", "probe_results.json")

PROMPT = """You are being tested on your knowledge of open-source repositories.
Repository: {repo}

Below is a GitHub issue from this repository. Based ONLY on your prior
knowledge of this codebase (you have no access to the code), predict which
source files the actual fix modified.

Respond with ONLY a JSON array of up to 10 file paths (repo-relative),
most likely first. No prose.

ISSUE:
{issue}
"""


def gold_files(patch):
    return re.findall(r"^diff --git a/(\S+) b/", patch, re.MULTILINE)


def mentioned(path, statement):
    base = path.rsplit("/", 1)[-1]
    return path in statement or base in statement


def norm(p):
    return p.strip().lstrip("./").replace("\\", "/")


def match(pred, gold):
    pred, gold = norm(pred), norm(gold)
    if pred == gold:
        return True
    parts = pred.split("/")
    return len(parts) >= 2 and gold.endswith("/" + pred)


def query(model, prompt, workdir):
    r = subprocess.run(
        ["claude", "-p", "--model", model, "--max-turns", "1"],
        input=prompt, capture_output=True, text=True, timeout=600,
        cwd=workdir, shell=True if os.name == "nt" else False,
    )
    return r.stdout.strip()


def parse_files(text):
    m = re.search(r"\[.*?\]", text, re.DOTALL)
    if not m:
        return []
    try:
        arr = json.loads(m.group(0))
        return [str(x) for x in arr if isinstance(x, str)][:10]
    except json.JSONDecodeError:
        return []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="claude-sonnet-5,claude-opus-5")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()
    models = args.models.split(",")

    df = pd.read_parquet(PARQUET).set_index("instance_id")
    frozen = json.load(open(INSTANCES))
    ids = [r["instance_id"] for r in frozen["instances"]]
    if args.limit:
        ids = ids[: args.limit]

    results = json.load(open(OUT)) if os.path.exists(OUT) else {}
    workdir = tempfile.mkdtemp(prefix="bench5_probe_")

    for i, iid in enumerate(ids):
        row = df.loc[iid]
        golds = gold_files(row.patch)
        scorable = [g for g in golds if not mentioned(g, row.problem_statement)]
        for model in models:
            key = f"{iid}::{model}"
            if key in results:
                continue
            out = query(model, PROMPT.format(repo=row.repo, issue=row.problem_statement), workdir)
            preds = parse_files(out)
            matched = [g for g in scorable if any(match(p, g) for p in preds)]
            results[key] = {
                "instance_id": iid,
                "model": model,
                "predicted": preds,
                "gold_files": golds,
                "scorable_gold": scorable,
                "matched": matched,
                "scorable": bool(scorable),
                "probe_recall": (len(matched) / len(scorable)) if scorable else None,
                "raw_output": out[:2000],
            }
            with open(OUT, "w", newline="\n") as f:
                json.dump(results, f, indent=1)
            print(f"[{i+1}/{len(ids)}] {model} {iid[:60]} recall="
                  f"{results[key]['probe_recall']}", flush=True)

    n_hi = len({r["instance_id"] for r in results.values()
                if r["probe_recall"] is not None and r["probe_recall"] >= 0.5})
    print(f"done. high-probe instances (either model >=0.5): {n_hi}")


if __name__ == "__main__":
    sys.exit(main())
