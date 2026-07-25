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
        self._history: list[tuple] = []

    def add(self, entry: Entry) -> None:
        self._entries.append(entry)
        self._history.append(("add", entry))

    def add_recurring(self, entry: Entry, months: int) -> None:
        """Add *months* copies of *entry*, one per following calendar month."""
        year, month, day = (int(part) for part in entry.date.split("-"))
        generated: list[Entry] = []
        for offset in range(months):
            total = month - 1 + offset
            y = year + total // 12
            m = total % 12 + 1
            d = min(day, calendar.monthrange(y, m)[1])
            created = Entry.from_cents(
                f"{y:04d}-{m:02d}-{d:02d}",
                entry.amount_cents,
                category=entry.category,
                note=entry.note,
            )
            self._entries.append(created)
            generated.append(created)
        self._history.append(("add_recurring", generated))

    def remove(self, index: int) -> Entry:
        """Remove and return the entry at *index* (in entries() order)."""
        ordered = self.entries()
        entry = ordered[index]
        position = self._entries.index(entry)
        del self._entries[position]
        self._history.append(("remove", entry, position))
        return entry

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
        result = []
        for e in self.entries():
            if category is not None and e.category != category:
                continue
            if low is not None and e.date < low:
                continue
            if high is not None and e.date > high:
                continue
            if needle is not None and needle not in e.note.lower():
                continue
            result.append(e)
        return result

    def set_budget(self, category: str, limit: float) -> None:
        previous = self.budgets.get(category)
        self._history.append(("set_budget", category, previous))
        self.budgets[category] = limit

    def undo(self, n: int = 1) -> int:
        """Revert the last *n* mutating operations; return how many were undone."""
        undone = 0
        while undone < n and self._history:
            op = self._history.pop()
            kind = op[0]
            if kind == "add":
                self._entries.remove(op[1])
            elif kind == "add_recurring":
                for created in op[1]:
                    self._entries.remove(created)
            elif kind == "remove":
                self._entries.insert(op[2], op[1])
            elif kind == "set_budget":
                _, category, previous = op
                if previous is None:
                    self.budgets.pop(category, None)
                else:
                    self.budgets[category] = previous
            undone += 1
        return undone

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
