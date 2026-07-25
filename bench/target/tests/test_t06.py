"""T06: multi-ledger files with backward compatibility."""

import json

from ledgerlite import cli, storage
from ledgerlite.ledger import Entry, Ledger


def test_legacy_roundtrip_still_works(tmp_path):
    led = Ledger()
    led.add(Entry("2026-03-01", 10.00, category="food"))
    path = str(tmp_path / "ledger.json")
    storage.save(led, path)
    loaded = storage.load(path)
    assert len(loaded) == 1
    assert loaded.entries()[0].category == "food"


def test_named_save_creates_multi_format(tmp_path):
    led = Ledger()
    led.add(Entry("2026-03-01", 10.00))
    path = str(tmp_path / "ledgers.json")
    storage.save(led, path, name="personal")
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    assert "ledgers" in raw
    assert "personal" in raw["ledgers"]


def test_two_named_ledgers_coexist(tmp_path):
    path = str(tmp_path / "ledgers.json")
    a = Ledger()
    a.add(Entry("2026-03-01", 10.00))
    storage.save(a, path, name="personal")
    b = Ledger()
    b.add(Entry("2026-03-02", 99.00))
    b.add(Entry("2026-03-03", 1.00))
    storage.save(b, path, name="work")

    loaded_a = storage.load(path, name="personal")
    loaded_b = storage.load(path, name="work")
    assert len(loaded_a) == 1
    assert len(loaded_b) == 2
    assert abs(loaded_a.total() - 10.00) < 1e-9


def test_load_legacy_file_with_default_name(tmp_path):
    led = Ledger()
    led.add(Entry("2026-03-01", 10.00))
    path = str(tmp_path / "ledger.json")
    storage.save(led, path)  # legacy format
    loaded = storage.load(path, name="default")
    assert len(loaded) == 1


def test_cli_ledger_flag(tmp_path, capsys):
    path = str(tmp_path / "ledgers.json")
    assert cli.main(["--file", path, "--ledger", "personal", "add",
                     "--date", "2026-03-05", "--amount", "12.50"]) == 0
    assert cli.main(["--file", path, "--ledger", "work", "add",
                     "--date", "2026-03-06", "--amount", "1.00"]) == 0
    capsys.readouterr()
    assert cli.main(["--file", path, "--ledger", "personal", "total"]) == 0
    assert "12.50" in capsys.readouterr().out
