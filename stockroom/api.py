"""The one module an embedder imports: every capability, one flat surface.

Everything stockroom can do is reachable from here under a name and a
signature that stay put, whatever moves underneath.  The functions are
thin: each one delegates to the module that owns the behaviour
(:mod:`stockroom.store`, :mod:`stockroom.reports`, :mod:`stockroom.csv_io`,
:mod:`stockroom.cache`, :mod:`stockroom.money`), so there is no second
implementation here to drift away from the first.  Those modules stay
importable exactly as they were - this is an addition, not a move.

The conventions across the whole surface:

* ``store`` - the object :func:`open_store` returns - comes first, and
  ``store.revision`` counts up with every change made through here.
* anything the caller got wrong raises ``ValueError``.
* every function that changes something writes it to disk before
  returning, so a script that stops halfway leaves the work it did.
* while :func:`set_read_only` is on, every one of those refuses; the
  reads, and turning the switch back off, carry on working.
"""

import os

from . import cache, csv_io, reports
from .dates import normalize_date
from .models import DEFAULT_CATEGORY, DEFAULT_WAREHOUSE
from .money import format_money
from .reports import DEFAULT_THRESHOLD
from .store import STATE_NAME, Store

__all__ = [
    # store / session
    "open_store", "save", "set_read_only", "backup", "restore",
    "list_backups",
    # catalogue
    "add_supplier", "add_item", "set_price", "price_history", "search_items",
    # stock
    "receive", "ship", "transfer",
    # orders
    "place_order", "receive_order", "cancel_order", "ship_order",
    "scheduled_reorders",
    # money
    "format_money", "set_discount", "discounts", "set_tax_rate",
    "order_total", "invoice_text",
    # reports
    "stock_report", "low_stock", "low_stock_by_category",
    "reorder_suggestions", "monthly_orders", "order_history",
    "per_warehouse_report", "turnover", "monthly_revenue",
    "supplier_on_time", "order_aging", "weekly_shipments", "summary",
    "cached_report",
    # csv / exchange
    "export_items_csv", "import_items_csv", "export_events_csv",
    "export_archive", "import_archive",
    # activity / undo
    "events", "undo", "redo",
    # operations
    "batch_apply", "fsck",
]


def _writable(store: Store) -> None:
    """Refuse the change we are about to make if the data is read-only.

    Called first thing by every mutating function here, before anything
    is looked up or worked out, so a refusal leaves the data and the
    files exactly as they were.
    """
    if store.is_locked():
        raise ValueError(
            "this data is read-only; call set_read_only(store, False) first"
        )


# ----------------------------------------------------------------------
# store / session
# ----------------------------------------------------------------------


def open_store(data_dir: str) -> Store:
    """Load the stockroom kept in ``data_dir`` and return it.

    Reads ``<data_dir>/state.json`` in whichever layout it was written -
    the original single file through today's split directory - and gives
    back an empty store when the directory holds nothing yet, so a first
    run needs no setting up.  The next :func:`save` writes the current
    layout, whatever was read.
    """
    store = Store(os.path.join(data_dir, STATE_NAME))
    store.load()
    return store


def save(store: Store) -> None:
    """Write the store to disk in the current layout.

    Every mutating function here saves already; this is for a caller who
    has been at ``store`` directly and wants the same durability.
    """
    store.save()


def set_read_only(store: Store, flag: bool) -> None:
    """Turn the read-only switch on or off, for good.

    The switch lives with the data rather than in this process, so it
    holds across runs and for every other tool looking at the same
    directory.  While it is on, every mutating function here raises
    ``ValueError``; this one is never refused, since it is the way back.
    """
    if flag:
        store.lock()
    else:
        store.unlock()


def backup(store: Store) -> str:
    """Snapshot the state beside itself and return the snapshot's path."""
    _writable(store)
    return os.path.join(store.data_dir(), store.backup())


def list_backups(store: Store) -> list[str]:
    """The paths of the snapshots taken so far, oldest first."""
    directory = store.data_dir()
    return [os.path.join(directory, name) for name in store.list_backups()]


def restore(store: Store, path: str) -> str:
    """Put the state back to what one snapshot captured.

    ``path`` is what :func:`backup` returned or one of
    :func:`list_backups`' entries; a snapshot we did not take raises
    ``ValueError`` before anything is written.  ``store`` is reloaded
    from it in place.
    """
    _writable(store)
    return store.restore(os.path.basename(path))


