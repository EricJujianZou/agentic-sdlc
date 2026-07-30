"""Locked tests for T27 - low-stock and reorder suggestions agree at threshold."""

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
    r = run_cli(tmp, "add-supplier", "acme", "Acme Supply",
                "orders@acme.example")
    assert r.returncode == 0, r.stderr
    for sku, name, qty, supplier in (
        ("WID-7", "Widget seven", "5", "acme"),
        ("WID-2", "Widget two", "3", "acme"),
        ("WID-9", "Widget nine", "5", None),
        ("WID-8", "Widget eight", "9", "acme"),
    ):
        args = ["add-item", sku, name, "--qty", qty, "--price", "1.00"]
        if supplier:
            args += ["--supplier", supplier]
        r = run_cli(tmp, *args)
        assert r.returncode == 0, r.stderr


def _load(tmp):
    from stockroom.store import Store
    store = Store(str(tmp / "state.json"))
    store.load()
    return store


def _low_skus(store, threshold):
    from stockroom import reports
    result = reports.low_stock(store, threshold=threshold)
    if isinstance(result, dict):
        rows = [row for group in result.values() for row in group]
    else:
        rows = list(result)
    return {row["sku"] for row in rows}


def _suggestion_rows(store, threshold):
    from stockroom import reports
    return {row["sku"]: row
            for row in reports.reorder_suggestions(store, threshold=threshold)}


def test_item_at_threshold_in_both_reports(tmp_path):
    _seed(tmp_path)
    store = _load(tmp_path)
    assert _low_skus(store, 5) == {"WID-2", "WID-7", "WID-9"}
    assert set(_suggestion_rows(store, 5)) == {"WID-2", "WID-7"}


def test_reports_agree_for_supplied_items(tmp_path):
    _seed(tmp_path)
    store = _load(tmp_path)
    low = _low_skus(store, 9)
    assert low == {"WID-2", "WID-7", "WID-8", "WID-9"}
    # every low item with a supplier gets a suggestion; no supplier, none
    assert set(_suggestion_rows(store, 9)) == {"WID-2", "WID-7", "WID-8"}


def test_suggested_qty_at_boundary(tmp_path):
    _seed(tmp_path)
    store = _load(tmp_path)
    rows = _suggestion_rows(store, 5)
    assert rows["WID-7"]["suggested_qty"] == 0
    assert rows["WID-2"]["suggested_qty"] == 2


def test_cli_low_report_agrees(tmp_path):
    _seed(tmp_path)
    r = run_cli(tmp_path, "report", "low", "--threshold", "5")
    assert r.returncode == 0, r.stderr
    assert "WID-7" in r.stdout
    # WID-7 must also appear as a reorder suggestion line
    assert "WID-7:" in r.stdout, r.stdout


def test_nothing_low_when_all_above_threshold(tmp_path):
    _seed(tmp_path)
    store = _load(tmp_path)
    assert _low_skus(store, 2) == set()
    assert _suggestion_rows(store, 2) == {}
