"""Read-only reports over a loaded Store.

Every function here takes a ``Store`` and returns plain data (lists and
dicts); formatting for the terminal happens in the CLI.  Nothing in this
module mutates state, so the CLI never saves after running a report.
"""

import datetime
from decimal import ROUND_HALF_UP, Decimal

from .dates import parse_date, sort_key
from .models import DEFAULT_CATEGORY, STATUS_PENDING, STATUS_RECEIVED
from .money import format_money, to_cents, to_dollars
from .store import Store

# Items at or around this stock level are worth another look.  The CLI
# lets the user override it per invocation with --threshold.
DEFAULT_THRESHOLD = 5


def _percent_of(cents: int, percent) -> int:
    """*percent* of an amount in cents, rounded to whole cents."""
    if not percent:
        return 0
    return int((Decimal(cents) * Decimal(str(percent)) / 100)
               .quantize(Decimal("1"), rounding=ROUND_HALF_UP))


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
    total_cents = 0
    for item in store.list_items():
        qty = item.qty if warehouse is None else item.qty_in(warehouse)
        if warehouse is not None and qty == 0:
            continue
        # Valuation is done in whole cents so totals come out exact.
        value_cents = qty * item.unit_price_cents
        total_cents += value_cents
        value = to_dollars(value_cents)
        row = {
            "sku": item.sku,
            "name": item.name,
            "qty": qty,
            "unit_price": item.unit_price,
            "value": value,
            "value_cents": value_cents,
            "category": item.category,
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
                "sku": order.sku,
                "qty": order.qty,
                "date": order.date,
                "status": order.status,
            })
    # Sort on parsed dates: legacy files spell them "2026-1-5", which
    # sorts wrongly as plain text.  Same-day orders keep the order they
    # were placed in.
    rows.sort(key=lambda row: sort_key(row["date"]))
    return rows


