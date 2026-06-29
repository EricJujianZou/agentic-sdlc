"""Unit tests for adw/github.py — no live API calls."""
from __future__ import annotations

import json
import sys
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from adw.github import (
    ENGINE_REPO_ENV,
    GitHubError,
    add_labels,
    comment_on_issue,
    create_issue,
    engine_repo_slug,
    in_flight_ref,
    list_account_repos,
    list_open_issues,
    open_or_update_pr,
    outcome_comment_body,
    pr_body,
    remove_label,
    repo_slug,
    source_issue_number,
)
from adw.tickets import Story


def _story(**overrides) -> Story:
    base = dict(
        id="GH-42", type="feat", priority=5, title="My feature",
        description="desc", acceptance_criteria=["c"],
    )
    base.update(overrides)
    return Story(**base)


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

def test_source_issue_number_gh():
    assert source_issue_number("GH-42") == 42
    assert source_issue_number("GH-1") == 1


def test_source_issue_number_non_gh():
    assert source_issue_number("S-001") is None
    assert source_issue_number("GH-") is None
    assert source_issue_number("GH-abc") is None


def test_pr_body_contains_outcome():
    s = _story()
    body = pr_body(s, "done")
    assert "done" in body
    assert "GH-42" in body
    assert "My feature" in body


def test_pr_body_closes_source_issue_on_done():
    body = pr_body(_story(id="GH-42"), "done")
    assert "Closes #42" in body


def test_pr_body_no_close_when_blocked_or_plain_story():
    assert "Closes #" not in pr_body(_story(id="GH-42"), "blocked")
    assert "Closes #" not in pr_body(_story(id="S-006"), "done")


def test_pr_body_without_pr_description_is_unchanged():
    s = _story()
    assert pr_body(s, "done") == pr_body(s, "done", None)


def test_pr_body_renders_pr_description_when_present():
    s = _story(id="GH-42")
    body = pr_body(s, "done", "Summary of what changed and the risks.")
    assert "Summary of what changed and the risks." in body
    assert "Closes #42" in body


def test_outcome_comment_body_done():
    s = _story()
    text = outcome_comment_body(s, "done")
    assert "DONE" in text
    assert "GH-42" in text


def test_outcome_comment_body_blocked_with_reason():
    s = _story()
    text = outcome_comment_body(s, "blocked", "tests failed")
    assert "BLOCKED" in text
    assert "tests failed" in text


def test_outcome_comment_body_includes_test_evidence():
    text = outcome_comment_body(_story(), "done", test_evidence="209 passed")
    assert "209 passed" in text
    assert "CI" in text  # nudge to cross-check the local count against CI


