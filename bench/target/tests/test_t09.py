"""T09: query/filter API."""

from ledgerlite.ledger import Entry, Ledger


def make_ledger():
    led = Ledger()
    led.add(Entry("2026-03-01", 10.00, note="Weekly Groceries", category="food"))
    led.add(Entry("2026-03-05", 12.50, note="coffee beans", category="food"))
    led.add(Entry("2026-03-10", 20.00, note="metro pass", category="transit"))
    led.add(Entry("2026-04-02", 7.25, note="bus fare", category="transit"))
    return led


def test_query_no_filters_returns_all():
    assert len(make_ledger().query()) == 4


def test_query_by_category():
    result = make_ledger().query(category="food")
    assert len(result) == 2
    assert all(e.category == "food" for e in result)


def test_query_date_range_inclusive():
    result = make_ledger().query(date_from="2026-03-05", date_to="2026-03-10")
    assert [e.date for e in result] == ["2026-03-05", "2026-03-10"]


def test_query_unpadded_date_bounds():
    # date bounds must be normalized like entry dates (T03).
    result = make_ledger().query(date_from="2026-3-5", date_to="2026-3-10")
    assert [e.date for e in result] == ["2026-03-05", "2026-03-10"]


def test_query_text_case_insensitive():
    result = make_ledger().query(text="groceries")
    assert len(result) == 1
    assert result[0].note == "Weekly Groceries"


def test_query_combined_filters():
    result = make_ledger().query(category="transit", date_from="2026-04-01")
    assert len(result) == 1
    assert result[0].date == "2026-04-02"
