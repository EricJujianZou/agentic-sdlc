"""Locked tests for T42 - all-or-nothing batch apply from CSV."""
import csv
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


def seed(data_dir):
    for args in [
        ("add-supplier", "ACME", "Acme Supply", "orders@acme.example"),
        ("add-item", "WID-1", "Widget", "--qty", "10", "--price", "2.00",
         "--supplier", "ACME"),
        ("add-item", "GAD-1", "Gadget", "--qty", "0", "--price", "1.00",
         "--supplier", "ACME"),
    ]:
        r = run_cli(data_dir, *args)
        assert r.returncode == 0, r.stderr


def write_batch(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["op", "sku", "qty", "warehouse", "to_warehouse"])
        for row in rows:
            writer.writerow(row)


def qty(data_dir, sku):
    store = Store(str(pathlib.Path(data_dir) / "state.json"))
    store.load()
    return store.items[sku].qty


def test_batch_applies_all_rows(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    seed(data)
    batch = tmp_path / "batch.csv"
    write_batch(batch, [
        ("receive", "GAD-1", "5", "", ""),
        ("ship", "WID-1", "3", "", ""),
        ("transfer", "WID-1", "2", "main", "east"),
    ])
    r = run_cli(data, "batch", str(batch))
    assert r.returncode == 0, (r.stdout, r.stderr)
    assert "applied 3" in r.stdout
    assert qty(data, "GAD-1") == 5
    # ship removed 3; transfer moves stock between warehouses, total unchanged
    assert qty(data, "WID-1") == 7


def test_batch_failure_rolls_back_everything(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    seed(data)
    batch = tmp_path / "batch.csv"
    write_batch(batch, [
        ("receive", "GAD-1", "7", "", ""),
        ("ship", "WID-1", "999", "", ""),
    ])
    r = run_cli(data, "batch", str(batch))
    assert r.returncode == 1, (r.stdout, r.stderr)
    assert "row 2" in (r.stdout + r.stderr)
    # Row 1 must have been rolled back too.
    assert qty(data, "GAD-1") == 0
    assert qty(data, "WID-1") == 10


def test_batch_unknown_op_rolls_back(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    seed(data)
    batch = tmp_path / "batch.csv"
    write_batch(batch, [
        ("receive", "GAD-1", "5", "", ""),
        ("frobnicate", "WID-1", "1", "", ""),
    ])
    r = run_cli(data, "batch", str(batch))
    assert r.returncode == 1, (r.stdout, r.stderr)
    assert "row 2" in (r.stdout + r.stderr)
    assert qty(data, "GAD-1") == 0


def test_batch_unknown_sku_fails_cleanly(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    seed(data)
    batch = tmp_path / "batch.csv"
    write_batch(batch, [
        ("receive", "NOPE-1", "5", "", ""),
    ])
    r = run_cli(data, "batch", str(batch))
    assert r.returncode == 1, (r.stdout, r.stderr)
    assert "row 1" in (r.stdout + r.stderr)
    store = Store(str(data / "state.json"))
    store.load()
    assert "NOPE-1" not in store.items
