"""Tests for T10: --actor on mutating commands records last_actor."""

import subprocess
import sys
from pathlib import Path

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


def load_store(tmp_path):
    store = make_store(tmp_path)
    store.load()
    return store


def test_add_item_records_actor(tmp_path):
    result = run_cli(tmp_path, "add-item", "WID-1", "Widget",
                     "--qty", "2", "--actor", "alice")
    assert result.returncode == 0, result.stderr

    store = load_store(tmp_path)
    assert store.get_item("WID-1").last_actor == "alice"


def test_receive_and_ship_overwrite_actor(tmp_path):
    assert run_cli(tmp_path, "add-item", "WID-1", "Widget", "--qty", "5",
                   "--actor", "alice").returncode == 0

    assert run_cli(tmp_path, "receive", "WID-1", "5",
                   "--actor", "bob").returncode == 0
    assert load_store(tmp_path).get_item("WID-1").last_actor == "bob"

    assert run_cli(tmp_path, "ship", "WID-1", "1",
                   "--actor", "carol").returncode == 0
    assert load_store(tmp_path).get_item("WID-1").last_actor == "carol"


def test_orders_record_actor_through_their_lifecycle(tmp_path):
    assert run_cli(tmp_path, "add-item", "WID-1", "Widget",
                   "--qty", "1").returncode == 0

    result = run_cli(tmp_path, "place-order", "WID-1", "20",
                     "--date", "2026-07-01", "--actor", "dana")
    assert result.returncode == 0, result.stderr
    assert load_store(tmp_path).get_order(1).last_actor == "dana"

    assert run_cli(tmp_path, "receive-order", "1",
                   "--actor", "evan").returncode == 0
    assert load_store(tmp_path).get_order(1).last_actor == "evan"

    result = run_cli(tmp_path, "place-order", "WID-1", "3",
                     "--date", "2026-07-02", "--actor", "dana")
    assert result.returncode == 0, result.stderr
    assert run_cli(tmp_path, "cancel-order", "2",
                   "--actor", "frank").returncode == 0
    assert load_store(tmp_path).get_order(2).last_actor == "frank"


def test_actor_is_optional_and_defaults_to_none(tmp_path):
    result = run_cli(tmp_path, "add-item", "WID-1", "Widget", "--qty", "2")
    assert result.returncode == 0, result.stderr

    store = load_store(tmp_path)
    assert store.get_item("WID-1").last_actor is None


def test_actor_survives_save_and_reload_round_trip(tmp_path):
    assert run_cli(tmp_path, "add-item", "WID-1", "Widget", "--qty", "2",
                   "--actor", "alice").returncode == 0
    # An unrelated mutation on another record must not disturb it.
    assert run_cli(tmp_path, "add-item", "GAD-1", "Gadget", "--qty", "1",
                   "--actor", "bob").returncode == 0

    store = load_store(tmp_path)
    assert store.get_item("WID-1").last_actor == "alice"
    assert store.get_item("GAD-1").last_actor == "bob"
