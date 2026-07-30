"""Locked tests for T24 - money formatting via stockroom.money.format_money."""

import pathlib
import re
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

# Money printed without a leading $ (e.g. "19.99" rather than "$19.99").
BARE_MONEY = re.compile(r"(?<!\$)\b\d+\.\d{2}\b")


def run_cli(data_dir, *args):
    return subprocess.run(
        [sys.executable, "-m", "stockroom.cli", "--data", str(data_dir), *args],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )


def test_format_money_int_means_cents():
    from stockroom.money import format_money
    assert format_money(1999) == "$19.99"
    assert format_money(250) == "$2.50"
    assert format_money(5) == "$0.05"
    assert format_money(0) == "$0.00"


def test_format_money_float_means_dollars():
    from stockroom.money import format_money
    assert format_money(19.99) == "$19.99"
    assert format_money(3.5) == "$3.50"
    assert format_money(0.1) == "$0.10"
    assert format_money(2.0) == "$2.00"


def test_format_money_negative():
    from stockroom.money import format_money
    assert format_money(-1250) == "-$12.50"
    assert format_money(-3.5) == "-$3.50"


def test_stock_report_money_formatted(tmp_path):
    r = run_cli(tmp_path, "add-item", "WID-1", "Widget", "--qty", "3",
                "--price", "19.99")
    assert r.returncode == 0, r.stderr
    r = run_cli(tmp_path, "add-item", "GAD-1", "Gadget", "--qty", "4",
                "--price", "2.50")
    assert r.returncode == 0, r.stderr
    r = run_cli(tmp_path, "report", "stock")
    assert r.returncode == 0, r.stderr
    out = r.stdout
    assert "$19.99" in out
    assert "$59.97" in out
    assert "$2.50" in out
    assert "$10.00" in out
    assert "$69.97" in out
    assert BARE_MONEY.search(out) is None, out


def test_price_changes_report_money_formatted(tmp_path):
    r = run_cli(tmp_path, "add-item", "WID-1", "Widget", "--qty", "3",
                "--price", "19.99")
    assert r.returncode == 0, r.stderr
    r = run_cli(tmp_path, "set-price", "WID-1", "24.50",
                "--date", "2026-07-05")
    assert r.returncode == 0, r.stderr
    r = run_cli(tmp_path, "report", "price-changes")
    assert r.returncode == 0, r.stderr
    out = r.stdout
    assert "$19.99" in out
    assert "$24.50" in out
    assert BARE_MONEY.search(out) is None, out
