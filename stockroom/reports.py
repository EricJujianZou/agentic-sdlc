"""Read-only reports over a loaded Store.

Every function here takes a ``Store`` and returns plain data (lists and
dicts); formatting for the terminal happens in the CLI.  Nothing in this
module mutates state, so the CLI never saves after running a report.
"""

import datetime

from . import dates
from .models import (STATUS_PENDING, STATUS_RECEIVED, normalize_sku,
                     percent_of, to_dollars)
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
    """The canonical YYYY-MM-DD spelling of a date, for sorting.

    Dates are stored zero-padded, so this is normally the date itself;
    anything odd enough not to parse is returned unchanged, so it still
    shows up in reports rather than breaking them.
    """
    return dates.normalize_stored(date)


def _in_month(date: str, month: str) -> bool:
    """Whether a stored date falls in the given "YYYY-MM" month.

    Both sides are read as numbers rather than compared as text, so
    neither an unpadded month nor an odd spelling on the date can put an
    order in the wrong month - or leave it out of every one.  A date
    that is not a real day belongs to no month.
    """
    try:
        value = dates.parse_date(date)
    except ValueError:
        return False
    return (value.year, value.month) == _month_parts(month)


def _month_parts(month: str) -> tuple[int, int] | None:
    """A "YYYY-MM" month as (year, month), or None when it is not one."""
    parts = month.split("-")
    if len(parts) != 2 or not all(part.isdigit() for part in parts):
        return None
    return int(parts[0]), int(parts[1])


def monthly_orders(store: Store, month: str) -> list[dict]:
    """All orders placed in the given month.

    Args:
        month: a month like "2026-01"; any order dated within that month
            is included, regardless of status.  The month and the order
            dates are matched as calendar dates rather than as text, so
            an order dated "2026-1-5" counts toward January just like
            "2026-01-05".

    Returns:
        A list of dicts (id, sku, qty, date, status), oldest first.
    """
    rows = []
    for order in store.orders:
        if _in_month(order.date, month):
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


def weekly_shipments(store: Store) -> dict[str, int]:
    """Units shipped, week by week.

    Pick-up rounds are planned by the week rather than the month, so the
    same shipment log ``turnover`` reads is counted off in ISO weeks: a
    week runs Monday to Sunday, and the year in the label is the ISO
    week-numbering year, which is why a shipment dated 2026-01-05 counts
    toward 2026-W02.

    Returns:
        A dict mapping the week label ("YYYY-Www", the week zero-padded
        to two digits) to the units shipped that week, oldest week
        first.  A week nothing left in is left out entirely, so an empty
        dict means nothing has gone out at all.
    """
    totals: dict[tuple[int, int], int] = {}
    for shipment in store.shipments:
        try:
            day = dates.parse_date(shipment.date)
        except ValueError:
            # A date we cannot read belongs to no week, the same way it
            # belongs to no month; skipping it beats inventing one.
            continue
        year, week, _ = day.isocalendar()
        totals[(year, week)] = totals.get((year, week), 0) + shipment.qty
    return {f"{year:04d}-W{week:02d}": units
            for (year, week), units in sorted(totals.items())}


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
        A list of dicts (id, qty, date, status), oldest first.  ``date``
        is the date as recorded; the sort zero-pads it first, so an
        order dated "2026-1-15" lands ahead of one dated "2026-01-20"
        rather than after it, the way plain text would have it.  Two
        orders placed on the same day keep the order they were placed
        in.  Empty when the SKU has never been ordered.
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
    rows.sort(key=lambda row: _normalize_date(row["date"]))
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
    cents = _order_total_cents(store, store.get_order(order_id))
    return {name: to_dollars(value) for name, value in cents.items()}


def _order_total_cents(store: Store, order) -> dict:
    """The ``order_total`` breakdown for one order, in whole cents.

    Kept apart from :func:`order_total` so a report that adds several
    orders up can total the cents and convert once at the end, rather
    than adding the rounded dollar figures back together.
    """
    item = store.get_item(order.sku)
    subtotal_cents = order.qty * item.unit_price_cents
    discount_cents = percent_of(subtotal_cents,
                                store.get_discount(item.category))
    tax_cents = percent_of(subtotal_cents - discount_cents, store.tax_rate)
    return {
        "subtotal": subtotal_cents,
        "discount": discount_cents,
        "tax": tax_cents,
        "total": subtotal_cents - discount_cents + tax_cents,
    }


