"""Tests for the multi-repo sweep driver (GH-56), with injected fakes — no
live GitHub, no real git network calls, no real workflow stages."""
from __future__ import annotations

import datetime as _dt
import json

import pytest

import workflows.poll_all as poll_all
from adw import paths
from adw.orchestrator import TicketOutcome
from adw.state import State
from adw.tickets import Story


def _story(sid="GH-1", status="open") -> Story:
    return Story(
        id=sid, type="feat", priority=5, title="t", description="d",
        acceptance_criteria=["c"], status=status,
    )


# --- discovery + filter ------------------------------------------------------


def test_discover_targets_keeps_only_repos_with_open_adw_issues(monkeypatch):
    repos = [
        ("acme", "has-issues", "url1"),
        ("acme", "no-issues", "url2"),
        ("acme", "errors", "url3"),
    ]
    monkeypatch.setattr(poll_all, "list_account_repos", lambda token, owner: repos)

    def fake_list_adw_issues(owner, name, token):
        if name == "has-issues":
            return [{"number": 1}]
        if name == "no-issues":
            return []
        raise poll_all.GitHubError("boom")

    monkeypatch.setattr(poll_all, "list_adw_issues", fake_list_adw_issues)
    targets = poll_all.discover_targets("tok", "acme")
    assert [t.name for t in targets] == ["has-issues"]


# --- global cooldown ----------------------------------------------------------


def test_global_cooldown_round_trip_future_blocks(tmp_path, monkeypatch):
    monkeypatch.setenv("ADW_GLOBAL_BREAKER", str(tmp_path / "breaker.json"))
    future = (_dt.datetime.now(_dt.timezone.utc) + _dt.timedelta(hours=1)).isoformat()
    poll_all.write_global_cooldown(future, "quotad in repo-x")
    msg = poll_all.read_global_cooldown()
    assert msg is not None
    assert "quotad in repo-x" in msg


def test_global_cooldown_past_does_not_block(tmp_path, monkeypatch):
    monkeypatch.setenv("ADW_GLOBAL_BREAKER", str(tmp_path / "breaker.json"))
    past = (_dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(hours=1)).isoformat()
    poll_all.write_global_cooldown(past, "old")
    assert poll_all.read_global_cooldown() is None


def test_global_cooldown_missing_file_fails_open(tmp_path, monkeypatch):
    monkeypatch.setenv("ADW_GLOBAL_BREAKER", str(tmp_path / "nope" / "breaker.json"))
    assert poll_all.read_global_cooldown() is None


# --- _target context manager --------------------------------------------------


def test_target_context_flips_and_reverts(tmp_path, monkeypatch):
    monkeypatch.delenv("ADW_REPO", raising=False)
    paths.target_root.cache_clear()
    repo_a = tmp_path / "a"
    with poll_all._target(repo_a):
        assert paths.target_root() == repo_a.resolve()
    assert "ADW_REPO" not in __import__("os").environ
    paths.target_root.cache_clear()


def test_target_context_restores_prior_on_exception(tmp_path, monkeypatch):
    monkeypatch.setenv("ADW_REPO", str(tmp_path / "original"))
    paths.target_root.cache_clear()
    with pytest.raises(ValueError):
        with poll_all._target(tmp_path / "other"):
            raise ValueError("boom")
    import os
    assert os.environ["ADW_REPO"] == str(tmp_path / "original")
    paths.target_root.cache_clear()


# --- ensure_clone --------------------------------------------------------------


def test_ensure_clone_self_host_maps_to_engine_root_with_no_clone(monkeypatch):
    owner, name = poll_all._ENGINE_SLUG
    descriptor = poll_all.RepoDescriptor(owner, name, "https://example/x.git")
    called = []
    monkeypatch.setattr(poll_all.subprocess, "run", lambda *a, **k: called.append(a))
    result = poll_all.ensure_clone(descriptor)
    assert result == paths.engine_root()
    assert called == []


def test_ensure_clone_clones_when_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("ADW_REPOS_DIR", str(tmp_path / "repos"))
    descriptor = poll_all.RepoDescriptor("other-owner", "other-repo", "https://example/other.git")
    calls = []

    class _Proc:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(args, **kwargs):
        calls.append(args)
        return _Proc()

    monkeypatch.setattr(poll_all.subprocess, "run", fake_run)
    result = poll_all.ensure_clone(descriptor)
    assert result == tmp_path / "repos" / "other-owner" / "other-repo"
    assert calls[0][:2] == ["git", "clone"]


def test_ensure_clone_fetches_when_present(tmp_path, monkeypatch):
    monkeypatch.setenv("ADW_REPOS_DIR", str(tmp_path / "repos"))
    repo_dir = tmp_path / "repos" / "owner" / "name"
    repo_dir.mkdir(parents=True)
    descriptor = poll_all.RepoDescriptor("owner", "name", "https://example/name.git")
    calls = []

    class _Proc:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(args, **kwargs):
        calls.append(args)
        return _Proc()

    monkeypatch.setattr(poll_all.subprocess, "run", fake_run)
    result = poll_all.ensure_clone(descriptor)
    assert result == repo_dir
    assert ["git", "fetch", "--prune", "origin"] in calls


