"""T05: CSV export."""

import csv

from ledgerlite import storage
from ledgerlite.ledger import Entry, Ledger


def make_ledger():
    led = Ledger()
    led.add(Entry("2026-03-05", 12.50, note="coffee", category="food"))
    led.add(Entry("2026-03-01", 40.00, note="groceries", category="food"))
    led.add(Entry("2026-04-02", 7.25, note="bus", category="transit"))
    return led


def export(tmp_path):
    path = str(tmp_path / "out.csv")
    storage.export_csv(make_ledger(), path)
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.reader(f))


def test_header_row(tmp_path):
    rows = export(tmp_path)
    assert rows[0] == ["date", "amount", "category", "note"]


def test_rows_sorted_by_date(tmp_path):
    rows = export(tmp_path)
    assert [r[0] for r in rows[1:]] == ["2026-03-01", "2026-03-05", "2026-04-02"]


def test_amount_two_decimal_places(tmp_path):
    rows = export(tmp_path)
    assert rows[1][1] == "40.00"
    assert rows[3][1] == "7.25"


def test_category_and_note_columns(tmp_path):
    rows = export(tmp_path)
    assert rows[1][2] == "food"
    assert rows[1][3] == "groceries"
    assert rows[3][2] == "transit"


def test_empty_ledger_only_header(tmp_path):
    path = str(tmp_path / "empty.csv")
    storage.export_csv(Ledger(), path)
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    assert rows == [["date", "amount", "category", "note"]]
