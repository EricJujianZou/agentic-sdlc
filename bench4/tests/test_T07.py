"""Tests for T07: strict order status transitions."""

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


def test_receiving_a_cancelled_order_is_rejected(tmp_path):
    store = make_store(tmp_path)
    store.add_item("WID-1", "Widget", qty=1)
    order = store.place_order("WID-1", 20, "2026-07-01")
    store.cancel_order(order.id)

    with pytest.raises(ValueError):
        store.receive_order(order.id)
    assert store.get_order(order.id).status == "cancelled"
    assert store.get_item("WID-1").qty == 1


def test_cancelling_a_received_order_is_rejected(tmp_path):
    store = make_store(tmp_path)
    store.add_item("WID-1", "Widget", qty=1)
    order = store.place_order("WID-1", 20, "2026-07-01")
    store.receive_order(order.id)

    with pytest.raises(ValueError):
        store.cancel_order(order.id)
    assert store.get_order(order.id).status == "received"


def test_double_receive_is_rejected_and_stock_added_once(tmp_path):
    store = make_store(tmp_path)
    store.add_item("WID-1", "Widget", qty=1)
    order = store.place_order("WID-1", 20, "2026-07-01")
    store.receive_order(order.id)
    assert store.get_item("WID-1").qty == 21

    with pytest.raises(ValueError):
        store.receive_order(order.id)
    assert store.get_item("WID-1").qty == 21


def test_double_cancel_is_rejected(tmp_path):
    store = make_store(tmp_path)
    store.add_item("WID-1", "Widget", qty=1)
    order = store.place_order("WID-1", 20, "2026-07-01")
    store.cancel_order(order.id)

    with pytest.raises(ValueError):
        store.cancel_order(order.id)


def test_valid_transitions_still_work(tmp_path):
    store = make_store(tmp_path)
    store.add_item("WID-1", "Widget", qty=1)
    first = store.place_order("WID-1", 5, "2026-07-01")
    second = store.place_order("WID-1", 7, "2026-07-02")

    store.receive_order(first.id)
    store.cancel_order(second.id)
    assert store.get_order(first.id).status == "received"
    assert store.get_order(second.id).status == "cancelled"
    assert store.get_item("WID-1").qty == 6


def test_cli_invalid_transition_exits_1_and_changes_nothing(tmp_path):
    assert run_cli(tmp_path, "add-item", "WID-1", "Widget",
                   "--qty", "1").returncode == 0
    assert run_cli(tmp_path, "place-order", "WID-1", "20",
                   "--date", "2026-07-01").returncode == 0
    assert run_cli(tmp_path, "cancel-order", "1").returncode == 0

    result = run_cli(tmp_path, "receive-order", "1")
    assert result.returncode == 1
    assert "error" in result.stderr.lower()

    store = make_store(tmp_path)
    store.load()
    assert store.get_order(1).status == "cancelled"
    assert store.get_item("WID-1").qty == 1
