"""Core ledger data model."""

import calendar
from dataclasses import dataclass, replace


def normalize_date(date: str) -> str:
    """Return *date* as zero-padded ISO ``YYYY-MM-DD``."""
    parts = date.split("-")
    if len(parts) != 3:
        return date
    try:
        year, month, day = (int(p) for p in parts)
    except ValueError:
        return date
    return f"{year:04d}-{month:02d}-{day:02d}"


@dataclass
class Entry:
    """A single expense entry.

    date is an ISO-style string like "2026-03-05".
    """

    date: str
    amount: float
    note: str = ""
    category: str = "uncategorized"

    def __post_init__(self) -> None:
        self.date = normalize_date(self.date)


class Ledger:
    """An in-memory collection of entries."""

    def __init__(self) -> None:
        self._entries: list[Entry] = []
        self.budgets: dict[str, float] = {}

    def set_budget(self, category: str, limit: float) -> None:
        """Record a monthly spending limit for *category*."""
        self.budgets[category] = limit

    def add(self, entry: Entry) -> None:
        self._entries.append(entry)

    def add_recurring(self, entry: Entry, months: int) -> None:
        """Add *entry* plus one copy per following month (day clamped)."""
        year, month, day = (int(p) for p in entry.date.split("-"))
        for offset in range(months):
            total = month - 1 + offset
            y = year + total // 12
            m = total % 12 + 1
            d = min(day, calendar.monthrange(y, m)[1])
            self.add(replace(entry, date=f"{y:04d}-{m:02d}-{d:02d}"))

    def remove(self, index: int) -> Entry:
        """Remove and return the entry at *index* (in entries() order)."""
        ordered = self.entries()
        entry = ordered[index]
        self._entries.remove(entry)
        return entry

    def entries(self) -> list[Entry]:
        """All entries, sorted by date."""
        return sorted(self._entries, key=lambda e: e.date)

    def total(self) -> float:
        return sum(e.amount for e in self._entries)

    def totals_by_category(self) -> dict[str, float]:
        """Sum of amounts per category."""
        totals: dict[str, float] = {}
        for e in self._entries:
            totals[e.category] = totals.get(e.category, 0.0) + e.amount
        return totals

    def __len__(self) -> int:
        return len(self._entries)
