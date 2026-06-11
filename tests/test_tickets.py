import json

import pytest

from adw.tickets import (
    Prd,
    PrdValidationError,
    Story,
    file_system_repair_story,
    load_prd,
    mark_story,
    next_story_id,
    pick_next_story,
    save_prd,
)


def story(**overrides) -> Story:
    base = dict(
        id="S-001",
        type="feat",
        priority=1,
        title="t",
        description="d",
        acceptance_criteria=["check passes"],
    )
    base.update(overrides)
    return Story(**base)


def write_prd(tmp_path, stories) -> str:
    path = tmp_path / "prd.json"
    path.write_text(json.dumps({"project": "p", "stories": stories}), encoding="utf-8")
    return str(path)


def test_load_save_roundtrip(tmp_path):
    prd = Prd(project="p", stories=[story()])
    path = tmp_path / "prd.json"
    save_prd(prd, path)
    assert load_prd(path) == prd


def test_load_rejects_missing_acceptance_criteria(tmp_path):
    path = write_prd(
        tmp_path,
        [{"id": "S-001", "type": "feat", "priority": 1, "title": "t", "description": "d"}],
    )
    with pytest.raises(PrdValidationError, match="acceptance_criteria"):
        load_prd(path)


def test_load_rejects_bad_type_and_duplicate_ids(tmp_path):
    s = {
        "id": "S-001",
        "type": "wat",
        "priority": 1,
        "title": "t",
        "description": "d",
        "acceptance_criteria": ["c"],
    }
    path = write_prd(tmp_path, [s, dict(s, type="feat")])
    with pytest.raises(PrdValidationError) as exc:
        load_prd(path)
    assert "type must be one of" in str(exc.value)
    assert "duplicate ids" in str(exc.value)


def test_pick_next_story_orders_by_priority_then_id():
    prd = Prd(
        project="p",
        stories=[
            story(id="S-003", priority=2),
            story(id="S-002", priority=1),
            story(id="S-001", priority=1, passes=True),
        ],
    )
    assert pick_next_story(prd).id == "S-002"


def test_pick_next_story_skips_non_open_and_returns_none_when_done():
    prd = Prd(
        project="p",
        stories=[
            story(id="S-001", status="blocked"),
            story(id="S-002", status="in_progress"),
            story(id="S-003", passes=True, status="done"),
        ],
    )
    assert pick_next_story(prd) is None


def test_mark_story_updates_status_and_passes():
    prd = Prd(project="p", stories=[story()])
    mark_story(prd, "S-001", status="done", passes=True)
    assert prd.stories[0].status == "done"
    assert prd.stories[0].passes is True
    with pytest.raises(ValueError):
        mark_story(prd, "S-001", status="nope")


def test_system_repair_story_is_blocked_and_never_picked():
    prd = Prd(project="p", stories=[story(id="S-001", passes=True, status="done")])
    repair = file_system_repair_story(
        prd,
        title="stage spec ambiguity",
        description="test_feat.md contradicts hooks on artifact path",
        evidence=["test_feat.md names a single artifact path"],
    )
    assert repair.id == "S-002"
    assert repair.type == "system-repair"
    assert repair.status == "blocked"
    assert pick_next_story(prd) is None
    # human approves
    mark_story(prd, repair.id, status="open")
    assert pick_next_story(prd).id == repair.id


def test_next_story_id_handles_empty_and_gaps():
    assert next_story_id(Prd(project="p")) == "S-001"
    prd = Prd(project="p", stories=[story(id="S-007")])
    assert next_story_id(prd) == "S-008"
