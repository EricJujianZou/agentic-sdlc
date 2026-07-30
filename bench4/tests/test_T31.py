"""T31: supplier on-time delivery report."""

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


def _reports():
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from stockroom import reports
    return reports


def _build(tmp):
    store = _store(tmp)
    store.add_supplier("acme", "Acme Supply", "orders@acme.example",
                       lead_time_days=5)
    store.add_supplier("globex", "Globex", "purchasing@globex.example",
                       lead_time_days=3)
    store.save()
    _cli(tmp, "add-item", "WID-1", "Widget", "--qty", "10",
         "--price", "4.0", "--supplier", "acme")
    _cli(tmp, "add-item", "GAD-1", "Gadget", "--qty", "10",
         "--price", "2.0", "--supplier", "globex")
    # id 1: acme, arrives exactly on the last allowed day -> on time
    _cli(tmp, "place-order", "WID-1", "5", "--date", "2026-07-01")
    _cli(tmp, "receive-order", "1", "--date", "2026-07-06")
    # id 2: acme, arrives 9 days after placing (lead 5) -> late
    _cli(tmp, "place-order", "WID-1", "5", "--date", "2026-07-01")
    _cli(tmp, "receive-order", "2", "--date", "2026-07-10")
    # id 3: globex, arrives next day (lead 3) -> on time
    _cli(tmp, "place-order", "GAD-1", "2", "--date", "2026-07-01")
    _cli(tmp, "receive-order", "3", "--date", "2026-07-02")
    # id 4: globex, still pending -> never counted
    _cli(tmp, "place-order", "GAD-1", "2", "--date", "2026-07-05")
    # id 5: acme, cancelled -> never counted
    _cli(tmp, "place-order", "WID-1", "1", "--date", "2026-07-03")
    _cli(tmp, "cancel-order", "5")


def _rows(tmp):
    return _reports().supplier_on_time(_store(tmp))


def test_cli_receive_order_accepts_date_flag(tmp_path):
    _cli(tmp_path, "add-item", "WID-1", "Widget", "--qty", "1")
    _cli(tmp_path, "place-order", "WID-1", "2", "--date", "2026-07-01")
    result = _cli(tmp_path, "receive-order", "1", "--date", "2026-07-04")
    assert result.returncode == 0, result.stderr


def test_receive_order_records_arrival_date(tmp_path):
    _build(tmp_path)
    store = _store(tmp_path)
    order = store.get_order(1)
    assert getattr(order, "received_date", None) == "2026-07-06"


def test_on_time_counts_and_percentages(tmp_path):
    _build(tmp_path)
    by_supplier = {row["supplier_id"]: row for row in _rows(tmp_path)}
    acme = by_supplier["acme"]
    # order 1 arrived exactly lead_time days after placing: still on time
    assert acme["total"] == 2
    assert acme["on_time"] == 1
    assert round(acme["pct"], 1) == 50.0
    globex = by_supplier["globex"]
    assert globex["total"] == 1
    assert globex["on_time"] == 1
    assert round(globex["pct"], 1) == 100.0


def test_pending_and_cancelled_orders_ignored(tmp_path):
    _build(tmp_path)
    by_supplier = {row["supplier_id"]: row for row in _rows(tmp_path)}
    # acme has 3 orders total but the cancelled one never counts
    assert by_supplier["acme"]["total"] == 2
    # globex has 2 orders total but the pending one never counts
    assert by_supplier["globex"]["total"] == 1


def test_rows_sorted_by_supplier_id(tmp_path):
    _build(tmp_path)
    assert [row["supplier_id"] for row in _rows(tmp_path)] == ["acme", "globex"]


def test_cli_on_time_report(tmp_path):
    _build(tmp_path)
    result = _cli(tmp_path, "report", "on-time")
    assert result.returncode == 0, result.stderr
    assert "acme" in result.stdout
    assert "globex" in result.stdout
    assert "50" in result.stdout
    assert "100" in result.stdout
