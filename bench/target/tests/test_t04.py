"""T04: per-category budgets and over-budget warnings."""

from ledgerlite import report, storage
from ledgerlite.ledger import Entry, Ledger


def make_ledger():
    led = Ledger()
    led.set_budget("food", 20.00)
    led.set_budget("transit", 100.00)
    led.add(Entry("2026-03-01", 15.00, category="food"))
    led.add(Entry("2026-03-10", 10.00, category="food"))   # food total 25 > 20
    led.add(Entry("2026-03-12", 30.00, category="transit"))  # under budget
    led.add(Entry("2026-04-01", 5.00, category="food"))      # other month
    return led


def test_set_budget_and_budgets_mapping():
    led = make_ledger()
    assert abs(led.budgets["food"] - 20.00) < 1e-9
    assert abs(led.budgets["transit"] - 100.00) < 1e-9


def test_budget_warnings_over_budget():
    warnings = report.budget_warnings(make_ledger(), 2026, 3)
    assert set(warnings) == {"food"}
    assert abs(warnings["food"] - 5.00) < 1e-9  # overage amount


def test_budget_warnings_respect_month():
    assert report.budget_warnings(make_ledger(), 2026, 4) == {}


def test_no_budget_no_warning():
    led = make_ledger()
    led.add(Entry("2026-03-15", 999.00, category="misc"))
    warnings = report.budget_warnings(led, 2026, 3)
    assert "misc" not in warnings


def test_budgets_persist_via_storage(tmp_path):
    led = make_ledger()
    path = str(tmp_path / "ledger.json")
    storage.save(led, path)
    loaded = storage.load(path)
    assert abs(loaded.budgets["food"] - 20.00) < 1e-9
    warnings = report.budget_warnings(loaded, 2026, 3)
    assert set(warnings) == {"food"}
