"""Core ledger data model."""

import calendar
from dataclasses import dataclass, replace


def normalize_date(date: str) -> str:
    """Return *date* in zero-padded ISO form ``YYYY-MM-DD``."""
    parts = date.split("-")
    if len(parts) != 3:
        return date
    year, month, day = parts
    return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"


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

    def add(self, entry: Entry) -> None:
        self._entries.append(entry)

    def add_recurring(self, entry: Entry, months: int) -> None:
        """Add *months* copies of *entry*, one per following calendar month."""
        year, month, day = (int(part) for part in entry.date.split("-"))
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

    def set_budget(self, category: str, limit: float) -> None:
        self.budgets[category] = limit

    def totals_by_category(self) -> dict[str, float]:
        totals: dict[str, float] = {}
        for e in self._entries:
            totals[e.category] = totals.get(e.category, 0.0) + e.amount
        return totals

    def total(self) -> float:
        return sum(e.amount for e in self._entries)

    def __len__(self) -> int:
        return len(self._entries)
