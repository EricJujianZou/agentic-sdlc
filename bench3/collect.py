"""Collect patches pushed by benchmark sessions into a predictions file.

Stdlib-only. Scans remote branches named bench3/<run_id>* for files under
bench3/results/<run_id>/, assembles the sb-cli predictions JSON, and writes a
run summary (per-instance timing/self-assessment from the meta files).

    uv run python bench3/collect.py --run-id armA-1
    uv run python bench3/collect.py --run-id armB-1

Outputs:
  bench3/results/<run_id>/predictions.json   (sb-cli format)
  bench3/results/<run_id>/summary.json       (timing, missing instances)

Run `git fetch origin` first. Trust note: patches come from session branches,
but the pass/fail verdicts come only from the official SWE-bench evaluation.
"""

import argparse
import json
import os
import subprocess

bench3 = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(bench3)


def _git(args, check=True):
    proc = subprocess.run(["git"] + args, cwd=REPO_ROOT,
                          capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout


def branches_for(run_id):
    out = _git(["branch", "-r", "--format=%(refname:short)"])
    names = [l.strip() for l in out.splitlines() if l.strip()]
    return [n for n in names
            if n.startswith(f"origin/bench3/{run_id}")]


def files_on(branch, run_id):
    prefix = f"bench3/results/{run_id}/"
    out = _git(["ls-tree", "-r", "--name-only", branch], check=False)
    return [l for l in out.splitlines() if l.startswith(prefix)]


def read_file(branch, path):
    return _git(["show", f"{branch}:{path}"])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-id", required=True)
    args = ap.parse_args()
    run_id = args.run_id

    with open(os.path.join(bench3, "manifest.json"), encoding="utf-8") as f:
        manifest = json.load(f)
    expected = set(manifest["instances"])

    predictions, meta = {}, {}
    for branch in branches_for(run_id):
        for path in files_on(branch, run_id):
            name = path.rsplit("/", 1)[-1]
            if name.endswith(".patch"):
                iid = name[:-len(".patch")]
                if iid in expected:
                    predictions[iid] = {
                        "instance_id": iid,
                        "model_patch": read_file(branch, path),
                        "model_name_or_path": f"bench3-{run_id}",
                    }
            elif name.endswith(".meta.json"):
                iid = name[:-len(".meta.json")]
                if iid in expected:
                    try:
                        meta[iid] = json.loads(read_file(branch, path))
                    except json.JSONDecodeError:
                        meta[iid] = {"error": "unparseable meta.json"}

    missing = sorted(expected - set(predictions))
    empty = sorted(i for i, p in predictions.items()
                   if not p["model_patch"].strip())

    out_dir = os.path.join(bench3, "results", run_id)
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "predictions.json"), "w",
              encoding="utf-8", newline="\n") as f:
        json.dump(predictions, f, indent=2)
        f.write("\n")
    summary = {"run_id": run_id, "collected": len(predictions),
               "expected": len(expected), "missing": missing,
               "empty_patches": empty, "meta": meta,
               "branches": branches_for(run_id)}
    with open(os.path.join(out_dir, "summary.json"), "w",
              encoding="utf-8", newline="\n") as f:
        json.dump(summary, f, indent=2)
        f.write("\n")

    print(f"{run_id}: collected {len(predictions)}/{len(expected)} patches "
          f"({len(empty)} empty), missing: {missing or 'none'}")
    print(f"wrote {out_dir}/predictions.json and summary.json")


if __name__ == "__main__":
    main()
