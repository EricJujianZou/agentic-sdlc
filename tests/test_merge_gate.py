"""finalize() is the testable core of the human-run merge gate; the git
merged-into-main check lives in main() and is exercised by humans, not here."""
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "workflows"))

from merge_gate import MergeGateError, finalize  # noqa: E402


def _write_prd(path: Path, *, status: str = "done", passes: bool = True) -> None:
    path.write_text(json.dumps({
        "project": "demo",
        "stories": [{
            "id": "S-001",
            "type": "feat",
            "priority": 1,
            "title": "t",
            "description": "d",
            "acceptance_criteria": ["c"],
            "passes": passes,
            "status": status,
        }],
    }), encoding="utf-8")


def test_finalize_appends_history_and_deletes_run_logs(tmp_path):
    prd = tmp_path / "prd.json"
    _write_prd(prd)
    history = tmp_path / "history.md"
    history.write_text("# Merge history\n", encoding="utf-8")
    runs = tmp_path / "runs"
    (runs / "S-001").mkdir(parents=True)
    (runs / "S-001" / "iter01_plan.json").write_text("{}", encoding="utf-8")

    actions = finalize("S-001", "dashboard shipped", prd_path=prd,
                       history_path=history, runs_root=runs)

    assert "S-001: dashboard shipped" in history.read_text(encoding="utf-8")
    assert not (runs / "S-001").exists()
    assert any("appended" in a for a in actions)
    assert any("deleted run logs" in a for a in actions)


def test_finalize_is_idempotent(tmp_path):
    prd = tmp_path / "prd.json"
    _write_prd(prd)
    history = tmp_path / "history.md"
    history.write_text("# Merge history\n", encoding="utf-8")
    runs = tmp_path / "runs"

    finalize("S-001", "first", prd_path=prd, history_path=history, runs_root=runs)
    actions = finalize("S-001", "second", prd_path=prd, history_path=history, runs_root=runs)

    content = history.read_text(encoding="utf-8")
    assert content.count("S-001:") == 1
    assert "second" not in content
    assert any("already present" in a for a in actions)
    assert any("no run logs" in a for a in actions)


def test_finalize_refuses_undone_ticket(tmp_path):
    prd = tmp_path / "prd.json"
    _write_prd(prd, status="in_progress", passes=False)
    history = tmp_path / "history.md"

    with pytest.raises(MergeGateError, match="done\\+passing"):
        finalize("S-001", "nope", prd_path=prd, history_path=history,
                 runs_root=tmp_path / "runs")
    assert not history.exists()


def test_finalize_force_overrides_status_gate(tmp_path):
    prd = tmp_path / "prd.json"
    _write_prd(prd, status="blocked", passes=False)
    history = tmp_path / "history.md"
    history.write_text("# Merge history\n", encoding="utf-8")

    finalize("S-001", "forced through", prd_path=prd, history_path=history,
             runs_root=tmp_path / "runs", force=True)
    assert "S-001: forced through" in history.read_text(encoding="utf-8")


def test_finalize_unknown_ticket(tmp_path):
    prd = tmp_path / "prd.json"
    _write_prd(prd)
    with pytest.raises(MergeGateError, match="S-999"):
        finalize("S-999", "x", prd_path=prd, history_path=tmp_path / "history.md",
                 runs_root=tmp_path / "runs")
