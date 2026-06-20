"""Parallel backlog coordinator tests (#4, PR C).

The coordinator (`run_backlog_parallel`) is driven with stub leaf operations —
no real git, agents, or GitHub — so these assert the orchestration contract:
the batch is the top N by priority, every picked story is marked in_progress
(prepared) before ANY work starts, outcomes are reconciled serially, the
worktree lifecycle brackets each survivor, one crashing worker never aborts the
batch, and the cooldown is checked once per batch (never overridden).
"""
import json
import threading

from adw.tickets import load_prd, mark_story, save_prd
from adw.orchestrator import TicketOutcome
from adw.workflow_runner import run_backlog_parallel


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


def _set_status(prd_path, story_id, *, status, passes=False):
    prd = load_prd(prd_path)
    mark_story(prd, story_id, status=status, passes=passes)
    save_prd(prd, prd_path)


def _no_cooldown(_state_path):
    return None


class _Harness:
    """Records the coordinator's calls and mutates the prd so the loop advances
    (prepare -> in_progress, finalize/block -> terminal), like the real wiring."""

    def __init__(self, prd_path, *, block_ids=(), raise_ids=()):
        self.prd_path = prd_path
        self.block_ids = set(block_ids)      # decompose-blocked at prepare
        self.raise_ids = set(raise_ids)      # worker raises
        self.timeline = []                   # ("prepare"|"work"|"finalize"|"block", id)
        self.added, self.removed = [], []
        self.finalized, self.blocked = [], []
        self._lock = threading.Lock()

    def prepare(self, story):
        self.timeline.append(("prepare", story.id))
        if story.id in self.block_ids:
            return "too vague to expand"
        _set_status(self.prd_path, story.id, status="in_progress")
        return None

    def work(self, story, worktree_dir):
        with self._lock:
            self.timeline.append(("work", story.id))
        if story.id in self.raise_ids:
            raise RuntimeError("worker exploded")
        return TicketOutcome(story.id, "done")

    def finalize(self, story, outcome, worktree_dir):
        self.timeline.append(("finalize", story.id))
        self.finalized.append((story.id, outcome.outcome))
        status = "done" if outcome.outcome == "done" else "blocked"
        _set_status(self.prd_path, story.id, status=status, passes=(status == "done"))

    def block(self, story, problem):
        self.timeline.append(("block", story.id))
        self.blocked.append((story.id, problem))
        _set_status(self.prd_path, story.id, status="blocked")
        return TicketOutcome(story.id, "blocked", reason=problem)

    def add_worktree(self, story):
        self.added.append(story.id)
        return f"/wt/{story.id}"

    def remove_worktree(self, story):
        self.removed.append(story.id)

    def run(self, **kw):
        defaults = dict(
            prepare_fn=self.prepare, work_fn=self.work, finalize_fn=self.finalize,
            block_fn=self.block, cooldown_fn=_no_cooldown,
            add_worktree_fn=self.add_worktree, remove_worktree_fn=self.remove_worktree,
            max_tickets=99, max_parallel=3,
            prd_path=self.prd_path, state_path=self.prd_path.parent / "state.json",
        )
        defaults.update(kw)
        return run_backlog_parallel(**defaults)


def test_runs_whole_backlog_in_priority_batches(tmp_path):
    prd_path = tmp_path / "prd.json"
    _write_prd(prd_path, 5)
    h = _Harness(prd_path)
    result = h.run(max_parallel=3)
    assert result.tickets_run == 5
    assert result.clean is True
    assert "no open stories" in result.stop_reason
    # First batch is the top 3 by priority; worktrees bracket every survivor.
    assert h.added[:3] == ["S-001", "S-002", "S-003"]
    assert sorted(h.added) == sorted(h.removed) == [f"S-{i:03d}" for i in range(1, 6)]
    assert all(o == "done" for _, o in h.finalized)


def test_all_prepared_before_any_work_in_a_batch(tmp_path):
    prd_path = tmp_path / "prd.json"
    _write_prd(prd_path, 3)
    h = _Harness(prd_path)
    h.run(max_tickets=3, max_parallel=3)
    # Every story in the batch is marked in_progress (prepared) before the first
    # worker runs — no worker starts against a half-prepared backlog.
    first_work = next(i for i, (kind, _) in enumerate(h.timeline) if kind == "work")
    prepared_before = {sid for kind, sid in h.timeline[:first_work] if kind == "prepare"}
    assert prepared_before == {"S-001", "S-002", "S-003"}


