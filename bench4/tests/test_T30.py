"""Locked tests for T30 - CSV money round-trip and tolerant price parsing."""

import csv
import pathlib
import re
import subprocess
import sys
from decimal import Decimal

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

TWO_DECIMALS = re.compile(r"^\d+\.\d{2}$")


def run_cli(data_dir, *args):
    return subprocess.run(
        [sys.executable, "-m", "stockroom.cli", "--data", str(data_dir), *args],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )


def _seed(tmp, rows):
    for sku, name, qty, price in rows:
        r = run_cli(tmp, "add-item", sku, name, "--qty", qty, "--price", price)
        assert r.returncode == 0, r.stderr


def _load(tmp):
    from stockroom.store import Store
    store = Store(str(tmp / "state.json"))
    store.load()
    return store


def test_export_prices_have_two_decimals(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    _seed(data, [("AAA-1", "Alpha", "10", "0.1"),
                 ("BBB-1", "Beta", "1", "0.2"),
                 ("CCC-1", "Gamma", "3", "19.99"),
                 ("DDD-1", "Delta", "2", "3.5")])
    out_csv = tmp_path / "items.csv"
    r = run_cli(data, "export-csv", str(out_csv))
    assert r.returncode == 0, r.stderr
    with open(out_csv, newline="", encoding="utf-8") as f:
        cells = {row["sku"]: row["unit_price"] for row in csv.DictReader(f)}
    assert cells["AAA-1"] == "0.10"
    assert cells["BBB-1"] == "0.20"
    assert cells["CCC-1"] == "19.99"
    assert cells["DDD-1"] == "3.50"
    for cell in cells.values():
        assert TWO_DECIMALS.match(cell), cell


def test_import_accepts_money_variants(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    src = tmp_path / "in.csv"
    src.write_text(
        "sku,name,qty,unit_price,supplier_id\n"
        "AAA-1,Alpha,2,3.5,\n"
        "BBB-1,Beta,3,$3.50,\n"
        "CCC-1,Gamma,4, 19.99 ,\n",
        encoding="utf-8",
    )
    r = run_cli(data, "import-csv", str(src))
    assert r.returncode == 0, r.stderr
    store = _load(data)
    assert round(store.get_item("AAA-1").unit_price, 2) == 3.5
    assert round(store.get_item("BBB-1").unit_price, 2) == 3.5
    assert round(store.get_item("CCC-1").unit_price, 2) == 19.99
    assert store.get_item("BBB-1").qty == 3


def test_import_category_layout_with_dollar_price(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    src = tmp_path / "in.csv"
    src.write_text(
        "sku,name,qty,unit_price,supplier_id,category\n"
        "EEE-1,Epsilon,2,$2.25,,parts\n",
        encoding="utf-8",
    )
    r = run_cli(data, "import-csv", str(src))
    assert r.returncode == 0, r.stderr
    item = _load(data).get_item("EEE-1")
    assert round(item.unit_price, 2) == 2.25
    assert item.category == "parts"


def test_import_warehouse_layout_with_dollar_price(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    src = tmp_path / "in.csv"
    src.write_text(
        "sku,name,qty,unit_price,supplier_id,category,warehouse\n"
        "FFF-1,Zeta,2,$1.10,,parts,main\n",
        encoding="utf-8",
    )
    r = run_cli(data, "import-csv", str(src))
    assert r.returncode == 0, r.stderr
    item = _load(data).get_item("FFF-1")
    assert round(item.unit_price, 2) == 1.1
    assert item.qty == 2


def test_roundtrip_reproduces_valuation_exactly(tmp_path):
    from stockroom import reports
    src_dir = tmp_path / "src"
    dst_dir = tmp_path / "dst"
    src_dir.mkdir()
    dst_dir.mkdir()
    _seed(src_dir, [("AAA-1", "Alpha", "1", "0.1"),
                    ("BBB-1", "Beta", "1", "0.2"),
                    ("CCC-1", "Gamma", "3", "19.99")])
    out_csv = tmp_path / "items.csv"
    r = run_cli(src_dir, "export-csv", str(out_csv))
    assert r.returncode == 0, r.stderr
    r = run_cli(dst_dir, "import-csv", str(out_csv))
    assert r.returncode == 0, r.stderr

    src_store = _load(src_dir)
    dst_store = _load(dst_dir)
    for sku in ("AAA-1", "BBB-1", "CCC-1"):
        assert dst_store.get_item(sku).qty == src_store.get_item(sku).qty
    src_total = reports.stock_report(src_store)["total_value"]
    dst_total = reports.stock_report(dst_store)["total_value"]
    assert Decimal(str(src_total)) == Decimal("60.27")
    assert Decimal(str(dst_total)) == Decimal("60.27")


def test_non_money_price_is_user_error(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    src = tmp_path / "in.csv"
    src.write_text(
        "sku,name,qty,unit_price,supplier_id\n"
        "GGG-1,Eta,2,abc,\n",
        encoding="utf-8",
    )
    r = run_cli(data, "import-csv", str(src))
    assert r.returncode == 1
