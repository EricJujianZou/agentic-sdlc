"""Persist a ledger to a JSON file."""

import csv
import json
import os

from .ledger import Entry, Ledger


def _to_dict(ledger: Ledger) -> dict:
    return {
        "entries": [
            {
                "date": e.date,
                "amount": e.amount,
                "note": e.note,
                "category": e.category,
            }
            for e in ledger.entries()
        ],
        "budgets": dict(ledger.budgets),
    }


def _from_dict(data: dict) -> Ledger:
    ledger = Ledger()
    for category, limit in data.get("budgets", {}).items():
        ledger.set_budget(category, limit)
    for row in data["entries"]:
        ledger.add(
            Entry(
                row["date"],
                row["amount"],
                row.get("note", ""),
                category=row.get("category", "uncategorized"),
            )
        )
    return ledger


def _read_json(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _write_json(data: dict, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def save(ledger: Ledger, path: str, name: str | None = None) -> None:
    """Save *ledger* to *path*; with *name*, into a multi-ledger file."""
    if name is None:
        _write_json(_to_dict(ledger), path)
        return

    data: dict = {}
    if os.path.exists(path):
        existing = _read_json(path)
        if "ledgers" in existing:
            data = existing
    data.setdefault("ledgers", {})[name] = _to_dict(ledger)
    _write_json(data, path)


def export_csv(ledger: Ledger, path: str) -> None:
    """Write the ledger's entries to *path* as CSV, sorted by date."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "amount", "category", "note"])
        for e in ledger.entries():
            writer.writerow([e.date, f"{e.amount:.2f}", e.category, e.note])


def load(path: str, name: str | None = None) -> Ledger:
    """Load a ledger from *path*; with *name*, from a multi-ledger file."""
    data = _read_json(path)
    if name is None:
        return _from_dict(data)
    if "ledgers" in data:
        return _from_dict(data["ledgers"][name])
    if name == "default":
        return _from_dict(data)
    raise KeyError(name)
