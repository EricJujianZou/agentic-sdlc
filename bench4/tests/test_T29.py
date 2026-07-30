"""Locked tests for T29 - monthly revenue over received orders."""

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
    r = run_cli(tmp, "add-item", "WID-1", "Widget", "--qty", "50",
                "--price", "20.00", "--category", "widgets")
    assert r.returncode == 0, r.stderr
    r = run_cli(tmp, "add-item", "GAD-1", "Gadget", "--qty", "50",
                "--price", "2.50", "--category", "gadgets")
    assert r.returncode == 0, r.stderr
    # order 1: July, will be received (3 x 20.00 = 60.00)
    # order 2: July, will be received (2 x 2.50 = 5.00)
    # order 3: July, stays pending
    # order 4: June, will be received (1 x 20.00 = 20.00)
    for sku, qty, date in (("WID-1", "3", "2026-07-03"),
                           ("GAD-1", "2", "2026-07-10"),
                           ("GAD-1", "4", "2026-07-15"),
                           ("WID-1", "1", "2026-06-05")):
        r = run_cli(tmp, "place-order", sku, qty, "--date", date)
        assert r.returncode == 0, r.stderr
    for order_id in ("1", "2", "4"):
        r = run_cli(tmp, "receive-order", order_id)
        assert r.returncode == 0, r.stderr


def _load(tmp):
    from stockroom.store import Store
    store = Store(str(tmp / "state.json"))
    store.load()
    return store


def test_api_monthly_revenue(tmp_path):
    _seed(tmp_path)
    from stockroom import reports
    revenue = reports.monthly_revenue(_load(tmp_path), "2026-07")
    rows = revenue["rows"]
    assert len(rows) == 2
    by_id = {row["id"]: row for row in rows}
    assert set(by_id) == {1, 2}
    assert by_id[1]["sku"] == "WID-1"
    assert Decimal(str(by_id[1]["total"])) == Decimal("60.00")
    assert Decimal(str(by_id[2]["total"])) == Decimal("5.00")
    assert Decimal(str(revenue["total"])) == Decimal("65.00")


def test_pending_and_cancelled_excluded(tmp_path):
    _seed(tmp_path)
    r = run_cli(tmp_path, "cancel-order", "3")
    assert r.returncode == 0, r.stderr
    from stockroom import reports
    store = _load(tmp_path)
    revenue = reports.monthly_revenue(store, "2026-07")
    assert Decimal(str(revenue["total"])) == Decimal("65.00")
    june = reports.monthly_revenue(store, "2026-06")
    assert len(june["rows"]) == 1
    assert Decimal(str(june["total"])) == Decimal("20.00")


def test_cli_revenue_report(tmp_path):
    _seed(tmp_path)
    r = run_cli(tmp_path, "report", "revenue", "2026-07")
    assert r.returncode == 0, r.stderr
    assert "Total revenue" in r.stdout
    assert "$65.00" in r.stdout


def test_cli_empty_month(tmp_path):
    _seed(tmp_path)
    r = run_cli(tmp_path, "report", "revenue", "2026-01")
    assert r.returncode == 0, r.stderr
    assert "$0.00" in r.stdout


def test_discount_affects_revenue(tmp_path):
    _seed(tmp_path)
    r = run_cli(tmp_path, "set-discount", "widgets", "10")
    assert r.returncode == 0, r.stderr
    from stockroom import reports
    revenue = reports.monthly_revenue(_load(tmp_path), "2026-07")
    # order 1: 60.00 minus 10% = 54.00; order 2 unchanged at 5.00
    assert Decimal(str(revenue["total"])) == Decimal("59.00")
