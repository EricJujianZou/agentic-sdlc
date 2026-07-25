"""Persist a ledger to a JSON file."""

import csv
import json
import os

from .ledger import Entry, Ledger


def _to_dict(ledger: Ledger) -> dict:
    return {
        "entries": [
            {"date": e.date, "amount": e.amount, "amount_cents": e.amount_cents,
             "note": e.note, "category": e.category}
            for e in ledger.entries()
        ],
        "budgets": dict(ledger.budgets),
    }


def _from_dict(data: dict) -> Ledger:
    ledger = Ledger()
    for row in data.get("entries", []):
        if "amount_cents" in row:
            entry = Entry.from_cents(row["date"], int(row["amount_cents"]),
                                     row.get("category", "uncategorized"),
                                     row.get("note", ""))
        else:
            entry = Entry(row["date"], row["amount"], row.get("note", ""),
                          row.get("category", "uncategorized"))
        ledger.add(entry)
    for category, limit in data.get("budgets", {}).items():
        ledger.set_budget(category, limit)
    return ledger


def save(ledger: Ledger, path: str, name: str | None = None) -> None:
    if name is None:
        data = _to_dict(ledger)
    else:
        data = {"ledgers": {}}
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                existing = json.load(f)
            if "ledgers" in existing:
                data["ledgers"] = existing["ledgers"]
            elif "entries" in existing:
                data["ledgers"]["default"] = existing
        data["ledgers"][name] = _to_dict(ledger)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load(path: str, name: str | None = None) -> Ledger:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if name is None:
        if "entries" not in data and "ledgers" in data:
            return _from_dict(data["ledgers"].get("default", {}))
        return _from_dict(data)
    if "ledgers" in data:
        return _from_dict(data["ledgers"][name])
    if name == "default":
        return _from_dict(data)
    raise KeyError(name)


def export_csv(ledger: Ledger, path: str) -> None:
    """Write the ledger's entries to *path* as CSV."""
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "amount", "category", "note"])
        for e in ledger.entries():
            writer.writerow([e.date, f"{e.amount:.2f}", e.category, e.note])
