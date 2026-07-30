"""Tests for T05: CSV import accepts files with and without a category column."""

import subprocess
import sys
from pathlib import Path

from stockroom import csv_io
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


def write_v1_csv(path):
    path.write_text(
        "sku,name,qty,unit_price,supplier_id\n"
        "WID-1,Widget,4,2.5,\n"
        "GAD-1,Gadget,9,1.25,\n",
        encoding="utf-8",
    )


def test_import_without_category_column_defaults_to_uncategorized(tmp_path):
    csv_path = tmp_path / "old.csv"
    write_v1_csv(csv_path)

    store = make_store(tmp_path)
    assert csv_io.import_items(store, str(csv_path)) == 2
    item = store.get_item("WID-1")
    assert item.qty == 4
    assert round(item.unit_price, 2) == 2.5
    assert item.category == "uncategorized"
    assert store.get_item("GAD-1").category == "uncategorized"


def test_import_with_category_column_keeps_category(tmp_path):
    csv_path = tmp_path / "new.csv"
    csv_path.write_text(
        "sku,name,qty,unit_price,supplier_id,category\n"
        "WID-1,Widget,4,2.5,,tools\n"
        "GAD-1,Gadget,9,1.25,,gadgets\n",
        encoding="utf-8",
    )

    store = make_store(tmp_path)
    assert csv_io.import_items(store, str(csv_path)) == 2
    assert store.get_item("WID-1").category == "tools"
    assert store.get_item("GAD-1").category == "gadgets"


def test_export_import_round_trip_preserves_categories(tmp_path):
    store = make_store(tmp_path)
    store.add_item("WID-1", "Widget", qty=2, unit_price=2.0, category="tools")
    store.add_item("SCR-1", "Screws", qty=10, unit_price=0.35)

    out = tmp_path / "items.csv"
    csv_io.export_items(store, str(out))

    other = Store(str(tmp_path / "other.json"))
    csv_io.import_items(other, str(out))
    assert other.get_item("WID-1").category == "tools"
    assert other.get_item("SCR-1").category == "uncategorized"


def test_cli_import_of_old_layout_succeeds(tmp_path):
    csv_path = tmp_path / "old.csv"
    write_v1_csv(csv_path)

    result = run_cli(tmp_path, "import-csv", str(csv_path))
    assert result.returncode == 0, result.stderr
    assert "2" in result.stdout

    store = make_store(tmp_path)
    store.load()
    assert store.get_item("WID-1").category == "uncategorized"
