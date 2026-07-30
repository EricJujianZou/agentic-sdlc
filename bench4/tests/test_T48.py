"""Locked tests for T48 - multi-step undo and redo."""
import pathlib
import subprocess
import sys

from stockroom.store import Store

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


def run_cli(data_dir, *args):
    return subprocess.run(
        [sys.executable, "-m", "stockroom.cli", "--data", str(data_dir), *args],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )


def seeded(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    for args in [
        ("add-item", "X-1", "Extra widget"),
        ("receive", "X-1", "5"),
        ("receive", "X-1", "7"),
    ]:
        r = run_cli(data, *args)
        assert r.returncode == 0, (args, r.stderr)
    return data


def qty(data_dir):
    store = Store(str(pathlib.Path(data_dir) / "state.json"))
    store.load()
    return store.items["X-1"].qty


def test_undo_steps_undoes_newest_first(tmp_path):
    data = seeded(tmp_path)
    assert qty(data) == 12
    r = run_cli(data, "undo", "--steps", "2")
    assert r.returncode == 0, (r.stdout, r.stderr)
    assert qty(data) == 0


def test_redo_walks_forward_in_original_order(tmp_path):
    data = seeded(tmp_path)
    assert run_cli(data, "undo", "--steps", "2").returncode == 0
    r = run_cli(data, "redo")
    assert r.returncode == 0, (r.stdout, r.stderr)
    assert qty(data) == 5  # the older receive came back first
    r = run_cli(data, "redo")
    assert r.returncode == 0, (r.stdout, r.stderr)
    assert qty(data) == 12
    r = run_cli(data, "redo")
    assert r.returncode == 1, (r.stdout, r.stderr)
    assert qty(data) == 12


def test_new_mutation_clears_redo(tmp_path):
    data = seeded(tmp_path)
    assert run_cli(data, "undo").returncode == 0
    assert qty(data) == 5
    assert run_cli(data, "receive", "X-1", "1").returncode == 0
    assert qty(data) == 6
    r = run_cli(data, "redo")
    assert r.returncode == 1, (r.stdout, r.stderr)
    assert qty(data) == 6


def test_undo_too_many_steps_changes_nothing(tmp_path):
    data = seeded(tmp_path)
    r = run_cli(data, "undo", "--steps", "99")
    assert r.returncode == 1, (r.stdout, r.stderr)
    assert qty(data) == 12
