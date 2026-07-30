"""Locked tests for T26 - order totals with discount and tax, invoice command."""

import pathlib
import subprocess
import sys
from decimal import Decimal

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


def _load(tmp):
    from stockroom.store import Store
    store = Store(str(tmp / "state.json"))
    store.load()
    return store


def _assert_breakdown(breakdown, subtotal, discount, tax, total):
    for key, want in (("subtotal", subtotal), ("discount", discount),
                      ("tax", tax), ("total", total)):
        assert Decimal(str(breakdown[key])) == Decimal(want), (key, breakdown)


def test_order_total_no_discount_no_tax(tmp_path):
    _seed(tmp_path)
    from stockroom import reports
    breakdown = reports.order_total(_load(tmp_path), 1)
    _assert_breakdown(breakdown, "40.00", "0.00", "0.00", "40.00")


def test_order_total_with_discount_and_tax(tmp_path):
    _seed(tmp_path)
    r = run_cli(tmp_path, "set-discount", "gadgets", "10")
    assert r.returncode == 0, r.stderr
    r = run_cli(tmp_path, "set-tax-rate", "5")
    assert r.returncode == 0, r.stderr
    from stockroom import reports
    breakdown = reports.order_total(_load(tmp_path), 1)
    _assert_breakdown(breakdown, "40.00", "4.00", "1.80", "37.80")


def test_discount_without_tax(tmp_path):
    _seed(tmp_path)
    r = run_cli(tmp_path, "set-discount", "gadgets", "10")
    assert r.returncode == 0, r.stderr
    from stockroom import reports
    breakdown = reports.order_total(_load(tmp_path), 1)
    _assert_breakdown(breakdown, "40.00", "4.00", "0.00", "36.00")


def test_invoice_cli_breakdown(tmp_path):
    _seed(tmp_path)
    r = run_cli(tmp_path, "set-discount", "gadgets", "10")
    assert r.returncode == 0, r.stderr
    r = run_cli(tmp_path, "set-tax-rate", "5")
    assert r.returncode == 0, r.stderr
    r = run_cli(tmp_path, "invoice", "1")
    assert r.returncode == 0, r.stderr
    out = r.stdout
    for amount in ("$40.00", "$4.00", "$1.80", "$37.80"):
        assert amount in out, out
    lower = out.lower()
    for word in ("subtotal", "discount", "tax", "total"):
        assert word in lower, out


def test_invoice_unknown_order_is_user_error(tmp_path):
    _seed(tmp_path)
    r = run_cli(tmp_path, "invoice", "99")
    assert r.returncode == 1
