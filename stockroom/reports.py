"""Read-only reports over a loaded Store.

Every function here takes a ``Store`` and returns plain data (lists and
dicts); formatting for the terminal happens in the CLI.  Nothing in this
module mutates state, so the CLI never saves after running a report.
"""

from .store import Store

# Items at or around this stock level are worth another look.  The CLI
# lets the user override it per invocation with --threshold.
DEFAULT_THRESHOLD = 5


def stock_report(store: Store, by_category: bool = False) -> dict:
    """Full stock listing plus total inventory value.

    Args:
        by_category: group the rows by shelf area instead of returning
            one flat list.

    Returns:
        A dict with two keys.  ``total_value`` is the value of the whole
        stockroom.  The other key is ``rows``, a list with one entry per
        item (sorted by SKU) carrying sku/name/qty/unit_price and the
        line ``value`` (qty times unit price) - or, when ``by_category``
        is set, ``categories``, mapping each category name to the rows
        for that category (still sorted by SKU).
    """
    rows = []
    total_value = 0.0
    categories: dict[str, list[dict]] = {}
    for item in store.list_items():
        value = item.qty * item.unit_price
        total_value += value
        row = {
            "sku": item.sku,
            "name": item.name,
            "qty": item.qty,
            "unit_price": item.unit_price,
            "value": value,
        }
        rows.append(row)
        categories.setdefault(item.category, []).append(row)
    if by_category:
        return {"categories": categories, "total_value": total_value}
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


def low_stock_by_category(store: Store,
                          threshold: int = DEFAULT_THRESHOLD
                          ) -> dict[str, list[dict]]:
    """The low-stock listing split up one shelf area at a time.

    Returns:
        A dict mapping category name to that category's low-stock rows
        (the same sku/name/qty rows as ``low_stock``, sorted by SKU).
        A category with nothing running low is left out entirely, so an
        empty dict means the whole stockroom is above the threshold.
    """
    grouped: dict[str, list[dict]] = {}
    for item in store.list_items():
        if item.qty <= threshold:
            grouped.setdefault(item.category, []).append({
                "sku": item.sku,
                "name": item.name,
                "qty": item.qty,
            })
    return grouped


def search_items(store: Store, query: str) -> list[dict]:
    """Items whose name or SKU contains ``query``.

    The match is a case-insensitive substring on either field, so
    "widget" finds "Steel Widget" and "gad" finds GAD-1.

    Returns:
        A list of dicts (sku, name, qty), sorted by SKU.  Empty when
        nothing matches.
    """
    needle = query.lower()
    rows = []
    for item in store.list_items():
        if needle in item.name.lower() or needle in item.sku.lower():
            rows.append({
                "sku": item.sku,
                "name": item.name,
                "qty": item.qty,
            })
    return rows


def _normalize_date(date: str) -> str:
    """Zero-pad a YYYY-M-D date so it matches and sorts as YYYY-MM-DD.

    Order dates are stored exactly as typed and people routinely leave
    the leading zeros off ("2026-1-5").  Anything that is not three
    numeric parts is returned unchanged, so an odd date still shows up
    in reports rather than breaking them.
    """
    parts = date.split("-")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        return date
    year, month, day = parts
    return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"


def monthly_orders(store: Store, month: str) -> list[dict]:
    """All orders placed in the given month.

    Args:
        month: a prefix like "2026-01"; any order dated within that
            month is included, regardless of status.  Order dates are
            zero-padded before matching, so one dated "2026-1-5" counts
            toward January just like "2026-01-05".

    Returns:
        A list of dicts (id, sku, qty, date, status), oldest first.
        ``date`` is the date as originally recorded.
    """
    rows = []
    for order in store.orders:
        if _normalize_date(order.date).startswith(month):
            rows.append({
                "id": order.id,
                "sku": order.sku,
                "qty": order.qty,
                "date": order.date,
                "status": order.status,
            })
    rows.sort(key=lambda row: _normalize_date(row["date"]))
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
        A list of dicts (sku, supplier_id, qty, suggested_qty,
        lead_time_days), sorted by SKU.  ``lead_time_days`` is the
        supplier's lead time, so slow suppliers stand out.
    """
    rows = []
    for item in store.list_items():
        if item.qty < threshold and item.supplier_id is not None:
            supplier = store.suppliers.get(item.supplier_id)
            rows.append({
                "sku": item.sku,
                "supplier_id": item.supplier_id,
                "qty": item.qty,
                "suggested_qty": threshold - item.qty,
                "lead_time_days": supplier.lead_time_days if supplier else 0,
            })
    return rows
