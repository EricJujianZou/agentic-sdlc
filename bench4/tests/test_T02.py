"""Tests for T02: supplier lead times and their surfacing in suggestions."""

import shutil
import subprocess
import sys
from pathlib import Path

from stockroom import reports
from stockroom.store import Store

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_V1 = Path(__file__).resolve().parent / "fixtures" / "state_v1.json"


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


def test_lead_time_round_trips_through_save_and_load(tmp_path):
    store = make_store(tmp_path)
    store.add_supplier("acme", "Acme Supply", "orders@acme.example",
                       lead_time_days=7)
    store.save()

    fresh = make_store(tmp_path)
    fresh.load()
    assert fresh.get_supplier("acme").lead_time_days == 7


def test_lead_time_defaults_to_zero(tmp_path):
    store = make_store(tmp_path)
    store.add_supplier("acme", "Acme Supply", "orders@acme.example")
    assert store.get_supplier("acme").lead_time_days == 0


def test_legacy_state_loads_with_zero_lead_time(tmp_path):
    shutil.copy(FIXTURE_V1, tmp_path / "state.json")
    store = make_store(tmp_path)
    store.load()
    assert store.get_supplier("acme").lead_time_days == 0
    assert store.get_supplier("globex").lead_time_days == 0


def test_reorder_suggestions_include_lead_time(tmp_path):
    store = make_store(tmp_path)
    store.add_supplier("acme", "Acme Supply", "orders@acme.example",
                       lead_time_days=10)
    store.add_item("WID-1", "Widget", qty=2, supplier_id="acme")

    rows = reports.reorder_suggestions(store, threshold=5)
    matching = [row for row in rows if row["sku"] == "WID-1"]
    assert len(matching) == 1
    assert matching[0]["lead_time_days"] == 10
    assert matching[0]["suggested_qty"] == 3


def test_cli_add_supplier_lead_time_flag(tmp_path):
    result = run_cli(tmp_path, "add-supplier", "acme", "Acme Supply",
                     "orders@acme.example", "--lead-time", "7")
    assert result.returncode == 0, result.stderr

    store = make_store(tmp_path)
    store.load()
    assert store.get_supplier("acme").lead_time_days == 7
