"""Read-only reports over a loaded Store.

Every function here takes a ``Store`` and returns plain data (lists and
dicts); formatting for the terminal happens in the CLI.  Nothing in this
module mutates state, so the CLI never saves after running a report.
"""

from .models import STATUS_PENDING, percent_of, to_dollars
from .store import Store

# Items at or around this stock level are worth another look.  The CLI
# lets the user override it per invocation with --threshold.
DEFAULT_THRESHOLD = 5


def stock_report(store: Store,
                 by_category: bool = False,
                 warehouse: str | None = None) -> dict:
    """Full stock listing plus total inventory value.

    Args:
        by_category: group the rows by shelf area instead of returning
            one flat list.
        warehouse: report on one warehouse alone - quantities, line
            values and the total cover only the units held there, and
            items with nothing in it are left out.  Left off (the
            default), the report covers every warehouse together.

    Returns:
        A dict with two keys.  ``total_value`` is the value of the whole
        stockroom.  The other key is ``rows``, a list with one entry per
        item (sorted by SKU) carrying sku/name/qty/unit_price and the
        line ``value`` (qty times unit price) - or, when ``by_category``
        is set, ``categories``, mapping each category name to the rows
        for that category (still sorted by SKU).  Both the line values
        and the total are worked out in whole cents, so they match a
        hand-added column to the cent.
    """
    rows = []
    total_cents = 0
    categories: dict[str, list[dict]] = {}
    for item in store.list_items():
        qty = item.qty if warehouse is None else item.qty_in(warehouse)
        if warehouse is not None and qty == 0:
            continue
        # Money is counted in whole cents: a price like 0.10 has no exact
        # form as a fraction of a dollar, so multiplying and adding those
        # up drifts off what the same column does on paper.
        value_cents = qty * item.unit_price_cents
        total_cents += value_cents
        row = {
            "sku": item.sku,
            "name": item.name,
            "qty": qty,
            "unit_price": item.unit_price,
            "value": to_dollars(value_cents),
        }
        rows.append(row)
        categories.setdefault(item.category, []).append(row)
    if by_category:
        return {"categories": categories,
                "total_value": to_dollars(total_cents)}
    return {"rows": rows, "total_value": to_dollars(total_cents)}


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


def turnover(store: Store) -> dict[str, dict[str, int]]:
    """Units shipped out per shelf area, month by month.

    This reads the shipment log, so it counts goods that actually left
    the building: walking stock between warehouses moves nothing out,
    and receiving stock or taking an order in moves it the other way -
    none of those show up here.

    Returns:
        A dict mapping category name to a dict of month ("YYYY-MM") to
        the units of that category shipped that month.  A category or
        month that shipped nothing is left out entirely, so an empty
        dict means nothing has gone out at all.
    """
    totals: dict[str, dict[str, int]] = {}
    for shipment in store.shipments:
        category = store.get_item(shipment.sku).category
        month = _normalize_date(shipment.date)[:7]
        months = totals.setdefault(category, {})
        months[month] = months.get(month, 0) + shipment.qty
    return totals


def price_changes(store: Store) -> list[dict]:
    """Every recorded price change, across every item.

    Returns:
        A list of dicts (sku, date, old, new), oldest first.  ``date``
        is the date as recorded; the sort zero-pads it first, so a
        change dated "2026-1-5" lands ahead of one dated "2026-01-10".
        Empty when no price has ever been changed.
    """
    rows = []
    for item in store.list_items():
        for entry in item.price_history:
            rows.append({
                "sku": item.sku,
                "date": entry["date"],
                "old": entry["old"],
                "new": entry["new"],
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


def order_total(store: Store, order_id: int) -> dict:
    """What one order comes to, broken down.

    The order is priced at the item's *current* unit price, then the
    discount rule for that item's category comes off (no rule means no
    discount), and the tax rate applies to what is left - you are not
    taxed on money you were never charged.  An unknown order id raises
    ``ValueError``, same as looking it up any other way.

    Returns:
        A dict of ``subtotal``, ``discount``, ``tax`` and ``total``, all
        in dollars.  Each line is worked out in whole cents, so the four
        add up exactly as printed.
    """
    order = store.get_order(order_id)
    item = store.get_item(order.sku)
    subtotal_cents = order.qty * item.unit_price_cents
    discount_cents = percent_of(subtotal_cents,
                                store.get_discount(item.category))
    tax_cents = percent_of(subtotal_cents - discount_cents, store.tax_rate)
    return {
        "subtotal": to_dollars(subtotal_cents),
        "discount": to_dollars(discount_cents),
        "tax": to_dollars(tax_cents),
        "total": to_dollars(subtotal_cents - discount_cents + tax_cents),
    }


def reorder_suggestions(store: Store,
                        threshold: int = DEFAULT_THRESHOLD) -> list[dict]:
    """Suggest order quantities for items running low.

    For each item the low report flags - stock at the threshold or below,
    the same test ``low_stock`` uses, so the two views always agree -
    suggest topping back up to the threshold, minus whatever is still on
    the way on that item's pending orders: orders that were received or
    cancelled count for nothing, and neither does the part of a pending
    order already delivered, since those units are on the shelf being
    counted already.  An item already at the threshold gets a row
    suggested at 0 rather than vanishing from under a low list that
    flagged it; the one item left out is one whose pending orders
    already cover the top-up, since the restock is on its way.  Only
    items with a supplier are included, since there is nobody to order
    the rest from.

    Returns:
        A list of dicts (sku, supplier_id, qty, suggested_qty,
        lead_time_days), sorted by SKU.  ``lead_time_days`` is the
        supplier's lead time, so slow suppliers stand out.
    """
    pending: dict[str, int] = {}
    for order in store.orders:
        if order.status == STATUS_PENDING:
            pending[order.sku] = pending.get(order.sku, 0) + order.outstanding
    rows = []
    for item in store.list_items():
        if item.qty <= threshold and item.supplier_id is not None:
            on_the_way = pending.get(item.sku, 0)
            suggested_qty = max(0, threshold - item.qty - on_the_way)
            if suggested_qty == 0 and on_the_way:
                continue
            supplier = store.suppliers.get(item.supplier_id)
            rows.append({
                "sku": item.sku,
                "supplier_id": item.supplier_id,
                "qty": item.qty,
                "suggested_qty": suggested_qty,
                "lead_time_days": supplier.lead_time_days if supplier else 0,
            })
    return rows