def reorder_suggestions(store: Store,
                        threshold: int = DEFAULT_THRESHOLD) -> list[dict]:
    """Suggest order quantities for items running low.

    For each item at or below the threshold -- the same items the
    low-stock report flags -- suggest topping back up to the threshold,
    minus whatever is already on the way on pending orders.
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
        # Same test as the low-stock report, so the two always agree.
        if item.qty > threshold or item.supplier_id is None:
            continue
        pending = pending_qty(store, item.sku)
        suggested = max(0, threshold - item.qty - pending)
        if suggested == 0 and pending:
            # Orders already on the way cover us; nothing to suggest.
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


def order_total(store: Store, order_id: int) -> dict:
    """What an order costs once discount and tax are applied.

    Returns:
        A dict with ``subtotal``, ``discount``, ``tax`` and ``total``,
        all dollar amounts, computed in whole cents so they are exact.
    """
    order = store.get_order(order_id)
    item = store.get_item(order.sku)
    subtotal = order.qty * item.unit_price_cents
    discount = _percent_of(subtotal, store.get_discount(item.category))
    tax = _percent_of(subtotal - discount, store.tax_rate)
    return {
        "subtotal": to_dollars(subtotal),
        "discount": to_dollars(discount),
        "tax": to_dollars(tax),
        "total": to_dollars(subtotal - discount + tax),
    }


def monthly_revenue(store: Store, month: str) -> dict:
    """What the month's completed orders were worth.

    Returns:
        ``{"rows": [{"id", "sku", "total"}, ...], "total": dollars}`` --
        one row per received order dated in *month*, priced the same way
        the invoice is (category discount and tax at current prices).
        Pending and cancelled orders do not count.
    """
    rows = []
    total_cents = 0
    for order in store.orders:
        if order.status != STATUS_RECEIVED or not _in_month(order.date, month):
            continue
        breakdown = order_total(store, order.id)
        total_cents += to_cents(breakdown["total"])
        rows.append({"id": order.id, "sku": order.sku,
                     "total": breakdown["total"]})
    rows.sort(key=lambda row: row["id"])
    return {"rows": rows, "total": to_dollars(total_cents)}


def invoice_text(store: Store, order_id: int) -> str:
    """The invoice for one order as plain text.

    The layout is fixed and carries nothing run-dependent, so the same
    order always produces byte-identical output.
    """
    order = store.get_order(order_id)
    breakdown = order_total(store, order_id)
    lines = [
        f"Invoice for order {order.id}",
        f"SKU:      {order.sku}",
        f"Quantity: {order.qty}",
        f"Date:     {order.date}",
        "",
        f"Subtotal: {format_money(breakdown['subtotal'])}",
        f"Discount: {format_money(breakdown['discount'])}",
        f"Tax:      {format_money(breakdown['tax'])}",
        f"Total:    {format_money(breakdown['total'])}",
    ]
    return "\n".join(lines) + "\n"


def price_changes(store: Store) -> list[dict]:
    """Every recorded price change across all items, oldest first.

    Returns:
        A list of dicts (sku, date, old, new) with the prices in
        dollars, sorted by date.
    """
    rows = []
    for item in store.list_items():
        for entry in item.price_history:
            rows.append({"sku": item.sku, **entry})
    rows.sort(key=lambda row: sort_key(row["date"]))
    return rows


def supplier_on_time(store: Store) -> list[dict]:
    """How often each supplier delivered inside its lead time.

    An order is on time when it arrived at most ``lead_time_days`` after
    the day it was placed; arriving exactly on the last day of that
    window still counts.  Only received orders with a recorded arrival
    date count at all.

    Returns:
        A list of dicts (supplier_id, total, on_time, pct), sorted by
        supplier id.  Suppliers with nothing to count are left out.
    """
    tally: dict[str, list[int]] = {}
    for order in store.orders:
        if order.status != STATUS_RECEIVED or not order.received_date:
            continue
        item = store.items.get(order.sku)
        supplier_id = item.supplier_id if item else None
        if supplier_id is None:
            continue
        placed = parse_date(order.date)
        arrived = parse_date(order.received_date)
        if placed is None or arrived is None:
            continue
        supplier = store.suppliers.get(supplier_id)
        lead = supplier.lead_time_days if supplier else 0
        counts = tally.setdefault(supplier_id, [0, 0])
        counts[0] += 1
        if (arrived - placed).days <= lead:
            counts[1] += 1
    return [{"supplier_id": sid,
             "total": total,
             "on_time": on_time,
             "pct": 100.0 * on_time / total}
            for sid, (total, on_time) in sorted(tally.items())]


AGING_BUCKETS = ("0-7", "8-30", "31+")


def order_aging(store: Store, as_of=None) -> dict:
    """Pending orders bucketed by how long they have been open.

    Args:
        as_of: an ISO date string or a ``datetime.date``; defaults to
            today.

    Returns:
        A dict with exactly the keys "0-7", "8-30" and "31+", each a
        list of order dicts (id, sku, qty, date).
    """
    if as_of is None:
        as_of = datetime.date.today()
    reference = parse_date(as_of)
    if reference is None:
        raise ValueError(f"invalid date: {as_of}")
    buckets: dict[str, list[dict]] = {name: [] for name in AGING_BUCKETS}
    for order in store.orders:
        if order.status != STATUS_PENDING:
            continue
        placed = parse_date(order.date)
        if placed is None:
            continue
        age = (reference - placed).days
        if age <= 7:
            name = "0-7"
        elif age <= 30:
            name = "8-30"
        else:
            name = "31+"
        buckets[name].append({"id": order.id, "sku": order.sku,
                              "qty": order.qty, "date": order.date,
                              "age_days": age})
    return buckets


def weekly_shipments(store: Store) -> dict:
    """Units shipped per ISO week.

    Returns:
        A mapping of week label ("2026-W28", ISO week-numbering year and
        zero-padded week) -> units shipped, oldest week first.  Weeks
        with no shipments do not appear.
    """
    weekly: dict[str, int] = {}
    for shipment in store.shipments:
        parsed = parse_date(shipment["date"])
        if parsed is None:
            continue
        year, week, _ = parsed.isocalendar()
        label = f"{year:04d}-W{week:02d}"
        weekly[label] = weekly.get(label, 0) + shipment["qty"]
    return {label: weekly[label] for label in sorted(weekly)}


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
