"""Tests for T08: CSV import treats SKUs case-insensitively."""

import subprocess
import sys
from pathlib import Path

from stockroom import csv_io, reports
from stockroom.store import Store

REPO_ROOT = Path(__file__).resolve().parents[2]


def make_store(tmp_path):
    return Store(str(tmp_path / "state.json"))


def run_cli(data_dir, *args):
    return subprocess.run(
        [sys.executable, "-m", "stockroom.cli", "--data", str(data_dir)]
        + list(args),
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )


def write_csv(path, rows):
    lines = ["sku,name,qty,unit_price,supplier_id"]
    lines.extend(rows)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_lowercase_row_updates_existing_uppercase_item(tmp_path):
    store = make_store(tmp_path)
    store.add_item("WID-1", "Widget", qty=3, unit_price=2.0)

    csv_path = tmp_path / "supplier.csv"
    write_csv(csv_path, ["wid-1,Widget,4,2.0,"])
    csv_io.import_items(store, str(csv_path))

    assert len(store.list_items()) == 1
    assert store.get_item("WID-1").qty == 4


def test_stock_totals_not_doubled_after_import(tmp_path):
    store = make_store(tmp_path)
    store.add_item("WID-1", "Widget", qty=3, unit_price=2.0)

    csv_path = tmp_path / "supplier.csv"
    write_csv(csv_path, ["wid-1,Widget,3,2.0,"])
    csv_io.import_items(store, str(csv_path))

    report = reports.stock_report(store)
    assert len(report["rows"]) == 1
    assert round(report["total_value"], 2) == 6.0


def test_new_skus_are_stored_uppercase(tmp_path):
    store = make_store(tmp_path)
    csv_path = tmp_path / "supplier.csv"
    write_csv(csv_path, ["gad-9,Gadget,5,1.5,"])
    csv_io.import_items(store, str(csv_path))

    assert [item.sku for item in store.list_items()] == ["GAD-9"]


def test_case_duplicates_within_one_file_yield_one_item(tmp_path):
    store = make_store(tmp_path)
    csv_path = tmp_path / "supplier.csv"
    write_csv(csv_path, [
        "ab1,Assorted bolts,3,0.5,",
        "AB1,Assorted bolts,4,0.5,",
    ])
    csv_io.import_items(store, str(csv_path))

    items = store.list_items()
    assert len(items) == 1
    assert items[0].sku == "AB1"


def test_cli_import_then_stock_report_shows_single_row(tmp_path):
    assert run_cli(tmp_path, "add-item", "WID-1", "Widget",
                   "--qty", "3", "--price", "2.00").returncode == 0

    csv_path = tmp_path / "supplier.csv"
    write_csv(csv_path, ["wid-1,Widget,5,2.0,"])
    result = run_cli(tmp_path, "import-csv", str(csv_path))
    assert result.returncode == 0, result.stderr

    result = run_cli(tmp_path, "report", "stock")
    assert result.returncode == 0, result.stderr
    # Exactly one row for the SKU regardless of how the file spelled it.
    assert result.stdout.upper().count("WID-1") == 1
