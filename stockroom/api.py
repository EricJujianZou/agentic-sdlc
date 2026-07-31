"""One stable entry point for everything stockroom can do.

Integrations import this module and nothing else: the names and
signatures here stay put even when the modules underneath move around.
The older module paths (``stockroom.store``, ``stockroom.reports``,
``stockroom.csv_io``, ``stockroom.cli``, ...) keep working as they
always have.

Conventions:

* user errors raise ``ValueError``;
* every mutating function writes its change to disk before returning;
* ``store`` is whatever ``open_store`` handed back;
* while the store is marked read-only, every mutating function refuses.
"""

import os

from . import cache, csv_io, reports
from .money import format_money as _format_money
from .store import Store

__all__ = [
    "open_store", "save", "set_read_only", "backup", "restore",
    "list_backups", "add_supplier", "add_item", "set_price", "price_history",
    "search_items", "receive", "ship", "transfer", "place_order",
    "receive_order", "cancel_order", "ship_order", "scheduled_reorders",
    "format_money", "set_discount", "discounts", "set_tax_rate",
    "order_total", "invoice_text", "stock_report", "low_stock",
    "low_stock_by_category", "reorder_suggestions", "monthly_orders",
    "order_history", "per_warehouse_report", "turnover", "monthly_revenue",
    "supplier_on_time", "order_aging", "weekly_shipments", "summary",
    "cached_report", "export_items_csv", "import_items_csv",
    "export_events_csv", "export_archive", "import_archive", "events",
    "undo", "redo", "batch_apply", "fsck",
]

STATE_FILE = "state.json"


# ----------------------------------------------------------------------
# store / session
# ----------------------------------------------------------------------

def open_store(data_dir: str) -> Store:
    """Load the store in *data_dir*, in any layout we have ever written."""
    store = Store(os.path.join(data_dir, STATE_FILE))
    store.load()
    return store


def save(store: Store) -> None:
    """Persist the store in the current layout."""
    store.save()


def set_read_only(store: Store, flag: bool) -> None:
    """Set or clear the persistent read-only switch.  Always allowed."""
    store.set_read_only(flag)
    store.save()


def _writable(store: Store) -> None:
    """Refuse to change anything while the data is read-only."""
    if store.read_only:
        raise ValueError("data is read-only")


def backup(store: Store) -> str:
    """Snapshot the state; returns the backup name."""
    _writable(store)
    return store.backup()


def restore(store: Store, path: str) -> None:
    """Restore a named backup."""
    _writable(store)
    store.restore(path)
    store.save()


def list_backups(store: Store) -> list:
    """The backups we hold, oldest first."""
    return store.list_backups()


# ----------------------------------------------------------------------
# catalogue
# ----------------------------------------------------------------------

def add_supplier(store: Store, supplier_id: str, name: str, email: str,
                 lead_time_days: int = 0):
    """Register a supplier."""
    _writable(store)
    supplier = store.add_supplier(supplier_id, name, email,
                                  lead_time_days=lead_time_days)
    store.save()
    return supplier


def add_item(store: Store, sku: str, name: str, qty: int = 0, price=0.0,
             supplier: str | None = None, category: str | None = None,
             warehouse: str = "main"):
    """Create an item; SKU identity ignores case, stored canonically."""
    _writable(store)
    item = store.add_item(sku, name, unit_price=price, supplier_id=supplier,
                          category=category)
    if qty:
        store.receive(item.sku, qty, warehouse=warehouse)
    store.save()
    return item


def set_price(store: Store, sku: str, price, date: str | None = None):
    """Change an item's unit price, remembering the old one."""
    _writable(store)
    item = store.set_price(sku, price, date=date)
    store.save()
    return item


def price_history(store: Store, sku: str) -> list:
    """An item's recorded price changes, amounts in dollars."""
    return store.get_item(sku).price_history


