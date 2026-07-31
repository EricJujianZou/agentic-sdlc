"""Read-only reports over a loaded Store.

Every function here takes a ``Store`` and returns plain data (lists and
dicts); formatting for the terminal happens in the CLI.  Nothing in this
module mutates state, so the CLI never saves after running a report.
"""

from .dates import parse_date, sort_key
from .models import DEFAULT_CATEGORY, STATUS_PENDING
from .store import Store

# Items at or around this stock level are worth another look.  The CLI
# lets the user override it per invocation with --threshold.
DEFAULT_THRESHOLD = 5


def _in_month(date: str, month: str) -> bool:
    """True when *date* falls in *month* ("2026-01"), however it is typed."""
    parsed = parse_date(date)
    if parsed is None:
        return str(date).startswith(month)
    return f"{parsed.year:04d}-{parsed.month:02d}" == month


def stock_report(store: Store, by_category: bool = False,
                 warehouse: str | None = None) -> dict:
    """Full stock listing plus total inventory value.

    Args:
        by_category: group the rows by shelf area instead of returning
            one flat list.
        warehouse: count only the units held in this warehouse, and
            leave out items it holds none of.  The default counts every
            warehouse, as reports always have.

    Returns:
        A dict with ``total_value`` (the value of the whole stockroom)
        plus either ``rows`` -- one entry per item, sorted by SKU, each
        carrying sku/name/qty/unit_price and the line ``value`` (qty
        times unit price) -- or, with ``by_category``, ``categories``
        mapping each category name to its own list of those rows.
    """
    rows = []
    categories: dict[str, list[dict]] = {}
    total_value = 0.0
    for item in store.list_items():
        qty = item.qty if warehouse is None else item.qty_in(warehouse)
        if warehouse is not None and qty == 0:
            continue
        value = qty * item.unit_price
        total_value += value
        row = {
            "sku": item.sku,
            "name": item.name,
            "qty": qty,
            "unit_price": item.unit_price,
            "value": value,
            "category": item.category,
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
                          threshold: int = DEFAULT_THRESHOLD) -> dict:
    """Low-stock rows grouped by shelf area, for walking the room.

    Returns:
        A dict of category name -> the same rows the flat low-stock
        report produces, sorted by SKU.  Categories with nothing running
        low are left out entirely.
    """
    grouped: dict[str, list[dict]] = {}
    for row in low_stock(store, threshold=threshold):
        category = store.get_item(row["sku"]).category
        grouped.setdefault(category, []).append(row)
    return grouped


def search_items(store: Store, query: str) -> list[dict]:
    """Items whose name or SKU contains *query*, case-insensitively.

    Returns:
        A list of dicts (sku, name, qty), sorted by SKU.  Empty when
        nothing matches.
    """
    needle = query.lower()
    return [
        {"sku": item.sku, "name": item.name, "qty": item.qty}
        for item in store.list_items()
        if needle in item.name.lower() or needle in item.sku.lower()
    ]


def monthly_orders(store: Store, month: str) -> list[dict]:
    """All orders placed in the given month.

    Args:
        month: a month like "2026-01"; any order dated within that month
            is included, regardless of status and regardless of how the
            date was typed ("2026-1-5" is January too).

    Returns:
        A list of dicts (id, sku, qty, date, status), oldest first.
    """
    rows = []
    for order in store.orders:
        if not _in_month(order.date, month):
            continue
        rows.append({
            "id": order.id,
            "sku": order.sku,
            "qty": order.qty,
            "date": order.date,
            "status": order.status,
        })
    rows.sort(key=lambda row: sort_key(row["date"]))
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
    threshold, minus whatever is already on the way on pending orders.
    Only items with a supplier are included, since there is nobody to
    order the rest from, and items the pending orders already cover are
    left out.

    Returns:
        A list of dicts (sku, supplier_id, qty, suggested_qty,
        lead_time_days), sorted by SKU.  The lead time is the supplier's,
        so slow suppliers stand out when deciding what to order first.
    """
    rows = []
    for item in store.list_items():
        if item.qty >= threshold or item.supplier_id is None:
            continue
        suggested = threshold - item.qty - pending_qty(store, item.sku)
        if suggested <= 0:
            continue
        supplier = store.suppliers.get(item.supplier_id)
        rows.append({
            "sku": item.sku,
            "supplier_id": item.supplier_id,
            "qty": item.qty,
            "suggested_qty": suggested,
            "lead_time_days": supplier.lead_time_days if supplier else 0,
        })
    return rows


def turnover(store: Store) -> dict:
    """Units shipped out per category per month.

    Returns:
        A mapping of category name -> {"YYYY-MM": units}.  Only real
        shipments count: transfers between warehouses are internal moves
        and stock coming in is not turnover at all.
    """
    result: dict[str, dict[str, int]] = {}
    for shipment in store.shipments:
        item = store.items.get(shipment["sku"])
        category = item.category if item else DEFAULT_CATEGORY
        parsed = parse_date(shipment["date"])
        month = (parsed.strftime("%Y-%m") if parsed
                 else str(shipment["date"])[:7])
        by_month = result.setdefault(category, {})
        by_month[month] = by_month.get(month, 0) + shipment["qty"]
    return result


def pending_qty(store: Store, sku: str) -> int:
    """Units of *sku* still on the way on pending purchase orders."""
    return sum(order.outstanding for order in store.orders
               if order.sku == sku and order.status == STATUS_PENDING)
