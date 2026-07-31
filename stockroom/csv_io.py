"""CSV import and export for items.

The CSV format is one row per item with a header::

    sku,name,qty,unit_price,supplier_id,category

Export always writes that header.  Import also accepts the older layout
without a ``category`` column - those rows get ``DEFAULT_CATEGORY``.
Import merges into the store (existing SKUs are updated in place, new
SKUs are added).  A row carries one total with no warehouse, so an
imported quantity is stocked in the default warehouse.  Suppliers named
in the file are not created - the supplier_id column is stored as-is,
and an empty cell means no supplier.

This is the format our suppliers exchange stock lists in, so the import
side has to accept files we did not write ourselves.
"""

import csv

from .models import DEFAULT_CATEGORY, Item, normalize_sku, record_actor
from .store import Store

FIELDNAMES = ["sku", "name", "qty", "unit_price", "supplier_id", "category"]


def export_items(store: Store, path: str) -> int:
    """Write all items to ``path`` as CSV.

    Rows are sorted by SKU so repeated exports of the same state produce
    identical files.

    Returns:
        The number of item rows written (excluding the header).
    """
    count = 0
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for item in store.list_items():
            writer.writerow({
                "sku": item.sku,
                "name": item.name,
                "qty": item.qty,
                "unit_price": item.unit_price,
                "supplier_id": item.supplier_id or "",
                "category": item.category,
            })
            count += 1
    return count


def import_items(store: Store, path: str, actor: str | None = None) -> int:
    """Read items from a CSV file into the store.

    Rows whose SKU already exists update that item; other rows create
    new items.  SKUs are matched without regard to case, so a supplier
    file that lower cases (or mixes) the spelling updates the item we
    already have rather than adding a near-duplicate.  ``actor``, when
    given, is recorded on every item the file touches.  The caller is
    responsible for saving the store afterwards.

    Returns:
        The number of rows processed.
    """
    count = 0
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sku = normalize_sku(row["sku"])
            qty = int(row["qty"])
            unit_price = float(row["unit_price"])
            supplier_id = row.get("supplier_id") or None
            category = row.get("category") or DEFAULT_CATEGORY
            if sku in store.items:
                # Known SKU: refresh the row in place.
                item = store.items[sku]
                item.name = row["name"]
                item.set_stock(qty)
                item.unit_price = unit_price
                item.supplier_id = supplier_id
                item.category = category
            else:
                # New SKU: add it to the catalogue.
                item = Item(
                    sku=sku,
                    name=row["name"],
                    qty=qty,
                    unit_price=unit_price,
                    supplier_id=supplier_id,
                    category=category,
                )
                store.items[sku] = item
            record_actor(item, actor)
            count += 1
    return count