# ----------------------------------------------------------------------
# catalogue
# ----------------------------------------------------------------------


def add_supplier(store: Store, supplier_id: str, name: str, email: str,
                 lead_time_days: int = 0, actor: str | None = None):
    """Add a supplier we buy from, and return it."""
    _writable(store)
    supplier = store.add_supplier(supplier_id, name, email,
                                  lead_time_days=lead_time_days, actor=actor)
    store.save()
    return supplier


def add_item(store: Store, sku: str, name: str, qty: int = 0,
             price: float = 0.0, supplier: str | None = None,
             category: str | None = None,
             warehouse: str = DEFAULT_WAREHOUSE, actor: str | None = None):
    """Add an item to the catalogue, and return it.

    The SKU is the item's identity whatever case it is typed in, and is
    stored canonically; ``category`` left off files it under
    "uncategorized".  ``qty`` is the stock it starts with, sitting in
    ``warehouse``.
    """
    _writable(store)
    item = store.add_item(sku, name, qty=qty, unit_price=price,
                          supplier_id=supplier,
                          category=category or DEFAULT_CATEGORY, actor=actor)
    if warehouse != DEFAULT_WAREHOUSE:
        item.set_stock(qty, warehouse)
    store.save()
    return item


def set_price(store: Store, sku: str, price: float, date: str | None = None,
              actor: str | None = None):
    """Change what an item costs, noting the change on its history."""
    _writable(store)
    item = store.set_price(sku, price, date=date, actor=actor)
    store.save()
    return item


def price_history(store: Store, sku: str) -> list[dict]:
    """One item's price changes, oldest first (date / old / new)."""
    return list(store.get_item(sku).price_history)


def search_items(store: Store, query: str) -> list:
    """The items whose name or SKU contains ``query``, any case.

    Returns the items themselves, sorted by SKU - the same objects
    ``store.items`` holds - so the caller can read anything off them.
    """
    return [store.items[row["sku"]] for row in reports.search_items(store, query)]


# ----------------------------------------------------------------------
# stock
# ----------------------------------------------------------------------


def receive(store: Store, sku: str, qty: int,
            warehouse: str = DEFAULT_WAREHOUSE, actor: str | None = None):
    """Book goods in to one warehouse, and return the item."""
    _writable(store)
    item = store.receive(sku, qty, warehouse, actor)
    store.save()
    return item


def ship(store: Store, sku: str, qty: int,
         warehouse: str = DEFAULT_WAREHOUSE, actor: str | None = None,
         date: str | None = None):
    """Send goods out of one warehouse, and return the item.

    A warehouse cannot go below zero: shipping more than it holds raises
    ``ValueError`` and nothing moves.
    """
    _writable(store)
    item = store.ship(sku, qty, warehouse, actor, date=date)
    store.save()
    return item


def transfer(store: Store, sku: str, qty: int, source: str, dest: str,
             actor: str | None = None):
    """Move goods between warehouses, and return the item.

    The source cannot go below zero; the destination is created by the
    move if it is new.
    """
    _writable(store)
    item = store.transfer(sku, qty, source, dest, actor)
    store.save()
    return item


# ----------------------------------------------------------------------
# orders
# ----------------------------------------------------------------------


def place_order(store: Store, sku: str, qty: int, date: str,
                supplier: str | None = None, actor: str | None = None):
    """Record a pending purchase order, and return it.

    ``date`` is accepted however it is spelled and stored zero-padded.
    With no supplier named, the item's own - or the one supplier whose
    catalogue lists the SKU - is used; a genuine choice between several
    raises ``ValueError`` rather than being guessed at.
    """
    _writable(store)
    order = store.place_order(sku, qty, date, supplier_id=supplier,
                              actor=actor)
    store.save()
    return order


def receive_order(store: Store, order_id: int, actor: str | None = None,
                  date: str | None = None):
    """Book the rest of a pending order into stock, and return it.

    Only a pending order can be received; anything else raises
    ``ValueError``.  ``date`` is the day the goods turned up (today when
    left off), which is what the on-time report measures.
    """
    _writable(store)
    order = store.receive_order(order_id, actor=actor, date=date)
    store.save()
    return order