def monthly_revenue(store: Store, month: str) -> dict:
    """What one month's completed orders came to.

    Only orders that were received count: one still pending has not been
    paid for yet and a cancelled one never will be.  Each order is
    priced the same way its invoice is - current unit price, category
    discount off, tax on the rest - so the two always agree.

    Args:
        month: a month like "2026-07"; order dates are matched as
            calendar dates, same as ``monthly_orders``.

    Returns:
        A dict with ``rows``, one dict per counted order (id, sku,
        total) oldest first, and ``total``, the dollar sum of those row
        totals.  A month with nothing received gives no rows and a
        total of 0.0.  The sum is worked out in whole cents, so it
        matches the printed rows added up by hand.
    """
    counted = [order for order in store.orders
               if order.status == STATUS_RECEIVED
               and _in_month(order.date, month)]
    counted.sort(key=lambda order: _normalize_date(order.date))
    rows = []
    total_cents = 0
    for order in counted:
        order_cents = _order_total_cents(store, order)["total"]
        total_cents += order_cents
        rows.append({
            "id": order.id,
            "sku": order.sku,
            "total": to_dollars(order_cents),
        })
    return {"rows": rows, "total": to_dollars(total_cents)}


def supplier_on_time(store: Store) -> list[dict]:
    """How well each supplier keeps to the lead time they quoted us.

    A delivery is on time when it turned up no later than the lead time
    the supplier quoted, counted in whole days from the day the order
    was placed - one landing on the last day of that window still
    counts.  Only orders that were received *and* have an arrival day
    recorded can be judged: a pending order has not arrived, a cancelled
    one never will, and one received before we started noting the day
    tells us nothing.  The supplier judged is the one the ordered item
    is bought from.

    Returns:
        A list of dicts (supplier_id, total, on_time, pct), sorted by
        supplier id, where ``pct`` is the on-time share out of 100.  A
        supplier with nothing to judge is left out entirely, so an empty
        list means no delivery has been booked in with a date yet.
    """
    counted: dict[str, list[int]] = {}
    for order in store.orders:
        if order.status != STATUS_RECEIVED or not order.received_date:
            continue
        supplier_id = store.get_item(order.sku).supplier_id
        if supplier_id is None:
            continue
        placed = _as_date(order.date)
        arrived = _as_date(order.received_date)
        due = placed + datetime.timedelta(
            days=store.get_supplier(supplier_id).lead_time_days)
        tally = counted.setdefault(supplier_id, [0, 0])
        tally[0] += 1
        if arrived <= due:
            tally[1] += 1
    return [
        {
            "supplier_id": supplier_id,
            "total": counted[supplier_id][0],
            "on_time": counted[supplier_id][1],
            "pct": 100 * counted[supplier_id][1] / counted[supplier_id][0],
        }
        for supplier_id in sorted(counted)
    ]


def _as_date(date: str) -> datetime.date:
    """Read a stored date as a real date, so days can be counted off it."""
    return dates.parse_date(date)


# How long an order has been waiting, in whole days, split into the three
# bands the shelf is worried about.  The last band has no upper edge.
AGING_BUCKETS = ("0-7", "8-30", "31+")


def order_aging(store: Store,
                as_of: str | datetime.date) -> dict[str, list[dict]]:
    """How long the orders still outstanding have been waiting.

    An order's age is the whole days from the day it was placed up to
    ``as_of``, so one placed on the as-of day itself is 0 days old and
    lands in the first band.  Only pending orders are aged: a received
    order is no longer waiting and a cancelled one never will be.

    Args:
        as_of: the day to count up to, either a ``datetime.date`` or a
            date string, which is read the way any typed date is.

    Returns:
        A dict with one key per band in ``AGING_BUCKETS`` - always all
        three, so an empty band shows up as an empty list rather than
        going missing - each holding that band's orders (id, sku, qty,
        date) oldest first.
    """
    today = as_of if isinstance(as_of, datetime.date) else _as_date(as_of)
    buckets: dict[str, list[dict]] = {name: [] for name in AGING_BUCKETS}
    for order in store.orders:
        if order.status != STATUS_PENDING:
            continue
        age = (today - _as_date(order.date)).days
        if age <= 7:
            bucket = "0-7"
        elif age <= 30:
            bucket = "8-30"
        else:
            bucket = "31+"
        buckets[bucket].append({
            "id": order.id,
            "sku": order.sku,
            "qty": order.qty,
            "date": order.date,
        })
    for rows in buckets.values():
        rows.sort(key=lambda row: (row["date"], row["id"]))
    return buckets


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


