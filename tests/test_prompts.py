"""Prompt assets are data the harness depends on; these tests pin the contract:
front-matter convention (plans/prompts_plan.md §5) and status-block sync with
adw/status.py (HANDOFF gotcha: keep stage_specs/commands in sync)."""
from pathlib import Path

import pytest

from adw.orchestrator import STAGE_ORDER
from adw.state import new_state
from adw.status import REQUIRED_KEYS
from adw.tickets import Story

REPO_ROOT = Path(__file__).resolve().parent.parent
PROMPT_MDS = [
    *(REPO_ROOT / "commands").glob("*.md"),
    *(REPO_ROOT / "stage_specs").glob("*.md"),
    *(REPO_ROOT / "skills").rglob("*.md"),
]
FRONT_MATTER_KEYS = ("name:", "description:", "read_when:", "sdlc_stage:")


@pytest.mark.parametrize("md", PROMPT_MDS, ids=lambda p: p.relative_to(REPO_ROOT).as_posix())
def test_front_matter_convention(md):
    text = md.read_text(encoding="utf-8")
    assert text.startswith("---\n"), "front-matter block missing"
    header = text.split("---", 2)[1]
    for key in FRONT_MATTER_KEYS:
        assert key in header, f"front-matter missing {key}"


@pytest.mark.parametrize("stage", STAGE_ORDER)
def test_stage_command_exists_with_status_contract(stage):
    command = REPO_ROOT / "commands" / f"{stage.upper()}.md"
    assert command.exists()
    text = command.read_text(encoding="utf-8")
    assert f'"stage": "{stage}"' in text
    for key in REQUIRED_KEYS + ("exit_signal", "summary", "failure_reason",
                                "files_changed", "suggested_tools",
                                "system_repair_suggested"):
        assert f'"{key}"' in text, f"{command.name} status template missing {key}"


@pytest.mark.parametrize("stage", STAGE_ORDER)
def test_feat_stage_spec_exists(stage):
    assert (REPO_ROOT / "stage_specs" / f"{stage}_feat.md").exists()


HEADLESS_STAGE_COMMANDS = ("PLAN", "IMPLEMENT", "TEST", "REVIEW")


@pytest.mark.parametrize("name", HEADLESS_STAGE_COMMANDS)
def test_headless_rule_present_in_stage_commands(name):
    """S-002: every loop-stage command must state it runs headless and that
    blockers go in the status block, never as a question to a human. Pins the
    rule so it cannot silently regress (evidence: test_run1.md follow-up 2)."""
    text = (REPO_ROOT / "commands" / f"{name}.md").read_text(encoding="utf-8").lower()
    assert "running headless" in text, f"{name}.md missing the headless framing"
    assert "no human will ever answer" in text, f"{name}.md missing the no-human rule"
    assert '"blocked"' in text, f"{name}.md must route blockers to outcome=blocked"


FAST_STOP_STAGE_COMMANDS = ("PLAN", "DECOMPOSE", "REVIEW")


@pytest.mark.parametrize("name", FAST_STOP_STAGE_COMMANDS)
def test_fast_stop_rule_present_in_readonly_stage_commands(name):
    """GH-64: read-only stages must report `blocked` immediately on a hard
    structural blocker rather than burning tokens producing the full
    deliverable first. IMPLEMENT/TEST are not read-only, so excluded here."""
    text = (REPO_ROOT / "commands" / f"{name}.md").read_text(encoding="utf-8").lower()
    assert "report `blocked` immediately" in text or "report \"blocked\" immediately" in text \
        or "blocked` immediately" in text, f"{name}.md missing the fast-stop rule"


def test_compose_stage_prompt_implement_harness_policy_by_type(tmp_path):
    from adw.workflow_runner import compose_stage_prompt

    state = new_state("S-001")
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    state.stage = "implement"

    feat_story = Story(id="S-001", type="feat", priority=1, title="t", description="d",
                        acceptance_criteria=["c"])
    feat_prompt = compose_stage_prompt("implement", state, feat_story, run_dir).read_text(encoding="utf-8")
    assert "outcome: \"blocked\"" in feat_prompt or '"blocked"' in feat_prompt
    assert "workflows/" in feat_prompt
    assert "Harness-edit policy" in feat_prompt

    repair_story = Story(id="GH-1", type="system-repair", priority=1, title="t", description="d",
                          acceptance_criteria=["c"])
    repair_prompt = compose_stage_prompt("implement", state, repair_story, run_dir).read_text(encoding="utf-8")
    assert "Harness-edit policy" not in repair_prompt


def test_compose_stage_prompt_includes_prior_outputs(tmp_path):
    from adw.workflow_runner import compose_stage_prompt

    story = Story(id="S-001", type="feat", priority=1, title="t", description="d",
                  acceptance_criteria=["c"])
    state = new_state("S-001")
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    state.stage = "plan"
    plan_prompt = compose_stage_prompt("plan", state, story, run_dir)
    text = plan_prompt.read_text(encoding="utf-8")
    assert "/PLAN" in text and '"id": "S-001"' in text
    assert "Prior stage outputs" not in text  # nothing produced yet

    (run_dir / "iter01_plan_output.md").write_text("the plan", encoding="utf-8")
    state.stage = "implement"
    impl_prompt = compose_stage_prompt("implement", state, story, run_dir)
    text = impl_prompt.read_text(encoding="utf-8")
    assert "iter01_plan_output.md" in text
    assert "File manifest" not in text  # no status block in this output, degrades cleanly


def test_compose_stage_prompt_inlines_file_manifest(tmp_path):
    from adw.workflow_runner import compose_stage_prompt

    story = Story(id="GH-61", type="system-repair", priority=1, title="t", description="d",
                  acceptance_criteria=["c"])
    state = new_state("GH-61")
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    plan_output = (
        '```json\n'
        '{"stage": "plan", "ticket_id": "GH-61", "outcome": "success", '
        '"file_manifest": {"edit": ["adw/status.py"], "read": ["adw/workflow_runner.py:466"]}}\n'
        '```\n'
    )
    (run_dir / "iter01_plan_output.md").write_text(plan_output, encoding="utf-8")

    state.stage = "implement"
    impl_prompt = compose_stage_prompt("implement", state, story, run_dir)
    text = impl_prompt.read_text(encoding="utf-8")
    assert "File manifest" in text
    assert "open only these" in text.lower()
    assert "adw/status.py" in text
    assert "adw/workflow_runner.py:466" in text
