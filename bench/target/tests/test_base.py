"""Baseline smoke tests. These must pass on the unmodified target app."""

from ledgerlite import cli, report, storage
from ledgerlite.ledger import Entry, Ledger


def make_ledger():
    led = Ledger()
    led.add(Entry("2026-03-05", 12.50, "coffee"))
    led.add(Entry("2026-03-01", 40.00, "groceries"))
    led.add(Entry("2026-04-02", 7.25, "bus"))
    return led


def test_entry_defaults():
    e = Entry("2026-03-05", 9.99)
    assert e.date == "2026-03-05"
    assert e.amount == 9.99
    assert e.note == ""


def test_add_and_len():
    led = make_ledger()
    assert len(led) == 3


def test_entries_sorted_by_date():
    led = make_ledger()
    assert [e.date for e in led.entries()] == ["2026-03-01", "2026-03-05", "2026-04-02"]


def test_remove_returns_entry():
    led = make_ledger()
    removed = led.remove(0)
    assert removed.date == "2026-03-01"
    assert len(led) == 2


def test_total():
    led = make_ledger()
    assert abs(led.total() - 59.75) < 1e-9


def test_storage_roundtrip(tmp_path):
    led = make_ledger()
    path = str(tmp_path / "ledger.json")
    storage.save(led, path)
    loaded = storage.load(path)
    assert len(loaded) == 3
    assert [e.date for e in loaded.entries()] == [e.date for e in led.entries()]
    assert abs(loaded.total() - led.total()) < 1e-9


def test_month_total():
    led = make_ledger()
    assert abs(report.month_total(led, 2026, 3) - 52.50) < 1e-9
    assert report.month_total(led, 2026, 5) == 0


def test_cli_add_list_total(tmp_path, capsys):
    path = str(tmp_path / "ledger.json")
    assert cli.main(["--file", path, "add", "--date", "2026-03-05",
                     "--amount", "12.50", "--note", "coffee"]) == 0
    assert cli.main(["--file", path, "add", "--date", "2026-03-01",
                     "--amount", "40.00"]) == 0
    capsys.readouterr()

    assert cli.main(["--file", path, "list"]) == 0
    out = capsys.readouterr().out
    lines = [line for line in out.splitlines() if line.strip()]
    assert len(lines) == 2
    assert lines[0].startswith("2026-03-01")

    assert cli.main(["--file", path, "total"]) == 0
    assert "52.50" in capsys.readouterr().out
