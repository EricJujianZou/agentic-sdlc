"""Locked tests for T47 - the summary dashboard report."""
import pathlib
import re
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

SEED = [
    ("add-supplier", "ACME", "Acme Supply", "orders@acme.example"),
    ("add-item", "T-1", "Torque wrench", "--qty", "4", "--price", "2.50",
     "--category", "tools", "--supplier", "ACME"),
    ("add-item", "P-1", "Pin small", "--qty", "10", "--price", "0.10",
     "--category", "parts"),
    ("add-item", "P-2", "Pin large", "--qty", "10", "--price", "0.20",
     "--category", "parts"),
    ("add-item", "D-1", "Dowel", "--qty", "1", "--price", "1.00",
     "--category", "parts"),
    ("ship", "T-1", "2"),
    ("place-order", "T-1", "5", "--date", "2026-01-05"),
    ("place-order", "T-1", "3", "--date", "2026-02-01"),
]
N_MUTATIONS = len(SEED)


def run_cli(data_dir, *args):
    return subprocess.run(
        [sys.executable, "-m", "stockroom.cli", "--data", str(data_dir), *args],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )


def seeded(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    for args in SEED:
        r = run_cli(data, *args)
        assert r.returncode == 0, (args, r.stderr)
    return data


def summary(data):
    r = run_cli(data, "report", "summary")
    assert r.returncode == 0, (r.stdout, r.stderr)
    return r.stdout


def test_summary_valuation_is_cent_exact(tmp_path):
    out = summary(seeded(tmp_path))
    # T-1: 2 left x 2.50, P-1: 10 x 0.10, P-2: 10 x 0.20, D-1: 1 x 1.00
    assert "valuation: $9.00" in out


def test_summary_low_stock_and_pending_orders(tmp_path):
    out = summary(seeded(tmp_path))
    # At the default threshold of 5, T-1 (qty 2) and D-1 (qty 1) are low.
    assert "D-1" in out
    assert "T-1" in out
    assert "pending orders: 2" in out


def test_summary_top_category(tmp_path):
    out = summary(seeded(tmp_path))
    # Only "tools" items were ever shipped.
    assert "top category: tools" in out


def test_summary_event_count_and_no_writes(tmp_path):
    data = seeded(tmp_path)
    files = {
        str(p.relative_to(data)): p.read_bytes()
        for p in sorted(data.rglob("*")) if p.is_file()
    }
    out = summary(data)
    match = re.search(r"events:\s*(\d+)", out)
    assert match, out
    assert int(match.group(1)) >= N_MUTATIONS
    after = {
        str(p.relative_to(data)): p.read_bytes()
        for p in sorted(data.rglob("*")) if p.is_file()
    }
    assert after == files, "report summary modified the data directory"
