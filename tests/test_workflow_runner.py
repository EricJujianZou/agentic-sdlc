"""Tests for the shared workflow runner's test-evidence verifier (S-010).

The verifier is the orchestrator's deterministic re-run of the suite after
the dual gate. These stub subprocess.run so no real pytest is spawned, and
assert the exit code maps to pass/fail and a timeout counts as a failure.
"""
import subprocess

import adw.workflow_runner as workflow_runner
from adw import paths
from adw.github import GitHubError
from adw.orchestrator import TicketOutcome
from adw.tickets import Story
from adw.workflow_runner import _ensure_work_branch, _make_verify_fn, _notify_github


def _run_git(cwd, *args):
    return subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True, check=True
    ).stdout.strip()


def _init_repo(root):
    """A temp git repo on `main` with a committed prd.json."""
    root.mkdir()
    _run_git(root, "init")
    _run_git(root, "config", "user.email", "t@t.t")
    _run_git(root, "config", "user.name", "tester")
    (root / "prd.json").write_text('{"stories": []}', encoding="utf-8")
    _run_git(root, "add", "-A")
    _run_git(root, "commit", "-m", "init")
    _run_git(root, "branch", "-M", "main")
    return root


class _Proc:
    def __init__(self, returncode, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_verify_passes_on_zero_exit_and_reports_count(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _Proc(0, "131 passed in 4.2s"))
    verify = _make_verify_fn({"test_evidence_command": ["x"], "test_evidence_timeout_minutes": 1})
    passed, detail = verify()
    assert passed is True
    # On green, the pass count is surfaced for the outcome comment to report.
    assert detail == "131 passed"


def test_verify_passes_with_no_parseable_count(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _Proc(0, "ok"))
    verify = _make_verify_fn({})
    passed, detail = verify()
    assert passed is True
    assert detail == ""


def test_verify_fails_on_nonzero_exit_and_keeps_detail(monkeypatch):
    monkeypatch.setattr(
        subprocess, "run", lambda *a, **k: _Proc(1, stdout="1 failed, 130 passed")
    )
    verify = _make_verify_fn({})  # defaults: uv run pytest -q, 10 min
    passed, detail = verify()
    assert passed is False
    assert "1 failed" in detail


def test_verify_runs_in_given_cwd(monkeypatch):
    # A parallel worker passes its worktree dir so the re-run exercises that
    # tree's changes, not the pristine main tree (#4).
    seen = {}

    def record(*a, **k):
        seen["cwd"] = k.get("cwd")
        return _Proc(0, "5 passed")

    monkeypatch.setattr(subprocess, "run", record)
    verify = _make_verify_fn({}, cwd="/tmp/.adw-worktrees/S-001")
    passed, _ = verify()
    assert passed is True
    assert seen["cwd"] == "/tmp/.adw-worktrees/S-001"


def test_verify_treats_timeout_as_failure(monkeypatch):
    def boom(*a, **k):
        raise subprocess.TimeoutExpired(cmd="pytest", timeout=1)

    monkeypatch.setattr(subprocess, "run", boom)
    verify = _make_verify_fn({"test_evidence_timeout_minutes": 1})
    passed, detail = verify()
    assert passed is False
    assert "timed out" in detail


def _story(story_id="S-006"):
    return Story(
        id=story_id, type="feat", priority=1, title="t",
        description="d", acceptance_criteria=["a"],
    )


def test_notify_github_with_issue_id_opens_pr_and_comments(monkeypatch):
    calls = {}
    monkeypatch.setattr(workflow_runner, "_push_branch", lambda branch: True)
    monkeypatch.setattr(workflow_runner, "get_token", lambda: "tok")
    monkeypatch.setattr(workflow_runner, "repo_slug", lambda: ("o", "r"))
    monkeypatch.setattr(
        workflow_runner, "open_or_update_pr",
        lambda *a, **k: calls.setdefault("pr", (a, k)),
    )
    monkeypatch.setattr(
        workflow_runner, "comment_on_issue",
        lambda *a, **k: calls.setdefault("comment", (a, k)),
    )
    _notify_github(_story("GH-42"), "done", "")
    assert "pr" in calls
    assert calls["pr"][1]["head"] == "adw/GH-42"
    assert calls["pr"][1]["base"] == "main"
    assert "comment" in calls


def test_notify_github_without_issue_id_skips_comment(monkeypatch):
    calls = {}
    monkeypatch.setattr(workflow_runner, "_push_branch", lambda branch: True)
    monkeypatch.setattr(workflow_runner, "get_token", lambda: "tok")
    monkeypatch.setattr(workflow_runner, "repo_slug", lambda: ("o", "r"))
    monkeypatch.setattr(
        workflow_runner, "open_or_update_pr",
        lambda *a, **k: calls.setdefault("pr", (a, k)),
    )
    monkeypatch.setattr(
        workflow_runner, "comment_on_issue",
        lambda *a, **k: calls.setdefault("comment", (a, k)),
    )
    _notify_github(_story("S-006"), "done", "")
    assert "pr" in calls
    assert "comment" not in calls


def test_notify_github_swallows_github_error(monkeypatch):
    monkeypatch.setattr(workflow_runner, "_push_branch", lambda branch: True)

    def boom():
        raise GitHubError("offline")

    monkeypatch.setattr(workflow_runner, "get_token", boom)
    # should not raise
    _notify_github(_story("S-006"), "blocked", "reason")


def test_notify_github_still_tries_pr_after_push_failure(monkeypatch):
    calls = {}
    monkeypatch.setattr(workflow_runner, "_push_branch", lambda branch: False)
    monkeypatch.setattr(workflow_runner, "get_token", lambda: "tok")
    monkeypatch.setattr(workflow_runner, "repo_slug", lambda: ("o", "r"))
    monkeypatch.setattr(
        workflow_runner, "open_or_update_pr",
        lambda *a, **k: calls.setdefault("pr", (a, k)),
    )
    monkeypatch.setattr(workflow_runner, "comment_on_issue", lambda *a, **k: None)
    _notify_github(_story("S-006"), "done", "")
    assert "pr" in calls


# --- _make_progress_fn (S-014) ----------------------------------------------

def test_progress_fn_is_none_for_plain_story():
    # S-NNN has no source issue, so nothing is posted.
    assert workflow_runner._make_progress_fn(_story("S-006")) is None


def test_progress_fn_posts_to_source_issue(monkeypatch):
    posted = {}
    monkeypatch.setattr(workflow_runner, "get_token", lambda: "tok")
    monkeypatch.setattr(workflow_runner, "repo_slug", lambda: ("o", "r"))
    monkeypatch.setattr(
        workflow_runner, "comment_on_issue",
        lambda owner, repo, token, num, body: posted.update(num=num, body=body),
    )
    fn = workflow_runner._make_progress_fn(_story("GH-42"))
    assert fn is not None
    fn("plan", "success")
    assert posted["num"] == 42
    assert "plan" in posted["body"] and "GH-42" in posted["body"]


def test_progress_fn_swallows_github_error(monkeypatch):
    def boom():
        raise GitHubError("offline")

    monkeypatch.setattr(workflow_runner, "get_token", boom)
    fn = workflow_runner._make_progress_fn(_story("GH-42"))
    fn("plan", "success")  # must not raise


def test_progress_fn_includes_summary(monkeypatch):
    posted = {}
    monkeypatch.setattr(workflow_runner, "get_token", lambda: "tok")
    monkeypatch.setattr(workflow_runner, "repo_slug", lambda: ("o", "r"))
    monkeypatch.setattr(
        workflow_runner, "comment_on_issue",
        lambda owner, repo, token, num, body: posted.update(body=body),
    )
    fn = workflow_runner._make_progress_fn(_story("GH-42"))
    fn("test", "success", "209 passed, all acceptance criteria verified")
    assert "209 passed" in posted["body"]
    assert "test" in posted["body"]


# --- _finalize_story quotad (S-015) -----------------------------------------


def test_finalize_story_quotad_sets_status_label_skips_pr_and_observer(monkeypatch):
    from adw.tickets import Prd

    story = _story("S-006")
    prd = Prd(project="p", stories=[story])
    monkeypatch.setattr(workflow_runner, "load_prd", lambda path: prd)
    monkeypatch.setattr(workflow_runner, "save_prd", lambda prd, path: None)
    monkeypatch.setattr(workflow_runner, "_commit_bookkeeping", lambda message: None)

    set_label_calls = []
    monkeypatch.setattr(
        workflow_runner,
        "_set_run_label",
        lambda story, **kwargs: set_label_calls.append(kwargs),
    )

    def boom_notify(*a, **k):
        raise AssertionError("_notify_github must not be called for a quotad outcome")

    def boom_observe(*a, **k):
        raise AssertionError("_observe_and_report must not be called for a quotad outcome")

    monkeypatch.setattr(workflow_runner, "_notify_github", boom_notify)
    monkeypatch.setattr(workflow_runner, "_observe_and_report", boom_observe)

    outcome = TicketOutcome(story.id, "quotad", reason="provider usage limit reached")
    workflow_runner._finalize_story(
        story, outcome, observer_invoke=None, observer_state_path="state.json", budgets={},
    )

    assert story.status == "quotad"
    assert set_label_calls == [
        {"remove": (workflow_runner.RUN_LABEL_IN_PROGRESS,),
         "add": (workflow_runner.RUN_LABEL_QUOTAD,)}
    ]


# --- _set_run_label (S-014 follow-up) ---------------------------------------

def test_set_run_label_swaps_labels_for_issue(monkeypatch):
    added, removed = [], []
    monkeypatch.setattr(workflow_runner, "get_token", lambda: "tok")
    monkeypatch.setattr(workflow_runner, "repo_slug", lambda: ("o", "r"))
    monkeypatch.setattr(
        workflow_runner, "remove_label",
        lambda owner, repo, token, num, label: removed.append((num, label)),
    )
    monkeypatch.setattr(
        workflow_runner, "add_labels",
        lambda owner, repo, token, num, labels: added.append((num, labels)),
    )
    workflow_runner._set_run_label(
        _story("GH-42"),
        remove=(workflow_runner.RUN_LABEL_IN_PROGRESS,),
        add=(workflow_runner.RUN_LABEL_DONE,),
    )
    assert removed == [(42, "in-progress")]
    assert added == [(42, ["done"])]


def test_set_run_label_noop_for_plain_story(monkeypatch):
    def fail(*a, **k):
        raise AssertionError("must not touch GitHub for a non-issue story")

    monkeypatch.setattr(workflow_runner, "get_token", fail)
    workflow_runner._set_run_label(_story("S-006"), add=(workflow_runner.RUN_LABEL_DONE,))


def test_set_run_label_swallows_github_error(monkeypatch):
    def boom():
        raise GitHubError("offline")

    monkeypatch.setattr(workflow_runner, "get_token", boom)
    # Must not raise — a relabel failure can never change a ticket's outcome.
    workflow_runner._set_run_label(_story("GH-42"), add=(workflow_runner.RUN_LABEL_DONE,))


# --- _make_stage_label_fn (S-016 lifecycle board) ---------------------------

def test_stage_label_fn_is_none_for_plain_story():
    assert workflow_runner._make_stage_label_fn(_story("S-006")) is None


def test_stage_label_fn_swaps_prior_label(monkeypatch):
    added, removed = [], []
    monkeypatch.setattr(workflow_runner, "get_token", lambda: "tok")
    monkeypatch.setattr(workflow_runner, "repo_slug", lambda: ("o", "r"))
    monkeypatch.setattr(
        workflow_runner, "remove_label",
        lambda owner, repo, token, num, label: removed.append((num, label)),
    )
    monkeypatch.setattr(
        workflow_runner, "add_labels",
        lambda owner, repo, token, num, labels: added.append((num, labels)),
    )
    fn = workflow_runner._make_stage_label_fn(_story("GH-42"))
    fn("plan")
    assert added == [(42, ["stage:plan"])]
    assert removed == []
    fn("implement")
    assert added == [(42, ["stage:plan"]), (42, ["stage:implement"])]
    assert removed == [(42, "stage:plan")]


def test_stage_label_fn_swallows_github_error(monkeypatch):
    def boom():
        raise GitHubError("offline")

    monkeypatch.setattr(workflow_runner, "get_token", boom)
    fn = workflow_runner._make_stage_label_fn(_story("GH-42"))
    # Must not raise — a label failure can never change a ticket's outcome.
    fn("plan")


# --- compose_stage_prompt (cross-repo inline of PRIME + spec) ----------------

def test_compose_stage_prompt_inlines_prime_and_spec(tmp_path):
    # A stage agent whose cwd is the TARGET repo (when building another repo via
    # ADW_REPO) has no engine files on disk, so PRIME + the stage spec must be
    # inlined into the prompt rather than left as relative "Read this" lines.
    from adw.state import State

    story = Story(
        id="GH-1", type="feat", priority=5, title="Input primitive",
        description="add an Input", acceptance_criteria=["renders"],
    )
    path = workflow_runner.compose_stage_prompt(
        "plan", State(ticket_id="GH-1", stage="plan"), story, tmp_path
    )
    text = path.read_text(encoding="utf-8")

    assert "/PLAN" in text                                      # command inlined
    assert "Orientation — `commands/PRIME.md`" in text          # PRIME inlined
    assert "Stage spec — `stage_specs/plan_feat.md`" in text    # spec inlined
    assert "do **not** try to" in text                          # don't-Read note
    assert "GH-1" in text and "Input primitive" in text         # ticket context


def test_pr_title_does_not_double_the_id():
    def _s(sid, title):
        return Story(id=sid, type="feat", priority=5, title=title,
                     description="d", acceptance_criteria=["a"])

    # A story whose title already carries the id must not become "GH-1: GH-1: …".
    assert workflow_runner._pr_title(_s("GH-1", "GH-1: Input primitive")) == "GH-1: Input primitive"
    # A clean title is prefixed exactly once.
    assert workflow_runner._pr_title(_s("GH-2", "Card primitive")) == "GH-2: Card primitive"


# --- _ensure_work_branch (GH-46) --------------------------------------------

def test_ensure_work_branch_commits_dirty_sync_write_before_resuming(tmp_path, monkeypatch):
    # Reproduces the bug: sync rewrites prd.json on `main` and leaves it
    # uncommitted, then the backlog runner resumes a pre-existing adw/<id>
    # branch whose prd.json has diverged. Without the fix, `git checkout`
    # raises CalledProcessError because the dirty tree would be overwritten.
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setattr(paths, "target_root", lambda: repo)

    _run_git(repo, "checkout", "-b", "adw/GH-46")
    (repo / "prd.json").write_text('{"stories": [{"id": "GH-46"}]}', encoding="utf-8")
    _run_git(repo, "add", "-A")
    _run_git(repo, "commit", "-m", "work branch prd")
    _run_git(repo, "checkout", "main")

    # Simulate sync's uncommitted prd.json write on main.
    synced_content = '{"stories": [{"id": "GH-46"}, {"id": "GH-47"}]}'
    (repo / "prd.json").write_text(synced_content, encoding="utf-8")

    _ensure_work_branch("adw/GH-46")  # must not raise

    assert _run_git(repo, "rev-parse", "--abbrev-ref", "HEAD") == "adw/GH-46"
    _run_git(repo, "checkout", "main")
    assert (repo / "prd.json").read_text(encoding="utf-8") == synced_content
    assert _run_git(repo, "status", "--porcelain") == ""


def test_ensure_work_branch_fresh_path_leaves_dirty_tree_uncommitted(tmp_path, monkeypatch):
    # The fresh-branch path (`checkout -b`) must behave exactly as today:
    # the dirty tree carries over uncommitted.
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setattr(paths, "target_root", lambda: repo)

    (repo / "prd.json").write_text('{"stories": [{"id": "GH-47"}]}', encoding="utf-8")

    _ensure_work_branch("adw/GH-47")

    assert _run_git(repo, "rev-parse", "--abbrev-ref", "HEAD") == "adw/GH-47"
    assert _run_git(repo, "status", "--porcelain") != ""
