"""Shared workflow orchestration: the outer setup every adw workflow needs.

The feat/bug/trivial workflows differ only in their stage order; everything
else — the cooldown gate, config loading, story selection, work branch,
prompt composition, invoke wiring, and outcome bookkeeping — is identical
and lives here so the entry-point scripts in workflows/ stay thin and never
triplicate orchestration (architecture.md principle 1). Each workflow script
owns its stage order and passes it in; this module never decides it. The
backlog runner (workflows/run_backlog.py) reuses the same per-story core.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from adw import isolation, paths, runlog
from adw.github import (
    GitHubError,
    comment_on_issue,
    get_token,
    open_or_update_pr,
    outcome_comment_body,
    pr_body,
    repo_slug,
    source_issue_number,
)
from adw.invoke import invoke_stage
from adw.orchestrator import STAGE_ORDER, TicketOutcome, run_decompose, run_ticket
from adw.safety import CircuitBreaker, SafetyConfig, check_cooldown
from adw.state import State
from adw.tickets import Story, get_story, load_prd, mark_story, pick_next_story, save_prd

# All repo paths resolve through adw/paths.py: prd.json/state.json/git/runs
# land in the *target* repo (ADW_REPO, else the engine for self-hosting),
# while commands/ and configs/ default to the engine. Resolved at call time so
# a process honoring ADW_REPO operates entirely on the target.

# Which stage pipeline each ticket type runs; the backlog runner dispatches
# on this. feat/system-repair get the full cycle, bug skips review, chore
# skips planning. Mirrors the STAGE_ORDER each workflow script declares.
STAGE_ORDER_BY_TYPE: dict[str, tuple[str, ...]] = {
    "feat": STAGE_ORDER,
    "system-repair": STAGE_ORDER,
    "bug": ("plan", "implement", "test"),
    "chore": ("implement", "test"),
}


def _git(*args: str) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=paths.target_root(), capture_output=True, text=True, check=True
    )
    return proc.stdout.strip()


def _ensure_work_branch(branch: str) -> None:
    if _git("branch", "--list", branch):
        _git("checkout", branch)
    else:
        _git("checkout", "-b", branch)


def _commit_bookkeeping(message: str) -> None:
    """Commit orchestrator state changes (prd.json status flips) so stages
    start from a clean tree — read-only stages cannot commit them, and the
    Stop checklist fails any stage that leaves a dirty tree."""
    if _git("status", "--porcelain").strip():
        _git("add", "-A")
        _git("commit", "-m", message)


def _make_verify_fn(budgets: dict):
    """Build the deterministic test-evidence runner the orchestrator calls
    after the dual gate (improvements C3). Command and timeout are budgets
    knobs; a non-zero exit or a timeout counts as 'not verified', so a
    failing tree can never be accepted as done."""
    command = budgets.get("test_evidence_command") or ["uv", "run", "pytest", "-q"]
    timeout_seconds = budgets.get("test_evidence_timeout_minutes", 10) * 60

    def verify() -> tuple[bool, str]:
        try:
            proc = subprocess.run(
                command, cwd=paths.target_root(), capture_output=True, text=True,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired:
            return False, f"test-evidence run timed out after {timeout_seconds}s"
        if proc.returncode == 0:
            return True, ""
        detail = ((proc.stdout or "") + (proc.stderr or "")).strip()
        return False, detail[-800:] if detail else f"pytest exited {proc.returncode}"

    return verify


def _push_branch(branch: str) -> bool:
    """Push `branch` to origin; degrade (print, return False) on any failure
    so a missing remote or offline credential never affects ticket outcome."""
    try:
        subprocess.run(
            ["git", "push", "-u", "origin", branch],
            cwd=paths.target_root(), capture_output=True, text=True, check=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        print(f"github notify: push of {branch} failed, continuing without it: {exc}")
        return False


def _notify_github(story: Story, outcome: str, reason: str = "") -> None:
    """Best-effort outbound notification: push the work branch, open/update a
    PR for it, and comment the outcome on the source issue if one exists.
    Never raises — any GitHub/credential failure is printed and swallowed so
    a `done` ticket can never be turned into a failure by notification."""
    branch = f"adw/{story.id}"
    _push_branch(branch)
    try:
        token = get_token()
        owner, repo = repo_slug()
        open_or_update_pr(
            owner, repo, token,
            head=branch, base="main",
            title=f"{story.id}: {story.title}",
            body=pr_body(story, outcome),
        )
        issue_number = source_issue_number(story.id)
        if issue_number is not None:
            comment_on_issue(
                owner, repo, token, issue_number,
                outcome_comment_body(story, outcome, reason),
            )
    except GitHubError as exc:
        print(f"github notify skipped: {exc}")


def compose_stage_prompt(stage: str, state: State, story: Story, run_dir: Path) -> Path:
    """Concatenate the stage's command file with the ticket and state context."""
    command_file = paths.commands_dir() / f"{stage.upper()}.md"
    if not command_file.exists():
        raise FileNotFoundError(
            f"{command_file} missing — stage entry commands are owned by "
            "plans/prompts_plan.md and must exist before workflows can run."
        )
    ticket_context = json.dumps(
        {
            "ticket": {
                "id": story.id,
                "type": story.type,
                "title": story.title,
                "description": story.description,
                "acceptance_criteria": story.acceptance_criteria,
                "skill_match": story.skill_match,
            },
            "state": {
                "stage": stage,
                "iteration": state.iteration,
                "branch": state.branch,
                "last_failure": state.last_failure,
            },
        },
        indent=2,
    )
    prompt = (
        command_file.read_text(encoding="utf-8")
        + "\n\n## Your ticket and state\n\n```json\n"
        + ticket_context
        + "\n```\n"
    )
    # Prior stage outputs are the hand-off within a run (plans/harness_plan.md
    # §5): the plan stage is read-only, so its plan reaches implement/test/
    # review as a saved output file the agent can Read.
    prior_outputs = sorted(run_dir.glob("iter*_output.md"))
    if prior_outputs:
        listing = "\n".join(f"- {p.as_posix()}" for p in prior_outputs)
        prompt += (
            "\n## Prior stage outputs this run\n\n"
            "Read the ones relevant to your stage (the latest plan output "
            "is your work order):\n" + listing + "\n"
        )
    prompt_path = run_dir / f"iter{state.iteration:02d}_{stage}_prompt.md"
    prompt_path.write_text(prompt, encoding="utf-8")
    return prompt_path


