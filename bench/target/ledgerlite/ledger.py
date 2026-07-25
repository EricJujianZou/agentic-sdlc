"""Core ledger data model."""

import calendar


def normalize_date(date: str) -> str:
    """Return *date* in zero-padded ISO form ``YYYY-MM-DD``."""
    parts = str(date).split("-")
    if len(parts) != 3:
        return str(date)
    year, month, day = parts
    if not (year.isdigit() and month.isdigit() and day.isdigit()):
        return str(date)
    return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"


class Entry:
    """A single expense entry.

    date is an ISO-style string like "2026-03-05"; money is stored internally
    as integer cents while ``amount`` stays a float.
    """

    __slots__ = ("date", "amount_cents", "note", "category")

    def __init__(self, date: str, amount: float, note: str = "",
                 category: str = "uncategorized") -> None:
        self.date = normalize_date(date)
        self.amount_cents = int(round(amount * 100))
        self.note = note
        self.category = category

    @classmethod
    def from_cents(cls, date: str, cents: int, category: str = "uncategorized",
                   note: str = "") -> "Entry":
        entry = cls(date, 0.0, note, category)
        entry.amount_cents = int(cents)
        return entry

    @property
    def amount(self) -> float:
        return self.amount_cents / 100

    def __repr__(self) -> str:
        return (f"Entry(date={self.date!r}, amount={self.amount!r}, "
                f"note={self.note!r}, category={self.category!r})")


class Ledger:
    """An in-memory collection of entries."""

    def __init__(self) -> None:
        self._entries: list[Entry] = []
        self._budgets: dict[str, float] = {}
        self._history: list[tuple] = []

    @property
    def budgets(self) -> dict[str, float]:
        return self._budgets

    def add(self, entry: Entry) -> None:
        self._entries.append(entry)
        self._history.append(("add", entry))

    def add_recurring(self, entry: Entry, months: int) -> None:
        """Add *months* copies of *entry*, one per following calendar month."""
        year, month, day = (int(p) for p in entry.date.split("-"))
        created = []
        for offset in range(months):
            total = (month - 1) + offset
            y = year + total // 12
            m = total % 12 + 1
            d = min(day, calendar.monthrange(y, m)[1])
            copy = Entry.from_cents(f"{y:04d}-{m:02d}-{d:02d}", entry.amount_cents,
                                    entry.category, entry.note)
            self._entries.append(copy)
            created.append(copy)
        self._history.append(("add_recurring", created))

    def remove(self, index: int) -> Entry:
        """Remove and return the entry at *index* (in entries() order)."""
        ordered = self.entries()
        entry = ordered[index]
        self._entries.remove(entry)
        self._history.append(("remove", entry))
        return entry

    def set_budget(self, category: str, limit: float) -> None:
        had = category in self._budgets
        previous = self._budgets.get(category)
        self._budgets[category] = limit
        self._history.append(("set_budget", category, had, previous))

    def undo(self, n: int = 1) -> int:
        """Revert the last *n* mutating operations; return how many were undone."""
        undone = 0
        for _ in range(n):
            if not self._history:
                break
            item = self._history.pop()
            kind = item[0]
            if kind == "add":
                self._entries.remove(item[1])
            elif kind == "remove":
                self._entries.append(item[1])
            elif kind == "add_recurring":
                for entry in item[1]:
                    self._entries.remove(entry)
            elif kind == "set_budget":
                _, category, had, previous = item
                if had:
                    self._budgets[category] = previous
                else:
                    self._budgets.pop(category, None)
            undone += 1
        return undone

    def entries(self) -> list[Entry]:
        """All entries, sorted by date."""
        return sorted(self._entries, key=lambda e: e.date)

    def query(self, category=None, date_from=None, date_to=None, text=None) -> list[Entry]:
        """All entries matching every given filter, in entries() order."""
        lo = normalize_date(date_from) if date_from is not None else None
        hi = normalize_date(date_to) if date_to is not None else None
        needle = text.lower() if text is not None else None
        result = []
        for entry in self.entries():
            if category is not None and entry.category != category:
                continue
            if lo is not None and entry.date < lo:
                continue
            if hi is not None and entry.date > hi:
                continue
            if needle is not None and needle not in entry.note.lower():
                continue
            result.append(entry)
        return result

    def total_cents(self) -> int:
        return sum(e.amount_cents for e in self._entries)

    def total(self) -> float:
        return self.total_cents() / 100

    def totals_by_category(self) -> dict[str, float]:
        cents: dict[str, int] = {}
        for entry in self._entries:
            cents[entry.category] = cents.get(entry.category, 0) + entry.amount_cents
        return {cat: value / 100 for cat, value in cents.items()}

    def __len__(self) -> int:
        return len(self._entries)
