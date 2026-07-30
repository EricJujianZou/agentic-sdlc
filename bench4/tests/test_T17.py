"""T17 — partial deliveries against purchase orders (ship-order)."""

import pathlib
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def run_cli(data_dir, *args):
    return subprocess.run(
        [sys.executable, "-m", "stockroom.cli", "--data", str(data_dir)]
        + [str(a) for a in args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )


def ok(result):
    assert result.returncode == 0, result.stdout + result.stderr
    return result


def load_store(data_dir):
    from stockroom.store import Store

    store = Store(str(pathlib.Path(data_dir) / "state.json"))
    store.load()
    return store


def _setup(tmp_path):
    ok(run_cli(tmp_path, "add-item", "WID-1", "Widget", "--qty", "0"))
    ok(run_cli(tmp_path, "place-order", "WID-1", "10", "--date",
               "2026-04-01"))


def test_partial_delivery_keeps_order_pending(tmp_path):
    _setup(tmp_path)
    ok(run_cli(tmp_path, "ship-order", "1", "--qty", "4"))
    store = load_store(tmp_path)
    assert store.get_item("WID-1").qty == 4
    order = store.get_order(1)
    assert order.status == "pending"
    assert order.shipped_qty == 4


def test_completing_delivery_flips_to_received(tmp_path):
    _setup(tmp_path)
    ok(run_cli(tmp_path, "ship-order", "1", "--qty", "4"))
    ok(run_cli(tmp_path, "ship-order", "1", "--qty", "6"))
    store = load_store(tmp_path)
    assert store.get_item("WID-1").qty == 10
    order = store.get_order(1)
    assert order.status == "received"
    assert order.shipped_qty == 10


def test_overdelivery_rejected(tmp_path):
    _setup(tmp_path)
    result = run_cli(tmp_path, "ship-order", "1", "--qty", "11")
    assert result.returncode == 1
    store = load_store(tmp_path)
    assert store.get_item("WID-1").qty == 0
    assert store.get_order(1).status == "pending"


def test_zero_quantity_rejected(tmp_path):
    _setup(tmp_path)
    result = run_cli(tmp_path, "ship-order", "1", "--qty", "0")
    assert result.returncode == 1
    assert load_store(tmp_path).get_item("WID-1").qty == 0


def test_cancelled_order_takes_no_delivery(tmp_path):
    _setup(tmp_path)
    ok(run_cli(tmp_path, "cancel-order", "1"))
    result = run_cli(tmp_path, "ship-order", "1", "--qty", "2")
    assert result.returncode == 1
    store = load_store(tmp_path)
    assert store.get_item("WID-1").qty == 0
    assert store.get_order(1).status == "cancelled"


def test_receive_order_delivers_only_the_remainder(tmp_path):
    _setup(tmp_path)
    ok(run_cli(tmp_path, "ship-order", "1", "--qty", "4"))
    ok(run_cli(tmp_path, "receive-order", "1"))
    store = load_store(tmp_path)
    assert store.get_item("WID-1").qty == 10
    assert store.get_order(1).status == "received"
