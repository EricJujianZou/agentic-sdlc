"""Tests for T03: orders dated without leading zeros and the monthly report."""

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


def test_unpadded_dates_count_toward_the_month(tmp_path):
    store = make_store(tmp_path)
    store.add_item("WID-1", "Widget", qty=1)
    o_unpadded = store.place_order("WID-1", 2, "2026-1-5")
    o_padded = store.place_order("WID-1", 3, "2026-01-20")
    store.place_order("WID-1", 4, "2025-12-30")

    rows = reports.monthly_orders(store, "2026-01")
    assert [row["id"] for row in rows] == [o_unpadded.id, o_padded.id]


def test_mixed_padding_sorts_by_day(tmp_path):
    store = make_store(tmp_path)
    store.add_item("WID-1", "Widget", qty=1)
    o_mid = store.place_order("WID-1", 1, "2026-1-15")
    o_early = store.place_order("WID-1", 1, "2026-01-02")
    o_late = store.place_order("WID-1", 1, "2026-1-28")

    rows = reports.monthly_orders(store, "2026-01")
    assert [row["id"] for row in rows] == [o_early.id, o_mid.id, o_late.id]


def test_unpadded_date_not_leaked_into_wrong_month(tmp_path):
    store = make_store(tmp_path)
    store.add_item("WID-1", "Widget", qty=1)
    store.place_order("WID-1", 2, "2026-1-5")
    o_nov = store.place_order("WID-1", 6, "2026-11-05")

    rows = reports.monthly_orders(store, "2026-11")
    assert [row["id"] for row in rows] == [o_nov.id]


def test_padded_only_months_unaffected(tmp_path):
    store = make_store(tmp_path)
    store.add_item("WID-1", "Widget", qty=1)
    o_first = store.place_order("WID-1", 5, "2026-07-02")
    o_second = store.place_order("WID-1", 8, "2026-07-15")
    store.place_order("WID-1", 3, "2026-08-01")

    rows = reports.monthly_orders(store, "2026-07")
    assert [row["id"] for row in rows] == [o_first.id, o_second.id]


def test_cli_monthly_report_counts_unpadded_orders(tmp_path):
    assert run_cli(tmp_path, "add-item", "WID-1", "Widget").returncode == 0
    result = run_cli(tmp_path, "place-order", "WID-1", "20",
                     "--date", "2026-1-5")
    assert result.returncode == 0, result.stderr
    result = run_cli(tmp_path, "place-order", "WID-1", "3",
                     "--date", "2026-01-20")
    assert result.returncode == 0, result.stderr

    result = run_cli(tmp_path, "report", "monthly", "2026-01")
    assert result.returncode == 0, result.stderr
    assert "2 orders" in result.stdout
