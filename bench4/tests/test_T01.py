"""Tests for T01: item categories (model, store, report grouping, CLI, CSV)."""

import csv
import subprocess
import sys
from pathlib import Path

from stockroom import reports
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


def test_category_round_trips_through_save_and_load(tmp_path):
    store = make_store(tmp_path)
    store.add_item("WID-1", "Widget", qty=3, unit_price=2.5, category="tools")
    store.save()

    fresh = make_store(tmp_path)
    fresh.load()
    assert fresh.get_item("WID-1").category == "tools"


def test_missing_category_defaults_to_uncategorized(tmp_path):
    store = make_store(tmp_path)
    store.add_item("WID-1", "Widget", qty=1)
    assert store.get_item("WID-1").category == "uncategorized"


def test_stock_report_by_category_groups_rows(tmp_path):
    store = make_store(tmp_path)
    store.add_item("WID-1", "Widget", qty=2, unit_price=2.0, category="tools")
    store.add_item("WID-2", "Widget deluxe", qty=1, unit_price=1.0,
                   category="tools")
    store.add_item("SCR-1", "Screws", qty=10, unit_price=0.1,
                   category="fasteners")

    report = reports.stock_report(store, by_category=True)
    categories = report["categories"]
    assert sorted(categories) == ["fasteners", "tools"]
    assert [row["sku"] for row in categories["tools"]] == ["WID-1", "WID-2"]
    assert [row["sku"] for row in categories["fasteners"]] == ["SCR-1"]
    assert round(report["total_value"], 2) == 6.0


def test_plain_stock_report_shape_unchanged(tmp_path):
    store = make_store(tmp_path)
    store.add_item("WID-1", "Widget", qty=4, unit_price=2.5)
    report = reports.stock_report(store)
    assert [row["sku"] for row in report["rows"]] == ["WID-1"]
    assert round(report["total_value"], 2) == 10.0


def test_cli_category_flag_and_csv_export(tmp_path):
    result = run_cli(tmp_path, "add-item", "WID-1", "Widget",
                     "--qty", "2", "--price", "1.50", "--category", "tools")
    assert result.returncode == 0, result.stderr
    result = run_cli(tmp_path, "add-item", "GAD-1", "Gadget")
    assert result.returncode == 0, result.stderr

    out = tmp_path / "items.csv"
    result = run_cli(tmp_path, "export-csv", str(out))
    assert result.returncode == 0, result.stderr

    with open(out, newline="", encoding="utf-8") as f:
        by_sku = {row["sku"]: row for row in csv.DictReader(f)}
    assert by_sku["WID-1"]["category"] == "tools"
    assert by_sku["GAD-1"]["category"] == "uncategorized"


def test_cli_report_stock_by_category(tmp_path):
    result = run_cli(tmp_path, "add-item", "WID-1", "Widget",
                     "--qty", "2", "--price", "1.00", "--category", "tools")
    assert result.returncode == 0, result.stderr

    result = run_cli(tmp_path, "report", "stock", "--by-category")
    assert result.returncode == 0, result.stderr
    assert "tools" in result.stdout
    assert "WID-1" in result.stdout
