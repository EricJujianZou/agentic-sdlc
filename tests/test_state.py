import pytest

from adw.state import State, load_state, new_state, save_state


def test_new_state_defaults_to_plan_stage_and_adw_branch():
    state = new_state("S-001")
    assert state.stage == "plan"
    assert state.iteration == 1
    assert state.branch == "adw/S-001"
    assert state.last_failure is None
    assert state.budget_used_tokens == 0


def test_invalid_stage_rejected():
    with pytest.raises(ValueError, match="stage"):
        State(ticket_id="S-001", stage="deploy")


def test_save_load_roundtrip(tmp_path):
    state = new_state("S-002")
    state.stage = "test"
    state.iteration = 3
    state.last_failure = "unit tests failed: 2 assertions"
    state.budget_used_tokens = 1234
    path = tmp_path / "state.json"
    save_state(state, path)
    assert load_state(path) == state
