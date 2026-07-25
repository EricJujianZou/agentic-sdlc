"""Objective grader for the ledgerlite context-rot benchmark.

Stdlib-only. Run from the repo root:

    python bench/grade.py                      # grade working tree
    python bench/grade.py --out path.json      # choose report path
    python bench/grade.py --replay             # grade every commit since bench/base
    python bench/grade.py --write-manifest     # (maintainer) regenerate hash manifest
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

BENCH_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(BENCH_DIR)
TESTS_REL = "bench/target/tests"
TASKS_REL = "bench/tasks"
MANIFEST_REL = "bench/test_manifest.json"
BASE_BRANCH = "bench/base"
TASK_IDS = [f"T{i:02d}" for i in range(1, 11)]
# Prefixes (forward-slash, repo-relative) a solver is allowed to touch.
ALLOWED_PREFIXES = ("bench/target/ledgerlite/", "bench/results/", "bench/state", "bench/progress")


def _git(args, cwd=REPO_ROOT, check=True):
    proc = subprocess.run(["git"] + args, cwd=cwd, capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _manifest_targets(root):
    """Repo-relative (forward-slash) paths of all protected files under *root*."""
    out = []
    tests_dir = os.path.join(root, *TESTS_REL.split("/"))
    if os.path.isdir(tests_dir):
        for name in sorted(os.listdir(tests_dir)):
            p = os.path.join(tests_dir, name)
            if os.path.isfile(p):
                out.append(f"{TESTS_REL}/{name}")
    tasks_dir = os.path.join(root, *TASKS_REL.split("/"))
    if os.path.isdir(tasks_dir):
        for name in sorted(os.listdir(tasks_dir)):
            if name.endswith(".md"):
                out.append(f"{TASKS_REL}/{name}")
    return out


def build_manifest(root):
    return {rel: _sha256(os.path.join(root, *rel.split("/"))) for rel in _manifest_targets(root)}


def load_manifest():
    with open(os.path.join(REPO_ROOT, *MANIFEST_REL.split("/")), encoding="utf-8") as f:
        return json.load(f)


def check_integrity(root, manifest):
    """Compare protected files under *root* against the trusted manifest."""
    actual = build_manifest(root)
    bad = sorted(
        set(k for k, v in manifest.items() if actual.get(k) != v)
        | set(k for k in actual if k not in manifest)
    )
    return {"tests_tampered": bool(bad), "tampered_files": bad}


def run_test_file(rel_path, cwd):
    """Run one pytest file; nonzero exit (incl. collection error) == fail."""
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", rel_path, "-q", "--no-header",
         "-p", "no:cacheprovider"],
        cwd=cwd, capture_output=True, text=True,
    )
    tail = (proc.stdout or "").strip().splitlines()
    return {
        "status": "pass" if proc.returncode == 0 else "fail",
        "returncode": proc.returncode,
        "summary": tail[-1] if tail else (proc.stderr or "").strip().splitlines()[-1:] or "",
    }


def grade_tree(root):
    """Per-file grading of the tree at *root* (repo root or a worktree)."""
    results = {"base": run_test_file(f"{TESTS_REL}/test_base.py", root)}
    for tid in TASK_IDS:
        results[tid] = run_test_file(f"{TESTS_REL}/test_{tid.lower()}.py", root)
    passed = sum(1 for r in results.values() if r["status"] == "pass")
    counts = {"passed": passed, "failed": len(results) - passed, "total": len(results)}
    return results, counts


def merge_base():
    try:
        return _git(["merge-base", BASE_BRANCH, "HEAD"])
    except RuntimeError:
        return None


def scope_check(mb):
    if mb is None:
        return {"error": f"could not compute merge-base with {BASE_BRANCH}"}
    changed = [l for l in _git(["diff", "--name-only", mb, "HEAD"]).splitlines() if l]
    violations = [f for f in changed if not f.startswith(ALLOWED_PREFIXES)]
    return {"merge_base": mb, "changed_files": changed, "violations": violations,
            "scope_ok": not violations}


def replay(manifest):
    """Grade each commit on the current branch since the merge-base with bench/base."""
    mb = merge_base()
    if mb is None:
        return {"error": f"branch {BASE_BRANCH} not found; cannot replay"}
    commits = [c for c in _git(["rev-list", "--reverse", f"{mb}..HEAD"]).splitlines() if c]
    timeline = []
    for sha in commits:
        wt = tempfile.mkdtemp(prefix="bench_replay_")
        try:
            _git(["worktree", "add", "--detach", wt, sha])
            results, counts = grade_tree(wt)
            integrity = check_integrity(wt, manifest)
            timeline.append({
                "commit": sha,
                "subject": _git(["log", "-1", "--format=%s", sha]),
                "tasks": {k: v["status"] for k, v in results.items()},
                "counts": counts,
                **integrity,
            })
        finally:
            try:
                _git(["worktree", "remove", "--force", wt])
            except RuntimeError:
                pass
    # regressions: a task that passed at some commit and fails at a later one
    regressions = []
    seen_pass = {}
    for point in timeline:
        for task, status in point["tasks"].items():
            if status == "pass":
                seen_pass[task] = point["commit"]
            elif status == "fail" and task in seen_pass:
                regressions.append({"task": task, "passed_at": seen_pass[task],
                                    "failed_at": point["commit"]})
    return {"merge_base": mb, "commits_graded": len(commits),
            "timeline": timeline, "regressions": regressions}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="bench/results/report.json")
    ap.add_argument("--replay", action="store_true",
                    help="grade every commit since the merge-base with bench/base")
    ap.add_argument("--write-manifest", action="store_true",
                    help="(maintainer only) regenerate bench/test_manifest.json")
    args = ap.parse_args(argv)

    if args.write_manifest:
        manifest = build_manifest(REPO_ROOT)
        with open(os.path.join(REPO_ROOT, *MANIFEST_REL.split("/")), "w",
                  encoding="utf-8", newline="\n") as f:
            json.dump(manifest, f, indent=2)
            f.write("\n")
        print(f"wrote {MANIFEST_REL} ({len(manifest)} files)")
        return 0

    manifest = load_manifest()
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "replay" if args.replay else "working_tree",
    }

    mb = merge_base()
    report["scope"] = scope_check(mb)
    report.update(check_integrity(REPO_ROOT, manifest))

    if args.replay:
        report["replay"] = replay(manifest)
    else:
        results, counts = grade_tree(REPO_ROOT)
        report["tasks"] = results
        report["counts"] = counts

    out_path = args.out if os.path.isabs(args.out) else os.path.join(REPO_ROOT, args.out)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(report, f, indent=2)
        f.write("\n")

    # console summary
    if not args.replay:
        for name in ["base"] + TASK_IDS:
            print(f"{name:5s} {report['tasks'][name]['status']}")
        print(f"passed {report['counts']['passed']}/{report['counts']['total']}")
    else:
        for point in report["replay"].get("timeline", []):
            statuses = " ".join(f"{k}:{v[0]}" for k, v in point["tasks"].items())
            print(f"{point['commit'][:8]} {statuses}")
        print(f"regressions: {len(report['replay'].get('regressions', []))}")
    print(f"tests_tampered: {report['tests_tampered']}")
    if report.get("scope", {}).get("violations"):
        print(f"scope violations: {report['scope']['violations']}")
    print(f"report written to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
