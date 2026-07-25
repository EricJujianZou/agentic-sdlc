"""Core ledger data model."""

import calendar


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


class Entry:
    """A single expense entry.

    date is an ISO-style string like "2026-03-05". Money is stored exactly, as
    integer cents; ``amount`` remains a float view of it.
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
        """Build an entry from an exact integer *cents* amount."""
        entry = cls(date, 0.0, note, category)
        entry.amount_cents = int(cents)
        return entry

    @property
    def amount(self) -> float:
        return self.amount_cents / 100

    @amount.setter
    def amount(self, value: float) -> None:
        self.amount_cents = round(value * 100)

    def _key(self) -> tuple:
        return (self.date, self.amount_cents, self.note, self.category)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Entry):
            return NotImplemented
        return self._key() == other._key()

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
        self._history: list[tuple] = []

    def _discard(self, entry: Entry) -> None:
        """Remove *entry* by identity."""
        for i, existing in enumerate(self._entries):
            if existing is entry:
                del self._entries[i]
                return

    def set_budget(self, category: str, limit: float) -> None:
        """Record a monthly spending limit for *category*."""
        had = category in self.budgets
        self._history.append(("set_budget", category, had, self.budgets.get(category)))
        self.budgets[category] = limit

    def add(self, entry: Entry) -> None:
        self._entries.append(entry)
        self._history.append(("add", entry))

    def add_recurring(self, entry: Entry, months: int) -> None:
        """Add *entry* plus one copy per following month (day clamped)."""
        year, month, day = (int(p) for p in entry.date.split("-"))
        created: list[Entry] = []
        for offset in range(months):
            total = month - 1 + offset
            y = year + total // 12
            m = total % 12 + 1
            d = min(day, calendar.monthrange(y, m)[1])
            copy = Entry.from_cents(
                f"{y:04d}-{m:02d}-{d:02d}",
                entry.amount_cents,
                entry.category,
                entry.note,
            )
            self._entries.append(copy)
            created.append(copy)
        self._history.append(("add_recurring", created))

    def remove(self, index: int) -> Entry:
        """Remove and return the entry at *index* (in entries() order)."""
        ordered = self.entries()
        entry = ordered[index]
        self._discard(entry)
        self._history.append(("remove", entry))
        return entry

    def undo(self, n: int = 1) -> int:
        """Revert the last *n* mutating operations; return how many were undone."""
        undone = 0
        for _ in range(n):
            if not self._history:
                break
            op = self._history.pop()
            kind = op[0]
            if kind == "add":
                self._discard(op[1])
            elif kind == "add_recurring":
                for entry in op[1]:
                    self._discard(entry)
            elif kind == "remove":
                self._entries.append(op[1])
            elif kind == "set_budget":
                _, category, had, previous = op
                if had:
                    self.budgets[category] = previous
                else:
                    self.budgets.pop(category, None)
            undone += 1
        return undone

    def entries(self) -> list[Entry]:
        """All entries, sorted by date."""
        return sorted(self._entries, key=lambda e: e.date)

    def query(
        self,
        category: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        text: str | None = None,
    ) -> list[Entry]:
        """Entries matching all given filters, in date-sorted order."""
        low = normalize_date(date_from) if date_from is not None else None
        high = normalize_date(date_to) if date_to is not None else None
        needle = text.lower() if text is not None else None
        results = []
        for e in self.entries():
            if category is not None and e.category != category:
                continue
            if low is not None and e.date < low:
                continue
            if high is not None and e.date > high:
                continue
            if needle is not None and needle not in e.note.lower():
                continue
            results.append(e)
        return results

    def total(self) -> float:
        return self.total_cents() / 100

    def total_cents(self) -> int:
        return sum(e.amount_cents for e in self._entries)

    def totals_by_category(self) -> dict[str, float]:
        """Sum of amounts per category."""
        cents: dict[str, int] = {}
        for e in self._entries:
            cents[e.category] = cents.get(e.category, 0) + e.amount_cents
        return {category: c / 100 for category, c in cents.items()}

    def __len__(self) -> int:
        return len(self._entries)