def run_one_story(
    story: Story,
    stage_order: tuple[str, ...],
    *,
    models: dict,
    budgets: dict,
    max_iterations: int,
) -> TicketOutcome:
    """Run one story through `stage_order` and record its outcome in prd.json.
    Shared by the single-ticket CLI (run_workflow) and the backlog runner."""
    timeout_seconds = budgets["stage_timeout_minutes"] * 60
    _ensure_work_branch(f"adw/{story.id}")
    prd = load_prd(paths.prd_path())
    mark_story(prd, story.id, status="in_progress")
    save_prd(prd, paths.prd_path())
    _commit_bookkeeping(f"chore: mark {story.id} in_progress")
    run_dir = runlog.run_dir(story.id)

    def invoke(stage: str, state: State, story: Story):
        prompt_path = compose_stage_prompt(stage, state, story, run_dir)
        result = invoke_stage(
            prompt_path,
            stage=stage,
            model=models[stage],
            cwd=paths.target_root(),
            timeout_seconds=timeout_seconds,
        )
        output_path = run_dir / f"iter{state.iteration:02d}_{stage}_output.md"
        output_text = result.raw_output
        if result.stderr.strip():
            output_text += f"\n\n## stage stderr\n\n```\n{result.stderr.strip()}\n```\n"
        output_path.write_text(output_text, encoding="utf-8")
        return result

    # Decompose first if the ticket arrived criteria-less (e.g. a terse phone
    # issue, S-013): the read-only decompose stage proposes acceptance criteria
    # and the orchestrator (here, not the agent) persists them to prd.json
    # before planning. A vague ticket that cannot be expanded blocks here.
    if not story.acceptance_criteria:
        criteria, problem = run_decompose(story, invoke, state_path=paths.state_path())
        if problem is not None:
            prd = load_prd(paths.prd_path())
            mark_story(prd, story.id, status="blocked")
            save_prd(prd, paths.prd_path())
            _commit_bookkeeping(f"chore: record {story.id} outcome: blocked")
            return TicketOutcome(
                story.id, "blocked", reason=problem, stages_run=["decompose"]
            )
        story.acceptance_criteria = criteria
        prd = load_prd(paths.prd_path())
        get_story(prd, story.id).acceptance_criteria = criteria
        save_prd(prd, paths.prd_path())
        _commit_bookkeeping(f"chore: decompose {story.id} into acceptance criteria")

    outcome = run_ticket(
        story,
        invoke,
        stage_order=stage_order,
        state_path=paths.state_path(),
        max_iterations=max_iterations,
        breaker=CircuitBreaker(SafetyConfig.from_budgets(paths.budgets_path())),
        verify_fn=_make_verify_fn(budgets),
    )

    prd = load_prd(paths.prd_path())
    if outcome.outcome == "done":
        mark_story(prd, story.id, status="done", passes=True)
    else:
        mark_story(prd, story.id, status="blocked")
    save_prd(prd, paths.prd_path())
    _commit_bookkeeping(f"chore: record {story.id} outcome: {outcome.outcome}")
    _notify_github(story, outcome.outcome, outcome.reason or "")
    return outcome


