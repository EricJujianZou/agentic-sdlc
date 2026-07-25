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
                "amount_cents": e.amount_cents,
                "category": e.category,
                "note": e.note,
            }
            for e in ledger.entries()
        ],
        "budgets": dict(ledger.budgets),
    }


def _from_dict(data: dict) -> Ledger:
    ledger = Ledger()
    for row in data.get("entries", []):
        if "amount_cents" in row:
            entry = Entry.from_cents(
                row["date"], int(row["amount_cents"]),
                category=row.get("category", "uncategorized"),
                note=row.get("note", ""),
            )
        else:
            entry = Entry(
                row["date"], row["amount"], note=row.get("note", ""),
                category=row.get("category", "uncategorized"),
            )
        ledger.add(entry)
    for category, limit in (data.get("budgets") or {}).items():
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
            if isinstance(existing.get("ledgers"), dict):
                data["ledgers"] = existing["ledgers"]
        data["ledgers"][name] = _to_dict(ledger)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load(path: str, name: str | None = None) -> Ledger:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if name is None:
        return _from_dict(data)
    ledgers = data.get("ledgers")
    if isinstance(ledgers, dict):
        return _from_dict(ledgers.get(name) or {})
    # Legacy-format file: "default" bridges to the single ledger it holds.
    if name == "default":
        return _from_dict(data)
    return Ledger()


def export_csv(ledger: Ledger, path: str) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "amount", "category", "note"])
        for e in ledger.entries():
            writer.writerow([e.date, f"{e.amount_cents / 100:.2f}", e.category, e.note])