def test_reconciliation_is_serial_and_in_order(tmp_path):
    prd_path = tmp_path / "prd.json"
    _write_prd(prd_path, 3)
    h = _Harness(prd_path)
    h.run(max_tickets=3, max_parallel=3)
    finalize_order = [sid for kind, sid in h.timeline if kind == "finalize"]
    # One finalize per survivor, in deterministic survivor (priority) order, and
    # all finalizes happen after all work (serial reconciliation phase).
    assert finalize_order == ["S-001", "S-002", "S-003"]
    last_work = max(i for i, (k, _) in enumerate(h.timeline) if k == "work")
    first_finalize = min(i for i, (k, _) in enumerate(h.timeline) if k == "finalize")
    assert first_finalize > last_work


def test_one_failing_worker_does_not_abort_batch(tmp_path):
    prd_path = tmp_path / "prd.json"
    _write_prd(prd_path, 3)
    h = _Harness(prd_path, raise_ids={"S-002"})
    result = h.run(max_tickets=3, max_parallel=3)
    assert result.tickets_run == 3
    outcomes = dict(h.finalized)
    # The crashing worker becomes a blocked outcome; the rest still complete and
    # every survivor is reconciled and torn down.
    assert outcomes["S-002"] == "blocked"
    assert outcomes["S-001"] == "done" and outcomes["S-003"] == "done"
    assert sorted(h.removed) == ["S-001", "S-002", "S-003"]


def test_decompose_blocked_ticket_skips_worktree(tmp_path):
    prd_path = tmp_path / "prd.json"
    _write_prd(prd_path, 3)
    h = _Harness(prd_path, block_ids={"S-002"})
    h.run(max_tickets=3, max_parallel=3)
    # S-002 blocks at prepare: it is finalized via block_fn and never gets a
    # worktree or a worker.
    assert ("S-002", "too vague to expand") in h.blocked
    assert "S-002" not in h.added
    assert "S-002" not in [sid for kind, sid in h.timeline if kind == "work"]
    assert sorted(h.added) == ["S-001", "S-003"]


def test_whole_batch_blocked_at_prepare_continues(tmp_path):
    prd_path = tmp_path / "prd.json"
    _write_prd(prd_path, 2)
    h = _Harness(prd_path, block_ids={"S-001", "S-002"})
    result = h.run(max_tickets=99, max_parallel=3)
    # Both block at decompose; no worktrees, no workers, and the loop ends on an
    # empty backlog rather than spinning (blocked stories are no longer open).
    assert h.added == []
    assert result.clean is True
    assert len(h.blocked) == 2


def test_single_cooldown_check_per_batch(tmp_path):
    prd_path = tmp_path / "prd.json"
    _write_prd(prd_path, 3)
    h = _Harness(prd_path)
    calls = []

    def counting_cooldown(state_path):
        calls.append(state_path)
        return None

    h.run(max_tickets=3, max_parallel=3, cooldown_fn=counting_cooldown)
    assert len(calls) == 1  # one batch -> exactly one cooldown check


def test_active_cooldown_stops_without_running(tmp_path):
    prd_path = tmp_path / "prd.json"
    _write_prd(prd_path, 3)
    h = _Harness(prd_path)
    result = h.run(cooldown_fn=lambda _s: "cooldown active for ~10 more minute(s)")
    assert result.tickets_run == 0
    assert result.clean is False
    assert "cooldown" in result.stop_reason
    assert h.added == [] and h.timeline == []  # nothing was prepared or run


def test_worktrees_removed_even_if_finalize_raises(tmp_path):
    prd_path = tmp_path / "prd.json"
    _write_prd(prd_path, 2)
    h = _Harness(prd_path)

    def boom_finalize(story, outcome, worktree_dir):
        raise RuntimeError("reconcile failed")

    try:
        h.run(max_tickets=2, max_parallel=3, finalize_fn=boom_finalize)
    except RuntimeError:
        pass
    # The finally tears down every worktree it created even when reconciliation
    # blows up — no orphan worktrees leak.
    assert sorted(h.removed) == ["S-001", "S-002"]


def test_max_tickets_bounds_the_batch(tmp_path):
    prd_path = tmp_path / "prd.json"
    _write_prd(prd_path, 5)
    h = _Harness(prd_path)
    result = h.run(max_tickets=2, max_parallel=3)
    # The batch is capped to the remaining budget, not max_parallel.
    assert result.tickets_run == 2
    assert sorted(h.added) == ["S-001", "S-002"]
    assert result.clean is True
    assert "max-tickets" in result.stop_reason
