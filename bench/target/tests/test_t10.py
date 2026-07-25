"""T10: undo of mutating operations."""

from ledgerlite.ledger import Entry, Ledger


def test_undo_add():
    led = Ledger()
    led.add(Entry("2026-03-01", 10.00))
    led.add(Entry("2026-03-02", 5.00))
    assert led.undo() == 1
    assert len(led) == 1
    assert led.entries()[0].date == "2026-03-01"


def test_undo_remove_restores_entry():
    led = Ledger()
    led.add(Entry("2026-03-01", 10.00, note="keepme"))
    led.remove(0)
    assert len(led) == 0
    assert led.undo() == 1
    assert len(led) == 1
    assert led.entries()[0].note == "keepme"


def test_undo_multiple():
    led = Ledger()
    led.add(Entry("2026-03-01", 10.00))
    led.add(Entry("2026-03-02", 5.00))
    led.add(Entry("2026-03-03", 1.00))
    assert led.undo(2) == 2
    assert len(led) == 1


def test_undo_more_than_history():
    led = Ledger()
    led.add(Entry("2026-03-01", 10.00))
    assert led.undo(5) == 1
    assert len(led) == 0
    assert led.undo() == 0


def test_undo_add_recurring_is_one_operation():
    led = Ledger()
    led.add(Entry("2026-01-01", 1.00))
    led.add_recurring(Entry("2026-03-05", 9.99), 3)
    assert len(led) == 4
    assert led.undo() == 1
    assert len(led) == 1
    assert led.entries()[0].date == "2026-01-01"


def test_undo_set_budget():
    led = Ledger()
    led.set_budget("food", 20.00)
    led.set_budget("food", 50.00)
    assert led.undo() == 1
    assert abs(led.budgets["food"] - 20.00) < 1e-9
    assert led.undo() == 1
    assert "food" not in led.budgets
