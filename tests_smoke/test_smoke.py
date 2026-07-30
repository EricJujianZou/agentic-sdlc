"""Smoke tests for the stockroom base code.

Quick sanity checks that the package hangs together: the store round-trips
state, the basic operations move stock the right way, reports run, and the
CLI is invocable as ``python -m stockroom.cli``.  Run from the repo root:

    python -m pytest tests_smoke -q
"""

import csv
import subprocess
import sys
from pathlib import Path

from stockroom import csv_io, reports
from stockroom.store import Store

REPO_ROOT = Path(__file__).resolve().parents[1]


def make_store(tmp_path):
    return Store(str(tmp_path / "state.json"))


def run_cli(data_dir, *args):
    """Invoke the CLI the way a user would and capture the result."""
    return subprocess.run(
        [sys.executable, "-m", "stockroom.cli", "--data", str(data_dir)]
        + list(args),
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )


def test_add_item_and_reload(tmp_path):
    store = make_store(tmp_path)
    store.add_item("WID-1", "Widget", qty=10, unit_price=2.5)
    store.save()

    fresh = make_store(tmp_path)
    fresh.load()
    item = fresh.get_item("WID-1")
    assert item.name == "Widget"
    assert item.qty == 10
    assert item.unit_price == 2.5


def test_receive_adds_stock(tmp_path):
    store = make_store(tmp_path)
    store.add_item("WID-1", "Widget", qty=3)
    store.receive("WID-1", 7)
    assert store.get_item("WID-1").qty == 10


def test_ship_removes_stock(tmp_path):
    store = make_store(tmp_path)
    store.add_item("WID-1", "Widget", qty=10)
    store.ship("WID-1", 4)
    assert store.get_item("WID-1").qty == 6


def test_place_and_receive_order(tmp_path):
    store = make_store(tmp_path)
    store.add_item("WID-1", "Widget", qty=1)
    order = store.place_order("WID-1", 20, "2026-07-01")
    assert order.status == "pending"

    store.receive_order(order.id)
    assert store.get_order(order.id).status == "received"
    assert store.get_item("WID-1").qty == 21


def test_cancel_order(tmp_path):
    store = make_store(tmp_path)
    store.add_item("WID-1", "Widget", qty=1)
    order = store.place_order("WID-1", 20, "2026-07-01")
    store.cancel_order(order.id)
    assert store.get_order(order.id).status == "cancelled"
    assert store.get_item("WID-1").qty == 1  # stock untouched


def test_stock_report_total(tmp_path):
    store = make_store(tmp_path)
    store.add_item("WID-1", "Widget", qty=4, unit_price=2.5)
    store.add_item("GAD-1", "Gadget", qty=2, unit_price=3.0)
    report = reports.stock_report(store)
    assert len(report["rows"]) == 2
    assert round(report["total_value"], 2) == 16.0


def test_monthly_report_happy_path(tmp_path):
    store = make_store(tmp_path)
    store.add_item("WID-1", "Widget", qty=1)
    store.place_order("WID-1", 5, "2026-07-02")
    store.place_order("WID-1", 8, "2026-07-15")
    store.place_order("WID-1", 3, "2026-08-01")

    rows = reports.monthly_orders(store, "2026-07")
    assert [row["date"] for row in rows] == ["2026-07-02", "2026-07-15"]


def test_low_stock_and_suggestions(tmp_path):
    store = make_store(tmp_path)
    store.add_supplier("acme", "Acme Supply", "orders@acme.example")
    store.add_item("WID-1", "Widget", qty=2, supplier_id="acme")
    store.add_item("GAD-1", "Gadget", qty=50)

    low = reports.low_stock(store, threshold=5)
    assert [row["sku"] for row in low] == ["WID-1"]

    suggestions = reports.reorder_suggestions(store, threshold=5)
    assert suggestions == [{
        "sku": "WID-1",
        "supplier_id": "acme",
        "qty": 2,
        "suggested_qty": 3,
    }]


def test_csv_round_trip(tmp_path):
    store = make_store(tmp_path)
    store.add_supplier("acme", "Acme Supply", "orders@acme.example")
    store.add_item("WID-1", "Widget", qty=4, unit_price=2.5,
                   supplier_id="acme")
    store.add_item("GAD-1", "Gadget", qty=9, unit_price=1.25)

    out = tmp_path / "items.csv"
    assert csv_io.export_items(store, str(out)) == 2
    with open(out, newline="", encoding="utf-8") as f:
        header = next(csv.reader(f))
    assert header == ["sku", "name", "qty", "unit_price", "supplier_id"]

    other = Store(str(tmp_path / "other.json"))
    other.add_supplier("acme", "Acme Supply", "orders@acme.example")
    assert csv_io.import_items(other, str(out)) == 2
    item = other.get_item("WID-1")
    assert item.qty == 4
    assert item.unit_price == 2.5
    assert item.supplier_id == "acme"


def test_cli_add_and_report_stock(tmp_path):
    result = run_cli(tmp_path, "add-item", "WID-1", "Widget",
                     "--qty", "4", "--price", "2.50")
    assert result.returncode == 0, result.stderr

    result = run_cli(tmp_path, "report", "stock")
    assert result.returncode == 0, result.stderr
    assert "WID-1" in result.stdout
    assert "Total value: 10.00" in result.stdout


def test_cli_order_lifecycle(tmp_path):
    assert run_cli(tmp_path, "add-item", "WID-1", "Widget").returncode == 0
    result = run_cli(tmp_path, "place-order", "WID-1", "12",
                     "--date", "2026-07-01")
    assert result.returncode == 0, result.stderr
    assert "placed order 1" in result.stdout

    result = run_cli(tmp_path, "receive-order", "1")
    assert result.returncode == 0, result.stderr

    result = run_cli(tmp_path, "report", "history", "WID-1")
    assert result.returncode == 0, result.stderr
    assert "2026-07-01" in result.stdout


def test_cli_unknown_sku_is_user_error(tmp_path):
    result = run_cli(tmp_path, "ship", "NOPE-1", "2")
    assert result.returncode == 1
    assert "unknown item" in result.stderr


def test_cli_corrupt_state_file(tmp_path):
    (tmp_path / "state.json").write_text("{not json", encoding="utf-8")
    result = run_cli(tmp_path, "report", "stock")
    assert result.returncode == 2
    assert "corrupt" in result.stderr
