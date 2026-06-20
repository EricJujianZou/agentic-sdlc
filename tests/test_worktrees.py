"""Worktree-lifecycle tests (#4, PR A).

Each test runs against a real temp git repo (not the engine), so add/remove/
prune exercise actual git plumbing. Covers: a worktree lands in the sibling
dir outside the repo on its own branch, removal cleans up, the context manager
removes even on an exception, and cleanup is idempotent / recovers from an
orphan dir left by a crash.
"""
import subprocess

import pytest

from adw import worktrees


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, check=True)


@pytest.fixture
def repo(tmp_path):
    """A temp git repo with one commit on `main`."""
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init")
    _git(root, "config", "user.email", "t@t.t")
    _git(root, "config", "user.name", "tester")
    (root / "f.txt").write_text("hello", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "init")
    _git(root, "branch", "-M", "main")
    return root


def _worktree_list(root):
    return subprocess.run(
        ["git", "worktree", "list"], cwd=str(root), capture_output=True, text=True, check=True
    ).stdout


def _branches(root):
    return subprocess.run(
        ["git", "branch", "--format=%(refname:short)"],
        cwd=str(root), capture_output=True, text=True, check=True,
    ).stdout.split()


def test_add_creates_sibling_worktree_on_its_own_branch(repo):
    path = worktrees.add_worktree("S-001", target_root=repo)
    # Rooted in the sibling dir OUTSIDE the repo — never inside the main tree.
    assert path == repo.parent / ".adw-worktrees" / "S-001"
    assert repo not in path.parents
    assert path.is_dir()
    assert (path / "f.txt").read_text(encoding="utf-8") == "hello"  # checked out from main
    assert "adw/S-001" in _branches(repo)
    assert path.as_posix() in _worktree_list(repo).replace("\\", "/")


def test_remove_cleans_up_the_worktree(repo):
    path = worktrees.add_worktree("S-002", target_root=repo)
    worktrees.remove_worktree("S-002", target_root=repo)
    assert not path.exists()
    assert path.as_posix() not in _worktree_list(repo).replace("\\", "/")


def test_remove_is_idempotent_when_nothing_to_remove(repo):
    # Safe to call from a finally even if add never ran — must not raise.
    worktrees.remove_worktree("S-404", target_root=repo)
    worktrees.prune(target_root=repo)


def test_context_manager_removes_on_exception(repo):
    path = worktrees.worktree_path("S-003", repo)

    class Boom(RuntimeError):
        pass

    with pytest.raises(Boom):
        with worktrees.worktree("S-003", target_root=repo) as wt:
            assert wt.is_dir()
            raise Boom("worker blew up")
    # The worktree was torn down despite the exception — no orphan left behind.
    assert not path.exists()
    assert path.as_posix() not in _worktree_list(repo).replace("\\", "/")


def test_add_recovers_from_orphan_dir(repo):
    # Simulate a hard crash: a leftover dir with no git admin entry.
    orphan = worktrees.worktree_path("S-005", repo)
    orphan.mkdir(parents=True)
    (orphan / "stale.txt").write_text("junk", encoding="utf-8")
    # add must clear the orphan and still produce a valid worktree.
    path = worktrees.add_worktree("S-005", target_root=repo)
    assert path.is_dir()
    assert not (path / "stale.txt").exists()
    assert (path / "f.txt").exists()


def test_add_resets_preexisting_branch(repo):
    # A leftover adw/<id> branch from a prior run is reset to base (-B), so a
    # re-run starts clean rather than failing on an existing branch.
    _git(repo, "branch", "adw/S-006")
    path = worktrees.add_worktree("S-006", target_root=repo)
    assert path.is_dir()
    assert "adw/S-006" in _branches(repo)
