"""Simple monthly reporting."""

from .ledger import Ledger


def _month_cents_by_category(ledger: Ledger, year: int, month: int) -> dict[str, int]:
    prefix = f"{year:04d}-{month:02d}"
    cents: dict[str, int] = {}
    for e in ledger.entries():
        if e.date[:7] == prefix:
            cents[e.category] = cents.get(e.category, 0) + e.amount_cents
    return cents


def month_total(ledger: Ledger, year: int, month: int) -> float:
    """Total amount spent in the given calendar month."""
    return sum(_month_cents_by_category(ledger, year, month).values()) / 100


def monthly_summary(ledger: Ledger, year: int, month: int) -> dict[str, float]:
    """Category -> total amount for the given calendar month."""
    return {c: v / 100 for c, v in _month_cents_by_category(ledger, year, month).items()}


def budget_warnings(ledger: Ledger, year: int, month: int) -> dict[str, float]:
    """Category -> overage for budgeted categories exceeding their limit."""
    spent = _month_cents_by_category(ledger, year, month)
    warnings: dict[str, float] = {}
    for category, limit in ledger.budgets.items():
        limit_cents = int(round(limit * 100))
        over = spent.get(category, 0) - limit_cents
        if over > 0:
            warnings[category] = over / 100
    return warnings


def format_month(ledger: Ledger, year: int, month: int) -> str:
    """One-line human-readable summary for a month."""
    return f"{year:04d}-{month:02d}: {month_total(ledger, year, month):.2f}"
