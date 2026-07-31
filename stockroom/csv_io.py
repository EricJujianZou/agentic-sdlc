"""CSV import and export for items, and export of the audit trail.

The CSV format is one row per item and warehouse, with a header::

    sku,name,qty,unit_price,supplier_id,category,warehouse

Export always writes that header, and ``qty`` is that warehouse's count.
Import reads by header name, so the columns may come in any order, and
it also accepts the two older layouts: without a ``warehouse`` column a
row carries one total that is stocked in the default warehouse, and
without a ``category`` column as well the rows get ``DEFAULT_CATEGORY``.
Import merges into the store (existing SKUs are updated in place, new
SKUs are added).  Suppliers named in the file are not created - the
supplier_id column is stored as-is, and an empty cell means no supplier.

This is the format our suppliers exchange stock lists in, so the import
side has to accept files we did not write ourselves: a price cell may be
spelled any of the ways :func:`money.parse_money` reads.  Export is the
strict side of that bargain - it always writes a price with exactly two
decimals, so a file we wrote reads back as the amounts it left with.
"""

import csv
import json

from .money import format_amount, parse_money
from .models import (
    DEFAULT_CATEGORY,
    DEFAULT_WAREHOUSE,
    Item,
    normalize_sku,
    record_actor,
)
from .store import Store

FIELDNAMES = [
    "sku", "name", "qty", "unit_price", "supplier_id", "category", "warehouse",
]

EVENT_FIELDNAMES = ["ts", "op", "actor", "args"]

BATCH_FIELDNAMES = ["op", "sku", "qty", "warehouse", "to_warehouse"]


def read_batch(path: str) -> list[dict]:
    """Read a batch file's rows from ``path``, in the order they appear.

    The header is ``op,sku,qty,warehouse,to_warehouse``; the cells are
    handed back exactly as typed, since it is
    :meth:`Store.apply_batch` that knows what a row means and which row
    number to blame when one of them does not add up.

    Returns:
        One dict per data row (the header is not a row).
    """
    with open(path, newline="", encoding="utf-8") as f:
        return [dict(row) for row in csv.DictReader(f)]


def export_items(store: Store, path: str) -> int:
    """Write all items to ``path`` as CSV.

    An item gets one row per warehouse it holds stock in, carrying that
    warehouse's count; one with no stock anywhere still gets a single
    row, in the default warehouse, for 0 units.  Rows are sorted by SKU
    and then by warehouse so repeated exports of the same state produce
    identical files.

    Returns:
        The number of rows written (excluding the header).
    """
    count = 0
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for item in store.list_items():
            stocked = sorted(w for w, qty in item.quantities.items() if qty)
            for warehouse in stocked or [DEFAULT_WAREHOUSE]:
                writer.writerow({
                    "sku": item.sku,
                    "name": item.name,
                    "qty": item.qty_in(warehouse),
                    "unit_price": format_amount(item.unit_price_cents),
                    "supplier_id": item.supplier_id or "",
                    "category": item.category,
                    "warehouse": warehouse,
                })
                count += 1
    return count


def _event_timestamp(event: dict) -> str:
    """When an event happened, whichever key the trail spells it with.

    Entries written by :meth:`Store.log_event` carry ``timestamp``;
    older trails wrote the same reading as ``ts``.  An entry with
    neither is handed back an empty string rather than a guess.
    """
    return event.get("timestamp") or event.get("ts") or ""


def export_events(store: Store, path: str, op: str | None = None,
                  since: str | None = None) -> int:
    """Write the audit trail to ``path`` as CSV.

    The rows are the events in the order they happened, oldest first,
    with the argument mapping JSON-encoded into a single cell so a
    spreadsheet holds one row per change; an event nobody was named for
    gets an empty ``actor`` cell.

    Args:
        op: keep only the events with exactly this op, so "receive"
            leaves out the "receive-order" ones.
        since: an ISO ``YYYY-MM-DD`` day; keep only the events stamped
            that day or later.  An event with no timestamp at all
            cannot be shown to fall after it, so it is left out.

    Filters given together both apply.  One that matches nothing still
    writes the header, so the file is a readable (empty) sheet.

    Returns:
        The number of events written (excluding the header).
    """
    count = 0
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=EVENT_FIELDNAMES)
        writer.writeheader()
        for event in store.events:
            timestamp = _event_timestamp(event)
            if op is not None and event.get("op") != op:
                continue
            if since is not None and timestamp[:10] < since:
                continue
            writer.writerow({
                "ts": timestamp,
                "op": event.get("op", ""),
                "actor": event.get("actor") or "",
                "args": json.dumps(event.get("args") or {}),
            })
            count += 1
    return count


def import_items(store: Store, path: str, actor: str | None = None) -> int:
    """Read items from a CSV file into the store.

    Rows whose SKU already exists update that item; other rows create
    new items.  SKUs are matched without regard to case, so a supplier
    file that lower cases (or mixes) the spelling updates the item we
    already have rather than adding a near-duplicate.  A file whose
    header names the warehouse sets the count of that warehouse alone,
    so its several rows for one SKU all apply; one without the column
    speaks for the item's whole stock, which lands in the default
    warehouse.  ``actor``, when given, is recorded on every item the
    file touches.  The whole file is one change as far as the audit
    trail is concerned, so it logs a single event rather than one per
    row.  The caller is responsible for saving the store afterwards.

    Returns:
        The number of rows processed.
    """
    count = 0
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        per_warehouse = "warehouse" in (reader.fieldnames or [])
        for row in reader:
            sku = normalize_sku(row["sku"])
            qty = int(row["qty"])
            unit_price = parse_money(row["unit_price"])
            supplier_id = row.get("supplier_id") or None
            category = row.get("category") or DEFAULT_CATEGORY
            warehouse = row.get("warehouse") or DEFAULT_WAREHOUSE
            if sku in store.items:
                # Known SKU: refresh the row in place.
                item = store.items[sku]
                item.name = row["name"]
                if per_warehouse:
                    item.set_warehouse_stock(qty, warehouse)
                else:
                    item.set_stock(qty)
                item.unit_price = unit_price
                item.supplier_id = supplier_id
                item.category = category
            else:
                # New SKU: add it to the catalogue.
                item = Item(
                    sku=sku,
                    name=row["name"],
                    unit_price=unit_price,
                    supplier_id=supplier_id,
                    category=category,
                    quantities={warehouse: qty},
                )
                store.items[sku] = item
            record_actor(item, actor)
            count += 1
    store.log_event("import-csv", {"path": path, "rows": count}, actor)
    return count
