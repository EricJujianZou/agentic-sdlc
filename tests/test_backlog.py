"""Backlog-runner loop-termination tests (S-005).

The loop is driven with a fake run_story_fn and cooldown_fn so no real
workflow or subprocess is spawned. Covers the four ways the loop ends:
backlog empty, a blocked ticket, an active cooldown, and the max-tickets
bound.
"""
import json

from adw.tickets import load_prd, mark_story, save_prd
from adw.orchestrator import TicketOutcome
from adw.workflow_runner import run_backlog_loop


def _write_prd(path, n_open):
    stories = [
        {
            "id": f"S-{i:03d}", "type": "feat", "priority": i, "title": "t",
            "description": "d", "acceptance_criteria": ["c"],
            "status": "open", "passes": False,
        }
        for i in range(1, n_open + 1)
    ]
    path.write_text(json.dumps({"project": "p", "stories": stories}), encoding="utf-8")


def _no_cooldown(_state_path):
    return None


def _mark_done(prd_path, story_id):
    prd = load_prd(prd_path)
    mark_story(prd, story_id, status="done", passes=True)
    save_prd(prd, prd_path)


def test_stops_when_backlog_empty(tmp_path):
    prd_path = tmp_path / "prd.json"
    _write_prd(prd_path, 3)

    def run_story(story):
        _mark_done(prd_path, story.id)
        return TicketOutcome(story.id, "done")

    result = run_backlog_loop(
        run_story_fn=run_story, cooldown_fn=_no_cooldown, max_tickets=99,
        prd_path=prd_path, state_path=tmp_path / "state.json",
    )
    assert result.tickets_run == 3
    assert result.clean is True
    assert "no open stories" in result.stop_reason


def test_stops_on_blocked_without_skipping(tmp_path):
    prd_path = tmp_path / "prd.json"
    _write_prd(prd_path, 3)

    def run_story(story):
        if story.id == "S-002":
            prd = load_prd(prd_path)
            mark_story(prd, story.id, status="blocked")
            save_prd(prd, prd_path)
            return TicketOutcome(story.id, "blocked", reason="needs human")
        _mark_done(prd_path, story.id)
        return TicketOutcome(story.id, "done")

    result = run_backlog_loop(
        run_story_fn=run_story, cooldown_fn=_no_cooldown, max_tickets=99,
        prd_path=prd_path, state_path=tmp_path / "state.json",
    )
    assert result.tickets_run == 2  # S-001 done, S-002 blocked -> stop
    assert result.clean is False
    assert "S-002" in result.stop_reason and "blocked" in result.stop_reason
    # S-003 was never started (no skipping past the blocked ticket)
    assert load_prd(prd_path).stories[2].status == "open"


def test_active_cooldown_stops_loop_without_running(tmp_path):
    prd_path = tmp_path / "prd.json"
    _write_prd(prd_path, 3)
    ran = []

    def run_story(story):
        ran.append(story.id)
        return TicketOutcome(story.id, "done")

    def active_cooldown(_state_path):
        return "cooldown active for ~10 more minute(s)"

    result = run_backlog_loop(
        run_story_fn=run_story, cooldown_fn=active_cooldown, max_tickets=99,
        prd_path=prd_path, state_path=tmp_path / "state.json",
    )
    assert result.tickets_run == 0
    assert ran == []  # the cooldown is never silently overridden
    assert result.clean is False
    assert "cooldown" in result.stop_reason


def test_max_tickets_bounds_loop(tmp_path):
    prd_path = tmp_path / "prd.json"
    _write_prd(prd_path, 5)

    def run_story(story):
        _mark_done(prd_path, story.id)
        return TicketOutcome(story.id, "done")

    result = run_backlog_loop(
        run_story_fn=run_story, cooldown_fn=_no_cooldown, max_tickets=2,
        prd_path=prd_path, state_path=tmp_path / "state.json",
    )
    assert result.tickets_run == 2
    assert result.clean is True
    assert "max-tickets" in result.stop_reason
