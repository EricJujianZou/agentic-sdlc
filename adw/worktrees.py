"""Git worktree lifecycle for parallel ticket execution (#4, Tier 1).

Each parallel ticket runs in its own `git worktree` on an `adw/<id>` branch so
one blocked ticket halts only its worktree, never the shared main working tree.
Worktrees are rooted in a *sibling* dir outside the target repo
(`../.adw-worktrees/<id>`) so they can never pollute the main tree's
`git status` or trip the repo's hooks (plans/parallelization_plan.md). Worktrees
share the object store and refs, so the parent coordinator can push an
`adw/<id>` branch after the worker returns (adw/workflow_runner.py).

The parent coordinator owns this whole lifecycle; workers only ever run inside
a worktree dir and never call these. Every operation is crash-safe: add prunes
stale admin entries and clears a leftover dir first, remove falls back to an
rmtree, and the `worktree` context manager removes in a `finally`.
"""
from __future__ import annotations

import shutil
import subprocess
from contextlib import contextmanager
from pathlib import Path

from adw import paths

# All worktrees live together under this sibling dir, outside the target repo.
WORKTREE_DIRNAME = ".adw-worktrees"


def _root(target_root: str | Path | None) -> Path:
    return Path(target_root) if target_root is not None else paths.target_root()


def worktrees_root(target_root: str | Path | None = None) -> Path:
    """The sibling dir holding all worktrees: `../.adw-worktrees` relative to
    the target repo, so a worktree never lands inside the main working tree."""
    return _root(target_root).parent / WORKTREE_DIRNAME


def worktree_path(story_id: str, target_root: str | Path | None = None) -> Path:
    """Where `story_id`'s worktree lives: `../.adw-worktrees/<id>`."""
    return worktrees_root(target_root) / story_id


def _git(target_root: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=str(target_root), capture_output=True, text=True, check=True
    )
    return proc.stdout.strip()


def prune(target_root: str | Path | None = None) -> None:
    """Clear stale worktree admin entries (orphans left by a hard crash)."""
    _git(_root(target_root), "worktree", "prune")


def _force_remove(target_root: Path, path: Path) -> None:
    """`git worktree remove --force`, falling back to an rmtree so cleanup
    always completes even when git no longer tracks the path."""
    try:
        _git(target_root, "worktree", "remove", "--force", str(path))
    except subprocess.CalledProcessError:
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)


def add_worktree(
    story_id: str, *, base: str = "main", target_root: str | Path | None = None
) -> Path:
    """Create `../.adw-worktrees/<id>` on a fresh `adw/<id>` branch off `base`.

    Crash-safe: prunes stale entries and clears any leftover dir first, then
    uses `-B` so a pre-existing `adw/<id>` branch is reset to `base` for a clean
    run. Returns the worktree path (a process can `cwd` into it)."""
    root = _root(target_root)
    path = worktree_path(story_id, root)
    prune(root)
    if path.exists():
        # An orphan dir from a hard crash: prune dropped the admin entry but
        # left the tree. `git worktree add` requires a missing path, so clear it.
        _force_remove(root, path)
    path.parent.mkdir(parents=True, exist_ok=True)
    _git(root, "worktree", "add", str(path), "-B", f"adw/{story_id}", base)
    return path


def remove_worktree(story_id: str, target_root: str | Path | None = None) -> None:
    """Remove a worktree and prune. Idempotent and tolerant of a missing one,
    so it is safe to call from a `finally` even if `add_worktree` never ran."""
    root = _root(target_root)
    _force_remove(root, worktree_path(story_id, root))
    prune(root)


@contextmanager
def worktree(story_id: str, *, base: str = "main", target_root: str | Path | None = None):
    """Add a worktree on enter and always remove + prune on exit (`try/finally`),
    so a worker exception or crash never leaks an orphan worktree."""
    root = _root(target_root)
    path = add_worktree(story_id, base=base, target_root=root)
    try:
        yield path
    finally:
        remove_worktree(story_id, target_root=root)