def test_ensure_clone_isolates_failure(tmp_path, monkeypatch):
    monkeypatch.setenv("ADW_REPOS_DIR", str(tmp_path / "repos"))
    descriptor = poll_all.RepoDescriptor("owner", "broken", "https://example/broken.git")

    def fake_run(args, **kwargs):
        raise poll_all.subprocess.CalledProcessError(1, args)

    monkeypatch.setattr(poll_all.subprocess, "run", fake_run)
    assert poll_all.ensure_clone(descriptor) is None


# --- sweep --------------------------------------------------------------------


def _stub_models_budgets(tmp_path, monkeypatch):
    configs = tmp_path / "configs"
    configs.mkdir()
    (configs / "models.json").write_text(
        json.dumps({s: "m" for s in ("plan", "implement", "test", "review", "decompose", "observe", "observe_triage")}),
        encoding="utf-8",
    )
    (configs / "budgets.json").write_text(
        json.dumps({"max_iterations_default": 3}), encoding="utf-8"
    )
    monkeypatch.setattr(paths, "configs_dir", lambda: configs)


def test_sweep_skips_work_when_global_cooldown_active(monkeypatch):
    monkeypatch.setattr(poll_all, "read_global_cooldown", lambda: "cooling down")
    result = poll_all.sweep()
    assert result.tickets_run == 0
    assert "cooling down" in result.stop_reason


def test_sweep_round_robins_across_repos(tmp_path, monkeypatch):
    monkeypatch.setattr(poll_all, "read_global_cooldown", lambda: None)
    monkeypatch.setattr(poll_all, "get_token", lambda: "tok")
    monkeypatch.setattr(poll_all, "engine_repo_slug", lambda: ("acme", "engine"))

    repos = [
        poll_all.RepoDescriptor("acme", "repo-a", "url-a"),
        poll_all.RepoDescriptor("acme", "repo-b", "url-b"),
        poll_all.RepoDescriptor("acme", "repo-c", "url-c"),
    ]
    monkeypatch.setattr(poll_all, "discover_targets", lambda token, owner: repos)

    repo_paths = {r.name: tmp_path / r.name for r in repos}
    monkeypatch.setattr(poll_all, "ensure_clone", lambda d: repo_paths[d.name])
    monkeypatch.setattr(poll_all, "pull_and_sync", lambda: ([], []))
    monkeypatch.setattr(poll_all, "reap_stale_in_progress", lambda **k: [])
    monkeypatch.setattr(poll_all, "in_flight_ref", lambda *a, **k: None)
    _stub_models_budgets(tmp_path, monkeypatch)

    # Each repo has exactly one open story; track which repo (by target_root)
    # picks/runs in what order.
    remaining = {name: 1 for name in repo_paths}
    order = []

    def fake_pick_next_story(prd, **kwargs):
        name = paths.target_root().name
        if remaining.get(name, 0) > 0:
            remaining[name] -= 1
            return _story(sid=f"GH-{name}")
        return None

    def fake_load_prd(path):
        return object()

    def fake_run_one_story(story, stage_order, **kwargs):
        order.append(paths.target_root().name)
        return TicketOutcome(story.id, "done", stages_run=["plan"])

    monkeypatch.setattr(poll_all, "pick_next_story", fake_pick_next_story)
    monkeypatch.setattr(poll_all, "load_prd", fake_load_prd)
    monkeypatch.setattr(poll_all, "run_one_story", fake_run_one_story)

    result = poll_all.sweep()
    assert result.tickets_run == 3
    assert order == ["repo-a", "repo-b", "repo-c"]
    assert result.stop_reason == "no open stories remain in any repo"


def test_sweep_isolates_one_repo_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(poll_all, "read_global_cooldown", lambda: None)
    monkeypatch.setattr(poll_all, "get_token", lambda: "tok")
    monkeypatch.setattr(poll_all, "engine_repo_slug", lambda: ("acme", "engine"))

    repos = [
        poll_all.RepoDescriptor("acme", "good", "url-good"),
        poll_all.RepoDescriptor("acme", "bad", "url-bad"),
    ]
    monkeypatch.setattr(poll_all, "discover_targets", lambda token, owner: repos)
    repo_paths = {r.name: tmp_path / r.name for r in repos}
    monkeypatch.setattr(poll_all, "ensure_clone", lambda d: repo_paths[d.name])
    monkeypatch.setattr(poll_all, "pull_and_sync", lambda: ([], []))
    monkeypatch.setattr(poll_all, "reap_stale_in_progress", lambda **k: [])
    monkeypatch.setattr(poll_all, "in_flight_ref", lambda *a, **k: None)
    _stub_models_budgets(tmp_path, monkeypatch)

    remaining = {"good": 1, "bad": 1}

    def fake_pick_next_story(prd, **kwargs):
        name = paths.target_root().name
        if remaining.get(name, 0) > 0:
            remaining[name] -= 1
            return _story(sid=f"GH-{name}")
        return None

    def fake_run_one_story(story, stage_order, **kwargs):
        if paths.target_root().name == "bad":
            raise RuntimeError("kaboom")
        return TicketOutcome(story.id, "done", stages_run=["plan"])

    monkeypatch.setattr(poll_all, "pick_next_story", fake_pick_next_story)
    monkeypatch.setattr(poll_all, "load_prd", lambda path: object())
    monkeypatch.setattr(poll_all, "run_one_story", fake_run_one_story)

    result = poll_all.sweep()
    # "good" ran successfully; "bad" raised and was dropped — the sweep
    # finished instead of aborting.
    assert result.tickets_run == 1