def cancel_order(store: Store, order_id: int, actor: str | None = None):
    """Cancel a pending order (stock is untouched), and return it.

    Only a pending order can be cancelled; anything else raises
    ``ValueError``.
    """
    _writable(store)
    order = store.cancel_order(order_id, actor=actor)
    store.save()
    return order


def ship_order(store: Store, order_id: int, qty: int,
               actor: str | None = None):
    """Book part of a pending order arriving, and return the order.

    The order stays pending while any of it is outstanding and becomes
    received as the last unit lands.
    """
    _writable(store)
    order = store.ship_order(order_id, qty, actor=actor)
    store.save()
    return order


def scheduled_reorders(store: Store, as_of: str,
                       threshold: int = DEFAULT_THRESHOLD,
                       actor: str | None = None) -> list:
    """Place the day's reorder suggestions, and return the new orders.

    One pending order per suggested SKU, for the suggested quantity,
    dated ``as_of``.  A SKU that already has an order dated that day is
    left alone, so running the job twice for the same date changes
    nothing.
    """
    _writable(store)
    as_of = normalize_date(as_of)
    ordered_today = {order.sku for order in store.orders if order.date == as_of}
    placed = []
    for row in reports.reorder_suggestions(store, threshold=threshold):
        if row["suggested_qty"] <= 0 or row["sku"] in ordered_today:
            continue
        placed.append(store.place_order(row["sku"], row["suggested_qty"], as_of,
                                        supplier_id=row["supplier_id"],
                                        actor=actor))
    if placed:
        store.save()
    return placed


# ----------------------------------------------------------------------
# money
# ----------------------------------------------------------------------


def set_discount(store: Store, category: str, percent: float,
                 actor: str | None = None) -> None:
    """Set the discount rule for one category (0 to 100 percent)."""
    _writable(store)
    store.set_discount(category, percent, actor=actor)
    store.save()


def discounts(store: Store) -> dict[str, float]:
    """The discount rules in force, category -> percent."""
    return dict(store.discounts)


def set_tax_rate(store: Store, percent: float, actor: str | None = None) -> None:
    """Set the flat sales tax charged on an order."""
    _writable(store)
    store.set_tax_rate(percent, actor=actor)
    store.save()


def order_total(store: Store, order_id: int) -> float:
    """What one order comes to, in dollars.

    Quantity times the item's current price, less the discount its
    category earns, plus tax on what is left - worked out in whole cents,
    so it is exact.
    """
    return reports.order_total(store, order_id)["total"]


def invoice_text(store: Store, order_id: int) -> str:
    """The invoice for one order as a plain-text document.

    The same document ``invoice --output`` writes, and just as
    reproducible: nothing in it depends on when it was made.
    """
    # Imported here rather than at the top: the CLI reaches into this
    # module for the reorder job, and only one of the two can go first.
    from . import cli
    return cli._invoice_text(store, order_id,
                             reports.order_total(store, order_id))


# ----------------------------------------------------------------------
# reports - read-only, cent-exact, date-aware
# ----------------------------------------------------------------------


def stock_report(store: Store) -> dict:
    """Every item with its line value, plus what the stockroom is worth."""
    return reports.stock_report(store)


def low_stock(store: Store, threshold: int = DEFAULT_THRESHOLD) -> list[dict]:
    """The items at or below ``threshold`` (sku / name / qty rows)."""
    return reports.low_stock(store, threshold)


def low_stock_by_category(store: Store,
                          threshold: int = DEFAULT_THRESHOLD) -> dict:
    """The low-stock rows split one category at a time."""
    return reports.low_stock_by_category(store, threshold)


def reorder_suggestions(store: Store,
                        threshold: int = DEFAULT_THRESHOLD) -> list[dict]:
    """What to order and how much, netting out what is already on the way."""
    return reports.reorder_suggestions(store, threshold)


def monthly_orders(store: Store, month: str) -> list[dict]:
    """The orders placed in one ``YYYY-MM``, however their date was typed."""
    return reports.monthly_orders(store, month)


def order_history(store: Store, sku: str) -> list[dict]:
    """One item's orders, oldest first (id / qty / date / status rows)."""
    return reports.order_history(store, sku)


def per_warehouse_report(store: Store) -> dict:
    """The stock report room by room."""
    return reports.per_warehouse_report(store)


def turnover(store: Store) -> dict:
    """Units shipped per category per month."""
    return reports.turnover(store)


