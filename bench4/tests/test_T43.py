"""Locked tests for T43 - report cache keyed by a store revision counter."""
import pathlib

import pytest

from stockroom.store import Store


def cached():
    from stockroom.cache import cached_report
    return cached_report


def make_store(tmp_path):
    store = Store(str(tmp_path / "state.json"))
    store.add_supplier("ACME", "Acme Supply", "orders@acme.example")
    store.add_item("WID-1", "Widget", qty=10, unit_price=2.0, supplier_id="ACME")
    store.add_item("GAD-1", "Gadget", qty=3, unit_price=1.0, supplier_id="ACME")
    return store


def test_cache_hit_returns_same_object(tmp_path):
    cr = cached()
    store = make_store(tmp_path)
    first = cr(store, "stock")
    second = cr(store, "stock")
    assert second is first


def test_arguments_are_cached_separately(tmp_path):
    cr = cached()
    store = make_store(tmp_path)
    low3 = cr(store, "low", threshold=3)
    low7 = cr(store, "low", threshold=7)
    assert low3 is not low7
    assert cr(store, "low", threshold=3) is low3
    monthly = cr(store, "monthly", month="2026-01")
    assert cr(store, "monthly", month="2026-01") is monthly
    history = cr(store, "history", sku="WID-1")
    assert cr(store, "history", sku="WID-1") is history


def test_revision_counts_mutations_not_reads(tmp_path):
    cr = cached()
    store = make_store(tmp_path)
    rev0 = store.revision
    assert isinstance(rev0, int)
    cr(store, "stock")
    cr(store, "low", threshold=3)
    cr(store, "history", sku="WID-1")
    assert store.revision == rev0
    store.receive("WID-1", 1)
    assert store.revision > rev0


def test_every_mutation_type_invalidates(tmp_path):
    cr = cached()
    store = make_store(tmp_path)
    placed = []

    def check(mutate):
        before = cr(store, "stock")
        rev = store.revision
        mutate()
        assert store.revision > rev
        after = cr(store, "stock")
        assert after is not before

    check(lambda: store.receive("WID-1", 2))
    check(lambda: store.ship("WID-1", 1))
    check(lambda: store.add_item("NEW-1", "New thing"))
    check(lambda: store.add_supplier("GLOB", "Globex", "purchasing@globex.example"))
    check(lambda: placed.append(store.place_order("WID-1", 2, "2026-01-05")))
    check(lambda: store.receive_order(placed[0].id))
    check(lambda: placed.append(store.place_order("WID-1", 1, "2026-01-06")))
    check(lambda: store.cancel_order(placed[1].id))


def test_invalidated_result_is_fresh_content(tmp_path):
    cr = cached()
    store = make_store(tmp_path)
    before = cr(store, "stock")
    by_sku = {row["sku"]: row for row in before["rows"]}
    qty_before = by_sku["WID-1"]["qty"]
    store.receive("WID-1", 5)
    after = cr(store, "stock")
    by_sku = {row["sku"]: row for row in after["rows"]}
    assert by_sku["WID-1"]["qty"] == qty_before + 5
