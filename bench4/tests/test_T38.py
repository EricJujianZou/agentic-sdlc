"""T38: order history must be chronological, whatever the stored date shape."""

import json
import pathlib
import re
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


def _history(tmp, sku):
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from stockroom import reports
    return reports.order_history(_store(tmp), sku)


def _write_state(tmp, orders):
    state = {
        "items": {
            "WID-1": {"sku": "WID-1", "name": "Widget", "qty": 10,
                      "unit_price": 1.0, "supplier_id": None},
        },
        "suppliers": {},
        "orders": orders,
    }
    (tmp / "state.json").write_text(json.dumps(state, indent=2),
                                    encoding="utf-8")


def _mixed_dates(tmp):
    # chronological order of ids: 3 (2025-12-30), 2 (Jan 5), 4 (Jan 15),
    # 1 (Jan 20); the legacy unpadded strings sort wrongly as plain text
    _write_state(tmp, [
        {"id": 1, "sku": "WID-1", "qty": 1, "date": "2026-01-20",
         "status": "pending"},
        {"id": 2, "sku": "WID-1", "qty": 2, "date": "2026-1-5",
         "status": "received"},
        {"id": 3, "sku": "WID-1", "qty": 3, "date": "2025-12-30",
         "status": "received"},
        {"id": 4, "sku": "WID-1", "qty": 4, "date": "2026-1-15",
         "status": "pending"},
    ])


def _parsed(date_string):
    year, month, day = date_string.split("-")
    return (int(year), int(month), int(day))


def test_history_is_chronological_with_legacy_dates(tmp_path):
    _mixed_dates(tmp_path)
    assert [row["id"] for row in _history(tmp_path, "WID-1")] == [3, 2, 4, 1]


def test_history_dates_nondecreasing_when_parsed(tmp_path):
    _mixed_dates(tmp_path)
    parsed = [_parsed(row["date"]) for row in _history(tmp_path, "WID-1")]
    assert parsed == sorted(parsed)


def test_cli_history_ordering(tmp_path):
    _mixed_dates(tmp_path)
    result = _cli(tmp_path, "report", "history", "WID-1")
    assert result.returncode == 0, result.stderr
    ids = [int(m) for m in re.findall(r"order\s+(\d+)", result.stdout)]
    assert ids == [3, 2, 4, 1]


def test_same_day_orders_keep_placement_order(tmp_path):
    _write_state(tmp_path, [
        {"id": 1, "sku": "WID-1", "qty": 1, "date": "2026-03-05",
         "status": "pending"},
        {"id": 2, "sku": "WID-1", "qty": 2, "date": "2026-03-01",
         "status": "pending"},
        {"id": 3, "sku": "WID-1", "qty": 3, "date": "2026-03-05",
         "status": "pending"},
    ])
    assert [row["id"] for row in _history(tmp_path, "WID-1")] == [2, 1, 3]


def test_iso_only_history_sorted(tmp_path):
    _cli(tmp_path, "add-item", "WID-1", "Widget", "--qty", "5",
         "--price", "1.0")
    _cli(tmp_path, "place-order", "WID-1", "1", "--date", "2026-05-01")
    _cli(tmp_path, "place-order", "WID-1", "1", "--date", "2026-04-01")
    assert [row["id"] for row in _history(tmp_path, "WID-1")] == [2, 1]
