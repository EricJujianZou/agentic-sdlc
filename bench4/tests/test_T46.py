"""Locked tests for T46 - batch --dry-run with zero file mutation."""
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


def snapshot(data_dir):
    """Content AND mtime of every file under the data directory."""
    data_dir = pathlib.Path(data_dir)
    return {
        str(p.relative_to(data_dir)): (p.read_bytes(), p.stat().st_mtime_ns)
        for p in sorted(data_dir.rglob("*"))
        if p.is_file()
    }


def qty(data_dir, sku):
    store = Store(str(pathlib.Path(data_dir) / "state.json"))
    store.load()
    return store.items[sku].qty


def test_dry_run_prints_plan_and_touches_nothing(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    seed(data)
    batch = tmp_path / "batch.csv"
    write_batch(batch, [
        ("receive", "GAD-1", "5", "", ""),
        ("ship", "WID-1", "3", "", ""),
    ])
    before = snapshot(data)
    r = run_cli(data, "batch", str(batch), "--dry-run")
    assert r.returncode == 0, (r.stdout, r.stderr)
    assert "dry-run" in r.stdout.lower()
    assert "GAD-1" in r.stdout
    assert "WID-1" in r.stdout
    assert snapshot(data) == before, "dry run changed file content or mtimes"
    assert qty(data, "GAD-1") == 0
    assert qty(data, "WID-1") == 10


def test_dry_run_reports_failing_row_without_touching(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    seed(data)
    batch = tmp_path / "batch.csv"
    write_batch(batch, [
        ("receive", "GAD-1", "5", "", ""),
        ("ship", "WID-1", "999", "", ""),
    ])
    before = snapshot(data)
    r = run_cli(data, "batch", str(batch), "--dry-run")
    assert r.returncode == 1, (r.stdout, r.stderr)
    assert "row 2" in (r.stdout + r.stderr)
    assert snapshot(data) == before, "failing dry run changed the data dir"


def test_real_run_after_dry_run_is_unaffected(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    seed(data)
    batch = tmp_path / "batch.csv"
    write_batch(batch, [
        ("receive", "GAD-1", "5", "", ""),
        ("ship", "WID-1", "3", "", ""),
    ])
    r = run_cli(data, "batch", str(batch), "--dry-run")
    assert r.returncode == 0, (r.stdout, r.stderr)
    r = run_cli(data, "batch", str(batch))
    assert r.returncode == 0, (r.stdout, r.stderr)
    assert "applied 2" in r.stdout
    assert qty(data, "GAD-1") == 5
    assert qty(data, "WID-1") == 7