def test_repo_slug_https():
    with patch("adw.github.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="https://github.com/EricJujianZou/agentic-sdlc.git\n")
        owner, repo = repo_slug("/fake/path")
    assert owner == "EricJujianZou"
    assert repo == "agentic-sdlc"


def test_repo_slug_ssh():
    with patch("adw.github.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="git@github.com:EricJujianZou/agentic-sdlc.git\n")
        owner, repo = repo_slug("/fake/path")
    assert owner == "EricJujianZou"
    assert repo == "agentic-sdlc"


# ---------------------------------------------------------------------------
# Request shaping via monkeypatched api_request
# ---------------------------------------------------------------------------

def test_open_or_update_pr_posts_correct_shape(monkeypatch):
    calls = []

    def fake_api(method, path, token, payload=None):
        calls.append((method, path, payload))
        return {"number": 1, "html_url": "https://github.com/..."}

    monkeypatch.setattr("adw.github.api_request", fake_api)
    open_or_update_pr("owner", "repo", "tok", "adw/GH-42", "main", "title", "body")
    assert calls[0][0] == "POST"
    assert "/repos/owner/repo/pulls" in calls[0][1]
    assert calls[0][2]["head"] == "adw/GH-42"
    assert calls[0][2]["base"] == "main"


def test_open_or_update_pr_patches_on_422(monkeypatch):
    calls = []

    def fake_api(method, path, token, payload=None):
        calls.append((method, path, payload))
        if method == "POST":
            raise GitHubError("HTTP 422 from POST /repos/o/r/pulls: already exists")
        if method == "GET":
            return [{"number": 7}]
        return {"number": 7}  # PATCH

    monkeypatch.setattr("adw.github.api_request", fake_api)
    open_or_update_pr("owner", "repo", "tok", "adw/GH-42", "main", "title", "updated body")
    methods = [c[0] for c in calls]
    assert "PATCH" in methods
    patch_call = next(c for c in calls if c[0] == "PATCH")
    assert "/pulls/7" in patch_call[1]
    assert patch_call[2]["body"] == "updated body"


def test_add_labels_correct_shape(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "adw.github.api_request",
        lambda method, path, token, payload=None: calls.append((method, path, payload)),
    )
    add_labels("owner", "repo", "tok", 42, ["in-progress"])
    assert calls[0][0] == "POST"
    assert "/issues/42/labels" in calls[0][1]
    assert calls[0][2]["labels"] == ["in-progress"]


def test_remove_label_swallows_404(monkeypatch):
    def fake_api(method, path, token, payload=None):
        raise GitHubError("HTTP 404 from DELETE: not labeled")

    monkeypatch.setattr("adw.github.api_request", fake_api)
    # A label that isn't on the issue must not raise — relabel is state-agnostic.
    remove_label("owner", "repo", "tok", 42, "in-progress")


def test_remove_label_reraises_non_404(monkeypatch):
    def fake_api(method, path, token, payload=None):
        raise GitHubError("HTTP 500 from DELETE: server error")

    monkeypatch.setattr("adw.github.api_request", fake_api)
    with pytest.raises(GitHubError, match="500"):
        remove_label("owner", "repo", "tok", 42, "in-progress")


def test_comment_on_issue_correct_shape(monkeypatch):
    calls = []

    def fake_api(method, path, token, payload=None):
        calls.append((method, path, payload))
        return {"id": 1}

    monkeypatch.setattr("adw.github.api_request", fake_api)
    comment_on_issue("owner", "repo", "tok", 42, "hello")
    assert calls[0][0] == "POST"
    assert "/issues/42/comments" in calls[0][1]
    assert calls[0][2]["body"] == "hello"


def test_create_issue_omits_labels_when_empty(monkeypatch):
    calls = []

    def fake_api(method, path, token, payload=None):
        calls.append((method, path, payload))
        return {"number": 9}

    monkeypatch.setattr("adw.github.api_request", fake_api)
    create_issue("owner", "repo", "tok", "title", "body")
    assert calls[0][0] == "POST"
    assert "/repos/owner/repo/issues" in calls[0][1]
    assert "labels" not in calls[0][2]


def test_create_issue_includes_labels_when_given(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "adw.github.api_request",
        lambda method, path, token, payload=None: calls.append((method, path, payload)),
    )
    create_issue("owner", "repo", "tok", "title", "body", labels=["self-heal-suggested"])
    assert calls[0][2]["labels"] == ["self-heal-suggested"]


def test_list_open_issues_filters_label_and_prs(monkeypatch):
    seen_path = {}

    def fake_api(method, path, token, payload=None):
        seen_path["path"] = path
        return [{"number": 1}, {"number": 2, "pull_request": {}}]

    monkeypatch.setattr("adw.github.api_request", fake_api)
    issues = list_open_issues("owner", "repo", "tok", label="self-heal-suggested")
    assert "labels=self-heal-suggested" in seen_path["path"]
    assert [i["number"] for i in issues] == [1]


def test_list_open_issues_no_label_filter(monkeypatch):
    seen_path = {}

    def fake_api(method, path, token, payload=None):
        seen_path["path"] = path
        return []

    monkeypatch.setattr("adw.github.api_request", fake_api)
    list_open_issues("owner", "repo", "tok")
    assert "labels=" not in seen_path["path"]


def test_engine_repo_slug_from_env(monkeypatch):
    monkeypatch.setenv(ENGINE_REPO_ENV, "SomeOrg/some-engine")
    assert engine_repo_slug() == ("SomeOrg", "some-engine")


def test_engine_repo_slug_malformed_env_raises(monkeypatch):
    monkeypatch.setenv(ENGINE_REPO_ENV, "not-a-slug")
    with pytest.raises(GitHubError, match=ENGINE_REPO_ENV):
        engine_repo_slug()


def test_engine_repo_slug_falls_back_to_engine_remote(monkeypatch):
    monkeypatch.delenv(ENGINE_REPO_ENV, raising=False)
    monkeypatch.setattr(
        "adw.github.repo_slug", lambda repo_root=None: ("EricJujianZou", "agentic-sdlc")
    )
    assert engine_repo_slug() == ("EricJujianZou", "agentic-sdlc")


def _repo(name, owner="EricJujianZou", archived=False, disabled=False):
    return {
        "name": name,
        "owner": {"login": owner},
        "archived": archived,
        "disabled": disabled,
        "clone_url": f"https://github.com/{owner}/{name}.git",
    }


def test_list_account_repos_filters_owner_archived_disabled(monkeypatch):
    page = [
        _repo("mine"),
        _repo("not-mine", owner="SomeoneElse"),
        _repo("dead", archived=True),
        _repo("off", disabled=True),
    ]

    def fake_api(method, path, token, payload=None):
        return page if "page=1" in path else []

    monkeypatch.setattr("adw.github.api_request", fake_api)
    repos = list_account_repos("tok", "EricJujianZou")
    assert repos == [("EricJujianZou", "mine", "https://github.com/EricJujianZou/mine.git")]


def test_list_account_repos_pages_until_short_page(monkeypatch):
    calls = []
    full_page = [_repo(f"repo{i}") for i in range(100)]
    last_page = [_repo("repo100")]

    def fake_api(method, path, token, payload=None):
        calls.append(path)
        if path.endswith("page=1"):
            return full_page
        if path.endswith("page=2"):
            return last_page
        return []

    monkeypatch.setattr("adw.github.api_request", fake_api)
    repos = list_account_repos("tok", "EricJujianZou")
    assert len(repos) == 101
    assert len(calls) == 2


def test_in_flight_ref_finds_open_pr(monkeypatch):
    monkeypatch.setattr("adw.github.api_request", lambda method, path, token, payload=None: [{"number": 6}])
    assert in_flight_ref("acme", "repo", "GH-2", "tok") == "PR #6"


def test_in_flight_ref_finds_branch_when_no_pr(monkeypatch):
    monkeypatch.setattr("adw.github.api_request", lambda method, path, token, payload=None: [])
    with patch("adw.github.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="abc123\trefs/heads/adw/GH-2\n")
        assert in_flight_ref("acme", "repo", "GH-2", "tok") == "branch adw/GH-2"


def test_in_flight_ref_none_when_neither(monkeypatch):
    monkeypatch.setattr("adw.github.api_request", lambda method, path, token, payload=None: [])
    with patch("adw.github.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="")
        assert in_flight_ref("acme", "repo", "GH-2", "tok") is None


def test_api_request_offline_raises_github_error(monkeypatch):
    import urllib.error

    def fake_urlopen(req):
        raise urllib.error.URLError("Network unreachable")

    monkeypatch.setattr("adw.github.urllib.request.urlopen", fake_urlopen)

    from adw.github import api_request
    with pytest.raises(GitHubError, match="offline"):
        api_request("GET", "/repos/o/r/issues", "tok")
