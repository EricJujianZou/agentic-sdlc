"""Read-only reports over a loaded Store.

Every function here takes a ``Store`` and returns plain data (lists and
dicts); formatting for the terminal happens in the CLI.  Nothing in this
module mutates state, so the CLI never saves after running a report.
"""

from .store import Store

# Items at or around this stock level are worth another look.  The CLI
# lets the user override it per invocation with --threshold.
DEFAULT_THRESHOLD = 5


def stock_report(store: Store) -> dict:
    """Full stock listing plus total inventory value.

    Returns:
        A dict with two keys: ``rows`` is a list with one entry per item
        (sorted by SKU), each carrying sku/name/qty/unit_price and the
        line ``value`` (qty times unit price); ``total_value`` is the
        value of the whole stockroom.
    """
    rows = []
    total_value = 0.0
    for item in store.list_items():
        value = item.qty * item.unit_price
        total_value += value
        rows.append({
            "sku": item.sku,
            "name": item.name,
            "qty": item.qty,
            "unit_price": item.unit_price,
            "value": value,
        })
    return {"rows": rows, "total_value": total_value}


def low_stock(store: Store, threshold: int = DEFAULT_THRESHOLD) -> list[dict]:
    """Items whose stock has dropped to the threshold or below.

    Returns:
        A list of dicts (sku, name, qty), sorted by SKU.  Empty when
        nothing is running low.
    """
    rows = []
    for item in store.list_items():
        if item.qty <= threshold:
            rows.append({
                "sku": item.sku,
                "name": item.name,
                "qty": item.qty,
            })
    return rows


def monthly_orders(store: Store, month: str) -> list[dict]:
    """All orders placed in the given month.

    Args:
        month: a prefix like "2026-01"; any order dated within that
            month is included, regardless of status.

    Returns:
        A list of dicts (id, sku, qty, date, status), oldest first.
    """
    rows = []
    for order in store.orders:
        if order.date.startswith(month):
            rows.append({
                "id": order.id,
                "sku": order.sku,
                "qty": order.qty,
                "date": order.date,
                "status": order.status,
            })
    rows.sort(key=lambda row: row["date"])
    return rows


def order_history(store: Store, sku: str) -> list[dict]:
    """Every order ever placed for one SKU.

    Returns:
        A list of dicts (id, qty, date, status), oldest first.  Empty
        when the SKU has never been ordered.
    """
    rows = []
    for order in store.orders:
        if order.sku == sku:
            rows.append({
                "id": order.id,
                "qty": order.qty,
                "date": order.date,
                "status": order.status,
            })
    rows.sort(key=lambda row: row["date"])
    return rows


def reorder_suggestions(store: Store,
                        threshold: int = DEFAULT_THRESHOLD) -> list[dict]:
    """Suggest order quantities for items running low.

    For each item below the threshold, suggest topping back up to the
    threshold.  Only items with a supplier are included, since there is
    nobody to order the rest from.

    Returns:
        A list of dicts (sku, supplier_id, qty, suggested_qty), sorted
        by SKU.
    """
    rows = []
    for item in store.list_items():
        if item.qty < threshold and item.supplier_id is not None:
            rows.append({
                "sku": item.sku,
                "supplier_id": item.supplier_id,
                "qty": item.qty,
                "suggested_qty": threshold - item.qty,
            })
    return rows
