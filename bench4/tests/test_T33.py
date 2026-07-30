"""T33: aging report for pending orders, bucketed by --as-of age."""

import datetime
import pathlib
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

BUCKETS = ("0-7", "8-30", "31+")


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


def _build(tmp):
    _cli(tmp, "add-item", "WID-1", "Widget", "--qty", "50", "--price", "1.0")
    # ages relative to as-of 2026-08-01: 0, 7, 8, 30, 31 days
    _cli(tmp, "place-order", "WID-1", "1", "--date", "2026-08-01")  # id 1
    _cli(tmp, "place-order", "WID-1", "1", "--date", "2026-07-25")  # id 2
    _cli(tmp, "place-order", "WID-1", "1", "--date", "2026-07-24")  # id 3
    _cli(tmp, "place-order", "WID-1", "1", "--date", "2026-07-02")  # id 4
    _cli(tmp, "place-order", "WID-1", "1", "--date", "2026-07-01")  # id 5
    # id 6 received, id 7 cancelled: excluded from aging
    _cli(tmp, "place-order", "WID-1", "1", "--date", "2026-07-01")
    _cli(tmp, "receive-order", "6")
    _cli(tmp, "place-order", "WID-1", "1", "--date", "2026-07-20")
    _cli(tmp, "cancel-order", "7")


def _aging(tmp, as_of="2026-08-01"):
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from stockroom import reports
    return reports.order_aging(_store(tmp), as_of)


def _ids(bucket_rows):
    return {row["id"] for row in bucket_rows}


def test_pending_orders_bucketed_by_age(tmp_path):
    _build(tmp_path)
    aging = _aging(tmp_path)
    assert _ids(aging["0-7"]) == {1, 2}
    assert _ids(aging["8-30"]) == {3, 4}
    assert _ids(aging["31+"]) == {5}


def test_bucket_boundaries(tmp_path):
    _build(tmp_path)
    aging = _aging(tmp_path)
    assert 2 in _ids(aging["0-7"])    # exactly 7 days old
    assert 3 in _ids(aging["8-30"])   # exactly 8 days old
    assert 4 in _ids(aging["8-30"])   # exactly 30 days old
    assert 5 in _ids(aging["31+"])    # exactly 31 days old


def test_received_and_cancelled_excluded(tmp_path):
    _build(tmp_path)
    aging = _aging(tmp_path)
    everything = _ids(aging["0-7"]) | _ids(aging["8-30"]) | _ids(aging["31+"])
    assert 6 not in everything
    assert 7 not in everything


def test_bucket_keys_exact(tmp_path):
    _build(tmp_path)
    assert set(_aging(tmp_path).keys()) == set(BUCKETS)


def test_rows_carry_order_fields(tmp_path):
    _build(tmp_path)
    rows = {row["id"]: row for row in _aging(tmp_path)["0-7"]}
    row = rows[1]
    assert row["sku"] == "WID-1"
    assert row["qty"] == 1
    assert row["date"] == "2026-08-01"


def test_accepts_date_object_as_of(tmp_path):
    _build(tmp_path)
    aging = _aging(tmp_path, datetime.date(2026, 8, 1))
    assert _ids(aging["31+"]) == {5}


def test_cli_aging_report(tmp_path):
    _build(tmp_path)
    result = _cli(tmp_path, "report", "aging", "--as-of", "2026-08-01")
    assert result.returncode == 0, result.stderr
    for bucket in BUCKETS:
        assert bucket in result.stdout
