"""T08: exact money via integer cents."""

import json

from ledgerlite import storage
from ledgerlite.ledger import Entry, Ledger


def test_amount_cents_attribute():
    e = Entry("2026-03-05", 10.50)
    assert e.amount_cents == 1050
    assert isinstance(e.amount_cents, int)


def test_from_cents_constructor():
    e = Entry.from_cents("2026-03-05", 1234, category="food", note="x")
    assert e.amount_cents == 1234
    assert abs(e.amount - 12.34) < 1e-9
    assert e.category == "food"


def test_amount_still_float():
    e = Entry("2026-03-05", 12.34)
    assert isinstance(e.amount, float)
    assert abs(e.amount - 12.34) < 1e-9
    assert e.amount == e.amount_cents / 100


def test_total_is_exact():
    led = Ledger()
    led.add(Entry("2026-03-01", 0.10))
    led.add(Entry("2026-03-02", 0.20))
    # naive float summation gives 0.30000000000000004
    assert led.total() == 0.30
    assert led.total_cents() == 30


def test_totals_by_category_exact():
    led = Ledger()
    for _ in range(10):
        led.add(Entry("2026-03-01", 0.10, category="food"))
    assert led.totals_by_category()["food"] == 1.00


def test_storage_persists_cents(tmp_path):
    led = Ledger()
    led.add(Entry("2026-03-01", 0.10))
    path = str(tmp_path / "ledger.json")
    storage.save(led, path)
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    assert raw["entries"][0]["amount_cents"] == 10
    loaded = storage.load(path)
    assert loaded.entries()[0].amount_cents == 10
