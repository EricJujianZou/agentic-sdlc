"""Tests for T09: case-insensitive item search over name and SKU."""

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


def populate(store):
    store.add_item("WID-1", "Steel Widget", qty=4)
    store.add_item("WID-2", "Brass Widget", qty=2)
    store.add_item("GAD-1", "Gadget", qty=9)


def test_search_by_name_is_case_insensitive(tmp_path):
    store = make_store(tmp_path)
    populate(store)
    rows = reports.search_items(store, "widget")
    assert [row["sku"] for row in rows] == ["WID-1", "WID-2"]
    assert rows[0]["name"] == "Steel Widget"


def test_search_matches_sku_substring(tmp_path):
    store = make_store(tmp_path)
    populate(store)
    rows = reports.search_items(store, "gad")
    assert [row["sku"] for row in rows] == ["GAD-1"]


def test_search_no_match_returns_empty_list(tmp_path):
    store = make_store(tmp_path)
    populate(store)
    assert reports.search_items(store, "zzz-nothing") == []


def test_search_results_sorted_by_sku(tmp_path):
    store = make_store(tmp_path)
    store.add_item("ZWID-1", "Widget premium", qty=1)
    store.add_item("AWID-1", "Widget budget", qty=1)
    rows = reports.search_items(store, "WIDGET")
    assert [row["sku"] for row in rows] == ["AWID-1", "ZWID-1"]


def test_cli_search_prints_matches_and_exits_zero(tmp_path):
    assert run_cli(tmp_path, "add-item", "WID-1", "Steel Widget",
                   "--qty", "4").returncode == 0
    assert run_cli(tmp_path, "add-item", "GAD-1", "Gadget",
                   "--qty", "9").returncode == 0

    result = run_cli(tmp_path, "search", "widget")
    assert result.returncode == 0, result.stderr
    assert "WID-1" in result.stdout
    assert "GAD-1" not in result.stdout

    result = run_cli(tmp_path, "search", "zzz-nothing")
    assert result.returncode == 0, result.stderr
    assert "WID-1" not in result.stdout
