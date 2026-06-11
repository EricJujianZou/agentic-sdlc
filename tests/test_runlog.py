import json

from adw.runlog import append_history_line, cleanup_run, run_dir, write_stage_log


def test_write_and_cleanup(tmp_path):
    root = tmp_path / "runs"
    path = write_stage_log(
        "S-001", stage="plan", iteration=1, payload={"outcome": "success"}, runs_root=root
    )
    assert path.exists()
    assert json.loads(path.read_text(encoding="utf-8")) == {"outcome": "success"}
    assert run_dir("S-001", root).exists()
    cleanup_run("S-001", root)
    assert not (root / "S-001").exists()
    cleanup_run("S-001", root)  # idempotent


def test_append_history_line(tmp_path):
    history = tmp_path / "history.md"
    history.write_text("# Merge history\n", encoding="utf-8")
    append_history_line("S-001", "added CSV export", history)
    content = history.read_text(encoding="utf-8")
    assert "S-001: added CSV export" in content
