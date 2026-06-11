"""Full-cycle workflow for feat tickets: pick -> plan -> implement -> test -> review.

Usage: uv run python workflows/feat_full_cycle.py [--ticket S-001] [--max-iterations N]

Deterministic control flow only; all intelligence lives in the prompt
assets the stage prompts point at. Stage prompts are composed from
commands/<STAGE>.md (prompts are data — this script never hardcodes
prompt content).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from adw import runlog
from adw.invoke import invoke_stage
from adw.orchestrator import run_ticket
from adw.safety import CircuitBreaker, SafetyConfig, check_cooldown
from adw.state import State
from adw.tickets import Story, get_story, load_prd, mark_story, pick_next_story, save_prd

PRD_PATH = REPO_ROOT / "prd.json"
STATE_PATH = REPO_ROOT / "state.json"
MODELS_PATH = REPO_ROOT / "configs" / "models.json"
BUDGETS_PATH = REPO_ROOT / "configs" / "budgets.json"
COMMANDS_DIR = REPO_ROOT / "commands"


def _git(*args: str) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    )
    return proc.stdout.strip()


def _ensure_work_branch(branch: str) -> None:
    branches = _git("branch", "--list", branch)
    if branches:
        _git("checkout", branch)
    else:
        _git("checkout", "-b", branch)


def _compose_stage_prompt(stage: str, state: State, story: Story, run_dir: Path) -> Path:
    """Concatenate the stage's command file with the ticket and state context."""
    command_file = COMMANDS_DIR / f"{stage.upper()}.md"
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ticket", help="story id; defaults to highest-priority open story")
    parser.add_argument("--max-iterations", type=int, default=None)
    parser.add_argument(
        "--override-cooldown",
        action="store_true",
        help="start despite an active circuit cooldown (human judgment call)",
    )
    args = parser.parse_args()

    cooldown_msg = check_cooldown(STATE_PATH)
    if cooldown_msg and not args.override_cooldown:
        print(f"refusing to start: {cooldown_msg}")
        print("pass --override-cooldown to start anyway")
        return 1

    models = json.loads(MODELS_PATH.read_text(encoding="utf-8"))
    budgets = json.loads(BUDGETS_PATH.read_text(encoding="utf-8"))
    max_iterations = args.max_iterations or budgets["max_iterations_default"]
    timeout_seconds = budgets["stage_timeout_minutes"] * 60

    prd = load_prd(PRD_PATH)
    story = get_story(prd, args.ticket) if args.ticket else pick_next_story(prd)
    if story is None:
        print("no open story with passes=false — nothing to do")
        return 0

    mark_story(prd, story.id, status="in_progress")
    save_prd(prd, PRD_PATH)
    _ensure_work_branch(f"adw/{story.id}")
    run_dir = runlog.run_dir(story.id)

    def invoke(stage: str, state: State, story: Story):
        prompt_path = _compose_stage_prompt(stage, state, story, run_dir)
        result = invoke_stage(
            prompt_path,
            stage=stage,
            model=models[stage],
            cwd=REPO_ROOT,
            timeout_seconds=timeout_seconds,
        )
        output_path = run_dir / f"iter{state.iteration:02d}_{stage}_output.md"
        output_path.write_text(result.raw_output, encoding="utf-8")
        return result

    outcome = run_ticket(
        story,
        invoke,
        state_path=STATE_PATH,
        max_iterations=max_iterations,
        breaker=CircuitBreaker(SafetyConfig.from_budgets(BUDGETS_PATH)),
    )

    prd = load_prd(PRD_PATH)
    if outcome.outcome == "done":
        # Merge to main stays a human gate (plans/safety_plan.md §4); the
        # ticket is done, the branch awaits review/merge.
        mark_story(prd, story.id, status="done", passes=True)
        print(f"{story.id} done after {outcome.iterations} iteration(s); "
              f"branch adw/{story.id} ready for merge gate")
    else:
        mark_story(prd, story.id, status="blocked")
        print(f"{story.id} {outcome.outcome}: {outcome.reason}")
    save_prd(prd, PRD_PATH)
    return 0 if outcome.outcome == "done" else 1


if __name__ == "__main__":
    raise SystemExit(main())
