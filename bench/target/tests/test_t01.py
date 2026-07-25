"""T01: category support."""

import json

from ledgerlite import cli, storage
from ledgerlite.ledger import Entry, Ledger


def test_entry_category_default():
    e = Entry("2026-03-05", 9.99)
    assert e.category == "uncategorized"


def test_entry_category_explicit():
    e = Entry("2026-03-05", 9.99, note="latte", category="food")
    assert e.category == "food"
    assert e.note == "latte"


def test_totals_by_category():
    led = Ledger()
    led.add(Entry("2026-03-01", 10.00, category="food"))
    led.add(Entry("2026-03-02", 5.00, category="food"))
    led.add(Entry("2026-03-03", 20.00, category="transit"))
    led.add(Entry("2026-03-04", 3.00))
    totals = led.totals_by_category()
    assert abs(totals["food"] - 15.00) < 1e-9
    assert abs(totals["transit"] - 20.00) < 1e-9
    assert abs(totals["uncategorized"] - 3.00) < 1e-9


def test_storage_roundtrips_category(tmp_path):
    led = Ledger()
    led.add(Entry("2026-03-01", 10.00, note="lunch", category="food"))
    path = str(tmp_path / "ledger.json")
    storage.save(led, path)
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    assert raw["entries"][0]["category"] == "food"
    loaded = storage.load(path)
    assert loaded.entries()[0].category == "food"


def test_cli_category_flag(tmp_path, capsys):
    path = str(tmp_path / "ledger.json")
    assert cli.main(["--file", path, "add", "--date", "2026-03-05",
                     "--amount", "12.50", "--category", "food",
                     "--note", "coffee"]) == 0
    capsys.readouterr()
    assert cli.main(["--file", path, "list"]) == 0
    out = capsys.readouterr().out
    assert "food" in out