def search_items(store: Store, query: str) -> list:
    """The items whose name or SKU contains *query*, case-insensitively."""
    return [store.get_item(row["sku"])
            for row in reports.search_items(store, query)]


# ----------------------------------------------------------------------
# stock
# ----------------------------------------------------------------------

def receive(store: Store, sku: str, qty: int, warehouse: str = "main",
            actor: str | None = None):
    """Book goods into a warehouse."""
    _writable(store)
    item = store.receive(sku, qty, warehouse=warehouse, actor=actor)
    store.save()
    return item


def ship(store: Store, sku: str, qty: int, warehouse: str = "main",
         actor: str | None = None):
    """Send goods out; never takes a warehouse below zero."""
    _writable(store)
    item = store.ship(sku, qty, warehouse=warehouse, actor=actor)
    store.save()
    return item


def transfer(store: Store, sku: str, qty: int, source: str, dest: str,
             actor: str | None = None):
    """Move stock between warehouses; a new destination is fine."""
    _writable(store)
    item = store.transfer(sku, qty, source, dest, actor=actor)
    store.save()
    return item


# ----------------------------------------------------------------------
# orders
# ----------------------------------------------------------------------

def place_order(store: Store, sku: str, qty: int, date: str,
                supplier: str | None = None, actor: str | None = None):
    """Place a purchase order; the date may be typed in any of our styles."""
    _writable(store)
    order = store.place_order(sku, qty, date, supplier_id=supplier,
                              actor=actor)
    store.save()
    return order


def receive_order(store: Store, order_id: int, date: str | None = None,
                  actor: str | None = None):
    """Book in whatever is still outstanding on a pending order."""
    _writable(store)
    order = store.receive_order(order_id, date=date, actor=actor)
    store.save()
    return order


def cancel_order(store: Store, order_id: int, actor: str | None = None):
    """Cancel a pending order."""
    _writable(store)
    order = store.cancel_order(order_id, actor=actor)
    store.save()
    return order


def ship_order(store: Store, order_id: int, qty: int,
               actor: str | None = None):
    """Book a partial delivery against a pending order."""
    _writable(store)
    order = store.ship_order(order_id, qty, actor=actor)
    store.save()
    return order


def scheduled_reorders(store: Store, as_of: str | None = None,
                       threshold: int | None = None,
                       actor: str | None = None) -> list:
    """Place today's suggested reorders; idempotent per day and SKU."""
    _writable(store)
    placed = store.scheduled_reorders(as_of=as_of, threshold=threshold,
                                      actor=actor)
    store.save()
    return placed


# ----------------------------------------------------------------------
# money
# ----------------------------------------------------------------------

def format_money(amount) -> str:
    """Format an amount as ``$X.XX`` (ints are cents, floats dollars)."""
    return _format_money(amount)


def set_discount(store: Store, category: str, percent) -> None:
    """Create or replace a category's discount rule."""
    _writable(store)
    store.set_discount(category, percent)
    store.save()


def discounts(store: Store) -> dict:
    """The discount rules, category -> percent."""
    return dict(store.discounts)


def set_tax_rate(store: Store, percent) -> None:
    """Set the flat tax rate, as a percent."""
    _writable(store)
    store.set_tax_rate(percent)
    store.save()


def order_total(store: Store, order_id: int) -> float:
    """What an order costs: qty x price, less discount, plus tax."""
    return reports.order_total(store, order_id)["total"]


def invoice_text(store: Store, order_id: int) -> str:
    """The invoice for one order as plain text."""
    return reports.invoice_text(store, order_id)


# ----------------------------------------------------------------------
# reports (read-only)
# ----------------------------------------------------------------------

def stock_report(store: Store, warehouse: str | None = None) -> dict:
    """Stock listing plus total inventory value."""
    return reports.stock_report(store, warehouse=warehouse)


def low_stock(store: Store, threshold: int = reports.DEFAULT_THRESHOLD) -> list:
    """Items at or below the threshold."""
    return reports.low_stock(store, threshold=threshold)


