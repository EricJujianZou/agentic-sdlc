"""Simple monthly reporting."""

from .ledger import Ledger


def _month_entries(ledger: Ledger, year: int, month: int) -> list:
    prefix = f"{year:04d}-{month:02d}"
    return [e for e in ledger.entries() if e.date[:7] == prefix]


def month_total(ledger: Ledger, year: int, month: int) -> float:
    """Total amount spent in the given calendar month."""
    return sum(e.amount_cents for e in _month_entries(ledger, year, month)) / 100


def monthly_summary(ledger: Ledger, year: int, month: int) -> dict[str, float]:
    """Category -> total amount for entries in the given calendar month."""
    cents: dict[str, int] = {}
    for e in _month_entries(ledger, year, month):
        cents[e.category] = cents.get(e.category, 0) + e.amount_cents
    return {category: c / 100 for category, c in cents.items()}


def budget_warnings(ledger: Ledger, year: int, month: int) -> dict[str, float]:
    """Category -> overage for budgeted categories exceeding their limit."""
    spent: dict[str, int] = {}
    for e in _month_entries(ledger, year, month):
        spent[e.category] = spent.get(e.category, 0) + e.amount_cents
    warnings: dict[str, float] = {}
    for category, limit in ledger.budgets.items():
        overage_cents = spent.get(category, 0) - round(limit * 100)
        if overage_cents > 0:
            warnings[category] = overage_cents / 100
    return warnings


def format_month(ledger: Ledger, year: int, month: int) -> str:
    """One-line human-readable summary for a month."""
    return f"{year:04d}-{month:02d}: {month_total(ledger, year, month):.2f}"
