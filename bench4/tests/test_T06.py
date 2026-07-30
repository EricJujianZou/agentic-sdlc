"""Tests for T06: low-stock report grouped by category."""

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


def test_groups_low_items_by_category(tmp_path):
    store = make_store(tmp_path)
    store.add_item("WID-1", "Widget", qty=2, category="tools")
    store.add_item("WID-2", "Widget deluxe", qty=1, category="tools")
    store.add_item("GLU-1", "Glue stick", qty=3, category="adhesives")
    store.add_item("SCR-1", "Screws", qty=100, category="fasteners")

    grouped = reports.low_stock_by_category(store, threshold=5)
    assert sorted(grouped) == ["adhesives", "tools"]
    assert [row["sku"] for row in grouped["tools"]] == ["WID-1", "WID-2"]
    assert [row["sku"] for row in grouped["adhesives"]] == ["GLU-1"]
    assert grouped["tools"][0]["qty"] == 2


def test_categories_with_no_low_items_are_absent(tmp_path):
    store = make_store(tmp_path)
    store.add_item("WID-1", "Widget", qty=50, category="tools")
    store.add_item("GLU-1", "Glue stick", qty=1, category="adhesives")

    grouped = reports.low_stock_by_category(store, threshold=5)
    assert "tools" not in grouped
    assert [row["sku"] for row in grouped["adhesives"]] == ["GLU-1"]


def test_uncategorized_items_grouped_under_uncategorized(tmp_path):
    store = make_store(tmp_path)
    store.add_item("MISC-1", "Mystery box", qty=1)

    grouped = reports.low_stock_by_category(store, threshold=5)
    assert [row["sku"] for row in grouped["uncategorized"]] == ["MISC-1"]


def test_nothing_low_gives_empty_dict(tmp_path):
    store = make_store(tmp_path)
    store.add_item("WID-1", "Widget", qty=50, category="tools")
    assert reports.low_stock_by_category(store, threshold=5) == {}


def test_cli_report_low_by_category(tmp_path):
    assert run_cli(tmp_path, "add-item", "WID-1", "Widget", "--qty", "2",
                   "--category", "tools").returncode == 0
    assert run_cli(tmp_path, "add-item", "GLU-1", "Glue stick", "--qty", "1",
                   "--category", "adhesives").returncode == 0

    result = run_cli(tmp_path, "report", "low", "--by-category")
    assert result.returncode == 0, result.stderr
    assert "tools" in result.stdout
    assert "adhesives" in result.stdout
    assert "WID-1" in result.stdout
    assert "GLU-1" in result.stdout