#: Audit-trail operations whose ``sku`` is not a claim that we stock the
def summary(store: Store, threshold: int = DEFAULT_THRESHOLD) -> dict:
    """The day's numbers, gathered from the reports that already know them.

    This is the one-screen view: rather than working anything out afresh
    it calls the reports management would otherwise run one at a time,
    so the figures here and the figures there cannot drift apart.

    Returns:
        A dict with ``valuation`` (dollars, the whole stockroom),
        ``threshold`` and the ``low_stock`` SKUs at or below it (sorted
        by SKU), ``pending_orders``, ``top_category`` - the category
        with the most units shipped over all time, ``None`` when nothing
        has ever shipped - and ``events``, the length of the audit
        trail.
    """
    shipped = {category: sum(months.values())
               for category, months in turnover(store).items()}
    # Most units first; a tie goes to the name that sorts first, so the
    # same state always names the same category.
    top = min(shipped, key=lambda name: (-shipped[name], name), default=None)
    return {
        "valuation": stock_report(store)["total_value"],
        "threshold": threshold,
        "low_stock": [row["sku"] for row in low_stock(store, threshold)],
        "pending_orders": sum(1 for order in store.orders
                              if order.status == STATUS_PENDING),
        "top_category": top,
        "events": len(store.events),
    }


#: item: a supplier's catalogue is their list of what they can sell us,
#: so a SKU on it we have never bought is ordinary, not dangling.
CATALOG_OPS = ("catalog-add",)


def _unknown_item(store: Store, sku: str) -> bool:
    """Whether a recorded SKU names no item in the catalogue."""
    return normalize_sku(sku) not in store.items


def fsck(store: Store) -> list[str]:
    """Cross-check the state and describe everything that does not add up.

    Records point at each other by SKU and by supplier id, and nothing
    stops a bad sync (or a bug we have since fixed) leaving a pointer
    with nothing on the other end, or a shelf holding fewer than no
    units.  Neither shows up in a report - a stock listing simply skips
    an order it cannot price - so this looks for them on purpose.

    Returns:
        One message per problem found, in a stable order: the items
        first, then the orders, the shipments and the audit trail.  An
        empty list means the data is consistent.  Like everything else
        in this module it only reads: what to do about a dangling
        reference is a judgement call, and a check that quietly
        "repaired" one would be a worse thing to run nightly than one
        that just says what it found.
    """
    problems = []
    for item in store.list_items():
        for warehouse in sorted(item.quantities):
            qty = item.quantities[warehouse]
            if qty < 0:
                problems.append(
                    f"item {item.sku} has a negative quantity ({qty}) in "
                    f"warehouse {warehouse}"
                )
        if (item.supplier_id is not None
                and item.supplier_id not in store.suppliers):
            problems.append(
                f"item {item.sku} references unknown supplier "
                f"{item.supplier_id}"
            )
    for order in store.orders:
        if _unknown_item(store, order.sku):
            problems.append(
                f"order {order.id} references unknown item {order.sku}"
            )
        if (order.supplier_id is not None
                and order.supplier_id not in store.suppliers):
            problems.append(
                f"order {order.id} references unknown supplier "
                f"{order.supplier_id}"
            )
    for number, shipment in enumerate(store.shipments, 1):
        if _unknown_item(store, shipment.sku):
            problems.append(
                f"shipment {number} references unknown item {shipment.sku}"
            )
    for number, event in enumerate(store.events, 1):
        sku = (event.get("args") or {}).get("sku")
        op = event.get("op")
        if sku is None or op in CATALOG_OPS:
            continue
        if _unknown_item(store, sku):
            problems.append(
                f"event {number} ({op}) references unknown item {sku}"
            )
    return problems
