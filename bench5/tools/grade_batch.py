"""Grade pushed subject branches with the official SWE-bench Pro harness.

Collects patch.diff + meta.json from result branches (fetched from origin),
builds the harness inputs (raw_samples.jsonl + patches.json), invokes the
official eval script inside WSL (LF-safe), and summarizes per-branch
verdicts.

Usage:
  uv run --with pandas --with pyarrow python bench5/tools/grade_batch.py \
      --branches bench5/pilot-sonnet5-r005,... --results-subdir pilot/results \
      --out bench5/results/pilot_grades.json [--redo]

Branch layout expected: <results-subdir>/<model_short>/<rank>/patch.diff
holding the unified diff for the instance named in the sibling meta.json.
"""
import argparse
import json
import os
import subprocess

import pandas as pd

REPO = r"C:\Users\zouju\Coding Projects\agentic-sdlc"
PARQUET = os.path.join(REPO, "bench5", "data", "swebench_pro_test.parquet")
HARNESS_WIN = r"C:\Users\zouju\Coding Projects\SWE-bench_Pro-os"
HARNESS_WSL = "/mnt/c/Users/zouju/Coding Projects/SWE-bench_Pro-os"


def sh(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", cwd=REPO, **kw)
    if r.returncode != 0:
        raise RuntimeError(f"{cmd}: {r.stderr[:500]}")
    return r.stdout


def git_show(branch, path):
    return sh(["git", "show", f"origin/{branch}:{path}"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--branches", default="", help="comma-separated branch names (one result per branch)")
    ap.add_argument("--arm-branch", default="", help="arm branch holding many rNNN results")
    ap.add_argument("--results-prefix", default="", help="e.g. bench5/results/armB/sonnet5 (with --arm-branch)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--eval-dir", default="bench5_eval/out_batch",
                    help="output dir under the harness checkout")
    ap.add_argument("--redo", action="store_true")
    ap.add_argument("--keep-images", action="store_true",
                    help="skip post-run removal of sweap eval images (disk!)")
    args = ap.parse_args()

    sh(["git", "fetch", "origin"])
    df = pd.read_parquet(PARQUET).set_index("instance_id", drop=False)

    patches, rows, branch_info = [], {}, {}

    if args.arm_branch:
        # rank -> instance mapping from the frozen list is authoritative;
        # subject meta.json is recorded but not trusted for identity.
        frozen = json.load(open(os.path.join(REPO, "bench5", "instances.json")))
        by_rank = {r["rank"]: r["instance_id"] for r in frozen["instances"]}
        cell = args.results_prefix.rstrip("/").split("/")[-2] + "_" + \
            args.results_prefix.rstrip("/").split("/")[-1]
        tree = sh(["git", "ls-tree", "-r", "--name-only",
                   f"origin/{args.arm_branch}"])
        import re as _re
        ranks = sorted({int(m.group(1)) for m in _re.finditer(
            _re.escape(args.results_prefix) + r"/r(\d{3})/patch\.diff",
            tree)})
        print(f"{args.arm_branch}: {len(ranks)} results present")
        for rank in ranks:
            iid = by_rank[rank]
            prefix = f"{cell}_r{rank:03d}"
            outp = os.path.join(HARNESS_WIN,
                                args.eval_dir.replace("/", os.sep), iid,
                                f"{prefix}_output.json")
            if not args.redo and os.path.exists(outp):
                continue  # already graded
            patch = git_show(args.arm_branch,
                             f"{args.results_prefix}/r{rank:03d}/patch.diff")
            try:
                meta = json.loads(git_show(
                    args.arm_branch, f"{args.results_prefix}/r{rank:03d}/meta.json"))
            except RuntimeError:
                meta = {}
            patches.append({"instance_id": iid, "patch": patch, "prefix": prefix})
            rows[iid] = df.loc[iid]
            branch_info[prefix] = {"status": "collected", "instance_id": iid,
                                   "prefix": prefix, "meta": meta,
                                   "patch_bytes": len(patch)}

    for branch in (args.branches.split(",") if args.branches else []):
        branch = branch.strip()
        # find patch.diff + meta.json anywhere in the branch tree
        tree = sh(["git", "ls-tree", "-r", "--name-only", f"origin/{branch}"])
        patch_paths = [p for p in tree.splitlines() if p.endswith("patch.diff")]
        meta_paths = [p for p in tree.splitlines() if p.endswith("meta.json")]
        if not patch_paths or not meta_paths:
            print(f"SKIP {branch}: no patch.diff/meta.json")
            branch_info[branch] = {"status": "missing_artifacts"}
            continue
        meta = json.loads(git_show(branch, meta_paths[0]))
        patch = git_show(branch, patch_paths[0])
        iid = meta["instance_id"]
        if iid not in df.index:
            print(f"SKIP {branch}: unknown instance {iid}")
            branch_info[branch] = {"status": "unknown_instance", "instance_id": iid}
            continue
        prefix = branch.replace("/", "_")
        patches.append({"instance_id": iid, "patch": patch, "prefix": prefix})
        rows[iid] = df.loc[iid]
        branch_info[branch] = {"status": "collected", "instance_id": iid,
                               "prefix": prefix, "meta": meta,
                               "patch_bytes": len(patch)}

    if not patches:
        print("nothing to grade")
        return

    # Pre-pull eval images via docker CLI: the harness's SDK pull fails
    # silently on large images and grades become "no output.json".
    import sys
    sys.path.insert(0, HARNESS_WIN)
    from helper_code.image_uri import get_dockerhub_image_uri
    for iid, row in rows.items():
        uri = get_dockerhub_image_uri(iid, "jefzda", row["repo"])
        for attempt in (1, 2):
            r = subprocess.run(["docker", "pull", "-q", uri],
                               capture_output=True, text=True, timeout=3600)
            if r.returncode == 0:
                print(f"pulled {uri.split(':')[1][:60]}")
                break
            print(f"pull attempt {attempt} failed for {iid[:50]}: {r.stderr[:200]}")
        else:
            print(f"GIVING UP on image for {iid[:60]} - will grade as infra-fail")

    eval_dir_win = os.path.join(HARNESS_WIN, "bench5_eval")
    os.makedirs(eval_dir_win, exist_ok=True)
    tag = os.path.basename(args.out).replace(".json", "")
    samples_rel = f"bench5_eval/samples_{tag}.jsonl"
    patches_rel = f"bench5_eval/patches_{tag}.json"
    with open(os.path.join(HARNESS_WIN, samples_rel), "w", newline="\n",
              encoding="utf-8") as f:
        for iid, row in rows.items():
            f.write(json.dumps({c: row[c] for c in df.columns}) + "\n")
    with open(os.path.join(HARNESS_WIN, patches_rel), "w", newline="\n",
              encoding="utf-8") as f:
        json.dump(patches, f)

    # One harness invocation PER PATCH: the Docker Desktop WSL socket
    # intermittently drops mid-batch (first eval of an invocation always
    # succeeds, later ones die with FileNotFoundError on the socket), so
    # every eval runs as the first of its own invocation, preceded by a
    # socket-health wait.
    for i, patch_sample in enumerate(patches):
        single_rel = f"bench5_eval/patch_single_{tag}.json"
        with open(os.path.join(HARNESS_WIN, single_rel), "w", newline="\n",
                  encoding="utf-8") as f:
            json.dump([patch_sample], f)
        wait = ("n=0; until docker ps >/dev/null 2>&1; do sleep 10; n=$((n+1)); "
                "if [ $n -gt 30 ]; then echo SOCKET-WAIT-TIMEOUT; break; fi; done")
        cmd = (f"{wait}; cd '{HARNESS_WSL}' && python3 swe_bench_pro_eval.py "
               f"--raw_sample_path {samples_rel} --patch_path {single_rel} "
               f"--output_dir {args.eval_dir} --scripts_dir run_scripts "
               f"--dockerhub_username jefzda --use_local_docker --num_workers 1"
               + (" --redo" if args.redo else ""))
        print(f"[{i+1}/{len(patches)}] grading {patch_sample['prefix']}...", flush=True)
        r = subprocess.run(["wsl", "-d", "Ubuntu", "--", "bash", "-lc", cmd],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace")
        print(r.stdout[-600:], flush=True)
        if r.returncode != 0:
            print("HARNESS STDERR:", r.stderr[-800:], flush=True)

    # per-prefix verdicts: recompute from per-instance outputs (prefix-keyed)
    verdicts = {}
    for branch, info in branch_info.items():
        if info.get("status") != "collected":
            verdicts[branch] = {"pass": None, **info}
            continue
        iid, prefix = info["instance_id"], info["prefix"]
        outp = os.path.join(HARNESS_WIN, args.eval_dir.replace("/", os.sep),
                            iid, f"{prefix}_output.json")
        if not os.path.exists(outp):
            verdicts[branch] = {"pass": False, "note": "no output.json", **info}
            continue
        output = json.load(open(outp))
        passed = {t["name"] for t in output.get("tests", []) if t["status"] == "PASSED"}
        row = rows[iid]
        needed = set(eval(row["fail_to_pass"])) | set(eval(row["pass_to_pass"]))
        verdicts[branch] = {"pass": needed <= passed,
                            "n_needed": len(needed), "n_passed_needed":
                            len(needed & passed), **info}

    if not args.keep_images:
        # ~5-20GB per instance image; the disk cannot hold a full campaign
        rm = subprocess.run(
            'docker images --format "{{.Repository}}:{{.Tag}}" | '
            'grep "^jefzda/sweap-images:" | xargs -r docker rmi',
            shell=True, capture_output=True, text=True)
        print("image cleanup:", (rm.stdout or rm.stderr)[-300:].strip() or "nothing to remove")

    os.makedirs(os.path.dirname(os.path.join(REPO, args.out)), exist_ok=True)
    with open(os.path.join(REPO, args.out), "w", newline="\n") as f:
        json.dump(verdicts, f, indent=1, default=str)
    n = sum(1 for v in verdicts.values() if v.get("pass"))
    print(f"\n{n}/{len(verdicts)} PASS -> {args.out}")
    for b, v in sorted(verdicts.items()):
        print(f"  {v.get('pass')}  {b}")


if __name__ == "__main__":
    main()