def monthly_revenue(store: Store, month: str) -> dict:
    """What the orders received in one ``YYYY-MM`` came to."""
    return reports.monthly_revenue(store, month)


def supplier_on_time(store: Store) -> list[dict]:
    """How often each supplier delivered within its lead time."""
    return reports.supplier_on_time(store)


def order_aging(store: Store, as_of) -> dict:
    """The pending orders bucketed by how long they have been waiting."""
    return reports.order_aging(store, as_of)


def weekly_shipments(store: Store) -> dict:
    """Units shipped per ISO week, oldest week first."""
    return reports.weekly_shipments(store)


def summary(store: Store, threshold: int = DEFAULT_THRESHOLD) -> dict:
    """The one-screen view: valuation, low stock, pending, top category, events."""
    return reports.summary(store, threshold)


def cached_report(store: Store, kind: str, **kwargs):
    """Run one report, or hand back what it returned last time.

    The identical object comes back for as long as nothing changes; the
    first change to the store drops it.
    """
    return cache.cached_report(store, kind, **kwargs)


# ----------------------------------------------------------------------
# csv / exchange
# ----------------------------------------------------------------------


def export_items_csv(store: Store, path: str) -> int:
    """Write the catalogue to ``path`` as CSV, and return the row count."""
    return csv_io.export_items(store, path)


def import_items_csv(store: Store, path: str, actor: str | None = None) -> int:
    """Read a catalogue CSV into the store, and return the row count.

    Every header version we have ever written is accepted: a missing
    category means "uncategorized", a missing warehouse the main one,
    prices read as "3.5" or "$3.50", and SKUs differing only in case are
    the same item.
    """
    _writable(store)
    count = csv_io.import_items(store, path, actor=actor)
    store.save()
    return count


def export_events_csv(store: Store, path: str, op: str | None = None,
                      since: str | None = None) -> int:
    """Write the activity history to ``path`` as CSV, and return the count.

    ``op`` keeps one kind of operation, ``since`` (a ``YYYY-MM-DD`` day,
    inclusive) keeps what happened on or after it; together they narrow.
    """
    return csv_io.export_events(store, path, op=op, since=since)


def export_archive(store: Store, path: str) -> str:
    """Write the whole store - activity history included - to one file."""
    return store.export_archive(path)


def import_archive(path: str, data_dir: str) -> Store:
    """Unpack an archive into an empty ``data_dir`` and return the store.

    A directory that already holds stockroom data is refused with
    ``ValueError`` before anything is written: an archive is a whole
    state, not something to merge.
    """
    store = Store(os.path.join(data_dir, STATE_NAME))
    store.import_archive(path)
    return store


# ----------------------------------------------------------------------
# activity / undo
# ----------------------------------------------------------------------


def events(store: Store) -> list[dict]:
    """The activity history, oldest first (op / args / actor / timestamp)."""
    return list(store.events)


def undo(store: Store, steps: int = 1) -> list[dict]:
    """Walk the newest ``steps`` changes back, and return them.

    All or nothing: too few changes to undo, or one among them that
    cannot be reversed, raises ``ValueError`` before anything moves.
    """
    _writable(store)
    undone = store.undo(steps)
    store.save()
    return undone


def redo(store: Store, steps: int = 1) -> list[dict]:
    """Put back what :func:`undo` took off, and return those changes."""
    _writable(store)
    redone = store.redo(steps)
    store.save()
    return redone


# ----------------------------------------------------------------------
# operations
# ----------------------------------------------------------------------


def batch_apply(store: Store, csv_path: str, dry_run: bool = False,
                actor: str | None = None):
    """Apply a file of stock operations, all of them or none.

    The file's rows (``op,sku,qty,warehouse,to_warehouse``) go through
    the ordinary receive / ship / transfer, so each lands on the activity
    history and can be undone.  The first row that will not apply raises
    ``ValueError`` and puts the store back as it was.

    Returns the number of operations applied, or - with ``dry_run`` - one
    line describing each operation, having changed and written nothing.
    """
    _writable(store)
    rows = csv_io.read_batch(csv_path)
    if dry_run:
        return store.plan_batch(rows)
    count = store.apply_batch(rows, actor=actor)
    store.save()
    return count


def fsck(store: Store) -> list[str]:
    """Everything inconsistent about the data, one message each.

    An empty list means the data is clean.
    """
    return reports.fsck(store)
