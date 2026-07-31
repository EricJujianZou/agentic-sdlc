"""CSV import and export for items.

The CSV format is one row per item per warehouse, with a header::

    sku,name,qty,unit_price,supplier_id,category,warehouse

Export writes the current items; import reads a file and merges it into
the store (existing SKUs are updated in place, new SKUs are added).
Suppliers named in the file are not created - the supplier_id column is
stored as-is, and an empty cell means no supplier.

This is the format our suppliers exchange stock lists in, so the import
side has to accept files we did not write ourselves: it is header-driven
(column order does not matter) and every older layout still works - a
file without a ``warehouse`` column puts its quantities in the main
room, and one without a ``category`` column leaves items uncategorized.
"""

import csv

from .models import DEFAULT_CATEGORY, MAIN_WAREHOUSE, Item, canonical_sku
from .store import Store

FIELDNAMES = ["sku", "name", "qty", "unit_price", "supplier_id", "category",
              "warehouse"]


def export_items(store: Store, path: str) -> int:
    """Write all items to ``path`` as CSV.

    An item gets one row per warehouse holding stock of it; an item with
    no stock anywhere still gets a single ``main`` row with quantity 0.
    Rows are sorted by SKU (then warehouse) so repeated exports of the
    same state produce identical files.

    Returns:
        The number of rows written (excluding the header).
    """
    count = 0
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for item in store.list_items():
            stocked = sorted(w for w, qty in item.quantities.items() if qty)
            for warehouse in stocked or [MAIN_WAREHOUSE]:
                writer.writerow({
                    "sku": item.sku,
                    "name": item.name,
                    "qty": item.qty_in(warehouse),
                    "unit_price": item.unit_price,
                    "supplier_id": item.supplier_id or "",
                    "category": item.category,
                    "warehouse": warehouse,
                })
                count += 1
    return count


def import_items(store: Store, path: str, actor: str | None = None) -> int:
    """Read items from a CSV file into the store.

    Rows whose SKU already exists update that item; other rows create
    new items.  The caller is responsible for saving the store
    afterwards.

    Returns:
        The number of rows processed.
    """
    count = 0
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Supplier files spell SKUs in whatever case they like, and
            # some mix both spellings of one SKU in the same file.
            sku = canonical_sku(row["sku"])
            qty = int(row["qty"])
            unit_price = float(row["unit_price"])
            supplier_id = row.get("supplier_id") or None
            # Older files have no category and no warehouse column.
            category = row.get("category") or None
            warehouse = row.get("warehouse") or MAIN_WAREHOUSE
            if sku in store.items:
                # Known SKU: refresh the row in place.
                item = store.items[sku]
                item.name = row["name"]
                item.unit_price = unit_price
                item.supplier_id = supplier_id
                if category:
                    item.category = category
                if actor:
                    item.last_actor = actor
            else:
                # New SKU: add it to the catalogue.
                item = Item(
                    sku=sku,
                    name=row["name"],
                    unit_price=unit_price,
                    supplier_id=supplier_id,
                    category=category or DEFAULT_CATEGORY,
                    last_actor=actor,
                )
                store.items[sku] = item
            item.set_qty(warehouse, qty)
            count += 1
    return count