def run_workflow(
    stage_order: tuple[str, ...],
    *,
    ticket_types: tuple[str, ...] | None = None,
    description: str = "",
) -> int:
    """Drive one ticket through `stage_order`. Returns a process exit code
    (0 = done, 1 = blocked/halted/cooldown-refused).

    `ticket_types` filters auto-selection so each workflow only picks the
    ticket types it is built for; an explicit --ticket overrides the filter.
    """
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--ticket", help="story id; defaults to highest-priority open story")
    parser.add_argument("--max-iterations", type=int, default=None)
    parser.add_argument(
        "--override-cooldown",
        action="store_true",
        help="start despite an active circuit cooldown (human judgment call)",
    )
    parser.add_argument(
        "--isolate",
        action="store_true",
        help="run stage sessions inside a docker container (plans/safety_plan.md §5); "
        "equivalent to setting ADW_ISOLATION=1. Requires a running Docker daemon "
        "and the adw-sandbox image — see README 'Container isolation'.",
    )
    args = parser.parse_args()
    if args.isolate:
        os.environ[isolation.ISOLATION_ENV] = "1"

    cooldown_msg = check_cooldown(paths.state_path())
    if cooldown_msg and not args.override_cooldown:
        print(f"refusing to start: {cooldown_msg}")
        print("pass --override-cooldown to start anyway")
        return 1

    models = json.loads(paths.models_path().read_text(encoding="utf-8"))
    budgets = json.loads(paths.budgets_path().read_text(encoding="utf-8"))
    max_iterations = args.max_iterations or budgets["max_iterations_default"]

    prd = load_prd(paths.prd_path())
    story = (
        get_story(prd, args.ticket)
        if args.ticket
        else pick_next_story(prd, types=ticket_types)
    )
    if story is None:
        print("no open story with passes=false — nothing to do")
        return 0

    outcome = run_one_story(
        story, stage_order, models=models, budgets=budgets, max_iterations=max_iterations
    )
    if outcome.outcome == "done":
        # Merge to main stays a human gate (plans/safety_plan.md §4); the
        # ticket is done, the branch awaits review/merge.
        print(f"{story.id} done after {outcome.iterations} iteration(s); "
              f"branch adw/{story.id} ready for merge gate")
    else:
        print(f"{story.id} {outcome.outcome}: {outcome.reason}")
    return 0 if outcome.outcome == "done" else 1


@dataclass
class BacklogResult:
    tickets_run: int
    stop_reason: str
    clean: bool  # True if the loop ended on an empty backlog or the bound


def run_backlog_loop(
    *,
    run_story_fn,
    cooldown_fn,
    max_tickets: int,
    prd_path=None,
    state_path=None,
) -> BacklogResult:
    """Outer loop over open stories (snarktank/ralph pattern). Picks the next
    open story, runs it via run_story_fn, and repeats until the backlog empties
    or max_tickets is hit. Stops (never skips) on the first non-done outcome,
    and never overrides an active circuit cooldown. Adds no new authority — the
    inner safety model (run_ticket + breaker) is untouched. run_story_fn and
    cooldown_fn are injected so the loop is testable without real workflows."""
    prd_path = paths.prd_path() if prd_path is None else prd_path
    state_path = paths.state_path() if state_path is None else state_path
    count = 0
    while count < max_tickets:
        cooldown = cooldown_fn(state_path)
        if cooldown is not None:
            return BacklogResult(count, f"circuit cooldown active; stopping: {cooldown}", False)
        prd = load_prd(prd_path)
        story = pick_next_story(prd)
        if story is None:
            return BacklogResult(count, "no open stories remain", True)
        outcome = run_story_fn(story)
        count += 1
        if outcome.outcome != "done":
            return BacklogResult(
                count, f"stopped at {story.id}: {outcome.outcome} ({outcome.reason})", False
            )
    return BacklogResult(count, f"reached --max-tickets ({max_tickets})", True)
