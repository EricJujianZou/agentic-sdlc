"""Cache for the read-only reports.

The reports screen recomputes everything on every refresh, so results
are memoised per store and keyed by the store's ``revision`` counter:
while nothing has changed, asking for the same report with the same
arguments hands back the very same object.  Any mutation bumps the
revision and the next call recomputes.
"""

from . import reports

# kind -> the report function and the keyword it takes.
KINDS = {
    "stock": reports.stock_report,
    "low": reports.low_stock,
    "monthly": reports.monthly_orders,
    "history": reports.order_history,
    "turnover": reports.turnover,
    "weekly": reports.weekly_shipments,
    "on-time": reports.supplier_on_time,
    "price-changes": reports.price_changes,
    "revenue": reports.monthly_revenue,
    "aging": reports.order_aging,
    "low-by-category": reports.low_stock_by_category,
    "reorder": reports.reorder_suggestions,
}


def cached_report(store, kind: str, **kwargs):
    """Return a report, recomputing it only when the data has changed."""
    if kind not in KINDS:
        raise ValueError(f"unknown report {kind}")
    cache = getattr(store, "_report_cache", None)
    if cache is None or cache["revision"] != store.revision:
        # Any change makes every earlier entry stale.
        cache = store._report_cache = {"revision": store.revision,
                                       "entries": {}}
    key = (kind, tuple(sorted(kwargs.items())))
    entries = cache["entries"]
    if key not in entries:
        entries[key] = KINDS[kind](store, **kwargs)
    return entries[key]
