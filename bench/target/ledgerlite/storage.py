"""Persist a ledger to a JSON file."""

import json

from .ledger import Entry, Ledger


def save(ledger: Ledger, path: str) -> None:
    data = {
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
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load(path: str) -> Ledger:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
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
