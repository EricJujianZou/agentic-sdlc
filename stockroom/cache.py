"""A cache sitting in front of the reports.

A report is worked out from the state and nothing else, so while the
state stands still the answer computed a moment ago is still the right
one - and on a busy screen that refreshes, most of the answers are
recomputations of exactly what was on it before.

``Store.revision`` counts the changes the store has seen, so a result is
good for as long as that number holds.  :func:`cached_report` keeps what
it worked out per store and hands back the very same object until the
revision moves, at which point the whole lot is dropped and the next
call recomputes.  Different arguments are separate answers and are kept
separately.

Nothing here writes anything: a miss simply runs the report it wraps.
"""

import weakref

from . import reports

#: Which report each kind runs, named as the ``report`` command names it.
KINDS = {
    "stock": reports.stock_report,
    "low": reports.low_stock,
    "low-by-category": reports.low_stock_by_category,
    "reorder": reports.reorder_suggestions,
    "monthly": reports.monthly_orders,
    "revenue": reports.monthly_revenue,
    "on-time": reports.supplier_on_time,
    "aging": reports.order_aging,
    "turnover": reports.turnover,
    "weekly": reports.weekly_shipments,
    "price-changes": reports.price_changes,
    "history": reports.order_history,
}

#: What has been worked out, per store: store -> (revision, {key: result}).
#: The stores are held weakly, so a store that goes out of scope takes
#: its cached reports with it rather than pinning them in memory.
_CACHES: "weakref.WeakKeyDictionary" = weakref.WeakKeyDictionary()


def cached_report(store, kind: str, **kwargs):
    """Run one report, or return what it returned last time.

    ``kind`` picks the report (:data:`KINDS`) and the keyword arguments
    are the ones that report takes - ``threshold=``, ``month=``,
    ``sku=`` and so on - so the result is exactly what calling the
    report directly would give.  A kind we do not know raises
    ``ValueError``.

    The answer is cached against ``(store.revision, kind, arguments)``:
    call it again with the same kind and arguments while nothing has
    changed and you get the identical object back, without the report
    running again.
    """
    try:
        report = KINDS[kind]
    except KeyError:
        raise ValueError(f"unknown report {kind}") from None
    revision, results = _CACHES.get(store, (None, None))
    if revision != store.revision:
        results = {}
        _CACHES[store] = (store.revision, results)
    key = (kind, tuple(sorted(kwargs.items())))
    if key not in results:
        results[key] = report(store, **kwargs)
    return results[key]
