"""Locked tests for T21 - price change tracking."""

import pathlib
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


def run_cli(data_dir, *args):
    return subprocess.run(
        [sys.executable, "-m", "stockroom.cli", "--data", str(data_dir), *args],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )


def _seed(tmp):
    r = run_cli(tmp, "add-item", "WID-1", "Widget", "--qty", "3",
                "--price", "19.99")
    assert r.returncode == 0, r.stderr


def _load(tmp):
    from stockroom.store import Store
    store = Store(str(tmp / "state.json"))
    store.load()
    return store


def test_set_price_api_updates_price_and_history(tmp_path):
    _seed(tmp_path)
    store = _load(tmp_path)
    store.set_price("WID-1", 24.5, date="2026-07-05")
    item = store.get_item("WID-1")
    assert round(item.unit_price, 2) == 24.5
    hist = item.price_history
    assert len(hist) == 1
    entry = hist[0]
    assert entry["date"] == "2026-07-05"
    assert round(entry["old"], 2) == 19.99
    assert round(entry["new"], 2) == 24.5


def test_multiple_changes_append_in_order(tmp_path):
    _seed(tmp_path)
    store = _load(tmp_path)
    store.set_price("WID-1", 24.5, date="2026-07-05")
    store.set_price("WID-1", 22.0, date="2026-07-12")
    item = store.get_item("WID-1")
    assert round(item.unit_price, 2) == 22.0
    hist = item.price_history
    assert len(hist) == 2
    assert round(hist[0]["old"], 2) == 19.99
    assert round(hist[0]["new"], 2) == 24.5
    assert round(hist[1]["old"], 2) == 24.5
    assert round(hist[1]["new"], 2) == 22.0


def test_cli_set_price_and_report(tmp_path):
    _seed(tmp_path)
    r = run_cli(tmp_path, "set-price", "WID-1", "24.50",
                "--date", "2026-07-05")
    assert r.returncode == 0, r.stderr
    r = run_cli(tmp_path, "report", "price-changes")
    assert r.returncode == 0, r.stderr
    assert "WID-1" in r.stdout
    assert "2026-07-05" in r.stdout
    assert "19.99" in r.stdout
    assert "24.50" in r.stdout


def test_price_history_persists_across_processes(tmp_path):
    _seed(tmp_path)
    r = run_cli(tmp_path, "set-price", "WID-1", "24.50",
                "--date", "2026-07-05")
    assert r.returncode == 0, r.stderr
    store = _load(tmp_path)
    item = store.get_item("WID-1")
    assert round(item.unit_price, 2) == 24.5
    hist = item.price_history
    assert len(hist) == 1
    assert hist[0]["date"] == "2026-07-05"
    assert round(hist[0]["old"], 2) == 19.99
    assert round(hist[0]["new"], 2) == 24.5


def test_price_changes_report_sorted_oldest_first(tmp_path):
    _seed(tmp_path)
    r = run_cli(tmp_path, "add-item", "GAD-1", "Gadget", "--qty", "1",
                "--price", "2.50")
    assert r.returncode == 0, r.stderr
    r = run_cli(tmp_path, "set-price", "WID-1", "24.50",
                "--date", "2026-07-10")
    assert r.returncode == 0, r.stderr
    r = run_cli(tmp_path, "set-price", "GAD-1", "3.00",
                "--date", "2026-07-05")
    assert r.returncode == 0, r.stderr

    from stockroom import reports
    store = _load(tmp_path)
    rows = reports.price_changes(store)
    assert len(rows) == 2
    assert {"sku", "date", "old", "new"} <= set(rows[0])
    assert rows[0]["sku"] == "GAD-1"
    assert rows[0]["date"] == "2026-07-05"
    assert rows[1]["sku"] == "WID-1"
    assert rows[1]["date"] == "2026-07-10"
    assert round(rows[0]["new"], 2) == 3.0
    assert round(rows[1]["new"], 2) == 24.5


def test_set_price_unknown_sku_is_user_error(tmp_path):
    _seed(tmp_path)
    r = run_cli(tmp_path, "set-price", "NOPE-1", "1.00",
                "--date", "2026-07-05")
    assert r.returncode == 1
