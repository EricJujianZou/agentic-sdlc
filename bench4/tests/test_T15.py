"""T15 — reorder suggestions subtract units on pending purchase orders."""

import pathlib
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

THRESHOLD = 10


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
    ok(run_cli(tmp_path, "add-supplier", "acme", "Acme Supply",
               "orders@acme.example"))
    ok(run_cli(tmp_path, "add-item", "WID-1", "Widget", "--qty", "2",
               "--supplier", "acme"))


def _suggestion_for(store, sku):
    from stockroom import reports

    rows = reports.reorder_suggestions(store, threshold=THRESHOLD)
    matches = [row for row in rows if row["sku"] == sku]
    assert len(matches) <= 1
    return matches[0] if matches else None


def test_pending_order_reduces_suggestion(tmp_path):
    _setup(tmp_path)
    ok(run_cli(tmp_path, "place-order", "WID-1", "3", "--date", "2026-04-01"))
    row = _suggestion_for(load_store(tmp_path), "WID-1")
    assert row is not None
    assert row["suggested_qty"] == 5  # 10 - 2 on hand - 3 pending


def test_fully_covered_item_is_dropped(tmp_path):
    _setup(tmp_path)
    ok(run_cli(tmp_path, "place-order", "WID-1", "20", "--date", "2026-04-01"))
    row = _suggestion_for(load_store(tmp_path), "WID-1")
    assert row is None


def test_cancelled_orders_do_not_count(tmp_path):
    _setup(tmp_path)
    ok(run_cli(tmp_path, "place-order", "WID-1", "5", "--date", "2026-04-01"))
    ok(run_cli(tmp_path, "cancel-order", "1"))
    row = _suggestion_for(load_store(tmp_path), "WID-1")
    assert row is not None
    assert row["suggested_qty"] == 8  # 10 - 2 on hand, nothing pending


def test_received_orders_count_as_stock_not_pending(tmp_path):
    _setup(tmp_path)
    ok(run_cli(tmp_path, "place-order", "WID-1", "5", "--date", "2026-04-01"))
    ok(run_cli(tmp_path, "receive-order", "1"))
    row = _suggestion_for(load_store(tmp_path), "WID-1")
    assert row is not None
    assert row["suggested_qty"] == 3  # 10 - 7 now on hand


def test_cli_low_report_shows_adjusted_suggestion(tmp_path):
    _setup(tmp_path)
    ok(run_cli(tmp_path, "place-order", "WID-1", "3", "--date", "2026-04-01"))
    result = ok(run_cli(tmp_path, "report", "low", "--threshold",
                        str(THRESHOLD)))
    assert "order 5 from acme" in result.stdout