def low_stock_by_category(store: Store,
                          threshold: int = reports.DEFAULT_THRESHOLD) -> dict:
    """Low-stock rows grouped by shelf area."""
    return reports.low_stock_by_category(store, threshold=threshold)


def reorder_suggestions(store: Store,
                        threshold: int = reports.DEFAULT_THRESHOLD) -> list:
    """What to order, allowing for stock already on the way."""
    return reports.reorder_suggestions(store, threshold=threshold)


def monthly_orders(store: Store, month: str) -> list:
    """Orders placed in one month, however their date was spelled."""
    return reports.monthly_orders(store, month)


def order_history(store: Store, sku: str) -> list:
    """Every order for one SKU, oldest first."""
    return reports.order_history(store, sku)


def per_warehouse_report(store: Store) -> dict:
    """A stock listing per warehouse."""
    return reports.per_warehouse_report(store)


def turnover(store: Store) -> dict:
    """Units shipped per category per month."""
    return reports.turnover(store)


def monthly_revenue(store: Store, month: str) -> dict:
    """What a month's received orders were worth."""
    return reports.monthly_revenue(store, month)


def supplier_on_time(store: Store) -> list:
    """Per-supplier delivery performance."""
    return reports.supplier_on_time(store)


def order_aging(store: Store, as_of=None) -> dict:
    """Pending orders bucketed by age."""
    return reports.order_aging(store, as_of)


def weekly_shipments(store: Store) -> dict:
    """Units shipped per ISO week."""
    return reports.weekly_shipments(store)


def summary(store: Store,
            threshold: int = reports.DEFAULT_THRESHOLD) -> dict:
    """The day's numbers on one screen."""
    return reports.summary(store, threshold=threshold)


def cached_report(store: Store, kind: str, **kwargs):
    """A report, recomputed only when the data has changed."""
    return cache.cached_report(store, kind, **kwargs)


# ----------------------------------------------------------------------
# CSV / exchange
# ----------------------------------------------------------------------

def export_items_csv(store: Store, path: str) -> int:
    """Write the items to a CSV file, category column included."""
    return csv_io.export_items(store, path)


def import_items_csv(store: Store, path: str,
                     actor: str | None = None) -> int:
    """Merge a CSV file of items in, in any header version we have used."""
    _writable(store)
    count = csv_io.import_items(store, path, actor=actor)
    store.save()
    return count


def export_events_csv(store: Store, path: str, op: str | None = None,
                      since: str | None = None) -> int:
    """Write the activity history to a CSV file."""
    return csv_io.export_events(store, path, op=op, since=since)


def export_archive(store: Store, path: str) -> None:
    """Write one self-contained snapshot of everything we hold."""
    store.export_archive(path)


def import_archive(path: str, data_dir: str) -> Store:
    """Recreate a whole state from an archive in an empty directory."""
    store = open_store(data_dir)
    store.import_archive(path)
    store.save()
    return store


# ----------------------------------------------------------------------
# activity / undo
# ----------------------------------------------------------------------

def events(store: Store) -> list:
    """The activity history, oldest first."""
    return store.events


def undo(store: Store, steps: int = 1) -> list:
    """Step back through the most recent changes."""
    _writable(store)
    undone = store.undo(steps)
    store.save()
    return undone


def redo(store: Store, steps: int = 1) -> list:
    """Walk forward again through changes that were undone."""
    _writable(store)
    redone = store.redo(steps)
    store.save()
    return redone


# ----------------------------------------------------------------------
# operations
# ----------------------------------------------------------------------

def batch_apply(store: Store, csv_path: str, dry_run: bool = False) -> list:
    """Apply a sheet of stock movements, all or nothing."""
    _writable(store)
    described = store.batch_apply(csv_path, dry_run=dry_run)
    if not dry_run:
        store.save()
    return described


def fsck(store: Store) -> list:
    """Cross-check the data; an empty list means it is clean."""
    return store.fsck()
