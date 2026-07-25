"""Simple monthly reporting."""

from .ledger import Ledger


def month_total(ledger: Ledger, year: int, month: int) -> float:
    """Total amount spent in the given calendar month."""
    prefix = f"{year:04d}-{month:02d}"
    return sum(e.amount_cents for e in ledger.entries() if e.date[:7] == prefix) / 100


def monthly_summary(ledger: Ledger, year: int, month: int) -> dict[str, float]:
    """Category -> total amount for entries in the given calendar month."""
    prefix = f"{year:04d}-{month:02d}"
    cents: dict[str, int] = {}
    for e in ledger.entries():
        if e.date[:7] == prefix:
            cents[e.category] = cents.get(e.category, 0) + e.amount_cents
    return {category: c / 100 for category, c in cents.items()}


def budget_warnings(ledger: Ledger, year: int, month: int) -> dict[str, float]:
    """Budgeted category -> overage for categories over budget that month."""
    spent = monthly_summary(ledger, year, month)
    warnings: dict[str, float] = {}
    for category, limit in ledger.budgets.items():
        over = spent.get(category, 0.0) - limit
        if over > 0:
            warnings[category] = over
    return warnings


def format_month(ledger: Ledger, year: int, month: int) -> str:
    """One-line human-readable summary for a month."""
    return f"{year:04d}-{month:02d}: {month_total(ledger, year, month):.2f}"
