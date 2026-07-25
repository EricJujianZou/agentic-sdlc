"""Simple monthly reporting."""

from .ledger import Ledger


def month_total(ledger: Ledger, year: int, month: int) -> float:
    """Total amount spent in the given calendar month."""
    prefix = f"{year:04d}-{month:02d}"
    return sum(e.amount for e in ledger.entries() if e.date[:7] == prefix)


def monthly_summary(ledger: Ledger, year: int, month: int) -> dict[str, float]:
    """Category -> total amount for entries in the given calendar month."""
    prefix = f"{year:04d}-{month:02d}"
    totals: dict[str, float] = {}
    for e in ledger.entries():
        if e.date[:7] == prefix:
            totals[e.category] = totals.get(e.category, 0.0) + e.amount
    return totals


def format_month(ledger: Ledger, year: int, month: int) -> str:
    """One-line human-readable summary for a month."""
    return f"{year:04d}-{month:02d}: {month_total(ledger, year, month):.2f}"
