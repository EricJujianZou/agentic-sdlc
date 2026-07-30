"""Locked tests for T22 - exact inventory valuation."""

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


def _store_with(tmp_path, rows):
    from stockroom.store import Store
    store = Store(str(tmp_path / "state.json"))
    for sku, name, qty, price in rows:
        store.add_item(sku, name, qty=qty, unit_price=price)
    return store


def test_total_value_exact_two_items(tmp_path):
    from stockroom import reports
    store = _store_with(tmp_path, [
        ("AAA-1", "Alpha", 1, 0.10),
        ("BBB-1", "Beta", 1, 0.20),
    ])
    total = reports.stock_report(store)["total_value"]
    assert Decimal(str(total)) == Decimal("0.30")


def test_line_value_exact(tmp_path):
    from stockroom import reports
    store = _store_with(tmp_path, [("GAD-2", "Gadget, large", 7, 1.15)])
    rows = reports.stock_report(store)["rows"]
    assert len(rows) == 1
    assert Decimal(str(rows[0]["value"])) == Decimal("8.05")


def test_total_value_exact_mixed_catalogue(tmp_path):
    from stockroom import reports
    store = _store_with(tmp_path, [
        ("AAA-1", "Alpha", 1, 0.10),
        ("BBB-1", "Beta", 1, 0.20),
        ("CCC-1", "Gamma", 3, 19.99),
    ])
    total = reports.stock_report(store)["total_value"]
    assert Decimal(str(total)) == Decimal("60.27")


def test_total_value_exact_small_prices(tmp_path):
    from stockroom import reports
    store = _store_with(tmp_path, [
        ("GAD-2", "Gadget, large", 7, 1.15),
        ("WID-2", "Widget, deluxe", 10, 0.10),
        ("WID-3", "Widget, economy", 10, 0.20),
    ])
    total = reports.stock_report(store)["total_value"]
    assert Decimal(str(total)) == Decimal("11.05")


def test_cli_stock_report_total_display(tmp_path):
    r = run_cli(tmp_path, "add-item", "AAA-1", "Alpha", "--qty", "1",
                "--price", "0.10")
    assert r.returncode == 0, r.stderr
    r = run_cli(tmp_path, "add-item", "BBB-1", "Beta", "--qty", "1",
                "--price", "0.20")
    assert r.returncode == 0, r.stderr
    r = run_cli(tmp_path, "report", "stock")
    assert r.returncode == 0, r.stderr
    assert "0.30" in r.stdout
