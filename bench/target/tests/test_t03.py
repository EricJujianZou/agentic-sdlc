"""T03: date normalization fix (non-zero-padded dates were silently dropped)."""

from ledgerlite import report, storage
from ledgerlite.ledger import Entry, Ledger


def test_entry_date_normalized_on_creation():
    e = Entry("2026-1-5", 10.00)
    assert e.date == "2026-01-05"


def test_padded_dates_unchanged():
    e = Entry("2026-11-30", 10.00)
    assert e.date == "2026-11-30"


def test_month_total_includes_unpadded_dates():
    led = Ledger()
    led.add(Entry("2026-1-5", 10.00))
    led.add(Entry("2026-01-20", 5.00))
    led.add(Entry("2026-02-01", 99.00))
    assert abs(report.month_total(led, 2026, 1) - 15.00) < 1e-9


def test_monthly_summary_includes_unpadded_dates():
    led = Ledger()
    led.add(Entry("2026-1-5", 10.00, category="food"))
    led.add(Entry("2026-01-20", 5.00, category="food"))
    summary = report.monthly_summary(led, 2026, 1)
    assert abs(summary["food"] - 15.00) < 1e-9


def test_entries_sorted_correctly_with_mixed_padding():
    led = Ledger()
    led.add(Entry("2026-10-01", 1.00))
    led.add(Entry("2026-2-1", 2.00))
    led.add(Entry("2026-09-15", 3.00))
    assert [e.date for e in led.entries()] == ["2026-02-01", "2026-09-15", "2026-10-01"]


def test_storage_roundtrip_normalizes(tmp_path):
    led = Ledger()
    led.add(Entry("2026-1-5", 10.00))
    path = str(tmp_path / "ledger.json")
    storage.save(led, path)
    loaded = storage.load(path)
    assert loaded.entries()[0].date == "2026-01-05"
