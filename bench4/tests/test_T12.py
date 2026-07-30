"""T12 — per-warehouse stock (schema v3); v1/v2 files load into "main"."""

import json
import pathlib
import shutil
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


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


def test_item_constructor_puts_initial_qty_in_main():
    from stockroom.models import Item

    item = Item(sku="AAA-1", name="Thing", qty=5)
    assert item.qty == 5
    assert item.qty_in("main") == 5
    assert item.qty_in("east") == 0


def test_receive_and_ship_by_warehouse_api(tmp_path):
    from stockroom.store import Store

    store = Store(str(tmp_path / "state.json"))
    store.add_item("AAA-1", "Thing", qty=5)
    store.receive("AAA-1", 4, warehouse="east")
    item = store.get_item("AAA-1")
    assert item.qty == 9
    assert item.qty_in("main") == 5
    assert item.qty_in("east") == 4
    store.ship("AAA-1", 2, warehouse="east")
    assert item.qty_in("east") == 2
    assert item.qty == 7


def test_cli_warehouse_flag(tmp_path):
    ok(run_cli(tmp_path, "add-item", "BBB-1", "Thing", "--qty", "6"))
    ok(run_cli(tmp_path, "receive", "BBB-1", "4", "--warehouse", "east"))
    ok(run_cli(tmp_path, "ship", "BBB-1", "1", "--warehouse", "east"))
    store = load_store(tmp_path)
    item = store.get_item("BBB-1")
    assert item.qty_in("main") == 6
    assert item.qty_in("east") == 3
    assert item.qty == 9


def test_state_file_version_is_at_least_3(tmp_path):
    ok(run_cli(tmp_path, "add-item", "BBB-1", "Thing", "--qty", "6"))
    data = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    assert isinstance(data.get("version"), int)
    assert data["version"] >= 3


def test_per_warehouse_split_survives_save_and_reload(tmp_path):
    from stockroom.store import Store

    store = Store(str(tmp_path / "state.json"))
    store.add_item("CCC-1", "Thing", qty=2)
    store.receive("CCC-1", 3, warehouse="east")
    store.save()
    again = load_store(tmp_path)
    item = again.get_item("CCC-1")
    assert item.qty_in("main") == 2
    assert item.qty_in("east") == 3
    assert item.qty == 5


def test_v1_fixture_loads_into_main(tmp_path):
    shutil.copy(FIXTURES / "state_v1.json", tmp_path / "state.json")
    store = load_store(tmp_path)
    item = store.get_item("WID-1")
    assert item.qty == 3
    assert item.qty_in("main") == 3
    assert item.qty_in("east") == 0
    assert store.get_item("SCR-2").qty == 0


def test_v2_fixture_loads_into_main(tmp_path):
    shutil.copy(FIXTURES / "state_v2.json", tmp_path / "state.json")
    store = load_store(tmp_path)
    assert store.get_item("WID-1").qty == 4
    assert store.get_item("WID-1").qty_in("main") == 4
    assert store.get_item("SCR-1").qty_in("main") == 2


def test_v3_fixture_loads_per_warehouse(tmp_path):
    shutil.copy(FIXTURES / "state_v3.json", tmp_path / "state.json")
    store = load_store(tmp_path)
    wid = store.get_item("WID-1")
    assert wid.qty == 5
    assert wid.qty_in("main") == 3
    assert wid.qty_in("east") == 2
    scr = store.get_item("SCR-1")
    assert scr.qty == 4
    assert scr.qty_in("main") == 0
    assert scr.qty_in("east") == 4
    assert store.get_item("GAD-1").qty == 7
    ok(run_cli(tmp_path, "receive", "WID-1", "1", "--warehouse", "east"))
    again = load_store(tmp_path)
    assert again.get_item("WID-1").qty_in("east") == 3
    assert again.get_item("WID-1").qty == 6


def test_reports_keep_total_shape(tmp_path):
    from stockroom import reports

    ok(run_cli(tmp_path, "add-item", "DDD-1", "Thing", "--qty", "2",
               "--price", "2.5"))
    ok(run_cli(tmp_path, "receive", "DDD-1", "3", "--warehouse", "east"))
    store = load_store(tmp_path)
    report = reports.stock_report(store)
    rows = [row for row in report["rows"] if row["sku"] == "DDD-1"]
    assert len(rows) == 1
    assert rows[0]["qty"] == 5
    assert isinstance(rows[0]["qty"], int)
    assert round(rows[0]["value"], 2) == 12.5
    result = ok(run_cli(tmp_path, "report", "stock"))
    assert "DDD-1" in result.stdout
