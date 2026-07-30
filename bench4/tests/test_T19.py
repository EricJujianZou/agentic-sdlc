"""T19 — CSV v3 with a warehouse column; v1/v2 files still import."""

import csv
import pathlib
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
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


def _data_dir(tmp_path, name):
    d = tmp_path / name
    d.mkdir()
    return d


def test_export_writes_one_row_per_stocked_warehouse(tmp_path):
    data = _data_dir(tmp_path, "data")
    ok(run_cli(data, "add-item", "AAA-1", "Alpha", "--qty", "3", "--price",
               "2.5", "--category", "widgets"))
    ok(run_cli(data, "receive", "AAA-1", "2", "--warehouse", "east"))
    ok(run_cli(data, "add-item", "BBB-2", "Beta", "--qty", "0", "--price",
               "1.5", "--category", "gadgets"))
    out = tmp_path / "items.csv"
    ok(run_cli(data, "export-csv", str(out)))
    with open(out, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert rows and "warehouse" in rows[0]
    a_rows = {r["warehouse"]: int(r["qty"]) for r in rows
              if r["sku"] == "AAA-1"}
    assert a_rows == {"main": 3, "east": 2}
    for r in rows:
        if r["sku"] == "AAA-1":
            assert r["category"] == "widgets"
            assert round(float(r["unit_price"]), 2) == 2.5
    b_rows = [r for r in rows if r["sku"] == "BBB-2"]
    assert len(b_rows) == 1
    assert b_rows[0]["warehouse"] == "main"
    assert int(b_rows[0]["qty"]) == 0


def test_import_with_warehouse_column(tmp_path):
    data = _data_dir(tmp_path, "data")
    path = tmp_path / "v3.csv"
    path.write_text(
        "sku,name,qty,unit_price,supplier_id,category,warehouse\n"
        "CCC-3,Gamma,4,1.25,,parts,main\n"
        "CCC-3,Gamma,6,1.25,,parts,east\n",
        encoding="utf-8",
    )
    ok(run_cli(data, "import-csv", str(path)))
    item = load_store(data).get_item("CCC-3")
    assert item.qty_in("main") == 4
    assert item.qty_in("east") == 6
    assert item.qty == 10
    assert item.category == "parts"


def test_import_original_format_defaults(tmp_path):
    data = _data_dir(tmp_path, "data")
    path = tmp_path / "v1.csv"
    path.write_text(
        "sku,name,qty,unit_price,supplier_id\n"
        "DDD-4,Delta,7,1.25,\n",
        encoding="utf-8",
    )
    ok(run_cli(data, "import-csv", str(path)))
    item = load_store(data).get_item("DDD-4")
    assert item.qty == 7
    assert item.qty_in("main") == 7
    assert item.category == "uncategorized"


def test_import_category_format_without_warehouse(tmp_path):
    data = _data_dir(tmp_path, "data")
    path = tmp_path / "v2.csv"
    path.write_text(
        "sku,name,qty,unit_price,supplier_id,category\n"
        "EEE-5,Epsilon,2,0.75,,tools\n",
        encoding="utf-8",
    )
    ok(run_cli(data, "import-csv", str(path)))
    item = load_store(data).get_item("EEE-5")
    assert item.qty_in("main") == 2
    assert item.qty == 2
    assert item.category == "tools"


def test_import_is_header_driven_not_positional(tmp_path):
    data = _data_dir(tmp_path, "data")
    path = tmp_path / "shuffled.csv"
    path.write_text(
        "warehouse,category,unit_price,qty,name,sku\n"
        "east,parts,1.25,9,Gamma,FFF-6\n",
        encoding="utf-8",
    )
    ok(run_cli(data, "import-csv", str(path)))
    item = load_store(data).get_item("FFF-6")
    assert item.qty_in("east") == 9
    assert item.category == "parts"


def test_export_import_round_trip(tmp_path):
    src = _data_dir(tmp_path, "src")
    dst = _data_dir(tmp_path, "dst")
    ok(run_cli(src, "add-item", "AAA-1", "Alpha", "--qty", "3", "--price",
               "2.5", "--category", "widgets"))
    ok(run_cli(src, "receive", "AAA-1", "2", "--warehouse", "east"))
    ok(run_cli(src, "add-item", "BBB-2", "Beta", "--qty", "4", "--price",
               "1.5", "--category", "gadgets"))
    out = tmp_path / "roundtrip.csv"
    ok(run_cli(src, "export-csv", str(out)))
    ok(run_cli(dst, "import-csv", str(out)))
    store = load_store(dst)
    a = store.get_item("AAA-1")
    assert a.qty_in("main") == 3
    assert a.qty_in("east") == 2
    assert a.category == "widgets"
    b = store.get_item("BBB-2")
    assert b.qty_in("main") == 4
    assert b.category == "gadgets"
