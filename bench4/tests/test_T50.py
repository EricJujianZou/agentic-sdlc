"""Locked tests for T50 - the stockroom.api facade.

These tests import ONLY stockroom.api and exercise one behavior per major
capability the library has accumulated.
"""
import pytest


def _api():
    from stockroom import api
    return api


def fresh(api, tmp_path, name):
    d = tmp_path / name
    d.mkdir()
    return api.open_store(str(d))


def test_catalogue_and_stock(tmp_path):
    api = _api()
    s = fresh(api, tmp_path, "A")
    api.add_supplier(s, "ACME", "Acme Supply", "orders@acme.example",
                     lead_time_days=7)
    api.add_item(s, "WID-1", "Widget", qty=0, price=2.5, supplier="ACME",
                 category="tools")
    api.receive(s, "WID-1", 5)
    api.ship(s, "WID-1", 2)
    assert s.items["WID-1"].qty == 3
    with pytest.raises(ValueError):
        api.ship(s, "WID-1", 99)
    assert len(api.search_items(s, "wid")) == 1


def test_warehouses_and_transfer(tmp_path):
    api = _api()
    s = fresh(api, tmp_path, "A")
    api.add_item(s, "WID-1", "Widget", qty=0, price=1.0)
    api.receive(s, "WID-1", 5)
    api.receive(s, "WID-1", 3, warehouse="east")
    api.transfer(s, "WID-1", 2, "east", "main")
    assert s.items["WID-1"].qty == 8
    with pytest.raises(ValueError):
        api.transfer(s, "WID-1", 99, "east", "main")


def test_orders_dates_and_history(tmp_path):
    api = _api()
    s = fresh(api, tmp_path, "A")
    api.add_supplier(s, "ACME", "Acme Supply", "orders@acme.example")
    api.add_item(s, "WID-1", "Widget", qty=0, price=1.0, supplier="ACME")
    o1 = api.place_order(s, "WID-1", 2, "2026-1-5")  # legacy unpadded date
    assert len(api.monthly_orders(s, "2026-01")) == 1
    api.receive_order(s, o1.id)
    assert s.items["WID-1"].qty == 2
    with pytest.raises(ValueError):
        api.receive_order(s, o1.id)  # already received
    api.place_order(s, "WID-1", 1, "2025-03-10")
    history = api.order_history(s, "WID-1")
    assert str(history[0]["date"]).startswith("2025")  # chronological


def test_money_valuation_discounts_totals(tmp_path):
    api = _api()
    assert api.format_money(3.5) == "$3.50"
    s = fresh(api, tmp_path, "A")
    api.add_item(s, "P-1", "Pin small", qty=10, price=0.1)
    api.add_item(s, "P-2", "Pin large", qty=10, price=0.2)
    report = api.stock_report(s)
    assert api.format_money(report["total_value"]) == "$3.00"
    api.add_supplier(s, "ACME", "Acme Supply", "orders@acme.example")
    api.add_item(s, "T-9", "Torque wrench", qty=0, price=2.0,
                 supplier="ACME", category="tools")
    api.set_discount(s, "tools", 10)
    order = api.place_order(s, "T-9", 10, "2026-04-01")
    assert round(api.order_total(s, order.id), 2) == 18.0


def test_events_cache_undo_redo(tmp_path):
    api = _api()
    s = fresh(api, tmp_path, "A")
    api.add_item(s, "WID-1", "Widget", qty=0, price=1.0)
    n0 = len(api.events(s))
    api.receive(s, "WID-1", 4)
    assert len(api.events(s)) > n0
    first = api.cached_report(s, "stock")
    assert api.cached_report(s, "stock") is first
    api.receive(s, "WID-1", 1)
    assert api.cached_report(s, "stock") is not first
    api.undo(s)
    assert s.items["WID-1"].qty == 4
    api.redo(s)
    assert s.items["WID-1"].qty == 5


def test_persistence_read_only_fsck_archive(tmp_path):
    api = _api()
    s = fresh(api, tmp_path, "A")
    api.add_supplier(s, "ACME", "Acme Supply", "orders@acme.example")
    api.add_item(s, "WID-1", "Widget", qty=5, price=2.5, supplier="ACME",
                 category="tools")
    order = api.place_order(s, "WID-1", 4, "2026-01-05")
    api.receive_order(s, order.id)

    s2 = api.open_store(str(tmp_path / "A"))
    assert s2.items["WID-1"].qty == 9  # mutations were persisted

    api.set_read_only(s2, True)
    with pytest.raises(ValueError):
        api.receive(s2, "WID-1", 1)
    api.set_read_only(s2, False)

    assert api.fsck(s2) == []

    archive = str(tmp_path / "arch.json")
    api.export_archive(s2, archive)
    b = tmp_path / "B"
    b.mkdir()
    s3 = api.import_archive(archive, str(b))
    assert (api.format_money(api.stock_report(s3)["total_value"])
            == api.format_money(api.stock_report(s2)["total_value"]))


def test_csv_reorder_and_boundary(tmp_path):
    api = _api()
    s = fresh(api, tmp_path, "A")
    incoming = tmp_path / "in.csv"
    incoming.write_text(
        "sku,name,qty,unit_price,supplier_id\nzz9,Thing,5,3.5,\n",
        encoding="utf-8",
    )
    api.import_items_csv(s, str(incoming))
    found = api.search_items(s, "zz9")  # case-insensitive identity
    assert len(found) == 1
    assert found[0].qty == 5
    out = tmp_path / "out.csv"
    api.export_items_csv(s, str(out))
    text = out.read_text(encoding="utf-8")
    assert "category" in text.splitlines()[0]
    assert "uncategorized" in text

    api.add_supplier(s, "ACME", "Acme Supply", "orders@acme.example")
    api.add_item(s, "R-1", "Rod", qty=2, price=1.0, supplier="ACME")
    api.place_order(s, "R-1", 2, "2026-05-01")  # pending
    suggestions = {row["sku"]: row
                   for row in api.reorder_suggestions(s, threshold=5)}
    assert suggestions["R-1"]["suggested_qty"] == 1  # 5 - 2 on hand - 2 pending

    api.add_item(s, "B-1", "Bracket", qty=5, price=1.0, supplier="ACME")
    low_skus = {row["sku"] for row in api.low_stock(s, threshold=5)}
    reorder_skus = {row["sku"]
                    for row in api.reorder_suggestions(s, threshold=5)}
    assert "B-1" in low_skus
    assert "B-1" in reorder_skus  # boundary handled consistently
