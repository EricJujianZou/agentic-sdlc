"""T07: recurring entries."""

from ledgerlite.ledger import Entry, Ledger


def test_add_recurring_count():
    led = Ledger()
    led.add_recurring(Entry("2026-03-05", 9.99, note="netflix", category="fun"), 3)
    assert len(led) == 3


def test_add_recurring_monthly_dates():
    led = Ledger()
    led.add_recurring(Entry("2026-03-05", 9.99), 3)
    assert [e.date for e in led.entries()] == ["2026-03-05", "2026-04-05", "2026-05-05"]


def test_add_recurring_year_rollover():
    led = Ledger()
    led.add_recurring(Entry("2026-11-15", 5.00), 3)
    assert [e.date for e in led.entries()] == ["2026-11-15", "2026-12-15", "2027-01-15"]


def test_add_recurring_clamps_short_months():
    led = Ledger()
    led.add_recurring(Entry("2026-01-31", 5.00), 3)
    # 2026 is not a leap year: Feb has 28 days.
    assert [e.date for e in led.entries()] == ["2026-01-31", "2026-02-28", "2026-03-31"]


def test_add_recurring_copies_fields():
    led = Ledger()
    led.add_recurring(Entry("2026-03-05", 9.99, note="netflix", category="fun"), 2)
    for e in led.entries():
        assert e.amount == 9.99
        assert e.note == "netflix"
        assert e.category == "fun"
