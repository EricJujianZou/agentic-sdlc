"""Locked tests for T44 - schema v7 split storage, atomic writes, and
backward-compatible loading of every earlier state format."""
import json
import pathlib
import shutil
import subprocess
import sys

import pytest

from stockroom import reports
from stockroom.store import Store

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "bench4" / "tests" / "fixtures"


def run_cli(data_dir, *args):
    return subprocess.run(
        [sys.executable, "-m", "stockroom.cli", "--data", str(data_dir), *args],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )


def load_store(state_path):
    store = Store(str(state_path))
    store.load()
    return store


def sig(store):
    return (
        sorted(store.items),
        {sku: store.items[sku].qty for sku in store.items},
        len(store.orders),
    )


def test_v1_fixture_loads_and_upgrades_to_v7(tmp_path):
    shutil.copy(FIXTURES / "state_v1.json", tmp_path / "state.json")
    store = load_store(tmp_path / "state.json")
    assert sorted(store.items) == [
        "GAD-1", "GAD-2", "SCR-1", "SCR-2", "WID-1", "WID-2", "WID-3",
    ]
    assert store.items["WID-1"].qty == 3
    assert len(store.orders) == 5
    # The legacy unpadded "2026-1-5" order must count as January 2026.
    assert len(reports.monthly_orders(store, "2026-01")) == 2
    before = sig(store)
    store.save()
    raw = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    assert raw.get("version") == 7
    assert sig(load_store(tmp_path / "state.json")) == before


LEGACY_VERSIONS = [
    pytest.param(
        k,
        marks=pytest.mark.skipif(
            not (FIXTURES / f"state_v{k}.json").exists(),
            reason=f"fixture state_v{k}.json not present yet",
        ),
    )
    for k in (2, 3, 4, 5, 6)
]


@pytest.mark.parametrize("version", LEGACY_VERSIONS)
def test_legacy_fixture_roundtrips_through_v7(tmp_path, version):
    shutil.copy(FIXTURES / f"state_v{version}.json", tmp_path / "state.json")
    if version == 6:
        sidecar = FIXTURES / "state_v6.events.json"
        if sidecar.exists():
            shutil.copy(sidecar, tmp_path / "state.events.json")
    store = load_store(tmp_path / "state.json")
    assert store.items, f"v{version} fixture loaded no items"
    before = sig(store)
    store.save()
    raw = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    assert raw.get("version") == 7
    assert sig(load_store(tmp_path / "state.json")) == before


def test_v7_layout_written_for_fresh_state(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    for args in [
        ("add-supplier", "ACME", "Acme Supply", "orders@acme.example"),
        ("add-item", "WID-1", "Widget", "--qty", "10", "--price", "2.50",
         "--supplier", "ACME"),
        ("receive", "WID-1", "4", "--warehouse", "east"),
        ("place-order", "WID-1", "5", "--date", "2026-03-01"),
    ]:
        r = run_cli(data, *args)
        assert r.returncode == 0, (args, r.stderr)

    meta = json.loads((data / "state.json").read_text(encoding="utf-8"))
    assert meta.get("version") == 7

    main = json.loads((data / "items.main.json").read_text(encoding="utf-8"))
    assert main.get("WID-1") == 10
    east = json.loads((data / "items.east.json").read_text(encoding="utf-8"))
    assert east.get("WID-1") == 4

    orders = json.loads((data / "orders.json").read_text(encoding="utf-8"))
    assert isinstance(orders, list)
    assert len(orders) == 1
    assert orders[0]["sku"] == "WID-1"

    # Atomic writes must not leave temp litter behind.
    leftovers = [p.name for p in data.rglob("*") if ".tmp" in p.name]
    assert leftovers == []

    store = load_store(data / "state.json")
    assert store.items["WID-1"].qty == 14
    assert len(store.orders) == 1


def test_old_single_file_state_upgraded_in_place_by_cli(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    shutil.copy(FIXTURES / "state_v1.json", data / "state.json")
    r = run_cli(data, "receive", "WID-1", "2")
    assert r.returncode == 0, r.stderr
    meta = json.loads((data / "state.json").read_text(encoding="utf-8"))
    assert meta.get("version") == 7
    main = json.loads((data / "items.main.json").read_text(encoding="utf-8"))
    assert main.get("WID-1") == 5
    assert main.get("GAD-1") == 5
