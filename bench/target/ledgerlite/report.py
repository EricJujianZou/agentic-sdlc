"""Simple monthly reporting."""

from .ledger import Ledger


def month_total(ledger: Ledger, year: int, month: int) -> float:
    """Total amount spent in the given calendar month."""
    prefix = f"{year:04d}-{month:02d}"
    return sum(e.amount for e in ledger.entries() if e.date[:7] == prefix)


def monthly_summary(ledger: Ledger, year: int, month: int) -> dict[str, float]:
    """Category -> total amount for entries in the given calendar month."""
    prefix = f"{year:04d}-{month:02d}"
    summary: dict[str, float] = {}
    for e in ledger.entries():
        if e.date[:7] == prefix:
            summary[e.category] = summary.get(e.category, 0.0) + e.amount
    return summary


def budget_warnings(ledger: Ledger, year: int, month: int) -> dict[str, float]:
    """Category -> overage for budgeted categories exceeding their limit."""
    spent = monthly_summary(ledger, year, month)
    warnings: dict[str, float] = {}
    for category, limit in ledger.budgets.items():
        overage = spent.get(category, 0.0) - limit
        if overage > 0:
            warnings[category] = overage
    return warnings


def format_month(ledger: Ledger, year: int, month: int) -> str:
    """One-line human-readable summary for a month."""
    return f"{year:04d}-{month:02d}: {month_total(ledger, year, month):.2f}"
