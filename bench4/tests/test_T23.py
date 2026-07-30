"""Locked tests for T23 - integer-cents storage (schema v4) and back-compat."""

import pathlib
import shutil
import subprocess
import sys
from decimal import Decimal

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures"


def run_cli(data_dir, *args):
    return subprocess.run(
        [sys.executable, "-m", "stockroom.cli", "--data", str(data_dir), *args],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )


def _load_fixture(tmp_path, name, subdir="d"):
    src = FIXTURES / name
    assert src.exists(), f"missing fixture {name}"
    data_dir = tmp_path / subdir
    data_dir.mkdir(exist_ok=True)
    dst = data_dir / "state.json"
    shutil.copyfile(src, dst)
    from stockroom.store import Store
    store = Store(str(dst))
    store.load()
    return store


def test_item_constructor_stays_float_compatible():
    from stockroom.models import Item
    item = Item(sku="X-1", name="Thing", unit_price=3.5)
    assert item.unit_price == 3.5
    cheap = Item(sku="Y-1", name="Cheap thing", unit_price=0.07)
    assert cheap.unit_price == 0.07


def test_v1_fixture_still_loads(tmp_path):
    store = _load_fixture(tmp_path, "state_v1.json")
    assert set(store.items) == {"WID-1", "WID-2", "WID-3", "GAD-1", "GAD-2",
                                "SCR-1", "SCR-2"}
    wid1 = store.get_item("WID-1")
    assert wid1.qty == 3
    assert round(wid1.unit_price, 2) == 19.99
    assert set(store.suppliers) == {"acme", "globex"}
    assert len(store.orders) == 5
    assert store.get_order(1).date in ("2026-1-5", "2026-01-05")
    assert store.get_order(2).date == "2026-01-20"


def test_v2_and_v3_fixtures_still_load(tmp_path):
    for i, name in enumerate(("state_v2.json", "state_v3.json")):
        store = _load_fixture(tmp_path, name, subdir=f"d{i}")
        assert store.items, f"{name} loaded no items"
        for item in store.items.values():
            qty = item.qty
            assert qty == int(qty) and qty >= 0
            price = item.unit_price
            assert round(price, 2) == price


def test_v4_fixture_loads(tmp_path):
    store = _load_fixture(tmp_path, "state_v4.json")
    wid1 = store.get_item("WID-1")
    assert wid1.qty == 5  # 3 in main + 2 in east
    assert round(wid1.unit_price, 2) == 19.99
    assert wid1.category == "widgets"
    assert wid1.supplier_id == "acme"
    hist = wid1.price_history
    assert len(hist) == 1
    assert hist[0]["date"] == "2026-07-05"
    assert round(hist[0]["old"], 2) == 18.99
    assert round(hist[0]["new"], 2) == 19.99

    gad1 = store.get_item("GAD-1")
    assert gad1.qty == 5
    assert round(gad1.unit_price, 2) == 2.5
    assert gad1.category == "gadgets"

    scr2 = store.get_item("SCR-2")
    assert scr2.qty == 0
    assert round(scr2.unit_price, 2) == 4.2

    assert store.get_supplier("acme").lead_time_days == 7
    assert store.get_supplier("globex").lead_time_days == 14

    assert len(store.orders) == 2
    assert store.get_order(1).status == "received"
    assert store.get_order(2).date == "2026-07-02"


def test_v4_save_reload_roundtrip(tmp_path):
    store = _load_fixture(tmp_path, "state_v4.json")
    store.save()
    from stockroom.store import Store
    again = Store(store.path)
    again.load()
    wid1 = again.get_item("WID-1")
    assert wid1.qty == 5
    assert round(wid1.unit_price, 2) == 19.99
    assert len(wid1.price_history) == 1
    assert round(wid1.price_history[0]["old"], 2) == 18.99
    assert round(again.get_item("GAD-1").unit_price, 2) == 2.5
    assert len(again.orders) == 2


def test_money_math_exact_in_cents(tmp_path):
    from stockroom import reports
    from stockroom.store import Store
    store = Store(str(tmp_path / "state.json"))
    store.add_item("AAA-1", "Alpha", qty=1, unit_price=0.10)
    store.add_item("BBB-1", "Beta", qty=1, unit_price=0.20)
    total = reports.stock_report(store)["total_value"]
    assert Decimal(str(total)) == Decimal("0.30")


def test_cli_reads_v4_state(tmp_path):
    shutil.copyfile(FIXTURES / "state_v4.json", tmp_path / "state.json")
    r = run_cli(tmp_path, "report", "stock")
    assert r.returncode == 0, r.stderr
    assert "19.99" in r.stdout
