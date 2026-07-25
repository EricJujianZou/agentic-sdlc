"""Core ledger data model."""

import calendar


def normalize_date(date: str) -> str:
    """Return *date* in zero-padded ISO form ``YYYY-MM-DD``."""
    parts = date.split("-")
    if len(parts) != 3:
        return date
    year, month, day = parts
    return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"


class Entry:
    """A single expense entry. Money is stored as integer cents.

    date is an ISO-style string like "2026-03-05".
    """

    def __init__(
        self,
        date: str,
        amount: float,
        note: str = "",
        category: str = "uncategorized",
    ) -> None:
        self.date = normalize_date(date)
        self.amount_cents = round(amount * 100)
        self.note = note
        self.category = category

    @classmethod
    def from_cents(
        cls,
        date: str,
        cents: int,
        category: str = "uncategorized",
        note: str = "",
    ) -> "Entry":
        entry = cls(date, 0.0, note, category)
        entry.amount_cents = int(cents)
        return entry

    @property
    def amount(self) -> float:
        return self.amount_cents / 100

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Entry):
            return NotImplemented
        return (
            self.date,
            self.amount_cents,
            self.note,
            self.category,
        ) == (other.date, other.amount_cents, other.note, other.category)

    def __repr__(self) -> str:
        return (
            f"Entry(date={self.date!r}, amount={self.amount!r}, "
            f"note={self.note!r}, category={self.category!r})"
        )


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
            self.add(
                Entry.from_cents(
                    f"{y:04d}-{m:02d}-{d:02d}",
                    entry.amount_cents,
                    category=entry.category,
                    note=entry.note,
                )
            )

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
        cents: dict[str, int] = {}
        for e in self._entries:
            cents[e.category] = cents.get(e.category, 0) + e.amount_cents
        return {category: c / 100 for category, c in cents.items()}

    def total_cents(self) -> int:
        return sum(e.amount_cents for e in self._entries)

    def total(self) -> float:
        return self.total_cents() / 100

    def __len__(self) -> int:
        return len(self._entries)
