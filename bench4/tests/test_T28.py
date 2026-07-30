"""Locked tests for T28 - deterministic invoice text files."""

import pathlib
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


def run_cli(data_dir, *args):
    return subprocess.run(
        [sys.executable, "-m", "stockroom.cli", "--data", str(data_dir), *args],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )


def _seed(tmp):
    r = run_cli(tmp, "add-item", "GAD-1", "Gadget", "--qty", "10",
                "--price", "8.00", "--category", "gadgets")
    assert r.returncode == 0, r.stderr
    r = run_cli(tmp, "place-order", "GAD-1", "5", "--date", "2026-07-02")
    assert r.returncode == 0, r.stderr
    r = run_cli(tmp, "set-discount", "gadgets", "10")
    assert r.returncode == 0, r.stderr
    r = run_cli(tmp, "set-tax-rate", "5")
    assert r.returncode == 0, r.stderr


def test_invoice_file_written(tmp_path):
    _seed(tmp_path)
    out_file = tmp_path / "inv.txt"
    r = run_cli(tmp_path, "invoice", "1", "--output", str(out_file))
    assert r.returncode == 0, r.stderr
    assert out_file.exists()
    text = out_file.read_text(encoding="utf-8")
    assert "GAD-1" in text
    assert "2026-07-02" in text
    assert "$37.80" in text


def test_invoice_file_contains_breakdown(tmp_path):
    _seed(tmp_path)
    out_file = tmp_path / "inv.txt"
    r = run_cli(tmp_path, "invoice", "1", "--output", str(out_file))
    assert r.returncode == 0, r.stderr
    text = out_file.read_text(encoding="utf-8")
    for amount in ("$40.00", "$4.00", "$1.80", "$37.80"):
        assert amount in text, text
    lower = text.lower()
    for word in ("subtotal", "discount", "tax", "total"):
        assert word in lower, text


def test_invoice_file_deterministic(tmp_path):
    _seed(tmp_path)
    first = tmp_path / "inv1.txt"
    second = tmp_path / "inv2.txt"
    r = run_cli(tmp_path, "invoice", "1", "--output", str(first))
    assert r.returncode == 0, r.stderr
    r = run_cli(tmp_path, "invoice", "1", "--output", str(second))
    assert r.returncode == 0, r.stderr
    assert first.read_bytes() == second.read_bytes()


def test_unknown_order_writes_nothing(tmp_path):
    _seed(tmp_path)
    out_file = tmp_path / "nope.txt"
    r = run_cli(tmp_path, "invoice", "99", "--output", str(out_file))
    assert r.returncode == 1
    assert not out_file.exists()
