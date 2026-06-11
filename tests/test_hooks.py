"""Hook scripts are exercised as real subprocesses with hook-protocol stdin,
since exit codes (0 allow / 2 deny) ARE the contract."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
GUARD = REPO_ROOT / "hooks" / "pretooluse_guard.py"
STOP = REPO_ROOT / "hooks" / "stop_checklist.py"
AUTOCOMMIT = REPO_ROOT / "hooks" / "posttooluse_autocommit.py"


def run_hook(script: Path, payload: dict, *, ticket_run: bool = False):
    env = {k: v for k, v in os.environ.items() if k != "ADW_TICKET_RUN"}
    if ticket_run:
        env["ADW_TICKET_RUN"] = "1"
    return subprocess.run(
        [sys.executable, str(script)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )


def bash_payload(command: str, cwd: str | None = None) -> dict:
    return {"tool_name": "Bash", "tool_input": {"command": command},
            "cwd": cwd or str(REPO_ROOT)}


@pytest.fixture
def git_repo(tmp_path):
    repo = tmp_path / "repo"  # sibling of transcripts etc., so they never dirty it
    repo.mkdir()

    def git(*args):
        subprocess.run(["git", *args], cwd=repo, capture_output=True, check=True)

    git("init", "-b", "main")
    git("config", "user.email", "t@t.t")
    git("config", "user.name", "t")
    (repo / "README.md").write_text("x\n", encoding="utf-8")
    git("add", ".")
    git("commit", "-m", "init")
    return repo


# --- pretooluse_guard: destructive commands (always enforced) ---

@pytest.mark.parametrize("command,fragment", [
    ("git push --force origin adw/S-001", "force push"),
    ("git push -f", "force push"),
    ("git push origin main", "pushing to main"),
    ("git reset --hard HEAD~3", "reset --hard"),
    ("git rebase -i HEAD~5", "history rewrites"),
    ("git commit --amend -m x", "history rewrites"),
    ("git commit -m x --no-verify", "--no-verify"),
    ("rm -rf /etc/passwd", "outside the worktree"),
    ("rm -rf ../other-project", "outside the worktree"),
    ("rm -rf C:/Users/somewhere", "outside the worktree"),
])
def test_guard_denies_destructive_commands(command, fragment):
    proc = run_hook(GUARD, bash_payload(command))
    assert proc.returncode == 2, proc.stderr
    assert fragment in proc.stderr


@pytest.mark.parametrize("command", [
    "git push origin adw/S-001",
    "rm -rf build/",
    "git commit -m 'normal commit'",
    "uv run pytest -q",
])
def test_guard_allows_safe_commands(command, git_repo):
    subprocess.run(["git", "checkout", "-b", "adw/S-001"], cwd=git_repo,
                   capture_output=True, check=True)
    proc = run_hook(GUARD, bash_payload(command, cwd=str(git_repo)))
    assert proc.returncode == 0, proc.stderr


def test_guard_denies_push_and_merge_while_on_main(git_repo):
    for command in ("git push", "git merge adw/S-001"):
        proc = run_hook(GUARD, bash_payload(command, cwd=str(git_repo)))
        assert proc.returncode == 2
        assert "on main" in proc.stderr


# --- pretooluse_guard: harness-file edits (ticket runs only) ---

def edit_payload(path: Path, cwd: Path) -> dict:
    return {"tool_name": "Edit", "tool_input": {"file_path": str(path)},
            "cwd": str(cwd)}


def write_project(tmp_path: Path, *, ticket_type: str) -> Path:
    (tmp_path / "state.json").write_text(json.dumps({
        "ticket_id": "S-009", "stage": "implement", "iteration": 1,
        "branch": "adw/S-009", "last_failure": None, "budget_used_tokens": 0,
    }), encoding="utf-8")
    (tmp_path / "prd.json").write_text(json.dumps({
        "project": "p",
        "stories": [{"id": "S-009", "type": ticket_type, "priority": 1,
                     "title": "t", "description": "d",
                     "acceptance_criteria": ["c"], "status": "in_progress"}],
    }), encoding="utf-8")
    return tmp_path


def test_guard_denies_harness_edit_during_normal_ticket_run(tmp_path):
    project = write_project(tmp_path, ticket_type="feat")
    proc = run_hook(GUARD, edit_payload(project / "hooks" / "x.py", project),
                    ticket_run=True)
    assert proc.returncode == 2
    assert "system-repair" in proc.stderr


def test_guard_allows_harness_edit_on_system_repair_ticket(tmp_path):
    project = write_project(tmp_path, ticket_type="system-repair")
    proc = run_hook(GUARD, edit_payload(project / "hooks" / "x.py", project),
                    ticket_run=True)
    assert proc.returncode == 0, proc.stderr


def test_guard_allows_harness_edit_in_attended_session(tmp_path):
    project = write_project(tmp_path, ticket_type="feat")
    proc = run_hook(GUARD, edit_payload(project / "hooks" / "x.py", project),
                    ticket_run=False)
    assert proc.returncode == 0, proc.stderr


def test_guard_allows_normal_source_edit_during_ticket_run(tmp_path):
    project = write_project(tmp_path, ticket_type="feat")
    proc = run_hook(GUARD, edit_payload(project / "src" / "app.py", project),
                    ticket_run=True)
    assert proc.returncode == 0, proc.stderr


# --- stop_checklist ---

def status_transcript(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "transcript.jsonl"
    line = json.dumps({"type": "assistant",
                       "message": {"content": [{"type": "text", "text": text}]}})
    path.write_text(line + "\n", encoding="utf-8")
    return path


GOOD_STATUS = json.dumps({"stage": "implement", "ticket_id": "S-001",
                          "outcome": "success", "files_changed": 1})


def stop_payload(git_repo: Path, transcript: Path, *, active: bool = False) -> dict:
    return {"transcript_path": str(transcript), "cwd": str(git_repo),
            "stop_hook_active": active}


def test_stop_inactive_outside_ticket_runs(git_repo, tmp_path):
    transcript = status_transcript(tmp_path, "no status block here")
    proc = run_hook(STOP, stop_payload(git_repo, transcript), ticket_run=False)
    assert proc.returncode == 0


def test_stop_passes_when_checklist_green(git_repo, tmp_path):
    transcript = status_transcript(tmp_path, f"done.\n{GOOD_STATUS}")
    proc = run_hook(STOP, stop_payload(git_repo, transcript), ticket_run=True)
    assert proc.returncode == 0, proc.stderr


def test_stop_blocks_on_missing_status_block(git_repo, tmp_path):
    transcript = status_transcript(tmp_path, "everything passes, trust me!")
    proc = run_hook(STOP, stop_payload(git_repo, transcript), ticket_run=True)
    assert proc.returncode == 2
    assert "status block" in proc.stderr


def test_stop_blocks_on_dirty_tree(git_repo, tmp_path):
    (git_repo / "uncommitted.py").write_text("x\n", encoding="utf-8")
    transcript = status_transcript(tmp_path, f"done.\n{GOOD_STATUS}")
    proc = run_hook(STOP, stop_payload(git_repo, transcript), ticket_run=True)
    assert proc.returncode == 2
    assert "not clean" in proc.stderr


def test_stop_blocks_on_progress_over_cap(git_repo, tmp_path):
    (git_repo / "progress.txt").write_text("line\n" * 150, encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=git_repo, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "progress"], cwd=git_repo,
                   capture_output=True, check=True)
    transcript = status_transcript(tmp_path, f"done.\n{GOOD_STATUS}")
    proc = run_hook(STOP, stop_payload(git_repo, transcript), ticket_run=True)
    assert proc.returncode == 2
    assert "150 lines" in proc.stderr


def test_stop_never_loops_forever(git_repo, tmp_path):
    transcript = status_transcript(tmp_path, "no status block")
    proc = run_hook(STOP, stop_payload(git_repo, transcript, active=True),
                    ticket_run=True)
    assert proc.returncode == 0


# --- posttooluse_autocommit ---

def test_autocommit_commits_edited_file(git_repo):
    target = git_repo / "src.py"
    target.write_text("print('hi')\n", encoding="utf-8")
    payload = {"tool_name": "Write", "tool_input": {"file_path": str(target)},
               "cwd": str(git_repo)}
    proc = run_hook(AUTOCOMMIT, payload, ticket_run=True)
    assert proc.returncode == 0, proc.stderr
    log = subprocess.run(["git", "log", "-1", "--format=%s"], cwd=git_repo,
                         capture_output=True, text=True, check=True).stdout
    assert "adw auto: write src.py" in log


def test_autocommit_inactive_outside_ticket_runs(git_repo):
    target = git_repo / "src.py"
    target.write_text("print('hi')\n", encoding="utf-8")
    payload = {"tool_name": "Write", "tool_input": {"file_path": str(target)},
               "cwd": str(git_repo)}
    proc = run_hook(AUTOCOMMIT, payload, ticket_run=False)
    assert proc.returncode == 0
    status = subprocess.run(["git", "status", "--porcelain"], cwd=git_repo,
                            capture_output=True, text=True, check=True).stdout
    assert "src.py" in status  # still uncommitted
