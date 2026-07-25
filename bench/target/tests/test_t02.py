"""T02: monthly per-category summary."""

from ledgerlite import report
from ledgerlite.ledger import Entry, Ledger


def make_ledger():
    led = Ledger()
    led.add(Entry("2026-03-01", 10.00, category="food"))
    led.add(Entry("2026-03-15", 5.00, category="food"))
    led.add(Entry("2026-03-20", 20.00, category="transit"))
    led.add(Entry("2026-03-25", 3.00))  # uncategorized
    led.add(Entry("2026-04-01", 99.00, category="food"))
    return led


def test_monthly_summary_per_category():
    summary = report.monthly_summary(make_ledger(), 2026, 3)
    assert abs(summary["food"] - 15.00) < 1e-9
    assert abs(summary["transit"] - 20.00) < 1e-9
    assert abs(summary["uncategorized"] - 3.00) < 1e-9


def test_monthly_summary_excludes_other_months():
    summary = report.monthly_summary(make_ledger(), 2026, 3)
    assert abs(sum(summary.values()) - 38.00) < 1e-9
    april = report.monthly_summary(make_ledger(), 2026, 4)
    assert set(april) == {"food"}
    assert abs(april["food"] - 99.00) < 1e-9


def test_monthly_summary_empty_month():
    assert report.monthly_summary(make_ledger(), 2026, 7) == {}


def test_monthly_summary_consistent_with_month_total():
    led = make_ledger()
    summary = report.monthly_summary(led, 2026, 3)
    assert abs(sum(summary.values()) - report.month_total(led, 2026, 3)) < 1e-9
