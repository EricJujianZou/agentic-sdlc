"""Locked tests for T41 - read-only mode."""
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


def snapshot(data_dir):
    data_dir = pathlib.Path(data_dir)
    return {
        str(p.relative_to(data_dir)): p.read_bytes()
        for p in sorted(data_dir.rglob("*"))
        if p.is_file()
    }


def seed(data_dir):
    for args in [
        ("add-supplier", "ACME", "Acme Supply", "orders@acme.example"),
        ("add-item", "WID-1", "Widget", "--qty", "5", "--price", "2.00",
         "--supplier", "ACME"),
        ("place-order", "WID-1", "3", "--date", "2026-01-05"),
    ]:
        r = run_cli(data_dir, *args)
        assert r.returncode == 0, r.stderr


def make_import_csv(path):
    path.write_text(
        "sku,name,qty,unit_price,supplier_id\nZZZ-9,Import thing,4,1.50,\n",
        encoding="utf-8",
    )


MUTATING = [
    ("add-item", "GAD-9", "Gadget"),
    ("add-supplier", "GLOB", "Globex", "purchasing@globex.example"),
    ("receive", "WID-1", "2"),
    ("ship", "WID-1", "1"),
    ("place-order", "WID-1", "1", "--date", "2026-01-06"),
    ("receive-order", "1"),
    ("cancel-order", "1"),
    ("undo",),
]


def test_read_only_flag_refuses_every_mutation(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    seed(data)
    csv_path = tmp_path / "in.csv"
    make_import_csv(csv_path)
    before = snapshot(data)
    for cmd in MUTATING + [("import-csv", str(csv_path))]:
        r = run_cli(data, "--read-only", *cmd)
        assert r.returncode == 1, (cmd, r.returncode, r.stdout, r.stderr)
        combined = (r.stdout + r.stderr).lower()
        assert "read-only" in combined, (cmd, r.stdout, r.stderr)
        assert snapshot(data) == before, f"{cmd} touched files in read-only mode"


def test_read_only_flag_allows_reads(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    seed(data)
    before = snapshot(data)
    for cmd in [
        ("report", "stock"),
        ("report", "low"),
        ("report", "monthly", "2026-01"),
        ("report", "history", "WID-1"),
        ("search", "wid"),
        ("export-csv", str(tmp_path / "out.csv")),
    ]:
        r = run_cli(data, "--read-only", *cmd)
        assert r.returncode == 0, (cmd, r.stdout, r.stderr)
        assert snapshot(data) == before, f"{cmd} modified the data directory"


def test_lock_is_persistent(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    seed(data)
    r = run_cli(data, "lock")
    assert r.returncode == 0, r.stderr
    before = snapshot(data)
    # A separate invocation, no --read-only flag: still refused.
    r = run_cli(data, "receive", "WID-1", "2")
    assert r.returncode == 1, (r.stdout, r.stderr)
    assert "read-only" in (r.stdout + r.stderr).lower()
    assert snapshot(data) == before
    # Reads still fine while locked.
    r = run_cli(data, "report", "stock")
    assert r.returncode == 0, r.stderr


def test_unlock_restores_mutability(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    seed(data)
    assert run_cli(data, "lock").returncode == 0
    r = run_cli(data, "unlock")
    assert r.returncode == 0, r.stderr
    r = run_cli(data, "receive", "WID-1", "2")
    assert r.returncode == 0, (r.stdout, r.stderr)
    store = Store(str(data / "state.json"))
    store.load()
    assert store.items["WID-1"].qty == 7
