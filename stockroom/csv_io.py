"""CSV import and export for items.

The CSV format is one row per item with a header::

    sku,name,qty,unit_price,supplier_id

Export writes the current items; import reads a file in the same format
and merges it into the store (existing SKUs are updated in place, new
SKUs are added).  Suppliers named in the file are not created - the
supplier_id column is stored as-is, and an empty cell means no supplier.

This is the format our suppliers exchange stock lists in, so the import
side has to accept files we did not write ourselves.
"""

import csv

from .models import Item
from .store import Store

FIELDNAMES = ["sku", "name", "qty", "unit_price", "supplier_id"]


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
            })
            count += 1
    return count


def import_items(store: Store, path: str) -> int:
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
            sku = row["sku"]
            qty = int(row["qty"])
            unit_price = float(row["unit_price"])
            supplier_id = row.get("supplier_id") or None
            if sku in store.items:
                # Known SKU: refresh the row in place.
                item = store.items[sku]
                item.name = row["name"]
                item.qty = qty
                item.unit_price = unit_price
                item.supplier_id = supplier_id
            else:
                # New SKU: add it to the catalogue.
                store.items[sku] = Item(
                    sku=sku,
                    name=row["name"],
                    qty=qty,
                    unit_price=unit_price,
                    supplier_id=supplier_id,
                )
            count += 1
    return count
