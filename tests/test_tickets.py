import json
import subprocess

import pytest

from adw.tickets import (
    Prd,
    PrdValidationError,
    Story,
    file_system_repair_story,
    load_prd,
    mark_story,
    next_story_id,
    pick_next_stories,
    pick_next_story,
    reclaim_stale_in_progress,
    reconcile_completed,
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


def test_save_prd_leaves_no_temp_files(tmp_path):
    # The atomic write goes through a sibling temp file; it must not linger.
    # The store shards into a prd/ directory: one file per story + _meta.json.
    save_prd(Prd(project="p", stories=[story()]), tmp_path / "prd.json")
    prd_dir = tmp_path / "prd"
    assert sorted(p.name for p in prd_dir.iterdir()) == ["S-001.json", "_meta.json"]


def test_save_prd_failure_leaves_original_intact(tmp_path, monkeypatch):
    # If the replace step fails mid-write, the existing shards must be untouched
    # (no torn file) and the temp file must be cleaned up.
    import adw.tickets as tickets

    path = tmp_path / "prd.json"
    save_prd(Prd(project="orig", stories=[story()]), path)
    prd_dir = tmp_path / "prd"
    before = {p.name: p.read_text(encoding="utf-8") for p in prd_dir.iterdir()}

    def boom(src, dst):
        raise OSError("replace failed")

    monkeypatch.setattr(tickets.os, "replace", boom)
    with pytest.raises(OSError):
        save_prd(Prd(project="new", stories=[]), path)

    assert {p.name: p.read_text(encoding="utf-8") for p in prd_dir.iterdir()} == before


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


# --- sharding (GH-79) --------------------------------------------------------

def test_save_writes_one_shard_per_story_and_no_legacy_file(tmp_path):
    prd = Prd(project="p", stories=[story(id="S-001"), story(id="GH-61")])
    save_prd(prd, tmp_path / "prd.json")
    assert not (tmp_path / "prd.json").exists()  # the anchor file is never written
    assert sorted(p.name for p in (tmp_path / "prd").iterdir()) == [
        "GH-61.json", "S-001.json", "_meta.json",
    ]


def test_load_prefers_shards_over_a_stale_legacy_file(tmp_path):
    # A pre-sharding tombstone may linger alongside the live shards; shards win.
    save_prd(Prd(project="p", stories=[story(id="S-001", status="done", passes=True)]),
             tmp_path / "prd.json")
    (tmp_path / "prd.json").write_text(
        json.dumps({"project": "p", "stories": [
            {"id": "S-001", "type": "feat", "priority": 1, "title": "t",
             "description": "d", "acceptance_criteria": ["c"], "status": "open"},
        ]}), encoding="utf-8")
    loaded = load_prd(tmp_path / "prd.json")
    assert loaded.stories[0].status == "done"


def test_load_falls_back_to_legacy_single_file_when_unmigrated(tmp_path):
    path = write_prd(tmp_path, [
        {"id": "S-001", "type": "feat", "priority": 1, "title": "t",
         "description": "d", "acceptance_criteria": ["c"]},
    ])
    assert not (tmp_path / "prd").exists()
    assert load_prd(path).stories[0].id == "S-001"


def test_load_raises_when_neither_shards_nor_legacy_exist(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_prd(tmp_path / "prd.json")


def test_save_removes_shards_for_dropped_stories(tmp_path):
    save_prd(Prd(project="p", stories=[story(id="S-001"), story(id="S-002")]),
             tmp_path / "prd.json")
    save_prd(Prd(project="p", stories=[story(id="S-001")]), tmp_path / "prd.json")
    assert not (tmp_path / "prd" / "S-002.json").exists()
    assert load_prd(tmp_path / "prd.json").stories == [story(id="S-001")]


def test_load_rejects_shard_whose_id_disagrees_with_filename(tmp_path):
    save_prd(Prd(project="p", stories=[story(id="S-001")]), tmp_path / "prd.json")
    (tmp_path / "prd" / "S-001.json").write_text(
        json.dumps(dict(json.loads((tmp_path / "prd" / "S-001.json").read_text()), id="S-999")),
        encoding="utf-8",
    )
    with pytest.raises(PrdValidationError, match="does not match filename"):
        load_prd(tmp_path / "prd.json")


def _git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True,
                   capture_output=True, text=True)


def test_independent_story_branches_merge_without_conflict(tmp_path):
    """The whole point of GH-79: two ticket branches that each touch only their
    own story merge to a base branch with no prd merge conflict."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    prd_path = repo / "prd.json"
    save_prd(Prd(project="p", stories=[story(id="GH-1"), story(id="GH-2")]), prd_path)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "base")
    base = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo,
                          capture_output=True, text=True, check=True).stdout.strip()

    # Branch A advances only GH-1.
    _git(repo, "checkout", "-q", "-b", "adw/GH-1")
    p = load_prd(prd_path); mark_story(p, "GH-1", status="done", passes=True)
    save_prd(p, prd_path)
    _git(repo, "commit", "-qam", "GH-1 done")

    # Branch B (off base) advances only GH-2.
    _git(repo, "checkout", "-q", base)
    _git(repo, "checkout", "-q", "-b", "adw/GH-2")
    p = load_prd(prd_path); mark_story(p, "GH-2", status="done", passes=True)
    save_prd(p, prd_path)
    _git(repo, "commit", "-qam", "GH-2 done")

    # Merge B into A — clean, no conflict, and both stories are terminal.
    _git(repo, "checkout", "-q", "adw/GH-1")
    merge = subprocess.run(["git", "merge", "--no-edit", "adw/GH-2"], cwd=repo,
                           capture_output=True, text=True)
    assert merge.returncode == 0, merge.stdout + merge.stderr
    merged = load_prd(prd_path)
    assert {s.id: s.status for s in merged.stories} == {"GH-1": "done", "GH-2": "done"}


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


def test_pick_next_story_exclude_drops_candidate():
    prd = Prd(
        project="p",
        stories=[
            story(id="S-001", priority=1),
            story(id="S-002", priority=2),
        ],
    )
    assert pick_next_story(prd, exclude={"S-001"}).id == "S-002"
    assert pick_next_story(prd, exclude={"S-001", "S-002"}) is None
    assert pick_next_story(prd).id == "S-001"  # no exclude: regression-free


def test_pick_next_story_picks_quotad_but_not_blocked():
    prd = Prd(
        project="p",
        stories=[
            story(id="S-001", status="blocked"),
            story(id="S-002", status="quotad", priority=1),
        ],
    )
    assert pick_next_story(prd).id == "S-002"


def test_load_prd_accepts_quotad_status(tmp_path):
    path = write_prd(
        tmp_path,
        [{
            "id": "S-001", "type": "feat", "priority": 1, "title": "t",
            "description": "d", "acceptance_criteria": ["c"], "status": "quotad",
        }],
    )
    prd = load_prd(path)
    assert prd.stories[0].status == "quotad"


def test_mark_story_accepts_quotad_status():
    prd = Prd(project="p", stories=[story()])
    mark_story(prd, "S-001", status="quotad")
    assert prd.stories[0].status == "quotad"


def test_pick_next_stories_returns_top_n_by_priority(tmp_path):
    prd = Prd(
        project="p",
        stories=[
            story(id="S-004", priority=3),
            story(id="S-001", priority=1),
            story(id="S-003", priority=2),
            story(id="S-002", priority=1),
            story(id="S-009", priority=1, passes=True),   # done -> excluded
            story(id="S-008", status="blocked"),          # not open -> excluded
        ],
    )
    picked = [s.id for s in pick_next_stories(prd, 3)]
    # Same (priority, id) order as pick_next_story, just the top N of them.
    assert picked == ["S-001", "S-002", "S-003"]
    assert pick_next_stories(prd, 3)[0].id == pick_next_story(prd).id


def test_pick_next_stories_caps_and_edge_counts():
    prd = Prd(project="p", stories=[story(id="S-001"), story(id="S-002")])
    assert len(pick_next_stories(prd, 99)) == 2  # never more than available
    assert pick_next_stories(prd, 0) == []
    assert pick_next_stories(prd, -1) == []
    assert pick_next_stories(Prd(project="p"), 3) == []  # empty backlog


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


def test_pick_next_story_filters_by_type():
    prd = Prd(
        project="p",
        stories=[
            story(id="S-001", type="feat", priority=1),
            story(id="S-002", type="bug", priority=2),
            story(id="S-003", type="chore", priority=3),
        ],
    )
    assert pick_next_story(prd, types=("bug",)).id == "S-002"
    assert pick_next_story(prd, types=("chore",)).id == "S-003"
    assert pick_next_story(prd, types=("feat", "system-repair")).id == "S-001"
    assert pick_next_story(prd, types=("system-repair",)) is None  # no match
    assert pick_next_story(prd).id == "S-001"  # default: any type, by priority


# --- reclaim_stale_in_progress (GH-47) --------------------------------------


def test_reclaim_stale_in_progress_reclaims_stale_same_ticket():
    prd = Prd(project="p", stories=[story(id="S-001", status="in_progress")])
    reclaimed = reclaim_stale_in_progress(
        prd, stale_seconds=60, live_ticket_id="S-001", state_age_seconds=120,
    )
    assert reclaimed == ["S-001"]
    assert prd.stories[0].status == "open"


def test_reclaim_stale_in_progress_leaves_fresh_same_ticket():
    prd = Prd(project="p", stories=[story(id="S-001", status="in_progress")])
    reclaimed = reclaim_stale_in_progress(
        prd, stale_seconds=60, live_ticket_id="S-001", state_age_seconds=10,
    )
    assert reclaimed == []
    assert prd.stories[0].status == "in_progress"


def test_reclaim_stale_in_progress_reclaims_foreign_ticket_even_if_fresh():
    # A fresh state.json belonging to a DIFFERENT ticket never protects this one.
    prd = Prd(project="p", stories=[story(id="S-001", status="in_progress")])
    reclaimed = reclaim_stale_in_progress(
        prd, stale_seconds=60, live_ticket_id="S-002", state_age_seconds=5,
    )
    assert reclaimed == ["S-001"]
    assert prd.stories[0].status == "open"


def test_reclaim_stale_in_progress_reclaims_when_heartbeat_missing():
    prd = Prd(project="p", stories=[story(id="S-001", status="in_progress")])
    reclaimed = reclaim_stale_in_progress(
        prd, stale_seconds=60, live_ticket_id=None, state_age_seconds=None,
    )
    assert reclaimed == ["S-001"]
    assert prd.stories[0].status == "open"


def test_reclaim_stale_in_progress_leaves_other_statuses_untouched():
    prd = Prd(
        project="p",
        stories=[
            story(id="S-001", status="open"),
            story(id="S-002", status="blocked"),
            story(id="S-003", status="quotad"),
            story(id="S-004", status="done", passes=True),
        ],
    )
    reclaimed = reclaim_stale_in_progress(
        prd, stale_seconds=60, live_ticket_id=None, state_age_seconds=None,
    )
    assert reclaimed == []
    assert [s.status for s in prd.stories] == ["open", "blocked", "quotad", "done"]


def test_reclaim_stale_in_progress_system_repair_returns_to_blocked():
    # GH-78: a stale system-repair ticket is human-gated, so reclaiming it must
    # restore `blocked` (not `open`), or it silently re-arms for auto-pick.
    prd = Prd(
        project="p",
        stories=[
            story(id="S-001", type="feat", status="in_progress"),
            story(id="S-002", type="system-repair", status="in_progress"),
        ],
    )
    reclaimed = reclaim_stale_in_progress(
        prd, stale_seconds=60, live_ticket_id=None, state_age_seconds=None,
    )
    assert reclaimed == ["S-001", "S-002"]
    assert prd.stories[0].status == "open"        # feat -> open
    assert prd.stories[1].status == "blocked"     # system-repair -> blocked (gated)


# --- reconcile_completed (GH-78 terminal-guard) -----------------------------


def test_reconcile_completed_marks_merged_ticket_terminal():
    # A ticket whose work is already merged (id in completed_ids) is forced
    # terminal, even if the local ledger drifted back to a pickable state.
    prd = Prd(
        project="p",
        stories=[story(id="GH-61", type="system-repair", status="open", passes=False)],
    )
    changed = reconcile_completed(prd, {"GH-61"})
    assert changed == ["GH-61"]
    assert prd.stories[0].passes is True
    assert prd.stories[0].status == "done"


def test_reconcile_completed_is_idempotent_and_ignores_unknown_ids():
    prd = Prd(
        project="p",
        stories=[
            story(id="GH-61", status="done", passes=True),   # already terminal
            story(id="GH-99", status="open", passes=False),  # not merged
        ],
    )
    # GH-61 already terminal -> no change; GH-2 not present -> ignored.
    assert reconcile_completed(prd, {"GH-61", "GH-2"}) == []
    assert prd.stories[1].status == "open"  # untouched


def test_reconcile_completed_only_touches_matching_stories():
    prd = Prd(
        project="p",
        stories=[
            story(id="GH-56", type="feat", status="open", passes=False),
            story(id="GH-57", type="feat", status="open", passes=False),
        ],
    )
    changed = reconcile_completed(prd, {"GH-56"})
    assert changed == ["GH-56"]
    assert (prd.stories[0].passes, prd.stories[0].status) == (True, "done")
    assert (prd.stories[1].passes, prd.stories[1].status) == (False, "open")
