"""T36: scheduled-reorders places suggested orders, idempotently per day."""

import pathlib
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


def _cli(tmp, *args):
    return subprocess.run(
        [sys.executable, "-m", "stockroom.cli", "--data", str(tmp), *args],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )


def _store(tmp):
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from stockroom.store import Store
    store = Store(str(tmp / "state.json"))
    store.load()
    return store


def _setup(tmp):
    _cli(tmp, "add-supplier", "acme", "Acme Supply", "orders@acme.example")
    # low and reorderable: suggested = 5 - 1 = 4 at the default threshold
    _cli(tmp, "add-item", "WID-1", "Widget", "--qty", "1",
         "--price", "1.0", "--supplier", "acme")
    # low but no supplier: never auto-ordered
    _cli(tmp, "add-item", "NOS-1", "No supplier", "--qty", "1",
         "--price", "1.0")
    # well stocked: never auto-ordered at the default threshold
    _cli(tmp, "add-item", "FUL-1", "Full shelf", "--qty", "50",
         "--price", "1.0", "--supplier", "acme")


def test_places_order_for_each_suggestion(tmp_path):
    _setup(tmp_path)
    result = _cli(tmp_path, "scheduled-reorders", "--as-of", "2026-08-01")
    assert result.returncode == 0, result.stderr
    orders = _store(tmp_path).orders
    assert len(orders) == 1
    order = orders[0]
    assert order.sku == "WID-1"
    assert order.qty == 4
    assert order.date == "2026-08-01"
    assert order.status == "pending"


def test_skips_items_without_supplier_or_not_low(tmp_path):
    _setup(tmp_path)
    _cli(tmp_path, "scheduled-reorders", "--as-of", "2026-08-01")
    assert {o.sku for o in _store(tmp_path).orders} == {"WID-1"}


def test_same_day_rerun_is_idempotent(tmp_path):
    _setup(tmp_path)
    _cli(tmp_path, "scheduled-reorders", "--as-of", "2026-08-01")
    result = _cli(tmp_path, "scheduled-reorders", "--as-of", "2026-08-01")
    assert result.returncode == 0
    assert len(_store(tmp_path).orders) == 1


def test_next_day_covered_by_pending_order(tmp_path):
    _setup(tmp_path)
    _cli(tmp_path, "scheduled-reorders", "--as-of", "2026-08-01")
    result = _cli(tmp_path, "scheduled-reorders", "--as-of", "2026-08-02")
    assert result.returncode == 0
    # the pending auto-order already covers the shortfall
    assert len(_store(tmp_path).orders) == 1


def test_threshold_option(tmp_path):
    _setup(tmp_path)
    result = _cli(tmp_path, "scheduled-reorders", "--as-of", "2026-08-02",
                  "--threshold", "60")
    assert result.returncode == 0, result.stderr
    orders = {o.sku: o for o in _store(tmp_path).orders}
    assert set(orders) == {"WID-1", "FUL-1"}
    assert orders["WID-1"].qty == 59
    assert orders["FUL-1"].qty == 10
    assert orders["WID-1"].date == "2026-08-02"


def test_nothing_to_do_exits_zero(tmp_path):
    _cli(tmp_path, "add-supplier", "acme", "Acme", "a@x.example")
    _cli(tmp_path, "add-item", "FUL-1", "Full shelf", "--qty", "50",
         "--price", "1.0", "--supplier", "acme")
    result = _cli(tmp_path, "scheduled-reorders", "--as-of", "2026-08-01")
    assert result.returncode == 0, result.stderr
    assert len(_store(tmp_path).orders) == 0
