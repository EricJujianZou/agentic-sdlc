"""Tests for T04: shipping must never take stock below zero."""

import subprocess
import sys
from pathlib import Path

import pytest

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


def test_overshipping_raises_and_leaves_qty_unchanged(tmp_path):
    store = make_store(tmp_path)
    store.add_item("WID-1", "Widget", qty=3)
    with pytest.raises(ValueError):
        store.ship("WID-1", 5)
    assert store.get_item("WID-1").qty == 3


def test_shipping_exact_stock_down_to_zero_is_allowed(tmp_path):
    store = make_store(tmp_path)
    store.add_item("WID-1", "Widget", qty=3)
    store.ship("WID-1", 3)
    assert store.get_item("WID-1").qty == 0


def test_cli_overship_exits_1_with_error(tmp_path):
    result = run_cli(tmp_path, "add-item", "WID-1", "Widget", "--qty", "3")
    assert result.returncode == 0, result.stderr

    result = run_cli(tmp_path, "ship", "WID-1", "10")
    assert result.returncode == 1
    assert "error" in result.stderr.lower()


def test_cli_overship_leaves_saved_state_untouched(tmp_path):
    assert run_cli(tmp_path, "add-item", "WID-1", "Widget",
                   "--qty", "3").returncode == 0
    assert run_cli(tmp_path, "ship", "WID-1", "10").returncode == 1

    store = make_store(tmp_path)
    store.load()
    assert store.get_item("WID-1").qty == 3


def test_cli_valid_ship_still_works(tmp_path):
    assert run_cli(tmp_path, "add-item", "WID-1", "Widget",
                   "--qty", "5").returncode == 0
    result = run_cli(tmp_path, "ship", "WID-1", "2")
    assert result.returncode == 0, result.stderr

    store = make_store(tmp_path)
    store.load()
    assert store.get_item("WID-1").qty == 3