def test_sweep_quotad_writes_global_breaker_and_halts(tmp_path, monkeypatch):
    monkeypatch.setattr(poll_all, "read_global_cooldown", lambda: None)
    monkeypatch.setattr(poll_all, "get_token", lambda: "tok")
    monkeypatch.setattr(poll_all, "engine_repo_slug", lambda: ("acme", "engine"))

    repos = [
        poll_all.RepoDescriptor("acme", "r1", "url-1"),
        poll_all.RepoDescriptor("acme", "r2", "url-2"),
    ]
    monkeypatch.setattr(poll_all, "discover_targets", lambda token, owner: repos)
    repo_paths = {r.name: tmp_path / r.name for r in repos}
    monkeypatch.setattr(poll_all, "ensure_clone", lambda d: repo_paths[d.name])
    monkeypatch.setattr(poll_all, "pull_and_sync", lambda: ([], []))
    monkeypatch.setattr(poll_all, "reap_stale_in_progress", lambda **k: [])
    _stub_models_budgets(tmp_path, monkeypatch)

    monkeypatch.setattr(poll_all, "pick_next_story", lambda prd: _story(sid="GH-1"))
    monkeypatch.setattr(poll_all, "load_prd", lambda path: object())
    monkeypatch.setattr(
        poll_all, "run_one_story",
        lambda story, stage_order, **k: TicketOutcome(story.id, "quotad"),
    )
    cooldown_iso = "2026-07-01T00:00:00+00:00"
    monkeypatch.setattr(poll_all, "load_state", lambda path: State(ticket_id="GH-1", cooldown_until=cooldown_iso))

    written = {}
    monkeypatch.setattr(
        poll_all, "write_global_cooldown",
        lambda until_iso, reason: written.update(until_iso=until_iso, reason=reason),
    )

    result = poll_all.sweep()
    assert "quotad" in result.stop_reason
    assert written["until_iso"] == cooldown_iso


def test_sweep_no_active_repos_after_clone_failures(monkeypatch):
    monkeypatch.setattr(poll_all, "read_global_cooldown", lambda: None)
    monkeypatch.setattr(poll_all, "get_token", lambda: "tok")
    monkeypatch.setattr(poll_all, "engine_repo_slug", lambda: ("acme", "engine"))
    repos = [poll_all.RepoDescriptor("acme", "x", "url-x")]
    monkeypatch.setattr(poll_all, "discover_targets", lambda token, owner: repos)
    monkeypatch.setattr(poll_all, "ensure_clone", lambda d: None)

    result = poll_all.sweep()
    assert result.tickets_run == 0
    assert "no repos" in result.stop_reason


def test_sweep_self_host_only_engine_has_issues(tmp_path, monkeypatch):
    monkeypatch.setattr(poll_all, "read_global_cooldown", lambda: None)
    monkeypatch.setattr(poll_all, "get_token", lambda: "tok")
    owner, name = poll_all._ENGINE_SLUG
    monkeypatch.setattr(poll_all, "engine_repo_slug", lambda: (owner, name))
    repos = [poll_all.RepoDescriptor(owner, name, "https://example/engine.git")]
    monkeypatch.setattr(poll_all, "discover_targets", lambda token, o: repos)

    clone_calls = []
    original_ensure_clone = poll_all.ensure_clone

    def fake_ensure_clone(descriptor):
        clone_calls.append(descriptor)
        return original_ensure_clone(descriptor)

    monkeypatch.setattr(poll_all, "ensure_clone", fake_ensure_clone)
    monkeypatch.setattr(poll_all, "pull_and_sync", lambda: ([], []))
    monkeypatch.setattr(poll_all, "reap_stale_in_progress", lambda **k: [])
    _stub_models_budgets(tmp_path, monkeypatch)
    monkeypatch.setattr(poll_all, "pick_next_story", lambda prd: None)
    monkeypatch.setattr(poll_all, "load_prd", lambda path: object())

    result = poll_all.sweep()
    assert len(clone_calls) == 1
    assert result.tickets_run == 0
    assert result.stop_reason == "no open stories remain in any repo"
