"""Tests for adw/paths.py — the engine-vs-target resolution that lets the
harness build any repo, not just itself (S-011).

Self-hosting must be unaffected: with ADW_REPO unset and cwd inside this repo,
the target resolves to the engine, which is exactly the pre-S-011 behavior the
rest of the suite already exercises. These tests pin the new axes: the env
override, the git-toplevel fallback, the no-git fallback, target-repo state
paths, and per-project .adw/ asset overrides.
"""
from __future__ import annotations

import subprocess

import pytest

from adw import paths


@pytest.fixture(autouse=True)
def _clear_target_cache():
    """target_root is memoized; reset around every test so env changes apply."""
    paths.target_root.cache_clear()
    yield
    paths.target_root.cache_clear()


def test_engine_root_holds_the_package_and_assets():
    root = paths.engine_root()
    assert (root / "adw" / "paths.py").exists()
    assert (root / "commands").is_dir()
    assert (root / "configs").is_dir()


def test_target_root_from_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("ADW_REPO", str(tmp_path))
    paths.target_root.cache_clear()
    assert paths.target_root() == tmp_path.resolve()


def test_target_root_git_toplevel_when_no_env(monkeypatch):
    # No ADW_REPO: falls back to the git top-level of cwd, which (running the
    # suite from inside this repo) is the engine itself.
    monkeypatch.delenv("ADW_REPO", raising=False)
    paths.target_root.cache_clear()
    assert paths.target_root() == paths.engine_root()


def test_target_root_detects_a_different_git_repo(monkeypatch, tmp_path):
    # A real, separate git repo: cwd inside it (no ADW_REPO) must resolve there,
    # not the engine — the genuine "operate on another repo" path.
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    monkeypatch.delenv("ADW_REPO", raising=False)
    monkeypatch.chdir(tmp_path)
    paths.target_root.cache_clear()
    assert paths.target_root() == tmp_path.resolve()
    assert paths.target_root() != paths.engine_root()


def test_target_root_falls_back_to_engine_without_git(monkeypatch):
    monkeypatch.delenv("ADW_REPO", raising=False)

    def no_git(*a, **k):
        raise FileNotFoundError("git not found")

    monkeypatch.setattr(paths.subprocess, "run", no_git)
    paths.target_root.cache_clear()
    assert paths.target_root() == paths.engine_root()


def test_state_paths_follow_the_target(monkeypatch, tmp_path):
    monkeypatch.setenv("ADW_REPO", str(tmp_path))
    paths.target_root.cache_clear()
    assert paths.prd_path() == tmp_path.resolve() / "prd.json"
    assert paths.state_path() == tmp_path.resolve() / "state.json"
    assert paths.runs_root() == tmp_path.resolve() / "observability" / "runs"
    assert paths.history_path() == tmp_path.resolve() / "observability" / "history.md"


def test_assets_default_to_engine(monkeypatch, tmp_path):
    # A target with no .adw/ override uses the engine's commands/ and configs/.
    monkeypatch.setenv("ADW_REPO", str(tmp_path))
    paths.target_root.cache_clear()
    assert paths.commands_dir() == paths.engine_root() / "commands"
    assert paths.configs_dir() == paths.engine_root() / "configs"
    assert paths.models_path() == paths.engine_root() / "configs" / "models.json"


def test_target_adw_override_wins(monkeypatch, tmp_path):
    (tmp_path / ".adw" / "commands").mkdir(parents=True)
    (tmp_path / ".adw" / "configs").mkdir(parents=True)
    monkeypatch.setenv("ADW_REPO", str(tmp_path))
    paths.target_root.cache_clear()
    assert paths.commands_dir() == tmp_path.resolve() / ".adw" / "commands"
    assert paths.configs_dir() == tmp_path.resolve() / ".adw" / "configs"
    assert paths.budgets_path() == tmp_path.resolve() / ".adw" / "configs" / "budgets.json"


def test_cross_repo_prd_roundtrip(monkeypatch, tmp_path):
    """End-to-end indirection: with ADW_REPO set, the ticket store reads/writes
    in the target repo, never the engine."""
    from adw.tickets import Prd, Story, load_prd, save_prd

    monkeypatch.setenv("ADW_REPO", str(tmp_path))
    paths.target_root.cache_clear()
    prd = Prd(project="other-project", stories=[
        Story(id="S-001", type="feat", priority=1, title="t",
              description="d", acceptance_criteria=["a"]),
    ])
    save_prd(prd, paths.prd_path())
    assert (tmp_path / "prd.json").exists()
    reloaded = load_prd(paths.prd_path())
    assert reloaded.project == "other-project"
    # The engine's own prd.json is untouched — the write landed in the target.
    engine_prd = load_prd(paths.engine_root() / "prd.json")
    assert engine_prd.project == "agentic-sdlc"
